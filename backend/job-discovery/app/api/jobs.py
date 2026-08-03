"""
API routes for job postings — listing, filtering, and detail views.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.company import Company
from app.models.job_posting import (
    JobPosting, PostingStatus, ApplyChannel, ApplyComplexity,
)
from app.schemas.job import JobPostingOut, JobPostingDetail, JobStats

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/", response_model=list[JobPostingOut])
async def list_jobs(
    status: PostingStatus | None = PostingStatus.ACTIVE,
    channel: ApplyChannel | None = None,
    complexity: ApplyComplexity | None = None,
    search: str | None = None,
    location: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="newest", pattern="^(newest|score)$"),
    db: AsyncSession = Depends(get_db),
):
    """List discovered job postings with filters."""
    query = (
        select(JobPosting, Company.name, Company.domain)
        .join(Company, JobPosting.company_id == Company.id)
    )

    if status:
        query = query.where(JobPosting.status == status)
    if channel:
        query = query.where(JobPosting.apply_channel == channel)
    if complexity:
        query = query.where(JobPosting.apply_complexity == complexity)
    if search:
        query = query.where(
            JobPosting.title.ilike(f"%{search}%")
            | Company.name.ilike(f"%{search}%")
        )
    if location:
        query = query.where(JobPosting.location.ilike(f"%{location}%"))

    if sort == "score":
        query = query.order_by(
            JobPosting.match_score.desc().nullslast(),
            JobPosting.first_seen_at.desc(),
        )
    else:
        query = query.order_by(JobPosting.first_seen_at.desc())

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)

    jobs = []
    for posting, company_name, company_domain in result.all():
        data = JobPostingOut.model_validate(posting)
        data.company_name = company_name
        data.company_domain = company_domain
        jobs.append(data)

    return jobs


@router.get("/stats", response_model=JobStats)
async def get_job_stats(db: AsyncSession = Depends(get_db)):
    """Get aggregated job posting statistics."""
    total_active = await db.scalar(
        select(func.count(JobPosting.id))
        .where(JobPosting.status == PostingStatus.ACTIVE)
    )

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    new_today = await db.scalar(
        select(func.count(JobPosting.id))
        .where(JobPosting.first_seen_at >= today_start)
    )

    channel_result = await db.execute(
        select(JobPosting.apply_channel, func.count(JobPosting.id))
        .where(JobPosting.status == PostingStatus.ACTIVE)
        .group_by(JobPosting.apply_channel)
    )
    by_channel = {r[0].value: r[1] for r in channel_result.all()}

    complexity_result = await db.execute(
        select(JobPosting.apply_complexity, func.count(JobPosting.id))
        .where(JobPosting.status == PostingStatus.ACTIVE)
        .group_by(JobPosting.apply_complexity)
    )
    by_complexity = {r[0].value: r[1] for r in complexity_result.all()}

    location_result = await db.execute(
        select(JobPosting.location, func.count(JobPosting.id))
        .where(JobPosting.status == PostingStatus.ACTIVE)
        .where(JobPosting.location.isnot(None))
        .group_by(JobPosting.location)
        .order_by(func.count(JobPosting.id).desc())
        .limit(10)
    )
    top_locations = [
        {"location": r[0], "count": r[1]}
        for r in location_result.all()
    ]

    return JobStats(
        total_active=total_active or 0,
        new_today=new_today or 0,
        by_channel=by_channel,
        by_complexity=by_complexity,
        top_locations=top_locations,
    )


@router.get("/{job_id}", response_model=JobPostingDetail)
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get full details for a single job posting."""
    result = await db.execute(
        select(JobPosting, Company.name, Company.domain)
        .join(Company, JobPosting.company_id == Company.id)
        .where(JobPosting.id == job_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Job posting not found")

    posting, company_name, company_domain = row
    data = JobPostingDetail.model_validate(posting)
    data.company_name = company_name
    data.company_domain = company_domain
    return data
