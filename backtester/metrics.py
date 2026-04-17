"""
backtester/metrics.py

Pure performance-metric functions for backtesting evaluation.
No DB, no I/O — takes DataFrames/arrays, returns scalars.

Acceptance gate thresholds imported from config:
  SHARPE_GATE, MAX_DD_GATE, PROFIT_FACTOR_GATE, MIN_TRADES_GATE
"""
from __future__ import annotations

import math
from typing import Dict

import numpy as np
import pandas as pd

from config import SHARPE_GATE, MAX_DD_GATE, PROFIT_FACTOR_GATE, MIN_TRADES_GATE

ANNUALISE_FACTOR = math.sqrt(525_600)  # 1-minute candles: sqrt(minutes per year)


def sharpe_ratio(equity_curve: pd.Series, periods_per_year: float = ANNUALISE_FACTOR) -> float:
    """
    Annualised Sharpe ratio from an equity curve (indexed by time or integer).
    Returns 0.0 when std == 0 (flat curve).
    """
    returns = equity_curve.pct_change().dropna()
    if len(returns) == 0 or returns.std() == 0:
        return 0.0
    return float((returns.mean() / returns.std()) * periods_per_year)


def max_drawdown(equity_curve: pd.Series) -> float:
    """
    Peak-to-trough maximum drawdown as a fraction (e.g. 0.15 = 15% drawdown).
    Returns 0.0 for a flat or empty curve.
    """
    if equity_curve.empty:
        return 0.0
    rolling_max = equity_curve.cummax()
    drawdowns   = (equity_curve - rolling_max) / rolling_max
    return float(abs(drawdowns.min()))


def profit_factor(trades: pd.DataFrame) -> float:
    """
    Gross profit / gross loss from a trades DataFrame with columns: side, price, qty.
    Uses average cost basis to handle multiple consecutive BUY fills before a SELL.
    Returns 0.0 when there are no completed round-trips or when only losses exist.
    When gross_loss == 0 and gross_profit > 0, returns 999.0 (infinity capped).
    """
    if trades.empty or "side" not in trades.columns:
        return 0.0

    gross_profit    = 0.0
    gross_loss      = 0.0
    accumulated_cost = 0.0
    position        = 0.0

    for _, row in trades.iterrows():
        if row["side"] == "BUY":
            accumulated_cost += row["qty"] * row["price"]
            position         += row["qty"]
        elif row["side"] == "SELL" and position > 0:
            avg_cost = accumulated_cost / position
            pnl = (row["price"] - avg_cost) * row["qty"]
            if pnl >= 0:
                gross_profit += pnl
            else:
                gross_loss += abs(pnl)
            accumulated_cost = 0.0
            position         = 0.0

    if gross_loss == 0:
        return 999.0 if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def acceptance_gate(metrics: Dict[str, float]) -> tuple[bool, list[str]]:
    """
    Check whether a backtest result meets all acceptance criteria.

    Args:
        metrics: dict with keys 'sharpe', 'max_drawdown', 'profit_factor', 'n_trades'

    Returns:
        (passed: bool, failures: list[str])  — failures is empty when passed is True
    """
    failures: list[str] = []

    sharpe = metrics.get("sharpe", 0.0)
    if sharpe < SHARPE_GATE:
        failures.append(f"Sharpe {sharpe:.2f} < {SHARPE_GATE} (gate)")

    dd = metrics.get("max_drawdown", 1.0)
    if dd > MAX_DD_GATE:
        failures.append(f"Max drawdown {dd:.1%} > {MAX_DD_GATE:.1%} (gate)")

    pf = metrics.get("profit_factor", 0.0)
    if pf < PROFIT_FACTOR_GATE:
        failures.append(f"Profit factor {pf:.2f} < {PROFIT_FACTOR_GATE} (gate)")

    n = metrics.get("n_trades", 0)
    if n < MIN_TRADES_GATE:
        failures.append(f"Trade count {int(n)} < {MIN_TRADES_GATE} (gate)")

    return (len(failures) == 0, failures)


def compute_metrics(trades: pd.DataFrame, equity_curve: pd.Series) -> Dict[str, float]:
    """Convenience wrapper: compute all metrics from trades + equity_curve."""
    return {
        "sharpe":        sharpe_ratio(equity_curve),
        "max_drawdown":  max_drawdown(equity_curve),
        "profit_factor": profit_factor(trades),
        "n_trades":      float(len(trades)),
    }
