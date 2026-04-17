"""Pure helpers for the strategy workbench dashboard."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from config import STARTING_BALANCE_USD


def compute_trade_equity_curve(
    trades: pd.DataFrame,
    starting_balance: float = STARTING_BALANCE_USD,
) -> pd.DataFrame:
    """Return a per-trade equity curve from a trade log."""
    if trades.empty:
        return pd.DataFrame({"step": [0], "equity": [float(starting_balance)]})

    equity = float(starting_balance)
    rows: list[dict[str, float]] = [{"step": 0, "equity": equity}]
    for step, (_, row) in enumerate(trades.iterrows(), start=1):
        notionals = float(row["qty"]) * float(row["price"])
        if row["side"] == "BUY":
            equity -= notionals
        else:
            equity += notionals
        rows.append({"step": step, "equity": equity})
    return pd.DataFrame(rows)


def compute_drawdown_curve(equity_curve: pd.DataFrame) -> pd.DataFrame:
    """Return drawdown percentages from an equity curve."""
    if equity_curve.empty or "equity" not in equity_curve.columns:
        return pd.DataFrame(columns=["step", "drawdown"])

    curve = equity_curve.copy()
    curve["peak"] = curve["equity"].cummax()
    curve["drawdown"] = (curve["equity"] - curve["peak"]) / curve["peak"]
    return curve[["step", "drawdown"]]


def parse_metrics_json(raw: str | None) -> dict[str, Any]:
    """Parse persisted metrics JSON safely."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def filter_runtime_data(
    frame: pd.DataFrame,
    strategy_name: str,
    run_mode: str,
) -> pd.DataFrame:
    """Filter runtime trade or portfolio data by strategy and run mode."""
    filtered = frame.copy()
    if not filtered.empty and "strategy_name" in filtered.columns:
        filtered = filtered[filtered["strategy_name"].fillna(strategy_name) == strategy_name]
    if run_mode != "All" and not filtered.empty and "run_mode" in filtered.columns:
        filtered = filtered[filtered["run_mode"].fillna("paper") == run_mode]
    return filtered


def runtime_summary(
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    starting_balance: float = STARTING_BALANCE_USD,
) -> dict[str, Any]:
    """Return headline runtime stats for the dashboard monitor."""
    latest_equity = float(equity["equity"].iloc[-1]) if not equity.empty and "equity" in equity.columns else float(starting_balance)
    latest_balance = float(equity["balance"].iloc[-1]) if not equity.empty and "balance" in equity.columns else latest_equity
    latest_unreal = float(equity["unreal_pnl"].iloc[-1]) if not equity.empty and "unreal_pnl" in equity.columns else 0.0
    last_trade = trades.iloc[-1].to_dict() if not trades.empty else {}
    return {
        "equity": latest_equity,
        "balance": latest_balance,
        "unreal_pnl": latest_unreal,
        "trade_count": int(len(trades)),
        "last_trade_side": last_trade.get("side", "—"),
        "last_trade_price": float(last_trade["price"]) if "price" in last_trade and pd.notna(last_trade["price"]) else None,
        "last_trade_regime": last_trade.get("regime", "—"),
        "last_trade_ts": last_trade.get("ts"),
    }
