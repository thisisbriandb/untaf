"""Tous les e-mails passent par le même transport, Resend en tête."""

import asyncio
from types import SimpleNamespace

from app.agents.application import email_sender
from app.agents.notifications import mailer
from app.config import settings


def test_candidature_via_resend_avec_cv_et_reponse_au_candidat(monkeypatch):
    sent = {}

    async def fake_resend(mail):
        sent["mail"] = mail
        return {"ok": True, "real": True, "provider": "resend", "id": "abc"}

    monkeypatch.setattr(settings, "resend_api_key", "re_test")
    monkeypatch.setattr(mailer, "_via_resend", fake_resend)
    candidate = SimpleNamespace(full_name="Camille Martin", email="camille@ex.fr")

    result = asyncio.run(email_sender.send_application_email(
        to_email="rh@acme.fr", candidate=candidate,
        letter={"subject": "Candidature Dev", "body": "Bonjour"},
        job_title="Dev", company_name="ACME", resume=b"%PDF", resume_name="CV.pdf",
    ))

    mail = sent["mail"]
    assert result["real"] and result["proof"]["provider"] == "resend"
    assert mail.sender == ("Camille Martin via Alice", "candidatures@alice-agent.fr")
    assert mail.reply_to == "camille@ex.fr"
    assert mail.attachments[0].filename == "CV.pdf"


def test_sans_transport_candidature_simulee(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "smtp_host", "")
    result = asyncio.run(email_sender.send_application_email(
        to_email="rh@acme.fr", candidate=SimpleNamespace(full_name="X", email=None),
        letter=None, job_title="Dev", company_name="ACME", resume=b"%PDF",
    ))
    assert result["ok"] and not result["real"] and result["proof"]["simulated"]
