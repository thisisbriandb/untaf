"""Historique des conversations — retrouvé sur n'importe quel appareil."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.conversation import Conversation, ConversationMessage

router = APIRouter(prefix="/candidates/{candidate_id}/conversations", tags=["conversations"])


class ConversationOut(BaseModel):
    id: UUID
    title: str
    updated_at: datetime
    #: Offre dont parle la conversation — la barre latérale l'affiche sous le
    #: nom de l'entreprise.
    job_id: UUID | None = None
    company_name: str | None = None
    job_title: str | None = None


class MessageOut(BaseModel):
    id: UUID
    sender: str
    text: str
    ui_blocks: list | None
    created_at: datetime
    model_config = {"from_attributes": True}


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    candidate_id: UUID,
    limit: int = Query(default=30, le=100),
    db: AsyncSession = Depends(get_db),
):
    from app.models.company import Company
    from app.models.job_posting import JobPosting

    rows = (await db.execute(
        select(Conversation, JobPosting.title, Company.name)
        .outerjoin(JobPosting, Conversation.job_posting_id == JobPosting.id)
        .outerjoin(Company, JobPosting.company_id == Company.id)
        .where(Conversation.candidate_id == candidate_id)
        .order_by(desc(Conversation.updated_at))
        .limit(limit)
    )).all()
    return [
        ConversationOut(
            id=c.id, title=c.title, updated_at=c.updated_at,
            job_id=c.job_posting_id, company_name=company, job_title=job_title,
        )
        for c, job_title, company in rows
    ]


async def _owned(db: AsyncSession, candidate_id: UUID, conversation_id: UUID) -> Conversation:
    conv = await db.get(Conversation, conversation_id)
    if not conv or conv.candidate_id != candidate_id:
        raise HTTPException(404, "Conversation introuvable")
    return conv


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def conversation_messages(
    candidate_id: UUID, conversation_id: UUID, db: AsyncSession = Depends(get_db),
):
    await _owned(db, candidate_id, conversation_id)
    return (await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at)
        .limit(400)
    )).scalars().all()


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    candidate_id: UUID, conversation_id: UUID, db: AsyncSession = Depends(get_db),
):
    await db.delete(await _owned(db, candidate_id, conversation_id))
    await db.commit()
