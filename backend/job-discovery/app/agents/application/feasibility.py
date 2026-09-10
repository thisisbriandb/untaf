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

from app.config import settings
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
IMPLEMENTED = {"email", "web_form", "greenhouse_api", "lever_api",
               "ashby_api", "workable_api"}

#: Une adresse, pas une consigne rédigée.
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")

#: Canaux dont le formulaire est public et dont l'ATS publie le schéma des
#: champs : ce sont ceux que le remplissage guidé couvre le mieux.
AUTOMATABLE_SOON = {"greenhouse_api", "lever_api", "ashby_api", "workable_api"}


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

    # ── Email : envoi direct, le chemin le plus sûr ───────
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

    # ── ATS à formulaire public ───────────────────────────
    if channel in AUTOMATABLE_SOON:
        ats = channel.replace("_api", "").capitalize()
        if not settings.browser_submit_enabled:
            blockers.append(
                "L'envoi par navigateur est désactivé sur ce serveur : je "
                "remplis le formulaire mais je ne le soumets pas."
            )
        return Feasibility(
            "medium", not blockers,
            f"Cette offre passe par {ats}. Je remplis le formulaire dans un "
            f"navigateur, en suivant les champs que l'ATS publie.",
            blockers, link, channel,
        )

    # ── Formulaire web quelconque ─────────────────────────
    if channel == "web_form":
        # Sans schéma publié, on travaille au socle commun : ça couvre les
        # champs d'identité et le CV, rarement les questions propres à
        # l'employeur. Le dire plutôt que promettre l'automatisation complète.
        blockers.append(
            "Formulaire propre à l'employeur : je remplis ce que je reconnais, "
            "les questions spécifiques peuvent rester à ta charge."
        )
        if not settings.browser_submit_enabled:
            blockers.append(
                "L'envoi par navigateur est désactivé sur ce serveur."
            )
        return Feasibility(
            "complex", False,
            "Le formulaire de cet employeur demande une navigation. "
            "Je le remplis autant que possible et je te dis ce qui reste.",
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
