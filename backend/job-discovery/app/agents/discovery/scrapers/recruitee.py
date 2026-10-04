"""
Recruitee — API publique du site carrière, sans clé.

    GET  https://{entreprise}.recruitee.com/api/offers/
    POST https://{entreprise}.recruitee.com/api/offers/{slug}/candidates

C'est l'un des rares ATS dont le site carrière accepte une candidature par
API sans la clé de l'employeur : Alice peut donc l'envoyer elle-même. Par
défaut l'employeur exige nom, e-mail, téléphone et CV ; il peut ajouter des
questions. Une offre avec des questions obligatoires n'est pas envoyée par
l'API (on ne répond pas à la place du candidat) : elle passe par le
formulaire, comme les autres.
"""

import html
import logging
import re

import httpx

from app.agents.discovery.scrapers.base import BaseScraper, ScrapedJob
from app.config import settings

logger = logging.getLogger(__name__)

OFFERS_URL = "https://{slug}.recruitee.com/api/offers/"
APPLY_URL = "https://{slug}.recruitee.com/api/offers/{offer}/candidates"


def _text(raw: str | None) -> str:
    """HTML du site carrière → texte lisible pour le qualifieur."""
    s = re.sub(r"<\s*(br|/p|/li|/h\d)\s*/?>", "\n", raw or "", flags=re.I)
    s = re.sub(r"<li[^>]*>", "• ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(s)).strip()


def required_questions(offer: dict) -> list[str]:
    return [
        q.get("body") or "question"
        for q in (offer.get("open_questions") or [])
        if isinstance(q, dict) and q.get("required")
    ]


def to_scraped_job(slug: str, offer: dict) -> ScrapedJob:
    location = offer.get("location") or ", ".join(
        p for p in (offer.get("city"), offer.get("country")) if p
    )
    parts = [_text(offer.get("description")), _text(offer.get("requirements"))]
    questions = required_questions(offer)
    return ScrapedJob(
        external_id=f"recruitee:{slug}:{offer.get('id')}",
        title=(offer.get("title") or "Offre").strip()[:500],
        source_url=offer.get("careers_url") or f"https://{slug}.recruitee.com/o/{offer.get('slug')}",
        description_raw="\n\n".join(p for p in parts if p),
        location=location or None,
        department=offer.get("department"),
        apply_url=offer.get("careers_apply_url") or offer.get("careers_url"),
        updated_at=offer.get("updated_at") or offer.get("created_at"),
        extra={
            "company_name": offer.get("company_name"),
            "employment_type": offer.get("employment_type_code"),
            "remote": offer.get("remote"),
            "hybrid": offer.get("hybrid"),
            "country_code": offer.get("country_code"),
            "recruitee": {"company": slug, "offer": offer.get("slug")},
            "required_questions": questions,
            # Le CV désactivé par l'employeur : rien à transmettre d'adapté.
            "cv_option": offer.get("options_cv"),
        },
    )


class RecruiteeScraper(BaseScraper):
    def platform_name(self) -> str:
        return "recruitee"

    async def scrape(self, slug: str) -> list[ScrapedJob]:
        async with httpx.AsyncClient(
            timeout=settings.scrape_request_timeout,
            headers={"User-Agent": settings.scrape_user_agent},
        ) as client:
            try:
                resp = await client.get(OFFERS_URL.format(slug=slug))
            except httpx.HTTPError as e:
                logger.warning("Recruitee '%s' injoignable : %s", slug, e)
                return []
        if resp.status_code != 200:
            return []
        offers = (resp.json() or {}).get("offers") or []
        return [
            to_scraped_job(slug, o) for o in offers
            if isinstance(o, dict) and o.get("status", "published") == "published"
        ]


# ── Envoi ──────────────────────────────────────────────────────────────────


class RecruiteeError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail


async def send_application(
    *, company: str, offer: str, name: str, email: str, phone: str | None,
    resume: bytes, resume_name: str, cover_letter: str | None,
) -> dict:
    """Dépose la candidature sur le site carrière. Lève RecruiteeError."""
    data = {"candidate[name]": name, "candidate[email]": email}
    if phone:
        data["candidate[phone]"] = phone
    if cover_letter:
        data["candidate[cover_letter]"] = cover_letter
    files = {"candidate[cv]": (resume_name or "CV.pdf", resume, "application/pdf")}
    async with httpx.AsyncClient(timeout=60, headers={"User-Agent": settings.scrape_user_agent}) as client:
        resp = await client.post(APPLY_URL.format(slug=company, offer=offer), data=data, files=files)
    if resp.status_code not in (200, 201, 202):
        raise RecruiteeError(resp.status_code, resp.text[:300])
    try:
        return resp.json() or {}
    except ValueError:
        return {}
