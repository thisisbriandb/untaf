"""Notifications, relances et étapes du pipeline — parties pures, sans base."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.agents.application.followup import followup_state, record_status
from app.agents.application.outcome import build_outcome
from app.agents.notifications import DEFAULT_PREFS, _allowed, resolve_prefs
from app.agents.notifications.mailer import deliver
from app.agents.notifications.templates import Email, Item, render_html, render_text
from app.api.pipeline import _stage
from app.config import settings
from app.models.application import Application, ApplicationStatus
from app.models.dispatch import ApplicationDispatch, DispatchChannel, DispatchStatus
from app.models.notification import NotificationKind


def _app(status=ApplicationStatus.MATCHED, applied_days=None, meta=None):
    applied = (
        datetime.now(timezone.utc) - timedelta(days=applied_days)
        if applied_days is not None else None
    )
    return Application(status=status, match_score=80, applied_at=applied, metadata_json=meta)


# ── Préférences ───────────────────────────────────────────────────────────


def test_preferences_par_defaut_et_valeurs_inconnues():
    prefs = resolve_prefs(SimpleNamespace(notification_prefs={"digest": "hourly", "x": 1}))
    assert prefs == DEFAULT_PREFS


def test_tout_couper_coupe_tout_sauf_l_essai():
    prefs = {**DEFAULT_PREFS, "enabled": False}
    assert not _allowed(prefs, NotificationKind.MISSION_REPORT)
    assert not _allowed(prefs, NotificationKind.DIGEST)
    assert _allowed(prefs, NotificationKind.TEST)


def test_rapport_periodique_desactivable():
    assert not _allowed({**DEFAULT_PREFS, "digest": "off"}, NotificationKind.DIGEST)
    assert not _allowed({**DEFAULT_PREFS, "followups": False}, NotificationKind.FOLLOWUP_DUE)


# ── Gabarit ───────────────────────────────────────────────────────────────


def test_gabarit_echappe_le_contenu_externe():
    email = Email(
        subject="s", preheader="p", heading="<script>x</script>",
        items=[Item("Dev <b>", "ACME & co", "à valider")],
        cta_label="Voir", cta_url="https://x.test/?a=1&b=2",
    )
    html = render_html(email)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "ACME &amp; co" in html
    text = render_text(email)
    assert "Dev <b>" in text and "https://x.test/?a=1&b=2" in text


def test_sans_transport_rien_ne_part_et_c_est_dit(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "smtp_host", "")
    result = asyncio.run(deliver("a@b.fr", "s", "<p>x</p>", "x"))
    assert result["ok"] and not result["real"]


# ── Relances ──────────────────────────────────────────────────────────────


def test_relance_due_apres_le_delai():
    assert followup_state(_app(ApplicationStatus.APPLIED, settings.followup_after_days))["due"]
    assert not followup_state(_app(ApplicationStatus.APPLIED, 1))["due"]


def test_relance_ecartee_ou_reponse_recue():
    days = settings.followup_after_days + 3
    dismissed = _app(ApplicationStatus.APPLIED, days, {"followup": {"status": "dismissed"}})
    assert not followup_state(dismissed)["due"]
    assert not followup_state(_app(ApplicationStatus.INTERVIEW, days))["due"]


def test_changement_de_statut_date_et_trace():
    app = _app()
    record_status(app, ApplicationStatus.APPLIED, "envoyée via email")
    assert app.status == ApplicationStatus.APPLIED and app.applied_at
    assert app.metadata_json["timeline"][-1]["status"] == "applied"


# ── Étapes du pipeline ────────────────────────────────────────────────────


def _dispatch(status, error=None):
    return ApplicationDispatch(
        status=status, channel=DispatchChannel.EMAIL, destination="rh@acme.fr",
        company_name="ACME", job_title="Dev", error=error,
    )


def test_etapes():
    pack = {"cover_letter": {"body": "x"}, "tailored_cv": {"headline": "y"}}
    assert _stage(_app(), None) == "to_prepare"
    assert _stage(_app(meta=pack), None) == "ready"
    assert _stage(_app(meta=pack), _dispatch(DispatchStatus.AWAITING_APPROVAL)) == "awaiting"
    assert _stage(_app(meta=pack), _dispatch(DispatchStatus.FAILED)) == "manual"
    assert _stage(_app(ApplicationStatus.INTERVIEW), _dispatch(DispatchStatus.SENT)) == "interview"


def test_repetition_donne_son_vrai_motif():
    d = _dispatch(DispatchStatus.SIMULATED, "l'envoi par navigateur est désactivé")
    d.id = "00000000-0000-0000-0000-000000000000"
    outcome = build_outcome(d)
    assert not outcome.sent
    assert "navigateur" in outcome.detail and "SMTP" not in outcome.detail


# ── Runs orphelins ────────────────────────────────────────────────────────


def test_echeance_depassee_sans_abandon_n_est_pas_orpheline():
    from app.agents.mission_runner import STALE_AFTER_SECONDS, is_orphaned
    from app.models.mission import MissionRun, RunStatus

    now = datetime.now(timezone.utc)
    finishing = MissionRun(
        status=RunStatus.RUNNING, ends_at=now - timedelta(minutes=2),
        heartbeat_at=now - timedelta(seconds=30),
    )
    assert not is_orphaned(finishing, now)

    dead = MissionRun(
        status=RunStatus.RUNNING, ends_at=now + timedelta(hours=1),
        heartbeat_at=now - timedelta(seconds=STALE_AFTER_SECONDS + 60),
    )
    assert is_orphaned(dead, now)
    assert not is_orphaned(MissionRun(status=RunStatus.COMPLETED), now)
