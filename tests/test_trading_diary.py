from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from trading_diary import export as export_mod
from trading_diary import service as diary_service
from trading_diary.backtest_insights import extract_backtest_insights


class _SessionContext:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, exc_type, exc, tb):
        return False


class _WriteSession:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1


class _Query:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *criteria):
        for criterion in criteria:
            left = getattr(criterion, "left", None)
            right = getattr(criterion, "right", None)
            if left is None or right is None:
                continue
            field_name = getattr(left, "name", None)
            expected = getattr(right, "value", None)
            if field_name is None:
                continue
            self._rows = [row for row in self._rows if getattr(row, field_name, None) == expected]
        return self

    def order_by(self, *_args, **_kwargs):
        self._rows = sorted(
            self._rows,
            key=lambda row: getattr(row, "created_at", datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        )
        return self

    def limit(self, value):
        self._rows = self._rows[: int(value)]
        return self

    def all(self):
        return list(self._rows)


class _ReadSession:
    def __init__(self, rows):
        self._rows = list(rows)

    def query(self, _model):
        return _Query(self._rows)


def _patch_write_session(monkeypatch):
    session = _WriteSession()
    monkeypatch.setattr(diary_service, "init_db", lambda: None)
    monkeypatch.setattr(diary_service, "SessionLocal", lambda: _SessionContext(session))
    return session


def _patch_read_session(monkeypatch, rows):
    monkeypatch.setattr(diary_service, "init_db", lambda: None)
    monkeypatch.setattr(diary_service, "SessionLocal", lambda: _SessionContext(_ReadSession(rows)))


def _trade(**overrides):
    base = {
        "id": 1,
        "symbol": "BTCUSDT",
        "side": "SELL",
        "qty": 1.0,
        "price": 100.0,
        "pnl": 5.0,
        "strategy_name": "mean_reversion_v1",
        "run_mode": "paper",
        "regime": "RANGING",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _diary_entry(**overrides):
    base = {
        "id": 1,
        "created_at": datetime(2026, 4, 19, tzinfo=timezone.utc),
        "entry_type": "trade",
        "run_mode": "paper",
        "symbol": "BTCUSDT",
        "strategy_name": "mean_reversion_v1",
        "trade_id": 1,
        "backtest_run_id": None,
        "content": "Sample entry",
        "tags": json.dumps(["regime:ranging"]),
        "pnl": 1.0,
        "outcome_rating": None,
        "learnings": None,
        "strategy_suggestion": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _run_result(**overrides):
    base = {
        "run_id": 11,
        "symbol": "BTCUSDT",
        "strategy_name": "mean_reversion_v1",
        "passed": True,
        "failures": [],
        "metrics": {
            "sharpe": 1.2,
            "max_drawdown": 0.10,
            "profit_factor": 1.8,
            "n_trades": 6,
        },
        "trades": pd.DataFrame(),
    }
    base.update(overrides)
    return base


def test_sell_win_content_contains_win(monkeypatch):
    _patch_write_session(monkeypatch)
    entry = diary_service.record_trade_diary_entry(_trade(side="SELL", pnl=12.5))
    assert "WIN" in entry.content


def test_sell_loss_content_contains_loss(monkeypatch):
    _patch_write_session(monkeypatch)
    entry = diary_service.record_trade_diary_entry(_trade(side="SELL", pnl=-3.25))
    assert "LOSS" in entry.content


def test_buy_entry_type_is_trade(monkeypatch):
    _patch_write_session(monkeypatch)
    entry = diary_service.record_trade_diary_entry(_trade(side="BUY", pnl=0.0))
    assert entry.entry_type == "trade"


def test_tags_contain_regime(monkeypatch):
    _patch_write_session(monkeypatch)
    entry = diary_service.record_trade_diary_entry(_trade(side="BUY", regime="RANGING"))
    assert "regime:ranging" in json.loads(entry.tags)


def test_passed_verdict_in_content(monkeypatch):
    _patch_write_session(monkeypatch)
    entry = diary_service.record_backtest_insight(_run_result(passed=True))
    assert "PASSED" in entry.content


def test_failed_verdict_in_content(monkeypatch):
    _patch_write_session(monkeypatch)
    entry = diary_service.record_backtest_insight(_run_result(passed=False, failures=["Sharpe below gate"]))
    assert "FAILED" in entry.content


def test_entry_type_is_backtest_insight(monkeypatch):
    _patch_write_session(monkeypatch)
    entry = diary_service.record_backtest_insight(_run_result())
    assert entry.entry_type == "backtest_insight"


def test_win_rate_computed_correctly(monkeypatch):
    rows = [
        _diary_entry(id=1, pnl=1.0),
        _diary_entry(id=2, pnl=2.0),
        _diary_entry(id=3, pnl=3.0),
        _diary_entry(id=4, pnl=4.0),
        _diary_entry(id=5, pnl=-1.0),
        _diary_entry(id=6, pnl=-2.0),
    ]
    _patch_read_session(monkeypatch, rows)
    summary = diary_service.get_trading_summary()
    assert summary["win_rate"] == pytest.approx(4 / 6)


def test_zero_win_rate_regime_triggers_suggest():
    trades = pd.DataFrame(
        [
            {"side": "SELL", "regime": "RANGING", "pnl": -1.0},
            {"side": "SELL", "regime": "RANGING", "pnl": -0.5},
            {"side": "SELL", "regime": "RANGING", "pnl": -0.25},
        ]
    )
    content = extract_backtest_insights(_run_result(), trades)
    assert "pre-filter" in content


def test_high_win_rate_regime_triggers_increase_position():
    trades = pd.DataFrame(
        [
            {"side": "SELL", "regime": "TRENDING", "pnl": 2.0},
            {"side": "SELL", "regime": "TRENDING", "pnl": 1.5},
            {"side": "SELL", "regime": "TRENDING", "pnl": 0.5},
            {"side": "SELL", "regime": "TRENDING", "pnl": -0.25},
        ]
    )
    content = extract_backtest_insights(_run_result(), trades)
    assert "position size" in content


def test_export_writes_diary_learnings_md(monkeypatch, tmp_path: Path):
    export_path = tmp_path / "knowledge" / "diary_learnings.md"
    monkeypatch.setattr(export_mod, "_KNOWLEDGE_DIR", export_path.parent)
    monkeypatch.setattr(export_mod, "DIARY_LEARNINGS_PATH", export_path)
    monkeypatch.setattr(
        export_mod,
        "get_trading_summary",
        lambda: {
            "total_trades": 3,
            "win_rate": 2 / 3,
            "win_count": 2,
            "loss_count": 1,
            "total_pnl": 4.5,
            "avg_pnl": 1.5,
            "best_pnl": 3.0,
            "worst_pnl": -1.0,
            "best_strategy": "mean_reversion_v1",
            "worst_strategy": "breakout_v1",
            "best_symbol": "BTCUSDT",
            "worst_symbol": "ETHUSDT",
            "by_strategy": {},
            "by_regime": {},
        },
    )
    monkeypatch.setattr(
        export_mod,
        "list_diary_entries",
        lambda *args, **kwargs: [
            {
                "strategy_name": "mean_reversion_v1",
                "symbol": "BTCUSDT",
                "outcome_rating": 5,
                "learnings": "Wait for confirmation.",
                "strategy_suggestion": "Tighten stop after 2R.",
                "backtest_run_id": 11,
                "content": "Insight body",
            }
        ],
    )

    written_path = export_mod.export_diary_to_knowledge()

    assert Path(written_path).exists()
    assert "# Trading Diary Learnings" in Path(written_path).read_text(encoding="utf-8")


def test_filter_by_entry_type_returns_matching_rows(monkeypatch):
    rows = [
        _diary_entry(id=1, entry_type="backtest_insight", trade_id=None, backtest_run_id=11, pnl=None),
        _diary_entry(id=2, entry_type="trade", backtest_run_id=None, pnl=1.0),
    ]
    _patch_read_session(monkeypatch, rows)
    entries = diary_service.list_diary_entries(entry_type="backtest_insight")
    assert len(entries) == 1
    assert entries[0]["entry_type"] == "backtest_insight"


def test_empty_result_returns_empty_list(monkeypatch):
    _patch_read_session(monkeypatch, [])
    assert diary_service.list_diary_entries(entry_type="trade") == []
