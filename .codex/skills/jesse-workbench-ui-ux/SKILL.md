---
name: jesse-workbench-ui-ux
description: Jesse-like trading workbench workflow for crypto_ai_trader. Use when modifying the dashboard, strategy selection UX, backtest visualization, paper/live monitoring, or agent-assisted strategy generation flow. Enforce a dashboard-first research-to-paper-to-live experience with consistent strategy identity, stored run history, and visible runtime mode/state.
---

# Jesse Workbench UI/UX

Treat the product as a trading workbench, not only a monitor.

## Core workflow

Preserve this user loop:

1. Discover or add a strategy
2. Inspect strategy metadata and status
3. Select the active strategy
4. Run a backtest visually
5. Inspect metrics, candles, equity, drawdown, and trades
6. Promote the same strategy into paper trading
7. Later use the same strategy in live trading

Do not design separate disconnected experiences for backtest, paper, and live.

## Required surfaces

Keep these surfaces visible in the dashboard:

- `Strategies`
- `Backtest Lab`
- `Runtime Monitor`

If adding navigation, prefer tabs or clearly separated sections over buried controls.

## Required backtest outputs

Backtest UX must show:

- strategy identity
- symbol and date range
- candlestick chart with BUY/SELL markers
- equity curve
- drawdown or risk view
- metrics summary
- trade log
- stored run history

Do not reduce backtest output to a single metric table or a plain CLI dump.

## Strategy identity rules

Keep the same strategy identity visible everywhere:

- strategy name
- version
- source (`builtin` or `plugin`)
- run mode (`backtest`, `paper`, `live`)

When strategy changes are saved:

- backtests may use the new selection immediately
- paper/live must show an explicit restart-required message
- never silently hot-swap the running live/paper strategy

## Plugin and generation rules

Surface plugin and generated strategy state in the UI:

- loaded strategies
- file/source provenance when available
- load errors
- generated/plugin distinction
- generated drafts vs reviewed plugins

Do not leave strategy load failures only in logs.

Generated strategies should be treated as drafts until they have been reviewed and backtested. The UI should make the next step explicit:

- generate draft
- review/edit draft
- backtest draft
- save accepted draft as a reviewed plugin
- only then set it active for paper/live

## Design direction

Prefer Jesse-like workflow traits:

- fast iteration
- compact but information-dense results
- saved run history
- seamless movement from research to execution
- strategy-first navigation, not chart-first navigation

Preserve the existing visual language where practical, but prioritize clarity of workflow over cosmetic consistency.
