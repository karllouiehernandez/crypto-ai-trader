"""Curated research-universe helpers for professional day-trading workflows."""

from __future__ import annotations

from typing import Any

from config import PROFESSIONAL_SYMBOL_UNIVERSE

EXCLUDED_LONG_TERM_RESEARCH_SYMBOLS = {
    "USDCUSDT",
    "FDUSDUSDT",
    "TUSDUSDT",
    "BUSDUSDT",
    "DAIUSDT",
    "USDTUSDT",
    "USD1USDT",
    "RLUSDUSDT",
    "WBTCUSDT",
    "STETHUSDT",
}


def _normalise_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def list_professional_universe() -> list[str]:
    """Return the durable curated research universe, preserving configured order."""
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_symbol in PROFESSIONAL_SYMBOL_UNIVERSE:
        symbol = _normalise_symbol(raw_symbol)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        ordered.append(symbol)
    return ordered


def validate_professional_universe_catalog(catalog_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate the curated universe against a Binance catalog snapshot."""
    universe = list_professional_universe()
    catalog_by_symbol = {
        _normalise_symbol(str(row.get("symbol", ""))): row
        for row in catalog_rows
        if row.get("symbol")
    }
    missing = [symbol for symbol in universe if symbol not in catalog_by_symbol]
    inactive = [
        symbol
        for symbol in universe
        if symbol in catalog_by_symbol and str(catalog_by_symbol[symbol].get("status", "")).upper() != "TRADING"
    ]
    excluded_present = [symbol for symbol in universe if symbol in EXCLUDED_LONG_TERM_RESEARCH_SYMBOLS]
    return {
        "universe": universe,
        "count": len(universe),
        "missing": missing,
        "inactive": inactive,
        "excluded_present": excluded_present,
        "is_valid": len(universe) == 20 and not missing and not inactive and not excluded_present,
    }


def build_professional_universe_frame(
    catalog_rows: list[dict[str, Any]],
    ready_symbols: list[str],
    runtime_symbols: list[str],
    load_jobs: list[dict[str, Any]],
    latest_candles: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build a dashboard-ready status table for the curated research universe."""
    catalog_by_symbol = {
        _normalise_symbol(str(row.get("symbol", ""))): row
        for row in catalog_rows
        if row.get("symbol")
    }
    ready_set = {_normalise_symbol(symbol) for symbol in ready_symbols}
    runtime_set = {_normalise_symbol(symbol) for symbol in runtime_symbols}
    job_by_symbol = {
        _normalise_symbol(str(job.get("symbol", ""))): job
        for job in load_jobs
        if job.get("symbol")
    }
    latest_candles = latest_candles or {}

    rows: list[dict[str, Any]] = []
    for symbol in list_professional_universe():
        catalog = catalog_by_symbol.get(symbol, {})
        job = job_by_symbol.get(symbol, {})
        rows.append(
            {
                "symbol": symbol,
                "binance_status": str(catalog.get("status") or "unknown"),
                "quote_volume_rank": catalog.get("quote_volume_rank"),
                "quote_volume": float(catalog.get("quote_volume", 0.0) or 0.0),
                "local_history": "ready" if symbol in ready_set else "not loaded",
                "runtime_watchlist": "active" if symbol in runtime_set else "research only",
                "load_status": str(job.get("status") or ("ready" if symbol in ready_set else "not queued")),
                "latest_candle_ts": latest_candles.get(symbol),
            }
        )
    return rows
