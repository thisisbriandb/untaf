"""
Offres publiées sur Werecruit (careers.werecruit.io) : PME, réseaux de
franchise, agences d'intérim et cabinets, environ 1 200 employeurs.

Collecte : le sitemap public (`/sitemap.xml`, ~20 000 offres datées), puis la
page de chaque offre nouvelle ou modifiée depuis moins de `MAX_AGE_DAYS`. La
page donne l'intitulé (h1), l'employeur, le contrat et le lieu (balises og:),
la date (dcterms.created) et le texte de l'annonce. Le robots.txt autorise
tout (vérifié le 17/10/2026).

Candidature : le formulaire public n'a ni compte ni captcha, mais il exige
toujours la civilité (Madame, Monsieur, Mx) et une case par laquelle le
candidat accepte que l'employeur garde ses données deux ans, souvent avec des
questions propres à l'employeur. Alice ne remplit jamais la civilité et ne
consent jamais à la place du candidat : ces offres passent par l'extension,
le dossier prêt. Elles ne doivent pas évincer celles où Alice envoie
elle-même : voir `feasibility.direct_first`.

Réutilisation : pas de licence ouverte. Les offres servent à Alice pour le
candidat, avec le lien vers la page Werecruit, mais ne sont pas republiées
sur Alice Community.

Écoles (Walter Learning, ESCAM…) : elles recrutent des élèves pour leurs
formations en alternance, pas des salariés. Écartées.

Politesse : une collecte par jour ; une page par seconde, au plus
`MAX_READS_PER_RUN` par passage.
"""

import asyncio
import html as html_lib
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.agents.discovery.deduplicator import compute_fingerprint
from app.agents.discovery.france_travail_task import _get_or_create_company
from app.agents.discovery.qualification import heuristic_qualify
from app.database import async_session
from app.models.job_posting import (
    ApplyChannel, ApplyComplexity, ContractType, JobPosting, PostingStatus, RemotePolicy,
)

logger = logging.getLogger(__name__)

BASE = "https://careers.werecruit.io"
SITEMAP = f"{BASE}/sitemap.xml"
#: Préfixe d'`external_id` : suivi de l'identifiant court de l'offre.
PREFIX = "werecruit:"
DOMAIN_SUFFIX = ".werecruit.source"
OFFER_URL = re.compile(rf"^{re.escape(BASE)}/fr/([a-z0-9-]+)/offres/[a-z0-9-]*?-?([0-9a-f]{{6}})$")
#: Écoles qui recrutent des élèves (alternance) : pas des offres d'emploi.
SCHOOL_TENANTS = {"walter-learning", "escam-alternance"}
#: Au-delà, une offre encore au sitemap est le plus souvent pourvue.
MAX_AGE_DAYS = 60
PAUSE_S = 1.0
MAX_READS_PER_RUN = 1500
USER_AGENT = "AliceBot/1.0 (+https://www.alice-agent.fr ; offres d'emploi, une visite par jour)"

_ENTRY = re.compile(r"<url>\s*<loc>\s*([^<\s]+)\s*</loc>(?:\s*<lastmod>\s*([^<\s]+)\s*</lastmod>)?")
_TAGS = re.compile(r"<[^>]+>")
_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)
_OG_TITLE = re.compile(r'<meta\s+content="([^"]*)"\s+property="og:title"', re.DOTALL)
_CREATED = re.compile(r'<meta\s+name="dcterms\.created"\s+content="(\d{4}-\d{2}-\d{2})"')
_CONTRACT = re.compile(r"Type de contrat\s*:(?:&nbsp;|\s)*</span>\s*([^<]+?)\s*</p>", re.IGNORECASE)
_FORM = re.compile(r'<form[^>]*id="form"[\s\S]*?</form>')
_CUSTOM_QUESTION = re.compile(r'name="question:([0-9a-f-]{36})')


@dataclass
class WerecruitOffer:
    code: str
    tenant: str
    url: str
    title: str
    company: str
    contract: ContractType
    location: str | None
    description: str
    posted: date | None
    #: Le formulaire est sur la page (sinon l'offre renvoie ailleurs).
    has_form: bool = False
    #: Ce que seul le candidat peut remplir.
    questions: list[str] = field(default_factory=list)


def _text(fragment: str | None) -> str:
    s = re.sub(r"<\s*(br|/p|/li|/h\d)\s*/?>", "\n", fragment or "", flags=re.IGNORECASE)
    s = re.sub(r"<li[^>]*>", "• ", s, flags=re.IGNORECASE)
    s = html_lib.unescape(_TAGS.sub("", s)).replace("\xa0", " ")
    s = "\n".join(line.strip() for line in s.splitlines())
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", s)).strip()


def contract_of(label: str | None, title: str) -> ContractType:
    t, c = title.lower(), (label or "").lower()
    if re.search(r"apprenti|alternan|professionnalisation", f"{t} {c}"):
        return ContractType.ALTERNANCE
    if re.search(r"\bstage|stagiaire", f"{t} {c}"):
        return ContractType.STAGE
    if "intérim" in c or "interim" in c or "temporaire" in c:
        return ContractType.INTERIM
    if "cdi" in c:
        return ContractType.CDI
    if "cdd" in c:
        return ContractType.CDD
    if re.search(r"freelance|indépendant|libéral|mandataire|franchis", c):
        return ContractType.FREELANCE
    return ContractType.UNKNOWN


def parse_sitemap(xml: str, now: datetime | None = None) -> dict[str, tuple[str, datetime | None]]:
    """Code de l'offre → (adresse, date de modification), offres récentes seulement."""
    now = now or datetime.now(UTC)
    out: dict[str, tuple[str, datetime | None]] = {}
    for loc, mod in _ENTRY.findall(xml):
        m = OFFER_URL.match(loc)
        if not m or m.group(1) in SCHOOL_TENANTS:
            continue
        try:
            modified = datetime.fromisoformat(mod) if mod else None
        except ValueError:
            modified = None
        if modified and modified.tzinfo is None:
            modified = modified.replace(tzinfo=UTC)
        if modified and now - modified > timedelta(days=MAX_AGE_DAYS):
            continue
        out[m.group(2)] = (loc, modified)
    return out


def parse_offer(url: str, page: str) -> WerecruitOffer | None:
    """La page d'une offre → l'offre, ou None si elle n'est pas lisible."""
    m = OFFER_URL.match(url)
    if not m:
        return None
    h1 = _H1.search(page)
    title = re.sub(r"\s+", " ", html_lib.unescape(_TAGS.sub("", h1.group(1)))).strip() if h1 else ""
    if not title:
        return None
    # « <intitulé> - <contrat> à <lieu> | <employeur> »
    og = html_lib.unescape(_OG_TITLE.search(page).group(1)) if _OG_TITLE.search(page) else ""
    head, _, company = og.rpartition(" | ")
    location = head.rsplit(" à ", 1)[1].strip() if " à " in head else None
    contract = _CONTRACT.search(page)
    created = _CREATED.search(page)

    start = page.find("description-subtitle")
    start = page.rfind("<div", 0, start) if start > 0 else -1
    end = page.find('<form', start) if start >= 0 else -1
    description = _text(page[start:end if end > 0 else None]) if start >= 0 else ""

    offer = WerecruitOffer(
        code=m.group(2),
        tenant=m.group(1),
        url=url,
        title=title[:500],
        company=(company or "").strip(),
        contract=contract_of(html_lib.unescape(contract.group(1)) if contract else None, title),
        location=location,
        description=description[:12000],
        posted=date.fromisoformat(created.group(1)) if created else None,
    )
    form = _FORM.search(page)
    if form and 'name="Resume"' in form.group(0):
        offer.has_form = True
        body = form.group(0)
        if re.search(r'name="civility"[^>]*required', body):
            offer.questions.append("civilité")
        if re.search(r'name="optin"[^>]*required', body):
            offer.questions.append("accord de conservation des données")
        custom = len(set(_CUSTOM_QUESTION.findall(body)))
        if custom:
            offer.questions.append(f"{custom} question(s) de l'employeur")
    return offer


# ── Enregistrement ────────────────────────────────────────────────────────


def _channel(o: WerecruitOffer) -> tuple[ApplyChannel, ApplyComplexity, dict]:
    if o.has_form:
        # Formulaire sur la page : l'extension le remplit, le candidat coche
        # lui-même civilité et accord, puis envoie.
        return ApplyChannel.WEB_FORM, ApplyComplexity.MEDIUM, {
            "apply_url": o.url, "questions": o.questions, "werecruit": {"tenant": o.tenant},
        }
    return ApplyChannel.EXTERNAL_LINK, ApplyComplexity.MEDIUM, {"apply_url": o.url}


def _fingerprint(domain: str, o: WerecruitOffer) -> str:
    return compute_fingerprint(domain, o.title, o.location, external_id=PREFIX + o.code)


async def persist(offers: list[WerecruitOffer]) -> int:
    saved = 0
    now = datetime.now(UTC)
    async with async_session() as session:
        for o in offers:
            company = await _get_or_create_company(session, o.company or o.tenant, suffix=DOMAIN_SUFFIX)
            text = f"{o.title}\n\n{o.description}"
            parsed = heuristic_qualify(o.title, text)
            parsed["contract_type"] = o.contract.value
            parsed["source"] = {"name": "Werecruit", "republish": False,
                                "posted": o.posted.isoformat() if o.posted else None}
            channel, complexity, contact = _channel(o)
            values = dict(
                title=o.title,
                description_raw=text,
                description_parsed=parsed,
                location=o.location,
                apply_url=o.url,
                apply_channel=channel,
                apply_complexity=complexity,
                contact_json=contact,
                contract_type=o.contract,
                remote_policy=RemotePolicy.ONSITE,
                tech_stack=parsed.get("tech_stack") or [],
                status=PostingStatus.ACTIVE,
            )
            await session.execute(
                pg_insert(JobPosting).values(
                    company_id=company.id,
                    external_id=PREFIX + o.code,
                    fingerprint=_fingerprint(company.domain, o),
                    source_url=o.url,
                    **values,
                ).on_conflict_do_update(
                    index_elements=["fingerprint"],
                    set_={**values, "last_seen_at": now},
                )
            )
            saved += 1
        await session.commit()
    return saved


async def collect(client: httpx.AsyncClient | None = None, limit: int | None = MAX_READS_PER_RUN) -> dict:
    """Collecte quotidienne. Ne lève pas : renvoie un rapport."""
    own = client is None
    client = client or httpx.AsyncClient(
        timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT},
    )
    try:
        res = await client.get(SITEMAP)
        if res.status_code != 200:
            return {"ok": False, "reason": f"sitemap {res.status_code}"}
        listed = parse_sitemap(res.text)
        if not listed:
            # Sitemap vide ou changé de forme : ne rien fermer sur cette base.
            return {"ok": False, "reason": "sitemap sans offre récente"}

        async with async_session() as session:
            known = dict((await session.execute(
                select(JobPosting.external_id, JobPosting.last_seen_at)
                .where(JobPosting.external_id.like(f"{PREFIX}%"))
            )).all())
        # Nouvelles, ou modifiées depuis notre dernière lecture ; les plus
        # récentes d'abord (le premier passage s'étale sur plusieurs jours).
        fresh = [c for c, (_, mod) in listed.items()
                 if PREFIX + c not in known or (mod and known[PREFIX + c] and mod > known[PREFIX + c])]
        fresh.sort(key=lambda c: listed[c][1] or datetime.min.replace(tzinfo=UTC), reverse=True)
        if limit is not None:
            fresh = fresh[:limit]
        seen = [PREFIX + c for c in listed if PREFIX + c in known and c not in fresh]

        offers: list[WerecruitOffer] = []
        for i, code in enumerate(fresh):
            if i:
                await asyncio.sleep(PAUSE_S)
            url = listed[code][0]
            try:
                page = await client.get(url)
            except httpx.HTTPError as e:
                logger.warning("Werecruit : %s illisible (%s)", url, type(e).__name__)
                continue
            if page.status_code != 200:
                continue
            offer = parse_offer(url, page.text)
            if offer:
                offers.append(offer)

        saved = await persist(offers)
        now = datetime.now(UTC)
        async with async_session() as session:
            if seen:
                await session.execute(
                    update(JobPosting).where(JobPosting.external_id.in_(seen)).values(last_seen_at=now)
                )
            # Plus au sitemap (ou trop ancienne) : retirée.
            await session.execute(
                update(JobPosting)
                .where(JobPosting.external_id.like(f"{PREFIX}%"))
                .where(JobPosting.status == PostingStatus.ACTIVE)
                .where(JobPosting.external_id.not_in([PREFIX + c for c in listed]))
                .values(status=PostingStatus.CLOSED)
            )
            await session.commit()
        with_form = sum(1 for o in offers if o.has_form)
        logger.info("Werecruit : %d offres récentes listées, %d lues, %d enregistrées (%d avec formulaire)",
                    len(listed), len(fresh), saved, with_form)
        return {"ok": True, "listed": len(listed), "read": len(fresh), "saved": saved,
                "with_form": with_form}
    except Exception as e:
        logger.error("Collecte Werecruit impossible : %s", e, exc_info=True)
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}
    finally:
        if own:
            await client.aclose()
