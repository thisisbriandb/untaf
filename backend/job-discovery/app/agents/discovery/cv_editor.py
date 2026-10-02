"""
Édition du CV par Alice.

Quand l'utilisateur colle le contenu d'un stage et demande de l'ajouter, Alice
doit structurer ce texte et l'écrire dans le CV. Sans cet outil, elle ne peut
que répondre — et comme sa consigne lui interdit d'inventer, elle refuse, ce
qui est le pire des deux mondes : l'information était fournie, et rien ne se
passe.

Ici on ne demande pas au modèle d'inventer : on lui demande de STRUCTURER un
texte que l'utilisateur a lui-même fourni.
"""

import json
import logging
from typing import Literal


from app import llm
from app.config import settings

logger = logging.getLogger(__name__)

CvSection = Literal["experiences", "education", "languages", "skills"]


STRUCTURE_PROMPT = """Tu structures un extrait de CV fourni PAR LE CANDIDAT
lui-même. Il te l'a copié depuis son document : ce n'est pas une invention, tu
as le droit et le devoir de l'exploiter.

TEXTE FOURNI
{raw}

TRAVAIL DEMANDÉ
Transforme ce texte en entrées structurées pour la section « {section} ».

Formats attendus :
- experiences : {{"jobTitle": str, "company": str, "location": str,
    "startDate": "AAAA-MM", "endDate": "AAAA-MM" ou "present",
    "isCurrent": bool, "highlights": [str]}}
    Un stage, une alternance, un job étudiant ou une mission freelance est une
    expérience professionnelle. L'intitulé doit le refléter (« Stage —
    Développeur web »), mais l'entrée est une expérience.
- education : {{"degree": str, "institution": str, "location": str,
    "startYear": "AAAA", "endYear": "AAAA"}}
- languages : {{"language": str, "level": str}}
- skills : une simple liste de chaînes.

RÈGLES
- N'invente rien qui ne soit pas dans le texte. Un champ absent reste une
  chaîne vide — jamais une valeur plausible.
- Reprends les puces telles qu'elles sont écrites dans 'highlights', sans les
  reformuler ni les enjoliver.
- Plusieurs entrées peuvent être présentes dans le même texte : renvoie-les
  toutes.

Réponds en JSON strict : {{"entries": [...]}}
"""


def _fallback_experience(raw: str) -> list[dict]:
    """
    Sans LLM, on conserve au moins le texte tel quel.

    Une entrée brute que le candidat pourra corriger vaut mieux qu'un refus :
    l'information est déjà dans le CV côté utilisateur, il ne doit pas avoir à
    la ressaisir.
    """
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    if not lines:
        return []
    return [{
        "jobTitle": lines[0][:120],
        "company": "",
        "location": "",
        "startDate": "",
        "endDate": "",
        "isCurrent": False,
        "highlights": lines[1:8],
    }]


async def structure_cv_entries(raw: str, section: CvSection) -> list[dict]:
    """Transforme un texte libre en entrées de CV. Ne lève jamais."""
    if not raw.strip():
        return []

    if not settings.gemini_api_key:
        return _fallback_experience(raw) if section == "experiences" else []

    try:
        response = await llm.generate(
            STRUCTURE_PROMPT.format(raw=raw[:4000], section=section), json=True
        )
        entries = json.loads(response).get("entries") or []
        return [e for e in entries if isinstance(e, (dict, str))]

    except Exception as e:  # noqa: BLE001
        logger.error("CV entry structuring failed: %s", e, exc_info=True)
        return _fallback_experience(raw) if section == "experiences" else []


def merge_entries(
    content: dict, section: CvSection, entries: list, replace: bool = False
) -> dict:
    """
    Fusionne les nouvelles entrées dans le CV.

    Par défaut on ajoute : l'utilisateur qui demande « ajoute ce stage » ne veut
    pas perdre le reste de son parcours. Les doublons évidents sont écartés.
    """
    updated = dict(content or {})
    existing = list(updated.get(section) or [])

    if replace:
        updated[section] = entries
        return updated

    if section == "skills":
        known = {str(s).strip().lower() for s in existing}
        updated[section] = existing + [
            s for s in entries
            if isinstance(s, str) and s.strip().lower() not in known
        ]
        return updated

    def key(entry: dict) -> tuple:
        return (
            str(entry.get("jobTitle") or entry.get("degree") or entry.get("language") or "").lower(),
            str(entry.get("company") or entry.get("institution") or "").lower(),
        )

    known = {key(e) for e in existing if isinstance(e, dict)}
    fresh = [e for e in entries if isinstance(e, dict) and key(e) not in known]

    # Les nouvelles expériences passent devant : on liste du plus récent au
    # plus ancien, et ce qu'on vient d'ajouter est en général le plus récent.
    updated[section] = (fresh + existing) if section == "experiences" else (existing + fresh)
    return updated
