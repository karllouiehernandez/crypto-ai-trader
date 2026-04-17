"""Backtest execution helpers for dashboard use."""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from backtester.engine import build_equity_curve, run_backtest
from backtester.metrics import acceptance_gate, compute_metrics
from database.models import BacktestRun, BacktestTrade, SessionLocal, init_db
from dashboard.workbench import parse_metrics_json


def run_and_persist_backtest(
    symbol: str,
    start: datetime,
    end: datetime,
    strategy_name: str,
) -> dict:
    """Run a backtest, persist the run, and return a dashboard-ready payload."""
    init_db()
    trades = run_backtest(symbol, start, end, strategy_name=strategy_name)
    equity_curve = build_equity_curve(trades)
    metrics = compute_metrics(trades, equity_curve)
    passed, failures = acceptance_gate(metrics)

    with SessionLocal() as sess:
        strategy_version = ""
        if not trades.empty and "strategy_version" in trades.columns:
            strategy_version = str(trades["strategy_version"].dropna().iloc[0]) if not trades["strategy_version"].dropna().empty else ""

        run = BacktestRun(
            symbol=symbol,
            start_ts=start,
            end_ts=end,
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            params_json="{}",
            metrics_json=json.dumps({**metrics, "passed": passed, "failures": failures}),
            status="passed" if passed else "failed",
        )
        sess.add(run)
        sess.flush()

        for _, row in trades.iterrows():
            sess.add(
                BacktestTrade(
                    run_id=run.id,
                    ts=row["time"],
                    symbol=symbol,
                    side=row["side"],
                    qty=float(row["qty"]),
                    price=float(row["price"]),
                    regime=row.get("regime"),
                    strategy_name=row.get("strategy_name", strategy_name),
                    strategy_version=row.get("strategy_version"),
                )
            )
        sess.commit()

    return {
        "run_id": run.id,
        "trades": trades,
        "equity_curve": equity_curve,
        "metrics": metrics,
        "passed": passed,
        "failures": failures,
    }


def list_backtest_runs(limit: int = 100) -> pd.DataFrame:
    init_db()
    with SessionLocal() as sess:
        rows = (
            sess.query(BacktestRun)
            .order_by(BacktestRun.created_at.desc())
            .limit(limit)
            .all()
        )

    data = [
        {
            "id": row.id,
            "created_at": row.created_at,
            "symbol": row.symbol,
            "start_ts": row.start_ts,
            "end_ts": row.end_ts,
            "strategy_name": row.strategy_name,
            "strategy_version": row.strategy_version,
            "status": row.status,
            **parse_metrics_json(row.metrics_json),
        }
        for row in rows
    ]
    return pd.DataFrame(data)


def get_backtest_run(run_id: int) -> dict | None:
    init_db()
    with SessionLocal() as sess:
        row = sess.get(BacktestRun, run_id)

    if row is None:
        return None
    return {
        "id": row.id,
        "created_at": row.created_at,
        "symbol": row.symbol,
        "start_ts": row.start_ts,
        "end_ts": row.end_ts,
        "strategy_name": row.strategy_name,
        "strategy_version": row.strategy_version,
        "status": row.status,
        **parse_metrics_json(row.metrics_json),
    }


def get_backtest_trades(run_id: int) -> pd.DataFrame:
    init_db()
    with SessionLocal() as sess:
        rows = (
            sess.query(BacktestTrade)
            .filter(BacktestTrade.run_id == run_id)
            .order_by(BacktestTrade.ts)
            .all()
        )

    return pd.DataFrame(
        [
            {
                "ts": row.ts,
                "symbol": row.symbol,
                "side": row.side,
                "qty": row.qty,
                "price": row.price,
                "regime": row.regime,
                "strategy_name": row.strategy_name,
                "strategy_version": row.strategy_version,
            }
            for row in rows
        ]
    )
