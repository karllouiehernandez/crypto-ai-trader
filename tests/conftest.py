from __future__ import annotations

import tempfile
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

import config as cfg


_TEST_DB_DIR = Path(tempfile.gettempdir()) / "crypto_ai_trader_pytest"
_TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
TEST_DB_PATH = _TEST_DB_DIR / "market_data_test.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

cfg.DB_PATH = TEST_DB_PATH

import database.models as db_models  # noqa: E402


def _session_engine() -> sa.Engine:
    return sa.create_engine(f"sqlite:///{TEST_DB_PATH}", future=True)


_ENGINE = _session_engine()


def _session_init_db() -> None:
    db_models.Base.metadata.create_all(bind=_ENGINE)
    db_models._ensure_runtime_schema(bind=_ENGINE)


db_models.DB_PATH = TEST_DB_PATH
db_models.Engine = _ENGINE
db_models.SessionLocal = sessionmaker(bind=_ENGINE, expire_on_commit=False)
db_models.get_engine = lambda echo=False: _ENGINE
db_models.init_db = _session_init_db
_session_init_db()
