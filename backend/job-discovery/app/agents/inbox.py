"""
Les réponses des recruteurs.

Chaque candidat a une adresse de réponse à lui, `<jeton>@<INBOUND_DOMAIN>`,
donnée dans les candidatures qu'Alice envoie (Reply-To), qu'elle transmet par
API (Recruitee, La bonne alternance) ou qu'elle remplit via l'extension. Ce qui
y arrive passe ici :

  1. on retrouve le candidat par le jeton de l'adresse ;
  2. on rattache le message à une de ses candidatures (domaine de l'expéditeur,
     nom de l'entreprise, intitulé du poste) ;
  3. Alice le lit : refus, entretien, offre, demande, accusé de réception ;
  4. le suivi se met à jour (un refus clôt, un entretien fait avancer) ;
  5. le message est transféré au candidat, avec ce qu'Alice en retient en tête
     et l'adresse du recruteur en Reply-To : il répond directement.

Rien ne se perd : même non rattaché ou mal compris, le message est transféré.
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
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.application import Application, ApplicationStatus
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.inbound_email import InboundEmail
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


@dataclass
class Incoming:
    provider_id: str
    from_raw: str
    to: list[str]
    subject: str = ""
    text: str = ""
    html: str | None = None
    attachments: list[str] = field(default_factory=list)

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
    return Incoming(
        provider_id=f"resend:{email_id}",
        from_raw=body.get("from") or data.get("from") or "",
        to=_as_list(body.get("to") or data.get("to")) + _as_list(body.get("cc") or data.get("cc")),
        subject=body.get("subject") or data.get("subject") or "",
        text=body.get("text") or (html_to_text(html) if html else ""),
        html=html,
        attachments=[a.get("filename", "") for a in (data.get("attachments") or []) if isinstance(a, dict)],
    )


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

    plain = content(msg.get_body(preferencelist=("plain",)))
    html = content(msg.get_body(preferencelist=("html",))) or None
    return {
        "from": str(msg.get("From") or ""),
        "to": [str(msg.get("To") or "")] + ([str(msg.get("Cc"))] if msg.get("Cc") else []),
        "subject": str(msg.get("Subject") or ""),
        "message_id": str(msg.get("Message-ID") or "").strip() or None,
        "text": plain.strip(),
        "html": html,
        "attachments": [p.get_filename() or "" for p in msg.iter_attachments()],
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
                    attachments=[a for a in payload.get("attachments") or [] if a])


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


def score_match(c: Candidacy, from_email: str, from_name: str, subject: str, text: str) -> int:
    """Plus c'est haut, plus le message parle de cette candidature."""
    score = 0
    sender_domain = from_email.rpartition("@")[2]
    root = sender_domain.split(".")[-2] if sender_domain.count(".") >= 1 else sender_domain
    company_domain = (c.domain or "").lower().removeprefix("www.")
    if company_domain and sender_domain not in _FREE_MAIL and not any(a in sender_domain for a in _ATS_MAIL):
        if sender_domain == company_domain or sender_domain.endswith("." + company_domain):
            score += 10
        elif root and root == company_domain.split(".")[0]:
            score += 8
    haystack = f" {_norm(from_name)} {_norm(subject)} {_norm(text[:4000])} "
    words = _company_words(c.company)
    if words and all(f" {w} " in haystack for w in words):
        score += 6
    elif words and any(f" {w} " in haystack for w in words if len(w) > 4):
        score += 2
    title_words = [w for w in _norm(c.title).split() if len(w) > 3]
    if title_words:
        hits = sum(1 for w in title_words if f" {w} " in haystack)
        score += round(4 * hits / len(title_words))
    if c.status in (ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEW):
        score += 1
    return score


def best_match(candidacies: list[Candidacy], msg: Incoming) -> tuple[Candidacy | None, bool]:
    """(candidature, sûr ?) — sûr quand le meilleur score est net et sans ex æquo."""
    if not candidacies:
        return None, False
    scored = sorted(
        ((score_match(c, msg.from_email, msg.from_name or "", msg.subject, msg.text), c) for c in candidacies),
        key=lambda x: x[0], reverse=True,
    )
    top, best = scored[0]
    runner = scored[1][0] if len(scored) > 1 else -1
    if top < 5:
        return None, False
    return best, top >= 8 and top > runner


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
        return reading
    except Exception as e:  # noqa: BLE001
        logger.warning("Lecture d'un e-mail reçu par le modèle impossible : %s", e)
        from app.agents.company_name import display_company

        kind = classify_by_rules(msg.subject, msg.text)
        who = (display_company(likely.company) if likely else None) or msg.from_name or msg.from_email
        about = f" pour « {likely.title} »" if likely else f" : « {msg.subject[:120]} »"
        return Reading(kind=kind, summary=f"{KIND_LABELS[kind].capitalize()} de {who}{about}.",
                       next_step=_FALLBACK_STEP.get(kind))


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
        select(Application.id, Company.name, Company.domain, JobPosting.title, Application.status)
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
    return [Candidacy(r[0], r[1] or "", r[2] or "", r[3] or "", r[4]) for r in rows]


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
        reading = await read_message(msg, candidacies, match)
        if not sure and 0 <= reading.application_index < len(candidacies):
            match = candidacies[reading.application_index]

        record = InboundEmail(
            candidate_id=candidate.id,
            application_id=match.application_id if match else None,
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
            meta={"attachments": msg.attachments[:20]} if msg.attachments else None,
        )
        session.add(record)
        await session.flush()

        company = display_company(match.company) if match else None
        if match:
            application = await session.get(Application, match.application_id)
            target = next_status(application.status, reading.kind) if application else None
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
             "job_title": match.title if match else None, "company": company},
        )
        try:
            await session.commit()
        except IntegrityError:  # le même e-mail livré deux fois en même temps
            await session.rollback()
            return None
        await session.refresh(record)
        recipient = candidate.email
        candidate_name = candidate.full_name

    record.forwarded = await forward(record, recipient, candidate_name, company, match.title if match else None)
    async with async_session() as session:
        stored = await session.get(InboundEmail, record.id)
        if stored:
            stored.forwarded = record.forwarded
            await session.commit()
    return record


async def forward(record: InboundEmail, recipient: str | None, name: str | None,
                  company: str | None, job_title: str | None) -> bool:
    """Transfère au candidat, avec la lecture d'Alice en tête. Répondre écrit au recruteur."""
    from app.agents.notifications import link
    from app.agents.notifications.mailer import Mail, send_mail
    from app.agents.notifications.templates import Email, render_html, render_text

    if not recipient or recipient.endswith("@" + (settings.inbound_domain or "-")):
        return False
    who = company or record.from_name or record.from_email
    label = KIND_LABELS.get(record.kind, "message")
    about = f" pour « {job_title} »" if job_title else ""
    email = Email(
        subject=f"{who} t'a répondu : {label}",
        preheader=record.summary[:140],
        heading=f"{who} t'a répondu{about}.",
        paragraphs=[p for p in [
            record.summary,
            f"À faire : {record.next_step}" if record.next_step else "",
            "Réponds directement à cet e-mail : ta réponse partira au recruteur.",
            f"— Message de {record.from_name or ''} <{record.from_email}> —".replace("  ", " "),
            f"Objet : {record.subject}",
            *[p for p in re.split(r"\n{2,}", record.text[:8000]) if p.strip()],
        ] if p],
        cta_label="Voir dans Alice",
        cta_url=link("messages"),
        footer="Alice lit les réponses arrivées sur ton adresse de candidature et te les transfère.",
    )
    result = await send_mail(Mail(
        to=recipient,
        subject=email.subject,
        text=render_text(email),
        html=render_html(email),
        reply_to=record.from_email,
    ))
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
