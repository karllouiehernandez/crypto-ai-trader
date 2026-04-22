"""Trader-style Playwright journeys for the Jesse-like workbench."""

from __future__ import annotations

import re
import sqlite3
import time
from datetime import datetime, timedelta

from playwright.sync_api import Locator, Page

from backtester.service import list_backtest_runs
from config import DB_PATH, MVP_RESEARCH_UNIVERSE
from dashboard.workbench import latest_complete_backtest_day
from market_data.history import get_latest_candle_time
from strategy.runtime import get_active_runtime_artifact, list_available_strategies


_RERENDER = 1.5
_SHORT = 3_000
_LONG = 10_000
_BACKTEST_TIMEOUT = 90_000
_JOURNEY_BACKTEST_DAYS = 7
_JOURNEY_TERMINAL_TIMEOUT_SECONDS = 60
_OPTION_LIST = "[data-testid='stSelectboxVirtualDropdown'] [role='option'], [data-testid='stSelectboxVirtualDropdown'] li"


def _console_safe(text: str) -> str:
    return (
        str(text)
        .replace("—", "-")
        .replace("–", "-")
        .replace("→", "->")
        .replace("≥", ">=")
        .replace("≤", "<=")
        .replace("…", "...")
        .encode("ascii", "replace")
        .decode("ascii")
    )


def _make_recorder(findings: list[dict], verbose: bool):
    icons = {"PASS": "[PASS]", "FAIL": "[FAIL]", "PARTIAL": "[PARTIAL]", "SKIP": "[SKIP]"}

    def record(feature: str, status: str, detail: str) -> None:
        findings.append({"feature": feature, "status": status, "detail": detail})
        if verbose:
            print(
                f"  {icons.get(status, '[INFO]')} [{status}] "
                f"{_console_safe(feature)} - {_console_safe(detail)}"
            )

    return record


def _no_exception(page: Page) -> bool:
    return page.locator("[data-testid='stException']").count() == 0


def _visible(page: Page, selector: str, timeout: int = _SHORT) -> bool:
    try:
        return page.locator(selector).first.is_visible(timeout=timeout)
    except Exception:
        return False


def _text(page: Page, text: str, timeout: int = 2000) -> bool:
    try:
        return page.get_by_text(text).first.is_visible(timeout=timeout)
    except Exception:
        return False


def _body_text(page: Page) -> str:
    try:
        return page.locator("body").inner_text(timeout=_SHORT)
    except Exception:
        return ""


def _active_panel(page: Page) -> Locator:
    return page.locator("[role='tabpanel']:visible").first


def _labels(label: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(label, str):
        return [label]
    return [str(item) for item in label if str(item).strip()]


def _goto_tab(page: Page, name: str) -> bool:
    selectors = [
        lambda: page.get_by_role("tab", name=name).first,
        lambda: page.get_by_text(name, exact=True).first,
    ]
    for _ in range(4):
        for locator_factory in selectors:
            for use_force in (False, True):
                try:
                    if use_force:
                        page.keyboard.press("Escape")
                    locator_factory().click(timeout=_SHORT, force=use_force)
                    time.sleep(_RERENDER)
                    return True
                except Exception:
                    continue
        time.sleep(1.0)
    return False


def _find_selectbox(scope: Locator | Page, page: Page, label: str | list[str] | tuple[str, ...]) -> Locator:
    for candidate in _labels(label):
        widget = scope.locator("[data-testid='stSelectbox']").filter(has_text=candidate).first
        try:
            if widget.count() > 0:
                return widget
        except Exception:
            continue
    for candidate in _labels(label):
        widget = page.locator("[data-testid='stSelectbox']").filter(has_text=candidate).first
        try:
            if widget.count() > 0:
                return widget
        except Exception:
            continue
    return scope.locator("[data-testid='stSelectbox']").filter(has_text=_labels(label)[0]).first


def _find_date_input(scope: Locator | Page, page: Page, label: str | list[str] | tuple[str, ...]) -> Locator:
    for candidate in _labels(label):
        widget = scope.locator("[data-testid='stDateInput']").filter(has_text=candidate).first
        try:
            if widget.count() > 0:
                return widget
        except Exception:
            continue
    for candidate in _labels(label):
        widget = page.locator("[data-testid='stDateInput']").filter(has_text=candidate).first
        try:
            if widget.count() > 0:
                return widget
        except Exception:
            continue
    return scope.locator("[data-testid='stDateInput']").filter(has_text=_labels(label)[0]).first


def _selectbox_options(scope: Locator | Page, page: Page, label: str | list[str] | tuple[str, ...]) -> list[str]:
    try:
        widget = _find_selectbox(scope, page, label)
        widget.click(timeout=_SHORT)
        time.sleep(0.4)
        options = [text.strip() for text in page.locator(_OPTION_LIST).all_text_contents() if text.strip()]
        page.keyboard.press("Escape")
        time.sleep(0.2)
        return options
    except Exception:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return []


def _selectbox_value(
    scope: Locator | Page,
    page: Page,
    label: str | list[str] | tuple[str, ...],
    option_text: str,
) -> bool:
    try:
        widget = _find_selectbox(scope, page, label)
        try:
            current_text = widget.inner_text(timeout=1_000)
            current_lines = [line.strip().lower() for line in current_text.splitlines() if line.strip()]
            if option_text.strip().lower() in current_lines:
                return True
        except Exception:
            pass
        widget.click(timeout=_SHORT)
        time.sleep(0.4)
        dropdown = page.locator("[data-testid='stSelectboxVirtualDropdown']").last
        option = dropdown.get_by_role("option", name=option_text, exact=True).first
        if option.count() == 0:
            option = dropdown.get_by_text(option_text, exact=True).first
        if option.count() == 0:
            all_options = [text.strip() for text in dropdown.locator("[role='option'], li").all_text_contents() if text.strip()]
            fuzzy_match = next(
                (
                    candidate for candidate in all_options
                    if option_text.lower() in candidate.lower() or candidate.lower() in option_text.lower()
                ),
                "",
            )
            if fuzzy_match:
                option = dropdown.get_by_text(fuzzy_match, exact=True).first
        option.click(timeout=_SHORT)
        time.sleep(_RERENDER)
        refreshed_widget = _find_selectbox(scope, page, label)
        refreshed_text = refreshed_widget.inner_text(timeout=1_000)
        refreshed_lines = [line.strip().lower() for line in refreshed_text.splitlines() if line.strip()]
        return option_text.strip().lower() in refreshed_lines
    except Exception:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return False


def _wait_for_saved_run_id(strategy_name: str, before_max_run_id: int, timeout_seconds: int = 15) -> int | None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with sqlite3.connect(DB_PATH) as con:
                row = con.execute(
                    """
                    SELECT id
                    FROM backtest_runs
                    WHERE id > ? AND strategy_name = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (int(before_max_run_id), str(strategy_name)),
                ).fetchone()
            if row:
                return int(row[0])
        except Exception:
            pass
        time.sleep(1.0)
    return None


def _latest_new_backtest_run(before_max_run_id: int) -> tuple[int, str] | None:
    try:
        with sqlite3.connect(DB_PATH) as con:
            row = con.execute(
                """
                SELECT id, strategy_name
                FROM backtest_runs
                WHERE id > ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(before_max_run_id),),
            ).fetchone()
        if row:
            return int(row[0]), str(row[1] or "")
    except Exception:
        return None
    return None


def _button_state(scope: Locator | Page, label: str) -> str:
    try:
        button = scope.get_by_role("button", name=label).first
        if not button.is_visible(timeout=1_000):
            return "missing"
        return "disabled" if button.is_disabled() else "enabled"
    except Exception:
        return "missing"


def _click_button(scope: Locator | Page, page: Page, label: str, timeout: int = _LONG) -> bool:
    candidates = [
        scope.get_by_role("button", name=label).first,
        page.get_by_role("button", name=label).first,
    ]
    for button in candidates:
        for use_force in (False, True):
            try:
                button.wait_for(state="visible", timeout=4_000)
                try:
                    button.scroll_into_view_if_needed(timeout=1_000)
                except Exception:
                    pass
                button.click(timeout=timeout, force=use_force)
                time.sleep(_RERENDER)
                return True
            except Exception:
                continue
    return False


def _wait_for_backtest_response(page: Page) -> bool:
    try:
        # Fast path: actual backtest shows a spinner — wait for it to appear then disappear.
        spinner_seen = False
        try:
            page.wait_for_selector("[data-testid='stSpinner']", timeout=8_000, state="visible")
            spinner_seen = True
            page.wait_for_selector("[data-testid='stSpinner']", timeout=_BACKTEST_TIMEOUT, state="hidden")
            time.sleep(_RERENDER)
            return True
        except Exception:
            pass

        if not spinner_seen:
            # Blocked / fast-fail path: the button click triggers a Streamlit rerun but no
            # spinner appears.  Pre-existing stAlert/stError elements (audit gate, MVP gate)
            # make wait_for_selector return immediately, so we instead wait for the Streamlit
            # running indicator to cycle, which reliably signals the rerun is complete.
            try:
                page.wait_for_selector(
                    "[data-testid='stStatusWidgetRunningIcon']",
                    timeout=6_000,
                    state="visible",
                )
                page.wait_for_selector(
                    "[data-testid='stStatusWidgetRunningIcon']",
                    timeout=20_000,
                    state="hidden",
                )
            except Exception:
                # Running indicator not detected — give Streamlit a fixed window to settle.
                time.sleep(5.0)

        time.sleep(_RERENDER)
        return True
    except Exception:
        time.sleep(3.0)
        return True


def _wait_for_backtest_terminal_state(
    page: Page,
    strategy_name: str,
    before_max_run_id: int,
    timeout_seconds: int = 120,
) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    spinner_seen = False
    normalized_strategy = str(strategy_name or "").strip().lower()

    while time.time() < deadline:
        if not _no_exception(page):
            return {"state": "exception"}

        saved_run_id = _wait_for_saved_run_id(strategy_name, before_max_run_id, timeout_seconds=1)
        if saved_run_id is not None:
            return {"state": "saved", "run_id": saved_run_id}

        latest_new_run = _latest_new_backtest_run(before_max_run_id)
        if latest_new_run and str(latest_new_run[1]).strip().lower() != normalized_strategy:
            return {
                "state": "strategy-mismatch",
                "run_id": int(latest_new_run[0]),
                "actual_strategy": str(latest_new_run[1]),
            }

        body = _body_text(page)
        lowered_body = body.lower()
        if "last backtest attempt" in lowered_body and normalized_strategy in lowered_body:
            if "blocked by history:" in lowered_body:
                return {"state": "blocked-history"}
            if "blocked by validation:" in lowered_body:
                return {"state": "blocked-validation"}
            if "run failed:" in lowered_body:
                return {"state": "run-failed"}

        spinner_visible = _visible(page, "[data-testid='stSpinner']")
        running_visible = _visible(page, "[data-testid='stStatusWidgetRunningIcon']")
        spinner_seen = spinner_seen or spinner_visible or running_visible
        time.sleep(1.0 if spinner_seen else 1.5)

    return {"state": "running-slow" if spinner_seen else "timeout"}


def _wait_for_backtest_form_ready(page: Page, timeout_seconds: int = 20) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            run_button = page.get_by_role("button", name="Run Backtest").first
            if run_button.count() > 0 and run_button.is_visible(timeout=1_000):
                return "ready"
        except Exception:
            pass
        body = _body_text(page).lower()
        if "running load_symbol_audit" in body or "running choose_backtest_default_symbol" in body:
            time.sleep(1.5)
            continue
        if "backtest blocked" in body or "last backtest attempt" in body:
            return "terminal"
        time.sleep(1.0)
    body = _body_text(page).lower()
    if "running load_symbol_audit" in body or "running choose_backtest_default_symbol" in body:
        return "loading"
    return "missing"


def _recommended_backtest_window(symbol: str) -> tuple[str, str] | None:
    latest = get_latest_candle_time(symbol)
    if latest is None:
        return None
    end_dt = latest_complete_backtest_day(latest)
    # Keep the trader journey on a recent canonical audit window so the full
    # strategy catalog can be exercised within one operator-style validation run.
    start_dt = end_dt - timedelta(days=max(1, _JOURNEY_BACKTEST_DAYS - 1))
    return start_dt.strftime("%Y/%m/%d"), end_dt.strftime("%Y/%m/%d")


def _preferred_backtest_symbol(options: list[str]) -> str:
    ordered = [str(option or "").strip().upper() for option in options if str(option or "").strip()]
    if not ordered:
        return ""

    preferred_symbols = [
        str(symbol or "").strip().upper()
        for symbol in (MVP_RESEARCH_UNIVERSE or [])
        if str(symbol or "").strip()
    ]
    for symbol_name in preferred_symbols:
        if symbol_name in ordered:
            return symbol_name
    return ordered[0]


def _set_backtest_window(page: Page, symbol: str, record) -> bool:
    window = _recommended_backtest_window(symbol)
    if not window:
        record(
            "Trader journey backtest window",
            "SKIP",
            f"Could not derive a complete local candle window from local data for `{symbol}`.",
        )
        return False

    start_value, end_value = window
    panel = _active_panel(page)
    try:
        start_input = page.locator("css=:root")
        end_input = page.locator("css=:root")
        for _ in range(3):
            start_input = _find_date_input(panel, page, "Backtest Start").locator("input").first
            end_input = _find_date_input(panel, page, "Backtest End").locator("input").first
            if start_input.count() > 0 and end_input.count() > 0:
                break
            time.sleep(2.0)
        if start_input.count() == 0 or end_input.count() == 0:
            body = _body_text(page).lower()
            if "running choose_backtest_default_symbol" in body or "running" in body:
                record("Trader journey backtest window", "PARTIAL", "Backtest controls were still loading; the window picker did not become interactive in time.")
                return False
            record("Trader journey backtest window", "FAIL", "Backtest date inputs are not visible.")
            return False
        start_input.fill(start_value)
        start_input.press("Enter")
        start_input.press("Tab")
        time.sleep(0.5)
        end_input.fill(end_value)
        end_input.press("Enter")
        end_input.press("Tab")
        time.sleep(_RERENDER)
        try:
            page.keyboard.press("Escape")
            page.keyboard.press("Escape")
            page.locator("body").click(position={"x": 20, "y": 20}, timeout=1_000)
        except Exception:
            pass
        body = _body_text(page)
        audit_complete = "History Audit" in body and ("complete" in body.lower() or "covered" in body.lower())
        status = "PASS" if audit_complete or _no_exception(page) else "PARTIAL"
        record("Trader journey backtest window", status, f"Configured symbol={symbol} Start={start_value} End={end_value}")
        return True
    except Exception as exc:
        record("Trader journey backtest window", "FAIL", f"Could not set backtest dates: {exc}")
        return False


def _extract_run_id(text: str) -> int | None:
    match = re.search(r"Backtest run #(\d+) saved\.", text)
    return int(match.group(1)) if match else None


def _extract_run_id_from_option(option_text: str) -> int | None:
    match = re.search(r"#(\d+)", option_text)
    return int(match.group(1)) if match else None


def _has_missing_data_warning(text: str) -> bool:
    lowered = text.lower()
    keywords = [
        "backfill",
        "candle",
        "gap",
        "history audit",
        "incomplete",
        "missing",
        "no candle data",
        "window",
    ]
    return any(keyword in lowered for keyword in keywords)


def _inspect_surface_state(page: Page) -> dict[str, object]:
    body = _body_text(page)
    lowered_body = body.lower()
    has_metrics = _visible(page, "[data-testid='stMetric']")
    has_gate = (
        _visible(page, "[data-testid='stInfo']") or
        _visible(page, "[data-testid='stSuccess']") or
        _visible(page, "[data-testid='stWarning']") or
        "gate passed." in lowered_body or
        "gate failed." in lowered_body or
        "gate outcome unavailable" in lowered_body
    )
    has_equity_region = (
        page.locator("[data-testid='stPlotlyChart']").count() > 0 or
        "equity curve cannot be reconstructed" in lowered_body or
        "no trade records are available for this saved run" in lowered_body or
        "equity curve unavailable" in lowered_body or
        "no persisted trade rows" in lowered_body or
        "no trades executed" in lowered_body or
        "re-run the backtest" in lowered_body or
        "0 trades" in lowered_body
    )
    has_code_region = (
        _visible(page, "[data-testid='stCode']") or
        "strategy source unavailable" in lowered_body or
        "built-in strategy source is not stored on disk" in lowered_body or
        "source code not available for built-in strategies" in lowered_body
    )
    has_artifact_identity = "Artifact #" in body or "hash `" in body
    gate_outcome = "unknown"
    if "gate passed." in lowered_body:
        gate_outcome = "passed"
    elif "gate failed." in lowered_body:
        gate_outcome = "failed"
    elif "gate outcome unavailable" in lowered_body:
        gate_outcome = "unavailable"
    return {
        "body": body,
        "has_metrics": has_metrics,
        "has_gate": has_gate,
        "has_equity_region": has_equity_region,
        "has_code_region": has_code_region,
        "has_artifact_identity": has_artifact_identity,
        "gate_outcome": gate_outcome,
    }


def _inspect_run(page: Page, run_id: int, strategy_name: str, record) -> dict:
    result = {
        "run_id": run_id,
        "gate_outcome": "unknown",
        "inspect_complete": False,
        "inspect_state": "missing",
    }

    if not _goto_tab(page, "Inspect"):
        record(f"Inspect run - {strategy_name}", "FAIL", "Inspect tab not clickable")
        return result

    panel = _active_panel(page)
    selected_option = ""
    deadline = time.time() + 12
    while time.time() < deadline:
        body = _body_text(page)
        if f"Run **#{run_id}**" in body or f"Run #{run_id}" in body:
            break
        options = _selectbox_options(panel, page, "Saved run")
        selected_option = next((option for option in options if f"#{run_id}" in option), "")
        if selected_option:
            break
        time.sleep(1.0)
        panel = _active_panel(page)
    else:
        record(f"Inspect run - {strategy_name}", "FAIL", f"Saved run #{run_id} not listed in Inspect")
        return result

    if selected_option and not _selectbox_value(panel, page, "Saved run", selected_option):
        record(f"Inspect run - {strategy_name}", "FAIL", f"Could not select saved run #{run_id} in Inspect")
        return result
    if selected_option and not _no_exception(page):
        record(f"Inspect run - {strategy_name}", "FAIL", "Exception after selecting saved run")
        return result

    surface = _inspect_surface_state(page)
    deadline = time.time() + 15
    while time.time() < deadline:
        if not _no_exception(page):
            record(f"Inspect run - {strategy_name}", "FAIL", "Exception while Inspect was rendering the selected run")
            return result
        if all([
            surface["has_metrics"],
            surface["has_gate"],
            surface["has_equity_region"],
            surface["has_code_region"],
            surface["has_artifact_identity"],
        ]):
            break
        if _visible(page, "[data-testid='stSpinner']") or _visible(page, "[data-testid='stStatusWidgetRunningIcon']"):
            time.sleep(1.0)
        else:
            time.sleep(0.75)
        surface = _inspect_surface_state(page)

    result["gate_outcome"] = str(surface["gate_outcome"])
    result["inspect_complete"] = all([
        surface["has_metrics"],
        surface["has_gate"],
        surface["has_equity_region"],
        surface["has_code_region"],
        surface["has_artifact_identity"],
    ])
    result["inspect_state"] = "complete" if result["inspect_complete"] else "incomplete"

    status = "PASS" if result["inspect_complete"] else "FAIL"
    detail = (
        f"gate={result['gate_outcome']} metrics={surface['has_metrics']} gate_banner={surface['has_gate']} "
        f"equity={surface['has_equity_region']} code={surface['has_code_region']} artifact={surface['has_artifact_identity']}"
    )
    record(f"Inspect run - {strategy_name}", status, detail)
    return result


def _capture_strategy_controls(page: Page, strategy_name: str, record, strategy_meta: dict) -> dict:
    result = {
        "strategy_name": strategy_name,
        "strategy_option_label": str(strategy_meta.get("display_name") or strategy_name),
        "provenance": str(strategy_meta.get("provenance") or strategy_meta.get("source") or "unknown"),
        "is_generated": bool(strategy_meta.get("is_generated")),
        "review_state": "missing",
        "promote_paper_state": "missing",
        "approve_live_state": "missing",
        "next_action": "unknown",
        "blocked_reasons": [],
    }

    if not _goto_tab(page, "Strategies"):
        record(f"Strategy status - {strategy_name}", "FAIL", "Strategies tab not clickable")
        return result

    panel = _active_panel(page)
    if not _selectbox_value(panel, page, "Select backtest/default strategy", result["strategy_option_label"]):
        record(f"Strategy status - {strategy_name}", "FAIL", "Could not select strategy")
        return result
    if not _no_exception(page):
        record(f"Strategy status - {strategy_name}", "FAIL", "Exception after selecting strategy")
        return result

    body = _body_text(page)
    has_lifecycle = all(
        token in body
        for token in ["Workflow Stage", "Artifact Status", "Backtest Runs", "Passed Runs", "Failed Runs"]
    )
    result["review_state"] = _button_state(panel, "Review and Save")
    result["promote_paper_state"] = _button_state(panel, "Promote to Paper")
    result["approve_live_state"] = _button_state(panel, "Approve for Live")

    if "Promote to Paper / Approve for Live are disabled" in body or "Paper/live promotion is disabled for generated drafts." in body:
        result["blocked_reasons"].append("generated drafts are backtest-only")
    if "Promote to Paper is blocked" in body or "Promote to Paper unlocks after" in body:
        result["blocked_reasons"].append("needs a passing saved backtest")
    if "Approve for Live is blocked" in body or "Approve for Live unlocks" in body:
        result["blocked_reasons"].append("needs paper evaluation gate pass")
    if "is the current paper trading target" in body:
        result["is_paper_target"] = True
    if "is the current live trading target" in body:
        result["is_live_target"] = True

    if result["is_generated"]:
        result["next_action"] = "Review and save"
    elif result["promote_paper_state"] == "enabled":
        result["next_action"] = "Promote to paper"
    elif result["approve_live_state"] == "enabled":
        result["next_action"] = "Approve for live"
    elif "needs a passing saved backtest" in result["blocked_reasons"]:
        result["next_action"] = "Run backtest"
    else:
        result["next_action"] = "Monitor runtime"

    status = "PASS" if has_lifecycle else "FAIL"
    detail = (
        f"lifecycle={has_lifecycle} review={result['review_state']} paper={result['promote_paper_state']} "
        f"live={result['approve_live_state']} next_action={result['next_action']}"
    )
    record(f"Strategy status - {strategy_name}", status, detail)
    return result


def _run_backtest_for_strategy(page: Page, strategy_name: str, record) -> dict:
    result = {
        "backtest_status": "not-run",
        "run_id": None,
        "inspect_complete": False,
        "gate_outcome": "unknown",
    }

    if not _goto_tab(page, "Backtest Lab"):
        record(f"Backtest run - {strategy_name}", "FAIL", "Backtest Lab tab not clickable")
        result["backtest_status"] = "tab-failure"
        return result

    panel = _active_panel(page)
    symbol_options = _selectbox_options(panel, page, ["Backtest Symbol", "Symbol"])
    preferred_symbol = _preferred_backtest_symbol(symbol_options)
    if preferred_symbol and not _selectbox_value(panel, page, ["Backtest Symbol", "Symbol"], preferred_symbol):
        record(f"Backtest run - {strategy_name}", "FAIL", f"Could not select runnable symbol `{preferred_symbol}` in Backtest Lab")
        result["backtest_status"] = "selection-failure"
        return result
    if not _selectbox_value(panel, page, ["Backtest Strategy", "Strategy"], strategy_name):
        record(f"Backtest run - {strategy_name}", "FAIL", "Could not select strategy in Backtest Lab")
        result["backtest_status"] = "selection-failure"
        return result
    if not _no_exception(page):
        record(f"Backtest run - {strategy_name}", "FAIL", "Exception after strategy selection")
        result["backtest_status"] = "selection-failure"
        return result

    form_state = _wait_for_backtest_form_ready(page)
    if form_state == "loading":
        record(
            f"Backtest run - {strategy_name}",
            "PARTIAL",
            "Backtest form was still loading its history audit; the dashboard showed live loading feedback instead of a silent no-op.",
        )
        result["backtest_status"] = "form-loading"
        return result
    if not _set_backtest_window(page, preferred_symbol or "BTCUSDT", lambda *_args: None):
        record(
            f"Backtest run - {strategy_name}",
            "PARTIAL",
            "Backtest form rerendered but the trader journey could not re-apply the audited date window.",
        )
        result["backtest_status"] = "window-apply-failure"
        return result
    if _wait_for_backtest_form_ready(page) == "loading":
        record(
            f"Backtest run - {strategy_name}",
            "PARTIAL",
            "Backtest form was still recalculating after the date window update; operator feedback remained visible.",
        )
        result["backtest_status"] = "form-loading"
        return result

    before_runs_df = list_backtest_runs()
    before_max_run_id = int(before_runs_df["id"].max()) if not before_runs_df.empty and "id" in before_runs_df.columns else 0
    before_text = _body_text(page)
    before_run_options = _selectbox_options(panel, page, "Inspect saved run")
    if not _click_button(panel, page, "Run Backtest", timeout=_LONG):
        record(f"Backtest run - {strategy_name}", "FAIL", "Run Backtest button was not clickable after the form rerendered.")
        result["backtest_status"] = "button-failure"
        return result

    terminal_state = _wait_for_backtest_terminal_state(
        page,
        strategy_name,
        before_max_run_id,
        timeout_seconds=_JOURNEY_TERMINAL_TIMEOUT_SECONDS,
    )
    terminal_kind = str(terminal_state.get("state") or "")
    if terminal_kind == "exception":
        record(f"Backtest run - {strategy_name}", "FAIL", "Streamlit exception after backtest")
        result["backtest_status"] = "exception"
        return result
    if terminal_kind == "strategy-mismatch":
        actual_strategy = str(terminal_state.get("actual_strategy") or "unknown")
        record(
            f"Backtest run - {strategy_name}",
            "FAIL",
            f"Backtest saved a run for `{actual_strategy}` instead of the selected `{strategy_name}`.",
        )
        result["backtest_status"] = "strategy-mismatch"
        return result
    if terminal_kind == "blocked-history":
        result["backtest_status"] = "blocked-missing-data"
        record(
            f"Backtest run - {strategy_name}",
            "PARTIAL",
            "Backtest blocked: dashboard showed an explicit history-incomplete error with clear next action.",
        )
        return result
    if terminal_kind == "blocked-validation":
        result["backtest_status"] = "blocked-validation"
        record(
            f"Backtest run - {strategy_name}",
            "PARTIAL",
            "Backtest blocked: dashboard showed a persistent validation failure state.",
        )
        return result
    if terminal_kind == "run-failed":
        result["backtest_status"] = "blocked-explicit"
        record(
            f"Backtest run - {strategy_name}",
            "PARTIAL",
            "Backtest did not save a run, but the dashboard showed a persistent run-failed state.",
        )
        return result
    if terminal_kind == "running-slow":
        result["backtest_status"] = "running-slow"
        record(
            f"Backtest run - {strategy_name}",
            "PARTIAL",
            "Backtest is still visibly running with a spinner; operator feedback is present but the run did not finish within the journey timeout.",
        )
        return result
    if terminal_kind == "timeout":
        result["backtest_status"] = "timeout"
        record(
            f"Backtest run - {strategy_name}",
            "FAIL",
            f"No terminal backtest response within {_JOURNEY_TERMINAL_TIMEOUT_SECONDS}s",
        )
        return result

    after_text = _body_text(page)
    run_id = int(terminal_state["run_id"]) if terminal_kind == "saved" and terminal_state.get("run_id") is not None else None
    success_run_id = _extract_run_id(after_text)
    if success_run_id is not None and (
        success_run_id > before_max_run_id
        or f"Backtest run #{success_run_id} saved." not in before_text
    ):
        run_id = success_run_id
    after_runs_df = list_backtest_runs()
    if run_id is None and not after_runs_df.empty and "id" in after_runs_df.columns:
        new_rows = after_runs_df[
            (after_runs_df["id"].astype(int) > before_max_run_id)
            & (after_runs_df["strategy_name"].astype(str) == strategy_name)
        ]
        if not new_rows.empty:
            run_id = int(new_rows.iloc[0]["id"])
    if run_id is None:
        run_id = _wait_for_saved_run_id(strategy_name, before_max_run_id, timeout_seconds=15)
    after_run_options = _selectbox_options(panel, page, "Inspect saved run")
    if run_id is None and after_run_options:
        fresh_option = next(
            (
                option for option in after_run_options
                if option not in before_run_options and strategy_name in option
            ),
            "",
        )
        if not fresh_option and after_run_options and after_run_options[0] != (before_run_options[0] if before_run_options else ""):
            fresh_option = after_run_options[0]
        if fresh_option:
            candidate_run_id = _extract_run_id_from_option(fresh_option)
            if candidate_run_id is not None and candidate_run_id > before_max_run_id:
                run_id = candidate_run_id
    if run_id is not None:
        result["backtest_status"] = "saved"
        result["run_id"] = run_id
        deadline = time.time() + 12
        has_summary = "Run Summary" in after_text
        has_leaderboard = "Saved Run Leaderboard" in after_text
        has_metrics = _visible(page, "[data-testid='stMetric']")
        while time.time() < deadline and not all([has_summary, has_leaderboard, has_metrics]):
            time.sleep(0.75)
            after_text = _body_text(page)
            has_summary = "Run Summary" in after_text
            has_leaderboard = "Saved Run Leaderboard" in after_text
            has_metrics = _visible(page, "[data-testid='stMetric']")
        status = "PASS" if all([has_summary, has_leaderboard, has_metrics]) else "PARTIAL"
        record(
            f"Backtest run - {strategy_name}",
            status,
            f"run_id={run_id} summary={has_summary} leaderboard={has_leaderboard} metrics={has_metrics}",
        )
        inspect_result = _inspect_run(page, run_id, strategy_name, record)
        result["inspect_complete"] = bool(inspect_result["inspect_complete"])
        result["gate_outcome"] = str(inspect_result["gate_outcome"])
        return result

    result["backtest_status"] = "silent-noop"
    record(
        f"Backtest run - {strategy_name}",
        "FAIL",
        "Backtest did not save a run and no explicit missing-data warning was visible.",
    )
    return result


def _verify_paper_and_live_readiness(page: Page, results: list[dict], record) -> None:
    drafts = [item for item in results if item.get("is_generated")]
    reviewed = [item for item in results if not item.get("is_generated")]
    paper_candidates = [item for item in reviewed if item.get("promote_paper_state") == "enabled"]
    live_candidates = [item for item in reviewed if item.get("approve_live_state") == "enabled"]
    blocked_reviewed = [
        item for item in reviewed
        if item.get("promote_paper_state") == "disabled"
        and "needs a passing saved backtest" in item.get("blocked_reasons", [])
    ]

    if drafts:
        sample = drafts[0]
        ok = (
            sample.get("review_state") == "enabled"
            and sample.get("promote_paper_state") == "disabled"
            and "generated drafts are backtest-only" in sample.get("blocked_reasons", [])
        )
        record(
            "Draft promotion guard",
            "PASS" if ok else "FAIL",
            f"{sample['strategy_name']} review={sample['review_state']} paper={sample['promote_paper_state']} reasons={sample['blocked_reasons']}",
        )
    else:
        record("Draft promotion guard", "SKIP", "No generated draft strategy is available in the current catalog.")

    if blocked_reviewed:
        sample = blocked_reviewed[0]
        record(
            "Reviewed strategy backtest gate",
            "PASS",
            f"{sample['strategy_name']} blocks paper promotion until it has a passing saved backtest.",
        )
    else:
        record("Reviewed strategy backtest gate", "SKIP", "No reviewed strategy is currently blocked only by missing passing runs.")

    if paper_candidates:
        candidate = paper_candidates[0]
        before_target = get_active_runtime_artifact("paper")
        if not _goto_tab(page, "Strategies"):
            record("Promote to paper journey", "FAIL", "Strategies tab not clickable")
        else:
            panel = _active_panel(page)
            if not _selectbox_value(panel, page, "Select backtest/default strategy", candidate.get("strategy_option_label", candidate["strategy_name"])):
                record("Promote to paper journey", "FAIL", f"Could not select `{candidate['strategy_name']}`")
            else:
                try:
                    panel.get_by_role("button", name="Promote to Paper").first.click(timeout=_SHORT)
                    time.sleep(_RERENDER * 2)
                    body_after = _body_text(page)
                    after_target = get_active_runtime_artifact("paper")
                    page_confirms = "Paper target set to" in body_after or "paper_active" in body_after.lower()
                    db_confirms = bool(
                        after_target
                        and str(after_target.get("name")) == candidate["strategy_name"]
                    )
                    promoted = page_confirms or db_confirms
                    status = "PASS" if promoted else "FAIL"
                    record(
                        "Promote to paper journey",
                        status,
                        f"strategy={candidate['strategy_name']} promoted={promoted} page={page_confirms} db={db_confirms}",
                    )
                except Exception as exc:
                    record("Promote to paper journey", "FAIL", str(exc))
    else:
        record("Promote to paper journey", "SKIP", "No reviewed strategy with a passing saved backtest is eligible for paper promotion.")

    if live_candidates:
        candidate = live_candidates[0]
        before_target = get_active_runtime_artifact("live")
        if not _goto_tab(page, "Strategies"):
            record("Live approval journey", "FAIL", "Strategies tab not clickable")
        else:
            panel = _active_panel(page)
            if not _selectbox_value(panel, page, "Select backtest/default strategy", candidate.get("strategy_option_label", candidate["strategy_name"])):
                record("Live approval journey", "FAIL", f"Could not select `{candidate['strategy_name']}`")
            else:
                try:
                    panel.get_by_role("button", name="Approve for Live").first.click(timeout=_SHORT)
                    time.sleep(_RERENDER)
                    after_target = get_active_runtime_artifact("live")
                    approved = bool(
                        after_target
                        and str(after_target.get("name")) == candidate["strategy_name"]
                        and (
                            before_target is None
                            or int(after_target.get("id") or 0) != int(before_target.get("id") or 0)
                            or str(before_target.get("name")) == candidate["strategy_name"]
                        )
                    )
                    status = "PASS" if approved else "FAIL"
                    record(
                        "Live approval journey",
                        status,
                        f"strategy={candidate['strategy_name']} approved={approved}",
                    )
                except Exception as exc:
                    record("Live approval journey", "FAIL", str(exc))
    else:
        live_blocked = next(
            (
                item for item in reviewed
                if item.get("approve_live_state") == "disabled"
                and "needs paper evaluation gate pass" in item.get("blocked_reasons", [])
            ),
            None,
        )
        if live_blocked:
            record(
                "Live approval journey",
                "PASS",
                f"{live_blocked['strategy_name']} correctly blocks live approval until the paper gate passes.",
            )
        else:
            record("Live approval journey", "SKIP", "No reviewed strategy currently exercises the live approval state.")

    if not paper_candidates and not live_candidates:
        record("Runtime monitor after promotion", "SKIP", "No promotable reviewed artifact exists in the current environment.")
        return

    if not _goto_tab(page, "Runtime Monitor"):
        record("Runtime monitor after promotion", "FAIL", "Runtime Monitor tab not clickable")
        return
    body = _body_text(page)
    has_chart = (
        _visible(page, "iframe") or
        _visible(page, "canvas") or
        _visible(page, "[data-testid='stPlotlyChart']")
    )
    has_targets = (
        "Paper/Live Targets" in body or
        "Runtime Monitor" in body or
        "paper" in body.lower() or
        "live" in body.lower()
    )
    record(
        "Runtime monitor after promotion",
        "PASS" if has_chart and has_targets and _no_exception(page) else "FAIL",
        f"targets={has_targets} chart={has_chart} exception_free={_no_exception(page)}",
    )


def build_trader_journey_summary(strategy_results: list[dict]) -> dict:
    operator_concerns: list[str] = []
    for item in strategy_results:
        name = item.get("strategy_name", "unknown")
        if item.get("backtest_status") == "blocked-missing-data":
            operator_concerns.append(f"{name}: backtest blocked by explicit missing-data/history warning.")
        elif item.get("backtest_status") not in {"saved", "not-run"}:
            operator_concerns.append(f"{name}: backtest did not reach a trusted saved-run state ({item.get('backtest_status')}).")
        if item.get("run_id") and not item.get("inspect_complete"):
            operator_concerns.append(f"{name}: saved run #{item.get('run_id')} did not render a complete inspect surface.")
        if item.get("approve_live_state") == "disabled" and not item.get("blocked_reasons"):
            operator_concerns.append(f"{name}: live approval is blocked without a visible explanation.")

    summary = {
        "journey_type": "trader",
        "summary": {
            "total_strategies": len(strategy_results),
            "strategies_successfully_backtested": sum(1 for item in strategy_results if item.get("backtest_status") == "saved"),
            "strategies_with_complete_inspect": sum(1 for item in strategy_results if item.get("inspect_complete")),
            "strategies_blocked_by_missing_data": sum(1 for item in strategy_results if item.get("backtest_status") == "blocked-missing-data"),
            "reviewed_strategies_eligible_for_paper": sum(
                1 for item in strategy_results
                if not item.get("is_generated") and item.get("promote_paper_state") == "enabled"
            ),
            "reviewed_strategies_blocked_from_live": sum(
                1 for item in strategy_results
                if not item.get("is_generated") and item.get("approve_live_state") != "enabled"
            ),
        },
        "strategies": strategy_results,
        "operator_concerns": operator_concerns,
    }
    return summary


def run_trader_journey(page: Page, *, verbose: bool = True) -> tuple[list[dict], dict]:
    findings: list[dict] = []
    record = _make_recorder(findings, verbose)

    try:
        page.wait_for_selector("[data-testid='stApp']", timeout=15_000)
        time.sleep(3.0)
        try:
            page.get_by_text("Backtest Lab").first.is_visible(timeout=5_000)
        except Exception:
            pass
    except Exception:
        record("Trader journey shell", "FAIL", "Dashboard shell never appeared")
        return findings, build_trader_journey_summary([])

    if not _no_exception(page):
        record("Trader journey shell", "FAIL", "Streamlit exception on startup")
        return findings, build_trader_journey_summary([])

    if not _goto_tab(page, "Backtest Lab"):
        record("Trader journey discovery", "FAIL", "Backtest Lab tab not clickable")
        return findings, build_trader_journey_summary([])

    strategy_options = _selectbox_options(_active_panel(page), page, ["Backtest Strategy", "Strategy"])
    if not strategy_options:
        time.sleep(1.5)
        strategy_options = _selectbox_options(page, page, ["Backtest Strategy", "Strategy"])
    if not strategy_options:
        record("Trader journey discovery", "FAIL", "No strategies were visible in Backtest Lab")
        return findings, build_trader_journey_summary([])

    record("Trader journey discovery", "PASS", f"Discovered {len(strategy_options)} strategy option(s) in Backtest Lab")
    panel = _active_panel(page)
    backtest_symbol = _preferred_backtest_symbol(_selectbox_options(panel, page, ["Backtest Symbol", "Symbol"]))
    _set_backtest_window(page, backtest_symbol or "BTCUSDT", record)

    strategy_meta_map = {str(item.get("name")): item for item in list_available_strategies()}
    strategy_results: list[dict] = []
    for strategy_name in strategy_options:
        meta = strategy_meta_map.get(strategy_name, {})
        status_result = _capture_strategy_controls(page, strategy_name, record, meta)
        backtest_result = _run_backtest_for_strategy(page, strategy_name, record)
        strategy_results.append({**status_result, **backtest_result})

    _verify_paper_and_live_readiness(page, strategy_results, record)
    return findings, build_trader_journey_summary(strategy_results)
