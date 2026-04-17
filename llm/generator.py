"""llm/generator.py — Generate Python strategy code from natural language.

Workflow:
  1. Build user prompt from description + symbol + regime hint
  2. Call LLM with STRATEGY_GENERATOR_SYSTEM (cached server-side)
  3. Strip markdown fences if LLM wrapped output
  4. AST-validate the code (no exec — just syntax check)
  5. If valid, write to strategies/generated_{timestamp}.py
  6. strategies/loader.py watchdog picks it up and hot-loads it automatically

Returns (code_str | None, LLMResponse).
code_str is None if generation failed, LLM unavailable, or syntax invalid.
"""

import ast
import logging
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from llm.client import LLMResponse, call_llm
from llm.prompts import STRATEGY_GENERATOR_SYSTEM

log = logging.getLogger(__name__)

STRATEGIES_DIR = Path(__file__).resolve().parent.parent / "strategies"


def generate_strategy(
    description: str,
    symbol: str = "BTCUSDT",
    regime_hint: str = "any",
    save: bool = True,
) -> tuple[Optional[str], LLMResponse]:
    """Generate a Python strategy file from a natural language description.

    Args:
        description:  Natural language strategy idea.
        symbol:       Primary trading pair (informational, passed to LLM).
        regime_hint:  Market regime this strategy targets (informational).
        save:         If True and code is valid, write to strategies/ directory.

    Returns:
        (python_code | None, LLMResponse)
    """
    user_prompt = textwrap.dedent(f"""
        Generate a Python strategy file for the crypto_ai_trader system.

        Description: {description}
        Primary symbol: {symbol}
        Target regime: {regime_hint}

        Remember:
        - Subclass StrategyBase from strategy.base
        - Set name (snake_case, ends with _v1+), version, regimes
        - Implement should_long(df) and should_short(df) returning bool
        - Use only the indicator columns documented in the system prompt
        - Output Python source code ONLY — no markdown, no explanations
    """).strip()

    response = call_llm(STRATEGY_GENERATOR_SYSTEM, user_prompt)

    if response.fallback or not response.content.strip():
        log.warning("strategy generation failed — LLM unavailable or empty response")
        return None, response

    code = _strip_fences(response.content)

    if not _is_valid_python(code):
        log.error("generated strategy failed syntax validation")
        return None, response

    if save:
        _save(code)

    return code, response


# ── Helpers ────────────────────────────────────────────────────────────────

def _strip_fences(raw: str) -> str:
    """Remove markdown code fences if the LLM wrapped output despite instructions."""
    cleaned = re.sub(r"^```(?:python)?\n?", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned.strip(), flags=re.MULTILINE)
    return cleaned.strip()


def _is_valid_python(code: str) -> bool:
    """AST-parse the code to check syntax without executing it."""
    try:
        ast.parse(code)
        return True
    except SyntaxError as exc:
        log.warning("generated code syntax error", extra={"error": str(exc)})
        return False


def _save(code: str) -> Path:
    """Write code to strategies/generated_{timestamp}.py and return the path."""
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = STRATEGIES_DIR / f"generated_{ts}.py"
    path.write_text(code, encoding="utf-8")
    log.info("strategy saved", extra={"path": str(path)})
    return path
