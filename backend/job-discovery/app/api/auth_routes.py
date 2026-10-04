"""
Connexion par e-mail — sans mot de passe.

1. `POST /auth/request` : un lien et un code partent à l'adresse donnée, depuis
   alice@alice-agent.fr. La réponse est la même que l'adresse soit connue ou
   non : on ne révèle pas qui a un compte.
2. `POST /auth/verify` : le lien (jeton) ou le code (avec l'adresse) ouvrent
   une session signée par l'API, valable SESSION_DAYS jours.

Garde-fous : jetons à usage unique, valables 15 minutes, empreintes seules en
base, 5 essais de code au plus, 5 demandes par adresse et par quart d'heure.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from app.auth import auth_configured, issue_session
from app.config import settings
from app.database import async_session
from app.models.login_token import LoginToken

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

TOKEN_TTL = timedelta(minutes=15)
MAX_CODE_ATTEMPTS = 5
MAX_REQUESTS_PER_WINDOW = 5


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class ConfigOut(BaseModel):
    #: Faux en développement sans configuration : l'interface saute la connexion.
    enabled: bool


@router.get("/config", response_model=ConfigOut)
async def auth_config():
    return ConfigOut(enabled=not settings.auth_bypassed)


class RequestIn(BaseModel):
    email: EmailStr


@router.post("/request", status_code=202)
async def request_link(body: RequestIn):
    if settings.auth_bypassed:
        return {"sent": False, "reason": "authentification désactivée en développement"}
    if not settings.auth_secret:
        raise HTTPException(503, "Connexion par e-mail non configurée (AUTH_SECRET).")

    email = body.email.strip().lower()
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        recent = (await session.execute(
            select(func.count(LoginToken.id))
            .where(LoginToken.email == email)
            .where(LoginToken.created_at >= now - TOKEN_TTL)
        )).scalar() or 0
        if recent >= MAX_REQUESTS_PER_WINDOW:
            raise HTTPException(429, "Trop de demandes. Réessaie dans quelques minutes.")

        token = secrets.token_urlsafe(32)
        code = f"{secrets.randbelow(1_000_000):06d}"
        session.add(LoginToken(
            email=email, token_hash=_hash(token), code_hash=_hash(f"{email}:{code}"),
            expires_at=now + TOKEN_TTL,
        ))
        await session.commit()

    link = (f"{settings.frontend_url.rstrip('/')}/auth/confirmed"
            f"?token={quote(token)}&email={quote(email)}")
    await _send_login_mail(email, link, code)
    return {"sent": True}


async def _send_login_mail(email: str, link: str, code: str) -> None:
    from app.agents.notifications.mailer import Mail, send_mail
    from app.agents.notifications.templates import Email, render_html, render_text

    content = Email(
        subject=f"{code} — ton code de connexion à Alice",
        preheader="Ton lien de connexion, valable 15 minutes.",
        heading="Connecte-toi à Alice",
        paragraphs=[
            "Clique sur le bouton pour te connecter. Le lien est valable 15 minutes et ne "
            "sert qu'une fois.",
            f"Tu peux aussi saisir ce code dans l'onglet ouvert : {code}",
        ],
        cta_label="Me connecter",
        cta_url=link,
        footer="Tu n'as rien demandé ? Ignore ce message : sans clic, rien ne se passe.",
    )
    result = await send_mail(Mail(
        to=email, subject=content.subject,
        text=render_text(content), html=render_html(content),
    ))
    if not result.get("real"):
        # En local sans transport, le lien est utilisable depuis les logs.
        logger.warning("Lien de connexion non envoyé (%s) : %s", result.get("error"), link)


class VerifyIn(BaseModel):
    token: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None
    code: str | None = Field(default=None, max_length=10)


class SessionOut(BaseModel):
    access_token: str
    expires_at: datetime
    email: str


@router.post("/verify", response_model=SessionOut)
async def verify(body: VerifyIn):
    if not settings.auth_secret or not auth_configured():
        raise HTTPException(503, "Connexion par e-mail non configurée (AUTH_SECRET).")

    now = datetime.now(timezone.utc)
    invalid = HTTPException(400, "Ce lien ou ce code n'est plus valable. Demande-en un nouveau.")

    async with async_session() as session:
        if body.token:
            row = (await session.execute(
                select(LoginToken).where(LoginToken.token_hash == _hash(body.token))
            )).scalar_one_or_none()
        elif body.email and body.code:
            email = body.email.strip().lower()
            row = (await session.execute(
                select(LoginToken)
                .where(LoginToken.email == email)
                .where(LoginToken.used_at.is_(None))
                .where(LoginToken.expires_at > now)
                .order_by(LoginToken.created_at.desc())
                .limit(1)
            )).scalar_one_or_none()
            if row:
                row.attempts += 1
                if row.attempts > MAX_CODE_ATTEMPTS or row.code_hash != _hash(f"{email}:{body.code.strip()}"):
                    await session.commit()
                    raise invalid
        else:
            raise invalid

        if not row or row.used_at or row.expires_at <= now:
            raise invalid
        row.used_at = now
        email = row.email
        await session.commit()

    token, expires = issue_session(email)
    return SessionOut(access_token=token, expires_at=expires, email=email)
