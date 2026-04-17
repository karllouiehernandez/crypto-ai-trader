# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Codex |
| **Last updated** | 2026-04-17 (Sprint 16 closed) |
| **Sprint completed** | Sprint 16 ✅ — Jesse Workbench Foundation |
| **Next sprint** | Sprint 17 — Backtest & Runtime Visualization Hardening |
| **Blocking issues** | Add one of: `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, or `OPENROUTER_API_KEY` to `.env` for LLM features |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Sprint 16 complete; continue Jesse-like workbench roadmap |

---

## Resume Here — Sprint 17: Backtest & Runtime Visualization Hardening

**Sprint 16 complete.** Jesse-style workbench foundation is now wired. 391 tests passing.

### What was done in Sprint 16
- `strategy/builtin.py` — NEW: first-class selectable built-in strategies (`regime_router_v1`, `mean_reversion_v1`, `momentum_v1`, `breakout_v1`)
- `strategy/runtime.py` — NEW: persisted active-strategy runtime used by backtest, paper, and live
- `database/models.py` — MODIFIED: added `AppSetting`, `BacktestRun`, `BacktestTrade`, `PortfolioSnapshot`; added backward-compatible trade attribution columns
- `simulator/paper_trader.py` — MODIFIED: active strategy loaded at startup; trade and portfolio snapshots are now persisted with strategy/mode metadata
- `dashboard/streamlit_app.py` — MODIFIED: first `Strategy Workbench` slice is live with strategy selection, plugin load/error visibility, `Backtest Lab`, saved backtest runs, and runtime filtering by strategy/mode
- `.codex/skills/jesse-workbench-ui-ux/SKILL.md` — NEW: repo-local Jesse-like UI/UX skill for future agents
- **391 total passing** (+4 from Sprint 16)

### Sprint 17 Goal — Backtest & Runtime Visualization Hardening
The first workbench slice is functional, but it still needs to feel more like a Jesse-style research loop. Complete the visual analysis layer and tighten the runtime monitor so backtests, paper trading, and live trading all surface richer, strategy-attributed information.

### Scope
- `dashboard/streamlit_app.py` — add a proper drawdown chart, richer backtest metrics display, and a clearer saved-run inspection flow; keep strategy identity visible in every panel
- `dashboard/streamlit_app.py` — improve runtime monitor for paper/live by showing tagged trade history, recent execution context, and clearer restart-required messaging after strategy changes
- `backtester/service.py` / dashboard helpers — harden backtest persistence and run querying so the workbench remains stable with repeated runs and larger histories
- Review `.codex/skills/jesse-workbench-ui-ux/SKILL.md` for drift while refining the UX

### Step 1 — Verify baseline
```bash
pytest tests/ -q   # must show 391 passed
```

### Step 2 — Sprint close checklist
- [ ] All CRITICAL and HIGH review findings fixed
- [ ] `knowledge/sprint_log.md` updated with Sprint 17 entry
- [ ] `HANDOFF.md` Current State table updated
- [ ] Committed and pushed to GitHub
- [ ] GitHub issue created and closed for Sprint 17

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
| Sprint 9 — Strategy Plugin System + StrategyBase ABC | ✅ CLOSED | Claude Code | 2026-04-17 |
| Sprint 10 — LLM Core Layer (multi-provider) | ✅ CLOSED | Claude Code | 2026-04-17 |
| Sprint 11 — Self-Learning Loop + KB Integration | ✅ CLOSED | GitHub Copilot | 2026-04-17 |
| Sprint 12 — Live Promotion Coordinator | ✅ CLOSED | Claude Code | 2026-04-17 |
| Sprint 13 — Dashboard Promotion Panel + Live Trade Gate | ✅ CLOSED | Claude Code | 2026-04-17 |
| Sprint 14 — Live Trade Execution Gate | ✅ CLOSED | Claude Code | 2026-04-17 |
| Sprint 15 — Order Fill Confirmation | ✅ CLOSED | Codex | 2026-04-17 |
| Sprint 16 — Jesse Workbench Foundation | ✅ CLOSED | Codex | 2026-04-17 |

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
