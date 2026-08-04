"""
Board registry — builds the list of ATS boards to scrape, without guessing.

The scrapers already accept a board slug; what was missing is the list of
slugs. Guessing them from company names is hopeless (a slug is rarely the
brand name), and there is no public directory of Greenhouse or Ashby boards.

Public web indexes solve it from the other end: Common Crawl records every URL
it ever crawled, so a single range query on `jobs.ashbyhq.com/*` returns the
boards directly. Each candidate slug is then validated against the ATS's own
public job API, which is authoritative — no HTML parsing involved.

Only boards that actually publish offers in France are registered. Greenhouse
and Ashby are US-centric: measured on random samples, 71-84% of indexed boards
are still live, but only 5-9% of those hire in France. Registering the rest
would cost a daily scrape each for nothing.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy import select

from app.database import async_session
from app.models.company import ATSType, Company, CompanyStatus, SeedSource

logger = logging.getLogger(__name__)

COLLINFO_URL = "https://index.commoncrawl.org/collinfo.json"

# Segments that follow the ATS host but are not board slugs.
_RESERVED = {
    "api", "assets", "static", "embed", "images", "img", "css", "js",
    "favicon.ico", "robots.txt", "sitemap.xml", "_next", "public", "share",
}

# A board counts as French-hiring when a posting names France or a large
# French city. Kept deliberately narrow: "EMEA" or "Europe" alone tells us
# nothing about whether the role can be filled from France.
FRENCH_LOCATION = re.compile(
    r"\b(france|paris|lyon|marseille|toulouse|bordeaux|lille|nantes|nice|"
    r"strasbourg|montpellier|rennes|grenoble|sophia[- ]antipolis)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AtsSource:
    """How to enumerate and validate boards for one ATS platform."""

    ats_type: ATSType
    #: Hosts to enumerate in the web index, most specific first.
    index_hosts: tuple[str, ...]
    #: Public job-listing endpoint, formatted with the slug.
    jobs_url: str
    #: Where the postings array lives in the JSON response.
    jobs_key: str | None = "jobs"
    #: Where a posting's location string lives.
    location_path: tuple[str, ...] = ("location", "name")
    #: Slug characters accepted by this platform.
    slug_chars: str = r"A-Za-z0-9_-"
    params: dict[str, str] = field(default_factory=dict)

    def slug_pattern(self, host: str) -> re.Pattern[str]:
        return re.compile(rf"{re.escape(host)}/([{self.slug_chars}]+)")

    def locations(self, payload: Any) -> list[str]:
        """Extract every posting's location string from an API response."""
        postings = payload.get(self.jobs_key, []) if self.jobs_key else payload
        if not isinstance(postings, list):
            return []

        found: list[str] = []
        for posting in postings:
            if not isinstance(posting, dict):
                continue
            node: Any = posting
            for key in self.location_path:
                node = node.get(key) if isinstance(node, dict) else None
                if node is None:
                    break
            found.append(node if isinstance(node, str) else "")
        return found


ATS_SOURCES: dict[str, AtsSource] = {
    "greenhouse": AtsSource(
        ats_type=ATSType.GREENHOUSE,
        index_hosts=("job-boards.greenhouse.io", "boards.greenhouse.io"),
        jobs_url="https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    ),
    "ashby": AtsSource(
        ats_type=ATSType.ASHBY,
        index_hosts=("jobs.ashbyhq.com",),
        jobs_url="https://api.ashbyhq.com/posting-api/job-board/{slug}",
        location_path=("location",),
        slug_chars=r"A-Za-z0-9_.-",
    ),
    "lever": AtsSource(
        ats_type=ATSType.LEVER,
        index_hosts=("jobs.lever.co",),
        jobs_url="https://api.lever.co/v0/postings/{slug}",
        jobs_key=None,  # Lever returns a bare array.
        location_path=("categories", "location"),
        params={"mode": "json"},
    ),
    "workable": AtsSource(
        ats_type=ATSType.WORKABLE,
        index_hosts=("apply.workable.com",),
        jobs_url="https://apply.workable.com/api/v1/widget/accounts/{slug}",
        location_path=("location", "city"),
    ),
}


@dataclass
class BoardProbe:
    """What a live board actually publishes."""

    slug: str
    total_jobs: int
    french_jobs: int


# ── Enumeration ────────────────────────────────────────────────────────────


async def _index_endpoints(
    client: httpx.AsyncClient, *, depth: int = 6
) -> list[str]:
    """
    Candidate CDX indexes, most recent first.

    The newest collections are also the busiest and routinely answer 502/504.
    Falling back to an older crawl costs nothing here: a board slug is a
    long-lived identifier, so a crawl from a few months back lists
    essentially the same companies.
    """
    try:
        collections = (await client.get(COLLINFO_URL)).json()
    except Exception as exc:  # noqa: BLE001 — the registry is best-effort
        logger.warning("Common Crawl collection list unavailable: %s", exc)
        return []
    return [c["cdx-api"] for c in collections[:depth] if c.get("cdx-api")]


async def _query_index(
    client: httpx.AsyncClient,
    endpoints: list[str],
    params: dict[str, str],
    *,
    attempts: int = 2,
) -> httpx.Response | None:
    """
    First endpoint that actually answers, or None when all are down.

    Gateway errors here are transient overload, not a permanent verdict, so
    each endpoint gets a second chance before moving to the next crawl.
    """
    for attempt in range(attempts):
        for cdx in endpoints:
            try:
                resp = await client.get(cdx, params=params)
            except Exception:  # noqa: BLE001
                continue
            if resp.status_code == 200:
                return resp
        if attempt + 1 < attempts:
            await asyncio.sleep(3)
    return None


async def harvest_slugs(
    source: AtsSource,
    *,
    max_pages: int = 6,
    client: httpx.AsyncClient | None = None,
) -> set[str]:
    """Read every board slug this ATS has under its indexed hosts."""
    owns_client = client is None
    client = client or httpx.AsyncClient(
        timeout=180, headers={"User-Agent": "untaf-board-registry/1.0"}
    )

    slugs: set[str] = set()
    try:
        endpoints = await _index_endpoints(client)
        if not endpoints:
            return slugs

        for host in source.index_hosts:
            pattern = source.slug_pattern(host)
            query = {"url": f"{host}/*", "output": "json"}

            # Ask how many pages exist rather than relying on `limit`, which
            # truncates alphabetically and would only ever return boards
            # starting with "a".
            meta = await _query_index(
                client, endpoints, {**query, "showNumPages": "true"}
            )
            if meta is None:
                logger.warning("no index answered for %s", host)
                continue

            # Prefer the collection that just answered, but let the others
            # take over if it stalls on the heavier page queries. Ranges do
            # not line up across crawls; that is harmless because slugs are
            # accumulated in a set.
            answered = str(meta.url).split("?")[0]
            ordered = [answered] + [e for e in endpoints if e != answered]
            try:
                pages = min(meta.json().get("pages", 0), max_pages)
            except json.JSONDecodeError:
                pages = 0

            for page in range(pages):
                resp = await _query_index(client, ordered, {**query, "page": str(page)})
                if resp is None:
                    logger.warning("index page %s/%s unavailable", host, page)
                    continue

                for line in resp.text.splitlines():
                    try:
                        url = json.loads(line).get("url", "")
                    except json.JSONDecodeError:
                        continue
                    match = pattern.search(url)
                    if match:
                        slug = match.group(1).lower()
                        if slug not in _RESERVED:
                            slugs.add(slug)

        logger.info("%s: %d candidate boards from the web index",
                    source.ats_type.value, len(slugs))
        return slugs
    finally:
        if owns_client:
            await client.aclose()


# ── Validation ─────────────────────────────────────────────────────────────


async def probe_board(
    client: httpx.AsyncClient, source: AtsSource, slug: str
) -> BoardProbe | None:
    """Ask the ATS what this board publishes. None when it is dead or empty."""
    try:
        resp = await client.get(
            source.jobs_url.format(slug=slug), params=source.params or None
        )
        if resp.status_code != 200:
            return None
        locations = source.locations(resp.json())
    except Exception:  # noqa: BLE001 — a dead board is the common case
        return None

    if not locations:
        return None
    french = sum(1 for loc in locations if FRENCH_LOCATION.search(loc or ""))
    return BoardProbe(slug=slug, total_jobs=len(locations), french_jobs=french)


async def probe_boards(
    source: AtsSource, slugs: set[str], *, concurrency: int = 10
) -> list[BoardProbe]:
    """Probe every candidate slug, keeping only boards that hire in France."""
    limiter = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        timeout=20, follow_redirects=True,
        headers={"User-Agent": "untaf-board-registry/1.0"},
    ) as client:

        async def guarded(slug: str) -> BoardProbe | None:
            async with limiter:
                return await probe_board(client, source, slug)

        results = await asyncio.gather(*(guarded(s) for s in sorted(slugs)))

    live = [r for r in results if r]
    keep = [r for r in live if r.french_jobs > 0]
    logger.info(
        "%s: %d live boards, %d hiring in France (%d offers)",
        source.ats_type.value, len(live), len(keep),
        sum(r.french_jobs for r in keep),
    )
    return keep


# ── Persistence ────────────────────────────────────────────────────────────


def _synthetic_domain(slug: str, ats: str) -> str:
    """
    `Company.domain` is unique and required, but an ATS board API never gives
    the employer's real domain. Same convention as France Travail employers:
    a reserved suffix that can never collide with a real host.
    """
    return f"{slug}.{ats}.board"


async def register_boards(source: AtsSource, boards: list[BoardProbe]) -> dict[str, int]:
    """Upsert probed boards as scrapable companies. Existing rows are kept."""
    added = updated = 0
    ats = source.ats_type.value

    async with async_session() as session:
        for board in boards:
            domain = _synthetic_domain(board.slug, ats)
            existing = (
                await session.execute(select(Company).where(Company.domain == domain))
            ).scalar_one_or_none()

            if existing:
                # Never overwrite a company someone curated by hand; only
                # make sure it is still pointed at the right board.
                if existing.ats_slug != board.slug:
                    existing.ats_slug = board.slug
                    updated += 1
                continue

            session.add(Company(
                name=board.slug.replace("-", " ").replace(".", " ").title(),
                domain=domain,
                slug=board.slug,
                ats_type=source.ats_type,
                ats_slug=board.slug,
                status=CompanyStatus.ATS_DIRECT,
                seed_source=SeedSource.ATS_INDEX,
                is_active=True,
            ))
            added += 1

        await session.commit()

    return {"added": added, "updated": updated}


async def discover(
    platforms: list[str] | None = None, *, max_pages: int = 6
) -> dict[str, dict[str, int]]:
    """
    Full pass: enumerate, validate, register.

    Safe to re-run — boards already known are left untouched.
    """
    report: dict[str, dict[str, int]] = {}

    for name in platforms or list(ATS_SOURCES):
        source = ATS_SOURCES.get(name)
        if not source:
            logger.warning("Unknown ATS platform '%s'", name)
            continue

        slugs = await harvest_slugs(source, max_pages=max_pages)
        if not slugs:
            report[name] = {"candidates": 0, "added": 0, "updated": 0}
            continue

        boards = await probe_boards(source, slugs)
        counts = await register_boards(source, boards)
        report[name] = {
            "candidates": len(slugs),
            "french_boards": len(boards),
            "french_offers": sum(b.french_jobs for b in boards),
            **counts,
        }

    return report
