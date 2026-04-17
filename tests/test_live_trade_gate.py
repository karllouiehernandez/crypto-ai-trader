"""tests/test_live_trade_gate.py — Unit tests for the live trade execution gate."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from simulator.paper_trader import PaperTrader


# ── helpers ───────────────────────────────────────────────────────────────────

def _trader() -> PaperTrader:
    return PaperTrader()


def _run(coro):
    return asyncio.run(coro)


# ── paper path (LIVE_TRADE_ENABLED=False) ─────────────────────────────────────

def test_submit_order_paper_path_does_not_call_binance(monkeypatch):
    monkeypatch.setattr("simulator.paper_trader.LIVE_TRADE_ENABLED", False)
    trader = _trader()
    trader._binance_client = AsyncMock()
    _run(trader._submit_order("BTCUSDT", "BUY", 0.001))
    trader._binance_client.create_order.assert_not_called()


def test_submit_order_paper_path_no_client_no_error(monkeypatch):
    monkeypatch.setattr("simulator.paper_trader.LIVE_TRADE_ENABLED", False)
    trader = _trader()
    # Must not raise even with no client set
    _run(trader._submit_order("BTCUSDT", "BUY", 0.001))


# ── live path (LIVE_TRADE_ENABLED=True) ───────────────────────────────────────

def test_submit_order_live_buy_calls_binance(monkeypatch):
    monkeypatch.setattr("simulator.paper_trader.LIVE_TRADE_ENABLED", True)
    trader = _trader()
    trader._binance_client = AsyncMock()
    trader._binance_client.create_order = AsyncMock()
    _run(trader._submit_order("BTCUSDT", "BUY", 0.001))
    trader._binance_client.create_order.assert_called_once_with(
        symbol="BTCUSDT", side="BUY", type="MARKET", quantity=0.001
    )


def test_submit_order_live_sell_calls_binance(monkeypatch):
    monkeypatch.setattr("simulator.paper_trader.LIVE_TRADE_ENABLED", True)
    trader = _trader()
    trader._binance_client = AsyncMock()
    trader._binance_client.create_order = AsyncMock()
    _run(trader._submit_order("ETHUSDT", "SELL", 0.05))
    trader._binance_client.create_order.assert_called_once_with(
        symbol="ETHUSDT", side="SELL", type="MARKET", quantity=0.05
    )


def test_submit_order_live_qty_rounded_to_6dp(monkeypatch):
    monkeypatch.setattr("simulator.paper_trader.LIVE_TRADE_ENABLED", True)
    trader = _trader()
    trader._binance_client = AsyncMock()
    trader._binance_client.create_order = AsyncMock()
    _run(trader._submit_order("BTCUSDT", "BUY", 0.123456789))
    call_kwargs = trader._binance_client.create_order.call_args.kwargs
    assert call_kwargs["quantity"] == round(0.123456789, 6)


# ── no client set ─────────────────────────────────────────────────────────────

def test_submit_order_live_no_client_logs_error_not_raises(monkeypatch):
    monkeypatch.setattr("simulator.paper_trader.LIVE_TRADE_ENABLED", True)
    trader = _trader()
    trader._binance_client = None
    # Must not raise
    _run(trader._submit_order("BTCUSDT", "BUY", 0.001))


def test_submit_order_live_no_client_does_not_raise_on_sell(monkeypatch):
    monkeypatch.setattr("simulator.paper_trader.LIVE_TRADE_ENABLED", True)
    trader = _trader()
    trader._binance_client = None
    _run(trader._submit_order("ETHUSDT", "SELL", 0.01))


# ── Binance exception handling ────────────────────────────────────────────────

def test_submit_order_binance_exception_does_not_propagate(monkeypatch):
    monkeypatch.setattr("simulator.paper_trader.LIVE_TRADE_ENABLED", True)
    trader = _trader()
    mock_client = AsyncMock()
    mock_client.create_order = AsyncMock(side_effect=Exception("Binance API error"))
    trader._binance_client = mock_client
    # Must not raise
    _run(trader._submit_order("BTCUSDT", "BUY", 0.001))


def test_submit_order_binance_timeout_does_not_propagate(monkeypatch):
    monkeypatch.setattr("simulator.paper_trader.LIVE_TRADE_ENABLED", True)
    trader = _trader()
    mock_client = AsyncMock()
    mock_client.create_order = AsyncMock(side_effect=TimeoutError("timeout"))
    trader._binance_client = mock_client
    _run(trader._submit_order("ETHUSDT", "SELL", 0.1))


# ── integration: _auto_buy/_auto_sell call _submit_order ─────────────────────

@pytest.mark.asyncio
async def test_auto_buy_calls_submit_order(monkeypatch):
    monkeypatch.setattr("simulator.paper_trader.LIVE_TRADE_ENABLED", True)
    trader = _trader()
    trader._binance_client = AsyncMock()
    trader._binance_client.create_order = AsyncMock()

    with patch("simulator.paper_trader.send_telegram_alert"):
        await trader._auto_buy("BTCUSDT", price=50000.0, atr=500.0)

    trader._binance_client.create_order.assert_called_once()
    assert trader._binance_client.create_order.call_args.kwargs["side"] == "BUY"


@pytest.mark.asyncio
async def test_auto_sell_calls_submit_order(monkeypatch):
    monkeypatch.setattr("simulator.paper_trader.LIVE_TRADE_ENABLED", True)
    trader = _trader()
    trader._binance_client = AsyncMock()
    trader._binance_client.create_order = AsyncMock()
    # Seed an open position so _auto_sell has something to sell
    trader.positions["BTCUSDT"] = 0.001
    trader.cost_basis["BTCUSDT"] = 50.0

    with patch("simulator.paper_trader.send_telegram_alert"), \
         patch("simulator.paper_trader.LLM_ENABLED", False):
        await trader._auto_sell("BTCUSDT", price=51000.0)

    trader._binance_client.create_order.assert_called_once()
    assert trader._binance_client.create_order.call_args.kwargs["side"] == "SELL"


@pytest.mark.asyncio
async def test_auto_buy_paper_path_does_not_call_binance(monkeypatch):
    monkeypatch.setattr("simulator.paper_trader.LIVE_TRADE_ENABLED", False)
    trader = _trader()
    mock_client = AsyncMock()
    trader._binance_client = mock_client

    with patch("simulator.paper_trader.send_telegram_alert"):
        await trader._auto_buy("BTCUSDT", price=50000.0, atr=500.0)

    mock_client.create_order.assert_not_called()
