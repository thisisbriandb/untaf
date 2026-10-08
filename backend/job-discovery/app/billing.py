"""
Abonnement hebdomadaire (Lemon Squeezy) et limites d'usage.

Deux formules :
  - gratuite : de quoi essayer Alice pour de vrai (quelques dossiers, une
    mission par semaine) ;
  - « Alice — semaine » : abonnement hebdomadaire sans engagement, résiliable
    en un clic ; ses plafonds ne sont là que contre les abus.

Ce qui coûte est compté dans `usage_events` : un dossier rédigé (deux appels
au modèle), une mission, un message à Alice, une candidature spontanée. Les
fenêtres sont glissantes (7 jours, 24 heures) : pas de remise à zéro le lundi
qui inviterait à tout consommer le dimanche.

Sans configuration Lemon Squeezy, la facturation est éteinte : rien n'est
limité, l'usage est seulement compté.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from sqlalchemy import func, select

from app.config import settings

logger = logging.getLogger(__name__)

API = "https://api.lemonsqueezy.com/v1"

#: Statuts Lemon Squeezy qui donnent accès. `past_due` : le paiement a échoué,
#: Lemon Squeezy réessaie pendant quelques jours ; on ne coupe pas pendant ce
#: temps. `cancelled` donne accès jusqu'à `ends_at` (semaine déjà payée).
ACTIVE_STATUSES = {"active", "on_trial", "past_due"}

WEEK = timedelta(days=7)
DAY = timedelta(days=1)


@dataclass(frozen=True)
class Limits:
    packs_per_week: int
    missions_per_week: int
    spontaneous_per_week: int
    messages_per_day: int


def free_limits() -> Limits:
    return Limits(settings.free_packs_per_week, settings.free_missions_per_week,
                  settings.free_spontaneous_per_week, settings.free_messages_per_day)


def paid_limits() -> Limits:
    return Limits(settings.paid_packs_per_week, settings.paid_missions_per_week,
                  settings.spontaneous_weekly_cap, settings.paid_messages_per_day)


#: kind → (champ de Limits, fenêtre, ce qu'on dit quand c'est atteint)
KINDS = {
    "pack": ("packs_per_week", WEEK, "dossiers de candidature"),
    "mission": ("missions_per_week", WEEK, "missions"),
    "spontaneous": ("spontaneous_per_week", WEEK, "candidatures spontanées"),
    "message": ("messages_per_day", DAY, "messages à Alice"),
}


class LimitReached(Exception):
    """Limite de la formule atteinte : à montrer, avec de quoi s'abonner."""

    def __init__(self, kind: str, used: int, limit: int, paid: bool):
        self.kind, self.used, self.limit, self.paid = kind, used, limit, paid
        label, window = KINDS[kind][2], ("aujourd'hui" if KINDS[kind][1] == DAY else "cette semaine")
        if paid:
            msg = (f"Tu as atteint le plafond de {limit} {label} {window}. "
                   "Il protège le service contre les abus ; il se libère au fil des jours.")
        elif limit == 0:
            msg = f"Les {label} font partie de l'abonnement Alice ({settings.billing_price_label})."
        else:
            msg = (f"Tu as utilisé tes {limit} {label} gratuits {window}. "
                   f"Avec l'abonnement ({settings.billing_price_label}, sans engagement), "
                   "Alice continue sans attendre.")
        super().__init__(msg)

    def detail(self) -> dict:
        return {"code": "plan_limit", "kind": self.kind, "used": self.used,
                "limit": self.limit, "paid": self.paid, "message": str(self)}


# ── Accès ──────────────────────────────────────────────────────────────────

def _aware(dt: datetime | None) -> datetime | None:
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def grants_access(status: str | None, ends_at: datetime | None,
                  now: datetime | None = None) -> bool:
    """Cet abonnement ouvre-t-il l'accès maintenant ?"""
    now = now or datetime.now(timezone.utc)
    if status in ACTIVE_STATUSES:
        return True
    if status == "cancelled":
        ends = _aware(ends_at)
        return bool(ends and ends > now)
    return False


async def active_subscription(session, candidate_id: UUID):
    from app.models.billing import Subscription

    subs = (await session.execute(
        select(Subscription).where(Subscription.candidate_id == candidate_id)
        .order_by(Subscription.updated_at.desc())
    )).scalars().all()
    return next((s for s in subs if grants_access(s.status, s.ends_at)), None)


async def limits_for(session, candidate_id: UUID) -> tuple[Limits, bool]:
    """(limites, abonné ?). Facturation éteinte : abonné d'office."""
    if not settings.billing_enabled:
        return paid_limits(), True
    paid = await active_subscription(session, candidate_id) is not None
    return (paid_limits() if paid else free_limits()), paid


async def used(session, candidate_id: UUID, kind: str) -> int:
    from app.models.billing import UsageEvent

    since = datetime.now(timezone.utc) - KINDS[kind][1]
    return (await session.execute(
        select(func.count(UsageEvent.id))
        .where(UsageEvent.candidate_id == candidate_id)
        .where(UsageEvent.kind == kind)
        .where(UsageEvent.created_at >= since)
    )).scalar() or 0


async def remaining(session, candidate_id: UUID, kind: str) -> int:
    limits, _ = await limits_for(session, candidate_id)
    return max(0, getattr(limits, KINDS[kind][0]) - await used(session, candidate_id, kind))


async def check(session, candidate_id: UUID, kind: str, count: int = 1) -> None:
    """Lève LimitReached si `count` de plus dépasserait la formule."""
    if not settings.billing_enabled:
        return
    limits, paid = await limits_for(session, candidate_id)
    limit = getattr(limits, KINDS[kind][0])
    n = await used(session, candidate_id, kind)
    if n + count > limit:
        raise LimitReached(kind, n, limit, paid)


async def record(session, candidate_id: UUID, kind: str, count: int = 1) -> None:
    """Compte un usage (la session appelante commite)."""
    from app.models.billing import UsageEvent

    for _ in range(count):
        session.add(UsageEvent(candidate_id=candidate_id, kind=kind))


async def consume(candidate_id: UUID, kind: str) -> None:
    """Vérifie puis compte, dans sa propre session : pour les appels isolés."""
    from app.database import async_session

    async with async_session() as session:
        await check(session, candidate_id, kind)
        await record(session, candidate_id, kind)
        await session.commit()


async def overview(session, candidate_id: UUID) -> dict:
    """Ce que voit le candidat : formule, usage, limites."""
    limits, paid = await limits_for(session, candidate_id)
    sub = await active_subscription(session, candidate_id) if settings.billing_enabled else None
    usage = {}
    for kind, (field, window, label) in KINDS.items():
        usage[kind] = {"used": await used(session, candidate_id, kind),
                       "limit": getattr(limits, field), "label": label,
                       "window": "day" if window == DAY else "week"}
    return {
        "enabled": settings.billing_enabled,
        "plan": "weekly" if paid else "free",
        "price_label": settings.billing_price_label,
        "status": sub.status if sub else None,
        "renews_at": sub.renews_at.isoformat() if sub and sub.renews_at else None,
        "ends_at": sub.ends_at.isoformat() if sub and sub.ends_at else None,
        "cancelled": bool(sub and sub.status == "cancelled"),
        "usage": usage,
    }


# ── Lemon Squeezy ──────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
        "Authorization": f"Bearer {settings.lemonsqueezy_api_key}",
    }


def checkout_body(candidate_id: UUID, email: str | None, name: str | None,
                  redirect_url: str) -> dict:
    checkout_data: dict = {"custom": {"candidate_id": str(candidate_id)}}
    if email:
        checkout_data["email"] = email
    if name:
        checkout_data["name"] = name
    return {"data": {
        "type": "checkouts",
        "attributes": {
            "checkout_data": checkout_data,
            "product_options": {"redirect_url": redirect_url},
        },
        "relationships": {
            "store": {"data": {"type": "stores", "id": str(settings.lemonsqueezy_store_id)}},
            "variant": {"data": {"type": "variants", "id": str(settings.lemonsqueezy_variant_id)}},
        },
    }}


async def create_checkout(candidate_id: UUID, email: str | None, name: str | None) -> str:
    """URL de paiement Lemon Squeezy, rattachée au candidat."""
    redirect = f"{settings.frontend_url.rstrip('/')}/dashboard?abonnement=merci"
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.post(f"{API}/checkouts", headers=_headers(),
                                json=checkout_body(candidate_id, email, name, redirect))
    if res.status_code >= 300:
        logger.error("Lemon Squeezy a refusé la création du paiement (%s) : %s",
                     res.status_code, res.text[:500])
        raise RuntimeError("Le paiement n'a pas pu être préparé.")
    return res.json()["data"]["attributes"]["url"]


async def portal_url(provider_id: str) -> str | None:
    """Lien signé (valable 24 h) vers l'espace client : carte, factures, résiliation."""
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.get(f"{API}/subscriptions/{provider_id}", headers=_headers())
    if res.status_code >= 300:
        logger.error("Abonnement %s illisible chez Lemon Squeezy (%s).", provider_id, res.status_code)
        return None
    return ((res.json()["data"]["attributes"].get("urls") or {}).get("customer_portal"))


def verify_signature(raw: bytes, signature: str | None) -> bool:
    secret = settings.lemonsqueezy_webhook_secret
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def _date(value) -> datetime | None:
    if not value:
        return None
    try:
        return _aware(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        return None


@dataclass
class SubscriptionEvent:
    provider_id: str
    candidate_id: UUID | None
    status: str
    customer_id: str | None
    variant_id: str | None
    renews_at: datetime | None
    ends_at: datetime | None
    test_mode: bool


def parse_event(payload: dict) -> SubscriptionEvent | None:
    """Un événement d'abonnement, ou None (factures, commandes : ignorées)."""
    data = payload.get("data") or {}
    if data.get("type") != "subscriptions" or not data.get("id"):
        return None
    attrs = data.get("attributes") or {}
    custom = (payload.get("meta") or {}).get("custom_data") or {}
    try:
        candidate_id = UUID(str(custom.get("candidate_id"))) if custom.get("candidate_id") else None
    except ValueError:
        candidate_id = None
    return SubscriptionEvent(
        provider_id=str(data["id"]),
        candidate_id=candidate_id,
        status=str(attrs.get("status") or ""),
        customer_id=str(attrs["customer_id"]) if attrs.get("customer_id") else None,
        variant_id=str(attrs["variant_id"]) if attrs.get("variant_id") else None,
        renews_at=_date(attrs.get("renews_at")),
        ends_at=_date(attrs.get("ends_at")),
        test_mode=bool(attrs.get("test_mode")),
    )


async def apply_event(session, event: SubscriptionEvent) -> bool:
    """Reporte l'état de l'abonnement. False si on ne sait pas à qui il est."""
    from app.models.billing import Subscription
    from app.models.candidate import Candidate

    sub = (await session.execute(
        select(Subscription).where(Subscription.provider_id == event.provider_id)
    )).scalars().first()
    if not sub:
        if not event.candidate_id or not await session.get(Candidate, event.candidate_id):
            logger.error("Abonnement %s sans candidat connu : ignoré.", event.provider_id)
            return False
        sub = Subscription(provider_id=event.provider_id, candidate_id=event.candidate_id)
        session.add(sub)
    sub.status = event.status
    sub.customer_id = event.customer_id or sub.customer_id
    sub.variant_id = event.variant_id or sub.variant_id
    sub.renews_at = event.renews_at
    sub.ends_at = event.ends_at
    sub.test_mode = event.test_mode
    sub.updated_at = datetime.now(timezone.utc)
    return True


async def sync_from_provider(session, candidate_id: UUID, email: str | None) -> int:
    """
    Relit chez Lemon Squeezy les abonnements de cette adresse et les reporte.

    Filet de sécurité du webhook : au retour du paiement, l'abonnement est
    visible tout de suite, même si le webhook est en retard, mal configuré ou
    perdu. Seuls les abonnements au produit d'Alice (sa variante) sont repris.
    """
    if not settings.billing_enabled or not email:
        return 0
    params = {"filter[store_id]": settings.lemonsqueezy_store_id,
              "filter[user_email]": email.strip().lower()}
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.get(f"{API}/subscriptions", headers=_headers(), params=params)
    if res.status_code >= 300:
        logger.error("Abonnements illisibles chez Lemon Squeezy (%s) : %s",
                     res.status_code, res.text[:300])
        return 0
    applied = 0
    for item in res.json().get("data") or []:
        event = parse_event({"data": item, "meta": {"custom_data": {"candidate_id": str(candidate_id)}}})
        if not event or event.variant_id != str(settings.lemonsqueezy_variant_id):
            continue
        if await apply_event(session, event):
            applied += 1
    return applied
