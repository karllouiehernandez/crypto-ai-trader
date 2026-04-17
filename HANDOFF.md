# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Codex |
| **Last updated** | 2026-04-17 (Sprint 15 closed) |
| **Sprint completed** | Sprint 15 ✅ — committed + pushed to GitHub |
| **Next sprint** | Sprint 16 — Exchange Fill Reconciliation (use Binance executed qty / avg fill price instead of requested qty / signal price) |
| **Blocking issues** | Add one of: `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, or `OPENROUTER_API_KEY` to `.env` for LLM features |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Sprint 15 complete; GitHub issue closeout blocked by app permissions |

---

## Resume Here — Sprint 16: Exchange Fill Reconciliation

**Sprint 15 complete.** Order fill confirmation is now wired. 387 tests passing.

### What was done in Sprint 15
- `simulator/paper_trader.py` — `_submit_order()` now returns `bool`; buy/sell paths submit first and only mutate paper state on success; failed live sells preserve position + cost basis unchanged
- `tests/test_live_trade_gate.py` — assertions updated for boolean submit contract; added regressions for aborted fills on submission failure and applied fills on success
- **387 total passing** (+4 from Sprint 15)

### Sprint 16 Goal — Exchange Fill Reconciliation
Current live-trading state now waits for order submission success, but paper fills still use the **requested qty** and **signal price** rather than Binance's actual executed quantity / fill price. This can still drift from exchange reality when partial fills, step-size rounding, or slippage differ from the signal assumptions. Fix this by reading the Binance order response and applying internal state from the confirmed execution data.

### Scope
- `simulator/paper_trader.py` — change `_submit_order` to return structured execution data for live orders (executed qty, average fill price, maybe order id/status), while preserving paper-mode behavior
- `simulator/paper_trader.py` — update `_auto_buy` / `_auto_sell` to apply cash, position, cost basis, and realised P&L from the confirmed execution values instead of assumed `qty` and `price`
- `tests/test_live_trade_gate.py` or a new focused test file — add cases for partial fills, response-based price slippage, and failure/non-filled statuses

### Step 1 — Verify baseline
```bash
pytest tests/ -q   # must show 387 passed
```

### Step 2 — Sprint close checklist
- [ ] All CRITICAL and HIGH review findings fixed
- [ ] `knowledge/sprint_log.md` updated with Sprint 16 entry
- [ ] `HANDOFF.md` Current State table updated
- [ ] Committed and pushed to GitHub
- [ ] GitHub issue created and closed for Sprint 16

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
