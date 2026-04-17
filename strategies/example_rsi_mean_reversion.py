"""strategies/example_rsi_mean_reversion.py — Reference plugin strategy.

Translates the existing inline mean-reversion logic from strategy/signal_engine.py
into the StrategyBase ABC format. This proves the ABC is expressive enough to
represent all existing strategies without duplicating behavior.

Active only in RANGING regime (ADX ≤ 20). The heuristic signal_engine.py
continues to handle this regime by default; this plugin can be selected instead
via: python run_agents.py --strategy rsi_mean_reversion_v1
"""

import pandas as pd

from config import VOLUME_CONFIRMATION_MULT
from strategy.base import StrategyBase
from strategy.regime import Regime


class RSIMeanReversionStrategy(StrategyBase):
    """RSI + Bollinger Band mean-reversion in ranging markets.

    BUY conditions  (oversold bounce):
        - RSI-14 < 35 (oversold)
        - Close below Bollinger lower band
        - MACD crossed above signal (bullish momentum confirmation)
        - Close above EMA-200 (only long above trend)
        - Volume ≥ 1.5× 20-period volume MA

    SELL conditions (overbought reversal):
        - RSI-14 > 70 (overbought)
        - Close above Bollinger upper band
        - MACD crossed below signal (bearish momentum confirmation)
        - Close below EMA-200 (only short below trend)
        - Volume ≥ 1.5× 20-period volume MA
    """

    name = "rsi_mean_reversion_v1"
    display_name = "RSI Mean Reversion Example"
    description = "Reference plugin showing how to implement a range-bound RSI/Bollinger/MACD strategy as a reviewed StrategyBase subclass."
    version = "1.0.0"
    regimes = [Regime.RANGING]

    def should_long(self, df: pd.DataFrame) -> bool:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        return bool(
            last["rsi_14"] < 35
            and last["close"] < last["bb_lo"]
            and last["macd"] > last["macd_s"]
            and prev["macd"] <= prev["macd_s"]   # fresh cross-above
            and last["close"] > last["ema_200"]
            and last["volume"] >= VOLUME_CONFIRMATION_MULT * last["volume_ma_20"]
        )

    def should_short(self, df: pd.DataFrame) -> bool:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        return bool(
            last["rsi_14"] > 70
            and last["close"] > last["bb_hi"]
            and last["macd"] < last["macd_s"]
            and prev["macd"] >= prev["macd_s"]   # fresh cross-below
            and last["close"] < last["ema_200"]
            and last["volume"] >= VOLUME_CONFIRMATION_MULT * last["volume_ma_20"]
        )
