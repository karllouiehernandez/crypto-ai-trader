# crypto_ai_trader/simulator/paper_trader.py
"""Paper trader that listens for AI signals and manual Telegram button commands."""
import asyncio, logging
from datetime import datetime, timezone
from typing import Dict, Optional

from database.models import Candle, SessionLocal
from strategy.signal_engine import compute_signal, Signal
from strategy.ta_features import add_indicators
from strategy.risk import atr_position_size, DailyLossTracker, DrawdownCircuitBreaker
from utils.telegram_utils import CALLBACK_QUEUE, send_telegram_alert, _token, _chat_id
from config import (
    SYMBOLS, POSITION_SIZE_PCT, FEE_RATE, STARTING_BALANCE_USD,
    DAILY_LOSS_LIMIT_PCT, DRAWDOWN_HALT_PCT, LLM_ENABLED,
)

TICK_SECONDS = 1
ATR_LOOKBACK = 20  # candles used to estimate ATR for position sizing

log = logging.getLogger(__name__)


class PaperTrader:
    def __init__(self):
        self.cash: float = STARTING_BALANCE_USD
        self.positions: Dict[str, float] = {}
        self.cost_basis: Dict[str, float] = {}  # tracks buy cost per symbol for P&L
        self.realised: float = 0.0

        equity = STARTING_BALANCE_USD
        self._daily_tracker = DailyLossTracker(start_equity=equity)
        self._drawdown_cb   = DrawdownCircuitBreaker(initial_equity=equity)

        self._coordinator = None          # optional; set externally before run()
        self._last_regime: Dict[str, str] = {}   # sym → regime string for critique context

    # ── equity helpers ─────────────────────────────────────────────────────────

    def _equity(self, prices: Optional[Dict[str, float]] = None) -> float:
        """Total equity = cash + mark-to-market value of open positions."""
        pos_value = sum(
            qty * (prices.get(sym, 0) if prices else 0)
            for sym, qty in self.positions.items()
        )
        return self.cash + pos_value

    def _update_risk_state(self, prices: Optional[Dict[str, float]] = None) -> None:
        """Refresh daily tracker and drawdown CB with current equity."""
        equity = self._equity(prices)
        self._daily_tracker.update(equity)
        self._drawdown_cb.update(equity)

    def _trading_halted(self) -> bool:
        if self._daily_tracker.is_halted:
            log.warning("Trading halted: daily loss limit reached.",
                        extra={"reason": "daily_loss_limit"})
            return True
        if self._drawdown_cb.is_halted:
            log.warning("Trading halted: drawdown circuit breaker triggered.",
                        extra={"reason": "drawdown_circuit_breaker"})
            return True
        return False

    # ── main loops ─────────────────────────────────────────────────────────────

    async def run(self):
        consumer = asyncio.create_task(self._consume_callbacks())
        try:
            while True:
                await self.step()
                await asyncio.sleep(TICK_SECONDS)
        except asyncio.CancelledError:
            consumer.cancel()
            await consumer
            log.info("PaperTrader stopped.")

    async def _consume_callbacks(self):
        while True:
            action, symbol = await CALLBACK_QUEUE.get()
            if self._trading_halted():
                log.warning("Manual %s for %s ignored — trading halted.", action, symbol,
                            extra={"action": action, "symbol": symbol, "reason": "halt"})
                continue
            if action == "BUY":
                await self._manual_buy(symbol)
            elif action == "SELL":
                await self._manual_sell(symbol)

    async def step(self):
        with SessionLocal() as sess:
            # Single pass: collect latest candle per symbol
            candles: Dict[str, object] = {}
            for sym in SYMBOLS:
                c = (
                    sess.query(Candle)
                        .filter(Candle.symbol == sym)
                        .order_by(Candle.open_time.desc())
                        .first()
                )
                if c:
                    candles[sym] = c

            prices = {sym: c.close for sym, c in candles.items()}
            self._update_risk_state(prices)

            if self._trading_halted():
                return

            for sym, candle in candles.items():
                sig: Signal = compute_signal(sess, candle)
                if sig == Signal.BUY:
                    atr = self._compute_atr(sess, sym)
                    await self._auto_buy(sym, candle.close, atr, prices)
                elif sig == Signal.SELL:
                    await self._auto_sell(sym, candle.close)

    # ── ATR helper ─────────────────────────────────────────────────────────────

    def _compute_atr(self, sess, sym: str) -> float:
        """Fetch recent candles and return the latest ATR value, or 0 on failure."""
        import pandas as pd
        try:
            candles = (
                sess.query(Candle)
                    .filter(Candle.symbol == sym)
                    .order_by(Candle.open_time.desc())
                    .limit(ATR_LOOKBACK + 5)
                    .all()
            )
            if len(candles) < ATR_LOOKBACK:
                return 0.0
            df = pd.DataFrame(
                [(c.high, c.low, c.close) for c in reversed(candles)],
                columns=["high", "low", "close"],
            )
            # True range: max(H-L, |H-prev_C|, |L-prev_C|)
            df["prev_close"] = df["close"].shift(1)
            df["tr"] = df[["high", "low", "prev_close"]].apply(
                lambda r: max(r["high"] - r["low"],
                              abs(r["high"] - r["prev_close"]) if pd.notna(r["prev_close"]) else 0,
                              abs(r["low"]  - r["prev_close"]) if pd.notna(r["prev_close"]) else 0),
                axis=1,
            )
            return df["tr"].iloc[-ATR_LOOKBACK:].mean()
        except Exception:
            return 0.0

    # ── order execution ────────────────────────────────────────────────────────

    async def _auto_buy(self, sym: str, price: float, atr: float = 0.0,
                        prices: Optional[Dict[str, float]] = None):
        if price <= 0:
            return

        # Use all known prices for accurate equity; merge sym's current price in
        all_prices = dict(prices or {})
        all_prices[sym] = price

        # ATR-based sizing; fall back to flat POSITION_SIZE_PCT when ATR unavailable
        if atr > 0:
            qty = atr_position_size(self._equity(all_prices), atr)
        else:
            qty = (self.cash * POSITION_SIZE_PCT) / price

        if qty <= 0:
            return
        cost = qty * price * (1 + FEE_RATE)
        if cost > self.cash:
            return
        self.cash -= cost
        self.positions[sym] = self.positions.get(sym, 0) + qty
        self.cost_basis[sym] = self.cost_basis.get(sym, 0) + cost
        log.info("AUTO BUY", extra={
            "symbol": sym, "qty": round(qty, 6), "price": round(price, 4),
            "atr": round(atr, 4), "cost": round(cost, 4), "cash": round(self.cash, 4),
        })
        send_telegram_alert(_token(), _chat_id(),
                            f"🤖 Auto-BUY {sym} qty={qty:.4f} @ {price:.2f}")

    async def _auto_sell(self, sym: str, price: float):
        if price <= 0:
            return
        qty = self.positions.pop(sym, 0)
        if qty == 0:
            return
        proceeds = qty * price * (1 - FEE_RATE)
        self.cash     += proceeds
        cost           = self.cost_basis.pop(sym, 0)
        self.realised += proceeds - cost
        log.info("AUTO SELL", extra={
            "symbol": sym, "qty": round(qty, 6), "price": round(price, 4),
            "proceeds": round(proceeds, 4), "pnl": round(proceeds - cost, 4),
            "cash": round(self.cash, 4),
        })
        send_telegram_alert(_token(), _chat_id(),
                            f"🤖 Auto-SELL {sym} qty={qty:.4f} @ {price:.2f}")
        # Fire-and-forget trade critique — non-blocking, never raises
        if LLM_ENABLED:
            pnl_pct = (proceeds - cost) / cost * 100 if cost else 0.0
            entry_price = cost / qty if qty else 0.0
            asyncio.create_task(
                _fire_critique(sym, price, entry_price, pnl_pct,
                               self._last_regime.get(sym, "UNKNOWN"))
            )

    async def _manual_buy(self, sym: str):
        with SessionLocal() as sess:
            candle = (
                sess.query(Candle)
                    .filter(Candle.symbol == sym)
                    .order_by(Candle.open_time.desc())
                    .first()
            )
            if not candle or candle.close <= 0:
                return
            atr = self._compute_atr(sess, sym)
            await self._auto_buy(sym, candle.close, atr)

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


# ── Module-level fire-and-forget critique ─────────────────────────────────────

async def _fire_critique(
    sym: str,
    exit_price: float,
    entry_price: float,
    pnl_pct: float,
    regime: str,
) -> None:
    """Non-blocking trade critique — called via asyncio.create_task(), never raises."""
    try:
        from llm.critiquer import critique_trade
        critique_trade(sym, "SELL", entry_price, exit_price, pnl_pct, regime, {})
    except Exception:   # noqa: BLE001
        pass
