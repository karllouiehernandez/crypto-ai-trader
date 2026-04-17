# crypto_ai_trader/strategy/risk.py
"""
Risk management primitives.

All functions/classes are pure or stateful-but-isolated — no DB, no I/O.
Designed to be called from simulator/paper_trader.py each tick.

Public API:
    atr_position_size(equity, atr, risk_pct, atr_multiplier) -> float
    DailyLossTracker   — tracks intraday P&L, signals halt at threshold
    DrawdownCircuitBreaker — tracks equity peak, signals halt at threshold
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from config import RISK_PCT_PER_TRADE, ATR_STOP_MULTIPLIER, DAILY_LOSS_LIMIT_PCT, DRAWDOWN_HALT_PCT

log = logging.getLogger(__name__)


# ── ATR position sizing ────────────────────────────────────────────────────────

def atr_position_size(
    equity: float,
    atr: float,
    risk_pct: float = RISK_PCT_PER_TRADE,
    atr_multiplier: float = ATR_STOP_MULTIPLIER,
) -> float:
    """
    Return the position size (in units of the asset) using ATR-based risk sizing.

    Formula:  size = (equity * risk_pct) / (atr_multiplier * atr)

    This ensures that if the price moves against us by `atr_multiplier * atr`,
    the loss equals exactly `equity * risk_pct` (e.g. 1% of equity).

    Returns 0.0 when ATR is zero or negative to prevent division by zero.
    """
    if atr <= 0 or equity <= 0:
        return 0.0
    stop_distance = atr_multiplier * atr
    return (equity * risk_pct) / stop_distance


# ── Daily loss tracker ─────────────────────────────────────────────────────────

class DailyLossTracker:
    """
    Tracks intraday realised equity and halts trading when the daily loss
    exceeds `limit_pct` of the start-of-day equity.

    Usage:
        tracker = DailyLossTracker(start_equity=1000.0)
        tracker.update(current_equity=970.0)
        if tracker.is_halted:
            # skip new orders
    """

    def __init__(
        self,
        start_equity: float,
        limit_pct: float = DAILY_LOSS_LIMIT_PCT,
    ) -> None:
        if start_equity <= 0:
            raise ValueError("start_equity must be positive")
        self._start_equity  = start_equity
        self._limit_pct     = limit_pct
        self._current_equity = start_equity
        self._halted        = False
        self._day           = date.today()

    # ── public interface ───────────────────────────────────────────────────────

    def update(self, current_equity: float) -> None:
        """Call after every trade or at each tick with the latest total equity."""
        self._maybe_reset_day()
        self._current_equity = current_equity
        loss_pct = (self._current_equity - self._start_equity) / self._start_equity
        if loss_pct <= -self._limit_pct and not self._halted:
            self._halted = True
            log.warning(
                "DailyLossTracker: HALT — daily loss %.2f%% exceeds limit %.2f%%",
                loss_pct * 100,
                self._limit_pct * 100,
            )

    @property
    def is_halted(self) -> bool:
        """True when the daily loss limit has been breached."""
        self._maybe_reset_day()
        return self._halted

    def reset(self, new_start_equity: float) -> None:
        """Manually reset (e.g. at start of a new day or after a review)."""
        if new_start_equity <= 0:
            raise ValueError("new_start_equity must be positive")
        self._start_equity   = new_start_equity
        self._current_equity = new_start_equity
        self._halted         = False
        self._day            = date.today()

    @property
    def loss_pct(self) -> float:
        """Current intraday loss as a fraction (negative = loss)."""
        return (self._current_equity - self._start_equity) / self._start_equity

    # ── internal ───────────────────────────────────────────────────────────────

    def _maybe_reset_day(self) -> None:
        """Auto-reset at calendar day rollover."""
        today = date.today()
        if today != self._day:
            log.info("DailyLossTracker: new day — resetting (start equity=%.2f)", self._current_equity)
            self._start_equity   = self._current_equity
            self._halted         = False
            self._day            = today


# ── Drawdown circuit breaker ───────────────────────────────────────────────────

class DrawdownCircuitBreaker:
    """
    Tracks the running equity peak and halts trading when the drawdown from
    that peak exceeds `halt_pct`.

    Usage:
        cb = DrawdownCircuitBreaker(initial_equity=1000.0)
        cb.update(current_equity=840.0)
        if cb.is_halted:
            # require manual review before resuming
    """

    def __init__(
        self,
        initial_equity: float,
        halt_pct: float = DRAWDOWN_HALT_PCT,
    ) -> None:
        if initial_equity <= 0:
            raise ValueError("initial_equity must be positive")
        self._peak      = initial_equity
        self._halt_pct  = halt_pct
        self._halted    = False
        self._current   = initial_equity

    # ── public interface ───────────────────────────────────────────────────────

    def update(self, current_equity: float) -> None:
        """Call after every trade or at each tick with the latest total equity."""
        self._current = current_equity
        if current_equity > self._peak:
            self._peak = current_equity

        drawdown = (self._peak - current_equity) / self._peak
        if drawdown >= self._halt_pct and not self._halted:
            self._halted = True
            log.warning(
                "DrawdownCircuitBreaker: HALT — drawdown %.2f%% from peak $%.2f (current $%.2f)",
                drawdown * 100,
                self._peak,
                current_equity,
            )

    @property
    def is_halted(self) -> bool:
        return self._halted

    @property
    def drawdown(self) -> float:
        """Current drawdown from peak as a fraction (0.0 = at peak)."""
        if self._peak <= 0:
            return 0.0
        return (self._peak - self._current) / self._peak

    @property
    def peak(self) -> float:
        return self._peak

    def reset(self, new_equity: float) -> None:
        """Manually resume trading after a review. Resets peak to current equity."""
        if new_equity <= 0:
            raise ValueError("new_equity must be positive")
        self._peak    = new_equity
        self._current = new_equity
        self._halted  = False
        log.info("DrawdownCircuitBreaker: manually reset, new peak=%.2f", new_equity)
