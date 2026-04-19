"""Deterministic paper-trade evidence evaluator.

Provides a non-LLM gate for transitioning a paper-active strategy artifact to
``paper_passed``. Reads real paper trades and runtime span from the live DB,
computes Sharpe / max_drawdown / profit_factor, and grades against thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from database.models import SessionLocal, Trade, init_db
from llm.self_learner import _metrics_from_pnls, _zero_metrics


@dataclass(frozen=True)
class PaperEvidenceThresholds:
    min_trades: int = 20
    min_runtime_days: float = 3.0
    min_sharpe: float = 1.5
    min_profit_factor: float = 1.5
    max_drawdown: float = 0.20  # absolute fraction, e.g. 0.20 == 20%
    starting_equity: float = 100.0


@dataclass
class PaperEvidenceResult:
    passed: bool
    metrics: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    runtime_days: float = 0.0
    first_trade_ts: datetime | None = None
    last_trade_ts: datetime | None = None
    thresholds: PaperEvidenceThresholds = field(default_factory=PaperEvidenceThresholds)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "metrics": dict(self.metrics),
            "reasons": list(self.reasons),
            "runtime_days": self.runtime_days,
            "first_trade_ts": self.first_trade_ts.isoformat() if self.first_trade_ts else None,
            "last_trade_ts": self.last_trade_ts.isoformat() if self.last_trade_ts else None,
            "thresholds": {
                "min_trades": self.thresholds.min_trades,
                "min_runtime_days": self.thresholds.min_runtime_days,
                "min_sharpe": self.thresholds.min_sharpe,
                "min_profit_factor": self.thresholds.min_profit_factor,
                "max_drawdown": self.thresholds.max_drawdown,
            },
        }


def evaluate_paper_evidence(
    artifact_id: int | None,
    *,
    thresholds: PaperEvidenceThresholds | None = None,
) -> PaperEvidenceResult:
    """Grade real paper-trade evidence for a strategy artifact.

    Counts only ``run_mode='paper'`` SELL rows tagged with the given artifact id —
    BUY rows are entries (no realised PnL); pre-tagging legacy trades have
    ``artifact_id=NULL`` and are correctly excluded.
    """
    th = thresholds or PaperEvidenceThresholds()
    result = PaperEvidenceResult(passed=False, metrics=_zero_metrics(), thresholds=th)

    if not artifact_id:
        result.reasons.append("No artifact id supplied")
        return result

    init_db()
    with SessionLocal() as sess:
        rows = (
            sess.query(Trade)
            .filter(
                Trade.artifact_id == int(artifact_id),
                Trade.run_mode == "paper",
                Trade.side == "SELL",
            )
            .order_by(Trade.ts)
            .all()
        )

    if not rows:
        result.reasons.append("No paper SELL trades tagged with this artifact yet")
        return result

    pnls = [float(r.pnl or 0.0) for r in rows]
    result.metrics = _metrics_from_pnls(pnls, th.starting_equity)
    result.first_trade_ts = rows[0].ts
    result.last_trade_ts = rows[-1].ts

    span = (rows[-1].ts - rows[0].ts) if rows[0].ts and rows[-1].ts else None
    result.runtime_days = (span.total_seconds() / 86400.0) if span else 0.0

    n = int(result.metrics.get("n_trades", 0))
    sharpe = float(result.metrics.get("sharpe", 0.0))
    pf = float(result.metrics.get("profit_factor", 0.0))
    max_dd = float(result.metrics.get("max_drawdown", 0.0))

    if n < th.min_trades:
        result.reasons.append(f"Only {n} paper trades (need >= {th.min_trades})")
    if result.runtime_days < th.min_runtime_days:
        result.reasons.append(
            f"Runtime span {result.runtime_days:.2f}d (need >= {th.min_runtime_days}d)"
        )
    if sharpe < th.min_sharpe:
        result.reasons.append(f"Sharpe {sharpe:.2f} (need >= {th.min_sharpe})")
    if pf < th.min_profit_factor:
        result.reasons.append(f"Profit factor {pf:.2f} (need >= {th.min_profit_factor})")
    if max_dd > th.max_drawdown:
        result.reasons.append(
            f"Max drawdown {max_dd:.1%} (must be <= {th.max_drawdown:.1%})"
        )

    result.passed = not result.reasons
    return result
