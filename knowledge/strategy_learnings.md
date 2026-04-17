# Strategy Learnings

What signal configurations worked, what failed, and why.
Update this file after every backtest and after every paper trading session.

---

## Current Strategy — Sprint 4 (2026-04-17)

**Name:** 3-condition mean reversion
**Location:** `strategy/signal_engine.py`
**Status:** ACTIVE (paper trading)

**Buy signal:**
- RSI-14 < 35 (oversold — note: standard threshold is 30, ours is slightly loose)
- Close price < Bollinger Band lower band (BB-20)
- MACD line crosses above signal line (bullish crossover on current vs prior candle)
- Close price > EMA-200 (trend filter — uptrend required for long entries)
- Entry candle volume >= 1.5× 20-period volume average (volume confirmation)

**Sell signal:**
- RSI-14 > 70 (overbought)
- Close price > Bollinger Band upper band
- MACD line crosses below signal line (bearish crossover)
- Close price < EMA-200 (trend filter — downtrend required for short entries)
- Entry candle volume >= 1.5× 20-period volume average (volume confirmation)

**Otherwise:** HOLD

**Regime gate (Sprint 5):**
- Mean-reversion BUY/SELL only fires when `detect_regime(df) == RANGING`
- HIGH_VOL regime halts all signals immediately (highest priority)
- SQUEEZE and TRENDING regimes also suppress mean-reversion (return HOLD)
- Regime priority: HIGH_VOL > SQUEEZE > TRENDING > RANGING

**Known weaknesses:**
1. All conditions must fire simultaneously — very rare, may miss many valid entries
2. EMA-200 runs on 1m candles (3.3h context) not 1h candles (8.3d context) as specified — see `parameter_history.md` 2026-04-17 for design rationale; proper 1h EMA-200 deferred to Sprint 6+
3. No multi-timeframe confirmation (1m+5m+15m) — deferred from Sprint 4; requires separate data feeds; target Sprint 6+
4. HIGH_VOL short window is 10 1m-candles (prototype); production spec is 30-day baseline — deferred to later sprint
5. Minimum 210 candles required — ~3.5h wait before any signal can fire

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
