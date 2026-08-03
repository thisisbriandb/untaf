"""
Base scraper interface — defines the contract for all job scrapers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ScrapedJob:
    """Normalized job posting from any source."""
    external_id: str
    title: str
    source_url: str
    description_raw: str | None = None
    location: str | None = None
    department: str | None = None
    apply_url: str | None = None
    updated_at: str | None = None
    extra: dict = field(default_factory=dict)


class BaseScraper(ABC):
    """Interface for all job scrapers."""

    @abstractmethod
    async def scrape(self, slug: str) -> list[ScrapedJob]:
        """
        Scrape all active job postings for a company.
        Args:
            slug: The company identifier on the ATS platform.
        Returns:
            List of normalized ScrapedJob objects.
        """
        ...

    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform name (e.g., 'greenhouse', 'lever')."""
        ...
