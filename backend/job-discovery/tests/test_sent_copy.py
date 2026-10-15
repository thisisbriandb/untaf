import asyncio
from types import SimpleNamespace

from app.agents import notifications
from app.models.dispatch import DispatchStatus


def test_candidate_gets_a_copy_of_what_was_sent(monkeypatch):
    dispatch = SimpleNamespace(
        status=DispatchStatus.SENT, job_title="Accompagnant", company_name="Tango",
        channel=SimpleNamespace(value="ats_api"), destination="taleez:tok",
        resume_blob=b"%PDF-cv", resume_name="CV_Briand.pdf",
        letter_body="Madame, Monsieur,\n\nJe me permets de vous écrire.\n\nCordialement",
    )

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, model, key):
            return dispatch

    seen = {}

    async def fake_send(candidate_id, kind, key, email, payload=None, attachments=None):
        seen.update(email=email, attachments=attachments)

    monkeypatch.setattr(notifications, "async_session", Session)
    monkeypatch.setattr(notifications, "_send", fake_send)
    asyncio.run(notifications.notify_application_sent("c", "d"))

    [cv] = seen["attachments"]
    assert (cv.filename, cv.content) == ("CV_Briand.pdf", b"%PDF-cv")
    text = "\n".join(seen["email"].paragraphs)
    assert "Je me permets de vous écrire." in text and "Ta copie" in text
    assert "Taleez" in text  # rappel du clic de confirmation
