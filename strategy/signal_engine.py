# crypto_ai_trader/strategy/signal_engine.py  (SESSION, CANDLE VERSION)
"""
Compute buy / sell / hold signals from the latest technical‑indicator values.
Signature is now `compute_signal(session, candle)` so it aligns with the
PaperTrader call‑site.
"""
from enum import Enum
from typing import List

import pandas as pd
from sqlalchemy.orm import Session

from database.models import Candle
from .ta_features import add_indicators


class Signal(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


def _fetch_recent_candles(session: Session, symbol: str, lookback: int = 120) -> List[Candle]:
    """Return latest `lookback` candles (≤ 120) for a symbol, newest first."""
    return (
        session.query(Candle)
               .filter(Candle.symbol == symbol)
               .order_by(Candle.open_time.desc())
               .limit(lookback)
               .all()
    )


def compute_signal(session: Session, candle: Candle) -> Signal:  # ← NEW SIGNATURE
    """Given the active DB session and the most‑recent `candle`, decide a signal."""
    candles = _fetch_recent_candles(session, candle.symbol)
    if len(candles) < 60:               # need at least 1 hour of history
        return Signal.HOLD

    # Oldest → newest for indicators
    df = pd.DataFrame(
        [
            (c.open_time, c.open, c.high, c.low, c.close, c.volume)
            for c in reversed(candles)
        ],
        columns=["open_time", "open", "high", "low", "close", "volume"],
    ).set_index("open_time")

    df = add_indicators(df)
    last, prev = df.iloc[-1], df.iloc[-2]

    # --- very simple rules ---------------------------------------------------
    if (
        last.rsi_14 < 35 and last.close < last.bb_lo
        and last.macd > last.macd_s and prev.macd <= prev.macd_s
    ):
        return Signal.BUY

    if (
        last.rsi_14 > 70 and last.close > last.bb_hi
        and last.macd < last.macd_s and prev.macd >= prev.macd_s
    ):
        return Signal.SELL

    return Signal.HOLD
