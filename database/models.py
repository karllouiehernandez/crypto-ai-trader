# crypto_ai_trader/database/models.py
from sqlalchemy import (
    Column, Integer, Float, String, DateTime, Index, create_engine
)
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import inspect, text
from datetime import datetime, timezone
from pathlib import Path

from config import DB_PATH

Base = declarative_base()

class Candle(Base):
    __tablename__ = "candles"
    id        = Column(Integer, primary_key=True, autoincrement=True)
    symbol    = Column(String(32), nullable=False, index=True)
    open_time = Column(DateTime(timezone=True), nullable=False)
    open      = Column(Float, nullable=False)
    high      = Column(Float, nullable=False)
    low       = Column(Float, nullable=False)
    close     = Column(Float, nullable=False)
    volume    = Column(Float, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("symbol", "open_time", name="uix_symbol_time"),
        Index("idx_symbol_time", "symbol", "open_time"),
    )

class Trade(Base):
    __tablename__ = "trades"
    id     = Column(Integer, primary_key=True, autoincrement=True)
    ts     = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc))
    symbol = Column(String(32), nullable=False)
    side   = Column(String(4), nullable=False)     # BUY / SELL
    qty    = Column(Float, nullable=False)
    price  = Column(Float, nullable=False)
    fee    = Column(Float, nullable=False)
    pnl    = Column(Float, nullable=False)
    strategy_name = Column(String(128), nullable=True)
    strategy_version = Column(String(32), nullable=True)
    run_mode = Column(String(16), nullable=True)
    regime = Column(String(32), nullable=True)

class Portfolio(Base):
    __tablename__ = "portfolio"
    id         = Column(Integer, primary_key=True, default=1)
    ts         = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc))
    balance    = Column(Float, nullable=False)
    equity     = Column(Float, nullable=False)
    unreal_pnl = Column(Float, nullable=False)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    ts         = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc))
    run_mode   = Column(String(16), nullable=False)
    strategy_name = Column(String(128), nullable=False)
    strategy_version = Column(String(32), nullable=True)
    balance    = Column(Float, nullable=False)
    equity     = Column(Float, nullable=False)
    unreal_pnl = Column(Float, nullable=False)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key   = Column(String(128), primary_key=True)
    value = Column(String, nullable=False)

class Promotion(Base):
    __tablename__ = "promotions"
    id                   = Column(Integer, primary_key=True, autoincrement=True)
    ts                   = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc))
    eval_number          = Column(Integer, nullable=False)
    consecutive_promotes = Column(Integer, nullable=False)
    sharpe               = Column(Float, nullable=False)
    max_dd               = Column(Float, nullable=False)
    profit_factor        = Column(Float, nullable=False)
    confidence_score     = Column(Float, nullable=False)
    recommendation       = Column(String(64), nullable=False)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    created_at       = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc))
    symbol           = Column(String(32), nullable=False)
    start_ts         = Column(DateTime(timezone=True), nullable=False)
    end_ts           = Column(DateTime(timezone=True), nullable=False)
    strategy_name    = Column(String(128), nullable=False)
    strategy_version = Column(String(32), nullable=True)
    preset_name      = Column(String(128), nullable=True)
    params_json      = Column(String, nullable=False, default="{}")
    metrics_json     = Column(String, nullable=False, default="{}")
    status           = Column(String(32), nullable=False, default="completed")


class BacktestPreset(Base):
    __tablename__ = "backtest_presets"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc))
    updated_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc))
    strategy_name = Column(String(128), nullable=False, index=True)
    preset_name   = Column(String(128), nullable=False)
    params_json   = Column(String, nullable=False, default="{}")

    __table_args__ = (
        sa.UniqueConstraint("strategy_name", "preset_name", name="uix_backtest_preset_strategy_name"),
    )


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    run_id        = Column(Integer, nullable=False, index=True)
    ts            = Column(DateTime(timezone=True), nullable=False)
    symbol        = Column(String(32), nullable=False)
    side          = Column(String(4), nullable=False)
    qty           = Column(Float, nullable=False)
    price         = Column(Float, nullable=False)
    regime        = Column(String(32), nullable=True)
    strategy_name = Column(String(128), nullable=False)
    strategy_version = Column(String(32), nullable=True)

# ────────────────────────── helpers ──────────────────────────────────────────
def get_engine(echo: bool = False):
    Path(DB_PATH).parent.mkdir(exist_ok=True)
    return create_engine(f"sqlite:///{DB_PATH}", echo=echo, future=True)

Engine       = get_engine()
SessionLocal = sessionmaker(bind=Engine, expire_on_commit=False)

def init_db():
    Base.metadata.create_all(bind=Engine)
    _ensure_runtime_schema(bind=Engine)


def _ensure_runtime_schema(bind) -> None:
    """Add newer nullable columns to legacy tables without dropping user data."""
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "trades" in existing_tables:
        existing_columns = {col["name"] for col in inspector.get_columns("trades")}
        migrations = {
            "strategy_name": "ALTER TABLE trades ADD COLUMN strategy_name VARCHAR(128)",
            "strategy_version": "ALTER TABLE trades ADD COLUMN strategy_version VARCHAR(32)",
            "run_mode": "ALTER TABLE trades ADD COLUMN run_mode VARCHAR(16)",
            "regime": "ALTER TABLE trades ADD COLUMN regime VARCHAR(32)",
        }
        with bind.begin() as conn:
            for column, ddl in migrations.items():
                if column not in existing_columns:
                    conn.execute(text(ddl))

    if "backtest_runs" in existing_tables:
        existing_columns = {col["name"] for col in inspector.get_columns("backtest_runs")}
        migrations = {
            "preset_name": "ALTER TABLE backtest_runs ADD COLUMN preset_name VARCHAR(128)",
        }
        with bind.begin() as conn:
            for column, ddl in migrations.items():
                if column not in existing_columns:
                    conn.execute(text(ddl))

def upsert_portfolio(session, balance: float, equity: float, unreal_pnl: float):
    stmt = sqlite_upsert(Portfolio).values(
        id=1,
        ts=datetime.now(tz=timezone.utc),
        balance=balance,
        equity=equity,
        unreal_pnl=unreal_pnl,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_=dict(ts=stmt.excluded.ts,
                  balance=stmt.excluded.balance,
                  equity=stmt.excluded.equity,
                  unreal_pnl=stmt.excluded.unreal_pnl)
    )
    session.execute(stmt)


def snapshot_portfolio(
    session,
    run_mode: str,
    strategy_name: str,
    strategy_version: str | None,
    balance: float,
    equity: float,
    unreal_pnl: float,
):
    session.add(
        PortfolioSnapshot(
            ts=datetime.now(tz=timezone.utc),
            run_mode=run_mode,
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            balance=balance,
            equity=equity,
            unreal_pnl=unreal_pnl,
        )
    )


def set_app_setting(session, key: str, value: str) -> None:
    stmt = sqlite_upsert(AppSetting).values(key=key, value=value)
    stmt = stmt.on_conflict_do_update(
        index_elements=["key"],
        set_=dict(value=stmt.excluded.value),
    )
    session.execute(stmt)


def get_app_setting(session, key: str, default: str | None = None) -> str | None:
    row = session.get(AppSetting, key)
    return row.value if row is not None else default
