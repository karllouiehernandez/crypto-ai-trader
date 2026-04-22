# Agent Resume Pack

Use this file for agent switching. It is the compact handoff intended for Codex, Claude Code, and GitHub Copilot Pro.
Codex and Claude Code must treat the repo as one continuous shared developer stream.

Read order for a new agent:
1. `HANDOFF.md`
2. `knowledge/agent_resume.md`
3. Only then open the specific source files needed for the current sprint
4. Read `knowledge/sprint_log.md` only when historical context is actually needed

## Current Sprint

- Sprint 41 is closed.
- Active local follow-on work: `Sprint 42 — Paper Evidence, Trader Journey Stabilization, and Legacy Integrity Closure`
- GitHub status: Sprint 42 is issue `#44` on Projects board `#1`, and the board card is now `In Progress`; `HANDOFF.md` remains the source of truth for the exact current continuation state.
- Baseline after the current Sprint 42 work:
  - `pytest tests/ -q` -> `657 passed, 4 warnings`
  - `python run_ui_agent.py --data-only` -> `0 FAIL, 0 PARTIAL, 1 SKIP` on `2026-04-22` with `run_live.py` active
  - `python run_ui_agent.py --journey trader --ui-only --url http://localhost:8785` -> `0 FAIL, 4 PARTIAL, 2 SKIP` on `2026-04-22`
  - `python run_ui_agent.py --ui-only --headed --url http://localhost:8785` -> `64/64 PASS`
  - `python run_ui_agent.py --journey trader --ui-only --headed --url http://localhost:8785` -> `27/28 PASS`, `0 FAIL`, `0 PARTIAL`, `1 SKIP`
  - The trader journey now exits deterministically and writes a report; the remaining operator gap is real paper evidence, not UI audit completion
  - Phase 1 persistence/recovery validation is now in the repo via `database/persistence.py`, `tests/test_persistence.py`, and the Strategies-tab `Persistence & Recovery` expander
  - Phase 2 deterministic paper-evidence progress surfaces are now in the repo via `strategy/paper_evaluation.py`, `simulator/paper_trader.py`, `run_live.py`, and the Strategies-tab `Paper Evidence Progress` section
  - Maintained-universe freshness auto-repair is now in the repo via `market_data/history.py::maintain_symbol_freshness()` and `run_live.py::freshness_guard_loop()`
  - Runtime log output is now ASCII-safe in `run_live.py`, `llm/self_learner.py`, `llm/client.py`, and `collectors/live_streamer.py`, so Windows stderr capture no longer fills with mojibake placeholders
  - Default environment now includes one generated draft strategy: `generated_range_probe_v1` from `strategies/generated_20260422_120800.py`, registered as draft artifact `#4`
  - Repo-root `install_once.bat` now exists as the non-destructive one-time Windows bootstrap path and has been validated locally
  - `tools/ui_agent/data_checks.py` now grades candle freshness against the maintained MVP research universe first, instead of every symbol with any candle rows
  - `tests/conftest.py` now redirects the full pytest session to a dedicated temp SQLite DB, so the suite no longer mutates the live workbench database
  - The maintained MVP universe (`BTCUSDT`, `ETHUSDT`, `BNBUSDT`) was directly backfilled back to 30-day coverage after the earlier live-DB corruption was discovered
  - Sprint 42 now has GitHub tracking: [issue #44](https://github.com/karllouiehernandez/crypto-ai-trader/issues/44)
  - Live DB legacy archive has now been applied: `731` trades + `83` backtest runs archived, `0` archivable legacy rows remain
  - Archive-gap refresh bug was fixed so archived rows no longer cause new false `legacy-invalid` tags across sequence gaps
  - `run_live.py` has been restarted; maintained-universe freshness is live again and candle freshness is no longer the data-check blocker
  - `backtester/engine.py` no longer rebuilds indicators from the DB on every candle; backtests now precompute one indicator source per run and pass trailing historical windows into `strategy/runtime.py`
  - This also fixes a correctness issue: backtests were previously reading the latest candles instead of an as-of historical window
  - `dashboard/workbench.py` now chooses Backtest Lab defaults from fresh/runnable symbols and latest known runnable windows instead of blindly inheriting any ready symbol
  - `dashboard/workbench.py` now also exposes `latest_complete_backtest_day()`, and Backtest Lab uses that shared helper so intraday candles do not default the trader to an incomplete current-day backtest window
  - `dashboard/streamlit_app.py` now carries a freshly saved backtest run directly into the Inspect tab via session state
  - `tools/ui_agent/agent.py` smoke coverage is calibrated to the actual six-tab workbench and the usable timeframe controls; smoke is now fully green
  - `tools/ui_agent/trader_journey.py` now uses a recent deterministic audit window plus explicit post-save / post-select waits, and the full headed trader journey now completes without FAIL/PARTIAL findings
  - `knowledge/iteration_learnings.md` now exists as the per-iteration learning log
  - `knowledge/kb_update.py --type iteration` can append a structured iteration learning after each meaningful development or validation slice
  - `database/models.py` now enables WAL mode and a 30-second SQLite busy timeout so `run_live.py` is less likely to die with `database is locked` while Streamlit is active
  - Sprint 42 now also carries a phased pre-deploy hardening track in issue comment `#4295460139`

## Why This Exists

`knowledge/sprint_log.md` is the long-form archive. It should not be the default first read during agent switching because it consumes a large amount of context for little immediate value.

## Current State

- Shared-agent rule:
  - Codex and Claude Code must act as one developer on this repo
  - Do not treat local dirty files as belonging to one specific agent unless the user explicitly asks for attribution
  - Continue from the current worktree as shared in-progress state
- Sprint 39 is now the latest closed sprint:
  - GitHub issue: `#41` — `Sprint 39 — Trading Diary + Backtest Knowledge`
  - Project board: issue added to GitHub Projects board `#1`
  - `dashboard/streamlit_app.py` now fully renders the `Trading Diary` tab with summary metrics, diary filters, annotation form, session summary action, recent backtest insights, and knowledge export
  - `tests/test_trading_diary.py` adds 13 mocked tests covering trade diary content, insight verdicts, regime suggestions, export writing, and filtered diary queries
  - `python -m py_compile dashboard/streamlit_app.py` passes
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

**Sprint 42 continuation** — persistence/recovery and evidence-progress visibility are implemented. The next work is operational follow-through, not another redesign.

Next steps:
1. Keep the active paper-mode `run_live.py` process on paper target `rsi_mean_reversion_v1` artifact `#2` until the first real tagged BUY and SELL trades exist
2. Once real SELL trades exist, use the deterministic evidence summary to decide whether `paper_passed` is justified or which metric gate is failing
3. Investigate the current trader-journey partials: `generated_range_probe_v1`, `ema200_filtered_momentum`, `mtf_confirmation`, and `rsi_mean_reversion_v1` all show persistent `run-failed` backtest states rather than saved runs in the current environment
4. Keep Sprint 42 issue `#44` updated as work lands
5. Keep recording one entry in `knowledge/iteration_learnings.md` after each meaningful development or validation slice
6. Avoid parallel pytest invocations; the current session-level temp DB bootstrap is not safe for concurrent pytest commands
7. Keep `HANDOFF.md` current; this file should stay compact and secondary

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
- `tests/conftest.py` is now a hard safety rail: do not bypass repo pytest isolation or point tests back at the live app DB
- Do not stage runtime-generated `reports/` or `.streamlit_eval.*` files unless the user explicitly asks
- Do not clear active paper/live artifact settings as part of test cleanup; those are live workspace state, not disposable fixtures
- Keep the Jesse-like workflow intact
- Prefer pure helpers in `dashboard/workbench.py` over embedding ranking/formatting logic directly in Streamlit
- Keep the responsive chart self-contained and locally bundled; do not introduce a Node build step

## Last Verified State

- Tests: `657 passed, 4 warnings`
- Data checks: `0 FAIL, 0 PARTIAL, 1 SKIP` on `2026-04-22`
- Smoke UI: `64/64 PASS` on the latest headed validation run
- Dashboard compile: `python -m py_compile dashboard/streamlit_app.py dashboard/workbench.py strategy/paper_evaluation.py simulator/paper_trader.py run_live.py` passed in the latest Sprint 42 validation slice
- Paper target: `rsi_mean_reversion_v1` artifact #2 = `paper_active` in DB
- Freshness contract: maintained universe (`BTCUSDT`, `ETHUSDT`, `BNBUSDT`) now passes freshness; stale exploratory symbols no longer create false freshness PARTIALs
- Maintained-universe sync on `2026-04-22` inserted `1295` fresh `1m` candles each for `BTCUSDT`, `ETHUSDT`, and `BNBUSDT`, restoring the clean data-only baseline
- New continuity guard: `maintain_symbol_freshness()` repaired an additional `14` stale minutes per maintained symbol during live verification; `run_live.py` now includes this guard at startup and every 5 minutes, but it still requires an active runner process to operate continuously
- Current runtime validation: `run_live.py` is active again in paper mode, startup and heartbeat logs are ASCII-clean, and maintained-universe candles are advancing in real time
- Paper-evidence blocker is now classified precisely: artifact `#2` has `0` artifact-tagged trades total (`0` BUY, `0` SELL), so the current gate failure is `no entries yet`
- Trader-journey draft-path coverage is now active: the generated draft guard passes against artifact `#4` instead of being skipped
- Verification caveat: do not run multiple `pytest` commands in parallel; the shared temp-DB bootstrap in `tests/conftest.py` can race and produce a false `table candles already exists` error
- Test isolation: full `pytest` now runs against a temp DB and no longer wipes live candles, artifacts, or app settings
- Maintained-universe recovery: `BTCUSDT`, `ETHUSDT`, `BNBUSDT` each restored to `43201` local 1m candles
- GitHub: Sprint 41 issue `#43` is closed history; Sprint 42 is now tracked as issue `#44` on board `#1`
- Live DB legacy containment: applied and consistent (`731` archived legacy trades, `83` archived legacy runs, `0` archivable rows remain)
- Current operational blocker: no artifact-tagged paper evidence yet, even though the default environment now yields a complete reviewed-strategy backtest -> Inspect -> paper-promotion audit path
- Headed production validation conclusion: UI smoke, trader journey, and data-only checks are green enough for a supervised research/backtest/paper-readiness workbench, but the app is still not yet production-ready for live trading because forward paper evidence and live-approval proof are still missing

## Token-Saving Rule

If you only need to continue the active sprint, do not read the full sprint log first. Use `HANDOFF.md` + this file + the relevant code files.
