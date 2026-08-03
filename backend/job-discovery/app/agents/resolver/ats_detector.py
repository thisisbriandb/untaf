"""
ATS Detector — resolves what ATS platform (if any) a company uses
by probing known endpoints, subdomains, and career page patterns.

Strategy:
1. Check known ATS API endpoints (Greenhouse, Lever, Workable, Ashby)
2. Check standard career page routes (/careers, /jobs, /recrutement)
3. Parse HTML for ATS-specific scripts/iframes
"""

import logging
import re
from dataclasses import dataclass

import httpx

from app.config import settings
from app.models.company import ATSType, CompanyStatus

logger = logging.getLogger(__name__)


@dataclass
class ATSResolution:
    """Result of ATS detection for a company domain."""
    ats_type: ATSType
    status: CompanyStatus
    ats_slug: str | None = None
    careers_url: str | None = None
    error: str | None = None


# ── Known ATS endpoint patterns ──────────────────────────
ATS_CHECKS = [
    {
        "type": ATSType.GREENHOUSE,
        "url_template": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        "slug_source": "domain_prefix",
        "validate": lambda resp: resp.status_code == 200 and "jobs" in resp.text,
    },
    {
        "type": ATSType.LEVER,
        "url_template": "https://api.lever.co/v0/postings/{slug}?mode=json",
        "slug_source": "domain_prefix",
        "validate": lambda resp: resp.status_code == 200 and resp.text.startswith("["),
    },
    {
        "type": ATSType.WORKABLE,
        "url_template": "https://apply.workable.com/api/v3/accounts/{slug}/jobs",
        "slug_source": "domain_prefix",
        "validate": lambda resp: resp.status_code == 200,
    },
    {
        "type": ATSType.ASHBY,
        "url_template": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
        "slug_source": "domain_prefix",
        "validate": lambda resp: resp.status_code == 200 and "jobs" in resp.text,
    },
]

# Standard career page routes to check on the company's own domain
CAREER_ROUTES = [
    "/careers", "/jobs", "/recrutement", "/join-us", "/nous-rejoindre",
    "/career", "/en/careers", "/fr/recrutement", "/hiring",
]

# Patterns in HTML that indicate an embedded ATS
ATS_HTML_PATTERNS = {
    ATSType.GREENHOUSE: [
        re.compile(r"boards\.greenhouse\.io/(\w+)", re.I),
        re.compile(r"grnh\.se", re.I),
    ],
    ATSType.LEVER: [
        re.compile(r"jobs\.lever\.co/(\w+)", re.I),
        re.compile(r"api\.lever\.co", re.I),
    ],
    ATSType.WORKABLE: [
        re.compile(r"apply\.workable\.com/(\w+)", re.I),
        re.compile(r"workable\.com", re.I),
    ],
    ATSType.WORKDAY: [
        re.compile(r"(\w+)\.wd\d+\.myworkdayjobs\.com", re.I),
        re.compile(r"workday\.com", re.I),
    ],
    ATSType.SMARTRECRUITERS: [
        re.compile(r"careers\.smartrecruiters\.com/(\w+)", re.I),
    ],
    ATSType.ASHBY: [
        re.compile(r"jobs\.ashbyhq\.com/(\w+)", re.I),
    ],
}


def _extract_slug(domain: str) -> str:
    """Extract likely ATS slug from domain (e.g., 'alan.com' → 'alan')."""
    return domain.split(".")[0].lower().replace("-", "")


async def _check_ats_apis(
    client: httpx.AsyncClient, domain: str
) -> ATSResolution | None:
    """Probe known ATS API endpoints to find a match."""
    slug = _extract_slug(domain)

    # Also try common slug variations
    slug_variations = [slug]
    if "-" in domain.split(".")[0]:
        slug_variations.append(domain.split(".")[0].lower())

    for check in ATS_CHECKS:
        for s in slug_variations:
            url = check["url_template"].format(slug=s)
            try:
                resp = await client.get(url, follow_redirects=True)
                if check["validate"](resp):
                    logger.info(
                        "✅ ATS detected for %s: %s (slug=%s)",
                        domain, check["type"].value, s,
                    )
                    return ATSResolution(
                        ats_type=check["type"],
                        status=CompanyStatus.ATS_DIRECT,
                        ats_slug=s,
                        careers_url=url,
                    )
            except httpx.HTTPError:
                continue

    return None


async def _check_career_pages(
    client: httpx.AsyncClient, domain: str
) -> ATSResolution | None:
    """Check standard career routes on the company's domain."""
    base_urls = [f"https://www.{domain}", f"https://{domain}"]

    for base in base_urls:
        for route in CAREER_ROUTES:
            url = f"{base}{route}"
            try:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code != 200:
                    continue

                html = resp.text

                # Check for embedded ATS in the HTML
                for ats_type, patterns in ATS_HTML_PATTERNS.items():
                    for pattern in patterns:
                        match = pattern.search(html)
                        if match:
                            extracted_slug = match.group(1) if match.lastindex else None
                            logger.info(
                                "✅ ATS detected in HTML for %s: %s at %s",
                                domain, ats_type.value, url,
                            )

                            status = CompanyStatus.ATS_DIRECT
                            if ats_type == ATSType.WORKDAY:
                                status = CompanyStatus.COMPLEX_WORKDAY

                            return ATSResolution(
                                ats_type=ats_type,
                                status=status,
                                ats_slug=extracted_slug or _extract_slug(domain),
                                careers_url=str(resp.url),
                            )

                # No embedded ATS found, but career page exists
                # Check if it has a form or just listings
                has_form = bool(re.search(
                    r'<form[^>]*action|<input[^>]*type=["\']file|apply|postuler',
                    html, re.I,
                ))

                if has_form:
                    return ATSResolution(
                        ats_type=ATSType.CUSTOM,
                        status=CompanyStatus.FORM_STANDARD,
                        careers_url=str(resp.url),
                    )

                # Career page exists but no clear apply method
                return ATSResolution(
                    ats_type=ATSType.CUSTOM,
                    status=CompanyStatus.FORM_STANDARD,
                    careers_url=str(resp.url),
                )

            except httpx.HTTPError:
                continue

    return None


async def resolve_ats(domain: str) -> ATSResolution:
    """
    Main entry point: detect what ATS a company uses.
    Tries API endpoints first (fast & reliable), then falls back to
    career page HTML inspection.
    """
    async with httpx.AsyncClient(
        timeout=settings.scrape_request_timeout,
        headers={"User-Agent": settings.scrape_user_agent},
    ) as client:
        # Step 1: Try direct ATS API checks (most reliable)
        result = await _check_ats_apis(client, domain)
        if result:
            return result

        # Step 2: Check career pages for embedded ATS
        result = await _check_career_pages(client, domain)
        if result:
            return result

    # Step 3: Nothing found
    logger.info("❌ No career page found for %s", domain)
    return ATSResolution(
        ats_type=ATSType.UNKNOWN,
        status=CompanyStatus.NO_CAREER_PAGE,
    )
