"""
API des messages reçus — réponses de recruteurs.

Aujourd'hui rien n'écrit automatiquement dans cette table : il n'y a pas
encore de boîte mail suivie en IMAP ni de webhook branché (voir ROADMAP.md,
Étape 5). `POST /` existe pour qu'un futur connecteur — ou un test manuel —
ait un point d'entrée unique, plutôt que d'attendre que ce connecteur
existe pour donner à l'onglet une vraie source de données.
"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_owner
from app.database import get_db
from app.models.message import RecruiterMessage, MessageDirection

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/candidates/{candidate_id}/messages", tags=["messages"],
    dependencies=[Depends(require_owner)],
)


class MessageOut(BaseModel):
    id: UUID
    dispatch_id: UUID | None
    direction: MessageDirection
    sender_name: str | None
    sender_email: str | None
    company_name: str | None
    subject: str | None
    body: str
    is_read: bool
    received_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    dispatch_id: UUID | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    company_name: str | None = None
    subject: str | None = None
    body: str


class MessageSummary(BaseModel):
    unread: int = 0
    total: int = 0


@router.get("", response_model=list[MessageOut])
async def list_messages(
    candidate_id: UUID,
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Messages reçus, du plus récent au plus ancien."""
    query = select(RecruiterMessage).where(
        RecruiterMessage.candidate_id == candidate_id
    )
    if unread_only:
        query = query.where(RecruiterMessage.is_read.is_(False))

    return (await db.execute(
        query.order_by(RecruiterMessage.received_at.desc()).limit(limit)
    )).scalars().all()


@router.get("/summary", response_model=MessageSummary)
async def message_summary(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """Compteurs — source des chiffres affichés sur la cloche de notifications."""
    total = await db.scalar(
        select(func.count(RecruiterMessage.id))
        .where(RecruiterMessage.candidate_id == candidate_id)
    )
    unread = await db.scalar(
        select(func.count(RecruiterMessage.id))
        .where(RecruiterMessage.candidate_id == candidate_id)
        .where(RecruiterMessage.is_read.is_(False))
    )
    return MessageSummary(unread=unread or 0, total=total or 0)


@router.post("", response_model=MessageOut, status_code=201)
async def create_message(
    candidate_id: UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Enregistre un message reçu.

    Point d'entrée unique pour toute future source réelle (IMAP, webhook).
    Rien n'appelle cette route automatiquement aujourd'hui.
    """
    message = RecruiterMessage(
        candidate_id=candidate_id,
        dispatch_id=body.dispatch_id,
        direction=MessageDirection.INBOUND,
        sender_name=body.sender_name,
        sender_email=body.sender_email,
        company_name=body.company_name,
        subject=body.subject,
        body=body.body,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


@router.post("/read", response_model=dict)
async def mark_all_read(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """Marque tous les messages du candidat comme lus."""
    result = await db.execute(
        update(RecruiterMessage)
        .where(RecruiterMessage.candidate_id == candidate_id)
        .where(RecruiterMessage.is_read.is_(False))
        .values(is_read=True)
    )
    await db.commit()
    return {"marked": result.rowcount}


@router.post("/{message_id}/read", response_model=MessageOut)
async def mark_read(
    candidate_id: UUID,
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Marque un message comme lu."""
    message = await db.get(RecruiterMessage, message_id)
    if not message or message.candidate_id != candidate_id:
        raise HTTPException(404, "Message introuvable")

    message.is_read = True
    await db.commit()
    await db.refresh(message)
    return message
