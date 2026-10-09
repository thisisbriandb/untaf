"""
Signer sur son téléphone, depuis un ordinateur.

1. L'ordinateur crée une session (POST) et affiche un QR code vers
   /signer?t=<jeton>.
2. Le téléphone ouvre la page, signe au doigt, dépose l'image (POST /{jeton}).
3. L'ordinateur interroge la session (GET /{jeton}) et récupère l'image.

Sans compte : l'inscription n'est pas finie quand on signe. Le jeton est long,
aléatoire, à usage unique, et expire au bout de dix minutes ; l'image n'est
lisible qu'avec lui. Création limitée par adresse (route publique).
"""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.signature_session import SignatureSession
from app.ratelimit import limited

router = APIRouter(prefix="/signature-sessions", tags=["signature"])

TTL = timedelta(minutes=10)
#: Une signature au doigt pèse quelques dizaines de Ko ; au-delà, ce n'en est pas une.
MAX_IMAGE_CHARS = 1_400_000


class SessionOut(BaseModel):
    token: str
    expires_at: datetime


class SessionState(BaseModel):
    status: str  # pending | signed | expired
    image: str | None = None


class SignatureIn(BaseModel):
    image: str


def _expired(session: SignatureSession, now: datetime) -> bool:
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires <= now


async def _get(db: AsyncSession, token: str) -> SignatureSession:
    session = (await db.execute(
        select(SignatureSession).where(SignatureSession.token == token)
    )).scalars().first()
    if not session:
        raise HTTPException(404, "Ce lien de signature n'existe pas ou a déjà servi.")
    return session


@router.post("", response_model=SessionOut, status_code=201,
             dependencies=[Depends(limited("signature-session", anonymous=20, user=40, overall=5000))])
async def open_session(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    # Ménage au passage : les sessions périmées n'ont plus rien à garder.
    await db.execute(delete(SignatureSession).where(SignatureSession.expires_at < now))
    session = SignatureSession(token=secrets.token_urlsafe(32), expires_at=now + TTL)
    db.add(session)
    await db.commit()
    return SessionOut(token=session.token, expires_at=session.expires_at)


@router.get("/{token}", response_model=SessionState)
async def session_state(token: str, db: AsyncSession = Depends(get_db)):
    """Interrogé par l'ordinateur ; l'image n'est rendue qu'une fois, puis effacée."""
    session = await _get(db, token)
    if session.image:
        image = session.image
        await db.delete(session)
        await db.commit()
        return SessionState(status="signed", image=image)
    if _expired(session, datetime.now(timezone.utc)):
        return SessionState(status="expired")
    return SessionState(status="pending")


@router.post("/{token}", response_model=SessionState)
async def drop_signature(token: str, data: SignatureIn, db: AsyncSession = Depends(get_db)):
    """Le téléphone dépose la signature."""
    session = await _get(db, token)
    if _expired(session, datetime.now(timezone.utc)):
        raise HTTPException(410, "Ce lien a expiré : affiche un nouveau QR code sur ton ordinateur.")
    if session.image:
        raise HTTPException(409, "Une signature a déjà été envoyée avec ce lien.")
    if not data.image.startswith("data:image/png;base64,"):
        raise HTTPException(400, "La signature doit être une image PNG.")
    if len(data.image) > MAX_IMAGE_CHARS:
        raise HTTPException(413, "Signature trop volumineuse.")
    session.image = data.image
    await db.commit()
    return SessionState(status="signed")
