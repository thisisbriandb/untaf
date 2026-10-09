"""
API routes for Applications — manage matches and status tracking.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthUser, assert_owner, require_admin, require_user
from app.config import settings
from app.database import get_db
from app.models.application import Application, ApplicationStatus
from app.models.company import Company
from app.models.job_posting import JobPosting
from app.schemas.application import ApplicationOut, ApplicationDetail, ApplicationStatusUpdate
from app.schemas.job import JobPostingOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("/", response_model=list[ApplicationDetail])
async def list_applications(
    candidate_id: UUID | None = None,
    status: ApplicationStatus | None = None,
    min_score: int = Query(default=0, ge=0, le=100),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_user),
):
    """List matched applications with filters, sorted by match score desc."""
    # Sans authentification, la liste couvrait tous les candidats. On exige
    # désormais un candidat, et qu'il appartienne à l'appelant.
    if not settings.auth_bypassed:
        if not candidate_id:
            raise HTTPException(400, "candidate_id requis")
        await assert_owner(db, user, candidate_id)
    query = (
        select(Application, JobPosting, Company.name, Company.domain)
        .join(JobPosting, Application.job_posting_id == JobPosting.id)
        .join(Company, JobPosting.company_id == Company.id)
        .where(Application.match_score >= min_score)
        .order_by(desc(Application.match_score), desc(Application.created_at))
    )

    if candidate_id:
        query = query.where(Application.candidate_id == candidate_id)
    if status:
        query = query.where(Application.status == status)

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    
    applications = []
    for app, posting, company_name, company_domain in result.all():
        app_data = ApplicationDetail(**ApplicationOut.model_validate(app).model_dump())
        job_data = JobPostingOut.model_validate(posting)
        job_data.company_name = company_name
        job_data.company_domain = company_domain
        app_data.job_posting = job_data
        applications.append(app_data)
        
    return applications


@router.get("/{application_id}", response_model=ApplicationDetail)
async def get_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_user),
):
    """Get single application details."""
    query = (
        select(Application, JobPosting, Company.name, Company.domain)
        .join(JobPosting, Application.job_posting_id == JobPosting.id)
        .join(Company, JobPosting.company_id == Company.id)
        .where(Application.id == application_id)
    )
    result = await db.execute(query)
    row = result.first()
    if not row:
        raise HTTPException(404, "Application not found")
        
    app, posting, company_name, company_domain = row
    await assert_owner(db, user, app.candidate_id)
    app_data = ApplicationDetail(**ApplicationOut.model_validate(app).model_dump())
    job_data = JobPostingOut.model_validate(posting)
    job_data.company_name = company_name
    job_data.company_domain = company_domain
    app_data.job_posting = job_data
    return app_data


@router.patch("/{application_id}/status", response_model=ApplicationOut)
async def update_application_status(
    application_id: UUID,
    data: ApplicationStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_user),
):
    """Update status of a candidate match/application."""
    from app.agents.application.followup import ANSWERED, record_status
    from app.agents.mission_log import log_event
    from app.models.mission import MissionEventKind

    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "Application not found")
    await assert_owner(db, user, application.candidate_id)

    previous = application.status
    if data.status != previous:
        record_status(application, data.status, data.note)
        # Une réponse du recruteur est un fait marquant de la recherche : elle
        # rejoint le journal, et Alice peut en parler.
        if data.status in ANSWERED:
            row = (await db.execute(
                select(JobPosting.title, Company.name)
                .join(Company, JobPosting.company_id == Company.id)
                .where(JobPosting.id == application.job_posting_id)
            )).first()
            title, company = row if row else ("cette offre", "l'entreprise")
            label = {
                ApplicationStatus.INTERVIEW: "Entretien décroché",
                ApplicationStatus.OFFER: "Offre reçue",
                ApplicationStatus.REJECTED: "Réponse négative",
                ApplicationStatus.CLOSED: "Processus clos",
            }[data.status]
            await log_event(
                db, application.candidate_id, MissionEventKind.REPLY,
                f"{label} chez {company} pour « {title} ».",
                {"application_id": str(application.id), "status": data.status.value},
            )
    await db.commit()
    await db.refresh(application)
    return application


@router.post("/match", status_code=202, dependencies=[Depends(require_admin)])
async def trigger_qualification_and_matching():
    """Trigger the qualification and matching pipeline async (Celery)."""
    from app.agents.discovery.tasks import qualify_and_match_jobs
    task = qualify_and_match_jobs.delay()
    return {"task_id": task.id, "status": "qualification and matching started"}
