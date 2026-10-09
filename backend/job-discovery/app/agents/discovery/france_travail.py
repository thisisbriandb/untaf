"""
Connecteur France Travail — API « Offres d'emploi v2 ».

Source officielle, gratuite, et sans les problèmes de tolérance des scrapers :
c'est la voie légitime pour couvrir le marché français, là où les ATS ne
donnent accès qu'aux entreprises qu'on a explicitement référencées.

Authentification OAuth2 client_credentials, jeton mis en cache jusqu'à son
expiration.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from app.agents.discovery.contact_extract import find_apply_email, find_apply_url
from app.agents.discovery.scrapers.base import ScrapedJob
from app.config import settings

logger = logging.getLogger(__name__)

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
API_BASE = "https://api.francetravail.io/partenaire/offresdemploi/v2"

#: Le scope doit contenir `application_<client_id>` en plus des scopes d'API.
#: Ce n'est documenté nulle part clairement, mais toutes les implémentations
#: qui fonctionnent le font, et l'omettre fait échouer l'échange de jeton.
def build_scope(client_id: str) -> str:
    return f"api_offresdemploiv2 o2dsoffre application_{client_id}"

#: L'API plafonne à 150 résultats par appel et 3149 au total sur une recherche.
PAGE_SIZE = 150
MAX_RESULTS = 1000

#: Codes ROME par famille de métier, vérifiés contre l'API en production.
#:
#: Interroger par code ROME plutôt que par mots-clés change tout : `motsCles`
#: combine les termes en ET, donc « developpeur web python react » ne ramène
#: que 37 offres là où le seul métier « développement informatique » en compte
#: plus de 2000. On élargit ici, et c'est le moteur de matching qui filtre —
#: c'est précisément son rôle.
ROME_BY_FAMILY: dict[str, list[str]] = {
    "software": ["M1805", "M1802", "M1806", "M1810", "M1803"],
    "data": ["M1805", "M1403", "M1401"],
    "product": ["M1806", "M1707"],
    "design": ["E1205", "E1104"],
    "marketing": ["M1705", "E1103"],
    "sales": ["D1407", "D1402", "M1707"],
    "support": ["D1408", "M1607"],
    "hr": ["M1502", "M1501"],
    "finance": ["M1203", "M1201"],
    "ops": ["N1303", "M1607"],
    "construction": ["F1201", "F1106", "F1703", "F1602"],
    "education": ["K2107", "K2106", "K2111"],
}

#: Correspondance des types de contrat France Travail vers les nôtres.
CONTRACT_MAP = {
    "CDI": "cdi",
    "CDD": "cdd",
    "MIS": "interim",       # mission d'intérim
    "SAI": "cdd",           # saisonnier
    "FRA": "freelance",     # franchise
    "LIB": "freelance",     # profession libérale
    "REP": "freelance",
    "TTI": "interim",
    "DDI": "cdd",           # CDD insertion
    "DIN": "cdi",           # CDI intérimaire
}


class FranceTravailAuthError(RuntimeError):
    """Les identifiants sont refusés — inutile de réessayer sans les corriger."""


class FranceTravailClient:
    """Client API avec jeton mis en cache."""

    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        self.client_id = client_id or settings.france_travail_client_id
        self.client_secret = client_secret or settings.france_travail_client_secret
        self._token: str | None = None
        self._expires_at: datetime | None = None
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def _get_token(self) -> str:
        async with self._lock:
            now = datetime.now(timezone.utc)
            if self._token and self._expires_at and now < self._expires_at:
                return self._token

            async with httpx.AsyncClient(timeout=settings.scrape_request_timeout) as client:
                resp = await client.post(
                    TOKEN_URL,
                    params={"realm": "/partenaire"},
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "scope": build_scope(self.client_id),
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

            if resp.status_code in (400, 401):
                # `invalid_client` porte sur la paire client_id/secret, pas sur
                # le scope — un scope invalide renverrait `invalid_scope`. Le
                # message oriente donc vers le portail plutôt que vers le code.
                hint = ""
                if "invalid_client" in resp.text:
                    hint = (
                        " — la paire client_id/secret n'est pas reconnue. "
                        "Vérifie sur francetravail.io que l'application est "
                        "active, abonnée à « Offres d'emploi v2 », et que la "
                        "clé secrète n'a pas été régénérée."
                    )
                raise FranceTravailAuthError(
                    f"Identifiants refusés par France Travail "
                    f"({resp.status_code}){hint} : {resp.text[:160]}"
                )
            resp.raise_for_status()

            payload = resp.json()
            self._token = payload["access_token"]
            # Marge de 60 s pour ne jamais présenter un jeton qui vient d'expirer.
            self._expires_at = now + timedelta(seconds=payload.get("expires_in", 1500) - 60)
            return self._token

    async def offer_exists(self, offer_id: str) -> bool | None:
        """
        L'offre est-elle toujours en ligne ? True / False, ou None si on ne
        peut pas le savoir (API injoignable) — l'appelant décide alors.
        """
        try:
            token = await self._get_token()
            async with httpx.AsyncClient(timeout=settings.scrape_request_timeout) as client:
                resp = await client.get(
                    f"{API_BASE}/offres/{offer_id}",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("Vérification de l'offre %s impossible : %s", offer_id, e)
            return None
        if resp.status_code == 200:
            return True
        if resp.status_code in (204, 404, 410):
            return False
        return None

    async def search(self, **params) -> tuple[list[dict], int]:
        """
        Une page de résultats.

        Renvoie (offres, total). L'API répond 206 quand elle tronque, ce qui
        est le cas nominal et non une erreur.
        """
        token = await self._get_token()

        async with httpx.AsyncClient(timeout=settings.scrape_request_timeout) as client:
            resp = await client.get(
                f"{API_BASE}/offres/search",
                params=params,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
            )

        if resp.status_code == 204:
            return [], 0
        if resp.status_code == 401:
            self._token = None
            raise FranceTravailAuthError("Jeton refusé par l'API des offres.")
        resp.raise_for_status()

        data = resp.json()
        results = data.get("resultats") or []

        # « Content-Range: offres 0-149/3210 » — le total est après le slash.
        total = len(results)
        content_range = resp.headers.get("Content-Range", "")
        if "/" in content_range:
            try:
                total = int(content_range.rsplit("/", 1)[1])
            except ValueError:
                pass

        return results, total


# ── Normalisation ──────────────────────────────────────────────────────────

_EXPERIENCE_RE = re.compile(r"(\d+)\s*[Aa]n")
_REMOTE_RE = re.compile(r"t[ée]l[ée]travail|remote|distanciel", re.I)
_FULL_REMOTE_RE = re.compile(r"t[ée]l[ée]travail\s+(?:complet|total|100)|100\s*%\s*t[ée]l[ée]travail|full\s*remote", re.I)


def to_description_parsed(offer: dict) -> dict:
    """
    Construit la qualification directement depuis les champs de l'API.

    France Travail livre déjà le type de contrat, l'expérience requise, le
    salaire et les compétences. Repasser un LLM là-dessus coûterait un appel
    par offre pour un résultat moins fiable que la donnée d'origine.
    """
    competences = [
        _clean(c.get("libelle"))
        for c in (offer.get("competences") or [])
        if isinstance(c, dict) and c.get("libelle")
    ]

    years = None
    if offer.get("experienceLibelle"):
        m = _EXPERIENCE_RE.search(offer["experienceLibelle"])
        if m:
            years = float(m.group(1))
    # « D » = débutant accepté : aucune expérience exigée.
    if offer.get("experienceExige") == "D" and years is None:
        years = 0.0

    haystack = " ".join(filter(None, [
        offer.get("description", ""), offer.get("dureeTravailLibelle", ""),
    ]))
    if _FULL_REMOTE_RE.search(haystack):
        remote = "remote"
    elif _REMOTE_RE.search(haystack):
        remote = "hybrid"
    else:
        remote = "unknown"

    contract = CONTRACT_MAP.get(offer.get("typeContrat"), "unknown")
    if offer.get("alternance"):
        contract = "alternance"

    salaire = (offer.get("salaire") or {}).get("libelle") or ""
    amounts = [int(float(a)) for a in re.findall(r"(\d{4,6})(?:\.\d+)?", salaire)]
    annual = [a for a in amounts if 15000 <= a <= 300000]

    return {
        "tech_stack": competences,
        "experience_years_required": years,
        "contract_type": contract,
        "remote_policy": remote,
        "salary_min": min(annual) if annual else None,
        "salary_max": max(annual) if len(annual) > 1 else None,
        "summary_french": _clean(offer.get("intitule")),
        "source": "france_travail",
    }


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def to_scraped_job(offer: dict) -> ScrapedJob:
    """Une offre France Travail vers notre format commun."""
    lieu = offer.get("lieuTravail") or {}
    entreprise = offer.get("entreprise") or {}
    origine = offer.get("origineOffre") or {}

    # Les compétences déclarées enrichissent la description : le qualifieur y
    # trouve la matière qu'un simple intitulé ne donne pas.
    competences = [
        _clean(c.get("libelle"))
        for c in (offer.get("competences") or [])
        if isinstance(c, dict) and c.get("libelle")
    ]

    parts = [_clean(offer.get("description"))]
    if offer.get("experienceLibelle"):
        parts.append(f"Expérience : {_clean(offer['experienceLibelle'])}")
    if (offer.get("salaire") or {}).get("libelle"):
        parts.append(f"Salaire : {_clean(offer['salaire']['libelle'])}")
    if offer.get("dureeTravailLibelle"):
        parts.append(f"Temps de travail : {_clean(offer['dureeTravailLibelle'])}")
    if competences:
        parts.append("Compétences attendues : " + ", ".join(competences))

    # Le bloc contact décide du canal de candidature : un courriel rend
    # l'offre candidatable directement, une urlPostulation mène au formulaire
    # de l'employeur. Sans l'un ni l'autre, il faut passer par le portail
    # candidat authentifié — donc pas d'automatisation possible.
    contact = offer.get("contact") or {}
    # Le champ `courriel` contient parfois une consigne en clair plutôt qu'une
    # adresse (« Pour postuler, utiliser le lien suivant : … »). Sans contrôle,
    # le verdict d'automatisation se croyait capable d'envoyer un email.
    #
    # Une adresse peut néanmoins s'y cacher (« Envoyer CV à rh@acme.fr »), ou
    # dans les coordonnées, ou dans la description : on la cherche partout,
    # par ordre de confiance, plutôt que de déclarer le canal vide.
    raw_email = (contact.get("courriel") or "").strip()
    coordinates = " ".join(
        str(contact.get(k) or "") for k in ("coordonnees1", "coordonnees2", "coordonnees3")
    )
    email = (
        find_apply_email(raw_email, coordinates)
        or find_apply_email(offer.get("description"), min_score=2)
    )
    apply_url = contact.get("urlPostulation") or find_apply_url(raw_email, coordinates)
    if raw_email and not email:
        logger.debug("Champ courriel non exploitable, ignoré : %s", raw_email[:60])

    contact_info = {
        k: v for k, v in {
            "email": email,
            "name": contact.get("nom"),
            "phone": contact.get("telephone"),
            "apply_url": apply_url,
            "instructions": contact.get("coordonnees1") or (raw_email if not email else None),
        }.items() if v
    }

    return ScrapedJob(
        external_id=str(offer.get("id") or ""),
        title=_clean(offer.get("intitule")) or "Offre sans intitulé",
        source_url=origine.get("urlOrigine") or "",
        description_raw="\n\n".join(p for p in parts if p),
        location=_clean(lieu.get("libelle")),
        department=_clean(offer.get("romeLibelle")),
        apply_url=apply_url or origine.get("urlOrigine") or "",
        updated_at=offer.get("dateActualisation") or offer.get("dateCreation"),
        extra={
            "company_name": _clean(entreprise.get("nom")),
            "contract_type": CONTRACT_MAP.get(offer.get("typeContrat"), "unknown"),
            "contract_label": _clean(offer.get("typeContratLibelle")),
            "rome_code": offer.get("romeCode"),
            "alternance": bool(offer.get("alternance")),
            "postal_code": lieu.get("codePostal"),
            "commune": lieu.get("commune"),
            "competences": competences,
            "experience_required": offer.get("experienceExige"),
            "salary_label": (offer.get("salaire") or {}).get("libelle"),
            "sector": _clean(offer.get("secteurActiviteLibelle")),
            "contact": contact_info,
            # Qualification déterministe : l'offre est matchable dès son
            # enregistrement, sans passer par le qualifieur LLM.
            "parsed": {
                **to_description_parsed(offer),
                # Qui publie : le secteur trahit l'école qui recrute des élèves.
                "employer": {k: v for k, v in {
                    "naf": offer.get("codeNAF"),
                    "sector_code": offer.get("secteurActivite"),
                    "sector": _clean(offer.get("secteurActiviteLibelle")),
                    "about": _clean(entreprise.get("description"))[:500] if entreprise.get("description") else None,
                }.items() if v},
            },
        },
    )


async def fetch_offers(
    *,
    rome_codes: list[str] | None = None,
    keywords: str | None = None,
    departements: list[str] | None = None,
    contract_types: list[str] | None = None,
    extra_params: dict | None = None,
    max_results: int = MAX_RESULTS,
    client: FranceTravailClient | None = None,
) -> list[ScrapedJob]:
    """
    Récupère les offres, en paginant.

    On privilégie les codes ROME aux mots-clés : ils cadrent le métier sans
    exclure des offres sur une différence de vocabulaire. Le tri fin revient
    au moteur de matching.
    """
    client = client or FranceTravailClient()
    if not client.configured:
        logger.warning("Identifiants France Travail absents — source ignorée.")
        return []

    base_params: dict[str, str] = {"sort": "1"}  # 1 = par date de création
    if extra_params:
        base_params.update({k: v for k, v in extra_params.items() if v})
    if rome_codes:
        base_params["codeROME"] = ",".join(sorted(set(rome_codes))[:10])
    elif keywords:
        base_params["motsCles"] = keywords[:200]
    if departements:
        base_params["departement"] = ",".join(departements[:10])
    if contract_types:
        codes = [c for c, mapped in CONTRACT_MAP.items() if mapped in contract_types]
        if codes:
            base_params["typeContrat"] = ",".join(sorted(set(codes)))

    jobs: list[ScrapedJob] = []
    offset = 0

    while offset < max_results:
        end = min(offset + PAGE_SIZE, max_results) - 1
        try:
            results, total = await client.search(**base_params, range=f"{offset}-{end}")
        except FranceTravailAuthError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("France Travail search failed at offset %d: %s", offset, e)
            break

        if not results:
            break

        jobs.extend(to_scraped_job(o) for o in results)
        offset += len(results)

        if offset >= total:
            break

        # Quota annoncé : 10 appels/seconde. On reste loin de la limite.
        await asyncio.sleep(0.15)

    logger.info("France Travail : %d offres récupérées", len(jobs))
    return jobs
