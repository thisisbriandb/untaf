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

from app.config import settings
from app.agents.inbox import contact_of
from app.database import async_session
from app.models.application import Application, ApplicationStatus
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.dispatch import ApplicationDispatch, DispatchChannel, DispatchStatus
from app.models.job_posting import ApplyChannel, JobPosting
from app.models.mission import AutonomyLevel, Mission, MissionStatus

logger = logging.getLogger(__name__)

#: Canal de l'offre → canal d'envoi.
#: Destination d'un envoi La bonne alternance : `lba:<recipient_id>`.
LBA_PREFIX = "lba:"
#: Destination d'un envoi Recruitee : `recruitee:<entreprise>/<offre>`.
RECRUITEE_PREFIX = "recruitee:"

CHANNEL_MAP = {
    ApplyChannel.EMAIL: DispatchChannel.EMAIL,
    ApplyChannel.GREENHOUSE_API: DispatchChannel.ATS_API,
    ApplyChannel.LEVER_API: DispatchChannel.ATS_API,
    ApplyChannel.ASHBY_API: DispatchChannel.ATS_API,
    ApplyChannel.WORKABLE_API: DispatchChannel.ATS_API,
    # La bonne alternance : transmission par l'API publique, sans navigateur.
    ApplyChannel.LBA_API: DispatchChannel.ATS_API,
    # Recruitee : dépôt par l'API publique du site carrière, sans navigateur.
    ApplyChannel.RECRUITEE_API: DispatchChannel.ATS_API,
    ApplyChannel.WEB_FORM: DispatchChannel.WEB_FORM,
    # Absent de la table, EXTERNAL_LINK retombait sur MANUAL et produisait le
    # message « canal manual pas encore automatisable » — incompréhensible.
    ApplyChannel.EXTERNAL_LINK: DispatchChannel.WEB_FORM,
}

#: Canaux réellement implémentés. Le reste est préparé mais pas envoyable —
#: mieux vaut une file d'attente honnête qu'un échec silencieux.
#: Canaux qu'Alice sait exécuter de bout en bout. `WEB_FORM` et `ATS_API`
#: passent par le remplissage de formulaire dans un navigateur ; le clic final
#: reste conditionné à `browser_submit_enabled`, comme l'email l'est à SMTP.
IMPLEMENTED_CHANNELS = {
    DispatchChannel.EMAIL,
    DispatchChannel.WEB_FORM,
    DispatchChannel.ATS_API,
}


@dataclass
class Decision:
    """Verdict du dispatcher, toujours motivé."""

    allowed: bool
    reason: str
    channel: DispatchChannel
    destination: str | None = None
    needs_approval: bool = False


FORM_NOT_AUTOMATABLE = (
    "le site de l'employeur a son propre formulaire : je ne l'envoie pas à ta place. "
    "Ton dossier est prêt, termine sur le site avec l'extension Alice ou « Finir sur le site »"
)

FORM_NOT_RECOGNIZED = (
    "je n'ai reconnu aucun champ du formulaire de l'employeur (page de présentation, "
    "compte à créer ou formulaire en plusieurs étapes) : rien n'est parti. Ton dossier "
    "est prêt, termine sur le site avec l'extension Alice ou « Finir sur le site »"
)


def browser_failure(result: dict) -> tuple[str, str | None]:
    """
    Échec du remplissage par navigateur → (statut, incident à signaler).

    Rien de reconnu sur la page, ce n'est pas une panne : c'est une page qu'on
    ne sait pas lire. Le dossier reste prêt, à finir sur le site — sans alerte.
    Un remplissage partiel, lui, mérite d'être signalé.
    """
    proof = result.get("proof") or {}
    if not proof.get("filled_fields") and not proof.get("uploaded_files"):
        return "prepared", None
    return "failed", "form_incomplete"


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
    run_authorized: bool = False,
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
    if job.apply_channel == ApplyChannel.LBA_API:
        # L'API ne connaît que le destinataire qu'elle a publié.
        recipient = contact.get("lba_recipient_id")
        destination = f"{LBA_PREFIX}{recipient}" if recipient else None
        if not settings.lba_configured:
            return Decision(False, "l'envoi via La bonne alternance n'est pas configuré "
                                   "sur ce serveur", channel, destination)

    if job.apply_channel == ApplyChannel.RECRUITEE_API:
        target = contact.get("recruitee") or {}
        destination = (
            f"{RECRUITEE_PREFIX}{target['company']}/{target['offer']}"
            if target.get("company") and target.get("offer") else None
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

    if channel in (DispatchChannel.WEB_FORM, DispatchChannel.ATS_API):
        # Le navigateur d'Alice ne remplit de façon fiable que les formulaires
        # dont l'ATS publie les champs. Un formulaire propre à l'employeur
        # échouerait, ou partirait incomplet : on ne tente pas.
        from app.agents.application.feasibility import assess
        if not assess(job, has_resume=True).automatable:
            return Decision(False, FORM_NOT_AUTOMATABLE, channel, destination)

    # « Postule pour moi », choisi au lancement d'une mission, vaut
    # autorisation pour cette mission : pas besoin de canaux pré-cochés.
    allowed_channels = mission.allowed_channels or []
    if not run_authorized and channel.value not in allowed_channels:
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
    # Une mission explicitement autorisée à envoyer a déjà la réponse.
    if run_authorized:
        return Decision(True, "autorisée par la mission", channel, destination)
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
    run_authorized: bool = False,
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

        verdict = await decide(
            session, candidate, mission, application, job, company_name,
            run_authorized=run_authorized,
        )

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

        cv_bytes, cv_name, cv_mode = resolve_cv(
            candidate, (application.metadata_json or {}).get("tailored_cv"),
        )
        cv_missing = cv_mode == "render_failed" or not cv_bytes
        if cv_mode == "render_failed":
            from app.agents.incidents import report_incident
            await report_incident(
                "cv_render_failed", candidate_id, "composition Typst échouée à l'assemblage",
                context={"job": job.title, "company": company_name},
            )
        if cv_missing and status != DispatchStatus.PREPARED:
            # Une candidature ne part jamais sans le CV adapté — ni avec
            # l'original glissé à sa place.
            status = DispatchStatus.PREPARED
            verdict = Decision(False, "CV adapté indisponible pour l'instant, rien n'est parti",
                               verdict.channel, verdict.destination)
        letter_body = _plain_text(letter, candidate, job.title, company_name or "")

        fields = dict(
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

        # Un envoi déjà ouvert pour cette candidature est mis à jour, pas
        # doublé : deux envois en attente finissaient par partir tous les deux.
        dispatch = (await session.execute(
            select(ApplicationDispatch)
            .where(ApplicationDispatch.application_id == application_id)
            .where(ApplicationDispatch.status.in_([
                DispatchStatus.PREPARED, DispatchStatus.AWAITING_APPROVAL, DispatchStatus.APPROVED,
            ]))
            .order_by(ApplicationDispatch.created_at.desc())
        )).scalars().first()
        if dispatch:
            for key, value in fields.items():
                setattr(dispatch, key, value)
            dispatch.approved_at = None
        else:
            dispatch = ApplicationDispatch(
                candidate_id=candidate_id, application_id=application_id, **fields,
            )
            session.add(dispatch)
        await session.commit()
        await session.refresh(dispatch)

    return dispatch


#: Au-delà, une offre qu'on n'a plus revue en source est peut-être pourvue.
STALE_AFTER_DAYS = 45


async def offer_still_open(job: JobPosting, company_domain: str | None) -> bool | None:
    """
    L'offre est-elle encore en ligne ? Vérifiée à la source quand c'est
    possible (France Travail), sinon d'après sa dernière apparition.
    None : on ne sait pas, et ce n'est pas une raison de bloquer.
    """
    from app.models.job_posting import PostingStatus

    if job.status in (PostingStatus.CLOSED, PostingStatus.EXPIRED):
        return False
    if (company_domain or "").endswith(".francetravail.local") and job.external_id:
        from app.agents.discovery.france_travail import FranceTravailClient
        client = FranceTravailClient()
        if client.configured:
            exists = await client.offer_exists(job.external_id)
            if exists is not None:
                return exists
    seen = job.last_seen_at
    if seen is not None:
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - seen > timedelta(days=STALE_AFTER_DAYS):
            return False
    return None


@dataclass
class Hold:
    """Un envoi retenu au dernier moment, avec son motif et le statut où il reste."""
    status: DispatchStatus
    reason: str


async def pre_send_check(session, dispatch: ApplicationDispatch,
                         application: Application | None) -> Hold | None:
    """
    Les vérifications faites JUSTE avant de partir, quel que soit le chemin
    (mission, « Valider », « Tout valider », relance d'un envoi) : ce qui était
    vrai à la préparation peut ne plus l'être.
    """
    from app.models.job_posting import PostingStatus

    # Déjà parti pour cette candidature : jamais deux fois le même dossier.
    already = (await session.execute(
        select(ApplicationDispatch.id)
        .where(ApplicationDispatch.application_id == dispatch.application_id)
        .where(ApplicationDispatch.status == DispatchStatus.SENT)
        .where(ApplicationDispatch.id != dispatch.id)
    )).first()
    if already or (application and application.status in (
        ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER,
    )):
        return Hold(DispatchStatus.REJECTED, "candidature déjà envoyée : rien n'est reparti")

    # Pas de candidature signée « Candidat » : sans nom, rien ne part.
    from app.agents.application.identity import MISSING_NAME_REASON, real_name
    if not real_name(await session.get(Candidate, dispatch.candidate_id)):
        return Hold(DispatchStatus.AWAITING_APPROVAL, MISSING_NAME_REASON)

    if application:
        row = (await session.execute(
            select(JobPosting, Company.domain)
            .join(Company, JobPosting.company_id == Company.id)
            .where(JobPosting.id == application.job_posting_id)
        )).first()
        if row:
            job, domain = row
            open_ = await offer_still_open(job, domain)
            if open_ is False:
                if job.status == PostingStatus.ACTIVE:
                    job.status = PostingStatus.EXPIRED
                return Hold(DispatchStatus.PREPARED,
                            "l'offre n'est plus en ligne : je n'ai rien envoyé")

        # Contenu rédigé sans le modèle (indisponible) : relu par le candidat
        # avant tout envoi. Son feu vert explicite (approved_at) suffit.
        meta = application.metadata_json or {}
        fallback = (meta.get("cover_letter") or {}).get("source") == "fallback" or \
            (meta.get("tailored_cv") or {}).get("source") == "fallback"
        if fallback and not dispatch.approved_at:
            return Hold(DispatchStatus.AWAITING_APPROVAL,
                        "lettre et CV rédigés sans mon assistant de rédaction (indisponible) : "
                        "relis-les avant que je les envoie")

    # Candidature spontanée : désinscription et plafonds, sans exception.
    if application and (application.metadata_json or {}).get("spontaneous"):
        from app.agents.spontaneous import is_opted_out

        if await is_opted_out(session, dispatch.destination or ""):
            return Hold(DispatchStatus.REJECTED,
                        "cette entreprise a demandé à ne plus recevoir de candidatures spontanées")
        now = datetime.now(timezone.utc)
        for days, cap, label in ((1, settings.spontaneous_daily_cap, "du jour"),
                                 (7, settings.spontaneous_weekly_cap, "de la semaine")):
            sent = (await session.execute(
                select(func.count(ApplicationDispatch.id))
                .join(Application, ApplicationDispatch.application_id == Application.id)
                .where(ApplicationDispatch.candidate_id == dispatch.candidate_id)
                .where(ApplicationDispatch.status == DispatchStatus.SENT)
                .where(ApplicationDispatch.sent_at >= now - timedelta(days=days))
                .where(Application.metadata_json["spontaneous"].as_boolean())
            )).scalar() or 0
            if sent >= cap:
                return Hold(DispatchStatus.AWAITING_APPROVAL,
                            f"plafond {label} des candidatures spontanées atteint ({sent}/{cap}) : "
                            "je l'enverrai plus tard, valide-la à nouveau quand tu veux")

    mission = (await session.execute(
        select(Mission).where(Mission.candidate_id == dispatch.candidate_id)
    )).scalars().first()
    if mission:
        sent = await _weekly_sent(session, dispatch.candidate_id)
        if sent >= mission.weekly_quota:
            return Hold(DispatchStatus.AWAITING_APPROVAL,
                        f"quota de la semaine atteint ({sent}/{mission.weekly_quota}) : "
                        "valide-le à nouveau quand tu veux l'envoyer")
    return None


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

        hold = await pre_send_check(session, dispatch, application)
        if hold:
            dispatch.status = hold.status
            dispatch.error = hold.reason
            # Un nouveau feu vert sera demandé : l'ancien ne vaut plus.
            if hold.status == DispatchStatus.AWAITING_APPROVAL:
                dispatch.approved_at = None
            await session.commit()
            await session.refresh(dispatch)
            return dispatch
        # L'adresse de réponse existe avant l'envoi : les réponses du recruteur
        # arriveront à Alice, qui les lira et les transférera.
        if candidate:
            from app.agents.inbox import ensure_reply_address

            await ensure_reply_address(session, candidate)
            await session.commit()

    if dispatch.channel == DispatchChannel.EMAIL:
        result = await send_application_email(
            to_email=dispatch.destination,
            candidate=candidate,
            letter=letter,
            job_title=dispatch.job_title,
            company_name=dispatch.company_name,
            resume=dispatch.resume_blob,
            resume_name=dispatch.resume_name,
            spontaneous=bool(application and (application.metadata_json or {}).get("spontaneous")),
        )
    elif (dispatch.destination or "").startswith(LBA_PREFIX):
        result = await _send_via_lba(dispatch, candidate)
    elif (dispatch.destination or "").startswith(RECRUITEE_PREFIX):
        result = await _send_via_recruitee(dispatch, candidate)
    elif dispatch.channel in (DispatchChannel.WEB_FORM, DispatchChannel.ATS_API):
        # Formulaire public : on le remplit dans un navigateur, guidé par le
        # schéma que l'ATS publie quand il en publie un.
        from app.agents.application.form_filler import submit_via_browser

        result = await submit_via_browser(
            dispatch, candidate, dispatch.destination or ""
        )
    else:
        async with async_session() as session:
            d = await session.get(ApplicationDispatch, dispatch_id)
            d.status = DispatchStatus.FAILED
            d.error = f"canal « {d.channel.value} » pas encore implémenté"
            await session.commit()
            await session.refresh(d)
            return d

    incident = "send_failed"
    async with async_session() as session:
        d = await session.get(ApplicationDispatch, dispatch_id)
        if result["ok"]:
            d.status = DispatchStatus.SENT if result["real"] else DispatchStatus.SIMULATED
            d.sent_at = datetime.now(timezone.utc)
            d.proof = result.get("proof")
            # Le motif de simulation dépend du canal : SMTP absent pour un
            # email, envoi navigateur désactivé pour un formulaire. C'est
            # l'exécuteur qui le sait, pas le dispatcher.
            d.error = None if result["real"] else (
                result.get("error") or "rien n'a été envoyé"
            )

            # Le statut de la candidature ne bascule que sur un envoi RÉEL.
            if result["real"] and d.application_id:
                app = await session.get(Application, d.application_id)
                if app:
                    from app.agents.application.followup import record_status
                    app.applied_at = d.sent_at
                    dest = d.destination or ""
                    via = ("La bonne alternance" if dest.startswith(LBA_PREFIX)
                           else "Recruitee" if dest.startswith(RECRUITEE_PREFIX)
                           else d.channel.value)
                    record_status(app, ApplicationStatus.APPLIED, f"envoyée via {via}")
        else:
            d.status = DispatchStatus.FAILED
            d.error = result.get("error", "échec inconnu")
            if d.channel in (DispatchChannel.WEB_FORM, DispatchChannel.ATS_API):
                outcome, incident = browser_failure(result)
                incident = incident or "send_failed"
                d.proof = result.get("proof")
                if outcome == "prepared":
                    d.status = DispatchStatus.PREPARED
                    d.error = FORM_NOT_RECOGNIZED

        await session.commit()
        await session.refresh(d)

    if d.status == DispatchStatus.FAILED:
        from app.agents.incidents import report_incident
        await report_incident(
            incident, d.candidate_id, d.error or "",
            context={"job": d.job_title, "company": d.company_name, "channel": d.channel.value,
                     "dispatch_id": str(d.id)},
        )
    return d


async def _send_via_lba(dispatch: ApplicationDispatch, candidate: Candidate) -> dict:
    """
    Transmet la candidature par l'API La bonne alternance : le CV adapté
    figé à la préparation et la lettre en message. Même contrat de retour que
    l'envoi par e-mail.
    """
    from app.agents.discovery.labonnealternance import (
        LbaError, build_application, send_application,
    )

    recipient = (dispatch.destination or "")[len(LBA_PREFIX):]
    proof = {"via": "La bonne alternance", "recipient_id": recipient,
             "attachments": [dispatch.resume_name] if dispatch.resume_blob else []}
    if not dispatch.resume_blob:
        return {"ok": False, "real": False, "error": "CV adapté absent : rien n'est parti"}
    if not candidate.phone:
        return {"ok": False, "real": False,
                "error": "La bonne alternance exige un numéro de téléphone : ajoute-le à ton profil"}
    try:
        body = build_application(
            recipient_id=recipient,
            full_name=candidate.full_name or "",
            email=contact_of(candidate),
            phone=candidate.phone,
            resume=dispatch.resume_blob,
            resume_name=dispatch.resume_name or "CV.pdf",
            message=dispatch.letter_body or "",
        )
        lba_id = await send_application(body)
    except ValueError as e:
        return {"ok": False, "real": False, "error": str(e)}
    except LbaError as e:
        reason = (
            "la permission d'envoi n'est pas encore accordée à Alice par La bonne alternance"
            if e.status in (401, 403)
            else "La bonne alternance n'a pas accepté l'envoi — ton dossier est prêt, "
                 "tu peux postuler depuis leur site"
        )
        return {"ok": False, "real": False, "error": reason, "proof": {**proof, "detail": e.detail}}
    except Exception as e:  # noqa: BLE001
        logger.error("Envoi La bonne alternance impossible : %s", e, exc_info=True)
        return {"ok": False, "real": False, "error": "La bonne alternance injoignable"}
    return {"ok": True, "real": True, "proof": {**proof, "lba_application_id": lba_id}}


async def _send_via_recruitee(dispatch: ApplicationDispatch, candidate: Candidate) -> dict:
    """
    Dépose la candidature sur le site carrière Recruitee de l'employeur : CV
    adapté figé à la préparation, lettre en lettre de motivation.
    """
    from app.agents.discovery.scrapers.recruitee import RecruiteeError, send_application

    company, _, offer = (dispatch.destination or "")[len(RECRUITEE_PREFIX):].partition("/")
    proof = {"via": "Recruitee", "company": company, "offer": offer,
             "attachments": [dispatch.resume_name] if dispatch.resume_blob else []}
    if not dispatch.resume_blob:
        return {"ok": False, "real": False, "error": "CV adapté absent : rien n'est parti"}
    if not candidate.phone:
        # Exigé par défaut sur les sites carrière Recruitee.
        return {"ok": False, "real": False,
                "error": "l'employeur demande un numéro de téléphone : ajoute-le à ton profil"}
    try:
        answer = await send_application(
            company=company, offer=offer,
            name=candidate.full_name or "", email=contact_of(candidate),
            phone=candidate.phone, resume=dispatch.resume_blob,
            resume_name=dispatch.resume_name or "CV.pdf",
            cover_letter=dispatch.letter_body,
        )
    except RecruiteeError as e:
        return {"ok": False, "real": False,
                "error": (
                    "le site carrière a refusé un champ (souvent le téléphone ou le CV) — "
                    "termine sur le site, ton dossier est prêt"
                    if e.status in (400, 422) else
                    "le site carrière n'a pas accepté l'envoi — termine sur le site, "
                    "ton dossier est prêt"
                ),
                "proof": {**proof, "detail": e.detail, "status": e.status}}
    except Exception as e:  # noqa: BLE001
        logger.error("Envoi Recruitee impossible : %s", e, exc_info=True)
        return {"ok": False, "real": False, "error": "site carrière injoignable"}
    candidate_id = ((answer or {}).get("candidate") or {}).get("id")
    return {"ok": True, "real": True, "proof": {**proof, "recruitee_candidate_id": candidate_id}}
