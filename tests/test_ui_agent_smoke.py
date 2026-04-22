"""Smoke tests for the UI agent report helpers — no live browser required."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

import run_ui_agent
from tools.ui_agent.report import build_report, write_report
from tools.ui_agent.trader_journey import (
    _extract_last_backtest_attempt,
    _last_backtest_attempt_matches_strategy,
)


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


def test_build_report_includes_trader_journey_payload():
    journey = {
        "journey_type": "trader",
        "summary": {"total_strategies": 2},
        "strategies": [{"strategy_name": "mean_reversion_v1"}],
        "operator_concerns": ["inspect incomplete"],
    }
    result = build_report([], elapsed_seconds=1.0, journey=journey)

    assert result["journey"]["journey_type"] == "trader"
    assert result["journey"]["summary"]["total_strategies"] == 2


def test_write_report_renders_trader_journey_sections(tmp_path):
    result = build_report(
        [{"feature": "Trader journey discovery", "status": "PASS", "detail": "found strategies"}],
        elapsed_seconds=3.0,
        journey={
            "journey_type": "trader",
            "summary": {
                "total_strategies": 2,
                "strategies_successfully_backtested": 1,
                "strategies_with_complete_inspect": 1,
                "strategies_blocked_by_missing_data": 1,
                "reviewed_strategies_eligible_for_paper": 1,
                "reviewed_strategies_blocked_from_live": 1,
            },
            "strategies": [
                {
                    "strategy_name": "mean_reversion_v1",
                    "provenance": "builtin",
                    "backtest_status": "saved",
                    "run_id": 123,
                    "gate_outcome": "failed",
                    "inspect_complete": True,
                    "promote_paper_state": "disabled",
                    "approve_live_state": "disabled",
                }
            ],
            "operator_concerns": ["generated draft is blocked from paper promotion"],
        },
    )
    _, md_path = write_report(result, out_dir=tmp_path)
    md_text = md_path.read_text(encoding="utf-8")

    assert "## Trader Journey Summary" in md_text
    assert "## Strategy Audit" in md_text
    assert "## Operator Concerns" in md_text
    assert "mean_reversion_v1" in md_text


def test_run_ui_agent_data_only_stdout_is_ascii_safe(capsys):
    fake_result = {"summary": "1/1 passed"}

    with patch("sys.argv", ["run_ui_agent.py", "--data-only"]), \
         patch("run_ui_agent.data_checks.run_data_checks", return_value=[]), \
         patch("run_ui_agent.report.build_report", return_value=fake_result), \
         patch("run_ui_agent.report.write_report", return_value=("report.json", "report.md")):
        run_ui_agent.main()

    output = capsys.readouterr().out
    output.encode("cp1252")
    assert "Pass 2" in output
    assert "->" not in output
    assert "──" not in output


def test_run_ui_agent_trader_journey_invokes_runner():
    fake_result = {"summary": "2/2 passed"}

    with patch("sys.argv", ["run_ui_agent.py", "--ui-only", "--journey", "trader"]), \
         patch("run_ui_agent.browser.launch", return_value=("pw", "browser", "page")), \
         patch("run_ui_agent.browser.close"), \
         patch("run_ui_agent.trader_journey.run_trader_journey", return_value=([], {"journey_type": "trader"})) as journey_mock, \
         patch("run_ui_agent.report.build_report", return_value=fake_result), \
         patch("run_ui_agent.report.write_report", return_value=("report.json", "report.md")):
        run_ui_agent.main()

    journey_mock.assert_called_once_with("page", verbose=True)


def test_extract_last_backtest_attempt_parses_latest_attempt_block():
    body = """
    Backtest Lab
    Last Backtest Attempt

    21:03:32 · generated_range_probe_v1 · BTCUSDT · 2026-04-15 -> 2026-04-21

    Run failed: 'bb_upper'
    """

    attempt = _extract_last_backtest_attempt(body)

    assert attempt == {
        "meta": "21:03:32 · generated_range_probe_v1 · BTCUSDT · 2026-04-15 -> 2026-04-21",
        "detail": "Run failed: 'bb_upper'",
    }


def test_last_backtest_attempt_match_ignores_other_strategy_mentions_on_page():
    body = """
    Last Backtest Attempt

    21:03:32 · generated_range_probe_v1 · BTCUSDT · 2026-04-15 -> 2026-04-21

    Run failed: 'bb_upper'

    rsi_mean_reversion_v1 is ranked #2 in saved evaluations.
    """

    assert _last_backtest_attempt_matches_strategy(body, "generated_range_probe_v1") is True
    assert _last_backtest_attempt_matches_strategy(body, "rsi_mean_reversion_v1") is False
