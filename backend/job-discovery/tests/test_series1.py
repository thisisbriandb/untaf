from app.agents.discovery.cover_letter import _fallback_body
from app.agents.discovery.deduplicator import compute_fingerprint
from app.agents.experience_key import adapted_for, experience_key


def test_anonymous_offers_do_not_merge():
    a = compute_fingerprint("employeur-non-precise.francetravail.local", "Comptable H/F", "Lyon", external_id="A1")
    b = compute_fingerprint("employeur-non-precise.francetravail.local", "Comptable H/F", "Lyon", external_id="B2")
    assert a != b


def test_adapted_bullets_follow_their_experience_not_their_position():
    acme = {"company": "Acme", "jobTitle": "Dev", "startDate": "2021-01"}
    beta = {"company": "Beta", "jobTitle": "Lead", "startDate": "2023-01"}
    adapted = [{"key": experience_key(acme), "highlights": ["API Acme"]}]
    # Le candidat ajoute une expérience en tête après la préparation du dossier.
    matched = adapted_for([beta, acme], adapted)
    assert matched[0] == {} and matched[1]["highlights"] == ["API Acme"]


def test_legacy_positional_bullets_dropped_when_the_cv_changed_size():
    assert adapted_for([{"company": "X"}, {"company": "Y"}], [{"highlights": ["a"]}]) == [{}, {}]


def test_fallback_letter_never_claims_a_job_that_ended():
    past = [{"jobTitle": "Comptable", "company": "Fidal", "isCurrent": False, "highlights": []}]
    _, body, _ = _fallback_body("", [], "Comptable", "", past)
    assert "Actuellement" not in body and "Fidal" in body
    current = [{**past[0], "isCurrent": True}]
    _, body, _ = _fallback_body("", [], "Comptable", "", current)
    assert "Actuellement" in body
