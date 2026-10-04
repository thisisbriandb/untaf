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
    model_config = {"from_attributes": True}


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
    return (await db.execute(
        select(Conversation)
        .where(Conversation.candidate_id == candidate_id)
        .order_by(desc(Conversation.updated_at))
        .limit(limit)
    )).scalars().all()


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
