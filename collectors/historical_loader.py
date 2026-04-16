# crypto_ai_trader/collectors/historical_loader.py  (SAFE, DE-DUPING VERSION)
"""
Pull ~90 days of 1‑minute klines per symbol into SQLite.  
Run once before live trading.

Changes   2025‑06‑15
──────── ─────────────────────────────────────────────────────────────
• Fixed mixed async/sync ctx‑manager bug
• Removed invalid `ignore_conflicts` flag (SQLAlchemy 2.x) and
  implemented explicit SQLite UPSERT (`ON CONFLICT DO NOTHING`).
• Parallel downloads throttled via `asyncio.Semaphore`.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Dict, Any

from binance import AsyncClient
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from config import (
    SYMBOLS, HIST_INTERVAL,
    BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_TESTNET,
)
from database.models import Candle, init_db, SessionLocal

# ────────────────────────────────────────────────────────────────────
ROWS_PER_REQ   = 1_000          # Binance hard limit per call
DAYS_BACK      = 365             # how far to back‑fill
MAX_CONCURRENT = 1              # tune to stay under weight caps
# ────────────────────────────────────────────────────────────────────

def _as_dict(obj: Candle) -> Dict[str, Any]:
    """Convert ORM Candle instance → plain dict (for bulk INSERT)."""
    return {
        "symbol"    : obj.symbol,
        "open_time" : obj.open_time,
        "open"      : obj.open,
        "high"      : obj.high,
        "low"       : obj.low,
        "close"     : obj.close,
        "volume"    : obj.volume,
    }


def save_candles(sess: Session, candles: List[Candle]) -> None:
    """Bulk‑insert candles, silently skipping duplicates."""
    if not candles:
        return

    stmt = (
        sqlite_insert(Candle)
        .values([_as_dict(c) for c in candles])
        .on_conflict_do_nothing(index_elements=["symbol", "open_time"])
    )
    sess.execute(stmt)
    sess.commit()


async def fetch_symbol(symbol: str, client: AsyncClient, session: Session) -> None:
    """Download 90‑day history for *symbol* and persist to DB."""
    print(f"[+] {symbol}")
    end_ts   = datetime.now(tz=timezone.utc)
    start_ts = end_ts - timedelta(days=DAYS_BACK)

    while start_ts < end_ts:
        klines = await client.get_klines(
            symbol    = symbol,
            interval  = HIST_INTERVAL,
            startTime = int(start_ts.timestamp() * 1000),
            limit     = ROWS_PER_REQ,
        )
        if not klines:
            break  # reached exchange limit / no more data

        candles = [
            Candle(
                symbol    = symbol,
                open_time = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc),
                open      = float(k[1]),
                high      = float(k[2]),
                low       = float(k[3]),
                close     = float(k[4]),
                volume    = float(k[5]),
            )
            for k in klines
        ]
        save_candles(session, candles)

        # next page – advance by 1 minute after last returned kline
        start_ts = (
            datetime.fromtimestamp(klines[-1][0] / 1000, tz=timezone.utc)
            + timedelta(minutes=1)
        )

    print(f"[✓] {symbol} done")


async def _worker(symbols: Iterable[str], sem: asyncio.Semaphore, client: AsyncClient):
    """Each worker runs under the same API client but its own DB session."""
    async with sem:
        with SessionLocal() as sess:
            for sym in symbols:
                await fetch_symbol(sym, client, sess)


async def main() -> None:
    """Entrypoint when executed as a module."""
    init_db()

    client = await AsyncClient.create(
        BINANCE_API_KEY,
        BINANCE_API_SECRET,
        testnet=BINANCE_TESTNET,
    )
    try:
        sem   = asyncio.Semaphore(MAX_CONCURRENT)
        tasks = [asyncio.create_task(_worker([s], sem, client)) for s in SYMBOLS]
        await asyncio.gather(*tasks)
    finally:
        await client.close_connection()


if __name__ == "__main__":
    asyncio.run(main())
