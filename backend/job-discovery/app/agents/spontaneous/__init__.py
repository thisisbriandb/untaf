"""
Candidatures spontanées : Alice écrit aux entreprises qui recrutent sans
publier d'offre.

Le moteur ne fait qu'une chose : trouver, pour un candidat, des entreprises de
son métier dans ses villes, et l'adresse que chacune publie pour recruter.
Pour chaque entreprise trouvée, il crée une « offre » interne (candidature
spontanée, envoi par e-mail) et la candidature du candidat. Tout le reste —
dossier adapté (lettre centrée sur l'entreprise), relecture, contrôles avant
envoi, adresse de réponse, suivi, relances — passe par le circuit habituel.

Garde-fous (voir aussi `dispatcher.pre_send_check`) :
  - adresse publiée par l'entreprise sur son propre site, jamais devinée ;
  - désinscription respectée (adresse ou domaine entier) ;
  - plafonds par jour et par semaine ;
  - une entreprise n'est contactée qu'une fois par candidat (sur 6 mois).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.application import Application, ApplicationStatus
from app.models.candidate import Candidate
from app.models.company import ATSType, Company, CompanyStatus, SeedSource
from app.models.email_optout import EmailOptout
from app.models.job_posting import (
    ApplyChannel, ApplyComplexity, ContractType, JobPosting, PostingStatus,
)

logger = logging.getLogger(__name__)

SPONTANEOUS_PREFIX = "spontaneous:"
#: Un contact trouvé reste valable ce temps-là (partagé entre candidats).
CONTACT_TTL = timedelta(days=90)
#: Une entreprise déjà sollicitée par ce candidat ne l'est pas de nouveau avant.
RECONTACT_AFTER = timedelta(days=180)
#: Score affiché : une spontanée n'est pas notée contre une annonce.
SPONTANEOUS_SCORE = 75

FAMILY_LABELS = {
    "software": "Développement logiciel", "data": "Data", "product": "Produit",
    "design": "Design", "marketing": "Marketing", "sales": "Commercial",
    "support": "Support", "hr": "Ressources humaines", "finance": "Finance et comptabilité",
    "legal": "Juridique", "ops": "Opérations et logistique", "engineering": "Ingénierie",
    "health": "Santé",
}


def is_spontaneous(job: JobPosting | None) -> bool:
    return bool(job and (job.external_id or "").startswith(SPONTANEOUS_PREFIX))


def _slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60] or "candidature"


async def is_opted_out(session, email: str) -> bool:
    email = (email or "").lower()
    domain = "@" + email.rsplit("@", 1)[-1]
    return (await session.execute(
        select(EmailOptout.id).where(EmailOptout.value.in_([email, domain]))
    )).first() is not None


async def _company_for(session, target) -> Company:
    company = (await session.execute(
        select(Company).where(Company.siren == target.siren)
    )).scalars().first()
    if company:
        return company
    company = Company(
        name=target.name[:300], domain=f"siren-{target.siren}.annuaire.local",
        slug=_slug(target.name), siren=target.siren, naf_code=target.naf,
        location_hq=target.city, ats_type=ATSType.UNKNOWN,
        status=CompanyStatus.NO_CAREER_PAGE, seed_source=SeedSource.SIRENE_API, is_active=True,
    )
    session.add(company)
    await session.flush()
    return company


async def _ensure_contact(company: Company) -> None:
    """Site vérifié + adresse publiée, au plus une fois tous les 90 jours."""
    from app.agents.spontaneous.contacts import find_website, scan_site

    now = datetime.now(timezone.utc)
    checked = company.contact_checked_at
    if checked and checked.tzinfo is None:
        checked = checked.replace(tzinfo=timezone.utc)
    if checked and now - checked < CONTACT_TTL:
        return
    website = company.website
    if not website and not company.domain.endswith(".local"):
        website = f"https://{company.domain}"
    if not website:
        website = await find_website(company.name, company.siren or "", company.location_hq)
    findings = await scan_site(website, company.name) if website else None
    company.contact_checked_at = now
    if findings:
        company.website = findings.website
        company.about = findings.summary or company.about
        if findings.contact:
            company.careers_email = findings.contact.email
            company.careers_email_source = findings.contact.source_url
            company.careers_email_kind = findings.contact.kind


async def prepare_spontaneous(candidate_id: UUID, wanted: int) -> list[tuple]:
    """
    Trouve jusqu'à `wanted` entreprises joignables et crée les candidatures.
    Renvoie [(application, posting, nom de l'entreprise)], prêtes pour le
    circuit habituel (dossier puis envoi). Ne lève pas.
    """
    from app.agents.discovery.deduplicator import compute_fingerprint
    from app.agents.discovery.signals import detect_job_family
    from app.agents.spontaneous.directory import NAF_BY_FAMILY, find_targets
    from app.schemas.matching import MatchingCriteria

    wanted = max(0, min(wanted, settings.spontaneous_per_run_max))
    if not wanted:
        return []

    async with async_session() as session:
        candidate = await session.get(Candidate, candidate_id)
        if not candidate:
            return []
        criteria = MatchingCriteria.resolve(candidate)
        families = list(criteria.job_families) or [detect_job_family(candidate.headline, list(candidate.skills or []))]
        families = [f for f in families if f in NAF_BY_FAMILY]
        cities = list(criteria.locations or candidate.preferred_locations or [])
        role = (candidate.headline or "").strip() or FAMILY_LABELS.get(families[0] if families else "", "")
        contract = next(iter(criteria.contract_types or []), None)

        # Déjà sollicitées par ce candidat récemment : on ne réécrit pas.
        since = datetime.now(timezone.utc) - RECONTACT_AFTER
        contacted = set((await session.execute(
            select(JobPosting.company_id)
            .join(Application, Application.job_posting_id == JobPosting.id)
            .where(Application.candidate_id == candidate_id)
            .where(JobPosting.external_id.like(f"{SPONTANEOUS_PREFIX}%"))
            .where(Application.created_at >= since)
        )).scalars().all())

    if not families:
        logger.info("Spontanées : métier inconnu pour %s, rien à cibler.", candidate_id)
        return []

    targets = await find_targets(families, cities, limit=wanted * 6)
    out: list[tuple] = []
    attempts = 0
    for target in targets:
        if len(out) >= wanted or attempts >= wanted * 5:
            break
        async with async_session() as session:
            company = await _company_for(session, target)
            if company.id in contacted:
                continue
            attempts += 1
            try:
                await _ensure_contact(company)
            except Exception as e:  # noqa: BLE001 — une entreprise ratée n'arrête pas les autres
                logger.info("Contact introuvable pour %s : %s", company.name, e)
            await session.commit()
            email = company.careers_email
            if not email or await is_opted_out(session, email):
                continue

            title = f"Candidature spontanée — {role}"[:500] if role else "Candidature spontanée"
            external_id = f"{SPONTANEOUS_PREFIX}{company.id}:{_slug(role)}"
            posting = (await session.execute(
                select(JobPosting).where(JobPosting.external_id == external_id)
            )).scalars().first()
            if not posting:
                posting = JobPosting(
                    company_id=company.id,
                    external_id=external_id,
                    fingerprint=compute_fingerprint(company.domain, title, company.location_hq,
                                                    external_id=external_id),
                    title=title,
                    description_raw=(
                        "Candidature spontanée : aucune offre n'est publiée. "
                        f"Ce que l'entreprise dit d'elle-même : {company.about or company.name}"
                    ),
                    location=company.location_hq,
                    source_url=company.careers_email_source or company.website or "",
                    apply_channel=ApplyChannel.EMAIL,
                    apply_complexity=ApplyComplexity.SIMPLE,
                    contract_type=ContractType(contract) if contract in ContractType._value2member_map_ else ContractType.UNKNOWN,
                    status=PostingStatus.ACTIVE,
                )
                session.add(posting)
                await session.flush()
            posting.contact_json = {
                "email": email, "source_url": company.careers_email_source,
                "kind": company.careers_email_kind, "spontaneous": True,
            }
            application = (await session.execute(
                select(Application).where(Application.candidate_id == candidate_id)
                .where(Application.job_posting_id == posting.id)
            )).scalars().first()
            if not application:
                application = Application(
                    candidate_id=candidate_id, job_posting_id=posting.id,
                    status=ApplicationStatus.MATCHED, match_score=SPONTANEOUS_SCORE,
                    metadata_json={
                        "spontaneous": True,
                        "match": {"reasons": [
                            f"entreprise du secteur ({target.naf})" if target.naf else "entreprise du secteur",
                            f"à {target.city}" if target.city else "",
                            "adresse de recrutement publiée sur son site"
                            if company.careers_email_kind == "recrutement" else "adresse de contact publiée sur son site",
                        ]},
                    },
                )
                session.add(application)
            await session.commit()
            await session.refresh(application)
            out.append((application, posting, company.name))
            contacted.add(company.id)
    logger.info("Spontanées : %d entreprise(s) joignable(s) sur %d essayée(s).", len(out), attempts)
    return out
