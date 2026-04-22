# crypto_ai_trader/run_live.py
"""
Boot sequence: load history, start live streamer, then launch paper trader + coordinator.
"""
import asyncio
import logging
from datetime import datetime, timezone

from config import (
    validate_env, LLM_ENABLED, LIVE_TRADE_ENABLED,
    BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_TESTNET,
    check_available_memory_gb,
)
from collectors.historical_loader import main as load_history
from collectors.live_streamer     import main as live_stream
from market_data.history          import maintain_symbol_freshness
from simulator.paper_trader       import PaperTrader
from simulator.coordinator        import Coordinator
from llm.self_learner             import SelfLearner
from strategy.artifacts           import mark_artifact_live_active
from strategy.runtime             import get_active_runtime_artifact, resolve_runtime_strategy_descriptor
from utils.telegram_utils         import send_telegram_alert, _token, _chat_id

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)
HEARTBEAT_SECONDS = 30
FRESHNESS_GUARD_SECONDS = 300


def _format_status_timestamp(value) -> str:
    if value is None:
        return "-"
    ts = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    return ts.strftime("%Y-%m-%d %H:%M:%S UTC")


def _status_fields(snapshot: dict) -> dict:
    return {
        "run_mode": snapshot.get("run_mode", "paper"),
        "strategy": f"{snapshot.get('strategy_name', '-')}@{snapshot.get('strategy_version') or '-'}",
        "artifact": str(snapshot.get("artifact_id") or "-"),
        "symbols": ",".join(snapshot.get("symbols", [])) or "-",
        "cash": f"{float(snapshot.get('cash', 0.0)):.2f}",
        "equity": f"{float(snapshot.get('equity', 0.0)):.2f}",
        "realized": f"{float(snapshot.get('realized_pnl', 0.0)):+.2f}",
        "open_positions": str(int(snapshot.get("open_position_count", 0) or 0)),
        "last_candle": _format_status_timestamp(snapshot.get("last_processed_candle_ts")),
        "last_trade": _format_status_timestamp(snapshot.get("last_trade_ts")),
        "halted": str(bool(snapshot.get("trading_halted", False))).lower(),
        "force_halt": str(bool(snapshot.get("force_halt", False))).lower(),
    }


def log_runner_snapshot(message: str, snapshot: dict, *, llm_enabled: bool | None = None, live_trade_enabled: bool | None = None) -> None:
    fields = _status_fields(snapshot)
    suffix_parts = []
    if llm_enabled is not None:
        suffix_parts.append(f"llm_enabled={str(bool(llm_enabled)).lower()}")
    if live_trade_enabled is not None:
        suffix_parts.append(f"live_trade_enabled={str(bool(live_trade_enabled)).lower()}")
    paper_evidence = snapshot.get("paper_evidence") or {}
    if paper_evidence:
        suffix_parts.append(f"paper_evidence={paper_evidence.get('stage') or 'unknown'}")
        suffix_parts.append(
            f"paper_trades={int(paper_evidence.get('trade_count', 0) or 0)}/"
            f"{int(paper_evidence.get('trade_target', 0) or 0)}"
        )
        suffix_parts.append(
            f"paper_runtime={float(paper_evidence.get('runtime_days', 0.0) or 0.0):.1f}/"
            f"{float(paper_evidence.get('runtime_target_days', 0.0) or 0.0):.1f}d"
        )
        suffix_parts.append(f"paper_blockers={int(paper_evidence.get('blocker_count', 0) or 0)}")
    suffix = f" | {' '.join(suffix_parts)}" if suffix_parts else ""
    log.info(
        "%s | mode=%s artifact=%s strategy=%s symbols=%s cash=%s equity=%s realized=%s open_positions=%s last_candle=%s last_trade=%s halted=%s force_halt=%s%s",
        message,
        fields["run_mode"],
        fields["artifact"],
        fields["strategy"],
        fields["symbols"],
        fields["cash"],
        fields["equity"],
        fields["realized"],
        fields["open_positions"],
        fields["last_candle"],
        fields["last_trade"],
        fields["halted"],
        fields["force_halt"],
        suffix,
    )


def _format_freshness_maintenance_summary(results: dict) -> str | None:
    if not results:
        return None
    refreshed = [
        f"{symbol}(+{int(payload.get('rows_inserted', 0) or 0)} rows)"
        for symbol, payload in results.items()
        if payload.get("status") == "synced"
    ]
    if refreshed:
        return "refreshed=" + ",".join(refreshed)
    return None


async def heartbeat_loop(trader: PaperTrader, interval_seconds: int = HEARTBEAT_SECONDS) -> None:
    """Emit a concise runner heartbeat so quiet markets do not look like a dead process."""
    while True:
        log_runner_snapshot("Runner heartbeat", trader.get_status_snapshot())
        await asyncio.sleep(interval_seconds)


async def freshness_guard_loop(interval_seconds: int = FRESHNESS_GUARD_SECONDS) -> None:
    """Keep the maintained research universe fresh without manual operator syncs."""
    while True:
        try:
            results = await asyncio.to_thread(maintain_symbol_freshness)
            summary = _format_freshness_maintenance_summary(results)
            if summary:
                log.info("Maintained-universe sync | %s", summary)
        except Exception:
            log.exception("Maintained-universe sync failed")
        await asyncio.sleep(interval_seconds)


async def boot():
    await load_history()          # idempotent; skips already-stored candles
    initial_freshness = await asyncio.to_thread(maintain_symbol_freshness)
    initial_summary = _format_freshness_maintenance_summary(initial_freshness)
    if initial_summary:
        log.info("Maintained-universe sync at startup | %s", initial_summary)

    runtime_mode = "live" if LIVE_TRADE_ENABLED else "paper"
    runtime_descriptor = resolve_runtime_strategy_descriptor(runtime_mode)
    paper_target = get_active_runtime_artifact("paper")
    live_target = get_active_runtime_artifact("live")

    trader      = PaperTrader(strategy_descriptor=runtime_descriptor, restore_runtime_state=True)
    learner     = SelfLearner()
    coordinator = Coordinator(learner, runtime_artifact=runtime_descriptor)
    trader._coordinator = coordinator
    log.info(
        "Runtime targets | paper=%s live=%s",
        (
            f"{paper_target.get('name')}@{paper_target.get('version')} "
            f"(artifact {paper_target.get('id')}, {paper_target.get('status')})"
            if paper_target else "unconfigured"
        ),
        (
            f"{live_target.get('name')}@{live_target.get('version')} "
            f"(artifact {live_target.get('id')}, {live_target.get('status')})"
            if live_target else "unconfigured"
        ),
    )
    log_runner_snapshot(
        "Runner startup",
        trader.get_status_snapshot(),
        llm_enabled=LLM_ENABLED,
        live_trade_enabled=LIVE_TRADE_ENABLED,
    )
    if LIVE_TRADE_ENABLED:
        mark_artifact_live_active(runtime_descriptor.get("artifact_id"))

    binance_client = None
    if LIVE_TRADE_ENABLED:
        from binance import AsyncClient
        binance_client = await AsyncClient.create(
            BINANCE_API_KEY, BINANCE_API_SECRET, testnet=BINANCE_TESTNET
        )
        trader._binance_client = binance_client
        log.warning("=" * 60)
        log.warning("LIVE TRADING ENABLED - real orders will be submitted")
        log.warning("=" * 60)
        send_telegram_alert(_token(), _chat_id(),
            "⚡ *LIVE TRADING ENABLED*\nBot is now submitting real Binance orders.")

    try:
        await asyncio.gather(
            live_stream(),
            trader.run(),
            coordinator.run_loop(),
            heartbeat_loop(trader),
            freshness_guard_loop(),
        )
    finally:
        if binance_client is not None:
            await binance_client.close()
        log.info("run_live shutdown complete")


if __name__ == "__main__":
    validate_env()                # fail fast with clear error if .env is missing
    avail_gb = check_available_memory_gb()
    if 0 < avail_gb < 1.0:
        log.warning(
            "LOW MEMORY WARNING: Only %.1fGB RAM available. "
            "Consider reducing MAX_SYMBOLS=1 in .env and ensuring swap is enabled. "
            "See deployment/README.md for Jetson Nano setup.",
            avail_gb,
        )
    try:
        asyncio.run(boot())
    except KeyboardInterrupt:
        log.info("run_live interrupted by user; shutting down")
