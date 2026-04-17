"""Template for manual agent-authored strategy plugins.

Files beginning with `_` are ignored by the plugin loader, so this template is
safe to keep in the strategies directory.
"""

import pandas as pd

from strategy.base import StrategyBase
from strategy.regime import Regime


class TemplateStrategy(StrategyBase):
    name = "template_strategy_v1"
    display_name = "Template Strategy"
    description = "Replace this with the strategy edge, trigger logic, and intended market behavior."
    version = "1.0.0"
    regimes = [Regime.RANGING]

    def should_long(self, df: pd.DataFrame) -> bool:
        last = df.iloc[-1]
        return bool(last["rsi_14"] < 30)

    def should_short(self, df: pd.DataFrame) -> bool:
        last = df.iloc[-1]
        return bool(last["rsi_14"] > 70)
