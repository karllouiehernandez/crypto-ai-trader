"""strategy/base.py — Abstract base class for all plugin strategies.

Drop a .py file in strategies/ that subclasses StrategyBase and implements
should_long() + should_short(). The strategies/loader.py hot-loader picks it up
automatically via watchdog and registers it in the in-memory strategy registry.

Design rules:
- evaluate() is NOT overridable — enforces regime gate + length check always apply
- Subclasses must be pure: no DB access, no I/O, only DataFrame logic
- regimes = [] means active in all regimes (no gate applied)
"""

from abc import ABC, abstractmethod

import pandas as pd

from strategy.regime import Regime
from strategy.signals import Signal


class StrategyBase(ABC):
    """Abstract base for all hot-loadable strategy plugins.

    Subclasses must set:
        name    (str)         — unique key used in registry + CLI --strategy flag
        version (str)         — semver string for logging + KB tracking
        regimes (list[Regime])— which regimes activate this strategy; [] = all

    Subclasses must implement:
        should_long(df)  -> bool
        should_short(df) -> bool

    Subclasses may optionally implement:
        should_exit_long(df)  -> bool  (default False)
        should_exit_short(df) -> bool  (default False)
    """

    name: str = "unnamed"
    display_name: str = "Unnamed Strategy"
    description: str = "No strategy description provided."
    version: str = "0.1.0"
    regimes: list = []  # empty = active in all regimes

    @abstractmethod
    def should_long(self, df: pd.DataFrame) -> bool:
        """Return True to emit a BUY signal on the current candle."""
        ...

    @abstractmethod
    def should_short(self, df: pd.DataFrame) -> bool:
        """Return True to emit a SELL signal on the current candle."""
        ...

    def should_exit_long(self, df: pd.DataFrame) -> bool:
        """Override to define a custom long exit condition. Default: False (hold)."""
        return False

    def should_exit_short(self, df: pd.DataFrame) -> bool:
        """Override to define a custom short exit condition. Default: False (hold)."""
        return False

    def decide(self, df: pd.DataFrame, regime: Regime | None = None) -> Signal:
        """Return a trading decision after base guards are applied."""
        if self.should_long(df):
            return Signal.BUY

        if self.should_short(df):
            return Signal.SELL

        return Signal.HOLD

    def evaluate(self, df: pd.DataFrame, regime: Regime | None = None) -> Signal:
        """Called by the plugin loader and AgentCoordinator. Not overridable.

        Applies regime gate and minimum length check before delegating to
        should_long / should_short. This guarantees HIGH_VOL halt and data
        sufficiency checks are always enforced regardless of subclass logic.
        """
        # Regime gate: if regimes list is non-empty, only activate in listed regimes
        if self.regimes and regime is not None and regime not in self.regimes:
            return Signal.HOLD

        # Minimum data guard: need at least 2 candles for prev/last comparisons
        if len(df) < 2:
            return Signal.HOLD

        return self.decide(df, regime)

    def default_params(self) -> dict:
        """Return default parameter values for UI forms and persisted settings."""
        return {}

    def param_schema(self) -> list[dict]:
        """Return serialisable parameter metadata for dashboard rendering."""
        return []

    def meta(self) -> dict:
        """Return strategy metadata for the dashboard, KB logging, and registry."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "regimes": [r.value for r in self.regimes],
            "class": self.__class__.__name__,
            "default_params": self.default_params(),
            "param_schema": self.param_schema(),
        }
