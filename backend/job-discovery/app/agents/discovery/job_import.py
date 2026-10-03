"""
Offres collées par le candidat.

Une annonce trouvée ailleurs (LinkedIn, Indeed, un courriel de recruteur…)
entre dans le même circuit que les offres découvertes : même qualification,
même score, même candidature. Elle rejoint d'office la liste du candidat —
c'est lui qui l'a choisie — quel que soit son score.

Elle reste privée : un courriel de recruteur n'a pas vocation à être proposé
aux autres candidats. Son `external_id` commence par IMPORT_PREFIX, et la
liste publique comme le matching collectif l'excluent.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from pydantic import Field
from sqlalchemy import select

from app import llm
from app.agents.discovery.contact_extract import find_apply_email, find_apply_url, is_valid_email
from app.agents.discovery.deduplicator import compute_fingerprint
from app.agents.discovery.france_travail_task import _slugify
from app.agents.discovery.matching import evaluate_match
from app.agents.discovery.qualification import QualifiedJobResponse, heuristic_qualify
from app.config import settings
from app.database import async_session
from app.models.application import Application, ApplicationStatus
from app.models.candidate import Candidate
from app.models.company import ATSType, Company, CompanyStatus, SeedSource
from app.models.job_posting import (
    IMPORT_PREFIX, ApplyChannel, ApplyComplexity, ContractType, JobPosting,
    PostingStatus, RemotePolicy,
)

logger = logging.getLogger(__name__)

#: Suffixe des employeurs créés par import : jamais confondus avec un vrai domaine.
IMPORT_DOMAIN_SUFFIX = ".import.local"

UNKNOWN_COMPANY = "Entreprise non précisée"

_CONTRACTS = {
    "cdi": ContractType.CDI, "cdd": ContractType.CDD,
    "freelance": ContractType.FREELANCE, "internship": ContractType.STAGE,
    "stage": ContractType.STAGE, "alternance": ContractType.ALTERNANCE,
}
_REMOTE = {
    "remote": RemotePolicy.REMOTE, "hybrid": RemotePolicy.HYBRID,
    "onsite": RemotePolicy.ONSITE,
}


class ImportedPosting(QualifiedJobResponse):
    title: str = Field(description="Intitulé exact du poste, tel qu'écrit dans l'annonce.")
    company_name: str = Field(
        description="Nom de l'entreprise qui recrute. Chaîne vide si l'annonce ne le dit pas."
    )
    location: str | None = Field(description="Ville ou lieu de travail. Null si absent.")
    contact_email: str | None = Field(
        description="Adresse e-mail où envoyer la candidature, si l'annonce en donne une. Null sinon."
    )
    apply_url: str | None = Field(
        description="Lien de candidature mentionné dans l'annonce. Null sinon."
    )


PROMPT = """Voici une offre d'emploi collée par un candidat. Extrais-en les
informations. N'invente rien : un champ absent de l'annonce reste vide ou null.

{text}"""


def _heuristic(text: str) -> dict:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    title = (lines[0] if lines else "Offre importée")[:200]
    return {
        **heuristic_qualify(title, text),
        "title": title,
        "company_name": "",
        "location": None,
        "contact_email": find_apply_email(text),
        "apply_url": None,
    }


async def extract_posting(text: str) -> dict:
    """Les champs de l'annonce. Ne lève jamais : repli heuristique sans LLM."""
    if not settings.gemini_api_key:
        return _heuristic(text)
    try:
        raw = await llm.generate(PROMPT.format(text=text[:12000]), schema=ImportedPosting)
        return ImportedPosting(**json.loads(raw)).model_dump()
    except Exception as e:  # noqa: BLE001
        logger.error("Extraction de l'offre importée impossible : %s", e, exc_info=True)
        return _heuristic(text)


async def _get_or_create_company(session, name: str) -> Company:
    clean_name = (name or "").strip() or UNKNOWN_COMPANY
    domain = f"{_slugify(clean_name)}{IMPORT_DOMAIN_SUFFIX}"
    company = (await session.execute(
        select(Company).where(Company.domain == domain)
    )).scalars().first()
    if company:
        return company
    company = Company(
        name=clean_name[:300],
        domain=domain,
        slug=_slugify(clean_name),
        ats_type=ATSType.UNKNOWN,
        # Pas de site carrière à résoudre : PENDING relancerait le résolveur.
        status=CompanyStatus.NO_CAREER_PAGE,
        seed_source=SeedSource.MANUAL,
        is_active=True,
    )
    session.add(company)
    await session.flush()
    return company


async def import_posting(
    candidate_id: uuid.UUID, text: str, url: str | None = None,
) -> tuple[JobPosting, str, Application] | None:
    """Enregistre l'offre et l'ajoute à la liste du candidat. None si candidat inconnu."""
    data = await extract_posting(text)
    parsed = {k: data.get(k) for k in QualifiedJobResponse.model_fields}

    title = (data.get("title") or "").strip()[:500] or "Offre importée"
    location = (data.get("location") or "").strip() or None
    # L'adresse proposée par le modèle est contrôlée comme les autres : une
    # boîte de plateforme ou une adresse inventée ferait partir la
    # candidature dans le vide. À défaut, on la cherche dans le texte.
    proposed = (data.get("contact_email") or "").strip()
    email = proposed.lower() if is_valid_email(proposed) else find_apply_email(text)
    contact = {
        k: v for k, v in (
            ("email", email),
            ("apply_url", data.get("apply_url") or url or find_apply_url(text)),
        ) if v
    }
    if contact.get("email"):
        channel, complexity = ApplyChannel.EMAIL, ApplyComplexity.SIMPLE
    elif contact.get("apply_url"):
        # Formulaire de l'employeur, et non portail France Travail : le
        # classer EXTERNAL_LINK faisait annoncer un compte candidat requis.
        channel, complexity = ApplyChannel.WEB_FORM, ApplyComplexity.MEDIUM
    else:
        channel, complexity = ApplyChannel.UNKNOWN, ApplyComplexity.COMPLEX

    async with async_session() as session:
        candidate = await session.get(Candidate, candidate_id)
        if not candidate:
            return None

        company = await _get_or_create_company(session, data.get("company_name") or "")

        # Le candidat fait partie de l'empreinte : deux personnes qui collent
        # la même annonce gardent chacune la leur, avec leur propre texte.
        fingerprint = compute_fingerprint(
            f"{company.domain}#{candidate_id}", title, location,
        )
        job = (await session.execute(
            select(JobPosting).where(JobPosting.fingerprint == fingerprint)
        )).scalars().first()

        if job is None:
            job = JobPosting(
                company_id=company.id,
                external_id=f"{IMPORT_PREFIX}{candidate_id}:{uuid.uuid4()}",
                fingerprint=fingerprint,
                status=PostingStatus.ACTIVE,
            )
            session.add(job)

        # Un second collage de la même annonce rafraîchit son contenu.
        job.title = title
        job.description_raw = text
        job.description_parsed = parsed
        job.location = location
        job.source_url = url or f"import://{fingerprint[:16]}"
        job.apply_url = contact.get("apply_url")
        job.apply_channel = channel
        job.apply_complexity = complexity
        job.contact_json = contact or None
        job.remote_policy = _REMOTE.get(parsed.get("remote_policy"), RemotePolicy.UNKNOWN)
        job.contract_type = _CONTRACTS.get(parsed.get("contract_type"), ContractType.UNKNOWN)
        job.tech_stack = parsed.get("tech_stack") or []
        await session.flush()

        match = evaluate_match(candidate, job, parsed, company_name=company.name)
        job.match_score = match.score

        application = (await session.execute(
            select(Application)
            .where(Application.candidate_id == candidate_id)
            .where(Application.job_posting_id == job.id)
        )).scalars().first()
        metadata = {
            "source": "import",
            "qualification": parsed,
            "match": match.to_metadata(),
            "matched_at": datetime.now(timezone.utc).isoformat(),
        }
        if application is None:
            application = Application(
                candidate_id=candidate_id,
                job_posting_id=job.id,
                status=ApplicationStatus.MATCHED,
                match_score=match.score,
                metadata_json=metadata,
            )
            session.add(application)
        else:
            application.match_score = match.score
            application.metadata_json = {**(application.metadata_json or {}), **metadata}

        await session.commit()
        await session.refresh(job)
        await session.refresh(application)
        return job, company.name, application
