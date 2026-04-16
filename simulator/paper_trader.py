# crypto_ai_trader/simulator/paper_trader.py
"""Paper trader that listens for AI signals and manual Telegram button commands."""
import asyncio, logging
from datetime import datetime, timezone
from typing import Dict

from database.models import Candle, SessionLocal
from strategy.signal_engine import compute_signal, Signal
from utils.telegram_utils import CALLBACK_QUEUE, send_telegram_alert, _token, _chat_id
from config import SYMBOLS, POSITION_SIZE_PCT, FEE_RATE

TICK_SECONDS = 1

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")


class PaperTrader:
    def __init__(self):
        self.cash: float = 10_000.0
        self.positions: Dict[str, float] = {}
        self.realised: float = 0.0

    async def run(self):
        consumer = asyncio.create_task(self._consume_callbacks())
        try:
            while True:
                await self.step()
                await asyncio.sleep(TICK_SECONDS)
        except asyncio.CancelledError:
            consumer.cancel()
            await consumer
            logging.info("PaperTrader stopped.")

    async def _consume_callbacks(self):
        while True:
            action, symbol = await CALLBACK_QUEUE.get()
            if action == "BUY":
                await self._manual_buy(symbol)
            elif action == "SELL":
                await self._manual_sell(symbol)

    async def step(self):
        with SessionLocal() as sess:
            for sym in SYMBOLS:
                candle = (
                    sess.query(Candle)
                        .filter(Candle.symbol == sym)
                        .order_by(Candle.open_time.desc())
                        .first()
                )
                if not candle:
                    continue
                sig: Signal = compute_signal(sess, candle)
                if sig == Signal.BUY:
                    await self._auto_buy(sym, candle.close)
                elif sig == Signal.SELL:
                    await self._auto_sell(sym, candle.close)

    async def _auto_buy(self, sym: str, price: float):
        qty = (self.cash * POSITION_SIZE_PCT) / price
        if qty <= 0:
            return
        cost = qty * price * (1 + FEE_RATE)
        if cost > self.cash:
            return
        self.cash -= cost
        self.positions[sym] = self.positions.get(sym, 0) + qty
        logging.info(f"AUTO BUY  {sym} qty={qty:.4f} @ {price:.2f}  cash={self.cash:.2f}")
        send_telegram_alert(_token(), _chat_id(),
                            f"🤖 Auto-BUY {sym} qty={qty:.4f} @ {price:.2f}")

    async def _auto_sell(self, sym: str, price: float):
        qty = self.positions.pop(sym, 0)
        if qty == 0:
            return
        proceeds = qty * price * (1 - FEE_RATE)
        self.cash     += proceeds
        self.realised += proceeds
        logging.info(f"AUTO SELL {sym} qty={qty:.4f} @ {price:.2f}  cash={self.cash:.2f}")
        send_telegram_alert(_token(), _chat_id(),
                            f"🤖 Auto-SELL {sym} qty={qty:.4f} @ {price:.2f}")

    async def _manual_buy(self, sym: str):
        price = await self._latest_price(sym)
        await self._auto_buy(sym, price)

    async def _manual_sell(self, sym: str):
        price = await self._latest_price(sym)
        await self._auto_sell(sym, price)

    async def _latest_price(self, sym: str) -> float:
        with SessionLocal() as sess:
            candle = (
                sess.query(Candle)
                    .filter(Candle.symbol == sym)
                    .order_by(Candle.open_time.desc())
                    .first()
            )
            return candle.close if candle else 0.0
