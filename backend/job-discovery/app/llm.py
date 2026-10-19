"""
Accès aux modèles de langage — point unique pour tout le backend.

Deux fournisseurs : Gemini (SDK `google-genai`) et Claude (SDK `anthropic`).
`LLM_PROVIDER` choisit :
  - « auto » (défaut) : Gemini d'abord, Claude en secours. Quand Gemini répond
    « quota épuisé » (ou clé refusée), il est mis de côté `GEMINI_COOLDOWN_S`
    secondes : les appels suivants vont droit à Claude, sans perdre le temps
    d'un échec à chaque fois ;
  - « claude » ou « gemini » : un seul fournisseur, sans détour.

Les appels passent par les clients asynchrones, pour ne pas bloquer la boucle
d'événements de FastAPI pendant qu'un modèle réfléchit.
"""

import asyncio
import json as json_lib
import logging
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from types import SimpleNamespace
from typing import Any

import anthropic
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

#: Après un « quota épuisé », Gemini n'est plus essayé pendant ce délai.
GEMINI_COOLDOWN_S = 30 * 60
#: Modèles Claude qui acceptent le repli automatique côté serveur (refus de
#: sécurité : la requête est rejouée sur un autre modèle dans le même appel).
_SERVER_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1"}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16000

#: Une limite « par minute » (offre gratuite, deux personnes en même temps)
#: se lève en quelques secondes : on attend une fois plutôt que d'échouer.
#: Au-delà de ce délai, c'est un quota du jour : on n'attend pas.
MAX_RATE_WAIT_S = 12.0

_gemini_down_until = 0.0


class LLMError(RuntimeError):
    """Aucun modèle n'a pu répondre."""


# ── Choix du fournisseur ──────────────────────────────────────────────────


def _provider() -> str:
    return (settings.llm_provider or "auto").strip().lower()


def _gemini_ok() -> bool:
    return (_provider() != "claude" and bool(settings.gemini_api_key.strip())
            and time.monotonic() >= _gemini_down_until)


def _claude_ok() -> bool:
    return _provider() != "gemini" and bool(settings.anthropic_api_key.strip())


_RETRY_DELAY = re.compile(r"retryDelay['\"]?\s*:\s*['\"](\d+(?:\.\d+)?)s")


def is_rate_limited(e: Exception) -> bool:
    """Trop de demandes en même temps (429)."""
    return isinstance(e, genai_errors.ClientError) and e.code == 429


def _short_wait(e: Exception) -> float | None:
    """Le délai annoncé par une limite « par minute », ou None si ce n'en est pas une."""
    if not is_rate_limited(e):
        return None
    # Gemini annonce le délai des limites par minute ; sans délai, c'est un quota épuisé.
    m = _RETRY_DELAY.search(str(e))
    if not m:
        return None
    delay = float(m.group(1))
    return delay if delay <= MAX_RATE_WAIT_S else None


async def _with_rate_retry(call):
    """Un appel Gemini ; sur limite par minute, une seconde tentative après le délai annoncé."""
    try:
        return await call()
    except Exception as e:
        delay = _short_wait(e)
        if delay is None:
            raise
        logger.info("Gemini : limite par minute, nouvel essai dans %.0f s.", delay)
        await asyncio.sleep(delay + 0.5)
        return await call()


def _out_of_credit(e: Exception) -> bool:
    """Quota du jour ou facturation épuisés, clé refusée : inutile de réessayer tout de suite.
    Une limite par minute n'en est pas un : elle se lève d'elle-même."""
    if is_rate_limited(e):
        return _short_wait(e) is None
    if isinstance(e, genai_errors.ClientError) and e.code in (401, 403):
        return True
    text = str(e).upper()
    return any(k in text for k in ("QUOTA", "BILLING", "API_KEY_INVALID"))


def _gemini_failed(e: Exception) -> None:
    global _gemini_down_until
    if _out_of_credit(e):
        _gemini_down_until = time.monotonic() + GEMINI_COOLDOWN_S
        logger.warning("Gemini indisponible (%s) : Claude prend le relais pour %d min.",
                       type(e).__name__, GEMINI_COOLDOWN_S // 60)
    else:
        logger.warning("Gemini en échec (%s) : repli sur Claude pour cet appel.", type(e).__name__)


# ── Clients ───────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def client() -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key)


@lru_cache(maxsize=1)
def claude() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


def _claude_extra() -> dict:
    """Repli serveur sur refus de sécurité, quand le modèle le permet."""
    if settings.claude_model in _SERVER_FALLBACK_MODELS:
        return {"betas": [_FALLBACK_BETA], "fallbacks": "default"}
    return {}


def _text_of(message) -> str:
    if message.stop_reason == "refusal":
        raise LLMError("Claude a décliné la demande")
    return "".join(b.text for b in message.content if b.type == "text")


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _strip_fence(text: str) -> str:
    m = _FENCE.match(text or "")
    return m.group(1) if m else (text or "")


# ── Appels simples ────────────────────────────────────────────────────────


async def _gemini_generate(prompt: str, json: bool, schema: type[BaseModel] | None) -> str:
    config = types.GenerateContentConfig(
        response_mime_type="application/json" if (json or schema) else None,
        response_schema=schema,
    )
    response = await _with_rate_retry(lambda: client().aio.models.generate_content(
        model=settings.gemini_model, contents=prompt, config=config,
    ))
    return response.text or ""


async def _claude_generate(prompt: str, json: bool, schema: type[BaseModel] | None) -> str:
    if schema:
        message = await claude().beta.messages.parse(
            model=settings.claude_model, max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema, **_claude_extra(),
        )
        return _text_of(message)
    if json:
        prompt += "\n\nRéponds uniquement avec du JSON valide, sans texte autour."
    message = await claude().beta.messages.create(
        model=settings.claude_model, max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}], **_claude_extra(),
    )
    text = _text_of(message)
    return _strip_fence(text) if json else text


async def generate(
    prompt: str,
    *,
    json: bool = False,
    schema: type[BaseModel] | None = None,
) -> str:
    """
    Un appel unique, sans conversation. Renvoie le texte de la réponse.

    `json` force une sortie JSON ; `schema` impose en plus sa structure.
    """
    if _gemini_ok():
        try:
            return await _gemini_generate(prompt, json, schema)
        except Exception as e:
            if not _claude_ok():
                raise
            _gemini_failed(e)
    if _claude_ok():
        return await _claude_generate(prompt, json, schema)
    raise LLMError("aucun modèle configuré (GEMINI_API_KEY ou ANTHROPIC_API_KEY)")


async def generate_grounded(prompt: str) -> str:
    """
    Un appel avec recherche web (« grounding ») : Google Search chez Gemini,
    l'outil de recherche web chez Claude. Pour les faits publics récents — le
    site d'une entreprise, par exemple. Le résultat reste à vérifier par
    l'appelant.
    """
    if _gemini_ok():
        try:
            config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
            response = await _with_rate_retry(lambda: client().aio.models.generate_content(
                model=settings.gemini_model, contents=prompt, config=config,
            ))
            return response.text or ""
        except Exception as e:
            if not _claude_ok():
                raise
            _gemini_failed(e)
    if not _claude_ok():
        raise LLMError("aucun modèle configuré (GEMINI_API_KEY ou ANTHROPIC_API_KEY)")
    messages: list[dict] = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}]
    for _ in range(4):
        message = await claude().beta.messages.create(
            model=settings.claude_model, max_tokens=MAX_TOKENS,
            messages=messages, tools=tools, **_claude_extra(),
        )
        if message.stop_reason != "pause_turn":
            return _text_of(message)
        # Recherche longue mise en pause par le serveur : on la relance telle quelle.
        messages = [{"role": "user", "content": prompt},
                    {"role": "assistant", "content": message.content}]
    return _text_of(message)


# ── Conversation avec outils (Alice) ──────────────────────────────────────


@dataclass
class ChatReply:
    """Réponse d'un tour, au même format pour les deux fournisseurs :
    des morceaux (`function_call`, `text`, `thought`) et le texte complet."""
    parts: list = field(default_factory=list)
    text: str = ""


def _reply_from_gemini(response: types.GenerateContentResponse) -> ChatReply:
    parts = []
    if response.candidates and response.candidates[0].content:
        parts = list(response.candidates[0].content.parts or [])
    return ChatReply(parts=parts, text=response.text or "")


class _ClaudeChat:
    def __init__(self, system: str, history: list[tuple[str, str]], tools: types.Tool):
        self.system = system
        self.tools = [
            {"name": f.name, "description": f.description or "",
             "input_schema": f.parameters_json_schema or {"type": "object", "properties": {}}}
            for f in (tools.function_declarations or [])
        ]
        self.messages: list[dict] = [{"role": role, "content": text} for role, text in history]
        self.pending: list[Any] = []

    async def send_message(self, message) -> ChatReply:
        if isinstance(message, str):
            self.messages.append({"role": "user", "content": message})
        else:
            # Résultats d'outils (au format Gemini) : rendus aux appels en
            # attente, dans l'ordre, tous dans un seul tour.
            results = []
            for call, part in zip(self.pending, message, strict=False):
                payload = getattr(part, "function_response", None)
                body = payload.response if payload is not None else part
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                "content": json_lib.dumps(body, ensure_ascii=False, default=str)})
            self.messages.append({"role": "user", "content": results})
        response = await claude().beta.messages.create(
            model=settings.claude_model, max_tokens=MAX_TOKENS, system=self.system,
            tools=self.tools, messages=self.messages, **_claude_extra(),
        )
        # Le contenu complet repart tel quel au tour suivant (blocs de réflexion compris).
        self.messages.append({"role": "assistant", "content": response.content})
        self.pending = [b for b in response.content if b.type == "tool_use"]
        parts = []
        for block in response.content:
            if block.type == "tool_use":
                parts.append(SimpleNamespace(
                    function_call=SimpleNamespace(name=block.name, args=dict(block.input or {})),
                    text=None, thought=False))
            elif block.type == "text":
                parts.append(SimpleNamespace(function_call=None, text=block.text, thought=False))
        text = "" if response.stop_reason == "refusal" else \
            "".join(b.text for b in response.content if b.type == "text")
        return ChatReply(parts=parts, text=text)


class Chat:
    """
    Une conversation avec outils. Gemini d'abord en mode « auto » ; s'il échoue
    au premier message, la conversation continue avec Claude. Au-delà du
    premier message, on ne change plus de fournisseur en cours de route : les
    appels d'outils en attente n'auraient pas de sens pour l'autre.
    """

    def __init__(self, system: str, history: list[tuple[str, str]], tools: types.Tool):
        self._args = (system, history, tools)
        self._gemini = None
        self._claude: _ClaudeChat | None = None
        self._started = False
        if _gemini_ok():
            contents = [types.Content(role="user" if r == "user" else "model",
                                      parts=[types.Part.from_text(text=t)]) for r, t in history]
            self._gemini = client().aio.chats.create(
                model=settings.gemini_model, history=contents,
                config=types.GenerateContentConfig(
                    tools=[tools], system_instruction=system,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
        elif _claude_ok():
            self._claude = _ClaudeChat(*self._args)
        else:
            raise LLMError("aucun modèle configuré (GEMINI_API_KEY ou ANTHROPIC_API_KEY)")

    async def send_message(self, message) -> ChatReply:
        if self._gemini is not None:
            try:
                reply = _reply_from_gemini(
                    await _with_rate_retry(lambda: self._gemini.send_message(message)))
                self._started = True
                return reply
            except Exception as e:
                if self._started or not _claude_ok():
                    raise
                _gemini_failed(e)
                self._gemini, self._claude = None, _ClaudeChat(*self._args)
        self._started = True
        return await self._claude.send_message(message)
