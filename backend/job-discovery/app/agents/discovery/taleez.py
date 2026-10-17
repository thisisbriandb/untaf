"""
Offres publiées sur Taleez (taleez.com/apply/…) : PME et ETI françaises.

Collecte : le sitemap public des offres (`sitemap-job.xml`, environ 10 000
offres), puis la page de chaque offre nouvelle. Tout ce qu'il faut est dans
la page : le JSON-LD de l'offre (titre, date, lieu, contrat, employeur) et
l'état Angular (`ng-state`) qui décrit le formulaire de candidature. Le
robots.txt autorise ces pages (il n'interdit que /api/, /files/…, et accueille
même les robots d'IA) et n'émet pas de Content-Signal (vérifié le 14/10/2026).

Réutilisation : les mentions légales de Taleez interdisent la reproduction
des contenus du site sans accord écrit. Les offres servent donc à Alice pour
le candidat (correspondance, préparation, envoi), toujours avec le lien vers
la page Taleez, mais ne sont PAS republiées sur Alice Community.

Candidature : le formulaire public n'a ni compte ni captcha. Il envoie le CV
(`/api/public/upload-file-doc`), puis la candidature en JSON
(`/api/public/apply`) : identité et réponses aux questions de l'employeur.
Taleez écrit ensuite au candidat : la candidature n'est transmise qu'après un
clic sur le lien de confirmation. Ce lien arrive sur l'adresse de suivi
d'Alice, qui le transfère au candidat : c'est lui qui valide.

Comme pour Recruitee, Alice ne répond jamais à la place du candidat : une
offre qui exige autre chose que le CV et un message (niveau d'études,
disponibilité, salaire, civilité…) passe par l'extension.

Politesse : une collecte par jour ; seules les offres nouvelles sont lues,
une par seconde, au plus `MAX_READS_PER_RUN` par passage.
"""

import asyncio
import html as html_lib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.agents.discovery.deduplicator import compute_fingerprint
from app.agents.discovery.france_travail_task import (
    ANONYMOUS_NAME, _get_or_create_company, _slugify,
)
from app.agents.discovery.qualification import heuristic_qualify
from app.database import async_session
from app.models.job_posting import (
    ApplyChannel,
    ApplyComplexity,
    ContractType,
    JobPosting,
    PostingStatus,
    RemotePolicy,
)

logger = logging.getLogger(__name__)

BASE = "https://taleez.com"
SITEMAP = f"{BASE}/sitemap-job.xml"
UPLOAD_URL = f"{BASE}/api/public/upload-file-doc"
APPLY_URL = f"{BASE}/api/public/apply"
#: Préfixe d'`external_id` : suivi du code court de l'offre dans le sitemap.
PREFIX = "taleez:"
DOMAIN_SUFFIX = ".taleez.source"
OFFER_URL = re.compile(r"^https://taleez\.com/apply/[A-Za-z0-9-]+$")
PAUSE_S = 1.0
#: Premier passage : ~10 000 offres. On les lit sur plusieurs jours.
MAX_READS_PER_RUN = 1500
USER_AGENT = "AliceBot/1.0 (+https://www.alice-agent.fr ; offres d'emploi, une visite par jour)"

_LD = re.compile(r'<script id="jobPostingSnippet"[^>]*>(.*?)</script>', re.DOTALL)
_STATE = re.compile(r'<script id="ng-state"[^>]*>(.*?)</script>', re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")
_SPONTANEOUS = re.compile(r"candidature spontan", re.IGNORECASE)

#: Questions auxquelles Alice sait répondre avec le dossier du candidat.
_CV = re.compile(r"^\s*(cv|curriculum)", re.IGNORECASE)
_LETTER_DOC = re.compile(r"lettre|motivation|cover", re.IGNORECASE)
_MESSAGE = re.compile(r"commentaire|message|motivation|pr[ée]sentez|cover", re.IGNORECASE)


@dataclass
class TaleezForm:
    """Ce qu'il faut pour remplir le formulaire, et ce qui en empêche l'envoi."""
    token: str
    cv: int | None = None
    letter_doc: int | None = None
    message: int | None = None
    message_required: bool = False
    #: Questions obligatoires auxquelles seul le candidat peut répondre.
    blocking: list[str] = field(default_factory=list)

    @property
    def sendable(self) -> bool:
        return self.cv is not None and not self.blocking


@dataclass
class TaleezOffer:
    #: Code court du sitemap (« fmudc »), ou jeton de l'offre si elle a été collée.
    code: str
    url: str
    title: str
    company: str
    contract: ContractType
    location: str | None
    description: str
    posted: datetime | None
    form: TaleezForm
    #: Identifiant Taleez de l'offre : le même quel que soit le lien suivi.
    job_id: int | None = None


def _text(fragment: str | None) -> str:
    s = re.sub(r"<\s*(br|/p|/li|/h\d)\s*/?>", "\n", fragment or "", flags=re.IGNORECASE)
    s = re.sub(r"<li[^>]*>", "• ", s, flags=re.IGNORECASE)
    s = html_lib.unescape(_TAGS.sub("", s)).replace("\xa0", " ")
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", s)).strip()


def contract_of(code: str | None, title: str) -> ContractType:
    """Le code Taleez (CDI, CDD, APPRENTICESHIP…), corrigé par l'intitulé."""
    t = title.lower()
    if re.search(r"apprenti|alternan", t) or code == "APPRENTICESHIP":
        return ContractType.ALTERNANCE
    if re.search(r"\bstage|stagiaire", t) or code in ("INTERNSHIP", "STUDENT"):
        return ContractType.STAGE
    return {
        "CDI": ContractType.CDI, "CDD": ContractType.CDD,
        "FREELANCE": ContractType.FREELANCE, "INTERIM": ContractType.INTERIM,
    }.get(code or "", ContractType.UNKNOWN)


def read_form(job: dict) -> TaleezForm:
    """Les questions de l'offre → ce qu'Alice sait remplir, et ce qui bloque."""
    form = TaleezForm(token=job.get("token") or "")
    for q in sorted(job.get("questions") or [], key=lambda q: q.get("order") or 0):
        if not q.get("displayed", True):
            continue
        qid, kind, label = q.get("id"), q.get("type"), (q.get("value") or "").strip()
        required = bool(q.get("required"))
        if kind == "DOC" and _CV.search(label) and form.cv is None:
            form.cv = qid
        elif kind == "DOC" and _LETTER_DOC.search(label) and form.letter_doc is None and not required:
            # Lettre en fichier, facultative : la lettre part dans le message.
            form.letter_doc = qid
        elif kind in ("TEXTAREA", "INPUT") and _MESSAGE.search(label) and form.message is None:
            form.message, form.message_required = qid, required
        elif required:
            form.blocking.append(label or kind or "question")
    if form.cv is None:
        form.blocking.insert(0, "CV")
    return form


def parse_offer(code: str, url: str, page: str) -> TaleezOffer | None:
    """La page d'une offre → l'offre, ou None si elle n'est pas (ou plus) publique."""
    ld_m, st_m = _LD.search(page), _STATE.search(page)
    if not ld_m or not st_m:
        return None
    try:
        ld = json.loads(ld_m.group(1))
        job = (json.loads(st_m.group(1)) or {}).get("DATA_QUESTIONS") or {}
    except ValueError:
        return None
    if job.get("jobStatus") != "PUBLISHED" or "PUBLIC" not in (job.get("visibility") or "") \
            or job.get("redirect") or job.get("pendingValidation"):
        return None
    title = (ld.get("title") or job.get("label") or "").strip()
    # La page « candidature spontanée » d'un employeur n'est pas une offre.
    if not title or _SPONTANEOUS.search(title):
        return None
    org = ld.get("hiringOrganization") or {}
    company = (org.get("name") if isinstance(org, dict) else None) or job.get("company") or ""
    place = ld.get("jobLocation") or {}
    if isinstance(place, list):
        place = place[0] if place else {}
    addr = (place.get("address") or {}) if isinstance(place, dict) else {}
    if (addr.get("addressCountry") or "FR").upper() not in ("FR", "FRANCE"):
        return None  # Alice cherche en France
    location = " ".join(p for p in (addr.get("postalCode"), addr.get("addressLocality")) if p) or None
    posted = None
    try:
        posted = datetime.strptime(ld.get("datePosted") or "", "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        pass
    description = "\n\n".join(p for p in (_text(ld.get("description")), _text(ld.get("qualifications"))) if p)
    return TaleezOffer(
        code=code,
        url=url,
        title=title[:500],
        company=company.strip(),
        contract=contract_of(job.get("contract"), title),
        location=location,
        description=description[:12000],
        posted=posted,
        form=read_form(job),
        job_id=job.get("id"),
    )


def parse_sitemap(xml: str) -> dict[str, str]:
    """Code court de l'offre → son adresse."""
    out: dict[str, str] = {}
    for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml):
        if OFFER_URL.match(loc):
            out[loc.rsplit("/", 1)[-1]] = loc
    return out


# ── Enregistrement ────────────────────────────────────────────────────────


def _channel(o: TaleezOffer) -> tuple[ApplyChannel, ApplyComplexity, dict]:
    f = o.form
    if f.sendable:
        return ApplyChannel.TALEEZ_API, ApplyComplexity.SIMPLE, {
            "apply_url": o.url,
            "taleez": {"token": f.token, "cv": f.cv, "message": f.message,
                       "message_required": f.message_required},
        }
    # Questions personnelles obligatoires : le candidat répond lui-même,
    # avec l'extension.
    return ApplyChannel.WEB_FORM, ApplyComplexity.MEDIUM, {
        "apply_url": o.url, "questions": f.blocking,
    }


def _fingerprint(domain: str, o: TaleezOffer) -> str:
    return compute_fingerprint(domain, o.title, o.location,
                               external_id=f"{PREFIX}{o.job_id}" if o.job_id else PREFIX + o.code)


async def persist(offers: list[TaleezOffer], from_sitemap: bool = True) -> int:
    saved = 0
    now = datetime.now(UTC)
    async with async_session() as session:
        for o in offers:
            company = await _get_or_create_company(session, o.company, suffix=DOMAIN_SUFFIX)
            text = f"{o.title}\n\n{o.description}"
            parsed = heuristic_qualify(o.title, text)
            parsed["contract_type"] = o.contract.value
            parsed["source"] = {"name": "Taleez", "republish": False,
                                "posted": o.posted.isoformat() if o.posted else None}
            channel, complexity, contact = _channel(o)
            values = dict(
                title=o.title,
                description_raw=text,
                description_parsed=parsed,
                location=o.location,
                apply_url=o.url,
                apply_channel=channel,
                apply_complexity=complexity,
                contact_json=contact,
                contract_type=o.contract,
                remote_policy=RemotePolicy.ONSITE,
                tech_stack=parsed.get("tech_stack") or [],
                status=PostingStatus.ACTIVE,
            )
            await session.execute(
                pg_insert(JobPosting).values(
                    company_id=company.id,
                    external_id=PREFIX + o.code,
                    fingerprint=_fingerprint(company.domain, o),
                    source_url=o.url,
                    **values,
                ).on_conflict_do_update(
                    index_elements=["fingerprint"],
                    # Une offre collée par un candidat puis trouvée dans le
                    # sitemap ne fait qu'une : elle prend le code du sitemap.
                    set_={**values, "last_seen_at": now,
                          **({"external_id": PREFIX + o.code} if from_sitemap else {})},
                )
            )
            saved += 1
        await session.commit()
    return saved


async def collect(client: httpx.AsyncClient | None = None, limit: int | None = MAX_READS_PER_RUN) -> dict:
    """Collecte quotidienne. Ne lève pas : renvoie un rapport."""
    own = client is None
    client = client or httpx.AsyncClient(
        timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT},
    )
    try:
        res = await client.get(SITEMAP)
        if res.status_code != 200:
            return {"ok": False, "reason": f"sitemap {res.status_code}"}
        listed = parse_sitemap(res.text)
        if not listed:
            # Sitemap vide ou changé de forme : ne rien fermer sur cette base.
            return {"ok": False, "reason": "sitemap sans offre"}

        async with async_session() as session:
            known = set((await session.execute(
                select(JobPosting.external_id).where(JobPosting.external_id.like(f"{PREFIX}%"))
            )).scalars().all())
        # Le sitemap ne date pas les offres : on lit les nouvelles seulement.
        fresh = [c for c in listed if PREFIX + c not in known]
        seen = [PREFIX + c for c in listed if PREFIX + c in known]
        if limit is not None:
            fresh = fresh[:limit]

        offers: list[TaleezOffer] = []
        gone = 0
        for i, code in enumerate(fresh):
            if i:
                await asyncio.sleep(PAUSE_S)
            try:
                page = await client.get(listed[code])
            except httpx.HTTPError as e:
                logger.warning("Taleez : %s illisible (%s)", listed[code], type(e).__name__)
                continue
            if page.status_code != 200:
                continue
            offer = parse_offer(code, str(page.url), page.text)
            if offer:
                offers.append(offer)
            else:
                gone += 1

        saved = await persist(offers)
        now = datetime.now(UTC)
        async with async_session() as session:
            if seen:
                await session.execute(
                    update(JobPosting).where(JobPosting.external_id.in_(seen)).values(last_seen_at=now)
                )
            await session.execute(
                update(JobPosting)
                .where(JobPosting.external_id.like(f"{PREFIX}%"))
                .where(JobPosting.status == PostingStatus.ACTIVE)
                .where(JobPosting.external_id.not_in([PREFIX + c for c in listed]))
                # Une offre collée il y a peu peut ne pas être encore au sitemap.
                .where(JobPosting.first_seen_at < now - timedelta(days=3))
                .values(status=PostingStatus.CLOSED)
            )
            await session.commit()
        sendable = sum(1 for o in offers if o.form.sendable)
        logger.info("Taleez : %d offres listées, %d lues, %d enregistrées dont %d envoyables par Alice",
                    len(listed), len(fresh), saved, sendable)
        return {"ok": True, "listed": len(listed), "read": len(fresh), "saved": saved,
                "sendable": sendable, "not_public": gone}
    except Exception as e:
        logger.error("Collecte Taleez impossible : %s", e, exc_info=True)
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}
    finally:
        if own:
            await client.aclose()


# ── Offre collée par un candidat ──────────────────────────────────────────

#: Lien d'offre Taleez : taleez.com/apply/<code ou jeton>, ou un site carrière
#: <entreprise>.taleez.com/… qui renvoie au même formulaire.
PASTED_URL = re.compile(r"^https://(?:www\.)?taleez\.com/apply/([A-Za-z0-9-]+)/?(?:[?#].*)?$")


def pasted_code(url: str | None) -> str | None:
    m = PASTED_URL.match((url or "").strip())
    return m.group(1) if m and m.group(1) not in ("confirm", "thanks") else None


async def import_url(url: str) -> JobPosting | None:
    """Lit l'offre Taleez collée et l'enregistre comme les autres. None si illisible."""
    code = pasted_code(url)
    if not code:
        return None
    async with httpx.AsyncClient(timeout=30, follow_redirects=True,
                                 headers={"User-Agent": USER_AGENT}) as client:
        try:
            page = await client.get(f"{BASE}/apply/{code}")
        except httpx.HTTPError:
            return None
    if page.status_code != 200:
        return None
    offer = parse_offer(code, str(page.url), page.text)
    if not offer:
        return None
    await persist([offer], from_sitemap=False)
    # Même domaine fictif que celui donné à l'employeur à l'enregistrement.
    domain = f"{_slugify((offer.company or '').strip() or ANONYMOUS_NAME)}{DOMAIN_SUFFIX}"
    async with async_session() as session:
        return (await session.execute(
            select(JobPosting).where(JobPosting.fingerprint == _fingerprint(domain, offer))
        )).scalars().first()


# ── Envoi ──────────────────────────────────────────────────────────────────


class TaleezError(RuntimeError):
    def __init__(self, status: int, code: str, detail: str = ""):
        super().__init__(f"{status}: {code} {detail}".strip())
        self.status = status
        self.code = code
        self.detail = detail


def _split_name(full_name: str) -> tuple[str, str]:
    parts = (full_name or "").strip().split()
    if len(parts) < 2:
        return (parts[0] if parts else ""), ""
    return parts[0], " ".join(parts[1:])


def _phone(raw: str | None) -> str:
    """« 06 12 34 56 78 » → « +33612345678 », comme le formulaire."""
    digits = re.sub(r"[^\d+]", "", raw or "")
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if re.fullmatch(r"0\d{9}", digits):
        digits = "+33" + digits[1:]
    return digits


def apply_payload(*, token: str, cv_question: int, cv_file: str, cv_name: str,
                  message_question: int | None, message: str | None,
                  first_name: str, last_name: str, email: str, phone: str) -> dict:
    """Le corps exact de la requête du formulaire (relevé le 14/10/2026)."""
    answers: list[dict] = [{"questionId": cv_question,
                            "doc": {"file": cv_file, "fileName": cv_name, "name": cv_name}}]
    if message_question is not None and message:
        answers.append({"questionId": message_question, "value": message})
    return {
        "lang": "fr", "utmSource": "unknown",
        # Pas de CVthèque ni de « GPT » : le candidat n'y a pas consenti ici.
        "cvthequeGpt": False, "rgpdCvtheque": False,
        "firstName": first_name, "lastName": last_name, "mail": email, "phone": phone,
        "answers": answers, "token": token,
    }


async def send_application(
    *, target: dict, full_name: str, email: str, phone: str | None,
    resume: bytes, resume_name: str, message: str | None,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Dépose le CV puis la candidature. Lève TaleezError."""
    if target.get("message_required") and not message:
        raise TaleezError(0, "MESSAGE_REQUIRED")
    first, last = _split_name(full_name)
    own = client is None
    client = client or httpx.AsyncClient(timeout=60, headers={"User-Agent": USER_AGENT})
    try:
        up = await client.post(UPLOAD_URL, files={"file": (resume_name or "CV.pdf", resume, "application/pdf")})
        if up.status_code != 200:
            raise TaleezError(up.status_code, "UPLOAD", up.text[:200])
        stored = (up.json() or {}).get("fileName")
        if not stored:
            raise TaleezError(up.status_code, "UPLOAD", "pas de nom de fichier en retour")
        body = apply_payload(
            token=target["token"], cv_question=target["cv"], cv_file=stored,
            cv_name=resume_name or "CV.pdf", message_question=target.get("message"),
            message=(message or "")[:5000] or None,
            first_name=first, last_name=last, email=email, phone=_phone(phone),
        )
        res = await client.post(APPLY_URL, json=body)
        if res.status_code not in (200, 201, 204):
            try:
                code = (res.json() or {}).get("error") or "REFUSED"
            except ValueError:
                code = "REFUSED"
            raise TaleezError(res.status_code, code, res.text[:200])
        try:
            return res.json() or {}
        except ValueError:
            return {}
    finally:
        if own:
            await client.aclose()


#: Le lien que Taleez envoie au candidat pour valider sa candidature.
CONFIRM_LINK = re.compile(r"https://(?:www\.)?taleez\.com/apply/confirm/[A-Za-z0-9._~-]+")
CONFIRM_URL = f"{BASE}/api/public/confirm-apply"
_CONFIRM_TOKEN = re.compile(r"^https://(?:www\.)?taleez\.com/apply/confirm/([A-Za-z0-9._~-]+)")


def _public_https(url: str) -> bool:
    """Un lien reçu par e-mail : https, nom de domaine public, jamais une IP ni un nom interne."""
    import ipaddress
    from urllib.parse import urlsplit

    parts = urlsplit(url or "")
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or "." not in host or host.endswith((".local", ".internal")):
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        return True


async def confirm(link: str, client: httpx.AsyncClient | None = None) -> bool:
    """
    Valide la candidature comme le ferait la page du lien : on suit le lien
    (il peut passer par un suivi de clics), on lit le jeton dans l'adresse
    d'arrivée, puis on fait l'appel que la page fait elle-même. Ne lève pas.
    """
    if not _public_https(link):
        logger.warning("Taleez : lien de confirmation refusé (%s)", link[:80])
        return False
    own = client is None
    client = client or httpx.AsyncClient(timeout=30, follow_redirects=True,
                                         headers={"User-Agent": USER_AGENT})
    try:
        page = await client.get(link)
        m = _CONFIRM_TOKEN.match(str(page.url))
        if not m:
            logger.warning("Taleez : lien de confirmation inattendu (%s)", str(page.url)[:120])
            return False
        res = await client.post(CONFIRM_URL, json={"token": m.group(1)})
        if res.status_code >= 300:
            logger.warning("Taleez : confirmation refusée (%s)", res.status_code)
        return res.status_code < 300
    except httpx.HTTPError as e:
        logger.warning("Taleez : confirmation impossible (%s)", type(e).__name__)
        return False
    finally:
        if own:
            await client.aclose()
