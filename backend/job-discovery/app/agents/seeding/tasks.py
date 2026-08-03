"""
Seeding Celery tasks — orchestrate company acquisition from all sources
and persist to PostgreSQL.
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.celery_app import celery_app
from app.database import async_session
from app.models.company import Company, SeedSource, ATSType, CompanyStatus
from app.agents.seeding.ecosystem import get_ecosystem_companies
from app.agents.seeding.wttj_sitemap import seed_from_wttj
from app.agents.seeding.sirene import query_sirene, guess_domain_from_name

logger = logging.getLogger(__name__)


async def _seed_ecosystem():
    """Insert curated ecosystem companies into DB."""
    companies = get_ecosystem_companies()
    count = 0

    async with async_session() as session:
        for c in companies:
            source_map = {
                "next40": SeedSource.ECOSYSTEM_NEXT40,
                "ft120": SeedSource.ECOSYSTEM_FT120,
                "vc_backed": SeedSource.ECOSYSTEM_VC,
            }
            stmt = pg_insert(Company).values(
                name=c.name,
                domain=c.domain,
                slug=c.domain.split(".")[0],
                sector=c.sector,
                seed_source=source_map.get(c.source, SeedSource.MANUAL),
                status=CompanyStatus.PENDING,
                ats_type=ATSType.UNKNOWN,
            ).on_conflict_do_nothing(index_elements=["domain"])

            result = await session.execute(stmt)
            if result.rowcount > 0:
                count += 1

        await session.commit()

    logger.info("Ecosystem seeding: %d new companies inserted", count)
    return count


async def _seed_wttj(max_companies: int = 2000):
    """Seed from WTTJ sitemap."""
    wttj_companies = await seed_from_wttj(max_companies=max_companies)
    count = 0

    async with async_session() as session:
        for c in wttj_companies:
            if not c.domain:
                continue

            stmt = pg_insert(Company).values(
                name=c.name or c.slug,
                domain=c.domain,
                slug=c.slug,
                seed_source=SeedSource.WTTJ_SITEMAP,
                status=CompanyStatus.PENDING,
                ats_type=ATSType.UNKNOWN,
            ).on_conflict_do_nothing(index_elements=["domain"])

            result = await session.execute(stmt)
            if result.rowcount > 0:
                count += 1

        await session.commit()

    logger.info("WTTJ seeding: %d new companies inserted", count)
    return count


async def _seed_sirene():
    """Seed from INSEE SIRENE API."""
    sirene_companies = await query_sirene()
    count = 0

    async with async_session() as session:
        for c in sirene_companies:
            domain = guess_domain_from_name(c.name)

            stmt = pg_insert(Company).values(
                name=c.name,
                domain=domain,
                siren=c.siren,
                naf_code=c.naf_code,
                seed_source=SeedSource.SIRENE_API,
                status=CompanyStatus.PENDING,
                ats_type=ATSType.UNKNOWN,
            ).on_conflict_do_nothing(index_elements=["domain"])

            result = await session.execute(stmt)
            if result.rowcount > 0:
                count += 1

        await session.commit()

    logger.info("SIRENE seeding: %d new companies inserted", count)
    return count


@celery_app.task(name="app.agents.seeding.tasks.run_full_seeding")
def run_full_seeding():
    """
    One-shot task: populate the companies table from all seeding sources.
    Run this once at platform launch, then periodically to discover new companies.
    """
    loop = asyncio.new_event_loop()
    try:
        eco_count = loop.run_until_complete(_seed_ecosystem())
        wttj_count = loop.run_until_complete(_seed_wttj())
        sirene_count = loop.run_until_complete(_seed_sirene())

        total = eco_count + wttj_count + sirene_count
        logger.info(
            "Full seeding complete: %d new companies "
            "(ecosystem=%d, wttj=%d, sirene=%d)",
            total, eco_count, wttj_count, sirene_count,
        )
        return {"total": total, "ecosystem": eco_count, "wttj": wttj_count, "sirene": sirene_count}
    finally:
        loop.close()
