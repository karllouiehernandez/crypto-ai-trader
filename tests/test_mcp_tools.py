"""Unit tests for mcp_server/tools.py — all external calls mocked."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from mcp_server.tools import (
    get_system_status,
    get_trade_history,
    get_portfolio_equity,
    get_backtest_runs,
    get_backtest_run_detail,
    get_strategy_catalog,
    get_market_focus,
    get_promotions,
    list_kb_files,
    read_kb_file,
    run_backtest,
    save_backtest_preset,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_session(portfolio_equity: float | None = 105.50):
    mock_port = MagicMock()
    mock_port.equity = portfolio_equity
    sess = MagicMock()
    sess.__enter__ = MagicMock(return_value=sess)
    sess.__exit__ = MagicMock(return_value=False)
    sess.get.return_value = mock_port if portfolio_equity is not None else None
    return sess


# ── get_system_status ─────────────────────────────────────────────────────────

def test_get_system_status_returns_required_keys():
    with patch("database.models.SessionLocal", return_value=_mock_session()), \
         patch("database.promotion_queries.query_promotions", return_value=pd.DataFrame()), \
         patch("strategy.runtime.get_active_strategy_config",
               return_value={"name": "regime_router_v1", "version": "1.0", "params": {}}), \
         patch("database.models.init_db"):
        result = get_system_status()

    assert "active_strategy" in result
    assert "portfolio_equity_usd" in result
    assert "latest_promotion" in result
    assert "llm_enabled" in result
    assert result["portfolio_equity_usd"] == pytest.approx(105.50)


def test_get_system_status_handles_missing_portfolio():
    with patch("database.models.SessionLocal", return_value=_mock_session(None)), \
         patch("database.promotion_queries.query_promotions", return_value=pd.DataFrame()), \
         patch("strategy.runtime.get_active_strategy_config",
               return_value={"name": "regime_router_v1", "version": "1.0", "params": {}}), \
         patch("database.models.init_db"):
        result = get_system_status()

    assert result["portfolio_equity_usd"] is None


# ── get_trade_history ─────────────────────────────────────────────────────────

def test_get_trade_history_returns_empty_list_on_missing_db():
    with patch("mcp_server.tools._db_path", return_value="/nonexistent/path.db"):
        result = get_trade_history()
    assert isinstance(result, list)


def test_get_trade_history_respects_limit(tmp_path):
    db = tmp_path / "test.db"
    import sqlite3
    con = sqlite3.connect(str(db))
    con.execute(
        "CREATE TABLE trades (ts TEXT, symbol TEXT, side TEXT, qty REAL, "
        "price REAL, fee REAL, pnl REAL, strategy_name TEXT, "
        "strategy_version TEXT, run_mode TEXT, regime TEXT)"
    )
    for i in range(5):
        con.execute(
            "INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (f"2024-01-0{i+1}", "BTCUSDT", "BUY", 1.0, 50000.0, 0.1, 0.0,
             "regime_router_v1", "1.0", "paper", "TRENDING"),
        )
    con.commit()
    con.close()

    with patch("mcp_server.tools._db_path", return_value=str(db)):
        result = get_trade_history(limit=3)
    assert len(result) == 3


# ── get_backtest_runs ─────────────────────────────────────────────────────────

def test_get_backtest_runs_returns_list():
    mock_df = pd.DataFrame([{
        "id": 1, "symbol": "BTCUSDT", "strategy_name": "regime_router_v1",
        "sharpe": 1.5, "status": "passed",
    }])
    with patch("backtester.service.list_backtest_runs", return_value=mock_df):
        result = get_backtest_runs(limit=10)
    assert isinstance(result, list)
    assert result[0]["symbol"] == "BTCUSDT"


def test_get_backtest_runs_filters_by_strategy():
    mock_df = pd.DataFrame([
        {"id": 1, "symbol": "BTCUSDT", "strategy_name": "regime_router_v1", "sharpe": 1.5},
        {"id": 2, "symbol": "ETHUSDT", "strategy_name": "momentum_v1", "sharpe": 2.0},
    ])
    with patch("backtester.service.list_backtest_runs", return_value=mock_df):
        result = get_backtest_runs(strategy_name="momentum_v1")
    assert len(result) == 1
    assert result[0]["strategy_name"] == "momentum_v1"


def test_get_backtest_runs_returns_empty_list_when_no_runs():
    with patch("backtester.service.list_backtest_runs", return_value=pd.DataFrame()):
        result = get_backtest_runs()
    assert result == []


# ── get_backtest_run_detail ───────────────────────────────────────────────────

def test_get_backtest_run_detail_returns_error_for_missing_run():
    with patch("backtester.service.get_backtest_run", return_value=None), \
         patch("backtester.service.get_backtest_trades", return_value=pd.DataFrame()):
        result = get_backtest_run_detail(999)
    assert "error" in result


# ── get_strategy_catalog ──────────────────────────────────────────────────────

def test_get_strategy_catalog_returns_strategies_and_errors():
    with patch("strategy.runtime.list_available_strategies",
               return_value=[{"name": "regime_router_v1"}]), \
         patch("strategy.runtime.list_available_strategy_errors", return_value=[]):
        result = get_strategy_catalog()
    assert "strategies" in result
    assert "load_errors" in result
    assert len(result["strategies"]) == 1


# ── get_market_focus ─────────────────────────────────────────────────────────

def test_get_market_focus_returns_none_when_no_study():
    with patch("backtester.service.get_latest_market_focus", return_value=None):
        result = get_market_focus()
    assert result["study"] is None
    assert result["candidates"] == []


def test_get_market_focus_returns_study_with_candidates():
    study = {"id": 1, "strategy_name": "regime_router_v1", "status": "done"}
    candidates = [{"symbol": "BTCUSDT", "rank": 1, "score": 0.9}]
    with patch("backtester.service.get_latest_market_focus", return_value=study), \
         patch("backtester.service.get_market_focus_candidates", return_value=candidates):
        result = get_market_focus()
    assert result["study"]["id"] == 1
    assert len(result["candidates"]) == 1


# ── read_kb_file + list_kb_files ─────────────────────────────────────────────

def test_read_kb_file_returns_content(tmp_path):
    kb = tmp_path / "knowledge"
    kb.mkdir()
    (kb / "test.md").write_text("# Test\nHello")
    with patch("mcp_server.tools._kb_dir", return_value=kb):
        result = read_kb_file("test.md")
    assert "Hello" in result


def test_read_kb_file_rejects_path_traversal(tmp_path):
    kb = tmp_path / "knowledge"
    kb.mkdir()
    with patch("mcp_server.tools._kb_dir", return_value=kb):
        with pytest.raises(ValueError, match="Access denied"):
            read_kb_file("../../etc/passwd")


def test_read_kb_file_raises_on_missing(tmp_path):
    kb = tmp_path / "knowledge"
    kb.mkdir()
    with patch("mcp_server.tools._kb_dir", return_value=kb):
        with pytest.raises(FileNotFoundError):
            read_kb_file("missing.md")


def test_list_kb_files_returns_metadata(tmp_path):
    kb = tmp_path / "knowledge"
    kb.mkdir()
    (kb / "bugs.md").write_text("content")
    (kb / "learnings.md").write_text("other")
    with patch("mcp_server.tools._kb_dir", return_value=kb):
        result = list_kb_files()
    names = [r["filename"] for r in result]
    assert "bugs.md" in names
    assert "learnings.md" in names
    assert all("size_bytes" in r for r in result)


# ── write tools ───────────────────────────────────────────────────────────────

def test_run_backtest_raises_when_writes_disabled():
    with patch("mcp_server.auth.writes_allowed", return_value=False):
        with pytest.raises(ValueError, match="disabled"):
            run_backtest("BTCUSDT", "2024-01-01", "2024-03-31", "regime_router_v1")


def test_run_backtest_calls_service_when_allowed():
    mock_result = {
        "run_id": 42, "passed": True, "failures": [],
        "metrics": {"sharpe": 1.8}, "preset_name": None,
    }
    with patch("mcp_server.auth.writes_allowed", return_value=True), \
         patch("backtester.service.run_and_persist_backtest", return_value=mock_result):
        result = run_backtest("BTCUSDT", "2024-01-01", "2024-03-31", "regime_router_v1")
    assert result["run_id"] == 42
    assert result["passed"] is True


def test_save_backtest_preset_raises_when_writes_disabled():
    with patch("mcp_server.auth.writes_allowed", return_value=False):
        with pytest.raises(ValueError, match="disabled"):
            save_backtest_preset("regime_router_v1", "my_preset", {})
