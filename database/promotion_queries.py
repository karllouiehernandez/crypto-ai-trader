"""database/promotion_queries.py — Read-only DB queries for the dashboard promotion panel.

Kept free of Streamlit imports so tests can import this module directly.
"""
import sqlite3
from pathlib import Path

import pandas as pd


def query_promotions(db_path: str | Path) -> pd.DataFrame:
    """Return all promotion records newest-first.

    Returns an empty DataFrame on error or when the table does not exist yet
    (normal state before the first promotion fires).
    """
    try:
        con = sqlite3.connect(str(db_path))
        try:
            df = pd.read_sql(
                "SELECT ts, eval_number, consecutive_promotes, sharpe, max_dd, "
                "profit_factor, confidence_score FROM promotions ORDER BY ts DESC",
                con,
                parse_dates=["ts"],
            )
        finally:
            con.close()
        return df
    except Exception:
        return pd.DataFrame()
