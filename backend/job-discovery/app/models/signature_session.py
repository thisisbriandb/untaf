"""
Signer sur son téléphone : l'ordinateur ouvre une session, affiche un QR code
qui porte son jeton, le téléphone y dépose la signature, l'ordinateur la
récupère. Pas de compte requis (l'inscription n'est pas finie) : le jeton,
long et à usage unique, vaut dix minutes.

En base plutôt qu'en mémoire : avec plusieurs instances de l'API, le
téléphone et l'ordinateur ne tombent pas forcément sur la même.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class SignatureSession(Base):
    __tablename__ = "signature_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    #: Data URL PNG déposée par le téléphone ; vide tant qu'il n'a pas signé.
    image: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
