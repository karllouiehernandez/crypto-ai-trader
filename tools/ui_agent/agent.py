"""Claude API agent loop for automated UI testing."""

from __future__ import annotations

import json
from typing import Any

import anthropic

from tools.ui_agent import browser as browser_mod
from tools.ui_agent.browser import TOOL_DEFINITIONS


_SYSTEM_PROMPT = """\
You are an experienced crypto trader testing a new algorithmic trading platform for the first time.
Your job: systematically test every feature across all 5 tabs — Strategies, Backtest Lab, \
Runtime Monitor, Market Focus, Inspect.

For each feature you attempt, use report_finding to record the result:
- PASS  — feature works as expected
- FAIL  — feature is broken or throws an error
- PARTIAL — feature loads but something is missing or incorrect
- SKIP  — feature could not be reached or has no data to test

Cover at minimum:
1. Strategies tab — Promotion Control Panel visible, artifact registry table loads
2. Backtest Lab — symbol selector loads, "Run Backtest" button present and clickable
3. Runtime Monitor — chart renders, mode selector works
4. Market Focus — tab loads, focus selector or table visible
5. Inspect tab — run selector loads, backtest summary metrics visible, strategy code shown

When you have covered all tabs and features, call done with an overall health summary.
Always take a screenshot first to see the current state before acting on anything.
"""


def _make_tool_result(tool_use_id: str, result: Any) -> dict:
    if isinstance(result, dict) and result.get("type") == "image":
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": result["data"],
                    },
                }
            ],
        }
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": json.dumps(result) if not isinstance(result, str) else result,
    }


def run_agent(page, *, max_steps: int = 50, model: str = "claude-sonnet-4-6") -> list[dict]:
    """Run the trader agent against the open page. Returns a list of finding dicts."""
    client = anthropic.Anthropic()
    findings: list[dict] = []

    messages: list[dict] = [
        {"role": "user", "content": "The dashboard is open. Begin testing. Take a screenshot first."}
    ]

    for _ in range(max_steps):
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        tool_uses = [b for b in assistant_content if b.type == "tool_use"]

        if not tool_uses:
            break

        tool_results = []
        done = False

        for block in tool_uses:
            tool_name: str = block.name
            tool_input: dict = block.input

            if tool_name == "done":
                done = True
                tool_results.append(_make_tool_result(block.id, {"ok": True}))
                break

            if tool_name == "report_finding":
                findings.append(tool_input)
                tool_results.append(_make_tool_result(block.id, {"ok": True, "recorded": tool_input["feature"]}))
                continue

            result = browser_mod.dispatch(tool_name, tool_input, page)
            tool_results.append(_make_tool_result(block.id, result))

        messages.append({"role": "user", "content": tool_results})

        if done:
            break

    return findings
