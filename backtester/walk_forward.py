"""
backtester/walk_forward.py

Rolling walk-forward validation.

For each 3-month window:
  - In-sample  (train_pct):  signal tuning / confirmation
  - Out-of-sample (1-train_pct):  reported metrics

Returns a list of per-window result dicts so callers can aggregate or print a table.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Any

import pandas as pd

from config import WALK_FORWARD_MONTHS, WALK_FORWARD_TRAIN
from backtester.engine import run_backtest, build_equity_curve
from backtester.metrics import compute_metrics, acceptance_gate


def _month_windows(
    start: datetime,
    end: datetime,
    window_months: int,
) -> List[tuple[datetime, datetime]]:
    """
    Generate rolling (window_start, window_end) pairs that each span `window_months`
    months, stepping forward one window at a time until `end` is exceeded.
    """
    windows = []
    w_start = start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start
    while True:
        w_end = w_start + relativedelta(months=window_months)
        if w_end > end:
            break
        windows.append((w_start, w_end))
        w_start = w_end
    return windows


def walk_forward(
    symbol: str,
    start: datetime,
    end: datetime,
    window_months: int = WALK_FORWARD_MONTHS,
    train_pct: float = WALK_FORWARD_TRAIN,
) -> List[Dict[str, Any]]:
    """
    Run rolling walk-forward validation on `symbol` from `start` to `end`.

    For each window:
      - Split into in-sample (first train_pct) and OOS (remainder)
      - Run backtest on OOS period only (signal quality is evaluated on unseen data)
      - Compute metrics for the OOS period

    Returns a list of dicts, one per window:
      {
        "window":        int,          # 1-indexed
        "oos_start":     datetime,
        "oos_end":       datetime,
        "sharpe":        float,
        "max_drawdown":  float,
        "profit_factor": float,
        "n_trades":      int,
        "passed":        bool,         # acceptance gate result
        "failures":      list[str],    # empty when passed
        "final_equity":  float,
      }
    """
    windows = _month_windows(start, end, window_months)
    results = []

    for i, (w_start, w_end) in enumerate(windows, start=1):
        # Split window into IS and OOS
        window_duration = w_end - w_start
        oos_start = w_start + (window_duration * train_pct)
        oos_end   = w_end

        try:
            trades = run_backtest(symbol, oos_start, oos_end)
        except ValueError:
            # No candles in this OOS window — record as zero-trades result
            results.append({
                "window": i, "oos_start": oos_start, "oos_end": oos_end,
                "sharpe": 0.0, "max_drawdown": 0.0, "profit_factor": 0.0,
                "n_trades": 0, "passed": False,
                "failures": ["No candles in OOS window"],
                "final_equity": 0.0,
            })
            continue

        equity_curve = build_equity_curve(trades)
        metrics      = compute_metrics(trades, equity_curve)
        passed, failures = acceptance_gate(metrics)

        final_equity = float(equity_curve.iloc[-1]) if not equity_curve.empty else 0.0

        results.append({
            "window":        i,
            "oos_start":     oos_start,
            "oos_end":       oos_end,
            "sharpe":        round(metrics["sharpe"], 3),
            "max_drawdown":  round(metrics["max_drawdown"], 4),
            "profit_factor": round(metrics["profit_factor"], 3),
            "n_trades":      int(metrics["n_trades"]),
            "passed":        passed,
            "failures":      failures,
            "final_equity":  round(final_equity, 2),
        })

    return results


def aggregate_results(windows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate stats across all walk-forward windows."""
    if not windows:
        return {}
    sharpes = [w["sharpe"] for w in windows]
    dds     = [w["max_drawdown"] for w in windows]
    pfs     = [w["profit_factor"] for w in windows]
    trades  = [w["n_trades"] for w in windows]
    passed  = [w["passed"] for w in windows]
    return {
        "n_windows":          len(windows),
        "windows_passed":     sum(passed),
        "pass_rate":          round(sum(passed) / len(windows), 3),
        "mean_sharpe":        round(sum(sharpes) / len(sharpes), 3),
        "mean_max_drawdown":  round(sum(dds) / len(dds), 4),
        "mean_profit_factor": round(sum(pfs) / len(pfs), 3),
        "total_trades":       sum(trades),
    }
