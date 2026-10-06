import asyncio
import json

import httpx

from app.agents.notifications import mailer
from app.agents.notifications.mailer import Attachment, Mail, send_mail


def test_scaleway_is_used_first_with_reply_to_and_attachment(monkeypatch):
    monkeypatch.setattr(mailer.settings, "scaleway_tem_secret_key", "scw-secret")
    monkeypatch.setattr(mailer.settings, "scaleway_project_id", "proj-1")
    monkeypatch.setattr(mailer.settings, "resend_api_key", "re_x")
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["token"] = request.headers.get("x-auth-token")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"emails": [{"id": "em-42"}]})

    real = httpx.AsyncClient
    monkeypatch.setattr(mailer.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))

    result = asyncio.run(send_mail(Mail(
        to="rh@acme.fr", subject="Candidature", text="Bonjour",
        sender=("Camille Martin via Alice", "candidatures@alice-agent.fr"),
        reply_to="camille.martin.k7f2q@reponses.alice-agent.fr",
        attachments=[Attachment("CV.pdf", b"%PDF")],
    )))

    assert result == {"ok": True, "real": True, "provider": "scaleway", "id": "em-42"}
    assert seen["url"].endswith("/transactional-email/v1alpha1/regions/fr-par/emails")
    assert seen["token"] == "scw-secret"
    body = seen["body"]
    assert body["from"] == {"email": "candidatures@alice-agent.fr", "name": "Camille Martin via Alice"}
    assert body["to"] == [{"email": "rh@acme.fr"}] and body["project_id"] == "proj-1"
    assert body["additional_headers"] == [{"key": "Reply-To", "value": "camille.martin.k7f2q@reponses.alice-agent.fr"}]
    assert body["attachments"][0] == {"name": "CV.pdf", "type": "application/pdf", "content": "JVBERg=="}


def test_scaleway_error_is_reported_not_hidden(monkeypatch):
    monkeypatch.setattr(mailer.settings, "scaleway_tem_secret_key", "scw-secret")
    monkeypatch.setattr(mailer.settings, "scaleway_project_id", "proj-1")
    real = httpx.AsyncClient
    monkeypatch.setattr(mailer.httpx, "AsyncClient", lambda **kw: real(
        transport=httpx.MockTransport(lambda r: httpx.Response(403, text="domain not verified")), **kw))
    result = asyncio.run(send_mail(Mail(to="rh@acme.fr", subject="s", text="t")))
    assert not result["ok"] and "403" in result["error"]
