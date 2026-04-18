from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from database.models import BacktestRun, SessionLocal, init_db
from strategies.loader import clear_registry, list_strategies, load_strategy_path
from strategy.artifacts import (
    get_active_runtime_artifact_id,
    promote_artifact_to_paper,
    register_strategy_artifact,
    review_generated_strategy,
    set_active_runtime_artifact_id,
    validate_runtime_artifact,
)
from strategy.runtime import resolve_runtime_strategy_descriptor


GENERATED_DRAFT = """
import pandas as pd
from strategy.base import StrategyBase
from strategy.regime import Regime

class DraftMomentum(StrategyBase):
    name = "generated_momentum_v1"
    version = "1.0.0"
    regimes = [Regime.TRENDING]

    def should_long(self, df: pd.DataFrame) -> bool:
        return True

    def should_short(self, df: pd.DataFrame) -> bool:
        return False
""".strip()


@pytest.fixture(autouse=True)
def clean_strategy_registry():
    clear_registry()
    set_active_runtime_artifact_id("paper", None)
    set_active_runtime_artifact_id("live", None)
    yield
    clear_registry()
    set_active_runtime_artifact_id("paper", None)
    set_active_runtime_artifact_id("live", None)


def _write_strategy(tmp_path: Path, stem: str, source: str = GENERATED_DRAFT) -> Path:
    path = tmp_path / f"{stem}.py"
    path.write_text(source, encoding="utf-8")
    return path


def _load_meta(path: Path) -> dict:
    load_strategy_path(path)
    return next(item for item in list_strategies() if item.get("path") == str(path))


def test_generated_draft_registers_as_draft(tmp_path):
    meta = _load_meta(_write_strategy(tmp_path, "generated_20260418_120000"))

    artifact = register_strategy_artifact(meta)

    assert artifact is not None
    assert artifact["provenance"] == "generated"
    assert artifact["status"] == "draft"


def test_review_generated_strategy_creates_reviewed_plugin(tmp_path, monkeypatch):
    source_path = _write_strategy(tmp_path, "generated_20260418_120001")
    source_meta = _load_meta(source_path)
    source_artifact = register_strategy_artifact(source_meta)

    monkeypatch.setattr("strategy.artifacts.STRATEGIES_DIR", tmp_path)
    result = review_generated_strategy(int(source_artifact["id"]), "reviewed_momentum_v1")

    reviewed_path = tmp_path / "reviewed_momentum_v1.py"
    reviewed_source = reviewed_path.read_text(encoding="utf-8")
    assert reviewed_path.exists()
    assert 'name = "reviewed_momentum_v1"' in reviewed_source
    assert result["artifact"]["provenance"] == "plugin"
    assert result["artifact"]["status"] == "reviewed"
    assert result["artifact"]["reviewed_from_artifact_id"] == source_artifact["id"]


def test_promote_artifact_to_paper_requires_passing_backtest(tmp_path, monkeypatch):
    source_path = _write_strategy(tmp_path, "generated_20260418_120002")
    source_meta = _load_meta(source_path)
    source_artifact = register_strategy_artifact(source_meta)
    monkeypatch.setattr("strategy.artifacts.STRATEGIES_DIR", tmp_path)
    reviewed = review_generated_strategy(int(source_artifact["id"]), "paper_candidate_v1")
    artifact_id = int(reviewed["artifact"]["id"])

    init_db()
    with SessionLocal() as sess:
        sess.add(
            BacktestRun(
                created_at=datetime.now(tz=timezone.utc),
                symbol="BTCUSDT",
                start_ts=datetime(2024, 4, 1, tzinfo=timezone.utc),
                end_ts=datetime(2024, 4, 2, tzinfo=timezone.utc),
                artifact_id=artifact_id,
                strategy_name="paper_candidate_v1",
                strategy_version="1.0.0",
                strategy_code_hash=reviewed["artifact"]["code_hash"],
                strategy_provenance="plugin",
                params_json="{}",
                metrics_json='{"sharpe": 2.0, "passed": true}',
                status="passed",
            )
        )
        sess.commit()

    promoted = promote_artifact_to_paper(artifact_id)

    assert promoted["status"] == "paper_active"
    assert get_active_runtime_artifact_id("paper") == artifact_id


def test_validate_runtime_artifact_detects_hash_mismatch(tmp_path, monkeypatch):
    source_path = _write_strategy(tmp_path, "generated_20260418_120003")
    source_meta = _load_meta(source_path)
    source_artifact = register_strategy_artifact(source_meta)
    monkeypatch.setattr("strategy.artifacts.STRATEGIES_DIR", tmp_path)
    reviewed = review_generated_strategy(int(source_artifact["id"]), "hash_checked_v1")
    reviewed_path = tmp_path / "hash_checked_v1.py"

    reviewed_path.write_text(reviewed_path.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")

    artifact, error = validate_runtime_artifact(int(reviewed["artifact"]["id"]))

    assert artifact is None
    assert error is not None
    assert "hash mismatch" in error.lower()


def test_resolve_runtime_strategy_descriptor_returns_promoted_reviewed_plugin(tmp_path, monkeypatch):
    source_path = _write_strategy(tmp_path, "generated_20260418_120004")
    source_meta = _load_meta(source_path)
    source_artifact = register_strategy_artifact(source_meta)
    monkeypatch.setattr("strategy.artifacts.STRATEGIES_DIR", tmp_path)
    reviewed = review_generated_strategy(int(source_artifact["id"]), "runtime_ready_v1")
    artifact_id = int(reviewed["artifact"]["id"])

    init_db()
    with SessionLocal() as sess:
        sess.add(
            BacktestRun(
                created_at=datetime.now(tz=timezone.utc),
                symbol="BTCUSDT",
                start_ts=datetime(2024, 4, 1, tzinfo=timezone.utc),
                end_ts=datetime(2024, 4, 2, tzinfo=timezone.utc),
                artifact_id=artifact_id,
                strategy_name="runtime_ready_v1",
                strategy_version="1.0.0",
                strategy_code_hash=reviewed["artifact"]["code_hash"],
                strategy_provenance="plugin",
                params_json="{}",
                metrics_json='{"sharpe": 2.1, "passed": true}',
                status="passed",
            )
        )
        sess.commit()

    promote_artifact_to_paper(artifact_id)
    descriptor = resolve_runtime_strategy_descriptor("paper")

    assert descriptor["artifact_id"] == artifact_id
    assert descriptor["strategy_name"] == "runtime_ready_v1"
    assert descriptor["strategy_provenance"] == "plugin"
