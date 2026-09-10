"""
Issue d'une candidature — ce qu'on rend à l'utilisateur, réussite ou échec.

Un échec n'est pas une impasse : les documents ont été préparés, l'offre existe
toujours, et il reste presque toujours un chemin manuel. Ce module transforme
l'état technique d'un envoi en quelque chose d'actionnable — les pièces à
récupérer, l'annonce d'origine, et les gestes précis qui restent à faire.

Aucune étape n'est inventée : elles découlent du canal et du motif d'échec
réellement enregistrés. Si on ne sait pas quoi conseiller, on le dit plutôt que
de meubler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote

from app.models.dispatch import ApplicationDispatch, DispatchChannel, DispatchStatus

# Un mailto trop long est tronqué en silence par certains clients. La lettre
# complète reste téléchargeable ; le brouillon n'est qu'un point de départ.
_MAILTO_BODY_LIMIT = 1500


@dataclass
class Outcome:
    """Ce que l'interface doit pouvoir montrer après une tentative."""

    dispatch_id: str
    status: str
    #: Vrai uniquement si quelque chose est réellement parti.
    sent: bool
    headline: str
    detail: str | None = None
    job_url: str | None = None
    has_resume: bool = False
    has_letter: bool = False
    resume_name: str | None = None
    #: Gestes restants, dans l'ordre. Vide quand il n'y a rien à faire.
    steps: list[str] = field(default_factory=list)
    #: Brouillon d'e-mail prêt à ouvrir, quand l'envoi manuel a du sens.
    mailto: str | None = None

    def as_dict(self) -> dict:
        return {
            "dispatch_id": self.dispatch_id,
            "status": self.status,
            "sent": self.sent,
            "headline": self.headline,
            "detail": self.detail,
            "job_url": self.job_url,
            "has_resume": self.has_resume,
            "has_letter": self.has_letter,
            "resume_name": self.resume_name,
            "steps": self.steps,
            "mailto": self.mailto,
        }


def _mailto(dispatch: ApplicationDispatch) -> str | None:
    """
    Brouillon pré-rempli avec la lettre figée.

    Le destinataire n'est renseigné que si on le connaît : proposer une adresse
    devinée ferait partir une candidature chez n'importe qui.
    """
    if not dispatch.letter_body:
        return None

    body = dispatch.letter_body
    if len(body) > _MAILTO_BODY_LIMIT:
        body = body[:_MAILTO_BODY_LIMIT].rsplit("\n", 1)[0] + "\n\n[…]"

    recipient = ""
    if dispatch.channel == DispatchChannel.EMAIL and dispatch.destination:
        recipient = quote(dispatch.destination)

    subject = quote(dispatch.letter_subject or f"Candidature — {dispatch.job_title}")
    return f"mailto:{recipient}?subject={subject}&body={quote(body)}"


#: Libellés lisibles des champs de formulaire les plus courants. Les questions
#: propres à l'employeur (`question_29245599003`) n'en ont pas : on les compte
#: plutôt que d'afficher un identifiant qui ne dit rien.
_FIELD_LABELS = {
    "first_name": "prénom",
    "last_name": "nom",
    "email": "adresse e-mail",
    "phone": "téléphone",
    "resume": "CV",
    "cover_letter": "lettre de motivation",
    "candidate-location": "ville",
    "country": "pays",
}


def _remaining_fields(dispatch: ApplicationDispatch) -> list[str]:
    """Champs que le remplissage automatique n'a pas su renseigner."""
    unhandled = (dispatch.proof or {}).get("unhandled_fields") or []
    if not unhandled:
        return []

    named = [_FIELD_LABELS[f] for f in unhandled if f in _FIELD_LABELS]
    others = len(unhandled) - len(named)
    if others:
        named.append(
            f"{others} question{'s' if others > 1 else ''} propre"
            f"{'s' if others > 1 else ''} à l'employeur"
        )
    return named


def _steps(dispatch: ApplicationDispatch, job_url: str | None) -> list[str]:
    """Les gestes qui restent, déduits du canal et du motif enregistré."""
    if dispatch.status == DispatchStatus.SENT:
        return []

    if dispatch.status == DispatchStatus.AWAITING_APPROVAL:
        return ["Valide l'envoi depuis la file d'attente : rien ne partira sans ton accord."]

    where = "sur l'annonce d'origine" if job_url else "sur le site de l'employeur"

    if dispatch.channel == DispatchChannel.EMAIL and dispatch.destination:
        return [
            "Récupère le CV et la lettre ci-dessous — ce sont exactement les pièces préparées.",
            f"Ouvre le brouillon d'e-mail, déjà adressé à {dispatch.destination}.",
            "Joins le CV téléchargé, relis, puis envoie.",
        ]

    if dispatch.channel in (DispatchChannel.WEB_FORM, DispatchChannel.ATS_API):
        steps = [
            "Télécharge le CV et la lettre préparés.",
            f"Ouvre le formulaire {where}.",
        ]
        # Nommer les champs restants plutôt que de dire « complète le
        # formulaire » : Alice sait précisément lesquels elle n'a pas su
        # renseigner, autant le dire.
        remaining = _remaining_fields(dispatch)
        if remaining:
            steps.append(
                "Le reste est déjà rempli ; il te manque : " + ", ".join(remaining) + "."
            )
        else:
            steps.append(
                "Reporte les informations et joins les pièces : le contenu est "
                "déjà rédigé."
            )
        return steps

    return [
        "Télécharge les pièces préparées.",
        f"Termine la candidature {where}.",
    ]


def build_outcome(
    dispatch: ApplicationDispatch, job_url: str | None = None
) -> Outcome:
    """Traduit l'état d'un envoi en issue exploitable par l'interface."""
    sent = dispatch.status == DispatchStatus.SENT

    if sent:
        headline = f"Candidature envoyée à {dispatch.company_name}."
        detail = (
            f"Partie le {dispatch.sent_at:%d/%m/%Y à %H:%M}."
            if dispatch.sent_at else None
        )
    elif dispatch.status == DispatchStatus.SIMULATED:
        headline = "Répétition terminée — rien n'est parti."
        detail = (
            "L'envoi réel demande une configuration SMTP. Les documents "
            "ci-dessous sont ceux qui seraient partis."
        )
    elif dispatch.status == DispatchStatus.AWAITING_APPROVAL:
        headline = "Candidature prête, en attente de ton accord."
        detail = dispatch.error
    else:
        headline = f"Je n'ai pas pu envoyer chez {dispatch.company_name}."
        detail = dispatch.error

    return Outcome(
        dispatch_id=str(dispatch.id),
        status=dispatch.status.value,
        sent=sent,
        headline=headline,
        detail=detail,
        job_url=job_url,
        has_resume=bool(dispatch.resume_blob),
        has_letter=bool(dispatch.letter_body),
        resume_name=dispatch.resume_name,
        steps=_steps(dispatch, job_url),
        # Inutile de proposer un envoi manuel de ce qui est déjà parti.
        mailto=None if sent else _mailto(dispatch),
    )
