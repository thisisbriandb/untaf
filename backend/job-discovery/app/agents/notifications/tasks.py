"""Tâches planifiées des notifications : relances dues et rapports périodiques."""

import asyncio
import logging

from sqlalchemy import select

from app.agents.discovery.tasks import _release
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _check_followups() -> int:
    from app.agents.application.followup import due_followups
    from app.agents.notifications import notify_followups_due
    from app.database import async_session
    from app.models.candidate import Candidate

    async with async_session() as session:
        ids = (await session.execute(select(Candidate.id))).scalars().all()

    notified = 0
    for candidate_id in ids:
        async with async_session() as session:
            due = await due_followups(session, candidate_id)
        if due and await notify_followups_due(candidate_id, due):
            notified += 1
    return notified


@celery_app.task(name="app.agents.notifications.tasks.check_followups")
def check_followups():
    """Quotidien : prévient les candidats dont des candidatures sont à relancer."""
    loop = asyncio.new_event_loop()
    try:
        return {"notified": loop.run_until_complete(_check_followups())}
    finally:
        _release(loop)


async def _remind_pending() -> int:
    from app.agents.notifications import notify_pending
    from app.database import async_session
    from app.models.dispatch import ApplicationDispatch, DispatchStatus

    async with async_session() as session:
        ids = (await session.execute(
            select(ApplicationDispatch.candidate_id)
            .where(ApplicationDispatch.status.in_((
                DispatchStatus.AWAITING_APPROVAL, DispatchStatus.PREPARED,
            )))
            .distinct()
        )).scalars().all()

    notified = 0
    for candidate_id in ids:
        if await notify_pending(candidate_id):
            notified += 1
    return notified


@celery_app.task(name="app.agents.notifications.tasks.remind_pending")
def remind_pending():
    """Quotidien : rappelle les dossiers prêts qui attendent le candidat (J+1, J+4)."""
    loop = asyncio.new_event_loop()
    try:
        return {"notified": loop.run_until_complete(_remind_pending())}
    finally:
        _release(loop)


@celery_app.task(name="app.agents.notifications.tasks.send_digests")
def send_digests(period: str = "weekly"):
    """Rapport d'activité aux candidats abonnés à cette période."""
    from app.agents.notifications import send_digests as run

    loop = asyncio.new_event_loop()
    try:
        return {"sent": loop.run_until_complete(run(period))}
    finally:
        _release(loop)
