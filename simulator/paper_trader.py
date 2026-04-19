# crypto_ai_trader/simulator/paper_trader.py
"""Paper trader that listens for AI signals and manual Telegram button commands."""
import asyncio, logging
from datetime import datetime, timezone
from typing import Dict, Optional

import config as _config
from database.models import (
    Candle,
    SessionLocal,
    Trade,
    init_db,
    snapshot_portfolio,
    upsert_portfolio,
)
from strategy.runtime import compute_strategy_decision, get_active_strategy_config
from strategy.signals import Signal
from strategy.risk import atr_position_size, DailyLossTracker, DrawdownCircuitBreaker
from utils.telegram_utils import CALLBACK_QUEUE, send_telegram_alert, _token, _chat_id
from config import (
    SYMBOLS,
    POSITION_SIZE_PCT, FEE_RATE, STARTING_BALANCE_USD,
    DAILY_LOSS_LIMIT_PCT, DRAWDOWN_HALT_PCT, LLM_ENABLED,
    LIVE_TRADE_ENABLED,
    PORTFOLIO_SNAP_MIN,
)
from market_data.runtime_watchlist import list_runtime_symbols

TICK_SECONDS = 1
ATR_LOOKBACK = 20  # candles used to estimate ATR for position sizing

log = logging.getLogger(__name__)


class PaperTrader:
    def __init__(self, strategy_descriptor: dict | None = None, *, restore_runtime_state: bool = False):
        init_db()
        self.cash: float = STARTING_BALANCE_USD
        self.positions: Dict[str, float] = {}
        self.cost_basis: Dict[str, float] = {}  # tracks buy cost per symbol for P&L
        self.realised: float = 0.0
        self._latest_prices: Dict[str, float] = {}
        self._last_trade_ts: Optional[datetime] = None

        equity = STARTING_BALANCE_USD
        self._daily_tracker = DailyLossTracker(start_equity=equity)
        self._drawdown_cb   = DrawdownCircuitBreaker(initial_equity=equity)

        self._coordinator = None          # optional; set externally before run()
        self._binance_client = None       # set by run_live.py when LIVE_TRADE_ENABLED=True
        self._force_halt = False          # set True/False via /halt and /resume Telegram commands
        self._last_regime: Dict[str, str] = {}   # sym → regime string for critique context
        self._last_processed_candle: Dict[str, datetime] = {}
        active = strategy_descriptor or get_active_strategy_config()
        self._strategy_name = active.get("strategy_name") or active.get("name", "")
        self._strategy_version = active.get("strategy_version") or active.get("version", "")
        self._strategy_params = dict(active.get("strategy_params") or active.get("params") or {})
        self._strategy_artifact_id = active.get("artifact_id")
        self._strategy_code_hash = str(active.get("strategy_code_hash") or "")
        self._strategy_provenance = str(active.get("strategy_provenance") or "")
        self._last_snapshot_minute: Optional[datetime] = None
        self._enforce_persisted_integrity = bool(restore_runtime_state)
        if restore_runtime_state:
            self._restore_runtime_state()

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

    def _runtime_mode(self) -> str:
        return "live" if LIVE_TRADE_ENABLED else "paper"

    def _trade_matches_runtime(self, trade: Trade) -> bool:
        if str(trade.run_mode or "") != self._runtime_mode():
            return False
        if self._strategy_artifact_id is not None:
            return trade.artifact_id == self._strategy_artifact_id
        return str(trade.strategy_name or "") == self._strategy_name

    def _restore_runtime_state(self) -> None:
        """Rebuild open positions/cash from persisted trades so restarts do not forget state."""
        with SessionLocal() as sess:
            rows = (
                sess.query(Trade)
                .order_by(Trade.ts.asc(), Trade.id.asc())
                .all()
            )

        matching_rows = [row for row in rows if self._trade_matches_runtime(row)]
        if not matching_rows:
            return

        cash = float(STARTING_BALANCE_USD)
        positions: Dict[str, float] = {}
        cost_basis: Dict[str, float] = {}
        realised = 0.0

        for row in matching_rows:
            symbol = str(row.symbol or "")
            side = str(row.side or "").upper()
            qty = float(row.qty or 0.0)
            price = float(row.price or 0.0)
            fee = float(row.fee or 0.0)
            pnl = float(row.pnl or 0.0)

            if side == "BUY":
                cash -= (qty * price) + fee
                positions[symbol] = positions.get(symbol, 0.0) + qty
                cost_basis[symbol] = cost_basis.get(symbol, 0.0) + (qty * price) + fee
            elif side == "SELL":
                cash += (qty * price) - fee
                positions[symbol] = max(0.0, positions.get(symbol, 0.0) - qty)
                if positions[symbol] <= 1e-12:
                    positions.pop(symbol, None)
                    cost_basis.pop(symbol, None)
                realised += pnl

        self.cash = cash
        self.positions = positions
        self.cost_basis = cost_basis
        self.realised = realised
        self._last_trade_ts = matching_rows[-1].ts
        log.info(
            "Restored runtime state from %s persisted trade(s).",
            len(matching_rows),
            extra={
                "run_mode": self._runtime_mode(),
                "strategy_name": self._strategy_name,
                "artifact_id": self._strategy_artifact_id,
                "open_positions": len(self.positions),
            },
        )

    def _would_duplicate_persisted_side(self, symbol: str, side: str) -> bool:
        if not self._enforce_persisted_integrity:
            return False
        with SessionLocal() as sess:
            rows = (
                sess.query(Trade)
                .filter(Trade.symbol == symbol)
                .order_by(Trade.ts.desc(), Trade.id.desc())
                .limit(20)
                .all()
            )
        for row in rows:
            if not self._trade_matches_runtime(row):
                continue
            return str(row.side or "").upper() == str(side or "").upper()
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

            if action == "HALT":
                self._force_halt = True
                from utils.telegram_utils import alert
                alert("🛑 Trading halted by Telegram command.")
                log.warning("Trading force-halted via Telegram.")
                continue
            if action == "RESUME":
                self._force_halt = False
                from utils.telegram_utils import alert
                alert("▶️ Trading resumed by Telegram command.")
                log.info("Trading resumed via Telegram.")
                continue

            if self._trading_halted() or getattr(self, "_force_halt", False):
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
            for sym in _current_runtime_symbols():
                c = (
                    sess.query(Candle)
                        .filter(Candle.symbol == sym)
                        .order_by(Candle.open_time.desc())
                        .first()
                )
                if c:
                    candles[sym] = c

            prices = {sym: c.close for sym, c in candles.items()}
            self._latest_prices = dict(prices)
            self._update_risk_state(prices)
            self._persist_portfolio_state(prices)

            if self._trading_halted():
                return

            for sym, candle in candles.items():
                candle_open_time = getattr(candle, "open_time", None)
                if candle_open_time is not None:
                    if candle_open_time.tzinfo is not None:
                        candle_open_time = candle_open_time.astimezone(timezone.utc).replace(tzinfo=None)
                    last_processed = self._last_processed_candle.get(sym)
                    if last_processed == candle_open_time:
                        continue

                decision = compute_strategy_decision(
                    sess,
                    candle,
                    strategy_name=self._strategy_name,
                    strategy_params=self._strategy_params,
                )
                self._last_regime[sym] = decision.regime.value
                if decision.signal == Signal.BUY:
                    atr = self._compute_atr(sess, sym)
                    await self._auto_buy(sym, candle.close, atr, prices, decision.regime.value)
                elif decision.signal == Signal.SELL:
                    await self._auto_sell(sym, candle.close, decision.regime.value)

                if candle_open_time is not None:
                    self._last_processed_candle[sym] = candle_open_time

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

    # ── live order submission ──────────────────────────────────────────────────

    async def _submit_order(self, sym: str, side: str, qty: float) -> bool:
        """Submit a real Binance market order when LIVE_TRADE_ENABLED=True, else no-op."""
        if not LIVE_TRADE_ENABLED:
            return True
        if self._binance_client is None:
            log.error("LIVE_TRADE_ENABLED=True but _binance_client not set — skipping real order",
                      extra={"symbol": sym, "side": side})
            return False
        try:
            await asyncio.wait_for(
                self._binance_client.create_order(
                    symbol=sym,
                    side=side,
                    type="MARKET",
                    quantity=round(qty, 6),
                ),
                timeout=10.0,
            )
            log.info("LIVE ORDER submitted", extra={"symbol": sym, "side": side, "qty": qty})
            return True
        except Exception as exc:  # noqa: BLE001
            log.error("LIVE ORDER failed: %s", exc, extra={"symbol": sym, "side": side})
            return False

    # ── order execution ────────────────────────────────────────────────────────

    async def _auto_buy(self, sym: str, price: float, atr: float = 0.0,
                        prices: Optional[Dict[str, float]] = None, regime: str = "UNKNOWN"):
        if price <= 0:
            return
        if self.positions.get(sym, 0) > 0:
            log.info("AUTO BUY skipped: open position already exists.", extra={"symbol": sym})
            return
        if self._would_duplicate_persisted_side(sym, "BUY"):
            log.warning(
                "AUTO BUY skipped: persisted trade history already ends with BUY for symbol.",
                extra={"symbol": sym, "run_mode": self._runtime_mode()},
            )
            self._restore_runtime_state()
            return

        # Use all known prices for accurate equity; merge sym's current price in
        all_prices = dict(prices or {})
        all_prices[sym] = price
        max_notional = float(STARTING_BALANCE_USD) * float(POSITION_SIZE_PCT)

        # ATR-based sizing; fall back to flat POSITION_SIZE_PCT when ATR unavailable
        if atr > 0:
            qty = atr_position_size(self._equity(all_prices), atr)
        else:
            qty = max_notional / price

        qty = min(float(qty), max_notional / price if price > 0 else 0.0)

        if qty <= 0:
            return
        cost = qty * price * (1 + FEE_RATE)
        if cost > self.cash:
            return
        submitted = await self._submit_order(sym, "BUY", qty)
        if not submitted:
            log.warning("AUTO BUY aborted: live order submission failed.",
                        extra={"symbol": sym, "qty": round(qty, 6), "price": round(price, 4)})
            return
        self.cash -= cost
        self.positions[sym] = self.positions.get(sym, 0) + qty
        self.cost_basis[sym] = self.cost_basis.get(sym, 0) + cost
        self._record_trade(sym, "BUY", qty, price, qty * price * FEE_RATE, 0.0, regime)
        log.info("AUTO BUY", extra={
            "symbol": sym, "qty": round(qty, 6), "price": round(price, 4),
            "atr": round(atr, 4), "cost": round(cost, 4), "cash": round(self.cash, 4),
        })
        send_telegram_alert(_token(), _chat_id(),
                            f"🤖 Auto-BUY {sym} qty={qty:.4f} @ {price:.2f}")

    async def _auto_sell(self, sym: str, price: float, regime: str = "UNKNOWN"):
        if price <= 0:
            return
        qty = self.positions.get(sym, 0)
        if qty == 0:
            if self._would_duplicate_persisted_side(sym, "SELL"):
                log.warning(
                    "AUTO SELL skipped: persisted trade history already ends with SELL for symbol.",
                    extra={"symbol": sym, "run_mode": self._runtime_mode()},
                )
            return
        if self._would_duplicate_persisted_side(sym, "SELL"):
            log.warning(
                "AUTO SELL skipped: persisted trade history already ends with SELL for symbol.",
                extra={"symbol": sym, "run_mode": self._runtime_mode()},
            )
            self._restore_runtime_state()
            return
        cost = self.cost_basis.get(sym, 0)
        submitted = await self._submit_order(sym, "SELL", qty)
        if not submitted:
            log.warning("AUTO SELL aborted: live order submission failed.",
                        extra={"symbol": sym, "qty": round(qty, 6), "price": round(price, 4)})
            return
        self.positions.pop(sym, None)
        proceeds = qty * price * (1 - FEE_RATE)
        self.cash += proceeds
        self.cost_basis.pop(sym, None)
        pnl = proceeds - cost
        self.realised += pnl
        self._record_trade(sym, "SELL", qty, price, qty * price * FEE_RATE, pnl, regime)
        log.info("AUTO SELL", extra={
            "symbol": sym, "qty": round(qty, 6), "price": round(price, 4),
            "proceeds": round(proceeds, 4), "pnl": round(pnl, 4),
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
            await self._auto_buy(sym, candle.close, atr, regime="MANUAL")

    async def _manual_sell(self, sym: str):
        price = await self._latest_price(sym)
        await self._auto_sell(sym, price, regime="MANUAL")

    async def _latest_price(self, sym: str) -> float:
        with SessionLocal() as sess:
            candle = (
                sess.query(Candle)
                    .filter(Candle.symbol == sym)
                    .order_by(Candle.open_time.desc())
                    .first()
            )
            return candle.close if candle else 0.0

    def _persist_portfolio_state(self, prices: Optional[Dict[str, float]] = None) -> None:
        equity = self._equity(prices)
        unreal_pnl = equity - self.cash - self.realised

        with SessionLocal() as sess:
            upsert_portfolio(sess, self.cash, equity, unreal_pnl)
            now = datetime.now(tz=timezone.utc)
            minute_bucket = now.replace(second=0, microsecond=0)
            should_snapshot = (
                self._last_snapshot_minute is None
                or (minute_bucket - self._last_snapshot_minute).total_seconds() >= PORTFOLIO_SNAP_MIN * 60
            )
            if should_snapshot:
                snapshot_portfolio(
                    sess,
                    run_mode="live" if LIVE_TRADE_ENABLED else "paper",
                    artifact_id=self._strategy_artifact_id,
                    strategy_name=self._strategy_name,
                    strategy_version=self._strategy_version,
                    strategy_code_hash=self._strategy_code_hash,
                    strategy_provenance=self._strategy_provenance,
                    balance=self.cash,
                    equity=equity,
                    unreal_pnl=unreal_pnl,
                )
                self._last_snapshot_minute = minute_bucket
            sess.commit()

    def get_status_snapshot(self) -> dict:
        """Return a read-only runtime status snapshot for operator-facing heartbeats."""
        latest_prices = dict(self._latest_prices)
        last_candle_ts = max(self._last_processed_candle.values()) if self._last_processed_candle else None
        halted = self._daily_tracker.is_halted or self._drawdown_cb.is_halted or self._force_halt
        return {
            "run_mode": "live" if LIVE_TRADE_ENABLED else "paper",
            "strategy_name": self._strategy_name,
            "strategy_version": self._strategy_version,
            "artifact_id": self._strategy_artifact_id,
            "strategy_code_hash": self._strategy_code_hash,
            "strategy_provenance": self._strategy_provenance,
            "symbols": _current_runtime_symbols(),
            "cash": self.cash,
            "equity": self._equity(latest_prices),
            "realized_pnl": self.realised,
            "open_position_count": len(self.positions),
            "last_processed_candle_ts": last_candle_ts,
            "last_trade_ts": self._last_trade_ts,
            "force_halt": self._force_halt,
            "trading_halted": halted,
            "daily_loss_halted": self._daily_tracker.is_halted,
            "drawdown_halted": self._drawdown_cb.is_halted,
        }

    def _record_trade(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        fee: float,
        pnl: float,
        regime: str,
    ) -> None:
        trade_ts  = datetime.now(tz=timezone.utc)
        trade_obj = Trade(
            ts=trade_ts,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            fee=fee,
            pnl=pnl,
            artifact_id=self._strategy_artifact_id,
            strategy_name=self._strategy_name,
            strategy_version=self._strategy_version,
            strategy_code_hash=self._strategy_code_hash,
            strategy_provenance=self._strategy_provenance,
            run_mode="live" if LIVE_TRADE_ENABLED else "paper",
            regime=regime,
            integrity_status="valid",
            integrity_note=None,
        )
        with SessionLocal() as sess:
            sess.add(trade_obj)
            sess.commit()

        try:
            from trading_diary.service import record_trade_diary_entry as _rde
            _rde(trade_obj)
        except Exception:
            pass  # diary write must never break paper trading

        self._last_trade_ts = trade_ts


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


def _current_runtime_symbols() -> list[str]:
    """Return the effective runtime symbol list, preserving legacy patched SYMBOLS in tests."""
    try:
        symbols = list_runtime_symbols()
    except Exception:
        symbols = []
    if symbols == list(getattr(_config, "SYMBOLS", [])) and list(SYMBOLS) != list(getattr(_config, "SYMBOLS", [])):
        return list(SYMBOLS)
    return symbols or list(SYMBOLS)
