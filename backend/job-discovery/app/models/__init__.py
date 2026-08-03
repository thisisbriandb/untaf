"""Models package — re-export all models and Base for Alembic."""

from app.database import Base
from app.models.company import Company, ATSType, CompanyStatus, SeedSource
from app.models.job_posting import (
    JobPosting,
    RemotePolicy,
    ContractType,
    ApplyChannel,
    ApplyComplexity,
    PostingStatus,
)

from app.models.candidate import Candidate
from app.models.application import Application, ApplicationStatus
from app.models.dispatch import ApplicationDispatch, DispatchChannel, DispatchStatus
from app.models.mission import (
    Mission,
    MissionEvent,
    MissionEventKind,
    MissionStatus,
    AutonomyLevel,
)

__all__ = [
    "Base",
    "Company",
    "ATSType",
    "CompanyStatus",
    "SeedSource",
    "JobPosting",
    "RemotePolicy",
    "ContractType",
    "ApplyChannel",
    "ApplyComplexity",
    "PostingStatus",
    "Candidate",
    "Application",
    "ApplicationStatus",
    "Mission",
    "MissionEvent",
    "MissionEventKind",
    "MissionStatus",
    "AutonomyLevel",
    "ApplicationDispatch",
    "DispatchChannel",
    "DispatchStatus",
]
