"""Pydantic schemas for Application API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.application import ApplicationStatus
from app.schemas.job import JobPostingOut


class ApplicationBase(BaseModel):
    candidate_id: UUID
    job_posting_id: UUID


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus
    #: Précision libre (« entretien le 12 avec la CTO »), gardée dans la frise.
    note: str | None = None


class ApplicationOut(ApplicationBase):
    id: UUID
    status: ApplicationStatus
    match_score: int
    applied_at: datetime | None
    metadata_json: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationDetail(ApplicationOut):
    job_posting: JobPostingOut | None = None
