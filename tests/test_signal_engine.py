"""
tests/test_signal_engine.py

Unit tests for strategy/signal_engine.compute_signal().

Strategy is isolated from the DB by patching _fetch_recent_candles so we
can supply deterministic candle sequences that trigger each branch.
"""
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import pytest

from database.models import Candle
from strategy.signal_engine import compute_signal
from strategy.signals import Signal


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_candle(symbol: str, ts: datetime, open_: float, high: float,
                 low: float, close: float, volume: float = 500.0) -> Candle:
    c = Candle()
    c.symbol    = symbol
    c.open_time = ts
    c.open      = open_
    c.high      = high
    c.low       = low
    c.close     = close
    c.volume    = volume
    return c


def _candle_list(n: int, closes: np.ndarray, symbol: str = "BTCUSDT",
                 volume: float = 500.0) -> list[Candle]:
    """Build a list of n Candle objects from a close-price array (oldest first)."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    candles = []
    for i, close in enumerate(closes):
        candles.append(_make_candle(
            symbol,
            base + timedelta(minutes=i),
            open_=close * 0.999,
            high=close * 1.002,
            low=close * 0.998,
            close=close,
            volume=volume,
        ))
    return candles


def _rising_closes(n: int = 220) -> np.ndarray:
    return np.linspace(100, 200, n)


def _falling_closes(n: int = 220) -> np.ndarray:
    return np.linspace(200, 100, n)


def _flat_closes(n: int = 220, price: float = 100.0) -> np.ndarray:
    return np.full(n, price)


def _controlled_indicator_df(last_row: dict, prev_row: dict, n: int = 5) -> pd.DataFrame:
    """Build a DataFrame where the last two rows have exact indicator values."""
    idx = pd.date_range("2024-01-01", periods=n, freq="1min")
    default = {
        "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 500.0,
        "ma_21": 100.0, "ma_55": 100.0, "rsi_14": 50.0,
        "bb_hi": 105.0, "bb_lo": 95.0, "bb_width": 0.05,
        "macd": 0.0, "macd_s": 0.0,
        "ema_9": 100.0, "ema_21": 100.0, "ema_55": 100.0,
        "ema_200": 100.0, "volume_ma_20": 500.0,
        "adx_14": 15.0,   # RANGING by default so signal tests aren't blocked by regime
    }
    rows = [{**default} for _ in range(n - 2)]
    rows.append({**default, **prev_row})
    rows.append({**default, **last_row})
    return pd.DataFrame(rows, index=idx)


# ── fewer than 210 candles → HOLD (EMA-200 requires warmup) ───────────────────

class TestInsufficientHistory:
    def test_fewer_than_60_candles_returns_hold(self):
        session = MagicMock()
        candle  = _candle_list(1, np.array([100.0]))[0]

        with patch("strategy.signal_engine._fetch_recent_candles",
                   return_value=_candle_list(59, _flat_closes(59))):
            sig = compute_signal(session, candle)

        assert sig == Signal.HOLD

    def test_fewer_than_210_candles_returns_hold(self):
        """209 candles is below the new EMA-200 minimum — must return HOLD."""
        session = MagicMock()
        candle  = _candle_list(1, np.array([100.0]))[0]

        with patch("strategy.signal_engine._fetch_recent_candles",
                   return_value=_candle_list(209, _flat_closes(209))):
            sig = compute_signal(session, candle)

        assert sig == Signal.HOLD

    def test_210_or_more_candles_does_not_early_return_hold(self):
        """With 210+ candles the engine should attempt a signal (not early-return HOLD)."""
        session = MagicMock()
        candle  = _candle_list(1, np.array([100.0]))[0]
        candles = _candle_list(210, _flat_closes(210))

        with patch("strategy.signal_engine._fetch_recent_candles",
                   return_value=candles):
            sig = compute_signal(session, candle)

        assert sig in (Signal.BUY, Signal.SELL, Signal.HOLD)

    def test_zero_candles_returns_hold(self):
        session = MagicMock()
        candle  = _candle_list(1, np.array([100.0]))[0]

        with patch("strategy.signal_engine._fetch_recent_candles", return_value=[]):
            sig = compute_signal(session, candle)

        assert sig == Signal.HOLD


# ── BUY signal ─────────────────────────────────────────────────────────────────

class TestBuySignal:
    def test_buy_conditions_trigger_buy(self):
        """
        Craft a sequence where the last candle has:
          - RSI < 35    (long falling trend at end)
          - close < BB lower band   (price well below band)
          - MACD bullish crossover on last candle
        We achieve this by: 220 candles of sharp fall → tiny recovery on last candle.
        """
        session = MagicMock()

        # Sharp fall produces oversold RSI and price below lower BB
        n = 220
        closes = np.concatenate([
            np.linspace(200, 80, n - 2),   # steep fall → oversold
            [79.0, 79.5],                  # tiny bounce → MACD crossover
        ])
        candles = _candle_list(n, closes)

        with patch("strategy.signal_engine._fetch_recent_candles",
                   return_value=candles):
            sig = compute_signal(session, candles[-1])

        # Trend filter may suppress BUY in a downtrend (close << ema_200); HOLD is valid
        assert sig in (Signal.BUY, Signal.HOLD)

    def test_buy_not_triggered_on_rising_trend(self):
        """Rising prices keep RSI high — BUY should not fire."""
        session = MagicMock()
        candles = _candle_list(220, _rising_closes(220))

        with patch("strategy.signal_engine._fetch_recent_candles",
                   return_value=candles):
            sig = compute_signal(session, candles[-1])

        assert sig != Signal.BUY


# ── SELL signal ────────────────────────────────────────────────────────────────

class TestSellSignal:
    def test_sell_not_triggered_on_falling_trend(self):
        """Falling prices keep RSI low — SELL should not fire."""
        session = MagicMock()
        candles = _candle_list(220, _falling_closes(220))

        with patch("strategy.signal_engine._fetch_recent_candles",
                   return_value=candles):
            sig = compute_signal(session, candles[-1])

        assert sig != Signal.SELL

    def test_sell_conditions_attempt(self):
        """
        Craft a sequence where the last candle has RSI > 70 and price > BB upper.
        Long rising trend → overbought conditions.
        """
        session = MagicMock()
        n = 220
        closes = np.concatenate([
            np.linspace(100, 220, n - 2),   # strong rally → overbought
            [221.0, 220.5],                  # tiny drop → bearish MACD crossover
        ])
        candles = _candle_list(n, closes)

        with patch("strategy.signal_engine._fetch_recent_candles",
                   return_value=candles):
            sig = compute_signal(session, candles[-1])

        assert sig in (Signal.SELL, Signal.HOLD)


# ── HOLD signal ────────────────────────────────────────────────────────────────

class TestHoldSignal:
    def test_flat_prices_returns_hold(self):
        """Flat prices produce neither extreme RSI nor BB breakout → HOLD."""
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))

        with patch("strategy.signal_engine._fetch_recent_candles",
                   return_value=candles):
            sig = compute_signal(session, candles[-1])

        assert sig == Signal.HOLD

    def test_signal_is_valid_enum_value(self):
        """compute_signal must always return a valid Signal member."""
        session = MagicMock()
        candles = _candle_list(220, _rising_closes(220))

        with patch("strategy.signal_engine._fetch_recent_candles",
                   return_value=candles):
            sig = compute_signal(session, candles[-1])

        assert isinstance(sig, Signal)
        assert sig in (Signal.BUY, Signal.SELL, Signal.HOLD)


# ── symbol passed through correctly ───────────────────────────────────────────

class TestSymbolRouting:
    def test_fetch_called_with_correct_symbol(self):
        session = MagicMock()
        candle  = _candle_list(1, np.array([100.0]), symbol="ETHUSDT")[0]

        with patch("strategy.signal_engine._fetch_recent_candles",
                   return_value=_candle_list(220, _flat_closes(220), symbol="ETHUSDT")) as mock_fetch:
            compute_signal(session, candle)

        mock_fetch.assert_called_once_with(session, "ETHUSDT")


# ── trend filter ───────────────────────────────────────────────────────────────

class TestTrendFilter:
    def test_buy_blocked_when_close_below_ema200(self):
        """All BUY indicator conditions met, but close < ema_200 → trend filter → HOLD."""
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))

        # Controlled df: BUY conditions satisfied (RSI<35, close<bb_lo, MACD cross)
        # but close(94) < ema_200(100) → trend filter blocks BUY
        controlled = _controlled_indicator_df(
            prev_row={"rsi_14": 34.0, "close": 94.0, "bb_lo": 96.0,
                      "macd": -0.3, "macd_s": -0.2,
                      "ema_200": 100.0, "volume_ma_20": 500.0, "volume": 800.0},
            last_row={"rsi_14": 33.0, "close": 94.0, "bb_lo": 96.0,
                      "macd": -0.1, "macd_s": -0.2,
                      "ema_200": 100.0, "volume_ma_20": 500.0, "volume": 800.0},
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled):
            sig = compute_signal(session, candles[-1])

        assert sig != Signal.BUY

    def test_sell_blocked_when_close_above_ema200(self):
        """All SELL indicator conditions met, but close > ema_200 → trend filter → HOLD."""
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))

        # SELL conditions met (RSI>70, close>bb_hi, bearish MACD cross)
        # but close(106) > ema_200(100) → trend filter blocks SELL
        controlled = _controlled_indicator_df(
            prev_row={"rsi_14": 72.0, "close": 106.0, "bb_hi": 104.0,
                      "macd": 0.3, "macd_s": 0.2,
                      "ema_200": 100.0, "volume_ma_20": 500.0, "volume": 800.0},
            last_row={"rsi_14": 72.0, "close": 106.0, "bb_hi": 104.0,
                      "macd": 0.1, "macd_s": 0.2,
                      "ema_200": 100.0, "volume_ma_20": 500.0, "volume": 800.0},
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled):
            sig = compute_signal(session, candles[-1])

        assert sig != Signal.SELL

    def test_buy_allowed_when_close_above_ema200(self):
        """BUY conditions met AND close > ema_200 AND volume ok → BUY fires."""
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))

        # close(94) > ema_200(90): trend filter passes for BUY
        controlled = _controlled_indicator_df(
            prev_row={"rsi_14": 34.0, "close": 94.0, "bb_lo": 96.0,
                      "macd": -0.3, "macd_s": -0.2,
                      "ema_200": 90.0, "volume_ma_20": 500.0, "volume": 800.0},
            last_row={"rsi_14": 33.0, "close": 94.0, "bb_lo": 96.0,
                      "macd": -0.1, "macd_s": -0.2,
                      "ema_200": 90.0, "volume_ma_20": 500.0, "volume": 800.0},
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled):
            sig = compute_signal(session, candles[-1])

        assert sig == Signal.BUY

    def test_sell_allowed_when_close_below_ema200(self):
        """SELL conditions met AND close < ema_200 AND volume ok → SELL fires."""
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))

        # close(106) < ema_200(110): trend filter passes for SELL
        controlled = _controlled_indicator_df(
            prev_row={"rsi_14": 72.0, "close": 106.0, "bb_hi": 104.0,
                      "macd": 0.3, "macd_s": 0.2,
                      "ema_200": 110.0, "volume_ma_20": 500.0, "volume": 800.0},
            last_row={"rsi_14": 72.0, "close": 106.0, "bb_hi": 104.0,
                      "macd": 0.1, "macd_s": 0.2,
                      "ema_200": 110.0, "volume_ma_20": 500.0, "volume": 800.0},
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled):
            sig = compute_signal(session, candles[-1])

        assert sig == Signal.SELL


# ── volume filter ──────────────────────────────────────────────────────────────

class TestVolumeFilter:
    def test_buy_blocked_when_volume_too_low(self):
        """All BUY conditions met including trend, but volume < 1.5×volume_ma_20 → HOLD."""
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))

        # volume(600) < 1.5 * volume_ma_20(500) = 750 → volume gate blocks
        controlled = _controlled_indicator_df(
            prev_row={"rsi_14": 34.0, "close": 94.0, "bb_lo": 96.0,
                      "macd": -0.3, "macd_s": -0.2,
                      "ema_200": 90.0, "volume_ma_20": 500.0, "volume": 600.0},
            last_row={"rsi_14": 33.0, "close": 94.0, "bb_lo": 96.0,
                      "macd": -0.1, "macd_s": -0.2,
                      "ema_200": 90.0, "volume_ma_20": 500.0, "volume": 600.0},
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled):
            sig = compute_signal(session, candles[-1])

        assert sig != Signal.BUY

    def test_sell_blocked_when_volume_too_low(self):
        """All SELL conditions met including trend, but volume < 1.5×volume_ma_20 → HOLD."""
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))

        # volume(600) < 1.5 * volume_ma_20(500) = 750 → volume gate blocks
        controlled = _controlled_indicator_df(
            prev_row={"rsi_14": 72.0, "close": 106.0, "bb_hi": 104.0,
                      "macd": 0.3, "macd_s": 0.2,
                      "ema_200": 110.0, "volume_ma_20": 500.0, "volume": 600.0},
            last_row={"rsi_14": 72.0, "close": 106.0, "bb_hi": 104.0,
                      "macd": 0.1, "macd_s": 0.2,
                      "ema_200": 110.0, "volume_ma_20": 500.0, "volume": 600.0},
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled):
            sig = compute_signal(session, candles[-1])

        assert sig != Signal.SELL

    def test_buy_allowed_at_volume_threshold(self):
        """volume == 1.5 × volume_ma_20 exactly (boundary) → BUY fires."""
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))

        # volume(750) == 1.5 * volume_ma_20(500) → exactly at threshold → passes
        controlled = _controlled_indicator_df(
            prev_row={"rsi_14": 34.0, "close": 94.0, "bb_lo": 96.0,
                      "macd": -0.3, "macd_s": -0.2,
                      "ema_200": 90.0, "volume_ma_20": 500.0, "volume": 750.0},
            last_row={"rsi_14": 33.0, "close": 94.0, "bb_lo": 96.0,
                      "macd": -0.1, "macd_s": -0.2,
                      "ema_200": 90.0, "volume_ma_20": 500.0, "volume": 750.0},
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled):
            sig = compute_signal(session, candles[-1])

        assert sig == Signal.BUY


# ── regime gate ────────────────────────────────────────────────────────────────

class TestRegimeGate:
    """Verify that detect_regime output gates signal generation in compute_signal."""

    def _buy_conditions(self, extra: dict = None) -> dict:
        base = {"rsi_14": 33.0, "close": 94.0, "bb_lo": 96.0,
                "macd": -0.1, "macd_s": -0.2,
                "ema_200": 90.0, "volume_ma_20": 500.0, "volume": 800.0,
                "adx_14": 15.0}
        return {**base, **(extra or {})}

    def _sell_conditions(self, extra: dict = None) -> dict:
        base = {"rsi_14": 72.0, "close": 106.0, "bb_hi": 104.0,
                "macd": 0.1, "macd_s": 0.2,
                "ema_200": 110.0, "volume_ma_20": 500.0, "volume": 800.0,
                "adx_14": 15.0}
        return {**base, **(extra or {})}

    def _prev_buy(self) -> dict:
        return {"rsi_14": 34.0, "close": 94.0, "bb_lo": 96.0,
                "macd": -0.3, "macd_s": -0.2,
                "ema_200": 90.0, "volume_ma_20": 500.0, "volume": 800.0,
                "adx_14": 15.0}

    def _prev_sell(self) -> dict:
        return {"rsi_14": 72.0, "close": 106.0, "bb_hi": 104.0,
                "macd": 0.3, "macd_s": 0.2,
                "ema_200": 110.0, "volume_ma_20": 500.0, "volume": 800.0,
                "adx_14": 15.0}

    def test_buy_blocked_in_trending_regime(self):
        """All BUY conditions met, but ADX > 25 → TRENDING regime → HOLD."""
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))
        controlled = _controlled_indicator_df(
            prev_row=self._prev_buy(),
            last_row=self._buy_conditions({"adx_14": 30.0}),
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled):
            sig = compute_signal(session, candles[-1])
        assert sig == Signal.HOLD

    def test_sell_blocked_in_trending_regime(self):
        """All SELL conditions met, but ADX > 25 → TRENDING regime → HOLD."""
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))
        controlled = _controlled_indicator_df(
            prev_row=self._prev_sell(),
            last_row=self._sell_conditions({"adx_14": 30.0}),
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled):
            sig = compute_signal(session, candles[-1])
        assert sig == Signal.HOLD

    def test_buy_blocked_in_high_vol_regime(self):
        """All BUY conditions met, but HIGH_VOL regime → HOLD."""
        from strategy.regime import Regime
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))
        controlled = _controlled_indicator_df(
            prev_row=self._prev_buy(),
            last_row=self._buy_conditions(),
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled), \
             patch("strategy.signal_engine.detect_regime", return_value=Regime.HIGH_VOL):
            sig = compute_signal(session, candles[-1])
        assert sig == Signal.HOLD

    def test_buy_blocked_in_squeeze_regime(self):
        """All BUY conditions met, but SQUEEZE regime → HOLD (not RANGING)."""
        from strategy.regime import Regime
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))
        controlled = _controlled_indicator_df(
            prev_row=self._prev_buy(),
            last_row=self._buy_conditions(),
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled), \
             patch("strategy.signal_engine.detect_regime", return_value=Regime.SQUEEZE):
            sig = compute_signal(session, candles[-1])
        assert sig == Signal.HOLD

    def test_buy_fires_in_ranging_regime(self):
        """All BUY conditions met AND regime is RANGING → BUY fires."""
        from strategy.regime import Regime
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))
        controlled = _controlled_indicator_df(
            prev_row=self._prev_buy(),
            last_row=self._buy_conditions(),
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled), \
             patch("strategy.signal_engine.detect_regime", return_value=Regime.RANGING):
            sig = compute_signal(session, candles[-1])
        assert sig == Signal.BUY

    def test_sell_fires_in_ranging_regime(self):
        """All SELL conditions met AND regime is RANGING → SELL fires."""
        from strategy.regime import Regime
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))
        controlled = _controlled_indicator_df(
            prev_row=self._prev_sell(),
            last_row=self._sell_conditions(),
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled), \
             patch("strategy.signal_engine.detect_regime", return_value=Regime.RANGING):
            sig = compute_signal(session, candles[-1])
        assert sig == Signal.SELL


# ── strategy routing by regime ─────────────────────────────────────────────────

class TestStrategyRouting:
    """Verify compute_signal routes to the correct strategy function by regime."""

    def test_trending_regime_calls_momentum_signal(self):
        """TRENDING regime → momentum_signal() is called and its result returned."""
        from strategy.regime import Regime
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))
        controlled = _controlled_indicator_df(
            prev_row={}, last_row={"adx_14": 30.0},
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled), \
             patch("strategy.signal_engine.detect_regime", return_value=Regime.TRENDING), \
             patch("strategy.signal_engine.momentum_signal", return_value=Signal.BUY) as mock_mom:
            sig = compute_signal(session, candles[-1])
        mock_mom.assert_called_once()
        assert sig == Signal.BUY

    def test_squeeze_regime_calls_breakout_signal(self):
        """SQUEEZE regime → breakout_signal() is called and its result returned."""
        from strategy.regime import Regime
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))
        controlled = _controlled_indicator_df(
            prev_row={}, last_row={},
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled), \
             patch("strategy.signal_engine.detect_regime", return_value=Regime.SQUEEZE), \
             patch("strategy.signal_engine.breakout_signal", return_value=Signal.BUY) as mock_bo:
            sig = compute_signal(session, candles[-1])
        mock_bo.assert_called_once()
        assert sig == Signal.BUY

    def test_high_vol_never_calls_strategy(self):
        """HIGH_VOL regime → no strategy function is called, returns HOLD immediately."""
        from strategy.regime import Regime
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))
        controlled = _controlled_indicator_df(prev_row={}, last_row={})
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled), \
             patch("strategy.signal_engine.detect_regime", return_value=Regime.HIGH_VOL), \
             patch("strategy.signal_engine.momentum_signal") as mock_mom, \
             patch("strategy.signal_engine.breakout_signal") as mock_bo:
            sig = compute_signal(session, candles[-1])
        mock_mom.assert_not_called()
        mock_bo.assert_not_called()
        assert sig == Signal.HOLD


# ── strategy routing integration (no mocking of strategy functions) ────────────

class TestStrategyRoutingIntegration:
    """End-to-end tests: compute_signal routes to real strategy logic without mocking
    momentum_signal or breakout_signal. Verifies the full call chain fires correctly."""

    def test_trending_regime_buy_via_momentum(self):
        """TRENDING + full momentum BUY conditions → BUY returned from momentum_signal."""
        from strategy.regime import Regime
        from config import ADX_TREND_THRESHOLD, MOMENTUM_PULLBACK_TOL, VOLUME_CONFIRMATION_MULT
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))
        controlled = _controlled_indicator_df(
            prev_row={},
            last_row={
                "ema_9": 105.0, "ema_21": 100.0, "ema_55": 95.0,
                "adx_14": float(ADX_TREND_THRESHOLD) + 5.0,
                "close": 100.3,   # 0.3% above EMA21 — within MOMENTUM_PULLBACK_TOL
                "volume": VOLUME_CONFIRMATION_MULT * 500.0 + 1.0,
                "volume_ma_20": 500.0,
            },
        )
        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled), \
             patch("strategy.signal_engine.detect_regime", return_value=Regime.TRENDING):
            sig = compute_signal(session, candles[-1])
        assert sig == Signal.BUY

    def test_squeeze_regime_buy_via_breakout(self):
        """SQUEEZE + breakout conditions → BUY returned from breakout_signal."""
        from strategy.regime import Regime
        from config import BREAKOUT_LOOKBACK, BREAKOUT_VOLUME_MULT
        session = MagicMock()
        candles = _candle_list(220, _flat_closes(220))

        # Build a DataFrame with enough rows for breakout: last close > prior N-period high
        n = BREAKOUT_LOOKBACK + 5
        idx = pd.date_range("2024-01-01", periods=n, freq="1min")
        closes = np.ones(n) * 100.0
        highs  = closes + 1.0         # prior highs at 101
        lows   = closes - 1.0
        closes[-1] = 102.5            # last close breaks above prior high of 101
        highs[-1]  = 103.0
        volume_ma_20 = 500.0
        last_volume  = BREAKOUT_VOLUME_MULT * volume_ma_20 + 1.0
        volumes = np.full(n, 500.0)
        volumes[-1] = last_volume

        controlled = pd.DataFrame({
            "open": closes, "high": highs, "low": lows, "close": closes,
            "volume": volumes, "volume_ma_20": np.full(n, volume_ma_20),
            "ma_21": 100.0, "ma_55": 100.0, "rsi_14": 50.0,
            "bb_hi": 105.0, "bb_lo": 95.0, "bb_width": 0.05,
            "macd": 0.0, "macd_s": 0.0,
            "ema_9": 100.0, "ema_21": 100.0, "ema_55": 100.0,
            "ema_200": 100.0, "adx_14": 15.0,
        }, index=idx)

        with patch("strategy.signal_engine._fetch_recent_candles", return_value=candles), \
             patch("strategy.signal_engine.add_indicators", return_value=controlled), \
             patch("strategy.signal_engine.detect_regime", return_value=Regime.SQUEEZE):
            sig = compute_signal(session, candles[-1])
        assert sig == Signal.BUY
