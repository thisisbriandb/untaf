"""
Le nom du candidat, tel qu'il signe.

L'onboarding enregistrait « Candidat » faute de mieux : les candidatures
partaient signées « Candidat via Alice ». Un nom de remplacement n'est pas un
nom — ici, on le traite comme absent.
"""

#: Valeurs de remplacement qui ne désignent personne.
PLACEHOLDER_NAMES = {"candidat", "candidate", "candidat via alice", "utilisateur", "user", "inconnu"}


def real_name(candidate) -> str | None:
    """Le nom complet du candidat, ou None s'il n'est pas connu."""
    name = " ".join((getattr(candidate, "full_name", None) or "").split())
    if not name or name.lower() in PLACEHOLDER_NAMES:
        return None
    return name


MISSING_NAME_REASON = (
    "ton nom et ton prénom manquent à ton profil : je ne signe pas une "
    "candidature à ta place sans eux. Ajoute-les dans ton CV, puis relance l'envoi"
)
