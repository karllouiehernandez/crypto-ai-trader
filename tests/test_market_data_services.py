"""Tests for symbol discovery, runtime watchlists, and history audit helpers."""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from database.models import AppSetting, Candle, SessionLocal, init_db
from market_data.binance_symbols import list_binance_spot_usdt_symbol_names, list_binance_spot_usdt_symbols
from market_data.history import audit, backfill, sync_recent
from market_data.runtime_watchlist import list_runtime_symbols, set_runtime_symbols


def _clear_market_data_state() -> None:
    init_db()
    with SessionLocal() as sess:
        sess.query(Candle).delete()
        sess.query(AppSetting).delete()
        sess.commit()


def test_list_binance_spot_usdt_symbols_filters_trading_spot_usdt_only():
    exchange_resp = MagicMock()
    exchange_resp.raise_for_status = MagicMock()
    exchange_resp.json.return_value = {
        "symbols": [
            {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING", "isSpotTradingAllowed": True},
            {"symbol": "ETHBUSD", "baseAsset": "ETH", "quoteAsset": "BUSD", "status": "TRADING", "isSpotTradingAllowed": True},
            {"symbol": "XRPUSDT", "baseAsset": "XRP", "quoteAsset": "USDT", "status": "BREAK", "isSpotTradingAllowed": True},
            {"symbol": "ADAUSDT", "baseAsset": "ADA", "quoteAsset": "USDT", "status": "TRADING", "isSpotTradingAllowed": False},
        ]
    }
    ticker_resp = MagicMock()
    ticker_resp.raise_for_status = MagicMock()
    ticker_resp.json.return_value = [
        {"symbol": "BTCUSDT", "quoteVolume": "5000000"},
        {"symbol": "ETHBUSD", "quoteVolume": "4000000"},
        {"symbol": "XRPUSDT", "quoteVolume": "3000000"},
        {"symbol": "ADAUSDT", "quoteVolume": "2000000"},
    ]

    with patch("market_data.binance_symbols.requests.get", side_effect=[exchange_resp, ticker_resp]):
        rows = list_binance_spot_usdt_symbols()

    assert [row["symbol"] for row in rows] == ["BTCUSDT"]
    assert rows[0]["quote_volume_rank"] == 1


def test_list_binance_spot_usdt_symbol_names_sorted_by_volume():
    exchange_resp = MagicMock()
    exchange_resp.raise_for_status = MagicMock()
    exchange_resp.json.return_value = {
        "symbols": [
            {"symbol": "ETHUSDT", "baseAsset": "ETH", "quoteAsset": "USDT", "status": "TRADING", "isSpotTradingAllowed": True},
            {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING", "isSpotTradingAllowed": True},
        ]
    }
    ticker_resp = MagicMock()
    ticker_resp.raise_for_status = MagicMock()
    ticker_resp.json.return_value = [
        {"symbol": "ETHUSDT", "quoteVolume": "3000000"},
        {"symbol": "BTCUSDT", "quoteVolume": "5000000"},
    ]

    with patch("market_data.binance_symbols.requests.get", side_effect=[exchange_resp, ticker_resp]):
        names = list_binance_spot_usdt_symbol_names()

    assert names == ["BTCUSDT", "ETHUSDT"]


def test_runtime_watchlist_seeds_from_config_defaults():
    _clear_market_data_state()
    symbols = list_runtime_symbols()
    assert symbols


def test_runtime_watchlist_persists_explicit_empty_list():
    _clear_market_data_state()
    set_runtime_symbols([])
    assert list_runtime_symbols() == []


def test_runtime_watchlist_replaces_symbols():
    _clear_market_data_state()
    updated = set_runtime_symbols(["DOGEUSDT", "BTCUSDT", "DOGEUSDT"])
    assert updated == ["DOGEUSDT", "BTCUSDT"]
    assert list_runtime_symbols() == ["DOGEUSDT", "BTCUSDT"]


def _make_row(symbol: str, offset_minutes: int, price: float = 100.0) -> dict:
    return {
        "symbol": symbol,
        "open_time": datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=offset_minutes),
        "open": price,
        "high": price + 1,
        "low": price - 1,
        "close": price,
        "volume": 10.0,
    }


def test_audit_detects_missing_ranges():
    _clear_market_data_state()
    with SessionLocal() as sess:
        for row in [_make_row("DOGEUSDT", 0), _make_row("DOGEUSDT", 2)]:
            sess.add(Candle(**row))
        sess.commit()

    result = audit(
        "DOGEUSDT",
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 0, 2, tzinfo=timezone.utc),
    )
    assert result["is_complete"] is False
    assert len(result["missing_ranges"]) == 1
    assert result["missing_ranges"][0]["start"].minute == 1


def test_backfill_inserts_archive_rows_for_non_default_symbol():
    _clear_market_data_state()
    archive_rows = [_make_row("DOGEUSDT", 0), _make_row("DOGEUSDT", 1)]

    with patch("market_data.history._download_archive_day", return_value=archive_rows), \
         patch("market_data.history._fetch_api_klines", return_value=[]):
        result = backfill(
            "DOGEUSDT",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
        )

    assert result["is_complete"] is True
    with SessionLocal() as sess:
        count = sess.query(Candle).filter(Candle.symbol == "DOGEUSDT").count()
    assert count == 2


def test_sync_recent_is_idempotent_when_no_new_rows():
    _clear_market_data_state()
    with SessionLocal() as sess:
        sess.add(Candle(**_make_row("DOGEUSDT", 0)))
        sess.commit()

    with patch("market_data.history._fetch_api_klines", return_value=[]):
        result = sync_recent("DOGEUSDT")

    assert result["actual_bars"] == 0
    assert result["is_complete"] is False
