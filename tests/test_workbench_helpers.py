"""Tests for pure Jesse workbench helper functions."""

from __future__ import annotations

import pandas as pd

from dashboard.workbench import (
    build_strategy_catalog_frame,
    compute_cumulative_trade_pnl,
    compute_drawdown_curve,
    compute_trade_equity_curve,
    filter_backtest_runs,
    filter_runtime_data,
    format_strategy_origin,
    list_runtime_strategies,
    parse_metrics_json,
    runtime_mode_table,
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


def test_format_strategy_origin_distinguishes_generated_plugins():
    assert format_strategy_origin({"provenance": "generated"}) == "Generated Plugin"
    assert format_strategy_origin({"source": "builtin"}) == "Built-in"


def test_build_strategy_catalog_frame_formats_origin_and_regimes():
    frame = build_strategy_catalog_frame(
        [
            {
                "name": "generated_rsi_v1",
                "display_name": "Generated RSI",
                "provenance": "generated",
                "version": "1.0.0",
                "regimes": ["RANGING"],
                "file_name": "generated_20260417_010203.py",
                "load_status": "loaded",
                "modified_at": "2026-04-17T01:02:03+00:00",
            }
        ]
    )
    assert frame.loc[0, "origin"] == "Generated Plugin"
    assert frame.loc[0, "regimes"] == "RANGING"


def test_filter_backtest_runs_filters_by_strategy_name():
    frame = pd.DataFrame(
        [
            {"strategy_name": "a", "id": 1},
            {"strategy_name": "b", "id": 2},
        ]
    )
    filtered = filter_backtest_runs(frame, "a")
    assert filtered["id"].tolist() == [1]


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


def test_list_runtime_strategies_keeps_active_first():
    trades = pd.DataFrame([{"strategy_name": "older_strategy_v1"}])
    equity = pd.DataFrame([{"strategy_name": "regime_router_v1"}])
    names = list_runtime_strategies(trades, equity, "regime_router_v1")
    assert names[0] == "regime_router_v1"
    assert "older_strategy_v1" in names


def test_runtime_mode_table_summarises_each_mode():
    trades = pd.DataFrame(
        [
            {"run_mode": "paper", "side": "BUY", "price": 100.0, "pnl": 0.0, "regime": "RANGING", "ts": pd.Timestamp("2026-01-01"), "strategy_version": "1.0.0"},
            {"run_mode": "live", "side": "SELL", "price": 110.0, "pnl": 5.0, "regime": "TRENDING", "ts": pd.Timestamp("2026-01-02"), "strategy_version": "1.1.0"},
        ]
    )
    equity = pd.DataFrame(
        [
            {"run_mode": "paper", "equity": 101.0, "balance": 90.0, "unreal_pnl": 11.0, "ts": pd.Timestamp("2026-01-01"), "strategy_version": "1.0.0"},
            {"run_mode": "live", "equity": 106.0, "balance": 96.0, "unreal_pnl": 10.0, "ts": pd.Timestamp("2026-01-02"), "strategy_version": "1.1.0"},
        ]
    )
    table = runtime_mode_table(trades, equity, starting_balance=100.0)
    assert set(table["run_mode"]) == {"paper", "live"}
    live_row = table[table["run_mode"] == "live"].iloc[0]
    assert live_row["realized_pnl"] == 5.0
    assert live_row["strategy_version"] == "1.1.0"


def test_compute_cumulative_trade_pnl_groups_by_mode():
    trades = pd.DataFrame(
        [
            {"run_mode": "paper", "ts": pd.Timestamp("2026-01-01"), "pnl": 1.5},
            {"run_mode": "paper", "ts": pd.Timestamp("2026-01-02"), "pnl": -0.5},
            {"run_mode": "live", "ts": pd.Timestamp("2026-01-03"), "pnl": 3.0},
        ]
    )
    curve = compute_cumulative_trade_pnl(trades)
    assert curve[curve["run_mode"] == "paper"]["cumulative_pnl"].tolist() == [1.5, 1.0]
    assert curve[curve["run_mode"] == "live"]["cumulative_pnl"].tolist() == [3.0]


def test_runtime_summary_extracts_latest_and_last_trade():
    trades = pd.DataFrame(
        [
            {"side": "BUY", "price": 100.0, "regime": "RANGING", "ts": pd.Timestamp("2026-01-01"), "pnl": 0.0},
            {"side": "SELL", "price": 110.0, "regime": "TRENDING", "ts": pd.Timestamp("2026-01-02"), "pnl": 5.0},
        ]
    )
    equity = pd.DataFrame(
        [
            {"equity": 100.0, "balance": 90.0, "unreal_pnl": 10.0, "ts": pd.Timestamp("2026-01-01")},
            {"equity": 105.0, "balance": 95.0, "unreal_pnl": 10.0, "ts": pd.Timestamp("2026-01-02")},
        ]
    )
    summary = runtime_summary(trades, equity, starting_balance=100.0)
    assert summary["equity"] == 105.0
    assert summary["trade_count"] == 2
    assert summary["last_trade_side"] == "SELL"
    assert summary["last_trade_regime"] == "TRENDING"
    assert summary["realized_pnl"] == 5.0
    assert summary["last_snapshot_ts"] == pd.Timestamp("2026-01-02")
