"""
Offres d'INRAE (jobs.inrae.fr) : stages, CDD, apprentissage.

Chaque offre donne l'adresse du chercheur qui recrute (« J'envoie mon CV et
ma lettre de motivation ») : pas de compte, pas de formulaire, Alice peut
postuler elle-même par e-mail.

Réutilisation : les contenus publics du site sont sous Licence Ouverte
Etalab 2.0 (conditions générales d'utilisation, lues le 14/10/2026), à
condition de citer la source — l'offre renvoie toujours à sa page INRAE.

Les adresses sont nominatives : elles ne servent qu'à envoyer, à la demande
du candidat, une candidature à l'offre pour laquelle elles sont publiées.
Jamais affichées sur la liste publique, jamais utilisées pour une
candidature spontanée.

Politesse : une collecte par jour, via le sitemap ; seules les offres
nouvelles ou modifiées sont relues, une par seconde.
"""

import asyncio
import html as html_lib
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

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

BASE = "https://jobs.inrae.fr"
SITEMAP = f"{BASE}/sitemap.xml"
#: Préfixe d'`external_id`.
PREFIX = "inrae:"
#: Domaine fictif de l'employeur (même convention que les autres sources).
DOMAIN_SUFFIX = ".inrae.source"
COMPANY = "INRAE"
#: Seules les offres « ot-NNNNN » sont des offres d'emploi ou de stage ; les
#: concours et la mobilité interne s'adressent aux fonctionnaires.
OFFER_URL = re.compile(r"^https://jobs\.inrae\.fr/ot-\d+$")
PAUSE_S = 1.0
USER_AGENT = "AliceBot/1.0 (+https://www.alice-agent.fr ; offres d'emploi, une visite par jour)"

_POSTAL = re.compile(r"\b(\d{5})\s+([^\d\s][^\d]*)$")
_POSTAL_AFTER = re.compile(r"([^\d]+?)\s+(\d{5})")
_MAILTO = re.compile(r'href="mailto:([^"?]+)"', re.I)
_TAGS = re.compile(r"<[^>]+>")
_BLOCKS = re.compile(r"<(script|style|svg|noscript)[\s\S]*?</\1>", re.I)


@dataclass
class InraeOffer:
    url: str
    ref: str
    title: str
    contract: ContractType
    location: str | None
    emails: list[str]
    description: str
    deadline: date | None = None
    fields: dict = field(default_factory=dict)


def _text(fragment: str) -> list[str]:
    """Le texte d'un fragment HTML, une ligne non vide par élément."""
    raw = _TAGS.sub("\n", _BLOCKS.sub("", fragment))
    lines = (html_lib.unescape(l).replace("\xa0", " ").strip() for l in raw.split("\n"))
    return [re.sub(r"\s+", " ", l) for l in lines if l.strip()]


def _labelled(lines: list[str]) -> dict[str, str]:
    """« Contrat : » suivi de « Stage » → {"contrat": "Stage"}."""
    out: dict[str, str] = {}
    for i, line in enumerate(lines[:-1]):
        if line.endswith(":"):
            key = line[:-1].strip().lower()
            out.setdefault(key, lines[i + 1])
    return out


def contract_of(label: str, title: str) -> ContractType:
    """
    L'intitulé d'abord (« Stage Master 2… » est parfois étiqueté « Mission
    temporaire »), puis le libellé du site : « Mission temporaire » est un CDD
    de contractuel, « Thèse » un contrat doctoral (CDD lui aussi).
    """
    for text in (title.lower(), label.lower()):
        if re.search(r"apprenti|alternan", text):
            return ContractType.ALTERNANCE
        if re.search(r"\bstage|stagiaire", text):
            return ContractType.STAGE
    text = f"{label} {title}".lower()
    if re.search(r"\bcdi\b|titulaire", text):
        return ContractType.CDI
    if re.search(r"\bcdd\b|mission temporaire|durée déterminée|post-?doc|doctora|th[èe]se", text):
        return ContractType.CDD
    return ContractType.UNKNOWN


def _date(value: str | None) -> date | None:
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", value or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def parse_offer(url: str, page: str) -> InraeOffer | None:
    """Les champs d'une page d'offre, ou None si elle n'en a pas la forme."""
    start = page.find("Hero-title")
    end = page.find("Haut de page", start)
    if start < 0:
        return None
    content = page[start:end if end > 0 else None]
    lines = _text(content[content.find(">") + 1:])
    if not lines:
        return None
    title = lines[0]
    fields = _labelled(lines)

    # Adresses de candidature : les liens mailto du contenu, hors bouton
    # « partager par e-mail » (qui porte un ?subject=).
    emails: list[str] = []
    for m in _MAILTO.finditer(content):
        for part in re.split(r"[;,]", html_lib.unescape(m.group(1))):
            addr = part.strip().lower()
            if is_valid_email(addr) and addr not in emails:
                emails.append(addr)

    # Lieu : la ligne sous le titre (« 91120 Palaiseau », parfois une adresse
    # complète), à défaut le bloc « Le centre ». On garde « code postal ville ».
    def postal(line: str) -> str | None:
        m = _POSTAL.search(line)
        if m:
            return f"{m.group(1)} {m.group(2).strip()}"
        m = _POSTAL_AFTER.fullmatch(line)  # « Aubière 63170 »
        if m:
            return f"{m.group(2)} {m.group(1).strip()}"
        # « 35000 », « 35 RENNES » : courts, avec un département ou un code.
        return line if len(line) < 40 and re.fullmatch(r"\d{2,5}( [^\d]+)?", line) else None

    location = postal(lines[1]) if len(lines) > 1 else None
    if not location:
        centre = next((i for i, l in enumerate(lines) if l == "Le centre"), None)
        if centre is not None:
            location = next(filter(None, map(postal, lines[centre:centre + 6])), None)

    # Description : de la présentation à la référence de l'offre.
    try:
        a = next(i for i, l in enumerate(lines) if l.startswith("Environnement de travail"))
    except StopIteration:
        a = 1
    b = next((i for i, l in enumerate(lines) if l.startswith("Référence de l'offre")), len(lines))
    description = "\n".join(lines[a:b])[:12000]

    ref = (fields.get("n° de l'offre") or url.rsplit("/", 1)[-1]).upper()
    return InraeOffer(
        url=url,
        ref=ref,
        title=title[:500],
        contract=contract_of(fields.get("contrat", ""), title),
        location=location,
        emails=emails,
        description=description,
        deadline=_date(fields.get("date limite")),
        fields={k: v for k, v in fields.items() if k in (
            "contrat", "durée", "début du contrat", "rémunération", "date limite", "n° de l'offre",
        )},
    )


def parse_sitemap(xml: str) -> dict[str, datetime | None]:
    """URL d'offre → date de dernière modification annoncée."""
    out: dict[str, datetime | None] = {}
    for block in re.findall(r"<url>([\s\S]*?)</url>", xml):
        loc = re.search(r"<loc>([^<]+)</loc>", block)
        if not loc or not OFFER_URL.match(loc.group(1).strip()):
            continue
        mod = re.search(r"<lastmod>([^<]+)</lastmod>", block)
        when = None
        if mod:
            try:
                when = datetime.fromisoformat(mod.group(1).strip().replace("Z", "+00:00"))
            except ValueError:
                when = None
        out[loc.group(1).strip()] = when
    return out


# ── Enregistrement ────────────────────────────────────────────────────────


def _external_id(url: str) -> str:
    return PREFIX + url.rsplit("/", 1)[-1]


async def persist(offers: list[InraeOffer]) -> int:
    saved = 0
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        company = await _get_or_create_company(session, COMPANY, suffix=DOMAIN_SUFFIX)
        for o in offers:
            if o.deadline and o.deadline < now.date():
                continue  # date limite passée : plus la peine de postuler
            text = f"{o.title}\n\n{o.description}"
            parsed = heuristic_qualify(o.title, text)
            parsed["contract_type"] = o.contract.value
            parsed["source"] = {"name": "INRAE", "licence": "Licence Ouverte Etalab 2.0", **o.fields}
            contact = {"email": o.emails[0], "emails": o.emails} if o.emails else {}
            channel, complexity = (
                (ApplyChannel.EMAIL, ApplyComplexity.SIMPLE) if o.emails
                else (ApplyChannel.EXTERNAL_LINK, ApplyComplexity.MEDIUM)
            )
            values = dict(
                title=o.title,
                description_raw=text,
                description_parsed=parsed,
                location=o.location,
                apply_url=o.url,
                apply_channel=channel,
                apply_complexity=complexity,
                contact_json=contact or None,
                contract_type=o.contract,
                remote_policy=RemotePolicy.ONSITE,
                tech_stack=parsed.get("tech_stack") or [],
                status=PostingStatus.ACTIVE,
            )
            await session.execute(
                pg_insert(JobPosting).values(
                    company_id=company.id,
                    external_id=_external_id(o.url),
                    fingerprint=compute_fingerprint(company.domain, o.title, o.location, external_id=o.ref),
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


async def collect(client: httpx.AsyncClient | None = None, limit: int | None = None) -> dict:
    """Collecte quotidienne. Ne lève pas : renvoie un rapport."""
    own = client is None
    client = client or httpx.AsyncClient(
        timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT},
    )
    try:
        res = await client.get(SITEMAP)
        if res.status_code != 200:
            return {"ok": False, "reason": f"sitemap {res.status_code}"}
        listed = parse_sitemap(res.text)

        # Offres déjà connues et inchangées depuis notre dernier passage (date
        # du sitemap antérieure à notre dernière lecture) : on note seulement
        # qu'elles sont toujours en ligne, sans relire la page.
        async with async_session() as session:
            known = dict((await session.execute(
                select(JobPosting.source_url, JobPosting.last_seen_at)
                .where(JobPosting.external_id.like(f"{PREFIX}%"))
            )).all())
        fresh = [u for u, mod in listed.items() if u not in known or (mod and mod > known[u])]
        stale_ok = [u for u in listed if u not in fresh and u in known]
        if limit is not None:
            fresh = fresh[:limit]

        offers: list[InraeOffer] = []
        for i, url in enumerate(fresh):
            if i:
                await asyncio.sleep(PAUSE_S)
            try:
                page = await client.get(url)
            except httpx.HTTPError as e:
                # Une page qui ne répond pas n'arrête pas la collecte : elle
                # sera relue demain (sa date reste plus récente que la nôtre).
                logger.warning("INRAE : %s illisible (%s)", url, type(e).__name__)
                continue
            if page.status_code != 200:
                continue
            offer = parse_offer(url, page.text)
            if offer:
                offers.append(offer)

        saved = await persist(offers)
        now = datetime.now(timezone.utc)
        async with async_session() as session:
            if stale_ok:
                await session.execute(
                    update(JobPosting).where(JobPosting.source_url.in_(stale_ok)).values(last_seen_at=now)
                )
            # Ce que le sitemap ne liste plus est retiré.
            await session.execute(
                update(JobPosting)
                .where(JobPosting.external_id.like(f"{PREFIX}%"))
                .where(JobPosting.status == PostingStatus.ACTIVE)
                .where(JobPosting.source_url.not_in(list(listed) or [""]))
                .values(status=PostingStatus.CLOSED)
            )
            await session.commit()
        logger.info("INRAE : %d offres listées, %d lues, %d enregistrées", len(listed), len(fresh), saved)
        return {"ok": True, "listed": len(listed), "read": len(fresh), "saved": saved,
                "with_email": sum(1 for o in offers if o.emails)}
    except Exception as e:  # noqa: BLE001
        logger.error("Collecte INRAE impossible : %s", e, exc_info=True)
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}
    finally:
        if own:
            await client.aclose()
