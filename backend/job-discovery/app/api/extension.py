"""
Ce dont l'extension navigateur a besoin.

L'extension agit dans le navigateur du candidat, sur sa session à lui : elle
ajoute à Alice l'offre qu'il regarde, et remplit le formulaire de candidature
qu'il a devant les yeux. Il garde la main sur le bouton « Envoyer ».

Trois appels ici :
  - retrouver, depuis l'adresse de la page, l'offre déjà connue d'Alice ;
  - l'identité à reporter dans les champs (nom, e-mail, téléphone, liens) ;
  - les réponses aux questions du formulaire, tirées du parcours et de l'offre,
    jamais inventées : une question sans réponse dans le parcours reste vide.
"""

import json
import logging
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.job_posting import JobPosting

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates/{candidate_id}/extension", tags=["extension"])


# ── Retrouver l'offre de la page ───────────────────────────────────────────


def url_key(url: str) -> str:
    """
    Clé de comparaison d'une adresse : hôte sans « www. » + chemin sans « / »
    final, sans requête ni ancre. Les paramètres de suivi (utm, ref…) varient
    d'un lien à l'autre, pas l'offre.
    """
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return ""
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = parts.path.rstrip("/")
    for suffix in ("/apply", "/application", "/postuler", "/candidater"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
    return f"{host}{path}" if host else ""


class MatchOut(BaseModel):
    job_id: UUID
    title: str
    company_name: str
    #: Le dossier (CV adapté + lettre) est rédigé pour cette offre.
    pack_ready: bool
    status: str | None = None


@router.get("/match", response_model=MatchOut | None)
async def match_page(candidate_id: UUID, url: str, db: AsyncSession = Depends(get_db)):
    """L'offre de la liste du candidat qui correspond à cette page, s'il y en a une."""
    from app.agents.application.pack import is_pack_ready
    from app.agents.company_name import display_company

    key = url_key(url)
    if not key:
        return None
    host = key.split("/", 1)[0]
    # Préfiltre SQL sur l'hôte, comparaison exacte en Python.
    rows = (await db.execute(
        select(JobPosting, Company.name, Application)
        .join(Company, JobPosting.company_id == Company.id)
        .join(Application, Application.job_posting_id == JobPosting.id)
        .where(Application.candidate_id == candidate_id)
        .where(or_(JobPosting.source_url.ilike(f"%{host}%"),
                   JobPosting.apply_url.ilike(f"%{host}%")))
        .limit(500)
    )).all()
    for job, company_name, application in rows:
        keys = {url_key(job.source_url or ""), url_key(job.apply_url or "")}
        if key in keys or any(k and key.startswith(k + "/") for k in keys):
            return MatchOut(
                job_id=job.id, title=job.title,
                company_name=display_company(company_name) or "",
                pack_ready=is_pack_ready(application),
                status=application.status.value,
            )
    return None


# ── Identité à reporter dans les champs ────────────────────────────────────


class ProfileOut(BaseModel):
    full_name: str
    first_name: str
    last_name: str
    email: str
    phone: str
    city: str
    linkedin_url: str
    github_url: str
    website_url: str
    headline: str


def split_name(full_name: str) -> tuple[str, str]:
    """« Briand Bataillon » → (« Briand », « Bataillon ») ; un seul mot → nom vide."""
    parts = (full_name or "").split()
    if not parts:
        return "", ""
    return parts[0], " ".join(parts[1:])


@router.get("/profile", response_model=ProfileOut)
async def profile(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Profil introuvable.")
    first, last = split_name(candidate.full_name)
    return ProfileOut(
        full_name=candidate.full_name or "",
        first_name=first, last_name=last,
        email=candidate.email or "",
        phone=candidate.phone or "",
        city=(candidate.preferred_locations or [""])[0] or "",
        linkedin_url=candidate.linkedin_url or "",
        github_url=candidate.github_url or "",
        website_url=candidate.website_url or "",
        headline=candidate.headline or "",
    )


# ── Réponses aux questions du formulaire ───────────────────────────────────


class Question(BaseModel):
    id: str = Field(max_length=200)
    label: str = Field(max_length=1000)
    #: text | textarea | select | radio | checkbox | number | date
    kind: str = Field(default="text", max_length=20)
    options: list[str] = Field(default_factory=list, max_length=60)


class AnswersIn(BaseModel):
    job_id: UUID | None = None
    #: Texte de la page, quand l'offre n'est pas (encore) dans la liste.
    page_text: str | None = Field(default=None, max_length=12000)
    questions: list[Question] = Field(max_length=40)


class Answer(BaseModel):
    id: str
    #: None : le parcours ne permet pas de répondre — le champ reste vide.
    value: str | None = None


class AnswersOut(BaseModel):
    answers: list[Answer]


class _LlmAnswers(BaseModel):
    answers: list[Answer]


ANSWER_PROMPT = """Tu aides un candidat à remplir un formulaire de candidature.
Réponds à chaque question UNIQUEMENT à partir de son parcours et de l'offre
ci-dessous. Règles :
- N'invente rien : pas de diplôme, d'expérience, de salaire, de date ou de
  disponibilité qui ne figure pas dans le parcours. Sans information, value = null.
- Questions juridiques ou sensibles (handicap, origine, religion, casier,
  situation familiale, consentement RGPD, acceptation de conditions) : value = null.
  Le candidat y répondra lui-même.
- Choix multiple (options fournies) : renvoie exactement le texte d'une option,
  sinon null.
- Questions ouvertes (motivation, « pourquoi nous ») : 2 à 4 phrases sobres,
  à la première personne, en français sauf si la question est dans une autre
  langue, reliées concrètement au parcours.
- Oui/non sur une compétence : « Oui » seulement si le parcours le montre.

Parcours du candidat :
{profile}

Offre :
{job}

Questions (JSON) :
{questions}

Réponds en JSON : {{"answers": [{{"id": "...", "value": "..." ou null}}]}}"""


def _sanitize(questions: list[Question], raw: list[Answer]) -> list[Answer]:
    """Une réponse par question posée ; une option inconnue devient null."""
    by_id = {a.id: a.value for a in raw}
    out = []
    for q in questions:
        value = by_id.get(q.id)
        if isinstance(value, str):
            value = value.strip() or None
        if value and q.options and q.kind in ("select", "radio", "checkbox"):
            match = next((o for o in q.options if o.strip().lower() == value.lower()), None)
            value = match
        out.append(Answer(id=q.id, value=value))
    return out


@router.post("/answers", response_model=AnswersOut)
async def answer_questions(
    candidate_id: UUID, data: AnswersIn, db: AsyncSession = Depends(get_db),
):
    from app.agents.application.pack import candidate_profile
    from app.llm import generate

    if not data.questions:
        return AnswersOut(answers=[])
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Profil introuvable.")

    job_text = (data.page_text or "")[:6000]
    if data.job_id:
        row = (await db.execute(
            select(JobPosting, Company.name)
            .join(Company, JobPosting.company_id == Company.id)
            .where(JobPosting.id == data.job_id)
        )).first()
        if row:
            job, company_name = row
            job_text = f"{job.title} — {company_name}\n{(job.description_raw or '')[:6000]}"

    profile = candidate_profile(candidate)
    profile.pop("signature_image", None)
    prompt = ANSWER_PROMPT.format(
        profile=json.dumps(profile, ensure_ascii=False, default=str)[:12000],
        job=job_text or "(non fournie)",
        questions=json.dumps([q.model_dump() for q in data.questions], ensure_ascii=False),
    )
    try:
        raw = _LlmAnswers.model_validate_json(await generate(prompt, schema=_LlmAnswers))
    except Exception as e:  # noqa: BLE001
        logger.warning("Réponses de formulaire : échec du modèle : %s", e)
        raise HTTPException(502, "Je n'ai pas pu préparer les réponses. Réessaie.") from None
    return AnswersOut(answers=_sanitize(data.questions, raw.answers))
