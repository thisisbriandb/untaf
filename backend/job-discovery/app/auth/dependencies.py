"""
Dépendances FastAPI pour l'authentification — même style que `get_db` dans
`app/database.py` : fonctions async simples, importées directement là où
elles servent.
"""

from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_session
from app.config import settings
from app.database import get_db
from app.models.candidate import Candidate


async def get_current_candidate(
    session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    db: AsyncSession = Depends(get_db),
) -> Candidate:
    if not session_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Non authentifié")

    candidate_id = await get_session(session_id)
    if not candidate_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session invalide ou expirée")

    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Compte introuvable")

    return candidate


def ensure_owner(current: Candidate, resource_candidate_id: UUID) -> None:
    if current.id != resource_candidate_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès interdit")


async def require_owner(
    candidate_id: UUID,
    current: Candidate = Depends(get_current_candidate),
) -> Candidate:
    """
    À utiliser comme dépendance sur une route (ou un routeur entier) qui
    porte un paramètre `candidate_id` — path ou query, FastAPI ne fait pas
    la différence pour la résolution. Lève 401 si non connecté, 403 si
    connecté mais pas propriétaire de la ressource visée.
    """
    ensure_owner(current, candidate_id)
    return current
