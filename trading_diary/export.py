"""
trading_diary/export.py

Exports aggregated diary learnings to knowledge/diary_learnings.md so future
AI agents operating on this codebase can read accumulated insights.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from trading_diary.service import list_diary_entries, get_trading_summary


_KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
DIARY_LEARNINGS_PATH = _KNOWLEDGE_DIR / "diary_learnings.md"


def export_diary_to_knowledge() -> str:
    """Aggregate diary entries into knowledge/diary_learnings.md.

    Sections: Trading Summary, Winning Patterns, Losing Patterns,
    Strategy Suggestions, Backtest Insights.

    Returns the absolute path to the written file.
    """
    summary     = get_trading_summary()
    all_entries = list_diary_entries(limit=500)
    bt_entries  = list_diary_entries(entry_type="backtest_insight", limit=100)

    lines: list[str] = [
        "# Trading Diary Learnings",
        f"_Auto-generated on {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "_This file is maintained by the Trading Diary export function._",
        "_Do not edit manually — it will be overwritten on next export._",
        "",
        "---",
        "",
        "## Trading Summary",
        "",
        f"- **Total completed trades:** {summary['total_trades']}",
        f"- **Win rate:** {summary['win_rate']:.1%} "
        f"({summary['win_count']} wins / {summary['loss_count']} losses)",
        f"- **Total realised PnL:** {summary['total_pnl']:+.4f}",
        f"- **Average PnL per trade:** {summary['avg_pnl']:+.4f}",
        f"- **Best single trade PnL:** {summary['best_pnl']:+.4f}",
        f"- **Worst single trade PnL:** {summary['worst_pnl']:+.4f}",
        f"- **Best strategy (by PnL):** {summary['best_strategy'] or 'N/A'}",
        f"- **Worst strategy (by PnL):** {summary['worst_strategy'] or 'N/A'}",
        f"- **Best symbol (by PnL):** {summary['best_symbol'] or 'N/A'}",
        f"- **Worst symbol (by PnL):** {summary['worst_symbol'] or 'N/A'}",
        "",
    ]

    if summary["by_strategy"]:
        lines.append("### Performance by Strategy")
        for strat, stats in sorted(summary["by_strategy"].items(), key=lambda kv: -kv[1]["total_pnl"]):
            wr = stats["wins"] / stats["trades"] if stats["trades"] else 0
            lines.append(
                f"- **{strat}**: {stats['trades']} trades, "
                f"{wr:.0%} win rate, PnL {stats['total_pnl']:+.4f}"
            )
        lines.append("")

    if summary["by_regime"]:
        lines.append("### Performance by Regime")
        for regime, stats in sorted(summary["by_regime"].items(), key=lambda kv: -kv[1]["total_pnl"]):
            wr = stats["wins"] / stats["trades"] if stats["trades"] else 0
            lines.append(
                f"- **{regime}**: {stats['trades']} trades, "
                f"{wr:.0%} win rate, PnL {stats['total_pnl']:+.4f}"
            )
        lines.append("")

    winning = [e for e in all_entries if (e.get("outcome_rating") or 0) >= 4 and e.get("learnings")]
    if winning:
        lines += ["---", "", "## Winning Patterns", ""]
        for e in winning:
            lines.append(f"### {e.get('strategy_name') or 'unknown'} / {e.get('symbol') or ''} "
                         f"(rating {e.get('outcome_rating')}/5)")
            lines.append(e["learnings"])
            lines.append("")

    losing = [e for e in all_entries if (e.get("outcome_rating") or 6) <= 2 and e.get("learnings")]
    if losing:
        lines += ["---", "", "## Losing Patterns", ""]
        for e in losing:
            lines.append(f"### {e.get('strategy_name') or 'unknown'} / {e.get('symbol') or ''} "
                         f"(rating {e.get('outcome_rating')}/5)")
            lines.append(e["learnings"])
            lines.append("")

    suggestions = [e for e in all_entries if e.get("strategy_suggestion")]
    if suggestions:
        lines += ["---", "", "## Strategy Suggestions", ""]
        by_strat: dict[str, list[str]] = defaultdict(list)
        for e in suggestions:
            by_strat[e.get("strategy_name") or "general"].append(e["strategy_suggestion"])
        for strat, suggs in sorted(by_strat.items()):
            lines.append(f"### {strat}")
            for s in suggs:
                lines.append(f"- {s}")
            lines.append("")

    if bt_entries:
        lines += ["---", "", "## Backtest Insights", ""]
        for e in bt_entries:
            run_id = e.get("backtest_run_id", "?")
            sym    = e.get("symbol") or "?"
            strat  = e.get("strategy_name") or "?"
            lines.append(f"### Run #{run_id} — {sym} / {strat}")
            lines.append(e.get("content", ""))
            lines.append("")

    _KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    DIARY_LEARNINGS_PATH.write_text("\n".join(lines), encoding="utf-8")
    return str(DIARY_LEARNINGS_PATH)
