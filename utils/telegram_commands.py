"""Telegram text command handlers.

All functions are pure (no Telegram I/O) — they take arguments and return a
formatted string. The poller in telegram_utils.py calls these and sends the
result. This makes them testable without a live bot.
"""
from __future__ import annotations

import sqlite3
from typing import Any


# ── helpers ───────────────────────────────────────────────────────────────────

def _db_path() -> str:
    from config import DB_PATH
    return str(DB_PATH)


def _starting_balance() -> float:
    from config import STARTING_BALANCE_USD
    return STARTING_BALANCE_USD


def _query(sql: str, params: list | None = None) -> list[dict]:
    try:
        con = sqlite3.connect(_db_path())
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, params or []).fetchall()
        con.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ── command parser ────────────────────────────────────────────────────────────

def parse_command(text: str) -> tuple[str, list[str]]:
    """Parse '/command arg1 arg2' → ('command', ['arg1', 'arg2'])."""
    parts = text.strip().split()
    if not parts:
        return ("help", [])
    cmd = parts[0].lstrip("/").lower().split("@")[0]  # strip bot username suffix
    return (cmd, parts[1:])


# ── handlers ─────────────────────────────────────────────────────────────────

def handle_help() -> str:
    return (
        "*Crypto AI Trader — Commands*\n\n"
        "/status — portfolio equity, strategy, halt state\n"
        "/trades \\[N\\] — last N trades (default 5)\n"
        "/equity — return % and drawdown\n"
        "/strategy — active strategy + params\n"
        "/strategies — all available strategies\n"
        "/halt — stop trading remotely\n"
        "/resume — resume trading\n"
        "/buy SYMBOL — manual buy\n"
        "/sell SYMBOL — manual sell\n"
        "/backtest SYMBOL START END \\[STRATEGY\\] — run backtest\n"
        "/focus — latest market focus candidates\n"
        "/help — this message"
    )


def handle_status() -> str:
    from strategy.runtime import get_active_strategy_config

    active = get_active_strategy_config()
    rows = _query(
        "SELECT equity, balance FROM portfolio WHERE id = 1"
    )
    equity = rows[0]["equity"] if rows else None
    balance = rows[0]["balance"] if rows else None

    # daily P&L: compare today's first snapshot equity vs current
    daily_rows = _query(
        "SELECT equity FROM portfolio_snapshots "
        "WHERE date(ts) = date('now') ORDER BY ts ASC LIMIT 1"
    )
    start_equity = daily_rows[0]["equity"] if daily_rows else equity
    daily_pnl = ((equity - start_equity) / start_equity * 100) if (equity and start_equity) else None

    lines = ["*System Status*"]
    lines.append(f"Strategy: `{active.get('name', 'unknown')}`")
    if equity is not None:
        lines.append(f"Equity: *${equity:.2f}*")
    if balance is not None:
        lines.append(f"Cash: ${balance:.2f}")
    if daily_pnl is not None:
        sign = "+" if daily_pnl >= 0 else ""
        lines.append(f"Daily P&L: {sign}{daily_pnl:.2f}%")
    return "\n".join(lines)


def handle_trades(n: int = 5) -> str:
    rows = _query(
        "SELECT ts, symbol, side, price, pnl, regime, run_mode "
        "FROM trades ORDER BY ts DESC LIMIT ?",
        [n],
    )
    if not rows:
        return "No trades recorded yet."
    lines = [f"*Last {len(rows)} trades*"]
    for r in rows:
        pnl_str = f" | P&L: {r['pnl']:+.2f}" if r.get("pnl") is not None else ""
        lines.append(
            f"`{r['side']}` {r['symbol']} @ {r['price']:.2f}{pnl_str} "
            f"[{r.get('regime', '?')}]"
        )
    return "\n".join(lines)


def handle_equity() -> str:
    start = _starting_balance()
    rows = _query("SELECT equity FROM portfolio WHERE id = 1")
    if not rows or rows[0]["equity"] is None:
        return "No portfolio data yet."
    equity = rows[0]["equity"]
    ret_pct = (equity - start) / start * 100

    # max drawdown from snapshots
    snap_rows = _query("SELECT equity FROM portfolio_snapshots ORDER BY ts ASC")
    max_dd_pct = 0.0
    if snap_rows:
        peak = start
        for r in snap_rows:
            e = r["equity"] or 0
            if e > peak:
                peak = e
            dd = (peak - e) / peak * 100 if peak > 0 else 0
            if dd > max_dd_pct:
                max_dd_pct = dd

    sign = "+" if ret_pct >= 0 else ""
    return (
        f"*Portfolio Equity*\n"
        f"Start: ${start:.2f}\n"
        f"Current: *${equity:.2f}*\n"
        f"Return: {sign}{ret_pct:.2f}%\n"
        f"Max Drawdown: -{max_dd_pct:.2f}%"
    )


def handle_strategy() -> str:
    from strategy.runtime import get_active_strategy_config, list_available_strategies

    active = get_active_strategy_config()
    name = active.get("name", "unknown")
    version = active.get("version", "?")
    params = active.get("params") or {}

    catalog = {s["name"]: s for s in list_available_strategies()}
    meta = catalog.get(name, {})
    desc = meta.get("description", "")

    lines = [f"*Active Strategy*", f"`{name}` v{version}"]
    if desc:
        lines.append(desc)
    if params:
        param_str = ", ".join(f"{k}={v}" for k, v in list(params.items())[:5])
        lines.append(f"Params: {param_str}")
    return "\n".join(lines)


def handle_strategies() -> str:
    from strategy.runtime import list_available_strategies

    strategies = list_available_strategies()
    if not strategies:
        return "No strategies loaded."
    lines = ["*Available Strategies*"]
    for s in strategies:
        src = s.get("source", "?")
        lines.append(f"• `{s['name']}` ({src})")
    return "\n".join(lines)


def handle_backtest(symbol: str, start: str, end: str, strategy_name: str | None = None) -> str:
    """Run a backtest synchronously and return a summary string."""
    from datetime import timezone
    from datetime import datetime as dt
    from backtester.service import run_and_persist_backtest
    from strategy.runtime import get_active_strategy_config

    strat = strategy_name or get_active_strategy_config().get("name", "regime_router_v1")
    try:
        start_dt = dt.fromisoformat(start).replace(tzinfo=timezone.utc)
        end_dt = dt.fromisoformat(end).replace(tzinfo=timezone.utc)
    except ValueError:
        return f"Invalid dates. Use: /backtest {symbol} YYYY-MM-DD YYYY-MM-DD"

    try:
        result = run_and_persist_backtest(symbol, start_dt, end_dt, strat)
    except Exception as e:
        return f"Backtest failed: {e}"

    m = result.get("metrics", {})
    passed = "✅ PASSED" if result.get("passed") else "❌ FAILED"
    failures = result.get("failures", [])
    lines = [
        f"*Backtest Result* — {symbol} | {strat}",
        f"{start} → {end}",
        f"Status: {passed}",
        f"Sharpe: {m.get('sharpe', 0):.2f} | MaxDD: {m.get('max_drawdown', 0)*100:.1f}% "
        f"| PF: {m.get('profit_factor', 0):.2f} | Trades: {m.get('n_trades', 0)}",
    ]
    if failures:
        lines.append("Failures: " + ", ".join(failures))
    return "\n".join(lines)


def handle_focus() -> str:
    from backtester.service import get_latest_market_focus, get_market_focus_candidates

    study = get_latest_market_focus()
    if study is None:
        return "No market focus study has been run yet. Use the dashboard to trigger one."

    candidates = get_market_focus_candidates(study["id"])
    if not candidates:
        return "Market focus study found no candidates."

    lines = [f"*Market Focus* — top {len(candidates)} picks"]
    for c in candidates[:5]:
        score = c.get("score") or 0
        sharpe = c.get("sharpe") or 0
        lines.append(f"{c['rank']}. `{c['symbol']}` score={score:.2f} sharpe={sharpe:.2f}")
    return "\n".join(lines)


# ── router ────────────────────────────────────────────────────────────────────

def format_command_response(command: str, args: list[str]) -> str:
    """Route a parsed command to its handler and return the response string."""
    try:
        if command in ("help", "start"):
            return handle_help()

        if command == "status":
            return handle_status()

        if command == "trades":
            n = int(args[0]) if args else 5
            return handle_trades(n)

        if command == "equity":
            return handle_equity()

        if command == "strategy":
            return handle_strategy()

        if command == "strategies":
            return handle_strategies()

        if command == "focus":
            return handle_focus()

        if command == "backtest":
            if len(args) < 3:
                return "Usage: /backtest SYMBOL YYYY-MM-DD YYYY-MM-DD [STRATEGY]"
            symbol, start, end = args[0], args[1], args[2]
            strategy_name = args[3] if len(args) > 3 else None
            return handle_backtest(symbol, start, end, strategy_name)

        # halt/resume/buy/sell are handled via CALLBACK_QUEUE in telegram_utils.py
        if command in ("halt", "resume", "buy", "sell"):
            return f"Command /{command} received — processing..."

        return f"Unknown command: /{command}\nSend /help for the full list."

    except Exception as e:
        return f"Error handling /{command}: {e}"
