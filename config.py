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

MVP_RESEARCH_UNIVERSE: List[str] = [
    symbol.strip().upper()
    for symbol in os.environ.get("MVP_RESEARCH_UNIVERSE", ",".join(SYMBOLS)).split(",")
    if symbol.strip()
]
MVP_FRESHNESS_MINUTES = int(os.environ.get("MVP_FRESHNESS_MINUTES", "10"))
MVP_MIN_HISTORY_DAYS  = int(os.environ.get("MVP_MIN_HISTORY_DAYS", "30"))

# Jetson Nano overrides — set via .env to reduce memory footprint
# MAX_SYMBOLS=1 limits to the first symbol; 0 = no limit (default)
_MAX_SYMBOLS = int(os.environ.get("MAX_SYMBOLS", "0"))
if _MAX_SYMBOLS > 0:
    SYMBOLS = SYMBOLS[:_MAX_SYMBOLS]

# DAYS_BACK controls how many days of 1m candles historical_loader fetches
# Set to 90 on Jetson for a faster cold start (~30 min vs ~2 hours for 365 days)
DAYS_BACK = int(os.environ.get("DAYS_BACK", "365"))

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
# ▓▓  LLM — Multi-provider (Sprint 10)
# Supported providers: anthropic | groq | openrouter
# ─────────────────────────────────────────────────────────────────────────────
LLM_PROVIDER          = os.environ.get("LLM_PROVIDER", "anthropic").lower()
LLM_ENABLED           = os.environ.get("LLM_ENABLED", "true").lower() == "true"
LLM_CACHE_TTL_SECONDS = int(os.environ.get("LLM_CACHE_TTL_SECONDS", "300"))   # 5-min minimum
LLM_MAX_TOKENS        = int(os.environ.get("LLM_MAX_TOKENS", "4096"))

# Provider API keys (only the one matching LLM_PROVIDER is required)
ANTHROPIC_API_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
GROQ_API_KEY          = os.environ.get("GROQ_API_KEY", "")
OPENROUTER_API_KEY    = os.environ.get("OPENROUTER_API_KEY", "")

# Model name — must match provider's model ID
# anthropic:   claude-sonnet-4-6
# groq:        llama-3.3-70b-versatile  (fast, generous free tier)
# openrouter:  anthropic/claude-sonnet-4-6  or  meta-llama/llama-3.3-70b-instruct
LLM_MODEL = os.environ.get("LLM_MODEL", _LLM_MODEL_DEFAULTS := {
    "anthropic":   "claude-sonnet-4-6",
    "groq":        "llama-3.3-70b-versatile",
    "openrouter":  "anthropic/claude-sonnet-4-6",
}.get(os.environ.get("LLM_PROVIDER", "anthropic").lower(), "claude-sonnet-4-6"))

# Self-learning loop
LLM_CONFIDENCE_GATE   = float(os.environ.get("LLM_CONFIDENCE_GATE", "0.80"))  # 0.0–1.0
LLM_PAPER_WINDOW_DAYS = int(os.environ.get("LLM_PAPER_WINDOW_DAYS", "30"))    # min days before promotion eval
LLM_AUTO_PROMOTE      = os.environ.get("LLM_AUTO_PROMOTE", "false").lower() == "true"

# Plugin strategy directory
STRATEGIES_DIR = BASE_DIR / "strategies"

# ─────────────────────────────────────────────────────────────────────────────
# ▓▓  Live trade gate (Sprint 13)
# Set LIVE_TRADE_ENABLED=true in .env ONLY after manual review of promotion event.
# When False (default) the bot runs in paper-trading mode regardless of gate state.
# ─────────────────────────────────────────────────────────────────────────────
LIVE_TRADE_ENABLED = os.environ.get("LIVE_TRADE_ENABLED", "false").lower() == "true"

# Provider base URLs (OpenAI-compatible endpoints for groq/openrouter)
_LLM_BASE_URLS = {
    "groq":       "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}
LLM_BASE_URL = _LLM_BASE_URLS.get(LLM_PROVIDER, "")


# ─────────────────────────────────────────────────────────────────────────────
# ▓▓  Weekly Market Focus Selector (Sprint 25)
# ─────────────────────────────────────────────────────────────────────────────
MARKET_FOCUS_UNIVERSE_SIZE = int(os.environ.get("MARKET_FOCUS_UNIVERSE_SIZE", "30"))
MARKET_FOCUS_TOP_N         = int(os.environ.get("MARKET_FOCUS_TOP_N", "5"))
MARKET_FOCUS_BACKTEST_DAYS = int(os.environ.get("MARKET_FOCUS_BACKTEST_DAYS", "30"))

# Stablecoins and wrapped tokens excluded from the research universe
_MARKET_FOCUS_EXCLUDE = {
    "USDCUSDT", "BUSDUSDT", "TUSDUSDT", "USDTUSDT", "DAIUSDT", "FDUSDUSDT",
    "WBTCUSDT", "STETHUSDT", "BTTCUSDT",
}

def check_available_memory_gb() -> float:
    """Return available RAM in GB. Returns -1.0 if psutil is unavailable."""
    try:
        import psutil
        return psutil.virtual_memory().available / (1024 ** 3)
    except ImportError:
        return -1.0


def validate_env_llm() -> None:
    """Validate that the active LLM provider has an API key in .env.
    Call at startup when LLM_ENABLED=True.
    """
    key_map = {
        "anthropic":  ANTHROPIC_API_KEY,
        "groq":       GROQ_API_KEY,
        "openrouter": OPENROUTER_API_KEY,
    }
    if not key_map.get(LLM_PROVIDER, ""):
        env_var = {"anthropic": "ANTHROPIC_API_KEY", "groq": "GROQ_API_KEY",
                   "openrouter": "OPENROUTER_API_KEY"}.get(LLM_PROVIDER, "LLM API key")
        raise RuntimeError(
            f"Missing {env_var} in .env for provider '{LLM_PROVIDER}'. "
            "Set LLM_ENABLED=false to run without LLM features."
        )
