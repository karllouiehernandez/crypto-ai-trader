# Iteration Learnings

What each implementation or validation iteration taught us.
Update this file after every meaningful development slice, especially when a test run, trader journey, or runtime check changes what we believe about product readiness.

---

## 2026-04-25 Jetson Thermal Control — Appliance deployment should include board cooling, not only app uptime
**What happened:** The Jetson Nano exposed a simple writable PWM fan interface at `/sys/devices/pwm-fan/target_pwm`, and a dedicated `crypto-trader-fan.service` was added to manage it automatically from temperature sensors.
**Why it happened:** A deployed Nano can run the trader and dashboard continuously, but uptime alone is not enough if the board can still heat-soak in a warm environment. Thermal protection needed to be treated as part of deployment hardening, not as a manual operator habit.
**Impact:** The Jetson is now closer to a real unattended appliance. The runtime, dashboard, and thermal fan control all survive reboots under `systemd`, and the board will spin the fan up only when needed instead of leaving it always-on.
**What we changed:** Added `deployment/jetson_fan_control.py` with hysteresis-based state transitions, added `deployment/crypto-trader-fan.service`, updated installer scripts and deployment docs, deployed the service in place over SSH/SFTP, and verified it selected `off` at the current `39.2C` control temperature with PWM `0`.
**What to try next:** Leave the Jetson running in the real location and monitor `journalctl -fu crypto-trader-fan` plus temperatures from `tegrastats` during warmer hours. If the environment is hotter than expected, tune the thresholds rather than rewriting the control model.
**Status:** RESOLVED

---

## 2026-04-25 Jetson Dashboard Service — Operator visibility needs its own supervisor, not only a background shell
**What happened:** The Jetson dashboard was first launched with `nohup`, which was enough for quick validation but not a real deployment posture. A dedicated `crypto-trader-dashboard.service` was then added, installed, enabled, and validated on the device, and the dashboard is now reachable at `http://192.168.100.30:8501`.
**Why it happened:** A deployed appliance should not depend on a remembered SSH command or an orphaned shell process for its operator console. The trader runtime was already under `systemd`; the dashboard needed the same treatment so the liveness panel and workbench remained available after disconnects and reboots.
**Impact:** The Jetson now exposes both core surfaces durably: `crypto-trader.service` for the paper worker and `crypto-trader-dashboard.service` for Streamlit. That makes the new `Live Data Freshness` panel operationally useful instead of just a local feature.
**What we changed:** Added `deployment/crypto-trader-dashboard.service`, updated all Jetson installer paths to install and enable it, documented dashboard operations and the `:8501` URL in `deployment/README.md`, deployed the updated files over SSH/SFTP, and validated that both services are active under `systemd`.
**What to try next:** Leave both services running and use the dashboard plus journald as the normal monitoring pair. The remaining product question is still strategy evidence: whether artifact `#8` ever produces the first real tagged BUY and SELL trades.
**Status:** RESOLVED

---

## 2026-04-25 Runtime Liveness Surface — Deployed trust improves when the dashboard shows heartbeat age, not only charts
**What happened:** A new `Live Data Freshness` panel was added to `Runtime Monitor`, and `run_live.py` now persists a worker heartbeat timestamp into `app_settings` on startup and every 30-second heartbeat.
**Why it happened:** On the Jetson deployment, logs and direct DB queries proved the worker was healthy, but the Streamlit dashboard still could not honestly answer the simple operator question: “is the runtime worker alive right now?” Snapshot timestamps and moving charts are useful, but they are indirect signals.
**Impact:** The workbench can now become a better operator console once this slice is deployed to Jetson. Traders will be able to see last candle timestamps per runtime symbol, candle age in minutes, last portfolio snapshot timestamp, last trade timestamp, and worker heartbeat age in one place.
**What we changed:** Persisted `runtime_worker_heartbeat_ts` in `run_live.py`, added pure freshness-formatting helpers in `dashboard/workbench.py`, extended `dashboard/streamlit_app.py` with the `Live Data Freshness` panel, and added regression coverage in `tests/test_run_live.py` and `tests/test_workbench_helpers.py`.
**What to try next:** Pull this commit onto the Jetson if you want the dashboard there to reflect the new liveness surface, then keep the device running and use the panel plus journald to observe whether artifact `#8` ever produces the first real tagged BUY and SELL trades.
**Status:** RESOLVED

---

## 2026-04-24 Jetson Python Reality — Deployment docs need a source-build fallback, not only an apt path
**What happened:** A real Jetson Nano install hit the first practical blocker: the device was on Ubuntu 20.04 arm64, but `apt` could not locate `python3.10` or `python3.10-venv`. The flash-drive installer therefore failed at virtual-environment creation.
**Why it happened:** The deployment flow assumed Python 3.10+ would be available from package repositories. On this Jetson image, that assumption was false, and the original Nano’s Ubuntu support path is already less standard than a regular x86 Ubuntu box.
**Impact:** The deployment path needed a real fallback, not more advice. Without it, the otherwise-correct bundle and service setup still could not get past interpreter setup on the actual device.
**What we changed:** Added `deployment/bootstrap_python310_install.sh` to compile Python `3.10.14` from source, rebuild the app venv, install requirements, wire the systemd service, and run health checks. Updated `deployment/README.md` to document this as the supported fallback when `apt` lacks Python 3.10.
**What to try next:** Run the fallback bootstrap directly on the Jetson from `~/crypto_ai_trader`, then continue with `.env` editing and `crypto-trader` service validation. The next useful learning should come from the first successful service start on the real device.
**Status:** RESOLVED

## 2026-04-24 Jetson Bootstrap Practicality — Deployability is not just systemd, it is how the first install actually happens
**What happened:** A flash-drive deployment path and a one-time Windows SSH/SFTP bootstrap were added for Jetson Nano. The repo can now produce a sanitized `crypto_ai_trader_bundle` for removable media, Jetson can install from that bundle without cloning from GitHub, and Windows can establish passwordless SSH/SFTP access using the standard OpenSSH server.
**Why it happened:** The deployment docs assumed network-first setup and manual remote-access preparation. That is fine for a comfortable Linux workflow, but it is not the most practical first-install path when the operator already has the repo on a Windows machine and a flash drive. The missing piece was an offline-friendly bootstrap path that preserves the same non-destructive guarantees as the main installer.
**Impact:** Jetson deployment is now much more realistic as a next step. The base app can be carried over by USB, installed locally on the device, and then managed remotely over SSH/SFTP without needing a second ad hoc setup sprint. This lowers the friction between “locally validated” and “actually running on the target appliance.”
**What we changed:** Added `prepare_jetson_flash_drive.bat`, `deployment/install_from_bundle.sh`, `setup_jetson_remote_access.bat`, `deployment/setup_remote_access.sh`, and updated `deployment/README.md`. Verified the Windows-side scripts locally and kept full Python regression green.
**What to try next:** Use these scripts on the actual Jetson Nano, then move immediately into multi-day long-run validation under `systemd`: service restart survival, backup/restore drills, candle freshness continuity, and paper-snapshot continuity.
**Status:** RESOLVED

---

## 2026-04-23 Strategy Pack Portability — Post-deploy flexibility improves when strategy exchange reuses the same draft gate
**What happened:** Sprint 47 added a portable strategy-pack workflow. The dashboard can now export a strategy as a `.zip` containing `manifest.json`, the source file, and optional `notes.md`, then import a pack back into the same generated-draft path used for pasted or uploaded strategy code.
**Why it happened:** The product goal is to deploy the base app once and evolve mostly through strategies. Single-file draft editing was already in place, but there was still no clean way to move strategies between machines or agents without manually copying files and rediscovering metadata. The missing piece was a portable bundle that still respected the existing SDK and lifecycle rules.
**Impact:** Strategy iteration is now more deployable. A Jetson box or another workstation can receive a strategy pack and bring it in as a backtest-only generated draft without relaxing any paper/live safety rules. The base application stays fixed while strategy work becomes more transferable.
**What we changed:** Added pack export/import helpers in `strategy/plugin_sdk.py`, exposed them in the dashboard `Create / Import Strategy Draft` expander, documented the pack format in `strategies/README.md`, and added regression coverage plus UI smoke verification.
**What to try next:** Use the next sprint for Jetson long-run validation rather than more authoring UX. The portability layer is now good enough to support post-deploy strategy exchange, so the remaining product risk is operational continuity and paper-evidence collection, not strategy file transport.
**Status:** RESOLVED

---

## 2026-04-23 Deployment Lock Phase 2 — A compatibility contract only works if the lifecycle enforces it visibly
**What happened:** Sprint 46 Phase 2 completed the strategy SDK lock by pushing it beyond draft validation into the actual operator workflow. The strategy lifecycle area now shows SDK version and compatibility, unsupported drafts/plugins render explicit blocked-state reasons, and `Review and Save` now rejects unsupported SDK versions before a reviewed plugin can be written to `strategies/`.
**Why it happened:** Phase 1 defined the SDK contract, but that alone still left a trust gap: a trader could see the SDK lock while authoring drafts, then lose that context during review/promotion and wonder why actions were disabled or why paper/live rejected a strategy later. The missing piece was lifecycle visibility plus enforcement at the reviewed-plugin boundary.
**Impact:** The deployed app is now closer to the intended steady state: the base software can stay fixed while strategy work continues inside a bounded compatibility envelope. Unsupported strategies fail early and visibly instead of drifting into reviewed artifacts or later runtime surprises.
**What we changed:** Added `strategy_sdk_compatibility(...)` and `SDK Mismatch` workflow states in `dashboard/workbench.py`, surfaced SDK metrics and blocked-action explanations in `dashboard/streamlit_app.py`, validated reviewed-plugin rewrites in `strategy/artifacts.py`, documented the contract in `strategies/README.md`, and added regression coverage plus UI smoke verification.
**What to try next:** Treat Sprint 46 as complete and keep Sprint 42 as the background ops thread. The next product-facing development sprint should improve strategy market fit or strategy-pack portability, not reopen the base-app compatibility contract unless the SDK version intentionally changes.
**Status:** RESOLVED

---

## 2026-04-21 Trader Journey Stabilization — Smoke is green but the trader journey is still the real blocker
**What happened:** Backtest Lab now defaults to the latest complete backtest day instead of the current intraday candle date. Smoke UI and DB checks are green, and backtest rows continue to persist during trader-journey runs.
**Why it happened:** The workbench and the trader harness were previously treating the latest fresh candle date as backtest-safe, which pushed operators into incomplete current-day windows. After fixing that, the remaining trust problem is the journey harness itself: it can still hang or lose track of terminal states while Streamlit rerenders.
**Impact:** Product confidence improved because normal smoke and data checks are stable, but the release contract is still incomplete. We still cannot claim a trustworthy trader-journey pass until the runner can finish consistently and report saved-run versus blocked-run outcomes honestly.
**What we changed:** Added a shared latest-complete-day helper in `dashboard/workbench.py`, wired Backtest Lab and ready-symbol health to use it, and started tightening `tools/ui_agent/trader_journey.py` toward exact selectbox matching and DB-backed saved-run detection.
**What to try next:** Finish stabilizing `tools/ui_agent/trader_journey.py` around terminal-state detection and Inspect follow-through, then rerun the full trader journey headed and record the next outcome here.
**Status:** OPEN

---

## 2026-04-21 Trader Journey Stabilization — The audit now completes; the next blocker is real paper evidence
**What happened:** The full headed trader journey now completes end-to-end on the live dashboard and writes a report instead of hanging. It backtested all 7 visible strategies on a recent BTCUSDT window, opened each saved run in Inspect, and verified paper-promotion readiness with `0 FAIL`, `0 PARTIAL`, and `1 SKIP` (no generated draft in the catalog). Smoke UI also reran headed at `64/64 PASS`, and the maintained-universe freshness gate returned to `0 FAIL / 0 PARTIAL / 1 SKIP` after a recent data sync.
**Why it happened:** The prior journey window was too large for an exhaustive operator audit and the harness was grading saved-run and Inspect surfaces before Streamlit finished rerendering. Moving the journey to a canonical recent 7-day window and adding explicit post-save / post-select waits aligned the automation with real UI timing.
**Impact:** The operator-trust contract is materially stronger. The workbench now has a credible automated proof for the research -> backtest -> Inspect -> paper-readiness flow. The remaining product gap is no longer UI audit completeness; it is the lack of real artifact-tagged paper evidence and, by extension, the lack of trustworthy live-readiness evidence.
**What we changed:** Updated `tools/ui_agent/trader_journey.py` to use a recent deterministic audit window, shorter per-run terminal timeouts, and stronger surface-state waits for saved-run summaries and Inspect equity/code rendering. Restarted Streamlit for headed validation and refreshed maintained-symbol recent history with `market_data.history.sync_recent()` so data-only checks reflected current local state.
**What to try next:** Keep `run_live.py` running under artifact `#2` until it produces real tagged SELL trades, then exercise the deterministic paper-evidence gate and the manual live-approval path. After that, decide whether the default environment should also include one generated draft so the draft-promotion guard stops being a permanent journey skip.
**Status:** RESOLVED

---

## 2026-04-21 Windows Bootstrap Installer — One-time setup should be repeatable without touching runtime state
**What happened:** A repo-root Windows batch installer was added and validated successfully against the current workspace. It created `.venv`, installed runtime and dev dependencies, left `.env` unchanged, initialized DB tables idempotently, and installed the Playwright Chromium browser.
**Why it happened:** The repo already had a Jetson/Linux `deployment/install.sh`, but no equivalent one-time bootstrap for Windows operators or future agents working on the same branch. Setup depended on ad hoc manual steps, which is exactly how stateful environments drift over time.
**Impact:** New Windows environments can now be bootstrapped consistently without overwriting credentials, resetting the DB, or disturbing active paper/live targets. That improves continuity and reduces the chance that future work starts from an inconsistent local setup.
**What we changed:** Added `install_once.bat` at the repo root and documented it in `deployment/README.md`. The script is explicitly non-destructive and points operators toward `run_all.ps1` after setup.
**What to try next:** If Jetson continuity remains the next focus, add a matching documented backup/recovery checklist and a restart-survival validation script so environment bootstrap and environment recovery are both first-class.
**Status:** RESOLVED

---

## 2026-04-22 Pre-deploy hardening plan — Packaging should follow recovery and evidence, not precede them
**What happened:** The remaining pre-deploy improvement work was turned into a phased Sprint 42 action slice instead of staying as an informal priority list.
**Why it happened:** The product is now strong enough on smoke, trader journey, and basic operator trust that the next gains come from software discipline: persistence, recovery, real paper evidence, data auto-repair, and Jetson-safe operating profiles.
**Impact:** Future work can now be sequenced without rediscovering priorities. The main remaining gap is no longer “what should we improve?” but “which pre-deploy hardening phase are we executing next?”
**What we changed:** Added a phased pre-deploy software hardening plan to Sprint 42 covering persistence/recovery, real paper evidence validation, data freshness auto-repair, generation/review quality, and Jetson deployment readiness.
**What to try next:** Start with Phase 1 persistence and restart-survival validation, then move directly into Phase 2 real paper-evidence capture on artifact `#2`.
**Status:** OPEN

---

## 2026-04-22 Paper Evidence Progress Surface — The gate is now visible before it is passable
**What happened:** Sprint 42 Phase 2 landed as a deterministic, operator-facing paper-evidence progress surface. The dashboard now shows trade-count progress, runtime-span progress, blocker reasons, and checklist rows for the selected reviewed paper artifact, while `run_live.py` heartbeats also include the same evidence stage in stdout.
**Why it happened:** The paper-evidence gate already existed logically, but traders and future agents still had to infer too much from raw trade rows or one-off evaluation actions. The missing piece was a shared summary that the paper trader, the dashboard, and the runner heartbeat could all expose consistently.
**Impact:** Trader trust improved because the paper-readiness gate is now inspectable even before there are enough real trades to pass it. The remaining blocker is operational rather than UI-related: artifact `#2` still needs real tagged SELL trades, and the latest 2026-04-22 data-only run is still honest about stale maintained-universe candles.
**What we changed:** Added `evaluate_paper_evidence_from_trades()` and `build_paper_evidence_summary()` in `strategy/paper_evaluation.py`, surfaced paper-evidence status in `simulator/paper_trader.py`, extended `run_live.py` heartbeats, added dashboard helpers in `dashboard/workbench.py`, and rendered a persistent `Paper Evidence Progress` section in `dashboard/streamlit_app.py`. Added regression coverage in `tests/test_paper_evaluation.py`, `tests/test_paper_trader.py`, `tests/test_run_live.py`, and `tests/test_workbench_helpers.py`.
**What to try next:** Refresh maintained-universe candles, keep `run_live.py` on paper target `#2`, and wait for real tagged SELL trades so the deterministic evidence summary can move from `waiting-for-first-close` to real gate evaluation.
**Status:** OPEN

---

## 2026-04-22 Maintained-Universe Sync — Data readiness can recover fast when the refresh path stays explicit
**What happened:** The maintained research universe (`BTCUSDT`, `ETHUSDT`, `BNBUSDT`) had aged out to a stale shared cutoff, which downgraded the operator data-only gate to `0 FAIL, 1 PARTIAL, 1 SKIP`. A targeted `sync_recent()` pass inserted `1295` fresh `1m` candles per symbol with no gaps, and the gate returned to `0 FAIL, 0 PARTIAL, 1 SKIP`.
**Why it happened:** The local data path was healthy, but freshness had not been maintained automatically through the current operator session. Because all three maintained symbols stopped at the same timestamp, the issue was not symbol selection or audit logic; it was simply a stale local tail.
**Impact:** This confirms the workbench can recover its research-grade baseline quickly without destructive rebuilds, but it also shows that long-lived production claims still depend on keeping the maintained-universe refresh path active over time rather than only repairing it after the fact.
**What we changed:** Ran `market_data.history.sync_recent()` for each maintained symbol, verified full coverage with no missing ranges, reran `python run_ui_agent.py --data-only`, and updated the handoff/resume files so the clean operator baseline is documented.
**What to try next:** Keep monitoring whether freshness stays green passively while the current runtime runs. If it ages out again without operator action, the next improvement should be an explicit automated freshness-maintenance path instead of more manual resyncs.
**Status:** OPEN

---

## 2026-04-22 Maintained-Universe Freshness Guard — Recovery should become continuous, not manual
**What happened:** A shared freshness-maintenance helper and runner loop were added so the maintained universe can self-repair when candles age out. The helper detected all three maintained symbols stale by 14 minutes, repaired them back to current, and the data-only gate returned to `0 FAIL, 0 PARTIAL, 1 SKIP`.
**Why it happened:** The earlier learning was correct: manual `sync_recent()` works, but it is not a production discipline. The right fix is a reusable helper plus a long-lived runner path that calls it automatically on startup and on a fixed cadence.
**Impact:** Product continuity improved because data freshness is no longer only an operator memory problem. The remaining operational caveat is explicit: the guard works in code today, but it only runs continuously when `run_live.py` is actually active.
**What we changed:** Added `maintain_symbol_freshness()` to `market_data/history.py`, wired `run_live.py` to run it once at startup and then every 5 minutes, added unit coverage in `tests/test_market_data_services.py` and `tests/test_run_live.py`, and reran the full suite to `656 passed`.
**What to try next:** Start or restart `run_live.py` so the new guard runs continuously, then observe whether candle freshness stays green over time without any manual sync intervention.
**Status:** OPEN

---

## 2026-04-22 Runtime Console Hardening — Production logs must stay readable on Windows defaults
**What happened:** The live runner was healthy, but redirected stderr still showed mojibake because several runtime log strings used non-ASCII characters such as em dashes, arrows, checkmarks, and placeholder glyphs. After replacing those with ASCII-safe text and restarting the runner, the startup and heartbeat logs became clean while behavior stayed unchanged.
**Why it happened:** Earlier Windows-safe work normalized the UI-agent CLI, but runtime logging still had legacy Unicode strings scattered across `run_live.py`, `llm/self_learner.py`, `llm/client.py`, and `collectors/live_streamer.py`. Redirected console output on the default Windows encoding path exposed that gap immediately.
**Impact:** Operator trust improved because the live process now looks healthy instead of corrupted when watched from PowerShell or redirected files. This matters for production readiness: if heartbeat logs are unreadable, a quiet but healthy bot can still look broken.
**What we changed:** Replaced non-ASCII runtime log strings and placeholder values with ASCII-safe equivalents, added a regression test for ASCII placeholders in `tests/test_run_live.py`, reran targeted tests plus the full suite to `657 passed`, and restarted `run_live.py` so the live process actually uses the cleaned output.
**What to try next:** Keep the runner alive long enough to confirm the maintained-universe freshness guard keeps candles current over time, and avoid running multiple `pytest` commands in parallel because the shared temp-DB bootstrap can create a false isolation failure.
**Status:** OPEN

---

## 2026-04-22 Paper Evidence Observation — The current blocker is no entries, not weak exits
**What happened:** The paper runner for `rsi_mean_reversion_v1` artifact `#2` was kept alive through multiple heartbeat intervals while candles advanced normally across `BTCUSDT`, `ETHUSDT`, and `BNBUSDT`. The artifact still produced `0` tagged trades total: no BUY entries and therefore no SELL closes. The deterministic evidence evaluator remained at `waiting-for-first-close`.
**Why it happened:** The strategy is healthy from an operator/runtime perspective, but its entry conditions are currently too sparse to trigger in the observed market window. This is not yet a Sharpe, profit-factor, drawdown, or "too few closes" problem because the system has not reached the first entry.
**Impact:** The next decision point is much clearer. There is no basis yet for paper promotion or live-readiness evaluation because the gate is blocked before trade sampling starts. Any corrective sprint should focus first on entry opportunity frequency or observation time, not on exit metrics.
**What we changed:** Kept `run_live.py` active in paper mode, queried the live DB directly for artifact-tagged trades, evaluated `evaluate_paper_evidence(2)`, and recorded the exact blocker as `no entries yet`.
**What to try next:** Let the runner continue longer to catch the first real entry, and if the artifact still shows zero tagged BUY trades after a meaningful additional window, open the next corrective sprint around entry scarcity rather than paper-evidence scoring.
**Status:** OPEN

---

## 2026-04-22 Generated Draft Presence — The draft lifecycle must be visible in the default environment
**What happened:** A generated draft strategy file was added to the default environment and discovered successfully as `generated_range_probe_v1`, registered as draft artifact `#4`. The trader journey now exercises the draft-promotion guard against a real generated artifact instead of skipping that path.
**Why it happened:** The previous environment had no generated draft present, so the trader journey could not verify whether generated drafts were correctly blocked from paper/live promotion. That left a blind spot in the research-to-review lifecycle.
**Impact:** Product trust improved because one more workflow is now exercised in the real workspace: generated drafts are visible, backtestable, and explicitly blocked from promotion until reviewed. The remaining trader-journey gaps are now specific run-failed backtests, not missing lifecycle coverage.
**What we changed:** Added `strategies/generated_20260422_120800.py`, verified discovery via `list_available_strategies()`, confirmed artifact `#4` is `draft`, and reran the trader journey to verify `Draft promotion guard` now passes instead of skipping.
**What to try next:** Investigate the remaining trader-journey partials where reviewed strategies or the new draft end in persistent `run-failed` states, because the lifecycle coverage gap is closed but some strategy operability gaps still remain.
**Status:** OPEN

---

## 2026-04-22 Trader Journey False Partials — A stale attempt banner can corrupt operator audits if the harness reads the whole page
**What happened:** The trader journey was still reporting four plugin strategies as `run-failed`, even though direct `run_and_persist_backtest()` calls and manual browser reproduction showed those same strategies could save runs successfully. The generated draft also still failed inside the long-lived Streamlit process with the old `'bb_upper'` error, despite the file already being fixed on disk.
**Why it happened:** Two separate issues overlapped. First, the journey harness was scanning the entire page body for `Run failed:` and accidentally reusing the previous strategy's `Last Backtest Attempt` banner. Second, the dashboard backtest path depended on the in-memory plugin registry, which had not been refreshed from disk before backtests in the long-lived Streamlit process.
**Impact:** Trader-facing audits looked worse than the actual product state, which could have driven the next sprint in the wrong direction. It also proved that draft/plugin edits must be reloaded explicitly for backtests if the dashboard stays up for a long time.
**What we changed:** Scoped trader-journey terminal-state detection to the actual `Last Backtest Attempt` block, refreshed the strategy catalog from disk before persisted backtests, updated dashboard strategy catalog/error loaders to use the refreshed registry, kept the generated draft on the corrected `bb_lo`/`bb_hi` and `macd`/`macd_s` logic, and restarted only the Streamlit dashboard so the updated modules were loaded cleanly.
**What to try next:** Keep `run_live.py` running for real artifact-`#2` trades, and once real tagged BUY/SELL rows exist, use the deterministic evidence gate to decide whether the next corrective sprint is about entry scarcity or paper-performance quality.
**Status:** RESOLVED

---

## 2026-04-23 Strategy Plugin SDK — Flexibility needs a contract before hot reload
**What happened:** Sprint 43 added a strategy plugin SDK so traders can create, paste, upload, validate, save, and hot-reload strategy drafts from the dashboard without changing application code.
**Why it happened:** The app needed post-deploy strategy flexibility, but unrestricted Python files entering the registry would make backtests and paper/live promotion unsafe. The missing discipline was a strict draft contract that catches bad metadata, duplicate `name + version`, unknown indicator columns, and missing behavior methods before discovery.
**Impact:** Strategy iteration can now happen inside the deployed workbench while keeping lifecycle safety intact: drafts are backtest-only, reviewed plugins remain hash-pinned artifacts, and paper/live still fail closed on invalid or mismatched reviewed code.
**What we changed:** Added `strategy/plugin_sdk.py`, relaxed `StrategyBase` to support either `should_long`/`should_short` or `decide`, enforced validation in `strategies/loader.py`, added a dashboard `Create / Import Strategy Draft` workflow with `Refresh Strategy Registry`, updated plugin templates/prompts, and added regression tests for the SDK and loader validation.
**What to try next:** Extend this into strategy pack import/export once the single-file workflow has been exercised by real strategy authors, and consider adding a dashboard editor for revising existing invalid drafts instead of only validating pasted/uploaded code.
**Status:** RESOLVED

---

## 2026-04-23 Jetson Deployment Readiness — Deployment needs operator commands, not just instructions
**What happened:** Sprint 44 turned Jetson deployment readiness into executable checks and commands. The repo now has a deployment health CLI, backup/restore CLI, explicit artifact repin command, logrotate template, improved systemd unit, and a dashboard readiness panel.
**Why it happened:** A long-running Jetson deployment must be restart-safe and observable for weeks. Documentation alone is not enough; the operator needs commands that verify DB/artifact/data freshness, create backups, and make risky actions explicit.
**Impact:** Production readiness improved because deployment health is now testable and visible. The Sprint 43 plugin-contract update also exposed a real hash-pinning issue; the new repin command resolved it safely by moving the paper target from stale artifact `#2` to current matching artifact `#8`.
**What we changed:** Added `deployment/jetson_ops.py`, `deployment/crypto-trader.logrotate`, restore planning/apply support in `database/persistence.py`, reviewed-artifact repin support in `strategy/artifacts.py`, dashboard Jetson readiness UI, deployment docs, and regression tests.
**What to try next:** On the physical Jetson, run `bash deployment/install.sh`, then `python -m deployment.jetson_ops health --strict`, keep `run_live.py` active through systemd, and let paper target `#8` collect real BUY/SELL evidence over weeks.
**Status:** RESOLVED

---

## 2026-04-23 Strategy Draft Editing — Draft creation is not enough without revision recovery
**What happened:** Sprint 45 added an existing-draft editor path to the dashboard strategy authoring workflow. Traders can now select an existing `generated_*.py` draft, revise the source, validate it inline, and save a valid revision as a new generated draft.
**Why it happened:** Sprint 43 made strategy creation possible, but iteration still required leaving the workbench when a generated/imported draft needed revision. Real strategy work is rarely one-shot; invalid or duplicate drafts need a visible recovery path.
**Impact:** Strategy authoring is more practical for deployed operation. Invalid drafts remain blocked from discovery/paper/live, but the trader now gets validation feedback plus a next-name suggestion instead of a dead end.
**What we changed:** Added draft listing/reading/name-suggestion helpers in `strategy/plugin_sdk.py`, extended the dashboard `Create / Import Strategy Draft` expander with `Edit Existing Draft`, and added SDK tests plus focused headed validation.
**What to try next:** Add full strategy-pack import/export only after the single-file draft editor has been used in real strategy-authoring sessions.
**Status:** RESOLVED

---

## 2026-04-23 Paper Runtime Refresh — Evidence collection depends on distinguishing dead runtime from scarce signals
**What happened:** The active paper target (`rsi_mean_reversion_v1`, artifact `#8`) had stopped producing fresh snapshots, so the paper-evidence follow-through was refreshed. Maintained-universe candles were re-synced, `run_live.py` was relaunched, fresh paper snapshots resumed, and artifact `#8` still showed `0` tagged BUY trades and `0` tagged SELL trades.
**Why it happened:** The remaining blocker after Sprint 45 was no longer product UX or test coverage. It was operational proof: the paper runner must stay alive long enough to produce real tagged trades. During verification, an accidental `python run_live.py --help` invocation exposed a separate operator-safety hazard because the script ignored CLI args and booted a second runtime worker.
**Impact:** The current blocker is now much clearer. The paper-evidence gate is blocked by no entries yet, not by bad paper-performance metrics. The CLI hazard is also resolved: `run_live.py --help` no longer creates duplicate workers.
**What we changed:** Queried the live DB for active artifact state and snapshot cadence, re-synced maintained symbol freshness, restarted the plain `run_live.py` worker, detected the accidental duplicate by same-minute duplicate `portfolio_snapshots` rows, terminated only the mistaken `--help` worker, checked the latest BTC/ETH/BNB indicator state to confirm no Bollinger breach, no fresh MACD cross, and no volume confirmation were present, then added a real `argparse` entrypoint plus regression tests so `python run_live.py --help` exits before booting.
**What to try next:** Keep the single correct paper worker alive for a longer observation window. If artifact `#8` still produces zero tagged BUY trades, open the next corrective sprint around entry scarcity / market fit rather than more runner plumbing.
**Status:** OPEN

---

## 2026-04-23 Entry Scarcity Quantified — “No trades yet” is now a measured market-fit problem
**What happened:** The healthy paper runner for artifact `#8` continued writing snapshots with zero trades, so the strategy was measured against recent historical opportunity frequency instead of waiting blindly. Across the last `30d` on every locally ready symbol (`AAVEUSDT`, `BNBUSDT`, `BTCUSDT`, `ETHUSDT`, `LINKUSDT`), `rsi_mean_reversion_v1` produced zero candles where all five long filters aligned and zero where all five short filters aligned.
**Why it happened:** Live observation alone could still be dismissed as bad luck or a short sample. The missing evidence was whether the current strategy/watchlist combination produces any realistic first-entry opportunities in the maintained environment at all.
**Impact:** The next sprint target is now unambiguous. This is not primarily a paper-evidence scoring problem and no longer mainly a runtime-uptime problem. It is an entry-scarcity / market-fit problem. The strongest repeated near-miss pattern is “all filters align except fresh MACD cross,” which makes that requirement the first thing to re-evaluate.
**What we changed:** Computed 30-day per-symbol counts for each entry component (`RSI`, `Bollinger`, `MACD cross`, trend filter, volume filter) plus full 5-of-5 alignment and 4-of-5 near misses. The result was consistent across all ready symbols: many 4-of-5 bars existed, but only when MACD cross was the missing filter.
**What to try next:** Open the next corrective sprint around market fit. Compare signal frequency and backtest behavior after changing the MACD-cross requirement, relaxing confirmation timing, or selecting a watchlist with stronger range-reversion behavior. Keep the current paper worker running, but do not expect paper evidence to advance until first-entry opportunity rate improves.
**Status:** OPEN

---

## 2026-04-23 Deployment Lock Phase 1 — A deployed strategy workbench needs an explicit compatibility contract
**What happened:** Sprint 46 started with a deployment-focused base-app lock. The app now declares an explicit strategy SDK version, uses that contract during draft validation, and shows the supported SDK version directly in the dashboard strategy-authoring flow.
**Why it happened:** The product direction is to deploy the base application once and then spend time creating or refining strategies. That only works if the deployed app says clearly which strategy contract it supports; otherwise every new strategy experiment risks turning into another core-app compatibility patch.
**Impact:** Post-deploy strategy work is now more bounded. New drafts can target the current supported SDK explicitly, unsupported SDK versions are rejected before discovery, and the workbench shows the author exactly what the deployed base supports.
**What we changed:** Added `sdk_version` to `StrategyBase.meta()`, defined `STRATEGY_SDK_VERSION = "1"` and `SUPPORTED_STRATEGY_SDK_VERSIONS` in `strategy/plugin_sdk.py`, added `strategy_sdk_support()`, rejected unsupported SDK versions during validation, updated both generated and manual templates to include `sdk_version = "1"`, and surfaced the deployment SDK lock in the dashboard `Create / Import Strategy Draft` expander.
**What to try next:** Extend the same compatibility lock into reviewed-plugin acceptance, strategy catalog visibility, and docs so the deployment contract is visible not only while drafting but across the full strategy lifecycle.
**Status:** OPEN

---

## 2026-04-25 Professional Universe — Research tracking must be separated from runtime streaming
**What happened:** Sprint 49 added a curated Professional 20 Binance spot USDT research universe and a local Binance Data Vision mirror cache. The dashboard can now queue history for all 20 symbols while keeping the runtime watchlist capped to a smaller Jetson-safe subset.
**Why it happened:** Raw Binance volume ranking includes stablecoin pairs and temporary hype listings, and adding every candidate directly to paper/live streaming would create unnecessary Jetson/API load. The app needs a durable research tracker for strategy creation without turning every tracked symbol into an active runtime symbol.
**Impact:** The product is better aligned with post-deploy strategy work: operators can maintain a long-term research universe, backfill/cache history for strategy development, and only promote selected symbols into the live paper runtime.
**What we changed:** Added `market_data/professional_universe.py`, archive ZIP mirror caching in `market_data/history.py`, the `warm-cache` historical-loader command, a sidebar Professional 20 panel, and deployment docs/env templates for `BINANCE_HISTORY_CACHE_DIR`.
**What to try next:** Deploy this slice to Jetson, set the cache path to USB/local storage if needed, warm the Professional 20 cache, and then use strategy generation/backtesting across this universe while keeping paper runtime limited to 3-5 symbols.
**Status:** RESOLVED
