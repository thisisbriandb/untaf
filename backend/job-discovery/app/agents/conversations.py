"""Conversations avec Alice : ouverture, fil, enregistrement des tours."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.database import async_session
from app.models.conversation import Conversation, ConversationMessage

#: Tours relus pour donner son contexte à Alice.
HISTORY_TURNS = 12


def _title(message: str) -> str:
    text = " ".join(message.split())
    return (text[:77] + "…") if len(text) > 80 else (text or "Conversation")


async def open_conversation(
    candidate_id: UUID, conversation_id: str | None, first_message: str,
) -> Conversation:
    """La conversation demandée si elle appartient au candidat, sinon une nouvelle."""
    async with async_session() as session:
        if conversation_id:
            try:
                conv = await session.get(Conversation, UUID(conversation_id))
            except ValueError:
                conv = None
            # Une conversation d'un autre candidat n'est jamais rouverte.
            if conv and conv.candidate_id == candidate_id:
                return conv
        conv = Conversation(candidate_id=candidate_id, title=_title(first_message))
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        return conv


async def history_for(conversation_id: UUID) -> list[dict]:
    async with async_session() as session:
        rows = (await session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(HISTORY_TURNS)
        )).scalars().all()
    return [{"sender": m.sender, "text": m.text} for m in reversed(rows)]


async def append_turn(conversation_id: UUID, user_text: str, reply: str, ui_blocks: list) -> None:
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        session.add(ConversationMessage(
            conversation_id=conversation_id, sender="user", text=user_text, created_at=now,
        ))
        session.add(ConversationMessage(
            conversation_id=conversation_id, sender="alice", text=reply,
            ui_blocks=ui_blocks or None,
            # Une microseconde après : l'ordre du fil ne dépend pas de l'horloge de la base.
            created_at=now.replace(microsecond=min(now.microsecond + 1, 999_999)),
        ))
        conv = await session.get(Conversation, conversation_id)
        if conv:
            conv.updated_at = now
        await session.commit()
