"""
Trace des candidatures envoyées.

Rien ne doit partir sans laisser d'enregistrement : ni Alice ni l'utilisateur
ne peuvent rendre compte de ce qui n'est pas écrit. Cette table est la mémoire
des actions — quelle offre, par quel canal, avec quels documents, quand, et
avec quel résultat.

Elle sert aussi de garde-fou contre les doublons : deux candidatures à la même
offre grillent le candidat auprès du recruteur.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Index, LargeBinary, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func, text

from app.database import Base


class DispatchChannel(str, enum.Enum):
    EMAIL = "email"
    WEB_FORM = "web_form"
    ATS_API = "ats_api"
    MANUAL = "manual"


class DispatchStatus(str, enum.Enum):
    """
    Cycle de vie d'un envoi.

    `AWAITING_APPROVAL` est le cœur du dispositif : une candidature préparée
    n'est jamais envoyée tant que l'autorisation ne le permet pas.
    """

    PREPARED = "prepared"                  # Documents prêts, canal identifié
    AWAITING_APPROVAL = "awaiting_approval"  # Attend le feu vert de l'utilisateur
    APPROVED = "approved"                  # Autorisée, en file d'envoi
    SENT = "sent"                          # Partie, avec preuve
    FAILED = "failed"                      # Échec technique, motif enregistré
    REJECTED = "rejected"                  # Refusée par l'utilisateur
    SIMULATED = "simulated"                # Répétition : rien n'est parti


class ApplicationDispatch(Base):
    __tablename__ = "application_dispatches"
    __table_args__ = (
        # Un seul envoi ABOUTI par offre. Index partiel : les échecs et les
        # simulations peuvent se répéter, un envoi réel non — deux candidatures
        # à la même offre grillent le candidat auprès du recruteur.
        Index(
            "uq_dispatch_sent_once",
            "application_id",
            unique=True,
            postgresql_where=text("status = 'SENT'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mission_runs.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="Mission qui a produit cette candidature, si elle vient d'un run.",
    )

    # ── Cible ─────────────────────────────────────────────
    job_title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    company_name: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    channel: Mapped[DispatchChannel] = mapped_column(
        Enum(DispatchChannel), nullable=False, default=DispatchChannel.MANUAL
    )
    destination: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Adresse email ou URL du formulaire."
    )

    # ── Contenu envoyé ────────────────────────────────────
    # Métadonnées lisibles (quel modèle de CV, quel objet de lettre).
    documents: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Copie figée des pièces elles-mêmes. Le CV et la lettre du candidat
    # évoluent après coup ; sans cet instantané, « télécharger ce qui a été
    # envoyé » ne pourrait que régénérer un document ressemblant, ce qui
    # reviendrait à présenter une reconstitution comme une preuve.
    resume_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    resume_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    letter_subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    letter_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Résultat ──────────────────────────────────────────
    status: Mapped[DispatchStatus] = mapped_column(
        Enum(DispatchStatus), nullable=False,
        default=DispatchStatus.PREPARED, index=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Preuve d'envoi : id de message SMTP, capture, réponse HTTP.",
    )

    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    application = relationship("Application")

    def __repr__(self) -> str:
        return f"<Dispatch {self.job_title[:30]} {self.channel.value} {self.status.value}>"
