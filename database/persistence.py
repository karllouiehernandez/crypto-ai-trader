"""Persistence and restart-survival helpers for trader-operability checks."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from config import MVP_FRESHNESS_MINUTES, MVP_RESEARCH_UNIVERSE
from database.models import BacktestRun, BacktestTrade, DB_PATH, SessionLocal, init_db
from market_data.history import get_latest_candle_time
from strategy.artifacts import (
    compute_strategy_code_hash,
    get_active_runtime_artifact_id,
    get_strategy_artifact,
    list_all_strategy_artifacts,
    validate_runtime_artifact,
)


def _default_backup_root() -> Path:
    db_path = Path(DB_PATH).resolve()
    return db_path.parent.parent / "backups"


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _normalise_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return _normalise_utc(value).isoformat() if _normalise_utc(value) else None
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def _target_state(run_mode: str) -> dict[str, Any]:
    artifact_id = get_active_runtime_artifact_id(run_mode)
    artifact = get_strategy_artifact(artifact_id)
    valid_artifact, error = validate_runtime_artifact(artifact_id)
    return {
        "configured": artifact_id is not None,
        "artifact_id": artifact_id,
        "name": artifact.get("name") if artifact else None,
        "status": artifact.get("status") if artifact else None,
        "valid": valid_artifact is not None and error is None,
        "error": error,
    }


def evaluate_restart_survival() -> dict[str, Any]:
    """Audit whether the current local state can survive a restart cleanly."""
    init_db()
    now_utc = _utc_now()
    db_path = Path(DB_PATH).resolve()
    db_exists = db_path.exists()
    db_size_bytes = db_path.stat().st_size if db_exists else 0
    paper_target = _target_state("paper")
    live_target = _target_state("live")
    artifacts = list_all_strategy_artifacts()

    artifact_rows: list[dict[str, Any]] = []
    missing_count = 0
    hash_mismatch_count = 0
    issues: list[str] = []
    for artifact in artifacts:
        path = Path(str(artifact.get("path") or "")).resolve()
        file_exists = path.exists()
        hash_matches = False
        actual_hash = None
        if file_exists:
            actual_hash = compute_strategy_code_hash(path)
            hash_matches = actual_hash == artifact.get("code_hash")
        if not file_exists:
            missing_count += 1
            issues.append(f"Artifact #{artifact['id']} is missing on disk: {path}")
        elif not hash_matches:
            hash_mismatch_count += 1
            issues.append(f"Artifact #{artifact['id']} hash mismatch: {artifact.get('name')}")
        artifact_rows.append(
            {
                **artifact,
                "path_exists": file_exists,
                "actual_hash": actual_hash,
                "hash_matches": hash_matches if file_exists else False,
            }
        )

    with SessionLocal() as sess:
        saved_run_count = int(sess.query(sa.func.count(BacktestRun.id)).scalar() or 0)
        backtest_trade_count = int(sess.query(sa.func.count(BacktestTrade.id)).scalar() or 0)
        latest_saved_run_id = sess.query(sa.func.max(BacktestRun.id)).scalar()
        auditable_run_count = int(
            (
                sess.query(sa.func.count(BacktestRun.id))
                .filter(
                    sa.or_(
                        BacktestRun.integrity_status.is_(None),
                        BacktestRun.integrity_status.notin_(["invalid-metrics", "missing-trades"]),
                    )
                )
                .scalar()
            )
            or 0
        )

    mvp_symbols: list[dict[str, Any]] = []
    fresh_symbol_count = 0
    for raw_symbol in MVP_RESEARCH_UNIVERSE:
        symbol = str(raw_symbol or "").strip().upper()
        if not symbol:
            continue
        latest_candle = _normalise_utc(get_latest_candle_time(symbol))
        age_minutes = None
        is_fresh = False
        if latest_candle is not None:
            age_minutes = max(0.0, (now_utc - latest_candle).total_seconds() / 60.0)
            is_fresh = age_minutes <= float(MVP_FRESHNESS_MINUTES)
        if latest_candle is None:
            issues.append(f"{symbol} is missing local candles for the MVP research universe.")
        elif not is_fresh:
            issues.append(
                f"{symbol} candles are stale for restart recovery "
                f"({age_minutes:.1f}m old, threshold {MVP_FRESHNESS_MINUTES}m)."
            )
        if is_fresh:
            fresh_symbol_count += 1
        mvp_symbols.append(
            {
                "symbol": symbol,
                "latest_candle_ts": latest_candle.isoformat() if latest_candle else None,
                "age_minutes": age_minutes,
                "is_fresh": is_fresh,
            }
        )

    if not db_exists:
        issues.insert(0, f"Primary DB file is missing: {db_path}")
    if paper_target["configured"] and not paper_target["valid"]:
        issues.append(f"Configured paper target is invalid: {paper_target['error']}")
    if live_target["configured"] and not live_target["valid"]:
        issues.append(f"Configured live target is invalid: {live_target['error']}")

    deduped_issues = list(dict.fromkeys(issue for issue in issues if issue))
    reviewed_plugin_count = sum(1 for item in artifact_rows if item.get("provenance") == "plugin")
    return {
        "db_path": str(db_path),
        "db_exists": db_exists,
        "db_size_bytes": db_size_bytes,
        "backup_root": str(_default_backup_root()),
        "paper_target": paper_target,
        "live_target": live_target,
        "artifact_count": len(artifact_rows),
        "reviewed_plugin_count": reviewed_plugin_count,
        "artifact_missing_count": missing_count,
        "artifact_hash_mismatch_count": hash_mismatch_count,
        "saved_run_count": saved_run_count,
        "auditable_run_count": auditable_run_count,
        "backtest_trade_count": backtest_trade_count,
        "latest_saved_run_id": int(latest_saved_run_id) if latest_saved_run_id else None,
        "mvp_symbols": mvp_symbols,
        "issues": deduped_issues,
        "ready_for_restart": not deduped_issues,
        "artifacts": artifact_rows,
        "generated_at": now_utc.isoformat(),
        "fresh_mvp_symbol_count": fresh_symbol_count,
    }


def create_state_backup(
    destination_dir: str | Path | None = None,
    *,
    include_env: bool = False,
) -> dict[str, Any]:
    """Create a non-destructive local backup of DB state and registered artifacts."""
    audit = evaluate_restart_survival()
    backup_root = Path(destination_dir) if destination_dir is not None else _default_backup_root()
    backup_root.mkdir(parents=True, exist_ok=True)

    timestamp = _utc_now().strftime("%Y%m%dT%H%M%SZ")
    backup_dir = backup_root / f"state_backup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    db_copy_path = None
    source_db = Path(audit["db_path"])
    if source_db.exists():
        db_copy_path = backup_dir / source_db.name
        shutil.copy2(source_db, db_copy_path)

    copied_strategy_files: list[str] = []
    strategy_backup_dir = backup_dir / "strategies"
    strategy_backup_dir.mkdir(exist_ok=True)
    for artifact in audit["artifacts"]:
        source_path = Path(str(artifact.get("path") or ""))
        if not source_path.exists():
            continue
        target_name = f"{artifact['id']}_{source_path.name}"
        target_path = strategy_backup_dir / target_name
        shutil.copy2(source_path, target_path)
        copied_strategy_files.append(str(target_path))

    env_copy_path = None
    if include_env:
        env_source = Path(__file__).resolve().parent.parent / ".env"
        if env_source.exists():
            env_copy_path = backup_dir / ".env"
            shutil.copy2(env_source, env_copy_path)

    manifest = {
        "created_at": _utc_now().isoformat(),
        "backup_dir": str(backup_dir),
        "database_copy": str(db_copy_path) if db_copy_path else None,
        "env_copy": str(env_copy_path) if env_copy_path else None,
        "copied_strategy_files": copied_strategy_files,
        "audit": audit,
    }
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=_json_default),
        encoding="utf-8",
    )
    manifest["manifest_path"] = str(manifest_path)
    return manifest
