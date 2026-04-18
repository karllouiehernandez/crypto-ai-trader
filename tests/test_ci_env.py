"""Smoke tests: config loads cleanly in CI without a real .env file."""
import os
import pytest


def test_config_imports_without_raising():
    import config
    assert hasattr(config, "BINANCE_API_KEY")
    assert hasattr(config, "SYMBOLS")
    assert hasattr(config, "DB_PATH")


def test_llm_enabled_flag_is_readable():
    import config
    assert hasattr(config, "LLM_ENABLED")
    assert isinstance(config.LLM_ENABLED, bool)


def test_symbols_is_non_empty_list():
    import config
    assert isinstance(config.SYMBOLS, list)
    assert len(config.SYMBOLS) > 0


def test_validate_env_raises_with_fake_credentials():
    """validate_env() must pass in CI because fake keys are non-empty strings."""
    import config
    # CI injects non-empty fake values — validate_env() should NOT raise
    config.validate_env()


def test_db_path_is_path_object():
    from pathlib import Path
    import config
    assert isinstance(config.DB_PATH, Path)
