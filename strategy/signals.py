"""strategy/signals.py — shared Signal enum to avoid circular imports."""
from enum import Enum


class Signal(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
