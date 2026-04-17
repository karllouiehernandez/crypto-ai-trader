"""
strategy/signal_breakout.py

Breakout strategy — active when regime == SQUEEZE (BB width compressed).
Pure function: takes indicator DataFrame, returns Signal.

Entry:  Close breaks above prior BREAKOUT_LOOKBACK-period high + volume 2× avg
Exit:   Close breaks below prior BREAKOUT_LOOKBACK-period low (trailing stop)
"""
import pandas as pd

from config import BREAKOUT_LOOKBACK, BREAKOUT_VOLUME_MULT
from .signals import Signal


def breakout_signal(df: pd.DataFrame) -> Signal:
    """Return BUY/SELL/HOLD for the breakout strategy given an indicator DataFrame."""
    if len(df) < BREAKOUT_LOOKBACK + 1:
        return Signal.HOLD

    last  = df.iloc[-1]
    prior = df.iloc[-(BREAKOUT_LOOKBACK + 1):-1]   # prior N candles, excludes current

    prior_high = prior["high"].max()
    prior_low  = prior["low"].min()

    # Breakout above prior resistance with volume confirmation
    if (
        last.close > prior_high
        and last.volume >= BREAKOUT_VOLUME_MULT * last.volume_ma_20
    ):
        return Signal.BUY

    # Breakdown below prior support (trailing stop)
    if last.close < prior_low:
        return Signal.SELL

    return Signal.HOLD
