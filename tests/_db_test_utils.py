from __future__ import annotations

from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

import database.models as db_models


def install_temp_app_db(
    monkeypatch,
    tmp_path: Path,
    *,
    module_globals: dict[str, Any] | None = None,
    module_targets: list[Any] | tuple[Any, ...] = (),
) -> Path:
    """Redirect selected tests and their target modules to an isolated SQLite DB."""
    db_path = tmp_path / "test_app.db"
    engine = sa.create_engine(f"sqlite:///{db_path}", future=True)
    test_session_local = sessionmaker(bind=engine, expire_on_commit=False)

    def temp_init_db() -> None:
        db_models.Base.metadata.create_all(bind=engine)
        db_models._ensure_runtime_schema(bind=engine)

    monkeypatch.setattr(db_models, "DB_PATH", db_path, raising=False)
    monkeypatch.setattr(db_models, "Engine", engine, raising=False)
    monkeypatch.setattr(db_models, "SessionLocal", test_session_local, raising=False)
    monkeypatch.setattr(db_models, "get_engine", lambda echo=False: engine, raising=False)
    monkeypatch.setattr(db_models, "init_db", temp_init_db, raising=False)

    if module_globals is not None:
        monkeypatch.setitem(module_globals, "SessionLocal", test_session_local)
        monkeypatch.setitem(module_globals, "init_db", temp_init_db)

    for target in module_targets:
        monkeypatch.setattr(target, "SessionLocal", test_session_local, raising=False)
        monkeypatch.setattr(target, "init_db", temp_init_db, raising=False)

    temp_init_db()
    return db_path
