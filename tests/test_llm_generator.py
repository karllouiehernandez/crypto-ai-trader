"""tests/test_llm_generator.py — Unit tests for llm/generator.py."""

from unittest.mock import patch

import pytest

from llm.cache import _default_cache
from llm.client import LLMResponse, reset_clients
from llm.generator import _is_valid_python, _strip_fences, generate_and_discover_strategy, generate_strategy
from strategies.loader import clear_registry

VALID_STRATEGY_CODE = '''
import pandas as pd
from strategy.base import StrategyBase
from strategy.regime import Regime

class GeneratedRSI(StrategyBase):
    name = "generated_rsi_v1"
    description = "Generated RSI strategy."
    version = "1.0.0"
    regimes = [Regime.RANGING]

    def default_params(self) -> dict:
        return {}

    def param_schema(self) -> list[dict]:
        return []

    def should_long(self, df: pd.DataFrame) -> bool:
        return df.iloc[-1]["rsi_14"] < 30

    def should_short(self, df: pd.DataFrame) -> bool:
        return df.iloc[-1]["rsi_14"] > 70
'''.strip()


@pytest.fixture(autouse=True)
def clean():
    _default_cache.clear()
    reset_clients()
    clear_registry()
    yield
    _default_cache.clear()
    clear_registry()


def _mock_llm(content: str, fallback: bool = False):
    return LLMResponse(content=content, fallback=fallback)


# ── _strip_fences ──────────────────────────────────────────────────────────

def test_strip_fences_removes_python_fence():
    raw = "```python\ncode here\n```"
    assert _strip_fences(raw) == "code here"


def test_strip_fences_removes_plain_fence():
    raw = "```\ncode here\n```"
    assert _strip_fences(raw) == "code here"


def test_strip_fences_no_op_when_no_fence():
    raw = "x = 1"
    assert _strip_fences(raw) == "x = 1"


def test_strip_fences_trims_whitespace():
    raw = "  \n```python\ncode\n```\n  "
    assert _strip_fences(raw) == "code"


# ── _is_valid_python ──────────────────────────────────────────────────────

def test_valid_python_returns_true():
    assert _is_valid_python("x = 1 + 2") is True


def test_invalid_python_returns_false():
    assert _is_valid_python("def broken(:") is False


def test_empty_string_is_valid_python():
    assert _is_valid_python("") is True


# ── generate_strategy ─────────────────────────────────────────────────────

def test_generate_returns_code_when_llm_responds(tmp_path):
    with patch("llm.generator.call_llm", return_value=_mock_llm(VALID_STRATEGY_CODE)), \
         patch("llm.generator.STRATEGIES_DIR", tmp_path):
        code, resp = generate_strategy("RSI reversal", save=True)

    assert code is not None
    assert code.startswith("# GENERATED STRATEGY DRAFT")
    assert "GeneratedRSI" in code
    assert resp.fallback is False
    # File should have been written to tmp_path
    files = list(tmp_path.glob("generated_*.py"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8").startswith("# GENERATED STRATEGY DRAFT")


def test_generate_returns_none_when_llm_unavailable():
    with patch("llm.generator.call_llm", return_value=_mock_llm("", fallback=True)):
        code, resp = generate_strategy("RSI reversal", save=False)

    assert code is None
    assert resp.fallback is True


def test_generate_returns_none_on_syntax_error():
    bad_code = "def broken(:"
    with patch("llm.generator.call_llm", return_value=_mock_llm(bad_code)):
        code, resp = generate_strategy("bad strategy", save=False)

    assert code is None


def test_generate_strips_fences_before_validation():
    fenced = f"```python\n{VALID_STRATEGY_CODE}\n```"
    with patch("llm.generator.call_llm", return_value=_mock_llm(fenced)):
        code, _ = generate_strategy("fenced strategy", save=False)

    assert code is not None
    assert "```" not in code


def test_generate_save_false_does_not_write_file(tmp_path):
    with patch("llm.generator.call_llm", return_value=_mock_llm(VALID_STRATEGY_CODE)), \
         patch("llm.generator.STRATEGIES_DIR", tmp_path):
        generate_strategy("test", save=False)

    assert list(tmp_path.glob("generated_*.py")) == []


def test_generate_returns_none_on_empty_llm_content():
    with patch("llm.generator.call_llm", return_value=_mock_llm("   ")):
        code, _ = generate_strategy("empty response", save=False)

    assert code is None


def test_generate_and_discover_strategy_returns_loaded_plugin_metadata(tmp_path):
    with patch("llm.generator.call_llm", return_value=_mock_llm(VALID_STRATEGY_CODE)), \
         patch("llm.generator.STRATEGIES_DIR", tmp_path):
        result = generate_and_discover_strategy("RSI reversal")

    assert result["load_status"] == "loaded"
    assert result["code"].startswith("# GENERATED STRATEGY DRAFT")
    assert result["strategy_names"] == ["generated_rsi_v1"]
    assert result["strategies"][0]["is_generated"] is True
    assert result["file_name"].startswith("generated_")


def test_generate_and_discover_strategy_returns_generation_failed_on_fallback():
    with patch("llm.generator.call_llm", return_value=_mock_llm("", fallback=True)):
        result = generate_and_discover_strategy("RSI reversal")

    assert result["load_status"] == "generation_failed"
    assert result["code"] is None
