"""tests/test_coordinator.py — Unit tests for Coordinator class."""
import asyncio
from contextlib import suppress
from unittest.mock import MagicMock, patch

import pytest

from simulator.coordinator import Coordinator


# ── Fake learner ───────────────────────────────────────────────────────────────

class FakeLearner:
    def __init__(self, gate_value: bool = False) -> None:
        self._gate_value  = gate_value
        self._eval_count  = 5

    def confidence_gate_passed(self) -> bool:
        return self._gate_value

    def _consecutive_promotes(self) -> int:
        return 3 if self._gate_value else 0

    def _compute_paper_metrics(self) -> dict:
        return {"sharpe": 1.8, "max_drawdown": 0.10, "profit_factor": 2.0, "n_trades": 250.0}

    async def run_loop(self) -> None:
        await asyncio.sleep(0)


# ── __init__ ───────────────────────────────────────────────────────────────────

def test_init_defaults():
    coord = Coordinator(FakeLearner())
    assert coord._promoted is False
    assert coord._check_interval == 3600


def test_init_custom_interval():
    coord = Coordinator(FakeLearner(), check_interval_s=60)
    assert coord._check_interval == 60


# ── _check_gate ────────────────────────────────────────────────────────────────

def test_check_gate_does_nothing_when_not_passed():
    coord = Coordinator(FakeLearner(gate_value=False))
    with patch.object(coord, "_record_promotion") as m_rec, \
         patch.object(coord, "_write_promotion_entry") as m_write, \
         patch.object(coord, "_send_promotion_alert") as m_alert:
        coord._check_gate()
    m_rec.assert_not_called()
    m_write.assert_not_called()
    m_alert.assert_not_called()
    assert coord._promoted is False


def test_check_gate_fires_all_three_when_gate_passes():
    coord = Coordinator(FakeLearner(gate_value=True))
    with patch.object(coord, "_record_promotion") as m_rec, \
         patch.object(coord, "_write_promotion_entry") as m_write, \
         patch.object(coord, "_send_promotion_alert") as m_alert:
        coord._check_gate()
    m_rec.assert_called_once()
    m_write.assert_called_once()
    m_alert.assert_called_once()
    assert coord._promoted is True


def test_check_gate_no_duplicate_after_first_promotion():
    coord = Coordinator(FakeLearner(gate_value=True))
    with patch.object(coord, "_record_promotion") as m_rec, \
         patch.object(coord, "_write_promotion_entry") as m_write, \
         patch.object(coord, "_send_promotion_alert") as m_alert:
        coord._check_gate()
        coord._check_gate()   # second call — already promoted, must be ignored
    assert m_rec.call_count == 1
    assert m_write.call_count == 1
    assert m_alert.call_count == 1


def test_check_gate_result_contains_expected_keys():
    coord = Coordinator(FakeLearner(gate_value=True))
    captured = {}
    def capture(result):
        captured.update(result)
    with patch.object(coord, "_record_promotion", side_effect=capture), \
         patch.object(coord, "_write_promotion_entry"), \
         patch.object(coord, "_send_promotion_alert"):
        coord._check_gate()
    assert "eval_number" in captured
    assert "consecutive_promotes" in captured
    assert "paper_metrics" in captured


# ── _record_promotion ─────────────────────────────────────────────────────────

def test_record_promotion_writes_to_db():
    coord = Coordinator(FakeLearner())
    result = {
        "eval_number": 3,
        "consecutive_promotes": 3,
        "paper_metrics": {"sharpe": 1.8, "max_drawdown": 0.1, "profit_factor": 2.0, "n_trades": 250.0},
        "confidence_score": 0.9,
    }
    mock_sess = MagicMock()
    mock_sess.__enter__ = MagicMock(return_value=mock_sess)
    mock_sess.__exit__ = MagicMock(return_value=False)
    with patch("simulator.coordinator.SessionLocal", return_value=mock_sess):
        coord._record_promotion(result)
    mock_sess.add.assert_called_once()
    mock_sess.commit.assert_called_once()


def test_record_promotion_db_record_has_correct_recommendation():
    coord = Coordinator(FakeLearner())
    added = []
    mock_sess = MagicMock()
    mock_sess.__enter__ = MagicMock(return_value=mock_sess)
    mock_sess.__exit__ = MagicMock(return_value=False)
    mock_sess.add.side_effect = lambda rec: added.append(rec)
    with patch("simulator.coordinator.SessionLocal", return_value=mock_sess):
        coord._record_promotion({"eval_number": 1, "consecutive_promotes": 3,
                                  "paper_metrics": {}, "confidence_score": 0.9})
    assert added[0].recommendation == "PROMOTE_TO_LIVE"


def test_record_promotion_survives_db_error():
    coord = Coordinator(FakeLearner())
    with patch("simulator.coordinator.SessionLocal", side_effect=Exception("DB down")):
        coord._record_promotion({})   # must not raise


def test_record_promotion_survives_missing_metrics_keys():
    coord = Coordinator(FakeLearner())
    mock_sess = MagicMock()
    mock_sess.__enter__ = MagicMock(return_value=mock_sess)
    mock_sess.__exit__ = MagicMock(return_value=False)
    with patch("simulator.coordinator.SessionLocal", return_value=mock_sess):
        coord._record_promotion({})   # empty dict — must not raise


# ── _write_promotion_entry ────────────────────────────────────────────────────

def test_write_promotion_entry_creates_file(tmp_path):
    coord = Coordinator(FakeLearner())
    dest  = tmp_path / "promotions.md"
    with patch("simulator.coordinator._PROMOTION_LOG", dest):
        coord._write_promotion_entry({
            "eval_number": 3,
            "consecutive_promotes": 3,
            "paper_metrics": {"sharpe": 1.8, "max_drawdown": 0.1,
                              "profit_factor": 2.0, "n_trades": 250.0},
        })
    content = dest.read_text()
    assert "PROMOTION EVENT" in content
    assert "Sharpe" in content
    assert "3" in content   # consecutive_promotes


def test_write_promotion_entry_appends_on_repeated_calls(tmp_path):
    coord = Coordinator(FakeLearner())
    dest  = tmp_path / "promotions.md"
    payload = {"eval_number": 1, "consecutive_promotes": 3,
               "paper_metrics": {"sharpe": 1.5, "max_drawdown": 0.08,
                                 "profit_factor": 1.8, "n_trades": 210.0}}
    with patch("simulator.coordinator._PROMOTION_LOG", dest):
        coord._write_promotion_entry(payload)
        coord._write_promotion_entry(payload)
    content = dest.read_text()
    assert content.count("PROMOTION EVENT") == 2


def test_write_promotion_entry_survives_os_error():
    coord = Coordinator(FakeLearner())
    with patch("simulator.coordinator._PROMOTION_LOG") as mock_path:
        mock_path.parent.mkdir.side_effect = OSError("no space")
        coord._write_promotion_entry({})   # must not raise


# ── _send_promotion_alert ─────────────────────────────────────────────────────

def test_send_promotion_alert_calls_alert():
    coord = Coordinator(FakeLearner())
    with patch("simulator.coordinator.alert") as mock_alert:
        coord._send_promotion_alert({
            "paper_metrics": {"sharpe": 1.8, "max_drawdown": 0.1,
                              "profit_factor": 2.0, "n_trades": 250.0},
        })
    mock_alert.assert_called_once()


def test_send_promotion_alert_message_contains_key_info():
    coord = Coordinator(FakeLearner())
    with patch("simulator.coordinator.alert") as mock_alert:
        coord._send_promotion_alert({
            "paper_metrics": {"sharpe": 2.1, "max_drawdown": 0.05,
                              "profit_factor": 3.0, "n_trades": 300.0},
        })
    msg = mock_alert.call_args[0][0]
    assert "Promotion" in msg or "PROMOTE" in msg
    assert "Sharpe" in msg


def test_send_promotion_alert_survives_missing_metrics():
    coord = Coordinator(FakeLearner())
    with patch("simulator.coordinator.alert"):
        coord._send_promotion_alert({})   # must not raise


# ── run_loop ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_loop_starts_self_learner_when_llm_enabled():
    learner  = FakeLearner()
    coord    = Coordinator(learner, check_interval_s=9999)
    started  = []
    original = learner.run_loop

    async def spy_run_loop():
        started.append(True)
        await original()

    learner.run_loop = spy_run_loop

    with patch("simulator.coordinator.LLM_ENABLED", True):
        task = asyncio.create_task(coord.run_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    assert len(started) == 1


@pytest.mark.asyncio
async def test_run_loop_skips_self_learner_when_llm_disabled():
    learner  = FakeLearner()
    coord    = Coordinator(learner, check_interval_s=9999)
    started  = []
    original = learner.run_loop

    async def spy_run_loop():
        started.append(True)
        await original()

    learner.run_loop = spy_run_loop

    with patch("simulator.coordinator.LLM_ENABLED", False):
        task = asyncio.create_task(coord.run_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    assert len(started) == 0


@pytest.mark.asyncio
async def test_run_loop_cancels_cleanly():
    coord = Coordinator(FakeLearner(), check_interval_s=9999)
    with patch("simulator.coordinator.LLM_ENABLED", False):
        task = asyncio.create_task(coord.run_loop())
        await asyncio.sleep(0.02)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    assert task.done()


@pytest.mark.asyncio
async def test_run_loop_stores_learner_task_reference():
    learner = FakeLearner()
    coord   = Coordinator(learner, check_interval_s=9999)
    assert coord._learner_task is None

    with patch("simulator.coordinator.LLM_ENABLED", True):
        task = asyncio.create_task(coord.run_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    assert coord._learner_task is not None


@pytest.mark.asyncio
async def test_run_loop_cancels_learner_task_on_shutdown():
    learner = FakeLearner()
    coord   = Coordinator(learner, check_interval_s=9999)

    with patch("simulator.coordinator.LLM_ENABLED", True):
        outer = asyncio.create_task(coord.run_loop())
        await asyncio.sleep(0.05)
        outer.cancel()
        with suppress(asyncio.CancelledError):
            await outer

    # learner task should be cancelled after coordinator shuts down
    assert coord._learner_task is not None
    assert coord._learner_task.cancelled() or coord._learner_task.done()
