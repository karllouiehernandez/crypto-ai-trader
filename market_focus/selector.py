"""Weekly market focus selector — deterministic, no LLM required."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import config
from backtester.engine import build_equity_curve, run_backtest
from backtester.metrics import compute_metrics
from database.models import (
    SessionLocal,
    WeeklyFocusCandidate,
    WeeklyFocusStudy,
    init_db,
)
from dashboard.workbench import parse_params_json
from market_data.binance_symbols import list_binance_spot_usdt_symbols

log = logging.getLogger(__name__)

def fetch_liquid_usdt_symbols(n: int = config.MARKET_FOCUS_UNIVERSE_SIZE) -> list[str]:
    """Return the top-N Binance spot USDT pairs by 24 h quote volume."""
    pairs: list[str] = []
    for item in list_binance_spot_usdt_symbols():
        sym = item["symbol"]
        if sym in config._MARKET_FOCUS_EXCLUDE:
            continue
        pairs.append(sym)
        if len(pairs) >= n:
            break
    return pairs


def _composite_score(metrics: dict[str, Any]) -> float:
    """Composite ranking score. Returns -999 when any key metric is missing."""
    raw_sharpe = metrics.get("sharpe")
    raw_pf = metrics.get("profit_factor")
    raw_dd = metrics.get("max_drawdown")
    if raw_sharpe is None or raw_pf is None:
        return -999.0
    sharpe = float(raw_sharpe)
    pf = float(raw_pf)
    max_dd = float(raw_dd) if raw_dd is not None else 0.0
    return sharpe * 0.4 + pf * 0.3 - abs(max_dd) * 0.3


def run_weekly_study(
    strategy_name: str,
    params: dict | None = None,
    *,
    backtest_days: int = config.MARKET_FOCUS_BACKTEST_DAYS,
    top_n: int = config.MARKET_FOCUS_TOP_N,
    universe_size: int = config.MARKET_FOCUS_UNIVERSE_SIZE,
) -> dict:
    """Discover top-liquid USDT symbols, backtest each, rank, and persist the study."""
    init_db()
    params = parse_params_json(json.dumps(params or {}))
    end = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
    start = end - timedelta(days=backtest_days)

    log.info("market_focus: fetching universe size=%d", universe_size)
    symbols = fetch_liquid_usdt_symbols(universe_size)

    with SessionLocal() as sess:
        study = WeeklyFocusStudy(
            strategy_name=strategy_name,
            params_json=json.dumps(params, sort_keys=True),
            universe_size=len(symbols),
            top_n=top_n,
            backtest_days=backtest_days,
            status="running",
        )
        sess.add(study)
        sess.flush()
        study_id = study.id
        sess.commit()

    scored: list[dict] = []
    for vol_rank, sym in enumerate(symbols, start=1):
        log.info("market_focus: backtest %s (vol_rank=%d)", sym, vol_rank)
        try:
            trades = run_backtest(sym, start, end, strategy_name=strategy_name, params=params)
            equity_curve = build_equity_curve(trades)
            metrics = compute_metrics(trades, equity_curve)
            score = _composite_score(metrics)
            status = "completed"
        except Exception as exc:
            log.warning("market_focus: backtest failed for %s — %s", sym, exc)
            metrics = {}
            score = -999.0
            status = "error"

        scored.append(
            {
                "symbol": sym,
                "volume_rank": vol_rank,
                "sharpe": metrics.get("sharpe"),
                "profit_factor": metrics.get("profit_factor"),
                "max_drawdown": metrics.get("max_drawdown"),
                "n_trades": metrics.get("n_trades"),
                "score": score,
                "status": status,
                "metrics": metrics,
            }
        )

    scored.sort(key=lambda r: r["score"], reverse=True)

    with SessionLocal() as sess:
        for final_rank, row in enumerate(scored, start=1):
            sess.add(
                WeeklyFocusCandidate(
                    study_id=study_id,
                    symbol=row["symbol"],
                    rank=final_rank,
                    volume_rank=row["volume_rank"],
                    sharpe=row["sharpe"],
                    profit_factor=row["profit_factor"],
                    max_drawdown=row["max_drawdown"],
                    n_trades=row["n_trades"],
                    score=row["score"],
                    status=row["status"],
                    metrics_json=json.dumps(row["metrics"], sort_keys=True),
                )
            )

        study_obj = sess.get(WeeklyFocusStudy, study_id)
        if study_obj:
            study_obj.status = "completed"
        sess.commit()

    top_candidates = scored[:top_n]
    log.info(
        "market_focus: study %d complete — top %s",
        study_id,
        [r["symbol"] for r in top_candidates],
    )
    return {
        "study_id": study_id,
        "strategy_name": strategy_name,
        "params": params,
        "top_candidates": top_candidates,
        "all_candidates": scored,
    }


def get_latest_study() -> dict | None:
    """Return the most recent completed study's header row, or None."""
    init_db()
    with SessionLocal() as sess:
        study = (
            sess.query(WeeklyFocusStudy)
            .filter(WeeklyFocusStudy.status == "completed")
            .order_by(WeeklyFocusStudy.created_at.desc())
            .first()
        )
        if study is None:
            return None
        return {
            "id": study.id,
            "created_at": study.created_at,
            "strategy_name": study.strategy_name,
            "params": parse_params_json(study.params_json),
            "universe_size": study.universe_size,
            "top_n": study.top_n,
            "backtest_days": study.backtest_days,
            "status": study.status,
        }


def get_study_candidates(study_id: int) -> list[dict]:
    """Return all candidates for a study ordered by rank."""
    init_db()
    with SessionLocal() as sess:
        rows = (
            sess.query(WeeklyFocusCandidate)
            .filter(WeeklyFocusCandidate.study_id == study_id)
            .order_by(WeeklyFocusCandidate.rank)
            .all()
        )
        return [
            {
                "id": row.id,
                "study_id": row.study_id,
                "symbol": row.symbol,
                "rank": row.rank,
                "volume_rank": row.volume_rank,
                "sharpe": row.sharpe,
                "profit_factor": row.profit_factor,
                "max_drawdown": row.max_drawdown,
                "n_trades": row.n_trades,
                "score": row.score,
                "status": row.status,
                "metrics": parse_params_json(row.metrics_json),
            }
            for row in rows
        ]
