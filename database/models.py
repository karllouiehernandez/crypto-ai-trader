# crypto_ai_trader/database/models.py
from sqlalchemy import (
    Column, Integer, Float, String, DateTime, Index, create_engine
)
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from sqlalchemy.orm import declarative_base, sessionmaker
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

class Portfolio(Base):
    __tablename__ = "portfolio"
    id         = Column(Integer, primary_key=True, default=1)
    ts         = Column(DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc))
    balance    = Column(Float, nullable=False)
    equity     = Column(Float, nullable=False)
    unreal_pnl = Column(Float, nullable=False)

# ────────────────────────── helpers ──────────────────────────────────────────
def get_engine(echo: bool = False):
    Path(DB_PATH).parent.mkdir(exist_ok=True)
    return create_engine(f"sqlite:///{DB_PATH}", echo=echo, future=True)

Engine       = get_engine()
SessionLocal = sessionmaker(bind=Engine, expire_on_commit=False)

def init_db():
    Base.metadata.create_all(bind=Engine)

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
