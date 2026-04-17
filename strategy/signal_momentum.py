"""
strategy/signal_momentum.py

Momentum strategy — active when regime == TRENDING (ADX > 25).
Pure function: takes indicator DataFrame, returns Signal.

Entry:  EMA9 > EMA21 > EMA55 (trend stack) + ADX > 25 + pullback to EMA21 + volume
Exit:   EMA9 crosses below EMA21 (momentum fading)
"""
import pandas as pd

from config import ADX_TREND_THRESHOLD, MOMENTUM_PULLBACK_TOL, VOLUME_CONFIRMATION_MULT
from .signals import Signal


def momentum_signal(df: pd.DataFrame) -> Signal:
    """Return BUY/SELL/HOLD for the momentum strategy given an indicator DataFrame."""
    if len(df) < 2:
        return Signal.HOLD

    last, prev = df.iloc[-1], df.iloc[-2]

    # Entry: clean EMA stack + strong ADX + price pulled back to EMA21 + volume spike
    # Use percentage distance to avoid floating-point multiplication rounding issues
    pullback_pct = (last.close - last.ema_21) / last.ema_21 if last.ema_21 > 0 else float("inf")
    if (
        last.ema_9 > last.ema_21
        and last.ema_21 > last.ema_55
        and last.adx_14 > ADX_TREND_THRESHOLD
        and 0.0 <= pullback_pct <= MOMENTUM_PULLBACK_TOL
        and last.volume >= VOLUME_CONFIRMATION_MULT * last.volume_ma_20
    ):
        return Signal.BUY

    # Exit: EMA9 crosses below EMA21 (momentum reversal)
    if last.ema_9 < last.ema_21 and prev.ema_9 >= prev.ema_21:
        return Signal.SELL

    return Signal.HOLD
