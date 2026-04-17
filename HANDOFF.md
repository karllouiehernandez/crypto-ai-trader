# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Codex |
| **Last updated** | 2026-04-18 (Sprint 20 closed) |
| **Sprint completed** | Sprint 20 ✅ — manual agent strategy workflow committed + pushed to GitHub |
| **Next sprint** | Sprint 21 — Jesse-Like Workbench Polish |
| **Blocking issues** | Add one of: `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, or `OPENROUTER_API_KEY` to `.env` for LLM features |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Sprint 20 complete; next agent should unify and polish the full Jesse-like workbench flow |

---

## Resume Here — Sprint 21: Jesse-Like Workbench Polish

**Sprint 20 complete.** The workbench now has an explicit manual agent strategy workflow with draft-vs-reviewed cues in the repo and dashboard. 413 tests passing.

### What was done in Sprint 20
- `strategies/README.md` — NEW: documented the manual plugin workflow, naming conventions, and draft-to-reviewed promotion path
- `strategies/_strategy_template.py` — NEW: added a non-loadable template strategy for agents to start from safely
- `strategies/example_rsi_mean_reversion.py` — MODIFIED: enriched the example plugin metadata so it behaves like a reviewed reference
- `llm/generator.py` — MODIFIED: generated strategy files now carry an explicit draft-review header
- `dashboard/workbench.py` — MODIFIED: added workflow-stage derivation from strategy metadata and persisted backtest history
- `dashboard/streamlit_app.py` — MODIFIED: added manual workflow guidance plus draft/review/evaluation messaging in the `Strategies` and `Backtest Lab` surfaces
- `.codex/skills/jesse-workbench-ui-ux/SKILL.md` — MODIFIED: updated the repo-local skill to encode generated-draft vs reviewed-plugin behavior
- **413 total passing** (+2 from Sprint 20)

### Sprint 21 Goal — Jesse-Like Workbench Polish
The workflow pieces now exist end-to-end, but the overall dashboard still feels like multiple adjacent tools instead of one polished Jesse-like workbench. Refine navigation, status clarity, and evaluation flow so the path from strategy discovery to backtest to runtime feels more coherent and deliberate.

### Scope
- `dashboard/streamlit_app.py` — tighten visual grouping and navigation so `Strategies`, `Backtest Lab`, and `Runtime Monitor` feel like one continuous workbench rather than separate blocks
- `dashboard/workbench.py` — keep pushing derived workflow/status logic into pure helpers where possible
- `.codex/skills/jesse-workbench-ui-ux/SKILL.md` — review against the final workbench polish pass and update if the information architecture shifts
- maintain compatibility with the existing strategy runtime, persisted backtests, and runtime attribution already in place

### Step 1 — Verify baseline
```bash
pytest tests/ -q   # must show 413 passed
```

### Step 2 — Sprint close checklist
- [ ] All CRITICAL and HIGH review findings fixed
- [ ] `knowledge/sprint_log.md` updated with Sprint 21 entry
- [ ] `HANDOFF.md` Current State table updated
- [ ] Committed and pushed to GitHub
- [ ] GitHub issue created and closed for Sprint 21

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
