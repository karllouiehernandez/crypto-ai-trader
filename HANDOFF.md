# HANDOFF.md — Agent Resume Point

This file is the **single source of truth** for where development is right now.
Both Claude Code and GitHub Copilot Pro agents must read this file first and update it last.

---

## Current State

| Field | Value |
|-------|-------|
| **Last active agent** | GitHub Copilot |
| **Last updated** | 2026-04-17 (Dashboard UX fix) |
| **Sprint completed** | Dashboard UX Fix ✅ |
| **Next sprint** | Start 30-day paper trading run |
| **Blocking issues** | None — bot is ready to run |
| **GitHub repo** | https://github.com/karllouiehernandez/crypto-ai-trader |
| **GitHub Projects board** | https://github.com/users/karllouiehernandez/projects/1 |
| **Reason for handoff** | Switching to Claude Code |

---

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
