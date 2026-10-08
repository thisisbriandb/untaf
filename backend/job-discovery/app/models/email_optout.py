"""
Les adresses (ou domaines entiers) qui ne veulent plus recevoir de
candidatures spontanées. Vérifié avant chaque envoi spontané, sans exception.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class EmailOptout(Base):
    __tablename__ = "email_optouts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: « jobs@acme.fr » pour une adresse, « @acme.fr » pour tout le domaine.
    value: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
