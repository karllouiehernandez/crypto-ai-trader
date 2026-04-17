# crypto_ai_trader/strategy/signal_engine.py
"""
Routes to the appropriate strategy based on the current market regime.
compute_signal() is the single entry point called by PaperTrader.
"""
import logging
from typing import List

import pandas as pd
from sqlalchemy.orm import Session

from config import EMA_LOOKBACK, MIN_CANDLES_EMA200, VOLUME_CONFIRMATION_MULT
from database.models import Candle
from .regime import Regime, detect_regime
from .signal_breakout import breakout_signal
from .signal_momentum import momentum_signal
from .signals import Signal
from .ta_features import add_indicators

log = logging.getLogger(__name__)


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

    # High volatility: halt all signals regardless of strategy
    if regime == Regime.HIGH_VOL:
        log.info(
            "signal computed",
            extra={"symbol": candle.symbol, "signal": "HOLD", "regime": regime.value,
                   "reason": "HIGH_VOL halt", "price": candle.close},
        )
        return Signal.HOLD

    # Route to active strategy by regime
    if regime == Regime.TRENDING:
        sig = momentum_signal(df)
        _log_signal(candle, sig, regime, df)
        return sig

    if regime == Regime.SQUEEZE:
        sig = breakout_signal(df)
        _log_signal(candle, sig, regime, df)
        return sig

    # RANGING: mean-reversion strategy
    last, prev = df.iloc[-1], df.iloc[-2]

    # Trend filter: long only above EMA-200, short only below EMA-200
    # Volume confirmation: entry volume must be >= 1.5x 20-period average
    if (
        last.rsi_14 < 35 and last.close < last.bb_lo
        and last.macd > last.macd_s and prev.macd <= prev.macd_s
        and last.close > last.ema_200
        and last.volume >= VOLUME_CONFIRMATION_MULT * last.volume_ma_20
    ):
        _log_signal(candle, Signal.BUY, regime, df)
        return Signal.BUY

    if (
        last.rsi_14 > 70 and last.close > last.bb_hi
        and last.macd < last.macd_s and prev.macd >= prev.macd_s
        and last.close < last.ema_200
        and last.volume >= VOLUME_CONFIRMATION_MULT * last.volume_ma_20
    ):
        _log_signal(candle, Signal.SELL, regime, df)
        return Signal.SELL

    return Signal.HOLD


def _log_signal(candle: Candle, sig: Signal, regime: Regime, df: pd.DataFrame) -> None:
    """Log a non-HOLD signal event with structured fields."""
    if sig == Signal.HOLD:
        return
    last = df.iloc[-1]
    log.info(
        "signal computed",
        extra={
            "symbol":  candle.symbol,
            "signal":  sig.value,
            "regime":  regime.value,
            "price":   round(float(candle.close), 4),
            "rsi":     round(float(last.rsi_14), 2) if "rsi_14" in df.columns else None,
            "adx":     round(float(last.adx_14), 2) if "adx_14" in df.columns else None,
        },
    )
