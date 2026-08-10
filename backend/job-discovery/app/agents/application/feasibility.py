"""
Évaluation de la faisabilité d'une candidature automatique.

Un seul service répond à la question « puis-je postuler à la place du
candidat, et sinon pourquoi ? ». Avant, la réponse était éparpillée entre le
détecteur de prérequis et le dispatcher, chacun avec sa propre table de
correspondance — d'où des messages du type « canal manual pas encore
automatisable », qui ne veulent rien dire pour l'utilisateur.

Le verdict porte toujours un motif lisible et, quand l'automatisation n'est pas
possible, le lien pour finir à la main.
"""

import logging
import re
from dataclasses import dataclass, field

from app.models.job_posting import ApplyChannel, JobPosting

logger = logging.getLogger(__name__)


@dataclass
class Feasibility:
    """Verdict d'automatisation, toujours motivé."""

    #: simple — un envoi direct · medium — formulaire à remplir
    #: complex — compte ou étapes multiples · impossible — hors de portée
    complexity: str
    automatable: bool
    #: Ce qu'Alice peut faire aujourd'hui, en une phrase adressée au candidat.
    summary: str
    #: Pourquoi ça ne passe pas, quand ça ne passe pas.
    blockers: list[str] = field(default_factory=list)
    #: Lien pour terminer soi-même.
    fallback_url: str | None = None
    channel: str = "unknown"


#: Ce qui est réellement implémenté aujourd'hui. Distinct de ce qui serait
#: techniquement possible : promettre l'un pour l'autre serait mentir.
#: Pour les trois ATS, l'implémentation vérifie le formulaire réel au moment
#: de l'envoi (voir `ats_connectors.py`) — Greenhouse peut bloquer sur une
#: question requise non automatisable, Lever et Ashby restent honnêtement
#: non-automatisables tant qu'ils ne publient pas le schéma du formulaire.
IMPLEMENTED = {"email", "greenhouse_api", "lever_api", "ashby_api"}

#: Une adresse, pas une consigne rédigée.
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")

#: Canaux techniquement automatisables une fois le connecteur écrit. Sert à
#: dire au candidat « c'est faisable, ce n'est pas encore fait » plutôt que
#: « impossible » — la nuance est honnête et utile pour prioriser.
AUTOMATABLE_SOON = {"workable_api"}


def assess(job: JobPosting, has_resume: bool = True) -> Feasibility:
    """Peut-on postuler automatiquement à cette offre ?"""
    channel = job.apply_channel.value if job.apply_channel else "unknown"
    contact = job.contact_json or {}
    raw_email = (contact.get("email") or "").strip()
    email = raw_email if _EMAIL_RE.fullmatch(raw_email) else None
    form_url = contact.get("apply_url") or job.apply_url
    link = form_url or job.source_url

    blockers: list[str] = []
    if not has_resume:
        blockers.append("Aucun CV enregistré — dépose-le dans l'éditeur.")

    # ── Email : le seul canal réellement branché ──────────
    if channel == "email" or email:
        if not email:
            blockers.append("Adresse de candidature absente de l'annonce.")
            return Feasibility(
                "impossible", False,
                "L'annonce ne donne pas d'adresse où écrire.",
                blockers, link, channel,
            )
        return Feasibility(
            "simple", not blockers,
            f"J'envoie ta candidature par email à {email}.",
            blockers, link, channel,
        )

    # ── ATS à formulaire public, connecteur écrit ─────────
    # Le verdict définitif (question requise non automatisable sur
    # Greenhouse, ou absence de schéma vérifiable sur Lever/Ashby) ne se
    # joue qu'au moment de l'envoi, une fois le formulaire réel consulté —
    # comme pour l'email, dont `assess` ne vérifie pas non plus que le SMTP
    # fonctionnera.
    if channel in ("greenhouse_api", "lever_api", "ashby_api"):
        ats = channel.replace("_api", "").capitalize()
        if not link:
            blockers.append("Lien de candidature absent de l'annonce.")
            return Feasibility(
                "impossible", False,
                f"Je n'ai pas de lien pour postuler sur {ats}.",
                blockers, link, channel,
            )
        return Feasibility(
            "simple", not blockers,
            f"Je postule pour toi via {ats} — je vérifie le formulaire exact "
            f"au moment de l'envoi.",
            blockers, link, channel,
        )

    # ── ATS à formulaire public, connecteur pas encore écrit ──
    if channel in AUTOMATABLE_SOON:
        ats = channel.replace("_api", "").capitalize()
        blockers.append(
            f"Le connecteur {ats} n'est pas encore écrit. Techniquement "
            f"faisable — le formulaire est public — mais je ne l'ai pas."
        )
        return Feasibility(
            "medium", False,
            f"Cette offre passe par {ats}. Je prépare tes documents, "
            f"tu finis en deux clics.",
            blockers, link, channel,
        )

    # ── Formulaire web quelconque ─────────────────────────
    if channel == "web_form":
        blockers.append(
            "Formulaire propre à l'employeur : il faut un agent navigateur "
            "pour le lire et le remplir."
        )
        return Feasibility(
            "complex", False,
            "Le formulaire de cet employeur demande une navigation. "
            "Je prépare tes documents, tu les déposes.",
            blockers, link, channel,
        )

    # ── Portail authentifié ───────────────────────────────
    if channel == "external_link":
        blockers.append(
            "Candidature via le portail France Travail : elle exige un compte "
            "candidat authentifié. Je ne manipule pas tes identifiants."
        )
        return Feasibility(
            "impossible", False,
            "Celle-ci se postule depuis ton espace France Travail. "
            "Je prépare tout, tu valides là-bas.",
            blockers, link, channel,
        )

    blockers.append("Canal de candidature non identifié dans l'annonce.")
    return Feasibility(
        "impossible", False,
        "Je n'ai pas trouvé par où postuler sur cette offre.",
        blockers, link, channel,
    )
