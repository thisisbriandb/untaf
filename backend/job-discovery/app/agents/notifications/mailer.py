"""
Acheminement des e-mails d'Alice vers le candidat.

Distinct de `application/email_sender.py` : là, le candidat écrit à un
recruteur, sous son nom. Ici, Alice écrit au candidat. Le transport est le
même souci — ne jamais prétendre avoir envoyé — avec un ordre de préférence
différent : un service transactionnel (Resend) délivre mieux qu'une boîte
SMTP personnelle, qui reste le repli.

Ne lève jamais. Renvoie `{ok, real, provider, error?, id?}`.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


def _sender() -> tuple[str, str]:
    address = settings.notify_from_email or settings.smtp_user or "alice@localhost"
    return settings.notify_from_name, address


async def _via_resend(to: str, subject: str, html: str, text: str) -> dict:
    name, address = _sender()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": formataddr((name, address)),
                    "to": [to],
                    "subject": subject,
                    "html": html,
                    "text": text,
                },
            )
        if response.status_code >= 400:
            return {"ok": False, "real": False, "provider": "resend",
                    "error": f"Resend {response.status_code} : {response.text[:200]}"}
        return {"ok": True, "real": True, "provider": "resend",
                "id": (response.json() or {}).get("id")}
    except Exception as e:  # noqa: BLE001
        logger.error("Resend injoignable : %s", e)
        return {"ok": False, "real": False, "provider": "resend", "error": str(e)[:200]}


def _smtp_send(to: str, subject: str, html: str, text: str) -> dict:
    name, address = _sender()
    message = EmailMessage()
    message["Subject"] = subject
    message["To"] = to
    message["From"] = formataddr((name, settings.smtp_user or address))
    message["Message-ID"] = make_msgid()
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_use_tls:
                server.starttls(context=ssl.create_default_context())
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
        return {"ok": True, "real": True, "provider": "smtp", "id": message["Message-ID"]}
    except Exception as e:  # noqa: BLE001
        logger.error("Notification SMTP vers %s échouée : %s", to, e)
        return {"ok": False, "real": False, "provider": "smtp", "error": str(e)[:200]}


async def deliver(to: str, subject: str, html: str, text: str) -> dict:
    """Envoie par le meilleur transport disponible, ou simule en le disant."""
    if not to:
        return {"ok": False, "real": False, "provider": None, "error": "aucun destinataire"}

    if settings.resend_api_key and settings.notify_from_email:
        return await _via_resend(to, subject, html, text)

    if settings.can_send_email:
        # smtplib est bloquant : hors de la boucle d'événements.
        return await asyncio.to_thread(_smtp_send, to, subject, html, text)

    logger.info("Notification « %s » vers %s non envoyée (aucun transport).", subject, to)
    return {"ok": True, "real": False, "provider": None,
            "error": "aucun service d'envoi configuré"}
