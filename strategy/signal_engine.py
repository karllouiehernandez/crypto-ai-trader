# crypto_ai_trader/strategy/signal_engine.py  (SESSION, CANDLE VERSION)
"""
Compute buy / sell / hold signals from the latest technical-indicator values.
Signature is now `compute_signal(session, candle)` so it aligns with the
PaperTrader call-site.
"""
from enum import Enum
from typing import List

import pandas as pd
from sqlalchemy.orm import Session

from config import EMA_LOOKBACK, MIN_CANDLES_EMA200, VOLUME_CONFIRMATION_MULT
from database.models import Candle
from .regime import Regime, detect_regime
from .ta_features import add_indicators


class Signal(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


def _fetch_recent_candles(session: Session, symbol: str, lookback: int = EMA_LOOKBACK) -> List[Candle]:
    """Return latest `lookback` candles for a symbol, newest first."""
    return (
        session.query(Candle)
               .filter(Candle.symbol == symbol)
               .order_by(Candle.open_time.desc())
               .limit(lookback)
               .all()
    )


def compute_signal(session: Session, candle: Candle) -> Signal:
    """Given the active DB session and the most-recent `candle`, decide a signal."""
    candles = _fetch_recent_candles(session, candle.symbol)
    if len(candles) < MIN_CANDLES_EMA200:
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
    if len(df) < 2:
        return Signal.HOLD

    regime = detect_regime(df)

    # High volatility: halt all signals
    if regime == Regime.HIGH_VOL:
        return Signal.HOLD

    # Mean reversion only fires in RANGING regime
    if regime != Regime.RANGING:
        return Signal.HOLD

    last, prev = df.iloc[-1], df.iloc[-2]

    # Trend filter: long only above EMA-200, short only below EMA-200
    # Volume confirmation: entry volume must be >= 1.5x 20-period average
    if (
        last.rsi_14 < 35 and last.close < last.bb_lo
        and last.macd > last.macd_s and prev.macd <= prev.macd_s
        and last.close > last.ema_200
        and last.volume >= VOLUME_CONFIRMATION_MULT * last.volume_ma_20
    ):
        return Signal.BUY

    if (
        last.rsi_14 > 70 and last.close > last.bb_hi
        and last.macd < last.macd_s and prev.macd >= prev.macd_s
        and last.close < last.ema_200
        and last.volume >= VOLUME_CONFIRMATION_MULT * last.volume_ma_20
    ):
        return Signal.SELL

    return Signal.HOLD
