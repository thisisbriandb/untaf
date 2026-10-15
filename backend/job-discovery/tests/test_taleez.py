import asyncio
import json

import httpx
import pytest

from app.agents.discovery import taleez
from app.agents.discovery.taleez import (
    TaleezError,
    apply_payload,
    contract_of,
    parse_offer,
    parse_sitemap,
    read_form,
    send_application,
)
from app.agents.inbox import Incoming, confirmation_link
from app.models.job_posting import ContractType


def question(qid, kind, label, required=False, displayed=True, choices=()):
    return {"id": qid, "displayed": displayed, "order": qid, "value": label, "required": required,
            "type": kind, "choices": [{"id": c, "value": str(c)} for c in choices]}


def page(questions, status="PUBLISHED", visibility="PUBLIC", contract="CDI",
         title="Chauffeur PL GRUE auxiliaire Magasinier - H/F", country="FR"):
    ld = {
        "@type": "JobPosting", "title": title, "datePosted": "2026-09-28T16:25:33+0200",
        "description": "<p>Nous recherchons un(e)&nbsp;<strong>Chauffeur</strong>.</p><ul><li>Permis C</li></ul>",
        "qualifications": "<p>Polyvalent(e).</p>",
        "hiringOrganization": {"@type": "Organization", "name": "Chausson Matériaux"},
        "jobLocation": {"@type": "Place", "address": {"addressLocality": "Saint-Omer", "postalCode": "62500",
                                                             "addressCountry": country}},
    }
    state = {"DATA_QUESTIONS": {
        "jobStatus": status, "visibility": visibility, "redirect": False, "pendingValidation": False,
        "contract": contract, "token": "magasinier-chauffeur-saint-omer-cdi", "questions": questions,
    }}
    return (f'<html><script id="jobPostingSnippet" type="application/ld+json">{json.dumps(ld)}</script>'
            f'<script id="ng-state" type="application/json">{json.dumps(state)}</script></html>')


SIMPLE = [
    question(1, "DOC", "CV", required=True),
    question(2, "DOC", "Lettre de motivation"),
    question(3, "TEXTAREA", "Commentaire sur votre candidature", required=True),
    question(4, "INPUT", "Rémunération actuelle brute (fixe + avantages)"),
]


def test_parse_offer_reads_json_ld_and_form():
    o = parse_offer("fmudc", "https://taleez.com/apply/x", page(SIMPLE))
    assert o.title.startswith("Chauffeur PL") and o.company == "Chausson Matériaux"
    assert o.location == "62500 Saint-Omer" and o.contract == ContractType.CDI
    assert "Chauffeur" in o.description and "<" not in o.description and "• Permis C" in o.description
    assert o.posted.year == 2026
    f = o.form
    assert f.sendable and (f.cv, f.letter_doc, f.message, f.message_required) == (1, 2, 3, True)
    assert f.token == "magasinier-chauffeur-saint-omer-cdi"


def test_personal_required_questions_block_sending():
    f = read_form({"token": "t", "questions": SIMPLE + [
        question(5, "SELECT", "Salaire souhaité (brut par an)", required=True, choices=(10, 11)),
        question(6, "RADIO", "Disponibilité", required=True, choices=(20, 21)),
        question(7, "DATE", "Date cachée", required=True, displayed=False),
    ]})
    assert not f.sendable and f.blocking == ["Salaire souhaité (brut par an)", "Disponibilité"]


def test_offer_without_cv_question_is_not_sendable():
    f = read_form({"token": "t", "questions": [question(3, "TEXTAREA", "Commentaire")]})
    assert not f.sendable and f.blocking == ["CV"]


def test_required_letter_file_is_left_to_the_candidate():
    f = read_form({"token": "t", "questions": [question(1, "DOC", "CV", True),
                                               question(2, "DOC", "Lettre de motivation", True)]})
    assert f.blocking == ["Lettre de motivation"]


def test_unpublished_or_internal_offers_are_skipped():
    assert parse_offer("a", "u", page(SIMPLE, status="CLOSED")) is None
    assert parse_offer("a", "u", page(SIMPLE, visibility="INTERNAL")) is None
    assert parse_offer("a", "u", page(SIMPLE, visibility="INTERNAL_AND_PUBLIC")) is not None
    assert parse_offer("a", "u", "<html>plus en ligne</html>") is None
    assert parse_offer("a", "u", page(SIMPLE, title="Candidature spontanée - H/F")) is None
    assert parse_offer("a", "u", page(SIMPLE, country="LU")) is None


def test_contract_codes():
    assert contract_of("APPRENTICESHIP", "Vendeur") == ContractType.ALTERNANCE
    assert contract_of("CDD", "Assistant RH en alternance") == ContractType.ALTERNANCE
    assert contract_of("STUDENT", "Job étudiant") == ContractType.STAGE
    assert contract_of("FREELANCE", "Développeur") == ContractType.FREELANCE
    assert contract_of("VOLUNTEER", "Bénévole") == ContractType.UNKNOWN


def test_sitemap_codes():
    xml = """<urlset><url>\n<loc>https://taleez.com/apply/fmudc</loc>\n</url>
    <url><loc>https://taleez.com/w/blog/article</loc></url>
    <url><loc>https://taleez.com/apply/36it1t</loc></url></urlset>"""
    assert parse_sitemap(xml) == {"fmudc": "https://taleez.com/apply/fmudc",
                                  "36it1t": "https://taleez.com/apply/36it1t"}


def test_apply_payload_matches_the_form():
    """Même corps que celui relevé sur le vrai formulaire (requête coupée, 14/10/2026)."""
    body = apply_payload(token="tok", cv_question=4102201, cv_file="abc.pdf", cv_name="CV.pdf",
                         message_question=4102203, message="Bonjour",
                         first_name="Camille", last_name="Test", email="c@x.fr", phone="+33612345678")
    assert body == {
        "lang": "fr", "utmSource": "unknown", "cvthequeGpt": False, "rgpdCvtheque": False,
        "firstName": "Camille", "lastName": "Test", "mail": "c@x.fr", "phone": "+33612345678",
        "answers": [{"questionId": 4102201, "doc": {"file": "abc.pdf", "fileName": "CV.pdf", "name": "CV.pdf"}},
                    {"questionId": 4102203, "value": "Bonjour"}],
        "token": "tok",
    }


def test_phone_formats():
    assert taleez._phone("06 12 34 56 78") == "+33612345678"
    assert taleez._phone("0033 6 12 34 56 78") == "+33612345678"
    assert taleez._phone("+32 470 12 34 56") == "+32470123456"


TARGET = {"token": "tok", "cv": 1, "message": 3, "message_required": True}


def run_send(handler, **kw):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await send_application(
                target=kw.get("target", TARGET), full_name="Camille de la Test", email="camille@alice.fr",
                phone="06 12 34 56 78", resume=b"%PDF", resume_name="CV.pdf",
                message=kw.get("message", "Ma lettre"), client=client,
            )
    return asyncio.run(go())


def test_send_uploads_cv_then_applies():
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path.endswith("upload-file-doc"):
            assert b'name="file"; filename="CV.pdf"' in request.content
            return httpx.Response(200, json={"fileName": "stored-123.pdf"})
        return httpx.Response(200, json={})

    run_send(handler)
    assert [r.url.path for r in seen] == ["/api/public/upload-file-doc", "/api/public/apply"]
    body = json.loads(seen[1].content)
    assert (body["firstName"], body["lastName"], body["phone"]) == ("Camille", "de la Test", "+33612345678")
    assert body["answers"][0]["doc"]["file"] == "stored-123.pdf"
    assert body["answers"][1] == {"questionId": 3, "value": "Ma lettre"}
    assert body["rgpdCvtheque"] is False and body["cvthequeGpt"] is False


def test_send_reports_taleez_error_code():
    def handler(request):
        if request.url.path.endswith("upload-file-doc"):
            return httpx.Response(200, json={"fileName": "f.pdf"})
        return httpx.Response(400, json={"error": "ALREADY_APPLIED"})

    with pytest.raises(TaleezError) as e:
        run_send(handler)
    assert e.value.code == "ALREADY_APPLIED"


def test_required_message_without_letter_sends_nothing():
    def handler(request):
        raise AssertionError("aucune requête ne doit partir")

    with pytest.raises(TaleezError) as e:
        run_send(handler, message="")
    assert e.value.code == "MESSAGE_REQUIRED"


def incoming(sender, html=None, text=""):
    return Incoming(provider_id="p", from_raw=sender, to=["tok@reply.alice-agent.fr"],
                    subject="Confirmez votre candidature", text=text, html=html)


def test_confirmation_link_from_taleez():
    link = "https://taleez.com/apply/confirm/AbC-123_x"
    assert confirmation_link(incoming("Taleez <noreply@taleez.com>", html=f'<a href="{link}">Confirmer</a>')) == link
    tracked = "https://u123.ct.sendgrid.net/ls/click?upn=abc&amp;x=1"
    assert confirmation_link(incoming("noreply@taleez.com", html=f'<a href="{tracked}"><span>Je confirme ma '
                                                                  'candidature</span></a><a href="https://taleez.com">'
                                                                  'Taleez</a>')) == tracked.replace("&amp;", "&")
    # Un autre expéditeur ne fait jamais apparaître de bouton.
    assert confirmation_link(incoming("rh@exemple.fr", html=f'<a href="{link}">Confirmer</a>')) is None


def test_taleez_is_never_republished():
    from app.api.community import NOT_REPUBLISHED
    assert taleez.PREFIX in NOT_REPUBLISHED


class _Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _dispatcher_with(monkeypatch, contact, sender):
    from app.agents.application import dispatcher

    job = _Row(contact_json=contact)
    application = _Row(job_posting_id="job")

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, model, key):
            return application if key == "app" else job

    monkeypatch.setattr(dispatcher, "async_session", Session)
    monkeypatch.setattr(taleez, "send_application", sender)
    return dispatcher


def _dispatch(**kw):
    base = dict(destination="taleez:tok", resume_blob=b"%PDF", resume_name="CV.pdf",
                letter_body="Ma lettre", application_id="app")
    return _Row(**{**base, **kw})


def _candidate(**kw):
    return _Row(**{"full_name": "Camille Test", "phone": "0612345678", "email": "c@x.fr",
                   "reply_token": None, **kw})


def test_dispatcher_sends_with_stored_questions(monkeypatch):
    sent = {}

    async def sender(**kw):
        sent.update(kw)
        return {}

    d = _dispatcher_with(monkeypatch, {"taleez": TARGET}, sender)
    out = asyncio.run(d._send_via_taleez(_dispatch(), _candidate()))
    assert out["ok"] and out["real"] and out["proof"]["via"] == "Taleez"
    assert sent["target"] == TARGET and sent["message"] == "Ma lettre" and sent["resume"] == b"%PDF"


def test_dispatcher_explains_refusals(monkeypatch):
    async def sender(**kw):
        raise TaleezError(400, "ALREADY_APPLIED")

    d = _dispatcher_with(monkeypatch, {"taleez": TARGET}, sender)
    out = asyncio.run(d._send_via_taleez(_dispatch(), _candidate()))
    assert not out["ok"] and "déjà postulé" in out["error"]

    async def never(**kw):
        raise AssertionError("rien ne doit partir")

    d = _dispatcher_with(monkeypatch, {"taleez": TARGET}, never)
    assert "téléphone" in asyncio.run(d._send_via_taleez(_dispatch(), _candidate(phone=None)))["error"]
    # Offre dont le jeton a changé depuis la préparation : on n'envoie pas à l'aveugle.
    d = _dispatcher_with(monkeypatch, {"taleez": {**TARGET, "token": "autre"}}, never)
    assert "introuvable" in asyncio.run(d._send_via_taleez(_dispatch(), _candidate()))["error"]


def test_pasted_links():
    assert taleez.pasted_code("https://taleez.com/apply/fmudc") == "fmudc"
    assert taleez.pasted_code(" https://taleez.com/apply/vendeur-h-f-lyon-cdi/?utm_source=x ") == "vendeur-h-f-lyon-cdi"
    assert taleez.pasted_code("https://taleez.com/apply/confirm/abc") is None
    assert taleez.pasted_code("https://taleez.com/apply/thanks") is None
    assert taleez.pasted_code("https://evil.example/taleez.com/apply/x") is None
    assert taleez.pasted_code(None) is None


def test_confirm_follows_link_then_calls_the_page_api():
    calls = []

    def handler(request):
        calls.append((request.method, str(request.url)))
        if request.url.host == "u1.ct.sendgrid.net":
            return httpx.Response(302, headers={"location": "https://taleez.com/apply/confirm/AbC-123"})
        if request.method == "GET":
            return httpx.Response(200, text="<html></html>")
        assert json.loads(request.content) == {"token": "AbC-123"}
        return httpx.Response(200, json={})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as c:
            return await taleez.confirm("https://u1.ct.sendgrid.net/ls/click?upn=x", client=c)

    assert asyncio.run(go()) is True
    assert calls[-1] == ("POST", "https://taleez.com/api/public/confirm-apply")


def test_confirm_refuses_unexpected_destinations():
    def handler(request):
        return httpx.Response(200, text="ailleurs")

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as c:
            return await taleez.confirm("https://evil.example/x", client=c)

    assert asyncio.run(go()) is False


def test_confirm_never_fetches_internal_addresses():
    for bad in ("http://taleez.com/apply/confirm/x", "https://127.0.0.1/x", "https://localhost/x",
                "https://api.railway.internal/x", "https://[::1]/x"):
        assert taleez._public_https(bad) is False, bad
    assert taleez._public_https("https://u1.ct.sendgrid.net/ls/click?upn=x")
