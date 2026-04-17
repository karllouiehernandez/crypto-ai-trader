"""llm/self_learner.py — Autonomous self-learning loop.

Runs as a background asyncio task. Every `interval_hours` it:
  1. Queries the Trade table for paper-trading metrics
     (last LLM_PAPER_WINDOW_DAYS days of completed round-trips)
  2. Reads knowledge/strategy_learnings.md as KB context
  3. Calls analyze_backtest() → LLM analysis dict
  4. Calls evaluate_gate() → GateResult
  5. Appends a structured entry to knowledge/experiment_log.md
  6. Returns the merged evaluation dict

After 3 consecutive cycles where recommendation == PROMOTE_TO_LIVE
the `confidence_gate_passed()` method returns True — the caller
(e.g. a future Sprint 12 coordinator) can then trigger live promotion.

No DB writes, no trading logic — pure observation + KB writing.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config import (
    BASE_DIR,
    LLM_ENABLED,
    LLM_PAPER_WINDOW_DAYS,
    STARTING_BALANCE_USD,
)
from database.models import SessionLocal, Trade
from llm.analyzer import analyze_backtest
from llm.confidence_gate import GateResult, evaluate_gate

log = logging.getLogger(__name__)

_KB_DIR          = BASE_DIR / "knowledge"
_EXPERIMENT_LOG  = _KB_DIR / "experiment_log.md"
_STRATEGY_KB     = _KB_DIR / "strategy_learnings.md"
_PROMOTE         = "PROMOTE_TO_LIVE"
_TREND_REQUIRED  = 3   # consecutive PROMOTE_TO_LIVE to flip confidence_gate_passed()


class SelfLearner:
    """Periodic self-evaluation loop that closes the paper → KB feedback cycle.

    Usage::

        learner = SelfLearner(interval_hours=24)
        asyncio.create_task(learner.run_loop())
    """

    def __init__(self, interval_hours: int = 24) -> None:
        self._interval    = interval_hours * 3600   # convert to seconds
        self._history:    list[str] = []            # recommendation strings, oldest first
        self._eval_count: int = 0

    # ── Public API ─────────────────────────────────────────────────────────────

    async def run_loop(self) -> None:
        """Run forever — call once via asyncio.create_task()."""
        log.info("SelfLearner started — evaluation every %dh", self._interval // 3600)
        while True:
            try:
                result = await self.evaluate()
                log.info(
                    "SelfLearner evaluation complete",
                    extra={
                        "recommendation": result.get("recommendation"),
                        "confidence":     result.get("confidence_score"),
                        "gate_passed":    result.get("gate_passed"),
                        "eval_count":     self._eval_count,
                    },
                )
            except asyncio.CancelledError:
                log.info("SelfLearner loop cancelled — shutting down")
                return
            except Exception as exc:   # noqa: BLE001
                log.exception("SelfLearner evaluation error: %s", exc)
            await asyncio.sleep(self._interval)

    async def evaluate(self) -> dict[str, Any]:
        """Run one full evaluation cycle and write a KB entry.

        Returns merged dict with keys from analyze_backtest() plus:
          gate_passed, gate_failures, consecutive_promotes.
        """
        self._eval_count += 1

        metrics      = self._compute_paper_metrics()
        kb_context   = self._read_kb_context()
        analysis     = analyze_backtest(
            metrics=metrics,
            walk_forward_results=[],
            strategy_name="paper_trader",
            kb_context=kb_context,
        )

        llm_conf     = float(analysis.get("confidence_score", 0.0))
        recommendation = str(analysis.get("recommendation", "HOLD_PAPER"))
        self._history.append(recommendation)

        gate: GateResult = evaluate_gate(
            metrics=metrics,
            llm_confidence=llm_conf,
            trailing_recommendations=self._history,
        )

        result: dict[str, Any] = {
            **analysis,
            "gate_passed":          gate.passed,
            "gate_failures":        gate.failures,
            "consecutive_promotes": self._consecutive_promotes(),
            "paper_metrics":        metrics,
            "eval_number":          self._eval_count,
        }

        self._write_kb_entry(result)
        return result

    def confidence_gate_passed(self) -> bool:
        """True after _TREND_REQUIRED consecutive PROMOTE_TO_LIVE evaluations."""
        return self._consecutive_promotes() >= _TREND_REQUIRED

    # ── Internals ──────────────────────────────────────────────────────────────

    def _consecutive_promotes(self) -> int:
        """Count consecutive PROMOTE_TO_LIVE recommendations from the end of history."""
        count = 0
        for rec in reversed(self._history):
            if rec == _PROMOTE:
                count += 1
            else:
                break
        return count

    def _compute_paper_metrics(self) -> dict[str, float]:
        """Query the Trade table for the last LLM_PAPER_WINDOW_DAYS of SELLs.

        Returns dict with: sharpe, max_drawdown, profit_factor, n_trades.
        Falls back to zero-metrics when DB has no data.
        """
        since = datetime.now(tz=timezone.utc) - timedelta(days=LLM_PAPER_WINDOW_DAYS)

        try:
            with SessionLocal() as sess:
                trades = (
                    sess.query(Trade)
                        .filter(Trade.ts >= since, Trade.side == "SELL")
                        .order_by(Trade.ts)
                        .all()
                )
        except Exception as exc:   # noqa: BLE001
            log.warning("SelfLearner: DB query failed — using zero metrics (%s)", exc)
            return _zero_metrics()

        if not trades:
            log.info("SelfLearner: no completed trades in window — using zero metrics")
            return _zero_metrics()

        pnls = [float(t.pnl) for t in trades]
        return _metrics_from_pnls(pnls, STARTING_BALANCE_USD)

    def _read_kb_context(self) -> str:
        """Return first 3000 chars of strategy_learnings.md as LLM context."""
        try:
            text = _STRATEGY_KB.read_text(encoding="utf-8")
            return text[:3000]
        except OSError:
            return ""

    def _write_kb_entry(self, result: dict[str, Any]) -> None:
        """Append a structured entry to knowledge/experiment_log.md."""
        ts       = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        metrics  = result.get("paper_metrics", {})
        gate_ok  = result.get("gate_passed", False)
        failures = result.get("gate_failures", [])
        rec      = result.get("recommendation", "N/A")
        conf     = result.get("confidence_score", 0.0)
        consec   = result.get("consecutive_promotes", 0)
        fallback = result.get("fallback", False)

        weaknesses = result.get("strategy_weaknesses", [])
        suggestions = result.get("parameter_suggestions", [])

        entry = f"""
## EXP-AUTO-{self._eval_count:04d} — Self-Learning Evaluation #{self._eval_count}
**Date:** {ts}
**Status:** COMPLETED

**Paper metrics ({LLM_PAPER_WINDOW_DAYS}d window):**
  - Sharpe ratio:   {metrics.get('sharpe', 0):.3f}
  - Max drawdown:   {metrics.get('max_drawdown', 0):.1%}
  - Profit factor:  {metrics.get('profit_factor', 0):.3f}
  - Trade count:    {int(metrics.get('n_trades', 0))}

**LLM analysis** {'(fallback — LLM unavailable)' if fallback else ''}:
  - Confidence:     {conf:.2f}
  - Recommendation: {rec}
  - Consecutive promotes: {consec}/{_TREND_REQUIRED}

**Promotion gate:** {'✅ PASSED' if gate_ok else '❌ FAILED'}
{('  Failures: ' + '; '.join(failures)) if failures else '  All gates passed.'}

**Strategy weaknesses:** {'; '.join(weaknesses) if weaknesses else 'none identified'}
**Parameter suggestions:** {'; '.join(str(s) for s in suggestions) if suggestions else 'none'}

---
"""
        try:
            _KB_DIR.mkdir(exist_ok=True)
            with _EXPERIMENT_LOG.open("a", encoding="utf-8") as fh:
                fh.write(entry)
            log.info("SelfLearner: KB entry written", extra={"eval": self._eval_count})
        except OSError as exc:
            log.warning("SelfLearner: could not write KB entry: %s", exc)


# ── Pure metric helpers (no I/O) ───────────────────────────────────────────────

def _zero_metrics() -> dict[str, float]:
    return {"sharpe": 0.0, "max_drawdown": 0.0, "profit_factor": 0.0, "n_trades": 0}


def _metrics_from_pnls(pnls: list[float], starting_equity: float) -> dict[str, float]:
    """Compute Sharpe, max_drawdown, profit_factor from a list of per-trade PnLs.

    Uses a cumulative equity curve derived from STARTING_BALANCE_USD.
    Annualises Sharpe assuming each trade ~= 1 period (conservative proxy for
    paper-trade data where we don't have per-minute granularity here).
    """
    import math

    n = len(pnls)
    if n == 0:
        return _zero_metrics()

    # Equity curve
    equity = starting_equity
    curve  = []
    for p in pnls:
        equity += p
        curve.append(equity)

    # Returns per trade
    returns: list[float] = []
    prev = starting_equity
    for eq in curve:
        returns.append((eq - prev) / prev if prev != 0 else 0.0)
        prev = eq

    mean_r = sum(returns) / n
    if n > 1:
        var = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
        std = math.sqrt(var) if var > 0 else 0.0
    else:
        std = 0.0

    sharpe = (mean_r / std * math.sqrt(252)) if std > 0 else 0.0

    # Max drawdown
    peak = starting_equity
    max_dd = 0.0
    running = starting_equity
    for p in pnls:
        running += p
        if running > peak:
            peak = running
        dd = (peak - running) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    # Profit factor
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss   = abs(sum(p for p in pnls if p < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (
        float("inf") if gross_profit > 0 else 0.0
    )
    # Cap inf at a large finite value for gate comparisons
    if profit_factor == float("inf"):
        profit_factor = 99.0

    return {
        "sharpe":         round(sharpe, 4),
        "max_drawdown":   round(max_dd, 4),
        "profit_factor":  round(profit_factor, 4),
        "n_trades":       float(n),
    }
