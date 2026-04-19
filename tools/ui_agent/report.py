"""Report generation for the AI UI testing agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


_STATUS_ICONS = {"PASS": "✅", "FAIL": "❌", "PARTIAL": "⚠️", "SKIP": "⏭️"}


def build_report(findings: list[dict], elapsed_seconds: float, journey: dict | None = None) -> dict:
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

    result = {
        "summary": summary,
        "elapsed_seconds": elapsed_seconds,
        "counts": counts,
        "findings": findings,
    }
    if journey:
        result["journey"] = journey
    return result


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

    journey = report.get("journey")
    if journey:
        summary = journey.get("summary", {})
        lines.extend([
            "",
            "## Trader Journey Summary",
            "",
            f"- Total strategies discovered: {summary.get('total_strategies', 0)}",
            f"- Strategies successfully backtested: {summary.get('strategies_successfully_backtested', 0)}",
            f"- Strategies with complete Inspect surfaces: {summary.get('strategies_with_complete_inspect', 0)}",
            f"- Strategies blocked by missing data: {summary.get('strategies_blocked_by_missing_data', 0)}",
            f"- Reviewed strategies eligible for paper: {summary.get('reviewed_strategies_eligible_for_paper', 0)}",
            f"- Reviewed strategies blocked from live: {summary.get('reviewed_strategies_blocked_from_live', 0)}",
            "",
            "## Strategy Audit",
            "",
        ])
        for item in journey.get("strategies", []):
            lines.append(
                "- "
                f"**{item.get('strategy_name', '?')}** — provenance `{item.get('provenance', 'unknown')}`; "
                f"backtest `{item.get('backtest_status', 'unknown')}`; "
                f"run `{item.get('run_id') or '—'}`; "
                f"gate `{item.get('gate_outcome', 'unknown')}`; "
                f"inspect_complete `{bool(item.get('inspect_complete'))}`; "
                f"paper `{item.get('promote_paper_state', 'missing')}`; "
                f"live `{item.get('approve_live_state', 'missing')}`"
            )

        concerns = journey.get("operator_concerns", [])
        lines.extend(["", "## Operator Concerns", ""])
        if concerns:
            for concern in concerns:
                lines.append(f"- {concern}")
        else:
            lines.append("- None.")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return json_path, md_path
