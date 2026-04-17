# crypto_ai_trader/backtester/engine.py  (SIMPLE EQUITY BACKTEST)
"""Vectorised back-test loop that re-uses `strategy.signal_engine.compute_signal`.

Exported call:
    run_backtest(symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame

The returned DataFrame contains one row per trade with columns:
    time | side | price | qty
"""
from __future__ import annotations

from datetime import datetime
from typing import List

import logging
import pandas as pd

from database.models import Candle, SessionLocal
from strategy.signal_engine import compute_signal, Signal
from config import FEE_RATE, POSITION_SIZE_PCT, STARTING_BALANCE_USD

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


class BacktestResult(pd.DataFrame):
    """Just a typed alias; behaves exactly like DataFrame."""


def run_backtest(symbol: str, start: datetime, end: datetime) -> BacktestResult:
    """Back-test `symbol` between *start* and *end* (inclusive)."""
    cash      = STARTING_BALANCE_USD
    position  = 0.0
    trades: list[dict] = []

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

        for c in candles:
            sig   = compute_signal(sess, c)
            price = c.close

            if sig == Signal.BUY and cash > 0:
                qty   = (cash * POSITION_SIZE_PCT) / price
                cash -= qty * price * (1 + FEE_RATE)
                position += qty
                trades.append(dict(time=c.open_time, side="BUY", price=price, qty=qty))

            elif sig == Signal.SELL and position > 0:
                qty       = position
                cash     += qty * price * (1 - FEE_RATE)
                position  = 0.0
                trades.append(dict(time=c.open_time, side="SELL", price=price, qty=qty))

        final_equity = cash + position * candles[-1].close
        pnl_pct      = (final_equity / STARTING_BALANCE_USD - 1) * 100
        logging.info(f"{symbol} back-test finished – final equity ${final_equity:,.2f} (PnL {pnl_pct:.2f}%)")

    return BacktestResult(trades)
