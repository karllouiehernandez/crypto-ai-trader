"""Unit tests for utils/telegram_commands.py — all DB and service calls mocked."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from utils.telegram_commands import (
    parse_command,
    format_command_response,
    handle_help,
    handle_trades,
    handle_equity,
    handle_strategy,
    handle_strategies,
    handle_focus,
    handle_backtest,
    handle_status,
)


# ── parse_command ─────────────────────────────────────────────────────────────

def test_parse_command_simple():
    assert parse_command("/status") == ("status", [])


def test_parse_command_with_args():
    assert parse_command("/trades 10") == ("trades", ["10"])


def test_parse_command_backtest():
    cmd, args = parse_command("/backtest BTCUSDT 2024-01-01 2024-03-31")
    assert cmd == "backtest"
    assert args == ["BTCUSDT", "2024-01-01", "2024-03-31"]


def test_parse_command_strips_bot_username():
    cmd, args = parse_command("/help@mybot")
    assert cmd == "help"


def test_parse_command_empty_text():
    assert parse_command("") == ("help", [])


# ── handle_help ───────────────────────────────────────────────────────────────

def test_handle_help_contains_key_commands():
    result = handle_help()
    assert "/status" in result
    assert "/trades" in result
    assert "/backtest" in result
    assert "/halt" in result


# ── handle_trades ─────────────────────────────────────────────────────────────

def test_handle_trades_returns_no_trades_message(tmp_path):
    import sqlite3
    db = tmp_path / "test.db"
    con = sqlite3.connect(str(db))
    con.execute(
        "CREATE TABLE trades (ts TEXT, symbol TEXT, side TEXT, "
        "price REAL, pnl REAL, regime TEXT, run_mode TEXT)"
    )
    con.commit()
    con.close()
    with patch("utils.telegram_commands._db_path", return_value=str(db)):
        result = handle_trades()
    assert "No trades" in result


def test_handle_trades_returns_rows(tmp_path):
    import sqlite3
    db = tmp_path / "test.db"
    con = sqlite3.connect(str(db))
    con.execute(
        "CREATE TABLE trades (ts TEXT, symbol TEXT, side TEXT, "
        "price REAL, pnl REAL, regime TEXT, run_mode TEXT)"
    )
    con.execute("INSERT INTO trades VALUES ('2024-01-01','BTCUSDT','BUY',50000,10.5,'TRENDING','paper')")
    con.commit()
    con.close()
    with patch("utils.telegram_commands._db_path", return_value=str(db)):
        result = handle_trades(n=3)
    assert "BTCUSDT" in result
    assert "BUY" in result


# ── handle_equity ─────────────────────────────────────────────────────────────

def test_handle_equity_no_portfolio(tmp_path):
    import sqlite3
    db = tmp_path / "test.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE portfolio (id INTEGER PRIMARY KEY, equity REAL, balance REAL)")
    con.commit()
    con.close()
    with patch("utils.telegram_commands._db_path", return_value=str(db)), \
         patch("utils.telegram_commands._starting_balance", return_value=100.0):
        result = handle_equity()
    assert "No portfolio" in result


def test_handle_equity_shows_return_pct(tmp_path):
    import sqlite3
    db = tmp_path / "test.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE portfolio (id INTEGER PRIMARY KEY, equity REAL, balance REAL)")
    con.execute("CREATE TABLE portfolio_snapshots (ts TEXT, equity REAL)")
    con.execute("INSERT INTO portfolio VALUES (1, 110.0, 55.0)")
    con.commit()
    con.close()
    with patch("utils.telegram_commands._db_path", return_value=str(db)), \
         patch("utils.telegram_commands._starting_balance", return_value=100.0):
        result = handle_equity()
    assert "110.00" in result
    assert "10.00%" in result


# ── handle_strategy ───────────────────────────────────────────────────────────

def test_handle_strategy_returns_name():
    with patch("strategy.runtime.get_active_strategy_config",
               return_value={"name": "momentum_v1", "version": "1.0", "params": {}}), \
         patch("strategy.runtime.list_available_strategies",
               return_value=[{"name": "momentum_v1", "description": "Trend follower"}]):
        result = handle_strategy()
    assert "momentum_v1" in result


# ── handle_strategies ─────────────────────────────────────────────────────────

def test_handle_strategies_lists_all():
    with patch("strategy.runtime.list_available_strategies",
               return_value=[
                   {"name": "regime_router_v1", "source": "builtin"},
                   {"name": "momentum_v1", "source": "builtin"},
               ]):
        result = handle_strategies()
    assert "regime_router_v1" in result
    assert "momentum_v1" in result


# ── handle_focus ──────────────────────────────────────────────────────────────

def test_handle_focus_no_study():
    with patch("backtester.service.get_latest_market_focus", return_value=None):
        result = handle_focus()
    assert "No market focus" in result


def test_handle_focus_returns_candidates():
    study = {"id": 1, "strategy_name": "regime_router_v1", "status": "done"}
    candidates = [
        {"rank": 1, "symbol": "BTCUSDT", "score": 0.9, "sharpe": 1.8},
        {"rank": 2, "symbol": "ETHUSDT", "score": 0.7, "sharpe": 1.5},
    ]
    with patch("backtester.service.get_latest_market_focus", return_value=study), \
         patch("backtester.service.get_market_focus_candidates", return_value=candidates):
        result = handle_focus()
    assert "BTCUSDT" in result
    assert "ETHUSDT" in result


# ── format_command_response (router) ─────────────────────────────────────────

def test_format_command_response_unknown_command():
    result = format_command_response("unknown_xyz", [])
    assert "Unknown command" in result


def test_format_command_response_help():
    result = format_command_response("help", [])
    assert "/status" in result


def test_format_command_response_backtest_missing_args():
    result = format_command_response("backtest", ["BTCUSDT"])
    assert "Usage" in result
