# Strategy Learnings

What signal configurations worked, what failed, and why.
Update this file after every backtest and after every paper trading session.

---

## Current Strategy — Sprint 6 (2026-04-17)

**Name:** Multi-strategy portfolio with regime routing
**Location:** `strategy/signal_engine.py`, `strategy/signal_momentum.py`, `strategy/signal_breakout.py`
**Status:** ACTIVE (paper trading)

**Regime routing (priority: HIGH_VOL > SQUEEZE > TRENDING > RANGING):**
- HIGH_VOL → HOLD immediately (no strategy fires)
- SQUEEZE → breakout strategy
- TRENDING → momentum strategy
- RANGING → mean-reversion strategy

**Mean-reversion (RANGING regime):**
- Buy: RSI-14 < 35 + close < BB-lower + MACD bullish crossover + close > EMA-200 + volume ≥ 1.5× avg
- Sell: RSI-14 > 70 + close > BB-upper + MACD bearish crossover + close < EMA-200 + volume ≥ 1.5× avg

**Momentum (TRENDING regime — ADX > 25):**
- Buy: EMA9 > EMA21 > EMA55 (stack) + ADX > 25 + close within 0.5% above EMA-21 (pullback) + volume ≥ 1.5× avg
- Sell: EMA9 crosses below EMA21 (momentum reversal crossover)

**Breakout (SQUEEZE regime — BB width below 20th percentile):**
- Buy: close breaks above prior 20-period high + volume ≥ 2× avg
- Sell: close falls below prior 20-period low (trailing stop, no volume confirmation)

**Regime gate:**
- HIGH_VOL: recent realized vol > 2× prior-window baseline → halt all signals
- SQUEEZE: BB width below 20th percentile of available history → breakout watch
- TRENDING: ADX > 25 → momentum strategy active
- RANGING: ADX ≤ 25 → mean-reversion active (default)

**Known weaknesses:**
1. All mean-reversion conditions must fire simultaneously — very rare, may miss many valid entries
2. EMA-200 runs on 1m candles (3.3h context) not 1h candles (8.3d context) as specified — see `parameter_history.md` 2026-04-17 for design rationale; proper 1h EMA-200 deferred to later sprint
3. No multi-timeframe confirmation (1m+5m+15m) — deferred from Sprint 4; requires separate data feeds; target later sprint
4. HIGH_VOL short window is 10 1m-candles (prototype); production spec is 30-day baseline — deferred to later sprint
5. Minimum 210 candles required — ~3.5h wait before any signal can fire
6. Momentum strategy uses same 1m EMA-9/21/55 (short context); true momentum needs 1h+ data

**Backtest results:** None yet (backtester was broken at project start — fixed in Sprint 0)

**Paper trading results:** Not yet collected

---

## Planned Improvements (by sprint)

| Sprint | Improvement | Expected Impact | Status |
|--------|-------------|-----------------|--------|
| 4 | Add 200 EMA trend filter | Reduce losing trades in trending markets by ~40% | ✅ Done |
| 4 | Volume confirmation (1.5× avg) | Filter low-conviction entries | ✅ Done |
| 5 | Regime detection (ADX gate) | Only use mean reversion when ADX < 20 | ✅ Done |
| 6 | Add momentum strategy (EMA crossover) | Capture trending regime alpha | ✅ Done |
| 6 | Add volatility squeeze / breakout strategy | Capture pre-breakout compression plays | ✅ Done |
| 7 | Dashboard observability | Monitor regime + signal distribution in real time | PENDING |
| 8 | Multi-timeframe 1h+ data feed | Proper EMA-200 context + better regime detection | PENDING |

---

## Experiment Results

_(Add entries here after each experiment is completed — see experiment_log.md for in-progress experiments)_
