from types import SimpleNamespace

import pytest

from app.agents.application import cv_resolver
from app.api.candidates import _prepare_photo_path, photo_mime_of

PNG = open("/home/user/untaf/extension/icons/128.png", "rb").read() if __import__("os").path.exists(
    "/home/user/untaf/extension/icons/128.png") else b"\x89PNG\r\n\x1a\n" + b"0" * 64


def test_photo_type_is_checked_by_content():
    assert photo_mime_of(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
    assert photo_mime_of(PNG) == "image/png"
    assert photo_mime_of(b"<svg>") is None


def test_download_never_fetches_urls_or_local_files():
    assert _prepare_photo_path("https://example.com/me.jpg") is None
    assert _prepare_photo_path("/etc/passwd") is None
    assert _prepare_photo_path(None) is None


@pytest.mark.skipif(not cv_resolver.HAS_ENGINE, reason="cv-engine absent")
def test_tailored_cv_carries_the_photo_only_when_asked():
    c = SimpleNamespace(
        full_name="Camille Martin", email="c@ex.fr", phone="", linkedin_url=None, headline="Dev",
        skills=["Python"], resume_file=None, resume_filename=None, photo=PNG, photo_mime="image/png",
        cv_design={"mode": "template", "template_id": "tech", "show_photo": True},
        cv_content={"summary": "Dev", "experiences": [], "education": []},
    )
    with_photo, _, mode = cv_resolver.resolve_cv(c, {"headline": "Dev Python", "summary": "x"})
    c.cv_design["show_photo"] = False
    without, _, _ = cv_resolver.resolve_cv(c, {"headline": "Dev Python", "summary": "x"})
    assert mode == "tailored" and len(with_photo) > len(without)
    png, _, _ = cv_resolver.resolve_cv(c, {"headline": "Dev Python", "summary": "x"}, image=True)
    assert png.startswith(b"\x89PNG")
