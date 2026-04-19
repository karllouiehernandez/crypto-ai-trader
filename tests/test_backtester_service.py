"""Tests for persisted backtest service helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd

from backtester.service import (
    get_backtest_run,
    list_backtest_presets,
    list_backtest_runs,
    run_and_persist_backtest,
    save_backtest_preset,
)
from database.models import BacktestRun, BacktestTrade, SessionLocal, init_db


def test_list_backtest_runs_respects_limit():
    init_db()
    with SessionLocal() as sess:
        sess.add(
            BacktestRun(
                symbol="BTCUSDT",
                start_ts=datetime(2024, 2, 1, tzinfo=timezone.utc),
                end_ts=datetime(2024, 2, 2, tzinfo=timezone.utc),
                strategy_name="regime_router_v1",
                strategy_version="1.0.0",
                params_json="{}",
                metrics_json=json.dumps({"sharpe": 1.0}),
                status="passed",
            )
        )
        sess.add(
            BacktestRun(
                symbol="ETHUSDT",
                start_ts=datetime(2024, 3, 1, tzinfo=timezone.utc),
                end_ts=datetime(2024, 3, 2, tzinfo=timezone.utc),
                strategy_name="momentum_v1",
                strategy_version="1.0.0",
                params_json="{}",
                metrics_json=json.dumps({"sharpe": 2.0}),
                status="passed",
            )
        )
        sess.commit()

    runs = list_backtest_runs(limit=1)
    assert len(runs) == 1


def test_get_backtest_run_parses_metrics_json(monkeypatch, tmp_path):
    # Use the project DB/session setup but insert an isolated row and read it back.
    init_db()
    with SessionLocal() as sess:
        run = BacktestRun(
            symbol="BTCUSDT",
            start_ts=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_ts=datetime(2024, 1, 2, tzinfo=timezone.utc),
            strategy_name="regime_router_v1",
            strategy_version="1.0.0",
            params_json=json.dumps({"rsi_buy_threshold": 30}),
            metrics_json=json.dumps({"sharpe": 1.23, "passed": True}),
            status="passed",
        )
        sess.add(run)
        sess.commit()
        run_id = run.id

    loaded = get_backtest_run(run_id)
    assert loaded is not None
    assert loaded["strategy_name"] == "regime_router_v1"
    assert loaded["params"] == {"rsi_buy_threshold": 30}
    assert loaded["sharpe"] == 1.23
    assert loaded["passed"] is True


def test_list_backtest_runs_handles_invalid_metrics_json():
    init_db()
    with SessionLocal() as sess:
        run = BacktestRun(
            symbol="ETHUSDT",
            start_ts=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_ts=datetime(2024, 1, 2, tzinfo=timezone.utc),
            strategy_name="regime_router_v1",
            strategy_version="1.0.0",
            params_json="{}",
            metrics_json="{bad-json}",
            status="failed",
        )
        sess.add(run)
        sess.commit()

    runs = list_backtest_runs(limit=5)
    assert not runs.empty
    match = runs[runs["id"] == run.id].iloc[0]
    assert match["integrity_status"] == "invalid-metrics"


def test_list_backtest_runs_exposes_params_dict():
    init_db()
    with SessionLocal() as sess:
        run = BacktestRun(
            symbol="BTCUSDT",
            start_ts=datetime(2024, 4, 1, tzinfo=timezone.utc),
            end_ts=datetime(2024, 4, 2, tzinfo=timezone.utc),
            strategy_name="mean_reversion_v1",
            strategy_version="1.0.0",
            params_json=json.dumps({"rsi_buy_threshold": 28, "volume_confirmation_mult": 1.7}),
            metrics_json=json.dumps({"sharpe": 1.5}),
            status="passed",
        )
        sess.add(run)
        sess.commit()

    runs = list_backtest_runs(limit=20)
    match = runs[runs["id"] == run.id].iloc[0]
    assert match["params"]["rsi_buy_threshold"] == 28


def test_run_and_persist_backtest_saves_params_payload():
    init_db()
    trades = pd.DataFrame(
        [
            {
                "time": datetime(2024, 4, 1, tzinfo=timezone.utc),
                "side": "BUY",
                "qty": 1.0,
                "price": 100.0,
                "regime": "RANGING",
                "strategy_name": "mean_reversion_v1",
                "strategy_version": "1.0.0",
            }
        ]
    )
    with patch("backtester.service.run_backtest", return_value=trades), \
         patch("backtester.service.build_equity_curve", return_value=pd.Series([100.0, 101.0])), \
         patch("backtester.service.compute_metrics", return_value={"sharpe": 1.2, "max_drawdown": 0.1, "profit_factor": 1.8, "n_trades": 1.0}), \
         patch("backtester.service.acceptance_gate", return_value=(True, [])):
        result = run_and_persist_backtest(
            "BTCUSDT",
            datetime(2024, 4, 1, tzinfo=timezone.utc),
            datetime(2024, 4, 2, tzinfo=timezone.utc),
            "mean_reversion_v1",
            params={"rsi_buy_threshold": 28},
        )

    loaded = get_backtest_run(result["run_id"])
    assert loaded is not None
    assert loaded["params"] == {"rsi_buy_threshold": 28}
    assert loaded["integrity_status"] == "valid"


def test_run_and_persist_backtest_saves_preset_name():
    init_db()
    trades = pd.DataFrame(
        [
            {
                "time": datetime(2024, 4, 1, tzinfo=timezone.utc),
                "side": "BUY",
                "qty": 1.0,
                "price": 100.0,
                "regime": "RANGING",
                "strategy_name": "mean_reversion_v1",
                "strategy_version": "1.0.0",
            }
        ]
    )
    with patch("backtester.service.run_backtest", return_value=trades), \
         patch("backtester.service.build_equity_curve", return_value=pd.Series([100.0, 101.0])), \
         patch("backtester.service.compute_metrics", return_value={"sharpe": 1.2, "max_drawdown": 0.1, "profit_factor": 1.8, "n_trades": 1.0}), \
         patch("backtester.service.acceptance_gate", return_value=(True, [])):
        result = run_and_persist_backtest(
            "BTCUSDT",
            datetime(2024, 4, 1, tzinfo=timezone.utc),
            datetime(2024, 4, 2, tzinfo=timezone.utc),
            "mean_reversion_v1",
            params={"rsi_buy_threshold": 28},
            preset_name="Pullback A",
        )

    loaded = get_backtest_run(result["run_id"])
    assert loaded is not None
    assert loaded["preset_name"] == "Pullback A"


def test_run_and_persist_backtest_persists_artifact_identity():
    init_db()
    trades = pd.DataFrame(
        [
            {
                "time": datetime(2024, 4, 1, tzinfo=timezone.utc),
                "side": "BUY",
                "qty": 1.0,
                "price": 100.0,
                "regime": "RANGING",
                "strategy_name": "reviewed_candidate_v1",
                "strategy_version": "1.0.0",
            }
        ]
    )
    strategy_meta = {
        "name": "reviewed_candidate_v1",
        "artifact_id": 321,
        "artifact_code_hash": "abc123",
        "provenance": "plugin",
    }
    with patch("backtester.service.list_available_strategies", return_value=[strategy_meta]), \
         patch("backtester.service.run_backtest", return_value=trades), \
         patch("backtester.service.build_equity_curve", return_value=pd.Series([100.0, 101.0])), \
         patch("backtester.service.compute_metrics", return_value={"sharpe": 1.2, "max_drawdown": 0.1, "profit_factor": 1.8, "n_trades": 1.0}), \
         patch("backtester.service.acceptance_gate", return_value=(True, [])), \
         patch("backtester.service.mark_artifact_backtest_result") as mock_mark:
        result = run_and_persist_backtest(
            "BTCUSDT",
            datetime(2024, 4, 1, tzinfo=timezone.utc),
            datetime(2024, 4, 2, tzinfo=timezone.utc),
            "reviewed_candidate_v1",
        )

    loaded = get_backtest_run(result["run_id"])
    assert loaded is not None
    assert loaded["artifact_id"] == 321
    assert loaded["strategy_code_hash"] == "abc123"
    assert loaded["strategy_provenance"] == "plugin"
    assert loaded["integrity_status"] == "valid"
    mock_mark.assert_called_once_with(321, True)


def test_list_backtest_runs_flags_missing_trade_rows():
    init_db()
    with SessionLocal() as sess:
        run = BacktestRun(
            symbol="BTCUSDT",
            start_ts=datetime(2024, 4, 1, tzinfo=timezone.utc),
            end_ts=datetime(2024, 4, 2, tzinfo=timezone.utc),
            strategy_name="mean_reversion_v1",
            strategy_version="1.0.0",
            params_json="{}",
            metrics_json=json.dumps({"n_trades": 2, "sharpe": 1.1}),
            status="passed",
        )
        sess.add(run)
        sess.commit()
        run_id = run.id

    runs = list_backtest_runs(limit=20)
    match = runs[runs["id"] == run_id].iloc[0]
    assert match["integrity_status"] == "missing-trades"


def test_run_and_persist_backtest_keeps_run_trade_linkage_consistent():
    init_db()
    trades = pd.DataFrame(
        [
            {
                "time": datetime(2024, 4, 1, tzinfo=timezone.utc),
                "side": "BUY",
                "qty": 1.0,
                "price": 100.0,
                "regime": "RANGING",
                "strategy_name": "mean_reversion_v1",
                "strategy_version": "1.0.0",
            },
            {
                "time": datetime(2024, 4, 1, 1, tzinfo=timezone.utc),
                "side": "SELL",
                "qty": 1.0,
                "price": 101.0,
                "regime": "RANGING",
                "strategy_name": "mean_reversion_v1",
                "strategy_version": "1.0.0",
            },
        ]
    )
    with patch("backtester.service.run_backtest", return_value=trades), \
         patch("backtester.service.build_equity_curve", return_value=pd.Series([100.0, 101.0])), \
         patch("backtester.service.compute_metrics", return_value={"sharpe": 1.2, "max_drawdown": 0.1, "profit_factor": 1.8, "n_trades": 2.0}), \
         patch("backtester.service.acceptance_gate", return_value=(True, [])):
        result = run_and_persist_backtest(
            "BTCUSDT",
            datetime(2024, 4, 1, tzinfo=timezone.utc),
            datetime(2024, 4, 2, tzinfo=timezone.utc),
            "mean_reversion_v1",
        )

    with SessionLocal() as sess:
        count = sess.query(BacktestTrade).filter(BacktestTrade.run_id == result["run_id"]).count()
    assert count == 2


def test_save_backtest_preset_creates_and_lists_preset():
    init_db()
    saved = save_backtest_preset(
        "mean_reversion_v1",
        "Pullback A",
        {"rsi_buy_threshold": 28, "volume_confirmation_mult": 1.7},
    )

    presets = list_backtest_presets("mean_reversion_v1")
    match = presets[presets["id"] == saved["id"]].iloc[0]
    assert match["preset_name"] == "Pullback A"
    assert match["params"]["rsi_buy_threshold"] == 28


def test_save_backtest_preset_updates_existing_name():
    init_db()
    first = save_backtest_preset("mean_reversion_v1", "Pullback A", {"rsi_buy_threshold": 28})
    second = save_backtest_preset("mean_reversion_v1", "Pullback A", {"rsi_buy_threshold": 31})

    presets = list_backtest_presets("mean_reversion_v1")
    same_name = presets[presets["preset_name"] == "Pullback A"]
    assert len(same_name) >= 1
    latest = same_name[same_name["id"] == second["id"]].iloc[0]
    assert first["id"] == second["id"]
    assert latest["params"]["rsi_buy_threshold"] == 31
