# Bugs and Fixes

Root cause analysis and fix record for every production incident and known bug.
Add an entry here whenever a bug is found — even before it is fixed.

---

## 2026-04-17 dashboard/streamlit_app.py — Chart overlay toggles reset on every auto-refresh
**What happened:** User untoggled OHLC candlesticks (or BB/EMAs) via Plotly's legend. Every 15s auto-refresh called `st.rerun()`, rebuilding the chart from scratch and re-adding all traces — ignoring what the user had toggled off.
**Why it happened:** Plotly legend toggles are client-side only. `st.checkbox(value=True)` without a `key=` also resets to the default on every rerun. Neither approach survives `st.rerun()`.
**Impact:** Dashboard unusable for focused analysis — any overlay customisation is lost every 15 seconds.
**What we changed:** Moved all overlay controls to sidebar `st.checkbox` widgets with `key=` parameter. Defaults initialised once via `if k not in st.session_state` guard. Added countdown timer and line-chart fallback.
**What to try next:** N/A — resolved.
**Status:** FIXED — 2026-04-17

---

## 2026-04-16 simulator/backtester.py — Wrong argument order in compute_signal() call
**What happened:** `simulator/backtester.py` calls `compute_signal(sym, sess)` but the actual function signature in `strategy/signal_engine.py` is `compute_signal(sess, candle)`. Running the backtester would raise a `TypeError` immediately.
**Why it happened:** The backtester was written against a stale API — `compute_signal` was refactored to take `(sess, candle)` but the caller was not updated.
**Impact:** Backtester is completely non-functional. Any historical simulation or strategy validation is blocked until fixed.
**What we changed:** Sprint 0 — fix call to `compute_signal(sess, candle)` and pass the actual candle object from the loop.
**What to try next:** Add a regression test in Sprint 2 (`test_backtester.py`) that runs the backtester on a small known dataset to prevent re-regression.
**Status:** FIXED — Sprint 0

---

## 2026-04-16 dashboard/streamlit_app.py — Imports of non-existent modules
**What happened:** `dashboard/streamlit_app.py` imports `simulate_trades` and `ai_engine`, neither of which exists in the codebase. The dashboard crashes on startup with `ModuleNotFoundError`.
**Why it happened:** These modules were planned but never implemented. The import statements were left as stubs.
**Impact:** Dashboard is completely non-functional. No live chart, no equity curve, no trade markers.
**What we changed:** Sprint 0 — remove the broken imports; stub out the functionality they were meant to provide with placeholder comments for Sprint 7.
**What to try next:** Sprint 7 will implement the actual dashboard with real data from the DB.
**Status:** FIXED — Sprint 0

---

## 2026-04-16 config.py — Hardcoded API credentials
**What happened:** Binance API key/secret and Telegram bot token + chat ID are hardcoded as string literals in `config.py`. This file is tracked by version control, meaning credentials are exposed to anyone with repo access.
**Why it happened:** Credentials were embedded during initial development for convenience and never migrated to environment variables.
**Impact:** CRITICAL security risk. Credentials must be rotated if the repo has ever been pushed to any remote. Paper trading only today, but this must be fixed before any real-money deployment.
**What we changed:** Sprint 0 — move all credentials to `.env` file (git-ignored); load via `python-dotenv`; create `.env.example` with variable names but no values.
**What to try next:** Add a startup assertion that raises a clear error if required env vars are missing, rather than silently using empty strings.
**Status:** FIXED — Sprint 0

---

## 2026-04-16 backtester/engine.py — Trade block de-indented out of the for loop (regression)
**What happened:** During the Sprint 0 fix to add a `with SessionLocal() as sess:` block, the `if sig == Signal.BUY / elif sig == Signal.SELL` trade block was accidentally de-indented outside the for loop. Only the last candle's signal was ever acted upon.
**Why it happened:** Indentation error introduced while restructuring the session context block during the CRIT-1 fix.
**Impact:** Backtester produced no trades or only one trade regardless of dataset. Caught by code review sub-agent in second review pass.
**What we changed:** Sprint 0 (second pass) — re-indented trade block inside the for loop; also added `FEE_RATE` to buy/sell which was missing.
**What to try next:** Sprint 2 regression test will prevent future indentation regressions.
**Status:** FIXED — Sprint 0 (second pass)

---

## 2026-04-16 config.py — validate_env() existed but was never called (dead guard)
**What happened:** `validate_env()` was added to `config.py` but never wired into `run_live.py` or `run_backtest.py`. Bot would start with empty credentials and fail silently at API call time.
**Why it happened:** Function was implemented but the integration step was missed.
**Impact:** Developers cloning the repo without a `.env` would get cryptic API errors instead of a clear message.
**What we changed:** Sprint 0 (second pass) — added `validate_env()` as first statement in both entry points.
**Status:** FIXED — Sprint 0 (second pass)

---

## 2026-04-16 telegram_utils.py — Alert functions used import-time credential snapshots
**What happened:** `alert_buy/sell/cutloss()` and `alert()` referenced module-level `TELEGRAM_TOKEN`/`TELEGRAM_CHAT_ID` captured at import time, before `.env` was loaded in some import orders. Alerts silently failed with empty tokens.
**Why it happened:** Module-level snapshot pattern doesn't account for load-order dependency with `dotenv`.
**Impact:** All Telegram trade alerts silently fail in environments where `telegram_utils` is imported before `load_dotenv()` runs.
**What we changed:** Sprint 0 (second pass) — replaced all module-level credential references with lazy `_token()`, `_chat_id()`, `_alerts_enabled()` functions that read from `config` at call time.
**Status:** FIXED — Sprint 0 (second pass)

---

## 2026-04-16 simulator/paper_trader.py — FEE_RATE not applied; hardcoded symbol list
**What happened:** `_auto_buy()` and `_auto_sell()` did not apply `FEE_RATE`, making paper trading results ~0.2% optimistic per round-trip vs backtesting. Symbol list was hardcoded instead of using `SYMBOLS` from config.
**Why it happened:** Fee logic was in the backtester but never ported to the paper trader.
**Impact:** Paper trading P&L not comparable to backtests; compounds significantly over many trades.
**What we changed:** Sprint 0 (second pass) — applied `FEE_RATE` to both sides; added cash guard on buy; replaced hardcoded list with `SYMBOLS`.
**Status:** FIXED — Sprint 0 (second pass)
