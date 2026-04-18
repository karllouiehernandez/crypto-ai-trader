# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Claude Code |
| **Last updated** | 2026-04-18 (Sprint 30 closed) |
| **Sprint completed** | Sprint 30 ✅ — Ready-First Symbol UX + Background History Loading — 510 tests passing |
| **Next sprint** | Sprint 31 — TBD; check GitHub Projects board #1 or ask user |
| **Blocking issues** | GitHub board/issue writes are still blocked for the current integration (`403 Resource not accessible by integration`). To enable LLM: add `OPENROUTER_API_KEY` + `LLM_ENABLED=true` to `.env`. To deploy on Jetson: follow `deployment/README.md`. |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Sprint 30 complete. |

---

## Resume Here — Sprint 31

**Sprint 30 complete.** The dashboard now shows only ready symbols (symbols with local candle data) in the chart and backtest selectors. A separate "Load New Symbol" sidebar expander lists all Binance USDT pairs, lets the user queue a background 30-day history load, and shows queue status with retry for failed loads. 510 tests passing.

### What was done in Sprint 30
- **`database/models.py`** — added `SymbolLoadJob` ORM model (`symbol PK`, `status`, `queued_at`, `started_at`, `completed_at`, `error_msg`). Auto-created by `init_db()` / `Base.metadata.create_all`.
- **`market_data/symbol_readiness.py`** (NEW) — `list_ready_symbols()`, `is_symbol_ready()`, `queue_symbol_load()`, `retry_failed_load()`, `list_load_jobs()`.
- **`market_data/background_loader.py`** (NEW) — daemon thread worker (`ensure_worker_running()`) that polls `SymbolLoadJob` for `queued` rows and calls `backfill` + `sync_recent`; writes `ready` or `failed` status back to DB.
- **`dashboard/streamlit_app.py`** — chart and backtest Lab symbol selectors now use `ready_symbols` (symbols with local candle data) instead of the full Binance catalog. Added a "Load New Symbol" sidebar expander backed by the full catalog + background loader; shows live queue status and retry for failed jobs. `ensure_worker_running()` called on every page load.
- **Tests** — 10 new tests in `test_market_data_services.py` covering readiness checks, job queuing, idempotency, failed-job reset, and job ordering.
- **510 total passing** (+10 over Sprint 29)

### Sprint 31 Goal
No queued roadmap item. Next agent should check GitHub Projects board `#1` or ask the user for the next priority.

### GitHub Sprint Tracking — Manual Fallback
- Attempted GitHub issue creation for Sprint 29 in `karllouiehernandez/crypto-ai-trader`
- Result: `403 Resource not accessible by integration`
- Manual issue title:
  `Sprint 29 — Dynamic Binance USDT Universe + Historical Data Coverage`
- Manual issue body:
  `Goal: remove the hardcoded 3-symbol restriction and support any Binance spot USDT pair across analysis, backtesting, paper trading, and live trading, with a Binance-first historical-data workflow and persisted runtime watchlist. Scope: discover Binance spot USDT pairs from metadata; replace static runtime symbol assumptions with a persisted runtime watchlist; allow dashboard analysis/backtest flows to choose any supported Binance USDT symbol; add backfill/audit/sync_recent commands for arbitrary symbols; fail backtests fast when the requested window has candle gaps; keep runtime activation explicit so chart/backtest selection does not auto-enable paper/live trading. Acceptance: any active Binance spot USDT symbol can be selected in dashboard and backtest flows; streamer and paper/live runtime use an editable persisted watchlist; historical backfill and gap audit work for non-default symbols; backtests stop with a clear error on incomplete windows; regression suite remains green.`
- Manual project-board card text:
  `Sprint 29 — Dynamic Binance USDT Universe + Historical Data Coverage: dynamic Binance USDT discovery, persisted runtime watchlist, arbitrary-symbol backfill/audit/sync, fail-fast gap detection, dashboard/runtime integration.`

## Resume Here — Sprint 26 (COMPLETED)

**Sprint 25 complete.** Dashboard now has a 4th "Market Focus" tab. Running a study fetches top-N Binance USDT pairs by 24h volume, backtests each with the active strategy, and ranks by composite score (Sharpe + profit_factor − drawdown). Results persist to DB. One-click prefill sends the top pick into Backtest Lab. 443 tests passing.

### What was done in Sprint 25
- `config.py` — added `MARKET_FOCUS_UNIVERSE_SIZE`, `MARKET_FOCUS_TOP_N`, `MARKET_FOCUS_BACKTEST_DAYS`, `_MARKET_FOCUS_EXCLUDE`
- `database/models.py` — added `WeeklyFocusStudy`, `WeeklyFocusCandidate` ORM models
- `market_focus/selector.py` (NEW) — deterministic ranking engine; no LLM required
- `backtester/service.py`, `dashboard/workbench.py`, `dashboard/streamlit_app.py` — integrated market focus into service layer and dashboard
- `tests/test_market_focus.py` (NEW) — 14 tests
- **443 total passing** (+14 over Sprint 24)

### Sprint 26 Goal
No queued roadmap item. Next agent should check GitHub Projects board `#1` or ask the user for the next priority.

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
| Sprint 24 — Named Scenario Presets | ✅ CLOSED | Codex | 2026-04-18 |
| Sprint 25 — Weekly Market Focus Selector | ✅ CLOSED | Claude Code | 2026-04-18 |
| Sprint 26 — CI/CD + Jetson + MCP + Telegram | ✅ CLOSED | Claude Code | 2026-04-18 |
| Sprint 27 — Responsive Chart + Runtime Marker Clarity | ✅ CLOSED | Codex | 2026-04-18 |
| Sprint 28 — Responsive Chart Indicator Overlays | ✅ CLOSED | Codex | 2026-04-18 |
| Sprint 29 — Dynamic Binance USDT Universe + Historical Data Coverage | ✅ CLOSED | Codex | 2026-04-18 |
| Sprint 30 — Ready-First Symbol UX + Background History Loading | ✅ CLOSED | Claude Code | 2026-04-18 |

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
| Dashboard | Streamlit + Plotly + Lightweight Charts |
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
