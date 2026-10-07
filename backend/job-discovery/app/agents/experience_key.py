"""
Identité d'une expérience du parcours.

Les réalisations reformulées pour une offre sont rangées avec la clé de
l'expérience d'origine, pas avec sa position : si le candidat ajoute ou
retire une expérience ensuite, chaque puce reste sous le bon employeur.
"""

import re
import unicodedata


def _norm(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def experience_key(exp: dict) -> str:
    """Employeur + intitulé + début : stable tant que l'expérience est la même."""
    return "|".join((
        _norm(exp.get("company")),
        _norm(exp.get("jobTitle") or exp.get("position")),
        _norm(exp.get("startDate") or exp.get("start_date")),
    ))


def adapted_for(experiences: list, adapted: list) -> list[dict]:
    """
    Pour chaque expérience actuelle, sa version adaptée ({} sinon).

    Les dossiers récents portent une clé : on les rattache par elle. Les
    anciens (sans clé) ne sont repris par position que si le parcours n'a pas
    changé de taille — sinon on préfère les puces d'origine à des faits
    attribués au mauvais employeur.
    """
    items = [a for a in (adapted or []) if isinstance(a, dict)]
    by_key = {a["key"]: a for a in items if a.get("key")}
    if by_key:
        return [by_key.get(experience_key(e), {}) if isinstance(e, dict) else {} for e in experiences]
    if items and len(adapted) == len(experiences):
        return [a if isinstance(a, dict) else {} for a in adapted]
    return [{} for _ in experiences]
