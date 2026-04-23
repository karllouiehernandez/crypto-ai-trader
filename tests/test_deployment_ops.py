from __future__ import annotations

import json
from pathlib import Path

from deployment.jetson_ops import evaluate_jetson_readiness, format_health_text


def _minimal_restart_report(*, ready: bool = True) -> dict:
    return {
        "ready_for_restart": ready,
        "issues": [] if ready else ["BTCUSDT candles are stale."],
    }


def test_evaluate_jetson_readiness_passes_with_required_assets(tmp_path):
    (tmp_path / "deployment").mkdir()
    (tmp_path / "run_live.py").write_text("", encoding="utf-8")
    (tmp_path / ".env").write_text("LLM_ENABLED=false\n", encoding="utf-8")
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    for name in ["install.sh", "crypto-trader.service", "crypto-trader.logrotate", "jetson_ops.py"]:
        (tmp_path / "deployment" / name).write_text("", encoding="utf-8")

    report = evaluate_jetson_readiness(
        repo_root=tmp_path,
        restart_report=_minimal_restart_report(),
        platform_name="Linux",
        machine="aarch64",
        python_version=(3, 10, 12),
    )

    assert report["ready"] is True
    assert report["status"] == "Ready"
    assert not report["issues"]


def test_evaluate_jetson_readiness_fails_when_required_asset_missing(tmp_path):
    (tmp_path / "deployment").mkdir()
    (tmp_path / "run_live.py").write_text("", encoding="utf-8")
    (tmp_path / "deployment" / "install.sh").write_text("", encoding="utf-8")

    report = evaluate_jetson_readiness(
        repo_root=tmp_path,
        restart_report=_minimal_restart_report(),
        platform_name="Linux",
        machine="aarch64",
        python_version=(3, 10, 12),
    )

    assert report["ready"] is False
    assert any("Systemd service template" in issue for issue in report["issues"])


def test_evaluate_jetson_readiness_includes_restart_issues(tmp_path):
    (tmp_path / "deployment").mkdir()
    (tmp_path / "run_live.py").write_text("", encoding="utf-8")
    for name in ["install.sh", "crypto-trader.service", "crypto-trader.logrotate", "jetson_ops.py"]:
        (tmp_path / "deployment" / name).write_text("", encoding="utf-8")

    report = evaluate_jetson_readiness(
        repo_root=tmp_path,
        restart_report=_minimal_restart_report(ready=False),
        platform_name="Linux",
        machine="aarch64",
        python_version=(3, 10, 12),
    )

    assert report["ready"] is False
    assert any("BTCUSDT candles are stale" in issue for issue in report["issues"])


def test_format_health_text_is_ascii_safe(tmp_path):
    report = {
        "status": "Attention",
        "platform": "linux",
        "machine": "aarch64",
        "python_version": "3.10.12",
        "repo_root": str(tmp_path),
        "checks": [{"name": "DB", "passed": False, "required": True, "detail": "missing"}],
        "issues": ["DB: missing"],
        "warnings": ["not running on Jetson"],
    }
    text = format_health_text(report)
    text.encode("ascii")
    assert "FAIL: DB" in text


def test_health_json_report_is_serializable(tmp_path):
    (tmp_path / "deployment").mkdir()
    (tmp_path / "run_live.py").write_text("", encoding="utf-8")
    for name in ["install.sh", "crypto-trader.service", "crypto-trader.logrotate", "jetson_ops.py"]:
        (tmp_path / "deployment" / name).write_text("", encoding="utf-8")
    report = evaluate_jetson_readiness(repo_root=tmp_path, restart_report=_minimal_restart_report())
    assert json.loads(json.dumps(report))["status"] in {"Ready", "Attention"}
