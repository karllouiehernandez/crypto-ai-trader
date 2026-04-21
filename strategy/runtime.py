"""Unified strategy runtime for built-ins, plugins, and persisted selection."""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from config import EMA_LOOKBACK, MIN_CANDLES_EMA200
from database.models import Candle, SessionLocal, get_app_setting, init_db, set_app_setting
from strategy.artifacts import (
    get_active_runtime_artifact_id,
    get_strategy_artifact,
    sync_strategy_artifacts,
    validate_runtime_artifact,
)
from strategy.base import StrategyBase
from strategy.builtin import BUILTIN_STRATEGY_CLASSES
from strategy.regime import Regime, detect_regime
from strategy.signals import Signal
from strategy.ta_features import add_indicators
from strategies.loader import get_strategy as get_plugin_strategy
from strategies.loader import list_strategies as list_plugin_strategies
from strategies.loader import list_strategy_errors, load_all

log = logging.getLogger(__name__)

LEGACY_ACTIVE_STRATEGY_NAME_KEY = "active_strategy_name"
LEGACY_ACTIVE_STRATEGY_VERSION_KEY = "active_strategy_version"
LEGACY_ACTIVE_STRATEGY_PARAMS_KEY = "active_strategy_params"
ACTIVE_BACKTEST_STRATEGY_NAME_KEY = "active_backtest_strategy_name"
ACTIVE_BACKTEST_STRATEGY_VERSION_KEY = "active_backtest_strategy_version"
ACTIVE_BACKTEST_STRATEGY_PARAMS_KEY = "active_backtest_strategy_params"
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


def get_strategy_instance(name: str, params: Optional[dict] = None) -> Optional[StrategyBase]:
    """Return an isolated strategy instance with explicit params applied."""
    prototype = get_strategy(name)
    if prototype is None:
        return None

    strategy = copy.deepcopy(prototype)
    strategy.apply_params(params)
    return strategy


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
    plugins = sync_strategy_artifacts(list_plugin_strategies())
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
    """Return the persisted backtest/default strategy selection."""
    init_db()
    with SessionLocal() as sess:
        name = (
            get_app_setting(sess, ACTIVE_BACKTEST_STRATEGY_NAME_KEY, None)
            or get_app_setting(sess, LEGACY_ACTIVE_STRATEGY_NAME_KEY, DEFAULT_STRATEGY_NAME)
            or DEFAULT_STRATEGY_NAME
        )
        version = (
            get_app_setting(sess, ACTIVE_BACKTEST_STRATEGY_VERSION_KEY, None)
            or get_app_setting(sess, LEGACY_ACTIVE_STRATEGY_VERSION_KEY, "")
            or ""
        )
        params_raw = (
            get_app_setting(sess, ACTIVE_BACKTEST_STRATEGY_PARAMS_KEY, None)
            or get_app_setting(sess, LEGACY_ACTIVE_STRATEGY_PARAMS_KEY, "{}")
            or "{}"
        )

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
    """Persist the selected backtest/default strategy and return its saved config."""
    strategy = get_strategy(name)
    if strategy is None:
        raise ValueError(f"Unknown strategy: {name}")

    params = params or strategy.default_params()
    init_db()
    with SessionLocal() as sess:
        set_app_setting(sess, ACTIVE_BACKTEST_STRATEGY_NAME_KEY, strategy.name)
        set_app_setting(sess, ACTIVE_BACKTEST_STRATEGY_VERSION_KEY, strategy.version)
        set_app_setting(sess, ACTIVE_BACKTEST_STRATEGY_PARAMS_KEY, json.dumps(params))
        set_app_setting(sess, LEGACY_ACTIVE_STRATEGY_NAME_KEY, strategy.name)
        set_app_setting(sess, LEGACY_ACTIVE_STRATEGY_VERSION_KEY, strategy.version)
        set_app_setting(sess, LEGACY_ACTIVE_STRATEGY_PARAMS_KEY, json.dumps(params))
        sess.commit()

    return {"name": strategy.name, "version": strategy.version, "params": params}


def get_active_runtime_artifact(run_mode: str) -> dict | None:
    artifact_id = get_active_runtime_artifact_id(run_mode)
    return get_strategy_artifact(artifact_id)


def resolve_runtime_strategy_descriptor(run_mode: str) -> dict:
    artifact_id = get_active_runtime_artifact_id(run_mode)
    artifact, error = validate_runtime_artifact(artifact_id)
    if error or artifact is None:
        raise RuntimeError(error or "Runtime strategy artifact is not available.")

    strategy = get_strategy(artifact["name"])
    if strategy is None:
        raise RuntimeError(
            f"Runtime strategy `{artifact['name']}` could not be loaded from `{artifact['path']}`."
        )
    return {
        "artifact_id": artifact["id"],
        "strategy_name": artifact["name"],
        "strategy_version": artifact.get("version") or strategy.version,
        "strategy_params": strategy.default_params(),
        "strategy_code_hash": artifact.get("code_hash", ""),
        "strategy_provenance": artifact.get("provenance", ""),
        "artifact_status": artifact.get("status", ""),
        "path": artifact.get("path", ""),
    }


def _fetch_recent_candles(
    session: Session,
    symbol: str,
    lookback: int = EMA_LOOKBACK,
    as_of_time=None,
) -> list[Candle]:
    query = (
        session.query(Candle)
        .filter(Candle.symbol == symbol)
    )
    if as_of_time is not None:
        query = query.filter(Candle.open_time <= as_of_time)
    return query.order_by(Candle.open_time.desc()).limit(lookback).all()


def _candles_to_indicator_frame(candles: list[Candle]) -> pd.DataFrame:
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


def build_indicator_frame(
    session: Session,
    symbol: str,
    lookback: int = EMA_LOOKBACK,
    as_of_time=None,
) -> pd.DataFrame:
    candles = _fetch_recent_candles(session, symbol, lookback=lookback, as_of_time=as_of_time)
    return _candles_to_indicator_frame(candles)


def compute_strategy_decision(
    session: Session,
    candle: Candle,
    strategy_name: Optional[str] = None,
    strategy_params: Optional[dict] = None,
    strategy: StrategyBase | None = None,
    indicator_frame: pd.DataFrame | None = None,
) -> StrategyDecision:
    """Resolve a strategy and compute the current signal for the given candle."""
    if strategy is None:
        config = get_active_strategy_config() if strategy_name is None else {"name": strategy_name, "params": strategy_params or {}}
        strategy = get_strategy_instance(config["name"], params=config.get("params"))
        if strategy is None:
            strategy = get_strategy_instance(DEFAULT_STRATEGY_NAME)
    if strategy is None:
        return StrategyDecision(
            signal=Signal.HOLD,
            regime=Regime.RANGING,
            strategy_name=DEFAULT_STRATEGY_NAME,
            strategy_version="",
        )

    df = indicator_frame if indicator_frame is not None else build_indicator_frame(session, candle.symbol)
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
