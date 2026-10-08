"""
Envoi d'une candidature par email.

Le canal le plus simple et le seul irréprochable : le candidat écrit à une
adresse que le recruteur a lui-même publiée. Ni scraping, ni contournement,
ni conditions d'utilisation à négocier.

Sans transport configuré (Resend ou SMTP), la fonction ne prétend pas avoir envoyé : elle renvoie
`real=False`, et l'appelant enregistre une simulation. Un envoi fictif rapporté
comme réel serait la pire trahison possible pour un agent qui agit au nom de
quelqu'un.
"""

import logging

from app.agents.application.identity import PLACEHOLDER_NAMES, real_name
from app.config import settings

logger = logging.getLogger(__name__)


def _signature(letter: dict | None, candidate) -> str:
    """Le nom qui signe : jamais « Candidat » ni aucun nom de remplacement."""
    signed = " ".join(((letter or {}).get("signature_name") or "").split())
    if signed and signed.lower() not in PLACEHOLDER_NAMES:
        return signed
    return real_name(candidate) or ""


def _plain_text(letter: dict | None, candidate, job_title: str, company: str) -> str:
    """Corps de l'email — la lettre, remise en texte lisible."""
    if not letter:
        return (
            f"Madame, Monsieur,\n\n"
            f"Je vous adresse ma candidature pour le poste de {job_title} "
            f"au sein de {company}.\n\n"
            f"Vous trouverez mon CV en pièce jointe.\n\n"
            f"Cordialement,\n{_signature(None, candidate)}"
        )

    # Le corps est en Markdown : on retire le balisage plutôt que de l'envoyer
    # tel quel dans un email texte.
    body = (letter.get("body") or "")
    body = body.replace("**", "").replace("*   ", "- ").replace("* ", "- ")

    return "\n\n".join(filter(None, [
        letter.get("salutation") or "Madame, Monsieur,",
        body,
        letter.get("closing") or "",
        _signature(letter, candidate),
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
    spontaneous: bool = False,
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
    if spontaneous:
        # Une candidature non sollicitée se refuse en un clic, et ce refus est
        # respecté pour toute l'entreprise (voir app/api/optout.py).
        from app.api.optout import optout_link
        link = optout_link(to_email)
        body += (
            "\n\n—\nCandidature spontanée transmise par Alice (alice-agent.fr) à l'adresse "
            "publiée sur votre site. "
            + (f"Pour ne plus recevoir de candidature spontanée : {link}" if link
               else "Pour ne plus en recevoir, répondez simplement « STOP ».")
        )

    # Le CV joint est celui figé à la préparation de l'envoi — adapté à
    # l'offre le cas échéant. À défaut, il suit le choix de présentation du
    # candidat, pas seulement le fichier déposé à l'inscription.
    if resume:
        cv_bytes, cv_name, cv_origin = resume, resume_name or "CV.pdf", "prepared"
    else:
        from app.agents.application.cv_resolver import resolve_cv
        cv_bytes, cv_name, cv_origin = resolve_cv(candidate)

    proof = {
        "to": to_email,
        "subject": subject,
        "attachments": [cv_name] if cv_bytes else [],
        "cv_origin": cv_origin,
    }

    if not settings.can_send_email:
        logger.warning("Aucun transport e-mail — candidature vers %s NON envoyée.", to_email)
        return {
            "ok": True,
            "real": False,
            "error": "l'envoi d'e-mails n'est pas configuré sur ce serveur",
            "proof": {**proof, "simulated": True, "body_preview": body[:400]},
        }

    # « Camille Martin via Alice » depuis le domaine vérifié : délivrable, et
    # honnête sur l'expéditeur. La réponse du recruteur va à l'adresse de
    # réponse du candidat (Alice la lit, la range et la lui transfère), ou
    # directement à lui tant que la réception n'est pas configurée.
    from app.agents.inbox import contact_of
    from app.agents.notifications.mailer import Attachment, Mail, send_mail

    # Sans nom, le dispatcher retient l'envoi ; à défaut, « Alice » seule.
    name = real_name(candidate)
    result = await send_mail(Mail(
        to=to_email,
        subject=subject,
        text=body,
        sender=(f"{name} via Alice" if name else "Alice",
                (spontaneous and settings.spontaneous_from_email) or settings.application_sender),
        reply_to=contact_of(candidate) or None,
        attachments=[Attachment(cv_name, cv_bytes)] if cv_bytes else [],
    ))
    if not result["ok"]:
        return {"ok": False, "real": False, "error": result.get("error") or "échec d'envoi"}

    logger.info("Candidature envoyée à %s (%s) via %s", to_email, job_title, result.get("provider"))
    return {
        "ok": True,
        "real": bool(result["real"]),
        "error": None if result["real"] else result.get("error"),
        "proof": {**proof, "message_id": result.get("id"), "provider": result.get("provider")},
    }
