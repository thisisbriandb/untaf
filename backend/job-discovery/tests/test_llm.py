"""Gemini d'abord, Claude en secours, et plus de détour par Gemini quand son crédit est épuisé."""

import asyncio
from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors
from google.genai import types

from app import llm
from app.config import settings


def _message(*blocks, stop="end_turn"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop)


def _text(t):
    return SimpleNamespace(type="text", text=t)


class FakeClaude:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create, parse=self.create))

    async def create(self, **kwargs):
        # Copie : la conversation continue de s'allonger après l'appel.
        self.calls.append({**kwargs, "messages": list(kwargs.get("messages", []))})
        return self.replies.pop(0)


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "g")
    monkeypatch.setattr(settings, "anthropic_api_key", "a")
    monkeypatch.setattr(settings, "llm_provider", "auto")
    monkeypatch.setattr(settings, "claude_model", "claude-opus-5-5")
    monkeypatch.setattr(llm, "_gemini_down_until", 0.0)


def _quota():
    return genai_errors.ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED",
                                                    "message": "Quota exceeded"}})


def test_quota_gemini_bascule_sur_claude_et_ne_reessaie_plus(keys, monkeypatch):
    gemini_calls = []

    async def gemini_down(*a, **k):
        gemini_calls.append(1)
        raise _quota()

    fake = FakeClaude([_message(_text("un")), _message(_text("deux"))])
    monkeypatch.setattr(llm, "_gemini_generate", gemini_down)
    monkeypatch.setattr(llm, "claude", lambda: fake)

    assert asyncio.run(llm.generate("a")) == "un"
    assert asyncio.run(llm.generate("b")) == "deux"
    # Un seul essai Gemini : le second appel va droit à Claude.
    assert len(gemini_calls) == 1 and len(fake.calls) == 2
    assert fake.calls[0]["model"] == "claude-opus-5-5"
    assert fake.calls[0]["fallbacks"] == "default"


def test_autre_erreur_gemini_repli_ponctuel(keys, monkeypatch):
    attempts = []

    async def gemini_flaky(*a, **k):
        attempts.append(1)
        raise RuntimeError("timeout")

    fake = FakeClaude([_message(_text("ok")), _message(_text("ok"))])
    monkeypatch.setattr(llm, "_gemini_generate", gemini_flaky)
    monkeypatch.setattr(llm, "claude", lambda: fake)
    asyncio.run(llm.generate("a"))
    asyncio.run(llm.generate("b"))
    # Une panne passagère ne met pas Gemini de côté.
    assert len(attempts) == 2


def test_fournisseur_claude_sans_detour(keys, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "claude")

    async def never(*a, **k):
        raise AssertionError("Gemini ne doit pas être appelé")

    fake = FakeClaude([_message(_text('```json\n{"a": 1}\n```'))])
    monkeypatch.setattr(llm, "_gemini_generate", never)
    monkeypatch.setattr(llm, "claude", lambda: fake)
    assert asyncio.run(llm.generate("x", json=True)) == '{"a": 1}'


def test_refus_leve_une_erreur(keys, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "claude")
    monkeypatch.setattr(llm, "claude", lambda: FakeClaude([_message(stop="refusal")]))
    with pytest.raises(llm.LLMError):
        asyncio.run(llm.generate("x"))


def test_sans_cle_claude_l_erreur_gemini_remonte(keys, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")

    async def gemini_down(*a, **k):
        raise _quota()

    monkeypatch.setattr(llm, "_gemini_generate", gemini_down)
    with pytest.raises(genai_errors.ClientError):
        asyncio.run(llm.generate("x"))


def test_conversation_claude_avec_outils(keys, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "claude")
    call = SimpleNamespace(type="tool_use", id="tu_1", name="search_jobs", input={"query": "dev"})
    fake = FakeClaude([_message(call, stop="tool_use"), _message(_text("Voici 3 offres."))])
    monkeypatch.setattr(llm, "claude", lambda: fake)
    tools = types.Tool(function_declarations=[types.FunctionDeclaration(
        name="search_jobs", description="Cherche",
        parameters_json_schema={"type": "object", "properties": {"query": {"type": "string"}}})])

    chat = llm.Chat("système", [("user", "salut"), ("assistant", "bonjour")], tools)
    first = asyncio.run(chat.send_message("des offres ?"))
    assert first.parts[0].function_call.name == "search_jobs"
    assert first.parts[0].function_call.args == {"query": "dev"}

    result = types.Part.from_function_response(name="search_jobs", response={"jobs": [1, 2, 3]})
    second = asyncio.run(chat.send_message([result]))
    assert second.text == "Voici 3 offres."

    sent = fake.calls[1]
    assert sent["tools"][0]["name"] == "search_jobs" and sent["system"] == "système"
    tool_result = sent["messages"][-1]["content"][0]
    assert tool_result["tool_use_id"] == "tu_1" and '"jobs": [1, 2, 3]' in tool_result["content"]
    assert [m["role"] for m in sent["messages"]] == ["user", "assistant", "user", "assistant", "user"]


def test_llm_configure(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "a")
    monkeypatch.setattr(settings, "llm_provider", "auto")
    assert settings.llm_configured
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    assert not settings.llm_configured


def _per_minute(delay="2s"):
    return genai_errors.ClientError(429, {"error": {
        "code": 429, "status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded",
        "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": delay}]}})


def test_limite_par_minute_on_attend_et_on_reessaie(keys, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    calls, waits = [], []

    async def generate_content(**kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise _per_minute("2s")
        return SimpleNamespace(text="ok")

    async def fake_sleep(s):
        waits.append(s)

    fake_client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    monkeypatch.setattr(llm, "client", lambda: fake_client)
    monkeypatch.setattr(llm.asyncio, "sleep", fake_sleep)
    assert asyncio.run(llm.generate("x")) == "ok"
    assert len(calls) == 2 and waits and waits[0] >= 2


def test_limite_par_minute_ne_coupe_pas_gemini(keys):
    # Une limite par minute n'est pas un crédit épuisé : pas de mise à l'écart de 30 min.
    assert not llm._out_of_credit(_per_minute("10s"))
    # Un quota du jour (délai long ou inconnu) l'est.
    assert llm._out_of_credit(_per_minute("3600s"))
    assert llm._out_of_credit(_quota())
