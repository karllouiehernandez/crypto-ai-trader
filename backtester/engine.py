# crypto_ai_trader/backtester/engine.py  (SIMPLE EQUITY BACKTEST)
"""Vectorised back-test loop that re-uses `strategy.signal_engine.compute_signal`.

Exported calls:
    run_backtest(symbol, start, end, slippage_pct) -> BacktestResult
    build_equity_curve(trades, starting_balance)   -> pd.Series

BacktestResult is a DataFrame with columns: time | side | price | qty
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import logging
import pandas as pd

from database.models import Candle, SessionLocal
from market_data.history import evaluate_candle_coverage, format_audit_summary
from strategy.ta_features import add_indicators
from strategy.runtime import compute_strategy_decision, get_active_strategy_config, get_strategy_instance
from strategy.signals import Signal
from config import EMA_LOOKBACK, FEE_RATE, POSITION_SIZE_PCT, STARTING_BALANCE_USD, SLIPPAGE_PCT

log = logging.getLogger(__name__)


class BacktestResult(pd.DataFrame):
    """Just a typed alias; behaves exactly like DataFrame."""


def _build_backtest_indicator_source(candles: list[Candle]) -> tuple[pd.DataFrame, dict]:
    if not candles:
        return pd.DataFrame(), {}

    raw_frame = pd.DataFrame(
        [
            (c.open_time, c.open, c.high, c.low, c.close, c.volume)
            for c in candles
        ],
        columns=["open_time", "open", "high", "low", "close", "volume"],
    )
    indicator_frame = add_indicators(raw_frame)
    if indicator_frame.empty:
        return pd.DataFrame(), {}

    indicator_positions = {
        open_time: idx
        for idx, open_time in enumerate(indicator_frame["open_time"].tolist())
    }
    return indicator_frame, indicator_positions


def run_backtest(
    symbol: str,
    start: datetime,
    end: datetime,
    slippage_pct: float = SLIPPAGE_PCT,
    strategy_name: str | None = None,
    params: dict | None = None,
) -> BacktestResult:
    """Back-test `symbol` between *start* and *end* (inclusive).

    Fills are adjusted for both FEE_RATE and slippage_pct:
      - BUY  effective price = close * (1 + slippage_pct)
      - SELL effective price = close * (1 - slippage_pct)
    Fees are applied on top of the slippage-adjusted price.
    """
    cash      = STARTING_BALANCE_USD
    position  = 0.0
    trades: list[dict] = []
    active_config = get_active_strategy_config()
    selected_strategy = strategy_name or active_config["name"]
    selected_params = params if params is not None else (active_config.get("params", {}) if strategy_name is None else {})
    strategy = get_strategy_instance(selected_strategy, selected_params)

    with SessionLocal() as sess:
        candles: List[Candle] = (
            sess.query(Candle)
                .filter(
                    Candle.symbol == symbol,
                    Candle.open_time >= start,
                    Candle.open_time <= end,
                )
                .order_by(Candle.open_time)
                .all()
        )

        if not candles:
            raise ValueError("No candles in the requested date range")

        coverage = evaluate_candle_coverage(symbol, start, end, [c.open_time for c in candles], interval="1m")
        if not coverage["is_complete"]:
            raise ValueError(format_audit_summary(coverage))

        indicator_source, indicator_positions = _build_backtest_indicator_source(candles)
        for c in candles:
            indicator_frame = pd.DataFrame()
            row_index = indicator_positions.get(c.open_time)
            if row_index is not None:
                window_start = max(0, row_index - EMA_LOOKBACK + 1)
                indicator_frame = indicator_source.iloc[window_start:row_index + 1]
            decision = compute_strategy_decision(
                sess,
                c,
                strategy_name=selected_strategy,
                strategy_params=selected_params,
                strategy=strategy,
                indicator_frame=indicator_frame,
            )
            sig   = decision.signal
            price = c.close

            if sig == Signal.BUY and cash > 0:
                fill_price = price * (1 + slippage_pct)
                qty        = (cash * POSITION_SIZE_PCT) / fill_price
                cost       = qty * fill_price * (1 + FEE_RATE)
                if cost > cash:
                    qty  = cash / (fill_price * (1 + FEE_RATE))
                    cost = cash
                cash      -= cost
                position  += qty
                trades.append(dict(time=c.open_time, side="BUY",
                                   price=fill_price, qty=qty,
                                   strategy_name=decision.strategy_name,
                                   strategy_version=decision.strategy_version,
                                   regime=decision.regime.value))

            elif sig == Signal.SELL and position > 0:
                fill_price = price * (1 - slippage_pct)
                qty        = position
                cash      += qty * fill_price * (1 - FEE_RATE)
                position   = 0.0
                trades.append(dict(time=c.open_time, side="SELL",
                                   price=fill_price, qty=qty,
                                   strategy_name=decision.strategy_name,
                                   strategy_version=decision.strategy_version,
                                   regime=decision.regime.value))

        final_equity = cash + position * candles[-1].close
        pnl_pct      = (final_equity / STARTING_BALANCE_USD - 1) * 100
        log.info("backtest finished",
                 extra={"symbol": symbol, "final_equity": round(final_equity, 2),
                        "pnl_pct": round(pnl_pct, 2), "n_trades": len(trades),
                        "slippage_pct": slippage_pct})

    return BacktestResult(trades)


def build_equity_curve(
    trades: pd.DataFrame,
    starting_balance: float = STARTING_BALANCE_USD,
) -> pd.Series:
    """
    Reconstruct a per-trade equity series from a trades DataFrame.

    Uses cash tracking: starts at starting_balance, adjusts on each BUY/SELL.
    Returns a Series indexed by trade index with the running cash balance.
    This is an approximation (ignores open position mark-to-market between trades)
    but sufficient for drawdown and Sharpe calculations.
    """
    if trades.empty:
        return pd.Series([starting_balance], dtype=float)

    cash     = starting_balance
    position = 0.0
    equity   = [starting_balance]

    for _, row in trades.iterrows():
        if row["side"] == "BUY":
            cost      = row["qty"] * row["price"] * (1 + FEE_RATE)
            cash     -= cost
            position += row["qty"]
        elif row["side"] == "SELL":
            cash     += row["qty"] * row["price"] * (1 - FEE_RATE)
            position  = 0.0
        equity.append(cash + position * row["price"])

    return pd.Series(equity, dtype=float)
