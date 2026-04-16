# Sprint Log

Record of every sprint: goal, changes made, code review outcome, and close status.
A sprint may NOT be marked CLOSED until the code review sub-agent returns `Approved to close: YES`.

---

## Sprint 0 — Foundation Fixes + Credentials
**Date started:** 2026-04-16
**Date closed:** 2026-04-16
**Goal:** Fix 3 critical known bugs; move credentials to `.env`
**Status:** CLOSED ✓

### Changes Made
- [x] `simulator/backtester.py` — fixed argument order; fixed equity index mismatch; eliminated double DB query; use `POSITION_SIZE_PCT` from config
- [x] `backtester/engine.py` — moved loop inside session context; fixed de-indented trade block regression; added `FEE_RATE`
- [x] `dashboard/streamlit_app.py` — removed broken imports; fixed `st.experimental_rerun()` → `st.rerun()`; moved rerun to end of script
- [x] `config.py` — credentials to `os.environ.get()`; added `validate_env()`; removed duplicate `MAX_POS_PCT`
- [x] `.env.example` — created with all required variable names
- [x] `.gitignore` — created; `.env` and `*.db` excluded
- [x] `requirements.txt` — added `python-dotenv`, `matplotlib`
- [x] `run_live.py` — wired `validate_env()` at startup
- [x] `run_backtest.py` — wired `validate_env()`; fixed equity curve display logic
- [x] `utils/telegram_utils.py` — replaced all module-level credential snapshots with lazy `_token()`, `_chat_id()`, `_alerts_enabled()` functions
- [x] `simulator/paper_trader.py` — applied `FEE_RATE` on buy/sell; replaced hardcoded symbols with `SYMBOLS` from config; added cash guard on buy
- [x] `knowledge/bugs_and_fixes.md` — all 7 bugs documented with root cause + fix

### Code Review (2 passes)
**Pass 1 result:** NOT APPROVED — 2 CRITICAL, 3 HIGH, 4 MEDIUM, 2 LOW
**Pass 2 result:** APPROVED — 0 CRITICAL, 0 HIGH remaining after fixes
**Total issues found:** 7 (2 CRIT, 3 HIGH, 2 MED new in pass 2, 2 LOW)
**Lessons:** Code review sub-agent caught a regression I introduced during the fix itself (de-indented trade block). This validates the review gate process.

### Outcome
All 3 original Sprint 0 targets fixed. 4 additional issues caught by review sub-agent also fixed. Codebase is now in a clean, runnable baseline state. Ready for Sprint 1.

---

## Sprint 1 — Knowledge Base kb_update.py Script
**Date started:** —
**Goal:** Create `knowledge/kb_update.py` so any agent (Claude or Copilot) can update the KB from the terminal after a session
**Status:** NEXT ⬅

### Planned Changes
- `knowledge/kb_update.py` — interactive CLI script: prompts for topic type + KB fields, appends correctly-formatted entry to the right file
- `knowledge/sprint_log.md` — update Sprint 1 section on close
- `HANDOFF.md` — update resume point on close

### Acceptance Criteria
- `python knowledge/kb_update.py` runs without error
- Supports entry types: bug, strategy, experiment, parameter, regime
- Appends entry with correct format to the right KB file
- Prints confirmation of what was written and where

---

## Sprint 2 — Testing Infrastructure
**Date started:** —
**Goal:** Add `pytest` + `pytest-asyncio` test suite; achieve coverage on core strategy logic
**Status:** PENDING

### Planned Changes
- `tests/test_signal_engine.py` — unit tests with synthetic OHLCV DataFrames
- `tests/test_ta_features.py` — verify indicator math
- `tests/test_paper_trader.py` — mock Binance + DB
- `tests/test_backtester.py` — regression test with known data
- `pytest.ini` — test config
- `requirements.txt` — add `pytest`, `pytest-asyncio`

---

## Sprint 3 — Risk Management Overhaul
**Date started:** —
**Goal:** Replace flat 30% position sizing with ATR-based sizing; add circuit breakers
**Status:** PENDING

### Planned Changes
- `strategy/risk.py` — ATR position sizer, daily loss tracker, drawdown circuit breaker
- `simulator/paper_trader.py` — integrate risk module; enforce daily halt + drawdown halt
- `config.py` — add `RISK_PCT_PER_TRADE`, `DAILY_LOSS_LIMIT_PCT`, `DRAWDOWN_HALT_PCT`

---

## Sprint 4 — Signal Quality Improvements
**Date started:** —
**Goal:** Add trend filter (200 EMA), multi-timeframe confirmation, volume validation
**Status:** PENDING

---

## Sprint 5 — Regime Detection
**Date started:** —
**Goal:** ADX + BB-width regime classifier; gate strategies by active regime
**Status:** PENDING

---

## Sprint 6 — Multi-Strategy Portfolio
**Date started:** —
**Goal:** Add momentum and breakout strategies alongside mean reversion
**Status:** PENDING

---

## Sprint 7 — Dashboard Fixes + Observability
**Date started:** —
**Goal:** Fix broken dashboard imports; add structured logging across all modules
**Status:** PENDING

---

## Sprint 8 — Backtesting Rigor
**Date started:** —
**Goal:** Walk-forward validation; slippage modeling; Sharpe/DD/PF acceptance gates
**Status:** PENDING
