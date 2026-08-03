"""
WTTJ Sitemap Seeder — extracts company slugs and domains from
Welcome to the Jungle's public sitemap to build an initial database
of actively-recruiting French companies.

Strategy: Parse the sitemap index → find company pages sitemap →
extract company slugs → resolve their official domains.
"""

import logging
import re
from dataclasses import dataclass
from xml.etree import ElementTree

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# WTTJ sitemap namespace
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# Known WTTJ sitemap patterns
WTTJ_SITEMAP_INDEX = "https://www.welcometothejungle.com/sitemap.xml"
WTTJ_COMPANIES_PATTERN = re.compile(r"/fr/companies/([a-z0-9\-]+)")


@dataclass
class WTTJCompany:
    """A company discovered from WTTJ sitemap."""
    slug: str
    wttj_url: str
    name: str | None = None
    domain: str | None = None


async def fetch_sitemap_index(client: httpx.AsyncClient) -> list[str]:
    """Fetch the WTTJ sitemap index and return URLs of sub-sitemaps."""
    logger.info("Fetching WTTJ sitemap index: %s", WTTJ_SITEMAP_INDEX)
    resp = await client.get(WTTJ_SITEMAP_INDEX, follow_redirects=True)
    resp.raise_for_status()

    root = ElementTree.fromstring(resp.text)
    urls = []

    # Look for sitemap entries in the index
    for sitemap in root.findall("sm:sitemap", SITEMAP_NS):
        loc = sitemap.find("sm:loc", SITEMAP_NS)
        if loc is not None and loc.text:
            urls.append(loc.text.strip())

    logger.info("Found %d sub-sitemaps in WTTJ index", len(urls))
    return urls


async def fetch_company_slugs_from_sitemap(
    client: httpx.AsyncClient,
    sitemap_url: str,
) -> list[WTTJCompany]:
    """Parse a single sitemap XML and extract company slugs."""
    logger.info("Fetching sitemap: %s", sitemap_url)
    resp = await client.get(sitemap_url, follow_redirects=True)
    resp.raise_for_status()

    root = ElementTree.fromstring(resp.text)
    companies = []
    seen_slugs: set[str] = set()

    for url_elem in root.findall("sm:url", SITEMAP_NS):
        loc = url_elem.find("sm:loc", SITEMAP_NS)
        if loc is None or not loc.text:
            continue

        match = WTTJ_COMPANIES_PATTERN.search(loc.text)
        if match:
            slug = match.group(1)
            if slug not in seen_slugs:
                seen_slugs.add(slug)
                companies.append(WTTJCompany(
                    slug=slug,
                    wttj_url=loc.text.strip(),
                ))

    logger.info("Extracted %d unique company slugs from %s", len(companies), sitemap_url)
    return companies


async def resolve_company_domain(
    client: httpx.AsyncClient,
    company: WTTJCompany,
) -> WTTJCompany:
    """
    Try to resolve the company's official domain from their WTTJ profile page.
    WTTJ pages typically contain a link to the company's website.
    """
    try:
        resp = await client.get(company.wttj_url, follow_redirects=True)
        resp.raise_for_status()

        # Look for common patterns of official website links in the HTML
        # WTTJ embeds the website URL in structured data or in specific elements
        text = resp.text

        # Try to find the company name from the page title
        title_match = re.search(r"<title>([^|<]+)", text)
        if title_match:
            raw_name = title_match.group(1).strip()
            # Remove common suffixes like " - Welcome to the Jungle"
            company.name = re.sub(r"\s*[-–—]\s*Welcome.*$", "", raw_name).strip()

        # Try to find the official website in meta or structured data
        # Pattern 1: og:see_also or canonical-like links
        website_patterns = [
            r'"website"\s*:\s*"(https?://[^"]+)"',
            r'"url"\s*:\s*"(https?://(?!.*welcometothejungle)[^"]+)"',
            r'href="(https?://(?!.*welcometothejungle|.*linkedin|.*twitter|.*facebook|.*instagram)[^"]+)"[^>]*>(?:Site web|Website|Voir le site)',
        ]
        for pattern in website_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                url = match.group(1)
                # Extract just the domain
                domain_match = re.match(r"https?://(?:www\.)?([^/]+)", url)
                if domain_match:
                    company.domain = domain_match.group(1).lower()
                    break

        # Fallback: derive domain from slug (e.g. "alan" → "alan.com")
        if not company.domain:
            company.domain = f"{company.slug}.com"
            logger.debug("Using fallback domain for %s: %s", company.slug, company.domain)

    except httpx.HTTPError as e:
        logger.warning("Failed to resolve domain for %s: %s", company.slug, e)
        company.domain = f"{company.slug}.com"

    return company


async def seed_from_wttj(max_companies: int = 5000) -> list[WTTJCompany]:
    """
    Main entry point: discover companies from WTTJ sitemap.
    Returns a list of WTTJCompany with slug, name, and best-guess domain.
    """
    companies: list[WTTJCompany] = []

    async with httpx.AsyncClient(
        timeout=settings.scrape_request_timeout,
        headers={"User-Agent": settings.scrape_user_agent},
    ) as client:
        # Step 1: Get all sub-sitemaps
        sitemap_urls = await fetch_sitemap_index(client)

        # Step 2: Extract company slugs from company-related sitemaps
        for sitemap_url in sitemap_urls:
            # Only process company-related sitemaps
            if "compan" not in sitemap_url.lower() and "entreprise" not in sitemap_url.lower():
                # Also check generic sitemaps that might contain company URLs
                pass

            batch = await fetch_company_slugs_from_sitemap(client, sitemap_url)
            companies.extend(batch)

            if len(companies) >= max_companies:
                companies = companies[:max_companies]
                break

        logger.info(
            "WTTJ seeding complete: %d companies discovered, resolving domains...",
            len(companies),
        )

        # Step 3: Resolve domains (in batches to avoid hammering WTTJ)
        for i, company in enumerate(companies):
            if i > 0 and i % 50 == 0:
                logger.info("Domain resolution progress: %d/%d", i, len(companies))
            await resolve_company_domain(client, company)

    return companies
