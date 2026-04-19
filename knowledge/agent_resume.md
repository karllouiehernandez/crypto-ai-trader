# Agent Resume Pack

Use this file for agent switching. It is the compact handoff intended for Codex, Claude Code, and GitHub Copilot Pro.
Codex and Claude Code must treat the repo as one continuous shared developer stream.

Read order for a new agent:
1. `HANDOFF.md`
2. `knowledge/agent_resume.md`
3. Only then open the specific source files needed for the current sprint
4. Read `knowledge/sprint_log.md` only when historical context is actually needed

## Current Sprint

- Sprint: `Sprint 38 — Trader Journey Trust Fixes` ✅ CLOSED
- Status: All trust-surface fixes implemented in `dashboard/streamlit_app.py` and `tools/ui_agent/trader_journey.py`. Pushed to master.
- Baseline: `pytest tests/ -q` shows `594 passed, 4 warnings`
- Next: Sprint 39 — check GitHub Projects board `#1` or ask user

## Why This Exists

`knowledge/sprint_log.md` is the long-form archive. It should not be the default first read during agent switching because it consumes a large amount of context for little immediate value.

## Current State

- Shared-agent rule:
  - Codex and Claude Code must act as one developer on this repo
  - Do not treat local dirty files as belonging to one specific agent unless the user explicitly asks for attribution
  - Continue from the current worktree as shared in-progress state
- Sprint 37 trader-journey coverage is now in the repo locally:
  - `tools/ui_agent/trader_journey.py` — new stateful Playwright runner that behaves like a normal trader: checks lifecycle status, attempts backtests across the visible strategy catalog, opens `Inspect`, and verifies paper/live readiness UX without placing live orders
  - `run_ui_agent.py` — added `--journey trader`
  - `tools/ui_agent/report.py` — report payloads now optionally include a `journey` block with summary counts, per-strategy audit rows, and operator concerns
  - `tests/test_ui_agent_smoke.py` — added regression tests for journey-aware reports and CLI invocation
  - `dashboard/streamlit_app.py` — `Inspect` saved-run labels now include `#run_id` for deterministic journey selection
- Sprint 37 key learnings from real operator flow:
  - default backtest date windows can still trap the user in incomplete-history states; the dashboard should better guide users toward latest-complete windows
  - trader-facing blocked states must stay explicit and consistent across strategies; if a run does not persist, the UI needs an obvious explanation
  - promotion success/readiness should be inferable from durable UI state, not transient success banners alone
  - the new trader journey is now the best way to catch "looks fine in smoke tests, confusing in real use" regressions
- Sprint 38 is queued remotely for pickup:
  - GitHub issue: `#40` — `Sprint 38 — Trader Journey Trust Fixes`
  - Project board: `https://github.com/users/karllouiehernandez/projects/1`
  - Priority: use the trader-journey audit to fix trust gaps in `Backtest Lab`, `Inspect`, and promotion/readiness UX
- Latest local journey reports to inspect first:
  - `reports/ui_test_20260419_001447.md` — smoke UI run
  - `reports/ui_test_20260419_001825.md` — trader journey audit with operator concerns
- Sprint 35 AI UI Testing Agent + Production Data Integrity Suite is complete and pushed:
  - `tools/ui_agent/browser.py` — Playwright wrapper, 11 tool actions, `TOOL_DEFINITIONS`, `dispatch()`
  - `tools/ui_agent/agent.py` — Pure Playwright 9-group test runner (~65 checks, no LLM)
  - `tools/ui_agent/data_checks.py` — 10 DB-level data integrity checks (candle freshness, history depth, OHLCV sanity, continuity, trade integrity, backtest metrics, equity, position sizing, artifact hash, symbol coverage)
  - `tools/ui_agent/report.py` — `build_report()`, `write_report()` (JSON + Markdown to `reports/`)
  - `run_ui_agent.py` — CLI: `python run_ui_agent.py [--headed] [--data-only] [--ui-only]`
  - `tests/test_ui_agent_smoke.py` — 5 smoke tests
  - `tests/test_data_checks.py` — 18 unit tests for data check logic
- Sprint 34 Promotion Control Panel is complete and pushed:
  - `strategy/artifacts.py` — `deactivate_runtime_artifact(run_mode)`, `list_all_strategy_artifacts()`
  - `dashboard/workbench.py` — `build_runtime_target_summary`, `build_artifact_registry_frame`, `list_rollback_candidates`
  - `dashboard/streamlit_app.py` — `validate_runtime_artifact()` called at page load for both paper/live targets; hero-area banner shows when targets are invalid; Promotion Control Panel expander in Strategies tab with paper/live status cards, Deactivate buttons, rollback selectors, and artifact registry audit table
  - `tests/test_workbench_helpers.py` — 8 new tests (+Sprint 34)
  - `tests/test_strategy_artifacts.py` — 5 new tests (+Sprint 34)
- Sprint 33 artifact lifecycle is complete and pushed:
  - `strategy/artifacts.py` — source of truth for code hashes, artifact registration, review/save, paper/live target selection, and runtime validation
  - `database/models.py` — `StrategyArtifact` model plus artifact/hash/provenance fields on backtest runs, backtest trades, trades, portfolio snapshots, and promotions
  - `strategy/runtime.py` — backtest/default strategy separate from paper/live artifact selection; runtime validates promoted reviewed artifacts
  - `backtester/service.py` — saved backtests persist artifact identity and upgrade reviewed artifacts to `backtest_passed`
  - `simulator/paper_trader.py`, `simulator/coordinator.py`, `run_live.py` — paper/live execution carries artifact identity and fails closed on missing/mismatched artifacts
  - `dashboard/streamlit_app.py` — `Review and Save`, `Promote to Paper`, `Approve for Live` actions; `Inspect` shows artifact identity and code-hash mismatch warnings
  - `dashboard/workbench.py` — artifact-aware workflow stages and catalog columns
- Strategy experiment plugins from Sprint 31 remain implemented and discoverable:
  - `strategies/ema200_filtered_momentum.py`
  - `strategies/mtf_confirmation_strategy.py`
  - Both are still available in Backtest Lab and the new Inspect tab
- Ready-First Symbol UX is in place (Sprint 30):
  - `market_data/symbol_readiness.py` — `list_ready_symbols()`, `is_symbol_ready()`, `queue_symbol_load()`, `retry_failed_load()`, `list_load_jobs()`
  - `list_load_jobs()` now uses a deterministic tie-break when queued timestamps match
  - `market_data/background_loader.py` — daemon thread worker; started by `ensure_worker_running()` on dashboard load
  - `database/models.py` — `SymbolLoadJob` table tracks load job status
  - `dashboard/streamlit_app.py` — chart and Backtest Lab selectors show ready-only symbols; "Load New Symbol" sidebar expander with queue status and retry
- Dynamic Binance spot `USDT` symbol discovery is in place:
  - `market_data/binance_symbols.py`
  - filters active spot `USDT` pairs from Binance metadata
  - sorts by 24h quote volume for UI defaults and market focus
- Runtime symbol activation is now separate from chart/backtest selection:
  - `market_data/runtime_watchlist.py`
  - persisted watchlist functions for paper/live runtime
  - `config.SYMBOLS` is now only the seed/default, not the active universe
- Historical data coverage workflow is now in place:
  - `market_data/history.py`
  - Binance archive backfill + REST delta sync
  - continuity audit and formatted fail-fast error summaries
- Runtime loops now read the persisted watchlist:
  - `collectors/live_streamer.py`
  - `simulator/paper_trader.py`
- Dashboard symbol selectors are dynamic and searchable:
  - `dashboard/streamlit_app.py`
  - runtime watchlist manager is separate from research/backtest symbol selection
  - Backtest Lab exposes history audit and backfill controls
- Backtests now fail fast on incomplete candle windows:
  - `backtester/engine.py`
  - `backtester/walk_forward.py`
  - `run_backtest.py`
- Workbench tabs are in place: `Strategies`, `Backtest Lab`, `Runtime Monitor`, `Market Focus`, `Inspect`
- Runtime and backtest now share one responsive chart renderer:
  - `dashboard/chart_component.py`
  - vendored `Lightweight Charts` asset under `dashboard/assets/`
  - shared payload helpers in `dashboard/workbench.py`
- Candlestick views are no longer Plotly-based:
  - `Runtime Monitor` and `Backtest Lab` use the same TradingView-like renderer
  - Plotly remains for equity, drawdown, and realized P&L
- Strategy studies are visible on the responsive chart again:
  - `EMA 9 / 21 / 55`
  - `EMA 200`
  - `Bollinger Bands`
  - `RSI`
  - `MACD`
- Runtime and backtest charts use the same study payload contract and synced multi-pane renderer
- Runtime marker clutter is reduced:
  - duplicate BUY/SELL markers are aggregated per candle/side
  - runtime mode defaults to `paper`
  - `All` mode now explicitly warns that live + paper markers are combined
- Paper trader now processes each latest candle once:
  - repeated loop ticks no longer generate duplicate trades on the same candle
- Backtest comparison UX is in place from Sprint 22:
  - strategy candidate comparison table
  - saved-run leaderboard
  - run ranking helpers in `dashboard/workbench.py`
- Run-scoped scenarios are in place from Sprint 23:
  - backtest parameter controls in `Backtest Lab`
  - params persisted with each saved run
  - comparison views treat `strategy + params` as the evaluation unit
- Named presets are now in place from Sprint 24:
  - strategy-scoped preset persistence
  - save/apply preset UX in `Backtest Lab`
  - preset names persisted with saved runs when params match a preset
- Weekly Market Focus Selector is now in place from Sprint 25:
  - `market_focus/selector.py` — deterministic ranking, no LLM required
  - `WeeklyFocusStudy` + `WeeklyFocusCandidate` DB tables
  - "Market Focus" 4th tab in dashboard with one-click Backtest Lab prefill
- Runtime monitoring is already strategy-aware and mode-aware

## Immediate Goal

Sprint 38 is closed. Next: determine Sprint 39 from GitHub Projects board `#1` or user direction.

## Likely Files

- `HANDOFF.md`
- `knowledge/agent_resume.md`
- `tools/ui_agent/trader_journey.py`
- `tools/ui_agent/report.py`
- `reports/ui_test_20260419_001825.md`
- `dashboard/streamlit_app.py`
- `dashboard/workbench.py`
- `run_live.py`
- `strategy/artifacts.py`
- `tests/test_workbench_helpers.py`

## Constraints

- `knowledge/experiment_log.md` may remain dirty because a background runtime process writes to it
- Do not edit, stage, or revert `knowledge/experiment_log.md` unless you intentionally stop that process
- Treat pre-existing dirty files as shared state from the combined Codex/Claude stream, not as separate ownership buckets
- Keep the Jesse-like workflow intact
- Prefer pure helpers in `dashboard/workbench.py` over embedding ranking/formatting logic directly in Streamlit
- Keep the responsive chart self-contained and locally bundled; do not introduce a Node build step

## Last Verified State

- Tests: `594 passed, 4 warnings`
- Headless dashboard startup: verified on fresh ports during Sprint 37 work
- Latest smoke UI run: `60/61`
- Trader journey run: completes and writes a report with operator concerns instead of failing at harness level
- Last sprint fully closed/pushed: `Sprint 38`

## Token-Saving Rule

If you only need to continue the active sprint, do not read the full sprint log first. Use `HANDOFF.md` + this file + the relevant code files.
