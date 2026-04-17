# crypto_ai_trader/dashboard/streamlit_app.py
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import DB_PATH, SYMBOLS, STARTING_BALANCE_USD, LIVE_TRADE_ENABLED, LLM_ENABLED, LLM_MODEL, LLM_PROVIDER
from strategy.ta_features import add_indicators
from strategy.regime import detect_regime, Regime
from strategy.runtime import (
    get_active_strategy_config,
    list_available_strategies,
    list_available_strategy_errors,
    set_active_strategy_config,
)
from backtester.service import (
    get_backtest_run,
    get_backtest_trades,
    list_backtest_runs,
    run_and_persist_backtest,
)
from dashboard.workbench import (
    build_strategy_catalog_frame,
    compute_cumulative_trade_pnl,
    compute_drawdown_curve,
    compute_trade_equity_curve,
    filter_backtest_runs,
    filter_runtime_data,
    format_strategy_origin,
    list_runtime_strategies,
    runtime_mode_table,
    strategy_workflow_status,
    runtime_summary,
)
from database.promotion_queries import query_promotions
from database.models import init_db
from llm.generator import generate_and_discover_strategy

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


@st.cache_data(ttl=30)
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


@st.cache_data(ttl=30)
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

# Persist all user preferences in session_state so auto-refresh never resets them
_DEFAULTS = {
    "symbol":        SYMBOLS[0],
    "autoref":       True,
    "show_ohlc":     True,
    "show_bb":       True,
    "show_ema":      True,
    "show_trades":   True,
    "show_ema200":   False,
    "runtime_mode_filter": "All",
    "show_all_backtest_runs": False,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

symbol  = st.sidebar.selectbox("Symbol", SYMBOLS, key="symbol")
autoref = st.sidebar.checkbox("Auto-refresh (15 s)", key="autoref")

st.sidebar.markdown("---")
st.sidebar.markdown("**📉 Chart Overlays**")
show_ohlc   = st.sidebar.checkbox("Candlesticks",      key="show_ohlc")
show_bb     = st.sidebar.checkbox("Bollinger Bands",   key="show_bb")
show_ema    = st.sidebar.checkbox("EMA 9 / 21 / 55",   key="show_ema")
show_ema200 = st.sidebar.checkbox("EMA 200",           key="show_ema200")
show_trades = st.sidebar.checkbox("Trade Markers",     key="show_trades")

active_strategy = get_active_strategy_config()
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

st.markdown("## Strategy Workbench")
workbench_col, backtest_col = st.columns([1.05, 1.35], gap="large")

with workbench_col:
    st.markdown("### Strategies")
    st.caption(
        "Research loop: generate or add a plugin, confirm it loads here, backtest it in the lab, "
        "then promote the same strategy into paper/live after restart."
    )
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
        if not LLM_ENABLED:
            st.warning(
                "LLM strategy generation is disabled. Add an LLM API key in `.env` or set `LLM_ENABLED=true` "
                "to generate plugin drafts from the dashboard."
            )
        with st.form("generate_strategy_form", clear_on_submit=False):
            gen_description = st.text_area(
                "Strategy brief",
                placeholder="Example: Trend-following pullback strategy that buys when EMA-9 stays above EMA-21 and RSI recovers from 45 in trending markets.",
                disabled=not LLM_ENABLED,
            )
            gen_cols = st.columns(2)
            gen_symbol = gen_cols[0].selectbox(
                "Primary symbol",
                SYMBOLS,
                index=SYMBOLS.index(symbol),
                key="gen_symbol",
                disabled=not LLM_ENABLED,
            )
            gen_regime = gen_cols[1].selectbox(
                "Target regime",
                ["any", "RANGING", "TRENDING", "SQUEEZE", "HIGH_VOL"],
                key="gen_regime",
                disabled=not LLM_ENABLED,
            )
            generate_now = st.form_submit_button(
                "Generate Plugin Draft",
                type="primary",
                use_container_width=True,
                disabled=not LLM_ENABLED or not strategy_names,
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
                st.dataframe(pd.DataFrame(generation_result["errors"]), use_container_width=True, hide_index=True)
            if generation_result.get("strategies"):
                st.dataframe(pd.DataFrame(generation_result["strategies"]), use_container_width=True, hide_index=True)
            if generation_result.get("code"):
                st.code(generation_result["code"], language="python")

    selected_strategy = st.selectbox(
        "Select active strategy",
        strategy_names,
        index=default_strategy_index,
        format_func=lambda name: next((item["display_name"] for item in strategy_catalog if item["name"] == name), name),
        key="active_strategy_selector",
    )
    st.session_state["strategy_focus_name"] = selected_strategy
    selected_meta = strategy_lookup.get(selected_strategy)
    if selected_meta:
        workflow_status = strategy_workflow_status(selected_meta, all_backtest_runs, active_strategy["name"])
        st.caption(selected_meta["description"])
        meta_cols = st.columns(4)
        meta_cols[0].metric("Origin", format_strategy_origin(selected_meta))
        meta_cols[1].metric("Version", selected_meta["version"])
        meta_cols[2].metric("Regimes", ", ".join(selected_meta["regimes"]) or "All")
        meta_cols[3].metric("Workflow Stage", workflow_status["stage"])
        if selected_meta.get("file_name"):
            st.caption(f"File: `{selected_meta['file_name']}`")
        if selected_meta.get("path"):
            st.caption(f"Path: `{selected_meta['path']}`")
        if selected_meta.get("modified_at"):
            st.caption(f"Last modified: {selected_meta['modified_at']}")
        review_cols = st.columns(3)
        review_cols[0].metric("Backtest Runs", str(workflow_status["run_count"]))
        review_cols[1].metric("Passed Runs", str(workflow_status["passed_runs"]))
        review_cols[2].metric("Failed Runs", str(workflow_status["failed_runs"]))
        st.info(workflow_status["next_step"])
        if selected_meta.get("is_generated"):
            st.warning("Generated plugin draft. Keep it in draft status until it passes backtesting and is reviewed as a stable plugin.")
        if selected_meta.get("default_params"):
            st.json(selected_meta["default_params"], expanded=False)
    if st.button("Set Active Strategy", type="primary", use_container_width=True):
        saved = set_active_strategy_config(selected_strategy)
        load_strategy_catalog.clear()
        load_strategy_errors.clear()
        st.cache_data.clear()
        st.success(
            f"Active strategy saved: {saved['name']} ({saved['version']}). "
            "Restart paper/live processes to apply the change outside dashboard backtests."
        )

    catalog_df = build_strategy_catalog_frame(strategy_catalog, all_backtest_runs, active_strategy["name"])
    st.dataframe(catalog_df, use_container_width=True, hide_index=True)

    if strategy_errors:
        st.warning("Plugin load issues detected")
        st.dataframe(pd.DataFrame(strategy_errors), use_container_width=True, hide_index=True)

with backtest_col:
    st.markdown("### Backtest Lab")
    with st.form("backtest_lab_form", clear_on_submit=False):
        bt_symbol = st.selectbox("Symbol", SYMBOLS, index=SYMBOLS.index(symbol), key="bt_symbol")
        bt_strategy = st.selectbox(
            "Strategy",
            strategy_names,
            index=default_strategy_index,
            key="bt_strategy",
        )
        date_cols = st.columns(2)
        bt_start = date_cols[0].date_input("Start", value=datetime.utcnow().date() - timedelta(days=30))
        bt_end = date_cols[1].date_input("End", value=datetime.utcnow().date())
        run_backtest_now = st.form_submit_button("Run Backtest", type="primary", use_container_width=True)

    selected_bt_meta = strategy_lookup.get(bt_strategy)
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

    if run_backtest_now:
        with st.spinner("Running backtest and persisting result..."):
            result = run_and_persist_backtest(
                bt_symbol,
                datetime.combine(bt_start, datetime.min.time()),
                datetime.combine(bt_end, datetime.min.time()),
                bt_strategy,
            )
        st.session_state["selected_backtest_run_id"] = result["run_id"]
        load_backtest_runs.clear()
        load_backtest_trades.clear()
        st.success(f"Backtest run #{result['run_id']} saved.")

    runs_df = load_backtest_runs()
    all_backtest_runs = runs_df
    st.checkbox("Show all saved runs", key="show_all_backtest_runs")
    visible_runs_df = filter_backtest_runs(runs_df, bt_strategy, show_all=st.session_state["show_all_backtest_runs"])
    if not visible_runs_df.empty:
        display_runs = visible_runs_df.copy()
        if "created_at" in display_runs.columns:
            display_runs["created_at"] = pd.to_datetime(display_runs["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
        if "start_ts" in display_runs.columns:
            display_runs["start_ts"] = pd.to_datetime(display_runs["start_ts"]).dt.strftime("%Y-%m-%d")
        if "end_ts" in display_runs.columns:
            display_runs["end_ts"] = pd.to_datetime(display_runs["end_ts"]).dt.strftime("%Y-%m-%d")
        if "failures" in display_runs.columns:
            display_runs["failures"] = display_runs["failures"].apply(
                lambda value: "; ".join(value) if isinstance(value, list) else value
            )
        st.markdown("#### Saved Runs")
        st.dataframe(display_runs, use_container_width=True, hide_index=True)
        available_run_ids = visible_runs_df["id"].astype(int).tolist()
        selected_run_id = st.selectbox(
            "Inspect saved run",
            available_run_ids,
            index=0 if "selected_backtest_run_id" not in st.session_state or st.session_state["selected_backtest_run_id"] not in available_run_ids
            else available_run_ids.index(st.session_state["selected_backtest_run_id"]),
            key="selected_backtest_run_id",
            format_func=lambda run_id: (
                f"#{run_id} · "
                f"{visible_runs_df.loc[visible_runs_df['id'] == run_id, 'strategy_name'].iloc[0]} · "
                f"{visible_runs_df.loc[visible_runs_df['id'] == run_id, 'symbol'].iloc[0]}"
            ),
        )
        selected_run = load_backtest_run(int(selected_run_id)) or visible_runs_df[visible_runs_df["id"] == selected_run_id].iloc[0].to_dict()
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

        if selected_run.get("failures"):
            failures = selected_run["failures"]
            if isinstance(failures, list):
                st.warning("Acceptance gate failures: " + "; ".join(failures))
            else:
                st.warning(f"Acceptance gate failures: {failures}")
        else:
            st.success(f"Acceptance gate: {str(selected_run.get('status', 'completed')).upper()}")

        st.caption(
            f"Window: {pd.to_datetime(selected_run.get('start_ts')).strftime('%Y-%m-%d')} "
            f"→ {pd.to_datetime(selected_run.get('end_ts')).strftime('%Y-%m-%d')}"
        )

        backtest_chart = go.Figure()
        candle_df = load_candles_raw(
            str(selected_run["symbol"]),
            max((pd.Timestamp.utcnow() - pd.Timestamp(selected_run["start_ts"])).days + 2, 2),
        )
        filtered_candles = candle_df[
            (candle_df["open_time"] >= pd.Timestamp(selected_run["start_ts"]))
            & (candle_df["open_time"] <= pd.Timestamp(selected_run["end_ts"]))
        ] if not candle_df.empty else pd.DataFrame()
        if not filtered_candles.empty:
            backtest_chart.add_trace(go.Candlestick(
                x=filtered_candles["open_time"],
                open=filtered_candles["open"],
                high=filtered_candles["high"],
                low=filtered_candles["low"],
                close=filtered_candles["close"],
                name="OHLC",
            ))
        if not selected_run_trades.empty:
            for side, color, marker in [("BUY", "#00e676", "triangle-up"), ("SELL", "#ff1744", "triangle-down")]:
                side_df = selected_run_trades[selected_run_trades["side"] == side]
                if not side_df.empty:
                    backtest_chart.add_trace(go.Scatter(
                        x=side_df["ts"],
                        y=side_df["price"],
                        mode="markers",
                        name=side,
                        marker=dict(color=color, size=11, symbol=marker),
                    ))
        backtest_chart.update_layout(
            title=f"Backtest #{selected_run_id} · {selected_run['strategy_name']} · {selected_run['symbol']}",
            height=380,
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            font=dict(color="#d1d4dc"),
            xaxis_rangeslider_visible=False,
        )
        st.plotly_chart(backtest_chart, use_container_width=True)

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
                st.plotly_chart(eq_fig, use_container_width=True)

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
                st.plotly_chart(dd_fig, use_container_width=True)

            st.markdown("#### Trade Log")
            st.dataframe(selected_run_trades, use_container_width=True, hide_index=True)
    elif not runs_df.empty:
        st.info(f"No saved runs yet for `{bt_strategy}`. Run a backtest to start its evaluation history or enable 'Show all saved runs'.")
    else:
        st.info("No backtest runs have been saved yet. Run the selected strategy to start its evaluation history.")

# ── Timeframe selector (horizontal buttons) ───────────────────────────────────
st.markdown("## Runtime Monitor")
st.caption(
    f"Viewing `{runtime_strategy_filter}` in `{runtime_mode_filter}` mode for runtime monitoring. "
    "Changing the active strategy affects dashboard backtests immediately and paper/live after restart."
)
st.markdown("### 📈 " + symbol + " Chart")
tf_cols = st.columns(len(_TF_OPTIONS))
if "timeframe" not in st.session_state:
    st.session_state.timeframe = "1h"

for i, tf in enumerate(_TF_OPTIONS):
    btn_type = "primary" if st.session_state.timeframe == tf else "secondary"
    if tf_cols[i].button(tf, key=f"tf_{tf}", type=btn_type, use_container_width=True):
        st.session_state.timeframe = tf

timeframe = st.session_state.timeframe
lookback  = _TF_LOOKBACK_DAYS[timeframe]
resample  = _TF_RESAMPLE[timeframe]

# ── Load & resample data ──────────────────────────────────────────────────────
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

# ── Sidebar: regime & metrics ─────────────────────────────────────────────────
regime = None
if not df.empty and len(df) >= 2:
    try:
        regime = detect_regime(df)
        last   = df.iloc[-1]
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📊 Current Regime")
        st.sidebar.markdown(f"**{_REGIME_EMOJI[regime]}**")
        st.sidebar.markdown(f"Strategy route: **{_REGIME_STRATEGY[regime]}**")
        st.sidebar.caption(f"Runtime view strategy: {runtime_strategy_filter}")
        st.sidebar.markdown("---")

        # Live price
        st.sidebar.metric("Last Price", f"${last.close:,.4f}")
        chg = ((last.close - df.iloc[-2].close) / df.iloc[-2].close * 100) if len(df) >= 2 else 0
        st.sidebar.metric("Change", f"{chg:+.2f}%")
        st.sidebar.markdown("---")
        st.sidebar.metric("RSI-14",   f"{last.rsi_14:.1f}"   if "rsi_14"   in df.columns else "—")
        st.sidebar.metric("ADX-14",   f"{last.adx_14:.1f}"   if "adx_14"   in df.columns else "—")
        st.sidebar.metric("BB Width", f"{last.bb_width:.4f}" if "bb_width" in df.columns else "—")
    except Exception:
        pass

st.sidebar.markdown("---")
if not eq.empty:
    st.sidebar.metric("Equity (USD)", f"${eq.equity.iloc[-1]:,.2f}",
                      delta=f"{eq.equity.iloc[-1] - STARTING_BALANCE_USD:+.2f}")
else:
    st.sidebar.metric("Equity (USD)", f"${STARTING_BALANCE_USD:,.2f}")

# ── Sidebar: AI Promotion Gate ────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("### 🤖 AI Promotion Gate")
try:
    promo_df = load_promotions()
    if not promo_df.empty:
        latest = promo_df.iloc[0]
        ts_str = pd.to_datetime(latest["ts"]).strftime("%Y-%m-%d")
        st.sidebar.success(f"🚀 PROMOTED  ·  {ts_str}")
        st.sidebar.metric("Sharpe",        f"{latest['sharpe']:.2f}")
        st.sidebar.metric("Max Drawdown",  f"{latest['max_dd']:.1%}")
        st.sidebar.metric("Profit Factor", f"{latest['profit_factor']:.2f}")
        if LIVE_TRADE_ENABLED:
            st.sidebar.warning("⚡ LIVE_TRADE_ENABLED=true")
        else:
            st.sidebar.caption("Set LIVE_TRADE_ENABLED=true in .env to enable real orders")
    else:
        st.sidebar.info("⏳ Not yet promoted")
        st.sidebar.caption("Requires 3 consecutive PROMOTE_TO_LIVE evaluations")
except Exception:
    st.sidebar.caption("Promotion data unavailable")

# ── Main chart: Price + Volume (subplots) ────────────────────────────────────
fig = make_subplots(
    rows=4, cols=1,
    shared_xaxes=True,
    row_heights=[0.55, 0.12, 0.17, 0.16],
    vertical_spacing=0.02,
    subplot_titles=("", "Volume", "MACD", "RSI")
)

if not df.empty:
    # ── Row 1: Candlesticks ────────────────────────────────────────────────────
    if show_ohlc:
        fig.add_trace(go.Candlestick(
            x=df.open_time, open=df.open, high=df.high, low=df.low, close=df.close,
            name="OHLC",
            increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
            increasing_fillcolor="#26a69a", decreasing_fillcolor="#ef5350",
        ), row=1, col=1)
    else:
        # Line chart fallback when OHLC hidden
        fig.add_trace(go.Scatter(
            x=df.open_time, y=df.close, name="Close",
            line=dict(color="#2962ff", width=1.5)
        ), row=1, col=1)

    # Bollinger Bands with fill
    if show_bb and "bb_hi" in df.columns and "bb_lo" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.open_time, y=df.bb_hi, name="BB Upper",
            line=dict(width=0.8, color="rgba(100,180,255,0.6)"), showlegend=False
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.open_time, y=df.bb_lo, name="BB Lower",
            line=dict(width=0.8, color="rgba(100,180,255,0.6)"),
            fill="tonexty", fillcolor="rgba(100,180,255,0.05)", showlegend=False
        ), row=1, col=1)

    # EMAs
    if show_ema:
        ema_styles = [
            ("ema_9",  "EMA 9",  "#f6c90e", 1),
            ("ema_21", "EMA 21", "#ff9800", 1.2),
            ("ema_55", "EMA 55", "#e91e63", 1.4),
        ]
        for col_name, label, color, width in ema_styles:
            if col_name in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.open_time, y=df[col_name], name=label,
                    line=dict(width=width, color=color)
                ), row=1, col=1)

    # EMA 200
    if show_ema200 and "ema_200" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.open_time, y=df["ema_200"], name="EMA 200",
            line=dict(width=1.5, color="#7c4dff", dash="dot")
        ), row=1, col=1)

    # Trade markers
    if show_trades and not tr.empty:
        tf_start = df.open_time.min()
        tf_end   = df.open_time.max()
        visible_tr = tr[(tr.ts >= tf_start) & (tr.ts <= tf_end)]
        buys  = visible_tr[visible_tr.side == "BUY"]
        sells = visible_tr[visible_tr.side == "SELL"]
        if not buys.empty:
            fig.add_trace(go.Scatter(
                x=buys.ts, y=buys.price, mode="markers", name="BUY",
                marker=dict(symbol="triangle-up", size=12, color="#00e676",
                            line=dict(width=1, color="white"))
            ), row=1, col=1)
        if not sells.empty:
            fig.add_trace(go.Scatter(
                x=sells.ts, y=sells.price, mode="markers", name="SELL",
                marker=dict(symbol="triangle-down", size=12, color="#ff1744",
                            line=dict(width=1, color="white"))
            ), row=1, col=1)

    # ── Row 2: Volume bars ─────────────────────────────────────────────────────
    vol_colors = [
        "#26a69a" if c >= o else "#ef5350"
        for c, o in zip(df.close, df.open)
    ]
    fig.add_trace(go.Bar(
        x=df.open_time, y=df.volume, name="Volume",
        marker_color=vol_colors, showlegend=False
    ), row=2, col=1)

    # ── Row 3: MACD ────────────────────────────────────────────────────────────
    if "macd" in df.columns:
        macd_hist = df.macd - df.macd_s
        hist_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in macd_hist]
        fig.add_trace(go.Bar(
            x=df.open_time, y=macd_hist, name="MACD Hist",
            marker_color=hist_colors, showlegend=False
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=df.open_time, y=df.macd,   name="MACD",
            line=dict(color="#2196f3", width=1)
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=df.open_time, y=df.macd_s, name="Signal",
            line=dict(color="#ff9800", width=1)
        ), row=3, col=1)

    # ── Row 4: RSI ─────────────────────────────────────────────────────────────
    if "rsi_14" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.open_time, y=df.rsi_14, name="RSI-14",
            line=dict(color="#ce93d8", width=1.2)
        ), row=4, col=1)
        for lvl, col in [(70, "rgba(239,83,80,0.4)"), (35, "rgba(38,166,154,0.4)"), (50, "rgba(120,120,120,0.3)")]:
            fig.add_hline(y=lvl, line_dash="dot", line_color=col, row=4, col=1)
        fig.add_hrect(y0=70, y1=100, fillcolor="rgba(239,83,80,0.05)",
                      line_width=0, row=4, col=1)
        fig.add_hrect(y0=0, y1=35, fillcolor="rgba(38,166,154,0.05)",
                      line_width=0, row=4, col=1)
else:
    fig.add_annotation(
        text="No data — run <b>python run_live.py</b> to load candles",
        xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False, font=dict(size=18, color="#aaaaaa")
    )

# ── Chart layout ───────────────────────────────────────────────────────────────
regime_label = _REGIME_EMOJI.get(regime, "") if regime else ""
fig.update_layout(
    title=dict(
        text=f"{symbol}  ·  {timeframe}  {regime_label}",
        font=dict(size=18, color="#ffffff")
    ),
    height=900,
    paper_bgcolor="#0e1117",
    plot_bgcolor="#0e1117",
    font=dict(color="#d1d4dc"),
    legend=dict(
        orientation="h", yanchor="bottom", y=1.01,
        xanchor="left", x=0,
        bgcolor="rgba(0,0,0,0)", font=dict(size=11)
    ),
    xaxis_rangeslider_visible=False,
    xaxis4=dict(
        rangeselector=dict(
            buttons=[
                dict(count=1,  label="1H",  step="hour",  stepmode="backward"),
                dict(count=6,  label="6H",  step="hour",  stepmode="backward"),
                dict(count=1,  label="1D",  step="day",   stepmode="backward"),
                dict(count=7,  label="1W",  step="day",   stepmode="backward"),
                dict(count=1,  label="1M",  step="month", stepmode="backward"),
                dict(count=3,  label="3M",  step="month", stepmode="backward"),
                dict(count=1,  label="1Y",  step="year",  stepmode="backward"),
                dict(step="all", label="All"),
            ],
            bgcolor="#1e222d", activecolor="#2962ff",
            font=dict(color="#d1d4dc"),
        ),
        type="date"
    ),
    margin=dict(l=10, r=10, t=60, b=10),
)
# Style all axes
for axis in ["xaxis", "xaxis2", "xaxis3", "xaxis4",
             "yaxis", "yaxis2", "yaxis3", "yaxis4"]:
    fig.update_layout(**{axis: dict(
        gridcolor="#1e222d", gridwidth=0.5,
        zerolinecolor="#363a45",
    )})

st.plotly_chart(fig, use_container_width=True)

# ── Runtime summary ───────────────────────────────────────────────────────────
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
    st.dataframe(display_mode_table, use_container_width=True, hide_index=True)

# ── Equity and drawdown ───────────────────────────────────────────────────────
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
                x=start_line_x, y=[STARTING_BALANCE_USD]*2,
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
        st.plotly_chart(eq_fig, use_container_width=True)

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
        st.plotly_chart(dd_fig, use_container_width=True)

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
    st.plotly_chart(pnl_fig, use_container_width=True)

# ── Recent execution context ──────────────────────────────────────────────────
st.markdown("### Recent Execution Context")
if not tr.empty:
    recent_trades = tr.sort_values("ts", ascending=False).head(12).copy()
    if "ts" in recent_trades.columns:
        recent_trades["ts"] = pd.to_datetime(recent_trades["ts"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    ordered_cols = [
        col for col in ["ts", "run_mode", "side", "qty", "price", "pnl", "regime", "strategy_version"]
        if col in recent_trades.columns
    ]
    st.dataframe(recent_trades[ordered_cols], use_container_width=True, hide_index=True)
else:
    st.info("No runtime trades recorded yet for the selected strategy/mode.")

# ── Auto-refresh ──────────────────────────────────────────────────────────────
if autoref:
    import time
    placeholder = st.empty()
    for remaining in range(15, 0, -1):
        placeholder.caption(f"⏱ Auto-refresh in {remaining}s  •  Toggle off in sidebar to pause")
        time.sleep(1)
    placeholder.empty()
    st.rerun()

