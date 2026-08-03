"""
Application model — represents a candidate's application to a discovered job.
Includes match score, current application status, and process tracking metadata.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class ApplicationStatus(str, enum.Enum):
    PENDING = "pending"          # Not yet reviewed
    MATCHED = "matched"          # High score, waiting for candidate decision
    APPLIED = "applied"          # Application submitted (either auto or manual)
    REJECTED = "rejected"        # Candidate rejected the match or company rejected application
    INTERVIEW = "interview"      # Candidate is interviewing
    OFFER = "offer"              # Offer received
    CLOSED = "closed"            # Process ended without success


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_posting_id", name="uq_candidate_job"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── Status & Scoring ──────────────────────────────────
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus), nullable=False, default=ApplicationStatus.PENDING, index=True
    )
    match_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── History & Custom Steps ─────────────────────────────
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Tracks apply history, step guidance, resume adapted versions, etc."
    )

    # ── Timestamps ────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ────────────────────────────────────
    candidate = relationship("Candidate", back_populates="applications")
    job_posting = relationship("JobPosting", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Application Candidate={self.candidate_id} Job={self.job_posting_id} Status={self.status.value}>"
