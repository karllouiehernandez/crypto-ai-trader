"""Tests for the responsive Streamlit chart wrapper."""

from __future__ import annotations

from dashboard.chart_component import build_chart_html


def test_build_chart_html_includes_chart_shell_and_payload():
    payload = {
        "candles": [{"time": 1713398400, "open": 100.0, "high": 102.0, "low": 99.5, "close": 101.0}],
        "volume": [{"time": 1713398400, "value": 12.0, "color": "#26a69a"}],
        "markers": [{"time": 1713398400, "position": "belowBar", "shape": "arrowUp", "color": "#00e676", "text": "BUY"}],
        "overlays": {
            "price": [{"label": "EMA 9", "color": "#ffb300", "lineWidth": 2, "lineStyle": "solid", "data": [{"time": 1713398400, "value": 100.5}]}],
            "rsi": {
                "series": [{"label": "RSI 14", "color": "#ffca28", "lineWidth": 2, "lineStyle": "solid", "data": [{"time": 1713398400, "value": 55.0}]}],
                "bands": [],
            },
            "macd": {
                "series": [{"label": "MACD", "color": "#29b6f6", "lineWidth": 2, "lineStyle": "solid", "data": [{"time": 1713398400, "value": 0.2}]}],
                "histogram": [{"time": 1713398400, "value": 0.1, "color": "#26a69a"}],
            },
        },
        "meta": {"symbol": "BTCUSDT", "timeframe": "1h", "strategy_name": "mean_reversion_v1", "context_label": "paper"},
    }

    html = build_chart_html(payload, chart_id="runtime-btc-1h", height=480)

    assert "runtime-btc-1h" in html
    assert "LightweightCharts.createChart" in html
    assert "BTCUSDT" in html
    assert "mean_reversion_v1" in html
    assert "TradingView Lightweight Charts" in html
    assert "RSI 14" in html
    assert "MACD" in html
    assert "EMA 9" in html
