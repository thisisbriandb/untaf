import asyncio

from app.api.apply import _detached


def test_run_continues_when_the_page_closes():
    done = []

    async def steps():
        yield "préparation"
        await asyncio.sleep(0.05)
        done.append("envoi")  # le travail après le départ du navigateur
        yield "envoyée"

    async def go():
        relay = _detached(steps())
        assert await relay.__anext__() == "préparation"
        await relay.aclose()  # l'onglet se ferme
        await asyncio.sleep(0.2)

    asyncio.run(go())
    assert done == ["envoi"]


def test_relays_every_step_in_order():
    async def steps():
        for s in ("a", "b", "c"):
            yield s

    async def go():
        return [s async for s in _detached(steps())]

    assert asyncio.run(go()) == ["a", "b", "c"]
