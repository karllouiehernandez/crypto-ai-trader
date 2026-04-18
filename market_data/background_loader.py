"""Background daemon thread that processes symbol history load jobs."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from database.models import SessionLocal, SymbolLoadJob, init_db

log = logging.getLogger(__name__)

_READY_DAYS = 30
_POLL_SECONDS = 5

_lock = threading.Lock()
_worker: threading.Thread | None = None


def _load_symbol(symbol: str) -> None:
    """Download 30 days of 1m history then sync to now."""
    from market_data.history import backfill, sync_recent

    now = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
    start = now - timedelta(days=_READY_DAYS)
    backfill(symbol, start, now, interval="1m")
    sync_recent(symbol, interval="1m")


def _run_next_job() -> bool:
    """Pick up one queued job, process it, update its status. Returns True if a job was found."""
    init_db()
    with SessionLocal() as sess:
        job = (
            sess.query(SymbolLoadJob)
            .filter(SymbolLoadJob.status == "queued")
            .order_by(SymbolLoadJob.queued_at)
            .first()
        )
        if job is None:
            return False
        job.status = "loading"
        job.started_at = datetime.now(tz=timezone.utc)
        sess.commit()
        symbol = job.symbol

    log.info("background_loader: loading %s", symbol)
    try:
        _load_symbol(symbol)
        with SessionLocal() as sess:
            job = sess.get(SymbolLoadJob, symbol)
            if job:
                job.status = "ready"
                job.completed_at = datetime.now(tz=timezone.utc)
                job.error_msg = None
                sess.commit()
        log.info("background_loader: %s ready", symbol)
    except Exception as exc:
        log.exception("background_loader: failed to load %s", symbol)
        with SessionLocal() as sess:
            job = sess.get(SymbolLoadJob, symbol)
            if job:
                job.status = "failed"
                job.completed_at = datetime.now(tz=timezone.utc)
                job.error_msg = str(exc)[:500]
                sess.commit()
    return True


def _worker_loop() -> None:
    while True:
        try:
            _run_next_job()
        except Exception:
            log.exception("background_loader: worker loop error")
        time.sleep(_POLL_SECONDS)


def ensure_worker_running() -> None:
    """Start the background loader daemon thread if it is not already running."""
    global _worker
    with _lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(
                target=_worker_loop,
                daemon=True,
                name="symbol-loader",
            )
            _worker.start()
            log.info("background_loader: worker started")
