"""
Authentification — qui appelle, et a-t-il le droit de toucher ce profil ?

Avant ce module, l'identité tenait à un `candidate_id` gardé dans le
navigateur : connaître un identifiant suffisait pour lire le CV, la signature
et les lettres de quelqu'un, ou valider des envois en son nom. Désormais chaque
requête porte un jeton Supabase, vérifié ici, et un candidat n'est accessible
qu'à l'utilisateur auquel il est rattaché (`Candidate.auth_user_id`).

Trois règles :
  - toute route dont le chemin contient `{candidate_id}` est gardée par
    `guard_candidate_path`, posée au niveau de l'application : une route
    ajoutée demain est protégée sans qu'on ait à y penser ;
  - les routes sans ce paramètre qui touchent des données personnelles ont
    leur garde explicite (`require_user`, `assert_owner`) ;
  - sans configuration, on refuse plutôt que d'ouvrir : seul
    `AUTH_DISABLED=true`, réservé au développement local, lève les gardes.

Jetons acceptés : HS256 signé par le secret JWT du projet (clés historiques),
ou ES256/RS256 vérifié contre le JWKS public du projet (nouvelles clés).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

#: Audience des jetons d'utilisateurs connectés sur Supabase.
AUDIENCE = "authenticated"


@dataclass(frozen=True)
class AuthUser:
    id: UUID
    email: str | None


#: Utilisateur fictif du mode développement : jamais rattaché à un candidat,
#: il ne sert qu'à laisser passer les gardes.
DEV_USER = AuthUser(id=UUID(int=0), email=None)


def auth_configured() -> bool:
    return bool(settings.supabase_jwt_secret or settings.supabase_url)


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    url = settings.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)


def _decode(token: str) -> dict:
    """Vérifie signature, expiration et audience. Lève jwt.PyJWTError."""
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "")
    options = {"require": ["exp", "sub"]}

    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            raise jwt.InvalidTokenError("jeton HS256 mais SUPABASE_JWT_SECRET absent")
        return jwt.decode(
            token, settings.supabase_jwt_secret, algorithms=["HS256"],
            audience=AUDIENCE, options=options,
        )

    if alg in ("ES256", "RS256") and settings.supabase_url:
        key = _jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=[alg], audience=AUDIENCE, options=options)

    raise jwt.InvalidTokenError(f"algorithme non accepté : {alg or 'absent'}")


async def get_user(request: Request) -> AuthUser | None:
    """L'utilisateur du jeton, ou None s'il n'y en a pas. Lève 401 s'il est invalide."""
    if settings.auth_bypassed:
        return DEV_USER

    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    if not auth_configured():
        raise HTTPException(503, "Authentification non configurée sur ce serveur.")

    try:
        # Le JWKS se récupère en HTTP synchrone (mis en cache ensuite).
        claims = await asyncio.to_thread(_decode, token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expirée — reconnecte-toi.") from None
    except jwt.PyJWTError as e:
        logger.info("Jeton refusé : %s", e)
        raise HTTPException(401, "Jeton d'authentification invalide.") from None

    try:
        user_id = UUID(claims["sub"])
    except (KeyError, ValueError):
        raise HTTPException(401, "Jeton d'authentification invalide.") from None
    email = (claims.get("email") or "").strip().lower() or None
    return AuthUser(id=user_id, email=email)


async def require_user(user: AuthUser | None = Depends(get_user)) -> AuthUser:
    if user is None:
        if not auth_configured():
            raise HTTPException(503, "Authentification non configurée sur ce serveur.")
        raise HTTPException(401, "Connexion requise.")
    return user


async def require_admin(user: AuthUser = Depends(require_user)) -> AuthUser:
    """Déclencheurs coûteux (scraping, seeding) : réservés aux administrateurs."""
    if settings.auth_bypassed:
        return user
    if not user.email or user.email not in settings.admin_email_list:
        raise HTTPException(403, "Réservé aux administrateurs.")
    return user


async def assert_owner(db: AsyncSession, user: AuthUser, candidate_id: UUID) -> None:
    """
    Le candidat appartient-il à cet utilisateur ? 404 sinon — pas 403 : on ne
    confirme pas l'existence d'un profil à qui n'y a pas droit.
    """
    if settings.auth_bypassed:
        return
    from app.models.candidate import Candidate

    owner = (await db.execute(
        select(Candidate.auth_user_id).where(Candidate.id == candidate_id)
    )).first()
    if owner is None or owner[0] != user.id:
        raise HTTPException(404, "Profil introuvable.")


async def guard_candidate_path(
    request: Request,
    user: AuthUser | None = Depends(get_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Garde globale : si le chemin désigne un candidat, l'appelant doit en être
    le propriétaire. Sans effet sur les autres routes.
    """
    raw = request.path_params.get("candidate_id")
    if raw is None:
        return
    user = await require_user(user)
    try:
        candidate_id = UUID(str(raw))
    except ValueError:
        raise HTTPException(404, "Profil introuvable.") from None
    await assert_owner(db, user, candidate_id)
