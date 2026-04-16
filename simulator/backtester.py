# crypto_ai_trader/simulator/backtester.py
from datetime import datetime
import pandas as pd
from tqdm import tqdm

from ..database.models import SessionLocal, Candle
from ..strategy.signal_engine import compute_signal, Signal
from ..config import SYMBOLS, STARTING_BALANCE_USD, FEE_RATE, POSITION_SIZE_PCT


def run_backtest(start: datetime, end: datetime):
    equity_curve = []
    timestamps   = []
    balance      = STARTING_BALANCE_USD
    positions    = {s: 0.0 for s in SYMBOLS}

    with SessionLocal() as sess:
        for ts in tqdm(pd.date_range(start, end, freq="1min")):
            # Fetch all symbols' candles for this timestamp in one pass
            candles_at_ts: dict[str, Candle] = {}
            for sym in SYMBOLS:
                candle = (
                    sess.query(Candle)
                        .filter(Candle.symbol == sym, Candle.open_time == ts)
                        .first()
                )
                if candle is not None:
                    candles_at_ts[sym] = candle

            if not candles_at_ts:
                continue  # no data at all for this minute — skip equity snapshot too

            # Trading logic — use the candles already fetched, no second query
            for sym, candle in candles_at_ts.items():
                sig   = compute_signal(sess, candle)
                price = candle.close

                if sig == Signal.BUY and balance > 0:
                    qty      = (balance * POSITION_SIZE_PCT) / price
                    balance -= price * qty * (1 + FEE_RATE)
                    positions[sym] += qty

                elif sig == Signal.SELL and positions[sym] > 0:
                    qty      = positions[sym]
                    balance += price * qty * (1 - FEE_RATE)
                    positions[sym] = 0.0

            # Equity snapshot — use close prices already in candles_at_ts
            equity = balance + sum(
                positions[s] * candles_at_ts[s].close
                for s in SYMBOLS
                if s in candles_at_ts
            )
            equity_curve.append(equity)
            timestamps.append(ts)

    return pd.Series(equity_curve, index=timestamps)
