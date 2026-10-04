"""Conversations avec Alice : ouverture, fil, enregistrement des tours."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.database import async_session
from app.models.conversation import Conversation, ConversationMessage

#: Tours relus pour donner son contexte à Alice.
HISTORY_TURNS = 12


def _title(message: str) -> str:
    text = " ".join(message.split())
    return (text[:77] + "…") if len(text) > 80 else (text or "Conversation")


async def open_conversation(
    candidate_id: UUID, conversation_id: str | None, first_message: str,
    job_id: UUID | None = None,
) -> Conversation:
    """
    La conversation demandée si elle appartient au candidat ; sinon celle de
    l'offre (une seule par offre, pour ne pas éparpiller le fil) ; sinon une
    nouvelle.
    """
    async with async_session() as session:
        if conversation_id:
            try:
                conv = await session.get(Conversation, UUID(conversation_id))
            except ValueError:
                conv = None
            # Une conversation d'un autre candidat n'est jamais rouverte.
            if conv and conv.candidate_id == candidate_id:
                return conv
        title = _title(first_message)
        if job_id:
            from app.models.company import Company
            from app.models.job_posting import JobPosting

            existing = (await session.execute(
                select(Conversation)
                .where(Conversation.candidate_id == candidate_id)
                .where(Conversation.job_posting_id == job_id)
                .order_by(Conversation.updated_at.desc())
                .limit(1)
            )).scalar_one_or_none()
            if existing:
                return existing
            row = (await session.execute(
                select(JobPosting.title, Company.name)
                .join(Company, JobPosting.company_id == Company.id)
                .where(JobPosting.id == job_id)
            )).first()
            if row:
                title = _title(f"{row[1]} — {row[0]}")
            else:
                job_id = None
        conv = Conversation(candidate_id=candidate_id, title=title, job_posting_id=job_id)
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        return conv


async def history_for(conversation_id: UUID) -> list[dict]:
    async with async_session() as session:
        rows = (await session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(HISTORY_TURNS)
        )).scalars().all()
    return [{"sender": m.sender, "text": m.text} for m in reversed(rows)]


async def append_turn(conversation_id: UUID, user_text: str, reply: str, ui_blocks: list) -> None:
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        session.add(ConversationMessage(
            conversation_id=conversation_id, sender="user", text=user_text, created_at=now,
        ))
        session.add(ConversationMessage(
            conversation_id=conversation_id, sender="alice", text=reply,
            ui_blocks=ui_blocks or None,
            # Une microseconde après : l'ordre du fil ne dépend pas de l'horloge de la base.
            created_at=now.replace(microsecond=min(now.microsecond + 1, 999_999)),
        ))
        conv = await session.get(Conversation, conversation_id)
        if conv:
            conv.updated_at = now
        await session.commit()


async def job_context(conversation: Conversation, candidate_id: UUID) -> str | None:
    """
    Le contexte de l'offre dont parle la conversation : il est donné à Alice
    à chaque tour, pour qu'elle réponde sur CETTE offre sans qu'on la renomme.
    """
    if not conversation.job_posting_id:
        return None
    from app.agents.application.feasibility import APPLY_MODE_LABELS, apply_mode
    from app.agents.application.pack import is_pack_ready
    from app.models.application import Application
    from app.models.company import Company
    from app.models.job_posting import JobPosting

    async with async_session() as session:
        row = (await session.execute(
            select(JobPosting, Company.name)
            .join(Company, JobPosting.company_id == Company.id)
            .where(JobPosting.id == conversation.job_posting_id)
        )).first()
        if not row:
            return None
        job, company = row
        app = (await session.execute(
            select(Application)
            .where(Application.candidate_id == candidate_id)
            .where(Application.job_posting_id == job.id)
        )).scalar_one_or_none()

    return (
        "CETTE CONVERSATION PORTE SUR UNE OFFRE PRÉCISE — réponds à son sujet, "
        "et pour les outils qui demandent une offre, c'est celle-ci.\n"
        f"Offre : {job.title} chez {company} ({job.location or 'lieu non précisé'})\n"
        f"Correspondance : {app.match_score if app else '?'} %\n"
        f"Qui envoie : {APPLY_MODE_LABELS[apply_mode(job)]}\n"
        f"Dossier prêt : {'oui' if is_pack_ready(app) else 'non'}\n"
        f"Statut : {app.status.value if app else 'hors de sa liste'}\n"
        f"Extrait de l'annonce :\n{(job.description_raw or '')[:1500]}"
    )
