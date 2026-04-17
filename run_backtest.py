# crypto_ai_trader/run_backtest.py
"""
Usage (walk-forward, default):
    python run_backtest.py BTCUSDT 2024-01-01 2024-06-30

Usage (single window, no walk-forward):
    python run_backtest.py BTCUSDT 2024-01-01 2024-03-31 --no-walk-forward

Exit code 1 if any OOS window fails the acceptance gate.
"""
import argparse
import sys
from datetime import datetime

from config import validate_env_backtest
from backtester.engine import run_backtest, build_equity_curve
from backtester.metrics import compute_metrics, acceptance_gate
from backtester.walk_forward import walk_forward, aggregate_results


def _print_window_table(results: list) -> None:
    header = (
        f"{'Win':>3}  {'OOS Start':>10}  {'OOS End':>10}  "
        f"{'Sharpe':>7}  {'MaxDD':>7}  {'PF':>6}  {'Trades':>6}  {'Pass':>4}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        status = "✓" if r["passed"] else "✗"
        print(
            f"{r['window']:>3}  {r['oos_start'].strftime('%Y-%m-%d'):>10}  "
            f"{r['oos_end'].strftime('%Y-%m-%d'):>10}  "
            f"{r['sharpe']:>7.3f}  {r['max_drawdown']:>7.2%}  "
            f"{r['profit_factor']:>6.2f}  {r['n_trades']:>6}  {status:>4}"
        )
        if not r["passed"]:
            for reason in r["failures"]:
                print(f"     ↳ {reason}")


def _run_walk_forward(args) -> int:
    start = datetime.fromisoformat(args.start)
    end   = datetime.fromisoformat(args.end)

    print(f"\n{'='*60}")
    print(f"Walk-forward: {args.symbol.upper()}  {args.start} → {args.end}")
    print(f"{'='*60}\n")

    results = walk_forward(args.symbol.upper(), start, end)

    if not results:
        print("No complete windows found in the given date range.")
        return 1

    _print_window_table(results)

    agg = aggregate_results(results)
    print(f"\n{'─'*60}")
    print("Aggregate summary:")
    print(f"  Windows:        {agg['n_windows']}  (passed: {agg['windows_passed']})")
    print(f"  Pass rate:      {agg['pass_rate']:.0%}")
    print(f"  Mean Sharpe:    {agg['mean_sharpe']:.3f}")
    print(f"  Mean MaxDD:     {agg['mean_max_drawdown']:.2%}")
    print(f"  Mean PF:        {agg['mean_profit_factor']:.3f}")
    print(f"  Total trades:   {agg['total_trades']}")
    print(f"{'─'*60}\n")

    failed_windows = [r for r in results if not r["passed"]]
    if failed_windows:
        print(f"⚠  {len(failed_windows)} window(s) failed acceptance gate — see table above.")
        return 1
    print("✓  All windows passed acceptance gate.")
    return 0


def _run_single(args) -> int:
    start = datetime.fromisoformat(args.start)
    end   = datetime.fromisoformat(args.end)

    trades = run_backtest(args.symbol.upper(), start, end)
    if not trades:
        print("No trades generated.")
        return 0

    print(trades.to_string(index=False))

    equity = build_equity_curve(trades)
    metrics = compute_metrics(trades, equity)
    passed, failures = acceptance_gate(metrics)

    print(f"\n--- Metrics ---")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    status = "PASSED ✓" if passed else "FAILED ✗"
    print(f"\nAcceptance gate: {status}")
    for reason in failures:
        print(f"  ↳ {reason}")

    try:
        import matplotlib.pyplot as plt
        plt.figure()
        plt.plot(equity.values)
        plt.title(f"{args.symbol} equity curve")
        plt.xlabel("Candle")
        plt.ylabel("Balance ($)")
        plt.show()
    except ImportError:
        pass

    return 0 if passed else 1


if __name__ == "__main__":
    validate_env_backtest()

    p = argparse.ArgumentParser(description="Backtest a symbol with walk-forward validation")
    p.add_argument("symbol")
    p.add_argument("start", help="YYYY-MM-DD")
    p.add_argument("end",   help="YYYY-MM-DD")
    p.add_argument(
        "--no-walk-forward",
        action="store_true",
        help="Run a single backtest over the full period instead of walk-forward",
    )
    args = p.parse_args()

    if args.no_walk_forward:
        sys.exit(_run_single(args))
    else:
        sys.exit(_run_walk_forward(args))
