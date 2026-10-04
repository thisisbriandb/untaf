"""
Promesses non tenues — le dire, proposer une issue, et prévenir l'équipe.

Un agent qui agit au nom de quelqu'un échoue parfois : un CV qui ne se compose
pas, un envoi refusé, une mission qui ne produit rien. Le pire est le silence.
Chaque incident fait donc deux choses :
  - côté candidat : une ligne au journal (cloche, onglet Mission) qui dit ce
    qui n'a pas marché ET ce qu'il peut faire à la place ;
  - côté équipe : un e-mail à OPS_ALERT_EMAIL, dédoublonné par jour, pour que
    le problème soit corrigé à la source plutôt que découvert par plainte.

Ne lève jamais : signaler un échec ne doit pas en créer un second.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from html import escape
from uuid import UUID

from app.config import settings

logger = logging.getLogger(__name__)

#: Ce qui peut casser, et ce qu'on propose au candidat à la place.
INCIDENTS: dict[str, tuple[str, str]] = {
    "cv_render_failed": (
        "Je n'ai pas réussi à mettre ton CV en page",
        "Ta lettre est prête ; télécharge ton CV d'origine ou réessaie dans un moment — "
        "l'équipe est prévenue.",
    ),
    "send_failed": (
        "L'envoi de ta candidature a échoué",
        "Ton dossier reste prêt dans Candidatures : envoie-le depuis ta messagerie en un "
        "clic, ou réessaie plus tard.",
    ),
    "form_incomplete": (
        "Je n'ai pas pu remplir tout le formulaire de l'employeur",
        "Termine sur le site avec le dossier préparé : il ne reste que les champs signalés.",
    ),
    "pack_failed": (
        "Je n'ai pas pu préparer ce dossier",
        "Réessaie depuis l'offre dans un moment ; l'équipe est prévenue.",
    ),
    "mission_empty": (
        "Ma mission n'a rien produit",
        "Ton mandat est peut-être trop étroit : élargis-le dans l'onglet Mission, ou colle "
        "une offre trouvée ailleurs.",
    ),
    "mission_failed": (
        "Ma mission s'est arrêtée sur une erreur",
        "Ce qui était fait est conservé. Relance-la quand tu veux ; l'équipe est prévenue.",
    ),
    "notification_failed": (
        "Je n'ai pas pu t'envoyer d'e-mail",
        "Tout reste visible ici, dans la cloche et l'onglet Mission.",
    ),
}


async def report_incident(
    kind: str,
    candidate_id: UUID | None,
    detail: str = "",
    *,
    context: dict | None = None,
    notify_user: bool = True,
) -> None:
    """Consigne l'incident pour le candidat et alerte l'équipe. Ne lève jamais."""
    title, alternative = INCIDENTS.get(kind, ("Quelque chose n'a pas marché", ""))
    try:
        if candidate_id and notify_user:
            from app.agents.mission_log import log_event
            from app.database import async_session
            from app.models.mission import MissionEventKind

            async with async_session() as session:
                await log_event(
                    session, candidate_id, MissionEventKind.ERROR,
                    f"{title}. {alternative}".strip(),
                    {"incident": kind, "detail": detail[:500], **(context or {})},
                )
                await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.error("Incident %s non consigné : %s", kind, e)

    await _alert_team(kind, title, candidate_id, detail, context or {})


async def _alert_team(kind: str, title: str, candidate_id: UUID | None, detail: str,
                      context: dict) -> None:
    if not settings.ops_alert_email:
        return
    try:
        from sqlalchemy import select
        from sqlalchemy.exc import IntegrityError

        from app.agents.notifications.mailer import Mail, send_mail
        from app.database import async_session
        from app.models.notification import Notification, NotificationKind, NotificationStatus

        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"incident:{kind}:{candidate_id or '-'}:{day}"[:200]

        async with async_session() as session:
            if (await session.execute(
                select(Notification.id).where(Notification.dedupe_key == key)
            )).scalar_one_or_none():
                return  # déjà signalé aujourd'hui pour ce candidat

        lines = [
            f"Incident : {kind} — {title}",
            f"Candidat : {candidate_id or 'inconnu'}",
            f"Détail : {detail or '—'}",
            *(f"{k} : {v}" for k, v in context.items()),
        ]
        text = "\n".join(lines)
        result = await send_mail(Mail(
            to=settings.ops_alert_email,
            subject=f"[Alice] Promesse non tenue : {title}",
            text=text,
            html="<pre style='font:13px ui-monospace,monospace'>" + escape(text) + "</pre>",
        ))

        # Une alerte n'est rattachée à un candidat que s'il y en a un ; sans
        # candidat, la trace reste dans les logs.
        if candidate_id:
            async with async_session() as session:
                session.add(Notification(
                    candidate_id=candidate_id,
                    kind=NotificationKind.INCIDENT,
                    status=NotificationStatus.SENT if result.get("real")
                    else NotificationStatus.SIMULATED if result.get("ok")
                    else NotificationStatus.FAILED,
                    dedupe_key=key,
                    subject=f"[ops] {title}"[:300],
                    recipient=settings.ops_alert_email,
                    error=result.get("error"),
                    payload={"incident": kind, "ops": True},
                ))
                try:
                    await session.commit()
                except IntegrityError:
                    await session.rollback()
        logger.warning("Incident %s signalé à l'équipe (%s)", kind, result.get("provider"))
    except Exception as e:  # noqa: BLE001
        logger.error("Alerte équipe impossible (%s) : %s", kind, e)
