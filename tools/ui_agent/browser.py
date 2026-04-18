"""Playwright browser wrapper and tool definitions for the UI testing agent."""

from __future__ import annotations

import base64
import time
from typing import Any

from playwright.sync_api import Page, sync_playwright


_STREAMLIT_READY_SELECTOR = "[data-testid='stApp']"
_RERENDER_WAIT_MS = 1500


def launch(url: str = "http://localhost:8501", *, headed: bool = True):
    """Launch browser and navigate to the dashboard. Returns (playwright, browser, page)."""
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=not headed, slow_mo=150)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(url, wait_until="networkidle", timeout=30_000)
    page.wait_for_selector(_STREAMLIT_READY_SELECTOR, timeout=20_000)
    time.sleep(1.5)
    return pw, browser, page


def close(pw, browser):
    try:
        browser.close()
    except Exception:
        pass
    try:
        pw.stop()
    except Exception:
        pass


# ── Tool implementations ───────────────────────────────────────────────────────

def take_screenshot(page: Page) -> str:
    """Capture current viewport as base64 PNG."""
    return base64.b64encode(page.screenshot(full_page=False)).decode()


def click_text(page: Page, text: str, *, exact: bool = False) -> dict[str, Any]:
    """Click the first element whose visible text matches."""
    try:
        if exact:
            page.get_by_text(text, exact=True).first.click(timeout=5_000)
        else:
            page.get_by_text(text).first.click(timeout=5_000)
        page.wait_for_load_state("networkidle", timeout=5_000)
        time.sleep(_RERENDER_WAIT_MS / 1000)
        return {"ok": True, "action": f"click text '{text}'"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def click_selector(page: Page, selector: str) -> dict[str, Any]:
    """Click element by CSS selector."""
    try:
        page.click(selector, timeout=5_000)
        time.sleep(_RERENDER_WAIT_MS / 1000)
        return {"ok": True, "action": f"click selector '{selector}'"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def fill_input(page: Page, label_or_placeholder: str, value: str) -> dict[str, Any]:
    """Fill an input field identified by its label or placeholder text."""
    try:
        inp = (
            page.get_by_label(label_or_placeholder).first
            or page.get_by_placeholder(label_or_placeholder).first
        )
        inp.fill(value, timeout=5_000)
        time.sleep(0.5)
        return {"ok": True, "action": f"fill '{label_or_placeholder}' with '{value}'"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def select_streamlit_selectbox(page: Page, label: str, option_text: str) -> dict[str, Any]:
    """Select an option in a Streamlit st.selectbox by label then option text."""
    try:
        # Click the selectbox widget
        page.get_by_label(label).first.click(timeout=5_000)
        time.sleep(0.4)
        # Click the matching option in the dropdown list
        page.get_by_text(option_text).first.click(timeout=5_000)
        time.sleep(_RERENDER_WAIT_MS / 1000)
        return {"ok": True, "action": f"select '{option_text}' in '{label}'"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def click_tab(page: Page, tab_name: str) -> dict[str, Any]:
    """Click a Streamlit tab by its label."""
    try:
        page.get_by_role("tab", name=tab_name).click(timeout=5_000)
        time.sleep(_RERENDER_WAIT_MS / 1000)
        return {"ok": True, "action": f"open tab '{tab_name}'"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def click_button(page: Page, label: str) -> dict[str, Any]:
    """Click a Streamlit button by its visible label."""
    try:
        page.get_by_role("button", name=label).first.click(timeout=5_000)
        time.sleep(_RERENDER_WAIT_MS / 1000)
        return {"ok": True, "action": f"click button '{label}'"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def expand_expander(page: Page, title: str) -> dict[str, Any]:
    """Open a Streamlit st.expander by its summary title."""
    try:
        summary = page.get_by_role("button", name=title).first
        if summary.get_attribute("aria-expanded") == "false":
            summary.click(timeout=5_000)
            time.sleep(_RERENDER_WAIT_MS / 1000)
        return {"ok": True, "action": f"expand '{title}'"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_visible_text(page: Page) -> str:
    """Return trimmed visible text of the current viewport (first 4000 chars)."""
    try:
        text = page.inner_text("body")
        return text[:4000].strip()
    except Exception:
        return ""


def scroll_down(page: Page, px: int = 600) -> dict[str, Any]:
    """Scroll down by px pixels."""
    page.mouse.wheel(0, px)
    time.sleep(0.4)
    return {"ok": True, "action": f"scroll down {px}px"}


# ── Tool schema for Claude API tool_use ───────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "screenshot",
        "description": "Take a screenshot of the current dashboard state. Always call this first to observe the page before acting.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "click_tab",
        "description": "Navigate to a dashboard tab by name. Tabs: Strategies, Backtest Lab, Runtime Monitor, Market Focus, Inspect.",
        "input_schema": {
            "type": "object",
            "properties": {"tab_name": {"type": "string", "description": "Exact tab label"}},
            "required": ["tab_name"],
        },
    },
    {
        "name": "click_button",
        "description": "Click a button by its visible label text.",
        "input_schema": {
            "type": "object",
            "properties": {"label": {"type": "string"}},
            "required": ["label"],
        },
    },
    {
        "name": "click_text",
        "description": "Click any visible element by its text content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "exact": {"type": "boolean", "default": False},
            },
            "required": ["text"],
        },
    },
    {
        "name": "fill_input",
        "description": "Type a value into an input field identified by its label or placeholder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "label_or_placeholder": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["label_or_placeholder", "value"],
        },
    },
    {
        "name": "select_option",
        "description": "Select an option in a dropdown (st.selectbox) by the widget label and the option text to choose.",
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Dropdown widget label"},
                "option_text": {"type": "string", "description": "Visible option to select"},
            },
            "required": ["label", "option_text"],
        },
    },
    {
        "name": "expand_expander",
        "description": "Open a collapsible section (expander) by its title.",
        "input_schema": {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
    },
    {
        "name": "scroll_down",
        "description": "Scroll the page down to reveal more content.",
        "input_schema": {
            "type": "object",
            "properties": {"px": {"type": "integer", "default": 600}},
            "required": [],
        },
    },
    {
        "name": "get_visible_text",
        "description": "Read the visible text on the current page to understand what is displayed.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "report_finding",
        "description": "Record the result of testing a feature. Call this after confirming whether a feature works or is broken.",
        "input_schema": {
            "type": "object",
            "properties": {
                "feature": {"type": "string", "description": "Feature or action tested, e.g. 'Run Backtest button'"},
                "status": {"type": "string", "enum": ["PASS", "FAIL", "PARTIAL", "SKIP"]},
                "detail": {"type": "string", "description": "What happened — what you saw, any errors or unexpected behaviour"},
            },
            "required": ["feature", "status", "detail"],
        },
    },
    {
        "name": "done",
        "description": "Signal that testing is complete and return the final summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Overall assessment of dashboard health"}
            },
            "required": ["summary"],
        },
    },
]


def dispatch(tool_name: str, tool_input: dict[str, Any], page: Page) -> Any:
    """Execute a tool and return the result."""
    if tool_name == "screenshot":
        return {"type": "image", "data": take_screenshot(page)}
    if tool_name == "click_tab":
        return click_tab(page, tool_input["tab_name"])
    if tool_name == "click_button":
        return click_button(page, tool_input["label"])
    if tool_name == "click_text":
        return click_text(page, tool_input["text"], exact=tool_input.get("exact", False))
    if tool_name == "fill_input":
        return fill_input(page, tool_input["label_or_placeholder"], tool_input["value"])
    if tool_name == "select_option":
        return select_streamlit_selectbox(page, tool_input["label"], tool_input["option_text"])
    if tool_name == "expand_expander":
        return expand_expander(page, tool_input["title"])
    if tool_name == "scroll_down":
        return scroll_down(page, tool_input.get("px", 600))
    if tool_name == "get_visible_text":
        return {"text": get_visible_text(page)}
    return {"error": f"Unknown tool: {tool_name}"}
