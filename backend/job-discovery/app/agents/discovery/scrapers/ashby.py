"""
Ashby Scraper — uses the public Job Board API (zero auth for GET).

Endpoint: GET https://api.ashbyhq.com/posting-api/job-board/{slug}
Returns `{"jobs": [...], "apiVersion": "..."}` with both HTML and plain-text
descriptions.
"""

import logging

import httpx

from app.config import settings
from app.agents.discovery.scrapers.base import BaseScraper, ScrapedJob

logger = logging.getLogger(__name__)

ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


class AshbyScraper(BaseScraper):

    def platform_name(self) -> str:
        return "ashby"

    async def scrape(self, slug: str) -> list[ScrapedJob]:
        """Fetch all listed jobs from an Ashby job board."""
        url = ASHBY_API.format(slug=slug)
        jobs: list[ScrapedJob] = []

        async with httpx.AsyncClient(
            timeout=settings.scrape_request_timeout,
            headers={"User-Agent": settings.scrape_user_agent},
        ) as client:
            try:
                resp = await client.get(url)

                if resp.status_code == 404:
                    logger.warning("Ashby board '%s' not found (404)", slug)
                    return []

                resp.raise_for_status()
                data = resp.json()

                for job in data.get("jobs", []) or []:
                    # Unlisted postings are drafts or internal — skip them.
                    if job.get("isListed") is False:
                        continue

                    # Plain text keeps the qualifier's language detection clean;
                    # the HTML is kept aside for the Canvas renderer.
                    description = job.get("descriptionPlain") or job.get("descriptionHtml") or ""

                    jobs.append(ScrapedJob(
                        external_id=str(job.get("id", "")),
                        title=job.get("title", "Untitled"),
                        source_url=job.get("jobUrl", ""),
                        description_raw=description,
                        location=job.get("location"),
                        department=job.get("department") or job.get("team"),
                        apply_url=job.get("applyUrl") or job.get("jobUrl", ""),
                        updated_at=job.get("publishedAt"),
                        extra={
                            "employment_type": job.get("employmentType"),
                            "workplace_type": job.get("workplaceType"),
                            "is_remote": job.get("isRemote"),
                            "secondary_locations": [
                                loc.get("location")
                                for loc in (job.get("secondaryLocations") or [])
                                if isinstance(loc, dict)
                            ],
                            # `address` is present-but-null on many postings,
                            # so `.get(k, {})` is not enough — chain on `or {}`.
                            "country": (
                                (job.get("address") or {})
                                .get("postalAddress") or {}
                            ).get("addressCountry"),
                            "description_html": job.get("descriptionHtml", ""),
                        },
                    ))

                logger.info("Ashby '%s': scraped %d jobs", slug, len(jobs))

            except httpx.HTTPError as e:
                logger.error("Ashby scrape failed for '%s': %s", slug, e)
            except Exception as e:  # noqa: BLE001
                # A payload shape we did not anticipate must not lose the
                # postings already normalised above.
                logger.error(
                    "Ashby '%s': unexpected payload (%s) — keeping %d jobs",
                    slug, e, len(jobs), exc_info=True,
                )

        return jobs
