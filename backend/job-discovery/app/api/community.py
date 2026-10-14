"""
Alice Community : la liste publique des alternances, des stages et des
premiers emplois (CDI et CDD ouverts aux débutants).

Une page ouverte à tous (alice-agent.fr/communaute) et sa version Markdown,
publiée chaque jour dans un dépôt GitHub, sur le modèle des listes de stages
de Simplify. Chaque offre renvoie à l'annonce d'origine et propose d'y
postuler avec Alice : c'est la porte d'entrée, sans publicité.

Ce qui est montré reste sobre : intitulé, employeur, lieu, date et source.
Ni description ni coordonnées de recruteur. L'annonce d'origine reste la
référence, et sa source est citée.

Les offres collées par un candidat (IMPORT_PREFIX) restent privées, et un
employeur anonyme n'est pas listé : une ligne « Employeur non précisé » ne
dit rien à qui parcourt la liste.
"""

import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import or_, select

from app.agents.application.feasibility import apply_mode
from app.agents.discovery.aggregators import ATTRIBUTION, NOT_STUDENT, listing_kind, via_school
from app.agents.company_name import display_company
from app.agents.discovery.signals import contract_from_title, detect_job_family
from app.config import settings
from app.database import async_session
from app.models.company import Company
from app.models.external_listing import ExternalListing
from app.models.job_posting import IMPORT_PREFIX, ContractType, JobPosting, PostingStatus
from app.ratelimit import limited

router = APIRouter(prefix="/community", tags=["community"])

#: Une offre que la source ne liste plus depuis ce délai est sans doute pourvue.
STALE_AFTER = timedelta(days=10)
#: Au-delà, une offre encore en ligne a peu de chances d'être lue.
MAX_AGE = timedelta(days=60)
#: Badge « Nouveau ».
NEW_WITHIN = timedelta(days=2)
#: Plafond par type d'offre.
MAX_ROWS = {"alternance": 3000, "stage": 3000, "emploi": 6000}
CACHE_TTL = 15 * 60

Kind = Literal["alternance", "stage", "emploi"]
#: La liste GitHub reste celle des étudiants.
ListKind = Literal["alternance", "stage"]

_TITLE_RE = r"(alternan|apprenti|contrat pro|stage|stagiaire|intern)"

FAMILIES: dict[str, str] = {
    "software": "Tech & développement",
    "data": "Data",
    "engineering": "Ingénierie",
    "product": "Produit",
    "design": "Design",
    "marketing": "Marketing & communication",
    "sales": "Commerce & vente",
    "support": "Relation client",
    "finance": "Finance & comptabilité",
    "hr": "Ressources humaines",
    "legal": "Juridique",
    "ops": "Logistique & opérations",
    "construction": "BTP",
    "health": "Santé",
    "education": "Éducation",
    "unknown": "Autres métiers",
}


class CommunityOffer(BaseModel):
    id: str
    title: str
    company: str
    city: str
    kind: Kind
    family: str
    remote: str
    published: str
    is_new: bool
    #: Alice peut envoyer la candidature elle-même (e-mail, API publique).
    alice_sends: bool
    source: str
    url: str
    #: Mention exigée par l'agrégateur qui relaie l'offre (« Adzuna » → adzuna.fr).
    attribution_label: str | None = None
    attribution_url: str | None = None
    #: La même offre publiée dans d'autres villes : une seule ligne, « +N villes ».
    other_cities: int = 0
    #: Recrutement par une école ou un CFA pour une entreprise partenaire.
    via_school: bool = False


class CommunityList(BaseModel):
    updated_at: str
    total: int
    new_count: int
    offers: list[CommunityOffer]


# ── Mise en forme ──────────────────────────────────────────────────────────

_DEPT = re.compile(r"^\s*\d{2,3}\s*-\s*")
#: « 33610 Cestas » → « Cestas ».
_POSTCODE = re.compile(r"^\s*\d{5}\s+")
_SMALL = {"de", "du", "des", "la", "le", "les", "sur", "en", "sous", "lès", "d", "l"}
_ARRDT = re.compile(r"\s+(\d{1,2})\s*(e|er|ème)?(\s+arrondissement)?\s*$", re.I)


def clean_city(location: str | None) -> str:
    """« 75 - PARIS 08 » → « Paris », « 69 - Lyon 3e Arrondissement » → « Lyon »."""
    loc = _POSTCODE.sub("", _DEPT.sub("", (location or "").strip()))
    loc = loc.split(",")[0].split("·")[0].strip()
    loc = _ARRDT.sub("", loc)
    if loc.isupper() or loc.islower():
        parts = re.split(r"([\s\-'])", loc.lower())
        loc = "".join(
            w if (i > 0 and w in _SMALL) else w[:1].upper() + w[1:]
            for i, w in enumerate(parts)
        )
    return loc or "France"


def source_label(job: JobPosting) -> str:
    url = (job.source_url or "").lower()
    if job.external_id.startswith("lba:"):
        return "La bonne alternance"
    if "francetravail" in url or "pole-emploi" in url:
        return "France Travail"
    if job.external_id.startswith("inrae:"):
        return "INRAE"
    if "welcometothejungle" in url:
        return "Welcome to the Jungle"
    return "Site carrière"


#: Un poste ouvert aux débutants le dit : « débutant accepté », « jeune
#: diplômé », « première expérience », « 0 à 2 ans »…
_JUNIOR_RE = re.compile(
    r"d[ée]butant\w*|jeunes? dipl[ôo]m\w*|premi[èe]re exp[ée]rience|sans exp[ée]rience|"
    r"\bjunior\b|\b0 ?(à|a|-) ?[12] ans?\b|moins de (1|2|un|deux) ans? d'exp|\bgraduate\b|sortie? d'[ée]cole",
    re.I,
)
#: … et un poste qui ne l'est pas le dit aussi, dans l'intitulé.
_SENIOR_RE = re.compile(
    r"\b(senior|sr\.?|confirm[ée]e?s?|exp[ée]riment[ée]e?s?|expert\w*|lead|principal|head of|"
    r"directeur|directrice|manager|chef d'[ée]quipe)\b",
    re.I,
)
#: Au-delà, ce n'est plus un premier emploi.
FIRST_JOB_MAX_YEARS = 2


def is_first_job(job: JobPosting) -> bool:
    """
    CDI ou CDD accessible à un jeune diplômé. L'expérience exigée par la
    source (France Travail : « débutant accepté » = 0 an) prime ; sans elle,
    l'annonce doit dire qu'elle accepte les débutants.
    """
    title = job.title or ""
    if _SENIOR_RE.search(title):
        return False
    years = (job.description_parsed or {}).get("experience_years_required")
    if isinstance(years, (int, float)):
        return years <= FIRST_JOB_MAX_YEARS
    return bool(_JUNIOR_RE.search(f"{title} {(job.description_raw or '')[:3000]}"))


def offer_kind(job: JobPosting) -> Kind | None:
    """L'intitulé prime sur le champ contrat, peu fiable chez certaines sources."""
    if NOT_STUDENT.search(job.title or ""):
        return None
    titled = contract_from_title(job.title)
    if titled in ("alternance", "stage"):
        return titled
    if job.contract_type in (ContractType.ALTERNANCE, ContractType.STAGE):
        return job.contract_type.value
    if titled is None and job.contract_type in (ContractType.CDI, ContractType.CDD) and is_first_job(job):
        return "emploi"
    return None


def to_offer(job: JobPosting, company_name: str, now: datetime) -> CommunityOffer | None:
    company = display_company(company_name)
    kind = offer_kind(job)
    if not company or not kind:
        return None
    seen = job.first_seen_at or now
    return CommunityOffer(
        id=str(job.id),
        title=job.title.strip(),
        company=company,
        city=clean_city(job.location),
        kind=kind,
        family=FAMILIES.get(detect_job_family(job.title, job.tech_stack), FAMILIES["unknown"]),
        remote=job.remote_policy.value,
        published=seen.date().isoformat(),
        is_new=now - seen <= NEW_WITHIN,
        alice_sends=apply_mode(job) == "auto",
        source=source_label(job),
        url=job.apply_url or job.source_url,
        via_school=via_school(company_name, (job.description_raw or "")[:4000], job.title),
    )


#: Préfixe d'identifiant des offres d'agrégateurs (table external_listings).
LISTING_PREFIX = "x:"


def listing_to_offer(listing: ExternalListing, now: datetime) -> CommunityOffer | None:
    company = display_company(listing.company)
    if not company or listing_kind(listing.title, listing.snippet or "", listing.kind) != listing.kind:
        return None
    seen = listing.published_at or listing.first_seen_at or now
    label, link = ATTRIBUTION.get(listing.source, (listing.source.capitalize(), listing.url))
    return CommunityOffer(
        id=f"{LISTING_PREFIX}{listing.id}",
        title=listing.title.strip(),
        company=company,
        city=clean_city(listing.location),
        kind=listing.kind,
        family=FAMILIES.get(detect_job_family(listing.title), FAMILIES["unknown"]),
        remote="unknown",
        published=seen.date().isoformat(),
        is_new=now - seen <= NEW_WITHIN,
        alice_sends=False,
        source=label,
        url=listing.url,
        attribution_label=label,
        attribution_url=link,
        via_school=via_school(listing.company, listing.snippet or "", listing.title),
    )


_GENDER = re.compile(r"\(?\b[hf]\s*/\s*[hf]\b\)?|\(e\)|\(ne\)|\(se\)", re.I)


def dedup_key(offer: CommunityOffer) -> tuple[str, str, str]:
    """« Chargé(e) marketing H/F » et « Chargé marketing » chez le même employeur : une offre."""
    def norm(text: str) -> str:
        t = unicodedata.normalize("NFD", _GENDER.sub(" ", text)).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()
    return norm(offer.company), norm(offer.title), norm(offer.city)


# ── Lecture, mise en cache ─────────────────────────────────────────────────

_cache: dict[str, tuple[float, CommunityList]] = {}


async def load_offers(now: datetime | None = None) -> CommunityList:
    now = now or datetime.now(timezone.utc)
    async with async_session() as session:
        rows = (await session.execute(
            select(JobPosting, Company.name)
            .join(Company, JobPosting.company_id == Company.id)
            .where(JobPosting.status == PostingStatus.ACTIVE)
            .where(JobPosting.external_id.not_like(f"{IMPORT_PREFIX}%"))
            .where(JobPosting.last_seen_at >= now - STALE_AFTER)
            .where(JobPosting.first_seen_at >= now - MAX_AGE)
            .where(or_(
                JobPosting.contract_type.in_([
                    ContractType.ALTERNANCE, ContractType.STAGE, ContractType.CDI, ContractType.CDD,
                ]),
                JobPosting.title.op("~*")(_TITLE_RE),
            ))
            .order_by(JobPosting.first_seen_at.desc())
            .limit(sum(MAX_ROWS.values()) * 2)
        )).all()

        listings = (await session.execute(
            select(ExternalListing)
            .where(ExternalListing.last_seen_at >= now - STALE_AFTER)
            .where(or_(
                ExternalListing.published_at.is_(None),
                ExternalListing.published_at >= now - MAX_AGE,
            ))
            .order_by(ExternalListing.published_at.desc().nullslast())
            .limit(MAX_ROWS["alternance"] + MAX_ROWS["stage"])
        )).scalars().all()

    # Les offres d'Alice d'abord : à doublon égal, c'est la version où elle
    # sait postuler (ou dont la source d'origine est connue) qui reste.
    candidates = [to_offer(job, name, now) for job, name in rows]
    candidates += [listing_to_offer(l, now) for l in listings]

    offers: list[CommunityOffer] = []
    seen: set[tuple[str, str, str]] = set()
    #: (employeur, intitulé) → première ligne : une offre déclinée ville par
    #: ville n'occupe qu'une ligne, qui compte les autres villes.
    first: dict[tuple[str, str], CommunityOffer] = {}
    per_kind: dict[str, int] = {}
    for offer in candidates:
        if not offer:
            continue
        key = dedup_key(offer)
        if key in seen:
            continue
        seen.add(key)
        head = first.get(key[:2])
        if head:
            head.other_cities += 1
            continue
        if per_kind.get(offer.kind, 0) >= MAX_ROWS[offer.kind]:
            continue
        per_kind[offer.kind] = per_kind.get(offer.kind, 0) + 1
        first[key[:2]] = offer
        offers.append(offer)
    # Plus récentes d'abord ; à date égale, les employeurs directs avant les CFA.
    offers.sort(key=lambda o: (o.published, not o.via_school), reverse=True)

    return CommunityList(
        updated_at=now.isoformat(timespec="minutes"),
        total=len(offers),
        new_count=sum(o.is_new for o in offers),
        offers=offers,
    )


async def cached_offers() -> CommunityList:
    hit = _cache.get("all")
    if hit and time.monotonic() - hit[0] < CACHE_TTL:
        return hit[1]
    data = await load_offers()
    _cache["all"] = (time.monotonic(), data)
    return data


def _filter(data: CommunityList, kinds: tuple[str, ...]) -> CommunityList:
    offers = [o for o in data.offers if o.kind in kinds]
    return CommunityList(
        updated_at=data.updated_at, total=len(offers),
        new_count=sum(o.is_new for o in offers), offers=offers,
    )


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t.lower()).strip()


class Facet(BaseModel):
    name: str
    count: int


class CommunityPage(BaseModel):
    """Une page de résultats, avec de quoi afficher les filtres."""
    updated_at: str
    kind: Kind
    #: Offres de ce type, avant filtres.
    total: int
    new_count: int
    alice_count: int
    #: Métiers présents (avec les autres filtres appliqués), du plus fourni au moins.
    families: list[Facet]
    #: Offres qui répondent aux filtres.
    matched: int
    page: int
    per_page: int
    offers: list[CommunityOffer]


def search(
    data: CommunityList, kind: Kind, *, q: str = "", city: str = "", family: str | None = None,
    alice: bool = False, new: bool = False, direct: bool = False, page: int = 1, per_page: int = 50,
) -> CommunityPage:
    of_kind = [o for o in data.offers if o.kind == kind]
    nq, nc = _norm(q), _norm(city)
    narrowed = [
        o for o in of_kind
        if (not alice or o.alice_sends) and (not new or o.is_new) and (not direct or not o.via_school)
        and (not nq or nq in _norm(f"{o.title} {o.company}"))
        and (not nc or nc in _norm(o.city))
    ]
    counts: dict[str, int] = {}
    for o in narrowed:
        counts[o.family] = counts.get(o.family, 0) + 1
    families = sorted(counts.items(), key=lambda kv: (kv[0] == FAMILIES["unknown"], -kv[1]))
    matched = [o for o in narrowed if not family or o.family == family]
    start = (page - 1) * per_page
    return CommunityPage(
        updated_at=data.updated_at,
        kind=kind,
        total=len(of_kind),
        new_count=sum(o.is_new for o in of_kind),
        alice_count=sum(o.alice_sends for o in of_kind),
        families=[Facet(name=n, count=c) for n, c in families],
        matched=len(matched),
        page=page,
        per_page=per_page,
        offers=matched[start:start + per_page],
    )


_public = [Depends(limited("community", anonymous=600, user=1200, overall=60000))]


@router.get("/recherche", response_model=CommunityPage, dependencies=_public)
async def community_search(
    kind: Kind = Query(default="alternance"),
    q: str = Query(default="", max_length=100),
    city: str = Query(default="", max_length=100),
    family: str | None = Query(default=None, max_length=100),
    alice: bool = False,
    new: bool = False,
    direct: bool = False,
    page: int = Query(default=1, ge=1, le=500),
    per_page: int = Query(default=50, ge=1, le=100),
):
    return search(
        await cached_offers(), kind, q=q, city=city, family=family,
        alice=alice, new=new, direct=direct, page=page, per_page=per_page,
    )


@router.get("/offres/{offer_id}", response_model=CommunityOffer, dependencies=_public)
async def community_offer(offer_id: str):
    """Une offre précise : le lien « Avec Alice » de la liste GitHub."""
    for o in (await cached_offers()).offers:
        if o.id == offer_id:
            return o
    raise HTTPException(404, "Offre introuvable ou retirée")


@router.get("/offres", response_model=CommunityList, dependencies=_public)
async def community_offers(kind: Kind | None = Query(default=None)):
    """
    Liste complète d'un type d'offre. Sans type : alternances et stages, comme
    avant l'arrivée des premiers emplois (trop nombreux pour une seule réponse).
    """
    return _filter(await cached_offers(), (kind,) if kind else ("alternance", "stage"))


# ── Version Markdown (dépôt GitHub) ────────────────────────────────────────


def _cell(text: str) -> str:
    return text.replace("|", "∣").replace("\n", " ").strip()


def site_url() -> str:
    front = settings.frontend_url.strip().rstrip("/")
    return front if front.startswith("http") and "localhost" not in front else "https://alice-agent.fr"


def render_markdown(data: CommunityList, kind: ListKind) -> str:
    site = site_url()
    label = "Alternances" if kind == "alternance" else "Stages"
    season = _season(datetime.fromisoformat(data.updated_at))
    updated = datetime.fromisoformat(data.updated_at).strftime("%d/%m/%Y")
    lines = [
        f"# {label} {season} · Alice Community",
        "",
        f"Les offres d'{'alternance' if kind == 'alternance' else 'stage'} en France, "
        "rassemblées chaque jour par [Alice](" + site + "?utm_source=github&utm_medium=liste) "
        "depuis France Travail, La bonne alternance, les sites carrière des entreprises "
        "et des agrégateurs comme Adzuna.",
        "",
        f"**{data.total} offres** · **{data.new_count} nouvelles** ces deux derniers jours "
        f"· mise à jour le {updated}",
        "",
        f"> Postuler à la main, une par une, c'est un travail à plein temps. "
        f"[Alice]({site}/communaute?utm_source=github&utm_medium=liste) adapte ton CV et ta lettre "
        "à chaque offre et peut envoyer la candidature pour toi. ⚡ = Alice l'envoie elle-même.",
        "",
        f"Version filtrable : {site}/communaute",
        "",
    ]
    by_family: dict[str, list[CommunityOffer]] = {}
    for o in data.offers:
        by_family.setdefault(o.family, []).append(o)
    order = sorted(by_family, key=lambda f: (f == FAMILIES["unknown"], -len(by_family[f])))
    lines.append("## Sommaire")
    lines.append("")
    for fam in order:
        anchor = re.sub(r"[^\w\- ]", "", fam.lower()).strip().replace(" ", "-")
        lines.append(f"- [{fam}](#{anchor}) ({len(by_family[fam])})")
    lines.append("")
    for fam in order:
        lines += [f"## {fam}", "", "| Entreprise | Poste | Lieu | Postuler | Publiée |", "|---|---|---|---|---|"]
        for o in by_family[fam]:
            new = "🆕 " if o.is_new else ""
            school = " · _via un CFA_" if o.via_school else ""
            bolt = " ⚡" if o.alice_sends else ""
            via = f" via [{o.attribution_label}]({o.attribution_url})" if o.attribution_label else ""
            apply = (
                f"[Annonce]({o.url}){via} · "
                f"[Avec Alice{bolt}]({site}/communaute?offre={o.id}&utm_source=github&utm_medium=liste)"
            )
            date = datetime.fromisoformat(o.published).strftime("%d/%m")
            more = f" (+{o.other_cities} villes)" if o.other_cities > 1 else (" (+1 ville)" if o.other_cities else "")
            lines.append(
                f"| **{_cell(o.company)}** | {new}{_cell(o.title)}{school} | {_cell(o.city)}{more} | {apply} | {date} |"
            )
        lines.append("")
    lines += [
        "---",
        "",
        f"Source des offres citée sur chaque annonce. Une offre pourvue ou une erreur ? "
        f"Ouvre une issue. Liste générée par [Alice]({site}).",
        "",
    ]
    return "\n".join(lines)


def _season(now: datetime) -> str:
    """La rentrée visée : à partir de septembre, on cherche pour l'année suivante."""
    return str(now.year + 1 if now.month >= 9 else now.year)


@router.get("/liste.md", response_class=PlainTextResponse, dependencies=_public)
async def community_markdown(kind: ListKind = Query(default="alternance")):
    return PlainTextResponse(
        render_markdown(_filter(await cached_offers(), (kind,)), kind),
        media_type="text/markdown; charset=utf-8",
    )
