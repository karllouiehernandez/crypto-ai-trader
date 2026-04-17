"""Built-in selectable strategies for the Jesse-like strategy workbench."""

from __future__ import annotations

import pandas as pd

from config import VOLUME_CONFIRMATION_MULT
from strategy.base import StrategyBase
from strategy.regime import Regime
from strategy.signal_breakout import breakout_signal
from strategy.signal_momentum import momentum_signal
from strategy.signals import Signal


def mean_reversion_signal(df: pd.DataFrame) -> Signal:
    """Return BUY/SELL/HOLD for the ranging mean-reversion strategy."""
    if len(df) < 2:
        return Signal.HOLD

    last, prev = df.iloc[-1], df.iloc[-2]

    if (
        last.rsi_14 < 35 and last.close < last.bb_lo
        and last.macd > last.macd_s and prev.macd <= prev.macd_s
        and last.close > last.ema_200
        and last.volume >= VOLUME_CONFIRMATION_MULT * last.volume_ma_20
    ):
        return Signal.BUY

    if (
        last.rsi_14 > 70 and last.close > last.bb_hi
        and last.macd < last.macd_s and prev.macd >= prev.macd_s
        and last.close < last.ema_200
        and last.volume >= VOLUME_CONFIRMATION_MULT * last.volume_ma_20
    ):
        return Signal.SELL

    return Signal.HOLD


class MeanReversionStrategy(StrategyBase):
    name = "mean_reversion_v1"
    display_name = "Mean Reversion"
    description = "Range-bound RSI/Bollinger/MACD strategy with EMA-200 and volume confirmation."
    version = "1.0.0"
    regimes = [Regime.RANGING]

    def default_params(self) -> dict:
        return {
            "rsi_buy_threshold": 35,
            "rsi_sell_threshold": 70,
            "volume_confirmation_mult": VOLUME_CONFIRMATION_MULT,
        }

    def param_schema(self) -> list[dict]:
        return [
            {
                "name": "rsi_buy_threshold",
                "label": "RSI Buy Threshold",
                "type": "int",
                "min": 5,
                "max": 50,
                "step": 1,
                "help": "Oversold threshold used to trigger long mean-reversion entries.",
            },
            {
                "name": "rsi_sell_threshold",
                "label": "RSI Sell Threshold",
                "type": "int",
                "min": 50,
                "max": 95,
                "step": 1,
                "help": "Overbought threshold used to trigger short mean-reversion entries.",
            },
            {
                "name": "volume_confirmation_mult",
                "label": "Volume Confirmation Multiplier",
                "type": "float",
                "min": 0.5,
                "max": 5.0,
                "step": 0.1,
                "help": "Minimum multiple of volume MA required before a signal is valid.",
            },
        ]

    def should_long(self, df: pd.DataFrame) -> bool:
        if len(df) < 2:
            return False
        last, prev = df.iloc[-1], df.iloc[-2]
        return bool(
            last.rsi_14 < float(self.params.get("rsi_buy_threshold", 35))
            and last.close < last.bb_lo
            and last.macd > last.macd_s
            and prev.macd <= prev.macd_s
            and last.close > last.ema_200
            and last.volume >= float(self.params.get("volume_confirmation_mult", VOLUME_CONFIRMATION_MULT)) * last.volume_ma_20
        )

    def should_short(self, df: pd.DataFrame) -> bool:
        if len(df) < 2:
            return False
        last, prev = df.iloc[-1], df.iloc[-2]
        return bool(
            last.rsi_14 > float(self.params.get("rsi_sell_threshold", 70))
            and last.close > last.bb_hi
            and last.macd < last.macd_s
            and prev.macd >= prev.macd_s
            and last.close < last.ema_200
            and last.volume >= float(self.params.get("volume_confirmation_mult", VOLUME_CONFIRMATION_MULT)) * last.volume_ma_20
        )


class MomentumStrategy(StrategyBase):
    name = "momentum_v1"
    display_name = "Momentum"
    description = "Trend-following EMA stack strategy with ADX, pullback, and volume confirmation."
    version = "1.0.0"
    regimes = [Regime.TRENDING]

    def should_long(self, df: pd.DataFrame) -> bool:
        return momentum_signal(df) == Signal.BUY

    def should_short(self, df: pd.DataFrame) -> bool:
        return momentum_signal(df) == Signal.SELL


class BreakoutStrategy(StrategyBase):
    name = "breakout_v1"
    display_name = "Breakout"
    description = "Squeeze breakout strategy using prior range highs/lows and volume confirmation."
    version = "1.0.0"
    regimes = [Regime.SQUEEZE]

    def should_long(self, df: pd.DataFrame) -> bool:
        return breakout_signal(df) == Signal.BUY

    def should_short(self, df: pd.DataFrame) -> bool:
        return breakout_signal(df) == Signal.SELL


class RegimeRouterStrategy(StrategyBase):
    name = "regime_router_v1"
    display_name = "Regime Router"
    description = "Current production router that selects mean reversion, momentum, or breakout by market regime."
    version = "1.0.0"
    regimes: list = []

    def should_long(self, df: pd.DataFrame) -> bool:
        return False

    def should_short(self, df: pd.DataFrame) -> bool:
        return False

    def decide(self, df: pd.DataFrame, regime: Regime | None = None) -> Signal:
        if regime == Regime.TRENDING:
            return momentum_signal(df)
        if regime == Regime.SQUEEZE:
            return breakout_signal(df)
        return mean_reversion_signal(df)


BUILTIN_STRATEGY_CLASSES = [
    RegimeRouterStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    BreakoutStrategy,
]
