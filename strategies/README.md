# Strategy Plugin Workflow

This directory holds hot-loadable strategy plugins for `crypto_ai_trader`.

Use this workflow when Codex, Claude Code, or GitHub Copilot Pro creates or edits a strategy:

1. Start from [`_strategy_template.py`](./_strategy_template.py) or review [`example_rsi_mean_reversion.py`](./example_rsi_mean_reversion.py).
2. Save generated drafts as `generated_YYYYMMDD_HHMMSS.py`.
3. Review the draft metadata and logic before treating it as a candidate:
   - `name` must be snake_case and end with `_v1`, `_v2`, etc.
   - `display_name` should be short and user-facing.
   - `description` should explain the edge and intended market behavior.
   - `version` should use semantic versioning.
4. Backtest the strategy in the dashboard `Backtest Lab`.
5. Only after a satisfactory backtest should the draft be promoted into a reviewed plugin:
   - copy or rename it to a stable filename such as `ema_pullback_reviewed.py`
   - keep the class `name` and `version` aligned with the reviewed revision
6. Set the reviewed plugin as active for paper trading from the dashboard.
7. Paper/live processes must be restarted after strategy changes.

Recommended naming conventions:

- Generated drafts: `generated_YYYYMMDD_HHMMSS.py`
- Reviewed plugins: descriptive filenames like `ema_pullback_reviewed.py`
- Strategy `name`: `ema_pullback_v1`
- Strategy class: `EmaPullbackStrategy`

Operational rules:

- Files beginning with `_` are ignored by the plugin loader and are safe for templates or notes.
- Plugin load failures appear in the dashboard. Do not rely on logs alone.
- Generated drafts are not automatically “ready”. Use passing backtests and code review before paper/live activation.
