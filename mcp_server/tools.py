"""MCP tool handlers — thin adapters over existing service functions.

All imports are lazy (inside each function) to avoid circular imports and to
keep the module importable in tests without triggering DB initialisation.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp_server.auth import check_write_gate


# ── helpers ───────────────────────────────────────────────────────────────────

def _db_path() -> str:
    from config import DB_PATH
    return str(DB_PATH)


def _kb_dir() -> Path:
    from config import BASE_DIR
    return BASE_DIR / "knowledge"


def _rows_to_dicts(rows: list) -> list[dict]:
    return [dict(r) for r in rows]


def _serialise_datetimes(d: dict) -> dict:
    return {k: v.isoformat() if isinstance(v, datetime) else v for k, v in d.items()}


# ── read tools ────────────────────────────────────────────────────────────────

def get_system_status() -> dict[str, Any]:
    """Return current system state: portfolio equity, active strategy, latest promotion."""
    from database.models import SessionLocal, Portfolio, init_db
    from database.promotion_queries import query_promotions
    from strategy.runtime import get_active_strategy_config

    init_db()
    active = get_active_strategy_config()

    portfolio_equity = None
    with SessionLocal() as sess:
        port = sess.get(Portfolio, 1)
        if port:
            portfolio_equity = port.equity

    promotions_df = query_promotions(_db_path())
    latest_promotion = None
    if not promotions_df.empty:
        row = promotions_df.iloc[0]
        latest_promotion = {
            "ts": str(row.get("ts", "")),
            "sharpe": float(row.get("sharpe", 0) or 0),
            "confidence_score": float(row.get("confidence_score", 0) or 0),
            "recommendation": str(row.get("recommendation", "")),
        }

    return {
        "active_strategy": active,
        "portfolio_equity_usd": portfolio_equity,
        "latest_promotion": latest_promotion,
        "llm_enabled": os.environ.get("LLM_ENABLED", "true").lower() == "true",
        "live_trade_enabled": os.environ.get("LIVE_TRADE_ENABLED", "false").lower() == "true",
    }


def get_trade_history(
    symbol: str | None = None,
    run_mode: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return recent paper/live trades with P&L, regime, and strategy."""
    clauses: list[str] = []
    params: list[Any] = []
    if symbol:
        clauses.append("symbol = ?")
        params.append(symbol)
    if run_mode:
        clauses.append("run_mode = ?")
        params.append(run_mode)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        f"SELECT ts, symbol, side, qty, price, fee, pnl, "
        f"strategy_name, strategy_version, run_mode, regime "
        f"FROM trades {where} ORDER BY ts DESC LIMIT ?"
    )
    params.append(limit)
    try:
        con = sqlite3.connect(_db_path())
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, params).fetchall()
        con.close()
        return _rows_to_dicts(rows)
    except Exception:
        return []


def get_portfolio_equity(limit: int = 100) -> list[dict[str, Any]]:
    """Return portfolio snapshot time series (chronological order)."""
    sql = (
        "SELECT ts, run_mode, strategy_name, balance, equity, unreal_pnl "
        "FROM portfolio_snapshots ORDER BY ts DESC LIMIT ?"
    )
    try:
        con = sqlite3.connect(_db_path())
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, [limit]).fetchall()
        con.close()
        return list(reversed(_rows_to_dicts(rows)))
    except Exception:
        return []


def get_backtest_runs(
    strategy_name: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return saved backtest results with parsed metrics."""
    from backtester.service import list_backtest_runs

    df = list_backtest_runs(limit=limit)
    if df.empty:
        return []
    if strategy_name:
        df = df[df["strategy_name"] == strategy_name]
    for col in df.select_dtypes(include=["datetime64[ns, UTC]", "datetime64[ns]"]).columns:
        df[col] = df[col].astype(str)
    return df.to_dict(orient="records")


def get_backtest_run_detail(run_id: int) -> dict[str, Any]:
    """Return a single backtest run with its full trade list."""
    from backtester.service import get_backtest_run, get_backtest_trades

    run = get_backtest_run(run_id)
    if run is None:
        return {"error": f"Backtest run {run_id} not found"}
    run = _serialise_datetimes(run)

    trades_df = get_backtest_trades(run_id)
    trades: list[dict] = []
    if not trades_df.empty:
        for col in trades_df.select_dtypes(include=["datetime64[ns, UTC]", "datetime64[ns]"]).columns:
            trades_df[col] = trades_df[col].astype(str)
        trades = trades_df.to_dict(orient="records")

    return {**run, "trades": trades}


def get_strategy_catalog() -> dict[str, Any]:
    """Return all strategies (built-in and plugin) with load/validation status."""
    from strategy.runtime import list_available_strategies, list_available_strategy_errors

    return {
        "strategies": list_available_strategies(),
        "load_errors": list_available_strategy_errors(),
    }


def get_market_focus() -> dict[str, Any]:
    """Return the latest market focus study and top candidates."""
    from backtester.service import get_latest_market_focus, get_market_focus_candidates

    study = get_latest_market_focus()
    if study is None:
        return {"study": None, "candidates": []}
    study = _serialise_datetimes(study)
    candidates = get_market_focus_candidates(study["id"])
    return {"study": study, "candidates": candidates}


def get_promotions(limit: int = 10) -> list[dict[str, Any]]:
    """Return promotion gate history with confidence scores (newest first)."""
    from database.promotion_queries import query_promotions

    df = query_promotions(_db_path())
    if df.empty:
        return []
    df = df.head(limit)
    for col in df.select_dtypes(include=["datetime64[ns, UTC]", "datetime64[ns]"]).columns:
        df[col] = df[col].astype(str)
    return df.to_dict(orient="records")


def list_kb_files() -> list[dict[str, Any]]:
    """List all files in knowledge/ with names and sizes."""
    kb = _kb_dir()
    result = []
    try:
        for f in sorted(kb.iterdir()):
            if f.is_file():
                result.append({
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                })
    except FileNotFoundError:
        pass
    return result


def read_kb_file(filename: str) -> str:
    """Read a file from knowledge/. Rejects path traversal attempts."""
    kb = _kb_dir()
    target = (kb / filename).resolve()
    if not str(target).startswith(str(kb.resolve())):
        raise ValueError(f"Access denied: {filename!r}")
    if not target.exists():
        raise FileNotFoundError(f"KB file not found: {filename!r}")
    return target.read_text(encoding="utf-8")


# ── write tools (gated by MCP_ALLOW_WRITES=true) ──────────────────────────────

def run_backtest(
    symbol: str,
    start: str,
    end: str,
    strategy_name: str,
    params: dict | None = None,
) -> dict[str, Any]:
    """Trigger a backtest run and return the run_id with summary metrics."""
    check_write_gate()
    from backtester.service import run_and_persist_backtest

    start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    result = run_and_persist_backtest(symbol, start_dt, end_dt, strategy_name, params=params)
    return {
        "run_id": result.get("run_id"),
        "passed": result.get("passed"),
        "failures": result.get("failures", []),
        "metrics": result.get("metrics", {}),
        "preset_name": result.get("preset_name"),
    }


def save_backtest_preset(
    strategy_name: str,
    preset_name: str,
    params: dict | None = None,
) -> dict[str, Any]:
    """Save or update a named backtest preset."""
    check_write_gate()
    from backtester.service import save_backtest_preset as _save

    return _save(strategy_name, preset_name, params)
