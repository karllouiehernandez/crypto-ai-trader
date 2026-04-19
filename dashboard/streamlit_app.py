# crypto_ai_trader/dashboard/streamlit_app.py
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from dashboard.chart_component import render_responsive_chart
from config import DB_PATH, SYMBOLS, STARTING_BALANCE_USD, LIVE_TRADE_ENABLED, LLM_ENABLED, LLM_MODEL, LLM_PROVIDER
from strategy.ta_features import add_indicators
from strategy.regime import detect_regime, Regime
from strategy.runtime import (
    get_active_strategy_config,
    get_active_runtime_artifact,
    list_available_strategies,
    list_available_strategy_errors,
    set_active_strategy_config,
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
    build_artifact_registry_frame,
    build_backtest_preset_frame,
    build_backtest_run_leaderboard,
    build_focus_candidate_frame,
    build_runtime_target_summary,
    build_trader_summary,
    build_trading_chart_payload,
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
    normalise_params,
    normalise_preset_name,
    runtime_mode_table,
    strategy_workflow_status,
    runtime_summary,
)
from database.promotion_queries import query_promotions
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


@st.cache_data(ttl=30)
def load_promotions() -> pd.DataFrame:
    return query_promotions(DB_PATH)


@st.cache_data(ttl=10)
def load_strategy_catalog() -> list[dict]:
    return list_available_strategies()


@st.cache_data(ttl=10)
def load_strategy_errors() -> list[dict]:
    return list_available_strategy_errors()


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
    st.success("Runtime watchlist updated.")
    st.rerun()

if sync_symbol:
    with st.spinner(f"Syncing history for {symbol}..."):
        ensure_symbol_history(symbol)
    load_candles_raw.clear()
    load_symbol_audit.clear()
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
_real_issues = []
if active_paper_artifact and runtime_target_summary["paper"]["error"]:
    _real_issues.append(f"Paper target invalid — {runtime_target_summary['paper']['error']}")
if active_live_artifact and runtime_target_summary["live"]["error"]:
    _real_issues.append(f"Live target invalid — {runtime_target_summary['live']['error']}")
if _real_issues:
    st.warning("⚠ Runtime target validation failed. See **Promotion Control Panel** in the Strategies tab.  \n" + "  \n".join(_real_issues))

strategy_tab, backtest_tab, runtime_tab, focus_tab, inspect_tab = st.tabs(
    ["Strategies", "Backtest Lab", "Runtime Monitor", "Market Focus", "Inspect"]
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
        meta_cols = st.columns(4)
        meta_cols[0].metric("Origin", format_strategy_origin(selected_meta))
        meta_cols[1].metric("Version", selected_meta["version"])
        meta_cols[2].metric("Regimes", ", ".join(selected_meta["regimes"]) or "All")
        meta_cols[3].metric("Workflow Stage", workflow_status["stage"])
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
        review_cols = st.columns(3)
        review_cols[0].metric("Backtest Runs", str(workflow_status["run_count"]))
        review_cols[1].metric("Passed Runs", str(workflow_status["passed_runs"]))
        review_cols[2].metric("Failed Runs", str(workflow_status["failed_runs"]))
        st.info(workflow_status["next_step"])
        if selected_meta.get("is_generated"):
            st.warning("Generated plugin draft. Keep it in draft status until it passes backtesting and is reviewed as a stable plugin.")
        if selected_meta.get("default_params"):
            st.json(selected_meta["default_params"], expanded=False)

        review_name = ""
        if selected_meta.get("is_generated"):
            default_review_name = selected_meta["name"]
            if default_review_name.startswith("generated_"):
                default_review_name = default_review_name.removeprefix("generated_") or "reviewed_strategy_v1"
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

        review_disabled = not (selected_meta.get("is_generated") and selected_meta.get("artifact_id"))
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

        _artifact_status = str(selected_meta.get("artifact_status") or "").lower()
        _is_paper_target = bool(selected_meta.get("active_paper_artifact"))
        _is_live_target = bool(selected_meta.get("active_live_artifact"))
        if _is_paper_target:
            st.caption(f"This strategy (`{selected_strategy}`) **is** the current paper trading target.")
        if _is_live_target:
            st.caption(f"This strategy (`{selected_strategy}`) **is** the current live trading target.")
        if selected_meta.get("is_generated"):
            st.caption(
                "**Promote to Paper / Approve for Live are disabled** for generated drafts. "
                "Use **Review and Save** to create a stable reviewed plugin, then backtest it."
            )
        elif selected_meta.get("provenance") != "plugin":
            st.caption(
                "**Promote to Paper / Approve for Live are only available for plugin strategies.** "
                "Built-in strategies cannot be promoted."
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
    _bt_sym_default = _prefill_sym if _prefill_sym else symbol
    _bt_sym_options = ready_symbols if _bt_sym_default in ready_symbols else [_bt_sym_default] + list(ready_symbols)
    bt_symbol = selector_cols[0].selectbox(
        "Symbol",
        _bt_sym_options,
        index=0 if _prefill_sym else (_bt_sym_options.index(_bt_sym_default) if _bt_sym_default in _bt_sym_options else 0),
        key="bt_symbol",
    )
    bt_strategy = selector_cols[1].selectbox(
        "Strategy",
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
    _latest_candle_date = _latest_candle_dt.date() if _latest_candle_dt else datetime.utcnow().date()
    _bt_end_default = _latest_candle_date
    _bt_start_default = _latest_candle_date - timedelta(days=30)
    if _latest_candle_dt:
        st.caption(
            f"Latest complete candle for **{bt_symbol}**: `{_latest_candle_date}` — "
            "end date defaults to this day. Adjust if you want a different window."
        )
    else:
        st.caption(f"No candle data found for **{bt_symbol}** — defaulting to today.")
    date_cols = st.columns(2)
    bt_start = date_cols[0].date_input("Start", value=_bt_start_default)
    bt_end = date_cols[1].date_input("End", value=_bt_end_default)
    bt_start_dt = datetime.combine(bt_start, datetime.min.time())
    bt_end_dt = datetime.combine(bt_end, datetime.min.time())
    audit_result = load_symbol_audit(bt_symbol, bt_start_dt.isoformat(), bt_end_dt.isoformat())
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

    if run_backtest_now:
        if not audit_result["is_complete"]:
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
                st.error(f"Backtest validation failed: {exc}")
                result = None
            except Exception as exc:
                st.error(f"Backtest run failed unexpectedly: {exc}")
                result = None
            else:
                if result is not None:
                    st.session_state["selected_backtest_run_id"] = result["run_id"]
                    load_backtest_runs.clear()
                    load_symbol_audit.clear()
                    load_backtest_run.clear()
                    load_backtest_trades.clear()
                    st.success(f"Backtest run #{result['run_id']} saved.")
                else:
                    st.error("Backtest returned no result. Check the strategy and date range.")

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
