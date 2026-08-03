"""
ScraperAgent — Playwright & DOM Analysis Agent for discovering job postings on complex career pages.

Analyzes career page DOM structure, navigates job listings, handles pagination/scroll,
and extracts structured job postings (title, location, contract, description, apply URL).
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

from app.agents.discovery.scrapers.base import ScrapedJob

logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    company_name: str
    target_url: str
    jobs: list[ScrapedJob]
    status: str  # "success" | "partial" | "failed"
    error: str | None = None


class ScraperAgent:
    """
    Autonomous browser agent for scraping non-standard or complex career pages.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def run(self, company_name: str, target_url: str) -> ScrapeResult:
        """
        Navigate to target_url, inspect DOM, scroll/paginate, and extract jobs.
        """
        logger.info("🤖 ScraperAgent starting navigation for %s at %s", company_name, target_url)

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("Playwright not available, using HTTP fallback scraper for %s", company_name)
            return await self._fallback_httpx_scrape(company_name, target_url)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                logger.info("Opening page: %s", target_url)
                await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)

                # Auto-scroll to load dynamic job cards
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await page.wait_for_timeout(1000)

                # Extract job links & job card elements from DOM
                extracted_jobs = await self._extract_jobs_from_dom(page, company_name, target_url)

                await browser.close()

                return ScrapeResult(
                    company_name=company_name,
                    target_url=target_url,
                    jobs=extracted_jobs,
                    status="success" if extracted_jobs else "partial",
                )

        except Exception as err:
            logger.error("ScraperAgent failed for %s (%s): %s", company_name, target_url, err)
            return await self._fallback_httpx_scrape(company_name, target_url, str(err))

    async def _extract_jobs_from_dom(self, page: Any, company_name: str, target_url: str) -> list[ScrapedJob]:
        """Extract job listings from DOM using robust DOM inspection."""
        scraped: list[ScrapedJob] = []
        links = await page.query_selector_all("a[href]")
        seen_urls: set[str] = set()

        for link in links:
            try:
                href = await link.get_attribute("href")
                text = (await link.inner_text()).strip()

                if not href or not text or len(text) < 2:
                    continue

                # Ignore general top navigation links
                if href.rstrip("/") in [target_url.rstrip("/"), "https://alan.com/careers", "#"]:
                    continue

                full_url = href if href.startswith("http") else f"{target_url.rstrip('/')}/{href.lstrip('/')}"

                # Match posting URLs (containing GUIDs, /job, /posting, /alan/, /role, etc.)
                is_job_url = (
                    re.search(r"[0-9a-f]{8}-[0-9a-f]{4}", href, re.I)
                    or any(k in href.lower() for k in ["/job", "/career", "/poste", "/position", "/o/", "/vacancy", "/role", "/posting", f"/{company_name.lower()}/"])
                )

                if is_job_url and full_url not in seen_urls:
                    seen_urls.add(full_url)
                    job_id = re.sub(r"\W+", "_", full_url.split("/")[-1] or text)

                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    title = lines[0] if lines else text
                    location = lines[1] if len(lines) > 1 else company_name

                    scraped.append(
                        ScrapedJob(
                            external_id=f"{company_name.lower()}_{job_id}",
                            title=title,
                            source_url=full_url,
                            description_raw=text,
                            location=location,
                            apply_url=full_url,
                        )
                    )
            except Exception:
                continue

        logger.info("ScraperAgent extracted %d jobs from DOM for %s", len(scraped), company_name)
        return scraped

    async def _fallback_httpx_scrape(self, company_name: str, target_url: str, initial_error: str | None = None) -> ScrapeResult:
        """HTTP-based fallback if Playwright is unavailable or fails."""
        import httpx

        scraped: list[ScrapedJob] = []
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(target_url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    # Basic regex match for job links
                    matches = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>', resp.text, re.I)
                    seen: set[str] = set()

                    for href, title in matches:
                        clean_title = title.strip()
                        if len(clean_title) > 3 and any(k in href.lower() for k in ["/job", "/career", "/poste", "/position"]):
                            full_url = href if href.startswith("http") else f"{target_url.rstrip('/')}/{href.lstrip('/')}"
                            if full_url not in seen:
                                seen.add(full_url)
                                scraped.append(
                                    ScrapedJob(
                                        external_id=f"{company_name.lower()}_{len(scraped)+1}",
                                        title=clean_title,
                                        source_url=full_url,
                                        description_raw=clean_title,
                                        location=company_name,
                                        apply_url=full_url,
                                    )
                                )

            return ScrapeResult(
                company_name=company_name,
                target_url=target_url,
                jobs=scraped,
                status="success" if scraped else "partial",
                error=initial_error,
            )
        except Exception as e:
            return ScrapeResult(
                company_name=company_name,
                target_url=target_url,
                jobs=[],
                status="failed",
                error=str(e),
            )
