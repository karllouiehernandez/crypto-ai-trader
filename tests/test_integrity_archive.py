"""Tests for legacy integrity containment archive (Sprint 42 Priority #3)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import database.integrity as integrity_module
from database.integrity import (
    ARCHIVED_LEGACY_STATUS,
    INVALID_METRICS_STATUS,
    LEGACY_INVALID_STATUS,
    MISSING_TRADES_STATUS,
    VALID_STATUS,
    archive_legacy_integrity_rows,
    count_archivable_legacy_rows,
    count_archived_legacy_rows,
    refresh_integrity_flags,
    unarchive_legacy_integrity_rows,
)
from database.models import BacktestRun, BacktestTrade, SessionLocal, Trade
from tests._db_test_utils import install_temp_app_db


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    install_temp_app_db(
        monkeypatch,
        tmp_path,
        module_globals=globals(),
        module_targets=[integrity_module],
    )


def _seed_legacy_fixture() -> None:
    """Insert rows that will classify as legacy-invalid / invalid-metrics / missing-trades."""
    base = datetime.now(tz=timezone.utc) - timedelta(days=1)
    with SessionLocal() as sess:
        # 3 consecutive BUYs on BTCUSDT at small in-policy notional → the 2nd and 3rd
        # trip the consecutive-same-side rule; the 1st stays valid.
        for i in range(3):
            sess.add(Trade(
                ts=base + timedelta(seconds=i),
                symbol="BTCUSDT", side="BUY",
                qty=0.0001, price=50000.0, fee=0.0, pnl=0.0,
                artifact_id=None, run_mode="paper",
            ))
        # 1 valid pair on ETHUSDT (BUY then SELL)
        sess.add(Trade(ts=base, symbol="ETHUSDT", side="BUY",
                       qty=0.001, price=2000.0, fee=0.0, pnl=0.0, run_mode="paper"))
        sess.add(Trade(ts=base + timedelta(seconds=10), symbol="ETHUSDT", side="SELL",
                       qty=0.001, price=2010.0, fee=0.0, pnl=0.1, run_mode="paper"))

        # Backtest runs
        sess.add(BacktestRun(
            created_at=base, strategy_name="s1", symbol="BTCUSDT",
            start_ts=base, end_ts=base + timedelta(days=1),
            metrics_json="{bad-json}",
        ))
        sess.add(BacktestRun(
            created_at=base, strategy_name="s2", symbol="BTCUSDT",
            start_ts=base, end_ts=base + timedelta(days=1),
            metrics_json='{"n_trades": 2, "sharpe": 1.0}',
        ))
        sess.add(BacktestRun(
            created_at=base, strategy_name="s3", symbol="BTCUSDT",
            start_ts=base, end_ts=base + timedelta(days=1),
            metrics_json='{"n_trades": 0, "sharpe": 0.0}',
        ))
        sess.commit()

    with SessionLocal() as sess:
        refresh_integrity_flags(sess, retag_existing=True)


def test_refresh_classifies_legacy_rows():
    _seed_legacy_fixture()
    with SessionLocal() as sess:
        trades = sess.query(Trade).order_by(Trade.symbol, Trade.ts, Trade.id).all()
        legacy = [t for t in trades if t.integrity_status == LEGACY_INVALID_STATUS]
        valid = [t for t in trades if t.integrity_status == VALID_STATUS]
        assert len(legacy) == 2  # 2nd and 3rd BUY on BTCUSDT
        assert len(valid) == 3   # 1st BTC BUY + ETH BUY + ETH SELL

        runs = sess.query(BacktestRun).order_by(BacktestRun.id).all()
        statuses = [r.integrity_status for r in runs]
        assert INVALID_METRICS_STATUS in statuses
        assert MISSING_TRADES_STATUS in statuses
        assert VALID_STATUS in statuses


def test_count_archivable_before_and_after():
    _seed_legacy_fixture()
    with SessionLocal() as sess:
        before = count_archivable_legacy_rows(sess)
        assert before["trades"] == 2
        assert before["backtest_runs"] == 2  # invalid-metrics + missing-trades
        assert count_archived_legacy_rows(sess) == {"trades": 0, "backtest_runs": 0}

    with SessionLocal() as sess:
        result = archive_legacy_integrity_rows(sess)
    assert result == {"trades": 2, "backtest_runs": 2}

    with SessionLocal() as sess:
        after_archivable = count_archivable_legacy_rows(sess)
        after_archived = count_archived_legacy_rows(sess)
    assert after_archivable == {"trades": 0, "backtest_runs": 0}
    assert after_archived == {"trades": 2, "backtest_runs": 2}


def test_archive_preserves_prior_status_in_note():
    _seed_legacy_fixture()
    with SessionLocal() as sess:
        archive_legacy_integrity_rows(sess)

    with SessionLocal() as sess:
        archived_trades = (
            sess.query(Trade)
            .filter(Trade.integrity_status == ARCHIVED_LEGACY_STATUS)
            .all()
        )
        assert archived_trades, "expected archived trades"
        for t in archived_trades:
            assert "[archived-legacy]" in (t.integrity_note or "")
            assert f"prior_status={LEGACY_INVALID_STATUS}" in (t.integrity_note or "")


def test_refresh_does_not_regress_archived_rows():
    _seed_legacy_fixture()
    with SessionLocal() as sess:
        archive_legacy_integrity_rows(sess)
    with SessionLocal() as sess:
        refresh_integrity_flags(sess, retag_existing=True)
        archived = (
            sess.query(Trade)
            .filter(Trade.integrity_status == ARCHIVED_LEGACY_STATUS)
            .count()
        )
        regressed = (
            sess.query(Trade)
            .filter(Trade.integrity_status == LEGACY_INVALID_STATUS)
            .count()
        )
    assert archived == 2
    assert regressed == 0


def test_unarchive_reverts_and_reclassifies():
    _seed_legacy_fixture()
    with SessionLocal() as sess:
        archive_legacy_integrity_rows(sess)

    with SessionLocal() as sess:
        reverted = unarchive_legacy_integrity_rows(sess)
    assert reverted == {"trades": 2, "backtest_runs": 2}

    with SessionLocal() as sess:
        # After unarchive + automatic refresh, the prior legacy statuses must be restored.
        legacy_trades = (
            sess.query(Trade)
            .filter(Trade.integrity_status == LEGACY_INVALID_STATUS)
            .count()
        )
        archived_trades = (
            sess.query(Trade)
            .filter(Trade.integrity_status == ARCHIVED_LEGACY_STATUS)
            .count()
        )
        invalid_runs = (
            sess.query(BacktestRun)
            .filter(BacktestRun.integrity_status == INVALID_METRICS_STATUS)
            .count()
        )
        missing_runs = (
            sess.query(BacktestRun)
            .filter(BacktestRun.integrity_status == MISSING_TRADES_STATUS)
            .count()
        )
    assert legacy_trades == 2
    assert archived_trades == 0
    assert invalid_runs == 1
    assert missing_runs == 1


def test_archive_is_idempotent():
    _seed_legacy_fixture()
    with SessionLocal() as sess:
        first = archive_legacy_integrity_rows(sess)
    with SessionLocal() as sess:
        second = archive_legacy_integrity_rows(sess)
    assert first == {"trades": 2, "backtest_runs": 2}
    assert second == {"trades": 0, "backtest_runs": 0}


def test_refresh_does_not_create_new_legacy_rows_across_archived_gaps():
    base = datetime.now(tz=timezone.utc) - timedelta(days=1)
    with SessionLocal() as sess:
        sess.add(Trade(
            ts=base,
            symbol="BTCUSDT", side="SELL",
            qty=0.001, price=50000.0, fee=0.0, pnl=1.0,
            run_mode="paper", integrity_status=VALID_STATUS,
        ))
        sess.add(Trade(
            ts=base + timedelta(seconds=1),
            symbol="BTCUSDT", side="BUY",
            qty=0.001, price=49900.0, fee=0.0, pnl=0.0,
            run_mode="paper", integrity_status=ARCHIVED_LEGACY_STATUS,
            integrity_note="[archived-legacy] archived test fixture",
        ))
        sess.add(Trade(
            ts=base + timedelta(seconds=2),
            symbol="BTCUSDT", side="SELL",
            qty=0.001, price=50100.0, fee=0.0, pnl=1.0,
            run_mode="paper", integrity_status=VALID_STATUS,
        ))
        sess.commit()

    with SessionLocal() as sess:
        refresh_integrity_flags(sess, retag_existing=True)
        statuses = sess.query(Trade.integrity_status).order_by(Trade.id).all()

    assert statuses == [
        (VALID_STATUS,),
        (ARCHIVED_LEGACY_STATUS,),
        (VALID_STATUS,),
    ]
