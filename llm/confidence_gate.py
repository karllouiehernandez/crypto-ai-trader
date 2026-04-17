"""llm/confidence_gate.py — Five-gate promotion evaluator.

All five gates must pass before a strategy is eligible for live promotion.
Used by SelfLearner to decide whether paper-trading results are strong enough
to warrant a PROMOTE_TO_LIVE recommendation.

Gates:
    1. sharpe_ok         — annualised Sharpe >= SHARPE_GATE (1.5)
    2. max_dd_ok         — peak-to-trough drawdown <= MAX_DD_GATE (20%)
    3. profit_factor_ok  — gross profit / gross loss >= PROFIT_FACTOR_GATE (1.5)
    4. llm_confidence_ok — LLM confidence score >= LLM_CONFIDENCE_GATE (0.80)
    5. trend_ok          — last 3 consecutive evaluations all returned PROMOTE_TO_LIVE
"""

from __future__ import annotations

from dataclasses import dataclass, field

from config import LLM_CONFIDENCE_GATE, MAX_DD_GATE, PROFIT_FACTOR_GATE, SHARPE_GATE

_PROMOTE = "PROMOTE_TO_LIVE"
_TREND_REQUIRED = 3   # consecutive PROMOTE_TO_LIVE needed before trend_ok passes


@dataclass
class GateResult:
    """Result of running all five promotion gates."""

    passed: bool
    failures: list[str] = field(default_factory=list)

    # Individual gate outcomes (all must be True for passed=True)
    sharpe_ok:         bool = False
    max_dd_ok:         bool = False
    profit_factor_ok:  bool = False
    llm_confidence_ok: bool = False
    trend_ok:          bool = False


def evaluate_gate(
    metrics: dict,
    llm_confidence: float,
    trailing_recommendations: list[str],
) -> GateResult:
    """Evaluate all five promotion gates against current metrics.

    Args:
        metrics:
            Dict with at least these keys (all numeric):
              - sharpe          : annualised Sharpe ratio
              - max_drawdown    : peak-to-trough drawdown as a fraction (e.g. 0.12 = 12%)
              - profit_factor   : gross profit / gross loss
        llm_confidence:
            Float 0–1 confidence score from ``analyze_backtest()["confidence_score"]``.
        trailing_recommendations:
            List of recent ``recommendation`` strings from past ``analyze_backtest()``
            calls, ordered oldest → newest. Only the last ``_TREND_REQUIRED`` entries
            are examined.

    Returns:
        :class:`GateResult` with ``passed=True`` only when all five gates pass.
    """
    failures: list[str] = []

    sharpe        = float(metrics.get("sharpe", 0.0))
    max_dd        = float(metrics.get("max_drawdown", 1.0))
    profit_factor = float(metrics.get("profit_factor", 0.0))

    sharpe_ok = sharpe >= SHARPE_GATE
    if not sharpe_ok:
        failures.append(
            f"sharpe {sharpe:.3f} < required {SHARPE_GATE:.3f}"
        )

    max_dd_ok = max_dd <= MAX_DD_GATE
    if not max_dd_ok:
        failures.append(
            f"max_drawdown {max_dd:.1%} > limit {MAX_DD_GATE:.1%}"
        )

    profit_factor_ok = profit_factor >= PROFIT_FACTOR_GATE
    if not profit_factor_ok:
        failures.append(
            f"profit_factor {profit_factor:.3f} < required {PROFIT_FACTOR_GATE:.3f}"
        )

    llm_confidence_ok = llm_confidence >= LLM_CONFIDENCE_GATE
    if not llm_confidence_ok:
        failures.append(
            f"llm_confidence {llm_confidence:.2f} < required {LLM_CONFIDENCE_GATE:.2f}"
        )

    # Trend gate: last _TREND_REQUIRED trailing recommendations must all be PROMOTE_TO_LIVE
    recent = (trailing_recommendations or [])[-_TREND_REQUIRED:]
    trend_ok = (
        len(recent) == _TREND_REQUIRED
        and all(r == _PROMOTE for r in recent)
    )
    if not trend_ok:
        n_promote = sum(1 for r in recent if r == _PROMOTE)
        failures.append(
            f"trend gate: only {n_promote}/{_TREND_REQUIRED} recent evals are PROMOTE_TO_LIVE"
        )

    passed = not failures

    return GateResult(
        passed=passed,
        failures=failures,
        sharpe_ok=sharpe_ok,
        max_dd_ok=max_dd_ok,
        profit_factor_ok=profit_factor_ok,
        llm_confidence_ok=llm_confidence_ok,
        trend_ok=trend_ok,
    )
