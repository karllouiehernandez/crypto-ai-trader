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

_(No changes yet — add entries below as parameters are modified)_

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
