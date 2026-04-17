"""tests/test_llm_client.py — Unit tests for llm/client.py (all providers mocked)."""

from unittest.mock import MagicMock, patch

import pytest

from llm.cache import _default_cache
from llm.client import LLMResponse, call_llm, reset_clients


@pytest.fixture(autouse=True)
def clean_state():
    """Clear cache and reset clients before every test."""
    _default_cache.clear()
    reset_clients()
    yield
    _default_cache.clear()
    reset_clients()


# ── LLM_ENABLED=False ─────────────────────────────────────────────────────

def test_returns_fallback_when_disabled():
    with patch("llm.client.LLM_ENABLED", False):
        resp = call_llm("sys", "user")
    assert resp.fallback is True
    assert resp.content == ""


# ── Anthropic provider ────────────────────────────────────────────────────

def _mock_anthropic_response(text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    msg.usage.input_tokens = 100
    msg.usage.output_tokens = 50
    return msg


def test_anthropic_returns_content():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response("BUY signal logic")

    with patch("llm.client.LLM_PROVIDER", "anthropic"), \
         patch("llm.client.ANTHROPIC_API_KEY", "sk-test"), \
         patch("llm.client._get_anthropic", return_value=mock_client):
        resp = call_llm("system", "user")

    assert resp.fallback is False
    assert resp.content == "BUY signal logic"
    assert resp.tokens_used == 150


def test_anthropic_fallback_when_no_key():
    with patch("llm.client.LLM_PROVIDER", "anthropic"), \
         patch("llm.client.ANTHROPIC_API_KEY", ""):
        resp = call_llm("system", "user")
    assert resp.fallback is True


def test_anthropic_fallback_on_exception():
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("network error")

    with patch("llm.client.LLM_PROVIDER", "anthropic"), \
         patch("llm.client.ANTHROPIC_API_KEY", "sk-test"), \
         patch("llm.client._get_anthropic", return_value=mock_client):
        resp = call_llm("system", "user")

    assert resp.fallback is True


# ── Groq provider ─────────────────────────────────────────────────────────

def _mock_openai_response(text: str):
    msg = MagicMock()
    msg.choices = [MagicMock(message=MagicMock(content=text))]
    msg.usage.total_tokens = 80
    return msg


def test_groq_returns_content():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response("groq result")

    with patch("llm.client.LLM_PROVIDER", "groq"), \
         patch("llm.client.GROQ_API_KEY", "gsk_test"), \
         patch("llm.client._get_openai_client", return_value=mock_client):
        resp = call_llm("system", "user")

    assert resp.fallback is False
    assert resp.content == "groq result"


def test_groq_fallback_when_no_key():
    with patch("llm.client.LLM_PROVIDER", "groq"), \
         patch("llm.client.GROQ_API_KEY", ""):
        resp = call_llm("system", "user")
    assert resp.fallback is True


# ── OpenRouter provider ───────────────────────────────────────────────────

def test_openrouter_returns_content():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response("openrouter result")

    with patch("llm.client.LLM_PROVIDER", "openrouter"), \
         patch("llm.client.OPENROUTER_API_KEY", "sk-or-test"), \
         patch("llm.client._get_openai_client", return_value=mock_client):
        resp = call_llm("system", "user")

    assert resp.fallback is False
    assert resp.content == "openrouter result"


def test_openrouter_fallback_when_no_key():
    with patch("llm.client.LLM_PROVIDER", "openrouter"), \
         patch("llm.client.OPENROUTER_API_KEY", ""):
        resp = call_llm("system", "user")
    assert resp.fallback is True


# ── Unknown provider ──────────────────────────────────────────────────────

def test_unknown_provider_returns_fallback():
    with patch("llm.client.LLM_PROVIDER", "unknown_xyz"), \
         patch("llm.client.LLM_ENABLED", True):
        resp = call_llm("system", "user")
    assert resp.fallback is True


# ── Caching behaviour ─────────────────────────────────────────────────────

def test_second_call_served_from_cache():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response("cached value")

    with patch("llm.client.LLM_PROVIDER", "anthropic"), \
         patch("llm.client.ANTHROPIC_API_KEY", "sk-test"), \
         patch("llm.client._get_anthropic", return_value=mock_client):
        r1 = call_llm("sys", "user")
        r2 = call_llm("sys", "user")

    assert r1.content == r2.content == "cached value"
    assert r2.cached is True
    # LLM was only called once
    assert mock_client.messages.create.call_count == 1


def test_different_prompts_not_cached_together():
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _mock_anthropic_response("result_a"),
        _mock_anthropic_response("result_b"),
    ]

    with patch("llm.client.LLM_PROVIDER", "anthropic"), \
         patch("llm.client.ANTHROPIC_API_KEY", "sk-test"), \
         patch("llm.client._get_anthropic", return_value=mock_client):
        r1 = call_llm("sys", "user_a")
        r2 = call_llm("sys", "user_b")

    assert r1.content == "result_a"
    assert r2.content == "result_b"
    assert mock_client.messages.create.call_count == 2
