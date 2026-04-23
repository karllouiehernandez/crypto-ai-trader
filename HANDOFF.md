# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Codex and Claude Code must read this file first and update it last, and they must treat the repo as one continuous shared developer stream.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | Codex |
| **Last updated** | 2026-04-23 (Sprint 47 strategy pack import/export implemented) |
| **Active sprint** | Sprint 42 — `#44` — Operational paper-evidence follow-through (background observation thread) |
| **Latest completed sprint** | Sprint 47 — GitHub issue creation blocked by integration — Strategy Pack Import / Export |
| **Sprint 40** | `#42` — Done on board |
| **Tests** | `pytest tests/ -q` → **700 passed, 4 warnings** on 2026-04-23; `python run_live.py --help` → safe CLI help exit on 2026-04-23; `python run_ui_agent.py --ui-only --url http://localhost:8791` → **64/64 PASS** on 2026-04-23 (temporary headless verification server); focused headed Sprint 45 check → **PASS** on 2026-04-23; `python run_ui_agent.py --data-only` → **0 FAIL, 0 PARTIAL, 1 SKIP** on 2026-04-23; `python -m deployment.jetson_ops health` → **Ready** on required checks on 2026-04-23 |
| **Branch** | `codex/sprint-27-responsive-chart` (shared working branch) |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Blocking issues** | LLM: add `OPENROUTER_API_KEY` + `LLM_ENABLED=true` to `.env`. Jetson: see `deployment/README.md`. |

---

## Resume Here — Sprint 42 Background + Post-Sprint-47 Baseline

Sprint 47 is completed locally as the strategy-pack portability sprint. Sprint 42 remains the background operational thread because reviewed paper artifact `#8` still needs real tagged BUY and SELL trades before deterministic paper evidence can advance.

Goal: lock the deployed base application so future post-deploy work focuses on creating compatible strategies rather than patching core app code.

### Latest Completed — Sprint 47 (2026-04-23)

- **What changed**
  - Extended [strategy/plugin_sdk.py](strategy/plugin_sdk.py):
    - added `STRATEGY_PACK_FORMAT_VERSION = "1"`
    - added `export_strategy_pack(...)`
    - added `inspect_strategy_pack(...)`
    - added `import_strategy_pack(...)`
    - SDK support metadata now reports the current strategy-pack format version
  - Extended [dashboard/streamlit_app.py](dashboard/streamlit_app.py) `Create / Import Strategy Draft` expander with a new `Strategy Packs` section:
    - export any local strategy with a filesystem-backed source path as a portable `.zip`
    - include optional operator notes in `notes.md`
    - preview uploaded pack metadata before import
    - import valid packs back into the same generated-draft workflow
  - Updated [strategies/README.md](strategies/README.md) with strategy-pack workflow notes and pack-format expectations.
  - Added regression coverage in [tests/test_strategy_plugin_sdk.py](tests/test_strategy_plugin_sdk.py) for:
    - pack export contents
    - missing manifest rejection
    - valid pack import into a generated draft
    - invalid zip rejection
- **What was verified**
  - `pytest tests/test_strategy_plugin_sdk.py -q` → **22 passed**
  - `python -m py_compile strategy/plugin_sdk.py dashboard/streamlit_app.py tests/test_strategy_plugin_sdk.py` → clean
  - `pytest tests/ -q` → **700 passed, 4 warnings**
  - `python run_ui_agent.py --ui-only --url http://localhost:8791` → **64/64 PASS** against a temporary headless Streamlit verification server
  - Paper-evidence background thread remains alive:
    - active worker command still `python run_live.py`
    - artifact `#8` latest paper snapshot observed at `2026-04-23 13:16:00 UTC`
    - artifact `#8` still has `0` tagged trades
- **What remains next**
  - GitHub write follow-through is still blocked by `403 Resource not accessible by integration`:
    - Sprint 46 issue `#48` still needs manual close / board sync
    - Sprint 47 issue / board card could not be created programmatically
  - The next product sprint after Sprint 47 should be Jetson long-run validation:
    - verify restart survival on the device
    - verify backup/restore on the device
    - verify freshness and paper snapshots stay healthy across days, not only local test windows
  - Keep Sprint 42 as a background operational observation thread:
    - active paper target artifact `#8` is still healthy
    - artifact `#8` still has `0` tagged BUY trades and `0` tagged SELL trades
    - the next strategy-focused corrective sprint should target entry scarcity / market fit if that remains true after a meaningful observation window

### Latest Completed — Sprint 46 Phase 2 (2026-04-23)

- **What changed**
  - Extended [dashboard/workbench.py](dashboard/workbench.py):
    - added `strategy_sdk_compatibility(...)`
    - strategy workflow status now surfaces `SDK Mismatch` as a first-class lifecycle state
    - strategy catalog rows now include `sdk_version` and `sdk_compatibility`
  - Extended [dashboard/streamlit_app.py](dashboard/streamlit_app.py) `Strategies` tab:
    - selected-strategy lifecycle area now shows SDK version and SDK compatibility beside origin/version/regimes
    - incompatible drafts/plugins render explicit blocked-state copy instead of leaving review/promotion buttons ambiguously disabled
    - `Review and Save`, `Promote to Paper`, `Approve for Live`, and `Evaluate for Paper Pass` now all require SDK-compatible strategy metadata
    - generated review-name defaults now auto-suggest a non-colliding reviewed plugin name when the current name would collide
  - Hardened [strategy/artifacts.py](strategy/artifacts.py):
    - `review_generated_strategy(...)` now validates the rewritten reviewed plugin source before writing it to `strategies/`
    - unsupported SDK versions are rejected before a reviewed plugin artifact can be registered
  - Documented the deployed strategy contract in [strategies/README.md](strategies/README.md):
    - required metadata
    - required parameter methods
    - supported signal contract
    - current and supported SDK versions
  - Added regression coverage in:
    - [tests/test_strategy_artifacts.py](tests/test_strategy_artifacts.py)
    - [tests/test_workbench_helpers.py](tests/test_workbench_helpers.py)
- **What was verified**
  - `pytest tests/test_strategy_artifacts.py tests/test_workbench_helpers.py tests/test_strategy_plugin_sdk.py -q` → **86 passed**
  - `python -m py_compile strategy/artifacts.py dashboard/workbench.py dashboard/streamlit_app.py tests/test_strategy_artifacts.py tests/test_workbench_helpers.py tests/test_strategy_plugin_sdk.py` → clean
  - `pytest tests/ -q` → **696 passed, 4 warnings**
  - `python run_ui_agent.py --ui-only --url http://localhost:8790` → **64/64 PASS** against a temporary headless Streamlit verification server
- **What remains next**
  - Sprint 46 is complete; the deployment-lock contract is now visible across draft authoring, strategy lifecycle UI, reviewed-plugin acceptance, and docs.
  - GitHub write follow-through is currently blocked again by `403 Resource not accessible by integration`; if access returns, close issue `#48` and sync the Projects board status to `Done`.
  - Keep Sprint 42 as a background operational observation thread:
    - active paper target artifact `#8` is still healthy
    - artifact `#8` still has `0` tagged BUY trades and `0` tagged SELL trades
    - the next strategy-focused sprint should target entry scarcity / market fit if that remains true after a meaningful observation window

### Latest Completed — Sprint 46 Phase 1 (2026-04-23)

- **What changed**
  - Added explicit strategy SDK compatibility metadata to [strategy/base.py](strategy/base.py):
    - `sdk_version = "1"` default on `StrategyBase`
    - `meta()` now includes `sdk_version`
  - Extended [strategy/plugin_sdk.py](strategy/plugin_sdk.py):
    - `STRATEGY_SDK_VERSION = "1"`
    - `SUPPORTED_STRATEGY_SDK_VERSIONS`
    - `strategy_sdk_support()`
    - validation now rejects unsupported `sdk_version` values with `unsupported_sdk_version`
    - generated template drafts now include explicit `sdk_version`
  - Updated [strategies/_strategy_template.py](strategies/_strategy_template.py) to carry `sdk_version = "1"` for manual file-based authoring.
  - Extended [dashboard/streamlit_app.py](dashboard/streamlit_app.py) `Create / Import Strategy Draft` with a visible deployment SDK lock banner showing:
    - current supported SDK version
    - supported versions list
    - signal contract
  - Added regression coverage in [tests/test_strategy_plugin_sdk.py](tests/test_strategy_plugin_sdk.py) for:
    - template SDK marker
    - SDK support helper
    - unsupported SDK version rejection
- **What was verified**
  - `pytest tests/test_strategy_plugin_sdk.py tests/test_strategy_base.py tests/test_strategy_loader.py -q` → **56 passed**
  - `python -m py_compile strategy/base.py strategy/plugin_sdk.py dashboard/streamlit_app.py strategies/_strategy_template.py tests/test_strategy_plugin_sdk.py` → clean
  - `pytest tests/ -q` → **693 passed, 4 warnings**
  - `python run_live.py --help` → safe CLI help exit
- **What remains next**
  - Phase 2 should extend the same deployment-lock concept into reviewed-plugin acceptance and dashboard status surfaces:
    - show SDK compatibility in the strategy catalog / lifecycle area
    - block review/save-to-plugin actions when a draft targets an unsupported SDK version
    - document the deployment strategy SDK contract clearly in `strategies/README.md`
  - Sprint 42 remains operationally relevant in the background:
    - paper target artifact `#8` is still healthy but has `0` tagged BUY trades and `0` tagged SELL trades
    - quantified scan confirmed the next corrective strategy-focused sprint should target entry scarcity / market fit

### Latest Completed — Sprint 43

Sprint 43 is tracked as GitHub issue `#45` and was implemented on 2026-04-23.

Goal: make the deployed application flexible enough that new strategies can be created, imported, validated, backtested, reviewed, and promoted as versioned artifacts without changing application code.

Implemented:
- Added formal Strategy Plugin SDK helpers in [strategy/plugin_sdk.py](strategy/plugin_sdk.py):
  - template generation
  - syntax/contract validation
  - duplicate `name + version` detection
  - parameter schema/default compatibility checks
  - indicator-column validation
  - generated draft file creation
- Relaxed [strategy/base.py](strategy/base.py) so strategies may implement either `should_long`/`should_short` or override `decide`.
- Enforced validation before discovery in [strategies/loader.py](strategies/loader.py), including unregistering stale registry entries when a previously valid file becomes invalid.
- Added dashboard `Create / Import Strategy Draft` workflow in [dashboard/streamlit_app.py](dashboard/streamlit_app.py):
  - create from template
  - paste code
  - upload `.py`
  - validate draft
  - save valid draft under `strategies/generated_YYYYMMDD_HHMMSS.py`
  - explicit `Refresh Strategy Registry`
- Updated current plugin strategies, template docs, and LLM generation prompts to the new contract.
- Preserved lifecycle safety:
  - generated/imported drafts remain backtest-only
  - reviewed plugin artifacts remain hash-pinned for paper/live
  - strategy pack `.zip` support remains future scope.

### Latest Completed — Sprint 44

Sprint 44 is tracked as GitHub issue `#46` and was implemented on 2026-04-23.

Goal: make the app deployable on Jetson Nano as a durable research/paper-trading appliance with health checks, systemd service assets, log retention, backup/restore, and dashboard readiness visibility.

Implemented:
- Added [deployment/jetson_ops.py](deployment/jetson_ops.py):
  - `health`
  - `backup`
  - `restore` with dry-run default and explicit `--apply`
  - `repin-artifact` for reviewed plugin hash acknowledgment after intentional review
- Added [deployment/crypto-trader.logrotate](deployment/crypto-trader.logrotate).
- Updated [deployment/crypto-trader.service](deployment/crypto-trader.service) with unbuffered output and cleaner SIGINT shutdown.
- Updated [deployment/install.sh](deployment/install.sh) to install logrotate, initialize DB tables, and print deployment health.
- Extended [database/persistence.py](database/persistence.py) with restore planning/apply and inactive artifact warnings.
- Extended [strategy/artifacts.py](strategy/artifacts.py) with explicit reviewed-artifact repin support.
- Added dashboard `Jetson Deployment Readiness` expander in [dashboard/streamlit_app.py](dashboard/streamlit_app.py).
- Added tests in [tests/test_deployment_ops.py](tests/test_deployment_ops.py), [tests/test_persistence_restore.py](tests/test_persistence_restore.py), and artifact repin coverage.

Operational repair:
- Sprint 43 changed reviewed plugin files to add contract methods, which invalidated old artifact hashes.
- Ran `python -m deployment.jetson_ops repin-artifact 2 --apply`.
- The command created a pre-repin backup and moved active paper target from stale artifact `#2` to matching artifact `#8`, still `rsi_mean_reversion_v1`.

### Latest Completed — Sprint 45

Sprint 45 is tracked as GitHub issue `#47` and was implemented on 2026-04-23.

Goal: polish strategy authoring so traders can revise existing generated drafts inside the dashboard, validate them, and save valid revisions without restarting Streamlit.

Implemented:
- Added draft editing helpers in [strategy/plugin_sdk.py](strategy/plugin_sdk.py):
  - `list_generated_draft_files()`
  - `read_strategy_source_file()`
  - `suggest_next_strategy_name()`
- Extended `Create / Import Strategy Draft` in [dashboard/streamlit_app.py](dashboard/streamlit_app.py):
  - new `Edit Existing Draft` source mode
  - existing `generated_*.py` selection
  - validation feedback remains visible beside the editor
  - duplicate/invalid drafts show a suggested next strategy name
  - saving valid revisions creates a new generated draft and refreshes the registry
- Added regression coverage in [tests/test_strategy_plugin_sdk.py](tests/test_strategy_plugin_sdk.py).

Verification:
- Focused headed check passed for `Create / Import Strategy Draft` → `Edit Existing Draft`.
- `pytest tests/test_strategy_plugin_sdk.py tests/test_strategy_loader.py tests/test_strategy_base.py -q` → **53 passed**
- `python -m py_compile strategy/plugin_sdk.py dashboard/streamlit_app.py` → clean
- `pytest tests/ -q` → **688 passed, 4 warnings**
- `python run_ui_agent.py --ui-only --url http://localhost:8785` → **64/64 PASS**

### Latest Operational Slice — Sprint 42 Follow-Through (2026-04-23)

- **What changed**
  - Verified the active paper target remains reviewed artifact `#8` (`rsi_mean_reversion_v1@1.0.0`).
  - Confirmed the previous paper runtime had stopped: last paper snapshot before intervention was `2026-04-23 10:27:00 UTC`, and artifact `#8` still had `0` tagged BUY trades and `0` tagged SELL trades.
  - Re-synced maintained-universe freshness with `maintain_symbol_freshness()` so `BTCUSDT`, `ETHUSDT`, and `BNBUSDT` returned to current-minute coverage.
  - Restarted `run_live.py` safely in the background and verified paper snapshots resumed for artifact `#8`.
  - Detected an operational hazard: `python run_live.py --help` was **not** a harmless help path and booted a second runtime worker because `run_live.py` ignored CLI args.
  - Confirmed the accidental `--help` worker by duplicate paper snapshot writes at `2026-04-23 10:28:00 UTC`, then terminated only that mistaken duplicate and left the correct plain `run_live.py` worker alive.
  - Fixed the help-path bug in code by adding a real `argparse` entrypoint to [run_live.py](run_live.py), so CLI help exits before env validation or runtime boot.
  - Added regression coverage in [tests/test_run_live.py](tests/test_run_live.py) to prove `main(["--help"])` exits with code `0` and never calls `validate_env()` or `asyncio.run(...)`.
  - Quantified artifact `#8` opportunity scarcity across recent history instead of only waiting on live paper mode:
    - scanned the last `30d` of `1m` candles for `BTCUSDT`, `ETHUSDT`, `BNBUSDT`, plus other ready symbols `AAVEUSDT` and `LINKUSDT`
    - measured each `rsi_mean_reversion_v1` entry component and full 5-of-5 entry alignment
- **What was verified**
  - `python run_ui_agent.py --data-only` → **0 FAIL, 0 PARTIAL, 1 SKIP** after freshness repair.
  - `pytest tests/test_run_live.py -q` → **7 passed**
  - `pytest tests/ -q` → **690 passed, 4 warnings**
  - `python run_live.py --help` now prints help text and exits safely with no duplicate worker (`before=1 after=1`).
  - Active paper worker now writes fresh snapshots again:
    - resumed at `2026-04-23 10:27:05 UTC`
    - single-writer cadence restored by `2026-04-23 10:29:00 UTC`
    - still advancing cleanly at `2026-04-23 10:43:00 UTC`
  - Artifact `#8` still has no tagged trades:
    - `0` BUY
    - `0` SELL
  - Current paper worker remains healthy and advancing:
    - latest paper snapshot observed at `2026-04-23 10:51:00 UTC`
  - Current watched-symbol state supports the "entry scarcity" explanation:
    - `BTCUSDT`: RSI ~`50`, ADX ~`27.5`, no Bollinger-band breach, no MACD cross, no volume confirmation
    - `ETHUSDT`: RSI ~`53.8`, ADX ~`16.6`, no Bollinger-band breach, no MACD cross, no volume confirmation
    - `BNBUSDT`: RSI ~`42.8`, ADX ~`33.5`, no Bollinger-band breach, no MACD cross, no volume confirmation
  - Historical opportunity scan confirms this is not just a short observation-window problem:
    - across the last `30d` on all five ready symbols (`AAVEUSDT`, `BNBUSDT`, `BTCUSDT`, `ETHUSDT`, `LINKUSDT`), artifact `#8` produced:
      - `0` long candles with all 5 entry conditions aligned
      - `0` short candles with all 5 entry conditions aligned
    - repeated near-miss pattern: many candles met all long or short filters **except** the fresh MACD-cross requirement
      - `ETHUSDT`: `90` long near-misses / `18` short near-misses
      - `BNBUSDT`: `81` long / `13` short
      - `BTCUSDT`: `74` long / `7` short
      - `AAVEUSDT`: `57` long / `23` short
      - `LINKUSDT`: `30` long / `4` short
- **What remains next**
  - Keep the restarted plain `run_live.py` paper worker alive long enough to capture the first real artifact-tagged BUY and then SELL trades for artifact `#8`.
  - The next corrective code sprint should now target entry scarcity / market fit, not runner CLI safety or paper-evidence scoring:
    - re-examine the MACD-cross requirement inside the current RSI/Bollinger/volume setup
    - test whether the watchlist should include symbols with better range-reversion behavior
    - compare signal frequency before and after any threshold change so paper mode is not left waiting indefinitely for a first BUY

### Latest Slice (2026-04-23 — Sprint 43)

- **What changed**
  - Implemented the Strategy Plugin SDK and draft import workflow.
  - Added [strategy/plugin_sdk.py](strategy/plugin_sdk.py) for strategy contract validation, template generation, and generated draft creation.
  - Updated [strategy/base.py](strategy/base.py) so strategy authors may either implement `should_long`/`should_short` or override `decide`.
  - Updated [strategies/loader.py](strategies/loader.py) to validate plugin files before discovery and unregister stale strategies when a file becomes invalid.
  - Added a dashboard `Create / Import Strategy Draft` expander in [dashboard/streamlit_app.py](dashboard/streamlit_app.py) with template, paste, upload, validate, save, and registry refresh actions.
  - Updated existing plugin strategy files, [strategies/_strategy_template.py](strategies/_strategy_template.py), [strategies/README.md](strategies/README.md), [llm/generator.py](llm/generator.py), and [llm/prompts.py](llm/prompts.py) to the new contract.
  - Added validation coverage in [tests/test_strategy_plugin_sdk.py](tests/test_strategy_plugin_sdk.py) plus loader/base/artifact/generator fixture updates.
  - Added a structured learning entry to [knowledge/iteration_learnings.md](knowledge/iteration_learnings.md).
- **What was verified**
  - `pytest tests/test_strategy_base.py tests/test_strategy_loader.py tests/test_strategy_plugin_sdk.py tests/test_strategy_artifacts.py tests/test_llm_generator.py -q` → **73 passed**
  - `python -m py_compile strategy/plugin_sdk.py strategy/base.py strategies/loader.py dashboard/streamlit_app.py llm/generator.py llm/prompts.py strategies/_strategy_template.py strategies/ema200_filtered_momentum.py strategies/example_rsi_mean_reversion.py strategies/generated_20260422_120800.py strategies/mtf_confirmation_strategy.py` → clean
  - `pytest tests/ -q` → **673 passed, 4 warnings**
- **What remains next**
  - Keep Sprint 42 operational follow-through active until paper target artifact `#8` (`rsi_mean_reversion_v1`) produces real tagged BUY/SELL evidence.
  - Exercise the new dashboard draft workflow manually in a headed Streamlit session before claiming it as operator-polished.
  - Future sprint candidate: strategy pack `.zip` import/export plus editable invalid-draft recovery.

### Latest Slice (2026-04-22)

- **What changed**
  - Resolved the remaining Sprint 42 trader-journey false partials.
  - Updated [tools/ui_agent/trader_journey.py](tools/ui_agent/trader_journey.py) so terminal-state detection reads the actual `Last Backtest Attempt` block instead of scanning the whole page body.
    - This prevents one strategy's stale `Run failed:` banner from being misattributed to a different strategy later in the same operator journey.
  - Updated [strategy/runtime.py](strategy/runtime.py), [backtester/service.py](backtester/service.py), and cached dashboard loaders in [dashboard/streamlit_app.py](dashboard/streamlit_app.py) so dashboard backtests refresh the plugin strategy registry from disk before execution and catalog rendering.
    - This fixed the long-lived Streamlit-process case where the generated draft still used the old `'bb_upper'` code path after the file had already been corrected on disk.
  - Kept the generated draft plugin fix in:
    - [strategies/generated_20260422_120800.py](strategies/generated_20260422_120800.py)
    - Uses `bb_lo` / `bb_hi` and `macd` / `macd_s` cross logic instead of stale nonexistent indicator keys.
  - Added regression coverage in:
    - [tests/test_backtester_service.py](tests/test_backtester_service.py)
    - [tests/test_ui_agent_smoke.py](tests/test_ui_agent_smoke.py)
  - Restarted only the Streamlit dashboard process on port `8785` so the updated modules were loaded cleanly.
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
  - Implemented **Sprint 42 maintained-universe freshness maintenance**.
  - Added [market_data/history.py](market_data/history.py) helper:
    - `maintain_symbol_freshness()` — audits configured symbols, syncs only stale ones, and reports per-symbol repair status
  - Extended [run_live.py](run_live.py) with:
    - startup maintained-universe sync
    - periodic `freshness_guard_loop()` so maintained symbols can self-repair without manual `sync_recent()` operator intervention
    - concise log summary whenever stale symbols are actually refreshed
  - Added tests in:
    - [tests/test_market_data_services.py](tests/test_market_data_services.py)
    - [tests/test_run_live.py](tests/test_run_live.py)
  - Implemented **ASCII-safe runtime logging for Windows console capture**.
  - Updated:
    - [run_live.py](run_live.py)
    - [llm/self_learner.py](llm/self_learner.py)
    - [llm/client.py](llm/client.py)
    - [collectors/live_streamer.py](collectors/live_streamer.py)
  - Replaced non-ASCII runtime log strings and placeholders so stderr/stdout capture stays readable under default Windows console encoding.
  - Added one default-environment generated draft plugin:
    - [strategies/generated_20260422_120800.py](strategies/generated_20260422_120800.py)
    - discovered as `generated_range_probe_v1`
    - registered as artifact `#4`
    - lifecycle status `draft`
  - Verified the trader journey now sees and exercises the draft-promotion guard instead of skipping it for lack of any generated draft.
- **What was verified**
  - `pytest tests/test_backtester_service.py tests/test_ui_agent_smoke.py -q` → **23 passed**
  - `python run_ui_agent.py --journey trader --ui-only --headed --url http://localhost:8785` → **29/31 PASS, 0 FAIL, 0 PARTIAL, 2 SKIP**
    - All 8 visible strategies now save backtest runs successfully
    - All 8 visible strategies now reach complete Inspect surfaces
    - Remaining skips are expected: no reviewed strategy currently has a passing saved backtest to unlock paper promotion in the default environment, and no live target is configured
  - `python run_ui_agent.py --ui-only --url http://localhost:8785` → **64/64 PASS**
  - `pytest tests/ -q` → **660 passed, 4 warnings**
  - `python run_ui_agent.py --data-only` → **0 FAIL, 0 PARTIAL, 1 SKIP**
    - Only remaining skip is expected: no active live artifact configured
  - `python -m py_compile database/persistence.py dashboard/streamlit_app.py dashboard/workbench.py strategy/paper_evaluation.py simulator/paper_trader.py run_live.py tests/test_persistence.py` → clean
  - `pytest tests/test_persistence.py tests/test_workbench_helpers.py tests/test_paper_evaluation.py tests/test_paper_trader.py tests/test_run_live.py -q` → **97 passed**
  - `python -m py_compile market_data/history.py run_live.py tests/test_market_data_services.py tests/test_run_live.py` → clean
  - `pytest tests/test_market_data_services.py tests/test_run_live.py -q` → **25 passed**
  - `pytest tests/test_llm_client.py tests/test_run_live.py -q` → **19 passed**
  - `pytest tests/ -q` → **657 passed, 4 warnings**
  - Maintained-universe sync executed successfully on 2026-04-22:
    - initial repair inserted `1295` fresh `1m` candles per symbol with no missing ranges
    - freshness-helper verification later repaired another `14` stale minutes per symbol back to current
  - `python run_ui_agent.py --data-only` → **0 FAIL, 0 PARTIAL, 1 SKIP**
    - Only remaining SKIP is expected: no active live artifact configured
  - Operational note:
    - `run_live.py` is now active again in paper mode as the normal parent/child Python pair
    - heartbeat lines and startup lines are now ASCII-clean in `.run_live_eval.err`
    - maintained-universe candles are advancing to the current minute while the runner is active
    - after a live observation window on 2026-04-22, artifact `#2` still has `0` tagged BUY trades and `0` tagged SELL trades in `trades`
    - deterministic paper-evidence status for artifact `#2` remains `waiting-for-first-close`
    - blocker classification is now exact: **no entries yet**, not merely "no closes yet"
  - `python run_ui_agent.py --journey trader --ui-only --url http://localhost:8785` → **0 FAIL, 4 PARTIAL, 2 SKIP**
    - `Draft promotion guard` now passes against `generated_range_probe_v1`
    - partials are persistent `run-failed` states, not silent no-ops
  - Sprint 42 issue `#44` remains the active tracking issue and already contains the phased pre-deploy plan comment:
    - [Issue #44 comment](https://github.com/karllouiehernandez/crypto-ai-trader/issues/44#issuecomment-4295460139)
- **What remains next**
  - **Phase 2 implementation is complete in code, and the trader-journey audit is now clean; the main remaining blocker is still real paper evidence, not dashboard trust surfaces.**
  - Keep the current paper-mode `run_live.py` process healthy long enough to collect the first real artifact-tagged BUY and then SELL trades for paper target `#8` (`rsi_mean_reversion_v1`).
  - If artifact `#8` still shows zero tagged BUY trades after a meaningful additional observation window, open the next corrective sprint around entry scarcity / market fit rather than paper-evidence scoring.
  - Use the new Persistence & Recovery panel to manually confirm the live operator environment before making stronger production-readiness claims.
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
5. Do not run multiple `pytest` invocations in parallel; `tests/conftest.py` uses one shared temp DB path and concurrent bootstrap can create a false `table candles already exists` failure
6. Update this file last with what changed, what was verified, and what remains next

Current shared baseline:
1. Last protection commit: `b207a44` — `Sprint 42 kickoff — isolate pytest DB and restore data gate`
2. `pytest tests/ -q` leaves the live DB intact
3. Maintained MVP universe is restored to 30-day local coverage
4. Active paper target should remain `rsi_mean_reversion_v1` artifact `#8` unless the user explicitly changes it
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
   - **No paper trades on the current paper artifact yet**. The existing ~1,500 pre-existing paper trades in the DB predate artifact tagging (`artifact_id=NULL`) and are correctly excluded from the paper→live evidence gate by design.
3. **Live trader gate** — establish the `paper_passed` → `live_approved` path with real paper evidence
   - **Status (2026-04-19, Claude Code)**: deterministic, non-LLM evidence gate now lives in [strategy/paper_evaluation.py](strategy/paper_evaluation.py). `evaluate_paper_evidence(artifact_id)` reads the actual `Trade` rows tagged with the artifact (run_mode='paper', side='SELL') and grades against `PaperEvidenceThresholds` (default: ≥20 trades, ≥3 days runtime, Sharpe ≥1.5, profit factor ≥1.5, max drawdown ≤20%).
   - [strategy/artifacts.py:308](strategy/artifacts.py#L308) `mark_artifact_paper_passed` now **requires** a passing evidence result by default; the LLM coordinator path in [simulator/coordinator.py:99](simulator/coordinator.py#L99) explicitly passes `force=True` so its own confidence gate stays authoritative.
   - Dashboard Strategies tab: new **"Evaluate for Paper Pass"** button below the four primary action buttons. Surfaces the metric snapshot + per-rule failure reasons when the gate fails, and promotes + unlocks "Approve for Live" when it passes.
   - Tests: 10 new cases in `tests/test_paper_evaluation.py` cover no-artifact, no-trades, low trade count, short runtime, high drawdown, passing evidence, force bypass, full promotion, and the legacy-untagged-trades exclusion (legacy `artifact_id=NULL` paper trades are correctly ignored as evidence).
   - Once the live paper runtime under Priority #1 produces real artifact-`#8` trades, this gate will determine eligibility for `approve_artifact_for_live` automatically.
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
   - **Heartbeat state**: paper target is now `rsi_mean_reversion_v1` artifact `#8`, balance/equity remain flat at `$100`, and no artifact-tagged SELL trades exist yet for the paper-evidence gate.
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
