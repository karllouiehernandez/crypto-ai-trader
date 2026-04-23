"""Jetson deployment readiness and maintenance CLI."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any

from database.persistence import create_state_backup, evaluate_restart_survival, restore_state_backup
from strategy.artifacts import repin_reviewed_artifact_hash


REPO_ROOT = Path(__file__).resolve().parent.parent


def evaluate_jetson_readiness(
    *,
    repo_root: str | Path | None = None,
    restart_report: dict[str, Any] | None = None,
    platform_name: str | None = None,
    machine: str | None = None,
    python_version: tuple[int, int, int] | None = None,
) -> dict[str, Any]:
    """Return an operator-facing Jetson deployment readiness report."""
    root = Path(repo_root or REPO_ROOT).resolve()
    platform_name = (platform_name or platform.system()).lower()
    machine = (machine or platform.machine()).lower()
    python_version = python_version or sys.version_info[:3]
    restart_report = restart_report if restart_report is not None else evaluate_restart_survival()

    is_linux = platform_name == "linux"
    is_arm = machine in {"aarch64", "arm64", "armv7l", "armv8l"} or machine.startswith("arm")
    is_jetson_hint = (Path("/etc/nv_tegra_release").exists() if is_linux else False) or is_arm

    checks = [
        _check("Linux host", is_linux, platform_name, required=False),
        _check("Jetson/ARM host", is_jetson_hint, machine, required=False),
        _check("Python 3.10+", python_version >= (3, 10, 0), ".".join(map(str, python_version)), required=True),
        _check("Repository root", (root / "run_live.py").exists(), str(root), required=True),
        _check(".env present", (root / ".env").exists(), str(root / ".env"), required=False),
        _check("Virtualenv present", _venv_python(root).exists(), str(_venv_python(root)), required=False),
        _check("Install script", (root / "deployment" / "install.sh").exists(), "deployment/install.sh", required=True),
        _check("Systemd service template", (root / "deployment" / "crypto-trader.service").exists(), "deployment/crypto-trader.service", required=True),
        _check("Logrotate template", (root / "deployment" / "crypto-trader.logrotate").exists(), "deployment/crypto-trader.logrotate", required=True),
        _check("Health CLI", (root / "deployment" / "jetson_ops.py").exists(), "python -m deployment.jetson_ops health", required=True),
        _check("DB restart survival", bool(restart_report.get("ready_for_restart")), "database + artifact + data freshness audit", required=True),
    ]

    issues = [
        f"{item['name']}: {item['detail']}"
        for item in checks
        if item["required"] and not item["passed"]
    ]
    warnings = [
        f"{item['name']}: {item['detail']}"
        for item in checks
        if not item["required"] and not item["passed"]
    ]
    for issue in restart_report.get("issues") or []:
        if issue not in issues:
            issues.append(str(issue))
    for warning in restart_report.get("artifact_warnings") or []:
        if warning not in warnings:
            warnings.append(str(warning))

    ready = not issues
    return {
        "ready": ready,
        "status": "Ready" if ready else "Attention",
        "repo_root": str(root),
        "platform": platform_name,
        "machine": machine,
        "python_version": ".".join(map(str, python_version)),
        "is_linux": is_linux,
        "is_jetson_hint": is_jetson_hint,
        "checks": checks,
        "issues": issues,
        "warnings": warnings,
        "restart_report": restart_report,
        "commands": {
            "install": "bash deployment/install.sh",
            "health": "python -m deployment.jetson_ops health",
            "backup": "python -m deployment.jetson_ops backup",
            "restore_dry_run": "python -m deployment.jetson_ops restore backups/<backup>/manifest.json",
            "restore_apply": "python -m deployment.jetson_ops restore backups/<backup>/manifest.json --apply",
            "service_status": "sudo systemctl status crypto-trader",
            "service_logs": "journalctl -fu crypto-trader",
        },
    }


def format_health_text(report: dict[str, Any]) -> str:
    """Return ASCII-safe terminal output for deployment health."""
    lines = [
        "Jetson Deployment Health",
        f"Status: {report.get('status')}",
        f"Host: {report.get('platform')} / {report.get('machine')}",
        f"Python: {report.get('python_version')}",
        f"Repo: {report.get('repo_root')}",
        "",
        "Checks:",
    ]
    for check in report.get("checks") or []:
        marker = "PASS" if check.get("passed") else ("WARN" if not check.get("required") else "FAIL")
        lines.append(f"- {marker}: {check.get('name')} ({check.get('detail')})")
    if report.get("issues"):
        lines.extend(["", "Issues:"])
        lines.extend(f"- {issue}" for issue in report["issues"])
    if report.get("warnings"):
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jetson deployment operations")
    sub = parser.add_subparsers(dest="command", required=True)

    health = sub.add_parser("health", help="Print deployment readiness")
    health.add_argument("--json", action="store_true", help="Print JSON report")
    health.add_argument("--strict", action="store_true", help="Return non-zero when readiness has required issues")

    backup = sub.add_parser("backup", help="Create a DB + strategy state backup")
    backup.add_argument("--dest", default="", help="Backup root directory")
    backup.add_argument("--include-env", action="store_true", help="Also copy .env into the backup")

    restore = sub.add_parser("restore", help="Plan or apply a state restore from a backup manifest")
    restore.add_argument("manifest", help="Path to backup manifest.json")
    restore.add_argument("--apply", action="store_true", help="Actually copy files. Without this, only a dry run is printed.")
    restore.add_argument("--include-env", action="store_true", help="Restore .env only when the backup includes it")

    repin = sub.add_parser("repin-artifact", help="Acknowledge a reviewed plugin file update by refreshing one artifact hash")
    repin.add_argument("artifact_id", type=int, help="Reviewed plugin artifact id")
    repin.add_argument("--apply", action="store_true", help="Actually update the artifact hash. Without this, only the current mismatch is reported.")

    args = parser.parse_args(argv)

    if args.command == "health":
        report = evaluate_jetson_readiness()
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True, default=str))
        else:
            print(format_health_text(report))
        return 1 if args.strict and not report["ready"] else 0

    if args.command == "backup":
        result = create_state_backup(args.dest or None, include_env=args.include_env)
        print(f"Backup created: {result['backup_dir']}")
        print(f"Manifest: {result['manifest_path']}")
        return 0

    if args.command == "restore":
        result = restore_state_backup(args.manifest, apply=args.apply, include_env=args.include_env)
        action = "Restore applied" if result["applied"] else "Restore dry run"
        print(f"{action}: {result['manifest_path']}")
        if result.get("pre_restore_backup"):
            print(f"Pre-restore backup: {result['pre_restore_backup']['backup_dir']}")
        for warning in result.get("warnings") or []:
            print(f"WARNING: {warning}")
        for operation in result.get("operations") or []:
            print(f"- {operation['type']}: {operation['source']} -> {operation['target']}")
        return 0

    if args.command == "repin-artifact":
        if not args.apply:
            print(f"Dry run: artifact #{args.artifact_id} would be repinned to the current file hash.")
            print("Re-run with --apply after reviewing the file change.")
            return 0
        backup_result = create_state_backup()
        result = repin_reviewed_artifact_hash(args.artifact_id)
        print(
            f"Artifact #{result['old_artifact_id']} repinned to #{result['id']}: changed={result['changed']} "
            f"old={str(result.get('old_code_hash') or '')[:12]} new={str(result.get('code_hash') or '')[:12]}"
        )
        if result.get("moved_runtime_modes"):
            print(f"Runtime target moved: {', '.join(result['moved_runtime_modes'])}")
        print(f"Pre-repin backup: {backup_result['backup_dir']}")
        return 0

    return 2


def _check(name: str, passed: bool, detail: str, *, required: bool) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": str(detail), "required": required}


def _venv_python(root: Path) -> Path:
    linux_python = root / ".venv" / "bin" / "python"
    if linux_python.exists():
        return linux_python
    return root / ".venv" / "Scripts" / "python.exe"


if __name__ == "__main__":
    raise SystemExit(main())
