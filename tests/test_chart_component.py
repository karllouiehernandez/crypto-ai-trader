"""Tests for the responsive Streamlit chart wrapper."""

from __future__ import annotations

from dashboard.chart_component import build_chart_html


def test_build_chart_html_includes_chart_shell_and_payload():
    payload = {
        "candles": [{"time": 1713398400, "open": 100.0, "high": 102.0, "low": 99.5, "close": 101.0}],
        "volume": [{"time": 1713398400, "value": 12.0, "color": "#26a69a"}],
        "markers": [{"time": 1713398400, "position": "belowBar", "shape": "arrowUp", "color": "#00e676", "text": "BUY"}],
        "meta": {"symbol": "BTCUSDT", "timeframe": "1h", "strategy_name": "mean_reversion_v1", "context_label": "paper"},
    }

    html = build_chart_html(payload, chart_id="runtime-btc-1h", height=480)

    assert "runtime-btc-1h" in html
    assert "LightweightCharts.createChart" in html
    assert "BTCUSDT" in html
    assert "mean_reversion_v1" in html
    assert "TradingView Lightweight Charts" in html
