"""Persistence integrity helpers for trader-facing audit surfaces."""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa

from config import POSITION_SIZE_PCT, STARTING_BALANCE_USD
from database.models import BacktestRun, BacktestTrade, Trade

VALID_STATUS = "valid"
LEGACY_INVALID_STATUS = "legacy-invalid"
MISSING_TRADES_STATUS = "missing-trades"
INVALID_METRICS_STATUS = "invalid-metrics"


def assess_backtest_run_integrity(metrics_json: str | None, trade_count: int) -> tuple[str, str | None]:
    """Return a stable integrity status for one persisted backtest run."""
    try:
        metrics = json.loads(metrics_json or "{}")
    except Exception:
        return INVALID_METRICS_STATUS, "Saved metrics_json is not valid JSON."

    if not isinstance(metrics, dict):
        return INVALID_METRICS_STATUS, "Saved metrics_json is not a JSON object."

    expected_trades = metrics.get("n_trades", metrics.get("num_trades"))
    try:
        expected_trades = int(expected_trades) if expected_trades is not None else None
    except (TypeError, ValueError):
        expected_trades = None

    if (expected_trades or 0) > 0 and int(trade_count or 0) == 0:
        return MISSING_TRADES_STATUS, "Saved run reports trades but no backtest trade rows were persisted."

    return VALID_STATUS, None


def refresh_integrity_flags(session, *, retag_existing: bool = False) -> dict[str, int]:
    """Tag legacy-null rows so UI and checks can distinguish contained history from fresh writes."""
    updates = {"backtest_runs": 0, "trades": 0}

    run_filter = sa.true() if retag_existing else BacktestRun.integrity_status.is_(None)
    runs = (
        session.execute(
            sa.select(BacktestRun)
            .where(run_filter)
            .order_by(BacktestRun.id.asc())
        )
        .scalars()
        .all()
    )
    for run in runs:
        trade_count = (
            session.execute(
                sa.select(sa.func.count(BacktestTrade.id))
                .where(BacktestTrade.run_id == run.id)
            ).scalar()
            or 0
        )
        status, note = assess_backtest_run_integrity(run.metrics_json, int(trade_count))
        run.integrity_status = status
        run.integrity_note = note
        updates["backtest_runs"] += 1

    max_notional = float(POSITION_SIZE_PCT) * float(STARTING_BALANCE_USD)
    trade_filter = sa.true() if retag_existing else Trade.integrity_status.is_(None)
    trades = (
        session.execute(
            sa.select(Trade)
            .where(trade_filter)
            .order_by(Trade.symbol.asc(), Trade.ts.asc(), Trade.id.asc())
        )
        .scalars()
        .all()
    )

    prev_side_by_symbol: dict[str, str] = {}
    for trade in trades:
        notes: list[str] = []
        side = str(trade.side or "").upper()
        symbol = str(trade.symbol or "")
        if prev_side_by_symbol.get(symbol) == side and side in {"BUY", "SELL"}:
            notes.append(f"Consecutive same-side sequence detected: {side}->{side}.")
        if side == "BUY":
            notional = float(trade.price or 0.0) * float(trade.qty or 0.0)
            if notional > max_notional * 1.05:
                notes.append(
                    f"BUY notional {notional:.2f} exceeded max size {max_notional:.2f}."
                )
        trade.integrity_status = LEGACY_INVALID_STATUS if notes else VALID_STATUS
        trade.integrity_note = " ".join(notes) if notes else None
        prev_side_by_symbol[symbol] = side
        updates["trades"] += 1

    if updates["backtest_runs"] or updates["trades"]:
        session.commit()

    return updates


def repair_legacy_integrity_rows() -> dict[str, int]:
    """Re-scan the existing DB and reclassify current invalid history as legacy-contained."""
    from database.models import SessionLocal, init_db

    init_db()
    with SessionLocal() as sess:
        return refresh_integrity_flags(sess, retag_existing=True)


def integrity_label(status: Any) -> str:
    raw = str(status or VALID_STATUS).strip().lower()
    mapping = {
        VALID_STATUS: "Valid",
        LEGACY_INVALID_STATUS: "Legacy Invalid",
        MISSING_TRADES_STATUS: "Missing Trades",
        INVALID_METRICS_STATUS: "Invalid Metrics",
    }
    return mapping.get(raw, raw.replace("-", " ").title() or "Unknown")
