"""
Ingestion des offres La bonne alternance, pilotée par le mandat.

N'entrent que les offres auxquelles Alice peut transmettre la candidature
elle-même (voir labonnealternance.py) : c'est tout l'intérêt de la source.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.agents.discovery.deduplicator import compute_fingerprint
from app.agents.discovery.france_travail import ROME_BY_FAMILY
from app.agents.discovery.france_travail_task import _get_or_create_company
from app.agents.discovery.labonnealternance import (
    LBA_DOMAIN_SUFFIX, LbaError, geocode, search,
)
from app.agents.discovery.scrapers.base import ScrapedJob
from app.config import settings
from app.database import async_session
from app.models.job_posting import (
    ApplyChannel, ApplyComplexity, ContractType, JobPosting, PostingStatus, RemotePolicy,
)

logger = logging.getLogger(__name__)

_REMOTE = {"remote": RemotePolicy.REMOTE, "hybrid": RemotePolicy.HYBRID,
           "onsite": RemotePolicy.ONSITE}


async def persist(jobs: list[ScrapedJob]) -> int:
    processed = 0
    async with async_session() as session:
        for job in jobs:
            company = await _get_or_create_company(
                session, job.extra.get("company_name", ""), suffix=LBA_DOMAIN_SUFFIX,
            )
            parsed = job.extra.get("parsed") or {}
            contact = job.extra.get("contact") or {}
            values = dict(
                description_raw=job.description_raw,
                apply_url=job.apply_url,
                apply_channel=ApplyChannel.LBA_API,
                apply_complexity=ApplyComplexity.SIMPLE,
                contact_json=contact or None,
                description_parsed=parsed or None,
                remote_policy=_REMOTE.get(parsed.get("remote_policy"), RemotePolicy.UNKNOWN),
                contract_type=ContractType.ALTERNANCE,
                tech_stack=parsed.get("tech_stack") or [],
                status=PostingStatus.ACTIVE,
            )
            await session.execute(
                pg_insert(JobPosting).values(
                    company_id=company.id,
                    external_id=job.external_id,
                    fingerprint=compute_fingerprint(company.domain, job.title, job.location),
                    title=job.title,
                    location=job.location,
                    source_url=job.source_url or "https://labonnealternance.apprentissage.beta.gouv.fr",
                    **values,
                ).on_conflict_do_update(
                    index_elements=["fingerprint"],
                    set_={**values, "last_seen_at": datetime.now(timezone.utc)},
                )
            )
            processed += 1
        await session.commit()
    return processed


async def ingest_lba_for_candidate(candidate_id) -> dict:
    """Ne lève pas : renvoie un rapport, comme l'ingestion France Travail."""
    if not settings.lba_configured:
        return {"ok": False, "reason": "lba_not_configured", "processed": 0}

    from app.models.candidate import Candidate
    from app.schemas.matching import MatchingCriteria

    async with async_session() as session:
        candidate = await session.get(Candidate, candidate_id)
        if not candidate:
            return {"ok": False, "reason": "candidate_not_found", "processed": 0}
    criteria = MatchingCriteria.resolve(candidate)

    wanted = {c.lower() for c in (criteria.contract_types or [])}
    if wanted and "alternance" not in wanted:
        # Source réservée à l'alternance : rien à y chercher pour un CDI.
        return {"ok": True, "processed": 0, "skipped": "hors alternance"}

    romes = [
        code for family in (criteria.job_families or [])
        for code in ROME_BY_FAMILY.get(family, [])
    ]
    # Une recherche par ville du mandat (jusqu'à trois), sinon nationale.
    places: list[tuple[float, float] | None] = []
    for city in (criteria.locations or [])[:3]:
        point = await geocode(city)
        if point:
            places.append(point)
    if not places:
        places = [None]

    jobs: dict[str, ScrapedJob] = {}
    try:
        for point in places:
            found = await search(
                romes=romes or None,
                latitude=point[0] if point else None,
                longitude=point[1] if point else None,
            )
            for j in found:
                jobs[j.external_id] = j
    except LbaError as e:
        logger.error("La bonne alternance a refusé la recherche : %s", e)
        return {"ok": False, "reason": "lba_error", "detail": str(e), "processed": 0}
    except Exception as e:  # noqa: BLE001
        logger.error("La bonne alternance injoignable : %s", e, exc_info=True)
        return {"ok": False, "reason": "error", "detail": str(e), "processed": 0}

    processed = await persist(list(jobs.values()))
    return {"ok": True, "processed": processed, "fetched": len(jobs)}
