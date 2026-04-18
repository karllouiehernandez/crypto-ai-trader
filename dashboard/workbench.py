"""Pure helpers for the strategy workbench dashboard."""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
import json
import math
import os
from typing import Any

import pandas as pd

from config import STARTING_BALANCE_USD


def compute_trade_equity_curve(
    trades: pd.DataFrame,
    starting_balance: float = STARTING_BALANCE_USD,
) -> pd.DataFrame:
    """Return a per-trade equity curve from a trade log."""
    if trades.empty:
        return pd.DataFrame({"step": [0], "equity": [float(starting_balance)]})

    equity = float(starting_balance)
    rows: list[dict[str, float]] = [{"step": 0, "equity": equity}]
    for step, (_, row) in enumerate(trades.iterrows(), start=1):
        notionals = float(row["qty"]) * float(row["price"])
        if row["side"] == "BUY":
            equity -= notionals
        else:
            equity += notionals
        rows.append({"step": step, "equity": equity})
    return pd.DataFrame(rows)


def to_utc_epoch_seconds(value: Any) -> int:
    """Return a timestamp-like value as whole UTC epoch seconds."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return int(ts.timestamp())


def build_trading_chart_payload(
    candles: pd.DataFrame,
    trades: pd.DataFrame | None = None,
    *,
    symbol: str = "",
    timeframe: str = "",
    strategy_name: str = "",
    context_label: str = "",
    show_fast_emas: bool = False,
    show_ema_200: bool = False,
    show_bbands: bool = False,
    show_rsi: bool = False,
    show_macd: bool = False,
) -> dict[str, Any]:
    """Serialize candles and trade markers for the responsive chart component."""
    frame = candles.copy() if isinstance(candles, pd.DataFrame) else pd.DataFrame()
    if frame.empty:
        return {
            "candles": [],
            "volume": [],
            "markers": [],
            "meta": {
                "symbol": symbol,
                "timeframe": timeframe,
                "strategy_name": strategy_name,
                "context_label": context_label,
            },
        }

    base_columns = ["open_time", "open", "high", "low", "close", "volume"]
    study_columns = ["ema_9", "ema_21", "ema_55", "ema_200", "bb_hi", "bb_lo", "rsi_14", "macd", "macd_s"]
    frame = frame[[col for col in base_columns + study_columns if col in frame.columns]].copy()
    frame["open_time"] = pd.to_datetime(frame["open_time"], errors="coerce")
    frame = frame.dropna(subset=["open_time", "open", "high", "low", "close", "volume"])
    if frame.empty:
        return {
            "candles": [],
            "volume": [],
            "markers": [],
            "meta": {
                "symbol": symbol,
                "timeframe": timeframe,
                "strategy_name": strategy_name,
                "context_label": context_label,
            },
        }

    frame = frame.sort_values("open_time").reset_index(drop=True)
    chart_times = [to_utc_epoch_seconds(value) for value in frame["open_time"]]

    candle_payload = [
        {
            "time": chart_times[idx],
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        }
        for idx, (_, row) in enumerate(frame.iterrows())
    ]

    volume_payload = [
        {
            "time": chart_times[idx],
            "value": float(row["volume"]),
            "color": "#26a69a" if float(row["close"]) >= float(row["open"]) else "#ef5350",
        }
        for idx, (_, row) in enumerate(frame.iterrows())
    ]

    markers = _build_chart_markers(
        chart_times,
        trades if isinstance(trades, pd.DataFrame) else pd.DataFrame(),
    )
    overlays = {
        "price": _build_price_overlays(
            frame,
            show_fast_emas=show_fast_emas,
            show_ema_200=show_ema_200,
            show_bbands=show_bbands,
        ),
        "rsi": _build_rsi_overlay(frame) if show_rsi else {"series": [], "bands": []},
        "macd": _build_macd_overlay(frame) if show_macd else {"series": [], "histogram": []},
    }
    return {
        "candles": candle_payload,
        "volume": volume_payload,
        "markers": markers,
        "overlays": overlays,
        "meta": {
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy_name": strategy_name,
            "context_label": context_label,
        },
    }


def _build_chart_markers(chart_times: list[int], trades: pd.DataFrame) -> list[dict[str, Any]]:
    """Map and aggregate trade timestamps onto the visible candle buckets used by the chart."""
    if not chart_times or trades.empty or "ts" not in trades.columns or "side" not in trades.columns:
        return []

    interval_seconds = 0
    if len(chart_times) >= 2:
        deltas = [later - earlier for earlier, later in zip(chart_times, chart_times[1:]) if later > earlier]
        if deltas:
            interval_seconds = int(pd.Series(deltas, dtype="int64").median())

    grouped: dict[tuple[int, str], dict[str, Any]] = {}
    for _, row in trades.sort_values("ts").iterrows():
        trade_ts = pd.to_datetime(row.get("ts"), errors="coerce")
        if pd.isna(trade_ts):
            continue

        trade_time = to_utc_epoch_seconds(trade_ts)
        if trade_time < chart_times[0]:
            continue
        if interval_seconds > 0 and trade_time >= chart_times[-1] + interval_seconds:
            continue

        idx = bisect_right(chart_times, trade_time) - 1
        if idx < 0 or idx >= len(chart_times):
            continue

        side = str(row.get("side", "")).upper().strip()
        if side not in {"BUY", "SELL"}:
            continue

        key = (chart_times[idx], side)
        if key not in grouped:
            grouped[key] = {
                "time": chart_times[idx],
                "position": "belowBar" if side == "BUY" else "aboveBar",
                "shape": "arrowUp" if side == "BUY" else "arrowDown",
                "color": "#00e676" if side == "BUY" else "#ff1744",
                "count": 0,
                "run_modes": defaultdict(int),
            }

        grouped[key]["count"] += 1
        run_mode = str(row.get("run_mode", "")).strip().lower()
        if run_mode:
            grouped[key]["run_modes"][run_mode] += 1

    markers: list[dict[str, Any]] = []
    for (_, side), marker in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        count = int(marker.pop("count"))
        run_modes = dict(marker.pop("run_modes"))
        text = ""
        if count > 1:
            if len(run_modes) > 1:
                parts = [f"{mode[0].upper()}{qty}" for mode, qty in sorted(run_modes.items())]
                text = "/".join(parts)
            else:
                text = f"x{count}"
        marker["text"] = text
        markers.append(marker)

    return markers


def _build_price_overlays(
    frame: pd.DataFrame,
    *,
    show_fast_emas: bool,
    show_ema_200: bool,
    show_bbands: bool,
) -> list[dict[str, Any]]:
    """Serialize price-pane study overlays from an enriched candle frame."""
    overlays: list[dict[str, Any]] = []

    if show_fast_emas:
        overlays.extend(
            [
                _build_line_overlay(frame, "ema_9", label="EMA 9", color="#ffb300", line_width=2),
                _build_line_overlay(frame, "ema_21", label="EMA 21", color="#42a5f5", line_width=2),
                _build_line_overlay(frame, "ema_55", label="EMA 55", color="#26a69a", line_width=2),
            ]
        )
    if show_ema_200:
        overlays.append(_build_line_overlay(frame, "ema_200", label="EMA 200", color="#e0e0e0", line_width=2))
    if show_bbands:
        overlays.extend(
            [
                _build_line_overlay(
                    frame,
                    "bb_hi",
                    label="BB High",
                    color="#7e8aa0",
                    line_width=1,
                    line_style="dashed",
                ),
                _build_line_overlay(
                    frame,
                    "bb_lo",
                    label="BB Low",
                    color="#7e8aa0",
                    line_width=1,
                    line_style="dashed",
                ),
            ]
        )

    return [overlay for overlay in overlays if overlay["data"]]


def _build_rsi_overlay(frame: pd.DataFrame) -> dict[str, Any]:
    """Serialize the RSI study pane."""
    series = _build_line_overlay(frame, "rsi_14", label="RSI 14", color="#ffca28", line_width=2)
    if not series["data"]:
        return {"series": [], "bands": []}

    times = [point["time"] for point in series["data"]]
    bands = [
        _build_constant_line(times, 70.0, label="Overbought", color="#ef5350", line_style="dashed"),
        _build_constant_line(times, 50.0, label="Midline", color="#5c6b7a", line_style="dotted"),
        _build_constant_line(times, 30.0, label="Oversold", color="#26a69a", line_style="dashed"),
    ]
    return {"series": [series], "bands": bands}


def _build_macd_overlay(frame: pd.DataFrame) -> dict[str, Any]:
    """Serialize the MACD study pane."""
    macd_series = _build_line_overlay(frame, "macd", label="MACD", color="#29b6f6", line_width=2)
    signal_series = _build_line_overlay(frame, "macd_s", label="Signal", color="#ffa726", line_width=2)

    histogram: list[dict[str, Any]] = []
    required = {"open_time", "macd", "macd_s"}
    if required.issubset(frame.columns):
        study = frame[list(required)].copy()
        study["open_time"] = pd.to_datetime(study["open_time"], errors="coerce")
        study["macd"] = pd.to_numeric(study["macd"], errors="coerce")
        study["macd_s"] = pd.to_numeric(study["macd_s"], errors="coerce")
        study = study.dropna(subset=["open_time", "macd", "macd_s"]).sort_values("open_time")
        for _, row in study.iterrows():
            hist_value = float(row["macd"]) - float(row["macd_s"])
            histogram.append(
                {
                    "time": to_utc_epoch_seconds(row["open_time"]),
                    "value": hist_value,
                    "color": "#26a69a" if hist_value >= 0 else "#ef5350",
                }
            )

    return {
        "series": [series for series in [macd_series, signal_series] if series["data"]],
        "histogram": histogram,
    }


def _build_line_overlay(
    frame: pd.DataFrame,
    column: str,
    *,
    label: str,
    color: str,
    line_width: int = 2,
    line_style: str = "solid",
) -> dict[str, Any]:
    """Serialize one line study from an enriched candle frame."""
    if "open_time" not in frame.columns or column not in frame.columns:
        return {"label": label, "color": color, "lineWidth": line_width, "lineStyle": line_style, "data": []}

    study = frame[["open_time", column]].copy()
    study["open_time"] = pd.to_datetime(study["open_time"], errors="coerce")
    study[column] = pd.to_numeric(study[column], errors="coerce")
    study = study.dropna(subset=["open_time", column]).sort_values("open_time")

    return {
        "label": label,
        "color": color,
        "lineWidth": line_width,
        "lineStyle": line_style,
        "data": [
            {
                "time": to_utc_epoch_seconds(row["open_time"]),
                "value": float(row[column]),
            }
            for _, row in study.iterrows()
        ],
    }


def _build_constant_line(
    times: list[int],
    value: float,
    *,
    label: str,
    color: str,
    line_style: str,
) -> dict[str, Any]:
    """Serialize a horizontal guide line aligned to the study pane times."""
    return {
        "label": label,
        "color": color,
        "lineWidth": 1,
        "lineStyle": line_style,
        "data": [{"time": ts, "value": value} for ts in times],
    }


def compute_drawdown_curve(equity_curve: pd.DataFrame) -> pd.DataFrame:
    """Return drawdown percentages from an equity curve."""
    if equity_curve.empty or "equity" not in equity_curve.columns:
        return pd.DataFrame(columns=["step", "drawdown"])

    curve = equity_curve.copy()
    curve["peak"] = curve["equity"].cummax()
    curve["drawdown"] = (curve["equity"] - curve["peak"]) / curve["peak"]
    return curve[["step", "drawdown"]]


def _parse_json_dict(raw: str | None) -> dict[str, Any]:
    """Parse a persisted JSON object safely."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_metrics_json(raw: str | None) -> dict[str, Any]:
    """Parse persisted metrics JSON safely."""
    return _parse_json_dict(raw)


def parse_params_json(raw: str | None) -> dict[str, Any]:
    """Parse persisted params JSON safely."""
    return _parse_json_dict(raw)


def normalise_preset_name(preset_name: Any) -> str:
    """Return a trimmed preset name or an empty string."""
    if preset_name is None:
        return ""
    return str(preset_name).strip()


def normalise_params(params: dict[str, Any] | None) -> dict[str, Any]:
    """Return a stable params dict for persistence and comparison."""
    if not isinstance(params, dict):
        return {}

    normalised: dict[str, Any] = {}
    for key in sorted(params):
        value = params[key]
        if isinstance(value, float) and math.isfinite(value) and value.is_integer():
            normalised[str(key)] = int(value)
        else:
            normalised[str(key)] = value
    return normalised


def format_params_summary(params: dict[str, Any] | None, max_items: int = 3) -> str:
    """Return a compact human-readable summary for a scenario payload."""
    payload = normalise_params(params)
    if not payload:
        return "Default"

    parts = [f"{key}={payload[key]}" for key in payload]
    if len(parts) <= max_items:
        return ", ".join(parts)
    visible = ", ".join(parts[:max_items])
    return f"{visible}, +{len(parts) - max_items} more"


def format_scenario_label(
    params: dict[str, Any] | None,
    preset_name: Any = None,
    max_items: int = 3,
) -> str:
    """Prefer a named preset label, otherwise fall back to a params summary."""
    clean_name = normalise_preset_name(preset_name)
    if clean_name:
        return clean_name
    return format_params_summary(params, max_items=max_items)


def scenario_key(params: dict[str, Any] | None) -> str:
    """Return a stable key for grouping runs by parameter scenario."""
    return json.dumps(normalise_params(params), sort_keys=True)


def scenario_identity(params: dict[str, Any] | None, preset_name: Any = None) -> str:
    """Return a stable grouping key that keeps named presets distinct from custom runs."""
    clean_name = normalise_preset_name(preset_name)
    if clean_name:
        return f"preset::{clean_name.lower()}"
    return f"params::{scenario_key(params)}"


def find_matching_preset_name(params: dict[str, Any] | None, presets: pd.DataFrame) -> str:
    """Return the preset name whose params exactly match the current payload."""
    if presets.empty or "params" not in presets.columns or "preset_name" not in presets.columns:
        return ""

    target = normalise_params(params)
    for _, row in presets.iterrows():
        if normalise_params(row.get("params")) == target:
            return normalise_preset_name(row.get("preset_name"))
    return ""


def build_backtest_preset_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a dashboard-ready preset table sorted by recency."""
    if frame.empty:
        return pd.DataFrame()

    presets = frame.copy()
    if "created_at" in presets.columns:
        presets["created_at"] = pd.to_datetime(presets["created_at"], errors="coerce")
    if "updated_at" in presets.columns:
        presets["updated_at"] = pd.to_datetime(presets["updated_at"], errors="coerce")
    if "params" not in presets.columns:
        presets["params"] = [{} for _ in range(len(presets))]
    presets["params"] = presets["params"].apply(
        lambda value: normalise_params(value) if isinstance(value, dict) else {}
    )
    presets["scenario_label"] = presets.apply(
        lambda row: format_scenario_label(row.get("params"), row.get("preset_name")),
        axis=1,
    )
    presets["params_summary"] = presets["params"].apply(format_params_summary)
    return presets.sort_values(by=["updated_at", "created_at"], ascending=[False, False], na_position="last").reset_index(drop=True)


def format_strategy_origin(meta: dict[str, Any] | None) -> str:
    """Return a user-facing origin label for strategy metadata."""
    if not meta:
        return "Unknown"

    provenance = str(meta.get("provenance") or meta.get("source") or "plugin").lower()
    if provenance == "generated":
        return "Generated Plugin"
    if provenance == "builtin":
        return "Built-in"
    return "Plugin"


def strategy_workflow_status(
    meta: dict[str, Any] | None,
    runs: pd.DataFrame | None = None,
    active_strategy_name: str = "",
) -> dict[str, Any]:
    """Return workflow stage and next-step guidance for a strategy."""
    if not meta:
        return {
            "stage": "Unknown",
            "next_step": "Inspect the strategy metadata before backtesting or activation.",
            "run_count": 0,
            "passed_runs": 0,
            "failed_runs": 0,
        }

    runs = runs if runs is not None else pd.DataFrame()
    strategy_name = str(meta.get("name", ""))
    strategy_runs = runs[runs["strategy_name"] == strategy_name].copy() if not runs.empty and "strategy_name" in runs.columns else pd.DataFrame()
    statuses = strategy_runs["status"].fillna("").astype(str).str.lower() if not strategy_runs.empty and "status" in strategy_runs.columns else pd.Series(dtype=str)
    passed_runs = int((statuses == "passed").sum())
    failed_runs = int((statuses == "failed").sum())
    run_count = int(len(strategy_runs))

    provenance = str(meta.get("provenance") or meta.get("source") or "plugin").lower()
    is_active = bool(active_strategy_name and strategy_name == active_strategy_name)

    if provenance == "builtin":
        stage = "Built-in"
        next_step = "Backtest it against your current market window, then keep it active or compare it with plugin candidates."
    elif provenance == "generated":
        if passed_runs > 0:
            stage = "Evaluated Draft"
            next_step = "Review the generated file, refine it if needed, then promote it into paper trading only after saving it as a reviewed plugin."
        elif run_count > 0:
            stage = "Draft Under Review"
            next_step = "Inspect the saved backtests, revise the draft if needed, and rerun until one passes the acceptance gate."
        else:
            stage = "Draft"
            next_step = "Review the generated file, then run a backtest before considering paper trading."
    else:
        if passed_runs > 0:
            stage = "Reviewed Candidate"
            next_step = "This plugin has a passing backtest history. It is a candidate for paper trading if the strategy logic is reviewed."
        elif run_count > 0:
            stage = "Candidate"
            next_step = "This plugin exists but has not passed a backtest yet. Iterate on the file and keep evaluating it in the workbench."
        else:
            stage = "Unreviewed Plugin"
            next_step = "Run a backtest to establish a baseline before making it active for paper or live trading."

    if is_active and provenance != "builtin":
        next_step = "It is currently the active strategy. Restart paper/live after any file changes and keep monitoring runtime behavior."

    return {
        "stage": stage,
        "next_step": next_step,
        "run_count": run_count,
        "passed_runs": passed_runs,
        "failed_runs": failed_runs,
    }


def build_strategy_catalog_frame(
    catalog: list[dict[str, Any]],
    runs: pd.DataFrame | None = None,
    active_strategy_name: str = "",
) -> pd.DataFrame:
    """Return a dashboard-ready strategy catalog table."""
    rows = [
        {
            "display_name": item.get("display_name", item.get("name", "")),
            "name": item.get("name", ""),
            "origin": format_strategy_origin(item),
            "workflow_stage": strategy_workflow_status(item, runs, active_strategy_name)["stage"],
            "version": item.get("version", ""),
            "regimes": ", ".join(item.get("regimes", [])) or "All",
            "file": item.get("file_name", ""),
            "status": item.get("load_status", ""),
            "modified_at": item.get("modified_at", ""),
        }
        for item in catalog
    ]
    return pd.DataFrame(rows)


def filter_backtest_runs(
    frame: pd.DataFrame,
    strategy_name: str,
    show_all: bool = False,
) -> pd.DataFrame:
    """Filter persisted backtest runs to one strategy unless the user wants all history."""
    if show_all or frame.empty or "strategy_name" not in frame.columns:
        return frame.copy()
    return frame[frame["strategy_name"] == strategy_name].copy()


def _safe_ratio(numerator: float, denominator: float) -> float:
    """Return a stable ratio for dashboard summaries."""
    if denominator <= 0:
        return 0.0
    return float(numerator / denominator)


def build_strategy_comparison_frame(
    runs: pd.DataFrame,
    catalog: list[dict[str, Any]] | None = None,
    active_strategy_name: str = "",
) -> pd.DataFrame:
    """Summarise saved backtests into one comparison row per strategy scenario."""
    catalog = catalog or []
    catalog_lookup = {str(item.get("name", "")): item for item in catalog if item.get("name")}

    if runs.empty:
        rows = []
        for name, meta in catalog_lookup.items():
            workflow_status = strategy_workflow_status(meta, runs, active_strategy_name)
            default_params = normalise_params(meta.get("default_params"))
            rows.append(
                {
                    "display_name": meta.get("display_name", name),
                    "strategy_name": name,
                    "scenario_key": scenario_identity(default_params),
                    "scenario_label": format_scenario_label(default_params),
                    "scenario_params": default_params,
                    "preset_name": "",
                    "origin": format_strategy_origin(meta),
                    "workflow_stage": workflow_status["stage"],
                    "is_active": name == active_strategy_name,
                    "run_count": 0,
                    "passed_runs": 0,
                    "failed_runs": 0,
                    "pass_rate": 0.0,
                    "best_sharpe": None,
                    "best_profit_factor": None,
                    "lowest_max_drawdown": None,
                    "latest_status": "Not Run",
                    "latest_symbol": "—",
                    "latest_run_id": None,
                    "latest_run_at": None,
                    "best_run_id": None,
                }
            )
        return pd.DataFrame(rows)

    frame = runs.copy()
    if "created_at" in frame.columns:
        frame["created_at"] = pd.to_datetime(frame["created_at"], errors="coerce")
    for column in ["sharpe", "profit_factor", "max_drawdown", "n_trades"]:
        if column not in frame.columns:
            frame[column] = pd.NA
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "params" not in frame.columns:
        frame["params"] = [{} for _ in range(len(frame))]
    frame["params"] = frame["params"].apply(
        lambda value: normalise_params(value) if isinstance(value, dict) else {}
    )
    if "preset_name" not in frame.columns:
        frame["preset_name"] = ""
    frame["preset_name"] = frame["preset_name"].apply(normalise_preset_name)
    frame["scenario_key"] = frame.apply(
        lambda row: scenario_identity(row.get("params"), row.get("preset_name")),
        axis=1,
    )
    frame["scenario_label"] = frame.apply(
        lambda row: format_scenario_label(row.get("params"), row.get("preset_name")),
        axis=1,
    )
    if "status" in frame.columns:
        frame["status"] = frame["status"].fillna("").astype(str).str.lower()
    else:
        frame["status"] = ""

    rows: list[dict[str, Any]] = []
    for (strategy_name, run_scenario_key), strategy_runs in frame.groupby(["strategy_name", "scenario_key"], dropna=False):
        strategy_name = str(strategy_name or "")
        strategy_runs = strategy_runs.sort_values("created_at", ascending=False, na_position="last").copy()
        meta = catalog_lookup.get(strategy_name, {"name": strategy_name, "display_name": strategy_name})
        workflow_status = strategy_workflow_status(meta, frame, active_strategy_name)

        passed_runs = strategy_runs[strategy_runs["status"] == "passed"] if "status" in strategy_runs.columns else pd.DataFrame()
        best_source = passed_runs if not passed_runs.empty else strategy_runs
        best_source = best_source.sort_values(
            by=["sharpe", "profit_factor", "max_drawdown", "n_trades", "created_at"],
            ascending=[False, False, True, False, False],
            na_position="last",
        )
        best_run = best_source.iloc[0].to_dict() if not best_source.empty else {}
        latest_run = strategy_runs.iloc[0].to_dict() if not strategy_runs.empty else {}

        passed_count = int((strategy_runs["status"] == "passed").sum()) if "status" in strategy_runs.columns else 0
        failed_count = int((strategy_runs["status"] == "failed").sum()) if "status" in strategy_runs.columns else 0
        run_count = int(len(strategy_runs))
        scenario_params = normalise_params(strategy_runs.iloc[0].get("params", {})) if not strategy_runs.empty else {}
        preset_name = normalise_preset_name(strategy_runs.iloc[0].get("preset_name")) if not strategy_runs.empty else ""

        rows.append(
            {
                "display_name": meta.get("display_name", strategy_name),
                "strategy_name": strategy_name,
                "scenario_key": run_scenario_key,
                "scenario_label": format_scenario_label(scenario_params, preset_name),
                "scenario_params": scenario_params,
                "preset_name": preset_name,
                "origin": format_strategy_origin(meta),
                "workflow_stage": workflow_status["stage"],
                "is_active": strategy_name == active_strategy_name,
                "run_count": run_count,
                "passed_runs": passed_count,
                "failed_runs": failed_count,
                "pass_rate": _safe_ratio(passed_count, run_count),
                "best_sharpe": best_run.get("sharpe"),
                "best_profit_factor": best_run.get("profit_factor"),
                "lowest_max_drawdown": best_run.get("max_drawdown"),
                "latest_status": str(latest_run.get("status", "not run")).replace("_", " ").title(),
                "latest_symbol": latest_run.get("symbol", "—"),
                "latest_run_id": latest_run.get("id"),
                "latest_run_at": latest_run.get("created_at"),
                "best_run_id": best_run.get("id"),
            }
        )

    seen_pairs = {(str(rows_item["strategy_name"]), str(rows_item["scenario_key"])) for rows_item in rows}
    for name, meta in catalog_lookup.items():
        default_params = normalise_params(meta.get("default_params"))
        default_scenario_key = scenario_identity(default_params)
        if (name, default_scenario_key) in seen_pairs:
            continue
        workflow_status = strategy_workflow_status(meta, frame, active_strategy_name)
        rows.append(
            {
                "display_name": meta.get("display_name", name),
                "strategy_name": name,
                "scenario_key": default_scenario_key,
                "scenario_label": format_scenario_label(default_params),
                "scenario_params": default_params,
                "preset_name": "",
                "origin": format_strategy_origin(meta),
                "workflow_stage": workflow_status["stage"],
                "is_active": name == active_strategy_name,
                "run_count": 0,
                "passed_runs": 0,
                "failed_runs": 0,
                "pass_rate": 0.0,
                "best_sharpe": None,
                "best_profit_factor": None,
                "lowest_max_drawdown": None,
                "latest_status": "Not Run",
                "latest_symbol": "—",
                "latest_run_id": None,
                "latest_run_at": None,
                "best_run_id": None,
            }
        )

    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary

    summary = summary.sort_values(
        by=["passed_runs", "pass_rate", "best_sharpe", "best_profit_factor", "lowest_max_drawdown", "latest_run_at"],
        ascending=[False, False, False, False, True, False],
        na_position="last",
    ).reset_index(drop=True)
    summary["rank"] = range(1, len(summary) + 1)
    return summary


def build_backtest_run_leaderboard(frame: pd.DataFrame) -> pd.DataFrame:
    """Return saved runs sorted for quick evaluation scanning."""
    if frame.empty:
        return pd.DataFrame()

    leaderboard = frame.copy()
    if "created_at" in leaderboard.columns:
        leaderboard["created_at"] = pd.to_datetime(leaderboard["created_at"], errors="coerce")
    for column in ["sharpe", "profit_factor", "max_drawdown", "n_trades"]:
        if column not in leaderboard.columns:
            leaderboard[column] = pd.NA
        leaderboard[column] = pd.to_numeric(leaderboard[column], errors="coerce")
    if "params" not in leaderboard.columns:
        leaderboard["params"] = [{} for _ in range(len(leaderboard))]
    leaderboard["params"] = leaderboard["params"].apply(
        lambda value: normalise_params(value) if isinstance(value, dict) else {}
    )
    if "preset_name" not in leaderboard.columns:
        leaderboard["preset_name"] = ""
    leaderboard["preset_name"] = leaderboard["preset_name"].apply(normalise_preset_name)
    leaderboard["scenario_label"] = leaderboard.apply(
        lambda row: format_scenario_label(row.get("params"), row.get("preset_name")),
        axis=1,
    )
    if "status" in leaderboard.columns:
        leaderboard["status"] = leaderboard["status"].fillna("").astype(str).str.lower()
        leaderboard["gate_passed"] = leaderboard["status"] == "passed"
    else:
        leaderboard["gate_passed"] = False

    if "failures" in leaderboard.columns:
        leaderboard["failure_summary"] = leaderboard["failures"].apply(
            lambda value: "; ".join(value) if isinstance(value, list) else (value or "")
        )
    else:
        leaderboard["failure_summary"] = ""

    leaderboard = leaderboard.sort_values(
        by=["gate_passed", "sharpe", "profit_factor", "max_drawdown", "n_trades", "created_at"],
        ascending=[False, False, False, True, False, False],
        na_position="last",
    ).reset_index(drop=True)
    leaderboard["rank"] = range(1, len(leaderboard) + 1)
    leaderboard["status_label"] = leaderboard["status"].replace({"passed": "Passed", "failed": "Failed"}).fillna("Unknown")
    return leaderboard


def filter_runtime_data(
    frame: pd.DataFrame,
    strategy_name: str,
    run_mode: str,
) -> pd.DataFrame:
    """Filter runtime trade or portfolio data by strategy and run mode."""
    filtered = frame.copy()
    if not filtered.empty and "strategy_name" in filtered.columns:
        filtered = filtered[filtered["strategy_name"].fillna(strategy_name) == strategy_name]
    if run_mode != "All" and not filtered.empty and "run_mode" in filtered.columns:
        filtered = filtered[filtered["run_mode"].fillna("paper") == run_mode]
    return filtered


def list_runtime_strategies(
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    active_strategy_name: str,
) -> list[str]:
    """Return strategy names seen in runtime data, keeping the active strategy first."""
    seen: set[str] = set()
    for frame in (trades, equity):
        if frame.empty or "strategy_name" not in frame.columns:
            continue
        for value in frame["strategy_name"].dropna().tolist():
            name = str(value).strip()
            if name:
                seen.add(name)

    if active_strategy_name:
        seen.add(active_strategy_name)

    if not seen:
        return [active_strategy_name] if active_strategy_name else []

    ordered = sorted(seen)
    if active_strategy_name in ordered:
        ordered.remove(active_strategy_name)
        ordered.insert(0, active_strategy_name)
    return ordered


def runtime_mode_table(
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    starting_balance: float = STARTING_BALANCE_USD,
) -> pd.DataFrame:
    """Return one summary row per runtime mode for comparison in the dashboard."""
    modes: set[str] = set()
    for frame in (trades, equity):
        if frame.empty or "run_mode" not in frame.columns:
            continue
        modes.update(str(value) for value in frame["run_mode"].dropna().tolist() if str(value))

    if not modes:
        return pd.DataFrame(columns=[
            "run_mode",
            "equity",
            "balance",
            "unreal_pnl",
            "realized_pnl",
            "trade_count",
            "last_trade_side",
            "last_trade_regime",
            "last_trade_ts",
            "last_snapshot_ts",
            "strategy_version",
        ])

    rows: list[dict[str, Any]] = []
    for mode in sorted(modes):
        mode_trades = trades[trades["run_mode"].fillna("paper") == mode].copy() if not trades.empty and "run_mode" in trades.columns else pd.DataFrame()
        mode_equity = equity[equity["run_mode"].fillna("paper") == mode].copy() if not equity.empty and "run_mode" in equity.columns else pd.DataFrame()
        summary = runtime_summary(mode_trades, mode_equity, starting_balance=starting_balance)
        latest_snapshot = mode_equity.iloc[-1].to_dict() if not mode_equity.empty else {}

        strategy_version = ""
        if latest_snapshot.get("strategy_version"):
            strategy_version = str(latest_snapshot["strategy_version"])
        elif not mode_trades.empty and "strategy_version" in mode_trades.columns:
            strategy_values = mode_trades["strategy_version"].dropna()
            if not strategy_values.empty:
                strategy_version = str(strategy_values.iloc[-1])

        rows.append(
            {
                "run_mode": mode,
                "equity": summary["equity"],
                "balance": summary["balance"],
                "unreal_pnl": summary["unreal_pnl"],
                "realized_pnl": float(mode_trades["pnl"].fillna(0).sum()) if not mode_trades.empty and "pnl" in mode_trades.columns else 0.0,
                "trade_count": summary["trade_count"],
                "last_trade_side": summary["last_trade_side"],
                "last_trade_regime": summary["last_trade_regime"],
                "last_trade_ts": summary["last_trade_ts"],
                "last_snapshot_ts": latest_snapshot.get("ts"),
                "strategy_version": strategy_version or "—",
            }
        )
    return pd.DataFrame(rows)


def compute_cumulative_trade_pnl(trades: pd.DataFrame) -> pd.DataFrame:
    """Return cumulative realised P&L grouped by runtime mode."""
    if trades.empty or "pnl" not in trades.columns or "ts" not in trades.columns:
        return pd.DataFrame(columns=["ts", "run_mode", "cumulative_pnl"])

    curve = trades.copy()
    curve["run_mode"] = curve["run_mode"].fillna("paper") if "run_mode" in curve.columns else "paper"
    curve["pnl"] = curve["pnl"].fillna(0.0)
    curve = curve.sort_values(["run_mode", "ts"]).reset_index(drop=True)
    curve["cumulative_pnl"] = curve.groupby("run_mode")["pnl"].cumsum()
    return curve[["ts", "run_mode", "cumulative_pnl"]]


def runtime_summary(
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    starting_balance: float = STARTING_BALANCE_USD,
) -> dict[str, Any]:
    """Return headline runtime stats for the dashboard monitor."""
    latest_equity = float(equity["equity"].iloc[-1]) if not equity.empty and "equity" in equity.columns else float(starting_balance)
    latest_balance = float(equity["balance"].iloc[-1]) if not equity.empty and "balance" in equity.columns else latest_equity
    latest_unreal = float(equity["unreal_pnl"].iloc[-1]) if not equity.empty and "unreal_pnl" in equity.columns else 0.0
    last_trade = trades.iloc[-1].to_dict() if not trades.empty else {}
    return {
        "equity": latest_equity,
        "balance": latest_balance,
        "unreal_pnl": latest_unreal,
        "realized_pnl": float(trades["pnl"].fillna(0).sum()) if not trades.empty and "pnl" in trades.columns else 0.0,
        "trade_count": int(len(trades)),
        "last_trade_side": last_trade.get("side", "—"),
        "last_trade_price": float(last_trade["price"]) if "price" in last_trade and pd.notna(last_trade["price"]) else None,
        "last_trade_regime": last_trade.get("regime", "—"),
        "last_trade_ts": last_trade.get("ts"),
        "last_snapshot_ts": equity["ts"].iloc[-1] if not equity.empty and "ts" in equity.columns else None,
    }


def build_focus_candidate_frame(candidates: list[dict]) -> pd.DataFrame:
    """Return a dashboard-ready table from market focus candidates."""
    if not candidates:
        return pd.DataFrame()

    rows = []
    for c in candidates:
        sharpe = c.get("sharpe")
        pf = c.get("profit_factor")
        dd = c.get("max_drawdown")
        rows.append(
            {
                "rank": c.get("rank"),
                "symbol": c.get("symbol"),
                "volume_rank": c.get("volume_rank"),
                "score": round(float(c.get("score") or 0), 4),
                "sharpe": round(float(sharpe), 3) if sharpe is not None else None,
                "profit_factor": round(float(pf), 3) if pf is not None else None,
                "max_drawdown": round(float(dd), 4) if dd is not None else None,
                "n_trades": c.get("n_trades"),
                "status": c.get("status", ""),
            }
        )
    return pd.DataFrame(rows)


def compute_win_loss_stats(trades: pd.DataFrame) -> dict[str, float | int]:
    """Pair sequential BUY->SELL rows and return basic win/loss stats."""
    empty_stats: dict[str, float | int] = {
        "win_count": 0,
        "loss_count": 0,
        "win_rate": 0.0,
        "avg_win_pct": 0.0,
        "avg_loss_pct": 0.0,
        "total_pairs": 0,
    }
    if trades.empty or "side" not in trades.columns or "price" not in trades.columns:
        return empty_stats

    frame = trades.copy()
    frame["side"] = frame["side"].astype(str).str.upper()
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame = frame.dropna(subset=["price"]).reset_index(drop=True)
    if len(frame) < 2:
        return empty_stats

    pair_returns: list[float] = []
    idx = 0
    while idx < len(frame) - 1:
        buy_row = frame.iloc[idx]
        sell_row = frame.iloc[idx + 1]
        if buy_row["side"] == "BUY" and sell_row["side"] == "SELL" and float(buy_row["price"]) > 0:
            buy_price = float(buy_row["price"])
            sell_price = float(sell_row["price"])
            pair_returns.append((sell_price - buy_price) / buy_price)
            idx += 2
            continue
        idx += 1

    if not pair_returns:
        return empty_stats

    wins = [value for value in pair_returns if value > 0]
    losses = [value for value in pair_returns if value <= 0]
    total_pairs = len(pair_returns)
    win_count = len(wins)
    loss_count = len(losses)
    return {
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": win_count / total_pairs if total_pairs else 0.0,
        "avg_win_pct": sum(wins) / len(wins) if wins else 0.0,
        "avg_loss_pct": sum(losses) / len(losses) if losses else 0.0,
        "total_pairs": total_pairs,
    }


def build_trader_summary(
    run: dict,
    equity_curve: pd.DataFrame,
    starting_balance: float,
) -> dict[str, Any]:
    """Return trader-facing backtest labels and headline metrics."""
    ending_equity = (
        float(equity_curve["equity"].iloc[-1])
        if not equity_curve.empty and "equity" in equity_curve.columns
        else float(starting_balance)
    )
    gain_pct = ((ending_equity - float(starting_balance)) / float(starting_balance) * 100.0) if starting_balance else 0.0

    sharpe = float(run.get("sharpe") or 0.0)
    if sharpe > 2:
        sharpe_label = "Excellent"
    elif sharpe >= 1:
        sharpe_label = "Good"
    elif sharpe >= 0.5:
        sharpe_label = "Marginal"
    else:
        sharpe_label = "Poor"

    drawdown_raw = float(run.get("max_drawdown") or 0.0)
    drawdown_pct = drawdown_raw * 100.0
    if drawdown_pct < 5:
        risk_label = "Low Risk"
    elif drawdown_pct <= 15:
        risk_label = "Moderate Risk"
    else:
        risk_label = "High Risk"

    failures_raw = run.get("failures", [])
    gate_failures: list[str] = []
    if isinstance(failures_raw, str):
        try:
            parsed_failures = json.loads(failures_raw)
        except json.JSONDecodeError:
            parsed_failures = []
        if isinstance(parsed_failures, list):
            gate_failures = [str(item) for item in parsed_failures]
    elif isinstance(failures_raw, list):
        gate_failures = [str(item) for item in failures_raw]

    return {
        "gain_pct": gain_pct,
        "profitable": gain_pct > 0,
        "sharpe_label": sharpe_label,
        "drawdown_pct": drawdown_pct,
        "risk_label": risk_label,
        "profit_factor": float(run.get("profit_factor") or 0.0),
        "n_trades": int(run.get("n_trades") or 0),
        "gate_passed": bool(run.get("gate_passed")),
        "gate_failures": gate_failures,
    }


def get_strategy_source_code(item: dict) -> str:
    """Return strategy source code when the strategy path is available on disk."""
    strategy_path = str(item.get("path") or "").strip()
    if strategy_path and os.path.exists(strategy_path):
        with open(strategy_path, encoding="utf-8") as handle:
            return handle.read()
    return (
        f"# Built-in strategy: {item.get('name')}\n"
        "# Source code not available for built-in strategies.\n"
    )
