"""Unit tests for tools/ui_agent/data_checks.py — no live DB or browser needed."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from database.integrity import INVALID_METRICS_STATUS, LEGACY_INVALID_STATUS, MISSING_TRADES_STATUS
from tools.ui_agent.data_checks import (
    _check_backtest_equity,
    _check_backtest_metrics,
    _check_candle_continuity,
    _check_candle_freshness,
    _check_ohlcv_sanity,
    _check_position_sizing,
    _check_trade_log_integrity,
    _finite,
    _resolve_health_symbols,
)


# ── _finite ───────────────────────────────────────────────────────────────────

def test_finite_normal():
    assert _finite(1.5) is True
    assert _finite(0.0) is True


def test_finite_rejects_nan_inf_none():
    assert _finite(float("nan")) is False
    assert _finite(float("inf")) is False
    assert _finite(None) is False


def test_resolve_health_symbols_prefers_maintained_ready_overlap():
    result = _resolve_health_symbols(
        ["BTCUSDT", "ETHUSDT", "BNBUSDT", "AAVEUSDT"],
        ["ETHUSDT", "BNBUSDT", "XRPUSDT"],
    )
    assert result == ["ETHUSDT", "BNBUSDT"]


def test_resolve_health_symbols_falls_back_to_all_ready_symbols():
    result = _resolve_health_symbols(
        ["BTCUSDT", "ETHUSDT"],
        ["XRPUSDT", "SOLUSDT"],
    )
    assert result == ["BTCUSDT", "ETHUSDT"]


# ── candle freshness ──────────────────────────────────────────────────────────

def _mock_sess_scalar(value):
    sess = MagicMock()
    sess.execute.return_value.scalar.return_value = value
    return sess


def test_candle_freshness_pass():
    findings = []
    now = datetime.now(tz=timezone.utc)
    sess = _mock_sess_scalar(now - timedelta(minutes=1))
    _check_candle_freshness(sess, ["BTCUSDT"], findings, verbose=False)
    assert findings[0]["status"] == "PASS"


def test_candle_freshness_stale():
    findings = []
    old = datetime.now(tz=timezone.utc) - timedelta(minutes=30)
    sess = _mock_sess_scalar(old)
    _check_candle_freshness(sess, ["BTCUSDT"], findings, verbose=False)
    assert findings[0]["status"] == "PARTIAL"


def test_candle_freshness_no_data():
    findings = []
    sess = _mock_sess_scalar(None)
    _check_candle_freshness(sess, ["BTCUSDT"], findings, verbose=False)
    assert findings[0]["status"] == "FAIL"


# ── OHLCV sanity ──────────────────────────────────────────────────────────────

def _ohlcv_sess(rows):
    sess = MagicMock()
    sess.execute.return_value.all.return_value = rows
    return sess


def test_ohlcv_sanity_pass():
    findings = []
    rows = [(100.0, 105.0, 95.0, 102.0, 1000.0)] * 10
    sess = _ohlcv_sess(rows)
    _check_ohlcv_sanity(sess, ["BTCUSDT"], findings, verbose=False)
    assert findings[0]["status"] == "PASS"


def test_ohlcv_sanity_zero_price():
    findings = []
    rows = [(0.0, 105.0, 95.0, 102.0, 1000.0)]
    sess = _ohlcv_sess(rows)
    _check_ohlcv_sanity(sess, ["BTCUSDT"], findings, verbose=False)
    assert findings[0]["status"] == "FAIL"


def test_ohlcv_sanity_inverted():
    findings = []
    # high < low — inverted
    rows = [(100.0, 90.0, 95.0, 102.0, 1000.0)]
    sess = _ohlcv_sess(rows)
    _check_ohlcv_sanity(sess, ["BTCUSDT"], findings, verbose=False)
    assert findings[0]["status"] == "FAIL"


# ── candle continuity ─────────────────────────────────────────────────────────

def test_candle_continuity_no_gaps():
    findings = []
    now = datetime.now(tz=timezone.utc)
    times = [(now - timedelta(minutes=i),) for i in range(59, -1, -1)]
    sess = MagicMock()
    sess.execute.return_value.all.return_value = times
    _check_candle_continuity(sess, ["BTCUSDT"], findings, verbose=False)
    assert findings[0]["status"] == "PASS"


def test_candle_continuity_gap_detected():
    findings = []
    now = datetime.now(tz=timezone.utc)
    # 10-minute gap between minute 30 and 40
    times = (
        [(now - timedelta(minutes=i),) for i in range(59, 30, -1)]
        + [(now - timedelta(minutes=i),) for i in range(20, -1, -1)]
    )
    sess = MagicMock()
    sess.execute.return_value.all.return_value = times
    _check_candle_continuity(sess, ["BTCUSDT"], findings, verbose=False)
    assert findings[0]["status"] == "PARTIAL"


# ── trade log integrity ───────────────────────────────────────────────────────

def _trade_rows(*sides):
    now = datetime.now(tz=timezone.utc)
    return [("BTCUSDT", side, now, "valid", None) for side in sides]


def test_trade_log_clean():
    findings = []
    rows = _trade_rows("BUY", "SELL", "BUY", "SELL")
    sess = MagicMock()
    sess.execute.return_value.all.return_value = rows
    _check_trade_log_integrity(sess, findings, verbose=False)
    assert findings[0]["status"] == "PASS"


def test_trade_log_consecutive_buy():
    findings = []
    rows = _trade_rows("BUY", "BUY", "SELL")
    sess = MagicMock()
    sess.execute.return_value.all.return_value = rows
    _check_trade_log_integrity(sess, findings, verbose=False)
    assert findings[0]["status"] == "FAIL"


def test_trade_log_legacy_invalid_sequence_is_partial():
    findings = []
    now = datetime.now(tz=timezone.utc)
    rows = [
        ("BTCUSDT", "BUY", now, "valid", None),
        ("BTCUSDT", "BUY", now + timedelta(minutes=1), LEGACY_INVALID_STATUS, "legacy sequence"),
    ]
    sess = MagicMock()
    sess.execute.return_value.all.return_value = rows
    _check_trade_log_integrity(sess, findings, verbose=False)
    assert findings[0]["status"] == "PARTIAL"


def test_trade_log_empty():
    findings = []
    sess = MagicMock()
    sess.execute.return_value.all.return_value = []
    _check_trade_log_integrity(sess, findings, verbose=False)
    assert findings[0]["status"] == "SKIP"


# ── backtest metrics ──────────────────────────────────────────────────────────

def _bt_run(metrics: dict, *, integrity_status: str | None = None):
    r = MagicMock()
    r.id = 1
    r.metrics_json = json.dumps(metrics)
    r.integrity_status = integrity_status
    return r


def test_backtest_metrics_valid():
    findings = []
    sess = MagicMock()
    sess.execute.return_value.scalars.return_value.all.return_value = [
        _bt_run({"sharpe": 1.5, "n_trades": 42, "max_drawdown": 0.12})
    ]
    _check_backtest_metrics(sess, findings, verbose=False)
    assert findings[0]["status"] == "PASS"


def test_backtest_metrics_nan_sharpe():
    findings = []
    sess = MagicMock()
    sess.execute.return_value.scalars.return_value.all.return_value = [
        _bt_run({"sharpe": float("nan"), "n_trades": 10})
    ]
    _check_backtest_metrics(sess, findings, verbose=False)
    assert findings[0]["status"] == "FAIL"


def test_backtest_metrics_no_runs():
    findings = []
    sess = MagicMock()
    sess.execute.return_value.scalars.return_value.all.return_value = []
    _check_backtest_metrics(sess, findings, verbose=False)
    assert findings[0]["status"] == "SKIP"


def test_backtest_metrics_legacy_invalid_json_is_partial():
    findings = []
    run = MagicMock()
    run.id = 7
    run.metrics_json = "{bad-json}"
    run.integrity_status = INVALID_METRICS_STATUS
    sess = MagicMock()
    sess.execute.return_value.scalars.return_value.all.return_value = [run]
    _check_backtest_metrics(sess, findings, verbose=False)
    assert findings[0]["status"] == "PARTIAL"


# ── position sizing ───────────────────────────────────────────────────────────

def _trade_buy(price, qty):
    r = MagicMock()
    r.symbol = "BTCUSDT"
    r.price = price
    r.qty = qty
    r.side = "BUY"
    return r


def test_position_sizing_compliant():
    findings = []
    sess = MagicMock()
    # 0.10 * $100 = $10 max notional; trade is $5
    sess.execute.return_value.all.return_value = [("BTCUSDT", 50.0, 0.1, "BUY", "valid")]
    _check_position_sizing(sess, findings, verbose=False)
    assert findings[0]["status"] == "PASS"


def test_position_sizing_oversized():
    findings = []
    sess = MagicMock()
    # 0.10 * $100 = $10 max; trade is $500 (price=500, qty=1)
    sess.execute.return_value.all.return_value = [("BTCUSDT", 500.0, 1.0, "BUY", "valid")]
    _check_position_sizing(sess, findings, verbose=False)
    assert findings[0]["status"] == "FAIL"


def test_position_sizing_legacy_invalid_trade_is_partial():
    findings = []
    sess = MagicMock()
    sess.execute.return_value.all.return_value = [("BTCUSDT", 500.0, 1.0, "BUY", LEGACY_INVALID_STATUS)]
    _check_position_sizing(sess, findings, verbose=False)
    assert findings[0]["status"] == "PARTIAL"


def test_backtest_equity_missing_trade_rows_flagged_as_partial():
    findings = []
    run = MagicMock()
    run.id = 9
    run.metrics_json = json.dumps({"n_trades": 2})
    run.integrity_status = MISSING_TRADES_STATUS

    sess = MagicMock()
    exec_mock = sess.execute
    exec_mock.return_value.scalars.return_value.first.return_value = run
    exec_mock.return_value.all.return_value = []

    _check_backtest_equity(sess, findings, verbose=False)
    assert findings[0]["status"] == "PARTIAL"


def test_backtest_equity_zero_trade_run_without_rows_is_pass():
    findings = []
    run = MagicMock()
    run.id = 10
    run.metrics_json = json.dumps({"n_trades": 0})
    run.integrity_status = "valid"

    sess = MagicMock()
    exec_mock = sess.execute
    exec_mock.return_value.scalars.return_value.first.return_value = run
    exec_mock.return_value.all.return_value = []

    _check_backtest_equity(sess, findings, verbose=False)
    assert findings[0]["status"] == "PASS"
