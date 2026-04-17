# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | GitHub Copilot |
| **Last updated** | 2026-04-18 (Sprint 8) |
| **Sprint completed** | Sprint 8 ✅ |
| **Next sprint** | Sprint 9 (or production deployment) |
| **Blocking issues** | None |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Sprint 8 complete |

---

## Resume Here — Post-Sprint 8

**Sprint 8 is complete.** All 8 planned sprints are now done. 213 tests passing.

### Pre-Live Checklist Status
- [x] Credentials in `.env` (Sprint 0)
- [x] Backtester fixed and validated (Sprint 0)
- [x] ATR-based position sizing (Sprint 3)
- [x] Daily loss limit + drawdown circuit breaker (Sprint 3)
- [x] Test suite passing — 213 tests (Sprint 2+8)
- [x] Knowledge base initialized (Sprint 1+)
- [x] Walk-forward validation with acceptance gates (Sprint 8)
- [ ] **30+ days paper trading with positive Sharpe** — this is the remaining gate

### Next action options
1. **Deploy paper trading**: run `python run_live.py` and monitor for 30+ days
2. **Sprint 9** (optional): multi-exchange support (ccxt), production deployment hardening
3. **Backtest validation**: run `python run_backtest.py BTCUSDT 2023-01-01 2024-12-31` to validate strategy against 2 years of data

### Sprint 8 Files
- `backtester/metrics.py` — pure metric functions
- `backtester/walk_forward.py` — rolling walk-forward engine
- `backtester/engine.py` — slippage-aware fills + `build_equity_curve()`
- `run_backtest.py` — walk-forward CLI (default) + `--no-walk-forward` single mode
- `tests/test_metrics.py` (24 tests), `tests/test_walk_forward.py` (14 tests)

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
| Sprint 8 — Backtesting rigor | ✅ CLOSED | GitHub Copilot | 2026-04-18 |

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
