#!/usr/bin/env python3
"""
knowledge/kb_update.py

Interactive CLI for appending structured entries to the knowledge base.
Run this after any trading session, bug discovery, experiment, or config change.

Usage:
    python knowledge/kb_update.py
    python knowledge/kb_update.py --type bug
    python knowledge/kb_update.py --type strategy
    python knowledge/kb_update.py --type experiment
    python knowledge/kb_update.py --type parameter
    python knowledge/kb_update.py --type regime
"""

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

KB_DIR = Path(__file__).parent

ENTRY_TYPES = {
    "bug":        ("bugs_and_fixes.md",       "Bug found or fixed"),
    "strategy":   ("strategy_learnings.md",   "Strategy insight from backtest or paper trading"),
    "experiment": ("experiment_log.md",        "New experiment hypothesis or result update"),
    "parameter":  ("parameter_history.md",    "Config or strategy parameter change"),
    "regime":     ("market_regime_notes.md",  "Market regime observation"),
}

STATUS_OPTIONS = {
    "bug":       ["OPEN", "FIXED", "MONITORING"],
    "strategy":  ["OPEN", "RESOLVED", "MONITORING"],
    "regime":    ["OPEN", "RESOLVED", "MONITORING"],
    "experiment":["HYPOTHESIS", "IN PROGRESS", "COMPLETED", "ABANDONED"],
    # parameter entries use a historical changelog format and don't have a Status field
}


# ── helpers ────────────────────────────────────────────────────────────────────

def prompt(label: str, required: bool = True, default: str = "") -> str:
    """Prompt the user for a single-line value."""
    hint = f" [{default}]" if default else (" (required)" if required else " (optional, enter to skip)")
    while True:
        value = input(f"  {label}{hint}: ").strip()
        if not value and default:
            return default
        if not value and required:
            print("    ⚠  This field is required.")
            continue
        return value or ""


def prompt_multiline(label: str, required: bool = True) -> str:
    """Prompt for multi-line input. Empty line ends entry."""
    hint = " (required)" if required else " (optional)"
    print(f"  {label}{hint} — enter text, blank line to finish:")
    lines = []
    while True:
        line = input("    > ")
        if not line:
            if not lines and required:
                print("    ⚠  This field is required.")
                continue
            break
        lines.append(line)
    return " ".join(lines)


def choose(label: str, options: list[str]) -> str:
    """Present a numbered menu and return the chosen value."""
    print(f"  {label}:")
    for i, opt in enumerate(options, 1):
        print(f"    {i}) {opt}")
    while True:
        raw = input("  Choice: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print(f"    ⚠  Enter a number between 1 and {len(options)}.")


def today() -> str:
    return date.today().strftime("%Y-%m-%d")


def next_exp_number(file_path: Path) -> str:
    """Scan experiment_log.md and return the next EXP-NNN id."""
    if not file_path.exists():
        return "EXP-001"
    text = file_path.read_text(encoding="utf-8")
    matches = re.findall(r"## EXP-(\d+)", text)
    if not matches:
        return "EXP-001"
    return f"EXP-{max(int(m) for m in matches) + 1:03d}"


def append_entry(file_path: Path, entry: str) -> None:
    """Append entry to a KB file, creating it with a header if necessary."""
    if not file_path.exists():
        # No trailing separator — append_entry adds one below
        file_path.write_text(f"# {file_path.stem.replace('_', ' ').title()}\n\n", encoding="utf-8")

    current = file_path.read_text(encoding="utf-8")
    separator = "\n\n---\n\n" if current.rstrip() else ""
    file_path.write_text(current.rstrip() + separator + entry.lstrip("\n") + "\n", encoding="utf-8")


# ── entry builders ─────────────────────────────────────────────────────────────

def build_bug() -> str:
    print("\n── Bug / Fix entry ──────────────────────────────────────────")
    topic   = prompt("Topic (e.g. 'simulator/paper_trader.py')")
    summary = prompt("One-line summary")
    happened = prompt_multiline("What happened")
    why      = prompt_multiline("Why it happened")
    impact   = prompt_multiline("Impact")
    changed  = prompt_multiline("What we changed (or 'pending')")
    next_try = prompt_multiline("What to try next")
    status   = choose("Status", STATUS_OPTIONS["bug"])

    return (
        f"\n## {today()} {topic} — {summary}\n"
        f"**What happened:** {happened}\n"
        f"**Why it happened:** {why}\n"
        f"**Impact:** {impact}\n"
        f"**What we changed:** {changed}\n"
        f"**What to try next:** {next_try}\n"
        f"**Status:** {status}\n"
    )


def build_strategy() -> str:
    print("\n── Strategy Learning entry ───────────────────────────────────")
    topic   = prompt("Symbol / topic (e.g. 'BTCUSDT — RSI threshold test')")
    summary = prompt("One-line summary")
    happened = prompt_multiline("What happened")
    why      = prompt_multiline("Why it happened (root cause or hypothesis)")
    impact   = prompt_multiline("Impact (P&L, Sharpe, trades affected)")
    changed  = prompt_multiline("What we changed (code/config diff or 'pending')")
    next_try = prompt_multiline("What to try next")
    status   = choose("Status", STATUS_OPTIONS["strategy"])

    return (
        f"\n## {today()} {topic} — {summary}\n"
        f"**What happened:** {happened}\n"
        f"**Why it happened:** {why}\n"
        f"**Impact:** {impact}\n"
        f"**What we changed:** {changed}\n"
        f"**What to try next:** {next_try}\n"
        f"**Status:** {status}\n"
    )


def build_experiment(file_path: Path) -> str:
    print("\n── Experiment entry ──────────────────────────────────────────")
    exp_id   = next_exp_number(file_path)
    print(f"  Auto-assigned ID: {exp_id}")
    hypothesis = prompt("One-line hypothesis")
    status     = choose("Status", STATUS_OPTIONS["experiment"])
    hyp_detail = prompt_multiline("Hypothesis (detailed)")
    method     = prompt_multiline("Method (what will be changed and how tested)")
    success    = prompt_multiline("Success criteria")
    symbols    = prompt("Symbols tested (e.g. BTCUSDT, ETHUSDT)", required=False, default="TBD")
    date_range = prompt("Date range (e.g. 2024-01-01 to 2024-12-31)", required=False, default="TBD")
    baseline   = prompt_multiline("Baseline metrics (Sharpe, max DD, profit factor)", required=False)
    result     = prompt_multiline("Result (leave blank if pending)", required=False)
    conclusion = prompt_multiline("Conclusion (leave blank if pending)", required=False)
    next_exp   = prompt_multiline("Next experiment")
    promoted   = choose("Promoted to main strategy?", ["PENDING", "YES", "NO"])

    return (
        f"\n## {exp_id} — {hypothesis}\n"
        f"**Date started:** {today()}\n"
        f"**Status:** {status}\n\n"
        f"**Hypothesis:** {hyp_detail}\n"
        f"**Method:** {method}\n"
        f"**Success criteria:** {success}\n"
        f"**Symbols tested:** {symbols}\n"
        f"**Date range:** {date_range}\n"
        f"**Baseline metrics:** {baseline or '(pending)'}\n\n"
        f"**Result:** {result or '(pending)'}\n"
        f"**Conclusion:** {conclusion or '(pending)'}\n"
        f"**Next experiment:** {next_exp}\n"
        f"**Promoted to main strategy:** {promoted}\n"
    )


def build_parameter() -> str:
    print("\n── Parameter Change entry ────────────────────────────────────")
    param    = prompt("Parameter name (e.g. RSI_OVERSOLD)")
    old_val  = prompt("Old value")
    new_val  = prompt("New value")
    reason   = prompt_multiline("Reason for change")
    effect   = prompt_multiline("Expected effect")
    sprint   = prompt("Sprint number (e.g. Sprint 3)")
    result   = prompt_multiline("Result (leave blank if pending)", required=False)

    return (
        f"\n## {today()} — {param}\n"
        f"**Old value:** {old_val}\n"
        f"**New value:** {new_val}\n"
        f"**Reason:** {reason}\n"
        f"**Expected effect:** {effect}\n"
        f"**Sprint:** {sprint}\n"
        f"**Result:** {result or '(pending)'}\n"
    )


def build_regime() -> str:
    print("\n── Market Regime Note entry ──────────────────────────────────")
    topic   = prompt("Topic (e.g. 'BTCUSDT high-vol regime 2024-Q1')")
    summary = prompt("One-line summary")
    happened = prompt_multiline("What happened")
    why      = prompt_multiline("Why it happened")
    impact   = prompt_multiline("Impact on bot performance")
    changed  = prompt_multiline("What we changed (or 'nothing')")
    next_try = prompt_multiline("What to try next")
    status   = choose("Status", STATUS_OPTIONS["regime"])

    return (
        f"\n## {today()} {topic} — {summary}\n"
        f"**What happened:** {happened}\n"
        f"**Why it happened:** {why}\n"
        f"**Impact:** {impact}\n"
        f"**What we changed:** {changed}\n"
        f"**What to try next:** {next_try}\n"
        f"**Status:** {status}\n"
    )


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Append a structured entry to the crypto_ai_trader knowledge base."
    )
    parser.add_argument(
        "--type",
        choices=list(ENTRY_TYPES.keys()),
        help="Entry type. If omitted, you will be prompted to choose.",
    )
    args = parser.parse_args()

    print("\n═══════════════════════════════════════════════")
    print("  Knowledge Base Update — crypto_ai_trader")
    print("═══════════════════════════════════════════════")

    # Choose entry type
    if args.type:
        entry_type = args.type
    else:
        print("\nEntry types:")
        type_list = list(ENTRY_TYPES.keys())
        for i, (k, (_, desc)) in enumerate(ENTRY_TYPES.items(), 1):
            print(f"  {i}) {k:12s} — {desc}")
        while True:
            raw = input("\nChoose entry type (number or name): ").strip().lower()
            if raw in ENTRY_TYPES:
                entry_type = raw
                break
            if raw.isdigit() and 1 <= int(raw) <= len(type_list):
                entry_type = type_list[int(raw) - 1]
                break
            print(f"  ⚠  Invalid choice. Enter 1–{len(type_list)} or a type name.")

    filename, _ = ENTRY_TYPES[entry_type]
    file_path = KB_DIR / filename

    # Build the entry
    builders = {
        "bug":        build_bug,
        "strategy":   build_strategy,
        "experiment": lambda: build_experiment(file_path),
        "parameter":  build_parameter,
        "regime":     build_regime,
    }
    entry = builders[entry_type]()

    # Preview
    print("\n── Preview ───────────────────────────────────────────────────")
    print(entry)

    confirm = input("Append this entry? [Y/n]: ").strip().lower()
    if confirm not in ("y", "yes", ""):
        print("Aborted — nothing written.")
        sys.exit(0)

    append_entry(file_path, entry)

    print(f"\n✓ Entry appended to: {file_path}")
    print(f"  Type    : {entry_type}")
    print(f"  File    : knowledge/{filename}")
    print(f"  Written : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


if __name__ == "__main__":
    main()
