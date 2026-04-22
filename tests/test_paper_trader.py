"""
tests/test_paper_trader.py

Unit tests for simulator/paper_trader.PaperTrader.

DB access (SessionLocal) and Telegram alerts are fully mocked so these tests
run with zero I/O.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from simulator.paper_trader import PaperTrader
from strategy.regime import Regime
from strategy.runtime import StrategyDecision
from strategy.signals import Signal
from config import POSITION_SIZE_PCT, FEE_RATE, STARTING_BALANCE_USD


# ── fixtures ───────────────────────────────────────────────────────────────────

def _make_candle(symbol: str = "BTCUSDT", close: float = 100.0):
    c = MagicMock()
    c.symbol = symbol
    c.close  = close
    c.open_time = datetime(2026, 4, 18, 4, 29, tzinfo=timezone.utc)
    return c


def _session_returning(candle):
    """Return a mock context-manager session whose first() returns `candle`."""
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.first.return_value = candle

    mock_sess = MagicMock()
    mock_sess.query.return_value = mock_query
    mock_sess.__enter__ = MagicMock(return_value=mock_sess)
    mock_sess.__exit__ = MagicMock(return_value=False)
    return mock_sess


def _session_with_trades(trades):
    mock_query = MagicMock()
    mock_query.order_by.return_value = mock_query
    mock_query.all.return_value = list(trades)

    mock_sess = MagicMock()
    mock_sess.query.return_value = mock_query
    mock_sess.__enter__ = MagicMock(return_value=mock_sess)
    mock_sess.__exit__ = MagicMock(return_value=False)
    return mock_sess


def _decision(signal: Signal) -> StrategyDecision:
    return StrategyDecision(
        signal=signal,
        regime=Regime.RANGING,
        strategy_name="regime_router_v1",
        strategy_version="1.0.0",
    )


# ── _auto_buy ──────────────────────────────────────────────────────────────────

class TestAutoBuy:
    @pytest.mark.asyncio
    async def test_auto_buy_reduces_cash(self):
        trader = PaperTrader()
        initial_cash = trader.cash
        price = 100.0

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_buy("BTCUSDT", price)

        expected_qty  = (initial_cash * POSITION_SIZE_PCT) / price
        expected_cost = expected_qty * price * (1 + FEE_RATE)
        assert abs(trader.cash - (initial_cash - expected_cost)) < 1e-9

    @pytest.mark.asyncio
    async def test_auto_buy_increases_position(self):
        trader = PaperTrader()
        price = 200.0

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_buy("BTCUSDT", price)

        assert trader.positions.get("BTCUSDT", 0) > 0

    @pytest.mark.asyncio
    async def test_auto_buy_fee_applied(self):
        """Cost must include FEE_RATE, not just qty * price."""
        trader = PaperTrader()
        initial_cash = trader.cash
        price = 100.0

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_buy("BTCUSDT", price)

        qty  = (initial_cash * POSITION_SIZE_PCT) / price
        cost_no_fee  = qty * price
        cost_with_fee = qty * price * (1 + FEE_RATE)
        cash_spent = initial_cash - trader.cash
        assert abs(cash_spent - cost_with_fee) < 1e-9
        assert cash_spent > cost_no_fee

    @pytest.mark.asyncio
    async def test_auto_buy_zero_price_does_nothing(self):
        """A zero price would cause infinite qty; guard should prevent the trade."""
        trader = PaperTrader()
        initial_cash = trader.cash

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_buy("BTCUSDT", 0.0)

        assert trader.cash == initial_cash
        assert trader.positions.get("BTCUSDT", 0) == 0

    @pytest.mark.asyncio
    async def test_auto_buy_cannot_spend_more_than_cash(self):
        """If cost exceeds available cash, the buy must be rejected.
        Simulate by patching POSITION_SIZE_PCT to 2.0 so cost = 2x cash."""
        trader = PaperTrader()
        initial_cash = trader.cash

        with patch("simulator.paper_trader.send_telegram_alert"), \
             patch("simulator.paper_trader.POSITION_SIZE_PCT", 2.0):
            await trader._auto_buy("BTCUSDT", 100.0)

        assert trader.cash == pytest.approx(initial_cash)

    @pytest.mark.asyncio
    async def test_auto_buy_skips_duplicate_buy_when_position_open(self):
        """Normal paper flow should not stack another BUY into an open position."""
        trader = PaperTrader()
        initial_cash = trader.cash

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_buy("BTCUSDT", 100.0)
            qty_after_first = trader.positions.get("BTCUSDT", 0)
            cash_after_first = trader.cash
            await trader._auto_buy("BTCUSDT", 100.0)

        assert trader.positions["BTCUSDT"] == qty_after_first
        assert trader.cash == cash_after_first
        assert trader.cash < initial_cash

    @pytest.mark.asyncio
    async def test_auto_buy_caps_notional_to_position_size_limit(self):
        trader = PaperTrader()
        price = 100.0
        atr = 0.1  # would imply a much larger ATR-sized position without the cap

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_buy("BTCUSDT", price, atr=atr)

        max_notional = STARTING_BALANCE_USD * POSITION_SIZE_PCT
        assert trader.positions["BTCUSDT"] * price == pytest.approx(max_notional, rel=1e-6)


# ── _auto_sell ────────────────────────────────────────────────────────────────

class TestAutoSell:
    @pytest.mark.asyncio
    async def test_auto_sell_increases_cash(self):
        trader = PaperTrader()
        trader.positions["BTCUSDT"] = 1.0  # already holding
        initial_cash = trader.cash
        price = 150.0

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_sell("BTCUSDT", price)

        expected_proceeds = 1.0 * price * (1 - FEE_RATE)
        assert abs(trader.cash - (initial_cash + expected_proceeds)) < 1e-9

    @pytest.mark.asyncio
    async def test_auto_sell_clears_position(self):
        trader = PaperTrader()
        trader.positions["BTCUSDT"] = 2.5

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_sell("BTCUSDT", 100.0)

        assert trader.positions.get("BTCUSDT", 0) == 0

    @pytest.mark.asyncio
    async def test_auto_sell_with_no_position_does_nothing(self):
        trader = PaperTrader()
        initial_cash = trader.cash

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_sell("BTCUSDT", 100.0)

        assert trader.cash == initial_cash

    @pytest.mark.asyncio
    async def test_auto_sell_zero_price_does_nothing(self):
        """Zero price guard should reject the sell and leave position intact."""
        trader = PaperTrader()
        trader.positions["BTCUSDT"] = 1.0
        initial_cash = trader.cash

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_sell("BTCUSDT", 0.0)

        assert trader.cash == initial_cash
        assert trader.positions.get("BTCUSDT", 0) == 1.0

    @pytest.mark.asyncio
    async def test_auto_sell_fee_applied(self):
        """Proceeds must be reduced by FEE_RATE."""
        trader = PaperTrader()
        qty = 1.0
        trader.positions["BTCUSDT"] = qty
        initial_cash = trader.cash
        price = 200.0

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_sell("BTCUSDT", price)

        gross = qty * price
        net   = gross * (1 - FEE_RATE)
        assert abs(trader.cash - (initial_cash + net)) < 1e-9
        assert trader.cash < initial_cash + gross

    @pytest.mark.asyncio
    async def test_auto_sell_updates_realised(self):
        """realised should track profit (proceeds - cost), not total proceeds."""
        trader = PaperTrader()
        buy_price  = 100.0
        sell_price = 110.0

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_buy("BTCUSDT", buy_price)
            cash_after_buy = trader.cash
            qty = trader.positions["BTCUSDT"]
            cost = trader.cost_basis["BTCUSDT"]
            await trader._auto_sell("BTCUSDT", sell_price)

        expected_proceeds = qty * sell_price * (1 - FEE_RATE)
        expected_pnl      = expected_proceeds - cost
        assert trader.realised == pytest.approx(expected_pnl, rel=1e-6)
        assert trader.realised > 0  # sold higher → profitable


# ── step ──────────────────────────────────────────────────────────────────────

class TestStep:
    @pytest.mark.asyncio
    async def test_step_calls_auto_buy_on_buy_signal(self):
        trader  = PaperTrader()
        candle  = _make_candle("BTCUSDT", close=50_000.0)
        session = _session_returning(candle)

        with patch("simulator.paper_trader.SessionLocal", return_value=session), \
             patch("simulator.paper_trader.compute_strategy_decision", return_value=_decision(Signal.BUY)), \
             patch("simulator.paper_trader.SYMBOLS", ["BTCUSDT"]), \
             patch("simulator.paper_trader.send_telegram_alert"):
            await trader.step()

        assert trader.positions.get("BTCUSDT", 0) > 0

    @pytest.mark.asyncio
    async def test_step_calls_auto_sell_on_sell_signal(self):
        trader = PaperTrader()
        trader.positions["BTCUSDT"] = 0.1
        candle  = _make_candle("BTCUSDT", close=50_000.0)
        session = _session_returning(candle)

        initial_cash = trader.cash

        with patch("simulator.paper_trader.SessionLocal", return_value=session), \
             patch("simulator.paper_trader.compute_strategy_decision", return_value=_decision(Signal.SELL)), \
             patch("simulator.paper_trader.SYMBOLS", ["BTCUSDT"]), \
             patch("simulator.paper_trader.send_telegram_alert"):
            await trader.step()

        assert trader.cash > initial_cash

    @pytest.mark.asyncio
    async def test_step_does_nothing_on_hold_signal(self):
        trader = PaperTrader()
        initial_cash = trader.cash
        candle  = _make_candle("BTCUSDT", close=50_000.0)
        session = _session_returning(candle)

        with patch("simulator.paper_trader.SessionLocal", return_value=session), \
             patch("simulator.paper_trader.compute_strategy_decision", return_value=_decision(Signal.HOLD)), \
             patch("simulator.paper_trader.SYMBOLS", ["BTCUSDT"]), \
             patch("simulator.paper_trader.send_telegram_alert"):
            await trader.step()

        assert trader.cash == initial_cash
        assert trader.positions.get("BTCUSDT", 0) == 0

    @pytest.mark.asyncio
    async def test_step_skips_symbol_with_no_candle(self):
        """If no candle exists for a symbol, step should silently skip it."""
        trader  = PaperTrader()
        session = _session_returning(None)  # first() returns None

        with patch("simulator.paper_trader.SessionLocal", return_value=session), \
             patch("simulator.paper_trader.SYMBOLS", ["BTCUSDT"]):
            await trader.step()  # should not raise

        assert trader.cash == trader.cash  # trivially true — no exception raised

    @pytest.mark.asyncio
    async def test_step_processes_each_candle_only_once(self):
        trader = PaperTrader()
        candle = _make_candle("BTCUSDT", close=50_000.0)
        session = _session_returning(candle)

        with patch("simulator.paper_trader.SessionLocal", return_value=session), \
             patch("simulator.paper_trader.compute_strategy_decision", return_value=_decision(Signal.BUY)), \
             patch("simulator.paper_trader.SYMBOLS", ["BTCUSDT"]), \
             patch.object(trader, "_auto_buy", new=AsyncMock()) as mock_auto_buy:
            await trader.step()
            await trader.step()

        assert mock_auto_buy.await_count == 1


# ── round-trip P&L math ────────────────────────────────────────────────────────

class TestRoundTripPnL:
    @pytest.mark.asyncio
    async def test_buy_then_sell_at_higher_price_is_profitable(self):
        trader = PaperTrader()
        buy_price  = 100.0
        sell_price = 110.0

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_buy("BTCUSDT", buy_price)
            cash_after_buy = trader.cash
            qty = trader.positions["BTCUSDT"]
            await trader._auto_sell("BTCUSDT", sell_price)

        profit = trader.cash - trader.__class__().cash  # compare to fresh initial cash
        assert profit > 0, "Expected profit on higher sell price"

    @pytest.mark.asyncio
    async def test_buy_then_sell_at_lower_price_is_loss(self):
        trader = PaperTrader()

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_buy("BTCUSDT", 100.0)
            await trader._auto_sell("BTCUSDT", 90.0)

        from config import STARTING_BALANCE_USD
        assert trader.cash < STARTING_BALANCE_USD, "Expected loss on lower sell price"


# ── risk integration ───────────────────────────────────────────────────────────

class TestRiskIntegration:
    @pytest.mark.asyncio
    async def test_step_halted_by_daily_loss_skips_signals(self):
        """When daily loss limit is reached, step() should skip all signal processing."""
        trader  = PaperTrader()
        candle  = _make_candle("BTCUSDT", close=100.0)
        session = _session_returning(candle)

        # Force halt via daily tracker
        trader._daily_tracker._halted = True

        initial_cash = trader.cash
        with patch("simulator.paper_trader.SessionLocal", return_value=session), \
             patch("simulator.paper_trader.compute_strategy_decision", return_value=_decision(Signal.BUY)), \
             patch("simulator.paper_trader.SYMBOLS", ["BTCUSDT"]), \
             patch("simulator.paper_trader.send_telegram_alert"):
            await trader.step()

        assert trader.cash == initial_cash  # no trade executed

    @pytest.mark.asyncio
    async def test_step_halted_by_drawdown_skips_signals(self):
        """When drawdown circuit breaker fires, step() should skip signal processing."""
        trader = PaperTrader()
        candle  = _make_candle("BTCUSDT", close=100.0)
        session = _session_returning(candle)

        # Force halt via drawdown breaker
        trader._drawdown_cb._halted = True

        initial_cash = trader.cash
        with patch("simulator.paper_trader.SessionLocal", return_value=session), \
             patch("simulator.paper_trader.compute_strategy_decision", return_value=_decision(Signal.BUY)), \
             patch("simulator.paper_trader.SYMBOLS", ["BTCUSDT"]), \
             patch("simulator.paper_trader.send_telegram_alert"):
            await trader.step()

        assert trader.cash == initial_cash

    @pytest.mark.asyncio
    async def test_auto_buy_with_atr_uses_risk_sizing(self):
        """When ATR is provided, position size should come from atr_position_size()."""
        trader = PaperTrader()
        from strategy.risk import atr_position_size

        price = 1.0
        atr   = 2.0
        expected_qty = atr_position_size(STARTING_BALANCE_USD, atr)

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_buy("BTCUSDT", price, atr=atr)

        assert trader.positions.get("BTCUSDT", 0) == pytest.approx(expected_qty, rel=1e-6)

    @pytest.mark.asyncio
    async def test_auto_buy_equity_uses_all_positions(self):
        """_auto_buy should size using full equity (cash + all positions), not just cash."""
        trader = PaperTrader()
        trader.positions["ETHUSDT"] = 1.0
        trader.cost_basis["ETHUSDT"] = 50.0

        from strategy.risk import atr_position_size

        # Use price=1.0 so the buy cost stays well within cash budget
        btc_price = 1.0
        eth_price = 200.0
        atr = 2.0

        # Full equity = cash + ETHUSDT position value
        expected_equity = trader.cash + 1.0 * eth_price
        expected_qty    = atr_position_size(expected_equity, atr)

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_buy("BTCUSDT", btc_price, atr=atr,
                                   prices={"ETHUSDT": eth_price, "BTCUSDT": btc_price})

        # Confirm trade executed and used full equity (not just cash)
        cash_only_equity = trader.__class__().cash  # fresh trader equity = just cash
        cash_only_qty    = atr_position_size(cash_only_equity, atr)
        assert trader.positions.get("BTCUSDT", 0) == pytest.approx(expected_qty, rel=1e-6)
        assert trader.positions["BTCUSDT"] > cash_only_qty  # larger than cash-only estimate


class TestStatusSnapshot:
    def test_status_snapshot_reports_runtime_fields(self):
        trader = PaperTrader()
        trader.cash = 900.0
        trader.realised = 12.5
        trader.positions["BTCUSDT"] = 1.5
        trader._latest_prices["BTCUSDT"] = 100.0
        trader._last_processed_candle["BTCUSDT"] = datetime(2026, 4, 18, 4, 29)
        trader._last_trade_ts = datetime(2026, 4, 18, 4, 30, tzinfo=timezone.utc)
        trader._force_halt = True

        with patch("simulator.paper_trader._current_runtime_symbols", return_value=["BTCUSDT"]):
            snapshot = trader.get_status_snapshot()

        assert snapshot["run_mode"] in {"paper", "live"}
        assert snapshot["strategy_name"] == trader._strategy_name
        assert snapshot["symbols"] == ["BTCUSDT"]
        assert snapshot["cash"] == 900.0
        assert snapshot["equity"] == pytest.approx(1050.0)
        assert snapshot["realized_pnl"] == 12.5
        assert snapshot["open_position_count"] == 1
        assert snapshot["last_processed_candle_ts"] == datetime(2026, 4, 18, 4, 29)
        assert snapshot["last_trade_ts"] == datetime(2026, 4, 18, 4, 30, tzinfo=timezone.utc)
        assert snapshot["force_halt"] is True
        assert snapshot["trading_halted"] is True
        assert snapshot["paper_evidence"]["stage"] == "waiting-for-first-close"

    def test_status_snapshot_reports_paper_evidence_progress(self):
        trader = PaperTrader()
        base = datetime(2026, 4, 18, 4, 0, tzinfo=timezone.utc)
        trader._paper_sell_pnls = [1.0] * 8
        trader._first_paper_sell_ts = base
        trader._last_paper_sell_ts = base + timedelta(days=1)

        snapshot = trader.get_status_snapshot()

        assert snapshot["paper_evidence"]["trade_count"] == 8
        assert snapshot["paper_evidence"]["trade_target"] == 20
        assert snapshot["paper_evidence"]["stage"] == "gathering-evidence"

    @pytest.mark.asyncio
    async def test_auto_buy_updates_last_trade_ts(self):
        trader = PaperTrader()

        with patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_buy("BTCUSDT", 100.0)

        assert trader._last_trade_ts is not None


class TestRuntimeStateRestore:
    def test_restore_runtime_state_rebuilds_open_position(self):
        trade_ts = datetime(2026, 4, 19, 4, 30, tzinfo=timezone.utc)
        persisted_trade = SimpleNamespace(
            ts=trade_ts,
            id=1,
            symbol="BTCUSDT",
            side="BUY",
            qty=1.0,
            price=100.0,
            fee=0.1,
            pnl=0.0,
            artifact_id=None,
            strategy_name="regime_router_v1",
            run_mode="paper",
        )
        session = _session_with_trades([persisted_trade])

        with patch("simulator.paper_trader.SessionLocal", return_value=session):
            trader = PaperTrader(
                strategy_descriptor={"strategy_name": "regime_router_v1"},
                restore_runtime_state=True,
            )

        assert trader.positions == {"BTCUSDT": 1.0}
        assert trader.cost_basis["BTCUSDT"] == pytest.approx(100.1)
        assert trader.cash == pytest.approx(STARTING_BALANCE_USD - 100.1)
        assert trader._last_trade_ts == trade_ts

    def test_restore_runtime_state_restores_sell_evidence_progress(self):
        buy_ts = datetime(2026, 4, 18, 4, 30, tzinfo=timezone.utc)
        sell_ts = datetime(2026, 4, 20, 4, 30, tzinfo=timezone.utc)
        persisted_trades = [
            SimpleNamespace(
                ts=buy_ts,
                id=1,
                symbol="BTCUSDT",
                side="BUY",
                qty=1.0,
                price=100.0,
                fee=0.1,
                pnl=0.0,
                artifact_id=None,
                strategy_name="regime_router_v1",
                run_mode="paper",
            ),
            SimpleNamespace(
                ts=sell_ts,
                id=2,
                symbol="BTCUSDT",
                side="SELL",
                qty=1.0,
                price=110.0,
                fee=0.1,
                pnl=9.8,
                artifact_id=None,
                strategy_name="regime_router_v1",
                run_mode="paper",
            ),
        ]
        session = _session_with_trades(persisted_trades)

        with patch("simulator.paper_trader.SessionLocal", return_value=session):
            trader = PaperTrader(
                strategy_descriptor={"strategy_name": "regime_router_v1"},
                restore_runtime_state=True,
            )

        assert trader._paper_sell_pnls == [9.8]
        assert trader._first_paper_sell_ts == sell_ts
        assert trader._last_paper_sell_ts == sell_ts

    @pytest.mark.asyncio
    async def test_auto_buy_skips_when_persisted_history_already_ends_with_buy(self):
        trader = PaperTrader()

        with patch.object(trader, "_would_duplicate_persisted_side", return_value=True), \
             patch.object(trader, "_restore_runtime_state") as mock_restore, \
             patch("simulator.paper_trader.send_telegram_alert"):
            await trader._auto_buy("BTCUSDT", 100.0)

        assert trader.positions == {}
        assert trader.cost_basis == {}
        mock_restore.assert_called_once()
