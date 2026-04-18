"""Helpers for persisted strategy artifacts and promotion lifecycle."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from database.models import SessionLocal, StrategyArtifact, get_app_setting, init_db, set_app_setting
from strategies.loader import list_strategies as list_plugin_strategies
from strategies.loader import load_strategy_path

ACTIVE_PAPER_ARTIFACT_ID_KEY = "active_paper_strategy_artifact_id"
ACTIVE_LIVE_ARTIFACT_ID_KEY = "active_live_strategy_artifact_id"
STRATEGIES_DIR = Path(__file__).resolve().parent.parent / "strategies"

_STATUS_RANK = {
    "draft": 0,
    "reviewed": 1,
    "backtest_passed": 2,
    "paper_candidate": 3,
    "paper_active": 4,
    "paper_passed": 5,
    "live_approved": 6,
    "live_active": 7,
    "archived": 8,
}
_VALID_REVIEW_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NAME_ASSIGNMENT = re.compile(r"(^\s*name\s*=\s*[\"'])([^\"']+)([\"']\s*$)", re.MULTILINE)


def compute_strategy_code_hash(path: str | Path) -> str:
    source = Path(path).read_bytes()
    return hashlib.sha256(source).hexdigest()


def _status_max(current: str | None, desired: str) -> str:
    current_key = str(current or "").lower()
    desired_key = str(desired or "").lower()
    if _STATUS_RANK.get(current_key, -1) >= _STATUS_RANK.get(desired_key, -1):
        return current_key or desired_key
    return desired_key


def _default_status(meta: dict[str, Any]) -> str:
    provenance = str(meta.get("provenance") or meta.get("source") or "plugin").lower()
    return "draft" if provenance == "generated" else "reviewed"


def _artifact_to_dict(row: StrategyArtifact | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row.id,
        "created_at": row.created_at,
        "name": row.name,
        "version": row.version,
        "path": row.path,
        "provenance": row.provenance,
        "code_hash": row.code_hash,
        "status": row.status,
        "reviewed_from_artifact_id": row.reviewed_from_artifact_id,
    }


def get_strategy_artifact(artifact_id: int | None) -> dict[str, Any] | None:
    if not artifact_id:
        return None
    init_db()
    with SessionLocal() as sess:
        return _artifact_to_dict(sess.get(StrategyArtifact, int(artifact_id)))


def register_strategy_artifact(
    meta: dict[str, Any] | None,
    *,
    status_override: str | None = None,
    reviewed_from_artifact_id: int | None = None,
) -> dict[str, Any] | None:
    if not meta:
        return None

    provenance = str(meta.get("provenance") or meta.get("source") or "plugin").lower()
    path = str(meta.get("path") or "").strip()
    name = str(meta.get("name") or "").strip()
    version = str(meta.get("version") or "").strip()
    if provenance == "builtin" or not path or not name or not version or not Path(path).exists():
        return None

    init_db()
    code_hash = compute_strategy_code_hash(path)
    desired_status = status_override or _default_status(meta)

    with SessionLocal() as sess:
        row = (
            sess.query(StrategyArtifact)
            .filter(
                StrategyArtifact.name == name,
                StrategyArtifact.version == version,
                StrategyArtifact.code_hash == code_hash,
            )
            .one_or_none()
        )
        if row is None:
            row = StrategyArtifact(
                name=name,
                version=version,
                path=path,
                provenance=provenance,
                code_hash=code_hash,
                status=desired_status,
                reviewed_from_artifact_id=reviewed_from_artifact_id,
            )
            sess.add(row)
            sess.commit()
            sess.refresh(row)
        else:
            row.path = path
            row.provenance = provenance
            row.reviewed_from_artifact_id = reviewed_from_artifact_id or row.reviewed_from_artifact_id
            row.status = _status_max(row.status, desired_status)
            sess.commit()
            sess.refresh(row)
        return _artifact_to_dict(row)


def sync_strategy_artifacts(catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active_paper_id = get_active_runtime_artifact_id("paper")
    active_live_id = get_active_runtime_artifact_id("live")
    enriched: list[dict[str, Any]] = []
    for item in catalog:
        artifact = register_strategy_artifact(item)
        merged = dict(item)
        if artifact:
            merged.update(
                {
                    "artifact_id": artifact["id"],
                    "artifact_status": artifact["status"],
                    "artifact_code_hash": artifact["code_hash"],
                    "reviewed_from_artifact_id": artifact["reviewed_from_artifact_id"],
                    "active_paper_artifact": artifact["id"] == active_paper_id,
                    "active_live_artifact": artifact["id"] == active_live_id,
                }
            )
        else:
            merged.update(
                {
                    "artifact_id": None,
                    "artifact_status": "",
                    "artifact_code_hash": "",
                    "reviewed_from_artifact_id": None,
                    "active_paper_artifact": False,
                    "active_live_artifact": False,
                }
            )
        enriched.append(merged)
    return enriched


def _runtime_setting_key(run_mode: str) -> str:
    clean_mode = str(run_mode or "").strip().lower()
    if clean_mode not in {"paper", "live"}:
        raise ValueError(f"Unsupported runtime mode: {run_mode}")
    return ACTIVE_PAPER_ARTIFACT_ID_KEY if clean_mode == "paper" else ACTIVE_LIVE_ARTIFACT_ID_KEY


def get_active_runtime_artifact_id(run_mode: str) -> int | None:
    init_db()
    key = _runtime_setting_key(run_mode)
    with SessionLocal() as sess:
        raw = get_app_setting(sess, key, "")
    if raw in {None, ""}:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def set_active_runtime_artifact_id(run_mode: str, artifact_id: int | None) -> None:
    init_db()
    key = _runtime_setting_key(run_mode)
    with SessionLocal() as sess:
        set_app_setting(sess, key, "" if artifact_id in {None, 0} else str(int(artifact_id)))
        sess.commit()


def _get_plugin_meta_by_path(path: Path) -> dict[str, Any] | None:
    for item in list_plugin_strategies():
        if str(item.get("path") or "") == str(path):
            return item
    return None


def review_generated_strategy(source_artifact_id: int, reviewed_name: str) -> dict[str, Any]:
    source_artifact = get_strategy_artifact(source_artifact_id)
    if not source_artifact:
        raise ValueError("Generated draft artifact could not be found")
    if source_artifact["provenance"] != "generated":
        raise ValueError("Only generated draft artifacts can be reviewed into a stable plugin")

    clean_name = str(reviewed_name or "").strip()
    if not _VALID_REVIEW_NAME.fullmatch(clean_name):
        raise ValueError("Reviewed plugin name must be a valid Python-style identifier")
    if clean_name.startswith("generated_"):
        raise ValueError("Reviewed plugin name cannot start with generated_")

    source_path = Path(source_artifact["path"])
    if not source_path.exists():
        raise ValueError("Generated draft file is missing on disk")

    target_path = STRATEGIES_DIR / f"{clean_name}.py"
    if target_path.exists():
        raise ValueError(f"Reviewed plugin file already exists: {target_path.name}")

    source = source_path.read_text(encoding="utf-8")
    if not _NAME_ASSIGNMENT.search(source):
        raise ValueError("Strategy file does not declare a top-level StrategyBase name")
    rewritten = _NAME_ASSIGNMENT.sub(rf"\1{clean_name}\3", source, count=1)
    rewritten = rewritten.replace("# GENERATED STRATEGY DRAFT", "# REVIEWED STRATEGY PLUGIN", 1)

    target_path.write_text(rewritten, encoding="utf-8")
    load_strategy_path(target_path)
    reviewed_meta = _get_plugin_meta_by_path(target_path)
    if reviewed_meta is None:
        raise ValueError("Reviewed plugin could not be loaded after save")

    artifact = register_strategy_artifact(
        reviewed_meta,
        status_override="reviewed",
        reviewed_from_artifact_id=source_artifact_id,
    )
    if artifact is None:
        raise ValueError("Reviewed plugin artifact could not be registered")
    return {
        "artifact": artifact,
        "strategy": {
            **reviewed_meta,
            "artifact_id": artifact["id"],
            "artifact_status": artifact["status"],
            "artifact_code_hash": artifact["code_hash"],
        },
    }


def _require_runtime_eligible_artifact(artifact_id: int) -> dict[str, Any]:
    artifact = get_strategy_artifact(artifact_id)
    if not artifact:
        raise ValueError("Strategy artifact could not be found")
    if artifact["provenance"] != "plugin":
        raise ValueError("Only reviewed plugins may be promoted to paper/live")
    if not artifact["path"] or not Path(artifact["path"]).exists():
        raise ValueError("Strategy artifact file is missing on disk")
    return artifact


def _has_passing_backtest(artifact_id: int) -> bool:
    from database.models import BacktestRun

    init_db()
    with SessionLocal() as sess:
        return (
            sess.query(BacktestRun)
            .filter(
                BacktestRun.artifact_id == int(artifact_id),
                BacktestRun.status == "passed",
            )
            .count()
            > 0
        )


def _set_artifact_status(artifact_id: int, desired_status: str, *, preserve_max: bool = True) -> dict[str, Any]:
    init_db()
    with SessionLocal() as sess:
        row = sess.get(StrategyArtifact, int(artifact_id))
        if row is None:
            raise ValueError("Strategy artifact could not be found")
        row.status = _status_max(row.status, desired_status) if preserve_max else desired_status
        sess.commit()
        sess.refresh(row)
        return _artifact_to_dict(row) or {}


def mark_artifact_backtest_result(artifact_id: int | None, passed: bool) -> dict[str, Any] | None:
    if not artifact_id or not passed:
        return get_strategy_artifact(artifact_id)
    return _set_artifact_status(int(artifact_id), "backtest_passed")


def promote_artifact_to_paper(artifact_id: int) -> dict[str, Any]:
    artifact = _require_runtime_eligible_artifact(artifact_id)
    if not _has_passing_backtest(artifact_id):
        raise ValueError("This reviewed plugin needs at least one passing backtest before paper promotion")

    current_paper_id = get_active_runtime_artifact_id("paper")
    if current_paper_id and current_paper_id != artifact_id:
        previous = get_strategy_artifact(current_paper_id)
        if previous and previous["status"] == "paper_active":
            _set_artifact_status(current_paper_id, "backtest_passed", preserve_max=False)

    promoted = _set_artifact_status(artifact_id, "paper_active")
    set_active_runtime_artifact_id("paper", artifact_id)
    return promoted


def mark_artifact_paper_passed(artifact_id: int | None) -> dict[str, Any] | None:
    if not artifact_id:
        return None
    return _set_artifact_status(int(artifact_id), "paper_passed")


def approve_artifact_for_live(artifact_id: int) -> dict[str, Any]:
    artifact = _require_runtime_eligible_artifact(artifact_id)
    if artifact["status"] not in {"paper_passed", "live_approved", "live_active"}:
        raise ValueError("Only reviewed plugins that have passed paper evaluation can be approved for live")

    current_live_id = get_active_runtime_artifact_id("live")
    if current_live_id and current_live_id != artifact_id:
        previous = get_strategy_artifact(current_live_id)
        if previous and previous["status"] in {"live_approved", "live_active"}:
            _set_artifact_status(current_live_id, "paper_passed", preserve_max=False)

    approved = _set_artifact_status(artifact_id, "live_approved")
    set_active_runtime_artifact_id("live", artifact_id)
    return approved


def mark_artifact_live_active(artifact_id: int | None) -> dict[str, Any] | None:
    if not artifact_id:
        return None
    return _set_artifact_status(int(artifact_id), "live_active")


def validate_runtime_artifact(artifact_id: int | None) -> tuple[dict[str, Any] | None, str | None]:
    artifact = get_strategy_artifact(artifact_id)
    if not artifact_id or artifact is None:
        return None, "No promoted strategy artifact is configured for this runtime mode."
    if artifact["provenance"] != "plugin":
        return None, "Only reviewed plugin artifacts may run in paper/live."
    artifact_path = Path(str(artifact.get("path") or ""))
    if not artifact_path.exists():
        return None, f"Strategy artifact file is missing: {artifact_path}"
    actual_hash = compute_strategy_code_hash(artifact_path)
    if actual_hash != artifact.get("code_hash"):
        return None, (
            "Strategy artifact hash mismatch. The plugin file changed after promotion; "
            "review and promote the updated file again."
        )
    return artifact, None
