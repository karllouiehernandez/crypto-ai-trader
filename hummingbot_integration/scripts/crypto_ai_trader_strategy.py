"""
crypto_ai_trader_strategy.py
────────────────────────────
Hummingbot ScriptStrategy that wraps the crypto_ai_trader signal engine.

DROP this file into Hummingbot's `scripts/` directory, then run inside Hummingbot:
    start --script crypto_ai_trader_strategy.py

All pure-function logic from the original project (ta_features, regime detection,
signal strategies, risk management) is inlined here so this script works as a
completely self-contained Hummingbot script with no external project dependencies.

REQUIRES: `ta` library in Hummingbot's environment.
  → Install once inside the running container:
      conda run -n hummingbot pip install ta
  → Or use the provided Dockerfile that pre-installs it.

Paper trading (default):
    Connector : binance_paper_trade
    Pairs     : BTC-USDT, ETH-USDT, BNB-USDT
    Interval  : 1m candles, signals evaluated every 60 s
    Risk      : ATR-based 1% equity per trade, 3% daily loss halt, 15% drawdown halt
"""
from __future__ import annotations

import logging
from datetime import date as _date
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional

import pandas as pd

# ── Hummingbot imports ────────────────────────────────────────────────────────
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

log = logging.getLogger(__name__)

# =============================================================================
# SECTION 1 — Enums (mirrors strategy/signals.py + strategy/regime.py)
# =============================================================================

class Signal(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Regime(str, Enum):
    TRENDING = "TRENDING"
    RANGING  = "RANGING"
    SQUEEZE  = "SQUEEZE"
    HIGH_VOL = "HIGH_VOL"


# =============================================================================
# SECTION 2 — Indicator computation (mirrors strategy/ta_features.py)
# =============================================================================

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all technical indicators required by the signal strategies.
    Uses the `ta` library to mirror behaviour of the original project exactly.
    Drops rows with NaN (indicator warm-up period).
    """
    import ta  # deferred import — fails loudly if library is missing

    if df.empty:
        return df

    out = df.copy()
    out["ma_21"]        = ta.trend.sma_indicator(out["close"], window=21)
    out["ma_55"]        = ta.trend.sma_indicator(out["close"], window=55)

    _macd               = ta.trend.MACD(out["close"])
    out["macd"]         = _macd.macd()
    out["macd_s"]       = _macd.macd_signal()

    out["rsi_14"]       = ta.momentum.RSIIndicator(out["close"], window=14).rsi()

    _bb                 = ta.volatility.BollingerBands(out["close"], window=20)
    out["bb_hi"]        = _bb.bollinger_hband()
    out["bb_lo"]        = _bb.bollinger_lband()
    out["bb_width"]     = _bb.bollinger_wband()

    out["ema_9"]        = ta.trend.EMAIndicator(out["close"], window=9).ema_indicator()
    out["ema_21"]       = ta.trend.EMAIndicator(out["close"], window=21).ema_indicator()
    out["ema_55"]       = ta.trend.EMAIndicator(out["close"], window=55).ema_indicator()
    out["ema_200"]      = ta.trend.EMAIndicator(out["close"], window=200).ema_indicator()

    out["volume_ma_20"] = ta.trend.sma_indicator(out["volume"], window=20)

    _adx                = ta.trend.ADXIndicator(out["high"], out["low"], out["close"], window=14)
    out["adx_14"]       = _adx.adx()

    out["atr_14"]       = ta.volatility.AverageTrueRange(
        out["high"], out["low"], out["close"], window=14
    ).average_true_range()

    return out.dropna()


# =============================================================================
# SECTION 3 — Regime detection (mirrors strategy/regime.py)
# =============================================================================

# Thresholds (match config.py)
_ADX_TREND_THRESHOLD         = 25
_BB_SQUEEZE_PERCENTILE       = 20
_HIGH_VOL_MULTIPLIER         = 2.0
_HIGH_VOL_SHORT_WINDOW       = 10


def detect_regime(df: pd.DataFrame) -> Regime:
    """Classify the current market regime. Priority: HIGH_VOL > SQUEEZE > TRENDING > RANGING."""
    if len(df) < 2:
        return Regime.RANGING
    if _is_high_vol(df):
        return Regime.HIGH_VOL
    if _is_squeeze(df):
        return Regime.SQUEEZE
    if df["adx_14"].iloc[-1] > _ADX_TREND_THRESHOLD:
        return Regime.TRENDING
    return Regime.RANGING


def _is_high_vol(df: pd.DataFrame) -> bool:
    if len(df) <= _HIGH_VOL_SHORT_WINDOW:
        return False
    returns = df["close"].pct_change().dropna()
    if len(returns) <= _HIGH_VOL_SHORT_WINDOW:
        return False
    baseline_vol = returns.iloc[:-_HIGH_VOL_SHORT_WINDOW].std()
    recent_vol   = returns.iloc[-_HIGH_VOL_SHORT_WINDOW:].std()
    if baseline_vol == 0:
        return recent_vol > 0
    return recent_vol > _HIGH_VOL_MULTIPLIER * baseline_vol


def _is_squeeze(df: pd.DataFrame) -> bool:
    if "bb_width" not in df.columns or len(df) < 21:
        return False
    threshold = df["bb_width"].iloc[:-1].quantile(_BB_SQUEEZE_PERCENTILE / 100.0)
    return float(df["bb_width"].iloc[-1]) < threshold


# =============================================================================
# SECTION 4 — Signal functions (mirrors signal_momentum, signal_breakout,
#              and the RANGING branch of signal_engine)
# =============================================================================

_VOLUME_MULT     = 1.5   # entry volume >= this × volume_ma_20
_PULLBACK_TOL    = 0.005 # momentum: price within 0.5% of EMA-21
_BREAKOUT_LOOKBACK = 20
_BREAKOUT_VOL_MULT = 2.0


def _mean_reversion_signal(df: pd.DataFrame) -> Signal:
    """RANGING regime: RSI + BB + MACD crossover + EMA-200 filter + volume."""
    if len(df) < 2:
        return Signal.HOLD
    last, prev = df.iloc[-1], df.iloc[-2]
    if (
        last["rsi_14"] < 35
        and last["close"] < last["bb_lo"]
        and last["macd"] > last["macd_s"]
        and prev["macd"] <= prev["macd_s"]
        and last["close"] > last["ema_200"]
        and last["volume"] >= _VOLUME_MULT * last["volume_ma_20"]
    ):
        return Signal.BUY
    if (
        last["rsi_14"] > 70
        and last["close"] > last["bb_hi"]
        and last["macd"] < last["macd_s"]
        and prev["macd"] >= prev["macd_s"]
        and last["close"] < last["ema_200"]
        and last["volume"] >= _VOLUME_MULT * last["volume_ma_20"]
    ):
        return Signal.SELL
    return Signal.HOLD


def _momentum_signal(df: pd.DataFrame) -> Signal:
    """TRENDING regime: EMA stack + ADX + pullback-to-EMA21 + volume."""
    if len(df) < 2:
        return Signal.HOLD
    last, prev = df.iloc[-1], df.iloc[-2]
    pullback_pct = (
        (last["close"] - last["ema_21"]) / last["ema_21"]
        if last["ema_21"] > 0
        else float("inf")
    )
    if (
        last["ema_9"] > last["ema_21"]
        and last["ema_21"] > last["ema_55"]
        and last["adx_14"] > _ADX_TREND_THRESHOLD
        and 0.0 <= pullback_pct <= _PULLBACK_TOL
        and last["volume"] >= _VOLUME_MULT * last["volume_ma_20"]
    ):
        return Signal.BUY
    if last["ema_9"] < last["ema_21"] and prev["ema_9"] >= prev["ema_21"]:
        return Signal.SELL
    return Signal.HOLD


def _breakout_signal(df: pd.DataFrame) -> Signal:
    """SQUEEZE regime: close above prior N-period high + 2× volume."""
    if len(df) < _BREAKOUT_LOOKBACK + 1:
        return Signal.HOLD
    last  = df.iloc[-1]
    prior = df.iloc[-(_BREAKOUT_LOOKBACK + 1):-1]
    if (
        last["close"] > prior["high"].max()
        and last["volume"] >= _BREAKOUT_VOL_MULT * last["volume_ma_20"]
    ):
        return Signal.BUY
    if last["close"] < prior["low"].min():
        return Signal.SELL
    return Signal.HOLD


def compute_signal(df: pd.DataFrame) -> tuple[Signal, Regime]:
    """
    Main signal router — mirrors signal_engine.compute_signal().
    Returns (Signal, Regime) so the caller can log the regime.
    """
    if len(df) < 2:
        return Signal.HOLD, Regime.RANGING
    regime = detect_regime(df)
    if regime == Regime.HIGH_VOL:
        return Signal.HOLD, regime
    if regime == Regime.TRENDING:
        return _momentum_signal(df), regime
    if regime == Regime.SQUEEZE:
        return _breakout_signal(df), regime
    return _mean_reversion_signal(df), regime


# =============================================================================
# SECTION 5 — Risk management (mirrors strategy/risk.py)
# =============================================================================

_RISK_PCT        = 0.01   # 1% equity at risk per trade
_ATR_MULT        = 1.5    # stop = ATR × this
_DAILY_LOSS_HALT = 0.03   # halt if daily P&L < -3%
_DRAWDOWN_HALT   = 0.15   # halt if equity drops 15% from peak
_MAX_PCT_PER_PAIR = 0.20  # hard cap: no single trade > 20% of equity


def _atr_position_size(equity: float, atr: float, price: float) -> float:
    """Return position size in base-asset units using ATR-based 1%-equity risk."""
    if atr <= 0 or equity <= 0 or price <= 0:
        return 0.0
    stop_distance = _ATR_MULT * atr
    size = (equity * _RISK_PCT) / stop_distance
    # Hard cap: never allocate more than _MAX_PCT_PER_PAIR of equity to one trade
    max_size = (equity * _MAX_PCT_PER_PAIR) / price
    return min(size, max_size)


class _DailyLossTracker:
    def __init__(self, start_equity: float) -> None:
        self._start   = start_equity
        self._current = start_equity
        self._halted  = False
        self._day     = _date.today()

    def update(self, equity: float) -> None:
        self._maybe_reset()
        self._current = equity
        if (self._current - self._start) / self._start <= -_DAILY_LOSS_HALT and not self._halted:
            self._halted = True
            log.warning(
                "DailyLossTracker: HALTED — daily loss %.2f%% exceeded limit %.0f%%",
                abs((self._current - self._start) / self._start) * 100,
                _DAILY_LOSS_HALT * 100,
            )

    @property
    def is_halted(self) -> bool:
        self._maybe_reset()
        return self._halted

    @property
    def loss_pct(self) -> float:
        return (self._current - self._start) / self._start

    def _maybe_reset(self) -> None:
        today = _date.today()
        if today != self._day:
            log.info("DailyLossTracker: new day reset (start=%.2f)", self._current)
            self._start   = self._current
            self._halted  = False
            self._day     = today


class _DrawdownCircuitBreaker:
    def __init__(self, initial_equity: float) -> None:
        self._peak    = initial_equity
        self._current = initial_equity
        self._halted  = False

    def update(self, equity: float) -> None:
        self._current = equity
        if equity > self._peak:
            self._peak = equity
        dd = (self._peak - equity) / self._peak if self._peak > 0 else 0.0
        if dd >= _DRAWDOWN_HALT and not self._halted:
            self._halted = True
            log.warning(
                "DrawdownCircuitBreaker: HALTED — drawdown %.2f%% from peak $%.2f",
                dd * 100,
                self._peak,
            )

    @property
    def is_halted(self) -> bool:
        return self._halted

    @property
    def drawdown(self) -> float:
        return (self._peak - self._current) / self._peak if self._peak > 0 else 0.0

    @property
    def peak(self) -> float:
        return self._peak

    def reset(self, new_equity: float) -> None:
        self._peak    = new_equity
        self._current = new_equity
        self._halted  = False
        log.info("DrawdownCircuitBreaker: manually reset, new peak=%.2f", new_equity)


# =============================================================================
# SECTION 6 — Hummingbot ScriptStrategy
# =============================================================================

# Minimum candles before computing a signal (warm-up for EMA-200)
_MIN_CANDLES = 210


class CryptoAITraderStrategy(ScriptStrategyBase):
    """
    Paper-trading strategy that routes live Binance 1m candles through the
    crypto_ai_trader signal engine and executes orders via Hummingbot's
    binance_paper_trade connector.

    Supported regimes:
        RANGING   → mean-reversion (RSI + BB + MACD)
        TRENDING  → momentum (EMA stack + ADX)
        SQUEEZE   → breakout (prior N-high/low + 2× volume)
        HIGH_VOL  → halt (no new entries)

    Risk controls (all three run every tick):
        • ATR-based position sizing (1% equity risk)
        • Daily loss limit (−3% of day-start equity → halt)
        • Drawdown circuit breaker (−15% from equity peak → halt)
    """

    # ── User-configurable class variables ─────────────────────────────────────
    exchange         = "binance_paper_trade"
    trading_pairs    = ["BTC-USDT", "ETH-USDT", "BNB-USDT"]
    candle_exchange  = "binance"   # price feed source (public, no API key needed)
    candle_interval  = "1m"
    candle_max_records = 250       # >210 to cover EMA-200 warm-up
    signal_interval  = 60          # evaluate signals every N seconds (aligns with 1m candles)

    # Hummingbot requires this to know which markets to connect
    markets = {exchange: set(trading_pairs)}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def __init__(self, connectors: Dict[str, ConnectorBase]) -> None:
        super().__init__(connectors)

        # One candle feed per trading pair
        self._candles: Dict[str, object] = {}
        for pair in self.trading_pairs:
            feed = CandlesFactory.get_candle(
                connector=self.candle_exchange,
                trading_pair=pair,
                interval=self.candle_interval,
                max_records=self.candle_max_records,
            )
            feed.start()
            self._candles[pair] = feed

        # Per-pair state
        self._positions:     Dict[str, float]  = {p: 0.0       for p in self.trading_pairs}
        self._entry_prices:  Dict[str, float]  = {p: 0.0       for p in self.trading_pairs}
        self._last_signals:  Dict[str, Signal] = {p: Signal.HOLD for p in self.trading_pairs}
        self._last_regimes:  Dict[str, Regime] = {p: Regime.RANGING for p in self.trading_pairs}

        # Risk trackers — initialised on first tick once balance is known
        self._daily_loss:  Optional[_DailyLossTracker]      = None
        self._drawdown_cb: Optional[_DrawdownCircuitBreaker] = None

        self._tick_count = 0
        log.info("CryptoAITraderStrategy initialised for pairs: %s", self.trading_pairs)

    def on_stop(self) -> None:
        for feed in self._candles.values():
            feed.stop()

    # ── Main tick ─────────────────────────────────────────────────────────────

    def on_tick(self) -> None:
        """Called every second by Hummingbot. Rate-limited to signal_interval seconds."""
        self._tick_count += 1
        if self._tick_count % self.signal_interval != 0:
            return

        if not all(feed.is_ready for feed in self._candles.values()):
            log.debug("Waiting for candle feeds to fill…")
            return

        equity = float(self.connectors[self.exchange].get_available_balance("USDT"))

        # Lazy-init risk trackers on first real tick
        if self._daily_loss is None:
            self._daily_loss  = _DailyLossTracker(equity)
            self._drawdown_cb = _DrawdownCircuitBreaker(equity)

        self._daily_loss.update(equity)
        self._drawdown_cb.update(equity)

        if self._daily_loss.is_halted:
            log.warning("[RISK] Daily loss limit breached — skipping all signals")
            return
        if self._drawdown_cb.is_halted:
            log.warning("[RISK] Drawdown circuit breaker triggered — skipping all signals")
            return

        for pair in self.trading_pairs:
            try:
                self._process_pair(pair, equity)
            except Exception as exc:  # noqa: BLE001
                log.exception("[%s] Error processing pair: %s", pair, exc)

    # ── Per-pair signal + execution ───────────────────────────────────────────

    def _process_pair(self, pair: str, equity: float) -> None:
        df_raw = self._candles[pair].candles_df.copy()

        if len(df_raw) < _MIN_CANDLES:
            log.debug("[%s] Not enough candles yet (%d/%d)", pair, len(df_raw), _MIN_CANDLES)
            return

        df = add_indicators(df_raw)
        if len(df) < 2:
            return

        signal, regime = compute_signal(df)
        self._last_signals[pair] = signal
        self._last_regimes[pair] = regime

        last  = df.iloc[-1]
        price = float(last["close"])
        atr   = float(last.get("atr_14", 0.0))
        rsi   = float(last.get("rsi_14", 0.0))
        adx   = float(last.get("adx_14", 0.0))

        log.info(
            "[%s] signal=%-4s regime=%-8s price=%.4f rsi=%.1f adx=%.1f",
            pair, signal.value, regime.value, price, rsi, adx,
        )

        has_position = self._positions[pair] > 0

        if signal == Signal.BUY and not has_position:
            self._open_long(pair, equity, price, atr, regime)

        elif signal == Signal.SELL and has_position:
            self._close_long(pair, price, regime)

    def _open_long(
        self, pair: str, equity: float, price: float, atr: float, regime: Regime
    ) -> None:
        size = _atr_position_size(equity, atr, price)
        if size <= 0:
            log.warning("[%s] ATR position size is zero (atr=%.6f) — skip BUY", pair, atr)
            return

        notional = size * price
        if notional < 10.0:
            log.debug("[%s] Notional $%.2f below $10 minimum — skip BUY", pair, notional)
            return

        order_size = Decimal(str(round(size, 6)))
        self.buy(self.exchange, pair, order_size, OrderType.MARKET)
        self._positions[pair]    = float(order_size)
        self._entry_prices[pair] = price
        log.info(
            "[%s] ✅ BUY %.6f @ %.4f  notional=$%.2f  regime=%s",
            pair, float(order_size), price, notional, regime.value,
        )

    def _close_long(self, pair: str, price: float, regime: Regime) -> None:
        size       = self._positions[pair]
        entry      = self._entry_prices[pair]
        pnl        = (price - entry) * size
        order_size = Decimal(str(round(size, 6)))

        self.sell(self.exchange, pair, order_size, OrderType.MARKET)
        self._positions[pair]    = 0.0
        self._entry_prices[pair] = 0.0
        log.info(
            "[%s] 🔴 SELL %.6f @ %.4f  PnL=$%.4f  regime=%s",
            pair, size, price, pnl, regime.value,
        )

    # ── Dashboard (shown by `status` command in Hummingbot CLI) ───────────────

    def format_status(self) -> str:
        lines = [
            "=" * 52,
            "  CryptoAI Trader — Paper Trading Status",
            "=" * 52,
        ]

        try:
            equity = float(self.connectors[self.exchange].get_available_balance("USDT"))
            lines.append(f"  USDT Balance  : ${equity:>10.2f}")
        except Exception:
            lines.append("  USDT Balance  : unavailable")

        if self._drawdown_cb:
            lines.append(
                f"  Drawdown      : {self._drawdown_cb.drawdown * 100:>6.2f}%  "
                f"(peak ${self._drawdown_cb.peak:.2f})"
            )
            lines.append(f"  DD Halted     : {self._drawdown_cb.is_halted}")
        if self._daily_loss:
            lines.append(
                f"  Daily P&L     : {self._daily_loss.loss_pct * 100:>+6.2f}%"
            )
            lines.append(f"  Daily Halted  : {self._daily_loss.is_halted}")

        lines.append("")
        lines.append(f"  {'Pair':<12} {'Signal':<6} {'Regime':<10} {'Position':>12} {'Entry':>10} {'Candles'}")
        lines.append("  " + "-" * 68)
        for pair in self.trading_pairs:
            pos   = self._positions[pair]
            entry = self._entry_prices[pair]
            sig   = self._last_signals[pair].value
            rgm   = self._last_regimes[pair].value
            feed  = self._candles.get(pair)
            ready = "✓" if (feed and feed.is_ready) else "…"
            lines.append(
                f"  {pair:<12} {sig:<6} {rgm:<10} {pos:>12.6f} {entry:>10.4f}  {ready}"
            )

        lines.append("=" * 52)
        return "\n".join(lines)
