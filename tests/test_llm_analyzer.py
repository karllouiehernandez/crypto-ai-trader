"""tests/test_llm_analyzer.py — Unit tests for llm/analyzer.py + llm/critiquer.py."""

import json
from unittest.mock import patch

import pytest

from llm.analyzer import analyze_backtest
from llm.cache import _default_cache
from llm.client import LLMResponse, reset_clients
from llm.critiquer import TradeVerdict, critique_trade

GOOD_METRICS = {
    "sharpe": 2.0,
    "max_drawdown": 0.10,
    "profit_factor": 2.5,
    "n_trades": 300.0,
}

FAILING_METRICS = {
    "sharpe": 0.5,
    "max_drawdown": 0.35,
    "profit_factor": 0.9,
    "n_trades": 50.0,
}

VALID_ANALYSIS_JSON = json.dumps({
    "parameter_suggestions": [
        {"param": "ADX_TREND_THRESHOLD", "current_value": 25,
         "suggested_value": 22, "rationale": "Lower threshold catches more trends"}
    ],
    "strategy_weaknesses": ["Underperforms in HIGH_VOL regime"],
    "confidence_score": 0.82,
    "recommendation": "PROMOTE_TO_LIVE",
})

VALID_CRITIQUE_JSON = json.dumps({
    "verdict": "GOOD",
    "reasoning": "Entry was at BB lower band with RSI oversold — textbook setup.",
    "improvement": "Could have held longer for a bigger move.",
})


@pytest.fixture(autouse=True)
def clean():
    _default_cache.clear()
    reset_clients()
    yield
    _default_cache.clear()


def _mock(content: str, fallback: bool = False):
    return LLMResponse(content=content, fallback=fallback)


# ── analyze_backtest — acceptance gate always present ─────────────────────

def test_analyze_includes_gate_passed_when_all_pass():
    with patch("llm.analyzer.call_llm", return_value=_mock(VALID_ANALYSIS_JSON)):
        result = analyze_backtest(GOOD_METRICS, [], "test_strategy")
    assert result["acceptance_gate_passed"] is True
    assert result["acceptance_gate_failures"] == []


def test_analyze_includes_gate_failures_when_failing():
    with patch("llm.analyzer.call_llm", return_value=_mock(VALID_ANALYSIS_JSON)):
        result = analyze_backtest(FAILING_METRICS, [], "test_strategy")
    assert result["acceptance_gate_passed"] is False
    assert len(result["acceptance_gate_failures"]) > 0


def test_analyze_returns_confidence_score():
    with patch("llm.analyzer.call_llm", return_value=_mock(VALID_ANALYSIS_JSON)):
        result = analyze_backtest(GOOD_METRICS, [], "test_strategy")
    assert result["confidence_score"] == pytest.approx(0.82)


def test_analyze_returns_recommendation():
    with patch("llm.analyzer.call_llm", return_value=_mock(VALID_ANALYSIS_JSON)):
        result = analyze_backtest(GOOD_METRICS, [], "test_strategy")
    assert result["recommendation"] == "PROMOTE_TO_LIVE"


def test_analyze_fallback_when_llm_unavailable():
    with patch("llm.analyzer.call_llm", return_value=_mock("", fallback=True)):
        result = analyze_backtest(GOOD_METRICS, [], "test_strategy")
    assert result["fallback"] is True
    assert result["recommendation"] == "HOLD_PAPER"
    assert result["acceptance_gate_passed"] is True   # gate still computed


def test_analyze_fallback_on_json_parse_error():
    with patch("llm.analyzer.call_llm", return_value=_mock("this is not json")):
        result = analyze_backtest(GOOD_METRICS, [], "test_strategy")
    assert result["fallback"] is True
    assert "raw_llm_output" in result


def test_analyze_handles_fenced_json():
    fenced = f"```json\n{VALID_ANALYSIS_JSON}\n```"
    with patch("llm.analyzer.call_llm", return_value=_mock(fenced)):
        result = analyze_backtest(GOOD_METRICS, [], "test_strategy")
    assert result["fallback"] is False
    assert result["confidence_score"] == pytest.approx(0.82)


def test_analyze_fallback_includes_gate_result():
    with patch("llm.analyzer.call_llm", return_value=_mock("", fallback=True)):
        result = analyze_backtest(FAILING_METRICS, [], "failing")
    assert "acceptance_gate_passed" in result
    assert result["acceptance_gate_passed"] is False


# ── critique_trade ────────────────────────────────────────────────────────

def test_critique_returns_good_verdict():
    with patch("llm.critiquer.call_llm", return_value=_mock(VALID_CRITIQUE_JSON)):
        verdict = critique_trade("BTCUSDT", "SELL", 50000, 51000, 2.0, "RANGING", {})
    assert verdict.verdict == "GOOD"
    assert verdict.fallback is False
    assert len(verdict.reasoning) > 0


def test_critique_fallback_profit_trade():
    with patch("llm.critiquer.call_llm", return_value=_mock("", fallback=True)):
        verdict = critique_trade("BTCUSDT", "SELL", 50000, 51000, 2.0, "RANGING", {})
    assert verdict.verdict == "GOOD"
    assert verdict.fallback is True


def test_critique_fallback_loss_trade():
    with patch("llm.critiquer.call_llm", return_value=_mock("", fallback=True)):
        verdict = critique_trade("BTCUSDT", "SELL", 50000, 49000, -2.0, "RANGING", {})
    assert verdict.verdict == "BAD"
    assert verdict.fallback is True


def test_critique_handles_invalid_verdict():
    bad_json = json.dumps({"verdict": "UNKNOWN", "reasoning": "x", "improvement": "y"})
    with patch("llm.critiquer.call_llm", return_value=_mock(bad_json)):
        verdict = critique_trade("ETHUSDT", "SELL", 3000, 3100, 3.3, "TRENDING", {})
    assert verdict.verdict == "MEDIOCRE"   # falls back to MEDIOCRE for unknown


def test_critique_handles_malformed_json():
    with patch("llm.critiquer.call_llm", return_value=_mock("not json at all")):
        verdict = critique_trade("BTCUSDT", "SELL", 50000, 51000, 2.0, "RANGING", {})
    assert verdict.fallback is True


def test_critique_handles_fenced_json():
    fenced = f"```json\n{VALID_CRITIQUE_JSON}\n```"
    with patch("llm.critiquer.call_llm", return_value=_mock(fenced)):
        verdict = critique_trade("BTCUSDT", "SELL", 50000, 51000, 2.0, "RANGING", {})
    assert verdict.verdict == "GOOD"
    assert verdict.fallback is False
