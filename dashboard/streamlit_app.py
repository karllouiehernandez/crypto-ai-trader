# crypto_ai_trader/dashboard/streamlit_app.py
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from config import DB_PATH, SYMBOLS, STARTING_BALANCE_USD
from strategy.ta_features import add_indicators
from strategy.regime import detect_regime, Regime

# Regime display config
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

# ───── helpers ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_candles(sym: str, days: int) -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    q = """
        SELECT open_time, open, high, low, close, volume
        FROM candles
        WHERE symbol = ? AND open_time >= ?
        ORDER BY open_time
    """
    df = pd.read_sql(q, con, params=[sym, since], parse_dates=["open_time"])
    con.close()
    return df

@st.cache_data(ttl=30)
def load_trades(sym: str) -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT ts, side, price FROM trades WHERE symbol = ? ORDER BY ts",
        con, params=[sym], parse_dates=["ts"]
    )
    con.close()
    return df

@st.cache_data(ttl=30)
def load_equity() -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT ts, equity FROM portfolio ORDER BY ts", con, parse_dates=["ts"])
    con.close()
    return df

# ───── Streamlit layout ──────────────────────────────────────────────────────
st.set_page_config(page_title="Crypto-AI Trader", layout="wide")

st.sidebar.title("⚙️ Controls")
symbol     = st.sidebar.selectbox("Symbol", SYMBOLS)
lookback_d = st.sidebar.slider("Look-back (days)", 1, 30, 7)
autoref    = st.sidebar.checkbox("Auto-refresh (30 s)", value=True)

# Data
raw = load_candles(symbol, lookback_d)
df  = add_indicators(raw) if not raw.empty else raw
tr  = load_trades(symbol)
eq  = load_equity()

# ── Regime & live metrics (sidebar) ──────────────────────────────────────────
if not df.empty and len(df) >= 2:
    regime = detect_regime(df)
    last   = df.iloc[-1]
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Current Regime")
    st.sidebar.markdown(f"**{_REGIME_EMOJI[regime]}**")
    st.sidebar.markdown(f"Active strategy: **{_REGIME_STRATEGY[regime]}**")
    st.sidebar.markdown("---")
    st.sidebar.metric("RSI-14",  f"{last.rsi_14:.1f}"  if "rsi_14"  in df.columns else "—")
    st.sidebar.metric("ADX-14",  f"{last.adx_14:.1f}"  if "adx_14"  in df.columns else "—")
    st.sidebar.metric("BB Width",f"{last.bb_width:.4f}" if "bb_width" in df.columns else "—")

# Sidebar equity metric
if not eq.empty:
    st.sidebar.metric("Equity (USD)", f"{eq.equity.iloc[-1]:.2f}")
else:
    st.sidebar.metric("Equity (USD)", f"{STARTING_BALANCE_USD:.2f}")

# ── price chart ───────────────────────────────────────────────────────────────
regime_label = _REGIME_EMOJI.get(regime, "") if (not df.empty and len(df) >= 2) else ""
price_fig = go.Figure()

if not df.empty:
    price_fig.add_trace(go.Candlestick(
        x=df.open_time, open=df.open, high=df.high, low=df.low, close=df.close,
        name="OHLC"
    ))
    if "ma_21" in df.columns:
        price_fig.add_trace(go.Scatter(x=df.open_time, y=df.ma_21, name="SMA 21", line=dict(width=1)))
    if "ma_55" in df.columns:
        price_fig.add_trace(go.Scatter(x=df.open_time, y=df.ma_55, name="SMA 55", line=dict(width=1)))
    if "ema_9" in df.columns:
        price_fig.add_trace(go.Scatter(x=df.open_time, y=df.ema_9,  name="EMA 9",  line=dict(width=1, dash="dot")))
    if "ema_21" in df.columns:
        price_fig.add_trace(go.Scatter(x=df.open_time, y=df.ema_21, name="EMA 21", line=dict(width=1, dash="dot")))
    if "ema_55" in df.columns:
        price_fig.add_trace(go.Scatter(x=df.open_time, y=df.ema_55, name="EMA 55", line=dict(width=1, dash="dot")))
    if "bb_hi" in df.columns:
        price_fig.add_trace(go.Scatter(x=df.open_time, y=df.bb_hi, name="BB High", line=dict(width=0.5, dash="dot")))
    if "bb_lo" in df.columns:
        price_fig.add_trace(go.Scatter(x=df.open_time, y=df.bb_lo, name="BB Low",  line=dict(width=0.5, dash="dot")))

    if not tr.empty:
        buys  = tr[tr.side == "BUY"]
        sells = tr[tr.side == "SELL"]
        price_fig.add_trace(go.Scatter(
            x=buys.ts, y=buys.price, mode="markers", name="BUY",
            marker=dict(symbol="triangle-up", size=10, color="green")
        ))
        price_fig.add_trace(go.Scatter(
            x=sells.ts, y=sells.price, mode="markers", name="SELL",
            marker=dict(symbol="triangle-down", size=10, color="red")
        ))
else:
    price_fig.add_annotation(text="No data available — load candles first",
                              xref="paper", yref="paper", x=0.5, y=0.5,
                              showarrow=False, font=dict(size=16))

price_fig.update_layout(
    title=f"{symbol} Price & Indicators  {regime_label}",
    height=600, xaxis_rangeslider_visible=False
)

# ── ADX chart ─────────────────────────────────────────────────────────────────
adx_fig = go.Figure()
if not df.empty and "adx_14" in df.columns:
    adx_fig.add_trace(go.Scatter(x=df.open_time, y=df.adx_14, name="ADX-14", line=dict(color="orange")))
    adx_fig.add_shape(type="line", x0=df.open_time.min(), x1=df.open_time.max(),
                      y0=25, y1=25, line=dict(dash="dot", width=1, color="gray"))
adx_fig.update_layout(height=180, showlegend=False, title="ADX-14  (25 = trend threshold)")

# ── MACD / RSI ────────────────────────────────────────────────────────────────
macd_fig = go.Figure()
if not df.empty and "macd" in df.columns:
    macd_fig.add_trace(go.Scatter(x=df.open_time, y=df.macd,   name="MACD"))
    macd_fig.add_trace(go.Scatter(x=df.open_time, y=df.macd_s, name="Signal"))
macd_fig.update_layout(height=200, showlegend=False)

rsi_fig = go.Figure()
if not df.empty and "rsi_14" in df.columns:
    rsi_fig.add_trace(go.Scatter(x=df.open_time, y=df.rsi_14, name="RSI-14"))
    for lvl in (70, 35):
        rsi_fig.add_shape(type="line", x0=df.open_time.min(), x1=df.open_time.max(),
                          y0=lvl, y1=lvl, line=dict(dash="dot", width=0.5))
rsi_fig.update_layout(height=200, showlegend=False)

# ── equity ────────────────────────────────────────────────────────────────────
eq_fig = go.Figure()
eq_fig.add_trace(go.Scatter(x=eq.ts, y=eq.equity, name="Equity"))
eq_fig.update_layout(title="Paper Equity", height=250)

# Layout
st.plotly_chart(price_fig, use_container_width=True)
c1, c2, c3 = st.columns(3)
c1.plotly_chart(macd_fig, use_container_width=True)
c2.plotly_chart(rsi_fig,  use_container_width=True)
c3.plotly_chart(adx_fig,  use_container_width=True)
st.plotly_chart(eq_fig, use_container_width=True)

# Auto-refresh must be last — st.rerun() interrupts execution immediately
if autoref:
    import time
    time.sleep(30)
    st.rerun()
