from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.api.community import (
    CommunityList, _season, clean_city, offer_kind, render_markdown, to_offer,
)
from app.models.job_posting import ApplyChannel, ContractType, RemotePolicy

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


def job(**kw):
    base = dict(
        id=uuid4(), title="Alternance Chargé(e) marketing digital", external_id="123",
        contract_type=ContractType.UNKNOWN, location="69 - LYON 03", tech_stack=[],
        remote_policy=RemotePolicy.ONSITE, first_seen_at=NOW - timedelta(days=1),
        source_url="https://candidat.francetravail.fr/offres/recherche/detail/123",
        apply_url=None, apply_channel=ApplyChannel.EXTERNAL_LINK, contact_json=None, description_raw="", description_parsed=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_clean_city():
    assert clean_city("75 - PARIS 08") == "Paris"
    assert clean_city("69 - Lyon 3e Arrondissement") == "Lyon"
    assert clean_city("13 - AIX-EN-PROVENCE") == "Aix-en-Provence"
    assert clean_city("33 - SAINT-ANDRE-DE-CUBZAC") == "Saint-Andre-de-Cubzac"
    assert clean_city("Bordeaux, France") == "Bordeaux"
    assert clean_city(None) == "France"


def test_kind_from_title_beats_contract_field():
    assert offer_kind(job(title="Stage - Développeur web", contract_type=ContractType.CDI)) == "stage"
    assert offer_kind(job(title="Comptable", contract_type=ContractType.ALTERNANCE)) == "alternance"
    assert offer_kind(job(title="Comptable", contract_type=ContractType.CDI)) is None


def test_anonymous_employer_is_not_listed():
    assert to_offer(job(), "Employeur non précisé", NOW) is None
    o = to_offer(job(), "DECATHLON FRANCE", NOW)
    assert o.company == "Decathlon France" and o.city == "Lyon" and o.kind == "alternance"
    assert o.is_new and o.source == "France Travail" and not o.alice_sends
    assert o.family == "Marketing & communication"


def test_email_offer_is_sent_by_alice(monkeypatch):
    from app.agents.application import feasibility
    monkeypatch.setattr(type(feasibility.settings), "can_send_email", property(lambda s: True))
    o = to_offer(job(apply_channel=ApplyChannel.EMAIL, contact_json={"email": "rh@acme-lyon.fr"}), "Acme", NOW)
    assert o.alice_sends


def test_markdown_table_and_links():
    o = to_offer(job(title="Alternance | Commercial B2B"), "Acme", NOW)
    md = render_markdown(CommunityList(updated_at=NOW.isoformat(), total=1, new_count=1, offers=[o]), "alternance")
    assert md.startswith("# Alternances 2027 · Alice Community")
    assert "Alternance ∣ Commercial B2B" in md  # le « | » ne casse pas le tableau
    assert f"/communaute?offre={o.id}&utm_source=github" in md
    assert "[Annonce](https://candidat.francetravail.fr/" in md


def test_season():
    assert _season(datetime(2026, 10, 1)) == "2027"
    assert _season(datetime(2027, 3, 1)) == "2027"


def test_first_job_kind():
    from app.api.community import offer_kind
    cdi = dict(contract_type=ContractType.CDI)
    # France Travail : « débutant accepté » = 0 an exigé.
    assert offer_kind(job(title="Assistant commercial", description_parsed={"experience_years_required": 0.0}, **cdi)) == "emploi"
    assert offer_kind(job(title="Assistant commercial", description_parsed={"experience_years_required": 5.0}, **cdi)) is None
    # Sans donnée d'expérience, l'annonce doit le dire.
    assert offer_kind(job(title="Développeur web junior", **cdi)) == "emploi"
    assert offer_kind(job(title="Chargé de clientèle", description_raw="Poste ouvert aux jeunes diplômés.", **cdi)) == "emploi"
    assert offer_kind(job(title="Chargé de clientèle", **cdi)) is None
    # Un intitulé senior l'emporte sur tout.
    assert offer_kind(job(title="Comptable confirmé", description_parsed={"experience_years_required": 0.0}, **cdi)) is None
    assert offer_kind(job(title="Développeur junior", contract_type=ContractType.FREELANCE)) is None


def test_search_filters_paginates_and_counts_families():
    from app.api.community import search
    offers = [
        to_offer(job(title=f"Alternance commercial {i}", location="69 - LYON 03"), "Acme", NOW) for i in range(5)
    ] + [
        to_offer(job(title="Alternance développeur web", location="75 - PARIS 08"), "Beta", NOW),
        to_offer(job(title="Développeur junior", contract_type=ContractType.CDI, location="Paris"), "Gamma", NOW),
    ]
    data = CommunityList(updated_at=NOW.isoformat(), total=len(offers), new_count=0, offers=offers)
    p = search(data, "alternance", per_page=2, page=2)
    assert p.total == 6 and p.matched == 6 and len(p.offers) == 2 and p.page == 2
    assert {f.name: f.count for f in p.families} == {"Commerce & vente": 5, "Tech & développement": 1}
    p = search(data, "alternance", city="paris")
    assert [o.company for o in p.offers] == ["Beta"]
    p = search(data, "alternance", q="DEVELOPPEUR")  # sans accents ni casse
    assert p.matched == 1
    p = search(data, "alternance", family="Commerce & vente")
    assert p.matched == 5 and len(p.families) == 2  # les métiers ignorent leur propre filtre
    assert search(data, "emploi").total == 1
