"""
Rattachement d'un compte authentifié à son profil candidat.

Les profils créés avant l'authentification n'ont pas de propriétaire. Ils sont
rattachés à la première connexion dont l'adresse e-mail est la même : Supabase
ne délivre de session qu'après preuve de possession de l'adresse (lien ou code
reçu par e-mail), c'est donc cette preuve qui fait foi. Le projet Supabase doit
exiger la confirmation de l'e-mail — c'est son réglage par défaut.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthUser
from app.models.candidate import Candidate

logger = logging.getLogger(__name__)


async def claim_candidate(db: AsyncSession, user: AuthUser) -> Candidate | None:
    """Le profil de cet utilisateur, rattaché au passage s'il était orphelin."""
    candidate = await db.scalar(select(Candidate).where(Candidate.auth_user_id == user.id))
    if candidate or not user.email:
        return candidate

    orphan = await db.scalar(
        select(Candidate)
        .where(func.lower(Candidate.email) == user.email)
        .where(Candidate.auth_user_id.is_(None))
    )
    if orphan:
        orphan.auth_user_id = user.id
        await db.commit()
        await db.refresh(orphan)
        logger.info("Profil %s rattaché au compte %s", orphan.id, user.id)
    return orphan
