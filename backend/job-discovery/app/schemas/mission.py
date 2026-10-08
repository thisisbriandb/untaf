"""Pydantic schemas for Mission API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from typing import Literal

from app.models.mission import (
    AutonomyLevel, MissionEventKind, MissionStatus, RunStatus, RunStep,
)
from app.schemas.matching import MatchingCriteria


class MissionEventOut(BaseModel):
    id: UUID
    kind: MissionEventKind
    summary: str
    payload: dict | None = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RunCreate(BaseModel):
    """Les paramètres que l'utilisateur confirme avant le lancement."""

    title: str = Field(default="Préparer mes candidatures", max_length=255)
    objective: Literal["search", "prepare", "apply"] = Field(
        default="prepare",
        description="prepare = dossiers complets (CV adapté + lettre) · apply = jusqu'à "
                    "l'envoi. « search » est accepté pour compatibilité et vaut prepare : "
                    "le repérage est fait chaque matin.",
    )
    #: Nombre d'offres à traiter. La mission n'a plus de durée : elle fait
    #: une passe et rend compte.
    count: int = Field(default=5, ge=1, le=10)
    #: Candidatures spontanées à préparer en plus des offres (0 = aucune).
    spontaneous: int = Field(default=0, ge=0, le=5)
    #: Ignoré, conservé pour les anciens clients.
    duration_minutes: int | None = Field(default=None)
    allowed_actions: dict = Field(
        default_factory=dict,
        description='{"send": bool} — l\'envoi n\'a lieu que s\'il est autorisé.',
    )


class RunEventOut(BaseModel):
    id: UUID
    kind: MissionEventKind
    summary: str
    payload: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MissionRunOut(BaseModel):
    id: UUID
    title: str
    objective: str
    duration_minutes: int
    status: RunStatus
    current_step: RunStep | None = None
    allowed_actions: dict | None = None
    stats: dict | None = None
    report: str | None = None
    started_at: datetime | None = None
    ends_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MissionRunDetail(MissionRunOut):
    """Vue temps réel : ce qu'il reste, où on en est, ce qui a été fait."""

    seconds_remaining: int = 0
    progress: float = Field(default=0.0, description="0 à 1, part du temps écoulée.")
    events: list[RunEventOut] = Field(default_factory=list)


class MissionUpdate(BaseModel):
    title: str | None = None
    status: MissionStatus | None = None
    autonomy: AutonomyLevel | None = None
    auto_apply_min_score: int | None = Field(default=None, ge=0, le=100)
    weekly_quota: int | None = Field(default=None, ge=0, le=200)


class MissionStats(BaseModel):
    """Compteurs dérivés — jamais stockés, toujours recalculés."""
    shortlisted: int = 0
    applied: int = 0
    interviews: int = 0
    scanned_last_run: int = 0
    applied_this_week: int = 0
    quota_remaining: int = 0


class MissionOut(BaseModel):
    id: UUID
    candidate_id: UUID
    title: str
    status: MissionStatus
    autonomy: AutonomyLevel
    auto_apply_min_score: int
    weekly_quota: int
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MissionDetail(MissionOut):
    """Vue complète : le mandat effectif, les compteurs, le début du journal."""
    criteria: MatchingCriteria
    criteria_is_explicit: bool
    stats: MissionStats
    recent_events: list[MissionEventOut] = Field(default_factory=list)
