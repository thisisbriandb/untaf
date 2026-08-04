"""
Candidature depuis le Canvas — prérequis et envoi en flux.

L'envoi est diffusé étape par étape plutôt que rendu d'un bloc : l'utilisateur
voit ce qui se passe pendant que ça se passe. C'est aussi ce qui rend l'attente
supportable quand la rédaction de la lettre prend dix secondes.
"""

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.application.outcome import build_outcome
from app.agents.application.requirements import detect_requirements
from app.database import async_session, get_db
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.dispatch import ApplicationDispatch
from app.models.job_posting import JobPosting

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates/{candidate_id}/apply", tags=["apply"])


class RequirementOut(BaseModel):
    key: str
    label: str
    status: str
    detail: str = ""


class PlanOut(BaseModel):
    job_id: UUID
    job_title: str
    company_name: str
    channel: str
    destination: str | None
    can_apply: bool
    blocked_reason: str | None
    #: simple | medium | complex | impossible
    complexity: str = "unknown"
    summary: str = ""
    fallback_url: str | None = None
    requirements: list[RequirementOut]


async def _load(session, candidate_id: UUID, job_id: UUID):
    row = (await session.execute(
        select(JobPosting, Company.name)
        .join(Company, JobPosting.company_id == Company.id)
        .where(JobPosting.id == job_id)
    )).first()
    if not row:
        return None, None, None, None
    job, company_name = row

    candidate = await session.get(Candidate, candidate_id)
    application = (await session.execute(
        select(Application)
        .where(Application.candidate_id == candidate_id)
        .where(Application.job_posting_id == job_id)
    )).scalars().first()

    return job, company_name, candidate, application


@router.get("/{job_id}/plan", response_model=PlanOut)
async def get_plan(
    candidate_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Ce que cette offre demande, et ce dont on dispose déjà."""
    job, company_name, candidate, application = await _load(db, candidate_id, job_id)
    if not job or not candidate:
        raise HTTPException(404, "Offre ou candidat introuvable")

    letter = (application.metadata_json or {}).get("cover_letter") if application else None
    plan = detect_requirements(job, candidate, letter)

    return PlanOut(
        job_id=job_id,
        job_title=job.title,
        company_name=company_name or "",
        channel=plan.channel,
        destination=plan.destination,
        can_apply=plan.can_apply,
        blocked_reason=plan.blocked_reason,
        complexity=plan.complexity,
        summary=plan.summary,
        fallback_url=plan.fallback_url,
        requirements=[RequirementOut(**r.__dict__) for r in plan.requirements],
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{job_id}/stream")
async def apply_stream(candidate_id: UUID, job_id: UUID):
    """
    Monte et envoie la candidature, en diffusant chaque étape.

    Chaque étape est annoncée avant d'être exécutée, puis confirmée avec son
    résultat réel. Aucun message d'étape n'est émis pour un travail qui n'a pas
    eu lieu.
    """

    async def steps():
        try:
            async with async_session() as session:
                job, company_name, candidate, application = await _load(
                    session, candidate_id, job_id
                )
                if not job or not candidate:
                    yield _sse("error", {"message": "Offre ou candidat introuvable"})
                    return

                letter = (application.metadata_json or {}).get("cover_letter") if application else None
                plan = detect_requirements(job, candidate, letter)
                job_title, apply_channel = job.title, job.apply_channel
                app_id = application.id if application else None
                cv = candidate.cv_content or {}
                profile = {
                    "full_name": candidate.full_name or "",
                    "email": candidate.email or "",
                    "phone": candidate.phone or "",
                    "linkedin_url": candidate.linkedin_url or "",
                    "headline": candidate.headline or "",
                    "skills": list(candidate.skills or []),
                    "summary": cv.get("summary") or candidate.resume_raw or "",
                    "experiences": cv.get("experiences") or [],
                    "education": cv.get("education") or [],
                    "signature_image": candidate.signature_image,
                }

            # Aucune étape n'est émise pour un travail instantané : cocher
            # des cases qui se remplissent seules donne l'illusion d'un
            # traitement qui n'a pas lieu. On rend le verdict directement.
            if not plan.can_apply and plan.complexity != "simple":
                yield _sse("unsupported", {
                    "complexity": plan.complexity,
                    "message": plan.summary,
                    "reason": plan.blocked_reason,
                    "fallback_url": plan.fallback_url,
                    "requirements": [
                        {"key": r.key, "label": r.label, "status": r.status, "detail": r.detail}
                        for r in plan.requirements
                    ],
                })
                return

            if plan.missing:
                yield _sse("blocked", {
                    "message": "Il me manque des éléments obligatoires.",
                    "missing": [{"label": r.label, "detail": r.detail} for r in plan.missing],
                })
                return

            # ── Lettre de motivation ──────────────────────
            if "cover_letter" in plan.to_generate:
                yield _sse("step", {
                    "key": "cover_letter",
                    "label": "Je rédige ta lettre pour cette offre",
                    "status": "running",
                })

                from app.agents.discovery.cover_letter import write_cover_letter
                parsed = job.description_parsed or {}
                written = await write_cover_letter(
                    **profile,
                    job_title=job_title,
                    company_name=company_name or "",
                    location=job.location or "",
                    tech_stack=list(parsed.get("tech_stack") or []),
                    job_excerpt=job.description_raw or "",
                )
                letter = written.model_dump()

                if app_id:
                    async with async_session() as session:
                        stored = await session.get(Application, app_id)
                        stored.metadata_json = {
                            **(stored.metadata_json or {}), "cover_letter": letter,
                        }
                        await session.commit()

                yield _sse("step", {
                    "key": "cover_letter",
                    "label": "Lettre rédigée",
                    "status": "done",
                    "detail": letter.get("subject", ""),
                    "grounded": written.grounded_on_experiences,
                })

            # ── Autorisation ──────────────────────────────
            if not app_id:
                yield _sse("blocked", {
                    "message": "Cette offre n'est pas dans ta liste — je ne peux pas la suivre.",
                    "missing": [],
                })
                return

            yield _sse("step", {
                "key": "authorization",
                "label": "Je vérifie ce que ton mandat m'autorise",
                "status": "running",
            })

            from app.agents.application.dispatcher import prepare_dispatch, send_dispatch
            dispatch = await prepare_dispatch(candidate_id, app_id)
            if not dispatch:
                yield _sse("error", {"message": "Préparation impossible"})
                return

            if dispatch.status.value != "approved":
                yield _sse("awaiting", {
                    "dispatch_id": str(dispatch.id),
                    "message": dispatch.error or "En attente de ta validation.",
                    "channel": dispatch.channel.value,
                    "destination": dispatch.destination,
                })
                return

            yield _sse("step", {
                "key": "authorization", "label": "Autorisée", "status": "done",
            })

            # ── Envoi ─────────────────────────────────────
            yield _sse("step", {
                "key": "send",
                "label": f"J'envoie à {dispatch.destination}",
                "status": "running",
            })

            sent = await send_dispatch(dispatch.id)
            real = sent and sent.status.value == "sent"

            yield _sse("done", {
                "dispatch_id": str(sent.id) if sent else None,
                "status": sent.status.value if sent else "failed",
                "real": bool(real),
                "message": (
                    f"Candidature envoyée à {company_name}."
                    if real
                    else (sent.error if sent else "Envoi non abouti.")
                ),
            })

        except Exception as e:  # noqa: BLE001
            logger.error("Apply stream failed: %s", e, exc_info=True)
            yield _sse("error", {"message": "Une erreur est survenue pendant l'envoi."})

    return StreamingResponse(
        steps(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Issue d'une candidature ────────────────────────────────────────────────
#
# Réussie ou non, une candidature laisse des pièces et un chemin à suivre.
# Ces routes rendent l'un et l'autre récupérables après coup — le Canvas peut
# être fermé, la conversation reprise plus tard.


async def _load_dispatch(session, candidate_id: UUID, dispatch_id: UUID):
    """
    Charge un envoi en vérifiant qu'il appartient bien à ce candidat.

    Le filtre sur `candidate_id` n'est pas décoratif : sans lui, connaître un
    identifiant d'envoi suffirait à télécharger le CV de quelqu'un d'autre.
    """
    dispatch = (await session.execute(
        select(ApplicationDispatch)
        .where(ApplicationDispatch.id == dispatch_id)
        .where(ApplicationDispatch.candidate_id == candidate_id)
    )).scalar_one_or_none()
    if not dispatch:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    return dispatch


async def _job_url(session, dispatch) -> str | None:
    """URL de l'annonce d'origine, quand elle est encore connue."""
    row = (await session.execute(
        select(JobPosting.apply_url, JobPosting.source_url)
        .join(Application, Application.job_posting_id == JobPosting.id)
        .where(Application.id == dispatch.application_id)
    )).first()
    if not row:
        return None
    apply_url, source_url = row
    return apply_url or source_url or None


@router.get("/dispatches/{dispatch_id}")
async def get_dispatch_outcome(
    candidate_id: UUID,
    dispatch_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Issue exploitable d'une candidature : pièces, annonce, gestes restants."""
    dispatch = await _load_dispatch(db, candidate_id, dispatch_id)
    return build_outcome(dispatch, await _job_url(db, dispatch)).as_dict()


@router.get("/dispatches/{dispatch_id}/resume")
async def download_dispatch_resume(
    candidate_id: UUID,
    dispatch_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Le CV tel qu'il a été joint — l'instantané, pas une régénération."""
    dispatch = await _load_dispatch(db, candidate_id, dispatch_id)
    if not dispatch.resume_blob:
        raise HTTPException(status_code=404, detail="Aucun CV joint à cette candidature")

    name = dispatch.resume_name or "CV.pdf"
    return Response(
        content=dispatch.resume_blob,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/dispatches/{dispatch_id}/letter")
async def download_dispatch_letter(
    candidate_id: UUID,
    dispatch_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """La lettre telle qu'elle a été rédigée, objet compris."""
    dispatch = await _load_dispatch(db, candidate_id, dispatch_id)
    if not dispatch.letter_body:
        raise HTTPException(status_code=404, detail="Aucune lettre pour cette candidature")

    subject = dispatch.letter_subject or f"Candidature — {dispatch.job_title}"
    body = f"{subject}\n\n{dispatch.letter_body}\n"
    slug = "".join(c if c.isalnum() else "_" for c in dispatch.company_name)[:40] or "lettre"
    return Response(
        content=body.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="Lettre_{slug}.txt"'},
    )
