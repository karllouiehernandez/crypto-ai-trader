# crypto_ai_trader/dashboard/streamlit_app.py
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# simulate_trades and ai_engine are planned for Sprint 7 — not yet implemented

import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import ta
import streamlit as st
import plotly.graph_objects as go

from crypto_ai_trader.config import (
    DB_PATH, SYMBOLS, STARTING_BALANCE_USD
)

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

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["ma_21"]  = ta.trend.sma_indicator(out.close, 21)
    out["ma_55"]  = ta.trend.sma_indicator(out.close, 55)
    macd          = ta.trend.MACD(out.close)
    out["macd"]   = macd.macd()
    out["macd_s"] = macd.macd_signal()
    out["rsi_14"] = ta.momentum.RSIIndicator(out.close, 14).rsi()
    bb            = ta.volatility.BollingerBands(out.close, 20)
    out["bb_hi"]  = bb.bollinger_hband()
    out["bb_lo"]  = bb.bollinger_lband()
    return out.dropna()

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
df  = add_indicators(raw)
tr  = load_trades(symbol)
eq  = load_equity()

# ── price chart
price_fig = go.Figure()
price_fig.add_trace(go.Candlestick(
    x=df.open_time, open=df.open, high=df.high, low=df.low, close=df.close,
    name="OHLC"
))
price_fig.add_trace(go.Scatter(x=df.open_time, y=df.ma_21, name="MA 21", line=dict(width=1)))
price_fig.add_trace(go.Scatter(x=df.open_time, y=df.ma_55, name="MA 55", line=dict(width=1)))
price_fig.add_trace(go.Scatter(x=df.open_time, y=df.bb_hi, name="BB High", line=dict(width=0.5, dash="dot")))
price_fig.add_trace(go.Scatter(x=df.open_time, y=df.bb_lo, name="BB Low", line=dict(width=0.5, dash="dot")))

if not tr.empty:
    buys  = tr[tr.side == "BUY"]
    sells = tr[tr.side == "SELL"]
    price_fig.add_trace(go.Scatter(
        x=buys.ts, y=buys.price, mode="markers", name="BUY",
        marker=dict(symbol="triangle-up", size=10)
    ))
    price_fig.add_trace(go.Scatter(
        x=sells.ts, y=sells.price, mode="markers", name="SELL",
        marker=dict(symbol="triangle-down", size=10)
    ))

price_fig.update_layout(
    title=f"{symbol} Price & Indicators",
    height=600, xaxis_rangeslider_visible=False
)

# ── MACD / RSI
macd_fig = go.Figure()
macd_fig.add_trace(go.Scatter(x=df.open_time, y=df.macd, name="MACD"))
macd_fig.add_trace(go.Scatter(x=df.open_time, y=df.macd_s, name="Signal"))
macd_fig.update_layout(height=200, showlegend=False)

rsi_fig = go.Figure()
rsi_fig.add_trace(go.Scatter(x=df.open_time, y=df.rsi_14, name="RSI-14"))
for lvl in (70, 30):
    rsi_fig.add_shape(type="line", x0=df.open_time.min(), x1=df.open_time.max(),
                      y0=lvl, y1=lvl, line=dict(dash="dot", width=0.5))
rsi_fig.update_layout(height=200, showlegend=False)

# ── equity
eq_fig = go.Figure()
eq_fig.add_trace(go.Scatter(x=eq.ts, y=eq.equity, name="Equity"))
eq_fig.update_layout(title="Paper Equity", height=250)

# Layout
st.plotly_chart(price_fig, use_container_width=True)
c1, c2 = st.columns(2)
c1.plotly_chart(macd_fig, use_container_width=True)
c2.plotly_chart(rsi_fig,  use_container_width=True)
st.plotly_chart(eq_fig, use_container_width=True)

# Sidebar equity metric
st.sidebar.metric("Equity (USD)", f"{eq.equity.iloc[-1]:.2f}" if not eq.empty else f"{STARTING_BALANCE_USD:.2f}")

# Auto-refresh must be last — st.rerun() interrupts execution immediately
if autoref:
    import time
    time.sleep(30)
    st.rerun()
