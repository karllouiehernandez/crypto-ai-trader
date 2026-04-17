# crypto_ai_trader/run_live.py
"""
Boot sequence: load history → start live streamer → launch paper trader + coordinator
"""
import asyncio
import logging

from config import validate_env, LLM_ENABLED
from collectors.historical_loader import main as load_history
from collectors.live_streamer     import main as live_stream
from simulator.paper_trader       import PaperTrader
from simulator.coordinator        import Coordinator
from llm.self_learner             import SelfLearner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

async def boot():
    await load_history()          # idempotent — skips already-stored candles

    trader      = PaperTrader()
    learner     = SelfLearner()
    coordinator = Coordinator(learner)
    trader._coordinator = coordinator   # give trader a handle for future use

    await asyncio.gather(
        live_stream(),            # runs forever
        trader.run(),             # runs forever
        coordinator.run_loop(),   # starts SelfLearner + watches promotion gate
    )

if __name__ == "__main__":
    validate_env()                # fail fast with clear error if .env is missing
    asyncio.run(boot())
