# crypto_ai_trader/config.py
from pathlib import Path
from typing import List
import os
from dotenv import load_dotenv

load_dotenv()  # loads .env from project root (git-ignored)

# ─────────────────────────────────────────────────────────────────────────────
# ▓▓  File & DB locations
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parent
DATA_DIR  = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH   = DATA_DIR / "market_data.db"

# ─────────────────────────────────────────────────────────────────────────────
# ▓▓  Credentials — loaded from .env (see .env.example)
# ─────────────────────────────────────────────────────────────────────────────
BINANCE_API_KEY    = os.environ.get("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET", "")
BINANCE_TESTNET    = True        # keep True for paper trading

TELEGRAM_TOKEN      = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "")
ENABLE_TG_ALERTS    = True
ENABLE_TG_STREAM_ALERTS = False  # per-price pings

_REQUIRED_ENV_VARS = {
    "BINANCE_API_KEY": BINANCE_API_KEY,
    "BINANCE_API_SECRET": BINANCE_API_SECRET,
    "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
    "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
}

def validate_env():
    """Call at process startup to fail fast with a clear error if .env is missing."""
    missing = [k for k, v in _REQUIRED_ENV_VARS.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in your credentials."
        )

# ─────────────────────────────────────────────────────────────────────────────
# ▓▓  Symbols & polling intervals
# ─────────────────────────────────────────────────────────────────────────────
SYMBOLS: List[str] = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
HIST_INTERVAL      = "1m"   # candle interval for history
LIVE_POLL_SECONDS  = 1      # real-time ticker poll

# ─────────────────────────────────────────────────────────────────────────────
# ▓▓  Paper-trading parameters
# ─────────────────────────────────────────────────────────────────────────────
STARTING_BALANCE_USD = 100.0
POSITION_SIZE_PCT    = 0.20   # fallback flat fraction (overridden by ATR sizing in Sprint 3+)
FEE_RATE             = 0.001  # 0.1% trading fee
PORTFOLIO_SNAP_MIN   = 1      # write equity snapshot every minute

# ─────────────────────────────────────────────────────────────────────────────
# ▓▓  Risk management (Sprint 3)
# ─────────────────────────────────────────────────────────────────────────────
RISK_PCT_PER_TRADE   = 0.01   # max 1% of equity risked per trade (ATR sizing)
ATR_STOP_MULTIPLIER  = 1.5    # stop distance = ATR * this multiplier
DAILY_LOSS_LIMIT_PCT = 0.03   # halt trading if daily P&L < -3% of start-of-day equity
DRAWDOWN_HALT_PCT    = 0.15   # halt if equity drops 15% from peak

# ─────────────────────────────────────────────────────────────────────────────
# ▓▓  Signal quality (Sprint 4)
# ─────────────────────────────────────────────────────────────────────────────
EMA_LOOKBACK            = 220   # candles fetched; gives ~20 post-warmup rows for EMA-200
MIN_CANDLES_EMA200      = 210   # minimum raw candles required before computing a signal
VOLUME_CONFIRMATION_MULT = 1.5  # entry volume must be >= this × volume_ma_20

# ─────────────────────────────────────────────────────────────────────────────
# ▓▓  Regime detection (Sprint 5)
# ─────────────────────────────────────────────────────────────────────────────
ADX_TREND_THRESHOLD         = 25    # ADX > this → TRENDING; ADX ≤ 25 (incl. grey zone 20-25) → RANGING
BB_WIDTH_SQUEEZE_PERCENTILE = 20    # BB width below this percentile of available history → SQUEEZE
HIGH_VOL_MULTIPLIER         = 2.0   # recent vol > this × baseline vol → HIGH_VOL
HIGH_VOL_SHORT_WINDOW       = 10    # candles for recent-vol window (prototype uses 1m; production: ~30m)

# ─────────────────────────────────────────────────────────────────────────────
# ▓▓  Multi-strategy portfolio (Sprint 6)
# ─────────────────────────────────────────────────────────────────────────────
MOMENTUM_PULLBACK_TOL = 0.005  # close within 0.5% above EMA-21 counts as pullback entry
BREAKOUT_LOOKBACK     = 20     # periods to scan for prior high/low in breakout strategy
BREAKOUT_VOLUME_MULT  = 2.0    # breakout entry volume must be >= this × volume_ma_20
