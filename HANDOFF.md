# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | GitHub Copilot |
| **Last updated** | 2026-04-17 (Sprint 7) |
| **Sprint completed** | Sprint 7 ✅ |
| **Next sprint** | Sprint 8 |
| **Blocking issues** | None |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Sprint 7 complete |

---

## Resume Here — Sprint 8

**GitHub issue:** https://github.com/karllouiehernandez/crypto-ai-trader/issues/9

**Goal:** Backtesting rigor — walk-forward validation; slippage modeling; Sharpe/DD/profit-factor acceptance gates.

**Acceptance criteria:**
- `backtester/engine.py` — add slippage (0.05–0.1% per fill) alongside `FEE_RATE`; add `SLIPPAGE_PCT` to `config.py`
- `backtester/walk_forward.py` — new module: rolling 3-month windows (70% train / 30% OOS); returns per-window metrics
- `backtester/metrics.py` — new module: `sharpe_ratio()`, `max_drawdown()`, `profit_factor()`, `acceptance_gate()` (Sharpe > 1.5, max_dd < 20%, PF > 1.5, min 200 trades)
- `run_backtest.py` — run walk-forward by default; print summary table; fail with exit code 1 if acceptance gate not met
- `tests/test_metrics.py`, `tests/test_walk_forward.py` — unit tests
- `knowledge/sprint_log.md`, `HANDOFF.md`

**Context from prior sprints:**
- `backtester/engine.py` now has module-level `log = logging.getLogger(__name__)` (Sprint 7)
- `config.py` has `FEE_RATE=0.001`; add `SLIPPAGE_PCT` alongside it
- `run_backtest.py` currently calls `run_backtest()` from `backtester.engine` directly

---

## Sprint History

| Sprint | Status | Closed by | Date |
|--------|--------|-----------|------|
| Sprint 0 — Foundation fixes + credentials | ✅ CLOSED | Claude Code | 2026-04-16 |
| Sprint 1 — Knowledge base kb_update.py | ✅ CLOSED | GitHub Copilot | 2026-04-16 |
| Sprint 2 — Testing infrastructure | ✅ CLOSED | GitHub Copilot | 2026-04-16 |
| Sprint 3 — Risk management overhaul | ✅ CLOSED | GitHub Copilot | 2026-04-16 |
| Sprint 4 — Signal quality improvements | ✅ CLOSED | Claude Code | 2026-04-17 |
| Sprint 5 — Regime detection | ✅ CLOSED | Claude Code | 2026-04-17 |
| Sprint 6 — Multi-strategy portfolio | ✅ CLOSED | GitHub Copilot | 2026-04-17 |
| Sprint 7 — Dashboard fixes + observability | ✅ CLOSED | GitHub Copilot | 2026-04-17 |

---

## Agent Protocol

### When you START a session:
1. Read this file
2. Read `knowledge/sprint_log.md`
3. Read any KB files relevant to the sprint goal
4. Begin work on the "Resume Here" sprint

### When you END a session (or hit rate limit / cooldown):
1. Update the **Current State** table above (agent name, date, sprint completed/in-progress)
2. Update **Resume Here** with the exact task the next agent should pick up
3. Note any blockers or partial work in a `## In Progress` section below if mid-sprint
4. Update `knowledge/sprint_log.md` with what was done this session

### Handoff note format (add below if mid-sprint):
```markdown
## In Progress — [AGENT NAME] left off here

**Sprint:** Sprint N
**Last file edited:** path/to/file.py
**What was done:** (1-2 sentences)
**What's next:** (exact next step for the incoming agent)
**Partial work notes:** (anything the next agent needs to know)
```

---

## Tech Stack Quick Reference

| Layer | Tech |
|-------|------|
| Language | Python 3.10+ |
| Exchange | python-binance (async) |
| DB | SQLite + SQLAlchemy 2.x |
| Data | pandas, numpy |
| Indicators | ta library |
| Dashboard | Streamlit + Plotly |
| Messaging | Telegram Bot API |
| Async | asyncio, aiosqlite |
| Credentials | python-dotenv (.env file) |

**Run:**
```bash
pip install -r requirements.txt
python run_live.py          # live paper trading
streamlit run dashboard/streamlit_app.py
python run_backtest.py BTCUSDT 2024-01-01 2024-03-31
```
