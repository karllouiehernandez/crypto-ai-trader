from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import textwrap

import pytest

from database.models import BacktestRun, SessionLocal, init_db
import strategy.artifacts as artifacts_module
from strategies.loader import clear_registry, list_strategies, load_strategy_path
from strategy.artifacts import (
    deactivate_runtime_artifact,
    get_active_runtime_artifact_id,
    list_all_strategy_artifacts,
    promote_artifact_to_paper,
    register_strategy_artifact,
    repin_reviewed_artifact_hash,
    review_generated_strategy,
    set_active_runtime_artifact_id,
    validate_runtime_artifact,
)
from strategy.runtime import resolve_runtime_strategy_descriptor
from tests._db_test_utils import install_temp_app_db


@pytest.fixture(autouse=True)
def isolate_strategy_artifact_db(monkeypatch, tmp_path):
    install_temp_app_db(
        monkeypatch,
        tmp_path,
        module_globals=globals(),
        module_targets=[artifacts_module],
    )


GENERATED_DRAFT = """
import pandas as pd
from strategy.base import StrategyBase
from strategy.regime import Regime

class DraftMomentum(StrategyBase):
    name = "generated_momentum_v1"
    description = "Generated momentum draft."
    version = "1.0.0"
    regimes = [Regime.TRENDING]

    def default_params(self) -> dict:
        return {}

    def param_schema(self) -> list[dict]:
        return []

    def should_long(self, df: pd.DataFrame) -> bool:
        return True

    def should_short(self, df: pd.DataFrame) -> bool:
        return False
""".strip()


@pytest.fixture(autouse=True)
def clean_strategy_registry():
    from database.models import StrategyArtifact, init_db
    init_db()
    with SessionLocal() as sess:
        sess.query(StrategyArtifact).delete()
        sess.commit()
    clear_registry()
    set_active_runtime_artifact_id("paper", None)
    set_active_runtime_artifact_id("live", None)
    yield
    with SessionLocal() as sess:
        sess.query(StrategyArtifact).delete()
        sess.commit()
    clear_registry()
    set_active_runtime_artifact_id("paper", None)
    set_active_runtime_artifact_id("live", None)


def _write_strategy(tmp_path: Path, stem: str, source: str = GENERATED_DRAFT) -> Path:
    path = tmp_path / f"{stem}.py"
    path.write_text(source.replace("generated_momentum_v1", stem), encoding="utf-8")
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


def test_review_generated_strategy_rejects_unsupported_sdk_version(tmp_path, monkeypatch):
    source = textwrap.dedent("""
        import pandas as pd
        from strategy.base import StrategyBase
        from strategy.regime import Regime

        class DraftMomentum(StrategyBase):
            name = "generated_momentum_v1"
            description = "Generated momentum draft."
            version = "1.0.0"
            sdk_version = "999"
            regimes = [Regime.TRENDING]

            def default_params(self) -> dict:
                return {}

            def param_schema(self) -> list[dict]:
                return []

            def should_long(self, df: pd.DataFrame) -> bool:
                return True

            def should_short(self, df: pd.DataFrame) -> bool:
                return False
    """).strip()
    source_path = _write_strategy(tmp_path, "generated_20260418_120001", source)
    artifact = register_strategy_artifact(
        {
            "name": "generated_20260418_120001",
            "version": "1.0.0",
            "path": str(source_path),
            "provenance": "generated",
        }
    )
    assert artifact is not None

    monkeypatch.setattr("strategy.artifacts.STRATEGIES_DIR", tmp_path)
    with pytest.raises(ValueError, match="not supported"):
        review_generated_strategy(int(artifact["id"]), "reviewed_sdk_guard_v1")


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


# ── Sprint 34: deactivate + list_all ─────────────────────────────────────────

def test_deactivate_runtime_artifact_clears_paper(tmp_path, monkeypatch):
    monkeypatch.setattr("strategy.artifacts.STRATEGIES_DIR", tmp_path)
    path = _write_strategy(tmp_path, "deactivate_me")
    meta = _load_meta(path)
    artifact = register_strategy_artifact(meta)
    set_active_runtime_artifact_id("paper", artifact["id"])
    assert get_active_runtime_artifact_id("paper") == artifact["id"]

    deactivate_runtime_artifact("paper")
    assert get_active_runtime_artifact_id("paper") is None


def test_deactivate_runtime_artifact_clears_live(tmp_path, monkeypatch):
    monkeypatch.setattr("strategy.artifacts.STRATEGIES_DIR", tmp_path)
    path = _write_strategy(tmp_path, "deactivate_live_me")
    meta = _load_meta(path)
    artifact = register_strategy_artifact(meta)
    set_active_runtime_artifact_id("live", artifact["id"])
    assert get_active_runtime_artifact_id("live") == artifact["id"]

    deactivate_runtime_artifact("live")
    assert get_active_runtime_artifact_id("live") is None


def test_deactivate_already_none_is_safe():
    assert get_active_runtime_artifact_id("paper") is None
    deactivate_runtime_artifact("paper")  # should not raise
    assert get_active_runtime_artifact_id("paper") is None


def test_list_all_strategy_artifacts_returns_registered(tmp_path, monkeypatch):
    monkeypatch.setattr("strategy.artifacts.STRATEGIES_DIR", tmp_path)
    path_a = _write_strategy(tmp_path, "list_test_a")
    path_b = _write_strategy(tmp_path, "list_test_b")
    meta_a = _load_meta(path_a)
    meta_b = _load_meta(path_b)
    register_strategy_artifact(meta_a)
    register_strategy_artifact(meta_b)

    artifacts = list_all_strategy_artifacts()
    names = {a["name"] for a in artifacts}
    assert {"list_test_a", "list_test_b"}.issubset(names)


def test_list_all_strategy_artifacts_empty_returns_list():
    result = list_all_strategy_artifacts()
    assert isinstance(result, list)


def test_repin_reviewed_artifact_hash_updates_hash(tmp_path):
    source = GENERATED_DRAFT.replace("generated_momentum_v1", "repin_me_v1")
    path = _write_strategy(tmp_path, "repin_me_v1", source)
    meta = _load_meta(path)
    artifact = register_strategy_artifact({**meta, "provenance": "plugin"})
    assert artifact is not None

    path.write_text(source + "\n# reviewed metadata update\n", encoding="utf-8")
    valid, error = validate_runtime_artifact(int(artifact["id"]))
    assert valid is None
    assert "hash mismatch" in str(error).lower()

    repinned = repin_reviewed_artifact_hash(int(artifact["id"]))
    assert repinned["changed"] is True
    valid, error = validate_runtime_artifact(int(artifact["id"]))
    assert valid is not None
    assert error is None


def test_repin_reviewed_artifact_hash_reuses_existing_matching_artifact(tmp_path):
    source = GENERATED_DRAFT.replace("generated_momentum_v1", "repin_existing_v1")
    path = _write_strategy(tmp_path, "repin_existing_v1", source)
    meta = _load_meta(path)
    old_artifact = register_strategy_artifact({**meta, "provenance": "plugin"})
    assert old_artifact is not None
    set_active_runtime_artifact_id("paper", int(old_artifact["id"]))

    path.write_text(source + "\n# reviewed metadata update\n", encoding="utf-8")
    newer_meta = _load_meta(path)
    existing_artifact = register_strategy_artifact({**newer_meta, "provenance": "plugin"})
    assert existing_artifact is not None
    assert existing_artifact["id"] != old_artifact["id"]

    repinned = repin_reviewed_artifact_hash(int(old_artifact["id"]))

    assert repinned["reused_existing_artifact"] is True
    assert repinned["id"] == existing_artifact["id"]
    assert repinned["moved_runtime_modes"] == ["paper"]
    assert get_active_runtime_artifact_id("paper") == existing_artifact["id"]
