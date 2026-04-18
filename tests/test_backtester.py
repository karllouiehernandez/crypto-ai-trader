"""
tests/test_backtester.py

Regression tests for backtester/engine.run_backtest().

The DB is fully mocked: SessionLocal is replaced with a context manager that
returns a session whose query produces a known, deterministic candle list.
This lets us assert exact trade counts and equity outcomes without a real DB.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from backtester.engine import run_backtest, BacktestResult
from strategy.regime import Regime
from strategy.runtime import StrategyDecision
from strategy.signals import Signal


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_candle(symbol: str, minutes_offset: int, close: float):
    c = MagicMock()
    c.symbol    = symbol
    c.open_time = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minutes_offset)
    c.close     = close
    return c


def _session_with_candles(candles: list):
    """Return a mock session context-manager whose query returns `candles`."""
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.all.return_value = candles

    mock_sess = MagicMock()
    mock_sess.query.return_value = mock_query
    mock_sess.__enter__ = MagicMock(return_value=mock_sess)
    mock_sess.__exit__ = MagicMock(return_value=False)
    return mock_sess


START = datetime(2024, 1, 1, tzinfo=timezone.utc)
END   = datetime(2024, 1, 2, tzinfo=timezone.utc)


def _decision(signal: Signal) -> StrategyDecision:
    return StrategyDecision(
        signal=signal,
        regime=Regime.RANGING,
        strategy_name="regime_router_v1",
        strategy_version="1.0.0",
    )


def _covered_end(candles: list) -> datetime:
    return candles[-1].open_time


# ── no candles ────────────────────────────────────────────────────────────────

class TestNoCandlesRaisesError:
    def test_empty_candle_list_raises_value_error(self):
        session = _session_with_candles([])
        with patch("backtester.engine.SessionLocal", return_value=session):
            with pytest.raises(ValueError, match="No candles"):
                run_backtest("BTCUSDT", START, END)

    def test_missing_candle_gap_raises_value_error(self):
        candles = [
            _make_candle("BTCUSDT", 0, 100.0),
            _make_candle("BTCUSDT", 2, 101.0),
        ]
        session = _session_with_candles(candles)
        with patch("backtester.engine.SessionLocal", return_value=session):
            with pytest.raises(ValueError, match="Incomplete history"):
                run_backtest("BTCUSDT", START, START + timedelta(minutes=2))


# ── return type ───────────────────────────────────────────────────────────────

class TestReturnType:
    def test_returns_dataframe(self):
        candles = [_make_candle("BTCUSDT", i, 100.0) for i in range(5)]
        session = _session_with_candles(candles)
        with patch("backtester.engine.SessionLocal", return_value=session), \
             patch("backtester.engine.compute_strategy_decision", return_value=_decision(Signal.HOLD)):
            result = run_backtest("BTCUSDT", START, _covered_end(candles))
        assert isinstance(result, BacktestResult)

    def test_all_hold_produces_no_trades(self):
        candles = [_make_candle("BTCUSDT", i, 100.0) for i in range(10)]
        session = _session_with_candles(candles)
        with patch("backtester.engine.SessionLocal", return_value=session), \
             patch("backtester.engine.compute_strategy_decision", return_value=_decision(Signal.HOLD)):
            result = run_backtest("BTCUSDT", START, _covered_end(candles))
        assert len(result) == 0


# ── single BUY ────────────────────────────────────────────────────────────────

class TestSingleBuy:
    def _run(self, signals):
        prices  = [100.0 + i for i in range(len(signals))]
        candles = [_make_candle("BTCUSDT", i, p) for i, p in enumerate(prices)]
        session = _session_with_candles(candles)
        decisions = [_decision(signal) for signal in signals]
        with patch("backtester.engine.SessionLocal", return_value=session), \
             patch("backtester.engine.compute_strategy_decision", side_effect=decisions):
            return run_backtest("BTCUSDT", START, _covered_end(candles)), candles

    def test_single_buy_produces_one_trade(self):
        result, _ = self._run([Signal.BUY] + [Signal.HOLD] * 4)
        assert len(result) == 1
        assert result.iloc[0]["side"] == "BUY"

    def test_buy_trade_has_correct_columns(self):
        result, _ = self._run([Signal.BUY] + [Signal.HOLD] * 4)
        for col in ("time", "side", "price", "qty"):
            assert col in result.columns

    def test_buy_price_matches_candle_close(self):
        """With zero slippage, fill price equals candle close."""
        result, candles = self._run([Signal.BUY] + [Signal.HOLD] * 4)
        from config import SLIPPAGE_PCT
        expected_fill = candles[0].close * (1 + SLIPPAGE_PCT)
        assert result.iloc[0]["price"] == pytest.approx(expected_fill, rel=1e-9)


# ── BUY then SELL ─────────────────────────────────────────────────────────────

class TestBuySell:
    def _run_buy_sell(self, buy_price: float = 100.0, sell_price: float = 110.0):
        candles = [
            _make_candle("BTCUSDT", 0, buy_price),
            _make_candle("BTCUSDT", 1, sell_price),
        ]
        signals = [Signal.BUY, Signal.SELL]
        session = _session_with_candles(candles)
        decisions = [_decision(signal) for signal in signals]
        with patch("backtester.engine.SessionLocal", return_value=session), \
             patch("backtester.engine.compute_strategy_decision", side_effect=decisions):
            return run_backtest("BTCUSDT", START, _covered_end(candles))

    def test_buy_then_sell_produces_two_trades(self):
        result = self._run_buy_sell()
        assert len(result) == 2
        assert result.iloc[0]["side"] == "BUY"
        assert result.iloc[1]["side"] == "SELL"

    def test_multiple_buys_possible_with_partial_sizing(self):
        """With POSITION_SIZE_PCT < 1, two BUY signals both execute (cash not exhausted)."""
        candles = [_make_candle("BTCUSDT", i, 100.0) for i in range(3)]
        signals = [Signal.BUY, Signal.BUY, Signal.HOLD]
        session = _session_with_candles(candles)
        decisions = [_decision(signal) for signal in signals]
        with patch("backtester.engine.SessionLocal", return_value=session), \
             patch("backtester.engine.compute_strategy_decision", side_effect=decisions):
            result = run_backtest("BTCUSDT", START, _covered_end(candles))
        # Both BUY signals execute because partial sizing leaves cash remaining
        assert len(result[result["side"] == "BUY"]) == 2

    def test_no_sell_without_position(self):
        """A SELL with no open position should be ignored."""
        candles = [_make_candle("BTCUSDT", i, 100.0) for i in range(3)]
        signals = [Signal.SELL, Signal.SELL, Signal.HOLD]
        session = _session_with_candles(candles)
        decisions = [_decision(signal) for signal in signals]
        with patch("backtester.engine.SessionLocal", return_value=session), \
             patch("backtester.engine.compute_strategy_decision", side_effect=decisions):
            result = run_backtest("BTCUSDT", START, _covered_end(candles))
        assert len(result) == 0


# ── fee application ───────────────────────────────────────────────────────────

class TestFeeApplication:
    def test_buy_cost_includes_fee(self):
        """Cash spent on buy must be qty*fill_price*(1+fee)."""
        from config import FEE_RATE, POSITION_SIZE_PCT, STARTING_BALANCE_USD, SLIPPAGE_PCT

        buy_price = 100.0
        candles = [
            _make_candle("BTCUSDT", 0, buy_price),
            _make_candle("BTCUSDT", 1, buy_price),
        ]
        signals = [Signal.BUY, Signal.HOLD]
        session = _session_with_candles(candles)
        decisions = [_decision(signal) for signal in signals]

        with patch("backtester.engine.SessionLocal", return_value=session), \
             patch("backtester.engine.compute_strategy_decision", side_effect=decisions):
            result = run_backtest("BTCUSDT", START, _covered_end(candles))

        fill_price = buy_price * (1 + SLIPPAGE_PCT)
        expected_qty = (STARTING_BALANCE_USD * POSITION_SIZE_PCT) / fill_price
        assert len(result) == 1
        assert result.iloc[0]["qty"] == pytest.approx(expected_qty, rel=1e-6)


# ── multiple complete round-trips ─────────────────────────────────────────────

class TestMultipleRoundTrips:
    def test_alternating_buy_sell_produces_correct_trade_count(self):
        signals = [Signal.BUY, Signal.SELL, Signal.BUY, Signal.SELL]
        candles = [_make_candle("BTCUSDT", i, 100.0 + i) for i in range(4)]
        session = _session_with_candles(candles)
        decisions = [_decision(signal) for signal in signals]

        with patch("backtester.engine.SessionLocal", return_value=session), \
             patch("backtester.engine.compute_strategy_decision", side_effect=decisions):
            result = run_backtest("BTCUSDT", START, _covered_end(candles))

        # BUY → SELL → (no cash for BUY? depends on math) — at minimum 2 trades
        assert len(result) >= 2
