"""
Les entreprises à qui écrire, d'après l'annuaire public.

Source : API Recherche d'entreprises (recherche-entreprises.api.gouv.fr), libre
et sans clé, alimentée par le répertoire SIRENE. On y cherche les entreprises
actives, d'une taille où l'on recrute (10 salariés et plus), dans les secteurs
où le métier du candidat est au cœur de l'activité, et dans ses départements.

L'annuaire ne donne ni site ni adresse e-mail : ce module ne renvoie que des
cibles. `contacts.py` trouve ensuite l'adresse publiée par l'entreprise.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

API = "https://recherche-entreprises.api.gouv.fr/search"
GEO = "https://api-adresse.data.gouv.fr/search/"

#: Secteurs (codes NAF) où chaque famille de métier est au cœur de l'activité.
#: Volontairement resserré : une candidature spontanée bien ciblée vaut mieux
#: que dix envoyées au hasard.
NAF_BY_FAMILY: dict[str, list[str]] = {
    "software": ["62.01Z", "62.02A", "62.02B", "62.03Z", "62.09Z", "63.11Z", "58.29C", "58.21Z"],
    "data": ["62.01Z", "62.02A", "63.11Z", "63.12Z", "73.20Z", "72.19Z"],
    "product": ["62.01Z", "58.29C", "63.12Z", "62.02A"],
    "design": ["74.10Z", "73.11Z", "62.01Z", "59.11B"],
    "marketing": ["73.11Z", "73.12Z", "73.20Z", "70.21Z", "63.12Z"],
    "sales": ["46.51Z", "46.69B", "46.90Z", "62.02A", "77.11A"],
    "support": ["62.02A", "62.03Z", "82.20Z", "95.11Z"],
    "hr": ["78.10Z", "78.20Z", "78.30Z", "70.22Z"],
    "finance": ["69.20Z", "70.22Z", "64.19Z", "66.22Z", "66.19B"],
    "legal": ["69.10Z", "70.22Z"],
    "ops": ["52.29A", "52.29B", "52.10B", "49.41A", "82.99Z"],
    "engineering": ["71.12B", "71.12A", "72.19Z", "33.20C", "28.99B"],
    "health": ["86.10Z", "86.22C", "86.90E", "87.10A", "88.10A"],
}

#: Tranches d'effectif SIRENE de 10 à 999 salariés : assez grand pour recruter,
#: assez petit pour qu'une candidature spontanée soit lue par quelqu'un.
SIZE_CODES = "11,12,21,22,31,32,41"


@dataclass
class Target:
    siren: str
    name: str
    naf: str | None
    city: str | None
    department: str | None
    size_code: str | None


async def department_of(city: str, client: httpx.AsyncClient) -> str | None:
    """« Lyon » → « 69 », via la Base Adresse Nationale. None si inconnue."""
    try:
        res = await client.get(GEO, params={"q": city, "type": "municipality", "limit": 1})
        features = (res.json() or {}).get("features") or []
        if not features:
            return None
        context = features[0].get("properties", {}).get("context", "")
        dep = context.split(",")[0].strip()
        return dep or None
    except Exception as e:  # noqa: BLE001
        logger.info("Département introuvable pour %s : %s", city, e)
        return None


def to_target(item: dict) -> Target | None:
    siren = str(item.get("siren") or "").strip()
    name = (item.get("nom_complet") or item.get("nom_raison_sociale") or "").strip()
    if not siren or not name:
        return None
    siege = item.get("siege") or {}
    return Target(
        siren=siren,
        name=name,
        naf=item.get("activite_principale") or siege.get("activite_principale"),
        city=siege.get("libelle_commune"),
        department=siege.get("departement"),
        size_code=item.get("tranche_effectif_salarie") or siege.get("tranche_effectif_salarie"),
    )


async def find_targets(
    families: list[str], cities: list[str], limit: int = 30,
    client: httpx.AsyncClient | None = None,
) -> list[Target]:
    """Entreprises actives des secteurs du métier, dans les départements visés."""
    naf = sorted({code for f in families for code in NAF_BY_FAMILY.get(f, [])})
    if not naf:
        return []
    own = client is None
    client = client or httpx.AsyncClient(timeout=20, headers={"User-Agent": "Alice (alice-agent.fr)"})
    try:
        departments = [d for d in [await department_of(c, client) for c in cities[:3]] if d]
        found: dict[str, Target] = {}
        for dep in departments or [None]:
            params = {
                "activite_principale": ",".join(naf),
                "tranche_effectif_salarie": SIZE_CODES,
                "etat_administratif": "A",
                "per_page": 25,
                "page": 1,
            }
            if dep:
                params["departement"] = dep
            try:
                res = await client.get(API, params=params)
                res.raise_for_status()
            except Exception as e:  # noqa: BLE001 — une recherche ratée n'arrête pas les autres
                logger.warning("Annuaire des entreprises injoignable (%s) : %s", dep, e)
                continue
            for item in (res.json() or {}).get("results") or []:
                t = to_target(item)
                if t and t.siren not in found:
                    found[t.siren] = t
            if len(found) >= limit:
                break
        return list(found.values())[:limit]
    finally:
        if own:
            await client.aclose()
