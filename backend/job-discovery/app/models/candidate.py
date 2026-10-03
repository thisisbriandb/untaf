"""
Candidate model — represents a candidate's profile, skills, and preferences.
Used for matching against scraped job postings.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, Text, Float, DateTime, LargeBinary
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Identity & Contact ────────────────────────────────
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── Links ─────────────────────────────────────────────
    github_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Professional Profile ──────────────────────────────
    headline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    experience_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    resume_raw: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── CV d'origine ──────────────────────────────────────
    # Conservé tel que déposé. Sans lui, « garder mon CV original » est une
    # promesse intenable : le document disparaîtrait à la fin de l'onboarding.
    # Stocké en base plutôt que sur disque — quelques centaines de Ko par
    # candidat, et rien à monter ni à sauvegarder à part la base elle-même.
    resume_file: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    resume_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resume_mime: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Parcours détaillé ─────────────────────────────────
    # Expériences, formation, langues. Ces données ne vivaient que dans le
    # navigateur : Alice, qui rédige côté serveur, ne pouvait donc argumenter
    # à partir de rien — d'où des lettres génériques par construction.
    cv_content: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment='{"summary": str, "experiences": [...], "education": [...], '
                '"languages": [...]}',
    )

    # ── Signature manuscrite ──────────────────────────────
    # Data URL PNG. Réutilisée automatiquement sur chaque lettre générée.
    signature_image: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Choix de présentation du CV ───────────────────────
    # `mode` vaut "original" tant que le candidat n'a pas explicitement demandé
    # un modèle. Aucun template, aucune palette n'est appliqué sans son geste.
    cv_design: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment='{"mode": "original"|"template", "template_id": str, '
                '"color_hex": str, "show_photo": bool}',
    )

    # ── Preferences ───────────────────────────────────────
    preferred_locations: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list,
        comment="Cities/regions of interest, e.g. ['Paris', 'Lyon']"
    )
    preferred_remote_policies: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list,
        comment="e.g. ['remote', 'hybrid']"
    )
    preferred_contract_types: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list,
        comment="e.g. ['cdi', 'freelance']"
    )

    # ── Mandat de matching ────────────────────────────────
    matching_criteria: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="MatchingCriteria: filtres durs (langue, pays, métier, exclusions) "
                "et pondérations. Null = dérivé du profil à la volée."
    )

    # ── Notifications ─────────────────────────────────────
    # Ce qu'Alice a le droit d'écrire au candidat, et à quel rythme. Null =
    # réglages par défaut (voir `app.agents.notifications.DEFAULT_PREFS`).
    notification_prefs: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment='{"enabled": bool, "mission_report": bool, "application_sent": bool, '
                '"awaiting_approval": bool, "followups": bool, "digest": "off"|"daily"|"weekly"}',
    )

    # ── Timestamps ────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ────────────────────────────────────
    applications = relationship(
        "Application", back_populates="candidate", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Candidate {self.full_name} ({self.email})>"
