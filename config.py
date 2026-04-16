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
POSITION_SIZE_PCT    = 0.20   # fraction of free cash per trade (Sprint 3 replaces with ATR sizing)
FEE_RATE             = 0.001  # 0.1% trading fee
PORTFOLIO_SNAP_MIN   = 1      # write equity snapshot every minute
