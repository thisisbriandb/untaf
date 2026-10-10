"""
Suivi de bout en bout — de l'offre retenue à la réponse du recruteur.

Une seule lecture rassemble ce que l'interface affichait en morceaux (ou pas du
tout) : où en est chaque candidature, si son pack est prêt, si un envoi
attend un feu vert, si une relance est due. S'y ajoutent les relances et les
préférences de notification.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import defer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.application.followup import (
    draft_followup,
    followup_state,
    recipient_for,
)
from app.agents.application.feasibility import apply_mode
from app.agents.application.outcome import _mailto
from app.agents.application.pack import is_pack_ready
from app.database import get_db
from app.models.application import Application, ApplicationStatus
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.dispatch import ApplicationDispatch, DispatchStatus
from app.models.job_posting import JobPosting
from app.models.notification import Notification, NotificationKind

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates/{candidate_id}", tags=["pipeline"])


# ── Pipeline ───────────────────────────────────────────────────────────────


class DispatchBrief(BaseModel):
    id: UUID
    status: DispatchStatus
    channel: str
    destination: str | None
    error: str | None
    sent_at: datetime | None
    created_at: datetime
    #: Brouillon prêt à ouvrir pour finir à la main, quand rien n'est parti.
    mailto: str | None = None


class FollowupOut(BaseModel):
    due: bool
    days_since_applied: int | None
    status: str | None
    subject: str | None = None
    body: str | None = None
    to: str | None = None
    sent_at: str | None = None


class PipelineItem(BaseModel):
    application_id: UUID
    job_id: UUID
    title: str
    company_name: str
    location: str | None
    contract_type: str
    remote_policy: str
    #: Qui envoie : auto (Alice) · assisted (un clic) · manual (sur le site)
    apply_mode: str = "manual"
    match_score: int
    status: ApplicationStatus
    #: Étape lisible, calculée : à préparer · prêt · à valider · envoyée ·
    #: répétition · à finir · entretien · offre · refusée · close
    stage: str
    pack_ready: bool
    applied_at: datetime | None
    source_url: str | None
    dispatch: DispatchBrief | None
    followup: FollowupOut
    timeline: list[dict] = []
    created_at: datetime


class PipelineOut(BaseModel):
    items: list[PipelineItem]
    counts: dict[str, int]


def _stage(application: Application, dispatch: ApplicationDispatch | None) -> str:
    status = application.status
    if status == ApplicationStatus.INTERVIEW:
        return "interview"
    if status == ApplicationStatus.OFFER:
        return "offer"
    if status == ApplicationStatus.REJECTED:
        return "rejected"
    if status == ApplicationStatus.CLOSED:
        return "closed"
    if status == ApplicationStatus.APPLIED:
        return "applied"
    if dispatch:
        if dispatch.status == DispatchStatus.AWAITING_APPROVAL:
            return "awaiting"
        if dispatch.status == DispatchStatus.SIMULATED:
            return "simulated"
        if dispatch.status in (DispatchStatus.FAILED, DispatchStatus.PREPARED):
            return "manual"
    return "ready" if is_pack_ready(application) else "to_prepare"


@router.get("/pipeline", response_model=PipelineOut)
async def get_pipeline(
    candidate_id: UUID,
    limit: int = Query(default=100, le=300),
    db: AsyncSession = Depends(get_db),
):
    """Toutes les candidatures du candidat, avec leur étape et ce qui reste à faire."""
    rows = (await db.execute(
        select(Application, JobPosting, Company.name)
        .join(JobPosting, Application.job_posting_id == JobPosting.id)
        .join(Company, JobPosting.company_id == Company.id)
        .where(Application.candidate_id == candidate_id)
        # « En attente » reste hors du suivi, sauf si un dossier y est prêt.
        .where(or_(
            Application.status != ApplicationStatus.PENDING,
            Application.metadata_json.has_key("cover_letter"),
        ))
        .order_by(desc(Application.updated_at))
        .limit(limit)
    )).all()

    app_ids = [a.id for a, _, _ in rows]
    latest: dict[UUID, ApplicationDispatch] = {}
    if app_ids:
        dispatches = (await db.execute(
            select(ApplicationDispatch)
        # Le PDF envoyé ne sert qu'au téléchargement : pas dans les listes.
        .options(defer(ApplicationDispatch.resume_blob, raiseload=True))
            .where(ApplicationDispatch.application_id.in_(app_ids))
            .where(ApplicationDispatch.status != DispatchStatus.REJECTED)
            .order_by(ApplicationDispatch.created_at)
        )).scalars().all()
        # Le plus récent l'emporte, sauf qu'un envoi réel n'est jamais masqué.
        for d in dispatches:
            current = latest.get(d.application_id)
            if not current or current.status != DispatchStatus.SENT:
                latest[d.application_id] = d

    items: list[PipelineItem] = []
    counts: dict[str, int] = {}
    for application, job, company in rows:
        dispatch = latest.get(application.id)
        stage = _stage(application, dispatch)
        counts[stage] = counts.get(stage, 0) + 1
        items.append(PipelineItem(
            application_id=application.id,
            job_id=job.id,
            title=job.title,
            company_name=company or "",
            location=job.location,
            contract_type=job.contract_type.value,
            remote_policy=job.remote_policy.value,
            apply_mode=apply_mode(job),
            match_score=application.match_score,
            status=application.status,
            stage=stage,
            pack_ready=is_pack_ready(application),
            applied_at=application.applied_at,
            source_url=None if (job.source_url or "").startswith("import://")
            else (job.apply_url or job.source_url),
            dispatch=DispatchBrief(
                id=dispatch.id, status=dispatch.status, channel=dispatch.channel.value,
                destination=dispatch.destination, error=dispatch.error,
                sent_at=dispatch.sent_at, created_at=dispatch.created_at,
                mailto=None if dispatch.status == DispatchStatus.SENT else _mailto(dispatch),
            ) if dispatch else None,
            followup=FollowupOut(**followup_state(application)),
            timeline=(application.metadata_json or {}).get("timeline") or [],
            created_at=application.created_at,
        ))
    counts["followup_due"] = sum(1 for i in items if i.followup.due)
    return PipelineOut(items=items, counts=counts)


# ── Validation groupée ─────────────────────────────────────────────────────


class BulkApproveOut(BaseModel):
    sent: int = 0
    simulated: int = 0
    failed: int = 0


@router.post("/dispatches/approve-all", response_model=BulkApproveOut)
async def approve_all(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Feu vert pour toute la file. Chaque envoi reste vérifié individuellement
    par l'exécuteur : approuver ne fait que lever l'attente de l'utilisateur.
    """
    from app.agents.application.dispatcher import send_dispatch
    from app.agents.notifications import notify_application_sent

    waiting = (await db.execute(
        select(ApplicationDispatch)
        .where(ApplicationDispatch.candidate_id == candidate_id)
        .where(ApplicationDispatch.status == DispatchStatus.AWAITING_APPROVAL)
        .order_by(ApplicationDispatch.created_at)
    )).scalars().all()
    # Formule gratuite : autant d'envois qu'il en reste ; s'il n'en reste
    # aucun, 402 → la fenêtre d'abonnement. Le reste attend, prêt.
    from app import billing
    from app.config import settings
    if settings.billing_enabled and waiting:
        left = await billing.remaining(db, candidate_id, "send")
        if left <= 0:
            await billing.check(db, candidate_id, "send")
        waiting = waiting[:left]
    now = datetime.now(timezone.utc)
    for d in waiting:
        d.status = DispatchStatus.APPROVED
        d.approved_at = now
        d.error = None
    await db.commit()

    result = BulkApproveOut()
    for d in waiting:
        sent = await send_dispatch(d.id)
        if sent and sent.status == DispatchStatus.SENT:
            result.sent += 1
            await notify_application_sent(candidate_id, sent.id)
        elif sent and sent.status == DispatchStatus.SIMULATED:
            result.simulated += 1
        else:
            result.failed += 1
    return result


# ── Relances ───────────────────────────────────────────────────────────────


async def _application(db: AsyncSession, candidate_id: UUID, application_id: UUID):
    row = (await db.execute(
        select(Application, JobPosting.title, Company.name)
        .join(JobPosting, Application.job_posting_id == JobPosting.id)
        .join(Company, JobPosting.company_id == Company.id)
        .where(Application.id == application_id)
        .where(Application.candidate_id == candidate_id)
    )).first()
    if not row:
        raise HTTPException(404, "Candidature introuvable")
    return row


@router.post("/applications/{application_id}/followup", response_model=FollowupOut)
async def prepare_followup(
    candidate_id: UUID,
    application_id: UUID,
    regenerate: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Rédige (ou rend) la relance de cette candidature."""
    application, title, company = await _application(db, candidate_id, application_id)
    meta = dict(application.metadata_json or {})
    existing = meta.get("followup") or {}

    if not existing.get("body") or regenerate:
        from app import billing
        await billing.consume(candidate_id, "message")  # un appel au modèle
        candidate = await db.get(Candidate, candidate_id)
        letter = (meta.get("cover_letter") or {}).get("body") or ""
        draft = await draft_followup(candidate, application, title, company or "", letter)
        existing = {
            **existing,
            **draft,
            "status": "drafted",
            "to": await recipient_for(db, application_id),
            "drafted_at": datetime.now(timezone.utc).isoformat(),
        }
        meta["followup"] = existing
        application.metadata_json = meta
        await db.commit()
        await db.refresh(application)

    return FollowupOut(**followup_state(application))


class FollowupMark(BaseModel):
    status: str = Field(pattern="^(sent|dismissed)$")


@router.post("/applications/{application_id}/followup/mark", response_model=FollowupOut)
async def mark_followup(
    candidate_id: UUID,
    application_id: UUID,
    body: FollowupMark,
    db: AsyncSession = Depends(get_db),
):
    """
    Le candidat a envoyé la relance (depuis sa messagerie), ou l'écarte.
    Alice ne l'envoie pas elle-même : c'est un second contact, il engage.
    """
    from app.agents.mission_log import log_event
    from app.models.mission import MissionEventKind

    application, title, company = await _application(db, candidate_id, application_id)
    meta = dict(application.metadata_json or {})
    followup = dict(meta.get("followup") or {})
    followup["status"] = body.status
    if body.status == "sent":
        followup["sent_at"] = datetime.now(timezone.utc).isoformat()
        await log_event(
            db, candidate_id, MissionEventKind.APPLIED,
            f"Relance envoyée chez {company} pour « {title} ».",
            {"application_id": str(application_id), "followup": True},
        )
    meta["followup"] = followup
    application.metadata_json = meta
    await db.commit()
    await db.refresh(application)
    return FollowupOut(**followup_state(application))


# ── Notifications ──────────────────────────────────────────────────────────


class NotificationPrefs(BaseModel):
    enabled: bool = True
    mission_report: bool = True
    application_sent: bool = True
    awaiting_approval: bool = True
    followups: bool = True
    digest: str = Field(default="weekly", pattern="^(off|daily|weekly)$")


class NotificationSettingsOut(BaseModel):
    prefs: NotificationPrefs
    recipient: str
    #: Faux tant qu'aucun service d'envoi n'est configuré : l'interface le dit.
    delivery_configured: bool


class NotificationOut(BaseModel):
    id: UUID
    kind: str
    status: str
    subject: str
    error: str | None
    created_at: datetime


async def _candidate(db: AsyncSession, candidate_id: UUID) -> Candidate:
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidat introuvable")
    return candidate


@router.get("/notifications", response_model=NotificationSettingsOut)
async def get_notification_settings(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    from app.agents.notifications import resolve_prefs
    from app.config import settings

    candidate = await _candidate(db, candidate_id)
    return NotificationSettingsOut(
        prefs=NotificationPrefs(**resolve_prefs(candidate)),
        recipient=candidate.email,
        delivery_configured=settings.can_notify,
    )


@router.put("/notifications", response_model=NotificationSettingsOut)
async def set_notification_settings(
    candidate_id: UUID, prefs: NotificationPrefs, db: AsyncSession = Depends(get_db),
):
    from app.config import settings

    candidate = await _candidate(db, candidate_id)
    candidate.notification_prefs = prefs.model_dump()
    await db.commit()
    return NotificationSettingsOut(
        prefs=prefs, recipient=candidate.email, delivery_configured=settings.can_notify,
    )


@router.post("/notifications/test", response_model=NotificationOut)
async def send_test_notification(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    from app.agents.notifications import send_test

    await _candidate(db, candidate_id)
    record = await send_test(candidate_id)
    if not record:
        raise HTTPException(500, "L'essai n'a pas pu être enregistré.")
    return NotificationOut(
        id=record.id, kind=record.kind.value, status=record.status.value,
        subject=record.subject, error=record.error,
        created_at=record.created_at or datetime.now(timezone.utc),
    )


@router.get("/notifications/history", response_model=list[NotificationOut])
async def notification_history(
    candidate_id: UUID,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Notification)
        .where(Notification.candidate_id == candidate_id)
        # Les alertes adressées à l'équipe ne sont pas des messages au candidat.
        .where(Notification.kind != NotificationKind.INCIDENT)
        .order_by(desc(Notification.created_at))
        .limit(limit)
    )).scalars().all()
    return [
        NotificationOut(
            id=n.id, kind=n.kind.value, status=n.status.value, subject=n.subject,
            error=n.error, created_at=n.created_at,
        )
        for n in rows
    ]
