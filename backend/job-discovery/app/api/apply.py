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
from pydantic import BaseModel, Field
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
from app.schemas.cover_letter import CoverLetterResult
from app.schemas.cv_content import CvContentResult

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


def _profile(candidate: Candidate) -> dict:
    """Le parcours du candidat, tel que les rédacteurs l'attendent."""
    from app.agents.application.pack import candidate_profile

    return candidate_profile(candidate)


def _tailoring(application: Application | None) -> dict | None:
    return (application.metadata_json or {}).get("tailored_cv") if application else None


# ── Offre collée par le candidat ───────────────────────────────────────────


class ImportIn(BaseModel):
    text: str = Field(min_length=80, max_length=30000, description="Texte de l'annonce.")
    url: str | None = Field(default=None, max_length=2000)


class JobCardOut(BaseModel):
    """Même forme que les offres renvoyées par Alice : le front les affiche pareil."""
    id: UUID
    title: str
    company_name: str
    location: str
    match_score: int
    contract_type: str
    remote_policy: str
    source_url: str
    status: str
    #: Motifs pour lesquels l'offre sort du mandat, s'il y en a.
    rejections: list[str] = []


@router.post("/import", response_model=JobCardOut, status_code=201)
async def import_job(candidate_id: UUID, data: ImportIn):
    """
    Ajoute une offre trouvée ailleurs à la liste du candidat.

    Elle y entre quel que soit son score — c'est lui qui l'a choisie — mais le
    score et ses motifs sont renvoyés, pour qu'il sache à quoi s'en tenir.
    """
    from app.agents.discovery.job_import import import_posting

    url = (data.url or "").strip() or None
    result = await import_posting(candidate_id, data.text.strip(), url)
    if not result:
        raise HTTPException(404, "Candidat introuvable")
    job, company_name, application = result

    return JobCardOut(
        id=job.id,
        title=job.title,
        company_name=company_name,
        location=job.location or "",
        match_score=application.match_score,
        contract_type=job.contract_type.value,
        remote_policy=job.remote_policy.value,
        source_url=job.source_url,
        status=application.status.value,
        rejections=(application.metadata_json or {}).get("match", {}).get("rejections", []),
    )


# ── CV et lettre adaptés à une offre ───────────────────────────────────────


class TailorOut(BaseModel):
    cv: CvContentResult
    letter: CoverLetterResult


@router.post("/{job_id}/tailor", response_model=TailorOut)
async def tailor_documents(candidate_id: UUID, job_id: UUID):
    """
    Rédige l'accroche, la synthèse et la lettre pour CETTE offre.

    Le résultat est rangé sur la candidature, pas sur le profil : les autres
    candidatures gardent le CV général. Ce sont ce CV et cette lettre qui
    partiront à l'envoi.
    """
    from app.agents.application.pack import build_pack

    async with async_session() as session:
        job, _, candidate, application = await _load(session, candidate_id, job_id)
        if not job or not candidate:
            raise HTTPException(404, "Offre ou candidat introuvable")
        if not application:
            raise HTTPException(404, "Cette offre n'est pas dans ta liste.")
        app_id = application.id

    pack = await build_pack(candidate_id, app_id)
    if not pack:
        raise HTTPException(404, "Offre ou candidat introuvable")
    return TailorOut(cv=pack.cv, letter=pack.letter)


@router.get("/{job_id}/cv")
async def download_tailored_cv(
    candidate_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Le CV qui partira pour cette offre : adapté s'il l'a été, général sinon."""
    from app.agents.application.cv_resolver import resolve_cv

    job, _, candidate, application = await _load(db, candidate_id, job_id)
    if not job or not candidate:
        raise HTTPException(404, "Offre ou candidat introuvable")

    # La compilation Typst occupe le processeur : hors de la boucle d'événements.
    pdf, name, _ = await asyncio.to_thread(resolve_cv, candidate, _tailoring(application))
    if not pdf:
        raise HTTPException(404, "Aucun CV disponible — dépose-le dans l'éditeur.")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )

@router.get("/{job_id}/pack")
async def download_pack(
    candidate_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Le dossier de candidature d'une offre, en un ZIP : CV, lettre, annonce.

    Candidature déjà partie : les pièces envoyées, telles quelles. Sinon : les
    pièces qui partiraient maintenant, adaptées à l'offre si elles l'ont été.
    """
    import io
    import zipfile

    from app.agents.application.cv_resolver import _safe_name, resolve_cv
    from app.agents.discovery.letter_render import render_letter_pdf
    from app.models.dispatch import DispatchStatus

    job, company_name, candidate, application = await _load(db, candidate_id, job_id)
    if not job or not candidate:
        raise HTTPException(404, "Offre ou candidat introuvable")

    sent = None
    if application:
        sent = (await db.execute(
            select(ApplicationDispatch)
            .where(ApplicationDispatch.application_id == application.id)
            .where(ApplicationDispatch.status == DispatchStatus.SENT)
            .order_by(ApplicationDispatch.sent_at.desc())
        )).scalars().first()

    files: dict[str, bytes] = {}

    # ── CV ──
    if sent and sent.resume_blob:
        files[sent.resume_name or "CV.pdf"] = sent.resume_blob
    else:
        pdf, name, _ = await asyncio.to_thread(resolve_cv, candidate, _tailoring(application))
        if pdf:
            files[name] = pdf

    # ── Lettre ──
    company_slug = _safe_name(company_name or "entreprise")
    letter = (application.metadata_json or {}).get("cover_letter") if application else None
    if sent and sent.letter_body:
        subject = sent.letter_subject or f"Candidature — {sent.job_title}"
        files[f"Lettre_{company_slug}.txt"] = f"{subject}\n\n{sent.letter_body}\n".encode()
    elif letter:
        try:
            files[f"Lettre_{company_slug}.pdf"] = await asyncio.to_thread(
                render_letter_pdf, CoverLetterResult(**letter),
            )
        except Exception as e:  # noqa: BLE001 — la lettre reste lisible en texte
            logger.error("Rendu PDF de la lettre impossible : %s", e, exc_info=True)
            files[f"Lettre_{company_slug}.txt"] = (
                f"{letter.get('subject', '')}\n\n{letter.get('body', '')}\n".encode()
            )

    # ── Annonce ──
    contact = job.contact_json or {}
    header = [
        job.title,
        f"{company_name or ''} · {job.location or ''}".strip(" ·"),
        f"Lien : {job.apply_url or job.source_url}" if not job.source_url.startswith("import://") else "",
        f"Contact : {contact['email']}" if contact.get("email") else "",
    ]
    annonce = "\n".join(l for l in header if l) + "\n\n" + (job.description_raw or "")
    files["Annonce.txt"] = annonce.encode()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="Candidature_{company_slug}.zip"'},
    )


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
    plan = detect_requirements(job, candidate, letter, _tailoring(application))

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
                plan = detect_requirements(job, candidate, letter, _tailoring(application))
                job_title, apply_channel = job.title, job.apply_channel
                app_id = application.id if application else None
                profile = _profile(candidate)

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
            if real:
                from app.agents.notifications import notify_application_sent
                await notify_application_sent(candidate_id, sent.id)

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
