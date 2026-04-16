# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Multi-Agent Continuity

This project alternates between **Claude Code** and **GitHub Copilot Pro**. The shared handoff protocol:

- `HANDOFF.md` — **read this first every session**; contains current sprint, resume point, and blocking issues
- `.github/copilot-instructions.md` — Copilot's equivalent of this file (kept in sync)
- `knowledge/sprint_log.md` — full sprint history

**When ending a session:** update `HANDOFF.md` with where you left off before hitting cooldown.

---

## Commands

```bash
pip install -r requirements.txt                        # install dependencies
python run_live.py                                     # start live paper trading bot
python run_backtest.py BTCUSDT 2024-01-01 2024-03-31  # run backtest
streamlit run dashboard/streamlit_app.py               # launch dashboard
python knowledge/kb_update.py                          # update knowledge base after session
pytest tests/                                          # run test suite (Sprint 2+)
```

No test suite, linting config, or CI/CD pipeline exists yet (Sprint 2 will add these).

---

## Sprint Development Workflow

This project is built sprint-by-sprint. After every sprint, a **code review sub-agent** inspects all changed files before work continues. Never skip the review gate.

### Sprint Map

| Sprint | Goal | Key Files |
|--------|------|-----------|
| 0 | Foundation fixes + credentials | `config.py`, `simulator/backtester.py`, `dashboard/streamlit_app.py` |
| 1 | Knowledge base initialization | `knowledge/` directory |
| 2 | Testing infrastructure | `tests/`, `pytest.ini` |
| 3 | Risk management overhaul | `strategy/risk.py`, `simulator/paper_trader.py` |
| 4 | Signal quality improvements | `strategy/signal_engine.py`, `strategy/ta_features.py` |
| 5 | Regime detection | `strategy/regime.py` |
| 6 | Multi-strategy portfolio | `strategy/signal_momentum.py`, `strategy/signal_breakout.py` |
| 7 | Dashboard fixes + observability | `dashboard/streamlit_app.py`, structured logging |
| 8 | Backtesting rigor | `backtester/engine.py`, walk-forward validation |

### Sprint Execution Protocol

Every sprint follows this exact loop:

```
1. PLAN      → Read relevant KB files before writing any code
2. BUILD     → Implement only what the sprint specifies — no scope creep
3. REVIEW    → Spawn code-review sub-agent on all changed files (see below)
4. FIX       → Address all CRITICAL and HIGH findings before closing sprint
5. DOCUMENT  → Update knowledge base files with sprint outcome
6. CLOSE     → Log sprint result in knowledge/sprint_log.md
```

### Code Review Sub-Agent

After completing each sprint, spawn a review agent:

```python
Agent(
    description="Sprint N code review",
    subagent_type="general-purpose",
    prompt="""
    You are a senior software engineer and crypto trading systems expert.
    Review the following changed files for Sprint N of the crypto_ai_trader project.

    Changed files: [list files]

    Review criteria:
    1. CORRECTNESS     — logic bugs, off-by-one errors, wrong argument order
    2. SECURITY        — hardcoded credentials, injection risks, exposed secrets
    3. ASYNC SAFETY    — blocking calls in async context, missing await, unclosed sessions
    4. TRADING LOGIC   — position sizing math, signal conditions, risk rule violations
    5. KNOWLEDGE BASE  — were KB files updated with sprint learnings?
    6. TEST COVERAGE   — are new functions covered by tests?

    Classify each issue: CRITICAL / HIGH / MEDIUM / LOW
    CRITICAL and HIGH must be fixed before the sprint is closed.

    Output:
    ## Summary
    ## CRITICAL Issues
    ## HIGH Issues
    ## MEDIUM Issues
    ## LOW Issues
    ## Approved to close: YES / NO
    """
)
```

Save the review result to `knowledge/sprint_log.md` before starting the next sprint.

---

## Codebase Architecture

Fully async Python system (`asyncio`) with three runtime modes: live trading, backtesting, dashboard.

### Data Layer (`database/`, `collectors/`)
- SQLite at `data/market_data.db` via SQLAlchemy 2.x async ORM
- `database/models.py`: `Candle` (OHLCV, unique on symbol+open_time), `Trade` (execution log), `Portfolio` (single-row upserted equity snapshot)
- `collectors/historical_loader.py`: parallel 365-day 1m candle fetch from Binance on first boot (idempotent)
- `collectors/live_streamer.py`: polls Binance every second, writes rolling 1m candles

### Strategy Layer (`strategy/`)
- `signal_engine.py`: BUY/SELL/HOLD via RSI-14 + Bollinger Bands + MACD crossover (requires 60+ candles)
- `ta_features.py`: SMA-21/55, MACD, RSI-14, BB via `ta` library
- All strategy files must be **pure functions** — no DB access, no I/O; takes DataFrame, returns signal

### Trading Engine (`simulator/`)
- `paper_trader.py`: async loop — signal per symbol per second, auto-executes or handles Telegram overrides via `CALLBACK_QUEUE`
- `backtester.py`: was broken (wrong arg order in `compute_signal` call) — fixed in Sprint 0

### Entry Points
- `run_live.py`: load history → live stream → paper trader (concurrent asyncio tasks)
- `run_backtest.py` → `backtester/engine.py`

### External Integrations
- Binance: `python-binance` async client (`BINANCE_TESTNET=True` in config)
- Telegram (`utils/telegram_utils.py`): trade alerts + manual BUY/SELL commands via shared `CALLBACK_QUEUE`
- Dashboard (`dashboard/streamlit_app.py`): Streamlit + Plotly, 30s auto-refresh

### Configuration (`config.py`)
All runtime parameters: `SYMBOLS`, `STARTING_BALANCE_USD`, `MAX_POS_PCT` (0.20), `POSITION_SIZE_PCT` (0.30), `FEE_RATE` (0.001), `LIVE_POLL_SECONDS` (1).
Credentials loaded from `.env` via `python-dotenv` (moved in Sprint 0).

---

## Knowledge Base System

Living memory in `knowledge/` — **read before every sprint, updated after every sprint**.

### Structure
```
knowledge/
  README.md                 # index of all KB docs
  sprint_log.md             # sprint progress + code review outcomes
  strategy_learnings.md     # what signal configs worked/failed and why
  risk_learnings.md         # sizing, stop-loss, drawdown incidents
  market_regime_notes.md    # observed regime patterns + bot performance
  bugs_and_fixes.md         # root cause + fix for every production incident
  experiment_log.md         # hypothesis → test → result for every experiment
  parameter_history.md      # changelog of every config/strategy parameter change
  backtest_results/         # one .md per backtest run (auto-generated)
```

### KB Entry Format
```markdown
## [DATE] [SYMBOL/TOPIC] — [ONE LINE SUMMARY]
**What happened:** (objective description)
**Why it happened:** (root cause or hypothesis)
**Impact:** (P&L, Sharpe, trades affected)
**What we changed:** (code/config diff or "pending")
**What to try next:** (concrete next experiment)
**Status:** [OPEN | RESOLVED | MONITORING]
```

### Rules for Claude
- **Before any sprint**: read `knowledge/sprint_log.md` and relevant topic files
- **After any sprint**: update KB — never leave learnings only in chat history
- **Before parameter changes**: read `knowledge/parameter_history.md` to avoid re-testing known bad values
- **Before backtesting**: check `knowledge/backtest_results/` for prior runs as baseline

### Iteration Loop
```
1. Hypothesis  → write in experiment_log.md
2. Backtest    → run on out-of-sample data, save to backtest_results/
3. Paper trade → run ≥2 weeks, observe real signal behavior
4. Evaluate    → compare metrics against KB baseline
5. Document    → update strategy_learnings.md regardless of outcome
6. Promote or discard → merge or mark failed in experiment_log.md
```

---

## Expert Crypto Trading Architecture

### Market Microstructure
- 24/7 trading — no session boundaries; avoid strategies that assume market open/close
- Lowest liquidity: UTC 01:00–05:00 | Highest liquidity: UTC 12:00–16:00
- Funding rates on perps reset every 8h — extreme funding (>0.1%) is a mean-reversion signal
- Correlations break during liquidation cascades — normal assumptions invalid in high-vol regimes

### Signal Quality Hierarchy (implement in this order)
1. **Trend filter**: longs only above 200-period EMA (1h chart); shorts only below
2. **Multi-timeframe confirmation**: signal must agree on 1m + 5m + 15m before entry
3. **Volume confirmation**: entry candle volume ≥ 1.5× 20-period average
4. **ATR-based stops**: stop = entry ± 1.5×ATR(14); never fixed-pip stops in crypto

### Strategy Portfolio (gate by regime)

| Strategy | Timeframe | Entry | Exit | Active When |
|----------|-----------|-------|------|-------------|
| Mean reversion | 1m–5m | RSI < 30 + BB lower touch + MACD cross | RSI > 55 or +1.5×ATR | ADX < 20 |
| Momentum | 1h–4h | EMA9>EMA21>EMA55, ADX>25, pullback to EMA21 | EMA9 < EMA21 | ADX > 25 |
| Breakout | Daily | Close above 20d high + volume 2× avg | Trail below prior swing low | Post-consolidation |
| Volatility squeeze | 1h | BB width at 6-month low, wait for expansion candle | First close outside BB | BB width < 20th %ile (90d) |

### Regime Detection
```python
# ADX > 25                         → trending   → momentum strategy active
# ADX < 20                         → ranging    → mean reversion active
# BB width < 20th percentile (90d) → squeeze    → breakout/squeeze active
# Realized vol > 2× 30d avg        → high vol   → reduce all position sizes 50%
```

### Risk Rules (non-negotiable)
- Max 1–2% equity risk per trade — current 30% flat is ruin math (fixed in Sprint 3)
- ATR position sizing: `size = (equity × 0.01) / (1.5 × ATR(14))`
- Max 3 concurrent positions; BTC + ETH count as correlated (only one long at a time)
- Daily loss limit: halt trading if down 3% on the day
- Drawdown circuit breaker: halt if equity drops 15% from peak; require manual review
- Never average down into a losing position

### Backtest Standards
1. Minimum 2 years of 1m data across bull + bear + sideways regimes
2. Walk-forward: 70% train / 30% out-of-sample, rolling 3-month windows
3. Include realistic slippage (0.05–0.1% per fill) + fees (0.1%)
4. Accept only: Sharpe > 1.5, max drawdown < 20%, profit factor > 1.5, ≥ 200 trades
5. Parameter sensitivity: ±20% on each param must not drastically shift results (overfitting check)

---

## Senior Software Engineering Standards

### Async Patterns
- All DB operations use `async with AsyncSession` — never mix sync/async SQLAlchemy sessions
- `asyncio.gather()` for concurrent symbol processing; `asyncio.Queue` for producer/consumer
- `asyncio.wait_for()` on all Binance API calls — they can hang indefinitely
- Long-running tasks must handle `asyncio.CancelledError` and flush state before exit

### Reliability
```python
async def fetch_with_retry(fn, max_retries=5, base_delay=1.0):
    for attempt in range(max_retries):
        try:
            return await fn()
        except (NetworkError, TimeoutError):
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(base_delay * 2 ** attempt)
```
- Circuit breaker: 5 consecutive Binance failures → pause 60s before retry
- Failed trade signals must be logged to DB, never silently dropped

### Database
- Use `on_conflict_do_nothing()` for idempotent candle writes
- Windowed queries only: `WHERE open_time >= now - interval AND symbol = ?`
- Add `(symbol, open_time DESC)` index for latest-candle lookups
- Use Alembic for all schema migrations — never alter production schema by dropping tables

### Observability
```python
import logging
log = logging.getLogger(__name__)
log.info("signal", extra={"symbol": sym, "signal": sig, "rsi": rsi, "price": close})
# Track: signal rate per symbol, slippage, candle→order latency, API error rate
```

### Code Organization
- `strategy/` = pure functions only — no DB, no I/O; takes DataFrame, returns signal
- `collectors/` owns all Binance communication — nothing else calls the Binance client
- `simulator/` orchestrates only — delegates all trading logic to `strategy/`
- No magic numbers in module files — all config values imported from `config.py`

### Testing Layout (Sprint 2)
```
tests/
  test_signal_engine.py    # unit tests with synthetic OHLCV DataFrames
  test_paper_trader.py     # mock Binance + DB; test signal→order lifecycle
  test_backtester.py       # regression: known data → known equity curve
  test_ta_features.py      # verify indicator math against known values
```
Use `pytest-asyncio` for async test cases. Mock Binance with `unittest.mock.AsyncMock`.

### Libraries to Add (progressively per sprint)
```
python-dotenv   # Sprint 0 — .env credential loading
pandas-ta       # Sprint 4 — more indicators, faster than `ta`
vectorbt        # Sprint 8 — vectorized backtesting + walk-forward
structlog       # Sprint 7 — structured logging
pytest-asyncio  # Sprint 2 — async test support
ccxt            # Sprint 6+ — multi-exchange support
```

---

## Pre-Live Checklist
- [ ] Credentials in `.env` (Sprint 0)
- [ ] Backtester fixed and validated (Sprint 0)
- [ ] ATR-based position sizing (Sprint 3)
- [ ] Daily loss limit + drawdown circuit breaker (Sprint 3)
- [ ] Test suite passing (Sprint 2)
- [ ] Knowledge base initialized with baseline (Sprint 1)
- [ ] 30+ days paper trading with positive Sharpe (post Sprint 8)
