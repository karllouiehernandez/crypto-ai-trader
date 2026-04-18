"""Responsive TradingView-like candlestick renderer for Streamlit."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_ASSET_PATH = Path(__file__).resolve().parent / "assets" / "lightweight-charts.standalone.production.js"


@lru_cache(maxsize=1)
def _load_lightweight_chart_js() -> str:
    """Read the vendored chart library once per process."""
    return _ASSET_PATH.read_text(encoding="utf-8").replace("</script>", "<\\/script>")


def build_chart_html(payload: dict[str, Any], *, chart_id: str, height: int) -> str:
    """Return a self-contained HTML document for the responsive chart."""
    library_js = _load_lightweight_chart_js()
    safe_chart_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", chart_id).strip("-") or "chart"
    safe_payload = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      html, body {{
        margin: 0;
        padding: 0;
        background: #0e1117;
        color: #d1d4dc;
        font-family: "Trebuchet MS", "Segoe UI", sans-serif;
      }}
      .tv-shell {{
        height: {height}px;
        min-height: {height}px;
        display: flex;
        flex-direction: column;
        border: 1px solid #1e222d;
        border-radius: 12px;
        overflow: hidden;
        background:
          radial-gradient(circle at top right, rgba(41, 98, 255, 0.14), transparent 30%),
          linear-gradient(180deg, #11161f 0%, #0e1117 100%);
      }}
      .tv-legend {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px 12px;
        padding: 10px 14px 8px;
        border-bottom: 1px solid rgba(54, 58, 69, 0.85);
        font-size: 12px;
        line-height: 1.4;
      }}
      .tv-legend strong {{
        color: #ffffff;
        font-size: 12px;
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }}
      .tv-chart-wrap {{
        position: relative;
        flex: 1;
        min-height: 0;
      }}
      .tv-chart {{
        position: absolute;
        inset: 0;
      }}
      .tv-empty {{
        position: absolute;
        inset: 0;
        display: none;
        align-items: center;
        justify-content: center;
        text-align: center;
        color: #9aa4b2;
        font-size: 14px;
        padding: 24px;
      }}
      .tv-footnote {{
        padding: 6px 14px 10px;
        font-size: 11px;
        color: #7f8a98;
        border-top: 1px solid rgba(54, 58, 69, 0.65);
      }}
      .tv-footnote a {{
        color: #8ab4ff;
        text-decoration: none;
      }}
      .tv-footnote a:hover {{
        text-decoration: underline;
      }}
      @media (max-width: 640px) {{
        .tv-shell {{
          border-radius: 10px;
        }}
        .tv-legend {{
          font-size: 11px;
          gap: 6px 10px;
          padding: 8px 10px 6px;
        }}
        .tv-footnote {{
          padding: 6px 10px 8px;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="tv-shell">
      <div class="tv-legend" id="{safe_chart_id}-legend"></div>
      <div class="tv-chart-wrap">
        <div id="{safe_chart_id}" class="tv-chart"></div>
        <div id="{safe_chart_id}-empty" class="tv-empty"></div>
      </div>
      <div class="tv-footnote">
        Charts powered by
        <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">TradingView Lightweight Charts&#8482;</a>
      </div>
    </div>
    <script>{library_js}</script>
    <script>
      const payload = {safe_payload};
      const container = document.getElementById("{safe_chart_id}");
      const emptyState = document.getElementById("{safe_chart_id}-empty");
      const legend = document.getElementById("{safe_chart_id}-legend");

      function formatNumber(value) {{
        if (value === undefined || value === null || Number.isNaN(Number(value))) {{
          return "—";
        }}
        return Number(value).toLocaleString(undefined, {{
          minimumFractionDigits: 2,
          maximumFractionDigits: 6,
        }});
      }}

      function setLegend(title, candle) {{
        const meta = payload.meta || {{}};
        const parts = [
          `<strong>${{title || meta.symbol || "Chart"}}</strong>`,
        ];
        if (meta.context_label) {{
          parts.push(`<span>${{meta.context_label}}</span>`);
        }}
        if (meta.strategy_name) {{
          parts.push(`<span>Strategy: ${{meta.strategy_name}}</span>`);
        }}
        if (meta.timeframe) {{
          parts.push(`<span>TF: ${{meta.timeframe}}</span>`);
        }}
        if (candle) {{
          parts.push(`<span>O ${{formatNumber(candle.open)}}</span>`);
          parts.push(`<span>H ${{formatNumber(candle.high)}}</span>`);
          parts.push(`<span>L ${{formatNumber(candle.low)}}</span>`);
          parts.push(`<span>C ${{formatNumber(candle.close)}}</span>`);
        }}
        legend.innerHTML = parts.join("");
      }}

      if (!payload.candles || payload.candles.length === 0) {{
        emptyState.style.display = "flex";
        emptyState.textContent = "No candle data available for this window.";
        setLegend(payload.meta && payload.meta.symbol ? payload.meta.symbol : "Chart", null);
      }} else {{
        const chart = LightweightCharts.createChart(container, {{
          autoSize: true,
          layout: {{
            background: {{ type: "solid", color: "#0e1117" }},
            textColor: "#d1d4dc",
            fontFamily: '"Trebuchet MS", "Segoe UI", sans-serif',
          }},
          grid: {{
            vertLines: {{ color: "#1e222d" }},
            horzLines: {{ color: "#1e222d" }},
          }},
          rightPriceScale: {{
            borderColor: "#363a45",
            scaleMargins: {{ top: 0.08, bottom: 0.22 }},
          }},
          timeScale: {{
            borderColor: "#363a45",
            timeVisible: true,
            secondsVisible: false,
            rightOffset: 8,
            barSpacing: 10,
            minBarSpacing: 0.5,
            fixLeftEdge: false,
            lockVisibleTimeRangeOnResize: false,
          }},
          crosshair: {{
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {{
              color: "rgba(209, 212, 220, 0.35)",
              labelBackgroundColor: "#131722",
            }},
            horzLine: {{
              color: "rgba(209, 212, 220, 0.35)",
              labelBackgroundColor: "#131722",
            }},
          }},
          handleScroll: {{
            mouseWheel: true,
            pressedMouseMove: true,
            horzTouchDrag: true,
            vertTouchDrag: false,
          }},
          handleScale: {{
            axisPressedMouseMove: true,
            mouseWheel: true,
            pinch: true,
          }},
        }});

        if (!chart.options().autoSize) {{
          const resizeChart = () => {{
            const rect = container.getBoundingClientRect();
            chart.resize(Math.max(Math.floor(rect.width), 320), Math.max(Math.floor(rect.height), 240));
          }};
          resizeChart();
          window.addEventListener("resize", resizeChart);
        }}

        const candleSeries = chart.addCandlestickSeries({{
          upColor: "#26a69a",
          downColor: "#ef5350",
          borderVisible: false,
          wickUpColor: "#26a69a",
          wickDownColor: "#ef5350",
          priceLineVisible: false,
          lastValueVisible: true,
        }});
        candleSeries.setData(payload.candles);

        const volumeSeries = chart.addHistogramSeries({{
          priceScaleId: "",
          priceFormat: {{ type: "volume" }},
          base: 0,
          lastValueVisible: false,
          priceLineVisible: false,
        }});
        volumeSeries.priceScale().applyOptions({{
          scaleMargins: {{ top: 0.78, bottom: 0.0 }},
        }});
        volumeSeries.setData(payload.volume || []);

        if (payload.markers && payload.markers.length > 0) {{
          candleSeries.setMarkers(payload.markers);
        }}

        chart.timeScale().fitContent();
        setLegend(payload.meta && payload.meta.symbol ? payload.meta.symbol : "Chart", payload.candles[payload.candles.length - 1]);

        chart.subscribeCrosshairMove((param) => {{
          if (!param || !param.time) {{
            setLegend(payload.meta && payload.meta.symbol ? payload.meta.symbol : "Chart", payload.candles[payload.candles.length - 1]);
            return;
          }}
          const candle = param.seriesData.get(candleSeries);
          setLegend(payload.meta && payload.meta.symbol ? payload.meta.symbol : "Chart", candle || payload.candles[payload.candles.length - 1]);
        }});
      }}
    </script>
  </body>
</html>
"""


def render_responsive_chart(payload: dict[str, Any], *, chart_id: str, height: int = 520) -> None:
    """Render a local responsive candlestick chart inside the Streamlit layout."""
    components.html(build_chart_html(payload, chart_id=chart_id, height=height), height=height, scrolling=False)
