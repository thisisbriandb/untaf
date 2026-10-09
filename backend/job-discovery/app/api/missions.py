"""
API Missions — le mandat confié à Alice, son niveau d'autonomie, et le journal
de ce qu'elle a fait.

La mission est adressée par candidat (un seul mandat actif), ce qui évite au
frontend d'avoir à connaître son id.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.application import Application, ApplicationStatus
from app.models.candidate import Candidate
from app.models.mission import (
    Mission, MissionEvent, MissionEventKind, MissionRun, MissionStatus, RunStatus,
)
from app.agents.mission_runner import execute_run, finalize_run
from app.agents.mission_log import get_or_create_mission, log_event
from app.schemas.matching import MatchingCriteria
from app.schemas.mission import (
    MissionDetail, MissionEventOut, MissionOut, MissionRunDetail, MissionRunOut,
    MissionStats, MissionUpdate, RunCreate, RunEventOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates/{candidate_id}/mission", tags=["missions"])


async def _load(db: AsyncSession, candidate_id: UUID) -> tuple[None, Mission]:
    """
    La mission du candidat. Appelée toutes les quelques secondes (suivi de
    mission, cloche) : on ne charge pas le candidat — son CV, sa photo… —
    pour vérifier qu'il existe, et on n'écrit que si la mission est créée.
    """
    exists = (await db.execute(select(Candidate.id).where(Candidate.id == candidate_id))).first()
    if not exists:
        raise HTTPException(404, "Candidate profile not found")
    mission = await get_or_create_mission(db, candidate_id)
    if db.new:
        await db.commit()
        await db.refresh(mission)
    return None, mission


async def _stats(db: AsyncSession, candidate_id: UUID, mission: Mission) -> MissionStats:
    counts = dict((await db.execute(
        select(Application.status, func.count(Application.id))
        .where(Application.candidate_id == candidate_id)
        .group_by(Application.status)
    )).all())

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    applied_this_week = (await db.execute(
        select(func.count(Application.id))
        .where(Application.candidate_id == candidate_id)
        .where(Application.applied_at.is_not(None))
        .where(Application.applied_at >= week_ago)
    )).scalar() or 0

    last_scan = (await db.execute(
        select(MissionEvent)
        .where(MissionEvent.mission_id == mission.id)
        .where(MissionEvent.kind == MissionEventKind.SCAN)
        .order_by(MissionEvent.created_at.desc())
        .limit(1)
    )).scalars().first()

    return MissionStats(
        shortlisted=counts.get(ApplicationStatus.MATCHED, 0) + counts.get(ApplicationStatus.PENDING, 0),
        applied=counts.get(ApplicationStatus.APPLIED, 0),
        interviews=counts.get(ApplicationStatus.INTERVIEW, 0),
        scanned_last_run=(last_scan.payload or {}).get("scanned", 0) if last_scan else 0,
        applied_this_week=applied_this_week,
        quota_remaining=max(0, mission.weekly_quota - applied_this_week),
    )


@router.get("", response_model=MissionDetail)
async def get_mission(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """La mission, son mandat effectif, ses compteurs et le début du journal."""
    _, mission = await _load(db, candidate_id)
    candidate = await db.get(Candidate, candidate_id)

    events = (await db.execute(
        select(MissionEvent)
        .where(MissionEvent.mission_id == mission.id)
        .order_by(MissionEvent.created_at.desc())
        .limit(15)
    )).scalars().all()

    return MissionDetail(
        **MissionOut.model_validate(mission).model_dump(),
        criteria=MatchingCriteria.resolve(candidate),
        criteria_is_explicit=candidate.matching_criteria is not None,
        stats=await _stats(db, candidate_id, mission),
        recent_events=[MissionEventOut.model_validate(e) for e in events],
    )


@router.patch("", response_model=MissionOut)
async def update_mission(
    candidate_id: UUID,
    data: MissionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Régler l'autonomie, le rythme ou l'état. Chaque changement laisse une trace
    au journal : le candidat doit pouvoir relire ce qu'il a autorisé et quand.
    """
    _, mission = await _load(db, candidate_id)

    changes = data.model_dump(exclude_unset=True)
    traces: list[tuple[MissionEventKind, str]] = []

    if "autonomy" in changes and changes["autonomy"] != mission.autonomy:
        labels = {
            "propose": "Je te propose, tu valides chaque envoi.",
            "auto_above": f"J'envoie seule au-dessus de {mission.auto_apply_min_score}%, je te propose en dessous.",
            "full": "Je gère les envois dans les limites de ton mandat.",
        }
        traces.append((
            MissionEventKind.AUTONOMY_CHANGED,
            f"Autonomie réglée : {labels.get(changes['autonomy'], changes['autonomy'])}",
        ))

    if "status" in changes and changes["status"] != mission.status:
        traces.append((
            MissionEventKind.STATUS_CHANGED,
            "Mission mise en pause. J'arrête la veille jusqu'à nouvel ordre."
            if changes["status"] == MissionStatus.PAUSED
            else "Mission relancée. Je reprends la veille.",
        ))

    for key, value in changes.items():
        setattr(mission, key, value)

    for kind, summary in traces:
        await log_event(db, candidate_id, kind, summary)

    await db.commit()
    await db.refresh(mission)
    return mission


def _run_detail(run: MissionRun, events: list[MissionEvent]) -> MissionRunDetail:
    now = datetime.now(timezone.utc)
    remaining = 0
    progress = 1.0

    if run.status == RunStatus.RUNNING and run.ends_at and run.started_at:
        total = (run.ends_at - run.started_at).total_seconds() or 1
        remaining = max(0, int((run.ends_at - now).total_seconds()))
        progress = min(1.0, max(0.0, 1 - remaining / total))
    elif run.status == RunStatus.PREPARING:
        progress = 0.0

    return MissionRunDetail(
        **MissionRunOut.model_validate(run).model_dump(),
        seconds_remaining=remaining,
        progress=round(progress, 3),
        events=[RunEventOut.model_validate(e) for e in events],
    )


#: Références des missions exécutées sur place : sans elles, le ramasse-miettes
#: pourrait interrompre une tâche asyncio en cours.
_INPROCESS_RUNS: set[asyncio.Task] = set()


@router.post("/runs", response_model=MissionRunDetail, status_code=201)
async def start_run(
    candidate_id: UUID,
    data: RunCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Confie une mission bornée à Alice et la lance immédiatement.

    Un seul run actif à la fois : deux pipelines concurrentes se marcheraient
    dessus sur les mêmes offres.
    """
    _, mission = await _load(db, candidate_id)

    active = (await db.execute(
        select(MissionRun)
        .where(MissionRun.mission_id == mission.id)
        .where(MissionRun.status.in_([RunStatus.PREPARING, RunStatus.RUNNING]))
    )).scalars().first()
    if active:
        raise HTTPException(409, "Une mission est déjà en cours.")

    from app import billing
    await billing.check(db, candidate_id, "mission")
    await billing.record(db, candidate_id, "mission")

    run = MissionRun(
        mission_id=mission.id,
        title=data.title,
        # Préparer et postuler ne font plus qu'une mission (voir mission_runner).
        objective="apply",
        duration_minutes=0,
        allowed_actions={**(data.allowed_actions or {}), "count": data.count,
                         "spontaneous": data.spontaneous},
        status=RunStatus.PREPARING,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # La mission part dans un worker, pas dans le process web : c'est ce qui
    # permet à l'utilisateur de fermer l'application — et à l'API d'être
    # redéployée — sans interrompre le travail confié.
    #
    # `retry=False` : sans courtier joignable, Celery réessaie une vingtaine de
    # secondes avant d'abandonner. Mieux vaut échouer tout de suite et le dire.
    from app.agents.discovery.tasks import run_mission

    try:
        run_mission.apply_async(
            args=[str(run.id), str(candidate_id)], retry=False
        )
    except Exception as exc:  # noqa: BLE001
        # Sans worker joignable, la mission tourne dans ce processus plutôt
        # que de ne pas tourner du tout : c'est une seule passe de quelques
        # minutes, pas une boucle de plusieurs heures. Elle survit à la
        # fermeture de l'onglet, pas à un redéploiement de l'API.
        logger.warning("File de tâches indisponible (%s) : mission exécutée sur place.", exc)
        task = asyncio.create_task(execute_run(run.id, candidate_id))
        _INPROCESS_RUNS.add(task)
        task.add_done_callback(_INPROCESS_RUNS.discard)

    return _run_detail(run, [])


@router.get("/runs/current", response_model=MissionRunDetail | None)
async def get_current_run(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """Le run actif, ou le dernier terminé s'il n'y en a plus."""
    _, mission = await _load(db, candidate_id)

    run = (await db.execute(
        select(MissionRun)
        .where(MissionRun.mission_id == mission.id)
        .order_by(MissionRun.created_at.desc())
        .limit(1)
    )).scalars().first()

    if not run:
        return None

    # Un worker mort laisse un run « en cours » orphelin. Le balayage
    # périodique s'en charge, mais on ne peut pas afficher un travail fantôme
    # en attendant son prochain passage : battement de cœur périmé, on clôt
    # ici aussi — par la clôture normale, pour que le compte rendu et l'e-mail
    # existent.
    #
    # L'heure de fin dépassée ne suffit PAS : le dernier cycle déborde souvent
    # de quelques minutes, et clore ici rendait sans effet la vraie clôture du
    # worker — mission « interrompue », sans rapport ni notification.
    from app.agents.mission_runner import is_orphaned

    if is_orphaned(run, datetime.now(timezone.utc)):
        await finalize_run(run.id, candidate_id, RunStatus.INTERRUPTED)
        await db.refresh(run)

    events = (await db.execute(
        select(MissionEvent)
        .where(MissionEvent.run_id == run.id)
        .order_by(MissionEvent.created_at.desc())
        .limit(30)
    )).scalars().all()

    return _run_detail(run, events)


@router.post("/runs/{run_id}/stop", response_model=MissionRunDetail)
async def stop_run(
    candidate_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Interrompt la mission. Le compte rendu est rédigé sur ce qui a été fait."""
    _, mission = await _load(db, candidate_id)

    run = await db.get(MissionRun, run_id)
    if not run or run.mission_id != mission.id:
        raise HTTPException(404, "Mission introuvable")

    if run.status in (RunStatus.COMPLETED, RunStatus.INTERRUPTED):
        raise HTTPException(409, "Cette mission est déjà terminée.")

    await finalize_run(run_id, candidate_id, RunStatus.INTERRUPTED)

    await db.refresh(run)
    events = (await db.execute(
        select(MissionEvent)
        .where(MissionEvent.run_id == run.id)
        .order_by(MissionEvent.created_at.desc())
        .limit(30)
    )).scalars().all()

    return _run_detail(run, events)


@router.get("/runs", response_model=list[MissionRunOut])
async def list_runs(
    candidate_id: UUID,
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Historique des missions confiées."""
    _, mission = await _load(db, candidate_id)
    return (await db.execute(
        select(MissionRun)
        .where(MissionRun.mission_id == mission.id)
        .order_by(MissionRun.created_at.desc())
        .limit(limit)
    )).scalars().all()


@router.get("/journal", response_model=list[MissionEventOut])
async def get_journal(
    candidate_id: UUID,
    kind: MissionEventKind | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Le journal complet, du plus récent au plus ancien."""
    _, mission = await _load(db, candidate_id)

    query = select(MissionEvent).where(MissionEvent.mission_id == mission.id)
    if kind:
        query = query.where(MissionEvent.kind == kind)
    query = query.order_by(MissionEvent.created_at.desc()).limit(limit).offset(offset)

    return (await db.execute(query)).scalars().all()


@router.post("/journal/read", response_model=dict)
async def mark_journal_read(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """Marque tout le journal comme lu."""
    _, mission = await _load(db, candidate_id)

    events = (await db.execute(
        select(MissionEvent)
        .where(MissionEvent.mission_id == mission.id)
        .where(MissionEvent.is_read.is_(False))
    )).scalars().all()

    for e in events:
        e.is_read = True
    await db.commit()

    return {"marked": len(events)}
