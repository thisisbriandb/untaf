"""
Envoi des candidatures.

Toute candidature passe par ici, quel que soit le canal. Le dispatcher répond à
une seule question : « ai-je le droit d'envoyer celle-ci, maintenant, par ce
canal ? » — et il enregistre sa réponse quoi qu'il arrive.

Trois principes non négociables :
  - rien ne part sans autorisation explicite du mandat ;
  - rien ne part deux fois ;
  - un envoi simulé n'est JAMAIS rapporté comme un envoi réel.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func

from app.database import async_session
from app.models.application import Application, ApplicationStatus
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.dispatch import ApplicationDispatch, DispatchChannel, DispatchStatus
from app.models.job_posting import ApplyChannel, JobPosting
from app.models.mission import AutonomyLevel, Mission, MissionStatus

logger = logging.getLogger(__name__)

#: Canal de l'offre → canal d'envoi.
CHANNEL_MAP = {
    ApplyChannel.EMAIL: DispatchChannel.EMAIL,
    ApplyChannel.GREENHOUSE_API: DispatchChannel.ATS_API,
    ApplyChannel.LEVER_API: DispatchChannel.ATS_API,
    ApplyChannel.ASHBY_API: DispatchChannel.ATS_API,
    ApplyChannel.WORKABLE_API: DispatchChannel.ATS_API,
    ApplyChannel.WEB_FORM: DispatchChannel.WEB_FORM,
    # Absent de la table, EXTERNAL_LINK retombait sur MANUAL et produisait le
    # message « canal manual pas encore automatisable » — incompréhensible.
    ApplyChannel.EXTERNAL_LINK: DispatchChannel.WEB_FORM,
}

#: Canaux réellement implémentés. Le reste est préparé mais pas envoyable —
#: mieux vaut une file d'attente honnête qu'un échec silencieux.
#: ATS_API regroupe Greenhouse/Lever/Ashby/Workable dans le mandat — seuls
#: les trois premiers ont un connecteur écrit (voir `ats_connectors.py`) ;
#: `send_dispatch` referme la porte sur Workable au moment de l'envoi.
IMPLEMENTED_CHANNELS = {DispatchChannel.EMAIL, DispatchChannel.ATS_API}


@dataclass
class Decision:
    """Verdict du dispatcher, toujours motivé."""

    allowed: bool
    reason: str
    channel: DispatchChannel
    destination: str | None = None
    needs_approval: bool = False


async def _weekly_sent(session, candidate_id: UUID) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    return (await session.execute(
        select(func.count(ApplicationDispatch.id))
        .where(ApplicationDispatch.candidate_id == candidate_id)
        .where(ApplicationDispatch.status == DispatchStatus.SENT)
        .where(ApplicationDispatch.sent_at >= since)
    )).scalar() or 0


async def decide(
    session, candidate: Candidate, mission: Mission,
    application: Application, job: JobPosting, company_name: str,
) -> Decision:
    """
    Peut-on envoyer cette candidature ? Chaque refus porte son motif, pour que
    l'utilisateur comprenne ce qui bloque plutôt que de constater un silence.
    """
    channel = CHANNEL_MAP.get(job.apply_channel, DispatchChannel.MANUAL)
    contact = job.contact_json or {}
    destination = contact.get("email") if channel == DispatchChannel.EMAIL else (
        contact.get("apply_url") or job.apply_url
    )

    if mission.status != MissionStatus.ACTIVE:
        return Decision(False, "mission en pause", channel, destination)

    # Doublon : un envoi abouti existe déjà pour cette offre.
    already = (await session.execute(
        select(ApplicationDispatch)
        .where(ApplicationDispatch.application_id == application.id)
        .where(ApplicationDispatch.status == DispatchStatus.SENT)
    )).scalars().first()
    if already:
        return Decision(False, "candidature déjà envoyée", channel, destination)

    blocked = [b.lower() for b in (mission.blocked_companies or [])]
    if any(b in (company_name or "").lower() for b in blocked if b):
        return Decision(False, f"entreprise bloquée : {company_name}", channel, destination)

    if channel not in IMPLEMENTED_CHANNELS:
        # Le motif vient de l'évaluateur : il parle au candidat, pas du code.
        from app.agents.application.feasibility import assess
        verdict = assess(job, has_resume=bool(candidate.resume_file))
        return Decision(
            False,
            verdict.blockers[0] if verdict.blockers else verdict.summary,
            channel, destination,
        )
    if not destination:
        return Decision(False, "aucune adresse de candidature", channel, destination)

    allowed_channels = mission.allowed_channels or []
    if channel.value not in allowed_channels:
        return Decision(
            False, f"canal « {channel.value} » non autorisé par ton mandat",
            channel, destination, needs_approval=True,
        )

    sent_this_week = await _weekly_sent(session, candidate.id)
    if sent_this_week >= mission.weekly_quota:
        return Decision(
            False,
            f"quota hebdomadaire atteint ({sent_this_week}/{mission.weekly_quota})",
            channel, destination,
        )

    # Niveau d'autonomie : c'est ici que se joue « qui appuie sur le bouton ».
    if mission.autonomy == AutonomyLevel.PROPOSE:
        return Decision(
            False, "tu valides chaque envoi", channel, destination, needs_approval=True,
        )
    if mission.autonomy == AutonomyLevel.AUTO_ABOVE:
        if application.match_score < mission.auto_apply_min_score:
            return Decision(
                False,
                f"score {application.match_score}% sous ton seuil "
                f"({mission.auto_apply_min_score}%)",
                channel, destination, needs_approval=True,
            )

    return Decision(True, "autorisée", channel, destination)


async def prepare_dispatch(
    candidate_id: UUID, application_id: UUID, run_id: UUID | None = None,
) -> ApplicationDispatch | None:
    """
    Crée la trace et arrête le statut selon l'autorisation.

    À la sortie, l'envoi est soit prêt à partir, soit en attente de validation,
    soit refusé avec son motif — jamais dans un état indéterminé.
    """
    async with async_session() as session:
        row = (await session.execute(
            select(Application, JobPosting, Company.name)
            .join(JobPosting, Application.job_posting_id == JobPosting.id)
            .join(Company, JobPosting.company_id == Company.id)
            .where(Application.id == application_id)
        )).first()
        if not row:
            return None
        application, job, company_name = row

        candidate = await session.get(Candidate, candidate_id)
        mission = (await session.execute(
            select(Mission).where(Mission.candidate_id == candidate_id)
        )).scalars().first()
        if not candidate or not mission:
            return None

        verdict = await decide(session, candidate, mission, application, job, company_name)

        letter = (application.metadata_json or {}).get("cover_letter")

        if verdict.allowed:
            status = DispatchStatus.APPROVED
        elif verdict.needs_approval:
            status = DispatchStatus.AWAITING_APPROVAL
        else:
            status = DispatchStatus.PREPARED

        # On fige les pièces ici, au moment de l'assemblage, et non à l'envoi :
        # une candidature qui échoue doit laisser à l'utilisateur exactement
        # les documents qu'Alice avait préparés, pour qu'il puisse finir à la
        # main sans avoir à les refaire.
        from app.agents.application.cv_resolver import resolve_cv
        from app.agents.application.email_sender import _plain_text

        cv_bytes, cv_name, cv_mode = resolve_cv(candidate)
        letter_body = _plain_text(letter, candidate, job.title, company_name or "")

        dispatch = ApplicationDispatch(
            candidate_id=candidate_id,
            application_id=application_id,
            run_id=run_id,
            job_title=job.title[:500],
            company_name=(company_name or "")[:300],
            channel=verdict.channel,
            destination=verdict.destination,
            status=status,
            error=None if verdict.allowed else verdict.reason,
            documents={
                "has_cover_letter": bool(letter),
                "cover_letter_subject": (letter or {}).get("subject"),
                "has_resume": bool(cv_bytes),
                "resume_filename": cv_name if cv_bytes else None,
                "resume_mode": cv_mode,
            },
            resume_blob=cv_bytes,
            resume_name=cv_name if cv_bytes else None,
            letter_subject=(letter or {}).get("subject")
            or f"Candidature — {job.title}"[:500],
            letter_body=letter_body or None,
        )
        session.add(dispatch)
        await session.commit()
        await session.refresh(dispatch)

    return dispatch


async def _send_via_ats(dispatch: ApplicationDispatch, candidate: Candidate) -> dict:
    """
    Route vers le connecteur du bon ATS. `dispatch.channel` ne dit que
    « ATS_API » — il faut relire l'offre pour savoir laquelle des trois
    plateformes implémentées (ou de Workable, non implémenté) est concernée.
    """
    from app.agents.application.ats_connectors import build_application_plan, submit_ats_application

    async with async_session() as session:
        row = (await session.execute(
            select(JobPosting, Company)
            .join(Application, Application.job_posting_id == JobPosting.id)
            .join(Company, JobPosting.company_id == Company.id)
            .where(Application.id == dispatch.application_id)
        )).first()

    if not row:
        return {"ok": False, "real": False, "error": "offre introuvable"}
    job, company = row

    if job.apply_channel not in (ApplyChannel.GREENHOUSE_API, ApplyChannel.LEVER_API, ApplyChannel.ASHBY_API):
        channel_name = job.apply_channel.value if job.apply_channel else "unknown"
        return {"ok": False, "real": False, "error": f"canal « {channel_name} » pas encore implémenté"}

    plan = await build_application_plan(job, company, candidate, dispatch.letter_body)
    return await submit_ats_application(plan)


async def send_dispatch(dispatch_id: UUID) -> ApplicationDispatch | None:
    """
    Exécute un envoi déjà autorisé.

    Ne décide de rien : si le statut n'est pas APPROVED, on ne part pas. La
    décision et l'exécution sont séparées pour qu'aucun chemin ne puisse
    court-circuiter l'autorisation.
    """
    from app.agents.application.email_sender import send_application_email

    async with async_session() as session:
        dispatch = await session.get(ApplicationDispatch, dispatch_id)
        if not dispatch or dispatch.status != DispatchStatus.APPROVED:
            return dispatch

        candidate = await session.get(Candidate, dispatch.candidate_id)
        application = await session.get(Application, dispatch.application_id)
        letter = (application.metadata_json or {}).get("cover_letter") if application else None

    if dispatch.channel == DispatchChannel.EMAIL:
        result = await send_application_email(
            to_email=dispatch.destination,
            candidate=candidate,
            letter=letter,
            job_title=dispatch.job_title,
            company_name=dispatch.company_name,
        )
    elif dispatch.channel == DispatchChannel.ATS_API:
        result = await _send_via_ats(dispatch, candidate)
    else:
        async with async_session() as session:
            d = await session.get(ApplicationDispatch, dispatch_id)
            d.status = DispatchStatus.FAILED
            d.error = f"canal « {d.channel.value} » pas encore implémenté"
            await session.commit()
            await session.refresh(d)
            return d

    async with async_session() as session:
        d = await session.get(ApplicationDispatch, dispatch_id)
        if result["ok"]:
            d.status = DispatchStatus.SENT if result["real"] else DispatchStatus.SIMULATED
            d.sent_at = datetime.now(timezone.utc)
            d.proof = result.get("proof")
            d.error = None if result["real"] else result.get(
                "simulated_reason", "SMTP non configuré — rien n'a été envoyé"
            )

            # Le statut de la candidature ne bascule que sur un envoi RÉEL.
            if result["real"] and d.application_id:
                app = await session.get(Application, d.application_id)
                if app:
                    app.status = ApplicationStatus.APPLIED
                    app.applied_at = d.sent_at
        else:
            d.status = DispatchStatus.FAILED
            d.error = result.get("error", "échec inconnu")

        await session.commit()
        await session.refresh(d)
        return d
