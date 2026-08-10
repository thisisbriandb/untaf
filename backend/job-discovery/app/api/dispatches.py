"""
API des candidatures — file d'approbation et historique.

C'est la contrepartie de l'autonomie : tout ce qu'Alice s'apprête à faire est
consultable avant, et tout ce qu'elle a fait est consultable après.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.application.dispatcher import prepare_dispatch, send_dispatch
from app.agents.mission_log import log_event
from app.auth.dependencies import require_owner
from app.database import get_db
from app.models.dispatch import ApplicationDispatch, DispatchChannel, DispatchStatus
from app.models.mission import MissionEventKind

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/candidates/{candidate_id}/dispatches", tags=["dispatches"],
    dependencies=[Depends(require_owner)],
)


class DispatchOut(BaseModel):
    id: UUID
    application_id: UUID
    job_title: str
    company_name: str
    channel: DispatchChannel
    destination: str | None
    status: DispatchStatus
    documents: dict | None
    error: str | None
    proof: dict | None
    approved_at: datetime | None
    sent_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PrepareRequest(BaseModel):
    application_id: UUID
    run_id: UUID | None = None


class DispatchSummary(BaseModel):
    awaiting_approval: int = 0
    approved: int = 0
    sent: int = 0
    simulated: int = 0
    failed: int = 0
    blocked: int = 0


@router.get("", response_model=list[DispatchOut])
async def list_dispatches(
    candidate_id: UUID,
    status: DispatchStatus | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Historique des candidatures, du plus récent au plus ancien."""
    query = select(ApplicationDispatch).where(
        ApplicationDispatch.candidate_id == candidate_id
    )
    if status:
        query = query.where(ApplicationDispatch.status == status)

    return (await db.execute(
        query.order_by(ApplicationDispatch.created_at.desc()).limit(limit)
    )).scalars().all()


@router.get("/summary", response_model=DispatchSummary)
async def dispatch_summary(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """Compteurs par état — la source des chiffres affichés à l'utilisateur."""
    rows = (await db.execute(
        select(ApplicationDispatch.status, ApplicationDispatch.error)
        .where(ApplicationDispatch.candidate_id == candidate_id)
    )).all()

    summary = DispatchSummary()
    for status, error in rows:
        if status == DispatchStatus.AWAITING_APPROVAL:
            summary.awaiting_approval += 1
        elif status == DispatchStatus.APPROVED:
            summary.approved += 1
        elif status == DispatchStatus.SENT:
            summary.sent += 1
        elif status == DispatchStatus.SIMULATED:
            summary.simulated += 1
        elif status == DispatchStatus.FAILED:
            summary.failed += 1
        elif status == DispatchStatus.PREPARED:
            summary.blocked += 1

    return summary


@router.post("/prepare", response_model=DispatchOut, status_code=201)
async def prepare(
    candidate_id: UUID,
    body: PrepareRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Prépare une candidature et détermine si elle peut partir.

    Ne l'envoie pas : préparer et envoyer sont deux gestes distincts, pour
    qu'aucun chemin ne puisse court-circuiter l'autorisation.
    """
    dispatch = await prepare_dispatch(candidate_id, body.application_id, body.run_id)
    if not dispatch:
        raise HTTPException(404, "Candidature ou offre introuvable")
    return dispatch


@router.post("/{dispatch_id}/approve", response_model=DispatchOut)
async def approve(
    candidate_id: UUID,
    dispatch_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Feu vert de l'utilisateur, puis envoi immédiat."""
    dispatch = await db.get(ApplicationDispatch, dispatch_id)
    if not dispatch or dispatch.candidate_id != candidate_id:
        raise HTTPException(404, "Envoi introuvable")
    if dispatch.status not in (DispatchStatus.AWAITING_APPROVAL, DispatchStatus.PREPARED):
        raise HTTPException(409, f"Statut « {dispatch.status.value} » : rien à approuver.")

    dispatch.status = DispatchStatus.APPROVED
    dispatch.approved_at = datetime.now(timezone.utc)
    dispatch.error = None
    await db.commit()

    sent = await send_dispatch(dispatch_id)

    async with db.begin_nested():
        await log_event(
            db, candidate_id,
            MissionEventKind.APPLIED if sent and sent.status == DispatchStatus.SENT
            else MissionEventKind.ERROR,
            (
                f"Candidature envoyée à {sent.company_name} pour « {sent.job_title} »."
                if sent and sent.status == DispatchStatus.SENT
                else f"Envoi vers {dispatch.company_name} non abouti : "
                     f"{(sent.error if sent else 'erreur inconnue')}"
            ),
            {"dispatch_id": str(dispatch_id)},
        )
    await db.commit()

    return sent or dispatch


@router.post("/{dispatch_id}/reject", response_model=DispatchOut)
async def reject(
    candidate_id: UUID,
    dispatch_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Refus de l'utilisateur — la candidature ne partira pas."""
    dispatch = await db.get(ApplicationDispatch, dispatch_id)
    if not dispatch or dispatch.candidate_id != candidate_id:
        raise HTTPException(404, "Envoi introuvable")
    if dispatch.status == DispatchStatus.SENT:
        raise HTTPException(409, "Déjà envoyée — impossible de revenir dessus.")

    dispatch.status = DispatchStatus.REJECTED
    await db.commit()
    await db.refresh(dispatch)
    return dispatch
