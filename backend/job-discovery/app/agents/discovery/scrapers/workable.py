"""
Workable — widget public des comptes (lecture seule, sans clé).

    GET https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true

Les boards Workable étaient déjà recensés par le registre, mais aucun
collecteur ne les lisait. La candidature passe par le formulaire hébergé
(remplissage navigateur), Workable n'ouvrant pas d'envoi par API sans la clé
de l'employeur.
"""

import logging

import httpx

from app.agents.discovery.scrapers.base import BaseScraper, ScrapedJob
from app.agents.discovery.scrapers.recruitee import _text
from app.config import settings

logger = logging.getLogger(__name__)

WIDGET_URL = "https://apply.workable.com/api/v1/widget/accounts/{slug}"


class WorkableScraper(BaseScraper):
    def platform_name(self) -> str:
        return "workable"

    async def scrape(self, slug: str) -> list[ScrapedJob]:
        async with httpx.AsyncClient(
            timeout=settings.scrape_request_timeout,
            headers={"User-Agent": settings.scrape_user_agent},
        ) as client:
            try:
                resp = await client.get(WIDGET_URL.format(slug=slug), params={"details": "true"})
            except httpx.HTTPError as e:
                logger.warning("Workable '%s' injoignable : %s", slug, e)
                return []
        if resp.status_code != 200:
            return []
        jobs = []
        for j in (resp.json() or {}).get("jobs") or []:
            if not isinstance(j, dict):
                continue
            location = ", ".join(p for p in (j.get("city"), j.get("country")) if p)
            jobs.append(ScrapedJob(
                external_id=f"workable:{slug}:{j.get('shortcode') or j.get('code')}",
                title=(j.get("title") or "Offre").strip()[:500],
                source_url=j.get("url") or j.get("shortlink") or "",
                description_raw=_text(" ".join(
                    filter(None, [j.get("description"), j.get("requirements"), j.get("benefits")])
                )) or None,
                location=location or None,
                department=j.get("department"),
                apply_url=j.get("application_url") or j.get("url"),
                updated_at=j.get("published_on") or j.get("created_at"),
                extra={"employment_type": j.get("employment_type"),
                       "remote": j.get("telecommuting")},
            ))
        return jobs
