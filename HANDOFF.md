# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Claude Code |
| **Last updated** | 2026-04-16 |
| **Sprint completed** | Sprint 0 ✅ |
| **Next sprint** | Sprint 1 |
| **Blocking issues** | None |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Claude Code at 93% usage limit — switching to Copilot |

---

## Resume Here — Sprint 1

**GitHub issue:** https://github.com/karllouiehernandez/crypto-ai-trader/issues/2

**Goal:** Create `knowledge/kb_update.py` — a script any agent can run after a trading session to append a structured entry to the knowledge base.

**Acceptance criteria:**
- `python knowledge/kb_update.py` runs without error
- Supports entry types: bug, strategy, experiment, parameter, regime
- Prompts for all KB fields (what happened, why, impact, what changed, next steps)
- Appends a correctly-formatted KB entry to the right `knowledge/` file
- Prints confirmation of what was written and where

**Files to create/modify:**
- `knowledge/kb_update.py` — new interactive CLI script
- `knowledge/sprint_log.md` — update Sprint 1 section on close
- `HANDOFF.md` — update this file when Sprint 1 closes

**After Sprint 1 is done:**
1. Run the code review checklist (see `.github/copilot-instructions.md`)
2. Close GitHub issue #2 with: `gh issue close 2 --comment "Sprint 1 complete"`
3. Update this file with Sprint 2 as the next sprint
4. Do NOT start Sprint 2 until Sprint 1 is reviewed and approved

---

## Sprint History

| Sprint | Status | Closed by | Date |
|--------|--------|-----------|------|
| Sprint 0 — Foundation fixes + credentials | ✅ CLOSED | Claude Code | 2026-04-16 |

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
