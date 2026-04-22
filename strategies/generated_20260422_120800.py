# GENERATED STRATEGY DRAFT
# Review workflow:
# 1. Verify metadata (`name`, `display_name`, `description`, `version`, `regimes`)
# 2. Backtest the draft in the Strategy Workbench
# 3. If accepted, save a reviewed copy under a non-generated plugin filename before paper/live use

import pandas as pd

from strategy.base import StrategyBase
from strategy.regime import Regime


class GeneratedRangeProbeStrategy(StrategyBase):
    name = "generated_range_probe_v1"
    display_name = "Generated Range Probe Draft"
    description = (
        "Draft generated-style plugin that probes ranging reversals with RSI, "
        "Bollinger Bands, and MACD histogram confirmation."
    )
    version = "1.0.0"
    regimes = [Regime.RANGING]

    def should_long(self, df: pd.DataFrame) -> bool:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        return bool(
            last["rsi_14"] < 28
            and last["close"] <= last["bb_lower"]
            and last["macd_hist"] > prev["macd_hist"]
        )

    def should_short(self, df: pd.DataFrame) -> bool:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        return bool(
            last["rsi_14"] > 68
            and last["close"] >= last["bb_upper"]
            and last["macd_hist"] < prev["macd_hist"]
        )
