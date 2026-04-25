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
- Active local sprint: `Sprint 42 — Operational paper-evidence follow-through (background observation thread)`
- GitHub status: Sprint 46 is issue `#48` on Projects board `#1`; Sprint 47 issue creation/update is currently blocked by GitHub integration write permissions; `HANDOFF.md` remains the source of truth for the exact current continuation state.
- GitHub write caveat: close-out comment/state sync for issue `#48` is currently blocked by `403 Resource not accessible by integration`, so repo-local handoff marks Sprint 46 complete even if GitHub issue state still needs a manual close.
- Latest completed sprint: `Sprint 49 — Professional Symbol Universe + Historical Data Mirror`
  - GitHub issue: not created programmatically; current integration previously returned `403 Resource not accessible by integration`
  - Delivered:
    - curated Professional 20 Binance spot USDT research universe in `market_data/professional_universe.py`
    - sidebar dashboard panel to queue Professional 20 history, inspect status/readiness, and save a Jetson-safe runtime subset
    - Binance Data Vision archive ZIP mirror cache controlled by `BINANCE_HISTORY_CACHE_DIR`
    - `python -m collectors.historical_loader warm-cache --universe professional --days 30`
    - deployment docs/env templates for USB/local cache operation
  - Verified:
    - `pytest tests/test_market_data_services.py -q` -> `26 passed` on `2026-04-25`
    - `pytest tests/ -q` -> `712 passed, 4 warnings` on `2026-04-25`
    - `python run_ui_agent.py --ui-only --url http://localhost:8794` -> `63/64 PASS, 1 PARTIAL, 0 FAIL` on `2026-04-25`
    - `python run_ui_agent.py --data-only` -> `0 FAIL, 1 PARTIAL, 1 SKIP` on `2026-04-25`; partial is stale Windows dev DB candle freshness
  - Deployed to Jetson on `2026-04-25`:
    - backup created at `/home/jetson/crypto_ai_trader/backups/state_backup_20260425T011511Z`
    - dashboard service restarted and reachable at `http://192.168.100.30:8501`
    - runtime service left active so artifact `#8` continues paper evidence observation
    - `python -m deployment.jetson_ops health` -> `Ready`
- Previously completed sprint: `Sprint 48.4 — Jetson Thermal Fan Service`
  - GitHub issue: not created programmatically; current integration returned `403 Resource not accessible by integration`
  - Delivered:
    - `deployment/jetson_fan_control.py` with hysteresis-based PWM control
    - `deployment/crypto-trader-fan.service`
    - Jetson installers now install/enable runtime, dashboard, and fan services together
  - Verified:
    - `pytest tests/test_jetson_fan_control.py -q` -> `3 passed` on `2026-04-25`
    - `pytest tests/ -q` -> `707 passed, 4 warnings` on `2026-04-25`
    - Jetson updated in place over SSH/SFTP and `crypto-trader-fan.service` is active under `systemd`
- Previously completed sprint: `Sprint 48.3 — Jetson Streamlit systemd Service`
  - GitHub issue: not created programmatically; current integration returned `403 Resource not accessible by integration`
  - Delivered:
    - `deployment/crypto-trader-dashboard.service`
    - Jetson installers now install/enable both runtime and dashboard services
    - deployment docs now include dashboard service operations and the `:8501` access path
  - Verified:
    - Jetson updated in place over SSH/SFTP on `2026-04-25`
    - `crypto-trader.service` active under `systemd`
    - `crypto-trader-dashboard.service` active under `systemd`
    - dashboard reachable at `http://192.168.100.30:8501`
- Previously completed sprint: `Sprint 48.2 — Live Data Freshness Panel`
  - GitHub issue: not created programmatically; current integration returned `403 Resource not accessible by integration`
  - Delivered:
    - persisted runtime worker heartbeat in `run_live.py` via `app_settings`
    - `Runtime Monitor` now has a `Live Data Freshness` panel showing heartbeat age, last snapshot, last trade, and per-symbol candle freshness
    - pure freshness-formatting helpers in `dashboard/workbench.py`
  - Verified:
    - `pytest tests/test_run_live.py tests/test_workbench_helpers.py -q` -> `66 passed` on `2026-04-25`
    - `pytest tests/ -q` -> `704 passed, 4 warnings` on `2026-04-25`
- Previously completed sprint: `Sprint 48.1 — Jetson Python 3.10 Bootstrap Fallback`
  - GitHub issue: not created programmatically; current integration returned `403 Resource not accessible by integration`
  - Delivered:
    - `deployment/bootstrap_python310_install.sh` to handle Jetson Nano images where `apt` cannot provide Python 3.10
    - deployment docs now include the explicit compile-from-source fallback
  - Verified:
    - fallback added in response to a real Jetson Nano install failure on Ubuntu 20.04 arm64 where `python3.10` packages were unavailable from `apt`
- Previously completed sprint: `Sprint 48 — Jetson Flash Deployment + Remote Access Bootstrap`
  - GitHub issue: not created programmatically; current integration returned `403 Resource not accessible by integration`
  - Projects board `#1` status: not synced programmatically for the same reason
  - Delivered:
    - repo-root `prepare_jetson_flash_drive.bat` for creating a sanitized `crypto_ai_trader_bundle` on a flash drive
    - `deployment/install_from_bundle.sh` for installing on Jetson from that bundle instead of cloning
    - repo-root `setup_jetson_remote_access.bat` for one-time Windows-side SSH key install and remote-access bootstrap
    - `deployment/setup_remote_access.sh` for enabling OpenSSH/SFTP on Jetson
    - updated `deployment/README.md` with flash-drive and SSH/SFTP instructions
  - Verified:
    - `cmd /c prepare_jetson_flash_drive.bat /?` -> help renders correctly on `2026-04-24`
    - `cmd /c setup_jetson_remote_access.bat /?` -> help renders correctly on `2026-04-24`
    - `pytest tests/ -q` -> `700 passed, 4 warnings` on `2026-04-24`
    - Linux shell scripts were reviewed but not executed locally because this Windows machine has no installed WSL distribution
- Previously completed sprint: `Sprint 47 — Strategy Pack Import / Export`
  - GitHub issue: not created programmatically; current integration returned `403 Resource not accessible by integration`
  - Projects board `#1` status: not synced programmatically for the same reason
  - Delivered:
    - portable strategy-pack export as `.zip` with `manifest.json`, strategy source, and optional `notes.md`
    - pack import preview and draft import in the dashboard `Create / Import Strategy Draft` workflow
    - imported packs still pass through the same SDK validator and remain backtest-only generated drafts until reviewed
    - strategy-pack workflow documented in `strategies/README.md`
  - Verified:
    - `pytest tests/test_strategy_plugin_sdk.py -q` -> `22 passed` on `2026-04-23`
    - `pytest tests/ -q` -> `700 passed, 4 warnings` on `2026-04-23`
    - `python run_ui_agent.py --ui-only --url http://localhost:8791` -> `64/64 PASS` on `2026-04-23` against a temporary headless verification server
- Earlier completed sprint: `Sprint 46 — Deployment Lock & Strategy SDK Compatibility`
  - GitHub issue: `#48`
  - Projects board `#1` status: `In Progress` until close-out is confirmed; `HANDOFF.md` is the current source of truth
  - Delivered:
    - explicit strategy SDK lock in `StrategyBase` and draft validation
    - strategy lifecycle surfaces now show SDK version and compatibility
    - reviewed-plugin save/review path hard-rejects unsupported SDK versions
    - `strategies/README.md` now documents the deployment strategy SDK contract
  - Verified:
    - `pytest tests/ -q` -> `696 passed, 4 warnings` on `2026-04-23`
    - `python run_ui_agent.py --ui-only --url http://localhost:8790` -> `64/64 PASS` on `2026-04-23` against a temporary headless verification server
    - `python run_live.py --help` -> safe CLI exit on `2026-04-23`
- Previously completed sprint: `Sprint 45 — Strategy Authoring Polish`
  - GitHub issue: `#47`
  - Projects board `#1` status: `Done`
  - Delivered: dashboard editing for existing generated drafts, safe draft source loading, generated-draft listing, next-name suggestions for duplicate drafts, and SDK regression coverage.
  - Sprint 44 remains complete: Jetson health CLI, backup/restore CLI, reviewed-artifact repin command, systemd/logrotate assets, installer hardening, and dashboard deployment readiness panel.
  - Sprint 43 remains complete: formal strategy template contract, dashboard create/import draft workflow, validation before discovery, explicit hot reload, backtest-only drafts, and reviewed artifact pinning preservation.
- Baseline after Sprint 49 completion:
  - `pytest tests/ -q` -> `712 passed, 4 warnings` on `2026-04-25`
  - `python run_ui_agent.py --data-only` -> `0 FAIL, 1 PARTIAL, 1 SKIP` on `2026-04-25` (local Windows dev DB candle freshness stale)
  - `python run_ui_agent.py --ui-only --url http://localhost:8794` -> `63/64 PASS, 1 PARTIAL, 0 FAIL` on `2026-04-25` (backtest click response partial under stale local data)
  - `python -m deployment.jetson_ops health` -> `Ready` on required checks on `2026-04-25`
  - Jetson runtime, dashboard, and fan services are all active under `systemd` on `2026-04-25`
  - Jetson dashboard is reachable at `http://192.168.100.30:8501`
  - `python run_ui_agent.py --journey trader --ui-only --headed --url http://localhost:8785` -> `29/31 PASS`, `0 FAIL`, `0 PARTIAL`, `2 SKIP` on `2026-04-22`
  - `python run_ui_agent.py --ui-only --url http://localhost:8791` -> `64/64 PASS`
  - The trader journey now exits deterministically, writes a report, and no longer produces false plugin `run-failed` partials; the remaining operator gap is real paper evidence, not UI audit completion
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
  - Sprint 43 now lets traders create/import strategy drafts inside the dashboard:
    - `strategy/plugin_sdk.py` validates syntax, required metadata, behavior methods, params schema/default compatibility, duplicate `name + version`, and known indicator-column references
    - `strategies/loader.py` validates before discovery and unregisters stale strategy entries when a plugin becomes invalid
    - `dashboard/streamlit_app.py` exposes `Create / Import Strategy Draft` with template, paste, upload, validate, save, and `Refresh Strategy Registry`
    - generated/imported drafts remain backtest-only until reviewed into pinned plugin artifacts
  - Sprint 44 added Jetson deployment operations:
    - `python -m deployment.jetson_ops health`
    - `python -m deployment.jetson_ops backup`
    - `python -m deployment.jetson_ops restore <manifest>` with dry-run default
    - `python -m deployment.jetson_ops repin-artifact <id> --apply` for explicit reviewed hash acknowledgment
    - active paper target was moved from stale artifact `#2` to current matching artifact `#8` for the same `rsi_mean_reversion_v1` reviewed plugin
  - Sprint 45 added Strategy Authoring Polish:
    - generated drafts can be selected and edited from the dashboard without restarting Streamlit
    - editing an existing draft saves a new generated revision instead of overwriting the original file
    - invalid or duplicate drafts surface a suggested next strategy name
    - `strategy/plugin_sdk.py` now exposes safe generated-draft listing and source-reading helpers
  - Sprint 42 operational follow-through was refreshed again on `2026-04-23`:
    - active paper target remains reviewed artifact `#8` (`rsi_mean_reversion_v1`)
    - `run_live.py` had stopped and was relaunched; paper snapshots resumed at current-minute cadence
    - artifact `#8` still has `0` tagged BUY trades and `0` tagged SELL trades, so paper-evidence remains blocked by no entries, not by failing metrics
    - accidental `python run_live.py --help` launches are now fixed in code: `argparse` owns the help path and exits before any boot logic runs
    - opportunity scan across the last `30d` of all 5 ready symbols found `0` full entry setups for artifact `#8`; the dominant near-miss is "all filters align except fresh MACD cross", so the next corrective sprint should target entry scarcity / market fit
  - Sprint 46 now locks the deployed app's strategy SDK contract end-to-end:
    - `StrategyBase.meta()` now exposes `sdk_version`
    - `strategy/plugin_sdk.py` defines `STRATEGY_SDK_VERSION = "1"` and rejects unsupported strategy SDK versions during validation
    - dashboard draft authoring now shows the deployment strategy SDK lock in the `Create / Import Strategy Draft` expander
    - generated drafts and the manual `_strategy_template.py` now carry explicit `sdk_version = "1"`
    - `dashboard/workbench.py` and `dashboard/streamlit_app.py` now surface SDK compatibility in the strategy lifecycle area and block unsupported review/promotion actions with explicit operator-facing reasons
    - `strategy/artifacts.py::review_generated_strategy()` now validates rewritten reviewed plugins before saving them into `strategies/`
    - `strategies/README.md` documents the deployment SDK contract for post-deploy strategy authoring
  - Sprint 47 adds deploy-friendly strategy portability:
    - `strategy/plugin_sdk.py` now exports/imports strategy packs with a manifest + source + optional notes bundle
    - `dashboard/streamlit_app.py` now exposes `Strategy Packs` inside `Create / Import Strategy Draft`
    - imported packs remain generated drafts, so paper/live safety rules are unchanged
  - Sprint 48 adds offline Jetson bootstrap and remote access:
    - `prepare_jetson_flash_drive.bat` builds a sanitized deployment bundle on removable media
    - `deployment/install_from_bundle.sh` installs from the copied bundle without requiring GitHub access on the Jetson
    - `setup_jetson_remote_access.bat` plus `deployment/setup_remote_access.sh` establish one-time SSH/SFTP access from Windows
  - Sprint 48.1 adds the missing Python-runtime fallback for real Jetson installs:
    - `deployment/bootstrap_python310_install.sh` compiles Python `3.10.14` locally when `apt` lacks `python3.10`
  - Sprint 48.2 adds a runtime liveness surface for deployed monitoring:
    - `run_live.py` now persists `runtime_worker_heartbeat_ts`
    - `dashboard/streamlit_app.py` `Runtime Monitor` now shows `Live Data Freshness`
    - `dashboard/workbench.py` formats operator-facing freshness metrics and per-symbol candle recency
  - Sprint 48.3 adds a durable dashboard service for deployed monitoring:
    - `deployment/crypto-trader-dashboard.service` runs Streamlit under `systemd`
    - installer paths now enable the dashboard on boot
    - the Jetson was updated in place and the dashboard is now live at `:8501`
  - Sprint 48.4 adds durable thermal protection on-device:
    - `deployment/jetson_fan_control.py` controls `/sys/devices/pwm-fan/target_pwm` from thermal sensors
    - `deployment/crypto-trader-fan.service` keeps fan control alive across reboots
    - the live Jetson now auto-enables fan cooling when temperatures rise and turns the fan back off after cooling

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

**Sprint 42 continuation** — persistence/recovery, evidence-progress visibility, and Sprint 43 strategy-authoring flexibility are implemented. The next work is operational follow-through, not another redesign.

Next steps:
1. Keep the active paper-mode `run_live.py` process on paper target `rsi_mean_reversion_v1` artifact `#8` until the first real tagged BUY and SELL trades exist
2. Once real SELL trades exist, use the deterministic evidence summary to decide whether `paper_passed` is justified or which metric gate is failing
3. Trader-journey false partials are now resolved:
   - the harness scopes terminal-state detection to the actual `Last Backtest Attempt` block
   - dashboard backtests refresh plugin strategies from disk before execution
   - all 8 visible strategies now save runs and open complete Inspect surfaces in the headed journey
4. Manually exercise the Sprint 43 dashboard draft workflow and Sprint 44 Jetson readiness panel in a headed Streamlit session before claiming them as operator-polished
5. Keep Sprint 42 issue `#44` updated as operational evidence lands
6. Keep recording one entry in `knowledge/iteration_learnings.md` after each meaningful development or validation slice
7. Avoid parallel pytest invocations; the current session-level temp DB bootstrap is not safe for concurrent pytest commands
8. Keep `HANDOFF.md` current; this file should stay compact and secondary

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
- `strategy/plugin_sdk.py`
- `strategies/loader.py`
- `strategies/_strategy_template.py`
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
- Paper target: `rsi_mean_reversion_v1` artifact #8 = `paper_active` in DB after Sprint 44 repin from stale artifact #2
- Freshness contract: maintained universe (`BTCUSDT`, `ETHUSDT`, `BNBUSDT`) now passes freshness; stale exploratory symbols no longer create false freshness PARTIALs
- Maintained-universe sync on `2026-04-22` inserted `1295` fresh `1m` candles each for `BTCUSDT`, `ETHUSDT`, and `BNBUSDT`, restoring the clean data-only baseline
- New continuity guard: `maintain_symbol_freshness()` repaired an additional `14` stale minutes per maintained symbol during live verification; `run_live.py` now includes this guard at startup and every 5 minutes, but it still requires an active runner process to operate continuously
- Current runtime validation: `run_live.py` is active again in paper mode, startup and heartbeat logs are ASCII-clean, and maintained-universe candles are advancing in real time
- Paper-evidence blocker is now classified precisely: current paper artifact `#8` has `0` artifact-tagged trades total (`0` BUY, `0` SELL), so the current gate failure is `no entries yet`
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
