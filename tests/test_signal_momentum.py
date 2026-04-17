"""
tests/test_signal_momentum.py

Unit tests for strategy/signal_momentum.momentum_signal().
All tests use synthetic DataFrames with controlled indicator columns.
No DB, no I/O.
"""
import numpy as np
import pandas as pd
import pytest

from strategy.signals import Signal
from strategy.signal_momentum import momentum_signal
from config import ADX_TREND_THRESHOLD, MOMENTUM_PULLBACK_TOL, VOLUME_CONFIRMATION_MULT


def _momentum_df(n: int = 5, last_row: dict = None, prev_row: dict = None) -> pd.DataFrame:
    """Build a DataFrame where the last two rows have exact indicator values."""
    idx = pd.date_range("2024-01-01", periods=n, freq="1min")
    default = {
        "ema_9": 105.0, "ema_21": 100.0, "ema_55": 95.0,   # bullish stack
        "adx_14": float(ADX_TREND_THRESHOLD) + 5.0,          # strong trend
        "close": 100.5,   # within 0.5% of ema_21=100 → pullback zone
        "volume": VOLUME_CONFIRMATION_MULT * 500.0 + 1.0,    # volume passes
        "volume_ma_20": 500.0,
        # other columns required by df access (not used by momentum_signal)
        "open": 100.0, "high": 101.0, "low": 99.0,
    }
    rows = [{**default} for _ in range(n - 2)]
    rows.append({**default, **(prev_row or {})})
    rows.append({**default, **(last_row or {})})
    return pd.DataFrame(rows, index=idx)


# ── BUY signal ─────────────────────────────────────────────────────────────────

class TestMomentumBuy:
    def test_buy_when_all_conditions_met(self):
        """EMA stack + ADX + pullback + volume → BUY."""
        df = _momentum_df()
        assert momentum_signal(df) == Signal.BUY

    def test_buy_blocked_when_ema_not_stacked(self):
        """ema_9 < ema_21 — no clean uptrend → no BUY."""
        df = _momentum_df(last_row={"ema_9": 98.0, "ema_21": 100.0, "ema_55": 95.0})
        assert momentum_signal(df) != Signal.BUY

    def test_buy_blocked_when_ema21_above_ema55(self):
        """ema_21 < ema_55 — stack broken → no BUY."""
        df = _momentum_df(last_row={"ema_9": 105.0, "ema_21": 100.0, "ema_55": 102.0})
        assert momentum_signal(df) != Signal.BUY

    def test_buy_blocked_when_adx_too_low(self):
        """ADX at or below threshold — not strong enough trend → no BUY."""
        df = _momentum_df(last_row={"adx_14": float(ADX_TREND_THRESHOLD)})
        assert momentum_signal(df) != Signal.BUY

    def test_buy_blocked_when_close_above_pullback_zone(self):
        """Close too far above EMA21 (not a pullback) → no BUY."""
        df = _momentum_df(last_row={"close": 101.5, "ema_21": 100.0})
        # 101.5 / 100.0 = 1.015 > 1 + MOMENTUM_PULLBACK_TOL (1.005)
        assert momentum_signal(df) != Signal.BUY

    def test_buy_blocked_when_close_below_ema21(self):
        """Close below EMA21 — breakdown, not pullback → no BUY."""
        df = _momentum_df(last_row={"close": 99.5, "ema_21": 100.0})
        assert momentum_signal(df) != Signal.BUY

    def test_buy_blocked_when_volume_too_low(self):
        """Volume below threshold → no BUY."""
        df = _momentum_df(last_row={"volume": 600.0, "volume_ma_20": 500.0})
        # 600 < 1.5 * 500 = 750
        assert momentum_signal(df) != Signal.BUY

    def test_buy_at_exact_pullback_boundary(self):
        """Close == ema_21 * (1 + TOL) exactly (upper boundary) → BUY."""
        ema21 = 100.0
        close = ema21 * (1 + MOMENTUM_PULLBACK_TOL)
        df = _momentum_df(last_row={"close": close, "ema_21": ema21})
        assert momentum_signal(df) == Signal.BUY

    def test_buy_at_exact_lower_boundary(self):
        """Close == ema_21 exactly (lower boundary) → BUY."""
        df = _momentum_df(last_row={"close": 100.0, "ema_21": 100.0})
        assert momentum_signal(df) == Signal.BUY


# ── SELL signal ────────────────────────────────────────────────────────────────

class TestMomentumSell:
    def test_sell_on_ema9_cross_below_ema21(self):
        """EMA9 crosses below EMA21 (prev: above; last: below) → SELL."""
        df = _momentum_df(
            prev_row={"ema_9": 101.0, "ema_21": 100.0},  # ema_9 >= ema_21
            last_row={"ema_9": 99.0,  "ema_21": 100.0,   # ema_9 < ema_21
                      "close": 99.0,  "volume": 100.0, "volume_ma_20": 500.0},
        )
        assert momentum_signal(df) == Signal.SELL

    def test_sell_not_triggered_when_ema9_already_below(self):
        """EMA9 was already below EMA21 last candle — not a new crossover → no SELL."""
        df = _momentum_df(
            prev_row={"ema_9": 98.0, "ema_21": 100.0},
            last_row={"ema_9": 97.0, "ema_21": 100.0,
                      "close": 99.0, "volume": 100.0, "volume_ma_20": 500.0},
        )
        assert momentum_signal(df) != Signal.SELL

    def test_sell_not_triggered_when_ema9_above_ema21(self):
        """EMA9 stays above EMA21 → no crossover → no SELL."""
        df = _momentum_df(
            prev_row={"ema_9": 102.0, "ema_21": 100.0},
            last_row={"ema_9": 101.0, "ema_21": 100.0,
                      "close": 99.0, "volume": 100.0, "volume_ma_20": 500.0},
        )
        assert momentum_signal(df) != Signal.SELL


# ── HOLD + edge cases ──────────────────────────────────────────────────────────

class TestMomentumHold:
    def test_hold_on_neutral_conditions(self):
        """Neither BUY nor SELL conditions → HOLD."""
        df = _momentum_df(
            last_row={"ema_9": 103.0, "ema_21": 100.0, "ema_55": 95.0,
                      "adx_14": 30.0, "close": 102.0,   # above pullback zone
                      "volume": 800.0, "volume_ma_20": 500.0},
        )
        assert momentum_signal(df) == Signal.HOLD

    def test_returns_valid_signal_enum(self):
        df = _momentum_df()
        result = momentum_signal(df)
        assert isinstance(result, Signal)

    def test_insufficient_history_returns_hold(self):
        df = pd.DataFrame(
            [{"ema_9": 105.0, "ema_21": 100.0, "ema_55": 95.0,
              "adx_14": 30.0, "close": 100.5, "volume": 800.0, "volume_ma_20": 500.0}],
            index=pd.date_range("2024-01-01", periods=1, freq="1min"),
        )
        assert momentum_signal(df) == Signal.HOLD
