"""
Réponses des recruteurs : réception (webhooks) et lecture (boîte du candidat).
"""

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.inbound_email import InboundEmail
from app.models.job_posting import JobPosting

logger = logging.getLogger(__name__)
router = APIRouter(tags=["inbox"])


# ── Réception ──────────────────────────────────────────────────────────────


@router.post("/inbound/resend", status_code=204)
async def resend_webhook(request: Request):
    """Webhook Resend « email.received », signé (Svix)."""
    from app.agents.inbox import incoming_from_resend, process_incoming, verify_svix

    body = await request.body()
    if not settings.resend_webhook_secret:
        raise HTTPException(503, "Réception non configurée (RESEND_WEBHOOK_SECRET).")
    h = request.headers
    if not verify_svix(settings.resend_webhook_secret, h.get("svix-id", ""), h.get("svix-timestamp", ""),
                       body, h.get("svix-signature", "")):
        raise HTTPException(401, "Signature invalide.")
    try:
        event = json.loads(body)
    except ValueError:
        raise HTTPException(400, "Corps illisible.") from None
    msg = await incoming_from_resend(event)
    if msg:
        await process_incoming(msg)


@router.post("/inbound/email", status_code=204)
async def relay_webhook(request: Request):
    """Autre relais (Cloudflare Email Worker…) : JSON {from, to, subject, text, html, message_id}."""
    import hmac

    from app.agents.inbox import incoming_from_generic, process_incoming

    if not settings.inbound_secret:
        raise HTTPException(503, "Réception non configurée (INBOUND_SECRET).")
    if not hmac.compare_digest(request.headers.get("x-inbound-secret", ""), settings.inbound_secret):
        raise HTTPException(401, "Secret invalide.")
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(400, "Corps illisible.") from None
    msg = incoming_from_generic(payload if isinstance(payload, dict) else {})
    if not msg:
        raise HTTPException(422, "Expéditeur ou destinataire manquant.")
    await process_incoming(msg)


# ── La boîte du candidat ───────────────────────────────────────────────────


class ReplyOut(BaseModel):
    id: UUID
    kind: str
    summary: str
    next_step: str | None
    subject: str
    from_email: str
    from_name: str | None
    received_at: datetime
    read: bool
    job_id: UUID | None = None
    job_title: str | None = None
    company_name: str | None = None


class ReplyDetail(ReplyOut):
    text: str


class InboxOut(BaseModel):
    #: L'adresse donnée aux recruteurs ; None tant que la réception n'est pas configurée.
    address: str | None
    configured: bool
    unread: int
    replies: list[ReplyOut]


def _row_out(record: InboundEmail, job_id, title, company, detail: bool = False):
    from app.agents.company_name import display_company

    data = dict(
        id=record.id, kind=record.kind, summary=record.summary, next_step=record.next_step,
        subject=record.subject, from_email=record.from_email, from_name=record.from_name,
        received_at=record.received_at, read=record.read_at is not None,
        job_id=job_id, job_title=title, company_name=display_company(company) if company else None,
    )
    return ReplyDetail(**data, text=record.text) if detail else ReplyOut(**data)


def _query(candidate_id: UUID):
    return (
        select(InboundEmail, JobPosting.id, JobPosting.title, Company.name)
        .outerjoin(Application, InboundEmail.application_id == Application.id)
        .outerjoin(JobPosting, Application.job_posting_id == JobPosting.id)
        .outerjoin(Company, JobPosting.company_id == Company.id)
        .where(InboundEmail.candidate_id == candidate_id)
    )


@router.get("/candidates/{candidate_id}/inbox", response_model=InboxOut)
async def inbox(candidate_id: UUID, job_id: UUID | None = None, db: AsyncSession = Depends(get_db)):
    from app.agents.inbox import ensure_reply_address

    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Profil introuvable.")
    address = await ensure_reply_address(db, candidate)
    await db.commit()

    query = _query(candidate_id)
    if job_id:
        query = query.where(JobPosting.id == job_id)
    rows = (await db.execute(query.order_by(InboundEmail.received_at.desc()).limit(200))).all()
    unread = (await db.execute(
        select(func.count()).select_from(InboundEmail)
        .where(InboundEmail.candidate_id == candidate_id).where(InboundEmail.read_at.is_(None))
    )).scalar_one()
    return InboxOut(
        address=address, configured=settings.inbound_configured, unread=unread,
        replies=[_row_out(*r) for r in rows],
    )


@router.get("/candidates/{candidate_id}/inbox/{reply_id}", response_model=ReplyDetail)
async def reply_detail(candidate_id: UUID, reply_id: UUID, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(_query(candidate_id).where(InboundEmail.id == reply_id))).first()
    if not row:
        raise HTTPException(404, "Message introuvable.")
    record = row[0]
    if record.read_at is None:
        record.read_at = datetime.now(timezone.utc)
        await db.commit()
    return _row_out(*row, detail=True)
