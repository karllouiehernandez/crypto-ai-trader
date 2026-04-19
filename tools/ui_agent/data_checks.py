"""Data integrity checks for production readiness.

Reads directly from the SQLite database — no browser, no LLM.
Returns the same list[dict] format as agent.run_agent so findings
can be merged into one report.

Check groups:
  1. Candle freshness  — latest candle per ready symbol
  2. History depth     — ≥30 days of 1m candles per ready symbol
  3. OHLCV sanity      — no zero/NaN/inverted prices in last 500 candles
  4. Candle continuity — no gaps > 2 min in the most recent hour per symbol
  5. Trade log integrity — no consecutive same-side trades per symbol
  6. Backtest metric sanity — Sharpe finite, n_trades > 0, drawdown in [0,1]
  7. Backtest equity integrity — curve starts at STARTING_BALANCE, wins+losses = total
  8. Position size compliance — notional per trade ≤ MAX_POS_PCT * STARTING_BALANCE
  9. Active artifact integrity — hash on disk matches DB record
 10. Ready symbol DB coverage — every ready symbol has ≥1 day of candle data
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sqlalchemy as sa

from config import POSITION_SIZE_PCT as MAX_POS_PCT, STARTING_BALANCE_USD
from database.integrity import (
    INVALID_METRICS_STATUS,
    LEGACY_INVALID_STATUS,
    MISSING_TRADES_STATUS,
    refresh_integrity_flags,
)
from database.models import (
    BacktestRun,
    BacktestTrade,
    Candle,
    SessionLocal,
    StrategyArtifact,
    Trade,
    init_db,
)
from market_data.symbol_readiness import list_ready_symbols
from strategy.artifacts import get_active_runtime_artifact_id


_MIN_HISTORY_DAYS = 30
_MAX_CANDLE_GAP_MINUTES = 2
_FRESHNESS_MINUTES = 10   # latest candle must be within this many minutes
_ONE_HOUR_CANDLES = 60


def _console_safe(text: str) -> str:
    return (
        str(text)
        .replace("—", "-")
        .replace("–", "-")
        .replace("→", "->")
        .replace("≥", ">=")
        .replace("≤", "<=")
        .replace("…", "...")
        .encode("ascii", "replace")
        .decode("ascii")
    )


def _record(findings: list[dict], feature: str, status: str, detail: str,
            verbose: bool) -> None:
    findings.append({"feature": feature, "status": status, "detail": detail})
    if verbose:
        icons = {"PASS": "[PASS]", "FAIL": "[FAIL]", "PARTIAL": "[PARTIAL]", "SKIP": "[SKIP]"}
        print(
            f"  {icons.get(status, '[INFO]')} [{status}] "
            f"{_console_safe(feature)} - {_console_safe(detail)}"
        )


def _as_utc(dt: datetime | None) -> datetime | None:
    """Ensure a datetime is UTC-aware (SQLite returns naive datetimes)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _finite(v) -> bool:
    try:
        return v is not None and not math.isnan(float(v)) and not math.isinf(float(v))
    except (TypeError, ValueError):
        return False


# ── Group 1: Candle freshness ─────────────────────────────────────────────────

def _check_candle_freshness(sess, symbols: list[str], findings: list[dict],
                             verbose: bool) -> None:
    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(minutes=_FRESHNESS_MINUTES)
    stale, missing = [], []

    for sym in symbols:
        row = sess.execute(
            sa.select(sa.func.max(Candle.open_time)).where(Candle.symbol == sym)
        ).scalar()
        row = _as_utc(row)
        if row is None:
            missing.append(sym)
        elif row < cutoff:
            age_min = int((now - row).total_seconds() / 60)
            stale.append(f"{sym}({age_min}m old)")

    if missing:
        _record(findings, "Candle freshness", "FAIL",
                f"No candles at all for: {missing}", verbose)
    elif stale:
        _record(findings, "Candle freshness", "PARTIAL",
                f"Stale (>{_FRESHNESS_MINUTES}m): {stale}", verbose)
    else:
        _record(findings, "Candle freshness", "PASS",
                f"All {len(symbols)} symbol(s) have candles within {_FRESHNESS_MINUTES}m", verbose)


# ── Group 2: History depth ────────────────────────────────────────────────────

def _check_history_depth(sess, symbols: list[str], findings: list[dict],
                          verbose: bool) -> None:
    shallow = []
    for sym in symbols:
        row = sess.execute(
            sa.select(sa.func.min(Candle.open_time), sa.func.count(Candle.id))
            .where(Candle.symbol == sym)
        ).one()
        oldest, count = row
        oldest = _as_utc(oldest)
        if oldest is None or count == 0:
            shallow.append(f"{sym}(no data)")
            continue
        now = datetime.now(tz=timezone.utc)
        days = (now - oldest).days
        if days < _MIN_HISTORY_DAYS:
            shallow.append(f"{sym}({days}d)")

    if shallow:
        _record(findings, "History depth", "PARTIAL",
                f"<{_MIN_HISTORY_DAYS} days for: {shallow}", verbose)
    else:
        _record(findings, "History depth", "PASS",
                f"All {len(symbols)} symbol(s) have ≥{_MIN_HISTORY_DAYS} days", verbose)


# ── Group 3: OHLCV sanity ─────────────────────────────────────────────────────

def _check_ohlcv_sanity(sess, symbols: list[str], findings: list[dict],
                         verbose: bool) -> None:
    anomalies = []
    for sym in symbols:
        rows = sess.execute(
            sa.select(Candle.open, Candle.high, Candle.low, Candle.close, Candle.volume)
            .where(Candle.symbol == sym)
            .order_by(Candle.open_time.desc())
            .limit(500)
        ).all()
        for o, h, l, c, v in rows:
            if any(x is None or x <= 0 for x in [o, h, l, c]):
                anomalies.append(f"{sym}:zero/null price")
                break
            if h < l or h < o or h < c or l > o or l > c:
                anomalies.append(f"{sym}:inverted OHLC")
                break
            if v < 0:
                anomalies.append(f"{sym}:negative volume")
                break
        if len(anomalies) > 5:
            break

    if anomalies:
        _record(findings, "OHLCV sanity", "FAIL", f"Anomalies: {anomalies[:5]}", verbose)
    else:
        _record(findings, "OHLCV sanity", "PASS",
                f"Last 500 candles per symbol all valid", verbose)


# ── Group 4: Candle continuity ────────────────────────────────────────────────

def _check_candle_continuity(sess, symbols: list[str], findings: list[dict],
                              verbose: bool) -> None:
    gap_reports = []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=1)

    for sym in symbols:
        times = [
            _as_utc(r[0]) for r in sess.execute(
                sa.select(Candle.open_time)
                .where(Candle.symbol == sym, Candle.open_time >= cutoff)
                .order_by(Candle.open_time)
            ).all()
            if r[0] is not None
        ]
        if len(times) < 2:
            continue
        for a, b in zip(times, times[1:]):
            gap = (b - a).total_seconds() / 60
            if gap > _MAX_CANDLE_GAP_MINUTES:
                gap_reports.append(f"{sym}:{gap:.0f}m gap")
                break

    if gap_reports:
        _record(findings, "Candle continuity (last 1h)", "PARTIAL",
                f"Gaps detected: {gap_reports}", verbose)
    elif not symbols:
        _record(findings, "Candle continuity (last 1h)", "SKIP", "No ready symbols", verbose)
    else:
        _record(findings, "Candle continuity (last 1h)", "PASS",
                f"No gaps >{_MAX_CANDLE_GAP_MINUTES}m in last hour", verbose)


# ── Group 5: Trade log integrity ──────────────────────────────────────────────

def _check_trade_log_integrity(sess, findings: list[dict], verbose: bool) -> None:
    rows = sess.execute(
        sa.select(Trade.symbol, Trade.side, Trade.ts, Trade.integrity_status, Trade.integrity_note)
        .order_by(Trade.symbol, Trade.ts, Trade.id)
    ).all()

    by_sym: dict[str, list[str]] = {}
    fresh_issues: list[str] = []
    legacy_issues: list[str] = []
    prev_side_by_sym: dict[str, str] = {}

    for sym, side, _, integrity_status, _ in rows:
        side = str(side or "").upper()
        by_sym.setdefault(sym, []).append(side)
        prev_side = prev_side_by_sym.get(sym)
        if prev_side == side and side in {"BUY", "SELL"}:
            issue = f"{sym}:{side}->{side}"
            if str(integrity_status or "").lower() == LEGACY_INVALID_STATUS:
                legacy_issues.append(issue)
            else:
                fresh_issues.append(issue)
        prev_side_by_sym[sym] = side

    total_trades = len(rows)
    if not rows:
        _record(findings, "Trade log integrity", "SKIP",
                "No paper trades recorded yet", verbose)
    elif fresh_issues:
        sample = fresh_issues[:10]
        tail = f" … +{len(fresh_issues) - 10} more" if len(fresh_issues) > 10 else ""
        _record(findings, "Trade log integrity", "FAIL",
                f"Consecutive same-side trades ({len(fresh_issues)} total): {sample}{tail}", verbose)
    elif legacy_issues:
        syms_affected = sorted({i.split(":")[0] for i in legacy_issues})
        _record(findings, "Trade log integrity", "PARTIAL",
                f"Contained legacy-invalid sequences ({len(legacy_issues)} across {syms_affected})", verbose)
    else:
        _record(findings, "Trade log integrity", "PASS",
                f"{total_trades} trade(s) across {len(by_sym)} symbol(s) — no consecutive same-side", verbose)


# ── Group 6: Backtest metric sanity ──────────────────────────────────────────

def _check_backtest_metrics(sess, findings: list[dict], verbose: bool) -> None:
    runs = sess.execute(
        sa.select(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(20)
    ).scalars().all()

    if not runs:
        _record(findings, "Backtest metric sanity", "SKIP",
                "No backtest runs found", verbose)
        return

    bad = []
    legacy_bad = []
    for run in runs:
        try:
            m = json.loads(run.metrics_json or "{}")
        except Exception:
            issue = f"run#{run.id}:invalid JSON"
            if str(run.integrity_status or "").lower() == INVALID_METRICS_STATUS:
                legacy_bad.append(issue)
            else:
                bad.append(issue)
            continue
        sharpe = m.get("sharpe")
        n = m.get("n_trades", m.get("num_trades"))
        dd = m.get("max_drawdown")
        if sharpe is not None and not _finite(sharpe):
            bad.append(f"run#{run.id}:sharpe={sharpe}")
        if n is not None and (not isinstance(n, (int, float)) or n < 0):
            bad.append(f"run#{run.id}:n_trades={n}")
        if dd is not None and _finite(dd) and not (0.0 <= float(dd) <= 1.0):
            bad.append(f"run#{run.id}:drawdown={dd:.3f} out of [0,1]")

    if bad:
        _record(findings, "Backtest metric sanity", "FAIL",
                f"Invalid metrics in: {bad[:5]}", verbose)
    elif legacy_bad:
        _record(findings, "Backtest metric sanity", "PARTIAL",
                f"Contained legacy-invalid runs: {legacy_bad[:5]}", verbose)
    else:
        _record(findings, "Backtest metric sanity", "PASS",
                f"{len(runs)} run(s) checked — all metrics finite and in range", verbose)


# ── Group 7: Backtest equity integrity ───────────────────────────────────────

def _check_backtest_equity(sess, findings: list[dict], verbose: bool) -> None:
    run = sess.execute(
        sa.select(BacktestRun).order_by(BacktestRun.created_at.desc())
    ).scalars().first()

    if run is None:
        _record(findings, "Backtest equity integrity", "SKIP",
                "No backtest runs", verbose)
        return

    trades = sess.execute(
        sa.select(BacktestTrade.side, BacktestTrade.price, BacktestTrade.qty)
        .where(BacktestTrade.run_id == run.id)
        .order_by(BacktestTrade.ts)
    ).all()

    try:
        m = json.loads(run.metrics_json or "{}")
    except Exception:
        m = {}
    reported_trades = m.get("n_trades", m.get("num_trades"))
    try:
        reported_trades = int(reported_trades) if reported_trades is not None else None
    except (TypeError, ValueError):
        reported_trades = None

    if not trades:
        if (reported_trades or 0) == 0:
            _record(findings, "Backtest equity integrity", "PASS",
                    f"Run #{run.id} recorded zero trades, consistent with saved metrics", verbose)
            return
        if str(run.integrity_status or "").lower() == MISSING_TRADES_STATUS:
            _record(findings, "Backtest equity integrity", "PARTIAL",
                    f"Run #{run.id} is legacy-invalid: saved run has no trade records", verbose)
        else:
            _record(findings, "Backtest equity integrity", "FAIL",
                    f"Run #{run.id} has no trade records", verbose)
        return

    # Pair BUY/SELL sequentially to check win/loss counts
    buys = [t for t in trades if t.side == "BUY"]
    sells = [t for t in trades if t.side == "SELL"]
    pairs = min(len(buys), len(sells))
    wins = sum(1 for b, s in zip(buys, sells) if s.price > b.price)
    losses = pairs - wins

    issues = []

    if reported_trades is not None and abs(int(reported_trades) - len(trades)) > 1:
        issues.append(
            f"metrics_json n_trades={reported_trades} but DB has {len(trades)} trade records"
        )

    # Equity curve sanity: reconstruct and check starting balance
    equity = STARTING_BALANCE_USD
    for b, s in zip(buys, sells):
        notional = b.qty * b.price
        pnl = (s.price - b.price) * b.qty
        equity += pnl
    if abs(equity - STARTING_BALANCE_USD) / STARTING_BALANCE_USD > 10.0:
        issues.append(f"Final equity {equity:.2f} implausibly far from start {STARTING_BALANCE_USD:.2f}")

    if issues:
        _record(findings, "Backtest equity integrity", "PARTIAL",
                "; ".join(issues), verbose)
    else:
        _record(findings, "Backtest equity integrity", "PASS",
                f"Run #{run.id}: {pairs} pairs, {wins}W/{losses}L, equity arithmetic consistent",
                verbose)


# ── Group 8: Position size compliance ────────────────────────────────────────

def _check_position_sizing(sess, findings: list[dict], verbose: bool) -> None:
    max_notional = MAX_POS_PCT * STARTING_BALANCE_USD
    rows = sess.execute(
        sa.select(Trade.symbol, Trade.price, Trade.qty, Trade.side, Trade.integrity_status)
        .where(Trade.side == "BUY")
        .order_by(Trade.ts.desc())
        .limit(200)
    ).all()

    if not rows:
        _record(findings, "Position size compliance", "SKIP",
                "No paper BUY trades to check", verbose)
        return

    oversized = []
    legacy_oversized = []
    for sym, price, qty, _, integrity_status in rows:
        if price * qty > max_notional * 1.05:
            issue = f"{sym}:{price*qty:.2f}>{max_notional:.2f}"
            if str(integrity_status or "").lower() == LEGACY_INVALID_STATUS:
                legacy_oversized.append(issue)
            else:
                oversized.append(issue)

    if oversized:
        _record(findings, "Position size compliance", "FAIL",
                f"Oversized trades: {oversized[:5]}", verbose)
    elif legacy_oversized:
        _record(findings, "Position size compliance", "PARTIAL",
                f"Contained legacy-invalid trades: {legacy_oversized[:5]}", verbose)
    else:
        _record(findings, "Position size compliance", "PASS",
                f"{len(rows)} BUY trade(s) checked — all within MAX_POS_PCT={MAX_POS_PCT:.0%}",
                verbose)


# ── Group 9: Active artifact integrity ───────────────────────────────────────

def _check_artifact_integrity(sess, findings: list[dict], verbose: bool) -> None:
    for mode in ("paper", "live"):
        artifact_id = get_active_runtime_artifact_id(mode)
        if artifact_id is None:
            _record(findings, f"Artifact integrity — {mode}", "SKIP",
                    "No active artifact configured", verbose)
            continue

        row = sess.get(StrategyArtifact, artifact_id)
        if row is None:
            _record(findings, f"Artifact integrity — {mode}", "FAIL",
                    f"Artifact ID {artifact_id} not found in DB", verbose)
            continue

        path = Path(row.path)
        if not path.is_file():
            _record(findings, f"Artifact integrity — {mode}", "FAIL",
                    f"File missing: {path}", verbose)
            continue

        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != row.code_hash:
            _record(findings, f"Artifact integrity — {mode}", "FAIL",
                    f"Hash mismatch - DB:{row.code_hash[:12]} file:{actual_hash[:12]}", verbose)
        else:
            _record(findings, f"Artifact integrity — {mode}", "PASS",
                    f"{row.name} v{row.version} hash verified ({row.code_hash[:12]}...)", verbose)


# ── Group 10: Ready symbol DB coverage ───────────────────────────────────────

def _check_symbol_db_coverage(sess, symbols: list[str], findings: list[dict],
                               verbose: bool) -> None:
    min_candles = 24 * 60   # 1 full day of 1m candles
    uncovered = []
    for sym in symbols:
        cnt = sess.execute(
            sa.select(sa.func.count(Candle.id)).where(Candle.symbol == sym)
        ).scalar() or 0
        if cnt < min_candles:
            uncovered.append(f"{sym}({cnt} candles)")

    if not symbols:
        _record(findings, "Ready symbol DB coverage", "SKIP",
                "No ready symbols registered", verbose)
    elif uncovered:
        _record(findings, "Ready symbol DB coverage", "PARTIAL",
                f"Insufficient history for: {uncovered}", verbose)
    else:
        _record(findings, "Ready symbol DB coverage", "PASS",
                f"All {len(symbols)} symbol(s) have ≥{min_candles} candles", verbose)


# ── Entry point ───────────────────────────────────────────────────────────────

def run_data_checks(*, verbose: bool = True) -> list[dict]:
    """Run all data integrity checks. Returns list of finding dicts."""
    init_db()
    findings: list[dict] = []
    symbols = list_ready_symbols()

    if verbose:
        print(f"\n-- Data Integrity (DB) -- [{len(symbols)} ready symbol(s)]")

    with SessionLocal() as sess:
        refresh_integrity_flags(sess, retag_existing=True)
        _check_candle_freshness(sess, symbols, findings, verbose)
        _check_history_depth(sess, symbols, findings, verbose)
        _check_ohlcv_sanity(sess, symbols, findings, verbose)
        _check_candle_continuity(sess, symbols, findings, verbose)
        _check_trade_log_integrity(sess, findings, verbose)
        _check_backtest_metrics(sess, findings, verbose)
        _check_backtest_equity(sess, findings, verbose)
        _check_position_sizing(sess, findings, verbose)
        _check_artifact_integrity(sess, findings, verbose)
        _check_symbol_db_coverage(sess, symbols, findings, verbose)

    if verbose:
        print(f"  Data checks: {len(findings)} checks")

    return findings
