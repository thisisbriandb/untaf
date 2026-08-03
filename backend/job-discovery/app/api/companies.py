"""
API routes for companies — CRUD + seeding + resolution triggers.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.company import Company, CompanyStatus, ATSType, SeedSource
from app.schemas.company import CompanyCreate, CompanyOut, CompanyStats

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/", response_model=list[CompanyOut])
async def list_companies(
    status: CompanyStatus | None = None,
    ats_type: ATSType | None = None,
    search: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all monitored companies with optional filters."""
    query = select(Company).order_by(Company.created_at.desc())

    if status:
        query = query.where(Company.status == status)
    if ats_type:
        query = query.where(Company.ats_type == ats_type)
    if search:
        query = query.where(
            Company.name.ilike(f"%{search}%") | Company.domain.ilike(f"%{search}%")
        )

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    companies = result.scalars().all()

    # Add job_count to each company
    output = []
    for c in companies:
        data = CompanyOut.model_validate(c)
        data.job_count = len(c.job_postings) if c.job_postings else 0
        output.append(data)

    return output


@router.get("/stats", response_model=CompanyStats)
async def get_company_stats(db: AsyncSession = Depends(get_db)):
    """Get aggregated company statistics."""
    total = await db.scalar(select(func.count(Company.id)))

    # Status breakdown
    status_result = await db.execute(
        select(Company.status, func.count(Company.id))
        .group_by(Company.status)
    )
    by_status = {row[0].value: row[1] for row in status_result.all()}

    # ATS breakdown
    ats_result = await db.execute(
        select(Company.ats_type, func.count(Company.id))
        .group_by(Company.ats_type)
    )
    by_ats = {row[0].value: row[1] for row in ats_result.all()}

    # Source breakdown
    source_result = await db.execute(
        select(Company.seed_source, func.count(Company.id))
        .group_by(Company.seed_source)
    )
    by_source = {row[0].value: row[1] for row in source_result.all()}

    return CompanyStats(
        total=total or 0,
        by_status=by_status,
        by_ats=by_ats,
        by_source=by_source,
    )


@router.post("/", response_model=CompanyOut, status_code=201)
async def create_company(
    data: CompanyCreate,
    db: AsyncSession = Depends(get_db),
):
    """Manually add a company to monitor."""
    # Check if domain already exists
    existing = await db.scalar(
        select(Company).where(Company.domain == data.domain)
    )
    if existing:
        raise HTTPException(409, f"Company with domain '{data.domain}' already exists")

    company = Company(
        name=data.name,
        domain=data.domain,
        slug=data.slug or data.domain.split(".")[0],
        sector=data.sector,
        location_hq=data.location_hq,
        seed_source=data.seed_source,
    )
    db.add(company)
    await db.flush()
    await db.refresh(company)

    return CompanyOut.model_validate(company)


@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(company_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single company by ID."""
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    data = CompanyOut.model_validate(company)
    data.job_count = len(company.job_postings) if company.job_postings else 0
    return data


@router.post("/seed", status_code=202)
async def trigger_seeding():
    """Trigger the full seeding pipeline (async via Celery)."""
    from app.agents.seeding.tasks import run_full_seeding
    task = run_full_seeding.delay()
    return {"task_id": task.id, "status": "seeding started"}


@router.post("/{company_id}/resolve", status_code=202)
async def trigger_resolution(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Trigger ATS resolution for a specific company."""
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    from app.agents.resolver.tasks import resolve_single_company
    task = resolve_single_company.delay(str(company.id), company.domain)
    return {"task_id": task.id, "status": "resolution started"}
