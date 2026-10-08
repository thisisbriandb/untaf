"""
Abonnement : ce que voit le candidat, le paiement, l'espace client, et le
webhook par lequel Lemon Squeezy tient l'état à jour.
"""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app import billing
from app.config import settings
from app.database import async_session, get_db
from app.models.candidate import Candidate

logger = logging.getLogger(__name__)
router = APIRouter(tags=["billing"])


@router.get("/candidates/{candidate_id}/billing")
async def get_billing(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    if not await db.get(Candidate, candidate_id):
        raise HTTPException(404, "Candidat introuvable")
    return await billing.overview(db, candidate_id)


@router.post("/candidates/{candidate_id}/billing/checkout")
async def start_checkout(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    if not settings.billing_enabled:
        raise HTTPException(503, "L'abonnement n'est pas encore ouvert.")
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidat introuvable")
    if await billing.active_subscription(db, candidate_id):
        raise HTTPException(409, "Tu es déjà abonné.")
    try:
        url = await billing.create_checkout(candidate_id, candidate.email, candidate.full_name)
    except Exception as e:  # noqa: BLE001
        logger.error("Paiement impossible pour %s : %s", candidate_id, e)
        raise HTTPException(502, "Le paiement n'a pas pu être préparé. Réessaie dans un instant.")
    return {"url": url}


@router.post("/candidates/{candidate_id}/billing/sync")
async def sync_billing(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """Au retour du paiement : relit l'abonnement chez Lemon Squeezy sans attendre le webhook."""
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidat introuvable")
    try:
        await billing.sync_from_provider(db, candidate_id, candidate.email)
        await db.commit()
    except Exception as e:  # noqa: BLE001 — on rend l'état connu, même si la relecture échoue
        logger.error("Relecture de l'abonnement impossible pour %s : %s", candidate_id, e)
        await db.rollback()
    return await billing.overview(db, candidate_id)


@router.post("/candidates/{candidate_id}/billing/portal")
async def open_portal(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """Carte bancaire, factures, résiliation : l'espace client Lemon Squeezy."""
    sub = await billing.active_subscription(db, candidate_id)
    if not sub:
        raise HTTPException(404, "Aucun abonnement en cours.")
    url = await billing.portal_url(sub.provider_id)
    if not url:
        raise HTTPException(502, "L'espace client est momentanément indisponible.")
    return {"url": url}


@router.post("/billing/lemonsqueezy")
async def lemonsqueezy_webhook(request: Request):
    raw = await request.body()
    if not billing.verify_signature(raw, request.headers.get("X-Signature")):
        raise HTTPException(401, "Signature invalide")
    try:
        payload = json.loads(raw)
    except ValueError:
        raise HTTPException(400, "Corps illisible")
    event = billing.parse_event(payload)
    if not event:
        return {"ok": True, "ignored": True}
    async with async_session() as session:
        known = await billing.apply_event(session, event)
        await session.commit()
    logger.info("Abonnement %s : %s (%s)", event.provider_id, event.status,
                (payload.get("meta") or {}).get("event_name"))
    # 200 même pour un abonnement orphelin : le renvoyer ne le rattacherait pas.
    return {"ok": True, "applied": known}
