"""
Connecteur La bonne alternance — API Apprentissage de l'État.

C'est aujourd'hui la seule source officielle où un service tiers peut
TRANSMETTRE une candidature, pas seulement lire des offres : `POST
/job/v1/apply` remet le CV et le message au recruteur. Pour une recherche
d'alternance, c'est ce qui permet de tenir la promesse « Alice postule ».

On n'ingère que les offres qui portent un `apply.recipient_id` — celles
auxquelles l'API sait transmettre. Les autres (offres de partenaires, dont
France Travail) se postulent ailleurs, et France Travail les fournit déjà.

Schémas vérifiés contre l'OpenAPI publié par mission-apprentissage
(api-apprentissage, shared/src/openapi).
"""

import base64
import logging
import re

import httpx

from app.agents.discovery.scrapers.base import ScrapedJob
from app.config import settings

logger = logging.getLogger(__name__)

#: Employeurs propres à cette source, jamais confondus avec un domaine réel.
LBA_DOMAIN_SUFFIX = ".labonnealternance.local"

#: Taille maximale du CV acceptée par l'API (~3 Mo une fois en base64).
MAX_ATTACHMENT_CHARS = 4_215_276

_REMOTE = {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite"}


class LbaError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.lba_api_key.strip()}",
        "Accept": "application/json",
    }


def _clean(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _join(value) -> str:
    """Les champs texte de l'API sont parfois des listes."""
    if isinstance(value, list):
        return "\n".join(_clean(v) for v in value if v)
    return str(value or "").strip()


def to_scraped_job(item: dict) -> ScrapedJob | None:
    """Une offre de l'API vers notre format commun. None si on ne peut pas y postuler."""
    apply = item.get("apply") or {}
    recipient = apply.get("recipient_id")
    if not recipient:
        return None

    ident = item.get("identifier") or {}
    offer = item.get("offer") or {}
    contract = item.get("contract") or {}
    workplace = item.get("workplace") or {}
    location = (workplace.get("location") or {}).get("address") or ""

    skills = [_clean(s) for s in (offer.get("desired_skills") or []) if s]
    acquired = [_clean(s) for s in (offer.get("to_be_acquired_skills") or []) if s]
    diploma = (offer.get("target_diploma") or {}).get("label")
    parts = [
        _join(offer.get("description")),
        f"Niveau visé : {diploma}" if diploma else "",
        "Compétences attendues : " + ", ".join(skills) if skills else "",
        "Ce que tu apprendras : " + ", ".join(acquired) if acquired else "",
        _join(offer.get("access_conditions")),
        f"L'entreprise : {_join(workplace.get('description'))}" if workplace.get("description") else "",
    ]
    duration = contract.get("duration")
    if duration:
        parts.append(f"Durée du contrat : {duration} mois")

    remote = _REMOTE.get(contract.get("remote") or "", "unknown")
    title = _clean(offer.get("title")) or "Offre en alternance"
    company = _clean(workplace.get("brand") or workplace.get("name") or workplace.get("legal_name"))
    url = apply.get("url") or ""

    return ScrapedJob(
        external_id=f"lba:{ident.get('id') or ident.get('partner_job_id') or recipient}",
        title=title[:500],
        source_url=url,
        description_raw="\n\n".join(p for p in parts if p),
        location=_clean(location),
        department=None,
        apply_url=url,
        updated_at=((offer.get("publication") or {}).get("creation")),
        extra={
            "company_name": company,
            "siret": workplace.get("siret"),
            "website": workplace.get("website"),
            "rome_codes": offer.get("rome_codes") or [],
            "contact": {k: v for k, v in {
                "lba_recipient_id": recipient,
                "apply_url": url,
                "phone": apply.get("phone"),
                # Questions du recruteur : l'API attend une réponse à chacune.
                "questions": offer.get("to_applicant_questions") or None,
            }.items() if v},
            "parsed": {
                "tech_stack": skills,
                "experience_years_required": 0.0,
                "contract_type": "alternance",
                "remote_policy": remote,
                "salary_min": None,
                "salary_max": None,
                "summary_french": title,
                "source": "labonnealternance",
                # Qui publie : le code NAF trahit l'école qui recrute des élèves.
                "employer": {k: v for k, v in {
                    "naf": (((workplace.get("domain") or {}).get("naf") or {}).get("code")),
                    "naf_label": (((workplace.get("domain") or {}).get("naf") or {}).get("label")),
                    "siret": workplace.get("siret"),
                    "legal_name": workplace.get("legal_name"),
                }.items() if v},
            },
        },
    )


async def search(
    *,
    romes: list[str] | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius: int = 60,
    departements: list[str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[ScrapedJob]:
    """Les offres d'alternance candidatables. Lève LbaError sur refus de l'API."""
    params: list[tuple[str, str]] = []
    if romes:
        params.append(("romes", ",".join(dict.fromkeys(romes))))
    if latitude is not None and longitude is not None:
        params += [("latitude", str(latitude)), ("longitude", str(longitude)),
                   ("radius", str(max(0, min(200, radius))))]
    for d in departements or []:
        params.append(("departements", d))

    own = client is None
    client = client or httpx.AsyncClient(timeout=30)
    try:
        res = await client.get(f"{settings.lba_api_url}/job/v1/search",
                               params=params, headers=_headers())
    finally:
        if own:
            await client.aclose()
    if res.status_code != 200:
        raise LbaError(res.status_code, res.text[:300])

    payload = res.json() or {}
    jobs = [j for j in (to_scraped_job(i) for i in payload.get("jobs") or []) if j]
    logger.info("La bonne alternance : %d offres, %d candidatables",
                len(payload.get("jobs") or []), len(jobs))
    return jobs


async def geocode(city: str) -> tuple[float, float] | None:
    """Ville → (latitude, longitude) via la Base Adresse Nationale. None si inconnue."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                "https://api-adresse.data.gouv.fr/search/",
                params={"q": city, "type": "municipality", "limit": 1},
            )
        features = res.json().get("features") or []
        if not features:
            return None
        lon, lat = features[0]["geometry"]["coordinates"]
        return float(lat), float(lon)
    except Exception as e:  # noqa: BLE001 — sans géocodage, recherche nationale
        logger.info("Géocodage impossible pour %s : %s", city, e)
        return None


# ── Envoi ──────────────────────────────────────────────────────────────────


def _split_name(full_name: str) -> tuple[str, str]:
    parts = _clean(full_name).split(" ")
    if len(parts) == 1:
        return parts[0][:50], parts[0][:50]
    return parts[0][:50], " ".join(parts[1:])[:50]


def build_application(
    *,
    recipient_id: str,
    full_name: str,
    email: str,
    phone: str,
    resume: bytes,
    resume_name: str,
    message: str,
) -> dict:
    """Le corps de `POST /job/v1/apply`, validé avant l'appel."""
    first, last = _split_name(full_name)
    name = resume_name if resume_name.lower().endswith((".pdf", ".docx")) else f"{resume_name}.pdf"
    content = "data:application/pdf;base64," + base64.b64encode(resume).decode()
    if len(content) > MAX_ATTACHMENT_CHARS:
        raise ValueError("CV trop lourd pour La bonne alternance (3 Mo au plus)")
    return {
        "recipient_id": recipient_id,
        "applicant_first_name": first,
        "applicant_last_name": last,
        "applicant_email": email,
        "applicant_phone": phone,
        "applicant_attachment_name": name,
        "applicant_attachment_content": content,
        "applicant_message": message[:5000] if message else None,
    }


async def send_application(body: dict) -> str:
    """Transmet la candidature. Renvoie l'identifiant LBA. Lève LbaError."""
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            f"{settings.lba_api_url}/job/v1/apply",
            json={k: v for k, v in body.items() if v is not None},
            headers=_headers(),
        )
    if res.status_code not in (200, 201, 202):
        raise LbaError(res.status_code, res.text[:300])
    return str((res.json() or {}).get("id") or "")
