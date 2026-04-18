"""Unit tests for market_focus.selector and related service helpers."""

from __future__ import annotations

import json
from unittest.mock import patch

import pandas as pd
import pytest

from dashboard.workbench import build_focus_candidate_frame
from market_focus.selector import (
    _composite_score,
    fetch_liquid_usdt_symbols,
    get_latest_study,
    get_study_candidates,
    run_weekly_study,
)


# ─── fetch_liquid_usdt_symbols ────────────────────────────────────────────────

def _make_ticker(symbol: str, quote_volume: float) -> dict:
    return {"symbol": symbol, "quoteVolume": str(quote_volume)}


def test_fetch_liquid_usdt_symbols_filters_usdt_only():
    catalog = [
        {"symbol": "BTCUSDT"},
        {"symbol": "ETHUSDT"},
        {"symbol": "BNBUSDT"},
    ]

    with patch("market_focus.selector.list_binance_spot_usdt_symbols", return_value=catalog):
        result = fetch_liquid_usdt_symbols(n=10)

    assert "BTCUSDT" in result
    assert "ETHUSDT" in result
    assert "BNBUSDT" in result
    assert "BTCBUSD" not in result


def test_fetch_liquid_usdt_symbols_excludes_stablecoins():
    catalog = [
        {"symbol": "USDCUSDT"},
        {"symbol": "BTCUSDT"},
        {"symbol": "ETHUSDT"},
    ]

    with patch("market_focus.selector.list_binance_spot_usdt_symbols", return_value=catalog):
        result = fetch_liquid_usdt_symbols(n=10)

    assert "USDCUSDT" not in result
    assert "BTCUSDT" in result


def test_fetch_liquid_usdt_symbols_sorted_by_volume():
    catalog = [
        {"symbol": "BTCUSDT"},
        {"symbol": "ETHUSDT"},
        {"symbol": "BNBUSDT"},
    ]

    with patch("market_focus.selector.list_binance_spot_usdt_symbols", return_value=catalog):
        result = fetch_liquid_usdt_symbols(n=3)

    assert result[0] == "BTCUSDT"
    assert result[1] == "ETHUSDT"
    assert result[2] == "BNBUSDT"


def test_fetch_liquid_usdt_symbols_respects_n():
    catalog = [{"symbol": f"TOK{i}USDT"} for i in range(20)]

    with patch("market_focus.selector.list_binance_spot_usdt_symbols", return_value=catalog):
        result = fetch_liquid_usdt_symbols(n=5)

    assert len(result) == 5


# ─── _composite_score ─────────────────────────────────────────────────────────

def test_composite_score_positive_metrics():
    metrics = {"sharpe": 2.0, "profit_factor": 2.0, "max_drawdown": -0.10}
    score = _composite_score(metrics)
    assert score > 0


def test_composite_score_penalises_drawdown():
    base = {"sharpe": 1.0, "profit_factor": 1.5, "max_drawdown": 0.0}
    high_dd = {"sharpe": 1.0, "profit_factor": 1.5, "max_drawdown": -0.30}
    assert _composite_score(base) > _composite_score(high_dd)


def test_composite_score_zero_metrics():
    score = _composite_score({})
    assert score == pytest.approx(-999.0)


# ─── run_weekly_study ────────────────────────────────────────────────────────

def _stub_trades() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "side": ["BUY", "SELL"],
            "qty": [1.0, 1.0],
            "price": [100.0, 110.0],
            "pnl": [0.0, 10.0],
            "regime": ["ranging", "ranging"],
            "strategy_name": ["test", "test"],
            "strategy_version": ["1.0", "1.0"],
        }
    )


def _stub_equity() -> pd.DataFrame:
    return pd.DataFrame({"step": [0, 1, 2], "equity": [100.0, 90.0, 110.0]})


def test_run_weekly_study_persists_and_returns(tmp_path, monkeypatch):
    import config as _cfg

    monkeypatch.setattr(_cfg, "DB_PATH", tmp_path / "test.db")

    from database import models as _models
    import importlib
    from database.models import get_engine, Base, SessionLocal as _SL
    new_engine = get_engine()
    Base.metadata.create_all(bind=new_engine)

    tickers = [_make_ticker(f"SYM{i}USDT", float(100 - i)) for i in range(5)]
    stub_trades = _stub_trades()
    stub_equity = _stub_equity()
    stub_metrics = {"sharpe": 1.2, "profit_factor": 1.5, "max_drawdown": -0.08, "n_trades": 2}

    with (
        patch("market_focus.selector.list_binance_spot_usdt_symbols", return_value=[{"symbol": f"SYM{i}USDT"} for i in range(5)]),
        patch("market_focus.selector.run_backtest", return_value=stub_trades),
        patch("market_focus.selector.build_equity_curve", return_value=stub_equity),
        patch("market_focus.selector.compute_metrics", return_value=stub_metrics),
    ):
        result = run_weekly_study(
            strategy_name="test_strategy",
            params={},
            universe_size=5,
            top_n=3,
            backtest_days=7,
        )

    assert result["study_id"] is not None
    assert len(result["top_candidates"]) == 3
    assert result["strategy_name"] == "test_strategy"


# ─── get_latest_study / get_study_candidates ─────────────────────────────────

def test_get_latest_study_returns_none_when_empty():
    from unittest.mock import patch, MagicMock
    mock_sess = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.first.return_value = None
    mock_sess.query.return_value = mock_query
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_sess)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    with patch("market_focus.selector.SessionLocal", return_value=mock_ctx):
        result = get_latest_study()
    assert result is None


def test_get_study_candidates_returns_empty_for_unknown_id():
    from unittest.mock import patch, MagicMock
    mock_sess = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.all.return_value = []
    mock_sess.query.return_value = mock_query
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_sess)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    with patch("market_focus.selector.SessionLocal", return_value=mock_ctx):
        result = get_study_candidates(99999)
    assert result == []


# ─── build_focus_candidate_frame ─────────────────────────────────────────────

def test_build_focus_candidate_frame_empty():
    frame = build_focus_candidate_frame([])
    assert frame.empty


def test_build_focus_candidate_frame_columns():
    candidates = [
        {
            "rank": 1,
            "symbol": "BTCUSDT",
            "volume_rank": 1,
            "score": 1.5,
            "sharpe": 2.0,
            "profit_factor": 1.8,
            "max_drawdown": -0.10,
            "n_trades": 50,
            "status": "completed",
        }
    ]
    frame = build_focus_candidate_frame(candidates)
    assert not frame.empty
    assert "rank" in frame.columns
    assert "symbol" in frame.columns
    assert "score" in frame.columns
    assert "sharpe" in frame.columns


def test_build_focus_candidate_frame_null_metrics():
    candidates = [
        {
            "rank": 1,
            "symbol": "XYZUSDT",
            "volume_rank": 5,
            "score": -999.0,
            "sharpe": None,
            "profit_factor": None,
            "max_drawdown": None,
            "n_trades": None,
            "status": "error",
        }
    ]
    frame = build_focus_candidate_frame(candidates)
    assert frame.iloc[0]["sharpe"] is None


# ─── service helpers ─────────────────────────────────────────────────────────

def test_service_run_market_focus_study_delegates(tmp_path, monkeypatch):
    import config as _cfg
    monkeypatch.setattr(_cfg, "DB_PATH", tmp_path / "svc.db")
    from database.models import get_engine, Base
    Base.metadata.create_all(bind=get_engine())

    tickers = [_make_ticker(f"T{i}USDT", float(50 - i)) for i in range(5)]
    stub_trades = _stub_trades()
    stub_equity = _stub_equity()
    stub_metrics = {"sharpe": 0.8, "profit_factor": 1.1, "max_drawdown": -0.05, "n_trades": 2}

    with (
        patch("market_focus.selector.list_binance_spot_usdt_symbols", return_value=[{"symbol": f"T{i}USDT"} for i in range(5)]),
        patch("market_focus.selector.run_backtest", return_value=stub_trades),
        patch("market_focus.selector.build_equity_curve", return_value=stub_equity),
        patch("market_focus.selector.compute_metrics", return_value=stub_metrics),
    ):
        from backtester.service import run_market_focus_study
        result = run_market_focus_study("test_strat", universe_size=5, top_n=2, backtest_days=7)

    assert "study_id" in result
    assert "top_candidates" in result
