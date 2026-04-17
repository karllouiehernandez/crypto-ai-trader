"""tests/test_strategy_loader.py — Unit tests for strategies/loader.py."""

import textwrap
from pathlib import Path

import pytest

from strategies.loader import (
    _load_file,
    clear_registry,
    get_strategy,
    list_strategies,
    registry_snapshot,
)


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_registry():
    """Clear the global registry before and after every test."""
    clear_registry()
    yield
    clear_registry()


def _write_strategy(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / f"{name}.py"
    path.write_text(content, encoding="utf-8")
    return path


VALID_STRATEGY = textwrap.dedent("""
    import pandas as pd
    from strategy.base import StrategyBase
    from strategy.regime import Regime

    class TestMomentum(StrategyBase):
        name = "test_momentum_v1"
        version = "1.0.0"
        regimes = [Regime.TRENDING]

        def should_long(self, df: pd.DataFrame) -> bool:
            return True

        def should_short(self, df: pd.DataFrame) -> bool:
            return False
""")

MULTI_STRATEGY = textwrap.dedent("""
    import pandas as pd
    from strategy.base import StrategyBase

    class StratA(StrategyBase):
        name = "multi_a"; version = "0.1"; regimes = []
        def should_long(self, df): return True
        def should_short(self, df): return False

    class StratB(StrategyBase):
        name = "multi_b"; version = "0.1"; regimes = []
        def should_long(self, df): return False
        def should_short(self, df): return True
""")

NON_STRATEGY_FILE = textwrap.dedent("""
    def helper():
        return 42

    class NotAStrategy:
        pass
""")

SYNTAX_ERROR_FILE = textwrap.dedent("""
    this is not valid python !!!
    def broken(:
""")

IMPORT_ERROR_FILE = textwrap.dedent("""
    from nonexistent_module_xyz import something
    from strategy.base import StrategyBase
    import pandas as pd

    class BrokenImport(StrategyBase):
        name = "broken"; version = "0.1"; regimes = []
        def should_long(self, df): return True
        def should_short(self, df): return False
""")


# ── _load_file: valid strategy ─────────────────────────────────────────────

def test_load_file_registers_valid_strategy(tmp_path):
    path = _write_strategy(tmp_path, "test_momentum_v1", VALID_STRATEGY)
    _load_file(path)
    strat = get_strategy("test_momentum_v1")
    assert strat is not None
    assert strat.name == "test_momentum_v1"


def test_load_file_registers_multiple_strategies_from_one_file(tmp_path):
    path = _write_strategy(tmp_path, "multi", MULTI_STRATEGY)
    _load_file(path)
    assert get_strategy("multi_a") is not None
    assert get_strategy("multi_b") is not None


def test_load_file_strategy_meta_is_correct(tmp_path):
    path = _write_strategy(tmp_path, "test_momentum_v1", VALID_STRATEGY)
    _load_file(path)
    strat = get_strategy("test_momentum_v1")
    meta = strat.meta()
    assert meta["name"] == "test_momentum_v1"
    assert meta["version"] == "1.0.0"
    assert meta["regimes"] == ["TRENDING"]


# ── _load_file: no-op cases ────────────────────────────────────────────────

def test_load_file_skips_underscore_prefix(tmp_path):
    path = tmp_path / "__init__.py"
    path.write_text("x = 1")
    _load_file(path)
    assert registry_snapshot() == {}


def test_load_file_skips_loader_py(tmp_path):
    path = tmp_path / "loader.py"
    path.write_text("x = 1")
    _load_file(path)
    assert registry_snapshot() == {}


def test_load_file_ignores_non_strategy_classes(tmp_path):
    path = _write_strategy(tmp_path, "helper", NON_STRATEGY_FILE)
    _load_file(path)
    assert registry_snapshot() == {}


# ── _load_file: error handling ─────────────────────────────────────────────

def test_load_file_handles_syntax_error_without_raising(tmp_path):
    path = _write_strategy(tmp_path, "broken_syntax", SYNTAX_ERROR_FILE)
    _load_file(path)   # must NOT raise
    assert registry_snapshot() == {}


def test_load_file_handles_import_error_without_raising(tmp_path):
    path = _write_strategy(tmp_path, "broken_import", IMPORT_ERROR_FILE)
    _load_file(path)   # must NOT raise
    assert registry_snapshot() == {}


# ── get_strategy ───────────────────────────────────────────────────────────

def test_get_strategy_returns_none_for_unknown_name():
    assert get_strategy("nonexistent") is None


def test_get_strategy_returns_correct_instance(tmp_path):
    path = _write_strategy(tmp_path, "test_momentum_v1", VALID_STRATEGY)
    _load_file(path)
    s = get_strategy("test_momentum_v1")
    assert s.name == "test_momentum_v1"


# ── list_strategies ────────────────────────────────────────────────────────

def test_list_strategies_empty_when_nothing_loaded():
    assert list_strategies() == []


def test_list_strategies_returns_meta_dicts(tmp_path):
    path = _write_strategy(tmp_path, "test_momentum_v1", VALID_STRATEGY)
    _load_file(path)
    result = list_strategies()
    assert len(result) == 1
    assert result[0]["name"] == "test_momentum_v1"
    assert result[0]["source"] == "plugin"
    assert result[0]["load_status"] == "loaded"


def test_list_strategies_returns_all_registered(tmp_path):
    path = _write_strategy(tmp_path, "multi", MULTI_STRATEGY)
    _load_file(path)
    names = {s["name"] for s in list_strategies()}
    assert names == {"multi_a", "multi_b"}


# ── Hot-reload: reloading replaces old instance ────────────────────────────

def test_reload_replaces_existing_strategy(tmp_path):
    v1 = textwrap.dedent("""
        import pandas as pd
        from strategy.base import StrategyBase
        class Reloadable(StrategyBase):
            name = "reloadable"; version = "1.0.0"; regimes = []
            def should_long(self, df): return True
            def should_short(self, df): return False
    """)
    v2 = textwrap.dedent("""
        import pandas as pd
        from strategy.base import StrategyBase
        class Reloadable(StrategyBase):
            name = "reloadable"; version = "2.0.0"; regimes = []
            def should_long(self, df): return False
            def should_short(self, df): return True
    """)
    path = _write_strategy(tmp_path, "reloadable", v1)
    _load_file(path)
    assert get_strategy("reloadable").version == "1.0.0"

    path.write_text(v2, encoding="utf-8")
    _load_file(path)
    assert get_strategy("reloadable").version == "2.0.0"
