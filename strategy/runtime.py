"""Unified strategy runtime for built-ins, plugins, and persisted selection."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from config import EMA_LOOKBACK, MIN_CANDLES_EMA200
from database.models import Candle, SessionLocal, get_app_setting, init_db, set_app_setting
from strategy.base import StrategyBase
from strategy.builtin import BUILTIN_STRATEGY_CLASSES
from strategy.regime import Regime, detect_regime
from strategy.signals import Signal
from strategy.ta_features import add_indicators
from strategies.loader import get_strategy as get_plugin_strategy
from strategies.loader import list_strategies as list_plugin_strategies
from strategies.loader import list_strategy_errors, load_all

log = logging.getLogger(__name__)

ACTIVE_STRATEGY_NAME_KEY = "active_strategy_name"
ACTIVE_STRATEGY_VERSION_KEY = "active_strategy_version"
ACTIVE_STRATEGY_PARAMS_KEY = "active_strategy_params"
DEFAULT_STRATEGY_NAME = "regime_router_v1"


@dataclass(frozen=True)
class StrategyDecision:
    signal: Signal
    regime: Regime
    strategy_name: str
    strategy_version: str


def _builtin_registry() -> dict[str, StrategyBase]:
    registry: dict[str, StrategyBase] = {}
    for cls in BUILTIN_STRATEGY_CLASSES:
        inst = cls()
        inst._source_type = "builtin"   # type: ignore[attr-defined]
        inst._source_path = ""          # type: ignore[attr-defined]
        registry[inst.name] = inst
    return registry


def get_strategy(name: str) -> Optional[StrategyBase]:
    builtins = _builtin_registry()
    if name in builtins:
        return builtins[name]

    load_all()
    return get_plugin_strategy(name)


def list_available_strategies() -> list[dict]:
    """Return built-in and plugin strategies for dashboard display."""
    builtins = []
    for strategy in _builtin_registry().values():
        builtins.append(
            {
                **strategy.meta(),
                "source": "builtin",
                "path": "",
                "file_name": "",
                "is_generated": False,
                "provenance": "builtin",
                "generated_at": "",
                "modified_at": "",
                "load_status": "loaded",
                "validation_status": "valid",
            }
        )

    load_all()
    plugins = list_plugin_strategies()
    return sorted(
        builtins + plugins,
        key=lambda s: (
            {"builtin": 0, "generated": 1, "plugin": 2}.get(s.get("provenance", s.get("source", "plugin")), 3),
            s["display_name"].lower(),
        ),
    )


def list_available_strategy_errors() -> list[dict]:
    load_all()
    return list_strategy_errors()


def _strategy_exists(name: str) -> bool:
    return get_strategy(name) is not None


def get_active_strategy_config() -> dict:
    """Return the persisted active strategy selection."""
    init_db()
    with SessionLocal() as sess:
        name = get_app_setting(sess, ACTIVE_STRATEGY_NAME_KEY, DEFAULT_STRATEGY_NAME) or DEFAULT_STRATEGY_NAME
        version = get_app_setting(sess, ACTIVE_STRATEGY_VERSION_KEY, "") or ""
        params_raw = get_app_setting(sess, ACTIVE_STRATEGY_PARAMS_KEY, "{}") or "{}"

    if not _strategy_exists(name):
        name = DEFAULT_STRATEGY_NAME
        version = get_strategy(name).version if get_strategy(name) else ""
        params_raw = "{}"

    try:
        params = json.loads(params_raw)
    except json.JSONDecodeError:
        params = {}

    strategy = get_strategy(name)
    if strategy is not None and not version:
        version = strategy.version

    return {
        "name": name,
        "version": version,
        "params": params,
    }


def set_active_strategy_config(name: str, params: Optional[dict] = None) -> dict:
    """Persist the selected strategy and return its saved config."""
    strategy = get_strategy(name)
    if strategy is None:
        raise ValueError(f"Unknown strategy: {name}")

    params = params or strategy.default_params()
    init_db()
    with SessionLocal() as sess:
        set_app_setting(sess, ACTIVE_STRATEGY_NAME_KEY, strategy.name)
        set_app_setting(sess, ACTIVE_STRATEGY_VERSION_KEY, strategy.version)
        set_app_setting(sess, ACTIVE_STRATEGY_PARAMS_KEY, json.dumps(params))
        sess.commit()

    return {"name": strategy.name, "version": strategy.version, "params": params}


def _fetch_recent_candles(session: Session, symbol: str, lookback: int = EMA_LOOKBACK) -> list[Candle]:
    return (
        session.query(Candle)
        .filter(Candle.symbol == symbol)
        .order_by(Candle.open_time.desc())
        .limit(lookback)
        .all()
    )


def build_indicator_frame(session: Session, symbol: str, lookback: int = EMA_LOOKBACK) -> pd.DataFrame:
    candles = _fetch_recent_candles(session, symbol, lookback=lookback)
    if len(candles) < MIN_CANDLES_EMA200:
        return pd.DataFrame()

    df = pd.DataFrame(
        [
            (c.open_time, c.open, c.high, c.low, c.close, c.volume)
            for c in reversed(candles)
        ],
        columns=["open_time", "open", "high", "low", "close", "volume"],
    )
    return add_indicators(df)


def compute_strategy_decision(
    session: Session,
    candle: Candle,
    strategy_name: Optional[str] = None,
) -> StrategyDecision:
    """Resolve a strategy and compute the current signal for the given candle."""
    config = get_active_strategy_config() if strategy_name is None else {"name": strategy_name}
    strategy = get_strategy(config["name"]) or get_strategy(DEFAULT_STRATEGY_NAME)
    if strategy is None:
        return StrategyDecision(
            signal=Signal.HOLD,
            regime=Regime.RANGING,
            strategy_name=DEFAULT_STRATEGY_NAME,
            strategy_version="",
        )

    df = build_indicator_frame(session, candle.symbol)
    if df.empty or len(df) < 2:
        return StrategyDecision(
            signal=Signal.HOLD,
            regime=Regime.RANGING,
            strategy_name=strategy.name,
            strategy_version=strategy.version,
        )

    regime = detect_regime(df.set_index("open_time"))
    if regime == Regime.HIGH_VOL:
        return StrategyDecision(
            signal=Signal.HOLD,
            regime=regime,
            strategy_name=strategy.name,
            strategy_version=strategy.version,
        )

    signal = strategy.evaluate(df.set_index("open_time"), regime=regime)
    return StrategyDecision(
        signal=signal,
        regime=regime,
        strategy_name=strategy.name,
        strategy_version=strategy.version,
    )
