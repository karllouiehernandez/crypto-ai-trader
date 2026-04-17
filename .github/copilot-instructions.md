# GitHub Copilot Workspace Instructions

This project is a Python async cryptocurrency paper trading bot.
It is developed in **sprints** and shared between **Claude Code** and **GitHub Copilot Pro** agents.

## ⚡ ALWAYS START HERE

Before doing anything, read these two files in order:
1. `HANDOFF.md` — current sprint, current task, and exact resume point
2. `knowledge/sprint_log.md` — full sprint history and what was completed last

Do not write any code until you have read both files.

---

## Project Commands

```bash
pip install -r requirements.txt
python run_live.py                                    # live paper trading
python run_backtest.py BTCUSDT 2024-01-01 2024-03-31  # backtest
streamlit run dashboard/streamlit_app.py              # dashboard
pytest tests/                                         # tests (Sprint 2+)
```

---

## Architecture

Fully async Python (`asyncio`). Three modes: live trading, backtesting, dashboard.

### Key Files
| File | Role |
|------|------|
| `config.py` | All runtime config; credentials via `.env` (see `.env.example`) |
| `run_live.py` | Entry point: loads history → streams → paper trades |
| `run_backtest.py` | CLI backtest entry point |
| `database/models.py` | SQLAlchemy ORM: `Candle`, `Trade`, `Portfolio` |
| `strategy/signal_engine.py` | Core signal: `compute_signal(sess, candle) → Signal` |
| `strategy/base.py` | **NEW (Sprint 9)** `StrategyBase` ABC — base class for all plugins |
| `strategy/ta_features.py` | Pure indicator functions (RSI, BB, MACD, SMA) |
| `strategies/loader.py` | **NEW (Sprint 9)** Hot-reload plugin engine (watchdog + compile/exec) |
| `strategies/` | **NEW (Sprint 9)** Drop `.py` files here to hot-load strategies automatically |
| `simulator/paper_trader.py` | Async paper trading loop |
| `backtester/engine.py` | Sync backtesting loop |
| `collectors/historical_loader.py` | One-time 365-day candle fetch from Binance |
| `collectors/live_streamer.py` | 1-second price polling loop |
| `utils/telegram_utils.py` | Telegram alerts + callback queue |
| `dashboard/streamlit_app.py` | Streamlit + Plotly live dashboard |
| `docs/architecture.html` | **NEW (Sprint 9)** Full architecture + Jesse-AI comparison (open in browser) |

### Critical Rules
- `strategy/` files must be **pure functions** — no DB calls, no I/O
- `collectors/` is the only layer that talks to Binance API
- All DB access uses `async with AsyncSession` (or `with SessionLocal()` in sync code)
- All external calls need `asyncio.wait_for()` / retry logic
- Credentials always via `os.environ.get()` — never hardcoded

---

## Sprint Workflow

Every sprint follows this loop — **never skip a step**:
```
1. Read HANDOFF.md + sprint_log.md
2. Read relevant knowledge/ files for context
3. Implement only what the sprint specifies (no scope creep)
4. Review all changed files against these criteria:
   - CORRECTNESS: logic bugs, wrong arg order, indentation
   - SECURITY: no hardcoded credentials
   - ASYNC SAFETY: no blocking calls in async context
   - TRADING LOGIC: position sizing math, fee application, signal conditions
   - KNOWLEDGE BASE: KB files updated?
5. Fix all CRITICAL and HIGH issues before marking sprint done
6. Update HANDOFF.md and knowledge/sprint_log.md
```

### Sprint Map
| Sprint | Goal | Status |
|--------|------|--------|
| 0 | Foundation fixes + credentials | ✅ CLOSED |
| 1 | Knowledge base `kb_update.py` script | ✅ CLOSED |
| 2 | Testing infrastructure (`pytest`) | ✅ CLOSED |
| 3 | Risk management (ATR sizing, circuit breakers) | ✅ CLOSED |
| 4 | Signal quality (trend filter, multi-timeframe, volume) | ✅ CLOSED |
| 5 | Regime detection | ✅ CLOSED |
| 6 | Multi-strategy portfolio | ✅ CLOSED |
| 7 | Dashboard fixes + observability | ✅ CLOSED |
| 8 | Backtesting rigor (walk-forward) | ✅ CLOSED |
| 9 | Strategy Plugin System + StrategyBase ABC | ✅ CLOSED |
| 10 | LLM Core Layer (`llm/` package) | ⬅ NEXT |
| 11 | Self-Learning Loop + KB Integration | PENDING |
| 12 | Multi-Agent Token Monitor | PENDING |
| 13 | Dashboard Extensions + End-to-End Integration | PENDING |

### New Entry Points (Sprint 9+)
```bash
# Plugin system — list loaded strategies
python -c "from strategies.loader import list_strategies; print(list_strategies())"

# Multi-agent mode (Sprint 12)
python run_agents.py
python run_agents.py --strategy rsi_mean_reversion_v1
python run_agents.py --learn   # enables 24h self-learning loop
```

### Strategy Plugin System (Sprint 9)
To add a new strategy:
1. Create a `.py` file in `strategies/`
2. Subclass `StrategyBase` from `strategy.base`
3. Implement `should_long(df)` and `should_short(df)` — pure DataFrame logic, no I/O
4. Set `name`, `version`, `regimes` class attributes
5. File is hot-loaded automatically (watchdog). No restart needed.

```python
from strategy.base import StrategyBase
from strategy.regime import Regime

class MyStrategy(StrategyBase):
    name = "my_strategy_v1"
    version = "1.0.0"
    regimes = [Regime.TRENDING]   # [] = active in all regimes

    def should_long(self, df):
        return df.iloc[-1]["rsi_14"] < 30

    def should_short(self, df):
        return df.iloc[-1]["rsi_14"] > 70
```

### LLM Config Keys (Sprint 9+, in `.env`)
```
ANTHROPIC_API_KEY=sk-ant-...      # Required for Sprint 10+
LLM_MODEL=claude-sonnet-4-6
LLM_ENABLED=true
LLM_CONFIDENCE_GATE=0.80
LLM_PAPER_WINDOW_DAYS=30
LLM_AUTO_PROMOTE=false
```

---

## Knowledge Base

All learnings live in `knowledge/`. Read before changing anything. Update after every sprint.

| File | Read when |
|------|-----------|
| `knowledge/sprint_log.md` | Always first |
| `knowledge/bugs_and_fixes.md` | Before touching any fixed file |
| `knowledge/strategy_learnings.md` | Before any strategy change |
| `knowledge/parameter_history.md` | Before changing any config value |
| `knowledge/experiment_log.md` | Before running any experiment |

KB entry format (use for every new finding):
```markdown
## [DATE] [TOPIC] — [ONE LINE SUMMARY]
**What happened:**
**Why it happened:**
**Impact:**
**What we changed:**
**What to try next:**
**Status:** [OPEN | FIXED | MONITORING]
```

---

## Crypto Strategy Reference

### Current Signal Logic (`strategy/signal_engine.py`)
- **BUY**: RSI-14 < 35 AND close < BB-lower AND MACD bullish crossover
- **SELL**: RSI-14 > 70 AND close > BB-upper AND MACD bearish crossover
- Requires 60+ candles; returns HOLD otherwise

### Planned Improvements (future sprints)
- Sprint 4: Add 200 EMA trend filter + volume confirmation
- Sprint 5: ADX regime gate (only mean reversion when ADX < 20)
- Sprint 6: Add momentum strategy (EMA crossover when ADX > 25)

### Risk Rules (non-negotiable — implement in Sprint 3)
- Max 1-2% equity risk per trade (current 20% flat is too large)
- ATR position sizing: `size = (equity × 0.01) / (1.5 × ATR)`
- Daily loss limit: halt if down 3% on the day
- Drawdown circuit breaker: halt if equity drops 15% from peak

---

## Pre-Live Checklist
- [x] Credentials in `.env`
- [x] Backtester working
- [ ] ATR-based position sizing (Sprint 3)
- [ ] Daily loss limit + circuit breaker (Sprint 3)
- [ ] Tests passing (Sprint 2)
- [ ] 30+ days paper trading positive Sharpe
