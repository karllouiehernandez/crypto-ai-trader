# crypto_ai_trader/collectors/live_streamer.py  (TELEGRAM‑FALLBACK VERSION)
"""
Polls the latest price every `LIVE_POLL_SECONDS` and keeps the current
1‑minute candle up‑to‑date.

✅ 2025‑06‑15 Fixes
───────────────────
• Import path now robust: tries `crypto_ai_trader.utils…`, then plain
  `utils…`; if both fail it creates a no‑op stub so the streamer still
  runs.
• `ENABLE_TG_STREAM_ALERTS` and `ENABLE_TG_ALERTS` are fetched via
  `getattr(config, …, False)` so they remain optional.
"""
import asyncio, logging
from datetime import datetime, timezone
from typing import Optional

from binance import AsyncClient
import config                           # import whole module so we can getattr
from config import (
    SYMBOLS, LIVE_POLL_SECONDS,
    BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_TESTNET,
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
)

# Optional switches
ENABLE_TG_ALERTS         = getattr(config, "ENABLE_TG_ALERTS", False)
ENABLE_TG_STREAM_ALERTS  = getattr(config, "ENABLE_TG_STREAM_ALERTS", False)

# ---------------------------------------------------------------------------
# Telegram helper import (robust to different package start locations)
# ---------------------------------------------------------------------------
try:
    from crypto_ai_trader.utils.telegram_utils import send_telegram_alert
except ImportError:  # user might be running script *inside* package dir
    try:
        from utils.telegram_utils import send_telegram_alert
    except ImportError:
        def send_telegram_alert(*_a, **_kw):  # type: ignore
            logging.warning("Telegram utils not found – alerts disabled")
            return

from database.models import Candle, SessionLocal, init_db

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")

def safe_telegram(msg: str):
    """Send `msg` if global alerts are enabled; swallow/log failures."""
    if not ENABLE_TG_ALERTS:
        return
    try:
        send_telegram_alert(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
    except Exception as e:  # pragma: no cover – network error logging only
        logging.error(f"Telegram send failed: {e}")


async def stream_symbol(sym: str, client: AsyncClient, retry: int = 0) -> None:
    """Continuously fetch the last price for *sym* and extend the live candle."""
    while True:
        try:
            price = float((await client.get_symbol_ticker(symbol=sym))["price"])
            now   = datetime.now(tz=timezone.utc).replace(microsecond=0)

            minute_open = now.replace(second=0)
            with SessionLocal() as session:
                candle: Optional[Candle] = (
                    session.query(Candle)
                          .filter_by(symbol=sym, open_time=minute_open)
                          .first()
                )

                if candle:
                    candle.close = price
                    candle.high  = max(candle.high, price)
                    candle.low   = min(candle.low,  price)
                else:
                    session.add(Candle(
                        symbol=sym, open_time=minute_open,
                        open=price, high=price, low=price, close=price,
                        volume=0.0,
                    ))
                session.commit()

            if ENABLE_TG_STREAM_ALERTS:
                safe_telegram(f"{sym} price: {price:.2f} @ {now:%H:%M:%S}")

            retry = 0  # reset back‑off on success
        except Exception as exc:
            wait = min(60, 2 ** retry)    # exponential back‑off, max 60 s
            logging.warning(f"{sym} stream error: {exc} – retrying in {wait}s")
            retry += 1
            await asyncio.sleep(wait)
            continue

        await asyncio.sleep(LIVE_POLL_SECONDS)


async def main() -> None:
    """Spin up one task per symbol, send Telegram startup ping, then wait."""
    init_db()
    logging.info("try TELEGRAM")

    safe_telegram("✅ Live streamer started – Telegram OK")

    client = await AsyncClient.create(
        BINANCE_API_KEY, BINANCE_API_SECRET, testnet=BINANCE_TESTNET,
    )
    try:
        tasks = [asyncio.create_task(stream_symbol(sym, client)) for sym in SYMBOLS]
        await asyncio.gather(*tasks)
    finally:
        await client.close_connection()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Live streamer stopped by user")
