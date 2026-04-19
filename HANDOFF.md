# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Codex and Claude Code must read this file first and update it last, and they must treat the repo as one continuous shared developer stream.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Codex |
| **Last updated** | 2026-04-19 (Sprint 42 kickoff: data-health alignment + pytest DB isolation + MVP data restored) |
| **Active sprint** | Sprint 42 kickoff — trust hardening follow-on (GitHub sprint issue not yet opened) |
| **Sprint 40** | `#42` — Done on board |
| **Tests** | `pytest tests/ -q` → **614 passed, 4 warnings** |
| **Branch** | `codex/sprint-27-responsive-chart` (shared working branch) |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Blocking issues** | LLM: add `OPENROUTER_API_KEY` + `LLM_ENABLED=true` to `.env`. Jetson: see `deployment/README.md`. |

---

## Resume Here — Sprint 42 Kickoff

Sprint 41 is closed. Sprint 42 is not yet opened as a GitHub issue, but local follow-on work has started.

## Shared-Agent Protection Protocol

Claude Code and Codex must preserve each other's work on this shared branch.

Before doing any substantial work:
1. Read `HANDOFF.md` first, then `knowledge/agent_resume.md`
2. Run `git status --short` and inspect existing dirty files before editing anything
3. Treat `codex/sprint-27-responsive-chart` as the shared continuation branch unless the user explicitly asks for a new branch
4. Assume existing local changes are intentional shared work unless directly proven otherwise

Never do these without an explicit user request:
1. `git reset --hard`
2. `git checkout -- <file>`
3. deleting or overwriting uncommitted files to "clean up"
4. changing the active paper/live artifact IDs as incidental test cleanup
5. truncating or replacing the live SQLite DB for tests

Required safety rules:
1. `pytest` must run through the repo's `tests/conftest.py` temp-DB isolation; do not bypass it
2. Do not edit, stage, or revert `knowledge/experiment_log.md` unless the runtime process writing to it has been intentionally stopped
3. Do not stage runtime-generated artifacts such as `reports/`, `.streamlit_eval.out`, or `.streamlit_eval.err` unless the user explicitly asks for them
4. If the live DB is found damaged, restore state before moving on:
   - re-sync strategy artifacts from `strategy.runtime.list_available_strategies()`
   - re-arm the paper target if needed
   - restore maintained-universe candles before claiming readiness
5. Update this file last with what changed, what was verified, and what remains next

Current shared baseline:
1. Last protection commit: `b207a44` — `Sprint 42 kickoff — isolate pytest DB and restore data gate`
2. `pytest tests/ -q` leaves the live DB intact
3. Maintained MVP universe is restored to 30-day local coverage
4. Active paper target should remain `rsi_mean_reversion_v1` artifact `#2` unless the user explicitly changes it

### Fresh progress after Sprint 41 close

| Check | Result |
|------|--------|
| `pytest tests/ -q` | **614 passed, 4 warnings** ✅ |
| Data checks (`--data-only`) | **0 FAIL, 2 PARTIAL (legacy), 1 SKIP** ✅ |
| Health-gate alignment | **Fixed** — data checks now grade freshness against the maintained MVP universe first, so stale non-maintained symbols no longer create false freshness PARTIALs |
| Pytest DB isolation | **Fixed** — test suite now runs against a dedicated temp SQLite DB and no longer mutates the live workbench database |
| MVP data recovery | **Restored** — `BTCUSDT`, `ETHUSDT`, `BNBUSDT` backfilled to 30 days (`43201` 1m candles each), artifact registry re-synced, paper target re-armed |

### Why this mattered

The dashboard MVP data gate already uses the maintained research universe (`BTCUSDT`, `ETHUSDT`, `BNBUSDT` by default), but `tools/ui_agent/data_checks.py` was still grading candle freshness against every symbol with any local candles. That created false PARTIALs whenever older exploratory symbols such as `AAVEUSDT` or `LINKUSDT` aged out, even though the maintained universe was fresh.

### Next priorities

1. **Paper trader forward evaluation** — keep `run_live.py --paper` running on the current paper target (`rsi_mean_reversion_v1`) and capture first real paper trades
2. **Live trader gate** — establish the `paper_passed` → `live_approved` path with real paper evidence
3. **Legacy integrity cleanup** — the remaining data-check PARTIALs are legacy trade-sequence rows and one legacy-invalid backtest metrics row; decide whether to repair, archive, or surface them more explicitly
4. **Maintained universe policy** — decide whether extra ready symbols should auto-refresh, or remain research-only and outside the release health gate
5. **Merge to master** — the branch `codex/sprint-27-responsive-chart` now contains Sprint 27–41 plus this Sprint 42 kickoff fix
### Sprint 41 Final Verification (all gates green)

| Gate | Result |
|------|--------|
| `pytest tests/ -q` | **612 passed, 4 warnings** ✅ |
| Smoke UI (`--ui-only`) | **61/61 (100%)** ✅ |
| Trader journey (`--journey trader`) | **0 FAIL, 7 PARTIAL (history-incomplete), 1 SKIP** ✅ |
| Data checks (`--data-only`) | **0 FAIL, 2 PARTIAL (legacy), 1 SKIP (no live target)** ✅ |
| Paper promotion journey | **PASS** (page=True, db=True) ✅ |
| Runtime monitor after promotion | **PASS** ✅ |

All 7 journey PARTIALs are "Backtest blocked — dashboard showed explicit history-incomplete error" which is the correct, expected behavior (not silent no-ops).

---

## Sprint 41 History — What Was Done

### Phase 1 — MVP Data Health Gate

Sprint 41 is `In Progress` on the board. Phases 1–3 are done. **Start at Phase 4.**

### What is Sprint 41

Issue `#43` — Trader Minimum Product Readiness (Phased). Goal: make the system trustworthy as a research + backtest + paper-readiness workbench. Five phases, three done.

### Phases Completed

**Phase 1** — MVP Data Health Gate
- `dashboard/workbench.py`: `build_data_health_frame()`, `summarise_data_health()`, stale-data detection per symbol
- `dashboard/streamlit_app.py`: MVP Data Health Gate expander at top of workbench, "Sync fresh data" button for stale symbols, Backtest Lab stale warning, runnable-window status

**Phase 2** — Backtest Operability / Trade Log Integrity
- `tools/ui_agent/data_checks.py`: `refresh_integrity_flags(retag_existing=True)` + `Trade.id` tiebreaker → trade log FAIL → PARTIAL
- `dashboard/streamlit_app.py`: "Sync fresh data for stale symbols" button in MVP gate

**Phase 3** — Paper Readiness Signals (just committed, pushed)
- Promoted `rsi_mean_reversion_v1` artifact #2 to `paper_active` via `promote_artifact_to_paper(2)` in DB
- `dashboard/streamlit_app.py` Strategies tab: paper/live target banner upgraded `st.caption` → `st.success`
- `dashboard/streamlit_app.py` hero area: paper-readiness advisory — green "armed" banner or blue "no target" info
- `dashboard/streamlit_app.py` Inspect tab: artifact badge per run showing whether it is the current paper/live target

### Phase 4 — Verified Complete ✅

Goal: **Release contract via trader journey — zero failures**. ✅ All gates passed.

Sprint 41 issue acceptance criteria:
- `pytest tests/ -q` green ✅ (already passing)
- `python run_ui_agent.py --ui-only` → zero failures (currently 59/61 before agent.py fixes; should be 61/61 after commit)
- `python run_ui_agent.py --journey trader --ui-only` → zero failures (currently 2 FAIL strategies)
- `python run_ui_agent.py --data-only` → zero failures (currently 3 PARTIAL, 0 FAIL)

**Immediate next steps for Codex:**

1. **Verify smoke UI** — run `python run_ui_agent.py --ui-only --url http://localhost:8785` (start dashboard first). Should be 61/61 after `tools/ui_agent/agent.py` `_count` fixes committed in Phase 2/3 batch. If still showing partial, check the "History audit status banner" and "Inspect equity chart" checks in `agent.py`.

2. **Re-run trader journey** — run `python run_ui_agent.py --journey trader --ui-only --url http://localhost:8785`. The `_wait_for_backtest_response` fix in `tools/ui_agent/trader_journey.py` should resolve 2 FAIL entries for `breakout_v1` and `mean_reversion_v1`. Verify they become SKIP or PARTIAL (blocked by history, not silent no-op).

3. **Fix remaining trader journey failures** — if any FAILs remain after step 2, read the report in `reports/` and fix the underlying issues. Common patterns:
   - Strategy shows "Backtest blocked — incomplete history" → that is a SKIP, not FAIL
   - "silent-noop" = UI state not captured after button click → check `_wait_for_backtest_response` and `_RERENDER` constant

4. **Data checks zero-failure target** — `python run_ui_agent.py --data-only --url http://localhost:8785`. Current PARTIALs are:
   - Candle freshness PARTIAL → live streamer not running; acceptable for dev, but note it in report
   - Legacy trade sequences PARTIAL → test DB contamination from Sprint 38 fixture trades; acceptable
   - Legacy-invalid backtest run #472 PARTIAL → metrics `{bad-json}`; acceptable
   - These 3 PARTIALs are known/acceptable; the goal is 0 FAIL, not 0 PARTIAL

5. **Sprint 41 close checklist**:
   - All tests passing (`612+`)
   - Smoke UI 61/61
   - Trader journey: zero unexplained FAILs (blocked/skipped is fine)
   - Data checks: 0 FAIL
   - Commit + push
   - Close issue #43 on GitHub + set board status to Done
   - Update `HANDOFF.md` + `knowledge/agent_resume.md`

---

## Current DB State (important for Codex cold start)

```
Strategy artifacts (DB):
  id=1  ema200_filtered_momentum  status=reviewed
  id=2  rsi_mean_reversion_v1     status=paper_active  ← paper target
  id=3  mtf_confirmation          status=reviewed

Paper target: artifact_id=2 (rsi_mean_reversion_v1)
Live target:  None

Maintained MVP universe:
  BTCUSDT  43201 candles (30d restored)
  ETHUSDT  43201 candles (30d restored)
  BNBUSDT  43201 candles (30d restored)
```

To verify: `python -c "from strategy.artifacts import list_all_strategy_artifacts, get_active_runtime_artifact_id; print(list_all_strategy_artifacts()); print('paper:', get_active_runtime_artifact_id('paper'))"`

---

## How to Start Dashboard

```bash
streamlit run dashboard/streamlit_app.py
# Default port 8501. Use --server.port N to change.
# Dashboard must be running before any UI agent run.
```

## How to Run Verification Suite

```bash
# Full pytest:
pytest tests/ -q

# UI smoke tests (dashboard must be running):
python run_ui_agent.py --ui-only --url http://localhost:8785

# Trader journey (dashboard must be running):
python run_ui_agent.py --journey trader --ui-only --url http://localhost:8785

# Data integrity checks (no browser needed):
python run_ui_agent.py --data-only

# Compile check:
python -m py_compile dashboard/streamlit_app.py
```

---

## Key Files for Sprint 41 Phase 4

| File | Relevance |
|------|-----------|
| `tools/ui_agent/agent.py` | Smoke UI test runner — 61 checks |
| `tools/ui_agent/trader_journey.py` | Trader journey — verifies full paper-readiness path |
| `tools/ui_agent/data_checks.py` | DB data integrity — 10 checks |
| `tools/ui_agent/report.py` | Report builder for all three runners |
| `dashboard/streamlit_app.py` | Main dashboard — all 6 tabs |
| `dashboard/workbench.py` | Pure helpers (catalog, artifact lifecycle, data health) |
| `strategy/artifacts.py` | Artifact registration, promotion, validation |
| `reports/` | Latest run reports — read these before debugging |

---

## Known Issues / Acceptable PARTIALs

| Check | Status | Reason |
|-------|--------|--------|
| Candle freshness | PARTIAL | Live streamer not running in dev env |
| Trade log integrity | PARTIAL | Legacy test-DB fixture trades from Sprint 38 |
| Backtest run #472 | PARTIAL | `{bad-json}` metrics from early test |
| Artifact integrity | was SKIP → now PASS | Paper artifact is now configured |

---

## Sprint 41 GitHub Tracking

- Issue: `#43` — `Sprint 41 — Trader Minimum Product Readiness (Phased)` → **In Progress**
- Issue: `#42` — `Sprint 40 — Production Trust Hardening` → **Done**
- Project board: https://github.com/users/karllouiehernandez/projects/1

---

## Sprint History (brief)

| Sprint | Issue | Status | Key output |
|--------|-------|--------|-----------|
| Sprint 39 | #41 | Done | Trading Diary tab + backtest insights |
| Sprint 38 | #40 | Done | Trader journey trust fixes |
| Sprint 37 | — | Done | Trader journey Playwright runner |
| Sprint 35 | #39/#38 | Done | AI UI testing agent + data integrity suite |
| Sprint 34 | #36/#37 | Done | Promotion Control Panel |
| Sprint 33 | — | Done | Strategy artifact lifecycle |
| Sprint 40 | #42 | Done | Production trust hardening |
| Sprint 41 | #43 | **In Progress** | Phases 1–3 done; Phase 4 next |

Full history: `knowledge/sprint_log.md`
