"""
Limites de débit, pour les routes qui coûtent (IA, mise en page) et que l'on
ne peut pas compter dans une formule : celles de l'inscription, appelées avant
toute connexion (lecture du CV, aperçu des modèles).

Fenêtre glissante en mémoire, par processus : ce n'est pas une comptabilité
exacte — plusieurs instances ont chacune leur compteur — mais un garde-fou
qui empêche de saigner le service en boucle. Les formules (`billing`) restent
la vraie limite des utilisateurs connectés.

Clé : l'utilisateur connecté s'il y en a un, sinon l'adresse IP. Un plafond
global par route borne en plus le coût total d'une attaque répartie.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request

from app.auth import AuthUser, get_user

HOUR = 3600.0

_hits: dict[str, deque[float]] = defaultdict(deque)


def hit(key: str, limit: int, window: float = HOUR, now: float | None = None) -> bool:
    """Compte un appel ; False si la limite de la fenêtre est déjà atteinte."""
    now = time.monotonic() if now is None else now
    q = _hits[key]
    while q and now - q[0] >= window:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def reset() -> None:
    _hits.clear()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "inconnu"


def limited(name: str, anonymous: int, user: int, overall: int):
    """
    Dépendance FastAPI : `anonymous` appels par heure et par IP sans
    connexion, `user` par utilisateur connecté, `overall` pour la route
    entière (tous appelants confondus).
    """
    async def guard(request: Request, who: AuthUser | None = Depends(get_user)) -> None:
        key, limit = ((f"u:{who.id}", user) if who and who.id.int else (f"ip:{client_ip(request)}", anonymous))
        if not hit(f"{name}:{key}", limit) or not hit(f"{name}:*", overall):
            raise HTTPException(429, "Trop de demandes d'un coup. Réessaie dans un moment.")
    return guard
