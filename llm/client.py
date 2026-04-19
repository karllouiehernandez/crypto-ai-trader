"""llm/client.py — Provider-agnostic LLM client.

Supports three providers, selected by LLM_PROVIDER in .env:
  anthropic   — Anthropic SDK, supports prompt caching (cache_control: ephemeral)
  groq        — OpenAI-compatible SDK, fast inference, generous free tier
  openrouter  — OpenAI-compatible SDK, aggregates 100+ models

All calls:
  1. Check TTL cache first (5-min minimum, enforced here)
  2. Route to provider-specific call
  3. Cache successful response
  4. Return LLMResponse(fallback=True) on any failure — never raises

Callers should always check response.fallback before using response.content.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from config import (
    ANTHROPIC_API_KEY,
    GROQ_API_KEY,
    LLM_BASE_URL,
    LLM_ENABLED,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_PROVIDER,
    OPENROUTER_API_KEY,
)
from llm.cache import _default_cache

log = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    cached: bool = False          # served from TTL cache
    fallback: bool = False        # LLM unavailable; caller should use heuristic
    tokens_used: int = 0
    provider: str = field(default_factory=lambda: LLM_PROVIDER)
    model: str = field(default_factory=lambda: LLM_MODEL)


_FALLBACK = LLMResponse(content="", fallback=True)

# Lazy-initialised provider clients
_anthropic_client = None
_openai_client = None   # used for both groq and openrouter

_PROVIDER_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def _provider_api_key(provider: str) -> str:
    provider = str(provider or "").strip().lower()
    if provider == "anthropic":
        return str(ANTHROPIC_API_KEY or "")
    if provider == "groq":
        return str(GROQ_API_KEY or "")
    if provider == "openrouter":
        return str(OPENROUTER_API_KEY or "")
    return ""


def get_generation_readiness() -> dict[str, object]:
    """Return the current dashboard generation readiness state."""
    provider = str(LLM_PROVIDER or "").strip().lower()
    env_var = _PROVIDER_KEY_ENV.get(provider)
    enabled = bool(LLM_ENABLED)
    has_key = bool(_provider_api_key(provider))
    supported_provider = env_var is not None
    ready = enabled and supported_provider and has_key

    if not enabled:
        reason = "LLM generation is disabled in config."
        missing_env_var = None
    elif not supported_provider:
        reason = f"Unsupported LLM provider `{provider or 'unknown'}`."
        missing_env_var = None
    elif not has_key:
        reason = f"Missing provider credential: {env_var}."
        missing_env_var = env_var
    else:
        reason = "Generation backend is ready."
        missing_env_var = None

    return {
        "enabled": enabled,
        "provider": provider or "unknown",
        "model": str(LLM_MODEL or ""),
        "configured": supported_provider and has_key,
        "ready": ready,
        "missing_env_var": missing_env_var,
        "reason": reason,
        "status_label": "Configured" if ready else "Unconfigured",
    }


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        import openai
        key = GROQ_API_KEY if LLM_PROVIDER == "groq" else OPENROUTER_API_KEY
        kwargs = {"api_key": key}
        if LLM_BASE_URL:
            kwargs["base_url"] = LLM_BASE_URL
        _openai_client = openai.OpenAI(**kwargs)
    return _openai_client


# ── Public API ─────────────────────────────────────────────────────────────

def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = LLM_MAX_TOKENS,
) -> LLMResponse:
    """Single entry point for all LLM calls.

    - Checks TTL cache first (returns cached result immediately)
    - Routes to correct provider based on LLM_PROVIDER
    - Caches successful responses
    - Returns LLMResponse(fallback=True) on any error — never raises
    """
    if not LLM_ENABLED:
        return LLMResponse(content="", fallback=True)

    # Cache check
    cached = _default_cache.get(system_prompt, user_prompt)
    if cached is not None:
        log.debug("llm cache hit", extra={"provider": LLM_PROVIDER})
        return LLMResponse(content=cached, cached=True, fallback=False)

    try:
        if LLM_PROVIDER == "anthropic":
            return _call_anthropic(system_prompt, user_prompt, max_tokens)
        elif LLM_PROVIDER in ("groq", "openrouter"):
            return _call_openai_compat(system_prompt, user_prompt, max_tokens)
        else:
            log.error("unknown LLM provider", extra={"provider": LLM_PROVIDER})
            return LLMResponse(content="", fallback=True)
    except Exception as exc:
        log.error("llm call failed", extra={"provider": LLM_PROVIDER, "error": str(exc)})
        return LLMResponse(content="", fallback=True)


# ── Provider implementations ───────────────────────────────────────────────

def _call_anthropic(system_prompt: str, user_prompt: str, max_tokens: int) -> LLMResponse:
    if not ANTHROPIC_API_KEY:
        log.warning("ANTHROPIC_API_KEY not set — LLM fallback")
        return LLMResponse(content="", fallback=True)

    client = _get_anthropic()
    response = client.messages.create(
        model=LLM_MODEL,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                # Prompt caching: cache the (usually large) system prompt for 5 min
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    )
    content = response.content[0].text
    tokens = response.usage.input_tokens + response.usage.output_tokens
    _default_cache.set(system_prompt, user_prompt, content)
    log.info("llm call complete",
             extra={"provider": "anthropic", "model": LLM_MODEL, "tokens": tokens})
    return LLMResponse(content=content, tokens_used=tokens)


def _call_openai_compat(system_prompt: str, user_prompt: str, max_tokens: int) -> LLMResponse:
    key = GROQ_API_KEY if LLM_PROVIDER == "groq" else OPENROUTER_API_KEY
    if not key:
        env_var = "GROQ_API_KEY" if LLM_PROVIDER == "groq" else "OPENROUTER_API_KEY"
        log.warning("%s not set — LLM fallback", env_var)
        return LLMResponse(content="", fallback=True)

    client = _get_openai_client()
    extra_headers = {}
    if LLM_PROVIDER == "openrouter":
        extra_headers = {
            "HTTP-Referer": "https://github.com/karllouiehernandez/crypto-ai-trader",
            "X-Title": "crypto-ai-trader",
        }

    response = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        extra_headers=extra_headers or None,
    )
    content = response.choices[0].message.content or ""
    tokens = (response.usage.total_tokens if response.usage else 0)
    _default_cache.set(system_prompt, user_prompt, content)
    log.info("llm call complete",
             extra={"provider": LLM_PROVIDER, "model": LLM_MODEL, "tokens": tokens})
    return LLMResponse(content=content, tokens_used=tokens)


def reset_clients() -> None:
    """Force re-initialisation of provider clients. Used in tests."""
    global _anthropic_client, _openai_client
    _anthropic_client = None
    _openai_client = None
