"""tests/test_paper_trader_llm.py — Tests for LLM integration in PaperTrader.

Verifies that:
- critique_trade is called after SELL when LLM_ENABLED=True
- critique is skipped when LLM_ENABLED=False
- _coordinator and _last_regime attributes are accessible
- _fire_critique coroutine never raises even if critiquer fails
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── PaperTrader attribute tests ────────────────────────────────────────────────

def test_paper_trader_has_coordinator_attr():
    from simulator.paper_trader import PaperTrader
    pt = PaperTrader()
    assert hasattr(pt, "_coordinator")
    assert pt._coordinator is None


def test_paper_trader_has_last_regime_attr():
    from simulator.paper_trader import PaperTrader
    pt = PaperTrader()
    assert hasattr(pt, "_last_regime")
    assert isinstance(pt._last_regime, dict)
    assert len(pt._last_regime) == 0


# ── _fire_critique coroutine ───────────────────────────────────────────────────

def test_fire_critique_calls_critique_trade():
    """_fire_critique should call critique_trade with correct arguments."""
    from simulator.paper_trader import _fire_critique

    with patch("simulator.paper_trader._fire_critique") as mock_fc:
        mock_fc.return_value = asyncio.coroutine(lambda: None)()

    # Call the real coroutine with a mock critiquer
    with patch("llm.critiquer.critique_trade") as mock_ct:
        asyncio.run(_fire_critique("BTCUSDT", 50000.0, 49000.0, 2.04, "TRENDING"))
        mock_ct.assert_called_once_with(
            "BTCUSDT", "SELL", 49000.0, 50000.0, 2.04, "TRENDING", {}
        )


def test_fire_critique_never_raises_on_exception():
    """_fire_critique must not propagate exceptions from critiquer."""
    from simulator.paper_trader import _fire_critique

    with patch("llm.critiquer.critique_trade", side_effect=RuntimeError("LLM down")):
        # Should complete silently
        asyncio.run(_fire_critique("ETHUSDT", 3000.0, 2900.0, 3.4, "RANGING"))


def test_fire_critique_never_raises_on_import_error():
    """_fire_critique must not propagate exceptions from critiquer — including errors."""
    from simulator.paper_trader import _fire_critique

    # Patch the already-imported module's function to raise ImportError
    with patch("llm.critiquer.critique_trade", side_effect=ImportError("no llm")):
        asyncio.run(_fire_critique("BNBUSDT", 400.0, 390.0, 2.6, "SQUEEZE"))


# ── auto_sell fires critique when LLM_ENABLED ─────────────────────────────────

def test_auto_sell_fires_critique_when_llm_enabled():
    """_auto_sell should schedule _fire_critique task when LLM_ENABLED=True."""
    from simulator.paper_trader import PaperTrader

    pt = PaperTrader()
    pt.positions   = {"BTCUSDT": 0.01}
    pt.cost_basis  = {"BTCUSDT": 490.0}
    pt._last_regime = {"BTCUSDT": "RANGING"}

    tasks_created = []

    def fake_create_task(coro):
        tasks_created.append(coro)
        # Prevent "coroutine was never awaited" warning
        coro.close()
        return MagicMock()

    with (
        patch("simulator.paper_trader.LLM_ENABLED", True),
        patch("simulator.paper_trader.send_telegram_alert"),
        patch("asyncio.create_task", side_effect=fake_create_task),
    ):
        asyncio.run(pt._auto_sell("BTCUSDT", 50000.0))

    assert len(tasks_created) == 1, "Expected exactly one create_task call for critique"


def test_auto_sell_skips_critique_when_llm_disabled():
    """_auto_sell should NOT call create_task when LLM_ENABLED=False."""
    from simulator.paper_trader import PaperTrader

    pt = PaperTrader()
    pt.positions   = {"BTCUSDT": 0.01}
    pt.cost_basis  = {"BTCUSDT": 490.0}
    pt._last_regime = {}

    tasks_created = []

    def fake_create_task(coro):
        tasks_created.append(coro)
        coro.close()
        return MagicMock()

    with (
        patch("simulator.paper_trader.LLM_ENABLED", False),
        patch("simulator.paper_trader.send_telegram_alert"),
        patch("asyncio.create_task", side_effect=fake_create_task),
    ):
        asyncio.run(pt._auto_sell("BTCUSDT", 50000.0))

    assert len(tasks_created) == 0, "No create_task call expected when LLM disabled"


def test_auto_sell_no_position_skips_critique():
    """If there's no open position, _auto_sell returns early — no critique."""
    from simulator.paper_trader import PaperTrader

    pt = PaperTrader()
    # No position for BTCUSDT
    tasks_created = []

    def fake_create_task(coro):
        tasks_created.append(coro)
        coro.close()
        return MagicMock()

    with (
        patch("simulator.paper_trader.LLM_ENABLED", True),
        patch("simulator.paper_trader.send_telegram_alert"),
        patch("asyncio.create_task", side_effect=fake_create_task),
    ):
        asyncio.run(pt._auto_sell("BTCUSDT", 50000.0))

    assert len(tasks_created) == 0
