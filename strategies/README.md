# Strategy Plugin Workflow

This directory holds hot-loadable strategy plugins for `crypto_ai_trader`.

Use this workflow when Codex, Claude Code, or GitHub Copilot Pro creates or edits a strategy:

1. Start from the dashboard `Create / Import Strategy Draft` expander, [`_strategy_template.py`](./_strategy_template.py), or [`example_rsi_mean_reversion.py`](./example_rsi_mean_reversion.py).
2. Save generated, pasted, or uploaded drafts as `generated_YYYYMMDD_HHMMSS.py`.
3. Validate the draft contract before discovery. A plugin must define:
   - `name` must be snake_case and end with `_v1`, `_v2`, etc.
   - `display_name` should be short and user-facing.
   - `description` should explain the edge and intended market behavior.
   - `version` should use semantic versioning.
   - `regimes` should define where the strategy may run.
   - `default_params()` must return a dict.
   - `param_schema()` must return dashboard-serialisable parameter metadata.
   - Signal logic must be either `should_long()` plus `should_short()`, or one `decide()` override.
   - Candle/indicator references must use columns produced by `strategy/ta_features.py`.
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
- Plugin validation/load failures appear in the dashboard. Do not rely on logs alone.
- Generated/imported drafts are backtest-only. Use the dashboard review action to save a pinned reviewed plugin before paper/live activation.
- Use `Refresh Strategy Registry` in the dashboard after editing files on disk; a full app restart should not be required for normal strategy iteration.
