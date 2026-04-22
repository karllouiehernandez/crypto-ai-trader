# crypto_ai_trader/database/models.py
from sqlalchemy import (
    Column, Integer, Float, String, DateTime, Index, create_engine, event
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
    artifact_id = Column(Integer, nullable=True, index=True)
    strategy_name = Column(String(128), nullable=True)
    strategy_version = Column(String(32), nullable=True)
    strategy_code_hash = Column(String(64), nullable=True)
    strategy_provenance = Column(String(32), nullable=True)
    run_mode = Column(String(16), nullable=True)
    regime = Column(String(32), nullable=True)
    integrity_status = Column(String(32), nullable=True)
    integrity_note = Column(String(256), nullable=True)

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
    artifact_id = Column(Integer, nullable=True, index=True)
    strategy_name = Column(String(128), nullable=False)
    strategy_version = Column(String(32), nullable=True)
    strategy_code_hash = Column(String(64), nullable=True)
    strategy_provenance = Column(String(32), nullable=True)
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
    artifact_id          = Column(Integer, nullable=True, index=True)
    strategy_name        = Column(String(128), nullable=True)
    strategy_version     = Column(String(32), nullable=True)
    strategy_code_hash   = Column(String(64), nullable=True)
    strategy_provenance  = Column(String(32), nullable=True)
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
    artifact_id      = Column(Integer, nullable=True, index=True)
    strategy_name    = Column(String(128), nullable=False)
    strategy_version = Column(String(32), nullable=True)
    strategy_code_hash = Column(String(64), nullable=True)
    strategy_provenance = Column(String(32), nullable=True)
    preset_name      = Column(String(128), nullable=True)
    params_json      = Column(String, nullable=False, default="{}")
    metrics_json     = Column(String, nullable=False, default="{}")
    status           = Column(String(32), nullable=False, default="completed")
    integrity_status = Column(String(32), nullable=True)
    integrity_note   = Column(String(256), nullable=True)


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
    artifact_id   = Column(Integer, nullable=True, index=True)
    regime        = Column(String(32), nullable=True)
    strategy_name = Column(String(128), nullable=False)
    strategy_version = Column(String(32), nullable=True)
    strategy_code_hash = Column(String(64), nullable=True)
    strategy_provenance = Column(String(32), nullable=True)


class StrategyArtifact(Base):
    __tablename__ = "strategy_artifacts"
    id                     = Column(Integer, primary_key=True, autoincrement=True)
    created_at             = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc))
    name                   = Column(String(128), nullable=False, index=True)
    version                = Column(String(32), nullable=False)
    path                   = Column(String(512), nullable=False)
    provenance             = Column(String(32), nullable=False)
    code_hash              = Column(String(64), nullable=False)
    status                 = Column(String(32), nullable=False, default="draft")
    reviewed_from_artifact_id = Column(Integer, nullable=True, index=True)

    __table_args__ = (
        sa.UniqueConstraint("name", "version", "code_hash", name="uix_strategy_artifact_identity"),
    )

class WeeklyFocusStudy(Base):
    __tablename__ = "weekly_focus_studies"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc))
    strategy_name = Column(String(128), nullable=False)
    params_json   = Column(String, nullable=False, default="{}")
    universe_size = Column(Integer, nullable=False)
    top_n         = Column(Integer, nullable=False)
    backtest_days = Column(Integer, nullable=False)
    status        = Column(String(32), nullable=False, default="completed")


class WeeklyFocusCandidate(Base):
    __tablename__ = "weekly_focus_candidates"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    study_id      = Column(Integer, nullable=False, index=True)
    symbol        = Column(String(32), nullable=False)
    rank          = Column(Integer, nullable=False)
    volume_rank   = Column(Integer, nullable=False)
    sharpe        = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    max_drawdown  = Column(Float, nullable=True)
    n_trades      = Column(Integer, nullable=True)
    score         = Column(Float, nullable=True)
    status        = Column(String(32), nullable=False, default="completed")
    metrics_json  = Column(String, nullable=False, default="{}")


class SymbolLoadJob(Base):
    """Tracks background 30-day history load jobs for new symbols."""
    __tablename__ = "symbol_load_jobs"
    symbol       = Column(String(32), primary_key=True)
    status       = Column(String(16), nullable=False, default="queued")  # queued|loading|ready|failed
    queued_at    = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    started_at   = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_msg    = Column(String(512), nullable=True)


class TradingDiaryEntry(Base):
    """Auto-generated and operator-annotated journal entries for paper/live trades and backtests."""
    __tablename__ = "trading_diary_entries"
    id                  = Column(Integer, primary_key=True, autoincrement=True)
    created_at          = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc))
    entry_type          = Column(String(32), nullable=False)   # trade | backtest_insight | manual | session_summary
    run_mode            = Column(String(16), nullable=True)    # paper | live | None for backtest entries
    symbol              = Column(String(32), nullable=True, index=True)
    strategy_name       = Column(String(128), nullable=True, index=True)
    trade_id            = Column(Integer, nullable=True)        # soft FK → trades.id
    backtest_run_id     = Column(Integer, nullable=True)        # soft FK → backtest_runs.id
    content             = Column(sa.Text, nullable=False)
    tags                = Column(String, nullable=True)         # JSON array string
    pnl                 = Column(Float, nullable=True)
    outcome_rating      = Column(Integer, nullable=True)        # 1–5, operator-supplied
    learnings           = Column(sa.Text, nullable=True)
    strategy_suggestion = Column(sa.Text, nullable=True)


# ────────────────────────── helpers ──────────────────────────────────────────
def get_engine(echo: bool = False):
    Path(DB_PATH).parent.mkdir(exist_ok=True)
    engine = create_engine(
        f"sqlite:///{DB_PATH}",
        echo=echo,
        future=True,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,
        },
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite_connection(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    return engine

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
            "artifact_id": "ALTER TABLE trades ADD COLUMN artifact_id INTEGER",
            "strategy_name": "ALTER TABLE trades ADD COLUMN strategy_name VARCHAR(128)",
            "strategy_version": "ALTER TABLE trades ADD COLUMN strategy_version VARCHAR(32)",
            "strategy_code_hash": "ALTER TABLE trades ADD COLUMN strategy_code_hash VARCHAR(64)",
            "strategy_provenance": "ALTER TABLE trades ADD COLUMN strategy_provenance VARCHAR(32)",
            "run_mode": "ALTER TABLE trades ADD COLUMN run_mode VARCHAR(16)",
            "regime": "ALTER TABLE trades ADD COLUMN regime VARCHAR(32)",
            "integrity_status": "ALTER TABLE trades ADD COLUMN integrity_status VARCHAR(32)",
            "integrity_note": "ALTER TABLE trades ADD COLUMN integrity_note VARCHAR(256)",
        }
        with bind.begin() as conn:
            for column, ddl in migrations.items():
                if column not in existing_columns:
                    conn.execute(text(ddl))

    if "portfolio_snapshots" in existing_tables:
        existing_columns = {col["name"] for col in inspector.get_columns("portfolio_snapshots")}
        migrations = {
            "artifact_id": "ALTER TABLE portfolio_snapshots ADD COLUMN artifact_id INTEGER",
            "strategy_code_hash": "ALTER TABLE portfolio_snapshots ADD COLUMN strategy_code_hash VARCHAR(64)",
            "strategy_provenance": "ALTER TABLE portfolio_snapshots ADD COLUMN strategy_provenance VARCHAR(32)",
        }
        with bind.begin() as conn:
            for column, ddl in migrations.items():
                if column not in existing_columns:
                    conn.execute(text(ddl))

    if "backtest_runs" in existing_tables:
        existing_columns = {col["name"] for col in inspector.get_columns("backtest_runs")}
        migrations = {
            "artifact_id": "ALTER TABLE backtest_runs ADD COLUMN artifact_id INTEGER",
            "preset_name": "ALTER TABLE backtest_runs ADD COLUMN preset_name VARCHAR(128)",
            "strategy_code_hash": "ALTER TABLE backtest_runs ADD COLUMN strategy_code_hash VARCHAR(64)",
            "strategy_provenance": "ALTER TABLE backtest_runs ADD COLUMN strategy_provenance VARCHAR(32)",
            "integrity_status": "ALTER TABLE backtest_runs ADD COLUMN integrity_status VARCHAR(32)",
            "integrity_note": "ALTER TABLE backtest_runs ADD COLUMN integrity_note VARCHAR(256)",
        }
        with bind.begin() as conn:
            for column, ddl in migrations.items():
                if column not in existing_columns:
                    conn.execute(text(ddl))

    if "backtest_trades" in existing_tables:
        existing_columns = {col["name"] for col in inspector.get_columns("backtest_trades")}
        migrations = {
            "artifact_id": "ALTER TABLE backtest_trades ADD COLUMN artifact_id INTEGER",
            "strategy_code_hash": "ALTER TABLE backtest_trades ADD COLUMN strategy_code_hash VARCHAR(64)",
            "strategy_provenance": "ALTER TABLE backtest_trades ADD COLUMN strategy_provenance VARCHAR(32)",
        }
        with bind.begin() as conn:
            for column, ddl in migrations.items():
                if column not in existing_columns:
                    conn.execute(text(ddl))

    if "promotions" in existing_tables:
        existing_columns = {col["name"] for col in inspector.get_columns("promotions")}
        migrations = {
            "artifact_id": "ALTER TABLE promotions ADD COLUMN artifact_id INTEGER",
            "strategy_name": "ALTER TABLE promotions ADD COLUMN strategy_name VARCHAR(128)",
            "strategy_version": "ALTER TABLE promotions ADD COLUMN strategy_version VARCHAR(32)",
            "strategy_code_hash": "ALTER TABLE promotions ADD COLUMN strategy_code_hash VARCHAR(64)",
            "strategy_provenance": "ALTER TABLE promotions ADD COLUMN strategy_provenance VARCHAR(32)",
        }
        with bind.begin() as conn:
            for column, ddl in migrations.items():
                if column not in existing_columns:
                    conn.execute(text(ddl))

    if "trading_diary_entries" in existing_tables:
        existing_columns = {col["name"] for col in inspector.get_columns("trading_diary_entries")}
        migrations = {
            "outcome_rating":      "ALTER TABLE trading_diary_entries ADD COLUMN outcome_rating INTEGER",
            "learnings":           "ALTER TABLE trading_diary_entries ADD COLUMN learnings TEXT",
            "strategy_suggestion": "ALTER TABLE trading_diary_entries ADD COLUMN strategy_suggestion TEXT",
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
    artifact_id: int | None,
    strategy_name: str,
    strategy_version: str | None,
    strategy_code_hash: str | None,
    strategy_provenance: str | None,
    balance: float,
    equity: float,
    unreal_pnl: float,
):
    session.add(
        PortfolioSnapshot(
            ts=datetime.now(tz=timezone.utc),
            run_mode=run_mode,
            artifact_id=artifact_id,
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            strategy_code_hash=strategy_code_hash,
            strategy_provenance=strategy_provenance,
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
