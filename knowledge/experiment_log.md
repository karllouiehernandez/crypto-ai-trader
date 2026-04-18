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
**Status:** IN PROGRESS — Sprint 31 (2026-04-18)

**Hypothesis:** The current mean reversion strategy takes trades counter to strong trends, which is a primary source of losing trades. Adding a rule that only allows BUY signals when price is above the 200-period EMA (1h timeframe) — and only SELL signals when price is below — should reduce the losing trade rate significantly in trending regimes without meaningfully reducing win rate in ranging markets.

**Method (updated for Sprint 31):**
1. `ema_200` already exists in `strategy/ta_features.py` — no change needed
2. Implemented as a new strategy plugin `strategies/ema200_filtered_momentum.py`
3. Plugin activates in TRENDING and SQUEEZE regimes (not RANGING, which already has EMA-200 gate)
4. Run via dashboard Backtest Lab against available history on BTCUSDT/ETHUSDT
5. Compare Sharpe, max DD, profit factor vs baseline `rsi_mean_reversion_v1` on same window

**Success criteria:** Sharpe improves by ≥ 0.2 OR max drawdown reduces by ≥ 3% with no worse than 10% reduction in trade count

**Symbols tested:** BTCUSDT (primary), ETHUSDT
**Date range:** last 30 days of available data (limited by Sprint 30's on-demand history loading)
**Baseline metrics:** (compare against `rsi_mean_reversion_v1` saved runs in Backtest Lab)

**Result:** Plugin implemented. Run `ema200_filtered_momentum` in Backtest Lab vs `rsi_mean_reversion_v1` baseline to record metrics.
**Conclusion:** (pending — awaiting backtest results)
**Next experiment:** If confirmed, combine with EXP-002 for full signal quality stack
**Promoted to main strategy:** PENDING

---

## EXP-002 — Multi-timeframe confirmation (1m+5m+15m) reduces false signals

**Date started:** (Sprint 4)
**Status:** IN PROGRESS — Sprint 31 (2026-04-18)

**Hypothesis:** Many 1m signals are noise that reverse within a few candles. Requiring the same signal direction on 5m and 15m timeframes before executing should filter out the lowest-quality entries and improve the win rate, at the cost of fewer total trades.

**Method (updated for Sprint 31):**
1. Implemented as new plugin `strategies/mtf_confirmation_strategy.py`
2. Active in RANGING regime — base signal is mean-reversion (RSI + BB)
3. 1m: RSI < 35 + close < BB-lower + close > EMA-200 (long); RSI > 65 + close > BB-upper + close < EMA-200 (short)
4. 5m: RSI < 40 + close < BB-lower (long confirmation); RSI > 60 + close > BB-upper (short)
5. 15m: RSI < 45 + close < BB-lower (long confirmation); RSI > 55 + close > BB-upper (short)
6. Minimum 300 1m candles required for reliable 15m indicator warmup
7. Run via dashboard Backtest Lab, compare vs `rsi_mean_reversion_v1` baseline

**Success criteria:** Win rate improves by ≥ 5% with trade count reduction < 50%

**Result:** Plugin implemented. Run `mtf_confirmation` in Backtest Lab vs `rsi_mean_reversion_v1` baseline to record metrics.
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

## EXP-AUTO-0001 — Self-Learning Evaluation #1
**Date:** 2026-04-17 23:50 UTC
**Status:** COMPLETED

**Paper metrics (30d window):**
  - Sharpe ratio:   4.375
  - Max drawdown:   0.3%
  - Profit factor:  306.372
  - Trade count:    112

**LLM analysis** (fallback — LLM unavailable):
  - Confidence:     0.00
  - Recommendation: HOLD_PAPER
  - Consecutive promotes: 0/3

**Promotion gate:** ❌ FAILED
  Failures: llm_confidence 0.00 < required 0.80; trend gate: only 0/3 recent evals are PROMOTE_TO_LIVE

**Strategy weaknesses:** LLM unavailable — using acceptance gate only
**Parameter suggestions:** none

---

## EXP-AUTO-0001 — Self-Learning Evaluation #1
**Date:** 2026-04-18 00:48 UTC
**Status:** COMPLETED

**Paper metrics (30d window):**
  - Sharpe ratio:   4.253
  - Max drawdown:   0.3%
  - Profit factor:  306.365
  - Trade count:    122

**LLM analysis** (fallback — LLM unavailable):
  - Confidence:     0.00
  - Recommendation: HOLD_PAPER
  - Consecutive promotes: 0/3

**Promotion gate:** ❌ FAILED
  Failures: llm_confidence 0.00 < required 0.80; trend gate: only 0/3 recent evals are PROMOTE_TO_LIVE

**Strategy weaknesses:** LLM unavailable — using acceptance gate only
**Parameter suggestions:** none

---

## EXP-AUTO-0001 — Self-Learning Evaluation #1
**Date:** 2026-04-18 02:00 UTC
**Status:** COMPLETED

**Paper metrics (30d window):**
  - Sharpe ratio:   3.787
  - Max drawdown:   0.3%
  - Profit factor:  306.342
  - Trade count:    172

**LLM analysis** (fallback — LLM unavailable):
  - Confidence:     0.00
  - Recommendation: HOLD_PAPER
  - Consecutive promotes: 0/3

**Promotion gate:** ❌ FAILED
  Failures: llm_confidence 0.00 < required 0.80; trend gate: only 0/3 recent evals are PROMOTE_TO_LIVE

**Strategy weaknesses:** LLM unavailable — using acceptance gate only
**Parameter suggestions:** none

---

## EXP-AUTO-0001 — Self-Learning Evaluation #1
**Date:** 2026-04-18 04:46 UTC
**Status:** COMPLETED

**Paper metrics (30d window):**
  - Sharpe ratio:   3.584
  - Max drawdown:   0.3%
  - Profit factor:  306.334
  - Trade count:    202

**LLM analysis** (fallback — LLM unavailable):
  - Confidence:     0.00
  - Recommendation: HOLD_PAPER
  - Consecutive promotes: 0/3

**Promotion gate:** ❌ FAILED
  Failures: llm_confidence 0.00 < required 0.80; trend gate: only 0/3 recent evals are PROMOTE_TO_LIVE

**Strategy weaknesses:** LLM unavailable — using acceptance gate only
**Parameter suggestions:** none

---

## EXP-AUTO-0001 — Self-Learning Evaluation #1
**Date:** 2026-04-18 04:46 UTC
**Status:** COMPLETED

**Paper metrics (30d window):**
  - Sharpe ratio:   3.584
  - Max drawdown:   0.3%
  - Profit factor:  306.334
  - Trade count:    202

**LLM analysis** (fallback — LLM unavailable):
  - Confidence:     0.00
  - Recommendation: HOLD_PAPER
  - Consecutive promotes: 0/3

**Promotion gate:** ❌ FAILED
  Failures: llm_confidence 0.00 < required 0.80; trend gate: only 0/3 recent evals are PROMOTE_TO_LIVE

**Strategy weaknesses:** LLM unavailable — using acceptance gate only
**Parameter suggestions:** none

---

## EXP-AUTO-0001 — Self-Learning Evaluation #1
**Date:** 2026-04-18 04:57 UTC
**Status:** COMPLETED

**Paper metrics (30d window):**
  - Sharpe ratio:   3.501
  - Max drawdown:   0.3%
  - Profit factor:  305.864
  - Trade count:    218

**LLM analysis** (fallback — LLM unavailable):
  - Confidence:     0.00
  - Recommendation: HOLD_PAPER
  - Consecutive promotes: 0/3

**Promotion gate:** ❌ FAILED
  Failures: llm_confidence 0.00 < required 0.80; trend gate: only 0/3 recent evals are PROMOTE_TO_LIVE

**Strategy weaknesses:** LLM unavailable — using acceptance gate only
**Parameter suggestions:** none

---

## EXP-AUTO-0001 — Self-Learning Evaluation #1
**Date:** 2026-04-18 05:13 UTC
**Status:** COMPLETED

**Paper metrics (30d window):**
  - Sharpe ratio:   3.446
  - Max drawdown:   0.3%
  - Profit factor:  305.882
  - Trade count:    228

**LLM analysis** (fallback — LLM unavailable):
  - Confidence:     0.00
  - Recommendation: HOLD_PAPER
  - Consecutive promotes: 0/3

**Promotion gate:** ❌ FAILED
  Failures: llm_confidence 0.00 < required 0.80; trend gate: only 0/3 recent evals are PROMOTE_TO_LIVE

**Strategy weaknesses:** LLM unavailable — using acceptance gate only
**Parameter suggestions:** none

---
