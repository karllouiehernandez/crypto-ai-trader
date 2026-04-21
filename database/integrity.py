"""Persistence integrity helpers for trader-facing audit surfaces."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa

from config import POSITION_SIZE_PCT, STARTING_BALANCE_USD
from database.models import BacktestRun, BacktestTrade, Trade

VALID_STATUS = "valid"
LEGACY_INVALID_STATUS = "legacy-invalid"
MISSING_TRADES_STATUS = "missing-trades"
INVALID_METRICS_STATUS = "invalid-metrics"
ARCHIVED_LEGACY_STATUS = "archived-legacy"

# Integrity statuses the release-gate checks should flag as PARTIAL.
LEGACY_CONTAINED_STATUSES: frozenset[str] = frozenset(
    {LEGACY_INVALID_STATUS, INVALID_METRICS_STATUS, MISSING_TRADES_STATUS}
)

_ARCHIVE_NOTE_PREFIX = "[archived-legacy]"


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
    """Tag legacy-null rows so UI and checks can distinguish contained history from fresh writes.

    Rows already tagged as ``archived-legacy`` are preserved verbatim — the archive
    is an explicit, operator-applied containment state and must not regress back to
    ``legacy-invalid`` on subsequent refreshes.
    """
    updates = {"backtest_runs": 0, "trades": 0}

    if retag_existing:
        run_filter = sa.or_(
            BacktestRun.integrity_status.is_(None),
            BacktestRun.integrity_status != ARCHIVED_LEGACY_STATUS,
        )
    else:
        run_filter = BacktestRun.integrity_status.is_(None)
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
    trades = (
        session.execute(
            sa.select(Trade)
            .order_by(Trade.symbol.asc(), Trade.ts.asc(), Trade.id.asc())
        )
        .scalars()
        .all()
    )

    prev_side_by_symbol: dict[str, str] = {}
    for trade in trades:
        symbol = str(trade.symbol or "")
        status = str(trade.integrity_status or "").strip().lower()
        side = str(trade.side or "").upper()

        if status == ARCHIVED_LEGACY_STATUS:
            # Archived fixture rows are historical barriers. They should stay archived
            # and should not cause later active rows to be retagged across the gap.
            prev_side_by_symbol.pop(symbol, None)
            continue

        if not retag_existing and trade.integrity_status is not None:
            prev_side_by_symbol[symbol] = side
            continue

        notes: list[str] = []
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


def count_archivable_legacy_rows(session) -> dict[str, int]:
    """Return counts of rows currently eligible for archive (but not yet archived)."""
    trade_count = (
        session.execute(
            sa.select(sa.func.count(Trade.id))
            .where(Trade.integrity_status.in_(tuple(LEGACY_CONTAINED_STATUSES)))
        ).scalar()
        or 0
    )
    run_count = (
        session.execute(
            sa.select(sa.func.count(BacktestRun.id))
            .where(BacktestRun.integrity_status.in_(tuple(LEGACY_CONTAINED_STATUSES)))
        ).scalar()
        or 0
    )
    return {"trades": int(trade_count), "backtest_runs": int(run_count)}


def count_archived_legacy_rows(session) -> dict[str, int]:
    """Return counts of rows already containment-archived."""
    trade_count = (
        session.execute(
            sa.select(sa.func.count(Trade.id))
            .where(Trade.integrity_status == ARCHIVED_LEGACY_STATUS)
        ).scalar()
        or 0
    )
    run_count = (
        session.execute(
            sa.select(sa.func.count(BacktestRun.id))
            .where(BacktestRun.integrity_status == ARCHIVED_LEGACY_STATUS)
        ).scalar()
        or 0
    )
    return {"trades": int(trade_count), "backtest_runs": int(run_count)}


def _archive_note(prior_status: Any, prior_note: Any, *, ts: str) -> str:
    prior_status_str = str(prior_status or "unknown")
    prior_note_str = str(prior_note or "").strip()
    parts = [f"{_ARCHIVE_NOTE_PREFIX} archived {ts} (prior_status={prior_status_str})"]
    if prior_note_str:
        parts.append(prior_note_str)
    return " | ".join(parts)


def archive_legacy_integrity_rows(session) -> dict[str, int]:
    """Containment-archive all currently legacy-invalid rows.

    Moves every Trade / BacktestRun row whose ``integrity_status`` is in
    ``LEGACY_CONTAINED_STATUSES`` into ``archived-legacy``, prefixes the
    ``integrity_note`` with an ``[archived-legacy]`` marker and a UTC timestamp,
    and preserves the prior status inside the note so the action is reversible.
    Returns the number of rows archived per table.
    """
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    trades = (
        session.execute(
            sa.select(Trade)
            .where(Trade.integrity_status.in_(tuple(LEGACY_CONTAINED_STATUSES)))
        )
        .scalars()
        .all()
    )
    for trade in trades:
        trade.integrity_note = _archive_note(trade.integrity_status, trade.integrity_note, ts=ts)
        trade.integrity_status = ARCHIVED_LEGACY_STATUS

    runs = (
        session.execute(
            sa.select(BacktestRun)
            .where(BacktestRun.integrity_status.in_(tuple(LEGACY_CONTAINED_STATUSES)))
        )
        .scalars()
        .all()
    )
    for run in runs:
        run.integrity_note = _archive_note(run.integrity_status, run.integrity_note, ts=ts)
        run.integrity_status = ARCHIVED_LEGACY_STATUS

    updates = {"trades": len(trades), "backtest_runs": len(runs)}
    if updates["trades"] or updates["backtest_runs"]:
        session.commit()
    return updates


def unarchive_legacy_integrity_rows(session) -> dict[str, int]:
    """Reverse the containment archive by re-running integrity classification.

    Rows tagged ``archived-legacy`` are temporarily reset to ``None`` so that
    :func:`refresh_integrity_flags` will reclassify them against the current rules
    and return them to ``legacy-invalid`` (or ``valid``, or the appropriate
    backtest-run status). The archive note marker is stripped from the note.
    Returns per-table counts of rows that were reverted.
    """
    trades = (
        session.execute(
            sa.select(Trade)
            .where(Trade.integrity_status == ARCHIVED_LEGACY_STATUS)
        )
        .scalars()
        .all()
    )
    for trade in trades:
        trade.integrity_status = None
        trade.integrity_note = None

    runs = (
        session.execute(
            sa.select(BacktestRun)
            .where(BacktestRun.integrity_status == ARCHIVED_LEGACY_STATUS)
        )
        .scalars()
        .all()
    )
    for run in runs:
        run.integrity_status = None
        run.integrity_note = None

    reverted = {"trades": len(trades), "backtest_runs": len(runs)}
    if reverted["trades"] or reverted["backtest_runs"]:
        session.commit()
        # Use retag_existing=True so sequence detection sees all non-archived rows
        # in symbol/ts order and classifies the just-reverted rows correctly.
        refresh_integrity_flags(session, retag_existing=True)
    return reverted


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
        ARCHIVED_LEGACY_STATUS: "Archived Legacy",
    }
    return mapping.get(raw, raw.replace("-", " ").title() or "Unknown")
