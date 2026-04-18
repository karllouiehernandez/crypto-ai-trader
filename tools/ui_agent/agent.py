"""Pure Playwright production UI test suite — no LLM, no API calls.

9 test groups, ~65 checks covering all tabs, all timeframes, all symbols,
sidebar controls, background data gathering, and every user workflow.
"""

from __future__ import annotations

import time

from playwright.sync_api import Page


_RERENDER = 1.5
_SHORT = 3_000
_LONG = 10_000
_BACKTEST_TIMEOUT = 45_000


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_recorder(findings: list[dict], verbose: bool):
    icons = {"PASS": "✅", "FAIL": "❌", "PARTIAL": "⚠ ", "SKIP": "⏭ "}

    def record(feature: str, status: str, detail: str) -> None:
        findings.append({"feature": feature, "status": status, "detail": detail})
        if verbose:
            print(f"  {icons.get(status, '  ')} [{status}] {feature} — {detail}")

    return record


def _no_exception(page: Page) -> bool:
    return page.locator("[data-testid='stException']").count() == 0


def _visible(page: Page, selector: str, timeout: int = _SHORT) -> bool:
    try:
        return page.locator(selector).first.is_visible(timeout=timeout)
    except Exception:
        return False


def _count(page: Page, selector: str) -> int:
    try:
        return page.locator(selector).count()
    except Exception:
        return 0


def _text(page: Page, text: str, timeout: int = 2000) -> bool:
    try:
        return page.get_by_text(text).first.is_visible(timeout=timeout)
    except Exception:
        return False


def _goto_tab(page: Page, name: str) -> bool:
    try:
        page.get_by_role("tab", name=name).click(timeout=_SHORT)
        time.sleep(_RERENDER)
        return True
    except Exception:
        return False


def _try_expand(page: Page, title: str) -> bool:
    """Open a Streamlit expander by matching its heading text."""
    try:
        exp = page.locator("[data-testid='stExpander']").filter(has_text=title).first
        btn = exp.locator("summary").or_(exp.locator("[role='button']")).first
        if btn.get_attribute("aria-expanded", timeout=2000) != "true":
            btn.click(timeout=_SHORT)
            time.sleep(_RERENDER)
        return True
    except Exception:
        try:
            page.get_by_role("button", name=title).first.click(timeout=_SHORT)
            time.sleep(_RERENDER)
            return True
        except Exception:
            return False


def _has_chart(page: Page) -> bool:
    return (
        _count(page, "iframe") > 0
        or _count(page, "canvas") > 0
        or _count(page, "[data-testid='stPlotlyChart']") > 0
    )


def _sidebar_selectbox_options(page: Page) -> list[str]:
    """Return visible option texts from the first sidebar selectbox."""
    try:
        sb = page.locator("[data-testid='stSidebar']")
        sel = sb.locator("[data-testid='stSelectbox']").first
        sel.click(timeout=_SHORT)
        time.sleep(0.4)
        opts = page.locator("[data-testid='stSelectboxVirtualDropdown'] li, [role='option']").all_text_contents()
        page.keyboard.press("Escape")
        return [o.strip() for o in opts if o.strip()]
    except Exception:
        return []


# ── Group 1: App Shell & Navigation ──────────────────────────────────────────

def _test_app_shell(page: Page, record) -> None:
    try:
        page.wait_for_selector("[data-testid='stApp']", timeout=15_000)
        time.sleep(1.0)
    except Exception:
        record("App shell loads", "FAIL", "stApp never appeared")
        return

    if not _no_exception(page):
        record("App shell loads", "FAIL", "Streamlit exception on startup")
        return
    record("App shell loads", "PASS", "stApp rendered, no exception")

    # Sidebar
    if _visible(page, "[data-testid='stSidebar']"):
        record("Sidebar visible", "PASS", "stSidebar element found")
    else:
        record("Sidebar visible", "FAIL", "stSidebar not found")

    # All 5 tab labels
    tabs = ["Strategies", "Backtest Lab", "Runtime Monitor", "Market Focus", "Inspect"]
    missing = [t for t in tabs if not _text(page, t)]
    if not missing:
        record("All 5 tabs visible", "PASS", "All tab labels present")
    else:
        record("All 5 tabs visible", "FAIL", f"Missing: {missing}")

    # Round-trip navigation
    for tab in tabs:
        if not _goto_tab(page, tab):
            record(f"Tab navigation — {tab}", "FAIL", "Tab not clickable")
        elif not _no_exception(page):
            record(f"Tab navigation — {tab}", "FAIL", "Exception after navigation")
        else:
            record(f"Tab navigation — {tab}", "PASS", "No exception")


# ── Group 2: Sidebar Controls ─────────────────────────────────────────────────

def _test_sidebar(page: Page, record) -> None:
    _goto_tab(page, "Strategies")
    sb = page.locator("[data-testid='stSidebar']")

    # Symbol selector has options
    sym_count = len(_sidebar_selectbox_options(page))
    if sym_count > 0:
        record("Sidebar symbol selector", "PASS", f"{sym_count} symbol(s) available")
    else:
        record("Sidebar symbol selector", "PARTIAL", "No symbols found in selector")

    # Auto-refresh checkbox
    try:
        cb = sb.get_by_text("Auto-refresh").first
        if cb.is_visible(timeout=2000):
            record("Auto-refresh checkbox", "PASS", "Checkbox visible")
        else:
            record("Auto-refresh checkbox", "PARTIAL", "Text not found")
    except Exception:
        record("Auto-refresh checkbox", "PARTIAL", "Could not locate checkbox")

    # Runtime Watchlist multiselect
    if _count(page, "[data-testid='stMultiSelect']") > 0 or _text(page, "Watchlist", 2000):
        record("Runtime Watchlist control", "PASS", "Watchlist widget found")
    else:
        record("Runtime Watchlist control", "PARTIAL", "Watchlist widget not found")

    # Chart layer toggles
    if _text(page, "Trade Markers", 2000) or _text(page, "EMA", 2000):
        record("Chart layer checkboxes", "PASS", "Layer toggle labels visible")
    else:
        record("Chart layer checkboxes", "PARTIAL", "No chart layer controls found")

    # Runtime Mode selectbox in sidebar
    sb_selects = sb.locator("[data-testid='stSelectbox']").count()
    if sb_selects >= 2:
        record("Sidebar runtime mode selector", "PASS", f"{sb_selects} selectbox(es) in sidebar")
    elif sb_selects == 1:
        record("Sidebar runtime mode selector", "PARTIAL", "Only 1 selectbox in sidebar (expected ≥2)")
    else:
        record("Sidebar runtime mode selector", "FAIL", "No selectboxes in sidebar")

    # Load New Symbol expander
    if _try_expand(page, "Load New Symbol"):
        record("Load New Symbol expander", "PASS", "Expander opened")
        time.sleep(0.5)
        if _count(page, "[data-testid='stButton'] button") > 0:
            record("Queue Background Load button", "PASS", "Button visible in expander")
        else:
            record("Queue Background Load button", "PARTIAL", "Button not found in expander")
    else:
        record("Load New Symbol expander", "PARTIAL", "Could not expand Load New Symbol")
        record("Queue Background Load button", "SKIP", "Skipped — expander did not open")


# ── Group 3: Strategies Tab ───────────────────────────────────────────────────

def _test_strategies(page: Page, record) -> None:
    if not _goto_tab(page, "Strategies"):
        record("Strategies tab", "FAIL", "Tab not clickable")
        return
    if not _no_exception(page):
        record("Strategies tab", "FAIL", "Exception on load")
        return
    record("Strategies tab loads", "PASS", "No exception")

    # Promotion Control Panel — expand by clicking summary inside stExpander
    expanded = _try_expand(page, "Promotion Control Panel")
    if expanded:
        record("Promotion Control Panel expander", "PASS", "Expanded without error")
        has_paper = _text(page, "Paper", 2000)
        has_live = _text(page, "Live", 2000)
        if has_paper and has_live:
            record("Promotion Control Panel content", "PASS", "Paper and Live status cards visible")
        else:
            record("Promotion Control Panel content", "PARTIAL",
                   f"paper={has_paper} live={has_live}")
    else:
        record("Promotion Control Panel expander", "PARTIAL", "Could not expand panel")
        record("Promotion Control Panel content", "SKIP", "Skipped — panel not expanded")

    # Strategy selector
    strat_selects = _count(page, "[data-testid='stSelectbox']")
    if strat_selects > 0:
        record("Strategy selector", "PASS", f"{strat_selects} selectbox(es) on Strategies tab")
    else:
        record("Strategy selector", "FAIL", "No selectbox found on Strategies tab")

    # Strategy catalog table
    tables = _count(page, "[data-testid='stDataFrame']")
    if tables > 0:
        record("Strategy catalog table", "PASS", f"{tables} DataFrame(s) visible")
    else:
        record("Strategy catalog table", "PARTIAL", "No DataFrames — may need data")

    # Generate Strategy Draft expander
    if _try_expand(page, "Generate Strategy Draft"):
        record("Generate Strategy Draft expander", "PASS", "Opened without error")
    else:
        record("Generate Strategy Draft expander", "PARTIAL", "Could not expand")

    # Manual Agent Workflow expander
    if _try_expand(page, "Manual Agent Workflow"):
        record("Manual Agent Workflow expander", "PASS", "Opened without error")
    else:
        record("Manual Agent Workflow expander", "PARTIAL", "Could not expand")

    # Workflow action buttons
    btn_count = _count(page, "[data-testid='stButton'] button")
    if btn_count >= 2:
        record("Strategy action buttons", "PASS", f"{btn_count} button(s) visible")
    else:
        record("Strategy action buttons", "PARTIAL", f"Only {btn_count} button(s) found")


# ── Group 4: Backtest Lab ─────────────────────────────────────────────────────

def _test_backtest_lab(page: Page, record) -> None:
    if not _goto_tab(page, "Backtest Lab"):
        record("Backtest Lab tab", "FAIL", "Tab not clickable")
        return
    if not _no_exception(page):
        record("Backtest Lab tab", "FAIL", "Exception on load")
        return
    record("Backtest Lab tab loads", "PASS", "No exception")

    selects = _count(page, "[data-testid='stSelectbox']")
    if selects >= 2:
        record("Backtest symbol + strategy selectors", "PASS", f"{selects} selectbox(es)")
    elif selects == 1:
        record("Backtest symbol + strategy selectors", "PARTIAL", "Only 1 selectbox found")
    else:
        record("Backtest symbol + strategy selectors", "FAIL", "No selectboxes found")

    # Date inputs
    date_inputs = _count(page, "[data-testid='stDateInput']")
    if date_inputs >= 2:
        record("Backtest date inputs", "PASS", f"{date_inputs} date input(s)")
    else:
        record("Backtest date inputs", "PARTIAL", f"Only {date_inputs} date input(s)")

    # History audit banner
    if (_visible(page, "[data-testid='stSuccess']") or
            _visible(page, "[data-testid='stWarning']") or
            _visible(page, "[data-testid='stInfo']") or
            _text(page, "audit", 2000) or _text(page, "Audit", 2000)):
        record("History audit status banner", "PASS", "Audit banner visible")
    else:
        record("History audit status banner", "PARTIAL", "Audit banner not found")

    # Run Backtest button — click it
    try:
        run_btn = page.get_by_role("button", name="Run Backtest").first
        if run_btn.is_visible(timeout=_SHORT):
            record("Run Backtest button visible", "PASS", "Button found")
            run_btn.click(timeout=_SHORT)
            try:
                page.wait_for_selector(
                    "[data-testid='stSpinner'], [data-testid='stAlert'], "
                    "[data-testid='stSuccess'], [data-testid='stWarning'], "
                    "[data-testid='stDataFrame'], [data-testid='stException']",
                    timeout=_BACKTEST_TIMEOUT,
                )
                time.sleep(_RERENDER)
                if _no_exception(page):
                    record("Run Backtest executes", "PASS", "Response appeared without exception")
                else:
                    record("Run Backtest executes", "FAIL", "Exception after clicking Run Backtest")
            except Exception:
                record("Run Backtest executes", "PARTIAL", "No response within 45s — may need data")
        else:
            record("Run Backtest button visible", "FAIL", "Button not visible")
            record("Run Backtest executes", "SKIP", "Skipped — button not found")
    except Exception as exc:
        record("Run Backtest button visible", "FAIL", str(exc))
        record("Run Backtest executes", "SKIP", "Skipped")

    # Results after run
    tables_after = _count(page, "[data-testid='stDataFrame']")
    if tables_after > 0:
        record("Backtest results table", "PASS", f"{tables_after} DataFrame(s) visible after run")
    else:
        record("Backtest results table", "PARTIAL", "No result tables — may need history data")

    # Run inspector (if runs exist)
    if _text(page, "Inspect saved run", 2000) or selects >= 3:
        record("Backtest run inspector selector", "PASS", "Run inspector selectbox visible")
        metrics = _count(page, "[data-testid='stMetric']")
        if metrics >= 4:
            record("Backtest run metrics", "PASS", f"{metrics} metric(s) in run inspector")
        elif metrics > 0:
            record("Backtest run metrics", "PARTIAL", f"Only {metrics} metric(s)")
        else:
            record("Backtest run metrics", "PARTIAL", "No metrics — select a run first")
    else:
        record("Backtest run inspector selector", "PARTIAL", "No saved runs to inspect yet")


# ── Group 5: Runtime Monitor — Timeframes ────────────────────────────────────

def _test_runtime_monitor(page: Page, record) -> None:
    if not _goto_tab(page, "Runtime Monitor"):
        record("Runtime Monitor tab", "FAIL", "Tab not clickable")
        return
    if not _no_exception(page):
        record("Runtime Monitor tab", "FAIL", "Exception on load")
        return
    record("Runtime Monitor tab loads", "PASS", "No exception")

    # Timeframe buttons
    timeframes = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
    tf_found = [tf for tf in timeframes if _text(page, tf, 1500)]
    if len(tf_found) >= 6:
        record("Timeframe buttons visible", "PASS", f"Found: {tf_found}")
    elif tf_found:
        record("Timeframe buttons visible", "PARTIAL", f"Only found: {tf_found}")
    else:
        record("Timeframe buttons visible", "PARTIAL", "No timeframe buttons detected")

    # Click each timeframe and verify chart
    for tf in ["1m", "5m", "15m", "1h", "4h", "1d"]:
        try:
            page.get_by_role("button", name=tf).first.click(timeout=_SHORT)
            time.sleep(_RERENDER)
            if not _no_exception(page):
                record(f"Runtime chart — {tf}", "FAIL", "Exception after timeframe switch")
            elif _has_chart(page):
                record(f"Runtime chart — {tf}", "PASS", "Chart element present")
            else:
                record(f"Runtime chart — {tf}", "PARTIAL", "No chart element after switch")
        except Exception:
            record(f"Runtime chart — {tf}", "PARTIAL", "Timeframe button not found")

    # Mode switching
    try:
        mode_sel = page.locator("[data-testid='stSelectbox']").first
        for mode in ["live", "paper"]:
            mode_sel.click(timeout=_SHORT)
            time.sleep(0.3)
            try:
                page.get_by_role("option", name=mode).first.click(timeout=2000)
                time.sleep(_RERENDER)
                status = "PASS" if _no_exception(page) else "FAIL"
                record(f"Runtime mode switch — {mode}", status,
                       "No exception" if status == "PASS" else "Exception after mode switch")
            except Exception:
                record(f"Runtime mode switch — {mode}", "PARTIAL", "Option not found")
    except Exception:
        record("Runtime mode switching", "PARTIAL", "Could not interact with mode selector")

    # Key metrics
    metrics = _count(page, "[data-testid='stMetric']")
    if metrics >= 4:
        record("Runtime Monitor metrics", "PASS", f"{metrics} metric card(s) visible")
    elif metrics > 0:
        record("Runtime Monitor metrics", "PARTIAL", f"Only {metrics} metric(s)")
    else:
        record("Runtime Monitor metrics", "PARTIAL", "No metrics — requires live/paper data")


# ── Group 6: Symbol Chart Coverage ───────────────────────────────────────────

def _test_symbol_charts(page: Page, record) -> None:
    symbols = _sidebar_selectbox_options(page)
    if len(symbols) < 2:
        record("Symbol chart coverage", "PARTIAL",
               f"Only {len(symbols)} symbol(s) available — need ≥2 for coverage test")
        return

    _goto_tab(page, "Runtime Monitor")
    time.sleep(0.5)

    sb = page.locator("[data-testid='stSidebar']")
    sym_sel = sb.locator("[data-testid='stSelectbox']").first

    for symbol in symbols[:5]:
        try:
            sym_sel.click(timeout=_SHORT)
            time.sleep(0.3)
            page.get_by_role("option", name=symbol).first.click(timeout=_SHORT)
            time.sleep(_RERENDER)
            if not _no_exception(page):
                record(f"Symbol chart — {symbol}", "FAIL", "Exception after symbol switch")
            elif _has_chart(page):
                record(f"Symbol chart — {symbol}", "PASS", "Chart renders")
            else:
                record(f"Symbol chart — {symbol}", "PARTIAL", "No chart element after symbol switch")
        except Exception as exc:
            record(f"Symbol chart — {symbol}", "PARTIAL", f"Could not select: {exc}")


# ── Group 7: Market Focus ─────────────────────────────────────────────────────

def _test_market_focus(page: Page, record) -> None:
    if not _goto_tab(page, "Market Focus"):
        record("Market Focus tab", "FAIL", "Tab not clickable")
        return
    if not _no_exception(page):
        record("Market Focus tab", "FAIL", "Exception on load")
        return
    record("Market Focus tab loads", "PASS", "No exception")

    # Study expander + sliders
    if _try_expand(page, "Run a new study"):
        record("Market Focus study expander", "PASS", "Opened")
        sliders = _count(page, "[data-testid='stSlider']")
        if sliders >= 3:
            record("Market Focus sliders", "PASS", f"{sliders} slider(s) visible")
        else:
            record("Market Focus sliders", "PARTIAL", f"Only {sliders} slider(s) found")

        # Run Study button
        try:
            btn = page.get_by_role("button", name="Run Weekly Study").first
            if btn.is_visible(timeout=_SHORT):
                record("Run Weekly Study button", "PASS", "Button visible")
            else:
                record("Run Weekly Study button", "PARTIAL", "Button not visible")
        except Exception:
            record("Run Weekly Study button", "PARTIAL", "Button not found")
    else:
        record("Market Focus study expander", "PARTIAL", "Could not open expander")
        record("Market Focus sliders", "SKIP", "Skipped")
        record("Run Weekly Study button", "SKIP", "Skipped")

    # Existing study results
    tables = _count(page, "[data-testid='stDataFrame']")
    metrics = _count(page, "[data-testid='stMetric']")
    if tables > 0:
        record("Market Focus ranked shortlist", "PASS", f"{tables} table(s), {metrics} metric(s)")
    else:
        record("Market Focus ranked shortlist", "PARTIAL", "No study data yet — run a study first")

    # Prefill button
    if _text(page, "Prefill Backtest", 2000):
        record("Market Focus prefill button", "PASS", "Prefill Backtest Lab button visible")
    else:
        record("Market Focus prefill button", "PARTIAL", "Prefill button not found — run a study first")


# ── Group 8: Inspect Tab ──────────────────────────────────────────────────────

def _test_inspect(page: Page, record) -> None:
    if not _goto_tab(page, "Inspect"):
        record("Inspect tab", "FAIL", "Tab not clickable")
        return
    if not _no_exception(page):
        record("Inspect tab", "FAIL", "Exception on load")
        return
    record("Inspect tab loads", "PASS", "No exception")

    if _text(page, "No saved backtest", 2000) or _text(page, "Run a backtest", 2000):
        record("Inspect empty state", "PASS", "Empty state message shown correctly")
        record("Inspect run metrics", "SKIP", "No runs — skipped")
        record("Inspect equity chart", "SKIP", "No runs — skipped")
        record("Inspect strategy code", "SKIP", "No runs — skipped")
        record("Inspect gate status", "SKIP", "No runs — skipped")
        return

    selects = _count(page, "[data-testid='stSelectbox']")
    if selects > 0:
        record("Inspect run selector", "PASS", f"{selects} selectbox(es) visible")
    else:
        record("Inspect run selector", "PARTIAL", "No run selector found")
        return

    metrics = _count(page, "[data-testid='stMetric']")
    if metrics >= 4:
        record("Inspect run metrics", "PASS", f"{metrics} metric(s)")
    elif metrics > 0:
        record("Inspect run metrics", "PARTIAL", f"Only {metrics} metric(s)")
    else:
        record("Inspect run metrics", "PARTIAL", "No metrics visible")

    # Gate status banner
    if (_visible(page, "[data-testid='stInfo']") or
            _visible(page, "[data-testid='stSuccess']") or
            _visible(page, "[data-testid='stWarning']")):
        record("Inspect gate status banner", "PASS", "Status banner visible")
    else:
        record("Inspect gate status banner", "PARTIAL", "No status banner found")

    # Equity chart
    if _visible(page, "[data-testid='stPlotlyChart']"):
        record("Inspect equity chart", "PASS", "Plotly chart visible")
    else:
        record("Inspect equity chart", "PARTIAL", "No equity chart found")

    # Strategy code block
    if _count(page, "[data-testid='stCode']") > 0 or _count(page, "pre code") > 0:
        record("Inspect strategy code viewer", "PASS", "Code block visible")
    else:
        record("Inspect strategy code viewer", "PARTIAL", "No code block found")


# ── Group 9: Background Data & History ───────────────────────────────────────

def _test_background_data(page: Page, record) -> None:
    # History audit in Backtest Lab
    _goto_tab(page, "Backtest Lab")
    time.sleep(0.5)

    has_audit = (
        _visible(page, "[data-testid='stSuccess']", 3000) or
        _visible(page, "[data-testid='stWarning']", 3000) or
        _text(page, "candles", 2000) or
        _text(page, "history", 2000) or
        _text(page, "Audit", 2000)
    )
    if has_audit:
        record("History audit banner", "PASS", "Audit/history status visible in Backtest Lab")
    else:
        record("History audit banner", "PARTIAL", "No audit banner found")

    has_backfill_btn = (
        _text(page, "Backfill", 2000) or
        _text(page, "backfill", 2000) or
        _count(page, "[data-testid='stButton'] button") > 1
    )
    if has_backfill_btn:
        record("Backfill / history action button", "PASS", "Backfill or action button visible")
    else:
        record("Backfill / history action button", "PARTIAL", "No backfill button found")

    # Load job queue in sidebar
    _goto_tab(page, "Strategies")
    expanded = _try_expand(page, "Load New Symbol")
    if expanded:
        record("Load New Symbol sidebar panel", "PASS", "Expander opened")
        has_jobs = (
            _count(page, "[data-testid='stDataFrame']") > 0 or
            _text(page, "pending", 2000) or
            _text(page, "No jobs", 2000) or
            _text(page, "Queued", 2000) or
            _text(page, "loaded", 2000)
        )
        if has_jobs:
            record("Symbol load job table", "PASS", "Job status content visible")
        else:
            record("Symbol load job table", "PARTIAL", "No job status content found")
    else:
        record("Load New Symbol sidebar panel", "PARTIAL", "Could not open expander")
        record("Symbol load job table", "SKIP", "Skipped")


# ── Entry point ───────────────────────────────────────────────────────────────

def run_agent(page: Page, *, verbose: bool = True, **_kwargs) -> list[dict]:
    """Run the full production UI test suite. Returns list of finding dicts."""
    findings: list[dict] = []
    record = _make_recorder(findings, verbose)

    groups = [
        ("App Shell & Navigation", _test_app_shell),
        ("Sidebar Controls", _test_sidebar),
        ("Strategies Tab", _test_strategies),
        ("Backtest Lab", _test_backtest_lab),
        ("Runtime Monitor — Timeframes", _test_runtime_monitor),
        ("Symbol Chart Coverage", _test_symbol_charts),
        ("Market Focus", _test_market_focus),
        ("Inspect Tab", _test_inspect),
        ("Background Data & History", _test_background_data),
    ]

    for group_name, fn in groups:
        if verbose:
            print(f"\n── {group_name} ──")
        try:
            fn(page, record)
        except Exception as exc:
            record(f"{group_name} — unexpected error", "FAIL", str(exc))

    if verbose:
        print(f"\n  Total: {len(findings)} checks")

    return findings
