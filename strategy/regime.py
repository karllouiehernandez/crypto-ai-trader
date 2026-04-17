"""
strategy/regime.py

Pure regime classifier — no DB, no I/O.
Takes the indicator DataFrame (output of add_indicators) and returns the
current market regime. Used by signal_engine to gate strategy selection.

Priority order: HIGH_VOL > SQUEEZE > TRENDING > RANGING
"""
from enum import Enum

import pandas as pd

from config import (
    ADX_TREND_THRESHOLD,
    BB_WIDTH_SQUEEZE_PERCENTILE,
    HIGH_VOL_MULTIPLIER,
    HIGH_VOL_SHORT_WINDOW,
)


class Regime(str, Enum):
    TRENDING = "TRENDING"   # ADX > 25 — momentum strategies active
    RANGING  = "RANGING"    # ADX < 20 — mean reversion active
    SQUEEZE  = "SQUEEZE"    # BB width compressed — breakout watch
    HIGH_VOL = "HIGH_VOL"   # realized vol spike — reduce/halt all positions


def detect_regime(df: pd.DataFrame) -> Regime:
    """
    Classify the current regime from a post-add_indicators DataFrame.
    Falls back to RANGING when insufficient data for a check.
    """
    if len(df) < 2:
        return Regime.RANGING

    if _is_high_vol(df):
        return Regime.HIGH_VOL

    if _is_squeeze(df):
        return Regime.SQUEEZE

    adx = df["adx_14"].iloc[-1]
    if adx > ADX_TREND_THRESHOLD:
        return Regime.TRENDING

    return Regime.RANGING


def _is_high_vol(df: pd.DataFrame) -> bool:
    """Recent realized vol > HIGH_VOL_MULTIPLIER × prior-window baseline vol.
    Baseline excludes the recent window to avoid contaminating the comparator."""
    if len(df) <= HIGH_VOL_SHORT_WINDOW:
        return False
    returns = df["close"].pct_change().dropna()
    if len(returns) <= HIGH_VOL_SHORT_WINDOW:
        return False
    prior_returns = returns.iloc[:-HIGH_VOL_SHORT_WINDOW]
    baseline_vol = prior_returns.std()
    recent_vol = returns.iloc[-HIGH_VOL_SHORT_WINDOW:].std()
    if baseline_vol == 0:
        # Flat prior history: any movement in recent window is HIGH_VOL
        return recent_vol > 0
    return recent_vol > HIGH_VOL_MULTIPLIER * baseline_vol


def _is_squeeze(df: pd.DataFrame) -> bool:
    """BB width is below its BB_WIDTH_SQUEEZE_PERCENTILE-th percentile of prior history.
    Excludes the current candle from the percentile to avoid self-inclusion bias."""
    if "bb_width" not in df.columns or len(df) < 21:
        return False
    threshold = df["bb_width"].iloc[:-1].quantile(BB_WIDTH_SQUEEZE_PERCENTILE / 100.0)
    return float(df["bb_width"].iloc[-1]) < threshold
