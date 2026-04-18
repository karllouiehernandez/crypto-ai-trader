# crypto_ai_trader/utils/telegram_utils.py  (CALLBACK QUEUE + POLLER)
"""Telegram helper used by the whole stack.

Exports
~~~~~~~
* `send_telegram_alert(token, chat_id, msg, reply_markup=None)` – low‑level sender.
* `alert(msg)` – convenience wrapper using global config.
* `alert_buy / alert_sell / alert_cutloss` – send buttons with callback data.
* `CALLBACK_QUEUE` – an `asyncio.Queue[(str, str)]` getting tuples like
  `(action, symbol)` when a user presses a button.
* `start_callback_poll()` – coroutine that polls the Bot API and pushes
  button presses onto the queue; run it as a background task.
"""
from __future__ import annotations

import asyncio, logging, time
from datetime import datetime
from typing import Optional, Sequence, Tuple

import requests

import config  # type: ignore – runtime module

def _token() -> str:
    return getattr(config, "TELEGRAM_TOKEN", "")

def _chat_id() -> str:
    return getattr(config, "TELEGRAM_CHAT_ID", "")

def _alerts_enabled() -> bool:
    return getattr(config, "ENABLE_TG_ALERTS", False)

def _api_url() -> str:
    """Build API base URL lazily so token is always read after .env is loaded."""
    return f"https://api.telegram.org/bot{_token()}"
CALLBACK_QUEUE: asyncio.Queue[Tuple[str, str]] = asyncio.Queue()

# ---------------------------------------------------------------------------
# send helpers
# ---------------------------------------------------------------------------

def send_telegram_alert(token: str, chat_id: str, message: str,
                        reply_markup: Optional[dict] = None):
    """Low-level sender with retry on 429 / transient errors (3 attempts)."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: dict = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 429:
                time.sleep(2)
                continue
            if r.status_code != 200:
                logging.error(f"Telegram HTTP {r.status_code}: {r.text}")
            return
        except requests.RequestException as e:
            if attempt == 2:
                logging.error(f"Telegram send failed after 3 attempts: {e}")


def alert(message: str):
    if _alerts_enabled() and _token() and _chat_id():
        send_telegram_alert(_token(), _chat_id(), message)

# ---------------------------------------------------------------------------
# BUY / SELL / CUT‑LOSS convenience wrappers
# ---------------------------------------------------------------------------

def _button(text: str, data: str):
    return {"text": text, "callback_data": data}


def alert_buy(symbol: str, price: float):
    if not _alerts_enabled():
        return
    msg = f"📈 *AI Suggestion: BUY*\nSymbol: `{symbol}`\nPrice: *{price:.4f}*"
    reply = {"inline_keyboard": [[_button("✅ Execute Buy", f"BUY:{symbol}")]]}
    send_telegram_alert(_token(), _chat_id(), msg, reply)


def alert_sell(symbol: str, price: float):
    if not _alerts_enabled():
        return
    msg = f"📉 *AI Suggestion: SELL*\nSymbol: `{symbol}`\nPrice: *{price:.4f}*"
    reply = {"inline_keyboard": [[_button("✅ Execute Sell", f"SELL:{symbol}")]]}
    send_telegram_alert(_token(), _chat_id(), msg, reply)


def alert_cutloss(symbol: str, price: float, pnl: float):
    if not _alerts_enabled():
        return
    msg = (
        f"⚠️ *Cut-loss alert*\nSymbol: `{symbol}`\nPrice: *{price:.4f}*\n"
        f"PnL: *{pnl:.2f}%*"
    )
    reply = {"inline_keyboard": [[_button("✅ Sell Now", f"SELL:{symbol}")]]}
    send_telegram_alert(_token(), _chat_id(), msg, reply)

# ---------------------------------------------------------------------------
# Callback poller
# ---------------------------------------------------------------------------

offset = 0  # last update_id processed

async def start_callback_poll(poll_interval: float = 2.0):
    global offset
    logging.info("Telegram callback poller started")
    loop = asyncio.get_event_loop()

    while True:
        try:
            resp = requests.get(
                f"{_api_url()}/getUpdates",
                params={"timeout": 0, "offset": offset + 1},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            for upd in data.get("result", []):
                offset = upd["update_id"]

                # ── button callback ──────────────────────────────────────────
                cq = upd.get("callback_query")
                if cq and "data" in cq:
                    data_str = cq["data"]  # e.g. "BUY:ETHUSDT"
                    try:
                        action, symbol = data_str.split(":")
                    except ValueError:
                        continue
                    logging.info(f"[TELEGRAM] button {action} {symbol}")
                    await CALLBACK_QUEUE.put((action, symbol))
                    requests.post(
                        f"{_api_url()}/answerCallbackQuery",
                        json={"callback_query_id": cq["id"], "text": "👌 Received"},
                    )
                    continue

                # ── text command ─────────────────────────────────────────────
                msg = upd.get("message", {})
                text = msg.get("text", "")
                if not text.startswith("/"):
                    continue

                from utils.telegram_commands import parse_command, format_command_response
                command, args = parse_command(text)
                logging.info(f"[TELEGRAM] command /{command} args={args}")

                # control commands route through CALLBACK_QUEUE so PaperTrader
                # processes them safely inside its own async loop
                if command == "halt":
                    await CALLBACK_QUEUE.put(("HALT", ""))
                    send_telegram_alert(_token(), _chat_id(), "🛑 Halt request queued.")
                    continue
                if command == "resume":
                    await CALLBACK_QUEUE.put(("RESUME", ""))
                    send_telegram_alert(_token(), _chat_id(), "▶️ Resume request queued.")
                    continue
                if command == "buy" and args:
                    await CALLBACK_QUEUE.put(("BUY", args[0].upper()))
                    send_telegram_alert(_token(), _chat_id(), f"🛒 Buy queued for {args[0].upper()}.")
                    continue
                if command == "sell" and args:
                    await CALLBACK_QUEUE.put(("SELL", args[0].upper()))
                    send_telegram_alert(_token(), _chat_id(), f"💰 Sell queued for {args[0].upper()}.")
                    continue

                # slow command: backtest — acknowledge first, run in executor
                if command == "backtest":
                    if len(args) < 3:
                        send_telegram_alert(
                            _token(), _chat_id(),
                            "Usage: /backtest SYMBOL YYYY-MM-DD YYYY-MM-DD [STRATEGY]",
                        )
                        continue
                    symbol, start, end = args[0], args[1], args[2]
                    strat = args[3] if len(args) > 3 else None
                    send_telegram_alert(
                        _token(), _chat_id(),
                        f"⏳ Running backtest {symbol} {start}→{end}...",
                    )
                    from utils.telegram_commands import handle_backtest
                    result_str = await loop.run_in_executor(
                        None, handle_backtest, symbol, start, end, strat
                    )
                    send_telegram_alert(_token(), _chat_id(), result_str)
                    continue

                # all other commands: run synchronously (fast)
                response = await loop.run_in_executor(
                    None, format_command_response, command, args
                )
                send_telegram_alert(_token(), _chat_id(), response)

        except Exception as e:
            logging.error(f"Telegram poll error: {e}")
        await asyncio.sleep(poll_interval)
