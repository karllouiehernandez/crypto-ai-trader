# Strategy Learnings

What signal configurations worked, what failed, and why.
Update this file after every backtest and after every paper trading session.

---

## Current Strategy — Baseline (2026-04-16)

**Name:** 3-condition mean reversion
**Location:** `strategy/signal_engine.py`
**Status:** ACTIVE (paper trading)

**Buy signal:**
- RSI-14 < 35 (oversold — note: standard threshold is 30, ours is slightly loose)
- Close price < Bollinger Band lower band (BB-20)
- MACD line crosses above signal line (bullish crossover on current vs prior candle)

**Sell signal:**
- RSI-14 > 70 (overbought)
- Close price > Bollinger Band upper band
- MACD line crosses below signal line (bearish crossover)

**Otherwise:** HOLD

**Known weaknesses:**
1. All three conditions must fire simultaneously — very rare, may miss many valid entries
2. No trend filter — will trade counter to strong trends, increasing losing trades
3. No volume confirmation — false breakouts not filtered
4. No ATR stop-loss — open-ended risk on each trade
5. No regime gate — runs the same logic in trending and ranging markets
6. Minimum 60 candles (1 hour) — cannot trade in the first hour after data loads

**Backtest results:** None yet (backtester was broken at project start — fixed in Sprint 0)

**Paper trading results:** Not yet collected

---

## Planned Improvements (by sprint)

| Sprint | Improvement | Expected Impact |
|--------|-------------|-----------------|
| 4 | Add 200 EMA trend filter | Reduce losing trades in trending markets by ~40% |
| 4 | Multi-timeframe confirmation (1m+5m+15m) | Reduce false signals |
| 4 | Volume confirmation (1.5× avg) | Filter low-conviction entries |
| 5 | Regime detection (ADX gate) | Only use mean reversion when ADX < 20 |
| 6 | Add momentum strategy (EMA crossover) | Capture trending regime alpha |
| 6 | Add volatility squeeze strategy | Capture pre-breakout compression plays |

---

## Experiment Results

_(Add entries here after each experiment is completed — see experiment_log.md for in-progress experiments)_
