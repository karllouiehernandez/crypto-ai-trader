# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Claude Code |
| **Last updated** | 2026-04-17 (Sprint 5) |
| **Sprint completed** | Sprint 5 ✅ |
| **Next sprint** | Sprint 6 |
| **Blocking issues** | None |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Sprint 4 complete |

---

## Resume Here — Sprint 6

**GitHub issue:** https://github.com/karllouiehernandez/crypto-ai-trader/issues/7

**Goal:** Multi-strategy portfolio — add momentum and breakout strategies alongside mean reversion.

**Acceptance criteria:**
- `strategy/signal_momentum.py` — EMA9>EMA21>EMA55 + ADX>25 + pullback-to-EMA21 momentum signal; active when regime == TRENDING
- `strategy/signal_breakout.py` — close above 20-period high + volume 2× avg breakout signal; active when regime == SQUEEZE
- `strategy/signal_engine.py` — route to appropriate strategy based on regime (RANGING→mean reversion, TRENDING→momentum, SQUEEZE→breakout, HIGH_VOL→HOLD)
- `strategy/ta_features.py` — add `ema_9`, `ema_21`, `ema_55` columns
- `config.py` — add `BREAKOUT_VOLUME_MULT=2.0`, `BREAKOUT_LOOKBACK=20`
- `tests/test_signal_momentum.py`, `tests/test_signal_breakout.py` — unit tests for new strategies
- `knowledge/sprint_log.md`, `HANDOFF.md`

**Context from prior sprints:**
- `detect_regime()` in `strategy/regime.py` is already wired; just route to new strategies
- Multi-timeframe confirmation still deferred — see `parameter_history.md`

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
