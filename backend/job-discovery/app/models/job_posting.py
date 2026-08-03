"""
JobPosting model — a discovered job listing from a company's career page.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class RemotePolicy(str, enum.Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class ContractType(str, enum.Enum):
    CDI = "cdi"
    CDD = "cdd"
    FREELANCE = "freelance"
    STAGE = "stage"
    ALTERNANCE = "alternance"
    INTERIM = "interim"
    UNKNOWN = "unknown"


class ApplyChannel(str, enum.Enum):
    """How to apply to this job."""
    GREENHOUSE_API = "greenhouse_api"
    LEVER_API = "lever_api"
    WORKABLE_API = "workable_api"
    ASHBY_API = "ashby_api"
    WEB_FORM = "web_form"
    EMAIL = "email"
    EXTERNAL_LINK = "external_link"
    UNKNOWN = "unknown"


class ApplyComplexity(str, enum.Enum):
    """How easy it is to auto-apply."""
    SIMPLE = "simple"      # One-click or API-submittable
    MEDIUM = "medium"      # Form with a few fields
    COMPLEX = "complex"    # Multi-step, account required, captcha


class PostingStatus(str, enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    EXPIRED = "expired"


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── Source identity ──────────────────────────────────
    external_id: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="ID in the source ATS (Greenhouse job ID, Lever posting ID, etc.)"
    )
    fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True,
        comment="SHA-256 hash for deduplication"
    )

    # ── Job details ──────────────────────────────────────
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_parsed: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Structured extraction by LLM (Sprint 2)"
    )

    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    remote_policy: Mapped[RemotePolicy] = mapped_column(
        Enum(RemotePolicy), nullable=False, default=RemotePolicy.UNKNOWN
    )
    contract_type: Mapped[ContractType] = mapped_column(
        Enum(ContractType), nullable=False, default=ContractType.UNKNOWN
    )
    experience_range: Mapped[str | None] = mapped_column(String(50), nullable=True)
    salary_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tech_stack: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Application ──────────────────────────────────────
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    apply_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    apply_channel: Mapped[ApplyChannel] = mapped_column(
        Enum(ApplyChannel), nullable=False, default=ApplyChannel.UNKNOWN
    )
    apply_complexity: Mapped[ApplyComplexity] = mapped_column(
        Enum(ApplyComplexity), nullable=False, default=ApplyComplexity.MEDIUM
    )
    #: Coordonnées de candidature quand la source en fournit (courriel du
    #: recruteur, URL de postulation directe). C'est ce qui rend une offre
    #: candidatable autrement qu'en traversant un portail authentifié.
    contact_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Lifecycle ────────────────────────────────────────
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[PostingStatus] = mapped_column(
        Enum(PostingStatus), nullable=False, default=PostingStatus.ACTIVE, index=True
    )

    # ── Matching (Sprint 2) ──────────────────────────────
    match_score: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="0-100 matching score vs candidate profile"
    )

    # ── Timestamps ───────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ────────────────────────────────────
    company = relationship("Company", back_populates="job_postings")

    def __repr__(self) -> str:
        return f"<JobPosting '{self.title}' @ {self.company_id} [{self.status.value}]>"
