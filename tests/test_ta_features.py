"""
tests/test_ta_features.py

Unit tests for strategy/ta_features.add_indicators().
All tests use purely synthetic OHLCV DataFrames — no DB, no I/O.
"""
import numpy as np
import pandas as pd
import pytest

from strategy.ta_features import add_indicators


def _synthetic_ohlcv(n: int = 220, base_price: float = 100.0, seed: int = 42) -> pd.DataFrame:
    """Return a deterministic OHLCV DataFrame with `n` rows."""
    rng = np.random.default_rng(seed)
    close = base_price + np.cumsum(rng.normal(0, 0.5, n))
    # Ensure prices are positive
    close = np.abs(close) + 1.0
    high   = close + rng.uniform(0, 0.5, n)
    low    = close - rng.uniform(0, 0.5, n)
    open_  = close + rng.normal(0, 0.2, n)
    volume = rng.uniform(100, 1000, n)
    idx = pd.date_range("2024-01-01", periods=n, freq="1min")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


# ── column presence ────────────────────────────────────────────────────────────

class TestAddIndicatorsColumns:
    def test_expected_columns_present(self):
        df = add_indicators(_synthetic_ohlcv(220))
        for col in ("ma_21", "ma_55", "macd", "macd_s", "rsi_14", "bb_hi", "bb_lo",
                    "ema_200", "volume_ma_20"):
            assert col in df.columns, f"Missing column: {col}"

    def test_input_columns_preserved(self):
        df = add_indicators(_synthetic_ohlcv(220))
        for col in ("open", "high", "low", "close", "volume"):
            assert col in df.columns

    def test_empty_df_returns_empty(self):
        empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        result = add_indicators(empty)
        assert result.empty


# ── RSI ────────────────────────────────────────────────────────────────────────

class TestRSI:
    def test_rsi_bounded_0_to_100(self):
        df = add_indicators(_synthetic_ohlcv(220))
        assert df["rsi_14"].between(0, 100).all(), "RSI values outside [0, 100]"

    def test_rsi_rising_prices_high(self):
        """Strictly rising prices → RSI should be high (>60)."""
        n = 220
        close = np.linspace(100, 200, n)
        idx = pd.date_range("2024-01-01", periods=n, freq="1min")
        df = pd.DataFrame(
            {"open": close, "high": close + 0.1, "low": close - 0.1,
             "close": close, "volume": np.ones(n) * 500},
            index=idx,
        )
        result = add_indicators(df)
        assert result["rsi_14"].iloc[-1] > 60

    def test_rsi_falling_prices_low(self):
        """Strictly falling prices → RSI should be low (<40)."""
        n = 220
        close = np.linspace(200, 100, n)
        idx = pd.date_range("2024-01-01", periods=n, freq="1min")
        df = pd.DataFrame(
            {"open": close, "high": close + 0.1, "low": close - 0.1,
             "close": close, "volume": np.ones(n) * 500},
            index=idx,
        )
        result = add_indicators(df)
        assert result["rsi_14"].iloc[-1] < 40


# ── Bollinger Bands ────────────────────────────────────────────────────────────

class TestBollingerBands:
    def test_bb_hi_above_lo(self):
        df = add_indicators(_synthetic_ohlcv(220))
        assert (df["bb_hi"] >= df["bb_lo"]).all()

    def test_bb_hi_above_close_most_of_the_time(self):
        """Upper band should be above close for the majority of candles."""
        df = add_indicators(_synthetic_ohlcv(220))
        pct_above = (df["bb_hi"] >= df["close"]).mean()
        assert pct_above > 0.8, f"bb_hi above close only {pct_above:.0%} of the time"

    def test_bb_lo_below_close_most_of_the_time(self):
        df = add_indicators(_synthetic_ohlcv(220))
        pct_below = (df["bb_lo"] <= df["close"]).mean()
        assert pct_below > 0.8


# ── MACD ───────────────────────────────────────────────────────────────────────

class TestMACD:
    def test_macd_and_signal_not_all_nan(self):
        df = add_indicators(_synthetic_ohlcv(220))
        assert df["macd"].notna().any()
        assert df["macd_s"].notna().any()

    def test_macd_columns_are_float(self):
        df = add_indicators(_synthetic_ohlcv(220))
        assert df["macd"].dtype == float
        assert df["macd_s"].dtype == float


# ── Moving Averages ────────────────────────────────────────────────────────────

class TestMovingAverages:
    def test_ma_21_positive(self):
        df = add_indicators(_synthetic_ohlcv(220))
        assert (df["ma_21"] > 0).all()

    def test_ma_55_positive(self):
        df = add_indicators(_synthetic_ohlcv(220))
        assert (df["ma_55"] > 0).all()

    def test_ma_21_close_to_close(self):
        """SMA-21 on flat prices should equal that price."""
        n = 220
        close = np.ones(n) * 50.0
        idx = pd.date_range("2024-01-01", periods=n, freq="1min")
        df = pd.DataFrame(
            {"open": close, "high": close, "low": close, "close": close,
             "volume": np.ones(n)},
            index=idx,
        )
        result = add_indicators(df)
        assert np.allclose(result["ma_21"], 50.0, atol=1e-6)
        assert np.allclose(result["ma_55"], 50.0, atol=1e-6)


# ── EMA-200 ────────────────────────────────────────────────────────────────────

class TestEMA200:
    def test_ema_200_present(self):
        df = add_indicators(_synthetic_ohlcv(220))
        assert "ema_200" in df.columns

    def test_ema_200_positive(self):
        df = add_indicators(_synthetic_ohlcv(220))
        assert (df["ema_200"] > 0).all()

    def test_ema_200_lags_rising_price(self):
        """In a rising market EMA-200 should be below the current close (it lags)."""
        n = 220
        close = np.linspace(100, 200, n)
        idx = pd.date_range("2024-01-01", periods=n, freq="1min")
        df = pd.DataFrame(
            {"open": close, "high": close + 0.1, "low": close - 0.1,
             "close": close, "volume": np.ones(n) * 500},
            index=idx,
        )
        result = add_indicators(df)
        assert result["ema_200"].iloc[-1] < result["close"].iloc[-1]

    def test_ema_200_leads_falling_price(self):
        """In a falling market EMA-200 should be above the current close (it lags)."""
        n = 220
        close = np.linspace(200, 100, n)
        idx = pd.date_range("2024-01-01", periods=n, freq="1min")
        df = pd.DataFrame(
            {"open": close, "high": close + 0.1, "low": close - 0.1,
             "close": close, "volume": np.ones(n) * 500},
            index=idx,
        )
        result = add_indicators(df)
        assert result["ema_200"].iloc[-1] > result["close"].iloc[-1]

    def test_ema_200_requires_220_rows_for_output(self):
        """220 rows is enough for EMA-200 warmup; output should be non-empty."""
        result = add_indicators(_synthetic_ohlcv(220))
        assert len(result) > 0
        assert result["ema_200"].notna().all()


# ── Volume MA-20 ───────────────────────────────────────────────────────────────

class TestVolumeMA20:
    def test_volume_ma_20_present(self):
        df = add_indicators(_synthetic_ohlcv(220))
        assert "volume_ma_20" in df.columns

    def test_volume_ma_20_positive(self):
        df = add_indicators(_synthetic_ohlcv(220))
        assert (df["volume_ma_20"] > 0).all()

    def test_volume_ma_20_flat_volume(self):
        """SMA-20 of constant volume should equal that volume."""
        n = 220
        close = np.ones(n) * 100.0
        vol = np.ones(n) * 300.0
        idx = pd.date_range("2024-01-01", periods=n, freq="1min")
        df = pd.DataFrame(
            {"open": close, "high": close, "low": close, "close": close, "volume": vol},
            index=idx,
        )
        result = add_indicators(df)
        assert np.allclose(result["volume_ma_20"], 300.0, atol=1e-6)


# ── dropna contract ────────────────────────────────────────────────────────────

class TestDropna:
    def test_no_nan_in_output(self):
        """add_indicators must drop NaN rows; output should have no NaN."""
        df = add_indicators(_synthetic_ohlcv(220))
        assert not df.isnull().any().any(), "NaN values found after add_indicators"

    def test_output_shorter_than_input(self):
        """dropna removes warm-up rows so output is shorter than input."""
        raw = _synthetic_ohlcv(220)
        result = add_indicators(raw)
        assert len(result) < len(raw)
