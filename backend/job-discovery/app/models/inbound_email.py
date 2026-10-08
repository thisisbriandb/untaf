"""
Réponses reçues des recruteurs.

Chaque candidat a une adresse de réponse à lui (`<jeton>@<domaine de réception>`),
utilisée dans les candidatures qu'Alice envoie ou remplit. Ce qui y arrive est
rangé ici, rattaché à la candidature quand on la reconnaît, lu par Alice
(refus, entretien, demande…) puis transféré au candidat.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class InboundEmail(Base):
    __tablename__ = "inbound_emails"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    #: Identifiant chez le fournisseur (ou Message-ID) : un e-mail n'est traité qu'une fois.
    provider_id: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    from_email: Mapped[str] = mapped_column(String(320), nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    to_email: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    html: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: interview | rejection | offer | request | acknowledgement | other
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="other")
    #: Ce qu'Alice en retient, en une phrase, et ce qu'il faut faire.
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    next_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    forwarded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class InboundAttachment(Base):
    """Pièce jointe d'une réponse (offre en PDF, test technique…), gardée telle quelle."""

    __tablename__ = "inbound_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inbound_email_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inbound_emails.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    mime: Mapped[str] = mapped_column(String(150), nullable=False, default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
