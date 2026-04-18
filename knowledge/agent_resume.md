# Agent Resume Pack

Use this file for agent switching. It is the compact handoff intended for Codex, Claude Code, and GitHub Copilot Pro.

Read order for a new agent:
1. `HANDOFF.md`
2. `knowledge/agent_resume.md`
3. Only then open the specific source files needed for the current sprint
4. Read `knowledge/sprint_log.md` only when historical context is actually needed

## Current Sprint

- Sprint: `Sprint 25 — Weekly Market Focus Selector`
- Status: ready to start
- Baseline: `pytest tests/ -q` must show `429 passed`
- GitHub tracking issue: `#26`

## Why This Exists

`knowledge/sprint_log.md` is the long-form archive. It should not be the default first read during agent switching because it consumes a large amount of context for little immediate value.

## Current State

- Workbench tabs are in place: `Strategies`, `Backtest Lab`, `Runtime Monitor`
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
- Runtime monitoring is already strategy-aware and mode-aware

## Immediate Goal

Add a weekly market-focus study that:
- discover a research-only top-liquid Binance `USDT` universe wider than runtime `SYMBOLS`
- ranks candidates using recent backtest results for the active strategy and active params
- persist weekly study runs and shortlisted candidates
- let the dashboard prefill `Backtest Lab` with the recommended token

## Files Most Likely Needed First

- `config.py`
- `collectors/historical_loader.py`
- `backtester/service.py`
- `database/models.py`
- `dashboard/streamlit_app.py`
- `dashboard/workbench.py`
- `strategy/runtime.py`
- `HANDOFF.md`

## Constraints

- `knowledge/experiment_log.md` may remain dirty because a background runtime process writes to it
- Do not edit, stage, or revert `knowledge/experiment_log.md` unless you intentionally stop that process
- Keep the Jesse-like workflow intact
- Prefer pure helpers in `dashboard/workbench.py` over embedding ranking/formatting logic directly in Streamlit

## Sprint 25 Working Target

Sprint 24 closed. The next sprint should:

- add a research-only symbol universe that is separate from runtime `SYMBOLS`
- rank a top-liquid Binance spot `USDT` shortlist using the active strategy
- persist weekly study runs and ranked results
- surface the latest recommendation in the workbench and allow one-click prefill into `Backtest Lab`
- keep paper/live symbol behavior unchanged

## Last Verified State

- Tests: `429 passed, 1 warning`
- Last sprint closed: `Sprint 24`
- Latest closed sprint artifacts are in the repo; use `git log --oneline -n 3` if you need the exact commit IDs without reopening the full sprint archive

## Token-Saving Rule

If you only need to continue the active sprint, do not read the full sprint log first. Use `HANDOFF.md` + this file + the relevant code files.
