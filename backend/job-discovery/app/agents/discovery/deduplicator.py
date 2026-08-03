"""
Job deduplicator — fingerprinting to avoid duplicate job postings.

Fingerprint = SHA-256 of (company_domain + normalized_title + normalized_location)
This catches the same job posted under slightly different IDs across scrapes.
"""

import hashlib
import re
import unicodedata


def normalize_text(text: str) -> str:
    """Normalize text for fingerprinting: lowercase, strip accents, collapse whitespace."""
    if not text:
        return ""
    # Remove accents
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    # Lowercase, collapse whitespace, strip
    cleaned = re.sub(r"\s+", " ", ascii_text.lower()).strip()
    # Remove common noise words
    for noise in ["(h/f)", "(f/h)", "(m/f)", "(m/w)", "- cdi", "- cdd", "(remote)"]:
        cleaned = cleaned.replace(noise, "")
    return cleaned.strip()


def compute_fingerprint(
    company_domain: str,
    title: str,
    location: str | None = None,
) -> str:
    """
    Compute a stable SHA-256 fingerprint for a job posting.
    Same job reposted under different ATS IDs will get the same fingerprint.
    """
    parts = [
        normalize_text(company_domain),
        normalize_text(title),
        normalize_text(location or ""),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()
