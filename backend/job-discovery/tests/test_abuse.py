"""Garde-fous contre l'usage abusif des routes coûteuses."""

import asyncio

import httpx
import pytest

from app import ratelimit


def test_sliding_window():
    ratelimit.reset()
    assert all(ratelimit.hit("k", 3, window=10, now=t) for t in (0, 1, 2))
    assert not ratelimit.hit("k", 3, window=10, now=5)
    # Le premier appel sort de la fenêtre : une place se libère.
    assert ratelimit.hit("k", 3, window=10, now=10.5)


def test_zero_limit_blocks():
    ratelimit.reset()
    assert not ratelimit.hit("z", 0)


def _client():
    from app.main import app
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


@pytest.mark.parametrize("url", [
    "http://www.linkedin.com/in/ada",              # pas HTTPS
    "https://evil.example/linkedin.com/in/ada",    # « linkedin.com » ailleurs que dans l'hôte
    "https://linkedin.com.evil.example/in/ada",
    "https://www.linkedin.com:8443/in/ada",
    "https://169.254.169.254/?linkedin.com",
])
def test_linkedin_fetch_only_linkedin(url):
    ratelimit.reset()

    async def go():
        async with _client() as c:
            return await c.post("/api/candidates/parse-linkedin", params={"linkedin_url": url})

    assert asyncio.run(go()).status_code == 400


def test_anonymous_resume_parsing_is_rate_limited(monkeypatch):
    ratelimit.reset()
    from app.api import candidates

    async def fake_parse(contents, filename):
        return candidates.ParsedCandidateProfile()

    monkeypatch.setattr(candidates, "parse_resume", fake_parse)

    async def go():
        async with _client() as c:
            codes = []
            for _ in range(7):
                r = await c.post("/api/candidates/parse-resume",
                                 files={"file": ("cv.pdf", b"%PDF-1.4 x", "application/pdf")})
                codes.append(r.status_code)
            return codes

    codes = asyncio.run(go())
    assert codes[:5] == [200] * 5 and codes[5:] == [429, 429]


@pytest.mark.parametrize("path", ["/api/candidates/cv-content", "/api/candidates/audit-cv",
                                  "/api/candidates/download-cover-letter"])
def test_llm_routes_need_login(path, monkeypatch):
    ratelimit.reset()
    monkeypatch.setattr("app.config.settings.auth_secret", "x")

    async def go():
        async with _client() as c:
            return await c.post(path, json={})

    assert asyncio.run(go()).status_code == 401
