"""Tests for symbol discovery, runtime watchlists, history audit helpers, and symbol readiness."""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from database.models import AppSetting, Candle, SessionLocal, SymbolLoadJob, init_db
from market_data import history as history_module
from market_data import runtime_watchlist as runtime_watchlist_module
from market_data import symbol_readiness as symbol_readiness_module
from market_data.binance_symbols import list_binance_spot_usdt_symbol_names, list_binance_spot_usdt_symbols
from market_data.history import _download_archive_day, audit, backfill, maintain_symbol_freshness, sync_recent
from market_data.professional_universe import (
    EXCLUDED_LONG_TERM_RESEARCH_SYMBOLS,
    build_professional_universe_frame,
    list_professional_universe,
    validate_professional_universe_catalog,
)
from market_data.runtime_watchlist import list_runtime_symbols, set_runtime_symbols
from market_data.symbol_readiness import (
    is_symbol_ready,
    list_load_jobs,
    list_ready_symbols,
    queue_symbol_load,
    retry_failed_load,
)
from tests._db_test_utils import install_temp_app_db


@pytest.fixture(autouse=True)
def isolate_market_data_db(monkeypatch, tmp_path):
    install_temp_app_db(
        monkeypatch,
        tmp_path,
        module_globals=globals(),
        module_targets=[
            history_module,
            runtime_watchlist_module,
            symbol_readiness_module,
        ],
    )


def _clear_market_data_state() -> None:
    init_db()
    with SessionLocal() as sess:
        sess.query(Candle).delete()
        sess.query(AppSetting).delete()
        sess.commit()


def _archive_zip_bytes(filename: str, content: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(filename, content)
    return buffer.getvalue()


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


def test_professional_universe_has_twenty_durable_non_stable_symbols():
    universe = list_professional_universe()

    assert len(universe) == 20
    assert len(set(universe)) == 20
    assert all(symbol.endswith("USDT") for symbol in universe)
    assert not (set(universe) & EXCLUDED_LONG_TERM_RESEARCH_SYMBOLS)


def test_professional_universe_validates_active_catalog_rows():
    catalog = [
        {
            "symbol": symbol,
            "status": "TRADING",
            "quote_volume_rank": idx,
            "quote_volume": 1000.0,
        }
        for idx, symbol in enumerate(list_professional_universe(), start=1)
    ]

    result = validate_professional_universe_catalog(catalog)

    assert result["is_valid"] is True
    assert result["missing"] == []
    assert result["inactive"] == []


def test_build_professional_universe_frame_marks_ready_and_runtime_state():
    catalog = [
        {
            "symbol": symbol,
            "status": "TRADING",
            "quote_volume_rank": idx,
            "quote_volume": float(1000 - idx),
        }
        for idx, symbol in enumerate(list_professional_universe(), start=1)
    ]
    rows = build_professional_universe_frame(
        catalog,
        ready_symbols=["BTCUSDT"],
        runtime_symbols=["BTCUSDT", "ETHUSDT"],
        load_jobs=[{"symbol": "ETHUSDT", "status": "queued"}],
        latest_candles={"BTCUSDT": datetime(2024, 1, 1, tzinfo=timezone.utc)},
    )

    by_symbol = {row["symbol"]: row for row in rows}
    assert by_symbol["BTCUSDT"]["local_history"] == "ready"
    assert by_symbol["BTCUSDT"]["runtime_watchlist"] == "active"
    assert by_symbol["ETHUSDT"]["load_status"] == "queued"
    assert by_symbol["SOLUSDT"]["runtime_watchlist"] == "research only"


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


def test_download_archive_day_supports_microsecond_spot_timestamps():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "DOGEUSDT-1m-2026-04-18.csv",
            "1776470400000000,0.1500,0.1600,0.1400,0.1550,1000,1776470459999999,0,0,0,0,0\n",
        )

    response = MagicMock()
    response.status_code = 200
    response.content = buffer.getvalue()
    response.raise_for_status = MagicMock()

    with patch("market_data.history.requests.get", return_value=response):
        rows = _download_archive_day("DOGEUSDT", datetime(2026, 4, 18, tzinfo=timezone.utc), "1m")

    assert len(rows) == 1
    assert rows[0]["open_time"] == datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)


def test_download_archive_day_reads_mirror_cache_before_network(monkeypatch, tmp_path):
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(history_module, "BINANCE_HISTORY_CACHE_DIR", cache_dir)
    cache_file = (
        cache_dir
        / "spot"
        / "daily"
        / "klines"
        / "DOGEUSDT"
        / "1m"
        / "DOGEUSDT-1m-2026-04-18.zip"
    )
    cache_file.parent.mkdir(parents=True)
    cache_file.write_bytes(
        _archive_zip_bytes(
            "DOGEUSDT-1m-2026-04-18.csv",
            "1776470400000000,0.1500,0.1600,0.1400,0.1550,1000,1776470459999999,0,0,0,0,0\n",
        )
    )

    with patch("market_data.history.requests.get") as get_mock:
        rows = _download_archive_day("DOGEUSDT", datetime(2026, 4, 18, tzinfo=timezone.utc), "1m")

    get_mock.assert_not_called()
    assert len(rows) == 1
    assert rows[0]["symbol"] == "DOGEUSDT"


def test_download_archive_day_writes_mirror_cache_on_network_fetch(monkeypatch, tmp_path):
    monkeypatch.setattr(history_module, "BINANCE_HISTORY_CACHE_DIR", tmp_path / "cache")
    response = MagicMock()
    response.status_code = 200
    response.content = _archive_zip_bytes(
        "DOGEUSDT-1m-2026-04-18.csv",
        "1776470400000000,0.1500,0.1600,0.1400,0.1550,1000,1776470459999999,0,0,0,0,0\n",
    )
    response.raise_for_status = MagicMock()

    with patch("market_data.history.requests.get", return_value=response):
        rows = _download_archive_day("DOGEUSDT", datetime(2026, 4, 18, tzinfo=timezone.utc), "1m")

    cache_file = (
        tmp_path
        / "cache"
        / "spot"
        / "daily"
        / "klines"
        / "DOGEUSDT"
        / "1m"
        / "DOGEUSDT-1m-2026-04-18.zip"
    )
    assert len(rows) == 1
    assert cache_file.exists()


def test_sync_recent_is_idempotent_when_no_new_rows():
    _clear_market_data_state()
    with SessionLocal() as sess:
        sess.add(Candle(**_make_row("DOGEUSDT", 0)))
        sess.commit()

    with patch("market_data.history._fetch_api_klines", return_value=[]):
        result = sync_recent("DOGEUSDT")

    assert result["actual_bars"] == 0
    assert result["is_complete"] is False


def test_maintain_symbol_freshness_skips_fresh_symbols(monkeypatch):
    _clear_market_data_state()
    fresh_open = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0) - timedelta(minutes=2)
    with SessionLocal() as sess:
        sess.add(Candle(
            symbol="BTCUSDT",
            open_time=fresh_open,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=10.0,
        ))
        sess.commit()

    sync_calls: list[str] = []

    def _unexpected_sync(symbol: str, interval: str = "1m"):
        sync_calls.append(symbol)
        return {"rows_inserted": 0, "is_complete": True}

    monkeypatch.setattr(history_module, "sync_recent", _unexpected_sync)
    results = maintain_symbol_freshness(["BTCUSDT"], max_age_minutes=10)

    assert sync_calls == []
    assert results["BTCUSDT"]["status"] == "fresh"
    assert results["BTCUSDT"]["rows_inserted"] == 0


def test_maintain_symbol_freshness_syncs_stale_symbols(monkeypatch):
    _clear_market_data_state()
    stale_open = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0) - timedelta(minutes=30)
    with SessionLocal() as sess:
        sess.add(Candle(
            symbol="ETHUSDT",
            open_time=stale_open,
            open=200.0,
            high=201.0,
            low=199.0,
            close=200.5,
            volume=12.0,
        ))
        sess.commit()

    sync_calls: list[str] = []

    def _fake_sync(symbol: str, interval: str = "1m"):
        sync_calls.append(symbol)
        now = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
        with SessionLocal() as sess:
            sess.add(Candle(
                symbol=symbol,
                open_time=now,
                open=201.0,
                high=202.0,
                low=200.0,
                close=201.5,
                volume=15.0,
            ))
            sess.commit()
        return {"rows_inserted": 5, "is_complete": True}

    monkeypatch.setattr(history_module, "sync_recent", _fake_sync)
    results = maintain_symbol_freshness(["ETHUSDT"], max_age_minutes=10)

    assert sync_calls == ["ETHUSDT"]
    assert results["ETHUSDT"]["status"] == "synced"
    assert results["ETHUSDT"]["rows_inserted"] == 5
    assert results["ETHUSDT"]["age_minutes_after"] is not None
    assert results["ETHUSDT"]["age_minutes_after"] <= 1.0


def test_maintain_symbol_freshness_uses_default_universe_and_dedupes(monkeypatch):
    sync_calls: list[str] = []
    monkeypatch.setattr(history_module, "MVP_RESEARCH_UNIVERSE", ["BTCUSDT", "BTCUSDT", "ETHUSDT"])
    monkeypatch.setattr(history_module, "get_latest_candle_time", lambda symbol: None)

    def _fake_sync(symbol: str, interval: str = "1m"):
        sync_calls.append(symbol)
        return {"rows_inserted": 1, "is_complete": True}

    monkeypatch.setattr(history_module, "sync_recent", _fake_sync)
    results = maintain_symbol_freshness()

    assert sync_calls == ["BTCUSDT", "ETHUSDT"]
    assert list(results.keys()) == ["BTCUSDT", "ETHUSDT"]


# ── symbol_readiness tests ────────────────────────────────────────────────────

def _clear_load_jobs() -> None:
    init_db()
    with SessionLocal() as sess:
        sess.query(SymbolLoadJob).delete()
        sess.commit()


def test_list_ready_symbols_empty_when_no_candles():
    _clear_market_data_state()
    assert list_ready_symbols() == []


def test_list_ready_symbols_returns_symbols_with_candles():
    _clear_market_data_state()
    with SessionLocal() as sess:
        sess.add(Candle(**_make_row("BTCUSDT", 0)))
        sess.add(Candle(**_make_row("ETHUSDT", 0)))
        sess.commit()
    result = list_ready_symbols()
    assert "BTCUSDT" in result
    assert "ETHUSDT" in result


def test_is_symbol_ready_true_when_candle_exists():
    _clear_market_data_state()
    with SessionLocal() as sess:
        sess.add(Candle(**_make_row("BTCUSDT", 0)))
        sess.commit()
    assert is_symbol_ready("BTCUSDT") is True
    assert is_symbol_ready("btcusdt") is True  # normalisation


def test_is_symbol_ready_false_when_no_candles():
    _clear_market_data_state()
    assert is_symbol_ready("DOGEUSDT") is False


def test_queue_symbol_load_creates_queued_job():
    _clear_load_jobs()
    job = queue_symbol_load("SOLUSDT")
    assert job["symbol"] == "SOLUSDT"
    assert job["status"] == "queued"
    jobs = list_load_jobs()
    assert any(j["symbol"] == "SOLUSDT" and j["status"] == "queued" for j in jobs)


def test_queue_symbol_load_is_idempotent_for_queued():
    _clear_load_jobs()
    queue_symbol_load("SOLUSDT")
    job2 = queue_symbol_load("SOLUSDT")
    assert job2["status"] == "queued"
    assert sum(1 for j in list_load_jobs() if j["symbol"] == "SOLUSDT") == 1


def test_queue_symbol_load_resets_failed_to_queued():
    _clear_load_jobs()
    init_db()
    with SessionLocal() as sess:
        sess.add(SymbolLoadJob(symbol="SOLUSDT", status="failed", error_msg="boom"))
        sess.commit()
    job = queue_symbol_load("SOLUSDT")
    assert job["status"] == "queued"
    assert job["error_msg"] is None


def test_retry_failed_load_resets_to_queued():
    _clear_load_jobs()
    with SessionLocal() as sess:
        sess.add(SymbolLoadJob(symbol="AVAXUSDT", status="failed", error_msg="timeout"))
        sess.commit()
    job = retry_failed_load("AVAXUSDT")
    assert job["status"] == "queued"


def test_list_load_jobs_returns_most_recent_first():
    _clear_load_jobs()
    queue_symbol_load("AAVEUSDT")
    queue_symbol_load("LINKUSDT")
    jobs = list_load_jobs()
    assert len(jobs) >= 2
    # most recent is first (LINKUSDT queued after AAVEUSDT)
    symbols = [j["symbol"] for j in jobs]
    assert symbols.index("LINKUSDT") < symbols.index("AAVEUSDT")
