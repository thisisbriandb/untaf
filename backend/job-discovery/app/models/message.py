"""
Réponses reçues par le candidat suite à ses candidatures.

Cette table est le vrai stockage de l'onglet « Messages » — plus de donnée
inventée côté frontend. Elle reste vide tant qu'aucune source réelle
(boîte mail suivie en IMAP, webhook d'un fournisseur d'emailing) n'y écrit ;
brancher une telle source est un chantier séparé, non fait ici.

`dispatch_id` relie une réponse à la candidature qui l'a provoquée quand
c'est identifiable (ex. réponse dans le même fil qu'un envoi tracé) ; sinon
la réponse reste rattachée au seul candidat.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Boolean, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class MessageDirection(str, enum.Enum):
    INBOUND = "inbound"    # Reçu d'un recruteur ou d'un employeur
    OUTBOUND = "outbound"  # Envoyé par Alice ou le candidat — réservé, non utilisé aujourd'hui


class RecruiterMessage(Base):
    __tablename__ = "recruiter_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    dispatch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("application_dispatches.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="Candidature d'origine, quand la réponse a pu y être rattachée.",
    )

    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection), nullable=False, default=MessageDirection.INBOUND,
    )
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<RecruiterMessage {self.subject or '(sans objet)'} candidate={self.candidate_id}>"
