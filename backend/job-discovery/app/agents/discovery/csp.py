"""
Offres de Choisir le service public (choisirleservicepublic.gouv.fr) : les
trois fonctions publiques (État, territoriale, hospitalière).

Collecte : le sitemap du site est figé (avril 2023). On lit donc la liste
publique des offres publiées ces dernières 48 heures
(`/nos-offres/filtres/date-de-publication/dernieres_48_heures/page/N/`,
20 offres par page), puis la page de chaque offre nouvelle : JSON-LD (titre,
employeur, lieu, date) et bloc « Postuler ». Le robots.txt n'interdit que
/wp-admin/ et les PDF d'offres (vérifié le 17/10/2026).

Réutilisation : contenus publics sous Licence Ouverte Etalab 2.0, à condition
de citer la source : l'offre renvoie toujours à sa page.

Candidature : environ six offres sur dix se postulent par e-mail (« Postuler
par mail »), avec un objet imposé « <référence> - <intitulé> » qu'Alice
reprend tel quel. Les autres renvoient au site de l'employeur ou demandent un
compte sur le site : le candidat y termine lui-même. Une offre qui exige des
pièces qu'Alice n'a pas (pièce d'identité, diplôme, CREP…) aussi : un dossier
incomplet desservirait le candidat. Les offres réservées aux fonctionnaires
ne sont pas retenues.

Les adresses sont souvent nominatives : elles ne servent qu'à envoyer, à la
demande du candidat, la candidature à l'offre où elles sont publiées. Jamais
affichées sur la liste publique, jamais utilisées pour une candidature
spontanée.

Politesse : une collecte par jour ; une page par seconde, au plus
`MAX_READS_PER_RUN` offres lues par passage.
"""

import asyncio
import html as html_lib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from urllib.parse import unquote

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.agents.discovery.contact_extract import is_valid_email
from app.agents.discovery.deduplicator import compute_fingerprint
from app.agents.discovery.france_travail_task import _get_or_create_company
from app.agents.discovery.qualification import heuristic_qualify
from app.database import async_session
from app.models.job_posting import (
    ApplyChannel, ApplyComplexity, ContractType, JobPosting, PostingStatus, RemotePolicy,
)

logger = logging.getLogger(__name__)

BASE = "https://choisirleservicepublic.gouv.fr"
LISTING = f"{BASE}/nos-offres/filtres/date-de-publication/dernieres_48_heures/"
#: Préfixe d'`external_id` : suivi de la référence de l'offre.
PREFIX = "csp:"
DOMAIN_SUFFIX = ".csp.source"
SOURCE_NAME = "Choisir le service public"
OFFER_URL = re.compile(rf"^{re.escape(BASE)}/offre-emploi/[a-z0-9-]+-reference-([A-Za-z0-9_-]+)/?$")
#: Une offre retirée renvoie vers cette page.
UNPUBLISHED = "/offre-depubliee"
PAUSE_S = 1.0
#: ~1 200 offres nouvelles par jour.
MAX_READS_PER_RUN = 1500
MAX_PAGES = 200
USER_AGENT = "AliceBot/1.0 (+https://www.alice-agent.fr ; offres d'emploi, une visite par jour)"

_LD = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")
_LINK = re.compile(r'href="([^"]+)"')
_DEADLINE = re.compile(r"Date limite de candidature\s*:\s*(\d{2}/\d{2}/\d{4})")
_TITULAIRES_ONLY = re.compile(r"ouvert uniquement aux (titulaires|fonctionnaires)", re.IGNORECASE)
#: Pièces qu'Alice ne peut pas joindre : le candidat envoie lui-même.
_EXTRA_DOCS = {
    "pièce d'identité": re.compile(r"pi[eè]ce d.identit", re.IGNORECASE),
    "diplôme": re.compile(r"copies? (du|des|de vos|de votre) dipl[oô]me", re.IGNORECASE),
    "certificat de travail": re.compile(r"certificats? de travail", re.IGNORECASE),
    "comptes rendus d'entretien professionnel": re.compile(
        r"\bCREP\b|comptes? rendus? d.entretiens? professionnel", re.IGNORECASE),
    "état des services": re.compile(r"[ée]tat (des|de) services", re.IGNORECASE),
    "dernier arrêté": re.compile(r"dernier arr[êe]t[ée]", re.IGNORECASE),
    # « un casier judiciaire compatible » est une condition, pas une pièce.
    "extrait de casier judiciaire": re.compile(r"extrait (de|du) casier|bulletin n.\s?3", re.IGNORECASE),
}


@dataclass
class CspOffer:
    reference: str
    url: str
    title: str
    employer: str
    location: str | None
    description: str
    posted: date | None
    deadline: date | None
    #: Adresse de candidature, et l'objet que l'employeur impose.
    email: str | None = None
    email_subject: str | None = None
    #: Lien « Postuler sur le site employeur ».
    employer_url: str | None = None
    #: Pièces demandées qu'Alice ne peut pas fournir.
    extra_documents: list[str] = field(default_factory=list)


def _text(fragment: str | None) -> str:
    s = re.sub(r"<\s*(br|/p|/li|/h\d)\s*/?>", "\n", fragment or "", flags=re.IGNORECASE)
    s = re.sub(r"<li[^>]*>", "• ", s, flags=re.IGNORECASE)
    s = html_lib.unescape(_TAGS.sub("", s)).replace("\xa0", " ")
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", s)).strip()


def _date(raw: str | None) -> date | None:
    try:
        return datetime.strptime((raw or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _location(raw: str | None) -> str | None:
    """« Paris (75), France » → « Paris (75) »."""
    loc = re.sub(r",\s*France\s*$", "", (raw or "").strip())
    return loc or None


def _mailto(href: str) -> tuple[str | None, str | None]:
    """`mailto:a@b.fr?subject=…` → (adresse valide ou None, objet)."""
    raw = html_lib.unescape(href)[len("mailto:"):]
    to, _, query = raw.partition("?")
    address = next((a.strip() for a in re.split(r"[,;]", unquote(to)) if is_valid_email(a.strip())), None)
    subject = None
    for part in query.split("&"):
        key, _, value = part.partition("=")
        if key.lower() == "subject":
            subject = re.sub(r"\s+", " ", unquote(value)).strip() or None
    return address, subject


def _apply_block(page: str) -> str:
    i = page.find("buttons-wrapper")
    if i < 0:
        return ""
    return page[i:page.find("</div>", i)]


def parse_offer(url: str, page: str) -> CspOffer | None:
    """La page d'une offre → l'offre, ou None si elle est retirée ou hors champ."""
    m = OFFER_URL.match(url)
    if not m:
        return None
    ld = None
    for raw in _LD.findall(page):
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            ld = data
            break
    if not ld:
        return None
    title = re.sub(r"\s+", " ", html_lib.unescape(ld.get("title") or "")).strip()
    if not title:
        return None
    flat = html_lib.unescape(re.sub(r"\s+", " ", _TAGS.sub(" ", page)))
    if _TITULAIRES_ONLY.search(flat):
        return None  # réservée aux fonctionnaires : pas pour les candidats d'Alice

    org = ld.get("hiringOrganization")
    employer = (org.get("name") if isinstance(org, dict) else org) or ""
    place = (ld.get("jobLocation") or {}).get("address") or {}
    location = _location(place.get("addressLocality") if isinstance(place, dict) else None) \
        or _location(ld.get("addressLocality"))
    description = "\n\n".join(p for p in (_text(ld.get("Description") or ld.get("description")),
                                          _text(ld.get("skills"))) if p)
    deadline = _DEADLINE.search(page)

    offer = CspOffer(
        reference=m.group(1),
        url=url,
        title=title[:500],
        employer=re.sub(r"\s+", " ", html_lib.unescape(employer)).strip(),
        location=location,
        description=description[:12000],
        posted=_date(ld.get("datePosted")),
        deadline=_date(deadline.group(1)) if deadline else None,
    )
    for href in _LINK.findall(_apply_block(page)):
        if href.lower().startswith("mailto:"):
            # Le lien « partager par e-mail » n'a pas de destinataire : ignoré.
            address, subject = _mailto(href)
            if address and not offer.email:
                offer.email, offer.email_subject = address, subject
        elif href.startswith("http") and not offer.employer_url:
            offer.employer_url = html_lib.unescape(href)
    offer.extra_documents = [name for name, rx in _EXTRA_DOCS.items() if rx.search(flat)]
    return offer


def parse_listing(page: str) -> list[str]:
    """Une page de la liste → les adresses des offres, dans l'ordre."""
    seen: dict[str, None] = {}
    for href in _LINK.findall(page):
        href = html_lib.unescape(href)
        if OFFER_URL.match(href):
            seen.setdefault(href if href.endswith("/") else href + "/", None)
    return list(seen)


# ── Enregistrement ────────────────────────────────────────────────────────


def _channel(o: CspOffer) -> tuple[ApplyChannel, ApplyComplexity, dict]:
    if o.email and not o.extra_documents:
        contact = {"email": o.email, "emails": [o.email], "apply_url": o.url}
        if o.email_subject:
            contact["email_subject"] = o.email_subject[:300]
        return ApplyChannel.EMAIL, ApplyComplexity.SIMPLE, contact
    if o.email:
        # Pièces qu'Alice n'a pas : le candidat complète et envoie lui-même.
        return ApplyChannel.EXTERNAL_LINK, ApplyComplexity.MEDIUM, {
            "email": o.email, "email_subject": o.email_subject, "apply_url": o.url,
            "extra_documents": o.extra_documents,
        }
    # Site de l'employeur, ou compte sur Choisir le service public.
    return ApplyChannel.EXTERNAL_LINK, ApplyComplexity.MEDIUM, {"apply_url": o.employer_url or o.url}


def contract_of(title: str, text: str) -> ContractType:
    """Le site ne donne pas le contrat : l'intitulé d'abord, puis le texte.
    Un poste ouvert aux contractuels est un CDD sauf mention d'un CDI."""
    if re.search(r"apprenti|alternan", title, re.IGNORECASE):
        return ContractType.ALTERNANCE
    if re.search(r"\bstage|stagiaire", title, re.IGNORECASE):
        return ContractType.STAGE
    if re.search(r"\bCDI\b|dur[ée]e ind[ée]termin[ée]e", text, re.IGNORECASE):
        return ContractType.CDI
    if re.search(r"\bCDD\b|dur[ée]e d[ée]termin[ée]e|contractuel", text, re.IGNORECASE):
        return ContractType.CDD
    return ContractType.UNKNOWN


def _fingerprint(domain: str, o: CspOffer) -> str:
    return compute_fingerprint(domain, o.title, o.location, external_id=PREFIX + o.reference)


async def persist(offers: list[CspOffer]) -> int:
    saved = 0
    now = datetime.now(UTC)
    async with async_session() as session:
        for o in offers:
            if o.deadline and o.deadline < now.date():
                continue  # date limite passée
            company = await _get_or_create_company(session, o.employer, suffix=DOMAIN_SUFFIX)
            text = f"{o.title}\n\n{o.description}"
            parsed = heuristic_qualify(o.title, text)
            contract = contract_of(o.title, text)
            parsed["contract_type"] = contract.value
            parsed["source"] = {
                "name": SOURCE_NAME, "licence": "Licence Ouverte Etalab 2.0",
                "reference": o.reference,
                "posted": o.posted.isoformat() if o.posted else None,
                "deadline": o.deadline.isoformat() if o.deadline else None,
            }
            channel, complexity, contact = _channel(o)
            values = dict(
                title=o.title,
                description_raw=text,
                description_parsed=parsed,
                location=o.location,
                apply_url=contact.get("apply_url") or o.url,
                apply_channel=channel,
                apply_complexity=complexity,
                contact_json=contact,
                contract_type=contract,
                remote_policy=RemotePolicy.ONSITE,
                tech_stack=parsed.get("tech_stack") or [],
                status=PostingStatus.ACTIVE,
            )
            await session.execute(
                pg_insert(JobPosting).values(
                    company_id=company.id,
                    external_id=PREFIX + o.reference,
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


async def collect(client: httpx.AsyncClient | None = None, limit: int | None = MAX_READS_PER_RUN,
                  max_pages: int = MAX_PAGES) -> dict:
    """Collecte quotidienne. Ne lève pas : renvoie un rapport."""
    own = client is None
    client = client or httpx.AsyncClient(
        timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT},
    )
    try:
        listed: dict[str, str] = {}  # référence → adresse
        for n in range(1, max_pages + 1):
            if n > 1:
                await asyncio.sleep(PAUSE_S)
            res = await client.get(LISTING if n == 1 else f"{LISTING}page/{n}/")
            if res.status_code != 200:
                if n == 1:
                    return {"ok": False, "reason": f"liste {res.status_code}"}
                break  # au-delà de la dernière page
            urls = parse_listing(res.text)
            new = [u for u in urls if OFFER_URL.match(u).group(1) not in listed]
            if not new:
                break
            for u in new:
                listed[OFFER_URL.match(u).group(1)] = u
        if not listed:
            return {"ok": False, "reason": "liste sans offre"}

        async with async_session() as session:
            known = set((await session.execute(
                select(JobPosting.external_id).where(JobPosting.external_id.like(f"{PREFIX}%"))
            )).scalars().all())
        fresh = [r for r in listed if PREFIX + r not in known]
        seen = [PREFIX + r for r in listed if PREFIX + r in known]
        if limit is not None:
            fresh = fresh[:limit]

        offers: list[CspOffer] = []
        skipped = 0
        for i, ref in enumerate(fresh):
            if i:
                await asyncio.sleep(PAUSE_S)
            try:
                page = await client.get(listed[ref])
            except httpx.HTTPError as e:
                logger.warning("CSP : %s illisible (%s)", listed[ref], type(e).__name__)
                continue
            if page.status_code != 200 or UNPUBLISHED in str(page.url):
                continue
            offer = parse_offer(listed[ref], page.text)
            if offer:
                offers.append(offer)
            else:
                skipped += 1

        saved = await persist(offers)
        now = datetime.now(UTC)
        async with async_session() as session:
            if seen:
                await session.execute(
                    update(JobPosting).where(JobPosting.external_id.in_(seen)).values(last_seen_at=now)
                )
            # La liste ne couvre que 48 heures : une offre absente n'est pas
            # retirée. On ferme celles dont la date limite est passée ; les
            # autres sont vérifiées sur leur page juste avant l'envoi.
            await session.execute(
                update(JobPosting)
                .where(JobPosting.external_id.like(f"{PREFIX}%"))
                .where(JobPosting.status == PostingStatus.ACTIVE)
                .where(JobPosting.description_parsed["source"]["deadline"].astext
                       < now.date().isoformat())
                .values(status=PostingStatus.CLOSED)
            )
            await session.commit()
        by_email = sum(1 for o in offers if o.email and not o.extra_documents)
        logger.info("CSP : %d offres listées, %d lues, %d enregistrées dont %d par e-mail",
                    len(listed), len(fresh), saved, by_email)
        return {"ok": True, "listed": len(listed), "read": len(fresh), "saved": saved,
                "by_email": by_email, "skipped": skipped}
    except Exception as e:  # noqa: BLE001
        logger.error("Collecte CSP impossible : %s", e, exc_info=True)
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}
    finally:
        if own:
            await client.aclose()


async def still_online(url: str, client: httpx.AsyncClient | None = None) -> bool | None:
    """L'offre est-elle encore publiée ? None si on ne sait pas."""
    own = client is None
    client = client or httpx.AsyncClient(timeout=15, follow_redirects=True,
                                         headers={"User-Agent": USER_AGENT})
    try:
        res = await client.get(url)
        if res.status_code in (404, 410) or UNPUBLISHED in str(res.url):
            return False
        return True if res.status_code == 200 else None
    except httpx.HTTPError:
        return None
    finally:
        if own:
            await client.aclose()
