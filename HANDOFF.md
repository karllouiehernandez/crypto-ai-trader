# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Codex |
| **Last updated** | 2026-04-18 (Sprint 24 ready; Sprint 25 queued) |
| **Sprint completed** | Sprint 23 ✅ — Strategy parameters and run-scoped scenarios committed + pushed to GitHub |
| **Next sprint** | Sprint 24 — Named Scenario Presets |
| **Blocking issues** | Add one of: `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, or `OPENROUTER_API_KEY` to `.env` for LLM features |
| **Local worktree note** | `dashboard/streamlit_app.py` has an uncommitted local compatibility fix; `knowledge/experiment_log.md` may stay dirty while the background runtime process is running. Do not overwrite or stage either blindly. |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Sprint 24 remains the active implementation sprint; Sprint 25 `Weekly Market Focus Selector` is now queued immediately after it with GitHub tracking issue `#26` |

---

## Resume Here — Sprint 24: Named Scenario Presets

**Sprint 23 complete.** The dashboard can now edit backtest params, persist them with saved runs, and compare parameterized scenarios directly inside `Backtest Lab`. 421 tests passing.

### What was done in Sprint 23
- `strategy/base.py`, `strategy/runtime.py` — MODIFIED: added isolated parameter application for backtest strategy instances
- `backtester/engine.py`, `backtester/service.py` — MODIFIED: backtests now accept params and persist them in saved runs
- `dashboard/workbench.py`, `dashboard/streamlit_app.py` — MODIFIED: `Backtest Lab` now renders strategy parameter controls and shows scenario-aware comparison/run views
- **421 total passing** (+6 over Sprint 22)

### Sprint 24 Goal — Named Scenario Presets
Sprint 23 made scenarios run-scoped, but they still vanish into individual backtest records. Add reusable named presets so a user can save a parameter set once, reapply it to future backtests, and compare stable scenario names instead of raw parameter blobs.

### Scope
- `dashboard/streamlit_app.py` — add preset save/apply UX on top of the existing parameter controls in `Backtest Lab`
- persistence layer — introduce a simple store for named presets keyed by strategy
- `dashboard/workbench.py` — add any pure helpers needed for preset labels and scenario formatting
- keep the current run-scoped scenario behavior intact; named presets should be additive, not a replacement
- review `.codex/skills/jesse-workbench-ui-ux/SKILL.md` if preset UX requires explicit workflow guidance

### Queued After Sprint 24 — Sprint 25: Weekly Market Focus Selector
GitHub tracking issue: `#26`

Goal:
- recommend the best Binance spot `USDT` token for the current week using a low-token deterministic ranking flow
- evaluate candidates using the active strategy and active params
- keep the result as research guidance only, not runtime auto-execution

Planned scope:
- add a research-only symbol universe wider than runtime `SYMBOLS`
- rank a dynamic top-liquid Binance `USDT` shortlist using recent backtest results
- persist weekly study runs and ranked candidates
- surface the latest recommendation inside the dashboard workbench
- allow one-click prefill into `Backtest Lab`

Important defaults:
- `config.SYMBOLS` remains the runtime watchlist
- no paper/live auto-switching in Sprint 25
- no LLM requirement in the baseline weekly selector flow
- do not start Sprint 25 until Sprint 24 closes unless the roadmap is explicitly reprioritized

### Step 1 — Verify baseline
```bash
pytest tests/ -q   # must show 421 passed
```

### Step 2 — Sprint close checklist
- [ ] All CRITICAL and HIGH review findings fixed
- [ ] `knowledge/agent_resume.md` updated for Sprint 24
- [ ] `knowledge/sprint_log.md` updated with Sprint 24 entry
- [ ] `HANDOFF.md` Current State table updated
- [ ] `HANDOFF.md` Next sprint updated to `Sprint 25 — Weekly Market Focus Selector`
- [ ] Committed and pushed to GitHub
- [ ] GitHub issue created and closed for Sprint 24

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
| Sprint 23 — Strategy Parameters & Scenario Presets | ✅ CLOSED | Codex | 2026-04-18 |

---

## Agent Protocol

### When you START a session:
1. Read this file
2. Read `knowledge/agent_resume.md`
3. Read only the code files and KB files relevant to the active sprint
4. Read `knowledge/sprint_log.md` only if historical context is actually needed
5. Begin work on the "Resume Here" sprint

### When you END a session (or hit rate limit / cooldown):
1. Update the **Current State** table above (agent name, date, sprint completed/in-progress)
2. Update **Resume Here** with the exact task the next agent should pick up
3. Note any blockers or partial work in a `## In Progress` section below if mid-sprint
4. Update `knowledge/agent_resume.md` with the new compact resume state
5. Update `knowledge/sprint_log.md` with what was done this session

### Token-Saving Rule
- `knowledge/sprint_log.md` is the long-form archive, not the default first-read file
- Agent switching should prefer `HANDOFF.md` + `knowledge/agent_resume.md` + targeted source files
- Only pull historical sprint entries when a decision depends on older implementation details

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
