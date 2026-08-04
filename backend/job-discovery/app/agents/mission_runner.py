"""
Exécution d'une mission bornée dans le temps.

La pipeline fait du travail réel à chaque étape où c'est possible : collecte
sur les plateformes, qualification des annonces, confrontation au mandat,
rédaction des lettres. L'envoi passe par le CandidateAgent, en simulation tant
que l'utilisateur ne l'a pas explicitement autorisé.

Rien n'est mimé. Une étape qui ne peut pas s'exécuter est consignée comme telle
plutôt que rapportée comme faite : c'est la seule manière de rendre un compte
rendu qui vaille quelque chose.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select

from app.database import async_session
from app.models.candidate import Candidate
from app.models.company import ATSType
from app.models.job_posting import JobPosting, PostingStatus
from app.models.application import Application, ApplicationStatus
from app.models.mission import (
    Mission, MissionEvent, MissionEventKind, MissionRun, RunStatus, RunStep,
)

logger = logging.getLogger(__name__)

#: Intervalle entre deux cycles quand la durée n'est pas écoulée. Alice
#: continue de surveiller : de nouvelles offres peuvent apparaître.
CYCLE_PAUSE_SECONDS = 120

#: Nombre de lettres préparées par cycle — au-delà, on sature l'API du modèle
#: pour un bénéfice nul.
LETTERS_PER_CYCLE = 3


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


# ── Étapes ─────────────────────────────────────────────────────────────────

async def _step_scan(run_id: UUID, candidate_id: UUID) -> int:
    """
    Collecte des offres.

    France Travail est la source principale : officielle, gratuite, et couvrant
    tout le marché français. Les ATS ne donnent accès qu'aux entreprises qu'on a
    explicitement référencées — ils restent en complément.
    """
    from app.agents.discovery.france_travail_task import ingest_for_candidate
    from app.agents.discovery.tasks import _scrape_platform

    total = 0
    detail: dict = {}

    report = await ingest_for_candidate(candidate_id)
    if report.get("ok"):
        total += report["processed"]
        detail["france_travail"] = report["processed"]
    else:
        detail["france_travail_error"] = report.get("reason")
        logger.warning("France Travail indisponible pendant le run : %s", report)

    for ats in (ATSType.GREENHOUSE, ATSType.LEVER, ATSType.ASHBY):
        try:
            count = await _scrape_platform(ats)
            total += count
            detail[ats.value] = count
        except Exception as e:  # noqa: BLE001
            logger.error("Scrape %s failed during run: %s", ats.value, e)

    async with async_session() as session:
        run = await session.get(MissionRun, run_id)
        _bump(run, scanned=total)

        if detail.get("france_travail_error"):
            # Dire que la source principale est muette plutôt que de laisser
            # croire que la veille a couvert tout le marché.
            summary = (
                f"J'ai relevé {total} offres, mais France Travail ne me répond "
                f"pas — il me manque une partie du marché."
            )
        else:
            summary = f"J'ai relevé {total} offres, dont {detail.get('france_travail', 0)} via France Travail."

        await _log(
            session, run, candidate_id, MissionEventKind.SCAN, summary,
            {"scraped": total, **detail},
        )
        await session.commit()

    return total


async def _step_qualify(run_id: UUID, candidate_id: UUID) -> int:
    """Lecture et structuration des annonces non encore qualifiées."""
    from app.agents.discovery.tasks import _qualify_and_match_all

    try:
        qualified, _ = await _qualify_and_match_all()
    except Exception as e:  # noqa: BLE001
        logger.error("Qualification failed during run: %s", e, exc_info=True)
        qualified = 0

    if qualified:
        async with async_session() as session:
            run = await session.get(MissionRun, run_id)
            _bump(run, qualified=qualified)
            await _log(
                session, run, candidate_id, MissionEventKind.SCAN,
                f"J'ai lu et structuré {qualified} nouvelles annonces.",
                {"qualified": qualified},
            )
            await session.commit()

    return qualified


async def _step_match(run_id: UUID, candidate_id: UUID) -> int:
    """Confrontation au mandat du candidat."""
    from app.agents.discovery.tasks import _match_candidate_to_existing_jobs

    try:
        kept = await _match_candidate_to_existing_jobs(candidate_id)
    except Exception as e:  # noqa: BLE001
        logger.error("Matching failed during run: %s", e, exc_info=True)
        kept = 0

    async with async_session() as session:
        run = await session.get(MissionRun, run_id)
        run.stats = {**(run.stats or {}), "shortlisted": kept}
        await session.commit()

    return kept


async def _step_prepare(run_id: UUID, candidate_id: UUID) -> int:
    """Rédaction des lettres pour les offres du haut du panier."""
    from app.agents.discovery.cover_letter import write_cover_letter
    from app.models.company import Company

    prepared = 0

    async with async_session() as session:
        candidate = await session.get(Candidate, candidate_id)
        rows = (await session.execute(
            select(Application, JobPosting, Company.name)
            .join(JobPosting, Application.job_posting_id == JobPosting.id)
            .join(Company, JobPosting.company_id == Company.id)
            .where(Application.candidate_id == candidate_id)
            .where(Application.status == ApplicationStatus.MATCHED)
            .order_by(Application.match_score.desc())
            .limit(LETTERS_PER_CYCLE)
        )).all()

    cv = (candidate.cv_content or {}) if candidate else {}

    for app, job, company in rows:
        # Une lettre déjà rédigée n'est pas refaite.
        if (app.metadata_json or {}).get("cover_letter"):
            continue

        try:
            letter = await write_cover_letter(
                full_name=candidate.full_name or "",
                email=candidate.email or "",
                phone=candidate.phone or "",
                linkedin_url=candidate.linkedin_url or "",
                headline=candidate.headline or "",
                skills=list(candidate.skills or []),
                summary=cv.get("summary") or candidate.resume_raw or "",
                experiences=cv.get("experiences") or [],
                education=cv.get("education") or [],
                job_title=job.title,
                company_name=company,
                location=job.location or "",
                tech_stack=list((job.description_parsed or {}).get("tech_stack") or []),
                job_excerpt=job.description_raw or "",
                signature_image=candidate.signature_image,
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Letter generation failed for %s: %s", job.id, e)
            continue

        async with async_session() as session:
            stored = await session.get(Application, app.id)
            stored.metadata_json = {
                **(stored.metadata_json or {}),
                "cover_letter": letter.model_dump(),
            }
            run_m = await session.get(MissionRun, run_id)
            _bump(run_m, letters=1)
            await _log(
                session, run_m, candidate_id, MissionEventKind.LETTER_WRITTEN,
                f"J'ai préparé la lettre pour « {job.title} » chez {company}.",
                {"job_id": str(job.id), "company": company},
            )
            await session.commit()

        prepared += 1

    return prepared


async def _step_apply(run_id: UUID, candidate_id: UUID, authorized: bool) -> int:
    """
    Envoi des candidatures.

    Sans autorisation explicite, on n'envoie pas et on le dit : les offres
    prêtes passent en attente de validation. Rapporter un envoi qui n'a pas eu
    lieu ruinerait la valeur du compte rendu.
    """
    async with async_session() as session:
        pending = (await session.execute(
            select(Application)
            .where(Application.candidate_id == candidate_id)
            .where(Application.status == ApplicationStatus.MATCHED)
        )).scalars().all()

        ready = [a for a in pending if (a.metadata_json or {}).get("cover_letter")]

        run = await session.get(MissionRun, run_id)
        if not authorized:
            if ready:
                await _log(
                    session, run, candidate_id, MissionEventKind.AWAITING_APPROVAL,
                    f"{len(ready)} candidature{'s sont prêtes' if len(ready) > 1 else ' est prête'} "
                    f"à partir. Tu ne m'as pas autorisée à envoyer : elles attendent ton feu vert.",
                    {"count": len(ready)},
                )
                run.stats = {**(run.stats or {}), "awaiting_approval": len(ready)}
            await session.commit()
            return 0

        await _log(
            session, run, candidate_id, MissionEventKind.ERROR,
            "L'envoi automatique n'est pas encore raccordé : je prépare les "
            "dossiers, mais je ne peux pas les soumettre moi-même.",
            {"ready": len(ready)},
        )
        run.stats = {**(run.stats or {}), "awaiting_approval": len(ready)}
        await session.commit()

    return 0


# ── Boucle d'exécution ─────────────────────────────────────────────────────

async def execute_run(run_id: UUID, candidate_id: UUID) -> None:
    """
    Déroule la pipeline jusqu'à la fin de la durée impartie.

    Chaque cycle refait une passe complète : de nouvelles offres peuvent
    apparaître pendant que la mission tourne, et c'est précisément ce qui
    justifie de la laisser travailler dans la durée.
    """
    async with async_session() as session:
        run = await session.get(MissionRun, run_id)
        if not run:
            return
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        run.heartbeat_at = run.started_at
        run.ends_at = run.started_at + timedelta(minutes=run.duration_minutes)
        run.stats = {}
        await _log(
            session, run, candidate_id, MissionEventKind.MISSION_CREATED,
            f"Je démarre : {run.title}. Je travaille dessus pendant "
            f"{run.duration_minutes} minutes.",
            {"duration_minutes": run.duration_minutes},
        )
        await session.commit()
        ends_at = run.ends_at
        objective = run.objective
        allowed = run.allowed_actions or {}

    try:
        while datetime.now(timezone.utc) < ends_at:
            async with async_session() as session:
                run = await session.get(MissionRun, run_id)
                if not run or run.status != RunStatus.RUNNING:
                    return
                # Signe de vie à chaque tour : c'est ce qui distingue une
                # mission qui travaille d'une mission dont le worker est mort.
                run.heartbeat_at = datetime.now(timezone.utc)
                await session.commit()

            for step, coro in (
                (RunStep.SCAN, lambda: _step_scan(run_id, candidate_id)),
                (RunStep.QUALIFY, lambda: _step_qualify(run_id, candidate_id)),
                (RunStep.MATCH, lambda: _step_match(run_id, candidate_id)),
            ):
                async with async_session() as s:
                    r = await s.get(MissionRun, run_id)
                    if not r or r.status != RunStatus.RUNNING:
                        return
                    r.current_step = step
                    # Un cycle complet peut durer bien plus longtemps qu'un
                    # seuil de péremption : qualifier plusieurs centaines
                    # d'annonces prend des minutes. Sans battement à chaque
                    # étape, le balayage conclurait à la mort d'une mission
                    # en plein travail.
                    r.heartbeat_at = datetime.now(timezone.utc)
                    await s.commit()
                await coro()

            if objective in ("prepare", "apply"):
                async with async_session() as s:
                    r = await s.get(MissionRun, run_id)
                    r.current_step = RunStep.PREPARE
                    await s.commit()
                await _step_prepare(run_id, candidate_id)

            if objective == "apply":
                async with async_session() as s:
                    r = await s.get(MissionRun, run_id)
                    r.current_step = RunStep.APPLY
                    await s.commit()
                await _step_apply(run_id, candidate_id, bool(allowed.get("send")))

            # Il reste du temps : on repasse plus tard plutôt que de boucler
            # à vide sur les mêmes offres.
            remaining = (ends_at - datetime.now(timezone.utc)).total_seconds()
            if remaining <= 0:
                break
            await asyncio.sleep(min(CYCLE_PAUSE_SECONDS, remaining))

    except asyncio.CancelledError:
        await finalize_run(run_id, candidate_id, RunStatus.INTERRUPTED)
        raise
    except Exception as e:  # noqa: BLE001
        logger.error("Mission run %s failed: %s", run_id, e, exc_info=True)
        await finalize_run(run_id, candidate_id, RunStatus.INTERRUPTED)
        return

    await finalize_run(run_id, candidate_id, RunStatus.COMPLETED)


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


async def _write_report(
    title: str, minutes: int, status: RunStatus, stats: dict, timeline: list[str]
) -> str:
    """Compte rendu conversationnel, écrit à partir des faits du journal."""
    from app.agents.persona import IDENTITY
    from app.config import settings

    facts = (
        f"Mission : {title}\n"
        f"Durée prévue : {minutes} minutes\n"
        f"Issue : {'terminée' if status == RunStatus.COMPLETED else 'interrompue'}\n"
        f"Compteurs : {stats}\n"
        f"Journal :\n" + "\n".join(f"- {t}" for t in timeline[-25:])
    )

    fallback = (
        f"Mission terminée. J'ai relevé {stats.get('scanned', 0)} offres, "
        f"retenu {stats.get('shortlisted', 0)}, et préparé "
        f"{stats.get('letters', 0)} lettre(s)."
    )

    if not settings.gemini_api_key:
        return fallback

    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(model_name=settings.gemini_model)
        response = model.generate_content(
            f"""{IDENTITY}

Tu rends compte d'une mission que tu viens de terminer.

{facts}

Rédige un compte rendu de 3 à 5 phrases, à la première personne, en français.
Donne les chiffres réels. Si quelque chose attend une validation, dis-le
clairement. N'invente aucune action qui ne figure pas dans le journal.
Pas de titre, pas de liste : un paragraphe parlé."""
        )
        return (response.text or "").strip() or fallback
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
    stale_before = now - timedelta(seconds=STALE_AFTER_SECONDS)

    async with async_session() as session:
        candidates = (await session.execute(
            select(MissionRun).where(
                MissionRun.status.in_([RunStatus.PREPARING, RunStatus.RUNNING])
            )
        )).scalars().all()

        orphans = []
        for run in candidates:
            # Avant le premier battement, c'est la date de création qui fait
            # foi : un run resté « en préparation » n'a jamais démarré.
            last_sign = run.heartbeat_at or run.started_at or run.created_at
            expired = run.ends_at is not None and run.ends_at < now
            if expired or (last_sign and last_sign < stale_before):
                orphans.append((run.id, run.mission_id))

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
