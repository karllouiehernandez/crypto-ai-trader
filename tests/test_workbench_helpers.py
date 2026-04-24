"""Tests for pure Jesse workbench helper functions."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from dashboard.workbench import (
    build_artifact_registry_frame,
    build_backtest_preset_frame,
    build_backtest_run_leaderboard,
    build_data_health_frame,
    build_live_freshness_frame,
    build_live_freshness_metrics,
    build_paper_evidence_checklist_frame,
    build_paper_evidence_metrics,
    build_restart_survival_frame,
    build_restart_survival_metrics,
    build_runtime_target_summary,
    build_trader_summary,
    build_strategy_comparison_frame,
    build_strategy_catalog_frame,
    build_trading_chart_payload,
    choose_backtest_default_symbol,
    choose_backtest_default_window,
    compute_win_loss_stats,
    compute_cumulative_trade_pnl,
    compute_drawdown_curve,
    compute_trade_equity_curve,
    find_matching_preset_name,
    filter_backtest_runs,
    filter_runtime_data,
    format_monitor_age,
    format_monitor_timestamp,
    format_params_summary,
    format_scenario_label,
    format_strategy_origin,
    get_strategy_source_code,
    list_rollback_candidates,
    list_runtime_strategies,
    latest_complete_backtest_day,
    normalise_preset_name,
    parse_metrics_json,
    parse_params_json,
    runtime_mode_table,
    summarise_data_health,
    strategy_workflow_status,
    strategy_sdk_compatibility,
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


def test_compute_win_loss_stats_empty_returns_zeros():
    stats = compute_win_loss_stats(pd.DataFrame())
    assert stats["win_count"] == 0 and stats["total_pairs"] == 0


def test_compute_win_loss_stats_one_win_one_loss():
    trades = pd.DataFrame(
        [
            {"side": "BUY", "price": 100.0, "qty": 1.0},
            {"side": "SELL", "price": 110.0, "qty": 1.0},
            {"side": "BUY", "price": 110.0, "qty": 1.0},
            {"side": "SELL", "price": 105.0, "qty": 1.0},
        ]
    )
    stats = compute_win_loss_stats(trades)
    assert stats["win_count"] == 1 and stats["loss_count"] == 1
    assert abs(stats["win_rate"] - 0.5) < 0.001


def test_build_trader_summary_labels():
    run = {
        "sharpe": 2.5,
        "profit_factor": 1.8,
        "max_drawdown": 0.04,
        "n_trades": 30,
        "gate_passed": True,
        "failures": "[]",
    }
    equity = pd.DataFrame({"equity": [100.0, 115.0]})
    summary = build_trader_summary(run, equity, starting_balance=100.0)
    assert summary["gain_pct"] == pytest.approx(15.0)
    assert summary["sharpe_label"] == "Excellent"
    assert summary["risk_label"] == "Low Risk"
    assert summary["gate_passed"] is True


def test_get_strategy_source_code_no_path_returns_placeholder():
    item = {"name": "builtin_test", "path": ""}
    source = get_strategy_source_code(item)
    assert "builtin_test" in source and "not available" in source


def test_build_restart_survival_metrics_and_frame():
    report = {
        "ready_for_restart": False,
        "artifact_count": 3,
        "auditable_run_count": 11,
        "saved_run_count": 12,
        "latest_saved_run_id": 44,
        "db_exists": True,
        "db_path": "D:/repo/data/market_data.db",
        "paper_target": {
            "configured": True,
            "valid": True,
            "name": "paper_v1",
            "error": None,
        },
        "live_target": {
            "configured": False,
            "valid": False,
            "name": None,
            "error": None,
        },
        "artifact_missing_count": 1,
        "artifact_hash_mismatch_count": 0,
        "mvp_symbols": [
            {
                "symbol": "BTCUSDT",
                "latest_candle_ts": "2026-04-22T00:00:00+00:00",
                "age_minutes": 2.0,
                "is_fresh": True,
            },
            {
                "symbol": "ETHUSDT",
                "latest_candle_ts": None,
                "age_minutes": None,
                "is_fresh": False,
            },
        ],
    }
    metrics = build_restart_survival_metrics(report)
    assert metrics["restart_status"] == "Issues Found"
    assert metrics["mvp_fresh_label"] == "1/2"
    assert metrics["artifact_count"] == 3
    assert metrics["auditable_runs"] == 11

    frame = build_restart_survival_frame(report)
    assert "Primary DB" in set(frame["surface"])
    assert "MVP Symbol · BTCUSDT" in set(frame["surface"])


def test_build_paper_evidence_metrics_and_checklist_frame():
    summary = {
        "gate_status": "Gathering evidence",
        "trade_count": 6,
        "trade_target": 20,
        "runtime_days": 1.5,
        "runtime_target_days": 3.0,
        "profit_factor": 1.25,
        "sharpe": 0.9,
        "min_sharpe": 1.5,
        "min_profit_factor": 1.5,
        "max_drawdown": 0.12,
        "max_drawdown_limit": 0.20,
    }
    metrics = build_paper_evidence_metrics(summary)
    assert metrics["gate_status"] == "Gathering evidence"
    assert metrics["trade_progress"] == "6/20"
    assert metrics["runtime_progress"] == "1.5/3.0d"
    assert metrics["profit_factor"] == "1.25"

    frame = build_paper_evidence_checklist_frame(summary)
    assert "SELL Trades" in set(frame["check"])
    assert "Profit Factor" in set(frame["check"])


def test_build_data_health_frame_formats_targeted_and_runnable_states():
    frame = build_data_health_frame(
        [
            {
                "symbol": "BTCUSDT",
                "latest_candle_ts": "2026-04-19T01:02:03+00:00",
                "age_minutes": 8,
                "is_fresh": True,
                "has_min_history": True,
                "latest_window_start": "2026-03-20",
                "latest_window_end": "2026-04-19",
                "window_runnable": True,
            },
            {
                "symbol": "XRPUSDT",
                "latest_candle_ts": None,
                "age_minutes": None,
                "is_fresh": False,
                "has_min_history": None,
                "latest_window_start": None,
                "latest_window_end": None,
                "window_runnable": None,
            },
        ]
    )
    assert frame.loc[0, "symbol"] == "BTCUSDT"
    assert frame.loc[0, "fresh"] == "Yes"
    assert frame.loc[0, "window_runnable"] == "Runnable"
    assert frame.loc[1, "history_30d"] == "Targeted"
    assert frame.loc[1, "window_runnable"] == "Not audited"


def test_summarise_data_health_flags_release_blockers():
    summary = summarise_data_health(
        [
            {
                "symbol": "BTCUSDT",
                "age_minutes": 5,
                "is_fresh": True,
                "has_min_history": True,
                "window_runnable": True,
            },
            {
                "symbol": "ETHUSDT",
                "age_minutes": 25,
                "is_fresh": False,
                "has_min_history": False,
                "window_runnable": False,
            },
        ],
        ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
        freshness_minutes=10,
    )
    assert summary["release_blocked"] is True
    assert summary["mvp_missing_symbols"] == ["BNBUSDT"]
    assert "ETHUSDT" in summary["mvp_stale_symbols"]
    assert "ETHUSDT" in summary["mvp_not_runnable_symbols"]


def test_summarise_data_health_passes_when_mvp_universe_is_ready():
    summary = summarise_data_health(
        [
            {
                "symbol": "BTCUSDT",
                "age_minutes": 2,
                "is_fresh": True,
                "has_min_history": True,
                "window_runnable": True,
            },
            {
                "symbol": "ETHUSDT",
                "age_minutes": 3,
                "is_fresh": True,
                "has_min_history": True,
                "window_runnable": True,
            },
            {
                "symbol": "BNBUSDT",
                "age_minutes": 4,
                "is_fresh": True,
                "has_min_history": True,
                "window_runnable": True,
            },
        ],
        ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
        freshness_minutes=10,
    )
    assert summary["release_blocked"] is False
    assert summary["mvp_runnable_count"] == 3


def test_choose_backtest_default_symbol_prefers_runnable_mvp_symbol():
    symbol_name = choose_backtest_default_symbol(
        "AAVEUSDT",
        ("BTCUSDT", "ETHUSDT", "AAVEUSDT"),
        [
            {"symbol": "BTCUSDT", "is_fresh": True, "window_runnable": True},
            {"symbol": "ETHUSDT", "is_fresh": True, "window_runnable": True},
            {"symbol": "AAVEUSDT", "is_fresh": False, "window_runnable": False},
        ],
        ("BTCUSDT", "ETHUSDT", "BNBUSDT"),
    )
    assert symbol_name == "BTCUSDT"


def test_choose_backtest_default_symbol_keeps_preferred_when_runnable():
    symbol_name = choose_backtest_default_symbol(
        "ETHUSDT",
        ("BTCUSDT", "ETHUSDT", "BNBUSDT"),
        [
            {"symbol": "BTCUSDT", "is_fresh": True, "window_runnable": True},
            {"symbol": "ETHUSDT", "is_fresh": True, "window_runnable": True},
        ],
        ("BTCUSDT", "ETHUSDT", "BNBUSDT"),
    )
    assert symbol_name == "ETHUSDT"


def test_choose_backtest_default_window_uses_known_runnable_window():
    start_date, end_date, is_known_runnable = choose_backtest_default_window(
        "BTCUSDT",
        datetime(2026, 4, 21, 8, 39),
        [
            {
                "symbol": "BTCUSDT",
                "window_runnable": True,
                "latest_window_start": "2026-03-22",
                "latest_window_end": "2026-04-21",
            }
        ],
        min_history_days=30,
    )
    assert (start_date.isoformat(), end_date.isoformat(), is_known_runnable) == ("2026-03-22", "2026-04-21", True)


def test_latest_complete_backtest_day_uses_prior_day_for_intraday_freshness():
    day = latest_complete_backtest_day(
        datetime(2026, 4, 21, 8, 39),
        now_utc=datetime(2026, 4, 21, 8, 40),
    )
    assert day.isoformat() == "2026-04-20"


def test_choose_backtest_default_window_falls_back_to_latest_completed_day():
    expected_end = latest_complete_backtest_day(datetime(2026, 4, 21, 8, 39))
    start_date, end_date, is_known_runnable = choose_backtest_default_window(
        "BTCUSDT",
        datetime(2026, 4, 21, 8, 39),
        [],
        min_history_days=30,
    )
    assert end_date == expected_end
    assert start_date == expected_end - timedelta(days=30)
    assert is_known_runnable is False


def test_compute_drawdown_curve_tracks_peak_to_trough():
    equity = pd.DataFrame({"step": [0, 1, 2], "equity": [100.0, 110.0, 99.0]})
    drawdown = compute_drawdown_curve(equity)
    assert drawdown["drawdown"].iloc[0] == 0.0
    assert drawdown["drawdown"].iloc[2] == (99.0 - 110.0) / 110.0


def test_parse_metrics_json_bad_input_returns_empty():
    assert parse_metrics_json("{not-json}") == {}
    assert parse_metrics_json(None) == {}


def test_parse_params_json_bad_input_returns_empty():
    assert parse_params_json("{not-json}") == {}
    assert parse_params_json(None) == {}


def test_normalise_preset_name_trims_input():
    assert normalise_preset_name("  Pullback A  ") == "Pullback A"
    assert normalise_preset_name(None) == ""


def test_format_params_summary_formats_default_and_values():
    assert format_params_summary({}) == "Default"
    assert "threshold=10" in format_params_summary({"threshold": 10, "enabled": True})


def test_format_scenario_label_prefers_preset_name():
    assert format_scenario_label({"threshold": 10}, "Pullback A") == "Pullback A"
    assert format_scenario_label({"threshold": 10}, "") == "threshold=10"


def test_format_strategy_origin_distinguishes_generated_plugins():
    assert format_strategy_origin({"provenance": "generated"}) == "Generated Plugin"
    assert format_strategy_origin({"source": "builtin"}) == "Built-in"


def test_build_strategy_catalog_frame_formats_origin_and_regimes():
    runs = pd.DataFrame([{"strategy_name": "generated_rsi_v1", "status": "passed"}])
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
        ],
        runs=runs,
        active_strategy_name="regime_router_v1",
    )
    assert frame.loc[0, "origin"] == "Generated Plugin"
    assert frame.loc[0, "workflow_stage"] == "Evaluated Draft"
    assert frame.loc[0, "sdk_version"] == "1"
    assert frame.loc[0, "sdk_compatibility"] == "Supported"
    assert frame.loc[0, "regimes"] == "RANGING"


def test_strategy_sdk_compatibility_marks_unsupported_version():
    status = strategy_sdk_compatibility({"sdk_version": "999"})
    assert status["compatible"] is False
    assert status["label"] == "Unsupported"


def test_strategy_workflow_status_marks_generated_without_runs_as_draft():
    status = strategy_workflow_status(
        {"name": "generated_rsi_v1", "provenance": "generated"},
        pd.DataFrame(),
        active_strategy_name="regime_router_v1",
    )
    assert status["stage"] == "Draft"
    assert status["run_count"] == 0


def test_strategy_workflow_status_marks_sdk_mismatch():
    status = strategy_workflow_status(
        {"name": "generated_rsi_v1", "provenance": "generated", "sdk_version": "999"},
        pd.DataFrame(),
        active_strategy_name="regime_router_v1",
    )
    assert status["stage"] == "SDK Mismatch"
    assert "unsupported SDK" in status["next_step"]


def test_strategy_workflow_status_marks_reviewed_plugin_with_passing_run():
    runs = pd.DataFrame([{"strategy_name": "ema_pullback_v1", "status": "passed"}])
    status = strategy_workflow_status(
        {"name": "ema_pullback_v1", "provenance": "plugin"},
        runs,
        active_strategy_name="regime_router_v1",
    )
    assert status["stage"] == "Reviewed Candidate"
    assert status["passed_runs"] == 1


def test_strategy_workflow_status_uses_artifact_lifecycle_flags():
    status = strategy_workflow_status(
        {
            "name": "reviewed_candidate_v1",
            "provenance": "plugin",
            "artifact_status": "paper_passed",
            "active_paper_artifact": True,
            "active_live_artifact": False,
        },
        pd.DataFrame(),
        active_strategy_name="regime_router_v1",
    )
    assert status["stage"] == "Paper Passed"
    assert status["active_paper_artifact"] is True


def test_build_strategy_catalog_frame_includes_runtime_target_columns():
    frame = build_strategy_catalog_frame(
        [
            {
                "name": "reviewed_candidate_v1",
                "display_name": "Reviewed Candidate",
                "provenance": "plugin",
                "version": "1.0.0",
                "regimes": ["TRENDING"],
                "artifact_id": 7,
                "artifact_status": "paper_active",
                "active_paper_artifact": True,
                "active_live_artifact": False,
                "file_name": "reviewed_candidate_v1.py",
                "load_status": "loaded",
                "modified_at": "2026-04-18T01:02:03+00:00",
            }
        ],
        runs=pd.DataFrame(),
        active_strategy_name="regime_router_v1",
    )
    assert frame.loc[0, "paper_target"] == "Yes"
    assert frame.loc[0, "artifact_status"] == "paper_active"


def test_filter_backtest_runs_filters_by_strategy_name():
    frame = pd.DataFrame(
        [
            {"strategy_name": "a", "id": 1},
            {"strategy_name": "b", "id": 2},
        ]
    )
    filtered = filter_backtest_runs(frame, "a")
    assert filtered["id"].tolist() == [1]


def test_build_strategy_comparison_frame_ranks_reviewed_candidate_first():
    runs = pd.DataFrame(
        [
            {
                "id": 11,
                "created_at": pd.Timestamp("2026-04-18 09:00:00"),
                "strategy_name": "candidate_a",
                "symbol": "BTCUSDT",
                "status": "passed",
                "params": {"rsi_buy_threshold": 30},
                "sharpe": 2.4,
                "profit_factor": 1.9,
                "max_drawdown": 0.11,
                "n_trades": 240,
            },
            {
                "id": 12,
                "created_at": pd.Timestamp("2026-04-18 08:00:00"),
                "strategy_name": "candidate_b",
                "symbol": "BTCUSDT",
                "status": "failed",
                "params": {"rsi_buy_threshold": 35},
                "sharpe": 0.8,
                "profit_factor": 1.2,
                "max_drawdown": 0.28,
                "n_trades": 180,
            },
        ]
    )
    catalog = [
        {"name": "candidate_a", "display_name": "Candidate A", "provenance": "plugin"},
        {"name": "candidate_b", "display_name": "Candidate B", "provenance": "generated"},
        {"name": "candidate_c", "display_name": "Candidate C", "provenance": "builtin"},
    ]

    frame = build_strategy_comparison_frame(runs, catalog=catalog, active_strategy_name="candidate_b")

    assert frame.iloc[0]["strategy_name"] == "candidate_a"
    assert frame.iloc[0]["rank"] == 1
    assert "rsi_buy_threshold=30" in frame.iloc[0]["scenario_label"]
    assert frame.loc[frame["strategy_name"] == "candidate_b", "is_active"].iloc[0]
    assert frame.loc[frame["strategy_name"] == "candidate_c", "latest_status"].iloc[0] == "Not Run"


def test_build_backtest_run_leaderboard_prioritizes_passed_runs():
    runs = pd.DataFrame(
        [
            {
                "id": 21,
                "created_at": pd.Timestamp("2026-04-18 09:00:00"),
                "strategy_name": "candidate_a",
                "symbol": "BTCUSDT",
                "status": "failed",
                "params": {"rsi_buy_threshold": 34},
                "sharpe": 3.0,
                "profit_factor": 2.0,
                "max_drawdown": 0.09,
                "n_trades": 210,
                "failures": ["Sharpe 1.0 < 1.5 (gate)"],
            },
            {
                "id": 22,
                "created_at": pd.Timestamp("2026-04-18 10:00:00"),
                "strategy_name": "candidate_a",
                "symbol": "BTCUSDT",
                "status": "passed",
                "params": {"rsi_buy_threshold": 28},
                "sharpe": 2.0,
                "profit_factor": 1.8,
                "max_drawdown": 0.12,
                "n_trades": 250,
                "failures": [],
            },
        ]
    )

    leaderboard = build_backtest_run_leaderboard(runs)

    assert leaderboard.iloc[0]["id"] == 22
    assert leaderboard.iloc[0]["rank"] == 1
    assert leaderboard.iloc[0]["status_label"] == "Passed"
    assert "rsi_buy_threshold=28" in leaderboard.iloc[0]["scenario_label"]
    assert "Sharpe" in leaderboard.iloc[1]["failure_summary"]


def test_build_backtest_run_leaderboard_uses_preset_name_when_present():
    runs = pd.DataFrame(
        [
            {
                "id": 31,
                "created_at": pd.Timestamp("2026-04-18 10:00:00"),
                "strategy_name": "mean_reversion_v1",
                "symbol": "BTCUSDT",
                "status": "passed",
                "preset_name": "Pullback A",
                "params": {"rsi_buy_threshold": 28},
                "sharpe": 2.0,
                "profit_factor": 1.8,
                "max_drawdown": 0.12,
                "n_trades": 250,
                "failures": [],
            },
        ]
    )

    leaderboard = build_backtest_run_leaderboard(runs)
    assert leaderboard.iloc[0]["scenario_label"] == "Pullback A"


def test_build_backtest_preset_frame_formats_summary_and_sorts():
    presets = pd.DataFrame(
        [
            {
                "preset_name": "Pullback B",
                "params": {"rsi_buy_threshold": 31},
                "created_at": pd.Timestamp("2026-04-18 09:00:00"),
                "updated_at": pd.Timestamp("2026-04-18 10:00:00"),
            },
            {
                "preset_name": "Pullback A",
                "params": {"rsi_buy_threshold": 28},
                "created_at": pd.Timestamp("2026-04-18 08:00:00"),
                "updated_at": pd.Timestamp("2026-04-18 11:00:00"),
            },
        ]
    )

    frame = build_backtest_preset_frame(presets)
    assert frame.iloc[0]["preset_name"] == "Pullback A"
    assert frame.iloc[0]["scenario_label"] == "Pullback A"
    assert "rsi_buy_threshold=28" in frame.iloc[0]["params_summary"]


def test_find_matching_preset_name_returns_exact_match():
    presets = pd.DataFrame(
        [
            {"preset_name": "Pullback A", "params": {"rsi_buy_threshold": 28}},
            {"preset_name": "Pullback B", "params": {"rsi_buy_threshold": 31}},
        ]
    )

    assert find_matching_preset_name({"rsi_buy_threshold": 31.0}, presets) == "Pullback B"
    assert find_matching_preset_name({"rsi_buy_threshold": 35}, presets) == ""


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


def test_build_trading_chart_payload_empty_candles_returns_empty_series():
    payload = build_trading_chart_payload(pd.DataFrame(), pd.DataFrame(), symbol="BTCUSDT", timeframe="1h")
    assert payload["candles"] == []
    assert payload["volume"] == []
    assert payload["markers"] == []
    assert payload["meta"]["symbol"] == "BTCUSDT"


def test_build_trading_chart_payload_without_trades_keeps_volume_and_no_markers():
    candles = pd.DataFrame(
        [
            {"open_time": pd.Timestamp("2026-04-18 00:00:00"), "open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0, "volume": 10.0},
            {"open_time": pd.Timestamp("2026-04-18 01:00:00"), "open": 104.0, "high": 106.0, "low": 102.0, "close": 103.0, "volume": 12.0},
        ]
    )

    payload = build_trading_chart_payload(candles, pd.DataFrame(), symbol="BTCUSDT", timeframe="1h")

    assert len(payload["candles"]) == 2
    assert len(payload["volume"]) == 2
    assert payload["markers"] == []
    assert payload["volume"][0]["color"] == "#26a69a"
    assert payload["volume"][1]["color"] == "#ef5350"


def test_build_trading_chart_payload_drops_trades_outside_visible_window():
    candles = pd.DataFrame(
        [
            {"open_time": pd.Timestamp("2026-04-18 10:00:00"), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 10.0},
            {"open_time": pd.Timestamp("2026-04-18 11:00:00"), "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.0, "volume": 12.0},
        ]
    )
    trades = pd.DataFrame(
        [
            {"ts": pd.Timestamp("2026-04-18 09:59:00"), "side": "BUY"},
            {"ts": pd.Timestamp("2026-04-18 12:00:00"), "side": "SELL"},
        ]
    )

    payload = build_trading_chart_payload(candles, trades, symbol="BTCUSDT", timeframe="1h")
    assert payload["markers"] == []


def test_build_trading_chart_payload_maps_mixed_markers_to_candle_buckets():
    candles = pd.DataFrame(
        [
            {"open_time": pd.Timestamp("2026-04-18 10:00:00"), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 10.0},
            {"open_time": pd.Timestamp("2026-04-18 11:00:00"), "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.0, "volume": 12.0},
        ]
    )
    trades = pd.DataFrame(
        [
            {"ts": pd.Timestamp("2026-04-18 10:20:00"), "side": "BUY"},
            {"ts": pd.Timestamp("2026-04-18 11:45:00"), "side": "SELL"},
        ]
    )

    payload = build_trading_chart_payload(candles, trades, symbol="BTCUSDT", timeframe="1h")

    assert [marker["text"] for marker in payload["markers"]] == ["", ""]
    assert payload["markers"][0]["position"] == "belowBar"
    assert payload["markers"][1]["position"] == "aboveBar"
    assert payload["markers"][0]["time"] == payload["candles"][0]["time"]
    assert payload["markers"][1]["time"] == payload["candles"][1]["time"]


def test_build_trading_chart_payload_aggregates_duplicate_markers_per_candle_side():
    candles = pd.DataFrame(
        [
            {"open_time": pd.Timestamp("2026-04-18 10:00:00"), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 10.0},
            {"open_time": pd.Timestamp("2026-04-18 11:00:00"), "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.0, "volume": 12.0},
        ]
    )
    trades = pd.DataFrame(
        [
            {"ts": pd.Timestamp("2026-04-18 10:05:00"), "side": "BUY", "run_mode": "paper"},
            {"ts": pd.Timestamp("2026-04-18 10:15:00"), "side": "BUY", "run_mode": "paper"},
            {"ts": pd.Timestamp("2026-04-18 10:20:00"), "side": "BUY", "run_mode": "live"},
            {"ts": pd.Timestamp("2026-04-18 11:10:00"), "side": "SELL", "run_mode": "paper"},
            {"ts": pd.Timestamp("2026-04-18 11:20:00"), "side": "SELL", "run_mode": "paper"},
        ]
    )

    payload = build_trading_chart_payload(candles, trades, symbol="BTCUSDT", timeframe="1h")

    assert len(payload["markers"]) == 2
    assert payload["markers"][0]["text"] == "L1/P2"
    assert payload["markers"][1]["text"] == "x2"


def test_build_trading_chart_payload_serializes_enabled_studies():
    candles = pd.DataFrame(
        [
            {
                "open_time": pd.Timestamp("2026-04-18 10:00:00"),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10.0,
                "ema_9": 100.1,
                "ema_21": 99.9,
                "ema_55": 99.5,
                "ema_200": 98.0,
                "bb_hi": 101.5,
                "bb_lo": 98.5,
                "rsi_14": 54.0,
                "macd": 0.35,
                "macd_s": 0.21,
            },
            {
                "open_time": pd.Timestamp("2026-04-18 11:00:00"),
                "open": 100.5,
                "high": 102.0,
                "low": 100.0,
                "close": 101.0,
                "volume": 12.0,
                "ema_9": 100.4,
                "ema_21": 100.0,
                "ema_55": 99.7,
                "ema_200": 98.1,
                "bb_hi": 101.9,
                "bb_lo": 98.9,
                "rsi_14": 58.0,
                "macd": 0.48,
                "macd_s": 0.31,
            },
        ]
    )

    payload = build_trading_chart_payload(
        candles,
        pd.DataFrame(),
        symbol="BTCUSDT",
        timeframe="1h",
        show_fast_emas=True,
        show_ema_200=True,
        show_bbands=True,
        show_rsi=True,
        show_macd=True,
    )

    price_labels = [overlay["label"] for overlay in payload["overlays"]["price"]]
    assert price_labels == ["EMA 9", "EMA 21", "EMA 55", "EMA 200", "BB High", "BB Low"]
    assert payload["overlays"]["rsi"]["series"][0]["label"] == "RSI 14"
    assert [band["label"] for band in payload["overlays"]["rsi"]["bands"]] == ["Overbought", "Midline", "Oversold"]
    assert [series["label"] for series in payload["overlays"]["macd"]["series"]] == ["MACD", "Signal"]
    assert round(payload["overlays"]["macd"]["histogram"][0]["value"], 2) == 0.14


# ── Sprint 34: Promotion Control Panel helpers ────────────────────────────────

def test_build_runtime_target_summary_both_none():
    summary = build_runtime_target_summary(None, None, None, None)
    assert summary["has_issues"] is True
    assert summary["paper"]["configured"] is False
    assert summary["live"]["configured"] is False
    assert summary["paper"]["valid"] is False
    assert summary["live"]["valid"] is False


def test_build_runtime_target_summary_paper_valid_live_error():
    paper = {"name": "ema_plugin", "version": "1.0.0", "status": "paper_active", "code_hash": "abc123", "id": 5}
    summary = build_runtime_target_summary(paper, None, None, "File missing")
    assert summary["has_issues"] is True
    assert summary["paper"]["valid"] is True
    assert summary["paper"]["name"] == "ema_plugin"
    assert summary["live"]["valid"] is False
    assert summary["live"]["error"] == "File missing"


def test_build_runtime_target_summary_both_valid():
    paper = {"name": "p", "version": "1.0.0", "status": "paper_active", "code_hash": "a" * 64, "id": 1}
    live = {"name": "l", "version": "1.0.0", "status": "live_active", "code_hash": "b" * 64, "id": 2}
    summary = build_runtime_target_summary(paper, live, None, None)
    assert summary["has_issues"] is False
    assert summary["paper"]["valid"] is True
    assert summary["live"]["valid"] is True
    assert summary["paper"]["code_hash_short"] == "a" * 12
    assert summary["live"]["code_hash_short"] == "b" * 12


def test_build_artifact_registry_frame_empty():
    frame = build_artifact_registry_frame([], pd.DataFrame())
    assert frame.empty


def test_build_artifact_registry_frame_maps_best_backtest():
    artifacts = [{"id": 1, "name": "ema_v1", "version": "1.0.0", "provenance": "plugin", "status": "backtest_passed", "code_hash": "abc", "created_at": None}]
    runs = pd.DataFrame([
        {"artifact_id": 1, "status": "passed", "sharpe": 1.8, "profit_factor": 1.5},
        {"artifact_id": 1, "status": "failed", "sharpe": 0.5, "profit_factor": 1.0},
    ])
    frame = build_artifact_registry_frame(artifacts, runs)
    assert len(frame) == 1
    assert frame.iloc[0]["best_bt_status"] == "passed"
    assert frame.iloc[0]["best_sharpe"] == 1.8


def test_list_rollback_candidates_paper_excludes_current():
    artifacts = [
        {"id": 1, "name": "a", "version": "1.0.0", "provenance": "plugin", "status": "backtest_passed"},
        {"id": 2, "name": "b", "version": "1.0.0", "provenance": "plugin", "status": "paper_passed"},
        {"id": 3, "name": "c", "version": "1.0.0", "provenance": "generated", "status": "backtest_passed"},
    ]
    candidates = list_rollback_candidates(artifacts, "paper", current_artifact_id=1)
    ids = [a["id"] for a in candidates]
    assert 1 not in ids
    assert 2 in ids
    assert 3 not in ids  # generated — not eligible


def test_list_rollback_candidates_live_requires_paper_passed():
    artifacts = [
        {"id": 1, "name": "a", "version": "1.0.0", "provenance": "plugin", "status": "backtest_passed"},
        {"id": 2, "name": "b", "version": "1.0.0", "provenance": "plugin", "status": "paper_passed"},
        {"id": 3, "name": "c", "version": "1.0.0", "provenance": "plugin", "status": "live_active"},
    ]
    candidates = list_rollback_candidates(artifacts, "live", current_artifact_id=3)
    ids = [a["id"] for a in candidates]
    assert 1 not in ids  # backtest_passed is not enough for live
    assert 2 in ids
    assert 3 not in ids  # excluded as current


def test_list_rollback_candidates_unknown_mode_returns_empty():
    artifacts = [{"id": 1, "name": "a", "version": "1.0.0", "provenance": "plugin", "status": "paper_passed"}]
    assert list_rollback_candidates(artifacts, "staging", None) == []


def test_build_live_freshness_frame_formats_candle_ages():
    frame = build_live_freshness_frame(
        [
            {"symbol": "BTCUSDT", "latest_candle_ts": "2026-04-25T00:00:00+00:00"},
            {"symbol": "ETHUSDT", "latest_candle_ts": None},
        ],
        freshness_minutes=10,
        now="2026-04-25T00:05:00+00:00",
    )

    assert list(frame["symbol"]) == ["BTCUSDT", "ETHUSDT"]
    assert frame.loc[0, "last_candle_ts"] == "2026-04-25 00:00:00 UTC"
    assert frame.loc[0, "candle_age_minutes"] == pytest.approx(5.0)
    assert frame.loc[0, "freshness"] == "Fresh"
    assert bool(frame.loc[0, "is_fresh"]) is True
    assert frame.loc[1, "freshness"] == "No candles"
    assert pd.isna(frame.loc[1, "candle_age_minutes"])


def test_build_live_freshness_metrics_formats_runtime_liveness_labels():
    freshness_frame = build_live_freshness_frame(
        [
            {"symbol": "BTCUSDT", "latest_candle_ts": "2026-04-25T00:00:00+00:00"},
            {"symbol": "ETHUSDT", "latest_candle_ts": "2026-04-24T23:30:00+00:00"},
        ],
        freshness_minutes=10,
        now="2026-04-25T00:05:00+00:00",
    )

    metrics = build_live_freshness_metrics(
        freshness_frame,
        worker_heartbeat_ts="2026-04-25T00:04:30+00:00",
        last_snapshot_ts="2026-04-25T00:04:00+00:00",
        last_trade_ts=None,
        now="2026-04-25T00:05:00+00:00",
    )

    assert metrics["heartbeat_value"] == "2026-04-25 00:04:30 UTC"
    assert metrics["heartbeat_delta"] == "<1 min old"
    assert metrics["snapshot_value"] == "2026-04-25 00:04:00 UTC"
    assert metrics["snapshot_delta"] == "1.0 min old"
    assert metrics["trade_value"] == "—"
    assert metrics["trade_delta"] == "No trades yet"
    assert metrics["fresh_symbols_value"] == "1/2"
    assert metrics["fresh_symbols_delta"] == "1 stale"


def test_format_monitor_helpers_return_empty_labels_when_missing():
    assert format_monitor_timestamp(None) == "—"
    assert format_monitor_age(None, empty_label="No heartbeat yet") == "No heartbeat yet"
