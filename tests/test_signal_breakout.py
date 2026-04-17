"""
tests/test_signal_breakout.py

Unit tests for strategy/signal_breakout.breakout_signal().
All tests use synthetic DataFrames with controlled OHLCV + indicator columns.
No DB, no I/O.
"""
import numpy as np
import pandas as pd
import pytest

from strategy.signals import Signal
from strategy.signal_breakout import breakout_signal
from config import BREAKOUT_LOOKBACK, BREAKOUT_VOLUME_MULT


def _breakout_df(n: int = None, closes: np.ndarray = None, highs: np.ndarray = None,
                 lows: np.ndarray = None, last_volume: float = 1100.0,
                 volume_ma_20: float = 500.0) -> pd.DataFrame:
    """
    Build a breakout-strategy DataFrame.
    Default: n = BREAKOUT_LOOKBACK + 5 rows of flat prices at 100,
    then last row with controllable volume.
    """
    n = n or (BREAKOUT_LOOKBACK + 5)
    idx = pd.date_range("2024-01-01", periods=n, freq="1min")

    if closes is None:
        closes = np.ones(n) * 100.0
    if highs is None:
        highs = closes + 1.0
    if lows is None:
        lows = closes - 1.0

    volume = np.ones(n) * 500.0
    volume[-1] = last_volume

    return pd.DataFrame({
        "close": closes, "high": highs, "low": lows,
        "open": closes, "volume": volume,
        "volume_ma_20": np.full(n, volume_ma_20),
    }, index=idx)


# ── BUY signal ─────────────────────────────────────────────────────────────────

class TestBreakoutBuy:
    def test_buy_on_breakout_with_volume(self):
        """Close exceeds prior 20-period high + volume ok → BUY."""
        n = BREAKOUT_LOOKBACK + 5
        closes = np.ones(n) * 100.0
        highs  = closes + 1.0         # prior highs all at 101
        closes[-1] = 102.5            # last close > 101 → breakout
        highs[-1]  = 103.0
        df = _breakout_df(n=n, closes=closes, highs=highs,
                          last_volume=BREAKOUT_VOLUME_MULT * 500.0 + 1.0)
        assert breakout_signal(df) == Signal.BUY

    def test_buy_at_exact_volume_threshold(self):
        """Volume == BREAKOUT_VOLUME_MULT × volume_ma_20 exactly → BUY."""
        n = BREAKOUT_LOOKBACK + 5
        closes = np.ones(n) * 100.0
        highs  = closes + 1.0
        closes[-1] = 102.5
        highs[-1]  = 103.0
        df = _breakout_df(n=n, closes=closes, highs=highs,
                          last_volume=BREAKOUT_VOLUME_MULT * 500.0)  # exactly at threshold
        assert breakout_signal(df) == Signal.BUY

    def test_buy_blocked_when_volume_too_low(self):
        """Close breaks out but volume is insufficient → no BUY."""
        n = BREAKOUT_LOOKBACK + 5
        closes = np.ones(n) * 100.0
        highs  = closes + 1.0
        closes[-1] = 102.5
        highs[-1]  = 103.0
        low_volume = BREAKOUT_VOLUME_MULT * 500.0 - 1.0  # just below threshold
        df = _breakout_df(n=n, closes=closes, highs=highs, last_volume=low_volume)
        assert breakout_signal(df) != Signal.BUY

    def test_buy_blocked_when_no_breakout(self):
        """Close is at prior high level but not above → no BUY."""
        n = BREAKOUT_LOOKBACK + 5
        closes = np.ones(n) * 100.0
        highs  = closes + 1.0         # prior highs at 101
        closes[-1] = 101.0            # exactly at prior high — not > prior_high
        highs[-1]  = 101.5
        df = _breakout_df(n=n, closes=closes, highs=highs,
                          last_volume=BREAKOUT_VOLUME_MULT * 500.0 + 1.0)
        assert breakout_signal(df) != Signal.BUY

    def test_buy_uses_prior_candles_only(self):
        """prior_high excludes the current candle — current high doesn't raise the bar."""
        # Set current candle's high very high — should NOT affect the prior_high threshold
        n = BREAKOUT_LOOKBACK + 5
        closes = np.ones(n) * 100.0
        highs  = closes + 1.0         # prior highs at 101
        closes[-1] = 102.5            # breakout close
        highs[-1]  = 200.0            # current high is very high but irrelevant
        df = _breakout_df(n=n, closes=closes, highs=highs,
                          last_volume=BREAKOUT_VOLUME_MULT * 500.0 + 1.0)
        # prior_high is still 101 (from prior candles); close=102.5 > 101 → BUY
        assert breakout_signal(df) == Signal.BUY


# ── SELL signal ────────────────────────────────────────────────────────────────

class TestBreakoutSell:
    def test_sell_on_breakdown_below_prior_low(self):
        """Close falls below prior 20-period low → SELL (trailing stop)."""
        n = BREAKOUT_LOOKBACK + 5
        closes = np.ones(n) * 100.0
        lows   = closes - 1.0         # prior lows at 99
        closes[-1] = 97.5             # breakdown below prior low
        lows[-1]   = 97.0
        df = _breakout_df(n=n, closes=closes, lows=lows)
        assert breakout_signal(df) == Signal.SELL

    def test_sell_not_triggered_when_close_at_prior_low(self):
        """Close == prior low exactly — not strictly below → no SELL."""
        n = BREAKOUT_LOOKBACK + 5
        closes = np.ones(n) * 100.0
        lows   = closes - 1.0         # prior lows at 99
        closes[-1] = 99.0             # exactly at prior low, not < prior_low
        lows[-1]   = 98.5
        df = _breakout_df(n=n, closes=closes, lows=lows)
        assert breakout_signal(df) != Signal.SELL

    def test_sell_does_not_require_volume_confirmation(self):
        """Breakdown (trailing stop) fires regardless of volume."""
        n = BREAKOUT_LOOKBACK + 5
        closes = np.ones(n) * 100.0
        lows   = closes - 1.0
        closes[-1] = 97.5
        lows[-1]   = 97.0
        df = _breakout_df(n=n, closes=closes, lows=lows, last_volume=10.0)  # tiny volume
        assert breakout_signal(df) == Signal.SELL


# ── HOLD + edge cases ──────────────────────────────────────────────────────────

class TestBreakoutHold:
    def test_hold_on_flat_prices(self):
        """Flat prices with no breakout or breakdown → HOLD."""
        df = _breakout_df()
        assert breakout_signal(df) == Signal.HOLD

    def test_insufficient_history_returns_hold(self):
        """Fewer than BREAKOUT_LOOKBACK+1 rows → HOLD."""
        df = _breakout_df(n=BREAKOUT_LOOKBACK)
        assert breakout_signal(df) == Signal.HOLD

    def test_returns_valid_signal_enum(self):
        df = _breakout_df()
        result = breakout_signal(df)
        assert isinstance(result, Signal)
