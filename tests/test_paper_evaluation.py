from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from database.models import SessionLocal, Trade
import strategy.artifacts as artifacts_module
import strategy.paper_evaluation as paper_eval_module
from strategy.artifacts import (
    _set_artifact_status,
    mark_artifact_paper_passed,
    register_strategy_artifact,
)
from strategy.paper_evaluation import (
    PaperEvidenceThresholds,
    build_paper_evidence_summary,
    evaluate_paper_evidence,
    evaluate_paper_evidence_from_trades,
)
from tests._db_test_utils import install_temp_app_db


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    install_temp_app_db(
        monkeypatch,
        tmp_path,
        module_globals=globals(),
        module_targets=[artifacts_module, paper_eval_module],
    )


def _make_artifact(tmp_path, stem: str = "paper_eval_v1") -> int:
    src = tmp_path / f"{stem}.py"
    src.write_text(
        "from strategy.base import StrategyBase\n"
        f"class S(StrategyBase):\n    name='{stem}'\n    version='1.0.0'\n",
        encoding="utf-8",
    )
    artifact = register_strategy_artifact(
        {
            "name": stem,
            "version": "1.0.0",
            "path": str(src),
            "provenance": "plugin",
        }
    )
    assert artifact is not None
    return int(artifact["id"])


def _add_paper_sells(artifact_id: int, pnls: list[float], *, span_days: float = 5.0) -> None:
    base = datetime.now(tz=timezone.utc) - timedelta(days=span_days)
    step = timedelta(seconds=(span_days * 86400.0) / max(len(pnls) - 1, 1))
    with SessionLocal() as sess:
        for i, p in enumerate(pnls):
            sess.add(
                Trade(
                    ts=base + step * i,
                    symbol="BTCUSDT",
                    side="SELL",
                    qty=0.001,
                    price=50000.0,
                    fee=0.05,
                    pnl=float(p),
                    artifact_id=artifact_id,
                    run_mode="paper",
                )
            )
        sess.commit()


def test_evidence_blocks_when_no_artifact_id():
    result = evaluate_paper_evidence(None)
    assert result.passed is False
    assert "No artifact id supplied" in result.reasons


def test_evidence_blocks_when_no_paper_trades(tmp_path):
    artifact_id = _make_artifact(tmp_path)
    result = evaluate_paper_evidence(artifact_id)
    assert result.passed is False
    assert any("No paper SELL trades" in r for r in result.reasons)


def test_evidence_blocks_on_insufficient_trade_count(tmp_path):
    artifact_id = _make_artifact(tmp_path)
    _add_paper_sells(artifact_id, [1.0] * 5, span_days=5.0)
    result = evaluate_paper_evidence(artifact_id)
    assert result.passed is False
    assert any("paper trades" in r for r in result.reasons)


def test_evidence_blocks_on_short_runtime_span(tmp_path):
    artifact_id = _make_artifact(tmp_path)
    _add_paper_sells(artifact_id, [1.0] * 30, span_days=0.5)
    result = evaluate_paper_evidence(artifact_id)
    assert result.passed is False
    assert any("Runtime span" in r for r in result.reasons)


def test_evidence_blocks_on_drawdown(tmp_path):
    artifact_id = _make_artifact(tmp_path)
    pnls = [1.0] * 20 + [-30.0] + [1.0] * 9  # forces ~30% drawdown
    _add_paper_sells(artifact_id, pnls, span_days=5.0)
    result = evaluate_paper_evidence(artifact_id)
    assert result.passed is False
    assert any("Max drawdown" in r for r in result.reasons)


def test_evidence_passes_with_consistent_winners(tmp_path):
    artifact_id = _make_artifact(tmp_path)
    _add_paper_sells(artifact_id, [1.5] * 25, span_days=10.0)
    th = PaperEvidenceThresholds(
        min_trades=20, min_runtime_days=3.0, min_sharpe=0.0,
        min_profit_factor=1.5, max_drawdown=0.2,
    )
    result = evaluate_paper_evidence(artifact_id, thresholds=th)
    assert result.passed is True, result.reasons
    assert result.metrics["n_trades"] == 25.0
    assert result.metrics["max_drawdown"] == 0.0


def test_build_paper_evidence_summary_waiting_for_first_close():
    result = evaluate_paper_evidence_from_trades([], thresholds=PaperEvidenceThresholds())
    summary = build_paper_evidence_summary(result)
    assert summary["stage"] == "waiting-for-first-close"
    assert summary["trade_count"] == 0
    assert summary["trade_target"] == 20


def test_build_paper_evidence_summary_reports_remaining_blockers():
    base = datetime.now(tz=timezone.utc) - timedelta(days=1)
    result = evaluate_paper_evidence_from_trades(
        [1.0] * 10,
        first_trade_ts=base,
        last_trade_ts=base + timedelta(days=1),
    )
    summary = build_paper_evidence_summary(result)
    assert summary["stage"] == "gathering-evidence"
    assert summary["trade_remaining"] == 10
    assert summary["runtime_days_remaining"] == pytest.approx(2.0)
    assert summary["blocker_count"] >= 2


def test_mark_artifact_paper_passed_blocks_without_evidence(tmp_path):
    artifact_id = _make_artifact(tmp_path)
    _set_artifact_status(artifact_id, "paper_active")
    with pytest.raises(ValueError, match="Paper evidence gate failed"):
        mark_artifact_paper_passed(artifact_id)


def test_mark_artifact_paper_passed_force_bypass(tmp_path):
    artifact_id = _make_artifact(tmp_path)
    _set_artifact_status(artifact_id, "paper_active")
    promoted = mark_artifact_paper_passed(artifact_id, force=True)
    assert promoted is not None
    assert promoted["status"] == "paper_passed"


def test_mark_artifact_paper_passed_promotes_with_evidence(tmp_path):
    artifact_id = _make_artifact(tmp_path)
    _set_artifact_status(artifact_id, "paper_active")
    _add_paper_sells(artifact_id, [1.5] * 25, span_days=10.0)
    th = PaperEvidenceThresholds(
        min_trades=20, min_runtime_days=3.0, min_sharpe=0.0,
        min_profit_factor=1.5, max_drawdown=0.2,
    )
    promoted = mark_artifact_paper_passed(artifact_id, thresholds=th)
    assert promoted is not None
    assert promoted["status"] == "paper_passed"


def test_legacy_untagged_trades_are_not_evidence(tmp_path):
    artifact_id = _make_artifact(tmp_path)
    # Insert a profitable history under artifact_id=NULL — must not count
    with SessionLocal() as sess:
        for i in range(50):
            sess.add(
                Trade(
                    ts=datetime.now(tz=timezone.utc) - timedelta(hours=i),
                    symbol="BTCUSDT",
                    side="SELL",
                    qty=0.001,
                    price=50000.0,
                    fee=0.05,
                    pnl=2.0,
                    artifact_id=None,
                    run_mode="paper",
                )
            )
        sess.commit()
    result = evaluate_paper_evidence(artifact_id)
    assert result.passed is False
    assert any("No paper SELL trades" in r for r in result.reasons)
