"""Tests for backtester/walk_forward.py"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pandas as pd
import pytest

from backtester.walk_forward import (
    _month_windows,
    walk_forward,
    aggregate_results,
)


# ---------------------------------------------------------------------------
# _month_windows — window generation
# ---------------------------------------------------------------------------

class TestMonthWindows:
    def test_3_month_windows_from_9_months(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end   = datetime(2024, 10, 1, tzinfo=timezone.utc)
        windows = _month_windows(start, end, window_months=3)
        # 9 months / 3-month windows → 3 complete windows
        assert len(windows) == 3

    def test_correct_date_ranges(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end   = datetime(2024, 7, 1, tzinfo=timezone.utc)
        windows = _month_windows(start, end, window_months=3)
        assert len(windows) == 2
        # Window 1: Jan–Apr
        assert windows[0][0] == datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert windows[0][1] == datetime(2024, 4, 1, tzinfo=timezone.utc)
        # Window 2: Apr–Jul
        assert windows[1][0] == datetime(2024, 4, 1, tzinfo=timezone.utc)
        assert windows[1][1] == datetime(2024, 7, 1, tzinfo=timezone.utc)

    def test_range_smaller_than_one_window_returns_empty(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end   = datetime(2024, 2, 1, tzinfo=timezone.utc)
        windows = _month_windows(start, end, window_months=3)
        assert windows == []

    def test_exact_one_window(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end   = datetime(2024, 4, 1, tzinfo=timezone.utc)
        windows = _month_windows(start, end, window_months=3)
        assert len(windows) == 1

    def test_naive_datetime_treated_as_utc(self):
        """Naive start should not raise."""
        start = datetime(2024, 1, 1)  # naive
        end   = datetime(2024, 7, 1, tzinfo=timezone.utc)
        windows = _month_windows(start, end, window_months=3)
        assert len(windows) == 2


# ---------------------------------------------------------------------------
# walk_forward — integration (mocked run_backtest + build_equity_curve)
# ---------------------------------------------------------------------------

def _dummy_trades():
    """Return a minimal trades DataFrame for testing."""
    return pd.DataFrame([
        {"side": "BUY",  "price": 100.0, "qty": 1.0},
        {"side": "SELL", "price": 110.0, "qty": 1.0},
    ])


def _dummy_equity():
    return pd.Series([10_000.0, 10_100.0, 10_200.0])


class TestWalkForward:
    @patch("backtester.walk_forward.build_equity_curve")
    @patch("backtester.walk_forward.run_backtest")
    def test_correct_number_of_calls(self, mock_run, mock_equity):
        mock_run.return_value = _dummy_trades()
        mock_equity.return_value = _dummy_equity()

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end   = datetime(2024, 10, 1, tzinfo=timezone.utc)
        results = walk_forward("BTCUSDT", start, end, window_months=3)

        # 9-month range / 3-month windows = 3 windows
        assert len(results) == 3
        assert mock_run.call_count == 3

    @patch("backtester.walk_forward.build_equity_curve")
    @patch("backtester.walk_forward.run_backtest")
    def test_result_structure(self, mock_run, mock_equity):
        mock_run.return_value = _dummy_trades()
        mock_equity.return_value = _dummy_equity()

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end   = datetime(2024, 4, 1, tzinfo=timezone.utc)
        results = walk_forward("BTCUSDT", start, end, window_months=3)

        assert len(results) == 1
        r = results[0]
        required_keys = {"window", "oos_start", "oos_end", "sharpe", "max_drawdown",
                         "profit_factor", "n_trades", "passed", "failures", "final_equity"}
        assert required_keys.issubset(r.keys())

    @patch("backtester.walk_forward.build_equity_curve")
    @patch("backtester.walk_forward.run_backtest")
    def test_oos_dates_within_window(self, mock_run, mock_equity):
        mock_run.return_value = _dummy_trades()
        mock_equity.return_value = _dummy_equity()

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end   = datetime(2024, 4, 1, tzinfo=timezone.utc)
        results = walk_forward("BTCUSDT", start, end, window_months=3, train_pct=0.7)

        r = results[0]
        assert r["oos_start"] >= start
        assert r["oos_end"]   <= end
        assert r["oos_start"] < r["oos_end"]

    @patch("backtester.walk_forward.run_backtest")
    def test_value_error_becomes_zero_trade_result(self, mock_run):
        mock_run.side_effect = ValueError("No candles in the requested date range")

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end   = datetime(2024, 4, 1, tzinfo=timezone.utc)
        results = walk_forward("BTCUSDT", start, end, window_months=3)

        assert len(results) == 1
        r = results[0]
        assert r["n_trades"] == 0
        assert r["passed"] is False
        assert r["failures"]  # not empty

    @patch("backtester.walk_forward.build_equity_curve")
    @patch("backtester.walk_forward.run_backtest")
    def test_window_index_is_1_indexed(self, mock_run, mock_equity):
        mock_run.return_value = _dummy_trades()
        mock_equity.return_value = _dummy_equity()

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end   = datetime(2024, 7, 1, tzinfo=timezone.utc)
        results = walk_forward("BTCUSDT", start, end, window_months=3)

        assert results[0]["window"] == 1
        assert results[1]["window"] == 2


# ---------------------------------------------------------------------------
# aggregate_results
# ---------------------------------------------------------------------------

class TestAggregateResults:
    def _make_results(self, passed_flags, sharpes=None):
        sharpes = sharpes or [1.0] * len(passed_flags)
        return [
            {
                "window": i + 1, "oos_start": None, "oos_end": None,
                "sharpe": s, "max_drawdown": 0.05, "profit_factor": 2.0,
                "n_trades": 50, "passed": p, "failures": [], "final_equity": 10_000.0,
            }
            for i, (p, s) in enumerate(zip(passed_flags, sharpes))
        ]

    def test_empty_returns_empty_dict(self):
        assert aggregate_results([]) == {}

    def test_all_pass(self):
        agg = aggregate_results(self._make_results([True, True, True]))
        assert agg["windows_passed"] == 3
        assert agg["pass_rate"] == 1.0

    def test_partial_pass(self):
        agg = aggregate_results(self._make_results([True, False, True]))
        assert agg["windows_passed"] == 2
        assert abs(agg["pass_rate"] - round(2 / 3, 3)) < 1e-9

    def test_mean_sharpe(self):
        agg = aggregate_results(self._make_results([True, True], sharpes=[1.0, 3.0]))
        assert abs(agg["mean_sharpe"] - 2.0) < 1e-6

    def test_total_trades(self):
        agg = aggregate_results(self._make_results([True, True, True]))
        assert agg["total_trades"] == 150  # 3 × 50
