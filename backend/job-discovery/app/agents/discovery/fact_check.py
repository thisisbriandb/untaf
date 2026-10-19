"""
Relecture des faits d'une lettre, après rédaction.

Les consignes ne suffisent pas : même avec « n'invente rien », les modèles
enjolivent (« utilisation quotidienne de SQL », « tableaux de bord adoptés par
les managers », « je suis basée à Lyon »), constaté sur six lettres le
19/10/2026. Une affirmation fausse dans une candidature, c'est le candidat qui
en paie le prix en entretien.

Deux contrôles :
  - les nombres de la lettre doivent figurer dans les données (contrôle exact,
    sans modèle) ;
  - un relecteur (le modèle, avec une consigne de contrôleur et non de
    rédacteur) relève chaque affirmation sur le candidat que les données ne
    prouvent pas.
Les passages relevés sont réécrits une fois, puis relus. Ce qui reste douteux
est rendu à l'appelant : la lettre est alors présentée au candidat avant tout
envoi.
"""

import logging
import re

from pydantic import BaseModel, Field

from app import llm

logger = logging.getLogger(__name__)

#: Nombres « de forme » qu'on ne vérifie pas (puces, H/F, années de date…).
_NUMBER = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)(?![\w])")
_IGNORED_NUMBERS = {"1", "2", "3"}


class Unsupported(BaseModel):
    quote: str = Field(description="Le passage exact de la lettre.")
    why: str = Field(description="Ce qui manque dans les données pour l'affirmer.")


class Review(BaseModel):
    unsupported: list[Unsupported] = Field(default_factory=list)


class Rewrite(BaseModel):
    body: str


REVIEW_PROMPT = """Tu es contrôleur. Tu ne rédiges pas : tu vérifies une lettre de
motivation contre les DONNÉES du candidat et de l'offre.

Relève chaque passage de la lettre qui affirme sur le CANDIDAT quelque chose que
les données ne disent pas explicitement : une tâche, un outil utilisé dans un
poste précis, une fréquence (« quotidiennement »), un volume, un résultat, un
jugement de tiers (« adopté par les managers »), une localisation, une
disponibilité, un trait de personnalité, une passion. Relève aussi ce qu'elle
affirme sur l'ENTREPRISE sans que le texte de l'offre le dise.

Ne relève PAS : les reformulations fidèles, la mise en relation entre une
expérience réelle et un besoin de l'offre, l'intérêt exprimé pour le poste, la
proposition d'échange.

DONNÉES
{facts}

LETTRE
{body}

Réponds en JSON : {{"unsupported": [{{"quote": "passage exact", "why": "ce qui manque"}}]}}.
Liste vide si tout est prouvé."""


REWRITE_PROMPT = """Corrige cette lettre de motivation. Les passages ci-dessous
affirment des choses que les données du candidat ne prouvent pas. Supprime-les,
ou réécris-les en ne gardant que ce que les données disent. N'ajoute aucune
information nouvelle. Garde le reste de la lettre tel quel, Markdown compris.

DONNÉES
{facts}

PASSAGES À CORRIGER
{issues}

LETTRE
{body}

Réponds en JSON : {{"body": "la lettre corrigée"}}."""


def unknown_numbers(body: str, facts: str) -> list[str]:
    """Les nombres de la lettre absents des données (« 12 magasins » doit y être)."""
    known = {n.replace(",", ".") for n in _NUMBER.findall(facts)}
    out = []
    for n in _NUMBER.findall(body):
        norm = n.replace(",", ".")
        if norm not in known and norm not in _IGNORED_NUMBERS and n not in out:
            out.append(n)
    return out


async def review(body: str, facts: str) -> list[Unsupported]:
    issues = [Unsupported(quote=n, why="nombre absent des données") for n in unknown_numbers(body, facts)]
    raw = await llm.generate(REVIEW_PROMPT.format(facts=facts, body=body), schema=Review)
    found = Review.model_validate_json(raw).unsupported
    # Un passage cité doit vraiment figurer dans la lettre (apostrophes et
    # espaces comparés sans leurs variantes typographiques).
    flat = _flat(body)
    issues += [u for u in found if u.quote and _flat(u.quote)[:40] in flat]
    return issues


def _flat(text: str) -> str:
    text = text.replace("’", "'").replace("\u202f", " ").replace("\xa0", " ").replace("*", "")
    return re.sub(r"\s+", " ", text).strip().lower()


async def checked(body: str, facts: str) -> tuple[str, list[str]]:
    """
    La lettre relue : (corps, passages encore non prouvés). Ne lève pas : si la
    relecture échoue, le corps revient tel quel avec un doute à signaler.
    """
    try:
        issues = await review(body, facts)
        if not issues:
            return body, []
        listing = "\n".join(f"- « {u.quote} » : {u.why}" for u in issues)
        raw = await llm.generate(REWRITE_PROMPT.format(facts=facts, issues=listing, body=body),
                                 schema=Rewrite)
        fixed = Rewrite.model_validate_json(raw).body.strip()
        if len(fixed) < 150:
            return body, [u.quote for u in issues]
        remaining = await review(fixed, facts)
        if remaining:
            logger.info("Lettre : %d passage(s) encore non prouvé(s) après correction.", len(remaining))
        return fixed, [u.quote for u in remaining]
    except Exception as e:  # noqa: BLE001 — la relecture ne bloque pas la rédaction
        logger.warning("Relecture des faits impossible : %s", e)
        return body, ["relecture des faits impossible"]


def facts_block(**parts: str) -> str:
    """Les données citables, en un bloc lisible par le relecteur."""
    return "\n\n".join(f"{name.upper()}\n{text}" for name, text in parts.items() if text)

