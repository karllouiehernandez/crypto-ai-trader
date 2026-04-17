# crypto_ai_trader/dashboard/streamlit_app.py
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import DB_PATH, SYMBOLS, STARTING_BALANCE_USD, LIVE_TRADE_ENABLED
from strategy.ta_features import add_indicators
from strategy.regime import detect_regime, Regime
from database.promotion_queries import query_promotions

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
            "SELECT ts, side, price FROM trades WHERE symbol = ? ORDER BY ts",
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
        df = pd.read_sql("SELECT ts, equity FROM portfolio ORDER BY ts", con, parse_dates=["ts"])
        con.close()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=30)
def load_promotions() -> pd.DataFrame:
    return query_promotions(DB_PATH)


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

# ── Timeframe selector (horizontal buttons) ───────────────────────────────────
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
tr = load_trades(symbol)
eq = load_equity()

# ── Sidebar: regime & metrics ─────────────────────────────────────────────────
regime = None
if not df.empty and len(df) >= 2:
    try:
        regime = detect_regime(df)
        last   = df.iloc[-1]
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📊 Current Regime")
        st.sidebar.markdown(f"**{_REGIME_EMOJI[regime]}**")
        st.sidebar.markdown(f"Active strategy: **{_REGIME_STRATEGY[regime]}**")
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

# ── Equity curve ──────────────────────────────────────────────────────────────
if not eq.empty:
    eq_fig = go.Figure()
    eq_fig.add_trace(go.Scatter(
        x=eq.ts, y=eq.equity, name="Equity",
        line=dict(color="#2962ff", width=2),
        fill="tozeroy", fillcolor="rgba(41,98,255,0.08)"
    ))
    start_line_x = [eq.ts.min(), eq.ts.max()]
    eq_fig.add_trace(go.Scatter(
        x=start_line_x, y=[STARTING_BALANCE_USD]*2,
        name="Starting Balance", line=dict(color="gray", dash="dot", width=1)
    ))
    eq_fig.update_layout(
        title="Paper Equity (USD)", height=220,
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font=dict(color="#d1d4dc"),
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(gridcolor="#1e222d"),
        yaxis=dict(gridcolor="#1e222d"),
    )
    st.plotly_chart(eq_fig, use_container_width=True)

# ── Auto-refresh ──────────────────────────────────────────────────────────────
if autoref:
    import time
    placeholder = st.empty()
    for remaining in range(15, 0, -1):
        placeholder.caption(f"⏱ Auto-refresh in {remaining}s  •  Toggle off in sidebar to pause")
        time.sleep(1)
    placeholder.empty()
    st.rerun()

