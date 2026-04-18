"""CLI entry point: UI smoke tests + data integrity checks.

Usage:
    python run_ui_agent.py [--headed] [--url http://localhost:8501]
    python run_ui_agent.py --data-only          # skip browser, DB checks only
    python run_ui_agent.py --ui-only            # skip DB checks
"""

from __future__ import annotations

import argparse
import time

from tools.ui_agent import browser, agent, report
from tools.ui_agent import data_checks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Production readiness test: UI checks + data integrity checks."
    )
    parser.add_argument("--headed", action="store_true",
                        help="Show the browser window (default: headless)")
    parser.add_argument("--url", default="http://localhost:8501",
                        help="Dashboard URL")
    parser.add_argument("--data-only", action="store_true", dest="data_only",
                        help="Run DB data checks only — no browser")
    parser.add_argument("--ui-only", action="store_true", dest="ui_only",
                        help="Run UI checks only — skip data integrity")
    args = parser.parse_args()

    all_findings: list[dict] = []
    start = time.time()

    # ── Pass 1: UI checks (Playwright) ────────────────────────────────────────
    if not args.data_only:
        print(f"Launching browser → {args.url} (headed={args.headed})")
        pw, br, page = browser.launch(args.url, headed=args.headed)
        try:
            print("── Pass 1: UI checks ──")
            ui_findings = agent.run_agent(page, verbose=True)
            all_findings.extend(ui_findings)
        finally:
            browser.close(pw, br)
    else:
        print("Skipping UI checks (--data-only)")

    # ── Pass 2: Data integrity checks (DB) ───────────────────────────────────
    if not args.ui_only:
        print("\n── Pass 2: Data integrity checks ──")
        db_findings = data_checks.run_data_checks(verbose=True)
        all_findings.extend(db_findings)
    else:
        print("Skipping data integrity checks (--ui-only)")

    elapsed = time.time() - start

    # ── Report ────────────────────────────────────────────────────────────────
    result = report.build_report(all_findings, elapsed_seconds=elapsed)
    json_path, md_path = report.write_report(result)

    print()
    print("=" * 60)
    print(result["summary"])
    print(f"\nReport written to:")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")


if __name__ == "__main__":
    main()
