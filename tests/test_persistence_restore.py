from __future__ import annotations

import json
from pathlib import Path

import database.persistence as persistence_module
from database.persistence import plan_state_restore, restore_state_backup


def _write_manifest(tmp_path: Path, repo_root: Path) -> Path:
    backup_dir = tmp_path / "backup"
    strategies_dir = backup_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    db_copy = backup_dir / "market_data.db"
    db_copy.write_text("backup-db", encoding="utf-8")
    strategy_copy = strategies_dir / "7_restore_me.py"
    strategy_copy.write_text("strategy-source", encoding="utf-8")
    target_strategy = repo_root / "strategies" / "restore_me.py"
    manifest = {
        "backup_dir": str(backup_dir),
        "database_copy": str(db_copy),
        "env_copy": None,
        "audit": {
            "artifacts": [
                {
                    "id": 7,
                    "path": str(target_strategy),
                }
            ]
        },
    }
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_plan_state_restore_maps_db_and_strategy(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "strategies").mkdir(parents=True)
    db_target = repo_root / "data" / "market_data.db"
    monkeypatch.setattr(persistence_module, "DB_PATH", db_target, raising=False)
    monkeypatch.setattr(persistence_module, "__file__", str(repo_root / "database" / "persistence.py"), raising=False)
    manifest_path = _write_manifest(tmp_path, repo_root)

    plan = plan_state_restore(manifest_path)

    assert plan["can_apply"] is True
    assert {op["type"] for op in plan["operations"]} == {"database", "strategy"}


def test_restore_state_backup_dry_run_does_not_copy(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "strategies").mkdir(parents=True)
    db_target = repo_root / "data" / "market_data.db"
    monkeypatch.setattr(persistence_module, "DB_PATH", db_target, raising=False)
    monkeypatch.setattr(persistence_module, "__file__", str(repo_root / "database" / "persistence.py"), raising=False)
    manifest_path = _write_manifest(tmp_path, repo_root)

    result = restore_state_backup(manifest_path)

    assert result["applied"] is False
    assert not db_target.exists()


def test_restore_state_backup_apply_copies_files(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "strategies").mkdir(parents=True)
    db_target = repo_root / "data" / "market_data.db"
    monkeypatch.setattr(persistence_module, "DB_PATH", db_target, raising=False)
    monkeypatch.setattr(persistence_module, "__file__", str(repo_root / "database" / "persistence.py"), raising=False)
    monkeypatch.setattr(
        persistence_module,
        "create_state_backup",
        lambda: {"backup_dir": str(tmp_path / "pre_restore")},
    )
    monkeypatch.setattr(persistence_module, "init_db", lambda: None)
    manifest_path = _write_manifest(tmp_path, repo_root)

    result = restore_state_backup(manifest_path, apply=True)

    assert result["applied"] is True
    assert db_target.read_text(encoding="utf-8") == "backup-db"
    assert (repo_root / "strategies" / "restore_me.py").read_text(encoding="utf-8") == "strategy-source"
