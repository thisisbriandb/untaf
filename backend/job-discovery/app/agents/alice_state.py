"""
État réel du système — la source de vérité unique d'Alice.

Toute réponse chiffrée passe par ici. Avant, chaque appelant recomptait à sa
façon : le briefing d'accueil comptait les offres en attente, `search_jobs`
renvoyait tout y compris les candidatures déjà envoyées. Alice annonçait donc
« j'en ai retenu 3 » puis en affichait 4 — deux vérités pour une seule réalité.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func

from app.database import async_session
from app.models.application import Application, ApplicationStatus
from app.models.candidate import Candidate
from app.models.job_posting import JobPosting, PostingStatus
from app.models.mission import Mission, MissionRun, RunStatus

logger = logging.getLogger(__name__)

#: Statuts qui sortent une offre de la liste « à traiter ». Une candidature
#: envoyée n'est plus une opportunité à présenter.
CLOSED_STATUSES = {
    ApplicationStatus.APPLIED,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.OFFER,
    ApplicationStatus.REJECTED,
    ApplicationStatus.CLOSED,
}

#: Statuts qui composent la liste d'offres proposées au candidat.
OPEN_STATUSES = {ApplicationStatus.MATCHED, ApplicationStatus.PENDING}


@dataclass
class AliceState:
    """Instantané vérifiable de ce que le système sait à un instant donné."""

    candidate_id: UUID
    full_name: str = ""
    headline: str = ""

    # Offres
    shortlisted: int = 0          # proposées, en attente de décision
    applied: int = 0              # candidatures envoyées
    interviews: int = 0
    total_active_postings: int = 0
    qualified_postings: int = 0

    # Mission
    mission_status: str = "active"
    autonomy: str = "propose"
    last_scan_at: datetime | None = None
    scanned_last_run: int = 0
    run_status: str | None = None
    run_title: str | None = None
    run_seconds_remaining: int = 0

    # Documents prêts
    letters_ready: int = 0
    packs_ready: int = 0

    # Ce qui attend le candidat
    awaiting_approval: int = 0
    followups_due: int = 0

    # Son CV
    cv_presentation: str = "aucun"     # original (PDF déposé) | modèle <id> | aucun
    cv_missing_sections: list[str] = field(default_factory=list)

    # Capacités de ce déploiement — ce qu'Alice peut réellement faire
    can_send_email: bool = False
    can_submit_forms: bool = False

    warnings: list[str] = field(default_factory=list)

    def as_facts(self) -> dict:
        """Forme compacte injectée dans le contexte du modèle."""
        return {
            "offres_proposees": self.shortlisted,
            "candidatures_envoyees": self.applied,
            "entretiens": self.interviews,
            "lettres_pretes": self.letters_ready,
            "offres_en_base": self.total_active_postings,
            "derniere_veille": (
                self.last_scan_at.isoformat() if self.last_scan_at else None
            ),
            "offres_vues_derniere_veille": self.scanned_last_run,
            "mission": self.mission_status,
            "autonomie": self.autonomy,
            "mission_en_cours": self.run_title if self.run_status == "running" else None,
            "dossiers_prets": self.packs_ready,
            "candidatures_a_valider": self.awaiting_approval,
            "relances_a_faire": self.followups_due,
            "cv_presentation": self.cv_presentation,
            "cv_sections_vides": self.cv_missing_sections,
            "envoi_email_actif": self.can_send_email,
            "envoi_formulaires_actif": self.can_submit_forms,
        }


async def load_state(candidate_id: UUID) -> AliceState:
    """Lit l'état réel. Ne devine rien, ne complète rien."""
    async with async_session() as session:
        candidate = await session.get(Candidate, candidate_id)
        if not candidate:
            return AliceState(candidate_id=candidate_id, warnings=["candidat introuvable"])

        state = AliceState(
            candidate_id=candidate_id,
            full_name=candidate.full_name or "",
            headline=candidate.headline or "",
        )

        counts = dict((await session.execute(
            select(Application.status, func.count(Application.id))
            .where(Application.candidate_id == candidate_id)
            .group_by(Application.status)
        )).all())

        state.shortlisted = sum(counts.get(s, 0) for s in OPEN_STATUSES)
        state.applied = counts.get(ApplicationStatus.APPLIED, 0)
        state.interviews = counts.get(ApplicationStatus.INTERVIEW, 0)

        state.total_active_postings = (await session.execute(
            select(func.count(JobPosting.id))
            .where(JobPosting.status == PostingStatus.ACTIVE)
        )).scalar() or 0
        state.qualified_postings = (await session.execute(
            select(func.count(JobPosting.id))
            .where(JobPosting.status == PostingStatus.ACTIVE)
            .where(JobPosting.description_parsed.is_not(None))
        )).scalar() or 0

        # Lettres réellement rédigées et rattachées à une offre.
        apps = (await session.execute(
            select(Application.metadata_json)
            .where(Application.candidate_id == candidate_id)
        )).scalars().all()
        state.letters_ready = sum(1 for m in apps if (m or {}).get("cover_letter"))
        state.packs_ready = sum(
            1 for m in apps if (m or {}).get("cover_letter") and (m or {}).get("tailored_cv")
        )

        from app.agents.application.cv_completeness import missing_sections
        from app.agents.application.followup import due_followups
        from app.config import settings
        from app.models.dispatch import ApplicationDispatch, DispatchStatus

        state.awaiting_approval = (await session.execute(
            select(func.count(ApplicationDispatch.id))
            .where(ApplicationDispatch.candidate_id == candidate_id)
            .where(ApplicationDispatch.status == DispatchStatus.AWAITING_APPROVAL)
        )).scalar() or 0
        state.followups_due = len(await due_followups(session, candidate_id))

        design = candidate.cv_design or {}
        if design.get("mode") == "template" and design.get("template_id"):
            state.cv_presentation = f"modèle {design['template_id']}"
        elif candidate.resume_file:
            state.cv_presentation = "original (PDF déposé, non modifiable)"
        state.cv_missing_sections = missing_sections(candidate)
        state.can_send_email = settings.can_send_email
        state.can_submit_forms = settings.browser_submit_enabled

        mission = (await session.execute(
            select(Mission).where(Mission.candidate_id == candidate_id)
        )).scalars().first()
        if mission:
            state.mission_status = mission.status.value
            state.autonomy = mission.autonomy.value
            state.last_scan_at = mission.last_run_at

            run = (await session.execute(
                select(MissionRun)
                .where(MissionRun.mission_id == mission.id)
                .order_by(MissionRun.created_at.desc())
                .limit(1)
            )).scalars().first()
            if run:
                state.run_status = run.status.value
                state.run_title = run.title
                state.scanned_last_run = (run.stats or {}).get("scanned", 0)
                if run.status == RunStatus.RUNNING and run.ends_at:
                    state.run_seconds_remaining = max(
                        0, int((run.ends_at - datetime.now(timezone.utc)).total_seconds())
                    )

    return state
