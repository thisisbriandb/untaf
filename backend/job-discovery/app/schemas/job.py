"""Pydantic schemas for JobPosting API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.job_posting import (
    ApplyChannel, ApplyComplexity, ContractType,
    PostingStatus, RemotePolicy,
)


class JobPostingOut(BaseModel):
    """Schema for API response — a discovered job posting."""
    id: UUID
    company_id: UUID

    title: str
    location: str | None
    department: str | None
    remote_policy: RemotePolicy
    contract_type: ContractType
    experience_range: str | None
    salary_range: str | None
    tech_stack: list[str] | None

    source_url: str
    apply_url: str | None
    apply_channel: ApplyChannel
    apply_complexity: ApplyComplexity
    status: PostingStatus

    match_score: int | None

    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime

    # Company info (joined)
    company_name: str | None = None
    company_domain: str | None = None

    model_config = {"from_attributes": True}


class JobPostingDetail(JobPostingOut):
    """Extended schema with full description."""
    description_raw: str | None
    description_parsed: dict | None
    external_id: str


class JobStats(BaseModel):
    """Aggregated stats for job postings."""
    total_active: int
    new_today: int
    by_channel: dict[str, int]
    by_complexity: dict[str, int]
    top_locations: list[dict]
