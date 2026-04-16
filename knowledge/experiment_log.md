# Experiment Log

Every strategy hypothesis lives here from idea to outcome.
Write the hypothesis BEFORE running the experiment. Fill in the result AFTER.

---

## Experiment Format

```markdown
## EXP-NNN — [ONE LINE HYPOTHESIS]
**Date started:** YYYY-MM-DD
**Status:** [HYPOTHESIS | IN PROGRESS | COMPLETED | ABANDONED]

**Hypothesis:** (what do you expect to happen and why)
**Method:** (exactly what will be changed and how it will be tested)
**Success criteria:** (what metric improvement counts as a win)
**Symbols tested:** 
**Date range:**
**Baseline metrics:** (Sharpe, max DD, profit factor from current strategy)

**Result:** (fill in after experiment)
**Conclusion:** (did it work? why or why not?)
**Next experiment:** (what this result suggests to try next)
**Promoted to main strategy:** YES / NO
```

---

## EXP-001 — Adding 200 EMA trend filter will reduce losing trades in trending markets

**Date started:** (Sprint 4)
**Status:** HYPOTHESIS

**Hypothesis:** The current mean reversion strategy takes trades counter to strong trends, which is a primary source of losing trades. Adding a rule that only allows BUY signals when price is above the 200-period EMA (1h timeframe) — and only SELL signals when price is below — should reduce the losing trade rate significantly in trending regimes without meaningfully reducing win rate in ranging markets.

**Method:**
1. Add `ema_200` to `strategy/ta_features.py` computed on 1h candles
2. Add trend filter gate to `strategy/signal_engine.py`
3. Backtest BTCUSDT on 2023-01-01 to 2024-12-31 (covers bull + bear + ranging)
4. Compare Sharpe, max DD, profit factor, win rate vs baseline (EXP-000)

**Success criteria:** Sharpe improves by ≥ 0.2 OR max drawdown reduces by ≥ 3% with no worse than 10% reduction in trade count

**Symbols tested:** BTCUSDT, ETHUSDT
**Date range:** 2023-01-01 to 2024-12-31
**Baseline metrics:** (run EXP-000 baseline backtest first in Sprint 0)

**Result:** (pending)
**Conclusion:** (pending)
**Next experiment:** If confirmed, try multi-timeframe confirmation (EXP-002)
**Promoted to main strategy:** PENDING

---

## EXP-002 — Multi-timeframe confirmation (1m+5m+15m) reduces false signals

**Date started:** (Sprint 4)
**Status:** HYPOTHESIS

**Hypothesis:** Many 1m signals are noise that reverse within a few candles. Requiring the same signal direction on 5m and 15m timeframes before executing should filter out the lowest-quality entries and improve the win rate, at the cost of fewer total trades.

**Method:**
1. Compute signals on 1m, 5m, 15m candles for the same symbol
2. Only enter if all three timeframes agree on direction
3. Backtest same period as EXP-001

**Success criteria:** Win rate improves by ≥ 5% with trade count reduction < 50%

**Result:** (pending)
**Promoted to main strategy:** PENDING

---

## EXP-003 — ATR-based position sizing reduces drawdown vs flat 30% sizing

**Date started:** (Sprint 3)
**Status:** HYPOTHESIS

**Hypothesis:** The current flat 30% position size is too large and volatility-unaware. In high-volatility regimes (e.g., BTC during a crash), 30% sizing leads to outsized losses. ATR-based sizing (`size = equity × 0.01 / (1.5 × ATR)`) automatically reduces size during volatile periods and increases it during calm periods, producing a smoother equity curve.

**Method:**
1. Implement ATR position sizer in `strategy/risk.py`
2. Backtest same dataset with old sizing vs new sizing
3. Compare max drawdown and Sharpe

**Success criteria:** Max drawdown reduces by ≥ 5% with Sharpe no worse

**Result:** (pending)
**Promoted to main strategy:** PENDING
