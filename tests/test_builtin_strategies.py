"""Tests for built-in selectable strategy classes."""

import pandas as pd

from strategy.builtin import (
    BreakoutStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    RegimeRouterStrategy,
)
from strategy.regime import Regime
from strategy.signals import Signal


def _base_df() -> pd.DataFrame:
    rows = [
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 500.0,
            "rsi_14": 50.0,
            "bb_lo": 95.0,
            "bb_hi": 105.0,
            "macd": 0.0,
            "macd_s": 0.0,
            "ema_9": 100.0,
            "ema_21": 100.0,
            "ema_55": 100.0,
            "ema_200": 100.0,
            "volume_ma_20": 500.0,
            "adx_14": 15.0,
        },
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 500.0,
            "rsi_14": 50.0,
            "bb_lo": 95.0,
            "bb_hi": 105.0,
            "macd": 0.0,
            "macd_s": 0.0,
            "ema_9": 100.0,
            "ema_21": 100.0,
            "ema_55": 100.0,
            "ema_200": 100.0,
            "volume_ma_20": 500.0,
            "adx_14": 15.0,
        },
    ]
    return pd.DataFrame(rows)


def test_builtin_strategy_meta_has_display_name_and_description():
    meta = MeanReversionStrategy().meta()
    assert meta["display_name"] == "Mean Reversion"
    assert "description" in meta


def test_regime_router_routes_trending_to_momentum_logic():
    df = _base_df()
    df.iloc[-1, df.columns.get_loc("ema_9")] = 105.0
    df.iloc[-1, df.columns.get_loc("ema_21")] = 100.0
    df.iloc[-1, df.columns.get_loc("ema_55")] = 95.0
    df.iloc[-1, df.columns.get_loc("close")] = 100.3
    df.iloc[-1, df.columns.get_loc("volume")] = 800.0
    df.iloc[-1, df.columns.get_loc("adx_14")] = 31.0
    assert RegimeRouterStrategy().evaluate(df, regime=Regime.TRENDING) == Signal.BUY


def test_momentum_strategy_holds_when_regime_gate_blocks():
    df = _base_df()
    assert MomentumStrategy().evaluate(df, regime=Regime.RANGING) == Signal.HOLD


def test_breakout_strategy_holds_with_insufficient_rows():
    df = _base_df()
    assert BreakoutStrategy().evaluate(df, regime=Regime.SQUEEZE) == Signal.HOLD
