"""
Notifications envoyées au candidat.

La table sert deux fois : c'est l'historique de ce qu'Alice a écrit (« sais-je
ce qu'elle m'a envoyé ? »), et c'est le verrou anti-doublon — la clé
`dedupe_key` est unique, donc un compte rendu de mission ne part qu'une fois
même si la clôture est rejouée par le balayage des runs orphelins.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class NotificationKind(str, enum.Enum):
    MISSION_REPORT = "mission_report"        # Fin de mission, compte rendu
    APPLICATION_SENT = "application_sent"    # Une candidature est réellement partie
    AWAITING_APPROVAL = "awaiting_approval"  # Des candidatures attendent un feu vert
    FOLLOWUP_DUE = "followup_due"            # Une relance est à faire
    DIGEST = "digest"                        # Rapport d'activité périodique
    TEST = "test"                            # Envoi d'essai depuis les paramètres


class NotificationStatus(str, enum.Enum):
    SENT = "sent"            # Remis au service d'envoi
    SIMULATED = "simulated"  # Aucun service configuré : rien n'est parti
    FAILED = "failed"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    kind: Mapped[NotificationKind] = mapped_column(Enum(NotificationKind), nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus), nullable=False
    )
    #: Ce qui rend la notification unique : `mission_report:<run_id>`, etc.
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
