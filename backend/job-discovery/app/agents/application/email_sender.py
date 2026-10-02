"""
Envoi d'une candidature par email.

Le canal le plus simple et le seul irréprochable : le candidat écrit à une
adresse que le recruteur a lui-même publiée. Ni scraping, ni contournement,
ni conditions d'utilisation à négocier.

Sans configuration SMTP, la fonction ne prétend pas avoir envoyé : elle renvoie
`real=False`, et l'appelant enregistre une simulation. Un envoi fictif rapporté
comme réel serait la pire trahison possible pour un agent qui agit au nom de
quelqu'un.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.config import settings

logger = logging.getLogger(__name__)


def _plain_text(letter: dict | None, candidate, job_title: str, company: str) -> str:
    """Corps de l'email — la lettre, remise en texte lisible."""
    if not letter:
        return (
            f"Madame, Monsieur,\n\n"
            f"Je vous adresse ma candidature pour le poste de {job_title} "
            f"au sein de {company}.\n\n"
            f"Vous trouverez mon CV en pièce jointe.\n\n"
            f"Cordialement,\n{candidate.full_name or ''}"
        )

    # Le corps est en Markdown : on retire le balisage plutôt que de l'envoyer
    # tel quel dans un email texte.
    body = (letter.get("body") or "")
    body = body.replace("**", "").replace("*   ", "- ").replace("* ", "- ")

    return "\n\n".join(filter(None, [
        letter.get("salutation") or "Madame, Monsieur,",
        body,
        letter.get("closing") or "",
        letter.get("signature_name") or candidate.full_name or "",
    ]))


async def send_application_email(
    *,
    to_email: str,
    candidate,
    letter: dict | None,
    job_title: str,
    company_name: str,
    resume: bytes | None = None,
    resume_name: str | None = None,
) -> dict:
    """
    Envoie la candidature. Ne lève jamais.

    Renvoie `{ok, real, proof?, error?}`. `real=False` signifie qu'aucun
    message n'est parti — le distinguer de `ok=False` compte : la préparation
    a réussi, seul l'acheminement manque.
    """
    if not to_email:
        return {"ok": False, "real": False, "error": "aucune adresse destinataire"}

    subject = (letter or {}).get("subject") or f"Candidature — {job_title}"
    body = _plain_text(letter, candidate, job_title, company_name)

    message = EmailMessage()
    message["Subject"] = subject
    message["To"] = to_email
    message["Message-ID"] = make_msgid()
    message["From"] = formataddr((
        candidate.full_name or settings.smtp_from_name,
        settings.smtp_user or "candidature@localhost",
    ))
    if candidate.email:
        message["Reply-To"] = candidate.email
    message.set_content(body)

    # Le CV joint est celui figé à la préparation de l'envoi — adapté à
    # l'offre le cas échéant. À défaut, il suit le choix de présentation du
    # candidat, pas seulement le fichier déposé à l'inscription.
    if resume:
        cv_bytes, cv_name, cv_origin = resume, resume_name or "CV.pdf", "prepared"
    else:
        from app.agents.application.cv_resolver import resolve_cv
        cv_bytes, cv_name, cv_origin = resolve_cv(candidate)
    if cv_bytes:
        message.add_attachment(
            cv_bytes, maintype="application", subtype="pdf", filename=cv_name,
        )

    if not settings.can_send_email:
        logger.warning(
            "SMTP non configuré — candidature vers %s NON envoyée (simulation).",
            to_email,
        )
        return {
            "ok": True,
            "real": False,
            "proof": {
                "simulated": True,
                "to": to_email,
                "subject": subject,
                "attachments": [cv_name] if cv_bytes else [],
                "cv_origin": cv_origin,
                "body_preview": body[:400],
            },
        }

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_use_tls:
                server.starttls(context=context)
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)

        logger.info("Candidature envoyée à %s (%s)", to_email, job_title)
        return {
            "ok": True,
            "real": True,
            "proof": {
                "message_id": message["Message-ID"],
                "to": to_email,
                "subject": subject,
                "attachments": [cv_name] if cv_bytes else [],
                "cv_origin": cv_origin,
            },
        }

    except Exception as e:  # noqa: BLE001
        logger.error("Envoi email vers %s échoué : %s", to_email, e, exc_info=True)
        return {"ok": False, "real": False, "error": str(e)[:300]}
