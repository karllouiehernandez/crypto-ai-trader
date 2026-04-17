# Agent Resume Pack

Use this file for agent switching. It is the compact handoff intended for Codex, Claude Code, and GitHub Copilot Pro.

Read order for a new agent:
1. `HANDOFF.md`
2. `knowledge/agent_resume.md`
3. Only then open the specific source files needed for the current sprint
4. Read `knowledge/sprint_log.md` only when historical context is actually needed

## Current Sprint

- Sprint: `Sprint 23 — Strategy Parameters & Scenario Presets`
- Status: ready to start
- Baseline: `pytest tests/ -q` must show `415 passed`

## Why This Exists

`knowledge/sprint_log.md` is the long-form archive. It should not be the default first read during agent switching because it consumes a large amount of context for little immediate value.

## Current State

- Workbench tabs are in place: `Strategies`, `Backtest Lab`, `Runtime Monitor`
- Backtest comparison UX is in place from Sprint 22:
  - strategy candidate comparison table
  - saved-run leaderboard
  - run ranking helpers in `dashboard/workbench.py`
- Runtime monitoring is already strategy-aware and mode-aware

## Immediate Goal

Make backtests parameter-aware so the dashboard can evaluate scenarios, not just fixed strategy names.

## Files Most Likely Needed First

- `dashboard/streamlit_app.py`
- `dashboard/workbench.py`
- `backtester/service.py`
- `strategy/base.py`
- `strategy/runtime.py`
- `HANDOFF.md`

## Constraints

- `knowledge/experiment_log.md` may remain dirty because a background runtime process writes to it
- Do not edit, stage, or revert `knowledge/experiment_log.md` unless you intentionally stop that process
- Keep the Jesse-like workflow intact
- Prefer pure helpers in `dashboard/workbench.py` over embedding ranking/formatting logic directly in Streamlit

## Sprint 23 Working Target

- surface strategy parameter controls in `Backtest Lab`
- persist chosen parameter payloads with each saved backtest run
- make saved runs and comparisons scenario-aware
- keep paper/live activation behavior unchanged unless explicitly required

## Last Verified State

- Tests: `415 passed, 1 warning`
- Last sprint closed: `Sprint 22`
- Last pushed commit at handoff creation: `fa3c8ba`

## Token-Saving Rule

If you only need to continue the active sprint, do not read the full sprint log first. Use `HANDOFF.md` + this file + the relevant code files.
