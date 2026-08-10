"""
Sessions côté serveur, stockées dans Redis.

Le cookie ne porte qu'un identifiant aléatoire opaque — jamais l'identité du
candidat, jamais de contenu signé à décoder. Révoquer une session (déconnexion,
compromission) se résume à supprimer une clé : pas de jeton auto-suffisant qui
resterait valide jusqu'à son expiration même après une déconnexion explicite.

Réutilise `settings.redis_url`, déjà requis pour Celery — aucune nouvelle
dépendance ni nouvelle variable d'environnement.
"""

import secrets
from uuid import UUID

import redis.asyncio as redis
from fastapi import Response

from app.config import settings

_redis: redis.Redis | None = None


def _client() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _key(session_id: str) -> str:
    return f"session:{session_id}"


async def create_session(candidate_id: UUID) -> str:
    session_id = secrets.token_urlsafe(32)
    await _client().set(_key(session_id), str(candidate_id), ex=settings.session_ttl_seconds)
    return session_id


async def get_session(session_id: str) -> UUID | None:
    raw = await _client().get(_key(session_id))
    if raw is None:
        return None
    # Fenêtre glissante : une session active ne doit pas expirer sous les
    # pieds de quelqu'un qui utilise l'app en continu.
    await _client().expire(_key(session_id), settings.session_ttl_seconds)
    return UUID(raw)


async def delete_session(session_id: str) -> None:
    await _client().delete(_key(session_id))


async def issue_session(response: Response, candidate) -> None:
    """Crée une session et pose le cookie httpOnly sur la réponse donnée."""
    session_id = await create_session(candidate.id)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_ttl_seconds,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
    )
