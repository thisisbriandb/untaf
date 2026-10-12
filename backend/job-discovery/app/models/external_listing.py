"""
Offre relayée par un agrégateur (Adzuna, Jooble) pour Alice Community.

Rangée à part des JobPosting : Alice n'y postule pas elle-même (le lien mène
à la page de l'agrégateur), et l'agrégateur peut exiger qu'on retire ses
données à la fin du partenariat — une table, une suppression.

Seuls l'intitulé, l'employeur, le lieu, un extrait et le lien sont gardés :
ce que la liste affiche, et ce qu'il faut pour préparer un dossier quand un
candidat choisit l'offre.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ExternalListing(Base):
    __tablename__ = "external_listings"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_external_listing_source_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: "adzuna" ou "jooble".
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str] = mapped_column(String(300), nullable=False)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    #: "alternance" ou "stage".
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Lien fourni par l'agrégateur (page de l'offre chez lui, qui mène à l'annonce).
    url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
