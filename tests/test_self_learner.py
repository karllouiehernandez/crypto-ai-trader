"""tests/test_self_learner.py — Unit tests for llm/self_learner.py"""
import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── _metrics_from_pnls (pure, no I/O) ─────────────────────────────────────────

def test_metrics_from_pnls_positive_pnls():
    from llm.self_learner import _metrics_from_pnls
    pnls = [10.0, 20.0, 15.0, 5.0, 12.0]
    m = _metrics_from_pnls(pnls, starting_equity=1000.0)
    assert m["sharpe"] > 0
    assert m["max_drawdown"] == 0.0        # all positive — no drawdown
    assert m["profit_factor"] == 99.0      # no losses → capped inf
    assert int(m["n_trades"]) == 5


def test_metrics_from_pnls_mixed():
    from llm.self_learner import _metrics_from_pnls
    pnls = [10.0, -5.0, 8.0, -3.0, 12.0]
    m = _metrics_from_pnls(pnls, starting_equity=1000.0)
    assert m["profit_factor"] == pytest.approx(30.0 / 8.0, rel=1e-3)
    assert m["max_drawdown"] > 0
    assert int(m["n_trades"]) == 5


def test_metrics_from_pnls_empty():
    from llm.self_learner import _metrics_from_pnls, _zero_metrics
    assert _metrics_from_pnls([], 1000.0) == _zero_metrics()


def test_zero_metrics_structure():
    from llm.self_learner import _zero_metrics
    zm = _zero_metrics()
    assert set(zm.keys()) == {"sharpe", "max_drawdown", "profit_factor", "n_trades"}
    assert all(v == 0.0 for v in zm.values())


# ── SelfLearner unit tests (mocked DB + LLM) ──────────────────────────────────

def _make_learner():
    from llm.self_learner import SelfLearner
    return SelfLearner(interval_hours=24)


def _mock_analysis(recommendation="HOLD_PAPER", confidence=0.5):
    return {
        "parameter_suggestions": [],
        "strategy_weaknesses":   [],
        "confidence_score":      confidence,
        "recommendation":        recommendation,
        "acceptance_gate_passed": False,
        "acceptance_gate_failures": [],
        "fallback": True,
    }


def test_consecutive_promotes_empty():
    sl = _make_learner()
    assert sl._consecutive_promotes() == 0


def test_consecutive_promotes_counts_from_end():
    sl = _make_learner()
    sl._history = ["HOLD_PAPER", "PROMOTE_TO_LIVE", "PROMOTE_TO_LIVE"]
    assert sl._consecutive_promotes() == 2


def test_consecutive_promotes_resets_on_non_promote():
    sl = _make_learner()
    sl._history = ["PROMOTE_TO_LIVE", "HOLD_PAPER", "PROMOTE_TO_LIVE"]
    assert sl._consecutive_promotes() == 1


def test_confidence_gate_passed_needs_three():
    sl = _make_learner()
    sl._history = ["PROMOTE_TO_LIVE", "PROMOTE_TO_LIVE"]
    assert sl.confidence_gate_passed() is False
    sl._history.append("PROMOTE_TO_LIVE")
    assert sl.confidence_gate_passed() is True


def test_evaluate_writes_kb_entry(tmp_path):
    """evaluate() must append an entry to experiment_log.md."""
    exp_log = tmp_path / "experiment_log.md"

    sl = _make_learner()

    fake_trades = []  # no trades → zero metrics

    with (
        patch("llm.self_learner._EXPERIMENT_LOG", exp_log),
        patch("llm.self_learner._KB_DIR", tmp_path),
        patch("llm.self_learner.SessionLocal") as mock_session,
        patch("llm.self_learner.analyze_backtest", return_value=_mock_analysis()),
    ):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__  = MagicMock(return_value=False)
        mock_ctx.query.return_value.filter.return_value.order_by.return_value.all.return_value = fake_trades
        mock_session.return_value = mock_ctx

        result = asyncio.run(sl.evaluate())

    assert exp_log.exists(), "experiment_log.md should have been created"
    content = exp_log.read_text(encoding="utf-8")
    assert "EXP-AUTO-0001" in content
    assert "Self-Learning Evaluation #1" in content


def test_evaluate_returns_gate_fields(tmp_path):
    exp_log = tmp_path / "experiment_log.md"

    sl = _make_learner()

    with (
        patch("llm.self_learner._EXPERIMENT_LOG", exp_log),
        patch("llm.self_learner._KB_DIR", tmp_path),
        patch("llm.self_learner.SessionLocal") as mock_session,
        patch("llm.self_learner.analyze_backtest", return_value=_mock_analysis()),
    ):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__  = MagicMock(return_value=False)
        mock_ctx.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_session.return_value = mock_ctx

        result = asyncio.run(sl.evaluate())

    assert "gate_passed" in result
    assert "gate_failures" in result
    assert "consecutive_promotes" in result
    assert "paper_metrics" in result


def test_evaluate_falls_back_when_llm_unavailable(tmp_path):
    """When analyze_backtest returns fallback=True the learner must still complete."""
    exp_log = tmp_path / "experiment_log.md"
    sl = _make_learner()

    fallback_analysis = {**_mock_analysis(), "fallback": True}

    with (
        patch("llm.self_learner._EXPERIMENT_LOG", exp_log),
        patch("llm.self_learner._KB_DIR", tmp_path),
        patch("llm.self_learner.SessionLocal") as mock_session,
        patch("llm.self_learner.analyze_backtest", return_value=fallback_analysis),
    ):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__  = MagicMock(return_value=False)
        mock_ctx.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_session.return_value = mock_ctx

        result = asyncio.run(sl.evaluate())

    assert result["fallback"] is True
    content = exp_log.read_text(encoding="utf-8")
    assert "LLM unavailable" in content


def test_three_consecutive_evals_pass_confidence_gate(tmp_path):
    """After 3 evaluations all returning PROMOTE_TO_LIVE the gate flips to True."""
    exp_log = tmp_path / "experiment_log.md"
    sl = _make_learner()

    good_metrics = {"sharpe": 2.0, "max_drawdown": 0.10, "profit_factor": 2.0}
    good_analysis = {
        **_mock_analysis("PROMOTE_TO_LIVE", confidence=0.95),
        "acceptance_gate_passed": True,
        "acceptance_gate_failures": [],
    }

    with (
        patch("llm.self_learner._EXPERIMENT_LOG", exp_log),
        patch("llm.self_learner._KB_DIR", tmp_path),
        patch("llm.self_learner.SessionLocal") as mock_session,
        patch("llm.self_learner.analyze_backtest", return_value=good_analysis),
        patch("llm.self_learner._metrics_from_pnls", return_value=good_metrics),
    ):
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__  = MagicMock(return_value=False)
        # Return one fake trade so the DB path is exercised
        fake_trade = MagicMock()
        fake_trade.pnl = 50.0
        mock_ctx.query.return_value.filter.return_value.order_by.return_value.all.return_value = [fake_trade]
        mock_session.return_value = mock_ctx

        assert sl.confidence_gate_passed() is False
        asyncio.run(sl.evaluate())
        assert sl.confidence_gate_passed() is False
        asyncio.run(sl.evaluate())
        assert sl.confidence_gate_passed() is False
        asyncio.run(sl.evaluate())
        assert sl.confidence_gate_passed() is True
