"""Backtest execution helpers for dashboard use."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from backtester.engine import build_equity_curve, run_backtest
from backtester.metrics import acceptance_gate, compute_metrics
from database.integrity import assess_backtest_run_integrity, refresh_integrity_flags
from database.models import BacktestPreset, BacktestRun, BacktestTrade, SessionLocal, init_db
from dashboard.workbench import normalise_preset_name, parse_metrics_json, parse_params_json
from market_focus.selector import (
    get_latest_study,
    get_study_candidates,
    run_weekly_study,
)
from strategy.artifacts import mark_artifact_backtest_result
from strategy.runtime import list_available_strategies


def run_and_persist_backtest(
    symbol: str,
    start: datetime,
    end: datetime,
    strategy_name: str,
    params: dict | None = None,
    preset_name: str | None = None,
) -> dict:
    """Run a backtest, persist the run, and return a dashboard-ready payload."""
    init_db()
    params = parse_params_json(json.dumps(params or {}))
    preset_name = normalise_preset_name(preset_name) or None
    strategy_meta = next(
        (item for item in list_available_strategies() if item.get("name") == strategy_name),
        None,
    )
    trades = run_backtest(symbol, start, end, strategy_name=strategy_name, params=params)
    equity_curve = build_equity_curve(trades)
    metrics = compute_metrics(trades, equity_curve)
    passed, failures = acceptance_gate(metrics)
    metrics_payload = json.dumps({**metrics, "passed": passed, "failures": failures}, sort_keys=True)
    integrity_status, integrity_note = assess_backtest_run_integrity(metrics_payload, len(trades))

    with SessionLocal() as sess:
        strategy_version = ""
        if not trades.empty and "strategy_version" in trades.columns:
            strategy_version = str(trades["strategy_version"].dropna().iloc[0]) if not trades["strategy_version"].dropna().empty else ""

        run = BacktestRun(
            symbol=symbol,
            start_ts=start,
            end_ts=end,
            artifact_id=strategy_meta.get("artifact_id") if strategy_meta else None,
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            strategy_code_hash=str(strategy_meta.get("artifact_code_hash") or "") if strategy_meta else "",
            strategy_provenance=str(strategy_meta.get("provenance") or strategy_meta.get("source") or "") if strategy_meta else "",
            preset_name=preset_name,
            params_json=json.dumps(params, sort_keys=True),
            metrics_json=metrics_payload,
            status="passed" if passed else "failed",
            integrity_status=integrity_status,
            integrity_note=integrity_note,
        )
        sess.add(run)
        sess.flush()

        for _, row in trades.iterrows():
            sess.add(
                BacktestTrade(
                    run_id=run.id,
                    ts=row["time"],
                    symbol=symbol,
                    side=row["side"],
                    qty=float(row["qty"]),
                    price=float(row["price"]),
                    artifact_id=strategy_meta.get("artifact_id") if strategy_meta else None,
                    regime=row.get("regime"),
                    strategy_name=row.get("strategy_name", strategy_name),
                    strategy_version=row.get("strategy_version"),
                    strategy_code_hash=str(strategy_meta.get("artifact_code_hash") or "") if strategy_meta else "",
                    strategy_provenance=str(strategy_meta.get("provenance") or strategy_meta.get("source") or "") if strategy_meta else "",
                )
            )
        sess.commit()

    try:
        from trading_diary.service import record_backtest_insight as _rbi
        _rbi({
            "run_id":        run.id,
            "trades":        trades,
            "metrics":       metrics,
            "passed":        passed,
            "failures":      failures,
            "symbol":        symbol,
            "strategy_name": strategy_name,
        })
    except Exception:
        pass  # diary write must never break backtesting

    mark_artifact_backtest_result(strategy_meta.get("artifact_id") if strategy_meta else None, passed)

    return {
        "run_id": run.id,
        "trades": trades,
        "equity_curve": equity_curve,
        "metrics": metrics,
        "preset_name": preset_name,
        "params": params,
        "passed": passed,
        "failures": failures,
    }


def list_backtest_runs(limit: int = 100) -> pd.DataFrame:
    init_db()
    with SessionLocal() as sess:
        refresh_integrity_flags(sess)
        rows = (
            sess.query(BacktestRun)
            .order_by(BacktestRun.created_at.desc())
            .limit(limit)
            .all()
        )

    data = [
        {
            "id": row.id,
            "created_at": row.created_at,
            "symbol": row.symbol,
            "start_ts": row.start_ts,
            "end_ts": row.end_ts,
            "artifact_id": row.artifact_id,
            "strategy_name": row.strategy_name,
            "strategy_version": row.strategy_version,
            "strategy_code_hash": row.strategy_code_hash or "",
            "strategy_provenance": row.strategy_provenance or "",
            "preset_name": row.preset_name,
            "status": row.status,
            "integrity_status": row.integrity_status or "valid",
            "integrity_note": row.integrity_note,
            "params": parse_params_json(row.params_json),
            **parse_metrics_json(row.metrics_json),
        }
        for row in rows
    ]
    return pd.DataFrame(data)


def get_backtest_run(run_id: int) -> dict | None:
    init_db()
    with SessionLocal() as sess:
        refresh_integrity_flags(sess)
        row = sess.get(BacktestRun, run_id)

    if row is None:
        return None
    return {
        "id": row.id,
        "created_at": row.created_at,
        "symbol": row.symbol,
        "start_ts": row.start_ts,
        "end_ts": row.end_ts,
        "artifact_id": row.artifact_id,
        "strategy_name": row.strategy_name,
        "strategy_version": row.strategy_version,
        "strategy_code_hash": row.strategy_code_hash or "",
        "strategy_provenance": row.strategy_provenance or "",
        "preset_name": row.preset_name,
        "status": row.status,
        "integrity_status": row.integrity_status or "valid",
        "integrity_note": row.integrity_note,
        "params": parse_params_json(row.params_json),
        **parse_metrics_json(row.metrics_json),
    }


def save_backtest_preset(
    strategy_name: str,
    preset_name: str,
    params: dict | None = None,
) -> dict:
    """Create or update a named backtest preset for one strategy."""
    init_db()
    clean_name = normalise_preset_name(preset_name)
    if not clean_name:
        raise ValueError("Preset name is required")

    clean_params = parse_params_json(json.dumps(params or {}))
    now = datetime.now(tz=timezone.utc)

    with SessionLocal() as sess:
        preset = (
            sess.query(BacktestPreset)
            .filter(
                BacktestPreset.strategy_name == strategy_name,
                BacktestPreset.preset_name == clean_name,
            )
            .one_or_none()
        )
        if preset is None:
            preset = BacktestPreset(
                strategy_name=strategy_name,
                preset_name=clean_name,
                params_json=json.dumps(clean_params, sort_keys=True),
                created_at=now,
                updated_at=now,
            )
            sess.add(preset)
        else:
            preset.params_json = json.dumps(clean_params, sort_keys=True)
            preset.updated_at = now
        sess.commit()
        preset_id = preset.id

    return get_backtest_preset(int(preset_id)) or {
        "id": preset_id,
        "strategy_name": strategy_name,
        "preset_name": clean_name,
        "params": clean_params,
        "created_at": now,
        "updated_at": now,
    }


def list_backtest_presets(strategy_name: str | None = None) -> pd.DataFrame:
    """Return saved presets, optionally filtered to one strategy."""
    init_db()
    with SessionLocal() as sess:
        query = sess.query(BacktestPreset)
        if strategy_name:
            query = query.filter(BacktestPreset.strategy_name == strategy_name)
        rows = query.order_by(BacktestPreset.updated_at.desc(), BacktestPreset.id.desc()).all()

    return pd.DataFrame(
        [
            {
                "id": row.id,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "strategy_name": row.strategy_name,
                "preset_name": row.preset_name,
                "params": parse_params_json(row.params_json),
            }
            for row in rows
        ]
    )


def get_backtest_preset(preset_id: int) -> dict | None:
    """Return one persisted preset by id."""
    init_db()
    with SessionLocal() as sess:
        row = sess.get(BacktestPreset, preset_id)

    if row is None:
        return None
    return {
        "id": row.id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "strategy_name": row.strategy_name,
        "preset_name": row.preset_name,
        "params": parse_params_json(row.params_json),
    }


def get_backtest_trades(run_id: int) -> pd.DataFrame:
    init_db()
    with SessionLocal() as sess:
        rows = (
            sess.query(BacktestTrade)
            .filter(BacktestTrade.run_id == run_id)
            .order_by(BacktestTrade.ts)
            .all()
        )

    return pd.DataFrame(
        [
            {
                "ts": row.ts,
                "symbol": row.symbol,
                "side": row.side,
                "qty": row.qty,
                "price": row.price,
                "artifact_id": row.artifact_id,
                "regime": row.regime,
                "strategy_name": row.strategy_name,
                "strategy_version": row.strategy_version,
                "strategy_code_hash": row.strategy_code_hash or "",
                "strategy_provenance": row.strategy_provenance or "",
            }
            for row in rows
        ]
    )


def run_market_focus_study(
    strategy_name: str,
    params: dict | None = None,
    *,
    backtest_days: int | None = None,
    top_n: int | None = None,
    universe_size: int | None = None,
) -> dict:
    """Run a weekly market focus study and return the result dict."""
    kwargs = {}
    if backtest_days is not None:
        kwargs["backtest_days"] = backtest_days
    if top_n is not None:
        kwargs["top_n"] = top_n
    if universe_size is not None:
        kwargs["universe_size"] = universe_size
    return run_weekly_study(strategy_name, params, **kwargs)


def get_latest_market_focus() -> dict | None:
    """Return the latest completed market focus study header, or None."""
    return get_latest_study()


def get_market_focus_candidates(study_id: int) -> list[dict]:
    """Return ranked candidates for a market focus study."""
    return get_study_candidates(study_id)
