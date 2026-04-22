# Knowledge Base Index

This directory is the institutional memory of the crypto_ai_trader project.
Every sprint must read relevant files here before starting, and update them before closing.

---

## Documents

| File | Purpose | Update When |
|------|---------|-------------|
| [sprint_log.md](sprint_log.md) | Sprint progress + code review outcomes | After every sprint closes |
| [bugs_and_fixes.md](bugs_and_fixes.md) | Root cause + fix for every production incident | After any bug is found or fixed |
| [strategy_learnings.md](strategy_learnings.md) | What signal configs worked/failed and why | After any backtest or paper trading session |
| [iteration_learnings.md](iteration_learnings.md) | What each delivery/test iteration taught us and what to change next | After every meaningful validation or implementation slice |
| [experiment_log.md](experiment_log.md) | Hypothesis → test → result for every experiment | Before starting and after completing any experiment |
| [parameter_history.md](parameter_history.md) | Changelog of every config/strategy parameter change | Any time a parameter in config.py or strategy files changes |
| [risk_learnings.md](risk_learnings.md) | Position sizing, stop-loss, drawdown incidents | After any drawdown event or risk rule change |
| [market_regime_notes.md](market_regime_notes.md) | Observed regime patterns + how bot performed | After notable market events or regime transitions |
| [backtest_results/](backtest_results/) | One .md file per backtest run | After every backtest run |

---

## KB Entry Format

All entries across all files follow this structure:

```markdown
## [DATE] [SYMBOL/TOPIC] — [ONE LINE SUMMARY]
**What happened:** (objective description)
**Why it happened:** (root cause or hypothesis)
**Impact:** (P&L, Sharpe, trades affected)
**What we changed:** (code/config diff or "pending")
**What to try next:** (concrete next experiment)
**Status:** [OPEN | RESOLVED | MONITORING]
```

---

## Rules

1. Never leave learnings only in chat history — write them here
2. After every meaningful implementation or validation iteration, add one entry to `iteration_learnings.md`
3. Before changing a parameter, check `parameter_history.md` to avoid re-testing known bad values
4. Before a backtest, check `backtest_results/` for prior runs on the same symbol/period
5. Sprint cannot close until code review sub-agent approves — see `sprint_log.md`
