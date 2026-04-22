# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Codex and Claude Code must read this file first and update it last, and they must treat the repo as one continuous shared developer stream.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Codex |
| **Last updated** | 2026-04-22 (Sprint 42 operator baseline refreshed after maintained-universe sync) |
| **Active sprint** | Sprint 42 — `#44` — Paper Evidence, Trader Journey Stabilization, and Legacy Integrity Closure |
| **Sprint 40** | `#42` — Done on board |
| **Tests** | `pytest tests/ -q` → **651 passed, 4 warnings**; `python run_ui_agent.py --data-only` → **0 FAIL, 0 PARTIAL, 1 SKIP** on 2026-04-22 after maintained-universe sync; headed smoke UI `64/64 PASS` on 2026-04-21; headed trader journey `27/28 PASS` with **0 FAIL, 0 PARTIAL, 1 SKIP** on 2026-04-21 |
| **Branch** | `codex/sprint-27-responsive-chart` (shared working branch) |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Blocking issues** | LLM: add `OPENROUTER_API_KEY` + `LLM_ENABLED=true` to `.env`. Jetson: see `deployment/README.md`. |

---

## Resume Here — Sprint 42

Sprint 41 is closed. Sprint 42 is now tracked as GitHub issue `#44` and has been added to Projects board `#1`.
The Sprint 42 issue title/body have now been updated and the board card is set to `In Progress`.

### Latest Slice (2026-04-22)

- **What changed**
  - Implemented **Sprint 42 Phase 1 — persistence and restart/recovery validation**.
  - Added new module [database/persistence.py](database/persistence.py) with:
    - `evaluate_restart_survival()` — audits DB presence, paper/live runtime targets, registered artifact file/hash integrity, saved-run counts, and MVP-symbol candle freshness.
    - `create_state_backup()` — creates a timestamped local backup of the current DB plus registered strategy files, with a JSON manifest and no `.env` copy by default.
  - Added new pure helpers in [dashboard/workbench.py](dashboard/workbench.py):
    - `build_restart_survival_metrics()`
    - `build_restart_survival_frame()`
  - Added a new **Persistence & Recovery** expander in the Strategies tab of [dashboard/streamlit_app.py](dashboard/streamlit_app.py) with:
    - restart status metrics
    - visible issue list when restart survival is not clean
    - status table for DB / paper target / live target / artifacts / saved runs / MVP symbols
    - explicit **Create State Backup** action
  - Added tests in [tests/test_persistence.py](tests/test_persistence.py) covering:
    - missing MVP data
    - valid runtime + saved-run counts
    - artifact hash mismatch detection
    - backup creation
  - Added workbench-helper coverage for the new restart-survival panel in [tests/test_workbench_helpers.py](tests/test_workbench_helpers.py).
  - Implemented **Sprint 42 Phase 2 — deterministic paper-evidence progress surfaces**.
  - Added shared paper-evidence summarization in [strategy/paper_evaluation.py](strategy/paper_evaluation.py):
    - `evaluate_paper_evidence_from_trades()`
    - `build_paper_evidence_summary()`
  - Extended [simulator/paper_trader.py](simulator/paper_trader.py) status snapshots to expose in-memory paper-evidence progress based on tagged SELL trades already seen by the trader.
  - Extended [run_live.py](run_live.py) heartbeat logging to include paper-evidence stage, trade-progress, runtime-progress, and blocker count in one operator-facing status line.
  - Added new pure helpers in [dashboard/workbench.py](dashboard/workbench.py):
    - `build_paper_evidence_metrics()`
    - `build_paper_evidence_checklist_frame()`
  - Added a persistent **Paper Evidence Progress** section in the Strategies tab of [dashboard/streamlit_app.py](dashboard/streamlit_app.py) so the active paper target always shows:
    - gate status
    - SELL-trade progress
    - runtime-span progress
    - profit-factor snapshot
    - checklist rows and blocker reasons
    - first/last paper SELL timestamps when evidence exists
  - Added tests in:
    - [tests/test_paper_evaluation.py](tests/test_paper_evaluation.py)
    - [tests/test_paper_trader.py](tests/test_paper_trader.py)
    - [tests/test_run_live.py](tests/test_run_live.py)
    - [tests/test_workbench_helpers.py](tests/test_workbench_helpers.py)
- **What was verified**
  - `python -m py_compile database/persistence.py dashboard/streamlit_app.py dashboard/workbench.py strategy/paper_evaluation.py simulator/paper_trader.py run_live.py tests/test_persistence.py` → clean
  - `pytest tests/test_persistence.py tests/test_workbench_helpers.py tests/test_paper_evaluation.py tests/test_paper_trader.py tests/test_run_live.py -q` → **97 passed**
  - `pytest tests/ -q` → **651 passed, 4 warnings**
  - Maintained-universe sync executed successfully on 2026-04-22:
    - `BTCUSDT` / `ETHUSDT` / `BNBUSDT` each inserted `1295` fresh `1m` candles with no missing ranges
  - `python run_ui_agent.py --data-only` → **0 FAIL, 0 PARTIAL, 1 SKIP**
    - Only remaining SKIP is expected: no active live artifact configured
  - Sprint 42 issue `#44` remains the active tracking issue and already contains the phased pre-deploy plan comment:
    - [Issue #44 comment](https://github.com/karllouiehernandez/crypto-ai-trader/issues/44#issuecomment-4295460139)
- **What remains next**
  - **Phase 2 implementation is complete in code, but the real-world evidence gate is still waiting on actual artifact-tagged SELL trades for paper target `#2`.**
  - Keep the maintained-universe refresh healthy over time. The data-only gate is green again now, but future readiness claims still depend on fresh local candles being maintained automatically or by operator action.
  - Use the new Persistence & Recovery panel to manually confirm the live operator environment before making stronger production-readiness claims.
  - Decide whether to create and keep one generated draft in the default environment. The only remaining trader-journey skip is still the draft-promotion guard because no generated draft is currently present in the catalog.
  - Continue adding one structured entry to [knowledge/iteration_learnings.md](knowledge/iteration_learnings.md) after each meaningful implementation or validation slice so this operator-trust history stays cumulative.

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
5. Sprint 42 tracking issue: `#44` — `Sprint 42 — Paper Evidence & Legacy Integrity Closure`

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

1. **Trader-journey stabilization** — finish the unstable `run_ui_agent.py --journey trader --ui-only` path
   - Latest code now shares the latest-complete backtest day rule between the dashboard and the journey harness.
   - Smoke and DB checks are green, but full trader journeys can still hang without writing a terminal report even while `backtest_runs` rows continue to be created underneath them.
   - Start by inspecting [tools/ui_agent/trader_journey.py](tools/ui_agent/trader_journey.py), the most recent rows in `backtest_runs`, and the current Backtest Lab "Last Backtest Attempt" surface together.
2. **Paper trader forward evaluation** — keep `run_live.py` running on the current paper target (`rsi_mean_reversion_v1`) and capture first real paper trades
   - **Status (2026-04-19 12:57 UTC)**: paper runtime is armed and healthy. Portfolio snapshots tagged `artifact_id=2 / rsi_mean_reversion_v1` are being written every minute; maintained universe (`BTCUSDT`, `ETHUSDT`, `BNBUSDT`) candles are fresh to the current minute; balance/equity flat at `$100` (no entries yet — RSI mean-reversion requires RSI<30 + BB lower touch + MACD cross, entries are sparse).
   - **"Duplicate `run_live.py`" concern — RESOLVED, was a false alarm.** PIDs `2616` and `11744` are a parent/child pair, not two concurrent launches: `2616` is the venv launcher stub (`D:\trader\Scripts\python.exe`, 1 thread, 3.3MB WS, 0 CPU) that re-execs into the real interpreter `11744` (`...\Python310\python.exe`, 18 threads, 135MB WS, 314 CPU sec). `Win32_Process.ParentProcessId(11744) = 2616`. Only one trader is doing work; snapshot write rate is 1/min (single writer). **Do not kill `2616`** — that would take the real trader `11744` down with it.
   - **No paper trades on artifact #2 yet**. The existing ~1,500 pre-existing paper trades in the DB predate artifact tagging (`artifact_id=NULL`) and are correctly excluded from the paper→live evidence gate by design.
3. **Live trader gate** — establish the `paper_passed` → `live_approved` path with real paper evidence
   - **Status (2026-04-19, Claude Code)**: deterministic, non-LLM evidence gate now lives in [strategy/paper_evaluation.py](strategy/paper_evaluation.py). `evaluate_paper_evidence(artifact_id)` reads the actual `Trade` rows tagged with the artifact (run_mode='paper', side='SELL') and grades against `PaperEvidenceThresholds` (default: ≥20 trades, ≥3 days runtime, Sharpe ≥1.5, profit factor ≥1.5, max drawdown ≤20%).
   - [strategy/artifacts.py:308](strategy/artifacts.py#L308) `mark_artifact_paper_passed` now **requires** a passing evidence result by default; the LLM coordinator path in [simulator/coordinator.py:99](simulator/coordinator.py#L99) explicitly passes `force=True` so its own confidence gate stays authoritative.
   - Dashboard Strategies tab: new **"Evaluate for Paper Pass"** button below the four primary action buttons. Surfaces the metric snapshot + per-rule failure reasons when the gate fails, and promotes + unlocks "Approve for Live" when it passes.
   - Tests: 10 new cases in `tests/test_paper_evaluation.py` cover no-artifact, no-trades, low trade count, short runtime, high drawdown, passing evidence, force bypass, full promotion, and the legacy-untagged-trades exclusion (legacy `artifact_id=NULL` paper trades are correctly ignored as evidence).
   - Once the live paper runtime under Priority #1 produces real artifact-#2 trades, this gate will determine eligibility for `approve_artifact_for_live` automatically.
4. **Legacy integrity cleanup** — containment archive is now available and has now been applied to the live DB.
   - **Actual live-DB inventory** (previously misreported in HANDOFF as "1 legacy row"):
     - 731 legacy-invalid `Trade` rows (all BTCUSDT, all `artifact_id=NULL`, ts range 2026-04-17 13:00 → 2026-04-19 09:24)
     - 62 `invalid-metrics` + 21 `missing-trades` backtest runs (all fixture-era)
     - Root cause: pre-Sprint-42 test runs wrote into the live DB before `tests/conftest.py` isolation landed. The latest `--data-only` surfaces 613 of those as legacy sequences today.
   - **Containment approach chosen**: tag affected rows `integrity_status = 'archived-legacy'`, preserve prior status in `integrity_note` with `[archived-legacy]` marker + UTC timestamp. No deletion. Fully reversible. Implemented in [database/integrity.py](database/integrity.py#L42) — `archive_legacy_integrity_rows()`, `unarchive_legacy_integrity_rows()`, `count_archivable_legacy_rows()`, `count_archived_legacy_rows()`. `refresh_integrity_flags()` preserves `archived-legacy` across re-runs.
   - **Release-gate behavior**: [tools/ui_agent/data_checks.py](tools/ui_agent/data_checks.py) — `_check_trade_log_integrity`, `_check_backtest_metrics`, `_check_backtest_equity`, and `_check_position_sizing` now exclude `archived-legacy` rows from grading and report the excluded count in the detail string (e.g. `"... (613 archived legacy row(s) excluded)"`).
   - **Dashboard maintenance UI**: new "Legacy Integrity Containment" expander in the Strategies tab with row counts + Archive / Unarchive buttons (below Promotion Control Panel → Artifact Registry).
   - **Tests**: 10 new cases in `tests/test_integrity_archive.py` (refresh classifies, count before/after, archive preserves prior status in note, refresh does not regress archived, unarchive reverts + reclassifies, archive is idempotent) + 3 new cases in `tests/test_data_checks.py` covering archived trade/backtest/BUY row acknowledgment.
   - **Live DB status — ARCHIVED APPLIED (2026-04-21)**: live DB archive action has now been executed. Current inventory is `731` archived legacy trades + `83` archived legacy backtest runs, with `0` archivable legacy rows remaining. `python run_ui_agent.py --data-only` now reports trade integrity and backtest metric sanity as `PASS` with archived-row exclusions in the detail.
   - **Follow-up bug fixed in code**: archived rows were initially being excluded from `refresh_integrity_flags()` traversal, which could create false new `legacy-invalid` tags across archived gaps. Fixed by traversing all trades, treating archived rows as sequence barriers, and preserving them without retagging. Added a regression test in `tests/test_integrity_archive.py`.
5. **Paper trader forward evaluation / runtime freshness** — runtime freshness has been restored; real paper evidence is still pending.
   - **Status (2026-04-21)**: `run_live.py` has been restarted in the background and is healthy. Maintained-universe candles and paper snapshots are advancing again, and `python run_ui_agent.py --data-only` is now **0 FAIL, 0 PARTIAL, 1 SKIP** (skip = no live artifact configured).
   - **Heartbeat state**: paper target remains `rsi_mean_reversion_v1` artifact `#2`, balance/equity remain flat at `$100`, and no artifact-tagged SELL trades exist yet for the paper-evidence gate.
   - **SQLite lock mitigation added**: [database/models.py](database/models.py) now creates SQLite connections with `check_same_thread=False`, `timeout=30`, `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, and `PRAGMA busy_timeout=30000`. This was added after `run_live.py` previously died during `sess.commit()` with `sqlite3.OperationalError: database is locked` while the dashboard was active.
6. **Backtest hot-path correctness/performance** — fixed on 2026-04-21.
   - **Problem**: historical backtests were rebuilding indicators from a fresh DB query on every candle, which was slow enough to leave the trader journey spinner-bound and also leaked future context by always reading the latest candles.
   - **Fix**: [backtester/engine.py](backtester/engine.py) now precomputes one indicator source per backtest and passes a trailing per-candle indicator window into [strategy/runtime.py](strategy/runtime.py). Runtime decision logic now accepts a supplied indicator frame, so backtests use historical-only context without per-candle DB fetches.
   - **Verification**: direct `ema200_filtered_momentum` backtest over the trader-journey window now completes and persists a run in about 63 seconds instead of timing out.
7. **Headed production validation (rerun 2026-04-21)** — the automation contract is now strong; the remaining gap is live-readiness evidence, not UI trust.
   - **Headed smoke**: `python run_ui_agent.py --ui-only --headed --url http://localhost:8785` → **64/64 PASS**
   - **Headed trader journey**: `python run_ui_agent.py --journey trader --ui-only --headed --url http://localhost:8785` → **27/28 PASS**, **0 FAIL**, **0 PARTIAL**, **1 SKIP** (`Draft promotion guard` skipped because no generated draft exists in the catalog)
   - **Data-only**: `python run_ui_agent.py --data-only` → **0 FAIL, 0 PARTIAL, 1 SKIP**
   - **Latest window hardening**: the trader journey now audits a recent deterministic 7-day BTCUSDT window, which keeps the exhaustive 7-strategy operator pass practical while still exercising real backtest persistence and Inspect rendering.
   - **Conclusion**: the workbench is now credible for supervised research, backtesting, Inspect auditing, and paper-readiness workflow validation. It is **still not ready for real live trading** because the paper-evidence gate has no real artifact-tagged SELL trades yet and live approval still lacks forward-performance proof.
8. **Maintained universe policy** — decide whether extra ready symbols should auto-refresh, or remain research-only and outside the release health gate
9. **Bootstrap and recovery** — Windows one-time setup is now scripted via `install_once.bat`; the next continuity improvement is Phase 1 restart-survival validation so long-lived deployments improve without rebuilding from scratch
9. **Merge to master** — the branch `codex/sprint-27-responsive-chart` now contains Sprint 27–42 work; prepare merge once operator decisions are stable
10. **GitHub tracking** — Sprint 42 is now issue `#44` on Projects board `#1`; keep that issue current instead of opening a new sprint ticket
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
