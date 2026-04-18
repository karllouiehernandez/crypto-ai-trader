"""Report generation for the AI UI testing agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


_STATUS_ICONS = {"PASS": "✅", "FAIL": "❌", "PARTIAL": "⚠️", "SKIP": "⏭️"}


def build_report(findings: list[dict], elapsed_seconds: float) -> dict:
    """Summarise agent findings into a structured report dict."""
    counts: dict[str, int] = {"PASS": 0, "FAIL": 0, "PARTIAL": 0, "SKIP": 0}
    for f in findings:
        status = f.get("status", "SKIP")
        counts[status] = counts.get(status, 0) + 1

    total = len(findings)
    pass_rate = counts["PASS"] / total * 100 if total else 0.0
    summary = (
        f"{counts['PASS']}/{total} features passed ({pass_rate:.0f}%) "
        f"in {elapsed_seconds:.1f}s — "
        f"{counts['FAIL']} failed, {counts['PARTIAL']} partial, {counts['SKIP']} skipped."
    )

    return {
        "summary": summary,
        "elapsed_seconds": elapsed_seconds,
        "counts": counts,
        "findings": findings,
    }


def write_report(report: dict, out_dir: Path = Path("reports")) -> tuple[Path, Path]:
    """Write JSON + Markdown report files. Returns (json_path, md_path)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"ui_test_{ts}.json"
    md_path = out_dir / f"ui_test_{ts}.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    counts = report["counts"]
    lines = [
        f"# UI Test Report — {ts}",
        "",
        f"> {report['summary']}",
        "",
        "| Status | Count |",
        "|--------|-------|",
        f"| ✅ PASS | {counts['PASS']} |",
        f"| ❌ FAIL | {counts['FAIL']} |",
        f"| ⚠️ PARTIAL | {counts['PARTIAL']} |",
        f"| ⏭️ SKIP | {counts['SKIP']} |",
        "",
        "## Findings",
        "",
    ]
    for f in report["findings"]:
        icon = _STATUS_ICONS.get(f.get("status", "SKIP"), "❓")
        lines.append(f"- {icon} **{f.get('feature', '?')}** — {f.get('detail', '')}")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return json_path, md_path
