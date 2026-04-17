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
**Date started:** 2026-04-16
**Date closed:** 2026-04-16
**Goal:** Create `knowledge/kb_update.py` so any agent (Claude or Copilot) can update the KB from the terminal after a session
**Status:** CLOSED ✓

### Changes Made
- [x] `knowledge/kb_update.py` — new interactive CLI script; supports 5 entry types (bug, strategy, experiment, parameter, regime); appends correctly-formatted markdown entries to the right KB file; `--type` CLI arg for non-interactive use; handles new file creation, auto-ID for experiments, required/optional field prompts

### Code Review (1 pass)
**Pass 1 result:** APPROVED (after fixes) — 1 CRITICAL, 1 MEDIUM, 2 LOW found
- CRITICAL: double-separator bug in `append_entry()` when creating a new file — **fixed** (removed trailing `---` from initial header write; also improved separator to `\n\n---\n\n` for clean formatting)
- MEDIUM: confirmation accepted any non-"n" input — **fixed** (now explicitly requires y/yes/blank)
- LOW: STATUS_OPTIONS missing "parameter" key comment — **fixed** (added explanatory comment)
- LOW: parameter entries omit Status field — **acceptable** (parameter_history.md format intentionally uses changelog style without Status; comment added in code)

### Outcome
Script is functional and correctly formats entries for all 5 KB types. Experiment auto-ID (EXP-NNN) works by scanning existing entries. All CRITICAL and HIGH issues resolved. Ready for Sprint 2.

---

## Sprint 2 — Testing Infrastructure
**Date started:** 2026-04-16
**Date closed:** 2026-04-16
**Goal:** Add `pytest` + `pytest-asyncio` test suite covering core strategy logic
**Status:** CLOSED ✓

### Changes Made
- [x] `tests/__init__.py` — created tests package
- [x] `tests/test_ta_features.py` — 16 unit tests: column presence, RSI bounds/direction, BB ordering, MACD types, SMA math, dropna contract
- [x] `tests/test_signal_engine.py` — 10 unit tests: insufficient history (0/59/60 candles), BUY/SELL/HOLD signal conditions, symbol routing via mock
- [x] `tests/test_paper_trader.py` — 18 unit tests: auto_buy/sell fee math, cash guard, zero-price guard, step dispatch, round-trip P&L
- [x] `tests/test_backtester.py` — 11 unit tests: empty candles error, return type, BUY/SELL trades, fee inclusion, no-sell-without-position, multi-round-trip
- [x] `pytest.ini` — asyncio_mode=auto, testpaths=tests
- [x] `requirements.txt` — added pytest>=8.0, pytest-asyncio>=0.23
- [x] `simulator/paper_trader.py` — **bug fixes**: added `price <= 0` guard in `_auto_buy`; added same guard in `_auto_sell`; added `cost_basis` tracking for correct realised P&L; use `STARTING_BALANCE_USD` from config
- [x] `backtester/engine.py` — **bug fixes**: use `POSITION_SIZE_PCT` for sizing (was all-in); use `STARTING_BALANCE_USD` from config (was hardcoded 10000)

### Code Review (1 pass)
**Pass 1 result:** APPROVED (after fixes) — 1 CRITICAL, 3 HIGH, 2 MEDIUM found
- CRITICAL: `realised` tracked total proceeds instead of actual P&L — **fixed** (added `cost_basis` dict)
- HIGH: missing `price <= 0` guard in `_auto_sell` — **fixed**
- HIGH: backtester used all-in sizing vs PaperTrader's POSITION_SIZE_PCT — **fixed** (backtester now uses POSITION_SIZE_PCT)
- HIGH: hardcoded `10_000.0` starting balance in both files vs `STARTING_BALANCE_USD=100` in config — **fixed**
- MEDIUM: weak `realised > 0` assertion — **fixed** with exact P&L value check
- MEDIUM: no zero-price test for `_auto_sell` — **fixed** (added test)

### Outcome
55 tests passing in 0.89s. All CRITICAL/HIGH issues resolved. Test suite covers all core modules with zero I/O dependencies. Ready for Sprint 3.

### Planned Changes
- `tests/test_signal_engine.py` — unit tests with synthetic OHLCV DataFrames
- `tests/test_ta_features.py` — verify indicator math
- `tests/test_paper_trader.py` — mock Binance + DB
- `tests/test_backtester.py` — regression test with known data
- `pytest.ini` — test config
- `requirements.txt` — add `pytest`, `pytest-asyncio`

---

## Sprint 3 — Risk Management Overhaul
**Date started:** 2026-04-16
**Date closed:** 2026-04-16
**Goal:** Replace flat position sizing with ATR-based sizing; add daily loss limit and drawdown circuit breaker
**Status:** CLOSED ✓

### Changes Made
- [x] `config.py` — added `RISK_PCT_PER_TRADE=0.01`, `ATR_STOP_MULTIPLIER=1.5`, `DAILY_LOSS_LIMIT_PCT=0.03`, `DRAWDOWN_HALT_PCT=0.15`
- [x] `strategy/risk.py` — new pure module: `atr_position_size()`, `DailyLossTracker` (daily loss halt with auto-day-rollover reset), `DrawdownCircuitBreaker` (peak-to-trough halt with manual reset)
- [x] `simulator/paper_trader.py` — integrated risk: `_compute_atr()` helper, ATR sizing in `_auto_buy()`, circuit breaker check in `step()`, manual trades check circuit breakers in `_consume_callbacks()`
- [x] `tests/test_risk.py` — 39 new unit tests covering all risk primitives and edge cases
- [x] `tests/test_paper_trader.py` — 4 new integration tests covering risk circuit breaker halt, ATR sizing, and multi-position equity calculation

### Code Review (1 pass)
**Pass 1 result:** APPROVED (after fixes) — 3 CRITICAL found
- CRITICAL #1: Manual trades via Telegram bypassed circuit breakers — **fixed** (halt check added in `_consume_callbacks`)
- CRITICAL #2: `_manual_buy()` didn't compute ATR, fell back to 20% flat sizing — **fixed** (now opens its own session and calls `_compute_atr`)
- CRITICAL #3: `_auto_buy` equity used only single-symbol price, ignoring existing positions — **fixed** (accepts `prices` dict; `step()` passes full prices; equity correct for multi-position portfolios)
- MEDIUM: duplicate DB queries in `step()` — **fixed** (single-pass candle collection)

### Outcome
98 tests passing in 0.90s. Risk management fully integrated. Bot now:
- Sizes positions based on 1% equity risk per ATR stop (RISK_PCT_PER_TRADE / ATR_STOP_MULTIPLIER)
- Halts all trading (including manual Telegram trades) if daily loss > 3%
- Halts all trading if peak-to-trough drawdown > 15%
- Falls back to flat POSITION_SIZE_PCT when ATR unavailable (new symbols, insufficient history)

### Planned Changes
- `strategy/risk.py` — ATR position sizer, daily loss tracker, drawdown circuit breaker
- `simulator/paper_trader.py` — integrate risk module; enforce daily halt + drawdown halt
- `config.py` — add `RISK_PCT_PER_TRADE`, `DAILY_LOSS_LIMIT_PCT`, `DRAWDOWN_HALT_PCT`

---

## Sprint 4 — Signal Quality Improvements
**Date started:** 2026-04-17
**Date closed:** 2026-04-17
**Goal:** Add trend filter (200 EMA), volume confirmation to signal engine
**Status:** CLOSED ✓

### Changes Made
- [x] `strategy/ta_features.py` — added `ema_200` (EMA-200) and `volume_ma_20` (SMA-20 of volume) columns
- [x] `strategy/signal_engine.py` — bumped lookback to `EMA_LOOKBACK=220`; raised minimum-candle guard to `MIN_CANDLES_EMA200=210`; added EMA-200 trend filter (BUY only above EMA, SELL only below); added 1.5× volume confirmation gate; added `len(df) < 2` safety guard after `add_indicators`; replaced all magic numbers with config constants
- [x] `config.py` — added `EMA_LOOKBACK=220`, `MIN_CANDLES_EMA200=210`, `VOLUME_CONFIRMATION_MULT=1.5`
- [x] `tests/test_ta_features.py` — bumped synthetic data to n=220 (required for EMA-200 warmup); added `TestEMA200` (5 tests) and `TestVolumeMA20` (3 tests); updated `test_expected_columns_present` to include new columns
- [x] `tests/test_signal_engine.py` — updated candle counts to 220; replaced old 60-candle threshold test with 210-candle tests; added `TestTrendFilter` (4 tests using patched `add_indicators` with controlled DataFrames); added `TestVolumeFilter` (3 tests)
- [x] `knowledge/parameter_history.md` — documented `MIN_CANDLES`, `EMA_LOOKBACK`, `VOLUME_CONFIRMATION_MULT` changes including 1m vs 1h EMA design note
- [x] `knowledge/strategy_learnings.md` — updated active strategy definition to reflect new filters; documented known limitations

### Deferred from Sprint 4
- **Multi-timeframe confirmation (1m+5m+15m):** Requires separate 5m/15m data streams or candle aggregation — scope beyond Sprint 4. Deferred to Sprint 5/6.
- **1h EMA-200:** Current implementation uses 1m candles (3.3h context); proper 1h EMA needs ~12,000 1m candles or a 1h feed. Deferred to Sprint 5/6 when multi-timeframe data support is added. See `parameter_history.md` for design rationale.

### Code Review (1 pass)
**Pass 1 result:** APPROVED AFTER FIXES — 0 CRITICAL, 3 HIGH found (2 were documentation gaps + 1 design issue)
- HIGH-1: EMA-200 on 1m not 1h — **accepted as Sprint 4 design constraint** (architecture only has 1m data); documented in `parameter_history.md` and `strategy_learnings.md`
- HIGH-2: `parameter_history.md` not updated — **fixed** (added 3 new parameter entries)
- HIGH-3: `sprint_log.md` Sprint 4 entry blank — **fixed** (this entry)
- MEDIUM-2: magic numbers not in `config.py` — **fixed** (extracted `EMA_LOOKBACK`, `MIN_CANDLES_EMA200`, `VOLUME_CONFIRMATION_MULT`)
- MEDIUM-3: `strategy_learnings.md` not updated — **fixed**

### Outcome
114 tests passing in 3.15s. Signal engine now:
- Only fires BUY when close > EMA-200 (uptrend) AND volume >= 1.5× average
- Only fires SELL when close < EMA-200 (downtrend) AND volume >= 1.5× average
- Requires 210+ candles (raised from 60) to ensure EMA-200 warmup
All new logic covered by deterministic controlled-DataFrame tests. Ready for Sprint 5.

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
