"""
tests/test_risk.py

Unit tests for strategy/risk.py:
  - atr_position_size()
  - DailyLossTracker
  - DrawdownCircuitBreaker
"""
import pytest
from unittest.mock import patch
from datetime import date, timedelta

from strategy.risk import atr_position_size, DailyLossTracker, DrawdownCircuitBreaker
from config import RISK_PCT_PER_TRADE, ATR_STOP_MULTIPLIER, DAILY_LOSS_LIMIT_PCT, DRAWDOWN_HALT_PCT


# ── atr_position_size ──────────────────────────────────────────────────────────

class TestAtrPositionSize:
    def test_basic_math(self):
        """size = (equity * risk_pct) / (atr_mult * atr)"""
        equity = 1000.0
        atr    = 10.0
        risk   = 0.01
        mult   = 1.5
        expected = (1000.0 * 0.01) / (1.5 * 10.0)  # = 0.6667
        assert atr_position_size(equity, atr, risk, mult) == pytest.approx(expected, rel=1e-6)

    def test_uses_config_defaults(self):
        """Default args should pull from config."""
        equity = 1000.0
        atr    = 5.0
        expected = (equity * RISK_PCT_PER_TRADE) / (ATR_STOP_MULTIPLIER * atr)
        assert atr_position_size(equity, atr) == pytest.approx(expected, rel=1e-6)

    def test_zero_atr_returns_zero(self):
        assert atr_position_size(1000.0, 0.0) == 0.0

    def test_negative_atr_returns_zero(self):
        assert atr_position_size(1000.0, -5.0) == 0.0

    def test_zero_equity_returns_zero(self):
        assert atr_position_size(0.0, 10.0) == 0.0

    def test_negative_equity_returns_zero(self):
        assert atr_position_size(-100.0, 10.0) == 0.0

    def test_larger_atr_produces_smaller_size(self):
        """Higher volatility → smaller position."""
        size_low_vol  = atr_position_size(1000.0, 5.0)
        size_high_vol = atr_position_size(1000.0, 20.0)
        assert size_low_vol > size_high_vol

    def test_larger_equity_produces_larger_size(self):
        """More equity → larger position (same % risk)."""
        size_small = atr_position_size(500.0,  10.0)
        size_large = atr_position_size(2000.0, 10.0)
        assert size_large > size_small

    def test_risk_scales_linearly_with_equity(self):
        """Doubling equity should double the position size."""
        size_base   = atr_position_size(1000.0, 10.0)
        size_double = atr_position_size(2000.0, 10.0)
        assert size_double == pytest.approx(size_base * 2, rel=1e-6)

    def test_result_is_positive(self):
        assert atr_position_size(1000.0, 10.0) > 0


# ── DailyLossTracker ───────────────────────────────────────────────────────────

class TestDailyLossTracker:
    def test_not_halted_initially(self):
        tracker = DailyLossTracker(start_equity=1000.0)
        assert not tracker.is_halted

    def test_not_halted_below_limit(self):
        """Loss of 2% with a 3% limit should not trigger halt."""
        tracker = DailyLossTracker(start_equity=1000.0, limit_pct=0.03)
        tracker.update(980.0)  # -2%
        assert not tracker.is_halted

    def test_halted_at_limit(self):
        """Loss of exactly limit_pct should trigger halt."""
        tracker = DailyLossTracker(start_equity=1000.0, limit_pct=0.03)
        tracker.update(970.0)  # -3%
        assert tracker.is_halted

    def test_halted_beyond_limit(self):
        """Loss beyond limit should trigger halt."""
        tracker = DailyLossTracker(start_equity=1000.0, limit_pct=0.03)
        tracker.update(900.0)  # -10%
        assert tracker.is_halted

    def test_profit_does_not_trigger_halt(self):
        tracker = DailyLossTracker(start_equity=1000.0, limit_pct=0.03)
        tracker.update(1100.0)  # +10%
        assert not tracker.is_halted

    def test_halt_persists_after_recovery(self):
        """Once halted, recovery should not auto-resume."""
        tracker = DailyLossTracker(start_equity=1000.0, limit_pct=0.03)
        tracker.update(960.0)  # -4% → halted
        tracker.update(1010.0)  # recovered → still halted
        assert tracker.is_halted

    def test_reset_clears_halt(self):
        tracker = DailyLossTracker(start_equity=1000.0, limit_pct=0.03)
        tracker.update(900.0)
        assert tracker.is_halted
        tracker.reset(new_start_equity=900.0)
        assert not tracker.is_halted

    def test_loss_pct_property(self):
        tracker = DailyLossTracker(start_equity=1000.0)
        tracker.update(950.0)
        assert tracker.loss_pct == pytest.approx(-0.05, rel=1e-6)

    def test_loss_pct_positive_on_gain(self):
        tracker = DailyLossTracker(start_equity=1000.0)
        tracker.update(1050.0)
        assert tracker.loss_pct == pytest.approx(0.05, rel=1e-6)

    def test_invalid_start_equity_raises(self):
        with pytest.raises(ValueError):
            DailyLossTracker(start_equity=0.0)
        with pytest.raises(ValueError):
            DailyLossTracker(start_equity=-100.0)

    def test_reset_with_invalid_equity_raises(self):
        tracker = DailyLossTracker(start_equity=1000.0)
        with pytest.raises(ValueError):
            tracker.reset(0.0)

    def test_uses_config_default_limit(self):
        """Default limit_pct should come from config."""
        tracker = DailyLossTracker(start_equity=1000.0)
        # Just below limit — should not halt
        equity_just_above_limit = 1000.0 * (1 - DAILY_LOSS_LIMIT_PCT + 0.005)
        tracker.update(equity_just_above_limit)
        assert not tracker.is_halted
        # At limit — should halt
        equity_at_limit = 1000.0 * (1 - DAILY_LOSS_LIMIT_PCT)
        tracker.update(equity_at_limit)
        assert tracker.is_halted

    def test_day_rollover_resets_halt(self):
        """At calendar day rollover, halt should clear and start_equity reset."""
        tracker = DailyLossTracker(start_equity=1000.0, limit_pct=0.03)
        tracker.update(900.0)  # halted
        assert tracker.is_halted

        # Simulate a new day
        tomorrow = date.today() + timedelta(days=1)
        with patch("strategy.risk.date") as mock_date:
            mock_date.today.return_value = tomorrow
            assert not tracker.is_halted  # auto-resets on property access

    def test_multiple_updates_no_duplicate_halt(self):
        """Calling update many times after halt should not cause errors."""
        tracker = DailyLossTracker(start_equity=1000.0, limit_pct=0.03)
        for equity in [990, 980, 970, 960, 950]:
            tracker.update(float(equity))
        assert tracker.is_halted  # still just halted once


# ── DrawdownCircuitBreaker ────────────────────────────────────────────────────

class TestDrawdownCircuitBreaker:
    def test_not_halted_initially(self):
        cb = DrawdownCircuitBreaker(initial_equity=1000.0)
        assert not cb.is_halted

    def test_not_halted_below_threshold(self):
        """14% drawdown with 15% threshold should not halt."""
        cb = DrawdownCircuitBreaker(initial_equity=1000.0, halt_pct=0.15)
        cb.update(860.0)  # -14%
        assert not cb.is_halted

    def test_halted_at_threshold(self):
        """Exactly 15% drawdown should trigger halt."""
        cb = DrawdownCircuitBreaker(initial_equity=1000.0, halt_pct=0.15)
        cb.update(850.0)  # -15%
        assert cb.is_halted

    def test_halted_beyond_threshold(self):
        cb = DrawdownCircuitBreaker(initial_equity=1000.0, halt_pct=0.15)
        cb.update(700.0)  # -30%
        assert cb.is_halted

    def test_new_peak_updates_peak(self):
        cb = DrawdownCircuitBreaker(initial_equity=1000.0, halt_pct=0.15)
        cb.update(1200.0)  # new peak
        assert cb.peak == pytest.approx(1200.0)

    def test_drawdown_calculated_from_highest_peak(self):
        """After new peak, drawdown is from that higher peak."""
        cb = DrawdownCircuitBreaker(initial_equity=1000.0, halt_pct=0.15)
        cb.update(1200.0)  # peak = 1200
        cb.update(1020.0)  # drawdown = (1200-1020)/1200 = 15% → halted
        assert cb.is_halted

    def test_recovery_does_not_auto_resume(self):
        """Once halted, equity recovery should NOT auto-resume trading."""
        cb = DrawdownCircuitBreaker(initial_equity=1000.0, halt_pct=0.15)
        cb.update(800.0)  # halted
        cb.update(1100.0)  # recovered above peak
        assert cb.is_halted

    def test_reset_clears_halt(self):
        cb = DrawdownCircuitBreaker(initial_equity=1000.0, halt_pct=0.15)
        cb.update(700.0)
        assert cb.is_halted
        cb.reset(new_equity=700.0)
        assert not cb.is_halted

    def test_reset_sets_new_peak(self):
        cb = DrawdownCircuitBreaker(initial_equity=1000.0, halt_pct=0.15)
        cb.update(700.0)
        cb.reset(new_equity=700.0)
        assert cb.peak == pytest.approx(700.0)

    def test_drawdown_property_at_peak(self):
        cb = DrawdownCircuitBreaker(initial_equity=1000.0)
        assert cb.drawdown == pytest.approx(0.0)

    def test_drawdown_property_after_loss(self):
        cb = DrawdownCircuitBreaker(initial_equity=1000.0)
        cb.update(900.0)
        assert cb.drawdown == pytest.approx(0.10, rel=1e-6)

    def test_invalid_initial_equity_raises(self):
        with pytest.raises(ValueError):
            DrawdownCircuitBreaker(initial_equity=0.0)
        with pytest.raises(ValueError):
            DrawdownCircuitBreaker(initial_equity=-500.0)

    def test_reset_with_invalid_equity_raises(self):
        cb = DrawdownCircuitBreaker(initial_equity=1000.0)
        with pytest.raises(ValueError):
            cb.reset(0.0)

    def test_uses_config_default_halt_pct(self):
        """Default halt_pct should come from config."""
        cb = DrawdownCircuitBreaker(initial_equity=1000.0)
        # Just above halt threshold — should not halt
        equity_just_above = 1000.0 * (1 - DRAWDOWN_HALT_PCT + 0.005)
        cb.update(equity_just_above)
        assert not cb.is_halted
        # At threshold — should halt
        equity_at_threshold = 1000.0 * (1 - DRAWDOWN_HALT_PCT)
        cb.update(equity_at_threshold)
        assert cb.is_halted

    def test_multiple_halting_updates_idempotent(self):
        """Multiple updates below threshold should not cause errors."""
        cb = DrawdownCircuitBreaker(initial_equity=1000.0, halt_pct=0.15)
        for equity in [900, 800, 700, 600, 500]:
            cb.update(float(equity))
        assert cb.is_halted
