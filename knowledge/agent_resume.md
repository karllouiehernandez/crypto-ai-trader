# Agent Resume Pack

Use this file for agent switching. It is the compact handoff intended for Codex, Claude Code, and GitHub Copilot Pro.

Read order for a new agent:
1. `HANDOFF.md`
2. `knowledge/agent_resume.md`
3. Only then open the specific source files needed for the current sprint
4. Read `knowledge/sprint_log.md` only when historical context is actually needed

## Current Sprint

- Sprint: `Sprint 30 — User-prioritized follow-up`
- Status: Sprint 29 is closed; dynamic Binance `USDT` symbol discovery, persisted runtime watchlists, and historical backfill/audit coverage are in place
- Baseline: `pytest tests/ -q` must show `500 passed`
- GitHub tracking issue: Sprint 29 issue creation was attempted and failed with `403 Resource not accessible by integration`; exact manual issue/card text is recorded in `HANDOFF.md` and `knowledge/sprint_log.md`

## Why This Exists

`knowledge/sprint_log.md` is the long-form archive. It should not be the default first read during agent switching because it consumes a large amount of context for little immediate value.

## Current State

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
- Workbench tabs are in place: `Strategies`, `Backtest Lab`, `Runtime Monitor`
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

Sprint 30 is not fixed yet. Likely next directions:
- expand historical providers/exchanges beyond Binance spot `USDT`
- improve watchlist and symbol-management UX
- harden GitHub sprint/project automation once write access exists

## Constraints

- `knowledge/experiment_log.md` may remain dirty because a background runtime process writes to it
- Do not edit, stage, or revert `knowledge/experiment_log.md` unless you intentionally stop that process
- Keep the Jesse-like workflow intact
- Prefer pure helpers in `dashboard/workbench.py` over embedding ranking/formatting logic directly in Streamlit
- Keep the responsive chart self-contained and locally bundled; do not introduce a Node build step

## Last Verified State

- Tests: `500 passed, 1 warning`
- Last sprint closed: `Sprint 29`

## Token-Saving Rule

If you only need to continue the active sprint, do not read the full sprint log first. Use `HANDOFF.md` + this file + the relevant code files.
