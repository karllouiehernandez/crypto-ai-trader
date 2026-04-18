"""Symbol readiness helpers — tracks which symbols have local candle data."""

from __future__ import annotations

from datetime import datetime, timezone

from database.models import Candle, SessionLocal, SymbolLoadJob, init_db
from sqlalchemy import text


def _normalise_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def list_ready_symbols() -> list[str]:
    """Return symbols that have at least one local candle row, in alphabetical order."""
    init_db()
    with SessionLocal() as sess:
        rows = sess.query(Candle.symbol).distinct().order_by(Candle.symbol).all()
    return [row[0] for row in rows]


def is_symbol_ready(symbol: str) -> bool:
    """Return True if symbol has any local candle data."""
    init_db()
    clean = _normalise_symbol(symbol)
    with SessionLocal() as sess:
        exists = sess.query(Candle.id).filter(Candle.symbol == clean).limit(1).first()
    return exists is not None


def queue_symbol_load(symbol: str) -> dict:
    """Queue a background 30-day history load for a symbol.

    - If no job exists, creates one with status ``queued``.
    - If a ``queued`` or ``loading`` job already exists, returns it unchanged.
    - If a ``ready`` job exists, returns it as-is.
    - If the job previously ``failed``, resets it to ``queued`` for retry.
    """
    init_db()
    clean = _normalise_symbol(symbol)
    if not clean:
        raise ValueError("symbol is required")

    with SessionLocal() as sess:
        existing = sess.get(SymbolLoadJob, clean)
        if existing is None:
            job = SymbolLoadJob(
                symbol=clean,
                status="queued",
                queued_at=datetime.now(tz=timezone.utc),
            )
            sess.add(job)
            sess.commit()
            return {
                "symbol": clean,
                "status": "queued",
                "queued_at": job.queued_at,
                "error_msg": None,
            }

        if existing.status in ("queued", "loading", "ready"):
            return {
                "symbol": existing.symbol,
                "status": existing.status,
                "queued_at": existing.queued_at,
                "error_msg": existing.error_msg,
            }

        # failed → reset to queued for retry
        existing.status = "queued"
        existing.queued_at = datetime.now(tz=timezone.utc)
        existing.started_at = None
        existing.completed_at = None
        existing.error_msg = None
        sess.commit()
        return {
            "symbol": clean,
            "status": "queued",
            "queued_at": existing.queued_at,
            "error_msg": None,
        }


def retry_failed_load(symbol: str) -> dict:
    """Reset a failed load job back to queued (alias for queue_symbol_load)."""
    return queue_symbol_load(symbol)


def list_load_jobs() -> list[dict]:
    """Return all load jobs ordered by queued_at descending."""
    init_db()
    with SessionLocal() as sess:
        jobs = (
            sess.query(SymbolLoadJob)
            .order_by(SymbolLoadJob.queued_at.desc(), text("rowid DESC"))
            .all()
        )
        return [
            {
                "symbol": job.symbol,
                "status": job.status,
                "queued_at": job.queued_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "error_msg": job.error_msg,
            }
            for job in jobs
        ]
