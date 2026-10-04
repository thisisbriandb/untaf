"""
Le parcours du candidat, complet, côté serveur.

Un CV adapté se compose à partir de `Candidate.cv_content` (expériences,
formation, langues). Quand ce parcours n'était jamais arrivé au serveur —
l'onboarding ne l'envoyait pas —, le CV adapté sortait avec un nom, une
accroche et des compétences, et rien d'autre : « un CV à moitié rempli ».

Ici, deux garanties :
  - si le parcours manque mais qu'un CV a été déposé, on le relit et on
    complète ce qui est vide — sans jamais écraser ce que le candidat a saisi ;
  - on dit précisément ce qui manque encore, pour que l'interface le montre
    plutôt que de livrer un document troué en silence.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.database import async_session
from app.models.candidate import Candidate

logger = logging.getLogger(__name__)

SECTIONS = ("experiences", "education", "languages")

SECTION_LABELS = {
    "experiences": "expériences",
    "education": "formation",
    "languages": "langues",
    "skills": "compétences",
    "summary": "présentation",
}


def missing_sections(candidate: Candidate) -> list[str]:
    """Sections vides du parcours, dans l'ordre où un recruteur les lit."""
    cv = candidate.cv_content or {}
    missing = [s for s in SECTIONS if not cv.get(s)]
    if not candidate.skills:
        missing.append("skills")
    if not (cv.get("summary") or candidate.resume_raw):
        missing.append("summary")
    return missing


async def ensure_cv_content(candidate_id: UUID) -> list[str]:
    """
    Complète le parcours depuis le CV déposé si des sections manquent.
    Renvoie les sections qui restent vides. Ne lève jamais.
    """
    async with async_session() as session:
        candidate = await session.get(Candidate, candidate_id)
        if not candidate:
            return list(SECTIONS)
        missing = missing_sections(candidate)
        if not missing or not candidate.resume_file:
            return missing
        pdf, filename = candidate.resume_file, candidate.resume_filename or "cv.pdf"

    try:
        from app.agents.discovery.resume_parser import parse_resume
        parsed = await parse_resume(pdf, filename)
    except Exception as e:  # noqa: BLE001 — le CV reste utilisable tel quel
        logger.warning("Relecture du CV déposé impossible : %s", e)
        return missing

    async with async_session() as session:
        candidate = await session.get(Candidate, candidate_id)
        cv = dict(candidate.cv_content or {})
        # Ce que le candidat a saisi l'emporte toujours sur la relecture.
        for key in SECTIONS:
            if not cv.get(key) and getattr(parsed, key, None):
                cv[key] = getattr(parsed, key)
        if not cv.get("summary") and parsed.summary:
            cv["summary"] = parsed.summary
        candidate.cv_content = cv
        if not candidate.skills and parsed.skills:
            candidate.skills = list(parsed.skills)
        if not candidate.headline and parsed.headline:
            candidate.headline = parsed.headline
        await session.commit()
        await session.refresh(candidate)
        remaining = missing_sections(candidate)

    filled = [s for s in missing if s not in remaining]
    if filled:
        logger.info("Parcours complété depuis le CV déposé : %s", ", ".join(filled))
    return remaining


def order_skills_for_job(skills: list[str], job_skills: list[str], job_text: str = "") -> list[str]:
    """
    Les compétences demandées par l'offre passent devant. Aucune n'est retirée :
    adapter, c'est mettre en avant, pas amputer.
    """
    wanted = {s.lower() for s in job_skills}
    text = (job_text or "").lower()

    def rank(skill: str) -> int:
        s = skill.lower()
        if s in wanted:
            return 0
        if s and s in text:
            return 1
        return 2

    return sorted(skills, key=rank)  # tri stable : l'ordre du candidat est gardé à rang égal
