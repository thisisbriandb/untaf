"""
Qui suis-je ? — le point d'entrée du frontend après connexion.

Remplace le `candidate_id` gardé dans le navigateur comme source de vérité :
c'est le jeton qui désigne l'utilisateur, et le serveur qui dit quel profil
lui appartient.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.account import claim_candidate
from app.auth import AuthUser, require_user
from app.config import settings
from app.database import get_db

router = APIRouter(tags=["auth"])


class MeOut(BaseModel):
    user_id: UUID
    email: str | None
    #: Null tant que l'onboarding n'a pas créé le profil.
    candidate_id: UUID | None
    auth_disabled: bool = False


@router.get("/me", response_model=MeOut)
async def me(user: AuthUser = Depends(require_user), db: AsyncSession = Depends(get_db)):
    if settings.auth_disabled:
        return MeOut(user_id=user.id, email=None, candidate_id=None, auth_disabled=True)
    candidate = await claim_candidate(db, user)
    return MeOut(
        user_id=user.id, email=user.email,
        candidate_id=candidate.id if candidate else None,
    )
