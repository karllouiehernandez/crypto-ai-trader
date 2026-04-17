# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Claude Code |
| **Last updated** | 2026-04-17 (Sprint 14 closed) |
| **Sprint completed** | Sprint 14 ✅ — committed + pushed to GitHub |
| **Next sprint** | Sprint 15 — Order Fill Confirmation (confirm Binance fill before updating paper state) |
| **Blocking issues** | Add one of: `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, or `OPENROUTER_API_KEY` to `.env` for LLM features |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Sprint 14 complete |

---

## Resume Here — Sprint 15: Order Fill Confirmation

**Sprint 14 complete.** Live Trade Execution Gate is wired. 383 tests passing.

### What was done in Sprint 14
- `simulator/paper_trader.py` — added `LIVE_TRADE_ENABLED` import; `_binance_client=None` attribute; `_submit_order()` async method with `asyncio.wait_for(timeout=10.0)`; called in `_auto_buy` and `_auto_sell`
- `run_live.py` — `log` logger added; credentials + `testnet=BINANCE_TESTNET` passed to `AsyncClient.create()`; `try/finally` closes client on exit; startup warning + Telegram alert
- `tests/test_live_trade_gate.py` — NEW: 12 unit tests
- **383 total passing** (+12 from Sprint 14)

### Sprint 15 Goal — Order Fill Confirmation
Currently paper state (cash/positions) is updated **before** the real Binance order is submitted. If the order fails, internal state is ahead of reality. Fix this by submitting the order first and only applying the internal fill after confirmation.

### Scope
- `simulator/paper_trader.py` — refactor `_auto_buy` and `_auto_sell` to call `_submit_order` first; only update cash/positions/cost_basis if the order succeeds (returns True); log a warning and abort the fill on failure
- `simulator/paper_trader.py` — change `_submit_order` return type to `bool` (True = submitted OK or paper mode, False = live order failed)
- `tests/test_live_trade_gate.py` — add tests: fill aborted on order failure, fill applied on order success, paper mode always applies fill

### Step 1 — Verify baseline
```bash
pytest tests/ -q   # must show 383 passed
```

### Step 2 — Sprint close checklist
- [ ] All CRITICAL and HIGH review findings fixed
- [ ] `knowledge/sprint_log.md` updated with Sprint 15 entry
- [ ] `HANDOFF.md` Current State table updated
- [ ] Committed and pushed to GitHub
- [ ] GitHub issue created and closed for Sprint 15

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
