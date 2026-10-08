"""
Les réponses des recruteurs.

Chaque candidat a une adresse de réponse à lui, `<jeton>@<INBOUND_DOMAIN>`,
donnée dans les candidatures qu'Alice envoie (Reply-To), qu'elle transmet par
API (Recruitee, La bonne alternance) ou qu'elle remplit via l'extension. Ce qui
y arrive passe ici :

  1. on retrouve le candidat par le jeton de l'adresse ;
  2. on rattache le message à une de ses candidatures (adresse ou domaine de
     l'expéditeur, nom de l'entreprise, intitulé du poste) ;
  3. Alice le lit : refus, entretien, offre, demande, accusé de réception ;
  4. le suivi se met à jour (un refus clôt, un entretien fait avancer) — mais
     seulement si le rattachement est sûr et la lecture faite par l'IA ; sinon
     le message attend que le candidat dise à quelle candidature il répond ;
  5. le message est transféré au candidat, pièces jointes comprises, avec ce
     qu'Alice en retient en tête et l'adresse du recruteur en Reply-To : il
     répond directement.

Rien ne se perd : même non rattaché ou mal compris, le message est transféré,
et ses pièces jointes restent téléchargeables dans Alice.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import re
import secrets
import time
import unicodedata
from dataclasses import dataclass, field
from email.utils import parseaddr
from uuid import UUID

import httpx
from pydantic import BaseModel, PrivateAttr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.application import Application, ApplicationStatus
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.inbound_email import InboundAttachment, InboundEmail
from app.models.job_posting import JobPosting

logger = logging.getLogger(__name__)

KINDS = ("interview", "rejection", "offer", "request", "acknowledgement", "other")

KIND_LABELS = {
    "interview": "proposition d'entretien",
    "rejection": "réponse négative",
    "offer": "proposition d'embauche",
    "request": "demande du recruteur",
    "acknowledgement": "accusé de réception",
    "other": "message",
}


# ── L'adresse de réponse ───────────────────────────────────────────────────

_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # sans 0/o, 1/l/i


def _slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", ".", ascii_name.lower()).strip(".")
    return slug[:30] or "candidat"


def new_token(full_name: str) -> str:
    """« Camille Martin » → « camille.martin.k7f2q » : lisible, et impossible à deviner."""
    return f"{_slug(full_name)}.{''.join(secrets.choice(_ALPHABET) for _ in range(5))}"


async def ensure_reply_address(session: AsyncSession, candidate: Candidate) -> str | None:
    """
    L'adresse de réponse du candidat, créée au besoin (sans commit). None tant
    que la réception n'est pas configurée : on garde alors son adresse à lui.
    """
    if not settings.inbound_configured:
        return None
    if not candidate.reply_token:
        candidate.reply_token = new_token(candidate.full_name)
        await session.flush()
    return f"{candidate.reply_token}@{settings.inbound_domain}"


def reply_address_of(candidate: Candidate) -> str | None:
    """Sans session : l'adresse si elle existe déjà."""
    if not settings.inbound_configured or not candidate.reply_token:
        return None
    return f"{candidate.reply_token}@{settings.inbound_domain}"


def contact_of(candidate: Candidate) -> str:
    """L'adresse à donner aux recruteurs, si elle existe déjà ; sinon la sienne."""
    return reply_address_of(candidate) or candidate.email or ""


async def contact_email(candidate_id: UUID) -> str | None:
    """L'adresse à donner aux recruteurs : celle de réponse, à défaut la sienne."""
    async with async_session() as session:
        candidate = await session.get(Candidate, candidate_id)
        if not candidate:
            return None
        address = await ensure_reply_address(session, candidate)
        await session.commit()
        return address or candidate.email


def token_from(addresses: list[str]) -> str | None:
    """Le jeton d'une adresse de notre domaine de réception, parmi les destinataires."""
    domain = (settings.inbound_domain or "").lower()
    for raw in addresses:
        _, addr = parseaddr(raw or "")
        local, _, host = addr.lower().partition("@")
        if domain and host == domain and local:
            return local.split("+", 1)[0]
    return None


# ── Webhook : signature et contenu ─────────────────────────────────────────


def verify_svix(secret: str, msg_id: str, timestamp: str, body: bytes, signatures: str,
                tolerance: int = 300) -> bool:
    """Signature des webhooks Resend (format Svix : HMAC-SHA256 de « id.timestamp.corps »)."""
    if not (secret and msg_id and timestamp and signatures):
        return False
    try:
        if abs(time.time() - int(timestamp)) > tolerance:
            return False
        key = base64.b64decode(secret.removeprefix("whsec_"))
    except (ValueError, TypeError):
        return False
    signed = f"{msg_id}.{timestamp}.".encode() + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    for part in signatures.split():
        _, _, sig = part.partition(",")
        if sig and hmac.compare_digest(sig, expected):
            return True
    return False


#: Plafonds des pièces jointes gardées : au-delà, on garde le nom et on le dit.
MAX_ATTACHMENT = 10 * 1024 * 1024
MAX_ATTACHMENTS_TOTAL = 25 * 1024 * 1024
MAX_ATTACHMENTS_COUNT = 20


@dataclass
class Piece:
    """Une pièce jointe reçue. `content` à None : non gardée (trop lourde, illisible)."""
    filename: str
    mime: str = "application/octet-stream"
    content: bytes | None = None
    size: int = 0


def cap_attachments(pieces: list[Piece]) -> list[Piece]:
    """Garde ce qui tient dans les plafonds ; le reste perd son contenu mais pas son nom."""
    out, total = [], 0
    for i, p in enumerate(pieces):
        size = len(p.content) if p.content is not None else p.size
        keep = (p.content is not None and i < MAX_ATTACHMENTS_COUNT
                and size <= MAX_ATTACHMENT and total + size <= MAX_ATTACHMENTS_TOTAL)
        if keep:
            total += size
        out.append(Piece(p.filename or "piece-jointe", p.mime or "application/octet-stream",
                         p.content if keep else None, size))
    return out


@dataclass
class Incoming:
    provider_id: str
    from_raw: str
    to: list[str]
    subject: str = ""
    text: str = ""
    html: str | None = None
    attachments: list[Piece] = field(default_factory=list)

    @property
    def kept(self) -> list[Piece]:
        return [p for p in self.attachments if p.content is not None]

    @property
    def skipped(self) -> list[Piece]:
        return [p for p in self.attachments if p.content is None]

    @property
    def from_email(self) -> str:
        return parseaddr(self.from_raw)[1].lower()

    @property
    def from_name(self) -> str | None:
        return parseaddr(self.from_raw)[0] or None


def _as_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    out = []
    for v in value:
        if isinstance(v, dict):
            v = v.get("email") or v.get("address") or ""
        if v:
            out.append(str(v))
    return out


def html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", "", html or "")
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    from html import unescape
    text = unescape(text)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


async def fetch_resend_email(email_id: str) -> dict:
    """Le corps d'un e-mail reçu : le webhook Resend n'en donne que les métadonnées."""
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"https://api.resend.com/emails/receiving/{email_id}",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        )
    response.raise_for_status()
    return response.json() or {}


async def incoming_from_resend(event: dict) -> Incoming | None:
    """Événement « email.received » → message complet (corps récupéré par l'API)."""
    if event.get("type") != "email.received":
        return None
    data = event.get("data") or {}
    email_id = data.get("email_id") or data.get("id")
    if not email_id:
        return None
    body: dict = {}
    try:
        body = await fetch_resend_email(email_id)
    except Exception as e:  # noqa: BLE001 — on traite au moins les métadonnées
        logger.error("Corps de l'e-mail %s introuvable chez Resend : %s", email_id, e)
    html = body.get("html")
    listed = [a for a in (body.get("attachments") or data.get("attachments") or []) if isinstance(a, dict)]
    return Incoming(
        provider_id=f"resend:{email_id}",
        from_raw=body.get("from") or data.get("from") or "",
        to=_as_list(body.get("to") or data.get("to")) + _as_list(body.get("cc") or data.get("cc")),
        subject=body.get("subject") or data.get("subject") or "",
        text=body.get("text") or (html_to_text(html) if html else ""),
        html=html,
        attachments=await resend_attachments(email_id, listed) if listed else [],
    )


def _piece_from_dict(a: dict) -> Piece:
    """{filename, content_type, size, content (base64)?} → pièce, contenu décodé s'il est là."""
    content = None
    if a.get("content"):
        try:
            content = base64.b64decode(a["content"])
        except (ValueError, TypeError):
            content = None
    return Piece(
        filename=str(a.get("filename") or a.get("name") or "piece-jointe")[:300],
        mime=str(a.get("content_type") or a.get("contentType") or a.get("type") or "application/octet-stream")[:150],
        content=content,
        size=len(content) if content is not None else int(a.get("size") or 0),
    )


async def resend_attachments(email_id: str, listed: list[dict]) -> list[Piece]:
    """
    Les pièces d'un e-mail reçu chez Resend. Le webhook n'en donne que la liste :
    le contenu se télécharge à part (lien temporaire), dans la limite des plafonds.
    """
    pieces = [_piece_from_dict(a) for a in listed]
    if all(p.content is not None for p in pieces):
        return cap_attachments(pieces)
    links: dict[str, str] = {}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"https://api.resend.com/emails/receiving/{email_id}/attachments",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            )
            response.raise_for_status()
            for a in (response.json() or {}).get("data") or []:
                if isinstance(a, dict) and a.get("download_url"):
                    links[str(a.get("id") or a.get("filename"))] = a["download_url"]
                    links.setdefault(str(a.get("filename")), a["download_url"])
            total = 0
            for a, p in zip(listed, pieces):
                url = links.get(str(a.get("id"))) or links.get(p.filename)
                if p.content is not None or not url:
                    continue
                if p.size > MAX_ATTACHMENT or total + p.size > MAX_ATTACHMENTS_TOTAL:
                    continue  # inutile de télécharger ce qu'on ne gardera pas
                got = await client.get(url)
                if got.status_code < 400:
                    p.content = got.content
                    p.size = len(got.content)
                    total += p.size
    except Exception as e:  # noqa: BLE001 — les noms au moins restent
        logger.warning("Pièces jointes de l'e-mail %s introuvables chez Resend : %s", email_id, e)
    return cap_attachments(pieces)


def parse_mime(raw: bytes) -> dict:
    """E-mail brut (RFC 822) → champs utiles. Le texte brut d'abord, sinon le HTML converti."""
    from email import policy
    from email.parser import BytesParser

    msg = BytesParser(policy=policy.default).parsebytes(raw)

    def content(part) -> str:
        try:
            return part.get_content() if part else ""
        except Exception:  # noqa: BLE001 — encodage exotique
            payload = part.get_payload(decode=True) or b""
            return payload.decode("utf-8", "replace")

    def piece(part) -> Piece | None:
        maintype = part.get_content_maintype()
        # Logos et images de signature : pas des pièces jointes.
        if part.get_content_disposition() != "attachment" and maintype == "image" and part.get("Content-ID"):
            return None
        try:
            data = part.get_payload(decode=True)
        except Exception:  # noqa: BLE001
            data = None
        if data is None and maintype == "message":
            data = part.as_bytes()
        return Piece(filename=(part.get_filename() or "piece-jointe")[:300],
                     mime=part.get_content_type()[:150], content=data,
                     size=len(data) if data is not None else 0)

    plain = content(msg.get_body(preferencelist=("plain",)))
    html = content(msg.get_body(preferencelist=("html",))) or None
    return {
        "from": str(msg.get("From") or ""),
        "to": [str(msg.get("To") or "")] + ([str(msg.get("Cc"))] if msg.get("Cc") else []),
        "subject": str(msg.get("Subject") or ""),
        "message_id": str(msg.get("Message-ID") or "").strip() or None,
        "text": plain.strip(),
        "html": html,
        "attachments": cap_attachments([p for p in map(piece, msg.iter_attachments()) if p]),
    }


def incoming_from_generic(payload: dict) -> Incoming | None:
    """
    Relais quelconque. Deux formes :
      - {raw: <e-mail brut en base64>, from, to} (Worker Cloudflare : l'enveloppe
        SMTP en from/to, le message complet en raw) ;
      - {from, to, subject, text, html, message_id} déjà découpé.
    """
    if payload.get("raw"):
        try:
            parsed = parse_mime(base64.b64decode(payload["raw"]))
        except Exception as e:  # noqa: BLE001
            logger.warning("E-mail brut illisible : %s", e)
            return None
        # L'enveloppe d'abord : l'adresse de réponse peut n'être qu'en copie cachée.
        payload = {
            **parsed,
            "from": parsed["from"] or payload.get("from") or "",
            "to": _as_list(payload.get("to")) + [t for t in parsed["to"] if t],
        }
    sender = payload.get("from") or ""
    to = _as_list(payload.get("to")) + _as_list(payload.get("cc"))
    if not sender or not to:
        return None
    html = payload.get("html")
    text = payload.get("text") or (html_to_text(html) if html else "")
    pid = payload.get("message_id") or hashlib.sha1(
        f"{sender}|{','.join(to)}|{payload.get('subject')}|{text[:500]}".encode()
    ).hexdigest()
    return Incoming(provider_id=f"relay:{pid}"[:300], from_raw=sender, to=to,
                    subject=payload.get("subject") or "", text=text, html=html,
                    attachments=cap_attachments([
                        a if isinstance(a, Piece) else _piece_from_dict(a) if isinstance(a, dict)
                        else Piece(filename=str(a)[:300])
                        for a in payload.get("attachments") or [] if a
                    ]))


# ── Rattacher à une candidature ────────────────────────────────────────────

_FREE_MAIL = {"gmail.com", "outlook.com", "hotmail.com", "hotmail.fr", "yahoo.com", "yahoo.fr",
              "orange.fr", "free.fr", "icloud.com", "live.fr", "laposte.net", "wanadoo.fr"}
# Les ATS écrivent depuis leur domaine : le nom de l'entreprise est dans le texte.
_ATS_MAIL = ("greenhouse", "lever", "workable", "recruitee", "smartrecruiters", "teamtailor",
             "welcometothejungle", "ashbyhq", "myworkday", "taleo", "jobteaser", "indeed",
             "linkedin", "flatchr", "digitalrecruiters", "breezy", "personio", "apprentissage")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


_LEGAL = {"sas", "sa", "sarl", "eurl", "sasu", "group", "groupe", "france", "inc", "ltd", "gmbh", "the"}


def _company_words(name: str) -> list[str]:
    return [w for w in _norm(name).split() if len(w) > 2 and w not in _LEGAL]


@dataclass
class Candidacy:
    application_id: UUID
    company: str
    domain: str
    title: str
    status: ApplicationStatus
    #: L'adresse à laquelle la candidature est partie, si on la connaît.
    contact: str = ""


def _domain_score(c: Candidacy, sender_domain: str) -> int:
    """10 : domaine de l'entreprise ; 8 : même racine (doctolib.fr / doctolib.com) ; 0 sinon."""
    company_domain = (c.domain or "").lower().removeprefix("www.")
    if not company_domain or sender_domain in _FREE_MAIL or any(a in sender_domain for a in _ATS_MAIL):
        return 0
    if sender_domain == company_domain or sender_domain.endswith("." + company_domain):
        return 10
    root = sender_domain.split(".")[-2] if sender_domain.count(".") >= 1 else sender_domain
    if root and root == company_domain.split(".")[0]:
        return 8
    return 0


def _haystack(from_name: str, subject: str, text: str) -> str:
    return f" {_norm(from_name)} {_norm(subject)} {_norm(text[:4000])} "


def _title_score(c: Candidacy, haystack: str) -> int:
    title_words = [w for w in _norm(c.title).split() if len(w) > 3]
    if not title_words:
        return 0
    hits = sum(1 for w in title_words if f" {w} " in haystack)
    return round(4 * hits / len(title_words))


def score_match(c: Candidacy, from_email: str, from_name: str, subject: str, text: str) -> int:
    """Plus c'est haut, plus le message parle de cette candidature."""
    score = _domain_score(c, from_email.rpartition("@")[2])
    haystack = _haystack(from_name, subject, text)
    words = _company_words(c.company)
    if words and all(f" {w} " in haystack for w in words):
        score += 6
    elif words and any(f" {w} " in haystack for w in words if len(w) > 4):
        score += 2
    score += _title_score(c, haystack)
    if c.status in (ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEW):
        score += 1
    return score


def best_match(candidacies: list[Candidacy], msg: Incoming) -> tuple[Candidacy | None, bool]:
    """
    (candidature, sûr ?). Seul un rattachement sûr change un statut tout seul.

    Sûr, c'est :
      - l'expéditeur est l'adresse même à laquelle la candidature est partie,
        et une seule candidature est partie là ;
      - ou il écrit depuis le domaine de l'entreprise (ni messagerie grand
        public, ni ATS) et c'est la seule candidature chez elle — s'il y en a
        plusieurs, l'intitulé du poste doit les départager nettement.

    Le reste (nom de l'entreprise dans le texte, message d'un ATS…) n'est
    qu'une suggestion : le candidat confirme.
    """
    if not candidacies:
        return None, False
    sender = msg.from_email
    sender_domain = sender.rpartition("@")[2]
    haystack = _haystack(msg.from_name or "", msg.subject, msg.text)

    exact = [c for c in candidacies if c.contact and c.contact.strip().lower() == sender]
    pool = exact or [c for c in candidacies if _domain_score(c, sender_domain) >= 8]
    if len(pool) == 1:
        return pool[0], True
    if len(pool) > 1:
        ranked = sorted(pool, key=lambda c: _title_score(c, haystack), reverse=True)
        first, second = _title_score(ranked[0], haystack), _title_score(ranked[1], haystack)
        return ranked[0], first > 0 and first > second

    scored = sorted(
        ((score_match(c, sender, msg.from_name or "", msg.subject, msg.text), c) for c in candidacies),
        key=lambda x: x[0], reverse=True,
    )
    top, best = scored[0]
    return (best, False) if top >= 5 else (None, False)


# ── Lire le message ────────────────────────────────────────────────────────

_RULES = [
    ("offer", r"proposition d.embauche|promesse d.embauche|offre (d.emploi|de poste) (ci-jointe|formelle)|job offer|offer letter|pleased to offer"),
    ("rejection", r"malheureusement|ne pas donner suite|pas (pu )?(donner|retenir)|pas retenu|ne correspond pas|autre candidat|unfortunately|not (to )?(move|moving) forward|other candidates|regret to inform|décidé de ne pas"),
    ("interview", r"entretien|interview|vos disponibilit|your availability|planifier un (échange|appel)|schedule a (call|meeting)|calendly|rencontrer|échanger avec vous|visio"),
    ("request", r"pourriez-vous|merci de (nous )?(transmettre|envoyer|compléter)|test technique|questionnaire|could you (please )?(send|provide|complete)|coding (test|challenge)|assessment"),
    ("acknowledgement", r"bien (été )?reçu|accusé de réception|nous avons reçu|we (have )?received|thank you for (applying|your application)|merci pour (votre|ta) candidature|nous reviendrons vers vous"),
]


def classify_by_rules(subject: str, text: str) -> str:
    hay = f"{subject}\n{text[:5000]}".lower()
    for kind, pattern in _RULES:
        if re.search(pattern, hay):
            return kind
    return "other"


class Reading(BaseModel):
    kind: str
    summary: str
    next_step: str | None = None
    #: Index de la candidature concernée dans la liste fournie, -1 si aucune.
    application_index: int = -1
    #: Lu par les règles de repli (sans IA) : trop grossier pour toucher au suivi.
    _by_rules: bool = PrivateAttr(default=False)

    @property
    def by_rules(self) -> bool:
        return self._by_rules


READ_PROMPT = """Tu lis, pour un candidat, un e-mail reçu en réponse à ses candidatures.

Ses candidatures (index : entreprise — poste) :
{candidacies}

L'e-mail :
De : {sender}
Objet : {subject}
---
{text}
---

Réponds en JSON :
- kind : "interview" (entretien ou échange proposé), "rejection" (refus),
  "offer" (proposition d'embauche), "request" (le recruteur demande quelque
  chose : document, test, questionnaire, disponibilités sans entretien),
  "acknowledgement" (accusé de réception automatique), "other".
- summary : une phrase en français, tutoiement, ce que dit le recruteur
  (ex. « Doctolib te propose un premier échange de 30 minutes. »). N'invente rien.
- next_step : ce que le candidat doit faire, une phrase, ou null s'il n'y a rien à faire.
- application_index : l'index de la candidature concernée, -1 si tu ne sais pas."""


_FALLBACK_STEP = {
    "interview": "Réponds au recruteur avec tes disponibilités.",
    "request": "Regarde ce que le recruteur te demande et réponds-lui.",
    "offer": "Prends le temps de lire la proposition ; je peux t'aider à la relire.",
}


async def read_message(msg: Incoming, candidacies: list[Candidacy],
                       likely: Candidacy | None = None) -> Reading:
    """Alice lit le message. Sans modèle disponible, des règles simples prennent le relais."""
    from app.llm import generate

    listing = "\n".join(f"{i} : {c.company} — {c.title}" for i, c in enumerate(candidacies[:60])) or "(aucune)"
    prompt = READ_PROMPT.format(
        candidacies=listing, sender=msg.from_raw[:200], subject=msg.subject[:300], text=msg.text[:6000],
    )
    try:
        reading = Reading.model_validate_json(await generate(prompt, schema=Reading))
        if reading.kind not in KINDS:
            reading.kind = classify_by_rules(msg.subject, msg.text)
            reading._by_rules = True
        return reading
    except Exception as e:  # noqa: BLE001
        logger.warning("Lecture d'un e-mail reçu par le modèle impossible : %s", e)
        from app.agents.company_name import display_company

        kind = classify_by_rules(msg.subject, msg.text)
        who = (display_company(likely.company) if likely else None) or msg.from_name or msg.from_email
        about = f" pour « {likely.title} »" if likely else f" : « {msg.subject[:120]} »"
        reading = Reading(kind=kind, summary=f"{KIND_LABELS[kind].capitalize()} de {who}{about}.",
                          next_step=_FALLBACK_STEP.get(kind))
        reading._by_rules = True
        return reading


# ── Le suivi ───────────────────────────────────────────────────────────────

#: Ce que chaque réponse fait au statut — jamais en arrière (un entretien ne
#: fait pas oublier une offre).
_RANK = {ApplicationStatus.PENDING: 0, ApplicationStatus.MATCHED: 1, ApplicationStatus.APPLIED: 2,
         ApplicationStatus.INTERVIEW: 3, ApplicationStatus.OFFER: 4}


def next_status(current: ApplicationStatus, kind: str) -> ApplicationStatus | None:
    if kind == "rejection":
        return None if current in (ApplicationStatus.REJECTED, ApplicationStatus.CLOSED) else ApplicationStatus.REJECTED
    target = {"interview": ApplicationStatus.INTERVIEW, "offer": ApplicationStatus.OFFER}.get(kind)
    if not target or current in (ApplicationStatus.REJECTED, ApplicationStatus.CLOSED):
        return None
    if _RANK.get(current, 0) >= _RANK[target]:
        return None
    return target


def auto_status(current: ApplicationStatus, reading: Reading, sure: bool) -> ApplicationStatus | None:
    """
    Le statut qu'Alice pose seule. Rien si le rattachement est incertain (un
    refus pour un poste ne doit pas en clore un autre) ni si le message n'a
    été lu que par les règles de repli (« malheureusement pas dispo jeudi »
    n'est pas un refus).
    """
    if not sure or reading.by_rules:
        return None
    return next_status(current, reading.kind)


# ── Désinscription par réponse ─────────────────────────────────────────────

_STOP = re.compile(r"^\s*stop\b|d[ée]sinscri|ne (plus|pas) (nous )?(recevoir|envoyer|contacter)|"
                   r"retirez[- ]nous|unsubscribe|remove (us|me)", re.I)


def wants_optout(msg: Incoming) -> bool:
    first = (msg.text or "").strip()[:300]
    return bool(_STOP.search(msg.subject or "") or _STOP.search(first))


async def _optout_company(session: AsyncSession, application: Application) -> None:
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.email_optout import EmailOptout

    posting = await session.get(JobPosting, application.job_posting_id)
    email = ((posting.contact_json or {}) if posting else {}).get("email") or ""
    if "@" not in email:
        return
    await session.execute(
        pg_insert(EmailOptout).values(value="@" + email.rsplit("@", 1)[1].lower(),
                                      reason="réponse STOP à une candidature spontanée")
        .on_conflict_do_nothing(index_elements=["value"])
    )


# ── Traitement complet ─────────────────────────────────────────────────────


async def _candidacies(session: AsyncSession, candidate_id: UUID) -> list[Candidacy]:
    rows = (await session.execute(
        select(Application.id, Company.name, Company.domain, JobPosting.title, Application.status,
               JobPosting.contact_json)
        .join(JobPosting, Application.job_posting_id == JobPosting.id)
        .join(Company, JobPosting.company_id == Company.id)
        .where(Application.candidate_id == candidate_id)
        .where(Application.status.in_([
            ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER,
            ApplicationStatus.MATCHED, ApplicationStatus.REJECTED,
        ]))
        .order_by(Application.applied_at.desc().nullslast())
        .limit(200)
    )).all()
    return [Candidacy(r[0], r[1] or "", r[2] or "", r[3] or "", r[4], str((r[5] or {}).get("email") or ""))
            for r in rows]


async def process_incoming(msg: Incoming) -> InboundEmail | None:
    """Range, lit, met à jour le suivi et transfère. None si l'adresse n'est à personne ou déjà traité."""
    from app.agents.application.followup import record_status
    from app.agents.company_name import display_company
    from app.agents.mission_log import log_event
    from app.models.mission import MissionEventKind

    token = token_from(msg.to)
    if not token:
        logger.info("E-mail reçu sans adresse de réponse connue (%s).", ", ".join(msg.to)[:200])
        return None

    async with async_session() as session:
        candidate = (await session.execute(
            select(Candidate).where(Candidate.reply_token == token)
        )).scalar_one_or_none()
        if not candidate:
            logger.info("Adresse de réponse inconnue : %s", token)
            return None
        already = (await session.execute(
            select(InboundEmail.id).where(InboundEmail.provider_id == msg.provider_id)
        )).scalar_one_or_none()
        if already:
            return None

        candidacies = await _candidacies(session, candidate.id)
        match, sure = best_match(candidacies, msg)
        # Pour une lecture sans IA, ne nommer l'entreprise que si on en est sûr.
        reading = await read_message(msg, candidacies, match if sure else None)
        linked = match if sure else None
        suggested = None
        if not sure:
            # La lecture d'Alice départage mieux que les mots-clés, mais reste une suggestion.
            if 0 <= reading.application_index < len(candidacies):
                suggested = candidacies[reading.application_index]
            else:
                suggested = match
        to_link = not sure and bool(candidacies)

        meta: dict = {"read_by": "rules" if reading.by_rules else "ai"}
        if msg.attachments:
            meta["attachments"] = [p.filename for p in msg.kept]
        if msg.skipped:
            meta["skipped_attachments"] = [{"filename": p.filename, "size": p.size} for p in msg.skipped]
        if to_link:
            meta["to_link"] = True
            if suggested:
                meta["suggested_application_id"] = str(suggested.application_id)
        elif linked:
            meta["linked_by"] = "auto"

        record = InboundEmail(
            candidate_id=candidate.id,
            application_id=linked.application_id if linked else None,
            provider_id=msg.provider_id,
            from_email=msg.from_email[:320] or "inconnu",
            from_name=(msg.from_name or "")[:300] or None,
            to_email=f"{token}@{settings.inbound_domain}"[:320],
            subject=msg.subject[:500],
            text=msg.text[:100_000],
            html=(msg.html or "")[:300_000] or None,
            kind=reading.kind,
            summary=reading.summary[:1000],
            next_step=(reading.next_step or "")[:1000] or None,
            meta=meta,
        )
        session.add(record)
        await session.flush()
        for p in msg.kept:
            session.add(InboundAttachment(inbound_email_id=record.id, filename=p.filename[:300],
                                          mime=p.mime[:150], size=len(p.content or b""), content=p.content))

        company = display_company(linked.company) if linked else None
        if linked:
            application = await session.get(Application, linked.application_id)
            target = auto_status(application.status, reading, sure) if application else None
            if target:
                record_status(application, target, f"réponse reçue : {KIND_LABELS[reading.kind]}")
            # « STOP » en réponse à une candidature spontanée : l'entreprise
            # entière ne reçoit plus de spontanées, de personne.
            if application and (application.metadata_json or {}).get("spontaneous") and wants_optout(msg):
                await _optout_company(session, application)
        await log_event(
            session, candidate.id, MissionEventKind.REPLY,
            reading.summary or f"Réponse reçue de {msg.from_name or msg.from_email}.",
            {"inbound_id": str(record.id), "kind": reading.kind,
             "job_title": linked.title if linked else None, "company": company},
        )
        try:
            await session.commit()
        except IntegrityError:  # le même e-mail livré deux fois en même temps
            await session.rollback()
            return None
        await session.refresh(record)
        recipient = candidate.email
        candidate_name = candidate.full_name

    record.forwarded = await forward(record, recipient, candidate_name, company,
                                     linked.title if linked else None,
                                     pieces=msg.attachments, to_link=to_link)
    async with async_session() as session:
        stored = await session.get(InboundEmail, record.id)
        if stored:
            stored.forwarded = record.forwarded
            await session.commit()
    return record


def _size(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} Mo".replace(".", ",") if n >= 1024 * 1024 else f"{max(1, n // 1024)} Ko"


async def forward(record: InboundEmail, recipient: str | None, name: str | None,
                  company: str | None, job_title: str | None,
                  pieces: list[Piece] | None = None, to_link: bool = False) -> bool:
    """Transfère au candidat, avec la lecture d'Alice en tête. Répondre écrit au recruteur."""
    from app.agents.notifications import link
    from app.agents.notifications.mailer import Attachment, Mail, send_mail
    from app.agents.notifications.templates import Email, render_html, render_text

    if not recipient or recipient.endswith("@" + (settings.inbound_domain or "-")):
        return False
    pieces = pieces or []
    kept = [p for p in pieces if p.content is not None]
    skipped = [p for p in pieces if p.content is None]
    who = company or record.from_name or record.from_email
    label = KIND_LABELS.get(record.kind, "message")
    about = f" pour « {job_title} »" if job_title else ""

    def build(with_files: bool) -> Mail:
        notes = []
        if kept:
            where = "jointes à cet e-mail et dans Alice" if with_files else "à télécharger dans Alice"
            notes.append(f"Pièces jointes ({where}) : "
                         + ", ".join(f"{p.filename} ({_size(len(p.content or b''))})" for p in kept) + ".")
        if skipped:
            notes.append("Trop lourdes pour être gardées, demande-les au recruteur : "
                         + ", ".join(f"{p.filename}" + (f" ({_size(p.size)})" if p.size else "") for p in skipped)
                         + ".")
        email = Email(
            subject=f"{who} t'a répondu : {label}",
            preheader=record.summary[:140],
            heading=f"{who} t'a répondu{about}.",
            paragraphs=[p for p in [
                record.summary,
                f"À faire : {record.next_step}" if record.next_step else "",
                ("Je ne sais pas à quelle candidature ce message répond : dis-le-moi dans Alice, "
                 "je mettrai ton suivi à jour.") if to_link else "",
                *notes,
                "Réponds directement à cet e-mail : ta réponse partira au recruteur.",
                f"— Message de {record.from_name or ''} <{record.from_email}> —".replace("  ", " "),
                f"Objet : {record.subject}",
                *[p for p in re.split(r"\n{2,}", record.text[:8000]) if p.strip()],
            ] if p],
            cta_label="Voir dans Alice",
            cta_url=link("messages"),
            footer="Alice lit les réponses arrivées sur ton adresse de candidature et te les transfère.",
        )
        return Mail(
            to=recipient,
            subject=email.subject,
            text=render_text(email),
            html=render_html(email),
            reply_to=record.from_email,
            attachments=[Attachment(p.filename, p.content, p.mime) for p in kept] if with_files else [],
        )

    result = await send_mail(build(with_files=bool(kept)))
    if kept and not result.get("ok"):
        # Pièce refusée par le service d'envoi (type, taille) : le message
        # part sans elle, elle reste téléchargeable dans Alice.
        logger.warning("Transfert de %s avec pièces jointes refusé (%s) : nouvel essai sans.",
                       record.id, result.get("error"))
        result = await send_mail(build(with_files=False))
    if not result.get("ok") or not result.get("real"):
        logger.warning("Transfert de la réponse %s à %s impossible : %s", record.id, name, result.get("error"))
        if not result.get("ok"):  # un vrai échec, pas l'absence de service d'envoi
            from app.agents.incidents import report_incident
            await report_incident(
                "reply_forward_failed", record.candidate_id,
                "réponse d'un recruteur non transférée (elle reste visible dans Alice)",
                context={"inbound_id": str(record.id), "erreur": result.get("error") or ""},
            )
        return False
    return True


# ── Le candidat rattache lui-même ──────────────────────────────────────────


async def link_reply(session: AsyncSession, record: InboundEmail,
                     application: Application | None) -> ApplicationStatus | None:
    """
    Le candidat dit à quelle candidature répond le message (ou à aucune).
    Le statut suit alors la lecture d'Alice — sauf lecture sans IA : il le
    corrige lui-même dans Candidatures. Renvoie le nouveau statut, s'il change.
    """
    from app.agents.application.followup import record_status

    meta = dict(record.meta or {})
    meta.pop("to_link", None)
    meta["linked_by"] = "user"
    record.meta = meta
    record.application_id = application.id if application else None
    if not application or meta.get("read_by") == "rules":
        return None
    target = next_status(application.status, record.kind)
    if target:
        record_status(application, target, f"réponse reçue : {KIND_LABELS.get(record.kind, 'message')}")
    return target
