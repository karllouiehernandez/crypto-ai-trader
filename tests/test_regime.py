"""
tests/test_regime.py

Unit tests for strategy/regime.detect_regime().
All tests use synthetic DataFrames with controlled indicator columns.
No DB, no I/O.
"""
import numpy as np
import pandas as pd
import pytest

from strategy.regime import Regime, detect_regime


def _regime_df(n: int = 30, adx: float = 15.0, bb_width: float = 0.05,
               close_series: np.ndarray = None) -> pd.DataFrame:
    """
    Build a minimal DataFrame with the columns detect_regime() reads:
    adx_14, bb_width, close. All rows get the given adx/bb_width;
    close defaults to flat unless close_series is supplied.
    """
    idx = pd.date_range("2024-01-01", periods=n, freq="1min")
    if close_series is None:
        close_series = np.ones(n) * 100.0
    return pd.DataFrame({
        "close":    close_series,
        "adx_14":   np.full(n, adx),
        "bb_width": np.full(n, bb_width),
    }, index=idx)


def _high_vol_df(seed: int = 0) -> pd.DataFrame:
    """
    DataFrame where recent HIGH_VOL_SHORT_WINDOW candles have clearly higher vol than baseline.
    Uses n = HIGH_VOL_SHORT_WINDOW * 5 rows so stable:volatile ratio is 4:1,
    guaranteeing recent_vol / baseline_vol > HIGH_VOL_MULTIPLIER (2.0).
    """
    from config import HIGH_VOL_SHORT_WINDOW
    n = HIGH_VOL_SHORT_WINDOW * 5
    rng = np.random.default_rng(seed)
    # Flat stable baseline → zero pct_change for most rows
    stable = np.ones(n - HIGH_VOL_SHORT_WINDOW) * 100.0
    # Large absolute jumps at end → pct_change ~10% per step
    volatile = stable[-1] + np.cumsum(rng.normal(0, 10.0, HIGH_VOL_SHORT_WINDOW))
    close = np.concatenate([stable, volatile])
    return _regime_df(n=n, adx=15.0, bb_width=0.05, close_series=close)


def _squeeze_df(n: int = 30) -> pd.DataFrame:
    """DataFrame where the last bb_width is the minimum in history (well below 20th pct)."""
    # Descending bb_width: last value is absolute minimum
    bb_widths = np.linspace(0.10, 0.001, n)
    idx = pd.date_range("2024-01-01", periods=n, freq="1min")
    return pd.DataFrame({
        "close":    np.ones(n) * 100.0,
        "adx_14":   np.full(n, 15.0),   # ranging ADX — squeeze takes priority
        "bb_width": bb_widths,
    }, index=idx)


# ── basic regime branches ──────────────────────────────────────────────────────

class TestBasicRegimes:
    def test_low_adx_returns_ranging(self):
        df = _regime_df(adx=15.0)
        assert detect_regime(df) == Regime.RANGING

    def test_high_adx_returns_trending(self):
        df = _regime_df(adx=30.0)
        assert detect_regime(df) == Regime.TRENDING

    def test_adx_exactly_at_trend_threshold_returns_trending(self):
        """ADX == ADX_TREND_THRESHOLD (25) is strictly greater-than, so RANGING."""
        from config import ADX_TREND_THRESHOLD
        df = _regime_df(adx=float(ADX_TREND_THRESHOLD))
        # 25 is NOT > 25, so falls through to RANGING
        assert detect_regime(df) == Regime.RANGING

    def test_adx_just_above_threshold_returns_trending(self):
        from config import ADX_TREND_THRESHOLD
        df = _regime_df(adx=float(ADX_TREND_THRESHOLD) + 0.1)
        assert detect_regime(df) == Regime.TRENDING

    def test_grey_zone_adx_returns_ranging(self):
        """ADX between 20 and 25 (grey zone) should return RANGING (conservative)."""
        df = _regime_df(adx=22.0)
        assert detect_regime(df) == Regime.RANGING

    def test_squeeze_returns_squeeze(self):
        df = _squeeze_df()
        assert detect_regime(df) == Regime.SQUEEZE

    def test_high_vol_returns_high_vol(self):
        df = _high_vol_df()
        assert detect_regime(df) == Regime.HIGH_VOL

    def test_high_vol_with_noisy_baseline(self):
        """Baseline has non-zero variance; spike still detected (regression for contamination bug)."""
        from config import HIGH_VOL_SHORT_WINDOW
        n = HIGH_VOL_SHORT_WINDOW * 5
        rng = np.random.default_rng(42)
        # Baseline: moderate noise (std ~0.3% returns)
        baseline_prices = 100.0 + np.cumsum(rng.normal(0, 0.3, n - HIGH_VOL_SHORT_WINDOW))
        # Spike: 10× larger moves (std ~3% returns)
        volatile = baseline_prices[-1] + np.cumsum(rng.normal(0, 3.0, HIGH_VOL_SHORT_WINDOW))
        close = np.concatenate([baseline_prices, volatile])
        idx = pd.date_range("2024-01-01", periods=n, freq="1min")
        df = pd.DataFrame({
            "close":    close,
            "adx_14":   np.full(n, 15.0),
            "bb_width": np.full(n, 0.05),
        }, index=idx)
        assert detect_regime(df) == Regime.HIGH_VOL


# ── priority ordering ─────────────────────────────────────────────────────────

class TestRegimePriority:
    def test_high_vol_overrides_squeeze(self):
        """HIGH_VOL takes priority over SQUEEZE."""
        from config import HIGH_VOL_SHORT_WINDOW
        n = HIGH_VOL_SHORT_WINDOW * 5
        rng = np.random.default_rng(1)
        stable   = np.ones(n - HIGH_VOL_SHORT_WINDOW) * 100.0
        volatile = stable[-1] + np.cumsum(rng.normal(0, 10.0, HIGH_VOL_SHORT_WINDOW))
        close = np.concatenate([stable, volatile])
        bb_widths = np.linspace(0.10, 0.001, n)   # squeeze condition also true
        idx = pd.date_range("2024-01-01", periods=n, freq="1min")
        df = pd.DataFrame({
            "close": close, "adx_14": np.full(n, 15.0), "bb_width": bb_widths,
        }, index=idx)
        assert detect_regime(df) == Regime.HIGH_VOL

    def test_high_vol_overrides_trending(self):
        """HIGH_VOL takes priority over TRENDING."""
        from config import HIGH_VOL_SHORT_WINDOW
        n = HIGH_VOL_SHORT_WINDOW * 5
        rng = np.random.default_rng(2)
        stable   = np.ones(n - HIGH_VOL_SHORT_WINDOW) * 100.0
        volatile = stable[-1] + np.cumsum(rng.normal(0, 10.0, HIGH_VOL_SHORT_WINDOW))
        close = np.concatenate([stable, volatile])
        idx = pd.date_range("2024-01-01", periods=n, freq="1min")
        df = pd.DataFrame({
            "close": close, "adx_14": np.full(n, 30.0), "bb_width": np.full(n, 0.05),
        }, index=idx)
        assert detect_regime(df) == Regime.HIGH_VOL

    def test_squeeze_overrides_trending(self):
        """SQUEEZE takes priority over TRENDING when no HIGH_VOL."""
        df = pd.DataFrame({
            "close":    np.ones(30) * 100.0,
            "adx_14":   np.full(30, 30.0),           # would be TRENDING
            "bb_width": np.linspace(0.10, 0.001, 30), # squeeze
        }, index=pd.date_range("2024-01-01", periods=30, freq="1min"))
        assert detect_regime(df) == Regime.SQUEEZE

    def test_squeeze_overrides_ranging(self):
        """SQUEEZE takes priority over RANGING when no HIGH_VOL."""
        df = _squeeze_df()  # adx=15 (ranging), but squeeze condition met
        assert detect_regime(df) == Regime.SQUEEZE


# ── edge cases ────────────────────────────────────────────────────────────────

class TestRegimeEdgeCases:
    def test_single_row_returns_ranging(self):
        df = _regime_df(n=1)
        assert detect_regime(df) == Regime.RANGING

    def test_empty_df_returns_ranging(self):
        df = pd.DataFrame(columns=["close", "adx_14", "bb_width"])
        assert detect_regime(df) == Regime.RANGING

    def test_flat_prices_no_high_vol(self):
        """Perfectly flat prices → zero vol → HIGH_VOL cannot fire."""
        df = _regime_df(n=30, adx=15.0, close_series=np.ones(30) * 100.0)
        assert detect_regime(df) != Regime.HIGH_VOL

    def test_missing_bb_width_no_squeeze(self):
        """If bb_width column absent, squeeze check must not raise and returns False."""
        df = pd.DataFrame({
            "close":  np.ones(30) * 100.0,
            "adx_14": np.full(30, 15.0),
        }, index=pd.date_range("2024-01-01", periods=30, freq="1min"))
        result = detect_regime(df)
        assert result in (Regime.RANGING, Regime.TRENDING, Regime.HIGH_VOL)

    def test_return_is_regime_enum(self):
        df = _regime_df()
        result = detect_regime(df)
        assert isinstance(result, Regime)
        assert result in (Regime.RANGING, Regime.TRENDING, Regime.SQUEEZE, Regime.HIGH_VOL)
