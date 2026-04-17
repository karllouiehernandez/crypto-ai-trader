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
# Live trading keys (BINANCE_API_KEY / BINANCE_API_SECRET)
BINANCE_API_KEY    = os.environ.get("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET", "")
BINANCE_TESTNET    = True        # keep True for paper trading

# Backtesting keys (separate testnet account — bkBINANCE_API_KEY / bkBINANCE_API_SECRET)
BK_BINANCE_API_KEY    = os.environ.get("bkBINANCE_API_KEY", "")
BK_BINANCE_API_SECRET = os.environ.get("bkBINANCE_API_SECRET", "")

TELEGRAM_TOKEN      = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "")
ENABLE_TG_ALERTS    = True
ENABLE_TG_STREAM_ALERTS = False  # per-price pings

def validate_env():
    """Validate credentials required for live trading (Binance + Telegram)."""
    required = {
        "BINANCE_API_KEY": BINANCE_API_KEY,
        "BINANCE_API_SECRET": BINANCE_API_SECRET,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in your credentials."
        )

def validate_env_backtest():
    """Validate credentials required for backtesting (bkBINANCE_API_KEY only, no Telegram needed)."""
    required = {
        "bkBINANCE_API_KEY": BK_BINANCE_API_KEY,
        "bkBINANCE_API_SECRET": BK_BINANCE_API_SECRET,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing backtest API credentials: {', '.join(missing)}\n"
            "Add bkBINANCE_API_KEY and bkBINANCE_API_SECRET to your .env file."
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
MOMENTUM_PULLBACK_TOL = 0.005  # momentum entry: close must be within 0.5% of EMA-21
BREAKOUT_LOOKBACK     = 20     # periods to scan for prior high/low in breakout strategy
BREAKOUT_VOLUME_MULT  = 2.0    # breakout entry volume must be >= this × volume_ma_20

# ─────────────────────────────────────────────────────────────────────────────
# ▓▓  Backtesting rigor (Sprint 8)
# ─────────────────────────────────────────────────────────────────────────────
SLIPPAGE_PCT        = 0.001   # 0.1% slippage per fill (in addition to fee)
WALK_FORWARD_MONTHS = 3       # window size for walk-forward (months)
WALK_FORWARD_TRAIN  = 0.70    # fraction of each window used as in-sample
MIN_TRADES_GATE     = 200     # minimum trades for acceptance gate
SHARPE_GATE         = 1.5     # minimum annualised Sharpe ratio
MAX_DD_GATE         = 0.20    # maximum peak-to-trough drawdown (fraction)
PROFIT_FACTOR_GATE  = 1.5     # minimum profit factor (gross profit / gross loss)

# ─────────────────────────────────────────────────────────────────────────────
# ▓▓  LLM / Claude API (Sprint 9+)
# ─────────────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL             = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
LLM_CACHE_TTL_SECONDS = int(os.environ.get("LLM_CACHE_TTL_SECONDS", "300"))   # 5-min minimum
LLM_ENABLED           = os.environ.get("LLM_ENABLED", "true").lower() == "true"
LLM_MAX_TOKENS        = int(os.environ.get("LLM_MAX_TOKENS", "4096"))

# Self-learning loop
LLM_CONFIDENCE_GATE   = float(os.environ.get("LLM_CONFIDENCE_GATE", "0.80"))  # 0.0–1.0
LLM_PAPER_WINDOW_DAYS = int(os.environ.get("LLM_PAPER_WINDOW_DAYS", "30"))    # min days before promotion eval
LLM_AUTO_PROMOTE      = os.environ.get("LLM_AUTO_PROMOTE", "false").lower() == "true"

# Plugin strategy directory
STRATEGIES_DIR = BASE_DIR / "strategies"


def validate_env_llm() -> None:
    """Validate credentials required for LLM features.
    Call at startup when LLM_ENABLED=True. Raises RuntimeError if key is missing.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "Missing ANTHROPIC_API_KEY in .env. "
            "Set LLM_ENABLED=false in .env to run without LLM features."
        )
