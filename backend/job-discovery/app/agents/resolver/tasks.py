"""
ATS Resolver Celery tasks — resolve ATS type for pending companies.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.celery_app import celery_app
from app.database import async_session
from app.models.company import Company, CompanyStatus
from app.agents.resolver.ats_detector import resolve_ats

logger = logging.getLogger(__name__)


async def _resolve_single(company_id, domain: str):
    """Resolve ATS for a single company and update DB."""
    result = await resolve_ats(domain)

    async with async_session() as session:
        await session.execute(
            update(Company)
            .where(Company.id == company_id)
            .values(
                ats_type=result.ats_type,
                status=result.status,
                ats_slug=result.ats_slug,
                careers_url=result.careers_url,
                resolve_error=result.error,
                last_resolved_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    logger.info("Resolved %s → %s (%s)", domain, result.ats_type.value, result.status.value)
    return result.status.value


async def _resolve_all_pending(batch_size: int = 50):
    """Resolve ATS for all companies in PENDING status."""
    async with async_session() as session:
        result = await session.execute(
            select(Company.id, Company.domain)
            .where(Company.status == CompanyStatus.PENDING)
            .where(Company.is_active.is_(True))
            .limit(batch_size)
        )
        pending = result.all()

    logger.info("Resolving ATS for %d pending companies", len(pending))

    resolved = 0
    for company_id, domain in pending:
        try:
            await _resolve_single(company_id, domain)
            resolved += 1
        except Exception as e:
            logger.error("Failed to resolve %s: %s", domain, e)
            # Mark as error
            async with async_session() as session:
                await session.execute(
                    update(Company)
                    .where(Company.id == company_id)
                    .values(
                        status=CompanyStatus.ERROR,
                        resolve_error=str(e)[:500],
                        last_resolved_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()

    return resolved


@celery_app.task(name="app.agents.resolver.tasks.resolve_single_company")
def resolve_single_company(company_id: str, domain: str):
    """Celery task: resolve ATS for a single company."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_resolve_single(company_id, domain))
    finally:
        loop.close()


@celery_app.task(name="app.agents.resolver.tasks.resolve_unresolved_companies")
def resolve_unresolved_companies(batch_size: int = 50):
    """Celery Beat task: resolve all pending companies (daily at 5 AM)."""
    loop = asyncio.new_event_loop()
    try:
        count = loop.run_until_complete(_resolve_all_pending(batch_size))
        logger.info("Resolved %d companies", count)
        return count
    finally:
        loop.close()
