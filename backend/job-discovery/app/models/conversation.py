"""
Conversations avec Alice, conservées côté serveur.

L'historique transitait par le navigateur à chaque tour et disparaissait avec
lui : changer d'appareil, c'était repartir de zéro, et Alice oubliait ce qui
avait été dit. Ici chaque échange est enregistré ; l'utilisateur retrouve ses
conversations partout, et Alice relit le fil depuis la base, pas depuis ce que
le client veut bien lui envoyer.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    #: Tiré du premier message — c'est ce qui permet de s'y retrouver.
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="Conversation")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True,
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    #: user | alice
    sender: Mapped[str] = mapped_column(String(10), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: Blocs affichés sous le message (offres, bilan, action Canvas) : la
    #: conversation se relit telle qu'elle a été vue.
    ui_blocks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True,
    )
