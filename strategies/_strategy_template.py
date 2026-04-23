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

    def default_params(self) -> dict:
        return {
            "rsi_buy_threshold": 30.0,
            "rsi_sell_threshold": 70.0,
        }

    def param_schema(self) -> list[dict]:
        return [
            {
                "name": "rsi_buy_threshold",
                "label": "RSI Buy Threshold",
                "type": "number",
                "default": 30.0,
                "min": 5.0,
                "max": 50.0,
            },
            {
                "name": "rsi_sell_threshold",
                "label": "RSI Sell Threshold",
                "type": "number",
                "default": 70.0,
                "min": 50.0,
                "max": 95.0,
            },
        ]

    def should_long(self, df: pd.DataFrame) -> bool:
        last = df.iloc[-1]
        return bool(last["rsi_14"] < self.params["rsi_buy_threshold"])

    def should_short(self, df: pd.DataFrame) -> bool:
        last = df.iloc[-1]
        return bool(last["rsi_14"] > self.params["rsi_sell_threshold"])
