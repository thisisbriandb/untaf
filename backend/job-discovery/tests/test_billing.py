"""Abonnement hebdomadaire : accès, webhook Lemon Squeezy, limites."""

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app import billing


NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def test_access_by_status():
    assert billing.grants_access("active", None, NOW)
    assert billing.grants_access("on_trial", None, NOW)
    # Paiement en échec : Lemon Squeezy réessaie, on ne coupe pas pendant ce temps.
    assert billing.grants_access("past_due", None, NOW)
    assert not billing.grants_access("expired", None, NOW)
    assert not billing.grants_access("unpaid", None, NOW)
    assert not billing.grants_access("paused", None, NOW)
    assert not billing.grants_access(None, None, NOW)


def test_cancelled_keeps_access_until_end_of_paid_week():
    assert billing.grants_access("cancelled", NOW + timedelta(days=3), NOW)
    assert not billing.grants_access("cancelled", NOW - timedelta(minutes=1), NOW)
    assert not billing.grants_access("cancelled", None, NOW)
    # Date sans fuseau (selon le pilote de base) : lue comme UTC.
    assert billing.grants_access("cancelled", (NOW + timedelta(days=1)).replace(tzinfo=None), NOW)


def test_signature(monkeypatch):
    monkeypatch.setattr(billing.settings, "lemonsqueezy_webhook_secret", "s3cret")
    raw = b'{"meta":{}}'
    good = hmac.new(b"s3cret", raw, hashlib.sha256).hexdigest()
    assert billing.verify_signature(raw, good)
    assert not billing.verify_signature(raw, "0" * 64)
    assert not billing.verify_signature(raw + b" ", good)
    assert not billing.verify_signature(raw, None)
    monkeypatch.setattr(billing.settings, "lemonsqueezy_webhook_secret", "")
    assert not billing.verify_signature(raw, good)


def _payload(candidate_id, status="active", type_="subscriptions", **attrs):
    return {
        "meta": {"event_name": "subscription_created", "custom_data": {"candidate_id": str(candidate_id)}},
        "data": {"type": type_, "id": "123456", "attributes": {
            "status": status, "customer_id": 42, "variant_id": 7,
            "renews_at": "2026-10-15T12:00:00.000000Z", "ends_at": None, "test_mode": True, **attrs,
        }},
    }


def test_parse_subscription_event():
    cid = uuid4()
    event = billing.parse_event(_payload(cid))
    assert event.provider_id == "123456"
    assert event.candidate_id == cid
    assert event.status == "active"
    assert event.customer_id == "42" and event.variant_id == "7"
    assert event.renews_at == datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
    assert event.ends_at is None and event.test_mode


def test_invoices_and_orders_are_ignored():
    assert billing.parse_event(_payload(uuid4(), type_="subscription-invoices")) is None
    assert billing.parse_event(_payload(uuid4(), type_="orders")) is None
    assert billing.parse_event({}) is None


def test_bad_candidate_id_is_not_trusted():
    payload = _payload("pas-un-uuid")
    assert billing.parse_event(payload).candidate_id is None


def test_checkout_carries_candidate(monkeypatch):
    monkeypatch.setattr(billing.settings, "lemonsqueezy_store_id", "11")
    monkeypatch.setattr(billing.settings, "lemonsqueezy_variant_id", "22")
    cid = uuid4()
    body = billing.checkout_body(cid, "a@b.fr", "Ada Lovelace", "https://alice-agent.fr/dashboard")
    data = body["data"]
    assert data["attributes"]["checkout_data"]["custom"] == {"candidate_id": str(cid)}
    assert data["attributes"]["checkout_data"]["email"] == "a@b.fr"
    assert data["relationships"]["store"]["data"]["id"] == "11"
    assert data["relationships"]["variant"]["data"]["id"] == "22"
    json.dumps(body)  # sérialisable tel quel


def test_limit_messages():
    free = billing.LimitReached("pack", 3, 3, paid=False)
    assert "3 dossiers de candidature gratuits cette semaine" in str(free)
    assert "abonnement" in str(free)
    assert free.detail()["code"] == "plan_limit"
    assert "font partie de l'abonnement" in str(billing.LimitReached("spontaneous", 0, 0, paid=False))
    paid = billing.LimitReached("message", 200, 200, paid=True)
    assert "aujourd'hui" in str(paid) and "abus" in str(paid)


def test_no_limit_when_billing_is_off(monkeypatch):
    monkeypatch.setattr(billing.settings, "lemonsqueezy_api_key", "")
    # Ne touche pas la base : la facturation éteinte ne limite rien.
    asyncio.run(billing.check(object(), uuid4(), "pack", count=10_000))


@pytest.mark.parametrize("paid,used,ok", [(False, 2, True), (False, 3, False), (True, 39, True), (True, 40, False)])
def test_check_against_plan(monkeypatch, paid, used, ok):
    for key, value in {"lemonsqueezy_api_key": "k", "lemonsqueezy_store_id": "1",
                       "lemonsqueezy_variant_id": "2", "free_packs_per_week": 3,
                       "paid_packs_per_week": 40}.items():
        monkeypatch.setattr(billing.settings, key, value)

    async def limits_for(session, cid):
        return (billing.paid_limits() if paid else billing.free_limits()), paid

    async def used_(session, cid, kind):
        return used

    monkeypatch.setattr(billing, "limits_for", limits_for)
    monkeypatch.setattr(billing, "used", used_)
    if ok:
        asyncio.run(billing.check(None, uuid4(), "pack"))
    else:
        with pytest.raises(billing.LimitReached):
            asyncio.run(billing.check(None, uuid4(), "pack"))
