"""Tests for Sprint 31 strategy plugins — EXP-001 and EXP-002."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd

from config import ADX_TREND_THRESHOLD, BREAKOUT_LOOKBACK, VOLUME_CONFIRMATION_MULT
from strategies.ema200_filtered_momentum import EMA200FilteredMomentumStrategy
from strategies.mtf_confirmation_strategy import MTFConfirmationStrategy
from strategy.regime import Regime
from strategy.signals import Signal


# ── shared helpers ────────────────────────────────────────────────────────────

def _neutral_row() -> dict:
    return {
        "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
        "volume": 500.0, "rsi_14": 50.0, "bb_lo": 90.0, "bb_hi": 110.0,
        "macd": 0.0, "macd_s": 0.0,
        "ema_9": 100.0, "ema_21": 100.0, "ema_55": 100.0, "ema_200": 100.0,
        "volume_ma_20": 500.0, "adx_14": 15.0,
    }


def _neutral_df(n: int = 2) -> pd.DataFrame:
    return pd.DataFrame([_neutral_row() for _ in range(n)])


def _datetime_index_df(n: int, row_template: dict | None = None) -> pd.DataFrame:
    """Return a DataFrame with a DatetimeIndex (as produced by signal_engine)."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    times = [start + timedelta(minutes=i) for i in range(n)]
    template = row_template or _neutral_row()
    rows = [dict(template) for _ in range(n)]
    df = pd.DataFrame(rows)
    df.index = pd.DatetimeIndex(times)
    return df


# ── EXP-001: EMA200FilteredMomentumStrategy ───────────────────────────────────

class TestEMA200FilteredMomentum:

    def test_meta_has_display_name_and_description(self):
        meta = EMA200FilteredMomentumStrategy().meta()
        assert "EXP-001" in meta["display_name"]
        assert "description" in meta
        assert meta["version"] == "1.0.0"

    def test_regime_gate_blocks_ranging(self):
        df = _neutral_df()
        sig = EMA200FilteredMomentumStrategy().evaluate(df, regime=Regime.RANGING)
        assert sig == Signal.HOLD

    def test_regime_gate_blocks_high_vol(self):
        df = _neutral_df()
        sig = EMA200FilteredMomentumStrategy().evaluate(df, regime=Regime.HIGH_VOL)
        assert sig == Signal.HOLD

    def test_trending_ema200_gate_blocks_buy_below_ema200(self):
        df = _neutral_df()
        # All momentum conditions satisfied, but close < ema_200
        df.iloc[-1, df.columns.get_loc("close")] = 95.0       # below EMA-200
        df.iloc[-1, df.columns.get_loc("ema_200")] = 100.0
        df.iloc[-1, df.columns.get_loc("ema_9")] = 105.0
        df.iloc[-1, df.columns.get_loc("ema_21")] = 100.0
        df.iloc[-1, df.columns.get_loc("ema_55")] = 95.0
        df.iloc[-1, df.columns.get_loc("adx_14")] = float(ADX_TREND_THRESHOLD + 5)
        df.iloc[-1, df.columns.get_loc("volume")] = 1000.0
        df.iloc[-1, df.columns.get_loc("volume_ma_20")] = 500.0
        sig = EMA200FilteredMomentumStrategy().evaluate(df, regime=Regime.TRENDING)
        assert sig == Signal.HOLD

    def test_trending_buy_fires_above_ema200_with_valid_conditions(self):
        df = _neutral_df()
        # pullback_pct = (100.2 - 100.0) / 100.0 = 0.002 (within MOMENTUM_PULLBACK_TOL=0.005)
        df.iloc[-1, df.columns.get_loc("close")] = 100.2
        df.iloc[-1, df.columns.get_loc("ema_200")] = 90.0     # close > ema_200 ✓
        df.iloc[-1, df.columns.get_loc("ema_9")] = 105.0
        df.iloc[-1, df.columns.get_loc("ema_21")] = 100.0
        df.iloc[-1, df.columns.get_loc("ema_55")] = 95.0
        df.iloc[-1, df.columns.get_loc("adx_14")] = float(ADX_TREND_THRESHOLD + 5)
        df.iloc[-1, df.columns.get_loc("volume")] = 1000.0
        df.iloc[-1, df.columns.get_loc("volume_ma_20")] = 500.0
        sig = EMA200FilteredMomentumStrategy().evaluate(df, regime=Regime.TRENDING)
        assert sig == Signal.BUY

    def test_trending_sell_fires_on_ema9_cross_below_ema21(self):
        df = _neutral_df()
        # prev: ema_9 >= ema_21; last: ema_9 < ema_21
        df.iloc[-2, df.columns.get_loc("ema_9")] = 101.0
        df.iloc[-2, df.columns.get_loc("ema_21")] = 100.0
        df.iloc[-1, df.columns.get_loc("ema_9")] = 99.0
        df.iloc[-1, df.columns.get_loc("ema_21")] = 100.0
        sig = EMA200FilteredMomentumStrategy().evaluate(df, regime=Regime.TRENDING)
        assert sig == Signal.SELL

    def test_squeeze_buy_blocked_below_ema200(self):
        n = BREAKOUT_LOOKBACK + 2
        rows = []
        for i in range(n):
            row = _neutral_row()
            row["high"] = 100.0
            row["low"] = 99.0
            rows.append(row)
        # Last row: breakout above prior high, but close < ema_200
        rows[-1]["close"] = 101.0   # above prior_high of 100.0
        rows[-1]["high"] = 102.0
        rows[-1]["ema_200"] = 110.0  # close < ema_200
        rows[-1]["volume"] = 1500.0
        rows[-1]["volume_ma_20"] = 500.0
        df = pd.DataFrame(rows)
        sig = EMA200FilteredMomentumStrategy().evaluate(df, regime=Regime.SQUEEZE)
        assert sig == Signal.HOLD

    def test_squeeze_buy_fires_above_ema200_on_breakout(self):
        n = BREAKOUT_LOOKBACK + 2
        rows = []
        for i in range(n):
            row = _neutral_row()
            row["high"] = 100.0
            row["low"] = 99.0
            rows.append(row)
        # Last row: breakout above prior high AND close > ema_200
        rows[-1]["close"] = 101.0
        rows[-1]["high"] = 102.0
        rows[-1]["ema_200"] = 90.0   # close > ema_200 ✓
        rows[-1]["volume"] = 1500.0
        rows[-1]["volume_ma_20"] = 500.0
        df = pd.DataFrame(rows)
        sig = EMA200FilteredMomentumStrategy().evaluate(df, regime=Regime.SQUEEZE)
        assert sig == Signal.BUY


# ── EXP-002: MTFConfirmationStrategy ─────────────────────────────────────────

class TestMTFConfirmationStrategy:

    def test_meta_has_display_name_and_description(self):
        meta = MTFConfirmationStrategy().meta()
        assert "EXP-002" in meta["display_name"]
        assert "description" in meta
        assert meta["version"] == "1.0.0"

    def test_regime_gate_blocks_trending(self):
        df = _neutral_df(300)
        sig = MTFConfirmationStrategy().evaluate(df, regime=Regime.TRENDING)
        assert sig == Signal.HOLD

    def test_min_rows_guard_returns_hold(self):
        df = _datetime_index_df(n=50)
        strat = MTFConfirmationStrategy()
        assert strat.should_long(df) is False
        assert strat.should_short(df) is False

    def test_ema200_gate_blocks_long_when_close_below_ema200(self):
        """1m is oversold but close < ema_200 → should_long must be False."""
        row = _neutral_row()
        row["rsi_14"] = 30.0
        row["close"] = 88.0
        row["bb_lo"] = 90.0
        row["ema_200"] = 100.0  # close < ema_200
        df = _datetime_index_df(n=300, row_template=row)
        strat = MTFConfirmationStrategy()
        assert strat.should_long(df) is False

    def test_ema200_gate_blocks_short_when_close_above_ema200(self):
        """1m is overbought but close > ema_200 → should_short must be False."""
        row = _neutral_row()
        row["rsi_14"] = 70.0
        row["close"] = 115.0
        row["bb_hi"] = 110.0
        row["ema_200"] = 100.0  # close > ema_200 blocks short
        df = _datetime_index_df(n=300, row_template=row)
        strat = MTFConfirmationStrategy()
        assert strat.should_short(df) is False

    def test_resample_guard_returns_false_without_datetime_index(self):
        """Non-datetime-indexed df → _resample_indicators returns empty → no signal."""
        strat = MTFConfirmationStrategy()
        df = _neutral_df(300)  # integer index, not DatetimeIndex
        result = strat._resample_indicators(df, "5min")
        assert result.empty

    def test_mtf_long_blocked_when_5m_not_oversold(self):
        """1m is oversold + above EMA-200, but 5m check fails → no BUY."""
        row = _neutral_row()
        row["rsi_14"] = 30.0
        row["close"] = 88.0
        row["bb_lo"] = 90.0
        row["ema_200"] = 80.0  # close > ema_200 ✓
        df = _datetime_index_df(n=300, row_template=row)
        strat = MTFConfirmationStrategy()

        # Patch _resample_indicators: 5m returns frame that is NOT oversold
        not_oversold = _neutral_df(10)  # rsi=50, neutral
        oversold_5m = _neutral_df(10)
        oversold_5m.iloc[-1, oversold_5m.columns.get_loc("rsi_14")] = 50.0  # not oversold

        with patch.object(strat, "_resample_indicators", return_value=not_oversold):
            assert strat.should_long(df) is False

    def test_neutral_data_returns_hold_on_evaluate(self):
        """Neutral 1m data (RSI=50, price in middle of BB) → HOLD."""
        df = _datetime_index_df(n=300)
        sig = MTFConfirmationStrategy().evaluate(df, regime=Regime.RANGING)
        assert sig == Signal.HOLD
