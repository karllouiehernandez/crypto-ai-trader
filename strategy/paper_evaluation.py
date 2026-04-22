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
            "summary": build_paper_evidence_summary(self),
        }


def _grade_paper_evidence(
    pnls: list[float],
    *,
    thresholds: PaperEvidenceThresholds | None = None,
    first_trade_ts: datetime | None = None,
    last_trade_ts: datetime | None = None,
    missing_reason: str = "No paper SELL trades tagged with this artifact yet",
) -> PaperEvidenceResult:
    th = thresholds or PaperEvidenceThresholds()
    result = PaperEvidenceResult(passed=False, metrics=_zero_metrics(), thresholds=th)
    if not pnls:
        result.reasons.append(missing_reason)
        return result

    result.metrics = _metrics_from_pnls(pnls, th.starting_equity)
    result.first_trade_ts = first_trade_ts
    result.last_trade_ts = last_trade_ts

    span = (last_trade_ts - first_trade_ts) if first_trade_ts and last_trade_ts else None
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


def build_paper_evidence_summary(result: PaperEvidenceResult) -> dict[str, Any]:
    """Return an operator-friendly summary for dashboard and runner surfaces."""
    n = int(result.metrics.get("n_trades", 0) or 0)
    trade_target = int(result.thresholds.min_trades)
    trade_remaining = max(0, trade_target - n)
    runtime_target = float(result.thresholds.min_runtime_days)
    runtime_remaining = max(0.0, runtime_target - float(result.runtime_days))

    if result.passed:
        stage = "passed"
        gate_status = "Passed"
    elif n == 0:
        stage = "waiting-for-first-close"
        gate_status = "Waiting for first close"
    elif trade_remaining > 0 or runtime_remaining > 0:
        stage = "gathering-evidence"
        gate_status = "Gathering evidence"
    else:
        stage = "thresholds-failed"
        gate_status = "Thresholds failed"

    return {
        "stage": stage,
        "gate_status": gate_status,
        "trade_count": n,
        "trade_target": trade_target,
        "trade_remaining": trade_remaining,
        "trade_progress_pct": min(1.0, n / trade_target) if trade_target > 0 else 1.0,
        "runtime_days": float(result.runtime_days),
        "runtime_target_days": runtime_target,
        "runtime_days_remaining": runtime_remaining,
        "runtime_progress_pct": min(1.0, float(result.runtime_days) / runtime_target) if runtime_target > 0 else 1.0,
        "sharpe": float(result.metrics.get("sharpe", 0.0) or 0.0),
        "profit_factor": float(result.metrics.get("profit_factor", 0.0) or 0.0),
        "max_drawdown": float(result.metrics.get("max_drawdown", 0.0) or 0.0),
        "min_sharpe": float(result.thresholds.min_sharpe),
        "min_profit_factor": float(result.thresholds.min_profit_factor),
        "max_drawdown_limit": float(result.thresholds.max_drawdown),
        "blocker_count": len(result.reasons),
        "reasons": list(result.reasons),
        "first_trade_ts": result.first_trade_ts.isoformat() if result.first_trade_ts else None,
        "last_trade_ts": result.last_trade_ts.isoformat() if result.last_trade_ts else None,
    }


def evaluate_paper_evidence_from_trades(
    pnls: list[float],
    *,
    first_trade_ts: datetime | None = None,
    last_trade_ts: datetime | None = None,
    thresholds: PaperEvidenceThresholds | None = None,
) -> PaperEvidenceResult:
    """Pure paper-evidence grader for in-memory trade evidence."""
    return _grade_paper_evidence(
        [float(p or 0.0) for p in pnls],
        thresholds=thresholds,
        first_trade_ts=first_trade_ts,
        last_trade_ts=last_trade_ts,
    )


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
    if not artifact_id:
        result = PaperEvidenceResult(passed=False, metrics=_zero_metrics(), thresholds=thresholds or PaperEvidenceThresholds())
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

    return _grade_paper_evidence(
        [float(r.pnl or 0.0) for r in rows],
        thresholds=thresholds,
        first_trade_ts=rows[0].ts if rows else None,
        last_trade_ts=rows[-1].ts if rows else None,
    )
