"""
Les dossiers pas encore envoyés suivent la mise en page du candidat.

Le CV joint à un envoi est figé à la préparation (c'est lui qu'on montre puis
qu'on envoie). Si le candidat change ensuite de modèle, de couleur ou de photo,
les envois en attente doivent partir avec ce nouveau choix, pas l'ancien.
"""

import logging
from uuid import UUID

from sqlalchemy import select

from app.database import async_session
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.dispatch import ApplicationDispatch, DispatchStatus

logger = logging.getLogger(__name__)

PENDING = (DispatchStatus.PREPARED, DispatchStatus.AWAITING_APPROVAL, DispatchStatus.APPROVED)


async def refresh_pending_resumes(candidate_id: UUID) -> int:
    """Recompose le CV des envois en attente. Renvoie le nombre de dossiers mis à jour."""
    from app.agents.application.cv_resolver import resolve_cv

    updated = 0
    try:
        async with async_session() as session:
            candidate = await session.get(Candidate, candidate_id)
            if not candidate:
                return 0
            rows = (await session.execute(
                select(ApplicationDispatch, Application)
                .join(Application, ApplicationDispatch.application_id == Application.id)
                .where(ApplicationDispatch.candidate_id == candidate_id)
                .where(ApplicationDispatch.status.in_(PENDING))
            )).all()
            for dispatch, application in rows:
                tailoring = (application.metadata_json or {}).get("tailored_cv")
                pdf, name, mode = resolve_cv(candidate, tailoring)
                if not pdf or mode == "render_failed":
                    continue  # on garde le CV déjà préparé plutôt que rien
                dispatch.resume_blob, dispatch.resume_name = pdf, name
                dispatch.documents = {**(dispatch.documents or {}), "resume_filename": name,
                                      "resume_mode": mode, "has_resume": True}
                updated += 1
            await session.commit()
    except Exception as e:  # noqa: BLE001 — une mise à jour ratée ne casse pas le choix
        logger.error("Mise à jour des CV en attente impossible : %s", e, exc_info=True)
    return updated
