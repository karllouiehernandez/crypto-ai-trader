"""simulator/coordinator.py — Live Promotion Coordinator.

Starts SelfLearner as a background asyncio task and watches its confidence gate.
When confidence_gate_passed() first returns True it:
  1. Writes a Promotion record to the DB
  2. Appends a promotion entry to knowledge/promotions.md
  3. Sends a Telegram alert

Wire into run_live.py::

    learner    = SelfLearner()
    coordinator = Coordinator(learner)
    trader._coordinator = coordinator
    await asyncio.gather(..., coordinator.run_loop())
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from config import BASE_DIR, LLM_ENABLED
from database.models import Promotion, SessionLocal
from utils.telegram_utils import alert

log = logging.getLogger(__name__)

_PROMOTION_LOG    = BASE_DIR / "knowledge" / "promotions.md"
_CHECK_INTERVAL_S = 3600   # poll gate every hour


class Coordinator:
    """Wraps SelfLearner and fires a one-time promotion event when the gate passes."""

    def __init__(self, learner, check_interval_s: int = _CHECK_INTERVAL_S) -> None:
        self._learner        = learner
        self._check_interval = check_interval_s
        self._promoted       = False   # True after first promotion fires
        self._learner_task: "asyncio.Task | None" = None

    # ── Public API ─────────────────────────────────────────────────────────────

    async def run_loop(self) -> None:
        """Start SelfLearner as a background task then poll the promotion gate."""
        if LLM_ENABLED:
            self._learner_task = asyncio.create_task(self._learner.run_loop())
            log.info("Coordinator: SelfLearner background task started")
        else:
            log.info("Coordinator: LLM_ENABLED=False — SelfLearner skipped")

        while True:
            try:
                await asyncio.sleep(self._check_interval)
                if not self._promoted and LLM_ENABLED:
                    # run_in_executor keeps blocking DB/file/HTTP calls off the event loop
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self._check_gate)
            except asyncio.CancelledError:
                log.info("Coordinator loop cancelled — shutting down")
                if self._learner_task is not None:
                    self._learner_task.cancel()
                return
            except Exception as exc:  # noqa: BLE001
                log.exception("Coordinator loop error: %s", exc)

    # ── Internals ──────────────────────────────────────────────────────────────

    def _check_gate(self) -> None:
        if self._promoted or not self._learner.confidence_gate_passed():
            return
        self._promoted = True
        metrics = self._learner._compute_paper_metrics()
        result = {
            "eval_number":          self._learner._eval_count,
            "consecutive_promotes": self._learner._consecutive_promotes(),
            "paper_metrics":        metrics,
            "confidence_score":     0.0,   # last LLM score not directly exposed; 0 is safe default
        }
        self._record_promotion(result)
        self._write_promotion_entry(result)
        self._send_promotion_alert(result)

    def _record_promotion(self, result: dict) -> None:
        metrics = result.get("paper_metrics", {})
        try:
            with SessionLocal() as sess:
                record = Promotion(
                    ts=datetime.now(tz=timezone.utc),
                    eval_number=result.get("eval_number", 0),
                    consecutive_promotes=result.get("consecutive_promotes", 0),
                    sharpe=metrics.get("sharpe", 0.0),
                    max_dd=metrics.get("max_drawdown", 0.0),
                    profit_factor=metrics.get("profit_factor", 0.0),
                    confidence_score=result.get("confidence_score", 0.0),
                    recommendation="PROMOTE_TO_LIVE",
                )
                sess.add(record)
                sess.commit()
            log.info("Coordinator: promotion record written to DB")
        except Exception as exc:  # noqa: BLE001
            log.warning("Coordinator: DB write failed: %s", exc)

    def _write_promotion_entry(self, result: dict) -> None:
        ts      = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        metrics = result.get("paper_metrics", {})
        entry = f"""
## PROMOTION EVENT — {ts}
**Eval number:** {result.get('eval_number', 0)}
**Consecutive PROMOTE_TO_LIVE:** {result.get('consecutive_promotes', 0)}/3

**Paper metrics at promotion:**
  - Sharpe ratio:  {metrics.get('sharpe', 0):.3f}
  - Max drawdown:  {metrics.get('max_drawdown', 0):.1%}
  - Profit factor: {metrics.get('profit_factor', 0):.3f}
  - Trade count:   {int(metrics.get('n_trades', 0))}

**Action:** Strategy promoted to live — confirm manually before enabling real funds.

---
"""
        try:
            _PROMOTION_LOG.parent.mkdir(exist_ok=True)
            with _PROMOTION_LOG.open("a", encoding="utf-8") as fh:
                fh.write(entry)
            log.info("Coordinator: promotion KB entry written")
        except OSError as exc:
            log.warning("Coordinator: KB write failed: %s", exc)

    def _send_promotion_alert(self, result: dict) -> None:
        metrics = result.get("paper_metrics", {})
        msg = (
            "🚀 *Promotion Gate PASSED*\n"
            "The self-learning loop has achieved 3 consecutive PROMOTE_TO_LIVE evaluations.\n\n"
            "📊 *Paper Metrics:*\n"
            f"  Sharpe: `{metrics.get('sharpe', 0):.2f}`\n"
            f"  Max DD: `{metrics.get('max_drawdown', 0):.1%}`\n"
            f"  PF:     `{metrics.get('profit_factor', 0):.2f}`\n"
            f"  Trades: `{int(metrics.get('n_trades', 0))}`\n\n"
            "⚠️ Review strategy performance before enabling live trading."
        )
        alert(msg)
        log.info("Coordinator: Telegram promotion alert sent")
