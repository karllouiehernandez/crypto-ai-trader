# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Codex and Claude Code must read this file first and update it last, and they must treat the repo as one continuous shared developer stream.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Claude Code |
| **Last updated** | 2026-04-19 (Sprint 41 Phase 2 complete) |
| **Sprint completed** | Sprint 41 Phase 2 ✅ — Trade log integrity fix + MVP sync button — 612 tests passing |
| **Next sprint** | Sprint 41 Phase 3 or next priority — check GitHub Projects board `#1` |
| **Blocking issues** | To enable LLM: add `OPENROUTER_API_KEY` + `LLM_ENABLED=true` to `.env`. To deploy on Jetson: follow `deployment/README.md`. |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Phase 2 data integrity fixes complete. data-only checks now show 0 FAIL / 3 PARTIAL. Remaining PARTIALs are candle freshness (live streamer not running), legacy trade sequences, legacy-invalid backtest run. Next priority: improve trader path toward reviewed artifact + paper readiness. |

---

## Resume Here — Sprint 41

Sprint 40 remains the active local hardening stream. The next structured follow-on sprint is now queued remotely:

- Issue: `#43` — `Sprint 41 — Trader Minimum Product Readiness (Phased)`
- Project board: added to GitHub Projects board `#1`
- Linked from Sprint 40 issue `#42` so the continuation path is explicit

### Sprint 41 phases

1. **Data Health Gate**
   - durable dashboard health surface
   - latest candle age per ready symbol
   - MVP research universe freshness + 30-day runnable-window gating
2. **Backtest Operability**
   - one terminal state per backtest click
   - at least one canonical reviewed-strategy saved-run path
3. **Inspect As Canonical Audit Screen**
   - guaranteed identity + gate + equity/code or explicit placeholders
4. **Research-To-Paper Readiness**
   - one reviewed strategy should complete saved backtest -> inspect -> paper target visibility
5. **Release Contract**
   - smoke UI, trader journey, data checks, and pytest all become zero-failure gates for MVP readiness

### Current local focus

- Phase 1 implemented: MVP data-health gate, sidebar summary, stale-data warning in Backtest Lab, runnable-window status
- Phase 2 implemented (just closed):
  - `data_checks.py`: `refresh_integrity_flags(retag_existing=True)` so consecutive same-side trades from isolated test writes are correctly tagged legacy-invalid → trade log FAIL → PARTIAL
  - `data_checks.py`: `Trade.id` tiebreaker in `_check_trade_log_integrity` matches `refresh_integrity_flags` ordering exactly
  - `data_checks.py`: legacy-issue detail truncated to count + affected symbols (avoids flooding report)
  - `dashboard/streamlit_app.py`: "Sync fresh data for stale symbols" button in MVP Data Health Gate — triggers `sync_recent` per stale symbol, clears cache, reruns

### Latest verified state

- `pytest tests/ -q` → **612 passed, 4 warnings**
- `python run_ui_agent.py --ui-only --url http://localhost:8785` → **59/61**, 0 failures, 2 partials
- `python run_ui_agent.py --data-only --url http://localhost:8785` → **0 FAIL, 3 PARTIAL, 2 SKIP** (was 1 FAIL before Phase 2)
  - Remaining PARTIALs: candle freshness (live streamer not running), legacy trade sequences (test DB contamination), legacy-invalid backtest run (#472)
  - SKIPs: no active paper/live artifact configured

### Remaining Phase 3 priorities

1. Improve trader path: at least one reviewed strategy with a saved passing backtest (paper readiness)
2. Inspect-complete audit surface: every saved run should have identity + gate + equity or explicit placeholder
3. Paper target readiness: clear "ready to promote" signal in dashboard when reviewed strategy has passed backtest

### Latest GitHub tracking

- `#42` — `Sprint 40 — Production Trust Hardening` (in progress)
- `#43` — `Sprint 41 — Trader Minimum Product Readiness (Phased)` (queued next)

### Sprint 39 summary (just closed)

Issue `#41` on GitHub Projects board `#1` is implemented locally and ready as the current baseline:

1. **Trading Diary tab completed** — `dashboard/streamlit_app.py` now renders the declared `diary_tab` with five guarded sections:
   trading summary metrics, P&L-by-strategy and P&L-by-symbol bar charts, recent diary entry filters and annotation form, session-summary recording, recent backtest insights, and knowledge export.
2. **Trader-facing diary services reused, not duplicated** — the tab uses existing helpers from `trading_diary.service`, `trading_diary.export`, and `dashboard.workbench`, keeping the workbench workflow consistent.
3. **Diary coverage added** — `tests/test_trading_diary.py` adds 13 mocked unit tests covering trade diary content, backtest insight verdicts, summary win-rate calculation, regime suggestions, export output, and filtered entry queries.
4. **Verification raised the baseline** — `pytest tests/ -q` now reports **607 passed, 4 warnings**.

### GitHub tracking

- Issue: `#41` — `Sprint 39 — Trading Diary + Backtest Knowledge`
- Project board: added to GitHub Projects board `#1`

### What to inspect first if continuing

- `dashboard/streamlit_app.py` — final `with diary_tab:` block at the end of the file
- `trading_diary/service.py` — diary entry creation/query/summarisation
- `trading_diary/backtest_insights.py` — deterministic backtest learnings
- `trading_diary/export.py` — knowledge export
- `tests/test_trading_diary.py` — mocked regression coverage

### Latest verified state

- `pytest tests/ -q` → **607 passed, 4 warnings**
- `python -m py_compile dashboard/streamlit_app.py` → passes

### What was done in Sprint 37

**Trader Journey Playwright (`tools/ui_agent/`)**
- `tools/ui_agent/trader_journey.py` (NEW)
  - stateful operator-style journey runner
  - iterates every visible strategy from `Backtest Lab`
  - checks lifecycle/readiness state in `Strategies`
  - tries to run a backtest for each strategy
  - inspects the saved run in `Inspect` when persistence succeeds
  - verifies paper/live readiness flows without enabling real live trading
- `run_ui_agent.py`
  - added `--journey trader`
  - keeps the existing smoke suite as default
- `tools/ui_agent/report.py`
  - report payload now supports a `journey` block
  - Markdown/JSON reports now include trader summary, per-strategy audit rows, and operator concerns
- `dashboard/streamlit_app.py`
  - `Inspect` run labels now include `#run_id` so Playwright can target exact saved runs deterministically
- `tests/test_ui_agent_smoke.py`
  - added regression coverage for journey-aware report output and `--journey trader` CLI wiring

### Trader-Journey Learnings To Build On

The new journey runner exposed operator-trust issues that smoke tests do not catch:

- Backtest windows still fail often from a trader point of view because the default date range can land on an incomplete candle window. The workbench should guide the user toward a latest-complete window instead of leaving this as a silent workflow trap.
- Several strategies in the local environment end with explicit warning states rather than persisted runs. That is acceptable only when the warning is clear. The dashboard should make these blocked states more obvious and more consistent across strategies.
- Promotion readiness is visible, but the trader journey shows that promotion success should be verified from durable state, not only transient toast/banner text.
- Inspect remains useful only when every saved run has a clear terminal state: full chart/code surface or an explicit warning. The journey harness should keep being used to prevent regression here.

### Latest Verified State

- `pytest tests/ -q` → **594 passed, 4 warnings**
- `python run_ui_agent.py --ui-only --url http://localhost:8779` → **60/61**, 1 partial in Inspect equity placeholder detection
- `python run_ui_agent.py --journey trader --ui-only --url http://localhost:8780` completes and writes a trader-audit report instead of crashing; current operator concerns are surfaced in the report rather than hidden

### Reports To Read First

- `reports/ui_test_20260419_001447.md` — latest smoke UI run
- `reports/ui_test_20260419_001825.md` — latest trader journey audit

### What's next

- Implement issue `#40` from the GitHub project board
- Improve Backtest Lab guidance around latest-complete windows and blocked history states
- Make promotion success/readiness easier to assert from visible durable UI state, not transient banners only
- Tighten trader-journey reporting so clearly explained blocked states are not treated like silent no-ops

### What was done in Sprint 35

**UI Testing Agent (`tools/ui_agent/`)**
- **`browser.py`** — Playwright wrapper: 11 tool actions (screenshot, click_tab, click_button, fill_input, select_option, expand_expander, scroll_down, get_visible_text, report_finding, done), `TOOL_DEFINITIONS` schema, `dispatch()`
- **`agent.py`** — Pure Playwright production test runner, 9 test groups, ~65 checks:
  - App shell & navigation (all 5 tabs round-trip)
  - Sidebar controls (symbol selector, auto-refresh, watchlist, chart layers, mode selector, Load New Symbol)
  - Strategies tab (Promotion Control Panel expand/content, strategy selector, catalog table, expanders, buttons)
  - Backtest Lab (selectors, date inputs, Run Backtest execution + result detection)
  - Runtime Monitor (6 timeframe switches 1m→1d, mode switching paper/live/all, metrics)
  - Symbol chart coverage (iterate up to 5 ready symbols, chart renders per symbol)
  - Market Focus (study expander, sliders, Run Weekly Study button, ranked table)
  - Inspect tab (run selector, 4 metrics, gate banner, equity chart, code viewer)
  - Background data & history (audit banner, backfill button, Load New Symbol job queue)
- **`data_checks.py`** (NEW) — 10 DB-level data integrity checks:
  - Candle freshness (latest candle ≤10 min old per ready symbol)
  - History depth (≥30 days per ready symbol)
  - OHLCV sanity (no zero/null/inverted candles in last 500 rows)
  - Candle continuity (no gaps >2 min in last 1h)
  - Trade log integrity (no consecutive same-side trades = no open position leaks)
  - Backtest metric sanity (Sharpe finite, n_trades ≥0, drawdown in [0,1])
  - Backtest equity integrity (win+loss pairs consistent, P&L arithmetic valid)
  - Position size compliance (notional per BUY ≤ POSITION_SIZE_PCT × STARTING_BALANCE)
  - Active artifact integrity (file exists on disk, SHA-256 hash matches DB)
  - Ready symbol DB coverage (every ready symbol has ≥1440 candles = 1 full day)
- **`report.py`** — `build_report()`, `write_report()` — JSON + Markdown to `reports/`
- **`run_ui_agent.py`** — CLI: `python run_ui_agent.py [--headed] [--data-only] [--ui-only]`
- **`tests/test_ui_agent_smoke.py`** — 5 smoke tests for report helpers
- **`tests/test_data_checks.py`** (NEW) — 18 unit tests for data check logic (mocked DB)
- **`requirements.txt`** — added `playwright>=1.44.0`, `groq>=1.0.0`
- **579 total passing** (+18 over Sprint 34)

### How to run
```bash
# Full run (UI + data checks):
python run_ui_agent.py --headed

# Data checks only (no browser):
python run_ui_agent.py --data-only

# UI only:
python run_ui_agent.py --ui-only --headed
```

### Sprint 36 Goal
No queued roadmap item. Check GitHub Projects board `#1` or ask the user for the next priority.

## Just Closed — Sprint 33

**Sprint 33 is closed and pushed to `master`.** The repo now has a versioned strategy promotion pipeline so the platform is deployed once while strategy artifacts move through `generated draft -> reviewed plugin -> backtest -> paper -> live`.

### What was done in Sprint 33
- **Artifact registry + persistence**
  - `database/models.py` now includes `StrategyArtifact` plus artifact/hash/provenance fields on backtest runs, backtest trades, runtime trades, portfolio snapshots, and promotions.
  - `strategy/artifacts.py` owns code-hash calculation, artifact registration, generated-draft review/save, paper/live target selection, promotion status changes, and runtime hash validation.
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
- **Verification**
  - `pytest tests/ -q` => **543 passed, 4 warnings**
  - headless dashboard startup verified
  - pushed to `master` as commit `62904ad`

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
| Sprint 33 — Versioned Strategy Promotion Pipeline | ✅ CLOSED | Shared Codex + Claude Code stream | 2026-04-18 |
| Sprint 34 — Promotion Control Panel Hardening | ✅ CLOSED | Claude Code | 2026-04-18 |
| Sprint 35 — AI UI Testing Agent + Production Data Integrity Suite | ✅ CLOSED | Claude Code | 2026-04-18 |

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

## In Progress — Claude Code left off here (Sprint 39)

**Sprint:** Sprint 39 — Trading Diary + Backtest Knowledge
**Last file edited:** `dashboard/streamlit_app.py` (write was rejected due to token limit — not yet written)
**What was done:**
- `database/models.py` — Added `TradingDiaryEntry` ORM model + migration block for `outcome_rating`, `learnings`, `strategy_suggestion`
- `trading_diary/__init__.py` — Created (package marker)
- `trading_diary/backtest_insights.py` — Created: `extract_backtest_insights`, `_regime_analysis`, `_hour_analysis`, `_loss_streak_analysis`, `_parameter_hints`, `_pair_trades_pnl`
- `trading_diary/service.py` — Created: `record_trade_diary_entry`, `record_backtest_insight`, `record_session_summary`, `list_diary_entries`, `update_diary_entry`, `get_trading_summary`
- `trading_diary/export.py` — Created: `export_diary_to_knowledge()` → `knowledge/diary_learnings.md`
- `backtester/service.py` — Wired `record_backtest_insight` after `sess.commit()` (try/except guard)
- `simulator/paper_trader.py` — Pulled `Trade()` out of `with` block; wired `record_trade_diary_entry` after commit
- `dashboard/workbench.py` — Added `build_diary_summary_metrics` and `build_diary_entries_frame` helpers
- `dashboard/streamlit_app.py` — Added diary imports and changed tabs from 5 to 6 (declared `diary_tab`)

**What's next (exact next step):**
Append the `with diary_tab:` content block to the END of `dashboard/streamlit_app.py` (currently 2141 lines). The tab is declared but has no content. Add the following 5 sections:

```python
# ── Trading Diary tab ──────────────────────────────────────────────────────────
with diary_tab:
    st.markdown("### Trading Diary")
    st.caption("Auto-generated entries from paper/live trades and backtests. Annotate entries with learnings and export to the knowledge base.")

    # a. Trading Summary — 4 metrics (st.columns(4)), P&L by strategy bar chart, P&L by symbol bar chart
    #    Use go.Bar (already imported as `go`), NOT plotly.express
    #    summary_raw = get_trading_summary()
    #    dsm = build_diary_summary_metrics(summary_raw)
    #    by_strategy = summary_raw.get("by_strategy") or {}
    #    by_symbol = summary_raw.get("by_symbol") or {}
    #    Wrap in try/except, show st.warning on error

    # b. Recent Diary Entries — 4 filters (run_mode selectbox, symbol text_input, strategy text_input, entry_type selectbox)
    #    diary_df = build_diary_entries_frame(list_diary_entries(...))
    #    st.dataframe(diary_df, use_container_width=True) or st.info("No entries")
    #    Annotation form: st.number_input entry ID → st.expander → st.form with slider(1-5), 2x text_area, form_submit_button → update_diary_entry()

    # c. Session Summary — st.selectbox(["paper","live"]) + st.button → record_session_summary(mode) → st.success

    # d. Backtest Insights — list_diary_entries(entry_type="backtest_insight", limit=20)
    #    for each entry: st.expander with st.text(entry["content"])

    # e. Export Knowledge — st.button → export_diary_to_knowledge() → st.success(path)
```

**Then write `tests/test_trading_diary.py`** (13 tests, all mocked — no real DB). See plan file at `C:\Users\karll\.claude\plans\whats-next-fluttering-cocke.md` for the full test list.

**Then run:** `pytest tests/ -q` → must stay at 594+ passed

**Then commit and push** with message: `Sprint 39 — Trading Diary + Backtest Knowledge`

**Then create GitHub issue** and add to Projects board #1.

**Partial work notes:**
- `knowledge/experiment_log.md` and `market_data/history.py` are dirty from earlier sprints — leave them unless specifically requested
- All diary writes are wrapped in `try/except Exception: pass` — they must never break the primary workflow
- Use soft FKs only (no `ForeignKey()`) — codebase convention
- Tags stored as JSON string (consistent with `params_json`/`metrics_json`)
- `go.Bar` only in dashboard — NOT `plotly.express`
- Full plan is at: `C:\Users\karll\.claude\plans\whats-next-fluttering-cocke.md`

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
