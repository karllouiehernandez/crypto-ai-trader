"""strategies/ema200_filtered_momentum.py — EXP-001

Momentum and breakout strategies with a 200-period EMA trend filter.

Hypothesis: requiring price to be on the EMA-200 side before entering reduces
counter-trend losses in TRENDING and SQUEEZE regimes without hurting win rate.

Active only in TRENDING and SQUEEZE regimes.  RANGING regime already applies
its own EMA-200 gate inside signal_engine.py / rsi_mean_reversion_v1.
"""

from __future__ import annotations

import pandas as pd

from config import (
    ADX_TREND_THRESHOLD,
    BREAKOUT_LOOKBACK,
    BREAKOUT_VOLUME_MULT,
    MOMENTUM_PULLBACK_TOL,
    VOLUME_CONFIRMATION_MULT,
)
from strategy.base import StrategyBase
from strategy.regime import Regime
from strategy.signals import Signal


class EMA200FilteredMomentumStrategy(StrategyBase):
    """Momentum + breakout strategies gated by the 200-period EMA trend filter.

    TRENDING regime:
        BUY  — EMA stack (9>21>55) + ADX>25 + pullback to EMA-21 + volume spike
                + close ABOVE EMA-200
        SELL — EMA-9 crosses below EMA-21

    SQUEEZE regime:
        BUY  — close breaks above prior N-period high + volume 2× avg
                + close ABOVE EMA-200
        SELL — close breaks below prior N-period low
    """

    name = "ema200_filtered_momentum"
    display_name = "EMA-200 Filtered Momentum (EXP-001)"
    description = (
        "Momentum and breakout strategies with a 200-period EMA trend filter. "
        "Only takes longs when price is above EMA-200; shorts below EMA-200. "
        "EXP-001: tests whether long-term trend alignment reduces counter-trend losses."
    )
    version = "1.0.0"
    regimes = [Regime.TRENDING, Regime.SQUEEZE]

    def default_params(self) -> dict:
        return {}

    def param_schema(self) -> list[dict]:
        return []

    # Method stubs — regime-aware logic is handled in decide()
    def should_long(self, df: pd.DataFrame) -> bool:
        return False

    def should_short(self, df: pd.DataFrame) -> bool:
        return False

    def decide(self, df: pd.DataFrame, regime: Regime | None = None) -> Signal:
        if len(df) < 2:
            return Signal.HOLD
        last = df.iloc[-1]
        prev = df.iloc[-2]
        if regime == Regime.TRENDING:
            return self._momentum_decide(last, prev)
        if regime == Regime.SQUEEZE:
            return self._breakout_decide(df, last)
        return Signal.HOLD

    # ── private helpers ────────────────────────────────────────────────────────

    def _momentum_decide(self, last, prev) -> Signal:
        pullback_pct = (
            (last.close - last.ema_21) / last.ema_21
            if last.ema_21 > 0
            else float("inf")
        )
        if (
            last.close > last.ema_200
            and last.ema_9 > last.ema_21
            and last.ema_21 > last.ema_55
            and last.adx_14 > ADX_TREND_THRESHOLD
            and 0.0 <= pullback_pct <= MOMENTUM_PULLBACK_TOL
            and last.volume >= VOLUME_CONFIRMATION_MULT * last.volume_ma_20
        ):
            return Signal.BUY

        if last.ema_9 < last.ema_21 and prev.ema_9 >= prev.ema_21:
            return Signal.SELL

        return Signal.HOLD

    def _breakout_decide(self, df: pd.DataFrame, last) -> Signal:
        if len(df) < BREAKOUT_LOOKBACK + 1:
            return Signal.HOLD

        prior = df.iloc[-(BREAKOUT_LOOKBACK + 1):-1]
        prior_high = prior["high"].max()
        prior_low = prior["low"].min()

        if (
            last.close > last.ema_200
            and last.close > prior_high
            and last.volume >= BREAKOUT_VOLUME_MULT * last.volume_ma_20
        ):
            return Signal.BUY

        if last.close < prior_low:
            return Signal.SELL

        return Signal.HOLD
