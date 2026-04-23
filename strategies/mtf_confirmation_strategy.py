"""strategies/mtf_confirmation_strategy.py — EXP-002

Multi-timeframe confirmation strategy.

Hypothesis: requiring oversold/overbought agreement on 1m, 5m, and 15m
timeframes before entering will filter low-quality 1m noise signals and
improve mean-reversion win rate in ranging markets.

Active only in RANGING regime.
"""

from __future__ import annotations

import pandas as pd

from strategy.base import StrategyBase
from strategy.regime import Regime
from strategy.ta_features import add_indicators

_OHLCV_AGG = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
}


class MTFConfirmationStrategy(StrategyBase):
    """Mean-reversion with multi-timeframe oversold/overbought confirmation.

    Entry requires RSI + Bollinger Band agreement across three timeframes:

        BUY  (oversold bounce):
            1m  — RSI-14 < 35  AND close < BB-lower AND close > EMA-200
            5m  — RSI-14 < 40  AND close < BB-lower
            15m — RSI-14 < 45  AND close < BB-lower

        SELL (overbought reversal):
            1m  — RSI-14 > 65  AND close > BB-upper AND close < EMA-200
            5m  — RSI-14 > 60  AND close > BB-upper
            15m — RSI-14 > 55  AND close > BB-upper

    Requires at least 300 rows of 1m data (≈5 h) for reliable 15m warmup.
    """

    name = "mtf_confirmation"
    display_name = "Multi-Timeframe Confirmation (EXP-002)"
    description = (
        "Mean-reversion requiring RSI + Bollinger Band oversold/overbought "
        "agreement across 1m, 5m, and 15m timeframes before entry. "
        "EXP-002: tests whether MTF confluence filters false 1m signals."
    )
    version = "1.0.0"
    regimes = [Regime.RANGING]

    _MIN_ROWS = 300  # ~5 h of 1m bars; enough for 15m RSI to warm up

    def default_params(self) -> dict:
        return {}

    def param_schema(self) -> list[dict]:
        return []

    # ── resampling helper ──────────────────────────────────────────────────────

    def _resample_indicators(self, df: pd.DataFrame, rule: str) -> pd.DataFrame:
        """Resample df (DatetimeIndex) to `rule` and recompute indicators."""
        if not isinstance(df.index, pd.DatetimeIndex):
            return pd.DataFrame()
        ohlcv = df[["open", "high", "low", "close", "volume"]].resample(rule).agg(_OHLCV_AGG).dropna()
        if ohlcv.empty:
            return pd.DataFrame()
        return add_indicators(ohlcv.reset_index(drop=True))

    # ── timeframe signal checks ────────────────────────────────────────────────

    def _is_oversold(self, frame: pd.DataFrame, rsi_max: float) -> bool:
        if len(frame) < 2:
            return False
        last = frame.iloc[-1]
        return bool(last["rsi_14"] < rsi_max and last["close"] < last["bb_lo"])

    def _is_overbought(self, frame: pd.DataFrame, rsi_min: float) -> bool:
        if len(frame) < 2:
            return False
        last = frame.iloc[-1]
        return bool(last["rsi_14"] > rsi_min and last["close"] > last["bb_hi"])

    # ── abstract method implementations ───────────────────────────────────────

    def should_long(self, df: pd.DataFrame) -> bool:
        if len(df) < self._MIN_ROWS:
            return False

        last = df.iloc[-1]
        # 1m: strict oversold + above EMA-200 (only long in uptrend)
        if not (
            last["rsi_14"] < 35
            and last["close"] < last["bb_lo"]
            and last["close"] > last["ema_200"]
        ):
            return False

        # 5m confirmation
        if not self._is_oversold(self._resample_indicators(df, "5min"), rsi_max=40.0):
            return False

        # 15m confirmation
        if not self._is_oversold(self._resample_indicators(df, "15min"), rsi_max=45.0):
            return False

        return True

    def should_short(self, df: pd.DataFrame) -> bool:
        if len(df) < self._MIN_ROWS:
            return False

        last = df.iloc[-1]
        # 1m: strict overbought + below EMA-200 (only short in downtrend)
        if not (
            last["rsi_14"] > 65
            and last["close"] > last["bb_hi"]
            and last["close"] < last["ema_200"]
        ):
            return False

        # 5m confirmation
        if not self._is_overbought(self._resample_indicators(df, "5min"), rsi_min=60.0):
            return False

        # 15m confirmation
        if not self._is_overbought(self._resample_indicators(df, "15min"), rsi_min=55.0):
            return False

        return True
