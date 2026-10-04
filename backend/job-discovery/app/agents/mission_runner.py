"""
Exécution d'une mission : une passe, du dossier à l'envoi.

Préparer les dossiers des meilleures offres retenues, et, si l'utilisateur l'a
demandé, les envoyer. Chaque action est écrite au journal au moment où elle a
lieu ; l'interface la diffuse en direct et un e-mail rend compte à la fin.

Rien n'est mimé. Une étape qui ne peut pas s'exécuter est consignée comme telle
plutôt que rapportée comme faite : c'est la seule manière de rendre un compte
rendu qui vaille quelque chose.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.job_posting import JobPosting, PostingStatus
from app.models.application import Application
from app.models.mission import (
    Mission, MissionEvent, MissionEventKind, MissionRun, RunStatus, RunStep,
)

logger = logging.getLogger(__name__)



async def _log(session, run: MissionRun, candidate_id: UUID, kind: MissionEventKind,
               summary: str, payload: dict | None = None) -> None:
    session.add(MissionEvent(
        mission_id=run.mission_id,
        run_id=run.id,
        kind=kind,
        summary=summary,
        payload=payload,
    ))


def _bump(run: MissionRun, **deltas: int) -> None:
    stats = dict(run.stats or {})
    for key, value in deltas.items():
        stats[key] = stats.get(key, 0) + value
    run.stats = stats


# ── Mission : une passe, sans durée ────────────────────────────────────────
#
# L'ancienne mission tournait « 30 minutes » en boucle : re-scrapait des
# sources déjà collectées chaque matin, ne préparait que les offres au-dessus
# du seuil de présélection (souvent aucune), et n'envoyait jamais faute de
# canaux autorisés. Elle occupait l'écran sans rien produire.
#
# Désormais une mission est une seule passe, du début à la fin :
#   1. reprendre les offres retenues (le repérage, lui, est fait chaque matin) ;
#   2. préparer le dossier complet des N meilleures (CV adapté + lettre) ;
#   3. si la mission va jusqu'à l'envoi : envoyer ce qui peut l'être, mettre le
#      reste en file de validation ;
#   4. rendre compte — dans le fil et par e-mail.
# Chaque action réelle est écrite au journal au moment où elle a lieu : c'est
# ce que l'interface diffuse en direct.

#: Nombre de dossiers par défaut, et plafond : au-delà, une mission devient
#: une rafale qu'on ne relit plus.
DEFAULT_TARGETS = 5
MAX_TARGETS = 10


async def _heartbeat(run_id: UUID, step: RunStep | None = None) -> bool:
    """Signe de vie + étape courante. Faux si la mission a été arrêtée."""
    async with async_session() as session:
        run = await session.get(MissionRun, run_id)
        if not run or run.status != RunStatus.RUNNING:
            return False
        run.heartbeat_at = datetime.now(timezone.utc)
        if step is not None:
            run.current_step = step
        await session.commit()
        return True


async def _say(run_id: UUID, candidate_id: UUID, kind: MissionEventKind, summary: str,
               payload: dict | None = None, **stats: int) -> None:
    async with async_session() as session:
        run = await session.get(MissionRun, run_id)
        if stats:
            _bump(run, **stats)
        await _log(session, run, candidate_id, kind, summary, payload)
        await session.commit()


async def _targets(candidate_id: UUID, count: int, sendable_first: bool):
    """Les offres à traiter : retenues, pas encore parties, les meilleures d'abord."""
    from app.agents.alice_state import OPEN_STATUSES
    from app.agents.application.feasibility import APPLY_MODE_RANK, apply_mode
    from app.models.company import Company
    from app.models.dispatch import ApplicationDispatch, DispatchStatus

    async with async_session() as session:
        rows = (await session.execute(
            select(Application, JobPosting, Company.name)
            .join(JobPosting, Application.job_posting_id == JobPosting.id)
            .join(Company, JobPosting.company_id == Company.id)
            .where(Application.candidate_id == candidate_id)
            # PENDING compris : le seuil de présélection (78) laissait la
            # mission sans rien à préparer alors que des offres à 70 % étaient là.
            .where(Application.status.in_(OPEN_STATUSES))
            .where(Application.match_score >= settings.match_min_score)
            .where(JobPosting.status == PostingStatus.ACTIVE)
            .order_by(Application.match_score.desc())
            .limit(count * 8)
        )).all()
        settled = set((await session.execute(
            select(ApplicationDispatch.application_id)
            .where(ApplicationDispatch.candidate_id == candidate_id)
            .where(ApplicationDispatch.status.in_((
                DispatchStatus.AWAITING_APPROVAL, DispatchStatus.APPROVED,
                DispatchStatus.SENT, DispatchStatus.REJECTED,
            )))
        )).scalars().all())

    rows = [r for r in rows if r[0].id not in settled]
    if sendable_first:
        # Mission « postuler » : d'abord ce qu'Alice peut réellement envoyer.
        rows.sort(key=lambda r: (APPLY_MODE_RANK[apply_mode(r[1])], -r[0].match_score))
    return rows[:count]


async def execute_run(run_id: UUID, candidate_id: UUID) -> None:
    """Déroule la mission en une passe, en écrivant chaque action au journal."""
    from app.agents.application.feasibility import APPLY_MODE_LABELS, apply_mode
    from app.agents.application.pack import build_pack, is_pack_ready
    from app.agents.discovery.tasks import _match_candidate_to_existing_jobs

    async with async_session() as session:
        run = await session.get(MissionRun, run_id)
        if not run:
            return
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        run.heartbeat_at = run.started_at
        run.ends_at = None
        run.stats = {}
        # Une seule mission : préparer et envoyer sont les deux temps du même
        # geste. On ne postule pas sans dossier, et un dossier qu'Alice peut
        # envoyer ne doit pas attendre une seconde mission. Seule question :
        # envoyer directement, ou présenter d'abord (`send`).
        objective = "apply"
        allowed = run.allowed_actions or {}
        count = max(1, min(MAX_TARGETS, int(allowed.get("count") or DEFAULT_TARGETS)))
        send = bool(allowed.get("send"))
        await session.commit()

    try:
        # 1. Les offres du jour, confrontées au mandat actuel.
        if not await _heartbeat(run_id, RunStep.MATCH):
            return
        try:
            kept = await _match_candidate_to_existing_jobs(candidate_id)
        except Exception as e:  # noqa: BLE001 — on travaille sur le stock déjà noté
            logger.warning("Re-notation impossible pendant la mission : %s", e)
            kept = 0
        targets = await _targets(candidate_id, count, sendable_first=objective == "apply")
        await _say(
            run_id, candidate_id, MissionEventKind.SHORTLIST,
            (f"Je reprends tes offres retenues : je m'occupe des {len(targets)} meilleures."
             if targets else "Aucune offre de ton mandat n'attend de dossier pour l'instant."),
            {"kept": kept, "targets": len(targets)}, shortlisted=len(targets),
        )
        if not targets:
            from app.agents.incidents import report_incident
            await report_incident("mission_empty", candidate_id, f"objectif {objective}",
                                  notify_user=False)
            await finalize_run(run_id, candidate_id, RunStatus.COMPLETED)
            return

        # 2. Un dossier complet par offre.
        prepared = []
        for app, job, company in targets:
            if not await _heartbeat(run_id, RunStep.PREPARE):
                return
            mode = apply_mode(job)
            if not is_pack_ready(app):
                try:
                    pack = await build_pack(candidate_id, app.id)
                except Exception as e:  # noqa: BLE001
                    logger.error("Pack impossible pour %s : %s", app.id, e)
                    pack = None
                if not pack:
                    from app.agents.incidents import report_incident
                    await report_incident("pack_failed", candidate_id, f"{job.title} — {company}",
                                          notify_user=False)
                    await _say(run_id, candidate_id, MissionEventKind.ERROR,
                               f"Je n'ai pas pu préparer le dossier pour « {job.title} » "
                               f"chez {company}. Je passe à la suivante.")
                    continue
            await _say(
                run_id, candidate_id, MissionEventKind.LETTER_WRITTEN,
                f"Dossier prêt pour « {job.title} » chez {company} — {APPLY_MODE_LABELS[mode].lower()}.",
                {"job_id": str(job.id), "application_id": str(app.id), "company": company,
                 "job_title": job.title,
                 "score": app.match_score, "apply_mode": mode},
                packs=1, letters=1,
            )
            prepared.append((app, job, company))

        # 3. L'envoi, si la mission va jusque-là.
        if objective == "apply" and prepared:
            if not await _heartbeat(run_id, RunStep.APPLY):
                return
            await _dispatch_all(run_id, candidate_id, prepared, send)

    except asyncio.CancelledError:
        await finalize_run(run_id, candidate_id, RunStatus.INTERRUPTED)
        raise
    except Exception as e:  # noqa: BLE001
        logger.error("Mission run %s failed: %s", run_id, e, exc_info=True)
        from app.agents.incidents import report_incident
        await report_incident("mission_failed", candidate_id, repr(e)[:300],
                              context={"run_id": str(run_id)})
        await finalize_run(run_id, candidate_id, RunStatus.INTERRUPTED)
        return

    await finalize_run(run_id, candidate_id, RunStatus.COMPLETED)


async def _dispatch_all(run_id: UUID, candidate_id: UUID, prepared: list, send: bool) -> None:
    """
    Envoie ce qui peut partir, met le reste en file de validation.

    Choisir « postule pour moi » au lancement EST l'autorisation : on ne
    redemande pas un réglage de canaux introuvable. Restent appliqués : pas de
    doublon, entreprises bloquées, quota hebdomadaire, mission en pause.
    """
    from app.agents.application.dispatcher import prepare_dispatch, send_dispatch
    from app.models.dispatch import ApplicationDispatch, DispatchStatus

    awaiting, manual = 0, 0
    for app, job, company in prepared:
        if not await _heartbeat(run_id):
            return
        dispatch = await prepare_dispatch(candidate_id, app.id, run_id, run_authorized=send)
        if not dispatch:
            continue

        if dispatch.status == DispatchStatus.APPROVED and not send:
            async with async_session() as session:
                d = await session.get(ApplicationDispatch, dispatch.id)
                d.status = DispatchStatus.AWAITING_APPROVAL
                d.error = "tu valides chaque envoi pour cette mission"
                await session.commit()
            dispatch.status = DispatchStatus.AWAITING_APPROVAL

        if dispatch.status == DispatchStatus.APPROVED:
            sent = await send_dispatch(dispatch.id)
            status = sent.status if sent else DispatchStatus.FAILED
            if status == DispatchStatus.SENT:
                await _say(run_id, candidate_id, MissionEventKind.APPLIED,
                           f"Candidature envoyée chez {company} pour « {job.title} ».",
                           {"dispatch_id": str(sent.id), "channel": sent.channel.value}, sent=1)
                from app.agents.notifications import notify_application_sent
                await notify_application_sent(candidate_id, sent.id)
            elif status == DispatchStatus.SIMULATED:
                await _say(run_id, candidate_id, MissionEventKind.AWAITING_APPROVAL,
                           f"Tout est prêt pour {company}, mais rien n'est parti : "
                           f"{sent.error}. Le dossier t'attend dans Candidatures.",
                           {"dispatch_id": str(sent.id), "simulated": True}, simulated=1)
            else:
                await _say(run_id, candidate_id, MissionEventKind.ERROR,
                           f"L'envoi chez {company} a échoué. Le dossier reste prêt pour "
                           f"finir à la main.", {"dispatch_id": str(dispatch.id)}, failed=1)
        elif dispatch.status == DispatchStatus.AWAITING_APPROVAL:
            awaiting += 1
        else:
            manual += 1

    if awaiting:
        await _say(run_id, candidate_id, MissionEventKind.AWAITING_APPROVAL,
                   f"{awaiting} candidature{'s attendent' if awaiting > 1 else ' attend'} ton feu "
                   f"vert dans Candidatures.", {"count": awaiting}, awaiting_approval=awaiting)
    if manual:
        await _say(run_id, candidate_id, MissionEventKind.AWAITING_APPROVAL,
                   f"{manual} dossier{'s' if manual > 1 else ''} à envoyer toi-même sur le site "
                   f"de l'employeur (portail ou formulaire propre) — tout est rédigé.",
                   {"count": manual}, blocked=manual)


async def finalize_run(
    run_id: UUID, candidate_id: UUID, status: RunStatus
) -> None:
    """Clôture le run et fait rédiger le compte rendu par Alice."""
    async with async_session() as session:
        run = await session.get(MissionRun, run_id)
        if not run or run.status in (RunStatus.COMPLETED, RunStatus.INTERRUPTED):
            return

        events = (await session.execute(
            select(MissionEvent)
            .where(MissionEvent.run_id == run_id)
            .order_by(MissionEvent.created_at)
        )).scalars().all()

        run.status = status
        run.current_step = None
        run.finished_at = datetime.now(timezone.utc)
        stats = dict(run.stats or {})
        title = run.title
        minutes = run.duration_minutes
        await session.commit()

    report = await _write_report(title, minutes, status, stats, [e.summary for e in events])

    async with async_session() as session:
        run = await session.get(MissionRun, run_id)
        run.report = report
        await _log(
            session, run, candidate_id, MissionEventKind.STATUS_CHANGED,
            report,
            {"stats": stats, "status": status.value},
        )
        await session.commit()

    # Le candidat a pu fermer l'application : c'est le moment de lui écrire.
    # Ne lève jamais, et la clé de déduplication protège d'une double clôture.
    from app.agents.notifications import notify_mission_report
    await notify_mission_report(run_id)


async def _write_report(
    title: str, minutes: int, status: RunStatus, stats: dict, timeline: list[str]
) -> str:
    """Compte rendu conversationnel, écrit à partir des faits du journal."""
    from app.agents.persona import IDENTITY
    from app.config import settings

    facts = (
        f"Mission : {title}\n"
        f"Issue : {'terminée' if status == RunStatus.COMPLETED else 'interrompue'}\n"
        f"Compteurs : {stats}\n"
        f"À valider par le candidat : {stats.get('awaiting_approval', 0)}\n"
        f"Où trouver les dossiers : onglet Candidatures (CV adapté et lettre "
        f"téléchargeables pour chaque offre)\n"
        f"Journal :\n" + "\n".join(f"- {t}" for t in timeline[-25:])
    )

    packs = stats.get("packs", stats.get("letters", 0))
    fallback = (
        f"C'est fait : j'ai préparé {packs} dossier{'s' if packs > 1 else ''} complet"
        f"{'s' if packs > 1 else ''} (CV adapté et lettre), à retrouver dans Candidatures."
        if packs else "Je n'ai trouvé aucune offre de ton mandat à préparer pour l'instant."
    )
    if stats.get("sent"):
        fallback += f" {stats['sent']} candidature(s) sont parties."
    if stats.get("awaiting_approval"):
        fallback += (
            f" {stats['awaiting_approval']} attendent ton feu vert dans Candidatures."
        )

    if not settings.gemini_api_key:
        return fallback

    try:
        from app import llm
        response = await llm.generate(
            f"""{IDENTITY}

Tu rends compte d'une mission que tu viens de terminer.

{facts}

Rédige un compte rendu de 3 à 5 phrases, à la première personne, en français.
Donne les chiffres réels. Si quelque chose attend une validation, dis-le
clairement ; si rien n'attend de validation, ne prétends pas le contraire.
Termine en disant où retrouver les dossiers (onglet Candidatures).
N'invente aucune action qui ne figure pas dans le journal.
Pas de titre, pas de liste : un paragraphe parlé."""
        )
        return response.strip() or fallback
    except Exception as e:  # noqa: BLE001
        logger.error("Report generation failed: %s", e)
        return fallback


# ── Runs orphelins ─────────────────────────────────────────────────────────

#: Délai au-delà duquel un run sans battement est considéré mort.
#:
#: Généreux à dessein. Le battement est écrit à chaque étape, mais une seule
#: étape peut durer longtemps — qualifier plusieurs centaines d'annonces
#: enchaîne autant d'appels au modèle. Déclarer morte une mission qui travaille
#: est bien pire que d'attendre un quart d'heure avant de clore une mission qui
#: l'est vraiment : dans un cas on détruit du travail, dans l'autre on affiche
#: un état périmé quelques minutes de plus.
STALE_AFTER_SECONDS = 15 * 60


def is_orphaned(run: MissionRun, now: datetime) -> bool:
    """
    Plus personne ne s'occupe de ce run.

    Le signe de vie fait foi, pas l'heure de fin : un cycle entamé avant
    l'échéance se termine après, et le worker clôt alors lui-même, rapport
    compris. Une échéance dépassée n'est un abandon qu'au-delà du même délai
    de grâce.
    """
    if run.status not in (RunStatus.PREPARING, RunStatus.RUNNING):
        return False
    grace = timedelta(seconds=STALE_AFTER_SECONDS)
    # Avant le premier battement, c'est la date de création qui fait foi : un
    # run resté « en préparation » n'a jamais démarré.
    last_sign = run.heartbeat_at or run.started_at or run.created_at
    if last_sign and last_sign < now - grace:
        return True
    return bool(run.ends_at and run.ends_at < now - grace)


async def sweep_stale_runs() -> int:
    """
    Clôt les missions dont plus personne ne s'occupe.

    Un processus tué net — redéploiement, plantage, conteneur arrêté — n'a
    aucune chance d'exécuter son `except` : le run reste `RUNNING` en base
    indéfiniment. Sans ce balayage, Alice rapporterait une mission en cours
    qui n'existe plus, ce qu'elle ne doit jamais faire.

    Retourne le nombre de runs clos.
    """
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        candidates = (await session.execute(
            select(MissionRun).where(
                MissionRun.status.in_([RunStatus.PREPARING, RunStatus.RUNNING])
            )
        )).scalars().all()

        orphans = [(run.id, run.mission_id) for run in candidates if is_orphaned(run, now)]

    for run_id, _ in orphans:
        async with async_session() as session:
            run = await session.get(MissionRun, run_id)
            if not run or run.status not in (RunStatus.PREPARING, RunStatus.RUNNING):
                continue
            candidate_id = (
                await session.execute(
                    select(Mission.candidate_id).where(Mission.id == run.mission_id)
                )
            ).scalar_one_or_none()

        if candidate_id:
            # Passe par la clôture normale : le compte rendu doit exister même
            # quand la mission s'est arrêtée toute seule.
            await finalize_run(run_id, candidate_id, RunStatus.INTERRUPTED)

    if orphans:
        logger.warning("Balayage : %d mission(s) orpheline(s) close(s)", len(orphans))
    return len(orphans)
