# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Codex |
| **Last updated** | 2026-04-17 (Sprint 18 closed) |
| **Sprint completed** | Sprint 18 ✅ — strategy generation/evaluation workflow committed + pushed to GitHub |
| **Next sprint** | Sprint 19 — Paper/Live Strategy Monitoring |
| **Blocking issues** | Add one of: `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, or `OPENROUTER_API_KEY` to `.env` for LLM features |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Sprint 18 complete; next agent should deepen paper/live strategy attribution and monitoring |

---

## Resume Here — Sprint 19: Paper/Live Strategy Monitoring

**Sprint 18 complete.** The workbench now supports dashboard-driven strategy generation/discovery and strategy-scoped evaluation history. 408 tests passing.

### What was done in Sprint 18
- `strategies/loader.py` — MODIFIED: strategy plugins now expose richer provenance/validation metadata and emit explicit validation errors when a file does not define a usable `StrategyBase` subclass; added direct single-file reload helper
- `strategy/runtime.py` — MODIFIED: built-ins now present the same provenance fields as plugins; catalog ordering favors built-ins first, then generated strategies, then normal plugins
- `llm/generator.py` — MODIFIED: added `generate_and_discover_strategy()` so the dashboard can generate, save, reload, and inspect plugin strategies in one flow
- `dashboard/workbench.py` — MODIFIED: added helpers for strategy origin labels, strategy catalog tables, and strategy-scoped saved-run filtering
- `dashboard/streamlit_app.py` — MODIFIED: added a `Generate Strategy Draft` flow, surfaced provider/model/token metadata, highlighted generated-plugin provenance, and focused backtest history on the currently evaluated strategy by default
- `.codex/skills/jesse-workbench-ui-ux/SKILL.md` — REVIEWED to confirm the new workflow still matches the Jesse-like workbench contract
- **408 total passing** (+8 from Sprint 18)

### Sprint 19 Goal — Paper/Live Strategy Monitoring
The dashboard now handles generation, discovery, and backtest evaluation more cleanly, but the runtime monitor still behaves mostly like a filtered observability view. Tighten the paper/live path so strategy attribution, mode attribution, and execution context feel like one continuous workbench from backtest into runtime.

### Scope
- `database/models.py` / runtime queries — ensure paper/live portfolio and trade history expose the fields needed for strategy-aware runtime views without ambiguity
- `dashboard/streamlit_app.py` — deepen `Runtime Monitor` so paper/live mode, active strategy, runtime drawdown, and recent execution context are clearly attributable and easier to compare
- `dashboard/workbench.py` — keep runtime calculations in pure helpers where possible; add any missing aggregation helpers needed for paper/live strategy views
- Review `.codex/skills/jesse-workbench-ui-ux/SKILL.md` again while refining runtime-monitor UX so it stays aligned with the workbench model rather than drifting back to a generic monitor

### Step 1 — Verify baseline
```bash
pytest tests/ -q   # must show 408 passed
```

### Step 2 — Sprint close checklist
- [ ] All CRITICAL and HIGH review findings fixed
- [ ] `knowledge/sprint_log.md` updated with Sprint 19 entry
- [ ] `HANDOFF.md` Current State table updated
- [ ] Committed and pushed to GitHub
- [ ] GitHub issue created and closed for Sprint 19

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
