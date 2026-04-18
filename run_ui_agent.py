"""CLI entry point for the AI UI testing agent.

Usage:
    python run_ui_agent.py [--headed] [--url http://localhost:8501] [--max-steps 50]
"""

from __future__ import annotations

import argparse
import time

from tools.ui_agent import browser, agent, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AI UI testing agent against the dashboard.")
    parser.add_argument("--headed", action="store_true", help="Show the browser window (default: headless)")
    parser.add_argument("--url", default="http://localhost:8501", help="Dashboard URL")
    parser.add_argument("--max-steps", type=int, default=50, dest="max_steps", help="Max agent steps")
    args = parser.parse_args()

    print(f"Launching browser → {args.url} (headed={args.headed})")
    pw, br, page = browser.launch(args.url, headed=args.headed)

    try:
        start = time.time()
        print("Agent running …")
        findings = agent.run_agent(page, max_steps=args.max_steps)
        elapsed = time.time() - start

        result = report.build_report(findings, elapsed_seconds=elapsed)
        json_path, md_path = report.write_report(result)

        print()
        print(result["summary"])
        print(f"\nReport written to:")
        print(f"  JSON: {json_path}")
        print(f"  MD:   {md_path}")
    finally:
        browser.close(pw, br)


if __name__ == "__main__":
    main()
