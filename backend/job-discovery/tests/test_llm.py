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
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(llm, "_down_until", {})


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
    monkeypatch.setattr(settings, "groq_api_key", "")
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


# ── Groq ──────────────────────────────────────────────────────────────────

import httpx  # noqa: E402
import openai  # noqa: E402


def _completion(content=None, tool_calls=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _groq_429(retry_after="2"):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, headers={"retry-after": retry_after}, request=request)
    return openai.RateLimitError("rate limited", response=response, body=None)


class FakeGroq:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs.get("messages", []))})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def groq_only(keys, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "groq_api_key", "gsk_test")
    monkeypatch.setattr(settings, "groq_model", "openai/gpt-oss-120b")
    monkeypatch.setattr(settings, "groq_fallback_model", "qwen/qwen3.8-27b")


def test_gemini_en_premier_groq_en_secours(keys, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "groq_api_key", "gsk_test")
    fake = FakeGroq([_completion("groq")])
    monkeypatch.setattr(llm, "groq", lambda: fake)

    async def gemini_ok(*a, **k):
        return "gemini"

    monkeypatch.setattr(llm, "_gemini_generate", gemini_ok)
    assert asyncio.run(llm.generate("salut")) == "gemini"
    assert fake.calls == []

    async def gemini_down(*a, **k):
        raise _quota()

    monkeypatch.setattr(llm, "_gemini_generate", gemini_down)
    assert asyncio.run(llm.generate("salut")) == "groq"
    assert fake.calls[0]["model"] == "openai/gpt-oss-120b"


def test_groq_modele_sature_le_second_prend_le_relais(groq_only, monkeypatch):
    fake = FakeGroq([_groq_429("3"), _completion("ok")])
    monkeypatch.setattr(llm, "groq", lambda: fake)
    assert asyncio.run(llm.generate("x")) == "ok"
    assert [c["model"] for c in fake.calls] == ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]


def test_groq_tous_satures_on_attend_puis_on_reessaie(groq_only, monkeypatch):
    fake = FakeGroq([_groq_429("2"), _groq_429("4"), _completion("ok")])
    waits = []

    async def fake_sleep(s):
        waits.append(s)

    monkeypatch.setattr(llm, "groq", lambda: fake)
    monkeypatch.setattr(llm.asyncio, "sleep", fake_sleep)
    assert asyncio.run(llm.generate("x")) == "ok"
    assert waits and 2 <= waits[0] < 4


def test_groq_quota_du_jour_bascule_sur_claude(groq_only, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "a")
    fake = FakeGroq([_groq_429("7200"), _groq_429("7200")])
    claude_fake = FakeClaude([_message(_text("claude")), _message(_text("claude"))])
    monkeypatch.setattr(llm, "groq", lambda: fake)
    monkeypatch.setattr(llm, "claude", lambda: claude_fake)
    assert asyncio.run(llm.generate("x")) == "claude"
    # Groq mis de côté : l'appel suivant ne le retente pas.
    assert asyncio.run(llm.generate("y")) == "claude"
    assert len(fake.calls) == 2


def test_groq_schema_invalide_modele_suivant(groq_only, monkeypatch):
    from pydantic import BaseModel

    class Sortie(BaseModel):
        titre: str

    fake = FakeGroq([_completion('{"autre": 1}'), _completion('{"titre": "Data analyst"}')])
    monkeypatch.setattr(llm, "groq", lambda: fake)
    text = asyncio.run(llm.generate("x", schema=Sortie))
    assert Sortie.model_validate_json(text).titre == "Data analyst"
    assert fake.calls[0]["response_format"] == {"type": "json_object"}


def test_conversation_groq_avec_outils(groq_only, monkeypatch):
    call = SimpleNamespace(id="call_1", function=SimpleNamespace(name="search_jobs", arguments='{"query": "data"}'))
    fake = FakeGroq([_completion(None, [call]), _completion("Voici 2 offres.")])
    monkeypatch.setattr(llm, "groq", lambda: fake)
    tools = types.Tool(function_declarations=[types.FunctionDeclaration(
        name="search_jobs", description="Cherche",
        parameters_json_schema={"type": "object", "properties": {"query": {"type": "string"}}})])

    chat = llm.Chat("système", [("user", "salut"), ("assistant", "bonjour")], tools)
    first = asyncio.run(chat.send_message("des offres ?"))
    assert first.parts[0].function_call.name == "search_jobs"
    assert first.parts[0].function_call.args == {"query": "data"}

    result = types.Part.from_function_response(name="search_jobs", response={"jobs": [1, 2]})
    second = asyncio.run(chat.send_message([result]))
    assert second.text == "Voici 2 offres."

    sent = fake.calls[1]
    assert sent["tools"][0]["function"]["name"] == "search_jobs"
    assert [m["role"] for m in sent["messages"]] == ["system", "user", "assistant", "user", "assistant", "tool"]
    assert sent["messages"][-1]["tool_call_id"] == "call_1"
    assert sent["messages"][-2]["tool_calls"][0]["function"]["name"] == "search_jobs"


def test_recherche_web_sans_gemini_ni_claude(groq_only, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with pytest.raises(llm.LLMError):
        asyncio.run(llm.generate_grounded("site de Decathlon ?"))
