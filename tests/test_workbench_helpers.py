"""Tests for pure Jesse workbench helper functions."""

from __future__ import annotations

import pandas as pd

from dashboard.workbench import (
    compute_drawdown_curve,
    compute_trade_equity_curve,
    filter_runtime_data,
    parse_metrics_json,
    runtime_summary,
)


def test_compute_trade_equity_curve_empty_returns_starting_balance():
    curve = compute_trade_equity_curve(pd.DataFrame(), starting_balance=100.0)
    assert list(curve["equity"]) == [100.0]


def test_compute_trade_equity_curve_buy_then_sell():
    trades = pd.DataFrame(
        [
            {"side": "BUY", "qty": 1.0, "price": 10.0},
            {"side": "SELL", "qty": 1.0, "price": 12.0},
        ]
    )
    curve = compute_trade_equity_curve(trades, starting_balance=100.0)
    assert list(curve["equity"]) == [100.0, 90.0, 102.0]


def test_compute_drawdown_curve_tracks_peak_to_trough():
    equity = pd.DataFrame({"step": [0, 1, 2], "equity": [100.0, 110.0, 99.0]})
    drawdown = compute_drawdown_curve(equity)
    assert drawdown["drawdown"].iloc[0] == 0.0
    assert drawdown["drawdown"].iloc[2] == (99.0 - 110.0) / 110.0


def test_parse_metrics_json_bad_input_returns_empty():
    assert parse_metrics_json("{not-json}") == {}
    assert parse_metrics_json(None) == {}


def test_filter_runtime_data_filters_strategy_and_mode():
    frame = pd.DataFrame(
        [
            {"strategy_name": "a", "run_mode": "paper", "value": 1},
            {"strategy_name": "a", "run_mode": "live", "value": 2},
            {"strategy_name": "b", "run_mode": "paper", "value": 3},
        ]
    )
    filtered = filter_runtime_data(frame, "a", "paper")
    assert filtered["value"].tolist() == [1]


def test_runtime_summary_extracts_latest_and_last_trade():
    trades = pd.DataFrame(
        [
            {"side": "BUY", "price": 100.0, "regime": "RANGING", "ts": pd.Timestamp("2026-01-01")},
            {"side": "SELL", "price": 110.0, "regime": "TRENDING", "ts": pd.Timestamp("2026-01-02")},
        ]
    )
    equity = pd.DataFrame(
        [
            {"equity": 100.0, "balance": 90.0, "unreal_pnl": 10.0},
            {"equity": 105.0, "balance": 95.0, "unreal_pnl": 10.0},
        ]
    )
    summary = runtime_summary(trades, equity, starting_balance=100.0)
    assert summary["equity"] == 105.0
    assert summary["trade_count"] == 2
    assert summary["last_trade_side"] == "SELL"
    assert summary["last_trade_regime"] == "TRENDING"
