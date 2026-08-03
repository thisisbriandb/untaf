"""Pydantic schemas for Company API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.company import ATSType, CompanyStatus, SeedSource


class CompanyBase(BaseModel):
    name: str
    domain: str
    sector: str | None = None
    location_hq: str | None = None


class CompanyCreate(CompanyBase):
    """Schema for manually adding a company."""
    slug: str | None = None
    seed_source: SeedSource = SeedSource.MANUAL


class CompanyOut(CompanyBase):
    """Schema for API response."""
    id: UUID
    slug: str | None
    ats_type: ATSType
    ats_slug: str | None
    status: CompanyStatus
    careers_url: str | None
    seed_source: SeedSource
    last_scraped_at: datetime | None
    last_resolved_at: datetime | None
    is_active: bool
    created_at: datetime
    job_count: int = 0

    model_config = {"from_attributes": True}


class CompanyStats(BaseModel):
    """Aggregated stats for the company dashboard."""
    total: int
    by_status: dict[str, int]
    by_ats: dict[str, int]
    by_source: dict[str, int]
