"""
Ingestion des offres France Travail.

Les offres ne viennent pas d'un site carrière : chaque employeur est créé à la
volée, sans domaine réel. On lui en fabrique un, stable et déterministe, pour
respecter la contrainte d'unicité de `Company.domain` sans jamais confondre
deux employeurs homonymes avec une vraie entreprise référencée.
"""

import logging
import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.agents.discovery.deduplicator import compute_fingerprint
from app.agents.discovery.france_travail import (
    ROME_BY_FAMILY, FranceTravailAuthError, FranceTravailClient, fetch_offers,
)
from app.agents.discovery.scrapers.base import ScrapedJob
from app.database import async_session
from app.models.company import ATSType, Company, CompanyStatus, SeedSource
from app.models.job_posting import (
    IMPORT_PREFIX, ApplyChannel, ApplyComplexity, ContractType, JobPosting,
    PostingStatus, RemotePolicy,
)

logger = logging.getLogger(__name__)

#: Suffixe réservé aux employeurs issus de France Travail. Il garantit qu'ils
#: n'entreront jamais en collision avec un domaine réel déjà en base.
FT_DOMAIN_SUFFIX = ".francetravail.local"

#: Employeur de repli : beaucoup d'offres sont publiées anonymement.
ANONYMOUS_NAME = "Employeur non précisé"


def _slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug[:60] or "anonyme"


async def _get_or_create_company(session, name: str) -> Company:
    """L'employeur, créé au premier besoin."""
    clean_name = (name or "").strip() or ANONYMOUS_NAME
    domain = f"{_slugify(clean_name)}{FT_DOMAIN_SUFFIX}"

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
        # Ces employeurs n'ont pas de site carrière à résoudre : les marquer
        # PENDING relancerait le résolveur ATS sur des domaines fictifs.
        status=CompanyStatus.NO_CAREER_PAGE,
        seed_source=SeedSource.MANUAL,
        is_active=True,
    )
    session.add(company)
    await session.flush()
    return company


async def _persist(jobs: list[ScrapedJob]) -> tuple[int, int]:
    """Enregistre les offres. Renvoie (traitées, employeurs créés)."""
    processed = 0
    companies_before: set[str] = set()

    async with async_session() as session:
        existing = (await session.execute(
            select(Company.domain).where(Company.domain.like(f"%{FT_DOMAIN_SUFFIX}"))
        )).scalars().all()
        companies_before = set(existing)

        for job in jobs:
            if not job.external_id:
                continue

            company = await _get_or_create_company(
                session, job.extra.get("company_name", "")
            )

            fingerprint = compute_fingerprint(company.domain, job.title, job.location)

            parsed = job.extra.get("parsed") or {}
            remote = {
                "remote": RemotePolicy.REMOTE, "hybrid": RemotePolicy.HYBRID,
                "onsite": RemotePolicy.ONSITE,
            }.get(parsed.get("remote_policy"), RemotePolicy.UNKNOWN)
            contract = {
                "cdi": ContractType.CDI, "cdd": ContractType.CDD,
                "freelance": ContractType.FREELANCE, "stage": ContractType.STAGE,
                "alternance": ContractType.ALTERNANCE, "interim": ContractType.INTERIM,
            }.get(parsed.get("contract_type"), ContractType.UNKNOWN)

            # Le canal reflète ce qui est réellement faisable, pas un défaut.
            contact = job.extra.get("contact") or {}
            if contact.get("email"):
                channel, complexity = ApplyChannel.EMAIL, ApplyComplexity.SIMPLE
            elif contact.get("apply_url"):
                channel, complexity = ApplyChannel.WEB_FORM, ApplyComplexity.MEDIUM
            else:
                # Portail candidat France Travail : compte authentifié requis.
                channel, complexity = ApplyChannel.EXTERNAL_LINK, ApplyComplexity.COMPLEX

            stmt = pg_insert(JobPosting).values(
                company_id=company.id,
                external_id=job.external_id,
                fingerprint=fingerprint,
                title=job.title[:500],
                description_raw=job.description_raw,
                location=job.location,
                department=job.department,
                source_url=job.source_url or f"https://candidat.francetravail.fr/offres/recherche/detail/{job.external_id}",
                apply_url=job.apply_url,
                apply_channel=channel,
                apply_complexity=complexity,
                contact_json=contact or None,
                description_parsed=parsed or None,
                remote_policy=remote,
                contract_type=contract,
                tech_stack=parsed.get("tech_stack") or [],
                status=PostingStatus.ACTIVE,
            ).on_conflict_do_update(
                index_elements=["fingerprint"],
                set_={
                    "last_seen_at": datetime.now(timezone.utc),
                    "status": PostingStatus.ACTIVE,
                    "description_raw": job.description_raw,
                    "apply_url": job.apply_url,
                    "apply_channel": channel,
                    "apply_complexity": complexity,
                    "contact_json": contact or None,
                    "description_parsed": parsed or None,
                    "remote_policy": remote,
                    "contract_type": contract,
                    "tech_stack": parsed.get("tech_stack") or [],
                },
            )
            await session.execute(stmt)
            processed += 1

        after = (await session.execute(
            select(Company.domain).where(Company.domain.like(f"%{FT_DOMAIN_SUFFIX}"))
        )).scalars().all()

        await session.commit()

    return processed, len(set(after) - companies_before)


async def ingest_france_travail(
    *,
    rome_codes: list[str] | None = None,
    keywords: str | None = None,
    extra_params: dict | None = None,
    departements: list[str] | None = None,
    contract_types: list[str] | None = None,
    max_results: int = 1000,
) -> dict:
    """
    Récupère et enregistre les offres. Ne lève pas : renvoie un rapport.

    Les erreurs d'authentification sont distinguées du reste — elles demandent
    une action sur le compte France Travail, pas une nouvelle tentative.
    """
    client = FranceTravailClient()
    if not client.configured:
        return {"ok": False, "reason": "credentials_missing", "processed": 0}

    try:
        jobs = await fetch_offers(
            rome_codes=rome_codes,
            keywords=keywords,
            extra_params=extra_params,
            departements=departements,
            contract_types=contract_types,
            max_results=max_results,
            client=client,
        )
    except FranceTravailAuthError as e:
        logger.error("France Travail auth failed: %s", e)
        return {"ok": False, "reason": "auth_failed", "detail": str(e), "processed": 0}
    except Exception as e:  # noqa: BLE001
        logger.error("France Travail ingest failed: %s", e, exc_info=True)
        return {"ok": False, "reason": "error", "detail": str(e), "processed": 0}

    processed, new_companies = await _persist(jobs)

    logger.info(
        "France Travail : %d offres enregistrées, %d employeurs créés",
        processed, new_companies,
    )
    return {
        "ok": True,
        "processed": processed,
        "fetched": len(jobs),
        "new_companies": new_companies,
    }


async def ingest_for_candidate(candidate_id) -> dict:
    """
    Ingestion pilotée par le mandat.

    Un seul balayage par codes ROME ne suffit pas : les stages et alternances
    sont minoritaires et se noient dans le tri par date. Un mandat qui les
    demande déclenche des requêtes dédiées — sans quoi le candidat cherche un
    stage et reçoit 900 CDI.
    """
    from app.models.candidate import Candidate
    from app.schemas.matching import MatchingCriteria

    async with async_session() as session:
        candidate = await session.get(Candidate, candidate_id)
        if not candidate:
            return {"ok": False, "reason": "candidate_not_found", "processed": 0}

    criteria = MatchingCriteria.resolve(candidate)

    rome_codes = [
        code
        for family in (criteria.job_families or [])
        for code in ROME_BY_FAMILY.get(family, [])
    ] or None

    wanted = {c.lower() for c in (criteria.contract_types or [])}
    plans: list[dict] = []

    # Le balayage large, sauf si le mandat ne vise que des contrats courts —
    # dans ce cas il ne ramènerait que du bruit.
    if not wanted or wanted - {"stage", "alternance"}:
        plans.append({"rome_codes": rome_codes, "max_results": 600})

    if "stage" in wanted:
        plans.append({"rome_codes": rome_codes, "extra_params": {"motsCles": "stage"},
                      "max_results": 150})
        plans.append({"keywords": "stage developpeur", "max_results": 150})
    if "alternance" in wanted:
        # E2 = contrat de professionnalisation / alternance.
        plans.append({"rome_codes": rome_codes, "extra_params": {"natureContrat": "E2"},
                      "max_results": 200})

    if not plans:
        plans.append({"rome_codes": rome_codes, "max_results": 600})

    total, fetched, companies = 0, 0, 0
    for plan in plans:
        report = await ingest_france_travail(
            contract_types=None,   # le tri fin revient au moteur de matching
            **plan,
        )
        if not report.get("ok"):
            return report
        total += report["processed"]
        fetched += report.get("fetched", 0)
        companies += report.get("new_companies", 0)

    return {
        "ok": True,
        "processed": total,
        "fetched": fetched,
        "new_companies": companies,
        "plans": len(plans),
    }


async def reclassify_contacts(batch: int = 500) -> dict:
    """
    Repasse le stock déjà collecté au crible de l'extraction de contacts.

    Les offres ingérées avant l'extraction élargie sont restées en `EMAIL`
    sans adresse valide (l'interface proposait un envoi impossible) ou en
    `EXTERNAL_LINK` alors qu'une adresse figurait dans la consigne ou la
    description. Idempotent : une offre déjà juste n'est pas modifiée.
    """
    from app.agents.discovery.contact_extract import (
        find_apply_email, find_apply_url, is_valid_email,
    )

    changed = {"to_email": 0, "to_web_form": 0, "to_external_link": 0}
    async with async_session() as session:
        jobs = (await session.execute(
            select(JobPosting)
            .where(JobPosting.status == PostingStatus.ACTIVE)
            .where(JobPosting.apply_channel.in_([
                ApplyChannel.EMAIL, ApplyChannel.EXTERNAL_LINK, ApplyChannel.UNKNOWN,
            ]))
            .limit(batch)
        )).scalars().all()

        for job in jobs:
            contact = dict(job.contact_json or {})
            current = contact.get("email")
            hints = " ".join(str(contact.get(k) or "") for k in ("instructions", "email"))
            email = (
                current if is_valid_email(current)
                else find_apply_email(hints) or find_apply_email(job.description_raw, min_score=2)
            )
            url = contact.get("apply_url") or find_apply_url(hints)

            if email:
                channel, complexity = ApplyChannel.EMAIL, ApplyComplexity.SIMPLE
            elif url:
                channel, complexity = ApplyChannel.WEB_FORM, ApplyComplexity.MEDIUM
            elif job.apply_channel != ApplyChannel.EMAIL:
                continue  # rien de neuf à en tirer
            elif job.external_id.startswith(IMPORT_PREFIX):
                # Offre collée sans aucun moyen de postuler : canal inconnu,
                # surtout pas « portail France Travail ».
                channel, complexity = ApplyChannel.UNKNOWN, ApplyComplexity.COMPLEX
            else:
                channel, complexity = ApplyChannel.EXTERNAL_LINK, ApplyComplexity.COMPLEX

            if channel == job.apply_channel and email == current:
                continue

            if email:
                contact["email"] = email
            else:
                contact.pop("email", None)
            if url:
                contact["apply_url"] = url
            job.contact_json = contact or None
            job.apply_channel = channel
            job.apply_complexity = complexity
            key = {
                ApplyChannel.EMAIL: "to_email",
                ApplyChannel.WEB_FORM: "to_web_form",
            }.get(channel, "to_external_link")  # UNKNOWN compté avec
            changed[key] += 1

        await session.commit()

    logger.info("Reclassement des contacts : %s", changed)
    return {"scanned": len(jobs), **changed}
