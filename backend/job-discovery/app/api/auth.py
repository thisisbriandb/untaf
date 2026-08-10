"""
API d'authentification — connexion, déconnexion, session courante.

Pas de POST /auth/register séparé : POST /candidates/ porte déjà tout le
flux d'inscription (profil complet construit par l'onboarding), il prend
juste un mot de passe en plus et pose la session à la création.
"""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_candidate
from app.auth.security import verify_password
from app.auth.session import delete_session, issue_session
from app.config import settings
from app.database import get_db
from app.models.candidate import Candidate
from app.schemas.candidate import CandidateOut

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


@router.post("/login", response_model=CandidateOut)
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    candidate = await db.scalar(
        select(Candidate).where(func.lower(Candidate.email) == data.email.strip().lower())
    )
    if not candidate or not candidate.password_hash or not verify_password(
        data.password, candidate.password_hash
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email ou mot de passe incorrect.")

    await issue_session(response, candidate)
    return candidate


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
):
    if session_id:
        await delete_session(session_id)
    response.delete_cookie(
        settings.session_cookie_name, path="/", samesite=settings.session_cookie_samesite
    )


@router.get("/me", response_model=CandidateOut)
async def me(current: Candidate = Depends(get_current_candidate)):
    return current
