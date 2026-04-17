"""Tests for persisted backtest service helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from backtester.service import get_backtest_run, list_backtest_runs
from database.models import BacktestRun, SessionLocal, init_db


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
            params_json="{}",
            metrics_json=json.dumps({"sharpe": 1.23, "passed": True}),
            status="passed",
        )
        sess.add(run)
        sess.commit()
        run_id = run.id

    loaded = get_backtest_run(run_id)
    assert loaded is not None
    assert loaded["strategy_name"] == "regime_router_v1"
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
