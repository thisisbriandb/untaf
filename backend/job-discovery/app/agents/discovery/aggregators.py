"""
Agrégateurs d'offres pour Alice Community : Adzuna, et Jooble une fois sa clé
obtenue et ses conditions vérifiées.

Ils rassemblent des centaines de jobboards : c'est par eux que la liste
publique couvre une bonne part de ce qu'on trouve ailleurs, sans aller
chercher chez Indeed ou LinkedIn ce qu'ils interdisent d'extraire.

Conditions Adzuna (developer.adzuna.com/docs/terms_of_service, lues le
12/10/2026) :
  - la publication des offres est permise, chaque offre portant la mention
    « Adzuna » avec un lien vers adzuna.fr ;
  - limites par défaut : 25 appels par minute, 250 par jour, 1 000 par
    semaine, 2 500 par mois. La collecte quotidienne en fait une trentaine ;
  - fin du partenariat : toutes les données Adzuna sont retirées
    (`purge_source("adzuna")`).
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.agents.discovery.signals import contract_from_title
from app.config import settings
from app.database import async_session
from app.models.external_listing import ExternalListing

logger = logging.getLogger(__name__)
# httpx écrit chaque URL appelée au niveau INFO : celles-ci portent les clés.
logging.getLogger("httpx").setLevel(logging.WARNING)

#: Mention et lien exigés à côté de chaque offre affichée.
ATTRIBUTION = {
    "adzuna": ("Adzuna", "https://www.adzuna.fr"),
    "jooble": ("Jooble", "https://fr.jooble.org"),
}

ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/fr/search/{page}"
JOOBLE_URL = "https://jooble.org/api/{key}"

#: Une recherche par type de contrat. « apprentissage » complète « alternance ».
QUERIES: list[tuple[str, str]] = [
    ("alternance", "alternance"),
    ("alternance", "apprentissage"),
    ("stage", "stage"),
]

#: Écart entre deux appels Adzuna : sous les 25 appels par minute.
ADZUNA_PAUSE_S = 3.0
#: Gardée au-delà, une offre que l'agrégateur ne renvoie plus est retirée.
KEEP_FOR = timedelta(days=30)

_KIND_RE = {
    "alternance": re.compile(r"\b(alternan\w*|apprenti\w*|contrat\s+pro\w*)\b", re.I),
    "stage": re.compile(r"\b(stage|stagiaire|internship)\b", re.I),
}
_TAGS = re.compile(r"<[^>]+>")


@dataclass
class Listing:
    source: str
    external_id: str
    title: str
    company: str
    location: str | None
    kind: str
    snippet: str | None
    url: str
    published_at: datetime | None


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", _TAGS.sub(" ", text or "")).strip()


def listing_kind(title: str, snippet: str, wanted: str) -> str | None:
    """
    Le type de contrat, lu dans l'intitulé d'abord, puis dans l'extrait. Une
    recherche « stage » renvoie aussi des CDI qui citent un stage : ceux-là
    ne passent pas.
    """
    titled = contract_from_title(title)
    if titled in ("alternance", "stage"):
        return titled
    if titled:  # freelance, etc.
        return None
    return wanted if _KIND_RE[wanted].search(snippet or "") else None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ── Adzuna ────────────────────────────────────────────────────────────────


def parse_adzuna(payload: dict, wanted: str) -> list[Listing]:
    out = []
    for r in payload.get("results") or []:
        title = _clean(r.get("title"))
        company = _clean((r.get("company") or {}).get("display_name"))
        url = r.get("redirect_url") or ""
        snippet = _clean(r.get("description"))
        if not (title and company and url and r.get("id")):
            continue
        kind = listing_kind(title, snippet, wanted)
        if not kind:
            continue
        out.append(Listing(
            source="adzuna",
            external_id=str(r["id"]),
            title=title[:500],
            company=company[:300],
            location=_clean((r.get("location") or {}).get("display_name")) or None,
            kind=kind,
            snippet=snippet[:2000] or None,
            url=url,
            published_at=_parse_date(r.get("created")),
        ))
    return out


async def fetch_adzuna(client: httpx.AsyncClient) -> list[Listing]:
    found: list[Listing] = []
    calls = 0
    for wanted, what in QUERIES:
        for page in range(1, settings.adzuna_pages_per_query + 1):
            if calls:
                await asyncio.sleep(ADZUNA_PAUSE_S)
            calls += 1
            res = await client.get(ADZUNA_URL.format(page=page), params={
                "app_id": settings.adzuna_app_id,
                "app_key": settings.adzuna_app_key,
                "what": what,
                "results_per_page": 50,
                "max_days_old": 30,
                "sort_by": "date",
                "content-type": "application/json",
            })
            if res.status_code in (401, 403):
                raise RuntimeError(f"Adzuna refuse la clé ({res.status_code})")
            if res.status_code == 429:
                logger.warning("Adzuna : limite d'appels atteinte, collecte arrêtée là")
                return found
            if res.status_code >= 400:
                # Jamais l'URL dans le message : elle porte la clé.
                raise RuntimeError(f"Adzuna répond {res.status_code}")
            batch = res.json().get("results") or []
            found += parse_adzuna({"results": batch}, wanted)
            if len(batch) < 50:
                break
    logger.info("Adzuna : %d offres retenues en %d appels", len(found), calls)
    return found


# ── Jooble (désactivé tant que JOOBLE_API_KEY est vide) ───────────────────


def parse_jooble(payload: dict, wanted: str) -> list[Listing]:
    out = []
    for r in payload.get("jobs") or []:
        title = _clean(r.get("title"))
        company = _clean(r.get("company"))
        url = r.get("link") or ""
        snippet = _clean(r.get("snippet"))
        if not (title and company and url and r.get("id")):
            continue
        kind = listing_kind(title, snippet, wanted)
        if not kind:
            continue
        out.append(Listing(
            source="jooble",
            external_id=str(r["id"]),
            title=title[:500],
            company=company[:300],
            location=_clean(r.get("location")) or None,
            kind=kind,
            snippet=snippet[:2000] or None,
            url=url,
            published_at=_parse_date(r.get("updated")),
        ))
    return out


async def fetch_jooble(client: httpx.AsyncClient) -> list[Listing]:
    found: list[Listing] = []
    for wanted, what in QUERIES:
        for page in range(1, settings.jooble_pages_per_query + 1):
            res = await client.post(
                JOOBLE_URL.format(key=settings.jooble_api_key),
                json={"keywords": what, "location": "France", "page": str(page)},
            )
            if res.status_code in (401, 403):
                raise RuntimeError(f"Jooble refuse la clé ({res.status_code})")
            if res.status_code >= 400:
                raise RuntimeError(f"Jooble répond {res.status_code}")
            batch = res.json()
            found += parse_jooble(batch, wanted)
            if not batch.get("jobs"):
                break
            await asyncio.sleep(1.0)
    logger.info("Jooble : %d offres retenues", len(found))
    return found


# ── Enregistrement ────────────────────────────────────────────────────────


async def persist(listings: list[Listing]) -> int:
    if not listings:
        return 0
    now = datetime.now(timezone.utc)
    unique = {(l.source, l.external_id): l for l in listings}
    async with async_session() as session:
        for l in unique.values():
            values = dict(
                title=l.title, company=l.company, location=l.location, kind=l.kind,
                snippet=l.snippet, url=l.url, published_at=l.published_at,
            )
            await session.execute(
                pg_insert(ExternalListing)
                .values(source=l.source, external_id=l.external_id, **values)
                .on_conflict_do_update(
                    constraint="uq_external_listing_source_id",
                    set_={**values, "last_seen_at": now},
                )
            )
        # Ce que l'agrégateur ne renvoie plus depuis un mois est retiré.
        await session.execute(delete(ExternalListing).where(ExternalListing.last_seen_at < now - KEEP_FOR))
        await session.commit()
    return len(unique)


async def purge_source(source: str) -> int:
    """Retire toutes les offres d'un agrégateur (fin de partenariat)."""
    async with async_session() as session:
        res = await session.execute(delete(ExternalListing).where(ExternalListing.source == source))
        await session.commit()
        return res.rowcount or 0


async def collect() -> dict:
    """Collecte quotidienne. Ne lève pas : un agrégateur en panne n'arrête pas l'autre."""
    report: dict = {}
    async with httpx.AsyncClient(timeout=30) as client:
        for source, enabled, fetch in (
            ("adzuna", settings.adzuna_configured, fetch_adzuna),
            ("jooble", settings.jooble_configured, fetch_jooble),
        ):
            if not enabled:
                report[source] = "non configuré"
                continue
            try:
                report[source] = await persist(await fetch(client))
            except Exception as e:  # noqa: BLE001
                logger.error("Collecte %s impossible : %s", source, e, exc_info=True)
                report[source] = f"erreur : {e}"
    return report
