"""
trading_diary/backtest_insights.py

Deterministic, rule-based extraction of human-readable insights from a completed
backtest result dict + its trades DataFrame.  No LLM required.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd


def extract_backtest_insights(run_result: dict[str, Any], trades_df: pd.DataFrame) -> str:
    """Return a Markdown string summarising actionable insights from one backtest run.

    Analyses: overall verdict, regime win rates, UTC-hour timing, loss streaks,
    parameter tuning hints derived from gate failures.
    """
    lines: list[str] = []

    metrics  = run_result.get("metrics", {}) or {}
    passed   = run_result.get("passed", False)
    failures = run_result.get("failures", []) or []
    symbol   = run_result.get("symbol", "?")
    strategy = run_result.get("strategy_name", "?")
    run_id   = run_result.get("run_id", "?")

    sharpe   = float(metrics.get("sharpe", 0) or 0)
    max_dd   = float(metrics.get("max_drawdown", 0) or 0)
    pf       = float(metrics.get("profit_factor", 0) or 0)
    n_trades = int(metrics.get("n_trades", 0) or 0)

    verdict = "PASSED" if passed else "FAILED"
    lines.append(f"## Backtest Insight — Run #{run_id} ({symbol} / {strategy})")
    lines.append(f"**Verdict:** {verdict}  ")
    lines.append(
        f"**Metrics:** Sharpe={sharpe:.2f}, MaxDD={max_dd:.1%}, "
        f"ProfitFactor={pf:.2f}, Trades={n_trades}"
    )

    if failures:
        lines.append("\n**Gate Failures:**")
        for f in failures:
            lines.append(f"- {f}")

    regime_lines = _regime_analysis(trades_df)
    if regime_lines:
        lines.append("\n### Regime Performance")
        lines.extend(regime_lines)

    hour_lines = _hour_analysis(trades_df)
    if hour_lines:
        lines.append("\n### Trade Timing (UTC Hour)")
        lines.extend(hour_lines)

    streak_lines = _loss_streak_analysis(trades_df)
    if streak_lines:
        lines.append("\n### Loss Streak Analysis")
        lines.extend(streak_lines)

    hints = _parameter_hints(metrics, failures)
    if hints:
        lines.append("\n### Parameter Tuning Suggestions")
        for h in hints:
            lines.append(f"- {h}")

    return "\n".join(lines)


def _regime_analysis(trades_df: pd.DataFrame) -> list[str]:
    if trades_df.empty or "regime" not in trades_df.columns or "side" not in trades_df.columns:
        return []

    df = trades_df.copy()
    df["regime"] = df["regime"].fillna("UNKNOWN").astype(str).str.upper()
    df["side"]   = df["side"].astype(str).str.upper()

    if "pnl" in df.columns:
        sell_rows = df[df["side"] == "SELL"].copy()
        sell_rows["pnl"] = pd.to_numeric(sell_rows["pnl"], errors="coerce").fillna(0.0)
    else:
        sell_rows = _pair_trades_pnl(df)

    if sell_rows.empty:
        return []

    regime_stats: dict[str, dict] = defaultdict(lambda: {"total": 0, "wins": 0, "pnl": 0.0})
    for _, row in sell_rows.iterrows():
        r = str(row.get("regime", "UNKNOWN")).upper()
        regime_stats[r]["total"] += 1
        pnl = float(row.get("pnl", 0) or 0)
        if pnl > 0:
            regime_stats[r]["wins"] += 1
        regime_stats[r]["pnl"] += pnl

    lines: list[str] = []
    total_sells = len(sell_rows)
    for regime, s in sorted(regime_stats.items()):
        win_rate = s["wins"] / s["total"] if s["total"] else 0.0
        pct = s["total"] / total_sells if total_sells else 0.0
        lines.append(
            f"- **{regime}**: {s['total']} trades ({pct:.0%} of total), "
            f"win rate {win_rate:.0%}, cumulative PnL {s['pnl']:+.4f}"
        )
        if win_rate == 0.0 and s["total"] >= 3:
            lines.append(
                f"  - Suggest adding a **{regime} regime pre-filter** — "
                f"0% win rate across {s['total']} trades."
            )
        elif win_rate >= 0.70 and s["total"] >= 3:
            lines.append(
                f"  - {regime} shows strong alpha ({win_rate:.0%} win rate). "
                f"Consider increasing position size when regime={regime}."
            )

    if len(regime_stats) >= 2:
        best  = max(regime_stats, key=lambda k: regime_stats[k]["wins"] / max(regime_stats[k]["total"], 1))
        worst = min(regime_stats, key=lambda k: regime_stats[k]["wins"] / max(regime_stats[k]["total"], 1))
        bwr = regime_stats[best]["wins"]  / max(regime_stats[best]["total"], 1)
        wwr = regime_stats[worst]["wins"] / max(regime_stats[worst]["total"], 1)
        if best != worst:
            lines.append(
                f"\n**Best regime:** {best} ({bwr:.0%} win rate)  "
                f"**Worst regime:** {worst} ({wwr:.0%} win rate)"
            )

    return lines


def _hour_analysis(trades_df: pd.DataFrame) -> list[str]:
    if trades_df.empty or "ts" not in trades_df.columns:
        return []

    df = trades_df.copy()
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce", utc=True)
    df = df.dropna(subset=["ts"])
    if df.empty:
        return []

    df["hour"] = df["ts"].dt.hour
    if "side" not in df.columns or "pnl" not in df.columns:
        return []

    sell_df = df[df["side"].astype(str).str.upper() == "SELL"].copy()
    sell_df["pnl"] = pd.to_numeric(sell_df["pnl"], errors="coerce").fillna(0.0)
    if sell_df.empty:
        return []

    hour_pnl = sell_df.groupby("hour")["pnl"].sum()
    best_hour  = int(hour_pnl.idxmax())
    worst_hour = int(hour_pnl.idxmin())
    lines = [
        f"- Best exit hour (UTC): **{best_hour:02d}:00** (total PnL {hour_pnl[best_hour]:+.4f})",
        f"- Worst exit hour (UTC): **{worst_hour:02d}:00** (total PnL {hour_pnl[worst_hour]:+.4f})",
    ]
    if hour_pnl[worst_hour] < 0:
        lines.append(
            f"  - Suggest evaluating a **time-of-day filter** — "
            f"exits at {worst_hour:02d}:xx UTC are net negative."
        )
    return lines


def _loss_streak_analysis(trades_df: pd.DataFrame) -> list[str]:
    if trades_df.empty or "pnl" not in trades_df.columns:
        return []

    df = trades_df.copy()
    if "side" in df.columns:
        df = df[df["side"].astype(str).str.upper() == "SELL"].copy()
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce").fillna(0.0)
    if df.empty:
        return []

    max_streak = current = 0
    for pnl in df["pnl"]:
        if pnl <= 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0

    if max_streak == 0:
        return ["- No consecutive losing trades detected."]

    lines = [f"- Maximum consecutive loss streak: **{max_streak}** trades"]
    if max_streak >= 5:
        lines.append(
            f"  - A {max_streak}-trade losing streak detected. "
            "Consider a circuit-breaker rule (e.g., pause after 3 consecutive losses)."
        )
    return lines


def _parameter_hints(metrics: dict[str, Any], failures: list[str]) -> list[str]:
    hints: list[str] = []
    sharpe   = float(metrics.get("sharpe", 0) or 0)
    max_dd   = float(metrics.get("max_drawdown", 0) or 0)
    pf       = float(metrics.get("profit_factor", 0) or 0)
    n_trades = int(metrics.get("n_trades", 0) or 0)
    failure_text = " ".join(failures).lower()

    if "sharpe" in failure_text:
        if sharpe < 0.5:
            hints.append(
                "Sharpe < 0.5 — strategy produces noisy returns. "
                "Try tightening entry conditions (stronger volume confirmation or higher ADX threshold)."
            )
        else:
            hints.append(
                f"Sharpe {sharpe:.2f} misses gate. "
                "Consider reducing fee drag by requiring a larger minimum move before entry."
            )

    if "drawdown" in failure_text:
        hints.append(
            f"Max drawdown {max_dd:.1%} exceeds gate. "
            "Reduce position size (RISK_PCT_PER_TRADE) or tighten ATR_STOP_MULTIPLIER."
        )

    if "profit factor" in failure_text:
        hints.append(
            f"Profit factor {pf:.2f} below gate. "
            "Winning trades are not large enough relative to losses — "
            "consider a tighter stop loss or wider take profit."
        )

    if "trade count" in failure_text or "n_trades" in failure_text:
        hints.append(
            f"Only {n_trades} trades — too few for statistical significance. "
            "Extend the test window, relax entry conditions, or add more symbols."
        )

    if not failures and sharpe < 2.0 and sharpe > 0:
        hints.append(
            f"Strategy passes all gates (Sharpe={sharpe:.2f}). "
            "To improve further, try walk-forward optimisation on the signal parameters."
        )

    return hints


def _pair_trades_pnl(df: pd.DataFrame) -> pd.DataFrame:
    """Approximate PnL for each SELL by pairing with the preceding BUY."""
    rows = df.reset_index(drop=True)
    result = []
    i = 0
    while i < len(rows) - 1:
        buy_row  = rows.iloc[i]
        sell_row = rows.iloc[i + 1]
        if (str(buy_row.get("side", "")).upper() == "BUY"
                and str(sell_row.get("side", "")).upper() == "SELL"):
            buy_price  = float(buy_row.get("price", 0) or 0)
            sell_price = float(sell_row.get("price", 0) or 0)
            qty        = float(sell_row.get("qty", 1) or 1)
            entry = sell_row.to_dict()
            entry["pnl"] = (sell_price - buy_price) * qty
            result.append(entry)
            i += 2
            continue
        i += 1
    return pd.DataFrame(result) if result else pd.DataFrame()
