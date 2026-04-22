"""Historical data backfill, sync, and continuity audit helpers."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from config import DAYS_BACK, MVP_FRESHNESS_MINUTES, MVP_RESEARCH_UNIVERSE
from database.models import Candle, SessionLocal, init_db

_SUPPORTED_INTERVALS = {"1m": timedelta(minutes=1)}
_BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
_ARCHIVE_URL_TEMPLATE = (
    "https://data.binance.vision/data/spot/daily/klines/{symbol}/{interval}/"
    "{symbol}-{interval}-{day}.zip"
)
_ROWS_PER_REQ = 1_000
_MICROSECOND_EPOCH_THRESHOLD = 10**15
_MILLISECOND_EPOCH_THRESHOLD = 10**12


def _normalise_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def _normalise_utc(value: datetime | str) -> datetime:
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(second=0, microsecond=0)


def _validate_interval(interval: str) -> timedelta:
    if interval not in _SUPPORTED_INTERVALS:
        raise ValueError(f"Unsupported interval: {interval}")
    return _SUPPORTED_INTERVALS[interval]


def _iterate_days(start: datetime, end: datetime) -> list[datetime]:
    cursor = start.replace(hour=0, minute=0)
    last = end.replace(hour=0, minute=0)
    days: list[datetime] = []
    while cursor <= last:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _parse_binance_epoch(value: Any) -> datetime:
    """Handle Binance timestamps emitted in either milliseconds or microseconds."""
    raw = int(value)
    if raw >= _MICROSECOND_EPOCH_THRESHOLD:
        return datetime.fromtimestamp(raw / 1_000_000, tz=timezone.utc)
    if raw >= _MILLISECOND_EPOCH_THRESHOLD:
        return datetime.fromtimestamp(raw / 1_000, tz=timezone.utc)
    return datetime.fromtimestamp(raw, tz=timezone.utc)


def _kline_to_row(symbol: str, kline: list[Any]) -> dict[str, Any]:
    return {
        "symbol": _normalise_symbol(symbol),
        "open_time": _parse_binance_epoch(kline[0]),
        "open": float(kline[1]),
        "high": float(kline[2]),
        "low": float(kline[3]),
        "close": float(kline[4]),
        "volume": float(kline[5]),
    }


def _filter_rows_to_window(rows: list[dict[str, Any]], start: datetime, end: datetime) -> list[dict[str, Any]]:
    return [row for row in rows if start <= row["open_time"] <= end]


def _download_archive_day(symbol: str, day: datetime, interval: str) -> list[dict[str, Any]]:
    day_str = day.strftime("%Y-%m-%d")
    url = _ARCHIVE_URL_TEMPLATE.format(symbol=_normalise_symbol(symbol), interval=interval, day=day_str)
    resp = requests.get(url, timeout=30)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()

    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
        names = archive.namelist()
        if not names:
            return []
        with archive.open(names[0]) as handle:
            reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8"))
            for record in reader:
                if not record:
                    continue
                rows.append(_kline_to_row(symbol, record))
    return rows


def _fetch_api_klines(
    symbol: str,
    start: datetime,
    end: datetime,
    interval: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = start
    step = _validate_interval(interval)
    while cursor <= end:
        resp = requests.get(
            _BINANCE_KLINES_URL,
            params={
                "symbol": _normalise_symbol(symbol),
                "interval": interval,
                "startTime": int(cursor.timestamp() * 1000),
                "endTime": int(end.timestamp() * 1000),
                "limit": _ROWS_PER_REQ,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        batch = [_kline_to_row(symbol, row) for row in data]
        rows.extend(batch)
        next_open = batch[-1]["open_time"] + step
        if next_open <= cursor:
            break
        cursor = next_open
    return rows


def _upsert_candles(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    init_db()
    with SessionLocal() as sess:
        stmt = (
            sqlite_insert(Candle)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["symbol", "open_time"])
        )
        result = sess.execute(stmt)
        sess.commit()
        return int(result.rowcount or 0)


def get_latest_candle_time(symbol: str) -> datetime | None:
    init_db()
    with SessionLocal() as sess:
        row = (
            sess.query(Candle.open_time)
            .filter(Candle.symbol == _normalise_symbol(symbol))
            .order_by(Candle.open_time.desc())
            .first()
        )
    if row is None:
        return None
    return _normalise_utc(row[0])


def _age_minutes(latest: datetime | None, now: datetime) -> float | None:
    if latest is None:
        return None
    return max(0.0, (now - _normalise_utc(latest)).total_seconds() / 60.0)


def backfill(symbol: str, start: datetime | str, end: datetime | str, interval: str = "1m") -> dict[str, Any]:
    """Backfill one symbol over an explicit date range using archive files plus API fallback."""
    step = _validate_interval(interval)
    start_dt = _normalise_utc(start)
    end_dt = _normalise_utc(end)
    if end_dt < start_dt:
        raise ValueError("End must be greater than or equal to start")

    inserted = 0
    today_utc = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    for day in _iterate_days(start_dt, end_dt):
        day_start = max(start_dt, day)
        day_end = min(end_dt, day + timedelta(days=1) - step)
        if day < today_utc:
            rows = _download_archive_day(symbol, day, interval)
            if not rows:
                rows = _fetch_api_klines(symbol, day_start, day_end, interval)
        else:
            rows = _fetch_api_klines(symbol, day_start, day_end, interval)
        inserted += _upsert_candles(_filter_rows_to_window(rows, day_start, day_end))

    audit_result = audit(symbol, start_dt, end_dt, interval=interval)
    audit_result["rows_inserted"] = inserted
    return audit_result


def sync_recent(symbol: str, interval: str = "1m") -> dict[str, Any]:
    """Sync recent data for one symbol from the latest stored candle to now."""
    _validate_interval(interval)
    latest = get_latest_candle_time(symbol)
    now = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
    if latest is None:
        start = now - timedelta(days=DAYS_BACK)
        return backfill(symbol, start, now, interval=interval)

    start = latest + timedelta(minutes=1)
    if start > now:
        return audit(symbol, latest, latest, interval=interval)

    rows = _fetch_api_klines(symbol, start, now, interval)
    inserted = _upsert_candles(rows)
    result = audit(symbol, start, now, interval=interval)
    result["rows_inserted"] = inserted
    return result


def maintain_symbol_freshness(
    symbols: list[str] | None = None,
    *,
    interval: str = "1m",
    max_age_minutes: int = MVP_FRESHNESS_MINUTES,
) -> dict[str, dict[str, Any]]:
    """Refresh stale symbols and report per-symbol freshness status."""
    _validate_interval(interval)
    now = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
    ordered_symbols: list[str] = []
    seen: set[str] = set()
    for raw_symbol in symbols or MVP_RESEARCH_UNIVERSE:
        symbol = _normalise_symbol(raw_symbol)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        ordered_symbols.append(symbol)

    results: dict[str, dict[str, Any]] = {}
    for symbol in ordered_symbols:
        latest_before = get_latest_candle_time(symbol)
        age_before = _age_minutes(latest_before, now)
        stale = latest_before is None or age_before is None or age_before > float(max_age_minutes)
        if stale:
            sync_result = sync_recent(symbol, interval=interval)
            refreshed_latest = get_latest_candle_time(symbol)
            refreshed_now = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
            results[symbol] = {
                "status": "synced",
                "age_minutes_before": age_before,
                "age_minutes_after": _age_minutes(refreshed_latest, refreshed_now),
                "rows_inserted": int(sync_result.get("rows_inserted", 0) or 0),
                "is_complete": bool(sync_result.get("is_complete", False)),
                "latest_candle_ts": refreshed_latest,
            }
            continue

        results[symbol] = {
            "status": "fresh",
            "age_minutes_before": age_before,
            "age_minutes_after": age_before,
            "rows_inserted": 0,
            "is_complete": True,
            "latest_candle_ts": latest_before,
        }
    return results


def ensure_symbol_history(symbol: str, interval: str = "1m") -> dict[str, Any]:
    """Ensure a symbol has at least the configured lookback plus recent sync."""
    latest = get_latest_candle_time(symbol)
    if latest is None:
        now = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
        start = now - timedelta(days=DAYS_BACK)
        return backfill(symbol, start, now, interval=interval)
    return sync_recent(symbol, interval=interval)


def audit(symbol: str, start: datetime | str, end: datetime | str, interval: str = "1m") -> dict[str, Any]:
    """Audit continuity for one symbol over a requested window."""
    start_dt = _normalise_utc(start)
    end_dt = _normalise_utc(end)
    if end_dt < start_dt:
        raise ValueError("End must be greater than or equal to start")

    init_db()
    with SessionLocal() as sess:
        rows = (
            sess.query(Candle.open_time)
            .filter(
                Candle.symbol == _normalise_symbol(symbol),
                Candle.open_time >= start_dt,
                Candle.open_time <= end_dt,
            )
            .order_by(Candle.open_time)
            .all()
        )
    return evaluate_candle_coverage(symbol, start_dt, end_dt, [row[0] for row in rows], interval=interval)


def evaluate_candle_coverage(
    symbol: str,
    start: datetime | str,
    end: datetime | str,
    candle_times: list[datetime | str],
    interval: str = "1m",
) -> dict[str, Any]:
    """Evaluate completeness for an already loaded candle-time sequence."""
    step = _validate_interval(interval)
    start_dt = _normalise_utc(start)
    end_dt = _normalise_utc(end)
    if end_dt < start_dt:
        raise ValueError("End must be greater than or equal to start")

    times = [_normalise_utc(value) for value in candle_times]
    times = sorted([value for value in times if start_dt <= value <= end_dt])
    expected_bars = int(((end_dt - start_dt) / step)) + 1
    missing_ranges: list[dict[str, datetime]] = []
    cursor = start_dt
    for timestamp in times:
        if timestamp > cursor:
            missing_ranges.append({"start": cursor, "end": timestamp - step})
        if timestamp >= cursor:
            cursor = timestamp + step
    if cursor <= end_dt:
        missing_ranges.append({"start": cursor, "end": end_dt})

    return {
        "symbol": _normalise_symbol(symbol),
        "interval": interval,
        "requested_start": start_dt,
        "requested_end": end_dt,
        "covered_start": times[0] if times else None,
        "covered_end": times[-1] if times else None,
        "expected_bars": expected_bars,
        "actual_bars": len(times),
        "missing_ranges": missing_ranges,
        "is_complete": len(times) == expected_bars and not missing_ranges,
    }


def format_audit_summary(result: dict[str, Any], max_ranges: int = 3) -> str:
    """Return a concise human-readable audit summary."""
    if result.get("is_complete"):
        return (
            f"History complete for {result['symbol']} "
            f"({result['actual_bars']}/{result['expected_bars']} bars)."
        )
    ranges = result.get("missing_ranges") or []
    preview = ", ".join(
        f"{item['start'].strftime('%Y-%m-%d %H:%M')} → {item['end'].strftime('%Y-%m-%d %H:%M')}"
        for item in ranges[:max_ranges]
    )
    remaining = len(ranges) - min(len(ranges), max_ranges)
    if remaining > 0:
        preview = f"{preview}, +{remaining} more"
    return (
        f"Incomplete history for {result['symbol']}: "
        f"{result['actual_bars']}/{result['expected_bars']} bars present. Missing {len(ranges)} range(s): {preview}"
    )


def require_complete_history(symbol: str, start: datetime, end: datetime, interval: str = "1m") -> None:
    """Raise when a backtest window has missing candles."""
    result = audit(symbol, start, end, interval=interval)
    if not result["is_complete"]:
        raise ValueError(format_audit_summary(result))
