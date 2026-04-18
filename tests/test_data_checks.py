"""Unit tests for tools/ui_agent/data_checks.py — no live DB or browser needed."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from tools.ui_agent.data_checks import (
    _check_backtest_equity,
    _check_backtest_metrics,
    _check_candle_continuity,
    _check_candle_freshness,
    _check_ohlcv_sanity,
    _check_position_sizing,
    _check_trade_log_integrity,
    _finite,
)


# ── _finite ───────────────────────────────────────────────────────────────────

def test_finite_normal():
    assert _finite(1.5) is True
    assert _finite(0.0) is True


def test_finite_rejects_nan_inf_none():
    assert _finite(float("nan")) is False
    assert _finite(float("inf")) is False
    assert _finite(None) is False


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
    return [("BTCUSDT", side, now) for side in sides]


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


def test_trade_log_empty():
    findings = []
    sess = MagicMock()
    sess.execute.return_value.all.return_value = []
    _check_trade_log_integrity(sess, findings, verbose=False)
    assert findings[0]["status"] == "SKIP"


# ── backtest metrics ──────────────────────────────────────────────────────────

def _bt_run(metrics: dict):
    r = MagicMock()
    r.id = 1
    r.metrics_json = json.dumps(metrics)
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
    sess.execute.return_value.all.return_value = [("BTCUSDT", 50.0, 0.1, "BUY")]
    _check_position_sizing(sess, findings, verbose=False)
    assert findings[0]["status"] == "PASS"


def test_position_sizing_oversized():
    findings = []
    sess = MagicMock()
    # 0.10 * $100 = $10 max; trade is $500 (price=500, qty=1)
    sess.execute.return_value.all.return_value = [("BTCUSDT", 500.0, 1.0, "BUY")]
    _check_position_sizing(sess, findings, verbose=False)
    assert findings[0]["status"] == "FAIL"
