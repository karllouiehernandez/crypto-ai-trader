# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Claude Code |
| **Last updated** | 2026-04-17 |
| **Sprint completed** | Sprint 4 ✅ |
| **Next sprint** | Sprint 5 |
| **Blocking issues** | None |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Sprint 4 complete |

---

## Resume Here — Sprint 5

**GitHub issue:** https://github.com/karllouiehernandez/crypto-ai-trader/issues/6 (create if not exists)

**Goal:** Regime detection — ADX + BB-width classifier; gate strategies by active regime.

**Acceptance criteria:**
- `strategy/regime.py` new module: `detect_regime(df) -> Regime` returning `TRENDING | RANGING | SQUEEZE | HIGH_VOL`
- Regime rules from `config.py` constants: ADX > 25 → TRENDING, ADX < 20 → RANGING, BB width < 20th percentile (90d) → SQUEEZE, realized vol > 2× 30d avg → HIGH_VOL
- `strategy/signal_engine.py` gates mean-reversion BUY/SELL to RANGING regime only (ADX < 20)
- HIGH_VOL regime halts all signal generation (return HOLD)
- `tests/test_regime.py` — unit tests for each regime branch
- `tests/test_signal_engine.py` — tests verifying signal is gated by regime
- `knowledge/sprint_log.md` — update Sprint 5 section on close

**Files to modify:**
- `strategy/regime.py` — new file
- `strategy/signal_engine.py` — import and gate on regime
- `strategy/ta_features.py` — add `adx_14` column (using `ta.trend.ADXIndicator`)
- `config.py` — add `ADX_TREND_THRESHOLD=25`, `ADX_RANGE_THRESHOLD=20`, `HIGH_VOL_MULTIPLIER=2.0`
- `tests/test_regime.py` — new file
- `knowledge/sprint_log.md`, `HANDOFF.md`

**Note on deferred Sprint 4 items:**
- Multi-timeframe confirmation (1m+5m+15m) — deferred to Sprint 6 when multi-strategy portfolio adds 5m/15m feeds
- 1h EMA-200 — same deferral; see `knowledge/parameter_history.md` for design rationale

---

## Sprint History

| Sprint | Status | Closed by | Date |
|--------|--------|-----------|------|
| Sprint 0 — Foundation fixes + credentials | ✅ CLOSED | Claude Code | 2026-04-16 |
| Sprint 1 — Knowledge base kb_update.py | ✅ CLOSED | GitHub Copilot | 2026-04-16 |
| Sprint 2 — Testing infrastructure | ✅ CLOSED | GitHub Copilot | 2026-04-16 |
| Sprint 3 — Risk management overhaul | ✅ CLOSED | GitHub Copilot | 2026-04-16 |
| Sprint 4 — Signal quality improvements | ✅ CLOSED | Claude Code | 2026-04-17 |

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
