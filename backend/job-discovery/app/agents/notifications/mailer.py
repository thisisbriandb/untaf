"""
Acheminement de tous les e-mails : candidatures, notifications, liens de
connexion, alertes.

Un seul transport pour tout ce qui part, pour qu'il n'y ait qu'un endroit où
la délivrabilité se joue, sur le domaine vérifié (alice-agent.fr) : Scaleway
Transactional Email s'il est configuré (API HTTPS, facturé à l'usage), sinon
Resend, avec le SMTP comme dernier repli (bloqué par Railway hors offre Pro). Sans l'un ni l'autre, rien ne part et le résultat
le dit — ne jamais prétendre avoir envoyé.

Ne lève jamais. Renvoie `{ok, real, provider, error?, id?}`.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
SCALEWAY_URL = "https://api.scaleway.com/transactional-email/v1alpha1/regions/{region}/emails"


@dataclass
class Attachment:
    filename: str
    content: bytes
    mime: str = "application/pdf"


@dataclass
class Mail:
    to: str
    subject: str
    text: str
    html: str | None = None
    #: (nom affiché, adresse). L'adresse doit appartenir au domaine vérifié.
    sender: tuple[str, str] | None = None
    reply_to: str | None = None
    attachments: list[Attachment] = field(default_factory=list)


def _default_sender() -> tuple[str, str]:
    return settings.notify_from_name, settings.notify_sender


async def _via_resend(mail: Mail) -> dict:
    name, address = mail.sender or _default_sender()
    payload: dict = {
        "from": formataddr((name, address)),
        "to": [mail.to],
        "subject": mail.subject,
        "text": mail.text,
    }
    if mail.html:
        payload["html"] = mail.html
    if mail.reply_to:
        payload["reply_to"] = mail.reply_to
    if mail.attachments:
        payload["attachments"] = [
            {"filename": a.filename, "content": base64.b64encode(a.content).decode()}
            for a in mail.attachments
        ]
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json=payload,
            )
        if response.status_code >= 400:
            return {"ok": False, "real": False, "provider": "resend",
                    "error": f"Resend {response.status_code} : {response.text[:200]}"}
        return {"ok": True, "real": True, "provider": "resend",
                "id": (response.json() or {}).get("id")}
    except Exception as e:  # noqa: BLE001
        logger.error("Resend injoignable : %s", e)
        return {"ok": False, "real": False, "provider": "resend", "error": str(e)[:200]}


async def _via_scaleway(mail: Mail) -> dict:
    name, address = mail.sender or _default_sender()
    payload: dict = {
        "from": {"email": address, "name": name},
        "to": [{"email": mail.to}],
        "subject": mail.subject,
        "text": mail.text,
        "html": mail.html or "",
        "project_id": settings.scaleway_project_id,
    }
    if mail.reply_to:
        payload["additional_headers"] = [{"key": "Reply-To", "value": mail.reply_to}]
    if mail.attachments:
        payload["attachments"] = [
            {"name": a.filename, "type": a.mime, "content": base64.b64encode(a.content).decode()}
            for a in mail.attachments
        ]
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                SCALEWAY_URL.format(region=settings.scaleway_region),
                headers={"X-Auth-Token": settings.scaleway_tem_secret_key},
                json=payload,
            )
        if response.status_code >= 400:
            return {"ok": False, "real": False, "provider": "scaleway",
                    "error": f"Scaleway {response.status_code} : {response.text[:200]}"}
        emails = (response.json() or {}).get("emails") or [{}]
        return {"ok": True, "real": True, "provider": "scaleway", "id": emails[0].get("id")}
    except Exception as e:  # noqa: BLE001
        logger.error("Scaleway injoignable : %s", e)
        return {"ok": False, "real": False, "provider": "scaleway", "error": str(e)[:200]}


def _smtp_send(mail: Mail) -> dict:
    name, _ = mail.sender or _default_sender()
    message = EmailMessage()
    message["Subject"] = mail.subject
    message["To"] = mail.to
    # Boîte classique (Gmail…) : l'expéditeur est la boîte connectée. Relais
    # (SES, Scaleway…) dont l'identifiant n'est pas une adresse : l'expéditeur
    # est celui du domaine vérifié.
    _, address = mail.sender or _default_sender()
    message["From"] = formataddr((name, settings.smtp_user if "@" in settings.smtp_user else address))
    message["Message-ID"] = make_msgid()
    if mail.reply_to:
        message["Reply-To"] = mail.reply_to
    message.set_content(mail.text)
    if mail.html:
        message.add_alternative(mail.html, subtype="html")
    for a in mail.attachments:
        maintype, _, subtype = a.mime.partition("/")
        message.add_attachment(a.content, maintype=maintype, subtype=subtype or "octet-stream",
                               filename=a.filename)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_use_tls:
                server.starttls(context=ssl.create_default_context())
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
        return {"ok": True, "real": True, "provider": "smtp", "id": message["Message-ID"]}
    except Exception as e:  # noqa: BLE001
        logger.error("Envoi SMTP vers %s échoué : %s", mail.to, e)
        return {"ok": False, "real": False, "provider": "smtp", "error": str(e)[:200]}


async def send_mail(mail: Mail) -> dict:
    """Envoie par le meilleur transport disponible, ou simule en le disant."""
    if not mail.to:
        return {"ok": False, "real": False, "provider": None, "error": "aucun destinataire"}
    if settings.scaleway_configured:
        return await _via_scaleway(mail)
    if settings.resend_api_key:
        return await _via_resend(mail)
    if settings.smtp_configured:
        # smtplib est bloquant : hors de la boucle d'événements.
        return await asyncio.to_thread(_smtp_send, mail)
    logger.info("E-mail « %s » vers %s non envoyé (aucun transport).", mail.subject, mail.to)
    return {"ok": True, "real": False, "provider": None,
            "error": "aucun service d'envoi configuré"}


async def deliver(to: str, subject: str, html: str, text: str) -> dict:
    """Notification au candidat — expéditeur Alice."""
    return await send_mail(Mail(to=to, subject=subject, text=text, html=html))
