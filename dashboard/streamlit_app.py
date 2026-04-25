# crypto_ai_trader/dashboard/streamlit_app.py
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from dashboard.chart_component import render_responsive_chart
from config import (
    DB_PATH,
    LIVE_TRADE_ENABLED,
    LLM_ENABLED,
    LLM_MODEL,
    LLM_PROVIDER,
    MVP_FRESHNESS_MINUTES,
    MVP_MIN_HISTORY_DAYS,
    MVP_RESEARCH_UNIVERSE,
    STARTING_BALANCE_USD,
    SYMBOLS,
)
from strategy.ta_features import add_indicators
from strategy.regime import detect_regime, Regime
from strategy.runtime import (
    get_active_strategy_config,
    get_active_runtime_artifact,
    list_available_strategies,
    list_available_strategy_errors,
    set_active_strategy_config,
)
from strategy.plugin_sdk import (
    create_strategy_draft,
    export_strategy_pack,
    import_strategy_pack,
    inspect_strategy_pack,
    list_generated_draft_files,
    read_strategy_source_file,
    strategy_template_source,
    strategy_sdk_support,
    suggest_next_strategy_name,
    validate_strategy_source,
)
from strategy.artifacts import (
    approve_artifact_for_live,
    compute_strategy_code_hash,
    deactivate_runtime_artifact,
    get_active_runtime_artifact_id,
    list_all_strategy_artifacts,
    promote_artifact_to_paper,
    get_strategy_artifact,
    review_generated_strategy,
    validate_runtime_artifact,
)
from backtester.service import (
    get_backtest_run,
    get_backtest_trades,
    get_latest_market_focus,
    get_market_focus_candidates,
    list_backtest_presets,
    list_backtest_runs,
    run_and_persist_backtest,
    run_market_focus_study,
    save_backtest_preset,
)
from dashboard.workbench import (
    build_data_health_frame,
    build_deployment_readiness_frame,
    build_deployment_readiness_metrics,
    build_artifact_registry_frame,
    build_backtest_preset_frame,
    build_backtest_run_leaderboard,
    build_diary_entries_frame,
    build_paper_evidence_checklist_frame,
    build_paper_evidence_metrics,
    build_restart_survival_frame,
    build_restart_survival_metrics,
    build_diary_summary_metrics,
    build_focus_candidate_frame,
    build_live_freshness_frame,
    build_live_freshness_metrics,
    build_runtime_target_summary,
    build_trader_summary,
    build_trading_chart_payload,
    choose_backtest_default_symbol,
    choose_backtest_default_window,
    build_strategy_comparison_frame,
    build_strategy_catalog_frame,
    compute_win_loss_stats,
    compute_cumulative_trade_pnl,
    compute_drawdown_curve,
    compute_trade_equity_curve,
    find_matching_preset_name,
    filter_backtest_runs,
    filter_runtime_data,
    format_params_summary,
    format_scenario_label,
    format_strategy_origin,
    get_strategy_source_code,
    list_rollback_candidates,
    list_runtime_strategies,
    latest_complete_backtest_day,
    normalise_params,
    normalise_preset_name,
    runtime_mode_table,
    strategy_sdk_compatibility,
    strategy_workflow_status,
    summarise_data_health,
    runtime_summary,
)
from deployment.jetson_ops import evaluate_jetson_readiness
from strategy.paper_evaluation import build_paper_evidence_summary, evaluate_paper_evidence
from trading_diary.service import (
    get_trading_summary,
    list_diary_entries,
    record_session_summary,
    update_diary_entry,
)
from trading_diary.export import export_diary_to_knowledge
from database.models import RUNTIME_WORKER_HEARTBEAT_TS_KEY
from database.promotion_queries import query_promotions
from database.persistence import create_state_backup, evaluate_restart_survival
from database.models import init_db
from database.integrity import integrity_label
from llm.client import get_generation_readiness
from llm.generator import generate_and_discover_strategy
from market_data.background_loader import ensure_worker_running
from market_data.binance_symbols import list_binance_spot_usdt_symbols
from market_data.history import (
    audit as audit_history,
    backfill as backfill_history,
    ensure_symbol_history,
    format_audit_summary,
    get_latest_candle_time,
    sync_recent as sync_recent_history,
)
from market_data.professional_universe import (
    build_professional_universe_frame,
    list_professional_universe,
    validate_professional_universe_catalog,
)
from market_data.runtime_watchlist import list_runtime_symbols, set_runtime_symbols
from market_data.symbol_readiness import (
    list_load_jobs as list_symbol_load_jobs,
    list_ready_symbols,
    queue_symbol_load,
    retry_failed_load as retry_symbol_load,
)

# ── Regime config ─────────────────────────────────────────────────────────────
_REGIME_EMOJI = {
    Regime.RANGING:  "🔵 RANGING",
    Regime.TRENDING: "🟢 TRENDING",
    Regime.SQUEEZE:  "🟡 SQUEEZE",
    Regime.HIGH_VOL: "🔴 HIGH VOL",
}
_REGIME_STRATEGY = {
    Regime.RANGING:  "Mean Reversion",
    Regime.TRENDING: "Momentum",
    Regime.SQUEEZE:  "Breakout",
    Regime.HIGH_VOL: "HALTED",
}

# ── Timeframe config ──────────────────────────────────────────────────────────
_TF_OPTIONS = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
_TF_RESAMPLE = {
    "1m":  None,          # raw 1m candles, no resample
    "5m":  "5min",
    "15m": "15min",
    "1h":  "1h",
    "4h":  "4h",
    "1d":  "1D",
    "1w":  "1W",
}
# How many days of 1m candles to load for each timeframe
_TF_LOOKBACK_DAYS = {
    "1m":  2,
    "5m":  7,
    "15m": 14,
    "1h":  30,
    "4h":  90,
    "1d":  365,
    "1w":  730,
}

init_db()
ensure_worker_running()

# ── Helpers ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=10)
def load_candles_raw(sym: str, days: int) -> pd.DataFrame:
    try:
        con = sqlite3.connect(DB_PATH)
        since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        df = pd.read_sql(
            "SELECT open_time, open, high, low, close, volume FROM candles "
            "WHERE symbol = ? AND open_time >= ? ORDER BY open_time",
            con, params=[sym, since], parse_dates=["open_time"]
        )
        con.close()
        return df
    except Exception:
        return pd.DataFrame()


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample 1m OHLCV DataFrame to a higher timeframe."""
    df = df.set_index("open_time")
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    resampled = df.resample(rule).agg(agg).dropna().reset_index()
    return resampled


@st.cache_data(ttl=5)
def load_trades(sym: str) -> pd.DataFrame:
    try:
        con = sqlite3.connect(DB_PATH)
        df = pd.read_sql(
            "SELECT ts, side, qty, price, fee, pnl, strategy_name, strategy_version, run_mode, regime "
            "FROM trades WHERE symbol = ? ORDER BY ts",
            con, params=[sym], parse_dates=["ts"]
        )
        con.close()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=5)
def load_equity() -> pd.DataFrame:
    try:
        con = sqlite3.connect(DB_PATH)
        df = pd.read_sql(
            "SELECT ts, equity, balance, unreal_pnl, strategy_name, strategy_version, run_mode "
            "FROM portfolio_snapshots ORDER BY ts",
            con,
            parse_dates=["ts"],
        )
        con.close()
        return df
    except Exception:
        try:
            con = sqlite3.connect(DB_PATH)
            df = pd.read_sql("SELECT ts, equity FROM portfolio ORDER BY ts", con, parse_dates=["ts"])
            con.close()
            return df
        except Exception:
            return pd.DataFrame()


@st.cache_data(ttl=5)
def load_live_data_freshness(symbols: tuple[str, ...]) -> dict[str, object]:
    ordered_symbols = [str(symbol) for symbol in symbols if str(symbol)]
    candles = pd.DataFrame(columns=["symbol", "latest_candle_ts"])
    worker_heartbeat_ts: str | None = None
    try:
        con = sqlite3.connect(DB_PATH)
        if ordered_symbols:
            placeholders = ",".join(["?"] * len(ordered_symbols))
            candles = pd.read_sql(
                "SELECT symbol, MAX(open_time) AS latest_candle_ts "
                f"FROM candles WHERE symbol IN ({placeholders}) GROUP BY symbol",
                con,
                params=ordered_symbols,
                parse_dates=["latest_candle_ts"],
            )
        heartbeat_row = con.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            [RUNTIME_WORKER_HEARTBEAT_TS_KEY],
        ).fetchone()
        worker_heartbeat_ts = heartbeat_row[0] if heartbeat_row else None
        con.close()
    except Exception:
        return {
            "candles": pd.DataFrame(columns=["symbol", "latest_candle_ts"]),
            "worker_heartbeat_ts": None,
        }

    return {
        "candles": candles,
        "worker_heartbeat_ts": worker_heartbeat_ts,
    }


@st.cache_data(ttl=30)
def load_promotions() -> pd.DataFrame:
    return query_promotions(DB_PATH)


@st.cache_data(ttl=10)
def load_strategy_catalog() -> list[dict]:
    return list_available_strategies(refresh=True)


@st.cache_data(ttl=10)
def load_strategy_errors() -> list[dict]:
    return list_available_strategy_errors(refresh=True)


@st.cache_data(ttl=10)
def load_backtest_runs() -> pd.DataFrame:
    return list_backtest_runs()


@st.cache_data(ttl=10)
def load_backtest_trades(run_id: int) -> pd.DataFrame:
    return get_backtest_trades(run_id)


@st.cache_data(ttl=10)
def load_backtest_run(run_id: int) -> dict | None:
    return get_backtest_run(run_id)


@st.cache_data(ttl=10)
def load_backtest_presets(strategy_name: str) -> pd.DataFrame:
    return list_backtest_presets(strategy_name)


def to_utc_naive_timestamp(value: object) -> pd.Timestamp:
    """Normalize timestamp-like values to a UTC-naive pandas Timestamp."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        return ts.tz_convert("UTC").tz_localize(None)
    return ts


def enrich_chart_studies(candles: pd.DataFrame) -> pd.DataFrame:
    """Merge indicator columns back onto the raw candle frame without dropping warmup rows."""
    if candles.empty:
        return candles

    frame = candles.copy()
    frame["open_time"] = pd.to_datetime(frame["open_time"], errors="coerce")
    frame = frame.dropna(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)

    study_source = add_indicators(frame.copy())
    study_columns = [
        "ema_9",
        "ema_21",
        "ema_55",
        "ema_200",
        "bb_hi",
        "bb_lo",
        "rsi_14",
        "macd",
        "macd_s",
    ]
    for column in study_columns:
        if column not in frame.columns:
            frame[column] = pd.NA

    if study_source.empty:
        return frame

    available_columns = ["open_time"] + [column for column in study_columns if column in study_source.columns]
    merged = frame.drop(columns=[column for column in study_columns if column in frame.columns], errors="ignore").merge(
        study_source[available_columns],
        on="open_time",
        how="left",
    )
    for column in study_columns:
        if column not in merged.columns:
            merged[column] = pd.NA
    return merged


def apply_backtest_params_to_session(
    strategy_name: str,
    param_schema: list[dict],
    params: dict,
    defaults: dict,
) -> None:
    """Push a parameter payload into the widget session state for one strategy."""
    params = normalise_params(params)
    for field in param_schema:
        field_name = str(field.get("name", "")).strip()
        if not field_name:
            continue
        key = f"bt_param_{strategy_name}_{field_name}"
        st.session_state[key] = params.get(field_name, defaults.get(field_name))


def render_strategy_param_control(strategy_name: str, field: dict, defaults: dict) -> object:
    """Render one parameter control for the selected strategy."""
    name = str(field.get("name", "")).strip()
    if not name:
        return None

    label = str(field.get("label") or name.replace("_", " ").title())
    help_text = field.get("help")
    key = f"bt_param_{strategy_name}_{name}"
    field_type = str(field.get("type", "text")).lower()
    default_value = defaults.get(name)

    if key not in st.session_state:
        st.session_state[key] = default_value

    if field_type == "bool":
        if st.session_state[key] is None:
            st.session_state[key] = False
        return st.checkbox(label, key=key, help=help_text)

    if field_type == "int":
        if st.session_state[key] is None:
            st.session_state[key] = int(default_value or 0)
        input_kwargs = {
            "label": label,
            "step": int(field.get("step", 1) or 1),
            "key": key,
            "help": help_text,
        }
        if field.get("min") is not None:
            input_kwargs["min_value"] = int(field["min"])
        if field.get("max") is not None:
            input_kwargs["max_value"] = int(field["max"])
        return int(st.number_input(**input_kwargs))

    if field_type == "float":
        if st.session_state[key] is None:
            st.session_state[key] = float(default_value or 0.0)
        input_kwargs = {
            "label": label,
            "step": float(field.get("step", 0.1) or 0.1),
            "key": key,
            "help": help_text,
            "format": "%.4f",
        }
        if field.get("min") is not None:
            input_kwargs["min_value"] = float(field["min"])
        if field.get("max") is not None:
            input_kwargs["max_value"] = float(field["max"])
        return float(st.number_input(**input_kwargs))

    if field_type == "select":
        options = list(field.get("options") or [])
        if not options:
            if st.session_state[key] is None:
                st.session_state[key] = str(default_value or "")
            return st.text_input(label, key=key, help=help_text)
        if st.session_state[key] not in options:
            st.session_state[key] = default_value if default_value in options else options[0]
        return st.selectbox(label, options, key=key, help=help_text)

    if st.session_state[key] is None:
        st.session_state[key] = "" if default_value is None else str(default_value)
    return st.text_input(label, key=key, help=help_text)


@st.cache_data(ttl=300)
def load_symbol_catalog() -> list[dict]:
    """Return Binance spot USDT symbols, falling back to seeded runtime symbols on error."""
    try:
        catalog = list_binance_spot_usdt_symbols()
        if catalog:
            return catalog
    except Exception:
        pass
    return [
        {
            "symbol": sym,
            "base_asset": sym[:-4] if sym.endswith("USDT") else sym,
            "quote_asset": "USDT",
            "status": "UNKNOWN",
            "quote_volume": 0.0,
            "quote_volume_rank": idx + 1,
        }
        for idx, sym in enumerate(list_runtime_symbols() or SYMBOLS)
    ]


@st.cache_data(ttl=30)
def load_symbol_audit(symbol: str, start_iso: str, end_iso: str) -> dict:
    """Return continuity audit results for one symbol/date window."""
    return audit_history(symbol, start_iso, end_iso, interval="1m")


@st.cache_data(ttl=30)
def load_ready_symbol_health(
    ready_symbols: tuple[str, ...],
    mvp_research_universe: tuple[str, ...],
) -> list[dict]:
    """Return freshness and 30-day runnable-window status for ready symbols."""
    now_utc = pd.Timestamp.utcnow()
    if now_utc.tzinfo is None:
        now_utc = now_utc.tz_localize("UTC")

    mvp_set = {str(symbol or "").strip().upper() for symbol in mvp_research_universe if str(symbol or "").strip()}
    rows: list[dict] = []
    for raw_symbol in ready_symbols:
        symbol_name = str(raw_symbol or "").strip().upper()
        if not symbol_name:
            continue

        latest_candle_dt = get_latest_candle_time(symbol_name)
        latest_ts = pd.Timestamp(latest_candle_dt) if latest_candle_dt is not None else None
        age_minutes: int | None = None
        latest_window_start = None
        latest_window_end = None
        window_runnable: bool | None = None
        has_min_history: bool | None = None

        if latest_ts is not None:
            if latest_ts.tzinfo is None:
                latest_ts = latest_ts.tz_localize("UTC")
            else:
                latest_ts = latest_ts.tz_convert("UTC")
            age_minutes = max(0, int((now_utc - latest_ts).total_seconds() // 60))

            if symbol_name in mvp_set:
                latest_day = latest_complete_backtest_day(latest_ts, now_utc=now_utc)
                window_end = datetime.combine(latest_day, datetime.min.time())
                window_start = window_end - timedelta(days=MVP_MIN_HISTORY_DAYS)
                audit_result = load_symbol_audit(symbol_name, window_start.isoformat(), window_end.isoformat())
                latest_window_start = window_start.date().isoformat()
                latest_window_end = window_end.date().isoformat()
                window_runnable = bool(audit_result.get("is_complete"))
                has_min_history = bool(audit_result.get("is_complete"))

        rows.append(
            {
                "symbol": symbol_name,
                "latest_candle_ts": latest_ts.isoformat() if latest_ts is not None else None,
                "age_minutes": age_minutes,
                "is_fresh": age_minutes is not None and age_minutes <= MVP_FRESHNESS_MINUTES,
                "has_min_history": has_min_history,
                "latest_window_start": latest_window_start,
                "latest_window_end": latest_window_end,
                "window_runnable": window_runnable,
            }
        )
    return rows


def format_data_age(age_minutes: int | None) -> str:
    """Return a concise trader-facing age label for candle freshness."""
    if age_minutes is None:
        return "No data"
    if age_minutes >= 1440:
        return f"{age_minutes // 1440}d"
    if age_minutes >= 60:
        return f"{age_minutes // 60}h"
    return f"{age_minutes}m"


@st.cache_data(ttl=15)
def load_ready_symbols_cached() -> list[str]:
    """Symbols with local candle data, ordered by Binance volume rank."""
    ready = set(list_ready_symbols())
    if not ready:
        return list(SYMBOLS)
    catalog = load_symbol_catalog()
    ranked = [row["symbol"] for row in catalog if row["symbol"] in ready]
    in_catalog = {row["symbol"] for row in catalog}
    ranked.extend(sorted(s for s in ready if s not in in_catalog))
    return ranked


@st.cache_data(ttl=5)
def load_symbol_jobs() -> list[dict]:
    """Return symbol load jobs, most recent first."""
    return list_symbol_load_jobs()


@st.cache_data(ttl=30)
def load_professional_universe_frame_cached(
    catalog_rows: tuple[tuple[str, str, int | None, float], ...],
    ready_symbols_tuple: tuple[str, ...],
    runtime_symbols_tuple: tuple[str, ...],
    jobs_tuple: tuple[tuple[str, str], ...],
) -> pd.DataFrame:
    """Return Professional 20 readiness rows for dashboard display."""
    catalog = [
        {
            "symbol": symbol,
            "status": status,
            "quote_volume_rank": rank,
            "quote_volume": volume,
        }
        for symbol, status, rank, volume in catalog_rows
    ]
    jobs = [{"symbol": symbol, "status": status} for symbol, status in jobs_tuple]
    latest = {symbol: get_latest_candle_time(symbol) for symbol in list_professional_universe()}
    rows = build_professional_universe_frame(
        catalog,
        list(ready_symbols_tuple),
        list(runtime_symbols_tuple),
        jobs,
        latest,
    )
    return pd.DataFrame(rows)


def render_runtime_monitor_panel(
    symbol: str,
    runtime_strategy_filter: str,
    runtime_mode_filter: str,
    active_strategy_name: str,
    runtime_watchlist: list[str],
    autoref_enabled: bool,
    show_trades: bool,
    show_fast_emas: bool,
    show_ema_200: bool,
    show_bbands: bool,
    show_rsi: bool,
    show_macd: bool,
) -> None:
    """Render the runtime monitor body; can be called from a fragment for partial refresh."""
    runtime_trades_all = load_trades(symbol)
    runtime_equity_all = load_equity()
    runtime_symbols = list(dict.fromkeys([*(runtime_watchlist or []), symbol]))
    freshness_payload = load_live_data_freshness(tuple(runtime_symbols))

    st.markdown("### Runtime Monitor")
    st.caption(
        f"Viewing `{runtime_strategy_filter}` in `{runtime_mode_filter}` mode for runtime monitoring. "
        "Changing the active strategy affects dashboard backtests immediately and paper/live after restart."
    )
    refresh_status = "Auto-refresh on" if autoref_enabled else "Auto-refresh paused"
    st.caption(f"{refresh_status} · last updated {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    if symbol not in runtime_watchlist:
        st.info(
            f"`{symbol}` is available for research/backtests but is not in the runtime watchlist. "
            "Add it in the sidebar to stream and trade it in paper/live."
        )
    st.markdown("### 📈 " + symbol + " Chart")
    tf_cols = st.columns(len(_TF_OPTIONS))
    if "timeframe" not in st.session_state:
        st.session_state.timeframe = "1h"

    for i, tf in enumerate(_TF_OPTIONS):
        btn_type = "primary" if st.session_state.timeframe == tf else "secondary"
        if tf_cols[i].button(tf, key=f"tf_{tf}", type=btn_type, width="stretch"):
            st.session_state.timeframe = tf

    timeframe = st.session_state.timeframe
    lookback = _TF_LOOKBACK_DAYS[timeframe]
    resample = _TF_RESAMPLE[timeframe]

    raw = load_candles_raw(symbol, lookback)
    if not raw.empty and resample:
        ohlcv = resample_ohlcv(raw, resample)
    elif not raw.empty:
        ohlcv = raw.copy()
    else:
        ohlcv = pd.DataFrame()

    df = add_indicators(ohlcv) if not ohlcv.empty else ohlcv
    tr = filter_runtime_data(runtime_trades_all, runtime_strategy_filter, runtime_mode_filter)
    eq = filter_runtime_data(runtime_equity_all, runtime_strategy_filter, runtime_mode_filter)
    runtime_stats = runtime_summary(tr, eq)
    candle_freshness = freshness_payload.get("candles", pd.DataFrame())
    candle_map = (
        {
            str(row.get("symbol")): row.get("latest_candle_ts")
            for row in candle_freshness.to_dict("records")
        }
        if isinstance(candle_freshness, pd.DataFrame) and not candle_freshness.empty
        else {}
    )
    freshness_rows = [
        {"symbol": runtime_symbol, "latest_candle_ts": candle_map.get(runtime_symbol)}
        for runtime_symbol in runtime_symbols
    ]
    freshness_frame = build_live_freshness_frame(
        freshness_rows,
        freshness_minutes=MVP_FRESHNESS_MINUTES,
    )
    freshness_metrics = build_live_freshness_metrics(
        freshness_frame,
        worker_heartbeat_ts=freshness_payload.get("worker_heartbeat_ts"),
        last_snapshot_ts=runtime_stats.get("last_snapshot_ts"),
        last_trade_ts=runtime_stats.get("last_trade_ts"),
    )
    mode_table = runtime_mode_table(
        filter_runtime_data(runtime_trades_all, runtime_strategy_filter, "All"),
        filter_runtime_data(runtime_equity_all, runtime_strategy_filter, "All"),
    )
    pnl_curve = compute_cumulative_trade_pnl(tr)

    regime = None
    if not df.empty and len(df) >= 2:
        try:
            regime = detect_regime(df)
        except Exception:
            pass

    chart_df = enrich_chart_studies(ohlcv) if not ohlcv.empty else pd.DataFrame()

    st.markdown("#### Live Data Freshness")
    st.caption(
        "Quick operator proof that the runtime worker is alive: latest worker heartbeat, "
        "latest persisted portfolio state, latest trade timestamp, and per-symbol candle freshness."
    )
    freshness_cols = st.columns(4)
    freshness_cols[0].metric(
        "Worker Heartbeat",
        freshness_metrics["heartbeat_value"],
        freshness_metrics["heartbeat_delta"],
    )
    freshness_cols[1].metric(
        "Last Portfolio Snapshot",
        freshness_metrics["snapshot_value"],
        freshness_metrics["snapshot_delta"],
    )
    freshness_cols[2].metric(
        "Last Trade",
        freshness_metrics["trade_value"],
        freshness_metrics["trade_delta"],
    )
    freshness_cols[3].metric(
        "Fresh Runtime Symbols",
        freshness_metrics["fresh_symbols_value"],
        freshness_metrics["fresh_symbols_delta"],
    )
    if not freshness_frame.empty:
        st.dataframe(
            freshness_frame[["symbol", "last_candle_ts", "candle_age_minutes", "freshness"]],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No runtime symbols are configured yet, so candle freshness cannot be audited.")

    st.caption("Responsive chart shows the active studies directly on the workbench: EMA overlays, Bollinger Bands, RSI, MACD, and runtime trade markers.")
    if runtime_mode_filter == "All":
        st.info("Trade markers are aggregated across paper and live. Switch Runtime Mode to `paper` or `live` to inspect one stream.")
    regime_label = _REGIME_EMOJI.get(regime, "") if regime else ""
    runtime_chart_payload = build_trading_chart_payload(
        chart_df,
        tr if show_trades else pd.DataFrame(),
        symbol=symbol,
        timeframe=timeframe,
        strategy_name=runtime_strategy_filter,
        context_label=f"{runtime_mode_filter.upper()} {regime_label}".strip(),
        show_fast_emas=show_fast_emas,
        show_ema_200=show_ema_200,
        show_bbands=show_bbands,
        show_rsi=show_rsi,
        show_macd=show_macd,
    )
    if runtime_chart_payload["candles"]:
        render_responsive_chart(
            runtime_chart_payload,
            chart_id=f"runtime-{symbol}-{timeframe}-{runtime_strategy_filter}-{runtime_mode_filter}",
            height=680,
        )
    else:
        st.info("No data — run `python run_live.py` to load candles.")

    overview_cols = st.columns(6)
    overview_cols[0].metric("Strategy View", runtime_strategy_filter)
    overview_cols[1].metric("Mode Filter", runtime_mode_filter)
    overview_cols[2].metric(
        "Last Snapshot",
        pd.to_datetime(runtime_stats["last_snapshot_ts"]).strftime("%Y-%m-%d %H:%M")
        if runtime_stats.get("last_snapshot_ts") is not None else "—",
    )
    overview_cols[3].metric(
        "Last Trade",
        pd.to_datetime(runtime_stats["last_trade_ts"]).strftime("%Y-%m-%d %H:%M")
        if runtime_stats.get("last_trade_ts") is not None else "—",
    )
    overview_cols[4].metric("Realized P&L", f"{runtime_stats['realized_pnl']:+,.2f}")
    overview_cols[5].metric("Trades", str(runtime_stats["trade_count"]))

    summary_cols = st.columns(5)
    summary_cols[0].metric("Equity", f"${runtime_stats['equity']:,.2f}")
    summary_cols[1].metric("Balance", f"${runtime_stats['balance']:,.2f}")
    summary_cols[2].metric("Unreal P&L", f"{runtime_stats['unreal_pnl']:+,.2f}")
    summary_cols[3].metric("Last Side", str(runtime_stats["last_trade_side"]))
    summary_cols[4].metric("Last Regime", str(runtime_stats["last_trade_regime"]))

    if not mode_table.empty:
        st.markdown("### Mode Comparison")
        display_mode_table = mode_table.copy()
        for ts_col in ["last_trade_ts", "last_snapshot_ts"]:
            if ts_col in display_mode_table.columns:
                display_mode_table[ts_col] = pd.to_datetime(display_mode_table[ts_col]).dt.strftime("%Y-%m-%d %H:%M:%S")
                display_mode_table[ts_col] = display_mode_table[ts_col].fillna("—")
        st.dataframe(display_mode_table, width="stretch", hide_index=True)

    if not eq.empty and "equity" in eq.columns:
        eq_left, eq_right = st.columns(2)
        with eq_left:
            eq_fig = go.Figure()
            mode_palette = {"paper": "#2962ff", "live": "#00c853"}
            grouped_equity = eq.groupby(eq["run_mode"].fillna("paper")) if "run_mode" in eq.columns else [("paper", eq)]
            latest_x = []
            for mode, mode_eq in grouped_equity:
                if mode_eq.empty:
                    continue
                latest_x.extend(mode_eq["ts"].tolist())
                eq_fig.add_trace(go.Scatter(
                    x=mode_eq["ts"],
                    y=mode_eq["equity"],
                    name=f"{mode.title()} Equity",
                    line=dict(color=mode_palette.get(str(mode), "#2962ff"), width=2),
                    fill="tozeroy" if runtime_mode_filter != "All" else None,
                    fillcolor="rgba(41,98,255,0.08)" if str(mode) == "paper" else "rgba(0,200,83,0.08)",
                ))
            start_line_x = [min(latest_x), max(latest_x)] if latest_x else []
            if start_line_x:
                eq_fig.add_trace(go.Scatter(
                    x=start_line_x, y=[STARTING_BALANCE_USD] * 2,
                    name="Starting Balance", line=dict(color="gray", dash="dot", width=1)
                ))
            eq_fig.update_layout(
                title="Runtime Equity",
                height=240,
                paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                font=dict(color="#d1d4dc"),
                margin=dict(l=10, r=10, t=40, b=10),
                xaxis=dict(gridcolor="#1e222d"),
                yaxis=dict(gridcolor="#1e222d"),
            )
            st.plotly_chart(eq_fig, width="stretch")

        with eq_right:
            dd_fig = go.Figure()
            grouped_equity = eq.groupby(eq["run_mode"].fillna("paper")) if "run_mode" in eq.columns else [("paper", eq)]
            for mode, mode_eq in grouped_equity:
                if mode_eq.empty:
                    continue
                runtime_equity = mode_eq[["ts", "equity"]].dropna().copy()
                runtime_equity["step"] = range(len(runtime_equity))
                runtime_drawdown = compute_drawdown_curve(runtime_equity.rename(columns={"equity": "equity", "step": "step"}))
                dd_fig.add_trace(go.Scatter(
                    x=runtime_equity["ts"],
                    y=runtime_drawdown["drawdown"],
                    name=f"{str(mode).title()} Drawdown",
                    line=dict(color=mode_palette.get(str(mode), "#ff7043"), width=2),
                    fill="tozeroy" if runtime_mode_filter != "All" else None,
                    fillcolor="rgba(255,112,67,0.12)",
                ))
            dd_fig.update_layout(
                title="Runtime Drawdown",
                height=240,
                paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                font=dict(color="#d1d4dc"),
                margin=dict(l=10, r=10, t=40, b=10),
                xaxis=dict(gridcolor="#1e222d"),
                yaxis=dict(gridcolor="#1e222d", tickformat=".1%"),
            )
            st.plotly_chart(dd_fig, width="stretch")

    if not pnl_curve.empty:
        st.markdown("### Realized P&L Curve")
        pnl_fig = go.Figure()
        for mode, mode_curve in pnl_curve.groupby("run_mode"):
            pnl_fig.add_trace(go.Scatter(
                x=mode_curve["ts"],
                y=mode_curve["cumulative_pnl"],
                name=f"{str(mode).title()} P&L",
                mode="lines+markers",
                line=dict(width=2),
            ))
        pnl_fig.update_layout(
            height=240,
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            font=dict(color="#d1d4dc"),
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(gridcolor="#1e222d"),
            yaxis=dict(gridcolor="#1e222d"),
        )
        st.plotly_chart(pnl_fig, width="stretch")

    st.markdown("### Recent Execution Context")
    if not tr.empty:
        recent_trades = tr.sort_values("ts", ascending=False).head(12).copy()
        if "ts" in recent_trades.columns:
            recent_trades["ts"] = pd.to_datetime(recent_trades["ts"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        ordered_cols = [
            col for col in ["ts", "run_mode", "side", "qty", "price", "pnl", "regime", "strategy_version"]
            if col in recent_trades.columns
        ]
        st.dataframe(recent_trades[ordered_cols], width="stretch", hide_index=True)
    else:
        st.info("No runtime trades recorded yet for the selected strategy/mode.")


def render_runtime_monitor_sidebar(
    symbol: str,
    runtime_strategy_filter: str,
    runtime_mode_filter: str,
) -> None:
    """Render the live runtime summary in the sidebar."""
    runtime_trades_all = load_trades(symbol)
    runtime_equity_all = load_equity()
    timeframe = st.session_state.get("timeframe", "1h")
    if timeframe not in _TF_LOOKBACK_DAYS:
        timeframe = "1h"
    lookback = _TF_LOOKBACK_DAYS[timeframe]
    resample = _TF_RESAMPLE[timeframe]

    raw = load_candles_raw(symbol, lookback)
    if not raw.empty and resample:
        ohlcv = resample_ohlcv(raw, resample)
    elif not raw.empty:
        ohlcv = raw.copy()
    else:
        ohlcv = pd.DataFrame()

    df = add_indicators(ohlcv) if not ohlcv.empty else ohlcv
    eq = filter_runtime_data(runtime_equity_all, runtime_strategy_filter, runtime_mode_filter)

    regime = None
    if not df.empty and len(df) >= 2:
        try:
            regime = detect_regime(df)
            last = df.iloc[-1]
            st.markdown("---")
            st.markdown("### 📊 Current Regime")
            st.markdown(f"**{_REGIME_EMOJI[regime]}**")
            st.markdown(f"Strategy route: **{_REGIME_STRATEGY[regime]}**")
            st.caption(f"Runtime view strategy: {runtime_strategy_filter}")
            st.markdown("---")
            st.metric("Last Price", f"${last.close:,.4f}")
            chg = ((last.close - df.iloc[-2].close) / df.iloc[-2].close * 100) if len(df) >= 2 else 0
            st.metric("Change", f"{chg:+.2f}%")
            st.markdown("---")
            st.metric("RSI-14", f"{last.rsi_14:.1f}" if "rsi_14" in df.columns else "—")
            st.metric("ADX-14", f"{last.adx_14:.1f}" if "adx_14" in df.columns else "—")
            st.metric("BB Width", f"{last.bb_width:.4f}" if "bb_width" in df.columns else "—")
        except Exception:
            pass

    st.markdown("---")
    if not eq.empty and "equity" in eq.columns:
        st.metric(
            "Equity (USD)",
            f"${eq.equity.iloc[-1]:,.2f}",
            delta=f"{eq.equity.iloc[-1] - STARTING_BALANCE_USD:+.2f}",
        )
    else:
        st.metric("Equity (USD)", f"${STARTING_BALANCE_USD:,.2f}")

    st.markdown("---")
    st.markdown("### 🤖 AI Promotion Gate")
    try:
        promo_df = load_promotions()
        if not promo_df.empty:
            latest = promo_df.iloc[0]
            ts_str = pd.to_datetime(latest["ts"]).strftime("%Y-%m-%d")
            st.success(f"🚀 PROMOTED  ·  {ts_str}")
            st.metric("Sharpe", f"{latest['sharpe']:.2f}")
            st.metric("Max Drawdown", f"{latest['max_dd']:.1%}")
            st.metric("Profit Factor", f"{latest['profit_factor']:.2f}")
            if LIVE_TRADE_ENABLED:
                st.warning("⚡ LIVE_TRADE_ENABLED=true")
            else:
                st.caption("Set LIVE_TRADE_ENABLED=true in .env to enable real orders")
        else:
            st.info("⏳ Not yet promoted")
            st.caption("Requires 3 consecutive PROMOTE_TO_LIVE evaluations")
    except Exception:
        st.caption("Promotion data unavailable")


def build_runtime_monitor_renderer(run_every: str | None):
    """Return a runtime panel renderer that can optionally rerun on a timer."""
    @st.fragment(run_every=run_every)
    def _render(
        symbol: str,
        runtime_strategy_filter: str,
        runtime_mode_filter: str,
        active_strategy_name: str,
        runtime_watchlist: list[str],
        autoref_enabled: bool,
        show_trades: bool,
        show_fast_emas: bool,
        show_ema_200: bool,
        show_bbands: bool,
        show_rsi: bool,
        show_macd: bool,
    ) -> None:
        render_runtime_monitor_panel(
            symbol,
            runtime_strategy_filter,
            runtime_mode_filter,
            active_strategy_name,
            runtime_watchlist,
            autoref_enabled,
            show_trades,
            show_fast_emas,
            show_ema_200,
            show_bbands,
            show_rsi,
            show_macd,
        )

    return _render


def build_runtime_monitor_sidebar_renderer(run_every: str | None):
    """Return a sidebar runtime renderer that can optionally rerun on a timer."""
    @st.fragment(run_every=run_every)
    def _render(
        symbol: str,
        runtime_strategy_filter: str,
        runtime_mode_filter: str,
    ) -> None:
        render_runtime_monitor_sidebar(
            symbol,
            runtime_strategy_filter,
            runtime_mode_filter,
        )

    return _render


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Crypto-AI Trader", layout="wide", initial_sidebar_state="expanded")

# Dark theme override
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .tf-btn button { border-radius: 4px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ Controls")

symbol_catalog = load_symbol_catalog()
available_symbols = [row["symbol"] for row in symbol_catalog]  # full Binance catalog
ready_symbols = load_ready_symbols_cached()                     # symbols with local data
runtime_watchlist = list_runtime_symbols()
if not available_symbols:
    available_symbols = runtime_watchlist or list(SYMBOLS)
if not ready_symbols:
    ready_symbols = runtime_watchlist or list(SYMBOLS)
if not runtime_watchlist:
    runtime_watchlist = list(SYMBOLS)
if not available_symbols:
    available_symbols = ["BTCUSDT"]
if not ready_symbols:
    ready_symbols = ["BTCUSDT"]

mvp_research_universe = tuple(
    symbol_name
    for symbol_name in dict.fromkeys(
        [str(symbol or "").strip().upper() for symbol in (MVP_RESEARCH_UNIVERSE or SYMBOLS)]
    )
    if symbol_name
)
ready_symbol_health = load_ready_symbol_health(tuple(ready_symbols), mvp_research_universe)
data_health_summary = summarise_data_health(
    ready_symbol_health,
    mvp_research_universe,
    MVP_FRESHNESS_MINUTES,
)
data_health_frame = build_data_health_frame(ready_symbol_health)

# Persist all user preferences in session_state so auto-refresh never resets them
_DEFAULTS = {
    "symbol":        runtime_watchlist[0] if runtime_watchlist else available_symbols[0],
    "autoref":       True,
    "show_trades":   True,
    "show_fast_emas": True,
    "show_ema_200": True,
    "show_bbands": True,
    "show_rsi": True,
    "show_macd": True,
    "runtime_mode_filter": "paper",
    "show_all_backtest_runs": False,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state["symbol"] not in available_symbols:
    available_symbols = [st.session_state["symbol"]] + [sym for sym in available_symbols if sym != st.session_state["symbol"]]
# Reset saved symbol to first ready option if it has no local data
if st.session_state.get("symbol") not in ready_symbols:
    st.session_state["symbol"] = ready_symbols[0]

symbol  = st.sidebar.selectbox("Symbol", ready_symbols, key="symbol")
autoref = st.sidebar.checkbox("Auto-refresh (15 s)", key="autoref")

st.sidebar.markdown("---")
st.sidebar.markdown("**Runtime Watchlist**")
watchlist_selection = st.sidebar.multiselect(
    "Paper/Live Symbols",
    options=available_symbols,
    default=[sym for sym in runtime_watchlist if sym in available_symbols] or runtime_watchlist,
    key="runtime_watchlist_editor",
)
watchlist_cols = st.sidebar.columns(2)
save_watchlist = watchlist_cols[0].button("Save Watchlist", width="stretch")
sync_symbol = watchlist_cols[1].button("Sync Selected", width="stretch")

if save_watchlist:
    previous_watchlist = set(runtime_watchlist)
    updated_watchlist = set_runtime_symbols(list(watchlist_selection))
    added_symbols = [sym for sym in updated_watchlist if sym not in previous_watchlist]
    if added_symbols:
        with st.spinner(f"Syncing history for {', '.join(added_symbols)}..."):
            for sym in added_symbols:
                ensure_symbol_history(sym)
    load_symbol_catalog.clear()
    load_candles_raw.clear()
    load_trades.clear()
    load_equity.clear()
    load_ready_symbol_health.clear()
    st.success("Runtime watchlist updated.")
    st.rerun()

if sync_symbol:
    with st.spinner(f"Syncing history for {symbol}..."):
        ensure_symbol_history(symbol)
    load_candles_raw.clear()
    load_symbol_audit.clear()
    load_ready_symbol_health.clear()
    st.success(f"Synced recent history for {symbol}.")
    st.rerun()

st.sidebar.markdown("---")
_ready_set = set(ready_symbols)
_unloaded_symbols = [s for s in available_symbols if s not in _ready_set]
with st.sidebar.expander(f"Load New Symbol ({len(_unloaded_symbols)} available)", expanded=False):
    st.caption("Queue a background 30-day history load. The symbol appears in chart/backtest selectors once ready.")
    if _unloaded_symbols:
        _new_sym = st.selectbox(
            "Search Binance USDT symbol",
            _unloaded_symbols,
            key="load_new_sym_picker",
        )
        if st.button("Queue Background Load", key="queue_new_load_btn", use_container_width=True):
            _job = queue_symbol_load(_new_sym)
            if _job["status"] == "queued":
                st.info(f"Queued: **{_new_sym}** will appear in the symbol list once ready (~30 min).")
            elif _job["status"] == "loading":
                st.info(f"**{_new_sym}** is already loading.")
            elif _job["status"] == "ready":
                st.success(f"**{_new_sym}** is already ready — refresh to see it in selectors.")
            load_ready_symbols_cached.clear()
            load_symbol_jobs.clear()
            load_ready_symbol_health.clear()
            st.rerun()
    else:
        st.caption("All discovered Binance symbols are already loaded.")

    _jobs = load_symbol_jobs()
    _active = [j for j in _jobs if j["status"] in ("queued", "loading", "failed")]
    if _active:
        st.markdown("**Load Queue**")
        for _j in _active[:10]:
            _icon = {"queued": "⏳", "loading": "🔄", "failed": "❌"}.get(_j["status"], "?")
            st.caption(f"{_icon} **{_j['symbol']}** — {_j['status']}")
            if _j["status"] == "failed":
                if _j.get("error_msg"):
                    st.caption(f"  {_j['error_msg'][:80]}")
                if st.button("Retry", key=f"retry_load_{_j['symbol']}", use_container_width=True):
                    retry_symbol_load(_j["symbol"])
                    load_symbol_jobs.clear()
                    st.rerun()
    _recently_ready = [j for j in _jobs if j["status"] == "ready"][:5]
    if _recently_ready:
        st.markdown("**Recently Loaded**")
        for _j in _recently_ready:
            st.caption(f"✅ {_j['symbol']}")

st.sidebar.markdown("---")
professional_universe = list_professional_universe()
professional_validation = validate_professional_universe_catalog(symbol_catalog)
_catalog_tuple = tuple(
    (
        str(row.get("symbol", "")),
        str(row.get("status", "")),
        row.get("quote_volume_rank"),
        float(row.get("quote_volume", 0.0) or 0.0),
    )
    for row in symbol_catalog
)
_job_tuple = tuple((str(job.get("symbol", "")), str(job.get("status", ""))) for job in load_symbol_jobs())
professional_frame = load_professional_universe_frame_cached(
    _catalog_tuple,
    tuple(ready_symbols),
    tuple(runtime_watchlist),
    _job_tuple,
)
with st.sidebar.expander("Professional 20 Research Universe", expanded=False):
    st.caption(
        "Long-term research tracker. Queue history for all 20, then promote only selected symbols "
        "into the smaller paper/live runtime watchlist."
    )
    if professional_validation["is_valid"]:
        st.success("Professional 20 active on Binance spot USDT.")
    else:
        st.warning("Professional 20 needs review against the latest Binance catalog.")
        if professional_validation["missing"]:
            st.caption("Missing: " + ", ".join(professional_validation["missing"]))
        if professional_validation["inactive"]:
            st.caption("Inactive: " + ", ".join(professional_validation["inactive"]))

    loaded_count = int((professional_frame["local_history"] == "ready").sum()) if not professional_frame.empty else 0
    runtime_count = int((professional_frame["runtime_watchlist"] == "active").sum()) if not professional_frame.empty else 0
    st.caption(f"History ready: {loaded_count}/20 · runtime active: {runtime_count}/20")

    if st.button("Queue Professional 20 History", key="queue_professional_20", use_container_width=True):
        queued = []
        for _sym in professional_universe:
            _job = queue_symbol_load(_sym)
            queued.append(f"{_sym}:{_job['status']}")
        load_symbol_jobs.clear()
        load_ready_symbols_cached.clear()
        load_professional_universe_frame_cached.clear()
        st.info("Queued/reused jobs: " + ", ".join(queued[:20]))
        st.rerun()

    _runtime_candidates = [sym for sym in professional_universe if sym in available_symbols]
    _current_prof_runtime = [sym for sym in runtime_watchlist if sym in _runtime_candidates]
    _prof_runtime_selection = st.multiselect(
        "Promote to runtime watchlist (max 5 recommended)",
        _runtime_candidates,
        default=_current_prof_runtime[:5],
        key="professional_runtime_picker",
    )
    if len(_prof_runtime_selection) > 5:
        st.warning("Jetson-safe default is 3-5 active runtime symbols. Reduce the selection before saving.")
    if st.button(
        "Save Professional Runtime Symbols",
        key="save_professional_runtime_symbols",
        disabled=len(_prof_runtime_selection) > 5,
        use_container_width=True,
    ):
        set_runtime_symbols(list(_prof_runtime_selection))
        load_professional_universe_frame_cached.clear()
        load_ready_symbol_health.clear()
        st.success("Runtime watchlist updated from Professional 20 selection.")
        st.rerun()

    if not professional_frame.empty:
        display_professional = professional_frame.copy()
        if "quote_volume" in display_professional.columns:
            display_professional["quote_volume"] = display_professional["quote_volume"].apply(
                lambda value: f"{float(value):,.0f}"
            )
        if "latest_candle_ts" in display_professional.columns:
            display_professional["latest_candle_ts"] = pd.to_datetime(
                display_professional["latest_candle_ts"],
                errors="coerce",
            ).dt.strftime("%Y-%m-%d %H:%M")
            display_professional["latest_candle_ts"] = display_professional["latest_candle_ts"].fillna("No data")
        st.dataframe(
            display_professional[
                [
                    "symbol",
                    "binance_status",
                    "quote_volume_rank",
                    "local_history",
                    "runtime_watchlist",
                    "load_status",
                    "latest_candle_ts",
                ]
            ],
            hide_index=True,
            width="stretch",
        )

st.sidebar.markdown("---")
st.sidebar.markdown("**MVP Data Health**")
if data_health_summary["release_blocked"]:
    st.sidebar.error("Research-only mode")
    st.sidebar.caption("MVP data gate is blocked. Do not treat this environment as paper/live ready.")
else:
    st.sidebar.success("MVP gate healthy")
    st.sidebar.caption("Maintained research universe has fresh data and runnable windows.")
st.sidebar.caption(
    f"Ready symbols: {data_health_summary['ready_symbol_count']} · "
    f"Fresh: {data_health_summary['fresh_symbol_count']} · "
    f"MVP runnable: {data_health_summary['mvp_runnable_count']}/{data_health_summary['mvp_symbol_count']}"
)

st.sidebar.markdown("---")
st.sidebar.markdown("**📉 Chart Layers**")
show_trades = st.sidebar.checkbox("Trade Markers",     key="show_trades")
show_fast_emas = st.sidebar.checkbox("EMA 9 / 21 / 55", key="show_fast_emas")
show_ema_200 = st.sidebar.checkbox("EMA 200", key="show_ema_200")
show_bbands = st.sidebar.checkbox("Bollinger Bands", key="show_bbands")
show_rsi = st.sidebar.checkbox("RSI", key="show_rsi")
show_macd = st.sidebar.checkbox("MACD", key="show_macd")
st.sidebar.caption("Responsive chart shows candles, volume, EMA/BB overlays, RSI, MACD, and BUY/SELL markers.")

active_strategy = get_active_strategy_config()
active_paper_artifact = get_active_runtime_artifact("paper")
active_live_artifact = get_active_runtime_artifact("live")
_paper_artifact_id = get_active_runtime_artifact_id("paper")
_live_artifact_id = get_active_runtime_artifact_id("live")
_, _paper_validation_error = validate_runtime_artifact(_paper_artifact_id)
_, _live_validation_error = validate_runtime_artifact(_live_artifact_id)
runtime_target_summary = build_runtime_target_summary(
    active_paper_artifact, active_live_artifact,
    _paper_validation_error, _live_validation_error,
)
strategy_catalog = load_strategy_catalog()
strategy_errors = load_strategy_errors()
all_backtest_runs = load_backtest_runs()
strategy_names = [item["name"] for item in strategy_catalog]
strategy_lookup = {item["name"]: item for item in strategy_catalog}
runtime_trades_all = load_trades(symbol)
runtime_equity_all = load_equity()
runtime_strategy_names = list_runtime_strategies(runtime_trades_all, runtime_equity_all, active_strategy["name"])
runtime_mode_filter = st.sidebar.selectbox("Runtime Mode", ["All", "paper", "live"], key="runtime_mode_filter")

if strategy_names:
    if "strategy_focus_name" not in st.session_state or st.session_state["strategy_focus_name"] not in strategy_names:
        st.session_state["strategy_focus_name"] = (
            active_strategy["name"] if active_strategy["name"] in strategy_names else strategy_names[0]
        )

    pending_focus = st.session_state.pop("strategy_focus_pending", None)
    if pending_focus in strategy_names:
        st.session_state["strategy_focus_name"] = pending_focus
        st.session_state["active_strategy_selector"] = pending_focus
        st.session_state["bt_strategy"] = pending_focus

default_strategy_name = st.session_state.get("strategy_focus_name", active_strategy["name"])
if strategy_names and default_strategy_name not in strategy_names:
    default_strategy_name = strategy_names[0]
default_strategy_index = strategy_names.index(default_strategy_name) if strategy_names else 0

if strategy_names:
    if st.session_state.get("active_strategy_selector") not in strategy_names:
        st.session_state["active_strategy_selector"] = default_strategy_name
    if st.session_state.get("bt_strategy") not in strategy_names:
        st.session_state["bt_strategy"] = default_strategy_name
if runtime_strategy_names:
    if st.session_state.get("runtime_strategy_filter") not in runtime_strategy_names:
        st.session_state["runtime_strategy_filter"] = active_strategy["name"] if active_strategy["name"] in runtime_strategy_names else runtime_strategy_names[0]
runtime_strategy_filter = st.sidebar.selectbox(
    "Runtime Strategy View",
    runtime_strategy_names or [active_strategy["name"]],
    key="runtime_strategy_filter",
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Strategy")
st.sidebar.markdown(f"Active: **{active_strategy['name']}**")
if active_strategy.get("version"):
    st.sidebar.caption(f"Version: {active_strategy['version']}")
with st.sidebar:
    _runtime_sidebar_renderer = build_runtime_monitor_sidebar_renderer("15s" if autoref else None)
    _runtime_sidebar_renderer(
        symbol,
        runtime_strategy_filter,
        runtime_mode_filter,
    )

focus_strategy_name = st.session_state.get("strategy_focus_name", default_strategy_name)
focus_strategy_meta = strategy_lookup.get(focus_strategy_name) if focus_strategy_name else None
focus_workflow_status = strategy_workflow_status(focus_strategy_meta, all_backtest_runs, active_strategy["name"])

st.markdown("## Strategy Workbench")
st.caption(
    "One flow: discover or generate a strategy, evaluate it in backtests, then monitor the same identity in paper/live."
)
hero_cols = st.columns(5)
hero_cols[0].metric("Backtest Default", active_strategy["name"])
hero_cols[1].metric("Focus Strategy", focus_strategy_name or "—")
hero_cols[2].metric("Workflow Stage", focus_workflow_status["stage"])
hero_cols[3].metric("Passing Backtests", str(focus_workflow_status["passed_runs"]))
hero_cols[4].metric(
    "Runtime Targets",
    f"P:{active_paper_artifact['name'] if active_paper_artifact else '—'} · L:{active_live_artifact['name'] if active_live_artifact else '—'}",
)
health_cols = st.columns(4)
health_cols[0].metric("Ready Symbols", str(data_health_summary["ready_symbol_count"]))
health_cols[1].metric("Fresh Symbols", str(data_health_summary["fresh_symbol_count"]))
health_cols[2].metric(
    "MVP Universe",
    f"{data_health_summary['mvp_ready_count']}/{data_health_summary['mvp_symbol_count']}",
)
health_cols[3].metric(
    "Runnable MVP Windows",
    f"{data_health_summary['mvp_runnable_count']}/{data_health_summary['mvp_symbol_count']}",
)
with st.expander("MVP Data Health Gate", expanded=data_health_summary["release_blocked"]):
    st.caption(
        f"Maintained research universe: {', '.join(f'`{symbol}`' for symbol in mvp_research_universe)}. "
        "This gate determines whether the environment should be treated as paper-readiness capable or research-only."
    )
    if data_health_summary["release_blocked"]:
        st.error(
            "The MVP data gate is blocked. Keep the system in research-only mode until the maintained universe is fresh and its latest 30-day windows are runnable."
        )
        st.markdown("\n".join(f"- {item}" for item in data_health_summary["release_blockers"]))
    else:
        st.success(
            "The maintained research universe is fresh and its latest 30-day windows are runnable. This environment is eligible for supervised paper-readiness evaluation."
        )
    st.dataframe(data_health_frame, width="stretch", hide_index=True)

    stale_symbols = [
        h["symbol"] for h in ready_symbol_health
        if not h.get("is_fresh", True)
    ]
    if stale_symbols:
        st.caption(f"Stale symbols: {', '.join(f'`{s}`' for s in stale_symbols)}")
        if st.button("Sync fresh data for stale symbols", key="mvp_sync_stale"):
            sync_results = {}
            for _sym in stale_symbols:
                try:
                    _res = sync_recent_history(_sym)
                    sync_results[_sym] = f"+{_res.get('rows_inserted', 0)} rows"
                except Exception as _sync_err:
                    sync_results[_sym] = f"error: {_sync_err}"
            for _sym, _msg in sync_results.items():
                st.write(f"`{_sym}`: {_msg}")
            st.cache_data.clear()
            st.rerun()

_real_issues = []
if active_paper_artifact and runtime_target_summary["paper"]["error"]:
    _real_issues.append(f"Paper target invalid — {runtime_target_summary['paper']['error']}")
if active_live_artifact and runtime_target_summary["live"]["error"]:
    _real_issues.append(f"Live target invalid — {runtime_target_summary['live']['error']}")
if _real_issues:
    st.warning("⚠ Runtime target validation failed. See **Promotion Control Panel** in the Strategies tab.  \n" + "  \n".join(_real_issues))

if active_paper_artifact and not runtime_target_summary["paper"]["error"]:
    _paper_name = active_paper_artifact.get("name", "?")
    _paper_status = str(active_paper_artifact.get("status") or "").lower()
    st.success(
        f"Paper trading armed — `{_paper_name}` is the active paper strategy "
        f"(status: `{_paper_status}`). Start the paper trader to begin forward evaluation."
    )
elif not active_paper_artifact:
    st.info(
        "No paper target set. Run a backtest for a reviewed plugin strategy, then promote it to paper "
        "from the Strategies tab to arm paper trading."
    )

strategy_tab, backtest_tab, runtime_tab, focus_tab, inspect_tab, diary_tab = st.tabs(
    ["Strategies", "Backtest Lab", "Runtime Monitor", "Market Focus", "Inspect", "Trading Diary"]
)

with strategy_tab:
    st.markdown("### Strategies")
    st.caption(
        "Research loop: generate or add a plugin, confirm it loads here, backtest it in the lab, "
        "then promote the same strategy into paper/live after restart."
    )

    # ── Promotion Control Panel ───────────────────────────────────────────────
    with st.expander("Promotion Control Panel", expanded=bool(_real_issues)):
        st.caption(
            "Manage active paper and live runtime targets. "
            "Deactivate or roll back to a different reviewed artifact without restarting."
        )
        _all_artifacts = list_all_strategy_artifacts()
        _pcp_cols = st.columns(2)

        # ── Paper target ──────────────────────────────────────────────────────
        with _pcp_cols[0]:
            st.markdown("##### Paper Target")
            _pt = runtime_target_summary["paper"]
            if _pt["configured"]:
                if _pt["valid"]:
                    st.success(f"✅ `{_pt['name']}` v{_pt['version']}  \nStatus: `{_pt['status']}` · hash `{_pt['code_hash_short']}`")
                else:
                    st.error(f"❌ `{_pt['name']}` — {_pt['error']}")
            else:
                st.info("No paper target configured.")

            if st.button("Deactivate Paper Target", key="deactivate_paper_btn", disabled=not _pt["configured"]):
                deactivate_runtime_artifact("paper")
                load_strategy_catalog.clear()
                st.cache_data.clear()
                st.success("Paper target cleared.")
                st.rerun()

            _paper_candidates = list_rollback_candidates(_all_artifacts, "paper", _pt["artifact_id"])
            if _paper_candidates:
                st.markdown("**Roll paper back to:**")
                _pc_labels = {
                    f"#{a['id']} {a['name']} v{a['version']} [{a['status']}]": a["id"]
                    for a in _paper_candidates
                }
                _pc_choice = st.selectbox("Select artifact", list(_pc_labels.keys()), key="paper_rollback_select")
                if st.button("Roll Back Paper Target", key="paper_rollback_btn"):
                    try:
                        _rolled = promote_artifact_to_paper(int(_pc_labels[_pc_choice]))
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        load_strategy_catalog.clear()
                        st.cache_data.clear()
                        st.success(f"Paper target set to artifact #{_rolled['id']} ({_rolled['name']}).")
                        st.rerun()
            elif _pt["configured"]:
                st.caption("No other eligible reviewed artifacts available for paper rollback.")

        # ── Live target ───────────────────────────────────────────────────────
        with _pcp_cols[1]:
            st.markdown("##### Live Target")
            _lt = runtime_target_summary["live"]
            if _lt["configured"]:
                if _lt["valid"]:
                    st.success(f"✅ `{_lt['name']}` v{_lt['version']}  \nStatus: `{_lt['status']}` · hash `{_lt['code_hash_short']}`")
                else:
                    st.error(f"❌ `{_lt['name']}` — {_lt['error']}")
            else:
                st.info("No live target configured.")

            if st.button("Deactivate Live Target", key="deactivate_live_btn", disabled=not _lt["configured"]):
                deactivate_runtime_artifact("live")
                load_strategy_catalog.clear()
                st.cache_data.clear()
                st.success("Live target cleared.")
                st.rerun()

            _live_candidates = list_rollback_candidates(_all_artifacts, "live", _lt["artifact_id"])
            if _live_candidates:
                st.markdown("**Roll live back to:**")
                _lc_labels = {
                    f"#{a['id']} {a['name']} v{a['version']} [{a['status']}]": a["id"]
                    for a in _live_candidates
                }
                _lc_choice = st.selectbox("Select artifact", list(_lc_labels.keys()), key="live_rollback_select")
                if st.button("Roll Back Live Target", key="live_rollback_btn"):
                    try:
                        _rolled_live = approve_artifact_for_live(int(_lc_labels[_lc_choice]))
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        load_strategy_catalog.clear()
                        st.cache_data.clear()
                        st.success(f"Live target set to artifact #{_rolled_live['id']} ({_rolled_live['name']}).")
                        st.rerun()
            elif _lt["configured"]:
                st.caption("No other eligible paper-passed artifacts available for live rollback.")

        # ── Artifact registry / audit trail ──────────────────────────────────
        st.markdown("---")
        st.markdown("##### Artifact Registry")
        _registry_df = build_artifact_registry_frame(_all_artifacts, all_backtest_runs)
        if not _registry_df.empty:
            st.dataframe(_registry_df, width="stretch", hide_index=True)
        else:
            st.caption("No strategy artifacts registered yet. Run a backtest on a reviewed plugin to begin.")

    with st.expander("Legacy Integrity Containment", expanded=False):
        from database.integrity import (
            archive_legacy_integrity_rows,
            count_archivable_legacy_rows,
            count_archived_legacy_rows,
            unarchive_legacy_integrity_rows,
        )
        from database.models import SessionLocal as _LegacySession

        st.caption(
            "Contain legacy test-fixture rows from pre-Sprint-42 runs that wrote into the "
            "live DB before pytest isolation landed. Archiving sets `integrity_status = "
            "'archived-legacy'`, excludes the rows from the release gate, and preserves the "
            "prior status in the note. No rows are deleted; the action is reversible."
        )

        with _LegacySession() as _legacy_sess:
            _archivable = count_archivable_legacy_rows(_legacy_sess)
            _archived = count_archived_legacy_rows(_legacy_sess)

        _mcols = st.columns(4)
        _mcols[0].metric("Legacy trades (active)", _archivable["trades"])
        _mcols[1].metric("Legacy backtests (active)", _archivable["backtest_runs"])
        _mcols[2].metric("Archived trades", _archived["trades"])
        _mcols[3].metric("Archived backtests", _archived["backtest_runs"])

        _btn_cols = st.columns(2)
        _archive_disabled = (_archivable["trades"] + _archivable["backtest_runs"]) == 0
        if _btn_cols[0].button(
            "Archive legacy rows",
            key="legacy_archive_btn",
            disabled=_archive_disabled,
            help="Move all currently legacy-invalid / invalid-metrics / missing-trades rows to archived-legacy.",
        ):
            with _LegacySession() as _sess:
                _result = archive_legacy_integrity_rows(_sess)
            st.success(
                f"Archived {_result['trades']} trade row(s) and {_result['backtest_runs']} "
                "backtest run(s) into `archived-legacy`."
            )
            st.rerun()

        _unarchive_disabled = (_archived["trades"] + _archived["backtest_runs"]) == 0
        if _btn_cols[1].button(
            "Unarchive legacy rows",
            key="legacy_unarchive_btn",
            disabled=_unarchive_disabled,
            help="Revert archived-legacy rows and re-classify them under current integrity rules.",
        ):
            with _LegacySession() as _sess:
                _reverted = unarchive_legacy_integrity_rows(_sess)
            st.warning(
                f"Reverted {_reverted['trades']} trade row(s) and {_reverted['backtest_runs']} "
                "backtest run(s) out of the archive."
            )
            st.rerun()

    with st.expander("Persistence & Recovery", expanded=False):
        st.caption(
            "Phase 1 continuity audit for restart survival. This checks the primary DB, "
            "runtime targets, registered artifacts, saved runs, and MVP-symbol freshness. "
            "State backups exclude `.env` secrets by default."
        )
        try:
            _restart_report = evaluate_restart_survival()
            _restart_metrics = build_restart_survival_metrics(_restart_report)
            _restart_cols = st.columns(4)
            _restart_cols[0].metric("Restart Status", _restart_metrics["restart_status"])
            _restart_cols[1].metric("Fresh MVP Symbols", _restart_metrics["mvp_fresh_label"])
            _restart_cols[2].metric("Artifacts", _restart_metrics["artifact_count"])
            _restart_cols[3].metric("Auditable Runs", _restart_metrics["auditable_runs"])

            if _restart_report["ready_for_restart"]:
                st.success(
                    "Current local state is restart-ready for the audited surfaces."
                )
            else:
                st.warning(
                    "Restart survival has operator-visible gaps. Review the issues below "
                    "before treating this environment as deployment-ready."
                )
                for _issue in _restart_report.get("issues") or []:
                    st.markdown(f"- {_issue}")

            _restart_frame = build_restart_survival_frame(_restart_report)
            if not _restart_frame.empty:
                st.dataframe(_restart_frame, width="stretch", hide_index=True)

            if st.button(
                "Create State Backup",
                key="create_state_backup_btn",
                help="Copy the current DB and registered strategy files into a timestamped local backup folder.",
            ):
                _backup = create_state_backup()
                st.success(
                    f"State backup created at `{_backup['backup_dir']}` with "
                    f"{len(_backup['copied_strategy_files'])} strategy file(s)."
                )
                st.caption(f"Manifest: `{_backup['manifest_path']}`")
        except Exception as _exc:
            st.warning(f"Persistence audit unavailable: {_exc}")

    with st.expander("Jetson Deployment Readiness", expanded=False):
        st.caption(
            "Pre-deploy operator check for running this workbench as a long-lived Jetson Nano paper-trading appliance. "
            "This does not start live trading or modify runtime targets."
        )
        try:
            _deploy_report = evaluate_jetson_readiness()
            _deploy_metrics = build_deployment_readiness_metrics(_deploy_report)
            _deploy_cols = st.columns(4)
            _deploy_cols[0].metric("Deployment Status", _deploy_metrics["status"])
            _deploy_cols[1].metric("Required Checks", _deploy_metrics["required_checks"])
            _deploy_cols[2].metric("Issues", _deploy_metrics["issues"])
            _deploy_cols[3].metric("Warnings", _deploy_metrics["warnings"])
            if _deploy_report.get("ready"):
                st.success("Jetson deployment assets and restart-survival checks are ready.")
            else:
                st.warning("Jetson deployment needs attention before production-style operation.")
                for _issue in _deploy_report.get("issues") or []:
                    st.caption(f"Issue: {_issue}")
            st.dataframe(build_deployment_readiness_frame(_deploy_report), width="stretch", hide_index=True)
            st.markdown("Operator commands")
            _commands = _deploy_report.get("commands") or {}
            st.code(
                "\n".join(
                    [
                        _commands.get("install", "bash deployment/install.sh"),
                        _commands.get("health", "python -m deployment.jetson_ops health"),
                        _commands.get("backup", "python -m deployment.jetson_ops backup"),
                        _commands.get("restore_dry_run", "python -m deployment.jetson_ops restore backups/<backup>/manifest.json"),
                    ]
                ),
                language="bash",
            )
        except Exception as _exc:
            st.warning(f"Jetson deployment readiness unavailable: {_exc}")

    with st.expander("Manual Agent Workflow", expanded=False):
        st.markdown(
            "1. Start from `strategies/_strategy_template.py` or revise a generated draft.\n"
            "2. Backtest the strategy in `Backtest Lab` until it has a passing evaluation.\n"
            "3. Save accepted drafts as reviewed plugins under a stable filename in `strategies/`.\n"
            "4. Only then set the strategy active for paper trading and restart runtime processes."
        )
        st.caption(
            "Reference files: `strategies/README.md`, `strategies/_strategy_template.py`, "
            "`strategies/example_rsi_mean_reversion.py`"
        )

    with st.expander("Create / Import Strategy Draft", expanded=bool(st.session_state.get("last_strategy_draft_result"))):
        sdk_support = strategy_sdk_support()
        st.caption(
            "Create a local draft without changing application code. Drafts are saved as generated strategy files, "
            "can be backtested immediately, and stay blocked from paper/live until reviewed as pinned plugins."
        )
        st.info(
            "Deployment strategy SDK lock: "
            f"current `{sdk_support['current_sdk_version']}` | supported "
            f"`{', '.join(sdk_support['supported_sdk_versions'])}` | signal contract "
            f"`{sdk_support['signal_contract']}`"
        )
        draft_files = list_generated_draft_files()
        draft_cols = st.columns([2, 1])
        draft_label = draft_cols[0].text_input(
            "Draft strategy name",
            value=st.session_state.get("draft_strategy_name", "custom_strategy_v1"),
            key="draft_strategy_name",
            help="Use lowercase letters, numbers, and underscores. Example: breakout_pullback_v1.",
        )
        draft_modes = ["Template", "Paste Code", "Upload .py"]
        if draft_files:
            draft_modes.append("Edit Existing Draft")
        draft_mode = draft_cols[1].selectbox(
            "Draft source",
            draft_modes,
            key="draft_source_mode",
        )
        uploaded_strategy = None
        selected_draft_file = None
        if draft_mode == "Upload .py":
            uploaded_strategy = st.file_uploader(
                "Upload strategy Python file",
                type=["py"],
                key="strategy_draft_upload",
            )
        elif draft_mode == "Edit Existing Draft":
            selected_draft_file = st.selectbox(
                "Existing generated draft",
                draft_files,
                format_func=lambda item: f"{item['file_name']} — {item.get('modified_at') or 'unknown modified time'}",
                key="strategy_existing_draft_file",
            )

        if uploaded_strategy is not None:
            draft_source = uploaded_strategy.getvalue().decode("utf-8", errors="replace")
        elif selected_draft_file is not None:
            try:
                existing_source = read_strategy_source_file(selected_draft_file["path"])
            except Exception as _exc:
                st.warning(f"Could not read selected draft: {_exc}")
                existing_source = strategy_template_source(draft_label)
            st.caption(
                "Editing an existing draft saves a new generated revision. Change the strategy `name` "
                "or `version` before saving if the catalog already contains this draft."
            )
            draft_source = st.text_area(
                "Strategy source",
                value=existing_source,
                height=420,
                key=f"strategy_existing_source_{selected_draft_file['file_name']}",
            )
        elif draft_mode == "Paste Code":
            draft_source = st.text_area(
                "Strategy source",
                value=st.session_state.get("strategy_paste_source", strategy_template_source(draft_label)),
                height=420,
                key="strategy_paste_source",
            )
        else:
            draft_source = st.text_area(
                "Strategy source",
                value=strategy_template_source(draft_label),
                height=420,
                key="strategy_template_source",
            )

        draft_action_cols = st.columns(3)
        if draft_action_cols[0].button("Validate Draft", key="validate_strategy_draft_btn", width="stretch"):
            st.session_state["last_strategy_draft_validation"] = validate_strategy_source(
                draft_source,
                file_name=f"{draft_label or 'draft'}.py",
                existing_catalog=strategy_catalog,
            ).as_dict()
        if draft_action_cols[1].button("Save Draft to strategies/", key="save_strategy_draft_btn", width="stretch"):
            draft_result = create_strategy_draft(
                draft_source,
                label=draft_label,
                existing_catalog=strategy_catalog,
            )
            st.session_state["last_strategy_draft_result"] = draft_result
            st.session_state["last_strategy_draft_validation"] = draft_result["validation"]
            if draft_result["saved"]:
                load_strategy_catalog.clear()
                load_strategy_errors.clear()
                st.cache_data.clear()
                strategy_names_saved = draft_result["validation"].get("strategy_names") or []
                if strategy_names_saved:
                    st.session_state["strategy_focus_pending"] = strategy_names_saved[0]
                st.success(f"Draft saved as `{draft_result['file_name']}`. It is backtest-only until reviewed.")
                st.rerun()
        if draft_action_cols[2].button("Refresh Strategy Registry", key="refresh_strategy_registry_btn", width="stretch"):
            load_strategy_catalog.clear()
            load_strategy_errors.clear()
            st.cache_data.clear()
            st.success("Strategy registry refresh queued.")
            st.rerun()

        draft_validation = st.session_state.get("last_strategy_draft_validation")
        if draft_validation:
            if draft_validation.get("valid"):
                names = ", ".join(draft_validation.get("strategy_names") or [])
                st.success(f"Draft contract is valid for: {names or 'strategy plugin'}.")
            else:
                st.error("Draft is not runnable yet. Fix the contract issues before saving.")
                strategy_names_for_suggestion = draft_validation.get("strategy_names") or []
                if strategy_names_for_suggestion:
                    st.info(
                        "Suggested next draft name: "
                        f"`{suggest_next_strategy_name(strategy_names_for_suggestion[0], strategy_catalog)}`"
                    )
            issues = draft_validation.get("issues") or []
            if issues:
                st.dataframe(pd.DataFrame(issues), width="stretch", hide_index=True)

        st.markdown("#### Strategy Packs")
        st.caption(
            "Portable zip bundles for moving strategies between deployed workbenches without editing application code. "
            "Imported packs still enter as backtest-only drafts until reviewed."
        )
        pack_candidates = [item for item in strategy_catalog if item.get("path")]
        pack_cols = st.columns(2)
        export_candidate = pack_cols[0].selectbox(
            "Export strategy pack",
            pack_candidates,
            format_func=lambda item: (
                f"{item.get('name')} ({format_strategy_origin(item)} · SDK {item.get('sdk_version') or '1'})"
            ),
            key="export_strategy_pack_candidate",
        ) if pack_candidates else None
        export_notes = pack_cols[1].text_area(
            "Pack notes",
            value=st.session_state.get("strategy_pack_notes", ""),
            key="strategy_pack_notes",
            height=120,
            help="Optional test notes, caveats, or setup instructions included as notes.md in the pack.",
        )
        if export_candidate is not None:
            try:
                pack_export = export_strategy_pack(export_candidate, notes=export_notes)
                st.download_button(
                    "Download Strategy Pack (.zip)",
                    data=pack_export["bytes"],
                    file_name=pack_export["file_name"],
                    mime="application/zip",
                    key="download_strategy_pack_btn",
                    width="stretch",
                )
                st.caption(
                    f"Pack includes `manifest.json`, `{pack_export['manifest'].get('source_file')}`, "
                    f"and `{pack_export['manifest'].get('notes_file') or 'no notes file'}`."
                )
            except Exception as _exc:
                st.warning(f"Strategy pack export unavailable: {_exc}")

        uploaded_pack = st.file_uploader(
            "Import strategy pack (.zip)",
            type=["zip"],
            key="strategy_pack_upload",
        )
        if uploaded_pack is not None:
            pack_preview = inspect_strategy_pack(uploaded_pack.getvalue(), filename=uploaded_pack.name)
            if pack_preview.get("valid"):
                pack_manifest = pack_preview.get("manifest") or {}
                pack_strategy = pack_manifest.get("strategy") or {}
                preview_cols = st.columns(4)
                preview_cols[0].metric("Pack Strategy", pack_strategy.get("name") or "Unknown")
                preview_cols[1].metric("Version", pack_strategy.get("version") or "Unknown")
                preview_cols[2].metric("SDK Version", pack_strategy.get("sdk_version") or "Unknown")
                preview_cols[3].metric("Format", pack_manifest.get("pack_format_version") or "Unknown")
                if pack_preview.get("notes"):
                    st.caption("Pack notes")
                    st.code(pack_preview["notes"], language="markdown")
                if st.button("Import Strategy Pack as Draft", key="import_strategy_pack_btn", width="stretch"):
                    pack_result = import_strategy_pack(
                        uploaded_pack.getvalue(),
                        filename=uploaded_pack.name,
                        existing_catalog=strategy_catalog,
                    )
                    st.session_state["last_strategy_draft_result"] = pack_result
                    st.session_state["last_strategy_draft_validation"] = pack_result["validation"]
                    if pack_result["saved"]:
                        load_strategy_catalog.clear()
                        load_strategy_errors.clear()
                        st.cache_data.clear()
                        strategy_names_saved = pack_result["validation"].get("strategy_names") or []
                        if strategy_names_saved:
                            st.session_state["strategy_focus_pending"] = strategy_names_saved[0]
                        st.success(
                            f"Strategy pack imported as `{pack_result['file_name']}`. "
                            "It is backtest-only until reviewed."
                        )
                        st.rerun()
            else:
                st.error("Strategy pack is not importable yet.")
                issues = pack_preview.get("issues") or []
                if issues:
                    st.dataframe(pd.DataFrame(issues), width="stretch", hide_index=True)

    with st.expander("Generate Strategy Draft", expanded=bool(st.session_state.get("last_generation_result"))):
        generation_ready = get_generation_readiness()
        status_cols = st.columns(3)
        status_cols[0].metric("Provider", f"{generation_ready['provider']} / {generation_ready['model']}")
        status_cols[1].metric("Status", str(generation_ready["status_label"]))
        status_cols[2].metric("Missing Env Var", generation_ready.get("missing_env_var") or "None")
        if generation_ready["ready"]:
            st.success("Strategy generation backend is configured and ready.")
        else:
            st.warning(str(generation_ready["reason"]))
        with st.form("generate_strategy_form", clear_on_submit=False):
            gen_description = st.text_area(
                "Strategy brief",
                placeholder="Example: Trend-following pullback strategy that buys when EMA-9 stays above EMA-21 and RSI recovers from 45 in trending markets.",
                disabled=not generation_ready["ready"],
            )
            gen_cols = st.columns(2)
            gen_symbol = gen_cols[0].selectbox(
                "Primary symbol",
                available_symbols,
                index=available_symbols.index(symbol) if symbol in available_symbols else 0,
                key="gen_symbol",
                disabled=not generation_ready["ready"],
            )
            gen_regime = gen_cols[1].selectbox(
                "Target regime",
                ["any", "RANGING", "TRENDING", "SQUEEZE", "HIGH_VOL"],
                key="gen_regime",
                disabled=not generation_ready["ready"],
            )
            generate_now = st.form_submit_button(
                "Generate Plugin Draft",
                type="primary",
                width="stretch",
                disabled=not generation_ready["ready"] or not strategy_names,
            )

        if generate_now:
            if not gen_description.strip():
                st.error("Strategy brief is required before generating a plugin draft.")
            else:
                with st.spinner("Generating strategy draft and loading plugin metadata..."):
                    generation_result = generate_and_discover_strategy(
                        gen_description.strip(),
                        symbol=gen_symbol,
                        regime_hint=gen_regime.lower(),
                    )
                st.session_state["last_generation_result"] = generation_result
                load_strategy_catalog.clear()
                load_strategy_errors.clear()
                st.cache_data.clear()
                if generation_result["load_status"] == "loaded" and generation_result["strategy_names"]:
                    st.session_state["strategy_focus_pending"] = generation_result["strategy_names"][0]
                    st.rerun()

        generation_result = st.session_state.get("last_generation_result")
        if generation_result:
            response_meta = generation_result.get("response", {})
            provider_label = f"{response_meta.get('provider', LLM_PROVIDER)} / {response_meta.get('model', LLM_MODEL)}"
            if generation_result["load_status"] == "loaded":
                st.success(
                    f"Generated `{', '.join(generation_result['strategy_names'])}` and loaded it into the strategy catalog."
                )
            elif generation_result["load_status"] == "generation_failed":
                st.error("Strategy generation failed. Check your LLM provider configuration or refine the strategy brief.")
            else:
                st.error("Strategy code was saved, but the plugin failed validation or discovery.")

            gen_meta_cols = st.columns(3)
            gen_meta_cols[0].metric("Provider", provider_label)
            gen_meta_cols[1].metric("Tokens", str(response_meta.get("tokens_used", 0)))
            gen_meta_cols[2].metric("Status", generation_result["load_status"].replace("_", " ").title())
            st.info(
                "Generated strategies are drafts by default. Review the file, run a backtest, and only promote "
                "to paper/live after saving a reviewed plugin copy."
            )

            if generation_result.get("file_name"):
                st.caption(f"Saved plugin file: `{generation_result['file_name']}`")
            if generation_result.get("errors"):
                st.dataframe(pd.DataFrame(generation_result["errors"]), width="stretch", hide_index=True)
            if generation_result.get("strategies"):
                st.dataframe(pd.DataFrame(generation_result["strategies"]), width="stretch", hide_index=True)
            if generation_result.get("code"):
                st.code(generation_result["code"], language="python")

    selected_strategy = st.selectbox(
        "Select backtest/default strategy",
        strategy_names,
        format_func=lambda name: next((item["display_name"] for item in strategy_catalog if item["name"] == name), name),
        key="active_strategy_selector",
    )
    st.session_state["strategy_focus_name"] = selected_strategy
    selected_meta = strategy_lookup.get(selected_strategy)
    if selected_meta:
        workflow_status = strategy_workflow_status(selected_meta, all_backtest_runs, active_strategy["name"])
        sdk_status = strategy_sdk_compatibility(selected_meta)
        selected_artifact_id = selected_meta.get("artifact_id")
        matching_runs = all_backtest_runs.copy() if not all_backtest_runs.empty else pd.DataFrame()
        if not matching_runs.empty:
            if selected_artifact_id and "artifact_id" in matching_runs.columns:
                matching_runs = matching_runs[matching_runs["artifact_id"] == selected_artifact_id]
            else:
                matching_runs = matching_runs[matching_runs["strategy_name"] == selected_strategy]
        passed_matching_runs = (
            matching_runs[matching_runs["status"].fillna("").astype(str).str.lower() == "passed"]
            if not matching_runs.empty and "status" in matching_runs.columns else pd.DataFrame()
        )
        latest_passing_run = passed_matching_runs.sort_values("created_at", ascending=False).head(1) if not passed_matching_runs.empty and "created_at" in passed_matching_runs.columns else passed_matching_runs.head(1)

        st.caption(selected_meta["description"])
        meta_cols = st.columns(5)
        meta_cols[0].metric("Origin", format_strategy_origin(selected_meta))
        meta_cols[1].metric("Version", selected_meta["version"])
        meta_cols[2].metric("Regimes", ", ".join(selected_meta["regimes"]) or "All")
        meta_cols[3].metric("SDK Version", sdk_status["sdk_version"])
        meta_cols[4].metric("Workflow Stage", workflow_status["stage"])
        lifecycle_cols = st.columns(4)
        lifecycle_cols[0].metric("Artifact Status", selected_meta.get("artifact_status", "") or "—")
        lifecycle_cols[1].metric("Paper Target", "Yes" if selected_meta.get("active_paper_artifact") else "No")
        lifecycle_cols[2].metric("Live Target", "Yes" if selected_meta.get("active_live_artifact") else "No")
        lifecycle_cols[3].metric(
            "Latest Passing Run",
            (
                f"#{int(latest_passing_run.iloc[0]['id'])}"
                if not latest_passing_run.empty and pd.notna(latest_passing_run.iloc[0].get("id"))
                else "—"
            ),
        )
        if selected_meta.get("file_name"):
            st.caption(f"File: `{selected_meta['file_name']}`")
        if selected_meta.get("path"):
            st.caption(f"Path: `{selected_meta['path']}`")
        if selected_meta.get("modified_at"):
            st.caption(f"Last modified: {selected_meta['modified_at']}")
        if selected_meta.get("artifact_code_hash"):
            st.caption(f"Artifact: `#{selected_meta['artifact_id']}` · hash `{selected_meta['artifact_code_hash'][:12]}` · provenance `{selected_meta.get('provenance', '')}`")
        review_cols = st.columns(4)
        review_cols[0].metric("Backtest Runs", str(workflow_status["run_count"]))
        review_cols[1].metric("Passed Runs", str(workflow_status["passed_runs"]))
        review_cols[2].metric("Failed Runs", str(workflow_status["failed_runs"]))
        review_cols[3].metric("SDK Compatibility", sdk_status["label"])
        st.info(workflow_status["next_step"])
        if sdk_status["compatible"]:
            st.caption(f"Strategy SDK compatibility: {sdk_status['reason']}")
        else:
            st.error(f"Strategy SDK compatibility: {sdk_status['reason']}")
        if selected_meta.get("is_generated"):
            st.warning("Generated plugin draft. Keep it in draft status until it passes backtesting and is reviewed as a stable plugin.")
        if selected_meta.get("default_params"):
            st.json(selected_meta["default_params"], expanded=False)

        review_name = ""
        if selected_meta.get("is_generated"):
            default_review_name = selected_meta["name"]
            if default_review_name.startswith("generated_"):
                default_review_name = default_review_name.removeprefix("generated_") or "reviewed_strategy_v1"
            if default_review_name == selected_meta["name"]:
                default_review_name = suggest_next_strategy_name(default_review_name, strategy_catalog)
            review_name = st.text_input(
                "Reviewed plugin name",
                value=default_review_name,
                key=f"review_name_{selected_strategy}",
                help="Creates a stable reviewed plugin filename and rewrites the strategy name so the draft and reviewed copy can coexist.",
            )

        action_cols = st.columns(4)
        if action_cols[0].button("Set Backtest Default", type="primary", width="stretch"):
            saved = set_active_strategy_config(selected_strategy)
            load_strategy_catalog.clear()
            load_strategy_errors.clear()
            st.cache_data.clear()
            st.success(
                f"Backtest default saved: {saved['name']} ({saved['version']}). "
                "Paper/live runtime now use promoted reviewed artifacts instead of this selector."
            )

        review_disabled = not (
            selected_meta.get("is_generated")
            and selected_meta.get("artifact_id")
            and sdk_status["compatible"]
        )
        if action_cols[1].button("Review and Save", width="stretch", disabled=review_disabled):
            try:
                reviewed = review_generated_strategy(int(selected_meta["artifact_id"]), review_name)
            except ValueError as exc:
                st.error(str(exc))
            else:
                load_strategy_catalog.clear()
                load_strategy_errors.clear()
                st.cache_data.clear()
                st.session_state["strategy_focus_pending"] = reviewed["strategy"]["name"]
                st.success(
                    f"Reviewed plugin saved as `{reviewed['strategy']['name']}` "
                    f"(artifact #{reviewed['artifact']['id']})."
                )
                st.rerun()

        can_promote_paper = (
            selected_meta.get("provenance") == "plugin"
            and selected_meta.get("artifact_id")
            and not passed_matching_runs.empty
            and sdk_status["compatible"]
        )
        if action_cols[2].button("Promote to Paper", width="stretch", disabled=not can_promote_paper):
            try:
                promoted = promote_artifact_to_paper(int(selected_meta["artifact_id"]))
            except ValueError as exc:
                st.error(str(exc))
            else:
                load_strategy_catalog.clear()
                st.cache_data.clear()
                st.success(f"Paper target set to `{selected_strategy}` (artifact #{promoted['id']}).")
                st.rerun()

        can_approve_live = (
            selected_meta.get("provenance") == "plugin"
            and selected_meta.get("artifact_id")
            and str(selected_meta.get("artifact_status") or "").lower() in {"paper_passed", "live_approved", "live_active"}
            and sdk_status["compatible"]
        )
        if action_cols[3].button("Approve for Live", width="stretch", disabled=not can_approve_live):
            try:
                approved = approve_artifact_for_live(int(selected_meta["artifact_id"]))
            except ValueError as exc:
                st.error(str(exc))
            else:
                load_strategy_catalog.clear()
                st.cache_data.clear()
                st.success(f"Live target approved for `{selected_strategy}` (artifact #{approved['id']}).")
                st.rerun()

        can_evaluate_paper = (
            selected_meta.get("provenance") == "plugin"
            and selected_meta.get("artifact_id")
            and str(selected_meta.get("artifact_status") or "").lower() in {"paper_active", "paper_passed", "live_approved", "live_active"}
            and sdk_status["compatible"]
        )
        eval_cols = st.columns([1, 3])
        evidence_result = None
        evidence_summary = None
        if selected_meta.get("provenance") == "plugin" and selected_meta.get("artifact_id"):
            evidence_result = evaluate_paper_evidence(int(selected_meta["artifact_id"]))
            evidence_summary = build_paper_evidence_summary(evidence_result)

        if eval_cols[0].button(
            "Evaluate for Paper Pass",
            width="stretch",
            disabled=not can_evaluate_paper,
            help="Grades real paper-trade evidence against the deterministic threshold gate "
                 "(min trades, runtime span, Sharpe, profit factor, max drawdown). "
                 "Promotes to `paper_passed` only if every check passes.",
        ):
            from strategy.artifacts import mark_artifact_paper_passed as _mark_paper_passed
            evidence = evidence_result or evaluate_paper_evidence(int(selected_meta["artifact_id"]))
            if not evidence.passed:
                eval_cols[1].error(
                    "Paper evidence gate failed:\n- " + "\n- ".join(evidence.reasons)
                )
                with eval_cols[1].expander("Metrics seen by the gate"):
                    st.json(evidence.as_dict())
            else:
                try:
                    _mark_paper_passed(int(selected_meta["artifact_id"]))
                except ValueError as exc:
                    eval_cols[1].error(str(exc))
                else:
                    load_strategy_catalog.clear()
                    st.cache_data.clear()
                    eval_cols[1].success(
                        f"`{selected_strategy}` promoted to `paper_passed` "
                        f"(Sharpe {evidence.metrics['sharpe']:.2f}, "
                        f"PF {evidence.metrics['profit_factor']:.2f}, "
                        f"DD {evidence.metrics['max_drawdown']:.1%}, "
                        f"{int(evidence.metrics['n_trades'])} trades over "
                        f"{evidence.runtime_days:.1f}d). Approve for Live is now unlocked."
                    )
                    st.rerun()

        if evidence_summary is not None:
            st.markdown("##### Paper Evidence Progress")
            st.caption(
                "Deterministic gate over real paper SELL trades tagged with this artifact. "
                "Promotion to `paper_passed` remains blocked until all checks are met."
            )
            evidence_metrics = build_paper_evidence_metrics(evidence_summary)
            evidence_metric_cols = st.columns(4)
            evidence_metric_cols[0].metric("Gate Status", evidence_metrics["gate_status"])
            evidence_metric_cols[1].metric("SELL Trades", evidence_metrics["trade_progress"])
            evidence_metric_cols[2].metric("Runtime Span", evidence_metrics["runtime_progress"])
            evidence_metric_cols[3].metric("Profit Factor", evidence_metrics["profit_factor"])

            if evidence_result and evidence_result.passed:
                st.success(
                    "Real paper evidence now satisfies the deterministic gate for this artifact."
                )
            elif bool(selected_meta.get("active_paper_artifact")) and evidence_summary["stage"] == "waiting-for-first-close":
                st.info(
                    "This is the active paper target, but it has not closed a tagged paper SELL trade yet. "
                    "The gate is waiting for the first realised paper result."
                )
            elif bool(selected_meta.get("active_paper_artifact")):
                st.warning(
                    "This artifact is the active paper target, but the evidence gate still has remaining blockers."
                )
            else:
                st.caption(
                    "Paper evidence matters only after the artifact is promoted to paper. "
                    "Until then, this panel is a dry-read of the same gate the paper target will use."
                )

            if evidence_summary.get("reasons"):
                st.markdown("**Current blockers**")
                for _reason in evidence_summary["reasons"]:
                    st.markdown(f"- {_reason}")

            evidence_frame = build_paper_evidence_checklist_frame(evidence_summary)
            if not evidence_frame.empty:
                st.dataframe(evidence_frame, width="stretch", hide_index=True)

            if evidence_summary.get("first_trade_ts") or evidence_summary.get("last_trade_ts"):
                st.caption(
                    f"First paper SELL: `{evidence_summary.get('first_trade_ts') or '—'}` · "
                    f"Last paper SELL: `{evidence_summary.get('last_trade_ts') or '—'}`"
                )

        _artifact_status = str(selected_meta.get("artifact_status") or "").lower()
        _is_paper_target = bool(selected_meta.get("active_paper_artifact"))
        _is_live_target = bool(selected_meta.get("active_live_artifact"))
        if _is_paper_target:
            st.success(f"Paper target active — `{selected_strategy}` is the current paper trading strategy.")
        if _is_live_target:
            st.success(f"Live target active — `{selected_strategy}` is the current live trading strategy.")
        if selected_meta.get("is_generated"):
            st.caption(
                "**Promote to Paper / Approve for Live are disabled** for generated drafts. "
                "Use **Review and Save** to create a stable reviewed plugin, then backtest it."
            )
            if not sdk_status["compatible"]:
                st.caption(
                    "**Review and Save is blocked** — this draft targets an unsupported SDK version. "
                    "Update the draft to the deployed SDK contract before reviewing it into a plugin."
                )
        elif selected_meta.get("provenance") != "plugin":
            st.caption(
                "**Promote to Paper / Approve for Live are only available for plugin strategies.** "
                "Built-in strategies cannot be promoted."
            )
        elif not sdk_status["compatible"]:
            st.caption(
                f"**Paper/Live actions are blocked** — strategy SDK `{sdk_status['sdk_version']}` is unsupported by the deployed app."
            )
        elif passed_matching_runs.empty:
            st.caption(
                "**Promote to Paper is blocked** — this artifact has no passing saved backtests. "
                "Run a backtest and ensure it passes the performance gate first."
            )
        if _artifact_status not in {"paper_passed", "live_approved", "live_active"}:
            st.caption(
                f"**Approve for Live is blocked** — artifact status is `{_artifact_status or 'unknown'}`. "
                "Approve for Live unlocks only after the paper artifact reaches `paper_passed` status."
            )

    catalog_df = build_strategy_catalog_frame(strategy_catalog, all_backtest_runs, active_strategy["name"])
    st.dataframe(catalog_df, width="stretch", hide_index=True)

    if strategy_errors:
        st.warning("Plugin load issues detected")
        st.dataframe(pd.DataFrame(strategy_errors), width="stretch", hide_index=True)

with backtest_tab:
    st.markdown("### Backtest Lab")
    selector_cols = st.columns(2)
    _prefill_sym = st.session_state.pop("focus_prefill_symbol", None)
    _bt_sym_default = (
        str(_prefill_sym).strip().upper()
        if _prefill_sym
        else choose_backtest_default_symbol(
            symbol,
            tuple(ready_symbols),
            ready_symbol_health,
            tuple(mvp_research_universe),
        )
    )
    _bt_sym_options = ready_symbols if _bt_sym_default in ready_symbols else [_bt_sym_default] + list(ready_symbols)
    bt_symbol = selector_cols[0].selectbox(
        "Backtest Symbol",
        _bt_sym_options,
        index=0 if _prefill_sym else (_bt_sym_options.index(_bt_sym_default) if _bt_sym_default in _bt_sym_options else 0),
        key="bt_symbol",
    )
    bt_strategy = selector_cols[1].selectbox(
        "Backtest Strategy",
        strategy_names,
        key="bt_strategy",
    )
    selected_bt_meta = strategy_lookup.get(bt_strategy)
    bt_default_params = normalise_params(selected_bt_meta.get("default_params", {}) if selected_bt_meta else {})
    bt_param_schema = list(selected_bt_meta.get("param_schema", []) if selected_bt_meta else [])
    bt_params = dict(bt_default_params)
    preset_flash = st.session_state.pop("backtest_preset_flash", "")
    if preset_flash:
        st.success(preset_flash)

    presets_df = load_backtest_presets(bt_strategy)
    presets_view = build_backtest_preset_frame(presets_df)
    preset_options = ["Custom"]
    if not presets_view.empty and "preset_name" in presets_view.columns:
        preset_options.extend(presets_view["preset_name"].astype(str).tolist())

    preset_select_key = f"bt_preset_choice_{bt_strategy}"
    active_preset_key = f"bt_active_preset_{bt_strategy}"
    if st.session_state.get(preset_select_key) not in preset_options:
        st.session_state[preset_select_key] = "Custom"
    if st.session_state.get(active_preset_key) not in preset_options:
        st.session_state[active_preset_key] = ""

    if bt_param_schema:
        st.markdown("#### Scenario Presets")
        st.caption("Named presets sit on top of run-scoped params. Applying a preset updates the form; saved runs still keep the exact params payload.")
        preset_cols = st.columns([2, 1])
        selected_preset_name = preset_cols[0].selectbox(
            "Preset",
            preset_options,
            key=preset_select_key,
        )
        apply_preset_now = preset_cols[1].button(
            "Apply Preset",
            width="stretch",
            disabled=selected_preset_name == "Custom",
        )
        if apply_preset_now and selected_preset_name != "Custom":
            preset_row = presets_view[presets_view["preset_name"] == selected_preset_name].head(1)
            if not preset_row.empty:
                preset_payload = preset_row.iloc[0].get("params", {})
                apply_backtest_params_to_session(bt_strategy, bt_param_schema, preset_payload, bt_default_params)
                st.session_state[active_preset_key] = selected_preset_name
                st.session_state["backtest_preset_flash"] = f"Applied preset `{selected_preset_name}`."
                st.rerun()

        st.markdown("#### Scenario Parameters")
        st.caption("Backtest-only in Sprint 24. These values are saved with the run and can optionally be attached to a named preset.")
        param_cols = st.columns(2)
        for idx, field in enumerate(bt_param_schema):
            with param_cols[idx % 2]:
                field_name = str(field.get("name", "")).strip()
                if not field_name:
                    continue
                bt_params[field_name] = render_strategy_param_control(bt_strategy, field, bt_default_params)

        matched_preset_name = find_matching_preset_name(bt_params, presets_view)
        st.session_state[active_preset_key] = matched_preset_name
        if matched_preset_name:
            st.caption(f"Preset match: **{matched_preset_name}**")
        else:
            st.caption("Preset match: **Custom scenario**")

        save_cols = st.columns([2, 1])
        save_name_key = f"bt_preset_save_name_{bt_strategy}"
        preset_name_input = save_cols[0].text_input(
            "Save current params as preset",
            key=save_name_key,
            placeholder="Example: Mean Reversion Pullback A",
        )
        save_preset_now = save_cols[1].button(
            "Save Preset",
            width="stretch",
            disabled=not preset_name_input.strip(),
        )
        if save_preset_now:
            saved_preset = save_backtest_preset(bt_strategy, preset_name_input, bt_params)
            load_backtest_presets.clear()
            st.session_state[preset_select_key] = saved_preset["preset_name"]
            st.session_state[active_preset_key] = saved_preset["preset_name"]
            st.session_state[save_name_key] = saved_preset["preset_name"]
            st.session_state["backtest_preset_flash"] = f"Saved preset `{saved_preset['preset_name']}` for `{bt_strategy}`."
            st.rerun()

        if not presets_view.empty:
            display_presets = presets_view.copy()
            if "updated_at" in display_presets.columns:
                display_presets["updated_at"] = pd.to_datetime(display_presets["updated_at"]).dt.strftime("%Y-%m-%d %H:%M")
            if "created_at" in display_presets.columns:
                display_presets["created_at"] = pd.to_datetime(display_presets["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(
                display_presets[["preset_name", "scenario_label", "params_summary", "updated_at", "created_at"]],
                width="stretch",
                hide_index=True,
            )
        else:
            st.info(f"No named presets saved yet for `{bt_strategy}`.")

    _latest_candle_dt = get_latest_candle_time(bt_symbol)
    _selected_symbol_health = next((item for item in ready_symbol_health if item.get("symbol") == bt_symbol), None)
    _selected_age_minutes = _selected_symbol_health.get("age_minutes") if _selected_symbol_health else None
    _selected_fresh = bool(_selected_symbol_health and _selected_symbol_health.get("is_fresh"))
    _latest_complete_day = latest_complete_backtest_day(_latest_candle_dt) if _latest_candle_dt is not None else None
    _bt_start_default, _bt_end_default, _bt_window_known_runnable = choose_backtest_default_window(
        bt_symbol,
        _latest_candle_dt,
        ready_symbol_health,
        min_history_days=MVP_MIN_HISTORY_DAYS,
    )
    _window_status_text = (
        f"Latest complete runnable window for **{bt_symbol}**: "
        f"`{_bt_start_default.isoformat()}` -> `{_bt_end_default.isoformat()}`."
        if _bt_window_known_runnable
        else (
            f"Latest known candle day for **{bt_symbol}**: `{_bt_end_default.isoformat()}`. "
            "A guaranteed runnable window has not been confirmed yet."
        )
    )
    if _latest_candle_dt:
        st.caption(
            f"Latest local candle for **{bt_symbol}**: `{_latest_candle_dt.isoformat()}` · "
            f"latest complete backtest day: `{_latest_complete_day.isoformat()}` — "
            "Backtest Lab defaults to the latest known runnable window when one is available."
        )
    else:
        st.caption(f"No candle data found for **{bt_symbol}** — defaulting to the latest completed UTC day.")
    st.info(_window_status_text)
    date_cols = st.columns(2)
    bt_start = date_cols[0].date_input("Backtest Start", value=_bt_start_default)
    bt_end = date_cols[1].date_input("Backtest End", value=_bt_end_default)
    bt_start_dt = datetime.combine(bt_start, datetime.min.time())
    bt_end_dt = datetime.combine(bt_end, datetime.min.time())
    audit_result = load_symbol_audit(bt_symbol, bt_start_dt.isoformat(), bt_end_dt.isoformat())
    _freshness_label = "Fresh" if _selected_fresh else f"Stale ({format_data_age(_selected_age_minutes)})"
    _window_status_label = "Runnable" if audit_result["is_complete"] else "Blocked"
    st.info(
        f"Health gate · latest candle age `{format_data_age(_selected_age_minutes)}` · "
        f"freshness `{_freshness_label}` · current window `{_window_status_label}`"
    )
    if _selected_age_minutes is None:
        st.error(
            f"`{bt_symbol}` has no local candle data. Load or sync history before treating this symbol as part of the MVP research universe."
        )
    elif not _selected_fresh:
        st.error(
            f"`{bt_symbol}` is stale by `{format_data_age(_selected_age_minutes)}`. Historical research may still be useful, "
            "but MVP paper-readiness is blocked until fresh candles are synced."
        )
    audit_cols = st.columns([4, 1])
    st.markdown("#### History Audit")
    if audit_result["is_complete"]:
        audit_cols[0].success(format_audit_summary(audit_result))
    else:
        audit_cols[0].warning(format_audit_summary(audit_result))
    if audit_cols[1].button("Backfill Range", width="stretch"):
        with st.spinner(f"Backfilling {bt_symbol}..."):
            backfill_history(bt_symbol, bt_start_dt, bt_end_dt, interval="1m")
        load_candles_raw.clear()
        load_symbol_audit.clear()
        load_ready_symbol_health.clear()
        st.success(f"Backfill complete for {bt_symbol}.")
        st.rerun()
    matched_preset_name = find_matching_preset_name(bt_params, presets_view)
    current_scenario_label = format_scenario_label(bt_params, matched_preset_name)
    st.caption(f"Scenario: **{current_scenario_label}**")
    if matched_preset_name:
        st.caption(f"Preset: **{matched_preset_name}**")
    if bt_params:
        st.json(bt_params, expanded=False)
    run_backtest_now = st.button("Run Backtest", type="primary", width="stretch")

    if selected_bt_meta:
        bt_workflow_status = strategy_workflow_status(selected_bt_meta, all_backtest_runs, active_strategy["name"])
        st.caption(
            f"Evaluating `{selected_bt_meta['name']}` · {format_strategy_origin(selected_bt_meta)} · "
            f"v{selected_bt_meta['version']}"
        )
        st.caption(f"Workflow stage: **{bt_workflow_status['stage']}**")
        if selected_bt_meta.get("is_generated"):
            st.info("This is a generated plugin draft. Use the saved runs below to decide whether it is ready to be reviewed into a stable plugin.")
        else:
            st.info(bt_workflow_status["next_step"])

    if not audit_result["is_complete"]:
        st.error(
            f"**Backtest blocked — incomplete history for {bt_symbol}** "
            f"({bt_start} → {bt_end}). "
            f"{format_audit_summary(audit_result)} "
            "Use the **Backfill Range** button above to fetch the missing candles, then re-run."
        )

    backtest_attempt_state = st.session_state.get("backtest_attempt_state")

    if run_backtest_now:
        if not audit_result["is_complete"]:
            backtest_attempt_state = {
                "status": "blocked-history",
                "strategy_name": bt_strategy,
                "symbol": bt_symbol,
                "window": f"{bt_start} → {bt_end}",
                "detail": (
                    f"History is incomplete for {bt_symbol} over the selected window. "
                    "Use Backfill Range, then run the backtest again."
                ),
                "recorded_at": datetime.now().strftime("%H:%M:%S"),
            }
            st.session_state["backtest_attempt_state"] = backtest_attempt_state
            st.warning(
                f"Run Backtest is blocked: history for **{bt_symbol}** is incomplete over the selected window. "
                "Backfill the missing range first."
            )
        else:
            try:
                with st.spinner("Running backtest and persisting result..."):
                    result = run_and_persist_backtest(
                        bt_symbol,
                        bt_start_dt,
                        bt_end_dt,
                        bt_strategy,
                        params=bt_params,
                        preset_name=matched_preset_name,
                    )
            except ValueError as exc:
                backtest_attempt_state = {
                    "status": "blocked-validation",
                    "strategy_name": bt_strategy,
                    "symbol": bt_symbol,
                    "window": f"{bt_start} → {bt_end}",
                    "detail": str(exc),
                    "recorded_at": datetime.now().strftime("%H:%M:%S"),
                }
                st.session_state["backtest_attempt_state"] = backtest_attempt_state
                st.error(f"Backtest validation failed: {exc}")
                result = None
            except Exception as exc:
                backtest_attempt_state = {
                    "status": "run-failed",
                    "strategy_name": bt_strategy,
                    "symbol": bt_symbol,
                    "window": f"{bt_start} → {bt_end}",
                    "detail": str(exc),
                    "recorded_at": datetime.now().strftime("%H:%M:%S"),
                }
                st.session_state["backtest_attempt_state"] = backtest_attempt_state
                st.error(f"Backtest run failed unexpectedly: {exc}")
                result = None
            else:
                if result is not None:
                    backtest_attempt_state = {
                        "status": "saved-run",
                        "strategy_name": bt_strategy,
                        "symbol": bt_symbol,
                        "window": f"{bt_start} → {bt_end}",
                        "detail": f"Backtest run #{result['run_id']} saved.",
                        "run_id": int(result["run_id"]),
                        "recorded_at": datetime.now().strftime("%H:%M:%S"),
                    }
                    st.session_state["backtest_attempt_state"] = backtest_attempt_state
                    st.session_state["selected_backtest_run_id"] = result["run_id"]
                    st.session_state["inspect_run_label"] = int(result["run_id"])
                    load_backtest_runs.clear()
                    load_symbol_audit.clear()
                    load_backtest_run.clear()
                    load_backtest_trades.clear()
                    st.success(f"Backtest run #{result['run_id']} saved.")
                else:
                    backtest_attempt_state = {
                        "status": "run-failed",
                        "strategy_name": bt_strategy,
                        "symbol": bt_symbol,
                        "window": f"{bt_start} → {bt_end}",
                        "detail": "Backtest returned no result. Check the strategy and date range.",
                        "recorded_at": datetime.now().strftime("%H:%M:%S"),
                    }
                    st.session_state["backtest_attempt_state"] = backtest_attempt_state
                    st.error("Backtest returned no result. Check the strategy and date range.")

    if backtest_attempt_state:
        st.markdown("#### Last Backtest Attempt")
        st.caption(
            f"{backtest_attempt_state.get('recorded_at', '—')} · "
            f"`{backtest_attempt_state.get('strategy_name', '—')}` · "
            f"`{backtest_attempt_state.get('symbol', '—')}` · "
            f"{backtest_attempt_state.get('window', '—')}"
        )
        attempt_status = str(backtest_attempt_state.get("status") or "")
        attempt_detail = str(backtest_attempt_state.get("detail") or "").strip()
        if attempt_status == "saved-run":
            st.success(attempt_detail)
        elif attempt_status == "blocked-history":
            st.warning(f"Blocked by history: {attempt_detail}")
        elif attempt_status == "blocked-validation":
            st.warning(f"Blocked by validation: {attempt_detail}")
        else:
            st.error(f"Run failed: {attempt_detail}")

    runs_df = load_backtest_runs()
    all_backtest_runs = runs_df
    comparison_df = build_strategy_comparison_frame(runs_df, strategy_catalog, active_strategy["name"])
    selected_strategy_row = comparison_df[comparison_df["strategy_name"] == bt_strategy].head(1)
    evaluated_strategies = comparison_df[comparison_df["run_count"] > 0].copy() if not comparison_df.empty else pd.DataFrame()
    leading_strategy_row = evaluated_strategies.head(1)

    if not comparison_df.empty:
        comparison_cols = st.columns(4)
        comparison_cols[0].metric("Compared Scenarios", str(int(len(evaluated_strategies))))
        comparison_cols[1].metric(
            "Passing Candidates",
            str(int((comparison_df["passed_runs"].fillna(0) > 0).sum())),
        )
        comparison_cols[2].metric(
            "Current Leader",
            (
                f"{leading_strategy_row.iloc[0]['display_name']} · {leading_strategy_row.iloc[0]['scenario_label']}"
                if not leading_strategy_row.empty else "—"
            ),
        )
        comparison_cols[3].metric(
            "Focus Rank",
            f"#{int(selected_strategy_row.iloc[0]['rank'])}" if not selected_strategy_row.empty else "—",
        )

    if not selected_strategy_row.empty:
        focus_summary = selected_strategy_row.iloc[0]
        focus_cols = st.columns(4)
        focus_cols[0].metric("Saved Runs", str(int(focus_summary["run_count"])))
        focus_cols[1].metric("Pass Rate", f"{float(focus_summary['pass_rate']):.0%}")
        focus_cols[2].metric(
            "Best Sharpe",
            f"{float(focus_summary['best_sharpe']):.2f}" if pd.notna(focus_summary["best_sharpe"]) else "—",
        )
        focus_cols[3].metric(
            "Best Scenario",
            str(focus_summary["scenario_label"]),
        )
        st.caption(
            f"`{bt_strategy}` is ranked #{int(focus_summary['rank'])} in saved evaluations. "
            f"Latest outcome: {focus_summary['latest_status']}."
        )

    if not comparison_df.empty:
        st.markdown("#### Candidate Comparison")
        display_comparison = comparison_df.copy()
        if "latest_run_at" in display_comparison.columns:
            display_comparison["latest_run_at"] = pd.to_datetime(display_comparison["latest_run_at"]).dt.strftime("%Y-%m-%d %H:%M")
            display_comparison["latest_run_at"] = display_comparison["latest_run_at"].fillna("—")
        display_comparison["pass_rate"] = display_comparison["pass_rate"].apply(lambda value: f"{float(value):.0%}")
        for col in ["best_sharpe", "best_profit_factor"]:
            if col in display_comparison.columns:
                display_comparison[col] = display_comparison[col].apply(
                    lambda value: f"{float(value):.2f}" if pd.notna(value) else "—"
                )
        if "lowest_max_drawdown" in display_comparison.columns:
            display_comparison["lowest_max_drawdown"] = display_comparison["lowest_max_drawdown"].apply(
                lambda value: f"{float(value):.1%}" if pd.notna(value) else "—"
            )
        if "best_run_id" in display_comparison.columns:
            display_comparison["best_run_id"] = display_comparison["best_run_id"].apply(
                lambda value: f"#{int(value)}" if pd.notna(value) else "—"
            )
        display_comparison["is_active"] = display_comparison["is_active"].apply(lambda value: "Yes" if value else "")
        st.dataframe(
            display_comparison[
                [
                    "rank",
                    "display_name",
                    "strategy_name",
                    "scenario_label",
                    "origin",
                    "workflow_stage",
                    "is_active",
                    "run_count",
                    "passed_runs",
                    "pass_rate",
                    "best_sharpe",
                    "best_profit_factor",
                    "lowest_max_drawdown",
                    "latest_status",
                    "latest_symbol",
                    "latest_run_at",
                    "best_run_id",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

    st.checkbox("Show all saved runs", key="show_all_backtest_runs")
    visible_runs_df = filter_backtest_runs(runs_df, bt_strategy, show_all=st.session_state["show_all_backtest_runs"])
    leaderboard_df = build_backtest_run_leaderboard(visible_runs_df)
    if not visible_runs_df.empty:
        display_runs = leaderboard_df.copy()
        if "created_at" in display_runs.columns:
            display_runs["created_at"] = pd.to_datetime(display_runs["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
        if "start_ts" in display_runs.columns:
            display_runs["start_ts"] = pd.to_datetime(display_runs["start_ts"]).dt.strftime("%Y-%m-%d")
        if "end_ts" in display_runs.columns:
            display_runs["end_ts"] = pd.to_datetime(display_runs["end_ts"]).dt.strftime("%Y-%m-%d")
        if "max_drawdown" in display_runs.columns:
            display_runs["max_drawdown"] = display_runs["max_drawdown"].apply(
                lambda value: f"{float(value):.1%}" if pd.notna(value) else "—"
            )
        if "integrity_status" in display_runs.columns:
            display_runs["integrity"] = display_runs["integrity_status"].apply(integrity_label)
        else:
            display_runs["integrity"] = "Valid"
        for col in ["sharpe", "profit_factor"]:
            if col in display_runs.columns:
                display_runs[col] = display_runs[col].apply(
                    lambda value: f"{float(value):.2f}" if pd.notna(value) else "—"
                )
        st.markdown("#### Saved Run Leaderboard")
        st.dataframe(
            display_runs[
                [
                    "rank",
                    "id",
                    "status_label",
                    "integrity",
                    "scenario_label",
                    "symbol",
                    "start_ts",
                    "end_ts",
                    "sharpe",
                    "max_drawdown",
                    "profit_factor",
                    "n_trades",
                    "created_at",
                    "failure_summary",
                ]
            ],
            width="stretch",
            hide_index=True,
        )
        available_run_ids = leaderboard_df["id"].astype(int).tolist()
        selected_run_id = st.selectbox(
            "Inspect saved run",
            available_run_ids,
            index=0 if "selected_backtest_run_id" not in st.session_state or st.session_state["selected_backtest_run_id"] not in available_run_ids
            else available_run_ids.index(st.session_state["selected_backtest_run_id"]),
            key="selected_backtest_run_id",
            format_func=lambda run_id: (
                f"#{run_id} · "
                f"{leaderboard_df.loc[leaderboard_df['id'] == run_id, 'strategy_name'].iloc[0]} · "
                f"{leaderboard_df.loc[leaderboard_df['id'] == run_id, 'scenario_label'].iloc[0]} · "
                f"{leaderboard_df.loc[leaderboard_df['id'] == run_id, 'symbol'].iloc[0]} · "
                f"{leaderboard_df.loc[leaderboard_df['id'] == run_id, 'status_label'].iloc[0]}"
            ),
        )
        selected_run = load_backtest_run(int(selected_run_id)) or leaderboard_df[leaderboard_df["id"] == selected_run_id].iloc[0].to_dict()
        selected_run_trades = load_backtest_trades(int(selected_run_id))
        selected_run_equity = compute_trade_equity_curve(selected_run_trades)
        selected_run_drawdown = compute_drawdown_curve(selected_run_equity)

        st.markdown("#### Run Summary")
        metric_cols = st.columns(6)
        metric_cols[0].metric("Strategy", selected_run.get("strategy_name", "—"))
        metric_cols[1].metric("Version", selected_run.get("strategy_version") or "—")
        metric_cols[2].metric("Sharpe", f"{float(selected_run.get('sharpe', 0.0)):.2f}")
        metric_cols[3].metric("Max DD", f"{float(selected_run.get('max_drawdown', 0.0)):.1%}")
        metric_cols[4].metric("PF", f"{float(selected_run.get('profit_factor', 0.0)):.2f}")
        metric_cols[5].metric("Trades", f"{int(selected_run.get('n_trades', 0))}")
        st.caption(f"Scenario: **{format_scenario_label(selected_run.get('params'), selected_run.get('preset_name'))}**")
        if normalise_preset_name(selected_run.get("preset_name")):
            st.caption(f"Preset: **{normalise_preset_name(selected_run.get('preset_name'))}**")
        if selected_run.get("params"):
            st.json(selected_run["params"], expanded=False)

        if selected_run.get("failures"):
            failures = selected_run["failures"]
            if isinstance(failures, list):
                st.warning("Acceptance gate failures: " + "; ".join(failures))
            else:
                st.warning(f"Acceptance gate failures: {failures}")
        else:
            st.success(f"Acceptance gate: {str(selected_run.get('status', 'completed')).upper()}")

        st.caption(
            f"Window: {to_utc_naive_timestamp(selected_run.get('start_ts')).strftime('%Y-%m-%d')} "
            f"→ {to_utc_naive_timestamp(selected_run.get('end_ts')).strftime('%Y-%m-%d')}"
        )

        selected_start_ts = to_utc_naive_timestamp(selected_run["start_ts"])
        selected_end_ts = to_utc_naive_timestamp(selected_run["end_ts"])
        now_ts = to_utc_naive_timestamp(pd.Timestamp.utcnow())
        candle_df = load_candles_raw(
            str(selected_run["symbol"]),
            max((now_ts - selected_start_ts).days + 2, 2),
        )
        enriched_candles = enrich_chart_studies(candle_df) if not candle_df.empty else pd.DataFrame()
        filtered_candles = enriched_candles[
            (enriched_candles["open_time"] >= selected_start_ts)
            & (enriched_candles["open_time"] <= selected_end_ts)
        ] if not enriched_candles.empty else pd.DataFrame()
        if not filtered_candles.empty:
            backtest_chart_payload = build_trading_chart_payload(
                filtered_candles,
                selected_run_trades,
                symbol=str(selected_run["symbol"]),
                timeframe="Backtest",
                strategy_name=str(selected_run.get("strategy_name", "")),
                context_label=f"Run #{selected_run_id}",
                show_fast_emas=show_fast_emas,
                show_ema_200=show_ema_200,
                show_bbands=show_bbands,
                show_rsi=show_rsi,
                show_macd=show_macd,
            )
            render_responsive_chart(
                backtest_chart_payload,
                chart_id=f"backtest-{selected_run_id}",
                height=560,
            )
        else:
            st.info("No candle data is available locally for this saved backtest window.")

        if not selected_run_trades.empty:
            lower_left, lower_right = st.columns(2)
            with lower_left:
                eq_fig = go.Figure()
                eq_fig.add_trace(go.Scatter(
                    x=selected_run_equity["step"],
                    y=selected_run_equity["equity"],
                    mode="lines",
                    name="Equity",
                    line=dict(color="#2962ff", width=2),
                    fill="tozeroy",
                    fillcolor="rgba(41,98,255,0.10)",
                ))
                eq_fig.update_layout(
                    title="Backtest Equity Curve",
                    height=240,
                    paper_bgcolor="#0e1117",
                    plot_bgcolor="#0e1117",
                    font=dict(color="#d1d4dc"),
                )
                st.plotly_chart(eq_fig, width="stretch")

            with lower_right:
                dd_fig = go.Figure()
                dd_fig.add_trace(go.Scatter(
                    x=selected_run_drawdown["step"],
                    y=selected_run_drawdown["drawdown"],
                    mode="lines",
                    name="Drawdown",
                    line=dict(color="#ff7043", width=2),
                    fill="tozeroy",
                    fillcolor="rgba(255,112,67,0.12)",
                ))
                dd_fig.update_layout(
                    title="Backtest Drawdown",
                    height=240,
                    paper_bgcolor="#0e1117",
                    plot_bgcolor="#0e1117",
                    font=dict(color="#d1d4dc"),
                    yaxis_tickformat=".1%",
                )
                st.plotly_chart(dd_fig, width="stretch")

            st.markdown("#### Trade Log")
            st.dataframe(selected_run_trades, width="stretch", hide_index=True)
    elif not runs_df.empty:
        st.info(f"No saved runs yet for `{bt_strategy}`. Run a backtest to start its evaluation history or enable 'Show all saved runs'.")
    else:
        st.info("No backtest runs have been saved yet. Run the selected strategy to start its evaluation history.")

with runtime_tab:
    _runtime_renderer = build_runtime_monitor_renderer("15s" if autoref else None)
    _runtime_renderer(
        symbol,
        runtime_strategy_filter,
        runtime_mode_filter,
        active_strategy["name"],
        runtime_watchlist,
        autoref,
        show_trades,
        show_fast_emas,
        show_ema_200,
        show_bbands,
        show_rsi,
        show_macd,
    )

# ── Market Focus tab ─────────────────────────────────────────────────────────
with focus_tab:
    import config as _cfg
    st.subheader("Weekly Market Focus Selector")
    st.caption(
        "Rank top-liquid Binance USDT pairs using the active strategy and params. "
        "Results are saved and can prefill Backtest Lab."
    )

    _latest_study = get_latest_market_focus()

    with st.expander("Run a new study", expanded=_latest_study is None):
        _focus_universe = st.slider(
            "Universe size (top pairs by 24 h volume)",
            min_value=5, max_value=50,
            value=_cfg.MARKET_FOCUS_UNIVERSE_SIZE,
            step=5,
        )
        _focus_top_n = st.slider(
            "Shortlist size (ranked candidates to keep)",
            min_value=3, max_value=15,
            value=_cfg.MARKET_FOCUS_TOP_N,
            step=1,
        )
        _focus_days = st.slider(
            "Backtest window (days back from today)",
            min_value=7, max_value=90,
            value=_cfg.MARKET_FOCUS_BACKTEST_DAYS,
            step=7,
        )
        _run_study = st.button("Run Weekly Study", type="primary")
        if _run_study:
            import concurrent.futures as _cf
            with st.spinner("Fetching universe and running backtests… this may take a minute."):
                try:
                    with _cf.ThreadPoolExecutor(max_workers=1) as _pool:
                        _future = _pool.submit(
                            run_market_focus_study,
                            active_strategy["name"],
                            None,
                            backtest_days=_focus_days,
                            top_n=_focus_top_n,
                            universe_size=_focus_universe,
                        )
                        _result = _future.result()
                    _latest_study = get_latest_market_focus()
                    st.success(
                        f"Study complete — top pick: **{_result['top_candidates'][0]['symbol']}**"
                        if _result.get("top_candidates") else "Study complete."
                    )
                    st.rerun()
                except Exception as _exc:
                    st.error(f"Study failed: {_exc}")

    if _latest_study:
        _study_id = _latest_study["id"]
        _study_ts = _latest_study.get("created_at")
        _study_ts_str = _study_ts.strftime("%Y-%m-%d %H:%M UTC") if _study_ts else "—"
        st.markdown(
            f"**Latest study** — {_study_ts_str}  ·  strategy: `{_latest_study['strategy_name']}`  "
            f"·  universe: {_latest_study['universe_size']} pairs  ·  window: {_latest_study['backtest_days']} days"
        )

        _candidates = get_market_focus_candidates(_study_id)
        _top_n_saved = _latest_study.get("top_n", _cfg.MARKET_FOCUS_TOP_N)
        _top_candidates = [c for c in _candidates if c.get("rank", 999) <= _top_n_saved]
        _all_candidates = _candidates

        if _top_candidates:
            st.markdown("#### Ranked Shortlist")
            _frame = build_focus_candidate_frame(_top_candidates)
            st.dataframe(_frame, hide_index=True, use_container_width=True)

            _recommendation = _top_candidates[0]["symbol"]
            st.markdown(f"**Recommended token this week: `{_recommendation}`**")

            if st.button(f"Prefill Backtest Lab with {_recommendation}"):
                st.session_state["focus_prefill_symbol"] = _recommendation
                st.info(f"Switch to **Backtest Lab** — the symbol is pre-set to `{_recommendation}`.")

        if len(_all_candidates) > _top_n_saved:
            with st.expander("Full universe results"):
                _full_frame = build_focus_candidate_frame(_all_candidates)
                st.dataframe(_full_frame, hide_index=True, use_container_width=True)
    else:
        st.info("No study run yet. Use the panel above to run your first weekly study.")

with inspect_tab:
    st.markdown("### Strategy Inspector")
    st.caption(
        "Review a saved backtest in trader-friendly terms, then inspect the exact Python strategy source behind that run."
    )

    all_runs = list_backtest_runs()
    if all_runs.empty:
        st.info("No saved runs yet.")
    else:
        run_labels: dict[int, str] = {}
        for _, row in all_runs.iterrows():
            run_id = int(row["id"])
            run_labels[run_id] = f"#{run_id} · {row['strategy_name']} — {row['symbol']} ({row['status']})"

        preferred_run_id = st.session_state.get("selected_backtest_run_id")
        if preferred_run_id not in run_labels:
            preferred_run_id = next(
                (
                    int(row["id"])
                    for _, row in all_runs.iterrows()
                    if float(row.get("n_trades") or 0) > 0
                    and str(row.get("integrity_status") or "valid").lower() == "valid"
                ),
                int(all_runs.iloc[0]["id"]),
            )
        if st.session_state.get("inspect_run_label") not in run_labels:
            st.session_state["inspect_run_label"] = preferred_run_id

        selected_run_id = st.selectbox(
            "Saved run",
            options=list(run_labels.keys()),
            format_func=lambda run_id: run_labels[int(run_id)],
            key="inspect_run_label",
        )

        selected_run = get_backtest_run(int(selected_run_id))
        trades_df = get_backtest_trades(int(selected_run_id))

        if selected_run is None:
            st.warning("The selected run could not be loaded.")
        else:
            run_artifact = get_strategy_artifact(selected_run.get("artifact_id"))
            equity_curve = compute_trade_equity_curve(trades_df, starting_balance=STARTING_BALANCE_USD)
            win_stats = compute_win_loss_stats(trades_df)
            summary = build_trader_summary(selected_run, equity_curve, STARTING_BALANCE_USD)
            run_integrity_status = str(selected_run.get("integrity_status") or "valid").lower()
            run_integrity_note = str(selected_run.get("integrity_note") or "").strip()
            has_trade_records = not trades_df.empty
            metrics_available = run_integrity_status != "invalid-metrics"

            _run_start = str(selected_run.get("start_date") or "—")[:10]
            _run_end = str(selected_run.get("end_date") or "—")[:10]
            st.caption(
                f"Run **#{selected_run_id}** · strategy `{selected_run.get('strategy_name', '—')}` · "
                f"symbol `{selected_run.get('symbol', '—')}` · window `{_run_start}` → `{_run_end}`"
            )
            artifact_caption = (
                f"Artifact #{selected_run.get('artifact_id') or '—'} · "
                f"provenance `{selected_run.get('strategy_provenance') or 'unknown'}` · "
                f"hash `{str(selected_run.get('strategy_code_hash') or '')[:12] or '—'}`"
            )
            st.caption(artifact_caption)
            _run_artifact_id = selected_run.get("artifact_id")
            if _run_artifact_id and int(_run_artifact_id) == (_paper_artifact_id or -1):
                st.success(f"This run's artifact is the **active paper target** (artifact #{_run_artifact_id}).")
            elif _run_artifact_id and int(_run_artifact_id) == (_live_artifact_id or -1):
                st.success(f"This run's artifact is the **active live target** (artifact #{_run_artifact_id}).")
            elif _run_artifact_id and run_artifact and str(run_artifact.get("status") or "").lower() in {"reviewed", "backtest_passed"}:
                st.info(f"Artifact #{_run_artifact_id} is reviewed but not yet promoted to paper. Use the Strategies tab to promote it.")
            st.caption(f"Integrity: **{integrity_label(run_integrity_status)}**")
            if run_integrity_status != "valid":
                warning_text = f"Saved run integrity warning: {integrity_label(run_integrity_status)}."
                if run_integrity_note:
                    warning_text += f" {run_integrity_note}"
                st.warning(warning_text)

            metric_cols = st.columns(4)
            metric_cols[0].metric("Total Gain", f"{summary['gain_pct']:+.2f}%")
            metric_cols[1].metric("Win Rate", f"{win_stats['win_rate']:.0%}")
            metric_cols[2].metric(
                "Sharpe Ratio",
                f"{float(selected_run.get('sharpe') or 0.0):.2f}" if metrics_available else "Unavailable",
            )
            metric_cols[3].metric(
                "Max Drawdown",
                f"{summary['drawdown_pct']:.2f}%" if metrics_available else "Unavailable",
            )

            if metrics_available:
                gate_icon = "✅" if summary["gate_passed"] else "❌"
                gate_message = (
                    f"{gate_icon} Gate {'passed' if summary['gate_passed'] else 'failed'}. "
                    f"Sharpe quality: {summary['sharpe_label']}. "
                    f"Risk profile: {summary['risk_label']}. "
                    f"Profit factor: {summary['profit_factor']:.2f}. "
                    f"Trades: {summary['n_trades']} total executions, "
                    f"{win_stats['total_pairs']} closed pairs, {win_stats['win_count']} wins, {win_stats['loss_count']} losses."
                )
                if summary["gate_passed"]:
                    st.success(gate_message)
                else:
                    st.warning(gate_message)
            else:
                st.warning("Gate outcome unavailable for this run because the saved metrics payload is invalid.")

            if metrics_available and summary["gate_failures"]:
                with st.expander("Gate failure details", expanded=False):
                    for failure in summary["gate_failures"]:
                        st.write(f"- {failure}")

            st.markdown("#### Equity Audit")
            if has_trade_records and not equity_curve.empty:
                inspect_fig = go.Figure()
                inspect_fig.add_trace(
                    go.Scatter(
                        x=equity_curve["step"],
                        y=equity_curve["equity"],
                        mode="lines",
                        name="Equity",
                        line=dict(color="#2962ff", width=2),
                        fill="tozeroy",
                        fillcolor="rgba(41,98,255,0.10)",
                    )
                )
                inspect_fig.update_layout(
                    title="Saved Run Equity Curve",
                    height=250,
                    paper_bgcolor="#0e1117",
                    plot_bgcolor="#0e1117",
                    font=dict(color="#d1d4dc"),
                    margin=dict(l=10, r=10, t=40, b=10),
                    xaxis=dict(gridcolor="#1e222d"),
                    yaxis=dict(gridcolor="#1e222d"),
                )
                st.plotly_chart(inspect_fig, width="stretch")
            elif run_integrity_status == "missing-trades":
                st.warning(
                    "**Equity curve unavailable — missing trades.** "
                    f"Run #{selected_run_id} has no persisted trade rows in the database. "
                    "This can happen when a backtest ran but failed before persisting its trade log. "
                    "Re-run the backtest to generate a fresh result."
                )
            elif run_integrity_status == "invalid-metrics":
                st.warning(
                    "**Equity curve unavailable — invalid metrics.** "
                    f"Run #{selected_run_id} has a corrupted metrics payload. "
                    "Re-run the backtest to replace this entry."
                )
            elif not has_trade_records:
                st.info(
                    "**Equity curve unavailable — no trades executed.** "
                    f"Run #{selected_run_id} completed with 0 trades. "
                    "The strategy may not have generated any signals over the selected date window. "
                    "Try widening the date range or checking the strategy parameters."
                )

            st.markdown("---")
            st.markdown("#### Strategy Algorithm")
            strat_item = run_artifact or next(
                (item for item in list_available_strategies() if item.get("name") == selected_run.get("strategy_name")),
                None,
            )
            if strat_item is None:
                source_reason = f"Strategy `{selected_run.get('strategy_name', 'unknown')}` is no longer available in the local catalog."
                st.warning(source_reason)
                st.code(f"# Strategy source unavailable\n# Reason: {source_reason}\n", language="python")
            else:
                if run_artifact and run_artifact.get("path"):
                    current_hash = ""
                    try:
                        current_hash = compute_strategy_code_hash(run_artifact["path"])
                    except OSError:
                        current_hash = ""
                    if current_hash and current_hash != str(selected_run.get("strategy_code_hash") or ""):
                        st.warning("The current plugin file no longer matches the saved run hash. Review the artifact history before trusting this source as an exact historical copy.")
                strategy_path = str(strat_item.get("path") or "").strip()
                if not strategy_path:
                    source_reason = "Built-in strategy source is not stored on disk."
                    st.info(source_reason)
                    st.code(get_strategy_source_code(strat_item), language="python")
                elif not os.path.exists(strategy_path):
                    source_reason = f"Strategy file is missing on disk: {strategy_path}"
                    st.warning(source_reason)
                    st.code(f"# Strategy source unavailable\n# Reason: {source_reason}\n", language="python")
                else:
                    st.code(get_strategy_source_code(strat_item), language="python")

with diary_tab:
    st.markdown("### Trading Diary")
    st.caption(
        "Review trade outcomes, annotate learnings, capture session summaries, and export repeatable knowledge."
    )

    try:
        st.markdown("#### Trading Summary")
        diary_summary = get_trading_summary()
        diary_metrics = build_diary_summary_metrics(diary_summary)

        diary_metric_cols = st.columns(4)
        diary_metric_cols[0].metric("Completed Trades", diary_metrics["total_trades"])
        diary_metric_cols[1].metric("Win Rate", diary_metrics["win_rate_label"])
        diary_metric_cols[2].metric("Total PnL", diary_metrics["total_pnl_label"])
        diary_metric_cols[3].metric("Best Strategy", diary_metrics["best_strategy"])

        strategy_chart_col, symbol_chart_col = st.columns(2)

        strategy_fig = go.Figure()
        strategy_names = list((diary_summary.get("by_strategy") or {}).keys())
        strategy_pnls = [
            float((diary_summary.get("by_strategy") or {}).get(name, {}).get("total_pnl", 0.0))
            for name in strategy_names
        ]
        strategy_fig.add_trace(
            go.Bar(
                x=strategy_names,
                y=strategy_pnls,
                marker_color="#26a69a",
                name="Strategy PnL",
            )
        )
        strategy_fig.update_layout(
            title="P&L by Strategy",
            height=320,
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            font=dict(color="#d1d4dc"),
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(gridcolor="#1e222d"),
            yaxis=dict(gridcolor="#1e222d"),
        )

        symbol_fig = go.Figure()
        symbol_names = list((diary_summary.get("by_symbol") or {}).keys())
        symbol_pnls = [
            float((diary_summary.get("by_symbol") or {}).get(name, {}).get("total_pnl", 0.0))
            for name in symbol_names
        ]
        symbol_fig.add_trace(
            go.Bar(
                x=symbol_names,
                y=symbol_pnls,
                marker_color="#2962ff",
                name="Symbol PnL",
            )
        )
        symbol_fig.update_layout(
            title="P&L by Symbol",
            height=320,
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            font=dict(color="#d1d4dc"),
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(gridcolor="#1e222d"),
            yaxis=dict(gridcolor="#1e222d"),
        )

        with strategy_chart_col:
            st.plotly_chart(strategy_fig, width="stretch")
        with symbol_chart_col:
            st.plotly_chart(symbol_fig, width="stretch")
    except Exception as exc:
        st.warning(f"Trading Summary unavailable: {exc}")

    try:
        st.markdown("#### Recent Diary Entries")
        diary_filter_cols = st.columns(4)
        filter_run_mode = diary_filter_cols[0].selectbox(
            "Run Mode",
            options=["all", "paper", "live"],
            key="diary_filter_run_mode",
        )
        filter_symbol = diary_filter_cols[1].text_input(
            "Symbol",
            key="diary_filter_symbol",
            placeholder="BTCUSDT",
        ).strip()
        filter_strategy = diary_filter_cols[2].text_input(
            "Strategy",
            key="diary_filter_strategy",
            placeholder="mean_reversion_v1",
        ).strip()
        filter_entry_type = diary_filter_cols[3].selectbox(
            "Entry Type",
            options=["all", "trade", "backtest_insight", "session_summary", "manual"],
            key="diary_filter_entry_type",
        )

        filtered_entries = list_diary_entries(
            run_mode=None if filter_run_mode == "all" else filter_run_mode,
            symbol=filter_symbol or None,
            strategy=filter_strategy or None,
            entry_type=None if filter_entry_type == "all" else filter_entry_type,
            limit=100,
        )
        diary_entries_frame = build_diary_entries_frame(filtered_entries)
        st.dataframe(diary_entries_frame, hide_index=True, use_container_width=True)

        default_entry_id = int(filtered_entries[0]["id"]) if filtered_entries else 1
        selected_entry_id = st.number_input(
            "Entry ID to annotate",
            min_value=1,
            value=default_entry_id,
            step=1,
            key="diary_entry_id",
        )
        with st.expander("Annotate diary entry", expanded=False):
            with st.form("diary_annotation_form"):
                outcome_rating = st.slider(
                    "Outcome Rating",
                    min_value=1,
                    max_value=5,
                    value=3,
                    key="diary_outcome_rating",
                )
                learnings = st.text_area(
                    "Learnings",
                    key="diary_learnings",
                    placeholder="What worked or failed in this setup?",
                )
                strategy_suggestion = st.text_area(
                    "Strategy Suggestion",
                    key="diary_strategy_suggestion",
                    placeholder="What should change before the next run?",
                )
                if st.form_submit_button("Save Annotation"):
                    update_diary_entry(
                        int(selected_entry_id),
                        learnings=learnings,
                        strategy_suggestion=strategy_suggestion,
                        outcome_rating=outcome_rating,
                    )
                    st.success(f"Diary entry #{int(selected_entry_id)} updated.")
    except Exception as exc:
        st.warning(f"Recent Diary Entries unavailable: {exc}")

    try:
        st.markdown("#### Session Summary")
        session_mode = st.selectbox(
            "Session Mode",
            options=["paper", "live"],
            key="diary_session_mode",
        )
        if st.button("Record Session Summary", key="diary_record_session_summary"):
            record_session_summary(session_mode)
            st.success(f"Session summary recorded for {session_mode}.")
    except Exception as exc:
        st.warning(f"Session Summary unavailable: {exc}")

    try:
        st.markdown("#### Backtest Insights")
        recent_insights = list_diary_entries(entry_type="backtest_insight", limit=20)
        if not recent_insights:
            st.info("No backtest insights recorded yet.")
        for entry in recent_insights:
            entry_symbol = entry.get("symbol") or "—"
            entry_strategy = entry.get("strategy_name") or "—"
            entry_id = entry.get("backtest_run_id") or entry.get("id")
            with st.expander(f"Run #{entry_id} — {entry_symbol} / {entry_strategy}", expanded=False):
                st.text(entry.get("content") or "")
    except Exception as exc:
        st.warning(f"Backtest Insights unavailable: {exc}")

    try:
        st.markdown("#### Export Knowledge")
        if st.button("Export Diary Learnings", key="diary_export_knowledge"):
            export_path = export_diary_to_knowledge()
            st.success(export_path)
    except Exception as exc:
        st.warning(f"Export Knowledge unavailable: {exc}")
