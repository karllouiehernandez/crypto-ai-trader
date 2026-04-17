# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Codex |
| **Last updated** | 2026-04-17 (Sprint 19 closed) |
| **Sprint completed** | Sprint 19 ✅ — paper/live strategy monitoring committed and ready to push |
| **Next sprint** | Sprint 20 — Manual Agent Strategy Workflow |
| **Blocking issues** | Add one of: `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, or `OPENROUTER_API_KEY` to `.env` for LLM features |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Sprint 19 complete; next agent should formalize the manual agent strategy workflow around plugins and generated drafts |

---

## Resume Here — Sprint 20: Manual Agent Strategy Workflow

**Sprint 19 complete.** The workbench now separates paper/live runtime monitoring more clearly and lets the runtime view follow strategy attribution instead of only the active strategy. 411 tests passing.

### What was done in Sprint 19
- `dashboard/workbench.py` — MODIFIED: added runtime strategy discovery, per-mode runtime summaries, cumulative realised P&L helper, and richer runtime summary fields
- `dashboard/streamlit_app.py` — MODIFIED: runtime monitor now has an explicit strategy view selector, mode comparison table, paper/live-aware equity and drawdown charts, realised P&L curve, and denser execution context with qty/pnl fields
- `.codex/skills/jesse-workbench-ui-ux/SKILL.md` — REVIEWED to ensure the runtime-monitor changes still fit the workbench UX
- `tests/test_workbench_helpers.py` — MODIFIED: added runtime-monitor helper coverage
- **411 total passing** (+3 from Sprint 19)

### Sprint 20 Goal — Manual Agent Strategy Workflow
The workbench can now generate, backtest, and monitor strategies, but the manual agent path is still underspecified. Formalize the “agent creates or edits a plugin strategy -> dashboard discovers it -> user evaluates it -> user knows whether it is ready for paper/live” workflow so Codex, Claude Code, and Copilot Pro can all contribute strategies consistently.

### Scope
- `strategies/` + repo docs — add or refine plugin templates/examples so agent-authored strategies follow one predictable contract and naming/versioning scheme
- `llm/generator.py` / generation workflow — make generated-strategy outputs easier to review, revise, and distinguish from hand-authored plugins
- `dashboard/streamlit_app.py` — add clearer “generated draft vs reviewed plugin” cues and tighten the evaluation-to-paper workflow messaging
- Review `.codex/skills/jesse-workbench-ui-ux/SKILL.md` again while formalizing the agent strategy workflow so the UX stays Jesse-like and handoff-safe

### Step 1 — Verify baseline
```bash
pytest tests/ -q   # must show 411 passed
```

### Step 2 — Sprint close checklist
- [ ] All CRITICAL and HIGH review findings fixed
- [ ] `knowledge/sprint_log.md` updated with Sprint 20 entry
- [ ] `HANDOFF.md` Current State table updated
- [ ] Committed and pushed to GitHub
- [ ] GitHub issue created and closed for Sprint 20

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
