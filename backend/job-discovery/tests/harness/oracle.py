"""
Le corrigé : ce que la page contient vraiment, d'après l'ATS lui-même.

Greenhouse publie sans authentification le contrat exact de ses formulaires —
`GET /jobs/{id}?questions=true` donne le nom, le type et le caractère
obligatoire de chaque champ. C'est une vérité terrain gratuite sur plusieurs
centaines d'offres, là où tout autre corpus demanderait un étiquetage manuel.

Son usage a changé de sens. Ce schéma était la source du moteur, ce qui le
limitait à une plateforme ; il devient ce contre quoi on vérifie que
l'extracteur DOM voit juste. Greenhouse ne sert plus à postuler, il sert à
noter — le cas facile qui doit sortir à 100 % et dont la chute signale une
régression.

Ce qu'on en tire, et qu'aucune autre méthode ne donne : le **rappel**. Un
extracteur ne peut pas signaler un champ qu'il n'a jamais vu ; sans corrigé,
sa cécité est indétectable. Mesuré sur une page `boards.eu`, l'extracteur
voit 12 champs obligatoires là où le DOM en déclare 19.
"""

from __future__ import annotations

import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

#: Board et identifiant d'offre dans une URL Greenhouse. Contrairement à la
#: version du moteur, celle-ci accepte le domaine européen : `boards.eu` est
#: le même produit, et l'ignorer écartait 64 offres du stock.
_URL_GREENHOUSE = re.compile(
    r"(?:job-)?boards(?:\.eu)?\.greenhouse\.io/([^/]+)/jobs/(\d+)", re.I
)

_QUESTIONS = (
    "https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job}?questions=true"
)
_QUESTIONS_EU = (
    "https://boards-api.eu.greenhouse.io/v1/boards/{board}/jobs/{job}?questions=true"
)


async def recuperer(url: str) -> list[dict] | None:
    """
    Le corrigé d'une page, ou `None` si l'ATS n'en publie pas.

    L'absence de corrigé n'est pas une anomalie : c'est le cas de la majorité
    du stock, et précisément la raison d'être du moteur. Ces pages se notent
    autrement — sur ce que le moteur sait faire, pas sur ce qu'il a manqué.
    """
    trouve = _URL_GREENHOUSE.search(url or "")
    if not trouve:
        return None

    board, job = trouve.group(1), trouve.group(2)
    gabarit = _QUESTIONS_EU if ".eu." in url.lower() else _QUESTIONS
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            reponse = await client.get(gabarit.format(board=board, job=job))
        if reponse.status_code != 200:
            logger.info("Corrigé indisponible (%s) pour %s", reponse.status_code, url)
            return None
        questions = reponse.json().get("questions") or []
    except Exception as exc:  # noqa: BLE001
        logger.info("Corrigé injoignable pour %s : %s", url, exc)
        return None

    champs: list[dict] = []
    for question in questions:
        for champ in question.get("fields") or []:
            if not champ.get("name"):
                continue
            champs.append({
                "name": champ["name"],
                "type": champ.get("type", "input_text"),
                "required": bool(question.get("required")),
                "label": question.get("label", ""),
            })
    return champs or None


def ecrire(chemin, champs: list[dict]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(champs, ensure_ascii=False, indent=2), encoding="utf-8")


def lire(chemin) -> list[dict] | None:
    if not chemin.exists():
        return None
    return json.loads(chemin.read_text(encoding="utf-8"))
