"""
trading_diary/service.py

Core service: create, query, and summarise Trading Diary entries.
All functions are synchronous, matching the existing backtester/service.py pattern.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from database.models import SessionLocal, TradingDiaryEntry, Trade, init_db
from trading_diary.backtest_insights import extract_backtest_insights


# ── Creation ──────────────────────────────────────────────────────────────────

def record_trade_diary_entry(trade: Trade) -> TradingDiaryEntry:
    """Auto-generate a diary entry for one completed paper/live trade.

    Called from paper_trader._record_trade() after the Trade is committed.
    BUY entries: note symbol, price, regime, strategy.
    SELL entries: note WIN/LOSS/FLAT, percentage move, regime.
    """
    init_db()
    side   = str(trade.side or "").upper()
    regime = str(trade.regime or "UNKNOWN").upper()
    pnl    = float(trade.pnl or 0.0)
    price  = float(trade.price or 0.0)
    qty    = float(trade.qty or 0.0)

    if side == "BUY":
        content = (
            f"BUY {trade.symbol} — entered at {price:.4f} "
            f"(qty {qty:.6f}) in {regime} regime via {trade.strategy_name or 'unknown'}. "
            f"Mode: {trade.run_mode or 'paper'}."
        )
        pnl_sign = "neutral"
        entry_pnl = None
    else:
        if pnl > 0:
            pnl_sign = "win"
            verdict  = f"WIN +{pnl:.4f}"
        elif pnl < 0:
            pnl_sign = "loss"
            verdict  = f"LOSS {pnl:.4f}"
        else:
            pnl_sign = "flat"
            verdict  = "FLAT"
        notional = price * qty
        content = (
            f"SELL {trade.symbol} — exited at {price:.4f} "
            f"(qty {qty:.6f}, notional {notional:.2f}) in {regime} regime. "
            f"Realised PnL: {verdict}. "
            f"Strategy: {trade.strategy_name or 'unknown'}. "
            f"Mode: {trade.run_mode or 'paper'}."
        )
        entry_pnl = pnl

    tags = json.dumps([
        f"side:{side.lower()}",
        f"regime:{regime.lower()}",
        f"run_mode:{trade.run_mode or 'paper'}",
        f"pnl_sign:{pnl_sign}",
    ])

    entry = TradingDiaryEntry(
        created_at=datetime.now(tz=timezone.utc),
        entry_type="trade",
        run_mode=trade.run_mode,
        symbol=trade.symbol,
        strategy_name=trade.strategy_name,
        trade_id=trade.id,
        backtest_run_id=None,
        content=content,
        tags=tags,
        pnl=entry_pnl,
        outcome_rating=None,
        learnings=None,
        strategy_suggestion=None,
    )

    with SessionLocal() as sess:
        sess.add(entry)
        sess.commit()

    return entry


def record_backtest_insight(run_result: dict[str, Any]) -> TradingDiaryEntry:
    """Auto-generate a diary entry from a completed backtest run result dict.

    Called from backtester/service.py run_and_persist_backtest() after sess.commit().
    """
    init_db()
    trades_df = run_result.get("trades", pd.DataFrame())
    if not isinstance(trades_df, pd.DataFrame):
        trades_df = pd.DataFrame()

    symbol        = run_result.get("symbol", "")
    strategy_name = run_result.get("strategy_name", "")
    run_id        = run_result.get("run_id")
    passed        = run_result.get("passed", False)
    failures      = run_result.get("failures", []) or []

    content = extract_backtest_insights(run_result, trades_df)

    tags = json.dumps([
        f"strategy:{strategy_name}",
        f"symbol:{symbol}",
        f"verdict:{'passed' if passed else 'failed'}",
        *[f"failure:{str(f)[:40]}" for f in failures],
    ])

    entry = TradingDiaryEntry(
        created_at=datetime.now(tz=timezone.utc),
        entry_type="backtest_insight",
        run_mode=None,
        symbol=symbol or None,
        strategy_name=strategy_name or None,
        trade_id=None,
        backtest_run_id=run_id,
        content=content,
        tags=tags,
        pnl=None,
        outcome_rating=None,
        learnings=None,
        strategy_suggestion=None,
    )

    with SessionLocal() as sess:
        sess.add(entry)
        sess.commit()

    return entry


def record_session_summary(run_mode: str) -> TradingDiaryEntry:
    """Summarise the last 50 SELL trades for run_mode and persist as session_summary."""
    init_db()
    with SessionLocal() as sess:
        rows = (
            sess.query(Trade)
            .filter(Trade.run_mode == run_mode, Trade.side == "SELL")
            .order_by(Trade.ts.desc())
            .limit(50)
            .all()
        )

    if not rows:
        content = f"Session summary for {run_mode}: no completed trades on record."
        tags    = json.dumps([f"run_mode:{run_mode}", "summary:empty"])
    else:
        pnls      = [float(r.pnl or 0) for r in rows]
        wins      = [p for p in pnls if p > 0]
        losses    = [p for p in pnls if p <= 0]
        total     = len(pnls)
        win_rate  = len(wins) / total if total else 0.0
        total_pnl = sum(pnls)
        best_pnl  = max(pnls) if pnls else 0.0
        worst_pnl = min(pnls) if pnls else 0.0

        strat_pnl: dict[str, float] = defaultdict(float)
        for r in rows:
            strat_pnl[str(r.strategy_name or "unknown")] += float(r.pnl or 0)
        best_strategy = max(strat_pnl, key=lambda k: strat_pnl[k]) if strat_pnl else "N/A"

        content = (
            f"Session summary ({run_mode}) — last {total} completed trades:\n"
            f"- Win rate: {win_rate:.1%} ({len(wins)} wins / {len(losses)} losses)\n"
            f"- Total realised PnL: {total_pnl:+.4f}\n"
            f"- Best trade: {best_pnl:+.4f}  |  Worst trade: {worst_pnl:+.4f}\n"
            f"- Best strategy by PnL: {best_strategy} ({strat_pnl.get(best_strategy, 0):+.4f})"
        )
        tags = json.dumps([
            f"run_mode:{run_mode}",
            "summary:session",
            f"win_rate:{win_rate:.2f}",
        ])

    entry = TradingDiaryEntry(
        created_at=datetime.now(tz=timezone.utc),
        entry_type="session_summary",
        run_mode=run_mode,
        symbol=None,
        strategy_name=None,
        trade_id=None,
        backtest_run_id=None,
        content=content,
        tags=tags,
        pnl=None,
        outcome_rating=None,
        learnings=None,
        strategy_suggestion=None,
    )

    with SessionLocal() as sess:
        sess.add(entry)
        sess.commit()

    return entry


# ── Query ─────────────────────────────────────────────────────────────────────

def list_diary_entries(
    run_mode: str | None = None,
    symbol: str | None = None,
    strategy: str | None = None,
    entry_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return diary entries matching the given filters, newest first."""
    init_db()
    with SessionLocal() as sess:
        query = sess.query(TradingDiaryEntry)
        if run_mode:
            query = query.filter(TradingDiaryEntry.run_mode == run_mode)
        if symbol:
            query = query.filter(TradingDiaryEntry.symbol == symbol)
        if strategy:
            query = query.filter(TradingDiaryEntry.strategy_name == strategy)
        if entry_type:
            query = query.filter(TradingDiaryEntry.entry_type == entry_type)
        rows = query.order_by(TradingDiaryEntry.created_at.desc()).limit(limit).all()

    return [_entry_to_dict(row) for row in rows]


def update_diary_entry(
    entry_id: int,
    learnings: str,
    strategy_suggestion: str,
    outcome_rating: int,
) -> dict[str, Any]:
    """Update operator-supplied fields on an existing diary entry."""
    init_db()
    with SessionLocal() as sess:
        entry = sess.get(TradingDiaryEntry, entry_id)
        if entry is None:
            raise ValueError(f"TradingDiaryEntry id={entry_id} not found")
        if learnings is not None:
            entry.learnings = str(learnings).strip() or None
        if strategy_suggestion is not None:
            entry.strategy_suggestion = str(strategy_suggestion).strip() or None
        if outcome_rating is not None:
            rating = int(outcome_rating)
            if not (1 <= rating <= 5):
                raise ValueError(f"outcome_rating must be 1-5, got {rating}")
            entry.outcome_rating = rating
        sess.commit()
        return _entry_to_dict(entry)


def get_trading_summary(run_mode: str | None = None) -> dict[str, Any]:
    """Return aggregate trading statistics across paper/live trade entries."""
    init_db()
    with SessionLocal() as sess:
        query = sess.query(TradingDiaryEntry).filter(TradingDiaryEntry.entry_type == "trade")
        if run_mode:
            query = query.filter(TradingDiaryEntry.run_mode == run_mode)
        rows = query.all()

    sell_entries = [r for r in rows if r.pnl is not None]

    if not sell_entries:
        return {
            "total_trades": 0, "win_count": 0, "loss_count": 0,
            "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0,
            "best_pnl": 0.0, "worst_pnl": 0.0,
            "best_strategy": None, "worst_strategy": None,
            "best_symbol": None, "worst_symbol": None,
            "by_strategy": {}, "by_symbol": {}, "by_regime": {},
        }

    pnls      = [float(r.pnl) for r in sell_entries]
    wins      = [p for p in pnls if p > 0]
    total     = len(pnls)
    total_pnl = sum(pnls)

    by_strategy: dict[str, dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "total_pnl": 0.0})
    by_symbol:   dict[str, dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "total_pnl": 0.0})
    by_regime:   dict[str, dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "total_pnl": 0.0})

    for entry in sell_entries:
        p = float(entry.pnl)

        strat = str(entry.strategy_name or "unknown")
        by_strategy[strat]["trades"]    += 1
        by_strategy[strat]["total_pnl"] += p
        if p > 0:
            by_strategy[strat]["wins"] += 1

        sym = str(entry.symbol or "unknown")
        by_symbol[sym]["trades"]    += 1
        by_symbol[sym]["total_pnl"] += p
        if p > 0:
            by_symbol[sym]["wins"] += 1

        regime = _extract_tag(entry.tags, "regime")
        by_regime[regime]["trades"]    += 1
        by_regime[regime]["total_pnl"] += p
        if p > 0:
            by_regime[regime]["wins"] += 1

    best_strategy  = max(by_strategy, key=lambda k: by_strategy[k]["total_pnl"])  if by_strategy  else None
    worst_strategy = min(by_strategy, key=lambda k: by_strategy[k]["total_pnl"])  if by_strategy  else None
    best_symbol    = max(by_symbol,   key=lambda k: by_symbol[k]["total_pnl"])     if by_symbol    else None
    worst_symbol   = min(by_symbol,   key=lambda k: by_symbol[k]["total_pnl"])     if by_symbol    else None

    return {
        "total_trades":   total,
        "win_count":      len(wins),
        "loss_count":     total - len(wins),
        "win_rate":       len(wins) / total if total else 0.0,
        "total_pnl":      total_pnl,
        "avg_pnl":        total_pnl / total if total else 0.0,
        "best_pnl":       max(pnls),
        "worst_pnl":      min(pnls),
        "best_strategy":  best_strategy,
        "worst_strategy": worst_strategy,
        "best_symbol":    best_symbol,
        "worst_symbol":   worst_symbol,
        "by_strategy":    dict(by_strategy),
        "by_symbol":      dict(by_symbol),
        "by_regime":      dict(by_regime),
    }


# ── Private ───────────────────────────────────────────────────────────────────

def _entry_to_dict(entry: TradingDiaryEntry) -> dict[str, Any]:
    tags_raw = entry.tags or "[]"
    try:
        tags = json.loads(tags_raw)
    except (json.JSONDecodeError, TypeError):
        tags = []
    return {
        "id":                  entry.id,
        "created_at":          entry.created_at,
        "entry_type":          entry.entry_type,
        "run_mode":            entry.run_mode,
        "symbol":              entry.symbol,
        "strategy_name":       entry.strategy_name,
        "trade_id":            entry.trade_id,
        "backtest_run_id":     entry.backtest_run_id,
        "content":             entry.content,
        "tags":                tags,
        "pnl":                 entry.pnl,
        "outcome_rating":      entry.outcome_rating,
        "learnings":           entry.learnings,
        "strategy_suggestion": entry.strategy_suggestion,
    }


def _extract_tag(tags_json: str | None, prefix: str) -> str:
    """Return the value portion of the first tag matching 'prefix:value'."""
    if not tags_json:
        return "unknown"
    try:
        tags = json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return "unknown"
    for tag in tags:
        if str(tag).startswith(f"{prefix}:"):
            return str(tag).split(":", 1)[1]
    return "unknown"
