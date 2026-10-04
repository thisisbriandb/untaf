"""
Collecte des ATS sans planificateur.

Les boards Greenhouse, Lever, Ashby, Workable et Recruitee ne sont collectés
que par le beat Celery. Un déploiement sans services `worker` et `beat` (le
cas d'un premier déploiement : seule l'API tourne) n'en voyait donc jamais
aucune offre — y compris celles où Alice postule elle-même.

Ici, la première recherche d'offres d'un candidat lance, en arrière-plan dans
le processus de l'API, ce que le beat aurait fait : recenser les boards s'il
n'y en a aucun, les collecter, qualifier les offres. Au plus une fois toutes
les 20 heures et jamais deux passes à la fois. Avec un beat actif, la passe
est inutile et ne part pas : les collectes du matin sont récentes.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.database import async_session
from app.models.company import ATSType, Company, CompanyStatus, SeedSource

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(hours=20)
PLATFORMS = (ATSType.RECRUITEE, ATSType.GREENHOUSE, ATSType.LEVER,
             ATSType.ASHBY, ATSType.WORKABLE)

_running: asyncio.Task | None = None
_last_start: datetime | None = None


async def _state() -> tuple[int, datetime | None]:
    async with async_session() as session:
        boards, last = (await session.execute(
            select(func.count(Company.id), func.max(Company.last_scraped_at))
            .where(Company.ats_type.in_(PLATFORMS))
            .where(Company.status == CompanyStatus.ATS_DIRECT)
        )).one()
        indexed = (await session.execute(
            select(func.count(Company.id))
            .where(Company.seed_source == SeedSource.ATS_INDEX)
            .where(Company.ats_type == ATSType.RECRUITEE)
        )).scalar() or 0
    return (boards or 0) if indexed else 0, last


async def _refresh() -> None:
    from app.agents.discovery.board_registry import discover
    from app.agents.discovery.tasks import _qualify_and_match_all, _scrape_platform

    try:
        boards, _ = await _state()
        if not boards:
            # Aucun board recensé (ou Recruitee jamais recensé) : l'index web d'abord.
            report = await discover()
            logger.info("Recensement des boards ATS : %s", report)
        total = 0
        for platform in PLATFORMS:
            try:
                total += await _scrape_platform(platform)
            except Exception as e:  # noqa: BLE001 — une plateforme en panne n'arrête pas les autres
                logger.error("Collecte %s impossible : %s", platform.value, e)
        qualified, matched = await _qualify_and_match_all()
        logger.info("Collecte ATS de secours : %d offres, %d qualifiées, %d rapprochements",
                    total, qualified, matched)
    except Exception as e:  # noqa: BLE001
        logger.error("Collecte ATS de secours échouée : %s", e, exc_info=True)


async def ensure_fresh() -> bool:
    """Lance la passe si les ATS n'ont pas été collectés récemment. Ne bloque pas."""
    global _running, _last_start
    now = datetime.now(timezone.utc)
    if _running and not _running.done():
        return False
    if _last_start and now - _last_start < STALE_AFTER:
        return False
    try:
        boards, last = await _state()
    except Exception as e:  # noqa: BLE001
        logger.warning("État des collectes ATS illisible : %s", e)
        return False
    if boards and last and now - last < STALE_AFTER:
        return False
    _last_start = now
    _running = asyncio.create_task(_refresh())
    return True
