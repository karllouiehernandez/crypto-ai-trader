# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Codex |
| **Last updated** | 2026-04-18 (Sprint 22 closed) |
| **Sprint completed** | Sprint 22 ✅ — Strategy comparison and evaluation UX committed + pushed to GitHub |
| **Next sprint** | Sprint 23 — Strategy Parameters & Scenario Presets |
| **Blocking issues** | Add one of: `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, or `OPENROUTER_API_KEY` to `.env` for LLM features |
| **Local worktree note** | `knowledge/experiment_log.md` is expected to stay dirty while the background runtime process is running; do not edit or stage it unless you intentionally stop that process |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Sprint 22 complete; next agent should move from comparison-only UX into parameterized scenario evaluation inside the workbench |

---

## Resume Here — Sprint 23: Strategy Parameters & Scenario Presets

**Sprint 22 complete.** The dashboard can now compare saved strategy candidates and rank saved runs directly inside `Backtest Lab`. 415 tests passing.

### What was done in Sprint 22
- `dashboard/workbench.py` — MODIFIED: added pure helper logic for ranking strategy candidates and sorting saved backtest runs into a leaderboard
- `dashboard/streamlit_app.py` — MODIFIED: added comparison overview cards, a candidate comparison table, a saved-run leaderboard, and focus-strategy ranking context in `Backtest Lab`
- `.codex/skills/jesse-workbench-ui-ux/SKILL.md` — REVIEWED: confirmed the new comparison surfaces still match the Jesse-like research workflow
- **415 total passing** (+2 over Sprint 21)

### Sprint 23 Goal — Strategy Parameters & Scenario Presets
The workbench can now compare saved runs, but it still treats every backtest as a fixed no-parameter scenario. Add parameter-aware evaluation controls so a user can adjust strategy inputs, save scenario context with the run, and compare parameterized candidates without leaving the dashboard.

### Scope
- `dashboard/streamlit_app.py` — surface parameter controls from each strategy’s `param_schema()` / `default_params()` in `Backtest Lab`
- `backtester/service.py` and related persistence — store selected parameter payloads so saved runs are scenario-aware instead of all looking identical
- `dashboard/workbench.py` — add pure helpers for formatting or comparing parameterized scenarios where useful
- keep the tabbed Jesse-like workbench structure intact; parameter entry should feel like part of the same research loop
- review `.codex/skills/jesse-workbench-ui-ux/SKILL.md` if scenario or parameter UX requires updated rules

### Step 1 — Verify baseline
```bash
pytest tests/ -q   # must show 415 passed
```

### Step 2 — Sprint close checklist
- [ ] All CRITICAL and HIGH review findings fixed
- [ ] `knowledge/sprint_log.md` updated with Sprint 23 entry
- [ ] `HANDOFF.md` Current State table updated
- [ ] Committed and pushed to GitHub
- [ ] GitHub issue created and closed for Sprint 23

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
| Sprint 17 — Backtest & Runtime Visualization Hardening | ✅ CLOSED | Codex | 2026-04-17 |
| Sprint 18 — Strategy Generation & Evaluation Workflow | ✅ CLOSED | Codex | 2026-04-17 |
| Sprint 19 — Paper/Live Strategy Monitoring | ✅ CLOSED | Codex | 2026-04-17 |
| Sprint 20 — Manual Agent Strategy Workflow | ✅ CLOSED | Codex | 2026-04-18 |
| Sprint 21 — Jesse-Like Workbench Polish | ✅ CLOSED | Codex | 2026-04-18 |
| Sprint 22 — Strategy Comparison & Evaluation UX | ✅ CLOSED | Codex | 2026-04-18 |

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
