# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | GitHub Copilot |
| **Last updated** | 2026-04-17 (Sprint 11 closed) |
| **Sprint completed** | Sprint 11 ✅ — committed + pushed to GitHub |
| **Next sprint** | Sprint 12 — Live Promotion Coordinator |
| **Blocking issues** | Add one of: `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, or `OPENROUTER_API_KEY` to `.env` for LLM features |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Sprint 11 complete |

---

## Resume Here — Sprint 12: Live Promotion Coordinator

**Sprint 11 complete.** Self-learning loop is live. 334 tests passing.

### What was done in Sprint 11
- `llm/confidence_gate.py` — five-gate evaluator (Sharpe, max DD, profit factor, LLM confidence, trailing trend); returns `GateResult` dataclass
- `llm/self_learner.py` — `SelfLearner` class: `run_loop()` async task, `evaluate()` cycle, `confidence_gate_passed()`, `_write_kb_entry()`; pure metric helpers `_metrics_from_pnls`, `_zero_metrics`
- `simulator/paper_trader.py` — added `_coordinator`, `_last_regime`; fires `_fire_critique` via `asyncio.create_task()` after every SELL when `LLM_ENABLED=True`; module-level `_fire_critique` coroutine (never raises)
- 39 new tests → **334 total passing**

### Sprint 12 Goal — Live Promotion Coordinator
Wire `SelfLearner` into `run_live.py` as a background asyncio task.
Add a `Coordinator` class that:
- Starts `SelfLearner.run_loop()` on bot startup
- Watches `SelfLearner.confidence_gate_passed()` and logs a promotion event
- Writes a promotion record to a new `promotions` table (or KB file)
- Sends a Telegram alert when the gate first flips True

### Key files for Sprint 12
- `run_live.py` — add `SelfLearner` task to the asyncio gather
- `simulator/coordinator.py` (new) — wraps `SelfLearner`, watches gate, logs promotion
- `database/models.py` — optional: add `Promotion` table to record promotion events
- `tests/test_coordinator.py` — unit tests for coordinator logic

### Step 1 — Verify baseline
```bash
cd D:\trader\crypto_ai_trader
pytest tests/ -q   # must show 334 passed
```

## Resume Here — Sprint 10: LLM Core Layer

**Sprint 9 complete.** Strategy plugin system is live. 245 tests passing.

### What was done in Sprint 9
- `strategy/base.py` — `StrategyBase` ABC with `should_long/short + evaluate()` (regime-gated, not overridable)
- `strategies/loader.py` — hot-reload engine (watchdog file watcher + compile/exec bypass of pyc cache)
- `strategies/example_rsi_mean_reversion.py` — reference plugin translating existing mean-reversion logic
- `config.py` — LLM config section (`ANTHROPIC_API_KEY`, `LLM_MODEL`, `LLM_ENABLED`, `LLM_CONFIDENCE_GATE`, `validate_env_llm()`)
- `requirements.txt` — added `anthropic>=0.25.0`, `watchdog>=4.0.0`
- `docs/architecture.html` — full system architecture + Jesse-AI comparison document
- 32 new tests: `test_strategy_base.py` (18) + `test_strategy_loader.py` (14)

### Sprint 10 Goal — `llm/` package
Build the Claude API wrapper with TTL cache, strategy generator, backtest analyzer, and trade critiquer.

**Key files to create:**
- `llm/__init__.py`
- `llm/cache.py` — thread-safe TTL cache (5-min minimum, SHA-256 keyed)
- `llm/client.py` — Anthropic SDK wrapper, prompt caching, fallback to heuristic
- `llm/prompts.py` — all 4 system prompt templates as module-level constants
- `llm/generator.py` — NL → Python strategy, AST validate, write to `strategies/`
- `llm/analyzer.py` — backtest metrics → JSON (param suggestions + confidence score)
- `llm/critiquer.py` — trade critique after SELL (GOOD/MEDIOCRE/BAD)

**Pre-requisite:** Add `ANTHROPIC_API_KEY=sk-ant-...` to `.env` (Sprint 10 needs it for integration testing; tests themselves mock the client)

### How to start Sprint 10
```bash
# Verify 245 tests still pass
pytest tests/ -v
# Check new plugin system works
python -c "from strategies.loader import list_strategies; print(list_strategies())"
# Begin Sprint 10: create llm/ package
```

## Resume Here — Start Paper Trading

**All 8 sprints done. Hummingbot integration complete. Dashboard UX fixed.** The bot is ready to run.

### Pre-Live Checklist Status
- [x] Credentials in `.env` (Sprint 0)
- [x] Backtester fixed and validated (Sprint 0)
- [x] ATR-based position sizing (Sprint 3)
- [x] Daily loss limit + drawdown circuit breaker (Sprint 3)
- [x] Test suite passing — 213 tests (Sprint 2+8)
- [x] Knowledge base initialized (Sprint 1+)
- [x] Walk-forward validation with acceptance gates (Sprint 8)
- [x] Hummingbot ScriptStrategy wrapping signal_engine (Hummingbot sprint)
- [x] Dashboard overlay toggles persist across auto-refresh (UX fix)
- [ ] **30+ days paper trading with positive Sharpe** — this is the remaining gate

### How to Start Paper Trading (no Docker needed)

**Terminal 1 — the trading bot:**
```bash
cd D:\trader\crypto_ai_trader
python run_live.py
```

**Terminal 2 — the live dashboard:**
```bash
cd D:\trader\crypto_ai_trader
streamlit run dashboard/streamlit_app.py
# Open browser: http://localhost:8501
```

### Dashboard Features (after UX fix)
- Sidebar overlay checkboxes (Candlesticks, BB, EMA 9/21/55, EMA 200, Trade Markers) — all persist across auto-refresh
- Live countdown timer `⏱ Auto-refresh in 14s` instead of frozen blank screen
- Unchecking OHLC switches to a clean line chart (no blank chart)
- Symbol selector, timeframe buttons, regime badge, RSI/ADX/BB metrics all persist

### Hummingbot (optional — Docker required)
Docker Desktop needs `HypervisorPlatform` Windows feature enabled + PC restart.
After Docker works:
```bash
cd hummingbot_integration
docker compose build && docker compose up -d
docker attach hummingbot_crypto_ai
# Inside CLI: connect binance_paper_trade → start --script crypto_ai_trader_strategy.py
```

### Files Changed This Session
- `dashboard/streamlit_app.py` — overlay checkboxes backed by session_state; countdown timer; line chart fallback
- `hummingbot_integration/scripts/crypto_ai_trader_strategy.py` — Hummingbot ScriptStrategy
- `hummingbot_integration/Dockerfile` + `docker-compose.yml` — container setup
- `hummingbot_integration/conf/connectors/binance_paper_trade.yml.template`

---

## Sprint History

| Sprint | Status | Closed by | Date |
|--------|--------|-----------|------|
| Sprint 0 — Foundation fixes + credentials | ✅ CLOSED | Claude Code | 2026-04-16 |
| Sprint 1 — Knowledge base kb_update.py | ✅ CLOSED | GitHub Copilot | 2026-04-16 |
| Sprint 2 — Testing infrastructure | ✅ CLOSED | GitHub Copilot | 2026-04-16 |
| Sprint 3 — Risk management overhaul | ✅ CLOSED | GitHub Copilot | 2026-04-16 |
| Sprint 4 — Signal quality improvements | ✅ CLOSED | Claude Code | 2026-04-17 |
| Sprint 5 — Regime detection | ✅ CLOSED | Claude Code | 2026-04-17 |
| Sprint 6 — Multi-strategy portfolio | ✅ CLOSED | GitHub Copilot | 2026-04-17 |
| Sprint 7 — Dashboard fixes + observability | ✅ CLOSED | GitHub Copilot | 2026-04-17 |
| Sprint 8 — Backtesting rigor | ✅ CLOSED | GitHub Copilot | 2026-04-18 |
| Sprint 9 — Strategy Plugin System + StrategyBase ABC | ✅ CLOSED | Claude Code | 2026-04-17 |
| Sprint 10 — LLM Core Layer (multi-provider) | ✅ CLOSED | Claude Code | 2026-04-17 |
| Sprint 11 — Self-Learning Loop + KB Integration | ✅ CLOSED | GitHub Copilot | 2026-04-17 |

---

## Agent Protocol

### When you START a session:
1. Read this file
2. Read `knowledge/sprint_log.md`
3. Read any KB files relevant to the sprint goal
4. Begin work on the "Resume Here" sprint

### When you END a session (or hit rate limit / cooldown):
1. Update the **Current State** table above (agent name, date, sprint completed/in-progress)
2. Update **Resume Here** with the exact task the next agent should pick up
3. Note any blockers or partial work in a `## In Progress` section below if mid-sprint
4. Update `knowledge/sprint_log.md` with what was done this session

### Handoff note format (add below if mid-sprint):
```markdown
## In Progress — [AGENT NAME] left off here

**Sprint:** Sprint N
**Last file edited:** path/to/file.py
**What was done:** (1-2 sentences)
**What's next:** (exact next step for the incoming agent)
**Partial work notes:** (anything the next agent needs to know)
```

---

## Tech Stack Quick Reference

| Layer | Tech |
|-------|------|
| Language | Python 3.10+ |
| Exchange | python-binance (async) |
| DB | SQLite + SQLAlchemy 2.x |
| Data | pandas, numpy |
| Indicators | ta library |
| Dashboard | Streamlit + Plotly |
| Messaging | Telegram Bot API |
| Async | asyncio, aiosqlite |
| Credentials | python-dotenv (.env file) |

**Run:**
```bash
pip install -r requirements.txt
python run_live.py          # live paper trading
streamlit run dashboard/streamlit_app.py
python run_backtest.py BTCUSDT 2024-01-01 2024-03-31
```
