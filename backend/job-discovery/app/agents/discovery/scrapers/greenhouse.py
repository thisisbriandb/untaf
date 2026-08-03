"""
Greenhouse Scraper — uses the public Job Board API (zero auth for GET).

Endpoint: GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
Returns all published jobs with full HTML descriptions.
"""

import logging

import httpx

from app.config import settings
from app.agents.discovery.scrapers.base import BaseScraper, ScrapedJob

logger = logging.getLogger(__name__)

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


class GreenhouseScraper(BaseScraper):

    def platform_name(self) -> str:
        return "greenhouse"

    async def scrape(self, slug: str) -> list[ScrapedJob]:
        """Fetch all jobs from a Greenhouse job board."""
        url = GREENHOUSE_API.format(slug=slug)
        jobs: list[ScrapedJob] = []

        async with httpx.AsyncClient(
            timeout=settings.scrape_request_timeout,
            headers={"User-Agent": settings.scrape_user_agent},
        ) as client:
            try:
                resp = await client.get(url, params={"content": "true"})

                if resp.status_code == 404:
                    logger.warning("Greenhouse board '%s' not found (404)", slug)
                    return []

                resp.raise_for_status()
                data = resp.json()

                for job in data.get("jobs", []):
                    jobs.append(ScrapedJob(
                        external_id=str(job["id"]),
                        title=job.get("title", "Untitled"),
                        source_url=job.get("absolute_url", ""),
                        description_raw=job.get("content", ""),
                        location=job.get("location", {}).get("name"),
                        department=(
                            job.get("departments", [{}])[0].get("name")
                            if job.get("departments")
                            else None
                        ),
                        apply_url=job.get("absolute_url", ""),
                        updated_at=job.get("updated_at"),
                        extra={
                            "offices": [
                                o.get("name") for o in job.get("offices", [])
                            ],
                            "internal_job_id": job.get("internal_job_id"),
                            "requisition_id": job.get("requisition_id"),
                        },
                    ))

                logger.info(
                    "Greenhouse '%s': scraped %d jobs", slug, len(jobs)
                )

            except httpx.HTTPError as e:
                logger.error("Greenhouse scrape failed for '%s': %s", slug, e)

        return jobs
