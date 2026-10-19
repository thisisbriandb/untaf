"""
Accès aux modèles de langage — point unique pour tout le backend.

Trois fournisseurs, essayés dans cet ordre quand leur clé est configurée :
  1. Gemini (SDK `google-genai`), en offre payante : le modèle principal ;
  2. Groq (API compatible OpenAI, SDK `openai`), en secours gratuit : modèles
     ouverts, sans entraînement sur les données envoyées. Deux modèles, chacun
     avec sa propre limite par minute : quand le premier sature, le second
     prend le relais ;
  3. Claude (SDK `anthropic`).

`LLM_PROVIDER` : « auto » (défaut) suit cet ordre ; « groq », « gemini » ou
« claude » n'utilise que celui-là. Un fournisseur qui répond « quota épuisé »
ou « clé refusée » est mis de côté un moment : les appels suivants vont droit
au suivant, sans perdre le temps d'un échec à chaque fois.

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
import openai
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)

PROVIDERS = ("gemini", "groq", "claude")
#: Après un « quota épuisé » ou une clé refusée, le fournisseur est mis de côté.
COOLDOWN_S = 30 * 60
#: Modèles Claude qui acceptent le repli automatique côté serveur (refus de
#: sécurité : la requête est rejouée sur un autre modèle dans le même appel).
_SERVER_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1"}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16000
#: gpt-oss réfléchit avant de répondre : sa réflexion compte dans ce plafond.
GROQ_MAX_TOKENS = 8192
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

#: Une limite « par minute » (offre gratuite, deux personnes en même temps)
#: se lève en quelques secondes : on attend une fois plutôt que d'échouer.
#: Au-delà de ce délai, c'est un quota du jour : on n'attend pas.
MAX_RATE_WAIT_S = 12.0

#: Fournisseur → instant jusqu'où il est mis de côté.
_down_until: dict[str, float] = {}


class LLMError(RuntimeError):
    """Aucun modèle n'a pu répondre."""


# ── Choix du fournisseur ──────────────────────────────────────────────────


def _provider() -> str:
    return (settings.llm_provider or "auto").strip().lower()


def _has_key(p: str) -> bool:
    key = {"groq": settings.groq_api_key, "gemini": settings.gemini_api_key,
           "claude": settings.anthropic_api_key}[p]
    return bool((key or "").strip())


def _chain(capable: tuple[str, ...] = PROVIDERS) -> list[str]:
    """Les fournisseurs à essayer, dans l'ordre, pour une capacité donnée."""
    chosen = _provider()
    order = [chosen] if chosen in PROVIDERS else list(PROVIDERS)
    now = time.monotonic()
    usable = [p for p in order if p in capable and _has_key(p)]
    ready = [p for p in usable if now >= _down_until.get(p, 0.0)]
    # Tous mis de côté : on retente quand même le premier plutôt que rien.
    return ready or usable[:1]


# ── Limites et erreurs ────────────────────────────────────────────────────

_RETRY_DELAY = re.compile(r"retryDelay['\"]?\s*:\s*['\"](\d+(?:\.\d+)?)s")


def is_rate_limited(e: Exception) -> bool:
    """Trop de demandes en même temps (429), quel que soit le fournisseur."""
    if isinstance(e, genai_errors.ClientError):
        return e.code == 429
    return isinstance(e, (openai.RateLimitError, anthropic.RateLimitError))


def _announced_wait(e: Exception) -> float | None:
    """Le délai annoncé par le fournisseur avant de réessayer, s'il en annonce un."""
    if isinstance(e, genai_errors.ClientError):
        m = _RETRY_DELAY.search(str(e))
        return float(m.group(1)) if m else None
    response = getattr(e, "response", None)
    raw = response.headers.get("retry-after") if response is not None else None
    try:
        return float(raw) if raw is not None else None
    except ValueError:
        return None


def _short_wait(e: Exception) -> float | None:
    """Le délai d'une limite « par minute », ou None si ce n'en est pas une."""
    if not is_rate_limited(e):
        return None
    # Sans délai annoncé, c'est un quota épuisé.
    delay = _announced_wait(e)
    return delay if delay is not None and delay <= MAX_RATE_WAIT_S else None


def _out_of_credit(e: Exception) -> bool:
    """Quota du jour ou facturation épuisés, clé refusée : inutile de réessayer tout de suite.
    Une limite par minute n'en est pas un : elle se lève d'elle-même."""
    if is_rate_limited(e):
        return _short_wait(e) is None
    if isinstance(e, genai_errors.ClientError) and e.code in (401, 403):
        return True
    if isinstance(e, (openai.AuthenticationError, openai.PermissionDeniedError,
                      anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return True
    text = str(e).upper()
    return any(k in text for k in ("QUOTA", "BILLING", "API_KEY_INVALID", "INSUFFICIENT"))


def _failed(p: str, e: Exception) -> None:
    if _out_of_credit(e):
        _down_until[p] = time.monotonic() + COOLDOWN_S
        logger.warning("%s indisponible (%s) : mis de côté %d min.", p, type(e).__name__, COOLDOWN_S // 60)
    else:
        logger.warning("%s en échec (%s) : fournisseur suivant pour cet appel.", p, type(e).__name__)


async def _with_rate_retry(call):
    """Un appel ; sur limite par minute, une seconde tentative après le délai annoncé."""
    try:
        return await call()
    except Exception as e:
        delay = _short_wait(e)
        if delay is None:
            raise
        logger.info("Limite par minute, nouvel essai dans %.0f s.", delay)
        await asyncio.sleep(delay + 0.5)
        return await call()


# ── Clients ───────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def client() -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key)


@lru_cache(maxsize=1)
def claude() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


@lru_cache(maxsize=1)
def groq() -> openai.AsyncOpenAI:
    # Les nouveaux essais sont gérés ici (changement de modèle), pas par le SDK.
    return openai.AsyncOpenAI(api_key=settings.groq_api_key, base_url=GROQ_BASE_URL,
                              max_retries=0, timeout=60)


def _groq_models() -> list[str]:
    return [m for m in (settings.groq_model, settings.groq_fallback_model) if m]


async def _groq_complete(check=None, **kwargs):
    """
    Une complétion Groq. Chaque modèle a sa propre limite par minute : quand
    l'un sature, l'autre prend le relais ; s'ils saturent tous, une seconde
    tentative après le délai annoncé. `check(réponse)` peut refuser une réponse
    (JSON invalide) : le modèle suivant est alors essayé.
    """
    last: Exception | None = None
    waits: list[float] = []
    for attempt in range(2):
        for model in _groq_models():
            try:
                response = await groq().chat.completions.create(
                    model=model, max_tokens=GROQ_MAX_TOKENS, **kwargs)
                if check:
                    check(response)
                return response
            except openai.RateLimitError as e:
                last = e
                delay = _short_wait(e)
                if delay is not None:
                    waits.append(delay)
            except (ValidationError, ValueError) as e:
                last = e
        if attempt == 0 and waits and len(waits) == len(_groq_models()):
            await asyncio.sleep(min(waits) + 0.5)
            waits.clear()
            continue
        break
    raise last or LLMError("Groq n'a pas répondu")


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


async def _groq_generate(prompt: str, json: bool, schema: type[BaseModel] | None) -> str:
    kwargs: dict[str, Any] = {}
    check = None
    if schema:
        prompt += ("\n\nRéponds uniquement avec un objet JSON conforme à ce schéma :\n"
                   + json_lib.dumps(schema.model_json_schema(), ensure_ascii=False))
        kwargs["response_format"] = {"type": "json_object"}

        def check(response):
            schema.model_validate_json(_strip_fence(response.choices[0].message.content or ""))
    elif json:
        prompt += "\n\nRéponds uniquement avec du JSON valide, sans texte autour."
        kwargs["response_format"] = {"type": "json_object"}

        def check(response):
            json_lib.loads(_strip_fence(response.choices[0].message.content or ""))
    response = await _groq_complete(check=check, messages=[{"role": "user", "content": prompt}], **kwargs)
    text = response.choices[0].message.content or ""
    return _strip_fence(text) if (json or schema) else text


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


def _generator(p: str):
    # Relue à chaque appel (et non figée au chargement) : remplaçable en test.
    return globals()[f"_{p}_generate"]


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
    last: Exception | None = None
    for p in _chain():
        try:
            return await _generator(p)(prompt, json, schema)
        except Exception as e:
            last = e
            _failed(p, e)
    raise last or LLMError("aucun modèle configuré (GEMINI_API_KEY, GROQ_API_KEY ou ANTHROPIC_API_KEY)")


async def _gemini_grounded(prompt: str) -> str:
    config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
    response = await _with_rate_retry(lambda: client().aio.models.generate_content(
        model=settings.gemini_model, contents=prompt, config=config,
    ))
    return response.text or ""


async def _claude_grounded(prompt: str) -> str:
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


#: Recherche web : Gemini (Google Search) et Claude seulement.
_GROUNDED = ("gemini", "claude")


async def generate_grounded(prompt: str) -> str:
    """
    Un appel avec recherche web (« grounding ») : Google Search chez Gemini,
    l'outil de recherche web chez Claude. Pour les faits publics récents — le
    site d'une entreprise, par exemple. Le résultat reste à vérifier par
    l'appelant. Sans l'un de ces deux fournisseurs, lève LLMError.
    """
    last: Exception | None = None
    for p in _chain(_GROUNDED):
        try:
            return await globals()[f"_{p}_grounded"](prompt)
        except Exception as e:
            last = e
            _failed(p, e)
    raise last or LLMError("recherche web indisponible (Gemini ou Claude requis)")


# ── Conversation avec outils (Alice) ──────────────────────────────────────


@dataclass
class ChatReply:
    """Réponse d'un tour, au même format pour tous les fournisseurs :
    des morceaux (`function_call`, `text`, `thought`) et le texte complet."""
    parts: list = field(default_factory=list)
    text: str = ""


def _call_part(name: str, args: dict) -> SimpleNamespace:
    return SimpleNamespace(function_call=SimpleNamespace(name=name, args=args), text=None, thought=False)


def _text_part(text: str) -> SimpleNamespace:
    return SimpleNamespace(function_call=None, text=text, thought=False)


def _tool_results(message) -> list[tuple[Any, Any]]:
    """Résultats d'outils (au format Gemini) → (nom, contenu), dans l'ordre."""
    out = []
    for part in message:
        payload = getattr(part, "function_response", None)
        out.append((getattr(payload, "name", None), payload.response if payload is not None else part))
    return out


class _GeminiChat:
    def __init__(self, system: str, history: list[tuple[str, str]], tools: types.Tool):
        contents = [types.Content(role="user" if r == "user" else "model",
                                  parts=[types.Part.from_text(text=t)]) for r, t in history]
        self.chat = client().aio.chats.create(
            model=settings.gemini_model, history=contents,
            config=types.GenerateContentConfig(
                tools=[tools], system_instruction=system,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )

    async def send_message(self, message) -> ChatReply:
        response = await _with_rate_retry(lambda: self.chat.send_message(message))
        parts = []
        if response.candidates and response.candidates[0].content:
            parts = list(response.candidates[0].content.parts or [])
        return ChatReply(parts=parts, text=response.text or "")


class _GroqChat:
    def __init__(self, system: str, history: list[tuple[str, str]], tools: types.Tool):
        self.tools = [
            {"type": "function", "function": {
                "name": f.name, "description": f.description or "",
                "parameters": f.parameters_json_schema or {"type": "object", "properties": {}}}}
            for f in (tools.function_declarations or [])
        ]
        self.messages: list[dict] = [{"role": "system", "content": system}]
        self.messages += [{"role": role, "content": text} for role, text in history]
        self.pending: list[Any] = []

    async def send_message(self, message) -> ChatReply:
        if isinstance(message, str):
            self.messages.append({"role": "user", "content": message})
        else:
            # Résultats d'outils rendus aux appels en attente, dans l'ordre.
            for call, (_, body) in zip(self.pending, _tool_results(message), strict=False):
                self.messages.append({"role": "tool", "tool_call_id": call.id,
                                      "content": json_lib.dumps(body, ensure_ascii=False, default=str)})
        response = await _groq_complete(messages=self.messages, tools=self.tools)
        msg = response.choices[0].message
        calls = list(msg.tool_calls or [])
        entry: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
        if calls:
            entry["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments or "{}"}}
                for c in calls
            ]
        self.messages.append(entry)
        self.pending = calls
        parts = []
        for c in calls:
            try:
                args = json_lib.loads(c.function.arguments or "{}")
            except ValueError:
                args = {}
            parts.append(_call_part(c.function.name, args if isinstance(args, dict) else {}))
        if msg.content:
            parts.append(_text_part(msg.content))
        return ChatReply(parts=parts, text=msg.content or "")


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
            # Résultats d'outils rendus aux appels en attente, dans l'ordre,
            # tous dans un seul tour.
            results = [{"type": "tool_result", "tool_use_id": call.id,
                        "content": json_lib.dumps(body, ensure_ascii=False, default=str)}
                       for call, (_, body) in zip(self.pending, _tool_results(message), strict=False)]
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
                parts.append(_call_part(block.name, dict(block.input or {})))
            elif block.type == "text":
                parts.append(_text_part(block.text))
        text = "" if response.stop_reason == "refusal" else \
            "".join(b.text for b in response.content if b.type == "text")
        return ChatReply(parts=parts, text=text)


_CHATS = {"groq": _GroqChat, "gemini": _GeminiChat, "claude": _ClaudeChat}


class Chat:
    """
    Une conversation avec outils. Le premier message essaie les fournisseurs
    dans l'ordre ; celui qui répond garde la conversation. Ensuite, on ne
    change plus de fournisseur en cours de route : les appels d'outils en
    attente n'auraient pas de sens pour un autre.
    """

    def __init__(self, system: str, history: list[tuple[str, str]], tools: types.Tool):
        self._args = (system, history, tools)
        self._chain = _chain()
        self._impl = None
        if not self._chain:
            raise LLMError("aucun modèle configuré (GEMINI_API_KEY, GROQ_API_KEY ou ANTHROPIC_API_KEY)")

    async def send_message(self, message) -> ChatReply:
        if self._impl is not None:
            return await self._impl.send_message(message)
        last: Exception | None = None
        for p in self._chain:
            impl = _CHATS[p](*self._args)
            try:
                reply = await impl.send_message(message)
            except Exception as e:
                last = e
                _failed(p, e)
                continue
            self._impl = impl
            return reply
        raise last or LLMError("aucun modèle n'a répondu")
