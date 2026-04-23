"""tests/test_strategy_base.py — Unit tests for strategy/base.py StrategyBase ABC."""

import pandas as pd

from strategy.base import StrategyBase
from strategy.regime import Regime
from strategy.signals import Signal


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_df(n: int = 5) -> pd.DataFrame:
    """Minimal DataFrame with two rows — enough for prev/last comparisons."""
    return pd.DataFrame({
        "open":  [100.0] * n,
        "high":  [101.0] * n,
        "low":   [99.0]  * n,
        "close": [100.0] * n,
        "volume":[1000.0]* n,
    })


class _AlwaysBuy(StrategyBase):
    name = "always_buy"
    version = "1.0.0"
    regimes = []

    def should_long(self, df):
        return True

    def should_short(self, df):
        return False


class _AlwaysSell(StrategyBase):
    name = "always_sell"
    version = "1.0.0"
    regimes = []

    def should_long(self, df):
        return False

    def should_short(self, df):
        return True


class _RangingOnly(StrategyBase):
    name = "ranging_only"
    version = "1.0.0"
    regimes = [Regime.RANGING]

    def should_long(self, df):
        return True

    def should_short(self, df):
        return False


class _NeverSignals(StrategyBase):
    name = "never"
    version = "1.0.0"
    regimes = []

    def should_long(self, df):
        return False

    def should_short(self, df):
        return False


# ── Flexible signal contract ───────────────────────────────────────────────

def test_default_should_long_returns_false():
    class _Missing(StrategyBase):
        name = "missing"
        version = "0.1.0"
        regimes = []
        def should_short(self, df): return False

    assert _Missing().should_long(_make_df()) is False


def test_default_should_short_returns_false():
    class _Missing(StrategyBase):
        name = "missing2"
        version = "0.1.0"
        regimes = []
        def should_long(self, df): return True

    assert _Missing().should_short(_make_df()) is False


def test_decide_only_strategy_can_signal():
    class _DecideOnly(StrategyBase):
        name = "decide_only"
        version = "0.1.0"
        regimes = []

        def decide(self, df, regime=None):
            return Signal.BUY

    assert _DecideOnly().evaluate(_make_df()) == Signal.BUY


def test_can_instantiate_with_both_methods():
    s = _AlwaysBuy()
    assert s.name == "always_buy"


# ── evaluate() signal routing ──────────────────────────────────────────────

def test_evaluate_returns_buy():
    s = _AlwaysBuy()
    df = _make_df()
    assert s.evaluate(df) == Signal.BUY


def test_evaluate_returns_sell():
    s = _AlwaysSell()
    df = _make_df()
    assert s.evaluate(df) == Signal.SELL


def test_evaluate_returns_hold_when_neither():
    s = _NeverSignals()
    df = _make_df()
    assert s.evaluate(df) == Signal.HOLD


# ── Regime gate ────────────────────────────────────────────────────────────

def test_evaluate_blocks_when_regime_not_in_list():
    s = _RangingOnly()   # regimes = [RANGING]
    df = _make_df()
    assert s.evaluate(df, regime=Regime.TRENDING) == Signal.HOLD


def test_evaluate_passes_when_regime_matches():
    s = _RangingOnly()
    df = _make_df()
    assert s.evaluate(df, regime=Regime.RANGING) == Signal.BUY


def test_evaluate_passes_when_regime_is_none():
    s = _RangingOnly()
    df = _make_df()
    # None regime = skip gate
    assert s.evaluate(df, regime=None) == Signal.BUY


def test_evaluate_passes_when_regimes_list_empty():
    s = _AlwaysBuy()   # regimes = []
    df = _make_df()
    # empty regimes = active in all
    assert s.evaluate(df, regime=Regime.HIGH_VOL) == Signal.BUY


# ── Minimum length guard ───────────────────────────────────────────────────

def test_evaluate_returns_hold_for_single_row_df():
    s = _AlwaysBuy()
    df = _make_df(n=1)
    assert s.evaluate(df) == Signal.HOLD


def test_evaluate_returns_hold_for_empty_df():
    s = _AlwaysBuy()
    df = pd.DataFrame()
    assert s.evaluate(df) == Signal.HOLD


def test_evaluate_returns_buy_for_two_row_df():
    s = _AlwaysBuy()
    df = _make_df(n=2)
    assert s.evaluate(df) == Signal.BUY


# ── Buy takes priority over sell ───────────────────────────────────────────

def test_buy_takes_priority_over_sell():
    class _BothTrue(StrategyBase):
        name = "both"; version = "0"; regimes = []
        def should_long(self, df): return True
        def should_short(self, df): return True

    s = _BothTrue()
    df = _make_df()
    assert s.evaluate(df) == Signal.BUY


# ── meta() ─────────────────────────────────────────────────────────────────

def test_meta_returns_expected_keys():
    s = _AlwaysBuy()
    m = s.meta()
    assert m["name"] == "always_buy"
    assert m["version"] == "1.0.0"
    assert m["regimes"] == []
    assert m["class"] == "_AlwaysBuy"


def test_meta_regimes_serialised_as_strings():
    s = _RangingOnly()
    m = s.meta()
    assert m["regimes"] == ["RANGING"]


# ── Default exit methods ───────────────────────────────────────────────────

def test_default_exit_long_returns_false():
    s = _AlwaysBuy()
    df = _make_df()
    assert s.should_exit_long(df) is False


def test_default_exit_short_returns_false():
    s = _AlwaysSell()
    df = _make_df()
    assert s.should_exit_short(df) is False
