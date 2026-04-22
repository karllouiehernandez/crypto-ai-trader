from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from database.models import BacktestRun, Candle, SessionLocal
import market_data.history as history_module
import strategy.artifacts as artifacts_module
import database.persistence as persistence_module
from database.persistence import create_state_backup, evaluate_restart_survival
from strategy.artifacts import register_strategy_artifact, set_active_runtime_artifact_id
from tests._db_test_utils import install_temp_app_db


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    db_path = install_temp_app_db(
        monkeypatch,
        tmp_path,
        module_globals=globals(),
        module_targets=[artifacts_module, history_module, persistence_module],
    )
    monkeypatch.setattr(persistence_module, "DB_PATH", db_path, raising=False)
    monkeypatch.setattr(persistence_module, "MVP_RESEARCH_UNIVERSE", ["BTCUSDT"], raising=False)
    monkeypatch.setattr(persistence_module, "MVP_FRESHNESS_MINUTES", 10, raising=False)


def _write_plugin(tmp_path: Path, stem: str) -> Path:
    src = tmp_path / f"{stem}.py"
    src.write_text(
        "from strategy.base import StrategyBase\n\n"
        f"class {stem.title().replace('_', '')}(StrategyBase):\n"
        f"    name = \"{stem}\"\n"
        "    version = \"1.0.0\"\n",
        encoding="utf-8",
    )
    return src


def _insert_fresh_candle(symbol: str = "BTCUSDT", *, age_minutes: int = 1) -> None:
    with SessionLocal() as sess:
        sess.add(
            Candle(
                symbol=symbol,
                open_time=datetime.now(tz=timezone.utc) - timedelta(minutes=age_minutes),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=10.0,
            )
        )
        sess.commit()


def test_evaluate_restart_survival_flags_missing_mvp_data():
    report = evaluate_restart_survival()
    assert report["ready_for_restart"] is False
    assert any("missing local candles" in issue.lower() for issue in report["issues"])


def test_evaluate_restart_survival_reports_valid_runtime_and_counts(tmp_path):
    src = _write_plugin(tmp_path, "restart_ready_v1")
    artifact = register_strategy_artifact(
        {
            "name": "restart_ready_v1",
            "version": "1.0.0",
            "path": str(src),
            "provenance": "plugin",
        }
    )
    assert artifact is not None
    set_active_runtime_artifact_id("paper", int(artifact["id"]))
    _insert_fresh_candle()

    with SessionLocal() as sess:
        sess.add(
            BacktestRun(
                symbol="BTCUSDT",
                start_ts=datetime(2026, 4, 1, tzinfo=timezone.utc),
                end_ts=datetime(2026, 4, 2, tzinfo=timezone.utc),
                artifact_id=int(artifact["id"]),
                strategy_name="restart_ready_v1",
                strategy_version="1.0.0",
                strategy_code_hash=str(artifact["code_hash"]),
                strategy_provenance="plugin",
                params_json="{}",
                metrics_json=json.dumps({"sharpe": 1.0}),
                status="passed",
                integrity_status="valid",
            )
        )
        sess.commit()

    report = evaluate_restart_survival()
    assert report["ready_for_restart"] is True, report["issues"]
    assert report["paper_target"]["valid"] is True
    assert report["artifact_count"] == 1
    assert report["saved_run_count"] == 1
    assert report["auditable_run_count"] == 1
    assert report["fresh_mvp_symbol_count"] == 1


def test_evaluate_restart_survival_detects_hash_mismatch(tmp_path):
    src = _write_plugin(tmp_path, "restart_hash_v1")
    artifact = register_strategy_artifact(
        {
            "name": "restart_hash_v1",
            "version": "1.0.0",
            "path": str(src),
            "provenance": "plugin",
        }
    )
    assert artifact is not None
    set_active_runtime_artifact_id("paper", int(artifact["id"]))
    _insert_fresh_candle()

    src.write_text(
        "from strategy.base import StrategyBase\n\n"
        "class RestartHashV1(StrategyBase):\n"
        "    name = \"restart_hash_v1\"\n"
        "    version = \"1.0.1\"\n",
        encoding="utf-8",
    )

    report = evaluate_restart_survival()
    assert report["ready_for_restart"] is False
    assert report["artifact_hash_mismatch_count"] == 1
    assert any("paper target is invalid" in issue.lower() for issue in report["issues"])


def test_create_state_backup_copies_db_and_strategy_files(tmp_path):
    src = _write_plugin(tmp_path, "restart_backup_v1")
    artifact = register_strategy_artifact(
        {
            "name": "restart_backup_v1",
            "version": "1.0.0",
            "path": str(src),
            "provenance": "plugin",
        }
    )
    assert artifact is not None
    set_active_runtime_artifact_id("paper", int(artifact["id"]))
    _insert_fresh_candle()

    manifest = create_state_backup(tmp_path / "backups")
    assert Path(manifest["backup_dir"]).exists()
    assert Path(manifest["manifest_path"]).exists()
    assert manifest["database_copy"] is not None
    assert Path(str(manifest["database_copy"])).exists()
    assert len(manifest["copied_strategy_files"]) == 1

    payload = json.loads(Path(manifest["manifest_path"]).read_text(encoding="utf-8"))
    assert payload["audit"]["paper_target"]["artifact_id"] == int(artifact["id"])
