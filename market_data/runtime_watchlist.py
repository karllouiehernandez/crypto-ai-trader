"""Persisted runtime watchlist helpers."""

from __future__ import annotations

import json

from config import SYMBOLS
from database.models import SessionLocal, get_app_setting, init_db, set_app_setting

_WATCHLIST_KEY = "runtime_symbols"


def _normalise_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def _normalise_symbols(symbols: list[str] | tuple[str, ...] | None) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in symbols or []:
        symbol = _normalise_symbol(raw)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        ordered.append(symbol)
    return ordered


def list_runtime_symbols() -> list[str]:
    """Return the persisted runtime watchlist, seeding from config defaults once."""
    init_db()
    with SessionLocal() as sess:
        raw = get_app_setting(sess, _WATCHLIST_KEY)
        if raw is None:
            seeded = _normalise_symbols(SYMBOLS)
            set_app_setting(sess, _WATCHLIST_KEY, json.dumps(seeded))
            sess.commit()
            return seeded
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = []
        return _normalise_symbols(data if isinstance(data, list) else [])


def set_runtime_symbols(symbols: list[str] | tuple[str, ...]) -> list[str]:
    """Replace the persisted runtime watchlist."""
    init_db()
    clean = _normalise_symbols(list(symbols))
    with SessionLocal() as sess:
        set_app_setting(sess, _WATCHLIST_KEY, json.dumps(clean))
        sess.commit()
    return clean


def add_runtime_symbol(symbol: str) -> list[str]:
    """Add one symbol to the runtime watchlist."""
    clean = _normalise_symbol(symbol)
    if not clean:
        return list_runtime_symbols()
    current = list_runtime_symbols()
    if clean in current:
        return current
    current.append(clean)
    return set_runtime_symbols(current)


def remove_runtime_symbol(symbol: str) -> list[str]:
    """Remove one symbol from the runtime watchlist."""
    clean = _normalise_symbol(symbol)
    if not clean:
        return list_runtime_symbols()
    current = [item for item in list_runtime_symbols() if item != clean]
    return set_runtime_symbols(current)

