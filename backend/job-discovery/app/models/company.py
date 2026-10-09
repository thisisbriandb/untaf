"""
Company model — represents a company being monitored for job postings.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Text, Boolean, Integer, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class ATSType(str, enum.Enum):
    """Known ATS platforms."""
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    WORKABLE = "workable"
    ASHBY = "ashby"
    SMARTRECRUITERS = "smartrecruiters"
    RECRUITEE = "recruitee"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class CompanyStatus(str, enum.Enum):
    """ATS resolution status — determines scraping strategy."""
    PENDING = "pending"                # Not yet resolved
    ATS_DIRECT = "ats_direct"          # Lever/Greenhouse/Workable → auto-apply via API
    FORM_STANDARD = "form_standard"    # Simple HTML form → auto via Playwright
    COMPLEX_WORKDAY = "complex_workday"  # Needs account creation → guided
    NO_CAREER_PAGE = "no_career_page"  # No careers page found → skip
    ERROR = "error"                    # Resolution failed


class SeedSource(str, enum.Enum):
    """How the company was discovered."""
    WTTJ_SITEMAP = "wttj_sitemap"
    ECOSYSTEM_FT120 = "ecosystem_ft120"
    ECOSYSTEM_NEXT40 = "ecosystem_next40"
    ECOSYSTEM_VC = "ecosystem_vc"
    SIRENE_API = "sirene_api"
    ATS_INDEX = "ats_index"
    MANUAL = "manual"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Identity ─────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    siren: Mapped[str | None] = mapped_column(String(9), nullable=True)

    # ── Careers / ATS ────────────────────────────────────
    careers_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ats_type: Mapped[ATSType] = mapped_column(
        Enum(ATSType), nullable=False, default=ATSType.UNKNOWN
    )
    ats_slug: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="board_token (Greenhouse) or company_slug (Lever)"
    )
    status: Mapped[CompanyStatus] = mapped_column(
        Enum(CompanyStatus), nullable=False, default=CompanyStatus.PENDING, index=True
    )

    # ── Contact pour les candidatures spontanées ─────────
    #: Site de l'entreprise, vérifié (la page d'accueil porte son nom).
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Adresse publiée par l'entreprise elle-même — jamais devinée.
    careers_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    careers_email_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: recrutement | general
    careers_email_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: Ce que l'entreprise dit d'elle-même (accueil du site), pour la lettre.
    about: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Metadata ─────────────────────────────────────────
    sector: Mapped[str | None] = mapped_column(String(255), nullable=True)
    naf_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    size_category: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="startup / pme / eti / grand_groupe"
    )
    location_hq: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seed_source: Mapped[SeedSource] = mapped_column(
        Enum(SeedSource), nullable=False, default=SeedSource.MANUAL
    )

    # ── Scraping state ───────────────────────────────────
    scrape_frequency_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolve_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Timestamps ───────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ────────────────────────────────────
    # Une entreprise anonyme (« Employeur non précisé ») porte des milliers
    # d'offres : on ne les charge jamais avec elle.
    job_postings = relationship("JobPosting", back_populates="company", lazy="noload")

    def __repr__(self) -> str:
        return f"<Company {self.name} ({self.domain}) status={self.status.value}>"
