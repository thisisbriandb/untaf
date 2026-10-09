"""Signature par téléphone : la session, de la création à la récupération."""

import asyncio
import os

import pytest

PG = os.environ.get("ALICE_TEST_PG")


@pytest.mark.skipif(not PG, reason="Postgres de test non fourni (ALICE_TEST_PG)")
def test_phone_signature_roundtrip():
    import httpx
    from app import ratelimit
    from app.main import app

    ratelimit.reset()
    png = "data:image/png;base64,iVBORw0KGgo="

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            token = (await c.post("/api/signature-sessions")).json()["token"]
            assert (await c.get(f"/api/signature-sessions/{token}")).json()["status"] == "pending"
            assert (await c.post(f"/api/signature-sessions/{token}", json={"image": "data:text/html,x"})).status_code == 400
            assert (await c.post(f"/api/signature-sessions/{token}", json={"image": png})).status_code == 200
            assert (await c.post(f"/api/signature-sessions/{token}", json={"image": png})).status_code == 409
            got = (await c.get(f"/api/signature-sessions/{token}")).json()
            assert got == {"status": "signed", "image": png}
            # Rendue une fois, puis effacée.
            assert (await c.get(f"/api/signature-sessions/{token}")).status_code == 404

    asyncio.run(go())
