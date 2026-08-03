"""
SIRENE API Seeder — queries INSEE SIRENE API for French tech companies.
Requires SIRENE_API_TOKEN env var (free at api.insee.fr).
"""

import logging
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SIRENE_BASE_URL = "https://api.insee.fr/entreprises/sirene/V3.11"

TARGET_NAF_CODES = [
    "6201Z",  # Programmation informatique
    "6202A",  # Conseil en systèmes et logiciels
    "6209Z",  # Autres activités informatiques
    "6311Z",  # Traitement de données / hébergement
    "5829C",  # Édition de logiciels applicatifs
]

MIN_TRANCHE_EFFECTIF = "12"  # 20-49 salariés minimum


@dataclass
class SireneCompany:
    siren: str
    name: str
    naf_code: str
    tranche_effectif: str
    domain: str | None = None


async def query_sirene(
    naf_codes: list[str] | None = None,
    max_results: int = 1000,
) -> list[SireneCompany]:
    """Query INSEE SIRENE for companies by NAF code and employee count."""
    if not settings.sirene_api_token:
        logger.warning("SIRENE_API_TOKEN not set — skipping SIRENE seeding.")
        return []

    codes = naf_codes or TARGET_NAF_CODES
    companies: list[SireneCompany] = []

    async with httpx.AsyncClient(
        timeout=30,
        headers={
            "Authorization": f"Bearer {settings.sirene_api_token}",
            "Accept": "application/json",
        },
    ) as client:
        for naf in codes:
            try:
                query = (
                    f"activitePrincipaleUniteLegale:{naf} "
                    f"AND trancheEffectifsUniteLegale:[{MIN_TRANCHE_EFFECTIF} TO *] "
                    f"AND etatAdministratifUniteLegale:A"
                )
                resp = await client.get(
                    f"{SIRENE_BASE_URL}/siren",
                    params={"q": query, "nombre": min(max_results, 1000)},
                )
                if resp.status_code in (401, 404):
                    logger.warning("SIRENE %s: status %d", naf, resp.status_code)
                    continue
                resp.raise_for_status()

                for unit in resp.json().get("unitesLegales", []):
                    name = unit.get("denominationUniteLegale", "").strip()
                    if name:
                        companies.append(SireneCompany(
                            siren=unit["siren"],
                            name=name,
                            naf_code=naf,
                            tranche_effectif=unit.get("trancheEffectifsUniteLegale", ""),
                        ))
            except httpx.HTTPError as e:
                logger.warning("SIRENE error for NAF %s: %s", naf, e)

    logger.info("SIRENE seeding: %d companies found", len(companies))
    return companies


def guess_domain_from_name(name: str) -> str:
    """Fallback domain guess from company name."""
    cleaned = name.lower()
    for s in [" sas", " sarl", " sa", " eurl", " sasu"]:
        cleaned = cleaned.replace(s, "")
    slug = "".join(c for c in cleaned if c.isalnum())
    return f"{slug}.com" if slug else "unknown.com"
