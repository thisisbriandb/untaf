"""
Après la candidature — le suivi jusqu'à la réponse.

Une candidature envoyée n'est pas une candidature finie. Sans réponse au bout
d'une semaine, une relance courte double à peu près les chances d'en obtenir
une ; c'est aussi le geste que les candidats oublient le plus. Alice le repère,
le rédige, et le propose — elle ne l'envoie pas d'elle-même : écrire une
seconde fois à un recruteur engage davantage le candidat que la première.

État rangé sur la candidature (`metadata_json`) :
  - `timeline` : chaque changement de statut, daté ;
  - `followup` : {status: drafted|sent|dismissed, subject, body, to, ...}.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.models.application import Application, ApplicationStatus
from app.models.company import Company
from app.models.dispatch import ApplicationDispatch, DispatchChannel, DispatchStatus
from app.models.job_posting import JobPosting

logger = logging.getLogger(__name__)

#: Statuts où le recruteur a répondu : plus rien à relancer.
ANSWERED = {
    ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER,
    ApplicationStatus.REJECTED, ApplicationStatus.CLOSED,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def record_status(application: Application, status: ApplicationStatus, note: str | None = None) -> None:
    """Change le statut en gardant la trace datée du changement."""
    meta = dict(application.metadata_json or {})
    timeline = list(meta.get("timeline") or [])
    entry = {"status": status.value, "at": _now().isoformat()}
    if note:
        entry["note"] = note[:300]
    timeline.append(entry)
    meta["timeline"] = timeline[-30:]
    application.metadata_json = meta
    application.status = status
    if status == ApplicationStatus.APPLIED and not application.applied_at:
        application.applied_at = _now()


def days_since(moment: datetime | None) -> int | None:
    if not moment:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return max(0, (_now() - moment).days)


def followup_state(application: Application) -> dict:
    """
    Où en est la relance de cette candidature.

    `due` est vrai quand la candidature est partie depuis assez longtemps, sans
    réponse consignée, et que la relance n'a été ni envoyée ni écartée.
    """
    meta = application.metadata_json or {}
    followup = meta.get("followup") or {}
    days = days_since(application.applied_at)
    due = (
        application.status == ApplicationStatus.APPLIED
        and days is not None
        and days >= settings.followup_after_days
        and followup.get("status") not in ("sent", "dismissed")
    )
    return {
        "due": due,
        "days_since_applied": days,
        "status": followup.get("status"),
        "subject": followup.get("subject"),
        "body": followup.get("body"),
        "to": followup.get("to"),
        "sent_at": followup.get("sent_at"),
    }


def _template(full_name: str, job_title: str, company: str, applied_at: datetime | None) -> tuple[str, str]:
    when = f"le {applied_at:%d/%m}" if applied_at else "récemment"
    subject = f"Relance — candidature {job_title}"
    body = (
        "Bonjour,\n\n"
        f"Je me permets de revenir vers vous au sujet de ma candidature au poste de "
        f"{job_title}, envoyée {when}. Le poste m'intéresse toujours vivement et je "
        f"reste à votre disposition pour un échange, à votre convenance.\n\n"
        f"Vous trouverez à nouveau mon CV en pièce jointe si besoin.\n\n"
        f"Bien cordialement,\n{full_name}"
    )
    return subject, body


async def draft_followup(candidate, application: Application, job_title: str,
                         company: str, letter_excerpt: str = "") -> dict:
    """
    Rédige la relance. Courte, polie, propre à l'offre — le modèle n'est
    qu'un raffinement : sans lui, le gabarit reste parfaitement envoyable.
    """
    subject, body = _template(candidate.full_name or "", job_title, company, application.applied_at)

    if settings.gemini_api_key:
        try:
            from app import llm
            from app.agents.persona import IDENTITY

            text = await llm.generate(
                f"""{IDENTITY}

Rédige, au nom du candidat {candidate.full_name or ''}, un e-mail de relance
pour une candidature restée sans réponse.

Poste : {job_title}
Entreprise : {company}
Candidature envoyée il y a {days_since(application.applied_at) or 0} jours.
Extrait de la lettre envoyée (pour rester cohérent, sans la répéter) :
{letter_excerpt[:800]}

Contraintes : 70 à 110 mots, vouvoiement, ton professionnel et chaleureux,
aucune insistance ni reproche, un seul argument concret tiré de la lettre,
proposer un échange. Termine par « Bien cordialement, » puis le nom.
Rends uniquement le corps du message, sans objet ni balisage."""
            )
            if text and len(text.strip()) > 60:
                body = text.strip()
        except Exception as e:  # noqa: BLE001 — le gabarit suffit
            logger.warning("Relance rédigée sans modèle : %s", e)

    return {"subject": subject, "body": body}


async def due_followups(session, candidate_id: UUID) -> list[dict]:
    """Les candidatures à relancer aujourd'hui, avec de quoi les présenter."""
    threshold = _now() - timedelta(days=settings.followup_after_days)
    rows = (await session.execute(
        select(Application, JobPosting.title, Company.name)
        .join(JobPosting, Application.job_posting_id == JobPosting.id)
        .join(Company, JobPosting.company_id == Company.id)
        .where(Application.candidate_id == candidate_id)
        .where(Application.status == ApplicationStatus.APPLIED)
        .where(Application.applied_at.is_not(None))
        .where(Application.applied_at <= threshold)
    )).all()

    due = []
    for application, title, company in rows:
        state = followup_state(application)
        if state["due"]:
            due.append({
                "application_id": str(application.id),
                "job_title": title,
                "company_name": company or "",
                "days": state["days_since_applied"],
            })
    return due


async def recipient_for(session, application_id: UUID) -> str | None:
    """L'adresse à relancer : celle où la candidature est réellement partie."""
    dispatch = (await session.execute(
        select(ApplicationDispatch)
        .where(ApplicationDispatch.application_id == application_id)
        .where(ApplicationDispatch.status == DispatchStatus.SENT)
        .order_by(ApplicationDispatch.sent_at.desc())
    )).scalars().first()
    if dispatch and dispatch.channel == DispatchChannel.EMAIL:
        return dispatch.destination
    return None
