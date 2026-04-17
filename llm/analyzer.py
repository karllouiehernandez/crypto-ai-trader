"""llm/analyzer.py — Analyze backtest results and suggest parameter improvements.

Sends walk-forward metrics + KB context to the LLM and returns structured JSON:
  parameter_suggestions, strategy_weaknesses, confidence_score, recommendation.

Always includes acceptance_gate results regardless of LLM availability.
Falls back to a heuristic analysis (gate check only) when LLM is unavailable.
"""

import json
import logging
import re
from typing import Any

from backtester.metrics import acceptance_gate
from llm.client import call_llm
from llm.prompts import BACKTEST_ANALYZER_SYSTEM

log = logging.getLogger(__name__)

_FALLBACK: dict[str, Any] = {
    "parameter_suggestions": [],
    "strategy_weaknesses":   ["LLM unavailable — using acceptance gate only"],
    "confidence_score":      0.0,
    "recommendation":        "HOLD_PAPER",
    "fallback":              True,
}


def analyze_backtest(
    metrics: dict[str, float],
    walk_forward_results: list,
    strategy_name: str = "active_strategy",
    kb_context: str = "",
) -> dict[str, Any]:
    """Send backtest results to the LLM for analysis.

    Args:
        metrics:              Dict with keys: sharpe, max_drawdown, profit_factor, n_trades.
        walk_forward_results: List of per-window dicts from walk_forward().
        strategy_name:        Name for logging/KB purposes.
        kb_context:           Raw text from relevant KB files (trimmed to 3000 chars).

    Returns:
        Dict with keys: parameter_suggestions, strategy_weaknesses, confidence_score,
        recommendation, acceptance_gate_passed, acceptance_gate_failures, fallback.
    """
    passed, failures = acceptance_gate(metrics)

    user_prompt = f"""Strategy: {strategy_name}

Backtest metrics:
  Sharpe ratio:   {metrics.get('sharpe', 0):.3f}
  Max drawdown:   {metrics.get('max_drawdown', 0):.1%}
  Profit factor:  {metrics.get('profit_factor', 0):.3f}
  Trade count:    {int(metrics.get('n_trades', 0))}

Walk-forward windows ({len(walk_forward_results)} total):
{json.dumps(walk_forward_results, indent=2, default=str)[:2000]}

Acceptance gate: {"PASSED" if passed else "FAILED"}
Failures: {failures or "none"}

Knowledge base context (most recent learnings):
{kb_context[:3000] if kb_context else "(none provided)"}

Respond with JSON only."""

    response = call_llm(BACKTEST_ANALYZER_SYSTEM, user_prompt, max_tokens=1024)

    gate_fields = {
        "acceptance_gate_passed":   passed,
        "acceptance_gate_failures": failures,
    }

    if response.fallback:
        result = dict(_FALLBACK)
        result.update(gate_fields)
        return result

    parsed = _parse_json(response.content)
    if parsed is None:
        result = dict(_FALLBACK)
        result["raw_llm_output"] = response.content[:500]
        result.update(gate_fields)
        return result

    parsed["fallback"] = False
    parsed.update(gate_fields)
    log.info("backtest analysis complete",
             extra={"strategy": strategy_name,
                    "confidence": parsed.get("confidence_score", 0),
                    "recommendation": parsed.get("recommendation")})
    return parsed


def _parse_json(raw: str) -> dict | None:
    """Extract and parse JSON from LLM response, handling optional markdown fences."""
    cleaned = re.sub(r"^```(?:json)?\n?", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        log.warning("LLM returned non-JSON backtest analysis", extra={"error": str(exc)})
        return None
