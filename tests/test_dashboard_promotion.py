"""tests/test_dashboard_promotion.py — Tests for promotion panel data helpers and gate status."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from database.promotion_queries import query_promotions
from simulator.coordinator import Coordinator


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_db(tmp_path: Path) -> Path:
    """Create a minimal SQLite DB with the promotions table."""
    db = tmp_path / "test.db"
    con = sqlite3.connect(str(db))
    con.execute("""
        CREATE TABLE promotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            eval_number INTEGER,
            consecutive_promotes INTEGER,
            sharpe REAL,
            max_dd REAL,
            profit_factor REAL,
            confidence_score REAL,
            recommendation TEXT
        )
    """)
    con.commit()
    con.close()
    return db


def _insert_promotion(db: Path, **kwargs) -> None:
    defaults = dict(
        ts="2026-04-17 12:00:00",
        eval_number=3,
        consecutive_promotes=3,
        sharpe=1.9,
        max_dd=0.08,
        profit_factor=2.1,
        confidence_score=0.85,
        recommendation="PROMOTE_TO_LIVE",
    )
    defaults.update(kwargs)
    con = sqlite3.connect(str(db))
    con.execute(
        "INSERT INTO promotions (ts, eval_number, consecutive_promotes, sharpe, max_dd, "
        "profit_factor, confidence_score, recommendation) VALUES "
        "(:ts, :eval_number, :consecutive_promotes, :sharpe, :max_dd, "
        ":profit_factor, :confidence_score, :recommendation)",
        defaults,
    )
    con.commit()
    con.close()


# ── query_promotions ──────────────────────────────────────────────────────────

def test_query_promotions_empty_table(tmp_path):
    db = _make_db(tmp_path)
    df = query_promotions(db)
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_query_promotions_returns_dataframe_with_correct_columns(tmp_path):
    db = _make_db(tmp_path)
    _insert_promotion(db)
    df = query_promotions(db)
    expected = {"ts", "eval_number", "consecutive_promotes", "sharpe", "max_dd",
                "profit_factor", "confidence_score"}
    assert expected.issubset(set(df.columns))


def test_query_promotions_returns_one_row(tmp_path):
    db = _make_db(tmp_path)
    _insert_promotion(db)
    df = query_promotions(db)
    assert len(df) == 1


def test_query_promotions_returns_multiple_rows_newest_first(tmp_path):
    db = _make_db(tmp_path)
    _insert_promotion(db, ts="2026-04-15 10:00:00", eval_number=1, sharpe=1.6)
    _insert_promotion(db, ts="2026-04-17 12:00:00", eval_number=3, sharpe=1.9)
    df = query_promotions(db)
    assert len(df) == 2
    assert df.iloc[0]["eval_number"] == 3   # newest first


def test_query_promotions_correct_sharpe_value(tmp_path):
    db = _make_db(tmp_path)
    _insert_promotion(db, sharpe=2.35)
    df = query_promotions(db)
    assert abs(df.iloc[0]["sharpe"] - 2.35) < 1e-6


def test_query_promotions_correct_max_dd_value(tmp_path):
    db = _make_db(tmp_path)
    _insert_promotion(db, max_dd=0.12)
    df = query_promotions(db)
    assert abs(df.iloc[0]["max_dd"] - 0.12) < 1e-6


def test_query_promotions_missing_table_returns_empty(tmp_path):
    db = tmp_path / "no_table.db"
    # DB exists but has no promotions table
    sqlite3.connect(str(db)).close()
    df = query_promotions(db)
    assert df.empty


def test_query_promotions_nonexistent_file_returns_empty(tmp_path):
    db = tmp_path / "does_not_exist.db"
    df = query_promotions(db)
    # sqlite3 creates the file — table is missing, returns empty
    assert df.empty


def test_query_promotions_returns_empty_on_bad_path():
    df = query_promotions("/dev/null/impossible/path.db")
    assert df.empty


# ── Coordinator.promotion_status ──────────────────────────────────────────────

class FakeLearner:
    def __init__(self, gate: bool = False, promotes: int = 0) -> None:
        self._eval_count   = 5
        self._gate         = gate
        self._promotes     = promotes

    def confidence_gate_passed(self) -> bool:
        return self._gate

    def _consecutive_promotes(self) -> int:
        return self._promotes

    def _compute_paper_metrics(self) -> dict:
        return {"sharpe": 1.8, "max_drawdown": 0.1, "profit_factor": 2.0, "n_trades": 250.0}

    async def run_loop(self):
        pass


def test_promotion_status_initial_state():
    coord = Coordinator(FakeLearner())
    status = coord.promotion_status()
    assert status["promoted"] is False
    assert status["gate_passed"] is False
    assert status["eval_count"] == 5
    assert status["consecutive_promotes"] == 0
    assert status["learner_running"] is False


def test_promotion_status_has_all_keys():
    coord = Coordinator(FakeLearner())
    status = coord.promotion_status()
    for key in ("promoted", "eval_count", "consecutive_promotes", "gate_passed", "learner_running"):
        assert key in status


def test_promotion_status_after_check_gate():
    learner = FakeLearner(gate=True, promotes=3)
    coord   = Coordinator(learner)
    from unittest.mock import patch
    with patch.object(coord, "_record_promotion"), \
         patch.object(coord, "_write_promotion_entry"), \
         patch.object(coord, "_send_promotion_alert"):
        coord._check_gate()
    status = coord.promotion_status()
    assert status["promoted"] is True
    assert status["gate_passed"] is True
    assert status["consecutive_promotes"] == 3


def test_promotion_status_gate_passed_reflects_learner():
    learner = FakeLearner(gate=True, promotes=3)
    coord   = Coordinator(learner)
    assert coord.promotion_status()["gate_passed"] is True

    learner._gate = False
    assert coord.promotion_status()["gate_passed"] is False


# ── config.LIVE_TRADE_ENABLED ─────────────────────────────────────────────────

def test_live_trade_enabled_defaults_false():
    import config
    # Default: env var not set → False
    # We verify the attribute exists and is a bool
    assert isinstance(config.LIVE_TRADE_ENABLED, bool)


def test_live_trade_enabled_is_false_by_default(monkeypatch):
    monkeypatch.delenv("LIVE_TRADE_ENABLED", raising=False)
    import importlib
    import config
    importlib.reload(config)
    assert config.LIVE_TRADE_ENABLED is False


def test_live_trade_enabled_true_when_env_set(monkeypatch):
    monkeypatch.setenv("LIVE_TRADE_ENABLED", "true")
    import importlib
    import config
    importlib.reload(config)
    assert config.LIVE_TRADE_ENABLED is True
    monkeypatch.delenv("LIVE_TRADE_ENABLED", raising=False)
    importlib.reload(config)   # restore default
