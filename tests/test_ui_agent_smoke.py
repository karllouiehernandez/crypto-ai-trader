"""Smoke tests for the UI agent report helpers — no live browser required."""

from __future__ import annotations

import json

import pytest

from tools.ui_agent.report import build_report, write_report


def test_build_report_counts():
    findings = [
        {"feature": "Tab navigation", "status": "PASS", "detail": "all tabs clickable"},
        {"feature": "Run Backtest", "status": "FAIL", "detail": "button not found"},
        {"feature": "Market Focus", "status": "SKIP", "detail": "no data available"},
    ]
    result = build_report(findings, elapsed_seconds=12.5)

    assert result["counts"]["PASS"] == 1
    assert result["counts"]["FAIL"] == 1
    assert result["counts"]["SKIP"] == 1
    assert result["counts"]["PARTIAL"] == 0
    assert result["elapsed_seconds"] == pytest.approx(12.5)
    assert "1/3" in result["summary"]


def test_build_report_empty():
    result = build_report([], elapsed_seconds=0.0)
    assert result["counts"]["PASS"] == 0
    assert "0/0" in result["summary"]


def test_build_report_all_pass():
    findings = [{"feature": f"feature_{i}", "status": "PASS", "detail": "ok"} for i in range(5)]
    result = build_report(findings, elapsed_seconds=30.0)
    assert result["counts"]["PASS"] == 5
    assert "5/5" in result["summary"]


def test_write_report_creates_files(tmp_path):
    findings = [{"feature": "Strategies tab", "status": "PASS", "detail": "loaded ok"}]
    result = build_report(findings, elapsed_seconds=5.0)
    json_path, md_path = write_report(result, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text())
    assert data["counts"]["PASS"] == 1

    md_text = md_path.read_text(encoding="utf-8")
    assert "PASS" in md_text
    assert "Strategies tab" in md_text


def test_write_report_markdown_structure(tmp_path):
    findings = [
        {"feature": "Backtest run", "status": "FAIL", "detail": "error on submit"},
        {"feature": "Chart render", "status": "PARTIAL", "detail": "loads but no candles"},
    ]
    result = build_report(findings, elapsed_seconds=20.0)
    _, md_path = write_report(result, out_dir=tmp_path)
    md_text = md_path.read_text(encoding="utf-8")

    assert "❌" in md_text
    assert "⚠️" in md_text
    assert "## Findings" in md_text
