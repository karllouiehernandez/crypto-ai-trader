# Iteration Learnings

What each implementation or validation iteration taught us.
Update this file after every meaningful development slice, especially when a test run, trader journey, or runtime check changes what we believe about product readiness.

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
