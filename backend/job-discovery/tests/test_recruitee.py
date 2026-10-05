"""Recruitee : Alice dépose elle-même, sauf questions obligatoires."""

import asyncio
from types import SimpleNamespace

import httpx

from app.agents.application import dispatcher
from app.agents.application.feasibility import apply_mode
from app.agents.discovery.board_registry import ATS_SOURCES
from app.agents.discovery.scrapers import recruitee
from app.agents.discovery.tasks import _channel_for
from app.models.job_posting import ApplyChannel

OFFER = {
    "id": 42, "slug": "developpeur-python", "title": "Développeur Python (CDI)",
    "status": "published", "location": "Paris, France", "department": "Tech",
    "description": "<p>Tu rejoins <b>l'équipe</b>.</p><ul><li>Python</li><li>SQL</li></ul>",
    "requirements": "<p>2 ans d'expérience</p>",
    "careers_url": "https://acme.recruitee.com/o/developpeur-python",
    "careers_apply_url": "https://acme.recruitee.com/o/developpeur-python/c/new",
    "employment_type_code": "fulltime_permanent", "options_cv": "required",
    "open_questions": [{"id": 1, "body": "Disponibilité ?", "required": False}],
}


def test_offre_convertie_et_html_nettoye():
    job = recruitee.to_scraped_job("acme", OFFER)
    assert job.external_id == "recruitee:acme:42"
    assert "<" not in job.description_raw and "• Python" in job.description_raw
    assert job.extra["recruitee"] == {"company": "acme", "offer": "developpeur-python"}


def test_canal_api_sans_question_obligatoire():
    channel, contact = _channel_for(recruitee.to_scraped_job("acme", OFFER), ApplyChannel.UNKNOWN)
    assert channel == ApplyChannel.RECRUITEE_API
    assert contact["recruitee"]["offer"] == "developpeur-python"


def test_question_obligatoire_bascule_sur_le_formulaire():
    offer = {**OFFER, "open_questions": [{"id": 2, "body": "Prétentions ?", "required": True}]}
    channel, contact = _channel_for(recruitee.to_scraped_job("acme", offer), ApplyChannel.UNKNOWN)
    assert channel == ApplyChannel.WEB_FORM
    assert contact["questions"] == ["Prétentions ?"]


def test_alice_postule_sur_recruitee():
    assert apply_mode(SimpleNamespace(apply_channel=ApplyChannel.RECRUITEE_API, contact_json={})) == "auto"


def test_registre_lit_les_sous_domaines():
    pattern = ATS_SOURCES["recruitee"].slug_pattern("recruitee.com")
    assert pattern.search("https://acme-sas.recruitee.com/o/dev").group(1) == "acme-sas"


def test_depot_multipart_avec_cv_et_lettre(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.read()
        return httpx.Response(201, json={"candidate": {"id": 777}})

    real = httpx.AsyncClient
    monkeypatch.setattr(recruitee.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))

    candidate = SimpleNamespace(full_name="Camille Martin", email="c@ex.fr", phone="0601020304")
    dispatch = SimpleNamespace(destination="recruitee:acme/developpeur-python",
                               resume_blob=b"%PDF-1.7", resume_name="CV_Camille.pdf",
                               letter_body="Madame, Monsieur")
    result = asyncio.run(dispatcher._send_via_recruitee(dispatch, candidate))

    assert result["ok"] and result["real"]
    assert result["proof"]["recruitee_candidate_id"] == 777
    assert seen["url"] == "https://acme.recruitee.com/api/offers/developpeur-python/candidates"
    body = seen["body"]
    assert b'name="candidate[cv]"; filename="CV_Camille.pdf"' in body
    assert b'name="candidate[cover_letter]"' in body and b"Madame, Monsieur" in body
    assert b"%PDF-1.7" in body


def test_refus_du_site_carriere(monkeypatch):
    async def refused(**kw):
        raise recruitee.RecruiteeError(422, "phone is required")

    monkeypatch.setattr(recruitee, "send_application", refused)
    candidate = SimpleNamespace(full_name="C M", email="c@ex.fr", phone="06")
    dispatch = SimpleNamespace(destination="recruitee:acme/x", resume_blob=b"%PDF",
                               resume_name="CV.pdf", letter_body="")
    result = asyncio.run(dispatcher._send_via_recruitee(dispatch, candidate))
    assert not result["ok"] and "téléphone" in result["error"]
    assert result["proof"]["status"] == 422
