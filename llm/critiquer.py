"""llm/critiquer.py — Critique individual paper/live trades after execution.

Called by PaperTrader._auto_sell() after every completed round-trip.
Rate-limited via the TTL cache in llm/cache.py (5-min minimum per identical trade
context) — so two similar BTCUSDT sells in the same regime within 5 min share one
LLM call rather than triggering two.

Falls back gracefully: verdict = GOOD if pnl > 0, BAD otherwise.
"""

import json
import logging
import re
from dataclasses import dataclass

from llm.client import call_llm
from llm.prompts import TRADE_CRITIQUER_SYSTEM

log = logging.getLogger(__name__)


@dataclass
class TradeVerdict:
    verdict: str        # GOOD | MEDIOCRE | BAD
    reasoning: str
    improvement: str
    fallback: bool = False


_VALID_VERDICTS = {"GOOD", "MEDIOCRE", "BAD"}


def critique_trade(
    symbol: str,
    side: str,            # BUY or SELL
    entry_price: float,
    exit_price: float,
    pnl_pct: float,
    regime: str,
    signal_conditions: dict,
) -> TradeVerdict:
    """Ask the LLM to evaluate a completed trade.

    The TTL cache means identical (symbol, regime, rough P&L) contexts within
    the cache window will reuse the same critique — intentional, as back-to-back
    similar trades in the same regime should get the same feedback.

    Args:
        symbol:            e.g. "BTCUSDT"
        side:              "BUY" or "SELL"
        entry_price:       Fill price at entry
        exit_price:        Fill price at exit
        pnl_pct:           Round-trip P&L as percentage (positive = profit)
        regime:            Regime string at entry ("RANGING", "TRENDING", etc.)
        signal_conditions: Dict of indicator values that triggered the signal
    """
    user_prompt = f"""Trade completed:
  Symbol:    {symbol}
  Side:      {side}
  Entry:     {entry_price:.4f}
  Exit:      {exit_price:.4f}
  P&L:       {pnl_pct:+.2f}%
  Regime:    {regime}
  Conditions that fired: {json.dumps(signal_conditions, default=str)}

Evaluate this trade. Output JSON only."""

    response = call_llm(TRADE_CRITIQUER_SYSTEM, user_prompt, max_tokens=256)

    if response.fallback:
        verdict_str = "GOOD" if pnl_pct >= 0 else "BAD"
        return TradeVerdict(
            verdict=verdict_str,
            reasoning="LLM unavailable — verdict based on P&L sign only.",
            improvement="Enable LLM for detailed critique.",
            fallback=True,
        )

    return _parse_verdict(response.content, pnl_pct)


def _parse_verdict(raw: str, pnl_pct: float) -> TradeVerdict:
    """Parse JSON verdict from LLM response."""
    cleaned = re.sub(r"^```(?:json)?\n?", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned.strip(), flags=re.MULTILINE)
    try:
        data = json.loads(cleaned)
        verdict = data.get("verdict", "MEDIOCRE").upper()
        if verdict not in _VALID_VERDICTS:
            verdict = "MEDIOCRE"
        return TradeVerdict(
            verdict=verdict,
            reasoning=str(data.get("reasoning", ""))[:300],
            improvement=str(data.get("improvement", ""))[:200],
        )
    except (json.JSONDecodeError, KeyError) as exc:
        log.warning("trade critique parse failed", extra={"error": str(exc)})
        return TradeVerdict(
            verdict="GOOD" if pnl_pct >= 0 else "BAD",
            reasoning=raw[:200],
            improvement="",
            fallback=True,
        )
