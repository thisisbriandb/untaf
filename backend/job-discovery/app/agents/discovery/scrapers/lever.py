"""
Lever Scraper — uses the public Postings API (zero auth).

Endpoint: GET https://api.lever.co/v0/postings/{company_slug}?mode=json
Returns all published jobs as a JSON array.
"""

import logging

import httpx

from app.config import settings
from app.agents.discovery.scrapers.base import BaseScraper, ScrapedJob

logger = logging.getLogger(__name__)

LEVER_API = "https://api.lever.co/v0/postings/{slug}"


class LeverScraper(BaseScraper):

    def platform_name(self) -> str:
        return "lever"

    async def scrape(self, slug: str) -> list[ScrapedJob]:
        """Fetch all jobs from a Lever job board."""
        url = LEVER_API.format(slug=slug)
        jobs: list[ScrapedJob] = []

        async with httpx.AsyncClient(
            timeout=settings.scrape_request_timeout,
            headers={"User-Agent": settings.scrape_user_agent},
        ) as client:
            try:
                resp = await client.get(url, params={"mode": "json"})

                if resp.status_code == 404:
                    logger.warning("Lever board '%s' not found (404)", slug)
                    return []

                resp.raise_for_status()
                data = resp.json()

                # Lever returns a flat JSON array
                if not isinstance(data, list):
                    logger.warning("Lever '%s': unexpected response format", slug)
                    return []

                for posting in data:
                    categories = posting.get("categories", {})

                    jobs.append(ScrapedJob(
                        external_id=posting.get("id", ""),
                        title=posting.get("text", "Untitled"),
                        source_url=posting.get("hostedUrl", ""),
                        description_raw=posting.get("descriptionPlain", ""),
                        location=categories.get("location"),
                        department=categories.get("team"),
                        apply_url=posting.get("applyUrl", ""),
                        updated_at=None,  # Lever doesn't expose updated_at
                        extra={
                            "commitment": categories.get("commitment"),
                            "allLocations": categories.get("allLocations", []),
                            "description_html": posting.get("description", ""),
                            "additional": posting.get("additional", ""),
                            "lists": [
                                {
                                    "text": lst.get("text", ""),
                                    "content": lst.get("content", ""),
                                }
                                for lst in posting.get("lists", [])
                            ],
                        },
                    ))

                logger.info("Lever '%s': scraped %d jobs", slug, len(jobs))

            except httpx.HTTPError as e:
                logger.error("Lever scrape failed for '%s': %s", slug, e)

        return jobs
