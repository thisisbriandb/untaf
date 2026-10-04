"""
Acheminement de tous les e-mails : candidatures, notifications, liens de
connexion, alertes.

Un seul transport pour tout ce qui part, pour qu'il n'y ait qu'un endroit où
la délivrabilité se joue : Resend sur le domaine vérifié (alice-agent.fr),
avec le SMTP comme repli. Sans l'un ni l'autre, rien ne part et le résultat
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


def _smtp_send(mail: Mail) -> dict:
    name, _ = mail.sender or _default_sender()
    message = EmailMessage()
    message["Subject"] = mail.subject
    message["To"] = mail.to
    # En SMTP, l'adresse d'expédition doit être celle de la boîte connectée.
    message["From"] = formataddr((name, settings.smtp_user))
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
