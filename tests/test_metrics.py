"""Tests for backtester/metrics.py"""
import math
import pandas as pd
import pytest

from backtester.metrics import (
    sharpe_ratio,
    max_drawdown,
    profit_factor,
    acceptance_gate,
    compute_metrics,
    ANNUALISE_FACTOR,
)
from config import SHARPE_GATE, MAX_DD_GATE, PROFIT_FACTOR_GATE, MIN_TRADES_GATE


# ---------------------------------------------------------------------------
# sharpe_ratio
# ---------------------------------------------------------------------------

class TestSharpeRatio:
    def test_flat_curve_returns_zero(self):
        equity = pd.Series([10_000.0] * 100)
        assert sharpe_ratio(equity) == 0.0

    def test_empty_series_returns_zero(self):
        assert sharpe_ratio(pd.Series([], dtype=float)) == 0.0

    def test_single_element_returns_zero(self):
        assert sharpe_ratio(pd.Series([10_000.0])) == 0.0

    def test_positive_trend(self):
        # Steady upward drift → positive Sharpe
        equity = pd.Series([10_000 + i * 10 for i in range(200)])
        assert sharpe_ratio(equity) > 0

    def test_negative_trend(self):
        # Steady downward drift → negative Sharpe
        equity = pd.Series([10_000 - i * 10 for i in range(200)])
        assert sharpe_ratio(equity) < 0

    def test_annualisation(self):
        # Build equity from variable returns and verify the Sharpe formula numerically
        rng = pd.Series([0.001 if i % 2 == 0 else -0.0005 for i in range(300)])
        equity = (1 + rng).cumprod() * 10_000
        raw_returns = equity.pct_change().dropna()
        expected = (raw_returns.mean() / raw_returns.std()) * ANNUALISE_FACTOR
        assert abs(sharpe_ratio(equity) - expected) < 1e-6


# ---------------------------------------------------------------------------
# max_drawdown
# ---------------------------------------------------------------------------

class TestMaxDrawdown:
    def test_known_sequence(self):
        # Peak=110, trough=90 → DD = (110-90)/110 ≈ 18.18%
        equity = pd.Series([100.0, 110.0, 90.0, 95.0])
        dd = max_drawdown(equity)
        assert abs(dd - (110 - 90) / 110) < 1e-9

    def test_monotone_up_returns_zero(self):
        equity = pd.Series([100.0, 110.0, 120.0, 130.0])
        assert max_drawdown(equity) == 0.0

    def test_flat_returns_zero(self):
        equity = pd.Series([100.0] * 50)
        assert max_drawdown(equity) == 0.0

    def test_empty_returns_zero(self):
        assert max_drawdown(pd.Series([], dtype=float)) == 0.0

    def test_total_loss(self):
        equity = pd.Series([100.0, 50.0, 0.001])
        assert max_drawdown(equity) > 0.99


# ---------------------------------------------------------------------------
# profit_factor
# ---------------------------------------------------------------------------

class TestProfitFactor:
    def _make_trades(self, pairs: list[tuple]) -> pd.DataFrame:
        """pairs: list of (buy_price, sell_price, qty)"""
        rows = []
        for buy_px, sell_px, qty in pairs:
            rows.append({"side": "BUY",  "price": buy_px,  "qty": qty})
            rows.append({"side": "SELL", "price": sell_px, "qty": qty})
        return pd.DataFrame(rows)

    def test_all_winners(self):
        df = self._make_trades([(100, 110, 1.0), (200, 220, 2.0)])
        pf = profit_factor(df)
        # gross_profit=10+40=50, gross_loss=0 → capped at 999
        assert pf == 999.0

    def test_all_losers(self):
        df = self._make_trades([(110, 100, 1.0), (220, 200, 2.0)])
        pf = profit_factor(df)
        assert pf == 0.0  # gross_profit=0, gross_loss>0

    def test_mixed(self):
        df = self._make_trades([(100, 120, 1.0), (200, 180, 1.0)])
        pf = profit_factor(df)
        # gross_profit=20, gross_loss=20 → PF=1.0
        assert abs(pf - 1.0) < 1e-9

    def test_empty_trades(self):
        assert profit_factor(pd.DataFrame()) == 0.0

    def test_no_sells(self):
        df = pd.DataFrame([{"side": "BUY", "price": 100.0, "qty": 1.0}])
        assert profit_factor(df) == 0.0
        """BUY-BUY-SELL: profit_factor must use avg cost basis, not last BUY price."""
        # BUY 1.0 @ 100, BUY 1.0 @ 120 → avg cost = 110
        # SELL 2.0 @ 130 → PnL = (130-110)*2 = 40 → PF = 999 (no losses)
        rows = [
            {"side": "BUY",  "price": 100.0, "qty": 1.0},
            {"side": "BUY",  "price": 120.0, "qty": 1.0},
            {"side": "SELL", "price": 130.0, "qty": 2.0},
        ]
        df = pd.DataFrame(rows)
        assert profit_factor(df) == 999.0  # all profit, no loss

    def test_accumulated_position_loss_uses_avg_cost(self):
        # BUY 1.0 @ 100, BUY 1.0 @ 120 → avg cost = 110
        # SELL 2.0 @ 100 → PnL = (100-110)*2 = -20 → PF = 0.0
        rows = [
            {"side": "BUY",  "price": 100.0, "qty": 1.0},
            {"side": "BUY",  "price": 120.0, "qty": 1.0},
            {"side": "SELL", "price": 100.0, "qty": 2.0},
        ]
        df = pd.DataFrame(rows)
        assert profit_factor(df) == 0.0  # all loss, no profit


# ---------------------------------------------------------------------------
# acceptance_gate
# ---------------------------------------------------------------------------

class TestAcceptanceGate:
    def _passing(self, **overrides):
        base = {
            "sharpe":        SHARPE_GATE + 0.1,
            "max_drawdown":  MAX_DD_GATE - 0.01,
            "profit_factor": PROFIT_FACTOR_GATE + 0.1,
            "n_trades":      MIN_TRADES_GATE + 50,
        }
        base.update(overrides)
        return base

    def test_all_pass(self):
        passed, failures = acceptance_gate(self._passing())
        assert passed is True
        assert failures == []

    def test_sharpe_fails(self):
        passed, failures = acceptance_gate(self._passing(sharpe=0.0))
        assert passed is False
        assert any("Sharpe" in f for f in failures)

    def test_drawdown_fails(self):
        passed, failures = acceptance_gate(self._passing(max_drawdown=0.99))
        assert passed is False
        assert any("drawdown" in f for f in failures)

    def test_profit_factor_fails(self):
        passed, failures = acceptance_gate(self._passing(profit_factor=0.5))
        assert passed is False
        assert any("Profit factor" in f for f in failures)

    def test_trade_count_fails(self):
        passed, failures = acceptance_gate(self._passing(n_trades=5))
        assert passed is False
        assert any("Trade count" in f for f in failures)

    def test_multiple_failures(self):
        passed, failures = acceptance_gate({
            "sharpe": 0.0, "max_drawdown": 0.99,
            "profit_factor": 0.1, "n_trades": 1
        })
        assert passed is False
        assert len(failures) == 4

    def test_boundary_sharpe_exactly_at_gate_passes(self):
        """Gate is strict less-than, so exactly at the threshold still passes."""
        passed, _ = acceptance_gate(self._passing(sharpe=SHARPE_GATE))
        assert passed is True


# ---------------------------------------------------------------------------
# compute_metrics
# ---------------------------------------------------------------------------

class TestComputeMetrics:
    def test_returns_all_keys(self):
        equity = pd.Series([10_000.0 + i for i in range(100)])
        trades = pd.DataFrame(
            [{"side": "BUY", "price": 100.0, "qty": 1.0},
             {"side": "SELL", "price": 110.0, "qty": 1.0}]
        )
        metrics = compute_metrics(trades, equity)
        assert set(metrics.keys()) == {"sharpe", "max_drawdown", "profit_factor", "n_trades"}

    def test_n_trades_matches_dataframe_length(self):
        equity = pd.Series([10_000.0] * 10)
        trades = pd.DataFrame(
            [{"side": "BUY",  "price": 100.0, "qty": 1.0},
             {"side": "SELL", "price": 105.0, "qty": 1.0}]
        )
        metrics = compute_metrics(trades, equity)
        assert metrics["n_trades"] == 2.0
