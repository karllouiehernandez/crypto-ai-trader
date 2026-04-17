"""tests/test_confidence_gate.py — Unit tests for llm/confidence_gate.py"""
import pytest
from unittest.mock import patch

# ── Helpers ────────────────────────────────────────────────────────────────────
_GOOD_METRICS = {"sharpe": 2.0, "max_drawdown": 0.10, "profit_factor": 2.0}
_PROMOTE = "PROMOTE_TO_LIVE"
_TRAILING_OK = [_PROMOTE, _PROMOTE, _PROMOTE]


def _import():
    from llm.confidence_gate import evaluate_gate, GateResult
    return evaluate_gate, GateResult


# ── Gate 1: Sharpe ─────────────────────────────────────────────────────────────

def test_sharpe_gate_passes():
    evaluate_gate, GateResult = _import()
    result = evaluate_gate(
        metrics=_GOOD_METRICS,
        llm_confidence=0.90,
        trailing_recommendations=_TRAILING_OK,
    )
    assert result.sharpe_ok is True


def test_sharpe_gate_fails_below_threshold():
    evaluate_gate, _ = _import()
    metrics = {**_GOOD_METRICS, "sharpe": 0.5}
    result = evaluate_gate(metrics, 0.90, _TRAILING_OK)
    assert result.sharpe_ok is False
    assert result.passed is False
    assert any("sharpe" in f for f in result.failures)


def test_sharpe_gate_exactly_at_threshold():
    """Sharpe exactly equal to SHARPE_GATE (1.5) must pass."""
    evaluate_gate, _ = _import()
    from config import SHARPE_GATE
    metrics = {**_GOOD_METRICS, "sharpe": SHARPE_GATE}
    result = evaluate_gate(metrics, 0.90, _TRAILING_OK)
    assert result.sharpe_ok is True


# ── Gate 2: Max drawdown ───────────────────────────────────────────────────────

def test_max_dd_gate_passes():
    evaluate_gate, _ = _import()
    result = evaluate_gate(_GOOD_METRICS, 0.90, _TRAILING_OK)
    assert result.max_dd_ok is True


def test_max_dd_gate_fails_above_limit():
    evaluate_gate, _ = _import()
    metrics = {**_GOOD_METRICS, "max_drawdown": 0.25}
    result = evaluate_gate(metrics, 0.90, _TRAILING_OK)
    assert result.max_dd_ok is False
    assert result.passed is False
    assert any("max_drawdown" in f for f in result.failures)


def test_max_dd_gate_exactly_at_limit():
    """Drawdown exactly equal to MAX_DD_GATE (0.20) must pass."""
    evaluate_gate, _ = _import()
    from config import MAX_DD_GATE
    metrics = {**_GOOD_METRICS, "max_drawdown": MAX_DD_GATE}
    result = evaluate_gate(metrics, 0.90, _TRAILING_OK)
    assert result.max_dd_ok is True


# ── Gate 3: Profit factor ──────────────────────────────────────────────────────

def test_profit_factor_gate_passes():
    evaluate_gate, _ = _import()
    result = evaluate_gate(_GOOD_METRICS, 0.90, _TRAILING_OK)
    assert result.profit_factor_ok is True


def test_profit_factor_gate_fails():
    evaluate_gate, _ = _import()
    metrics = {**_GOOD_METRICS, "profit_factor": 0.8}
    result = evaluate_gate(metrics, 0.90, _TRAILING_OK)
    assert result.profit_factor_ok is False
    assert result.passed is False
    assert any("profit_factor" in f for f in result.failures)


# ── Gate 4: LLM confidence ─────────────────────────────────────────────────────

def test_llm_confidence_gate_passes():
    evaluate_gate, _ = _import()
    result = evaluate_gate(_GOOD_METRICS, 0.90, _TRAILING_OK)
    assert result.llm_confidence_ok is True


def test_llm_confidence_gate_fails():
    evaluate_gate, _ = _import()
    result = evaluate_gate(_GOOD_METRICS, 0.50, _TRAILING_OK)
    assert result.llm_confidence_ok is False
    assert result.passed is False
    assert any("llm_confidence" in f for f in result.failures)


def test_llm_confidence_exactly_at_threshold():
    evaluate_gate, _ = _import()
    from config import LLM_CONFIDENCE_GATE
    result = evaluate_gate(_GOOD_METRICS, LLM_CONFIDENCE_GATE, _TRAILING_OK)
    assert result.llm_confidence_ok is True


# ── Gate 5: Trend (consecutive PROMOTE_TO_LIVE) ────────────────────────────────

def test_trend_gate_passes_with_three_promotes():
    evaluate_gate, _ = _import()
    result = evaluate_gate(_GOOD_METRICS, 0.90, _TRAILING_OK)
    assert result.trend_ok is True


def test_trend_gate_fails_with_only_two_promotes():
    evaluate_gate, _ = _import()
    result = evaluate_gate(_GOOD_METRICS, 0.90, [_PROMOTE, _PROMOTE])
    assert result.trend_ok is False
    assert result.passed is False


def test_trend_gate_fails_when_third_not_promote():
    evaluate_gate, _ = _import()
    result = evaluate_gate(_GOOD_METRICS, 0.90, [_PROMOTE, _PROMOTE, "HOLD_PAPER"])
    assert result.trend_ok is False


def test_trend_gate_uses_only_last_three():
    """Even 10 entries is fine as long as the last 3 are all PROMOTE_TO_LIVE."""
    evaluate_gate, _ = _import()
    trailing = ["HOLD_PAPER"] * 7 + _TRAILING_OK
    result = evaluate_gate(_GOOD_METRICS, 0.90, trailing)
    assert result.trend_ok is True


def test_trend_gate_empty_history_fails():
    evaluate_gate, _ = _import()
    result = evaluate_gate(_GOOD_METRICS, 0.90, [])
    assert result.trend_ok is False


# ── All gates together ─────────────────────────────────────────────────────────

def test_all_gates_pass_returns_passed_true():
    evaluate_gate, _ = _import()
    result = evaluate_gate(_GOOD_METRICS, 0.90, _TRAILING_OK)
    assert result.passed is True
    assert result.failures == []


def test_single_gate_failure_blocks_promotion():
    """Any one failure must set passed=False regardless of the others."""
    evaluate_gate, _ = _import()
    # Only sharpe fails
    metrics = {**_GOOD_METRICS, "sharpe": 0.1}
    result = evaluate_gate(metrics, 0.90, _TRAILING_OK)
    assert result.passed is False
    assert len(result.failures) >= 1


def test_multiple_failures_all_reported():
    """All failing gates should appear in the failures list."""
    evaluate_gate, _ = _import()
    bad_metrics = {"sharpe": 0.1, "max_drawdown": 0.50, "profit_factor": 0.5}
    result = evaluate_gate(bad_metrics, 0.10, [])
    assert result.passed is False
    assert len(result.failures) >= 4  # sharpe, dd, pf, llm_conf, trend
