# crypto_ai_trader/run_backtest.py
"""
Usage:
    python -m crypto_ai_trader.run_backtest BTCUSDT 2024-01-01 2024-03-31
"""
import argparse
from datetime import datetime
import matplotlib.pyplot as plt

from config import validate_env
from backtester.engine import run_backtest

if __name__ == "__main__":
    validate_env()                # fail fast with clear error if .env is missing

    p = argparse.ArgumentParser()
    p.add_argument("symbol")
    p.add_argument("start")
    p.add_argument("end")
    args = p.parse_args()

    start = datetime.fromisoformat(args.start)
    end   = datetime.fromisoformat(args.end)

    df = run_backtest(args.symbol.upper(), start, end)
    print(df.to_string(index=False))

    # Equity curve: track running cash balance across trades
    balance = 10_000.0
    equity  = [balance]
    for t in df.itertuples():
        if t.side == "SELL":
            balance += t.qty * t.price  # realised proceeds
            equity.append(balance)

    plt.figure()
    plt.plot(equity)
    plt.title(f"{args.symbol} equity curve")
    plt.xlabel("Sell trade #")
    plt.ylabel("Balance ($)")
    plt.show()
