"""
Journal de mission — le point d'entrée unique pour consigner ce qu'Alice fait.

Deux règles :
  - écrire au journal ne doit JAMAIS faire échouer l'action qu'on consigne.
    Un log en erreur casserait une candidature réussie, ce qui serait absurde.
  - la mission est créée à la volée à la première consignation, pour que les
    candidats existants n'aient pas besoin d'une migration de données.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mission import Mission, MissionEvent, MissionEventKind, MissionStatus

logger = logging.getLogger(__name__)

#: Une passe de veille identique à la précédente dans ce délai n'est pas redite.
SCAN_REPEAT_WINDOW = timedelta(hours=12)


async def get_or_create_mission(session: AsyncSession, candidate_id: UUID) -> Mission:
    """La mission unique du candidat, créée au premier besoin."""
    mission = (await session.execute(
        select(Mission).where(Mission.candidate_id == candidate_id)
    )).scalars().first()

    if mission:
        return mission

    mission = Mission(candidate_id=candidate_id)
    session.add(mission)
    await session.flush()

    session.add(MissionEvent(
        mission_id=mission.id,
        kind=MissionEventKind.MISSION_CREATED,
        summary="Mission ouverte. Je commence la veille.",
    ))
    return mission


async def log_event(
    session: AsyncSession,
    candidate_id: UUID,
    kind: MissionEventKind,
    summary: str,
    payload: dict | None = None,
) -> MissionEvent | None:
    """
    Consigne une action. Ne commit pas — l'appelant reste maître de sa
    transaction. Renvoie None si la consignation a échoué.
    """
    try:
        mission = await get_or_create_mission(session, candidate_id)
        event = MissionEvent(
            mission_id=mission.id,
            kind=kind,
            summary=summary,
            payload=payload,
        )
        session.add(event)
        return event
    except Exception as e:  # noqa: BLE001 — journaliser ne doit rien casser
        logger.error("Mission log failed (%s): %s", kind, e, exc_info=True)
        return None


async def log_scan(
    session: AsyncSession,
    candidate_id: UUID,
    scanned: int,
    kept: int,
    discarded: int,
    top_reasons: dict[str, int] | None = None,
) -> None:
    """Résumé d'une passe de veille, formulé comme Alice le dirait."""
    if kept == 0:
        summary = (
            f"J'ai passé {scanned} offres en revue. Aucune ne correspond à ton "
            f"mandat pour l'instant."
        )
    else:
        summary = (
            f"J'ai passé {scanned} offres en revue et j'en ai retenu "
            f"{kept}{' (1 nouvelle)' if kept == 1 else ''}."
        )

    # Une passe identique à la précédente (même stock, même verdict) n'apprend
    # rien : elle remplissait le journal de la même ligne, dix fois de suite.
    mission = await get_or_create_mission(session, candidate_id)
    previous = (await session.execute(
        select(MissionEvent)
        .where(MissionEvent.mission_id == mission.id)
        .where(MissionEvent.kind == MissionEventKind.SCAN)
        .order_by(MissionEvent.created_at.desc())
        .limit(1)
    )).scalars().first()
    if (previous and previous.summary == summary
            and previous.created_at >= datetime.now(timezone.utc) - SCAN_REPEAT_WINDOW):
        return

    await log_event(
        session, candidate_id, MissionEventKind.SCAN, summary,
        payload={
            "scanned": scanned,
            "kept": kept,
            "discarded": discarded,
            "top_reasons": top_reasons or {},
        },
    )


async def is_mission_active(session: AsyncSession, candidate_id: UUID) -> bool:
    """Une mission en pause suspend la veille sans effacer le mandat."""
    mission = (await session.execute(
        select(Mission).where(Mission.candidate_id == candidate_id)
    )).scalars().first()
    return mission is None or mission.status == MissionStatus.ACTIVE
