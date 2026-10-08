"""
Abonnement et consommation.

`Subscription` est le reflet local d'un abonnement Lemon Squeezy, tenu à jour
par ses webhooks : la source de vérité reste chez Lemon Squeezy, on n'en garde
que ce qu'il faut pour décider d'un accès sans l'appeler.

`UsageEvent` compte ce qui coûte (dossier rédigé, mission, message à Alice,
candidature spontanée) : c'est sur ces lignes que s'appliquent les limites.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), index=True,
    )
    provider: Mapped[str] = mapped_column(String(30), default="lemonsqueezy")
    #: Identifiant de l'abonnement chez le fournisseur.
    provider_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    variant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: on_trial | active | paused | past_due | unpaid | cancelled | expired
    status: Mapped[str] = mapped_column(String(20))
    renews_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Fin d'accès d'un abonnement résilié (fin de la semaine déjà payée).
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    test_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_events_candidate_kind_at", "candidate_id", "kind", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"),
    )
    #: pack | mission | message | spontaneous
    kind: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
