# Parameter History

Changelog of every configuration and strategy parameter change.
Before changing any parameter, read this file to avoid re-testing known bad values.

---

## Baseline State — 2026-04-16

Initial parameter snapshot from `config.py` at project start. No changes have been made yet.

| Parameter | Value | Location | Notes |
|-----------|-------|----------|-------|
| `SYMBOLS` | `["BTCUSDT", "ETHUSDT", "BNBUSDT"]` | `config.py` | 3 pairs; all Binance USDT pairs |
| `BINANCE_TESTNET` | `True` | `config.py` | Paper trading only — no real orders |
| `STARTING_BALANCE_USD` | `100.0` | `config.py` | Initial paper trading balance |
| `MAX_POS_PCT` | `0.20` | `config.py` | Max 20% of equity in any one position |
| `POSITION_SIZE_PCT` | `0.30` | `config.py` | 30% of cash per trade — **known issue**: too large, ignores volatility. Sprint 3 replaces with ATR sizing |
| `FEE_RATE` | `0.001` | `config.py` | 0.1% per trade (Binance taker fee) |
| `LIVE_POLL_SECONDS` | `1` | `config.py` | Price poll interval in seconds |
| `HIST_INTERVAL` | `"1m"` | `config.py` | Candle resolution for historical data |
| `RSI_PERIOD` | `14` | `strategy/ta_features.py` | RSI lookback window |
| `BB_PERIOD` | `20` | `strategy/ta_features.py` | Bollinger Band window |
| `SMA_FAST` | `21` | `strategy/ta_features.py` | Fast SMA period |
| `SMA_SLOW` | `55` | `strategy/ta_features.py` | Slow SMA period |
| `MIN_CANDLES` | `60` | `strategy/signal_engine.py` | Minimum candles required to compute a signal (1 hour of 1m data) |
| `RSI_OVERSOLD` | `35` | `strategy/signal_engine.py` | RSI threshold for buy signal — **note**: standard oversold is 30; 35 may be too loose |
| `RSI_OVERBOUGHT` | `70` | `strategy/signal_engine.py` | RSI threshold for sell signal |

---

## Change Log

---

## 2026-04-17 — MIN_CANDLES (signal_engine.py guard)
**Old value:** 60
**New value:** 210 (via `config.MIN_CANDLES_EMA200`)
**Reason:** EMA-200 requires 200 rows of warmup before producing a non-NaN value. With the previous guard of 60, `add_indicators` would return an empty DataFrame (all rows NaN-dropped) and the engine would crash on `iloc[-2]`.
**Expected effect:** Signals only fire when sufficient history exists for EMA-200; eliminates empty-DataFrame crash.
**Sprint:** Sprint 4
**Result:** Pending backtest validation.

---

## 2026-04-17 — EMA_LOOKBACK (new parameter)
**Old value:** N/A (hardcoded 120 in `_fetch_recent_candles`)
**New value:** 220 (via `config.EMA_LOOKBACK`)
**Reason:** 220 raw 1m candles → ~20 post-warmup rows after EMA-200 dropna. Provides enough rows for both `iloc[-1]` and `iloc[-2]` with comfortable margin.
**Expected effect:** Stable EMA-200 computation on every signal call.
**Sprint:** Sprint 4
**Result:** Pending backtest validation.

**Design note — 1m vs 1h EMA-200:** The spec calls for a 200-period EMA on the 1h chart (8.3 days of context). The current implementation computes it on 1m candles (3.3 hours). This is a deliberate Sprint 4 simplification — the system only collects 1m data. A proper 1h EMA-200 requires ~12,000 1m candles or a separate 1h data feed. Multi-timeframe data support is deferred to Sprint 5/6. The 1m EMA-200 still provides trend context but at a much shorter horizon; it will suppress fewer trades than the intended 1h version.

---

## 2026-04-17 — VOLUME_CONFIRMATION_MULT (new parameter)
**Old value:** N/A (no volume gate existed)
**New value:** 1.5 (via `config.VOLUME_CONFIRMATION_MULT`)
**Reason:** Filters low-conviction entries where entry volume is below 1.5× the 20-period volume average. Aligns with CLAUDE.md signal quality spec.
**Expected effect:** Reduces false breakout entries; may reduce overall trade frequency.
**Sprint:** Sprint 4
**Result:** Pending backtest validation.

### Entry Format
```markdown
## [DATE] — [PARAMETER NAME]
**Old value:** X
**New value:** Y
**Reason:** (why this was changed)
**Expected effect:** (what we expect to improve)
**Sprint:** Sprint N
**Result:** (fill in after observing outcome)
```
