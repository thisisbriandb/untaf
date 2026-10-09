"""
Pack de candidature — le CV adapté et la lettre pour UNE offre.

Un seul point d'entrée pour le Canvas (bouton « adapter ») et pour les missions
(étape « préparer ») : avant, la mission ne rédigeait que la lettre, et le CV
joint restait le CV général alors que l'utilisateur obtenait un CV adapté en
passant par le Canvas. Deux chemins, deux qualités de candidature.

Le résultat est rangé sur la candidature, jamais sur le profil : les autres
offres gardent le CV général.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.agents.application.identity import real_name
from app.database import async_session
from app.models.application import Application, ApplicationStatus
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.job_posting import JobPosting
from app.schemas.cover_letter import CoverLetterResult
from app.schemas.cv_content import CvContentRequest, CvContentResult

logger = logging.getLogger(__name__)


@dataclass
class Pack:
    cv: CvContentResult
    letter: CoverLetterResult
    job_title: str
    company_name: str
    #: Sections du parcours encore vides — à montrer, pas à taire.
    missing_sections: list[str] = field(default_factory=list)


def candidate_profile(candidate: Candidate) -> dict:
    """Le parcours du candidat, tel que les rédacteurs l'attendent."""
    cv = candidate.cv_content or {}
    return {
        # « Candidat » n'est pas un nom : la lettre ne le signe pas.
        "full_name": real_name(candidate) or "",
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


def is_pack_ready(application: Application | None) -> bool:
    """CV adapté ET lettre : tout ce qui partira est rédigé pour cette offre."""
    meta = (application.metadata_json or {}) if application else {}
    return bool(meta.get("cover_letter") and meta.get("tailored_cv"))


async def build_pack(candidate_id: UUID, application_id: UUID) -> Pack | None:
    """
    Rédige l'accroche, la synthèse et la lettre, puis les range sur la
    candidature. None si la candidature ou le candidat est introuvable.

    Le dossier est réservé dans la formule AVANT l'appel au modèle (sinon des
    demandes simultanées passaient toutes le contrôle), et rendu s'il n'a pas
    pu être rédigé. Lève `billing.LimitReached` quand la formule n'en permet
    plus cette semaine.
    """
    from app import billing

    reservation = await billing.reserve(candidate_id, "pack")
    try:
        pack = await _write_pack(candidate_id, application_id)
    except BaseException:
        await billing.release(reservation)
        raise
    if pack is None:
        await billing.release(reservation)
    return pack


async def _write_pack(candidate_id: UUID, application_id: UUID) -> Pack | None:
    from app.agents.application.cv_completeness import ensure_cv_content, order_skills_for_job
    from app.agents.discovery.cover_letter import write_cover_letter
    from app.agents.discovery.cv_writer import write_cv_content

    # Le parcours complet d'abord : sans lui, le CV adapté sortait à moitié vide.
    missing = await ensure_cv_content(candidate_id)

    async with async_session() as session:
        row = (await session.execute(
            select(Application, JobPosting, Company.name)
            .join(JobPosting, Application.job_posting_id == JobPosting.id)
            .join(Company, JobPosting.company_id == Company.id)
            .where(Application.id == application_id)
            .where(Application.candidate_id == candidate_id)
        )).first()
        candidate = await session.get(Candidate, candidate_id)
        if not row or not candidate:
            return None
        _, job, company_name = row
        profile = candidate_profile(candidate)
        languages = (candidate.cv_content or {}).get("languages") or []
        experience_years = candidate.experience_years

    from app.agents.spontaneous import is_spontaneous

    # Un employeur anonyme ne s'écrit pas « Employeur non précisé » dans une lettre.
    from app.agents.company_name import display_company
    company_name = display_company(company_name) or ""
    tech_stack = list((job.description_parsed or {}).get("tech_stack") or job.tech_stack or [])
    cv_request = CvContentRequest(
        full_name=profile["full_name"],
        headline=profile["headline"],
        summary=profile["summary"],
        skills=profile["skills"],
        experience_years=experience_years,
        experiences=profile["experiences"],
        education=profile["education"],
        languages=languages,
        target_role=job.title,
        job_title=job.title,
        company_name=company_name,
        job_excerpt=job.description_raw,
        job_skills=tech_stack,
    )
    # Les deux rédactions sont indépendantes : l'une n'attend pas l'autre.
    cv, letter = await asyncio.gather(
        write_cv_content(cv_request),
        write_cover_letter(
            **profile,
            job_title=job.title,
            company_name=company_name,
            location=job.location or "",
            tech_stack=tech_stack,
            job_excerpt=job.description_raw or "",
            spontaneous=is_spontaneous(job),
        ),
    )

    async with async_session() as session:
        stored = await session.get(Application, application_id)
        stored.metadata_json = {
            **(stored.metadata_json or {}),
            "tailored_cv": {
                "headline": cv.headline,
                "summary": cv.summary,
                # Mise en avant, jamais suppression : toutes les compétences
                # restent, celles que l'offre demande passent devant.
                "skills_order": order_skills_for_job(
                    profile["skills"], tech_stack, job.description_raw or "",
                ),
                # Réalisations reformulées pour l'offre et points forts : ce
                # qui distingue ce CV de celui que le candidat avait déjà.
                "experiences": cv.experiences,
                "strengths": cv.differentiators[:4] if cv.tailored_to_job else [],
                # « fallback » : rédigé sans le modèle (indisponible). Un tel
                # dossier ne part jamais sans que le candidat l'ait relu.
                "source": cv.source,
            },
            "cover_letter": letter.model_dump(),
            "pack_ready_at": datetime.now(timezone.utc).isoformat(),
        }
        # Un dossier rédigé est une offre retenue : restée « en attente », elle
        # n'apparaissait nulle part dans Candidatures.
        if stored.status == ApplicationStatus.PENDING:
            stored.status = ApplicationStatus.MATCHED
        await session.commit()

    return Pack(
        cv=cv, letter=letter, job_title=job.title, company_name=company_name,
        missing_sections=missing,
    )
