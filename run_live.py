# crypto_ai_trader/run_live.py
"""
Boot sequence: load history → start live streamer → launch paper trader + coordinator
"""
import asyncio
import logging

from config import (
    validate_env, LLM_ENABLED, LIVE_TRADE_ENABLED,
    BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_TESTNET,
)
from collectors.historical_loader import main as load_history
from collectors.live_streamer     import main as live_stream
from simulator.paper_trader       import PaperTrader
from simulator.coordinator        import Coordinator
from llm.self_learner             import SelfLearner
from strategy.runtime             import get_active_strategy_config
from utils.telegram_utils         import send_telegram_alert, _token, _chat_id

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)


async def boot():
    await load_history()          # idempotent — skips already-stored candles

    trader      = PaperTrader()
    learner     = SelfLearner()
    coordinator = Coordinator(learner)
    trader._coordinator = coordinator
    active_strategy = get_active_strategy_config()
    log.info(
        "Active strategy loaded",
        extra={"strategy": active_strategy["name"], "version": active_strategy["version"]},
    )

    binance_client = None
    if LIVE_TRADE_ENABLED:
        from binance import AsyncClient
        binance_client = await AsyncClient.create(
            BINANCE_API_KEY, BINANCE_API_SECRET, testnet=BINANCE_TESTNET
        )
        trader._binance_client = binance_client
        log.warning("=" * 60)
        log.warning("⚡  LIVE TRADING ENABLED — real orders will be submitted")
        log.warning("=" * 60)
        send_telegram_alert(_token(), _chat_id(),
            "⚡ *LIVE TRADING ENABLED*\nBot is now submitting real Binance orders.")

    try:
        await asyncio.gather(
            live_stream(),
            trader.run(),
            coordinator.run_loop(),
        )
    finally:
        if binance_client is not None:
            await binance_client.close()


if __name__ == "__main__":
    validate_env()                # fail fast with clear error if .env is missing
    asyncio.run(boot())
