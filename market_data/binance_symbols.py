"""Discover Binance spot USDT symbols for UI and research use."""

from __future__ import annotations

from typing import Any

import requests

_BINANCE_EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"
_BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"


def list_binance_spot_usdt_symbols() -> list[dict[str, Any]]:
    """Return active Binance spot USDT symbols sorted by 24h quote volume."""
    exchange_resp = requests.get(_BINANCE_EXCHANGE_INFO_URL, timeout=15)
    exchange_resp.raise_for_status()
    exchange_info = exchange_resp.json()

    ticker_resp = requests.get(_BINANCE_TICKER_URL, timeout=15)
    ticker_resp.raise_for_status()
    ticker_rows = ticker_resp.json()

    quote_volume_by_symbol: dict[str, float] = {}
    for row in ticker_rows:
        symbol = str(row.get("symbol", "")).strip().upper()
        try:
            quote_volume_by_symbol[symbol] = float(row.get("quoteVolume", 0.0))
        except (TypeError, ValueError):
            quote_volume_by_symbol[symbol] = 0.0

    symbols: list[dict[str, Any]] = []
    for row in exchange_info.get("symbols", []):
        symbol = str(row.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        if row.get("quoteAsset") != "USDT":
            continue
        if row.get("status") != "TRADING":
            continue
        if row.get("isSpotTradingAllowed") is False:
            continue
        symbols.append(
            {
                "symbol": symbol,
                "base_asset": str(row.get("baseAsset", "")),
                "quote_asset": str(row.get("quoteAsset", "")),
                "status": str(row.get("status", "")),
                "quote_volume": float(quote_volume_by_symbol.get(symbol, 0.0)),
            }
        )

    symbols.sort(key=lambda item: (-item["quote_volume"], item["symbol"]))
    for idx, item in enumerate(symbols, start=1):
        item["quote_volume_rank"] = idx
    return symbols


def list_binance_spot_usdt_symbol_names() -> list[str]:
    """Return symbol strings only, sorted by 24h quote volume."""
    return [row["symbol"] for row in list_binance_spot_usdt_symbols()]

