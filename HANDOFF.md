# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Codex and Claude Code must read this file first and update it last, and they must treat the repo as one continuous shared developer stream.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Codex |
| **Last updated** | 2026-04-18 (Sprint 33 in progress) |
| **Sprint completed** | Sprint 32 ✅ — Strategy Inspector Tab |
| **Next sprint** | Sprint 33 — Versioned Strategy Promotion Pipeline |
| **Blocking issues** | GitHub board/issue writes are still blocked for the current integration (`403 Resource not accessible by integration`). To enable LLM: add `OPENROUTER_API_KEY` + `LLM_ENABLED=true` to `.env`. To deploy on Jetson: follow `deployment/README.md`. |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Sprint 33 is implemented in the local worktree and verified, but not yet committed/pushed. The next agent should continue from the shared in-progress state without distinguishing Codex-vs-Claude authorship. |

---

## Resume Here — Sprint 33

**Sprint 33 is in progress.** The repo now has a local, verified implementation of a versioned strategy promotion pipeline so the platform is deployed once while strategy artifacts move through `generated draft -> reviewed plugin -> backtest -> paper -> live`.

### What was done in Sprint 33
- **Artifact registry + persistence**
  - `database/models.py` now includes `StrategyArtifact` plus artifact/hash/provenance fields on backtest runs, backtest trades, runtime trades, portfolio snapshots, and promotions.
  - `strategy/artifacts.py` is new and owns code-hash calculation, artifact registration, generated-draft review/save, paper/live target selection, promotion status changes, and runtime hash validation.
- **Runtime enforcement**
  - `strategy/runtime.py` now treats the old active strategy selector as the backtest/default strategy and resolves reviewed promoted artifacts separately for `paper` and `live`.
  - `run_live.py` now resolves the promoted runtime artifact, logs paper/live targets at startup, and fails closed if the selected reviewed artifact is missing or hash-mismatched.
  - `simulator/paper_trader.py` and `simulator/coordinator.py` now track `artifact_id`, `strategy_code_hash`, and `strategy_provenance` so paper trades, portfolio snapshots, and promotion events are tied to the exact reviewed artifact.
- **Workbench UX**
  - `dashboard/streamlit_app.py` now exposes `Review and Save`, `Promote to Paper`, and `Approve for Live` actions in the `Strategies` tab.
  - Generated drafts remain backtest-only; reviewed plugins with a passing saved backtest can become the paper target; only paper-passed reviewed plugins can be approved for live.
  - `dashboard/workbench.py` now surfaces artifact-aware lifecycle stages and strategy catalog columns, and the `Inspect` tab now shows artifact identity, provenance, code hash, and a warning when the current file no longer matches the saved run hash.
- **Backtest integration**
  - `backtester/service.py` now persists artifact identity with saved runs and upgrades reviewed artifacts to `backtest_passed` when a saved run passes.
- **Regression coverage**
  - Added/updated tests in `tests/test_strategy_artifacts.py`, `tests/test_backtester_service.py`, `tests/test_workbench_helpers.py`, and `tests/test_run_live.py`.
  - Current verification: `pytest tests/ -q` => **543 passed, 4 warnings**
  - Headless dashboard startup verified: `streamlit run dashboard/streamlit_app.py --server.headless true --server.port 8768`

### What’s next
1. Review the shared dirty worktree as one continuous in-progress change set. Do **not** split it into “Codex changes” versus “Claude changes”.
2. Commit/push Sprint 33 once the user confirms the working tree should be finalized together.
3. After commit/push, update this handoff again to move Sprint 33 from in-progress to closed.

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
| Sprint 31 — Strategy Experiments EXP-001 + EXP-002 | ✅ CLOSED | Claude Code | 2026-04-18 |
| Sprint 32 — Strategy Inspector Tab | ✅ CLOSED | Codex | 2026-04-18 |

---

## Agent Protocol

### When you START a session:
1. Read this file
2. Read `knowledge/agent_resume.md`
3. Read only the code files and KB files relevant to the active sprint
4. Read `knowledge/sprint_log.md` only if historical context is actually needed
5. Begin work on the "Resume Here" sprint
6. Treat Codex and Claude Code as one shared developer. Local dirty files are shared project state unless a technical conflict proves otherwise.

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

### Shared-Agent Rule
- Codex and Claude Code must act as one developer stream for this repo.
- Do not spend time attributing uncommitted changes to one agent or the other unless the user explicitly asks for forensic attribution.
- Treat the current worktree as shared in-progress state and continue from it carefully without reverting unrelated local changes.

### Handoff note format (add below if mid-sprint):
```markdown
## In Progress — [AGENT NAME] left off here

**Sprint:** Sprint N
**Last file edited:** path/to/file.py
**What was done:** (1-2 sentences)
**What's next:** (exact next step for the incoming agent)
**Partial work notes:** (anything the next agent needs to know)
```

## In Progress — Codex left off here

**Sprint:** Sprint 33 — Versioned Strategy Promotion Pipeline
**Last file edited:** `dashboard/streamlit_app.py`
**What was done:** Implemented the artifact registry, reviewed-plugin promotion flow, paper/live runtime enforcement, and dashboard lifecycle actions. Verified the integrated branch with `543 passed, 4 warnings` and a successful headless Streamlit startup.
**What's next:** Review the unified dirty worktree, then commit and push Sprint 33 as one shared change set if the user wants the sprint finalized.
**Partial work notes:** The worktree includes older shared dirty files such as `knowledge/experiment_log.md`; treat them as shared repo state, not as belonging to a specific agent. `run_live.py` now requires a promoted reviewed artifact for `paper` or `live`.

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
