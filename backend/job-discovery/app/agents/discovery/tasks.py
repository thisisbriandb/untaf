"""
Discovery Celery tasks — daily job scraping for all resolved companies.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.celery_app import celery_app
from app.database import async_session, engine
from app.models.company import Company, ATSType, CompanyStatus
from app.models.job_posting import (
    JobPosting, ApplyChannel, ApplyComplexity, PostingStatus,
    RemotePolicy, ContractType,
)
from app.models.candidate import Candidate
from app.models.application import Application, ApplicationStatus
from app.agents.discovery.scrapers.greenhouse import GreenhouseScraper
from app.agents.discovery.scrapers.lever import LeverScraper
from app.agents.discovery.scrapers.ashby import AshbyScraper
from app.agents.discovery.scrapers.base import ScrapedJob
from app.agents.discovery.deduplicator import compute_fingerprint
from app.agents.discovery.qualification import qualify_job_description
from app.agents.discovery.matching import evaluate_match
from app.agents.mission_log import get_or_create_mission, log_event, log_scan
from app.models.mission import MissionEventKind
from app.config import settings
from app.schemas.matching import MatchingCriteria

logger = logging.getLogger(__name__)

# Map ATS type → apply channel
ATS_TO_CHANNEL = {
    ATSType.GREENHOUSE: ApplyChannel.GREENHOUSE_API,
    ATSType.LEVER: ApplyChannel.LEVER_API,
    ATSType.WORKABLE: ApplyChannel.WORKABLE_API,
    ATSType.ASHBY: ApplyChannel.ASHBY_API,
}


def _release(loop: asyncio.AbstractEventLoop) -> None:
    """
    Ferme la boucle d'une tâche en rendant d'abord le pool SQLAlchemy.

    Les connexions du moteur restent attachées à la boucle qui les a ouvertes.
    Sans ce `dispose`, la tâche suivante exécutée par le même worker Celery
    hérite de connexions rattachées à une boucle déjà fermée et meurt sur
    « attached to a different loop » — le premier scrape passe, les suivants
    jamais.
    """
    try:
        loop.run_until_complete(engine.dispose())
    except Exception:  # noqa: BLE001 — ne pas masquer le résultat de la tâche
        logger.warning("Engine dispose failed", exc_info=True)
    finally:
        loop.close()


def _hires_in_france(location: str | None) -> bool:
    """
    Garde une offre d'un board international.

    Une localisation absente est conservée, contrairement à la règle qui
    prévaut au scoring où l'inconnu ne reçoit jamais de laissez-passer. Les
    asymétries sont inverses : ici, écarter à tort supprime définitivement une
    offre qu'on ne reverra pas, alors qu'au scoring un faux positif ne coûte
    qu'une ligne de plus à trier. Le matching tranchera ensuite.
    """
    from app.agents.discovery.board_registry import FRENCH_LOCATION

    if not location or not location.strip():
        return True
    return bool(FRENCH_LOCATION.search(location))


async def _persist_jobs(
    company_id,
    company_domain: str,
    scraped: list[ScrapedJob],
    apply_channel: ApplyChannel,
):
    """Persist scraped jobs to DB with dedup via fingerprint."""
    new_count = 0
    updated_count = 0

    async with async_session() as session:
        for job in scraped:
            fp = compute_fingerprint(company_domain, job.title, job.location)

            # Upsert: insert if new fingerprint, update last_seen if existing
            stmt = pg_insert(JobPosting).values(
                company_id=company_id,
                external_id=job.external_id,
                fingerprint=fp,
                title=job.title,
                description_raw=job.description_raw,
                location=job.location,
                department=job.department,
                source_url=job.source_url,
                apply_url=job.apply_url,
                apply_channel=apply_channel,
                apply_complexity=ApplyComplexity.SIMPLE,
                status=PostingStatus.ACTIVE,
            ).on_conflict_do_update(
                index_elements=["fingerprint"],
                set_={
                    "last_seen_at": datetime.now(timezone.utc),
                    "status": PostingStatus.ACTIVE,
                    "apply_url": job.apply_url,
                    "description_raw": job.description_raw,
                },
            ).returning(text("(xmax = 0) AS inserted"))

            result = await session.execute(stmt)
            row = result.first()
            if row is not None and row[0]:
                new_count += 1
            else:
                updated_count += 1

        # Update company's last_scraped_at
        await session.execute(
            update(Company)
            .where(Company.id == company_id)
            .values(last_scraped_at=datetime.now(timezone.utc))
        )

        await session.commit()

    return new_count


async def _scrape_platform(ats_type: ATSType):
    """Scrape all companies of a given ATS type."""
    scraper_map = {
        ATSType.GREENHOUSE: GreenhouseScraper(),
        ATSType.LEVER: LeverScraper(),
        ATSType.ASHBY: AshbyScraper(),
    }

    scraper = scraper_map.get(ats_type)
    if not scraper:
        logger.warning("No scraper for ATS type: %s", ats_type.value)
        return 0

    async with async_session() as session:
        result = await session.execute(
            select(Company.id, Company.domain, Company.ats_slug)
            .where(Company.ats_type == ats_type)
            .where(Company.status == CompanyStatus.ATS_DIRECT)
            .where(Company.is_active.is_(True))
        )
        companies = result.all()

    logger.info(
        "Starting %s scrape for %d companies",
        ats_type.value, len(companies),
    )

    total_jobs = 0
    for company_id, domain, ats_slug in companies:
        slug = ats_slug or domain.split(".")[0]
        try:
            jobs = await scraper.scrape(slug)

            # Si l'API ne rend rien, on retombe sur Playwright — mais seulement
            # quand on connaît le vrai domaine de l'entreprise. Les boards
            # découverts via un index web portent un domaine synthétique
            # (`<slug>.greenhouse.board`) : lancer un navigateur dessus ne
            # ferait qu'ouvrir une URL inexistante, une fois par board mort.
            if not jobs and not domain.endswith(".board"):
                logger.info("⚡ API returned 0 jobs for %s. Injecting ScraperAgent fallback...", domain)
                from app.agents.discovery.scraper_agent import ScraperAgent
                agent = ScraperAgent()
                careers_url = f"https://www.{domain}/careers"
                res = await agent.run(domain.split(".")[0], careers_url)
                jobs = res.jobs

            # Un board est retenu parce qu'il recrute en France, pas parce que
            # tout son catalogue nous concerne : Capco publie 713 postes dont 8
            # ici. On filtre avant d'écrire, sinon 99 % des lignes stockées ne
            # seront jamais proposées à personne.
            jobs = [j for j in jobs if _hires_in_france(j.location)]

            if jobs:
                channel = ATS_TO_CHANNEL.get(ats_type, ApplyChannel.UNKNOWN)
                count = await _persist_jobs(company_id, domain, jobs, channel)
                total_jobs += count
                logger.info(
                    "%s/%s: %d jobs persisted", ats_type.value, slug, count
                )
        except Exception as e:
            logger.error(
                "Error scraping %s/%s: %s", ats_type.value, slug, e
            )

    return total_jobs


@celery_app.task(name="app.agents.discovery.tasks.scrape_all_greenhouse")
def scrape_all_greenhouse():
    """Daily task: scrape all Greenhouse companies."""
    loop = asyncio.new_event_loop()
    try:
        count = loop.run_until_complete(_scrape_platform(ATSType.GREENHOUSE))
        logger.info("Greenhouse daily scrape complete: %d jobs", count)
        return count
    finally:
        _release(loop)


@celery_app.task(name="app.agents.discovery.tasks.scrape_all_lever")
def scrape_all_lever():
    """Daily task: scrape all Lever companies."""
    loop = asyncio.new_event_loop()
    try:
        count = loop.run_until_complete(_scrape_platform(ATSType.LEVER))
        logger.info("Lever daily scrape complete: %d jobs", count)
        return count
    finally:
        _release(loop)


@celery_app.task(name="app.agents.discovery.tasks.scrape_all_ashby")
def scrape_all_ashby():
    """Daily task: scrape all Ashby companies."""
    loop = asyncio.new_event_loop()
    try:
        count = loop.run_until_complete(_scrape_platform(ATSType.ASHBY))
        logger.info("Ashby daily scrape complete: %d jobs", count)
        return count
    finally:
        _release(loop)


@celery_app.task(name="app.agents.discovery.tasks.ingest_france_travail_daily")
def ingest_france_travail_daily(keywords: str | None = None):
    """Tâche quotidienne : ingestion des offres France Travail."""
    from app.agents.discovery.france_travail_task import ingest_france_travail

    loop = asyncio.new_event_loop()
    try:
        report = loop.run_until_complete(
            ingest_france_travail(keywords=keywords, max_results=1500)
        )
        logger.info("France Travail daily ingest: %s", report)
        return report
    finally:
        _release(loop)


@celery_app.task(name="app.agents.discovery.tasks.scrape_company")
def scrape_company(company_id: str, domain: str, ats_type: str, ats_slug: str):
    """On-demand task: scrape a single company."""
    loop = asyncio.new_event_loop()
    try:
        scraper_map = {
            "greenhouse": GreenhouseScraper(),
            "lever": LeverScraper(),
        }
        scraper = scraper_map.get(ats_type)
        if not scraper:
            return 0

        jobs = loop.run_until_complete(scraper.scrape(ats_slug))
        channel_map = {
            "greenhouse": ApplyChannel.GREENHOUSE_API,
            "lever": ApplyChannel.LEVER_API,
        }
        channel = channel_map.get(ats_type, ApplyChannel.UNKNOWN)
        count = loop.run_until_complete(
            _persist_jobs(company_id, domain, jobs, channel)
        )
        return count
    finally:
        _release(loop)


async def _qualify_and_match_all():
    """Qualify all job postings using LLM/heuristics, then compute candidate matching scores."""
    qualified_count = 0
    application_count = 0

    async with async_session() as session:
        # 1. Fetch active, unqualified jobs — company joined explicitly so the
        #    matcher never has to touch the lazy relationship from async code.
        jobs_result = await session.execute(
            select(JobPosting, Company.name)
            .join(Company, JobPosting.company_id == Company.id)
            .where(JobPosting.status == PostingStatus.ACTIVE)
            .where(JobPosting.description_parsed.is_(None))
        )
        job_rows = jobs_result.all()
        jobs = [row[0] for row in job_rows]
        company_names = {row[0].id: row[1] for row in job_rows}

        # 2. Fetch all candidates
        candidates_result = await session.execute(select(Candidate))
        candidates = candidates_result.scalars().all()

    if not jobs:
        logger.info("No new job postings to qualify.")
        return 0, 0

    logger.info("Qualifying %d job postings and matching with %d candidates", len(jobs), len(candidates))

    # Helper mapping for remote policy
    remote_map = {
        "remote": RemotePolicy.REMOTE,
        "hybrid": RemotePolicy.HYBRID,
        "onsite": RemotePolicy.ONSITE,
        "unknown": RemotePolicy.UNKNOWN,
    }

    # Helper mapping for contract type
    contract_map = {
        "cdi": ContractType.CDI,
        "cdd": ContractType.CDD,
        "freelance": ContractType.FREELANCE,
        "internship": ContractType.STAGE,
        "alternance": ContractType.ALTERNANCE,
        "other": ContractType.UNKNOWN,
    }

    for job in jobs:
        try:
            logger.info("Qualifying job: %s", job.title)
            parsed_data = await qualify_job_description(job.title, job.description_raw or "")
            
            # Map values
            remote_val = remote_map.get(parsed_data.get("remote_policy", "unknown"), RemotePolicy.UNKNOWN)
            contract_val = contract_map.get(parsed_data.get("contract_type", "other"), ContractType.UNKNOWN)
            
            # Salary range string
            sal_min = parsed_data.get("salary_min")
            sal_max = parsed_data.get("salary_max")
            sal_range = None
            if sal_min and sal_max:
                sal_range = f"{sal_min // 1000}k - {sal_max // 1000}k EUR"
            elif sal_min:
                sal_range = f"{sal_min // 1000}k+ EUR"
            elif sal_max:
                sal_range = f"Up to {sal_max // 1000}k EUR"

            # Exp range
            exp_yrs = parsed_data.get("experience_years_required")
            exp_range = f"{int(exp_yrs)}+ years" if exp_yrs is not None else None

            # Update job posting fields
            async with async_session() as session:
                await session.execute(
                    update(JobPosting)
                    .where(JobPosting.id == job.id)
                    .values(
                        description_parsed=parsed_data,
                        remote_policy=remote_val,
                        contract_type=contract_val,
                        tech_stack=parsed_data.get("tech_stack", []),
                        salary_range=sal_range,
                        experience_range=exp_range,
                    )
                )
                await session.commit()
            
            qualified_count += 1
            
            # Compute match score for each candidate and create applications
            highest_score = 0
            for candidate in candidates:
                result = evaluate_match(
                    candidate, job, parsed_data,
                    company_name=company_names.get(job.id, ""),
                )

                if not result.accepted:
                    logger.debug(
                        "Rejected '%s' for %s: %s",
                        job.title, candidate.id, "; ".join(result.rejections),
                    )
                    continue

                score = result.score
                highest_score = max(highest_score, score)

                if score >= settings.match_min_score:
                    async with async_session() as session:
                        stmt = pg_insert(Application).values(
                            candidate_id=candidate.id,
                            job_posting_id=job.id,
                            status=(
                                ApplicationStatus.MATCHED
                                if score >= settings.match_shortlist_score
                                else ApplicationStatus.PENDING
                            ),
                            match_score=score,
                            metadata_json={
                                "qualification": parsed_data,
                                "match": result.to_metadata(),
                                "matched_at": datetime.now(timezone.utc).isoformat(),
                            }
                        ).on_conflict_do_update(
                            index_elements=["candidate_id", "job_posting_id"],
                            set_={
                                "match_score": score,
                                "updated_at": datetime.now(timezone.utc),
                            }
                        )
                        await session.execute(stmt)
                        await session.commit()
                    application_count += 1

            # Update job posting with highest match score
            if highest_score > 0:
                async with async_session() as session:
                    await session.execute(
                        update(JobPosting)
                        .where(JobPosting.id == job.id)
                        .values(match_score=highest_score)
                    )
                    await session.commit()

        except Exception as e:
            logger.error("Error qualifying job posting %s: %s", job.id, e, exc_info=True)

    return qualified_count, application_count


@celery_app.task(name="app.agents.discovery.tasks.qualify_and_match_jobs")
def qualify_and_match_jobs():
    """Daily task or trigger: qualify job descriptions and match with candidates."""
    loop = asyncio.new_event_loop()
    try:
        q_count, a_count = loop.run_until_complete(_qualify_and_match_all())
        logger.info("Qualification and matching complete. Qualified: %d, Matches: %d", q_count, a_count)
        return {"qualified": q_count, "matches": a_count}
    finally:
        _release(loop)


#: Statuses the candidate (or a recruiter) has already acted on — a re-match
#: must never rewrite or delete those.
_LOCKED_STATUSES = {
    ApplicationStatus.APPLIED,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.OFFER,
    ApplicationStatus.REJECTED,
    ApplicationStatus.CLOSED,
}


async def _match_candidate_to_existing_jobs(candidate_id):
    """
    (Re)score a candidate against every active, qualified posting.

    Idempotent: a posting that no longer passes the mandate has its shortlist
    entry pruned, so tightening the criteria actually cleans the list instead
    of leaving stale matches behind. Applications already acted on are locked.
    """
    async with async_session() as session:
        candidate = await session.get(Candidate, candidate_id)
        if not candidate:
            logger.warning("Candidate %s not found for matching", candidate_id)
            return 0

        criteria = MatchingCriteria.resolve(candidate)

        # Company is joined explicitly: `JobPosting.company` is a lazy
        # relationship and touching it from here would raise MissingGreenlet.
        result = await session.execute(
            select(JobPosting, Company.name)
            .join(Company, JobPosting.company_id == Company.id)
            .where(JobPosting.status == PostingStatus.ACTIVE)
            .where(JobPosting.description_parsed.is_not(None))
        )
        rows = result.all()

        existing_result = await session.execute(
            select(Application).where(Application.candidate_id == candidate.id)
        )
        existing = {a.job_posting_id: a for a in existing_result.scalars().all()}

        logger.info(
            "Matching candidate %s (%s) against %d jobs",
            candidate.full_name, candidate.id, len(rows),
        )

        kept = 0
        pruned = 0
        rejected = 0
        seen: set = set()
        reasons: dict[str, int] = {}
        newly_shortlisted: list[tuple] = []

        for job, company_name in rows:
            seen.add(job.id)
            current = existing.get(job.id)

            try:
                match = evaluate_match(
                    candidate, job, job.description_parsed, criteria,
                    company_name=company_name,
                )
            except Exception as e:  # noqa: BLE001
                # One unscoreable posting must never abort the whole pass.
                logger.error("Match failed on job %s: %s", job.id, e, exc_info=True)
                continue

            passes = match.accepted and match.score >= settings.match_min_score

            if not passes:
                rejected += 1
                # Motif normalisé pour agréger le journal : on coupe la partie
                # explicative et la ponctuation résiduelle, on garde la valeur
                # (« contrat 'cdi' ») qui est justement l'information utile.
                motif = (
                    match.rejections[0].split(" :")[0].split(" hors")[0].rstrip(" ,.")
                    if match.rejections else "score insuffisant"
                )
                reasons[motif] = reasons.get(motif, 0) + 1
                if current and current.status not in _LOCKED_STATUSES:
                    await session.delete(current)
                    pruned += 1
                continue

            status = (
                ApplicationStatus.MATCHED
                if match.score >= settings.match_shortlist_score
                else ApplicationStatus.PENDING
            )
            metadata = {
                "qualification": job.description_parsed,
                "match": match.to_metadata(),
                "matched_at": datetime.now(timezone.utc).isoformat(),
            }

            if current is None:
                newly_shortlisted.append((match.score, job.title, company_name, job.id))
                session.add(Application(
                    candidate_id=candidate.id,
                    job_posting_id=job.id,
                    status=status,
                    match_score=match.score,
                    metadata_json=metadata,
                ))
            elif current.status not in _LOCKED_STATUSES:
                current.status = status
                current.match_score = match.score
                current.metadata_json = metadata
            else:
                # Keep the status, refresh the score so the UI stays honest.
                current.match_score = match.score

            kept += 1

        # Entries pointing at a posting that left the pool entirely — closed,
        # or never qualified so it is not in `rows`. Without this they survive
        # every re-match, because the loop above never visits them.
        for job_id, app in existing.items():
            if job_id in seen or app.status in _LOCKED_STATUSES:
                continue
            await session.delete(app)
            pruned += 1

        # ── Journal de mission ────────────────────────────
        # Une entrée de synthèse pour la passe, puis une par offre nouvellement
        # retenue : c'est le récit qu'Alice pourra restituer sans qu'on le lui
        # demande.
        await log_scan(
            session, candidate.id,
            scanned=len(rows), kept=kept, discarded=rejected,
            top_reasons=dict(sorted(reasons.items(), key=lambda kv: -kv[1])[:5]),
        )

        for score, title, company, job_id in sorted(newly_shortlisted, reverse=True)[:10]:
            await log_event(
                session, candidate.id, MissionEventKind.SHORTLIST,
                f"Retenu « {title} » chez {company} — {score}% de correspondance.",
                payload={"job_id": str(job_id), "score": score, "company": company},
            )

        mission = await get_or_create_mission(session, candidate.id)
        mission.last_run_at = datetime.now(timezone.utc)

        await session.commit()
        logger.info(
            "Matching complete for candidate %s — retenues: %d, écartées: %d, purgées: %d",
            candidate.id, kept, rejected, pruned,
        )
        return kept


@celery_app.task(name="app.agents.discovery.tasks.match_candidate_jobs")
def match_candidate_jobs(candidate_id_str: str):
    """Celery task to match a single candidate against existing jobs."""
    from uuid import UUID
    loop = asyncio.new_event_loop()
    try:
        count = loop.run_until_complete(_match_candidate_to_existing_jobs(UUID(candidate_id_str)))
        return {"matches": count}
    finally:
        _release(loop)



@celery_app.task(name="app.agents.discovery.tasks.discover_ats_boards")
def discover_ats_boards(platforms: list[str] | None = None, max_pages: int = 6):
    """
    Hebdomadaire : rafraîchit le registre des boards ATS à scraper.

    Purement additif — un board déjà connu n'est jamais écrasé, et un échec
    de l'index web laisse le registre existant intact.
    """
    from app.agents.discovery.board_registry import discover

    loop = asyncio.new_event_loop()
    try:
        report = loop.run_until_complete(discover(platforms, max_pages=max_pages))
        logger.info("ATS board discovery: %s", report)
        return report
    finally:
        _release(loop)


# `ignore_result` : l'état d'une mission vit dans `mission_runs`, pas dans
# Redis. Sans ça, chaque enfilement interroge le magasin de résultats et
# fait attendre l'API quand il est absent.
@celery_app.task(name="app.agents.discovery.tasks.run_mission", ignore_result=True)
def run_mission(run_id: str, candidate_id: str):
    """
    Exécute une mission dans un worker, et non dans le process web.

    C'est la différence entre « la mission continue tant que le serveur
    tourne » et une vraie délégation : un redéploiement de l'API ne doit pas
    tuer le travail confié à Alice.
    """
    from uuid import UUID
    from app.agents.mission_runner import execute_run

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(execute_run(UUID(run_id), UUID(candidate_id)))
    finally:
        _release(loop)


@celery_app.task(name="app.agents.discovery.tasks.sweep_stale_missions")
def sweep_stale_missions():
    """Clôt périodiquement les missions dont le worker ne donne plus signe."""
    from app.agents.mission_runner import sweep_stale_runs

    loop = asyncio.new_event_loop()
    try:
        closed = loop.run_until_complete(sweep_stale_runs())
        return {"closed": closed}
    finally:
        _release(loop)
