from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from run_live import (
    _format_freshness_maintenance_summary,
    _status_fields,
    build_arg_parser,
    log_runner_snapshot,
    main,
)


def test_status_fields_formats_snapshot_values():
    snapshot = {
        "run_mode": "paper",
        "artifact_id": 42,
        "strategy_name": "regime_router_v1",
        "strategy_version": "1.2.3",
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "cash": 950.25,
        "equity": 1001.75,
        "realized_pnl": 12.5,
        "open_position_count": 2,
        "last_processed_candle_ts": datetime(2026, 4, 18, 4, 29),
        "last_trade_ts": datetime(2026, 4, 18, 4, 30, tzinfo=timezone.utc),
        "trading_halted": False,
        "force_halt": False,
        "paper_evidence": {
            "stage": "gathering-evidence",
            "trade_count": 4,
            "trade_target": 20,
            "runtime_days": 1.0,
            "runtime_target_days": 3.0,
            "blocker_count": 2,
        },
    }

    fields = _status_fields(snapshot)

    assert fields["artifact"] == "42"
    assert fields["strategy"] == "regime_router_v1@1.2.3"
    assert fields["symbols"] == "BTCUSDT,ETHUSDT"
    assert fields["cash"] == "950.25"
    assert fields["equity"] == "1001.75"
    assert fields["realized"] == "+12.50"
    assert fields["open_positions"] == "2"
    assert fields["last_candle"] == "2026-04-18 04:29:00 UTC"
    assert fields["last_trade"] == "2026-04-18 04:30:00 UTC"
    assert fields["halted"] == "false"
    assert fields["force_halt"] == "false"


def test_status_fields_use_ascii_placeholders_when_values_missing():
    fields = _status_fields({})

    assert fields["strategy"] == "-@-"
    assert fields["artifact"] == "-"
    assert fields["symbols"] == "-"
    assert fields["last_candle"] == "-"
    assert fields["last_trade"] == "-"


def test_log_runner_snapshot_emits_single_operator_line():
    snapshot = {
        "run_mode": "paper",
        "artifact_id": 42,
        "strategy_name": "regime_router_v1",
        "strategy_version": "1.2.3",
        "symbols": ["BTCUSDT"],
        "cash": 1000.0,
        "equity": 1000.0,
        "realized_pnl": 0.0,
        "open_position_count": 0,
        "last_processed_candle_ts": None,
        "last_trade_ts": None,
        "trading_halted": False,
        "force_halt": False,
        "paper_evidence": {
            "stage": "waiting-for-first-close",
            "trade_count": 0,
            "trade_target": 20,
            "runtime_days": 0.0,
            "runtime_target_days": 3.0,
            "blocker_count": 1,
        },
    }

    with patch("run_live.log.info") as mock_info:
        log_runner_snapshot("Runner startup", snapshot, llm_enabled=True, live_trade_enabled=False)

    assert mock_info.call_count == 1
    fmt = mock_info.call_args.args[0]
    args = mock_info.call_args.args[1:]
    assert "mode=%s artifact=%s strategy=%s symbols=%s" in fmt
    assert args[-1] == (
        " | llm_enabled=true live_trade_enabled=false "
        "paper_evidence=waiting-for-first-close paper_trades=0/20 paper_runtime=0.0/3.0d paper_blockers=1"
    )
    assert args[0] == "Runner startup"
    assert args[1] == "paper"
    assert args[2] == "42"
    assert args[3] == "regime_router_v1@1.2.3"


def test_format_freshness_maintenance_summary_only_reports_refreshed_symbols():
    summary = _format_freshness_maintenance_summary(
        {
            "BTCUSDT": {"status": "fresh", "rows_inserted": 0},
            "ETHUSDT": {"status": "synced", "rows_inserted": 12},
            "BNBUSDT": {"status": "synced", "rows_inserted": 3},
        }
    )

    assert summary == "refreshed=ETHUSDT(+12 rows),BNBUSDT(+3 rows)"


def test_format_freshness_maintenance_summary_returns_none_when_nothing_refreshed():
    assert _format_freshness_maintenance_summary({"BTCUSDT": {"status": "fresh", "rows_inserted": 0}}) is None


def test_build_arg_parser_help_describes_runtime_worker():
    parser = build_arg_parser()

    assert "runtime worker" in parser.format_help()


def test_main_help_exits_before_validate_or_boot():
    with patch("run_live.validate_env") as mock_validate:
        with patch("run_live.asyncio.run") as mock_asyncio_run:
            with pytest.raises(SystemExit) as exc:
                main(["--help"])

    assert exc.value.code == 0
    mock_validate.assert_not_called()
    mock_asyncio_run.assert_not_called()
