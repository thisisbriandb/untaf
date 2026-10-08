from types import SimpleNamespace

from app.agents.application import feasibility
from app.agents.application.dispatcher import browser_failure
from app.models.job_posting import ApplyChannel


def _job(channel):
    return SimpleNamespace(apply_channel=channel, contact_json={}, apply_url="https://igf.fr/postuler",
                           source_url="https://candidat.francetravail.fr/offres/1")


def test_employer_form_is_never_auto_sent():
    job = _job(ApplyChannel.WEB_FORM)
    assert feasibility.apply_mode(job) == "manual"
    assert not feasibility.assess(job).automatable


def test_unrecognized_page_is_not_an_outage():
    # Rien de reconnu (le cas « Comptable (H/F) — GROUPE IGF ») : dossier à finir sur le site.
    nothing = {"ok": False, "proof": {"filled_fields": [], "uploaded_files": [],
                                      "unhandled_fields": ["first_name", "email", "resume"]}}
    assert browser_failure(nothing) == ("prepared", None)
    partial = {"ok": False, "proof": {"filled_fields": ["email"], "uploaded_files": [],
                                      "unhandled_fields": ["resume"]}}
    assert browser_failure(partial) == ("failed", "form_incomplete")


def test_captcha_protected_ats_go_through_the_extension(monkeypatch):
    # Même avec l'envoi navigateur activé : reCAPTCHA / hCaptcha bloquent le serveur.
    monkeypatch.setattr(feasibility.settings, "browser_submit_enabled", True)
    for channel in (ApplyChannel.GREENHOUSE_API, ApplyChannel.LEVER_API):
        job = _job(channel)
        verdict = feasibility.assess(job)
        assert not verdict.automatable and "extension" in verdict.summary
        assert feasibility.apply_mode(job) == "manual"
