# crypto_ai_trader/collectors/historical_loader.py  (SAFE, DE-DUPING VERSION)
"""Historical data bootstrap and CLI commands."""

from __future__ import annotations

import asyncio
import argparse
from datetime import datetime, timedelta, timezone

from config import HIST_INTERVAL
from database.models import init_db
from market_data.history import (
    audit,
    backfill,
    ensure_symbol_history,
    format_audit_summary,
    sync_recent,
)
from market_data.professional_universe import list_professional_universe
from market_data.runtime_watchlist import list_runtime_symbols


def _print_audit(result: dict) -> None:
    print(format_audit_summary(result))
    if result.get("missing_ranges"):
        for item in result["missing_ranges"][:10]:
            print(
                "  - "
                f"{item['start'].strftime('%Y-%m-%d %H:%M')} → "
                f"{item['end'].strftime('%Y-%m-%d %H:%M')}"
            )


async def main() -> None:
    """Ensure every runtime-watchlist symbol has recent history."""
    init_db()
    symbols = list_runtime_symbols()
    for symbol in symbols:
        await asyncio.to_thread(ensure_symbol_history, symbol, HIST_INTERVAL)


def _run_cli(args: argparse.Namespace) -> int:
    init_db()
    if args.command == "backfill":
        result = backfill(args.symbol, args.start, args.end, interval=args.interval)
        _print_audit(result)
        return 0
    if args.command == "audit":
        result = audit(args.symbol, args.start, args.end, interval=args.interval)
        _print_audit(result)
        return 0 if result["is_complete"] else 1
    if args.command == "sync_recent":
        result = sync_recent(args.symbol, interval=args.interval)
        _print_audit(result)
        return 0
    if args.command == "warm-cache":
        symbols = _symbols_for_universe(args.universe)
        end = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
        start = end - timedelta(days=int(args.days))
        print(
            f"Warming Binance history cache for {len(symbols)} symbol(s), "
            f"{args.days} day(s), interval={args.interval}"
        )
        failures: list[str] = []
        for symbol in symbols:
            try:
                result = backfill(symbol, start, end, interval=args.interval)
                print(f"{symbol}: {format_audit_summary(result)}")
            except Exception as exc:
                failures.append(symbol)
                print(f"{symbol}: failed: {exc}")
        return 1 if failures else 0
    raise ValueError(f"Unknown command: {args.command}")


def _symbols_for_universe(name: str) -> list[str]:
    clean = str(name or "").strip().lower()
    if clean == "professional":
        return list_professional_universe()
    if clean == "runtime":
        return list_runtime_symbols()
    raise ValueError(f"Unknown universe: {name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Historical market data loader")
    sub = parser.add_subparsers(dest="command")

    backfill_parser = sub.add_parser("backfill")
    backfill_parser.add_argument("symbol")
    backfill_parser.add_argument("start", help="YYYY-MM-DD or ISO datetime")
    backfill_parser.add_argument("end", help="YYYY-MM-DD or ISO datetime")
    backfill_parser.add_argument("--interval", default=HIST_INTERVAL)

    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("symbol")
    audit_parser.add_argument("start", help="YYYY-MM-DD or ISO datetime")
    audit_parser.add_argument("end", help="YYYY-MM-DD or ISO datetime")
    audit_parser.add_argument("--interval", default=HIST_INTERVAL)

    sync_parser = sub.add_parser("sync_recent")
    sync_parser.add_argument("symbol")
    sync_parser.add_argument("--interval", default=HIST_INTERVAL)

    warm_parser = sub.add_parser("warm-cache")
    warm_parser.add_argument("--universe", choices=["professional", "runtime"], default="professional")
    warm_parser.add_argument("--days", type=int, default=30)
    warm_parser.add_argument("--interval", default=HIST_INTERVAL)

    args = parser.parse_args()
    if args.command:
        raise SystemExit(_run_cli(args))
    asyncio.run(main())
