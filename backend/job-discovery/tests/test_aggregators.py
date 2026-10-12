import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx

from app.agents.discovery import aggregators
from app.agents.discovery.aggregators import listing_kind, parse_adzuna, parse_jooble
from app.api.community import dedup_key, listing_to_offer, render_markdown, CommunityList

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


def adzuna_result(i, title, desc="", company="ACME FRANCE"):
    return {
        "id": str(i), "title": f"<strong>{title}</strong>", "description": desc,
        "company": {"display_name": company},
        "location": {"display_name": "Lyon, Rhône"},
        "redirect_url": f"https://www.adzuna.fr/land/ad/{i}",
        "created": "2026-10-11T08:00:00Z",
    }


def test_listing_kind():
    assert listing_kind("Alternance - Assistant RH", "", "stage") == "alternance"
    assert listing_kind("Assistant RH", "Contrat en apprentissage de 24 mois", "alternance") == "alternance"
    # Un CDI qui cite un stage dans son texte n'est pas un stage.
    assert listing_kind("Comptable", "après un premier stage réussi", "alternance") is None
    assert listing_kind("Développeur freelance", "stage", "stage") is None
    assert listing_kind("Comptable confirmé H/F", "Contrat d'apprentissage", "alternance") is None
    assert listing_kind("Orthophoniste", "Nous accueillons des stagiaires.", "stage") is None
    assert listing_kind("Assistant RH", "Stage de 6 mois à partir de janvier", "stage") == "stage"


def test_parse_adzuna_keeps_only_matching_contracts_and_strips_html():
    out = parse_adzuna({"results": [
        adzuna_result(1, "Stage Marketing digital"),
        adzuna_result(2, "Comptable confirmé", "10 ans d'expérience"),
        adzuna_result(3, "Commercial", "Poste en alternance, rythme 3 semaines / 1 semaine"),  # alternance, pas stage
        {**adzuna_result(4, "Stage sans lien"), "redirect_url": ""},
    ]}, "stage")
    assert [(l.external_id, l.kind) for l in out] == [("1", "stage")]
    assert out[0].title == "Stage Marketing digital" and out[0].source == "adzuna"
    out = parse_adzuna({"results": [adzuna_result(3, "Commercial", "Poste en alternance")]}, "alternance")
    assert out[0].kind == "alternance" and out[0].published_at.year == 2026


def test_parse_jooble():
    out = parse_jooble({"jobs": [{
        "id": 99, "title": "Alternant(e) data analyst", "company": "Beta", "location": "Paris",
        "snippet": "…", "link": "https://fr.jooble.org/desc/99", "updated": "2026-10-10T00:00:00",
    }]}, "alternance")
    assert out[0].source == "jooble" and out[0].kind == "alternance"


def listing(**kw):
    base = dict(
        id=uuid4(), source="adzuna", title="Stage Marketing digital H/F", company="ACME FRANCE",
        location="Lyon, Rhône", kind="stage", url="https://www.adzuna.fr/land/ad/1",
        published_at=NOW - timedelta(hours=5), first_seen_at=NOW, snippet="",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_listing_offer_carries_attribution():
    o = listing_to_offer(listing(), NOW)
    assert o.id.startswith("x:") and o.company == "Acme France" and o.city == "Lyon"
    assert o.attribution_label == "Adzuna" and o.attribution_url == "https://www.adzuna.fr"
    assert o.is_new and not o.alice_sends
    md = render_markdown(CommunityList(updated_at=NOW.isoformat(), total=1, new_count=1, offers=[o]), "stage")
    assert "via [Adzuna](https://www.adzuna.fr)" in md


def test_dedup_ignores_gender_marks_and_accents():
    a = listing_to_offer(listing(title="Stage Chargé(e) de marketing H/F"), NOW)
    b = listing_to_offer(listing(title="Stage Chargé de marketing", company="Acme France"), NOW)
    assert dedup_key(a) == dedup_key(b)


def test_fetch_adzuna_paginates_and_stops_on_rate_limit(monkeypatch):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        if len(calls) == 3:
            return httpx.Response(429)
        page = [adzuna_result(f"{len(calls)}-{i}", f"Stage {i}") for i in range(50)]
        return httpx.Response(200, json={"results": page})

    monkeypatch.setattr(aggregators, "ADZUNA_PAUSE_S", 0)
    monkeypatch.setattr(aggregators.settings, "adzuna_pages_per_query", 5)
    monkeypatch.setattr(aggregators.settings, "adzuna_app_id", "id")
    monkeypatch.setattr(aggregators.settings, "adzuna_app_key", "secret")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await aggregators.fetch_adzuna(client)

    found = asyncio.run(run())
    assert calls[:2] == ["/v1/api/jobs/fr/search/1", "/v1/api/jobs/fr/search/2"]
    # Intitulés « Stage » trouvés par la recherche « alternance » : gardés, comme stages.
    assert len(found) == 100 and {l.kind for l in found} == {"stage"}
    assert len(calls) == 3


def test_errors_never_carry_the_key(monkeypatch):
    monkeypatch.setattr(aggregators, "ADZUNA_PAUSE_S", 0)
    monkeypatch.setattr(aggregators.settings, "adzuna_app_key", "TOPSECRET")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))) as client:
            await aggregators.fetch_adzuna(client)

    try:
        asyncio.run(run())
    except RuntimeError as e:
        assert "TOPSECRET" not in str(e) and "500" in str(e)
    else:
        raise AssertionError("une erreur était attendue")


def test_regulated_statuses_out_cfa_offers_flagged():
    assert listing_kind("Expert-comptable stagiaire en cabinet - H/F", "", "stage") is None
    cfa = listing_to_offer(listing(
        company="FORMAZOT", title="Magasinier en alternance", kind="alternance",
        snippet="centre de formation de proximité, recrute pour l'une de ses entreprises partenaires",
    ), NOW)
    direct = listing_to_offer(listing(company="Leroy Merlin", title="Vendeur en alternance", kind="alternance"), NOW)
    assert cfa.via_school and not direct.via_school
    assert listing_to_offer(listing(company="RUNAPP", title="Employé polyvalent en alternance H/F RUN12862", kind="alternance"), NOW).via_school
    md = render_markdown(CommunityList(updated_at=NOW.isoformat(), total=1, new_count=1, offers=[cfa]), "stage")
    assert "_via un CFA_" in md


def test_same_offer_in_many_cities_is_one_line(monkeypatch):
    from app.api import community

    rows = [listing(location=city) for city in ("Reims", "Troyes", "Soissons")]

    class FakeSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def execute(self, stmt):
            entity = stmt.column_descriptions[0]["entity"].__name__
            data = rows if entity == "ExternalListing" else []
            return SimpleNamespace(all=lambda: data, scalars=lambda: SimpleNamespace(all=lambda: data))

    monkeypatch.setattr(community, "async_session", FakeSession)
    d = asyncio.run(community.load_offers(NOW))
    assert d.total == 1 and d.offers[0].other_cities == 2
    md = render_markdown(d, "stage")
    assert "(+2 villes)" in md
