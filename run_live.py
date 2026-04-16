# crypto_ai_trader/run_live.py
"""
Boot sequence: load history → start live streamer → launch paper trader
"""
import asyncio
from config import validate_env
from collectors.historical_loader import main as load_history
from collectors.live_streamer     import main as live_stream
from simulator.paper_trader       import PaperTrader

async def boot():
    await load_history()          # idempotent — skips already-stored candles
    trader = PaperTrader()
    await asyncio.gather(
        live_stream(),            # runs forever
        trader.run(),             # runs forever
    )

if __name__ == "__main__":
    validate_env()                # fail fast with clear error if .env is missing
    asyncio.run(boot())
