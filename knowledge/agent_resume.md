# Agent Resume Pack

Use this file for agent switching. It is the compact handoff intended for Codex, Claude Code, and GitHub Copilot Pro.

Read order for a new agent:
1. `HANDOFF.md`
2. `knowledge/agent_resume.md`
3. Only then open the specific source files needed for the current sprint
4. Read `knowledge/sprint_log.md` only when historical context is actually needed

## Current Sprint

- Sprint: `Sprint 24 — Named Scenario Presets`
- Status: ready to start
- Baseline: `pytest tests/ -q` must show `421 passed`
- Queued next sprint: `Sprint 25 — Weekly Market Focus Selector` (GitHub issue `#26`)

## Why This Exists

`knowledge/sprint_log.md` is the long-form archive. It should not be the default first read during agent switching because it consumes a large amount of context for little immediate value.

## Current State

- Workbench tabs are in place: `Strategies`, `Backtest Lab`, `Runtime Monitor`
- Backtest comparison UX is in place from Sprint 22:
  - strategy candidate comparison table
  - saved-run leaderboard
  - run ranking helpers in `dashboard/workbench.py`
- Run-scoped scenarios are now in place from Sprint 23:
  - backtest parameter controls in `Backtest Lab`
  - params persisted with each saved run
  - comparison views treat `strategy + params` as the evaluation unit
- Runtime monitoring is already strategy-aware and mode-aware

## Immediate Goal

Add reusable named presets on top of the run-scoped scenario system so backtests can reapply saved parameter sets without manual re-entry.

## Queued After Sprint 24

- Sprint: `Sprint 25 — Weekly Market Focus Selector`
- GitHub tracking issue: `#26`
- Goal: recommend the best Binance spot `USDT` token for the week using a deterministic, low-token ranking flow
- Strategy basis: evaluate the active strategy and active params only
- Output boundary: recommendation-only inside the workbench; no paper/live auto-switching

Planned capability:
- discover a research-only top-liquid Binance `USDT` universe wider than runtime `SYMBOLS`
- rank candidates using recent backtest results
- persist weekly study runs and shortlisted candidates
- let the dashboard prefill `Backtest Lab` with the recommended token

## Files Most Likely Needed First

- `dashboard/streamlit_app.py`
- `dashboard/workbench.py`
- `backtester/service.py`
- `database/models.py`
- `strategy/base.py`
- `strategy/runtime.py`
- `HANDOFF.md`

## Constraints

- `dashboard/streamlit_app.py` currently has an uncommitted local compatibility fix; review before overwriting or staging unrelated changes
- `knowledge/experiment_log.md` may remain dirty because a background runtime process writes to it
- Do not edit, stage, or revert `knowledge/experiment_log.md` unless you intentionally stop that process
- Keep the Jesse-like workflow intact
- Prefer pure helpers in `dashboard/workbench.py` over embedding ranking/formatting logic directly in Streamlit

## Sprint 23 Working Target

Sprint 23 closed. The next sprint should:

- add named presets keyed by strategy
- let the dashboard save and reapply a preset in `Backtest Lab`
- keep run-scoped params and saved-run comparisons working as they do now
- keep paper/live parameter behavior unchanged unless explicitly expanded

## Last Verified State

- Tests: `421 passed, 1 warning`
- Last sprint closed: `Sprint 23`
- Latest closed sprint artifacts are in the repo; use `git log --oneline -n 3` if you need the exact commit IDs without reopening the full sprint archive

## Token-Saving Rule

If you only need to continue the active sprint, do not read the full sprint log first. Use `HANDOFF.md` + this file + the relevant code files.
