"""La bonne alternance : seules les offres où Alice transmet elle-même entrent."""

import asyncio
import base64
from types import SimpleNamespace

import pytest

from app.agents.application import dispatcher
from app.agents.application.feasibility import apply_mode
from app.agents.discovery import labonnealternance as lba
from app.config import settings
from app.models.job_posting import ApplyChannel

OFFER = {
    "identifier": {"id": "6687165396d52b5e01b40954", "partner_job_id": "x", "partner_label": "La bonne alternance"},
    "apply": {"recipient_id": "recruiters_6687165396d52b5e01b40954", "url": "https://lba/offre/1", "phone": None},
    "contract": {"duration": 24, "remote": "hybrid", "type": ["Apprentissage"]},
    "offer": {
        "title": "Développeur web en alternance",
        "description": "Rejoins l'équipe produit.",
        "desired_skills": ["JavaScript", "SQL"],
        "to_be_acquired_skills": ["React"],
        "target_diploma": {"european": "6", "label": "Licence"},
        "rome_codes": ["M1805"],
        "publication": {"creation": "2026-09-01T00:00:00.000Z"},
    },
    "workplace": {"name": "ACME SAS", "brand": "Acme", "siret": "13002526500013",
                  "location": {"address": "1 rue de Paris 69001 Lyon"}},
}


def test_une_offre_candidatable_est_convertie():
    job = lba.to_scraped_job(OFFER)
    assert job.external_id == "lba:6687165396d52b5e01b40954"
    assert job.extra["company_name"] == "Acme"
    assert job.extra["contact"]["lba_recipient_id"] == "recruiters_6687165396d52b5e01b40954"
    assert job.extra["parsed"]["contract_type"] == "alternance"
    assert job.extra["parsed"]["remote_policy"] == "hybrid"
    assert "Durée du contrat : 24 mois" in job.description_raw
    assert job.location.endswith("Lyon")


def test_une_offre_sans_destinataire_est_ignoree():
    offer = {**OFFER, "apply": {"recipient_id": None, "url": "https://partenaire"}}
    assert lba.to_scraped_job(offer) is None


def test_corps_de_candidature():
    body = lba.build_application(
        recipient_id="recruiters_1", full_name="Camille Anne Martin", email="c@ex.fr",
        phone="0601020304", resume=b"%PDF-1.7", resume_name="CV_Camille", message="Bonjour",
    )
    assert body["applicant_first_name"] == "Camille"
    assert body["applicant_last_name"] == "Anne Martin"
    assert body["applicant_attachment_name"] == "CV_Camille.pdf"
    prefix = "data:application/pdf;base64,"
    assert base64.b64decode(body["applicant_attachment_content"][len(prefix):]) == b"%PDF-1.7"


def test_cv_trop_lourd_refuse():
    with pytest.raises(ValueError):
        lba.build_application(
            recipient_id="r", full_name="A B", email="a@b.fr", phone="06",
            resume=b"x" * 3_300_000, resume_name="CV.pdf", message="",
        )


def test_alice_postule_seulement_si_la_cle_est_configuree(monkeypatch):
    job = SimpleNamespace(apply_channel=ApplyChannel.LBA_API, contact_json={})
    monkeypatch.setattr(settings, "lba_api_key", "")
    assert apply_mode(job) == "manual"
    monkeypatch.setattr(settings, "lba_api_key", "k")
    assert apply_mode(job) == "auto"


def _dispatch(**kw):
    base = dict(destination="lba:recruiters_1", resume_blob=b"%PDF", resume_name="CV.pdf",
                letter_body="Madame, Monsieur")
    return SimpleNamespace(**{**base, **kw})


def test_envoi_lba_transmet_cv_et_lettre(monkeypatch):
    seen = {}

    async def fake_send(body):
        seen.update(body)
        return "lba-123"

    monkeypatch.setattr(lba, "send_application", fake_send)
    candidate = SimpleNamespace(full_name="Camille Martin", email="c@ex.fr", phone="0601020304")
    result = asyncio.run(dispatcher._send_via_lba(_dispatch(), candidate))
    assert result["ok"] and result["real"]
    assert result["proof"]["lba_application_id"] == "lba-123"
    assert seen["recipient_id"] == "recruiters_1"
    assert seen["applicant_message"] == "Madame, Monsieur"


def test_envoi_lba_sans_telephone_ne_part_pas():
    candidate = SimpleNamespace(full_name="Camille Martin", email="c@ex.fr", phone=None)
    result = asyncio.run(dispatcher._send_via_lba(_dispatch(), candidate))
    assert not result["ok"] and "téléphone" in result["error"]


def test_permission_manquante_dite_clairement(monkeypatch):
    async def refused(body):
        raise lba.LbaError(403, "forbidden")

    monkeypatch.setattr(lba, "send_application", refused)
    candidate = SimpleNamespace(full_name="Camille Martin", email="c@ex.fr", phone="06")
    result = asyncio.run(dispatcher._send_via_lba(_dispatch(), candidate))
    assert not result["ok"] and "permission" in result["error"]
