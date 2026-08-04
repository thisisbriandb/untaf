"""
Mission — le mandat que le candidat confie à Alice, et le journal de ce
qu'elle en fait.

Un candidat a une seule mission active. Le mandat de recherche lui-même
(langues, pays, métiers, exclusions) reste porté par `Candidate.matching_criteria` :
il est déjà câblé de bout en bout depuis l'onboarding jusqu'au matcher, et
comme il n'y a qu'une mission par candidat, le déplacer n'apporterait rien
qu'un risque de régression. La mission porte ce qui est réellement nouveau :
le niveau d'autonomie, le rythme, et le récit.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class AutonomyLevel(str, enum.Enum):
    """Jusqu'où Alice peut aller sans repasser par le candidat."""

    PROPOSE = "propose"        # Elle présélectionne, le candidat valide chaque envoi
    AUTO_ABOVE = "auto_above"  # Envoi automatique au-dessus d'un score, proposition en dessous
    FULL = "full"              # Envoi automatique dans les limites du mandat


class MissionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class RunStatus(str, enum.Enum):
    """Cycle de vie d'une mission bornée dans le temps."""

    PREPARING = "preparing"      # Paramètres confirmés, pas encore démarrée
    RUNNING = "running"          # Alice travaille
    COMPLETED = "completed"      # Durée écoulée, travail terminé
    INTERRUPTED = "interrupted"  # Arrêtée par l'utilisateur, ou par un incident


class RunStep(str, enum.Enum):
    """Étapes de la pipeline, dans l'ordre d'exécution."""

    SCAN = "scan"            # Collecte des offres sur les plateformes
    QUALIFY = "qualify"      # Lecture et structuration des annonces
    MATCH = "match"          # Confrontation au mandat
    PREPARE = "prepare"      # Rédaction des lettres pour les offres retenues
    APPLY = "apply"          # Envoi des candidatures, si autorisé


class MissionEventKind(str, enum.Enum):
    """
    Types d'entrées du journal.

    Volontairement large dès maintenant : la file d'approbation et le suivi
    des réponses viendront s'y ranger sans migration.
    """

    MISSION_CREATED = "mission_created"
    MANDATE_CHANGED = "mandate_changed"
    AUTONOMY_CHANGED = "autonomy_changed"
    STATUS_CHANGED = "status_changed"

    SCAN = "scan"                          # Veille effectuée sur N offres
    SHORTLIST = "shortlist"                # Offre retenue
    DISCARD = "discard"                    # Offre écartée (avec le motif)
    CV_ADAPTED = "cv_adapted"
    LETTER_WRITTEN = "letter_written"
    APPLIED = "applied"
    AWAITING_APPROVAL = "awaiting_approval"
    REPLY = "reply"
    ERROR = "error"


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
        comment="Une seule mission par candidat.",
    )

    title: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Ma recherche"
    )
    status: Mapped[MissionStatus] = mapped_column(
        Enum(MissionStatus), nullable=False, default=MissionStatus.ACTIVE, index=True
    )

    # ── Autonomie ─────────────────────────────────────────
    autonomy: Mapped[AutonomyLevel] = mapped_column(
        Enum(AutonomyLevel), nullable=False, default=AutonomyLevel.PROPOSE
    )
    auto_apply_min_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=85,
        comment="Score à partir duquel AUTO_ABOVE envoie sans demander.",
    )
    weekly_quota: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10,
        comment="Nombre maximum de candidatures par semaine.",
    )

    #: Canaux qu'Alice a le droit d'emprunter. Vide = aucun envoi autonome.
    #: Le canal email est le seul activable sans réserve aujourd'hui.
    allowed_channels: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True,
        comment="email | web_form | ats_api",
    )
    #: Entreprises auxquelles Alice ne doit jamais écrire — employeur actuel,
    #: candidatures déjà en cours ailleurs, refus antérieurs.
    blocked_companies: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )

    # ── Suivi ─────────────────────────────────────────────
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    candidate = relationship("Candidate")
    events = relationship(
        "MissionEvent",
        back_populates="mission",
        cascade="all, delete-orphan",
        order_by="MissionEvent.created_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<Mission {self.title} candidate={self.candidate_id} {self.status.value}>"


class MissionRun(Base):
    """
    Une mission confiée pour une durée donnée.

    À distinguer de `Mission`, qui est le mandat permanent (autonomie, quota,
    critères). Un run est une exécution : « cherche pendant deux heures », avec
    un début, une fin, une progression et un compte rendu.
    """

    __tablename__ = "mission_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("missions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Recherche d'offres")
    objective: Mapped[str] = mapped_column(
        String(64), nullable=False, default="search",
        comment="search | prepare | apply — jusqu'où va la pipeline.",
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), nullable=False, default=RunStatus.PREPARING, index=True
    )
    current_step: Mapped[RunStep | None] = mapped_column(Enum(RunStep), nullable=True)

    #: Ce que l'utilisateur autorise explicitement pour ce run.
    allowed_actions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    #: Compteurs cumulés, rafraîchis à chaque étape.
    stats: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    #: Compte rendu final, rédigé par Alice.
    report: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment=(
            "Dernier signe de vie du worker. Un processus tué net ne peut pas "
            "clore son run : c'est l'absence de battement, et non le statut en "
            "base, qui permet de savoir qu'une mission n'existe plus."
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    mission = relationship("Mission")

    def __repr__(self) -> str:
        return f"<MissionRun {self.title} {self.status.value}>"


class MissionEvent(Base):
    """
    Une ligne du journal. C'est ce qui transforme un automate en mandataire :
    rendre des comptes de ce qui a été fait, sans avoir à le demander.
    """

    __tablename__ = "mission_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("missions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    #: Rattache l'événement à un run — le journal reste unique, l'activité
    #: d'une mission n'en est qu'une vue filtrée.
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mission_runs.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )

    kind: Mapped[MissionEventKind] = mapped_column(
        Enum(MissionEventKind), nullable=False, index=True
    )
    summary: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Phrase lisible telle qu'Alice la raconterait.",
    )
    payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Détail structuré : ids d'offres, motifs de rejet, compteurs.",
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    mission = relationship("Mission", back_populates="events")

    def __repr__(self) -> str:
        return f"<MissionEvent {self.kind.value} {self.created_at:%d/%m %H:%M}>"
