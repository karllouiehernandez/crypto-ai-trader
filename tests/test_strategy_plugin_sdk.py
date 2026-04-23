import textwrap
import zipfile
from io import BytesIO
from pathlib import Path

from strategy.plugin_sdk import (
    STRATEGY_PACK_FORMAT_VERSION,
    STRATEGY_SDK_VERSION,
    create_strategy_draft,
    export_strategy_pack,
    import_strategy_pack,
    inspect_strategy_pack,
    list_generated_draft_files,
    read_strategy_source_file,
    suggest_next_strategy_name,
    strategy_template_source,
    strategy_sdk_support,
    validate_strategy_source,
)


VALID_SOURCE = textwrap.dedent("""
    import pandas as pd
    from strategy.base import StrategyBase
    from strategy.regime import Regime

    class ValidDraft(StrategyBase):
        name = "valid_draft_v1"
        description = "A valid strategy contract."
        version = "1.0.0"
        regimes = [Regime.RANGING]

        def default_params(self):
            return {"threshold": 35.0}

        def param_schema(self):
            return [{"name": "threshold", "type": "number", "default": 35.0}]

        def should_long(self, df: pd.DataFrame) -> bool:
            last = df.iloc[-1]
            return bool(last["rsi_14"] < self.params["threshold"])

        def should_short(self, df: pd.DataFrame) -> bool:
            last = df.iloc[-1]
            return bool(last["rsi_14"] > 70)
""")


def test_validate_strategy_source_accepts_valid_long_short_contract():
    result = validate_strategy_source(VALID_SOURCE, file_name="valid.py")
    assert result.valid is True
    assert result.strategy_names == ["valid_draft_v1"]


def test_validate_strategy_source_accepts_decide_only_contract():
    source = textwrap.dedent("""
        import pandas as pd
        from strategy.base import StrategyBase
        from strategy.signals import Signal

        class DecideOnly(StrategyBase):
            name = "decide_only_v1"
            description = "Decide-only contract."
            version = "1.0.0"
            regimes = []

            def default_params(self): return {}
            def param_schema(self): return []
            def decide(self, df: pd.DataFrame, regime=None): return Signal.HOLD
    """)
    assert validate_strategy_source(source, file_name="decide.py").valid is True


def test_validate_strategy_source_rejects_missing_metadata():
    source = VALID_SOURCE.replace('    description = "A valid strategy contract."\n', "")
    result = validate_strategy_source(source, file_name="missing.py")
    assert result.valid is False
    assert any(issue.code == "missing_metadata" for issue in result.errors)


def test_validate_strategy_source_rejects_missing_signal_contract():
    source = textwrap.dedent("""
        from strategy.base import StrategyBase
        from strategy.regime import Regime

        class MissingSignal(StrategyBase):
            name = "missing_signal_v1"
            description = "Missing signal contract."
            version = "1.0.0"
            regimes = [Regime.RANGING]
            def default_params(self): return {}
            def param_schema(self): return []
    """)
    result = validate_strategy_source(source, file_name="missing_signal.py")
    assert result.valid is False
    assert any(issue.code == "missing_signal_contract" for issue in result.errors)


def test_validate_strategy_source_rejects_unknown_indicator_column():
    source = VALID_SOURCE.replace('last["rsi_14"]', 'last["bb_upper"]', 1)
    result = validate_strategy_source(source, file_name="bad_column.py")
    assert result.valid is False
    assert any(issue.code == "unknown_indicator_column" for issue in result.errors)


def test_validate_strategy_source_rejects_duplicate_name_version():
    result = validate_strategy_source(
        VALID_SOURCE,
        file_name="new.py",
        existing_catalog=[{"name": "valid_draft_v1", "version": "1.0.0", "path": str(Path("other.py").resolve())}],
    )
    assert result.valid is False
    assert any(issue.code == "duplicate_name_version" for issue in result.errors)


def test_validate_strategy_source_rejects_default_without_schema():
    source = VALID_SOURCE.replace('return [{"name": "threshold", "type": "number", "default": 35.0}]', "return []")
    result = validate_strategy_source(source, file_name="bad_params.py")
    assert result.valid is False
    assert any(issue.code == "params_missing_schema" for issue in result.errors)


def test_strategy_template_source_is_valid():
    result = validate_strategy_source(strategy_template_source("sample_strategy_v1"), file_name="template.py")
    assert result.valid is True
    assert result.strategy_names == ["sample_strategy_v1"]


def test_strategy_template_source_includes_sdk_version():
    source = strategy_template_source("sample_strategy_v1")
    assert f'sdk_version = "{STRATEGY_SDK_VERSION}"' in source


def test_strategy_sdk_support_exposes_current_contract():
    support = strategy_sdk_support()
    assert support["current_sdk_version"] == STRATEGY_SDK_VERSION
    assert STRATEGY_SDK_VERSION in support["supported_sdk_versions"]
    assert support["signal_contract"] == "should_long+should_short or decide"


def test_validate_strategy_source_rejects_unsupported_sdk_version():
    source = textwrap.dedent("""
        import pandas as pd
        from strategy.base import StrategyBase
        from strategy.regime import Regime

        class UnsupportedSdkDraft(StrategyBase):
            name = "unsupported_sdk_v1"
            description = "A draft with an unsupported SDK version."
            version = "1.0.0"
            sdk_version = "999"
            regimes = [Regime.RANGING]

            def default_params(self):
                return {"threshold": 35.0}

            def param_schema(self):
                return [{"name": "threshold", "type": "number", "default": 35.0}]

            def should_long(self, df: pd.DataFrame) -> bool:
                last = df.iloc[-1]
                return bool(last["rsi_14"] < self.params["threshold"])

            def should_short(self, df: pd.DataFrame) -> bool:
                last = df.iloc[-1]
                return bool(last["rsi_14"] > 70)
    """)
    result = validate_strategy_source(source, file_name="bad_sdk.py")
    assert result.valid is False
    assert any(issue.code == "unsupported_sdk_version" for issue in result.errors)


def test_create_strategy_draft_writes_generated_file(tmp_path):
    result = create_strategy_draft(VALID_SOURCE, label="valid_draft_v1", strategies_dir=tmp_path)
    assert result["saved"] is True
    path = Path(result["path"])
    assert path.exists()
    assert path.name.startswith("generated_")
    assert "Backtest-only" in path.read_text(encoding="utf-8")


def test_create_strategy_draft_does_not_save_invalid_source(tmp_path):
    result = create_strategy_draft("not python !!!", label="broken", strategies_dir=tmp_path)
    assert result["saved"] is False
    assert list(tmp_path.iterdir()) == []


def test_list_generated_draft_files_returns_editable_drafts(tmp_path):
    draft = tmp_path / "generated_20260423_010203.py"
    draft.write_text(VALID_SOURCE, encoding="utf-8")
    (tmp_path / "reviewed.py").write_text(VALID_SOURCE, encoding="utf-8")

    rows = list_generated_draft_files(tmp_path)

    assert [row["file_name"] for row in rows] == ["generated_20260423_010203.py"]
    assert rows[0]["editable"] is True


def test_read_strategy_source_file_blocks_outside_strategies_dir(tmp_path):
    outside = tmp_path.parent / "outside_strategy.py"
    outside.write_text("x = 1", encoding="utf-8")
    try:
        read_strategy_source_file(outside, strategies_dir=tmp_path)
    except ValueError as exc:
        assert "inside" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_read_strategy_source_file_reads_safe_draft(tmp_path):
    draft = tmp_path / "generated_20260423_010203.py"
    draft.write_text(VALID_SOURCE, encoding="utf-8")
    assert "ValidDraft" in read_strategy_source_file(draft, strategies_dir=tmp_path)


def test_suggest_next_strategy_name_increments_catalog_versions():
    suggestion = suggest_next_strategy_name(
        "alpha_pullback_v1",
        [
            {"name": "alpha_pullback_v1"},
            {"name": "alpha_pullback_v2"},
            {"name": "other_v9"},
        ],
    )
    assert suggestion == "alpha_pullback_v3"


def test_suggest_next_strategy_name_appends_version_when_missing():
    assert suggest_next_strategy_name("alpha pullback", []) == "alpha_pullback_v1"


def test_export_strategy_pack_includes_manifest_source_and_notes(tmp_path):
    draft = tmp_path / "generated_20260423_010203.py"
    draft.write_text(VALID_SOURCE, encoding="utf-8")

    result = export_strategy_pack(
        {
            "name": "valid_draft_v1",
            "display_name": "Valid Draft",
            "description": "A valid strategy contract.",
            "version": "1.0.0",
            "sdk_version": STRATEGY_SDK_VERSION,
            "regimes": ["RANGING"],
            "provenance": "generated",
            "default_params": {"threshold": 35.0},
            "param_schema": [{"name": "threshold", "type": "number", "default": 35.0}],
            "path": str(draft),
        },
        notes="Test notes",
        strategies_dir=tmp_path,
    )

    assert result["file_name"] == "valid_draft_v1__1.0.0.zip"
    assert result["manifest"]["pack_format_version"] == STRATEGY_PACK_FORMAT_VERSION
    with zipfile.ZipFile(BytesIO(result["bytes"])) as archive:
        assert set(archive.namelist()) == {"manifest.json", "generated_20260423_010203.py", "notes.md"}


def test_inspect_strategy_pack_rejects_missing_manifest():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("strategy.py", VALID_SOURCE)

    result = inspect_strategy_pack(buffer.getvalue(), filename="broken.zip")

    assert result["valid"] is False
    assert any(issue["code"] == "missing_pack_manifest" for issue in result["issues"])


def test_import_strategy_pack_saves_generated_draft(tmp_path):
    source_path = tmp_path / "source.py"
    source_path.write_text(VALID_SOURCE, encoding="utf-8")
    exported = export_strategy_pack(
        {
            "name": "valid_draft_v1",
            "display_name": "Valid Draft",
            "description": "A valid strategy contract.",
            "version": "1.0.0",
            "sdk_version": STRATEGY_SDK_VERSION,
            "regimes": ["RANGING"],
            "provenance": "generated",
            "default_params": {"threshold": 35.0},
            "param_schema": [{"name": "threshold", "type": "number", "default": 35.0}],
            "path": str(source_path),
        },
        notes="Portable strategy pack",
        strategies_dir=tmp_path,
    )

    result = import_strategy_pack(
        exported["bytes"],
        filename=exported["file_name"],
        existing_catalog=[],
        strategies_dir=tmp_path,
    )

    assert result["saved"] is True
    assert result["validation"]["valid"] is True
    assert Path(result["path"]).exists()
    assert "Portable strategy pack" in result["notes"]


def test_import_strategy_pack_rejects_invalid_zip(tmp_path):
    result = import_strategy_pack(b"not a zip", filename="bad.zip", existing_catalog=[], strategies_dir=tmp_path)
    assert result["saved"] is False
    assert any(issue["code"] == "invalid_pack_zip" for issue in result["pack_validation"]["issues"])
