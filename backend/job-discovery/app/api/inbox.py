"""
Réponses des recruteurs : réception (webhooks) et lecture (boîte du candidat).
"""

import json
import logging
from datetime import datetime, timezone
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.config import settings
from app.database import get_db
from app.models.application import Application, ApplicationStatus
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.inbound_email import InboundAttachment, InboundEmail
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
    application_id: UUID | None = None
    #: Rattachement incertain : le candidat dit à quelle candidature il répond.
    to_link: bool = False
    suggested_application_id: UUID | None = None
    attachments_count: int = 0


class AttachmentOut(BaseModel):
    id: UUID
    filename: str
    mime: str
    size: int


class SkippedAttachment(BaseModel):
    filename: str
    size: int = 0


class ReplyDetail(ReplyOut):
    text: str
    attachments: list[AttachmentOut] = []
    #: Trop lourdes pour être gardées : le nom seulement.
    skipped_attachments: list[SkippedAttachment] = []


class Choice(BaseModel):
    """Une candidature à laquelle rattacher un message."""
    application_id: UUID
    job_title: str
    company_name: str | None
    status: str


class InboxOut(BaseModel):
    #: L'adresse donnée aux recruteurs ; None tant que la réception n'est pas configurée.
    address: str | None
    configured: bool
    unread: int
    replies: list[ReplyOut]
    #: Les candidatures proposées pour rattacher un message (vide si rien n'attend).
    choices: list[Choice] = []


def _row_out(record: InboundEmail, job_id, title, company, detail: bool = False, attachments=None):
    from app.agents.company_name import display_company

    meta = record.meta or {}
    suggested = meta.get("suggested_application_id")
    data = dict(
        id=record.id, kind=record.kind, summary=record.summary, next_step=record.next_step,
        subject=record.subject, from_email=record.from_email, from_name=record.from_name,
        received_at=record.received_at, read=record.read_at is not None,
        job_id=job_id, job_title=title, company_name=display_company(company) if company else None,
        application_id=record.application_id,
        to_link=bool(meta.get("to_link")) and record.application_id is None,
        suggested_application_id=UUID(suggested) if suggested else None,
        attachments_count=len(meta.get("attachments") or []),
    )
    if not detail:
        return ReplyOut(**data)
    return ReplyDetail(
        **data, text=record.text,
        attachments=[AttachmentOut(id=a.id, filename=a.filename, mime=a.mime, size=a.size)
                     for a in attachments or []],
        skipped_attachments=[SkippedAttachment(**x) for x in meta.get("skipped_attachments") or []
                             if isinstance(x, dict) and x.get("filename")],
    )


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
    replies = [_row_out(*r) for r in rows]
    choices: list[Choice] = []
    if any(r.to_link for r in replies):
        choices = await _choices(db, candidate_id)
    return InboxOut(
        address=address, configured=settings.inbound_configured, unread=unread,
        replies=replies, choices=choices,
    )


async def _choices(db: AsyncSession, candidate_id: UUID) -> list[Choice]:
    from app.agents.company_name import display_company

    rows = (await db.execute(
        select(Application.id, JobPosting.title, Company.name, Application.status)
        .join(JobPosting, Application.job_posting_id == JobPosting.id)
        .join(Company, JobPosting.company_id == Company.id)
        .where(Application.candidate_id == candidate_id)
        .where(Application.status.in_([
            ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER,
            ApplicationStatus.MATCHED, ApplicationStatus.REJECTED, ApplicationStatus.CLOSED,
        ]))
        .order_by(Application.applied_at.desc().nullslast())
        .limit(200)
    )).all()
    return [Choice(application_id=r[0], job_title=r[1] or "", company_name=display_company(r[2]) if r[2] else None,
                   status=r[3].value) for r in rows]


@router.get("/candidates/{candidate_id}/inbox/{reply_id}", response_model=ReplyDetail)
async def reply_detail(candidate_id: UUID, reply_id: UUID, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(_query(candidate_id).where(InboundEmail.id == reply_id))).first()
    if not row:
        raise HTTPException(404, "Message introuvable.")
    record = row[0]
    if record.read_at is None:
        record.read_at = datetime.now(timezone.utc)
        await db.commit()
    attachments = (await db.execute(
        select(InboundAttachment).where(InboundAttachment.inbound_email_id == record.id)
        .order_by(InboundAttachment.created_at)
        .options(defer(InboundAttachment.content))
    )).scalars().all()
    return _row_out(*row, detail=True, attachments=attachments)


class LinkIn(BaseModel):
    #: None : le message ne concerne aucune de ses candidatures.
    application_id: UUID | None = None


class LinkOut(BaseModel):
    reply: ReplyOut
    #: Le nouveau statut de la candidature, s'il a changé.
    status: str | None = None


@router.post("/candidates/{candidate_id}/inbox/{reply_id}/link", response_model=LinkOut)
async def link_reply(candidate_id: UUID, reply_id: UUID, data: LinkIn, db: AsyncSession = Depends(get_db)):
    """Le candidat dit à quelle candidature répond un message ; le suivi suit."""
    from app.agents import inbox as agent

    record = (await db.execute(
        select(InboundEmail).where(InboundEmail.id == reply_id, InboundEmail.candidate_id == candidate_id)
    )).scalar_one_or_none()
    if not record:
        raise HTTPException(404, "Message introuvable.")
    application = None
    if data.application_id:
        application = await db.get(Application, data.application_id)
        if not application or application.candidate_id != candidate_id:
            raise HTTPException(404, "Candidature introuvable.")
    status = await agent.link_reply(db, record, application)
    await db.commit()
    row = (await db.execute(_query(candidate_id).where(InboundEmail.id == reply_id))).first()
    return LinkOut(reply=_row_out(*row), status=status.value if status else None)


#: Types que le navigateur pourrait exécuter : servis comme fichier brut.
_UNSAFE_MIME = ("text/html", "image/svg+xml", "application/xhtml+xml", "text/xml", "application/xml",
                "text/javascript", "application/javascript")


@router.get("/candidates/{candidate_id}/inbox/{reply_id}/attachments/{attachment_id}")
async def download_attachment(candidate_id: UUID, reply_id: UUID, attachment_id: UUID,
                              db: AsyncSession = Depends(get_db)):
    """Une pièce jointe reçue d'un recruteur (la garde globale vérifie le propriétaire)."""
    piece = (await db.execute(
        select(InboundAttachment)
        .join(InboundEmail, InboundAttachment.inbound_email_id == InboundEmail.id)
        .where(InboundAttachment.id == attachment_id, InboundEmail.id == reply_id,
               InboundEmail.candidate_id == candidate_id)
    )).scalar_one_or_none()
    if not piece:
        raise HTTPException(404, "Pièce jointe introuvable.")
    mime = (piece.mime or "").lower()
    if not mime or mime.startswith(_UNSAFE_MIME):
        mime = "application/octet-stream"
    ascii_name = piece.filename.encode("ascii", "ignore").decode().replace('"', "") or "piece-jointe"
    return Response(
        content=piece.content, media_type=mime,
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(piece.filename)}",
            "X-Content-Type-Options": "nosniff",
        },
    )
