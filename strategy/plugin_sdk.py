"""Strategy plugin SDK helpers for draft creation and validation."""

from __future__ import annotations

import ast
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

from strategy.base import StrategyBase


STRATEGY_SDK_VERSION = "1"
SUPPORTED_STRATEGY_SDK_VERSIONS = (STRATEGY_SDK_VERSION,)
STRATEGY_PACK_FORMAT_VERSION = "1"

KNOWN_STRATEGY_COLUMNS = {
    "open_time",
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "ma_21",
    "ma_55",
    "macd",
    "macd_s",
    "rsi_14",
    "bb_hi",
    "bb_lo",
    "bb_width",
    "ema_9",
    "ema_21",
    "ema_55",
    "ema_200",
    "volume_ma_20",
    "adx_14",
}

REQUIRED_METADATA = {"name", "version", "description", "regimes"}
REQUIRED_METHODS = {"param_schema", "default_params"}
SIGNAL_METHODS = {
    "should_long",
    "should_short",
    "should_exit_long",
    "should_exit_short",
    "decide",
    "_momentum_decide",
    "_breakout_decide",
    "_is_oversold",
    "_is_overbought",
}
DATAFRAME_ALIASES = {"df", "frame", "last", "prev", "prior", "row", "candle"}
STRATEGY_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
GENERATED_DRAFT_RE = re.compile(r"^generated_\d{8}_\d{6}\.py$")


@dataclass(frozen=True)
class StrategyValidationIssue:
    severity: str
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"severity": self.severity, "code": self.code, "message": self.message}


@dataclass
class StrategyValidationResult:
    valid: bool
    path: str = ""
    strategy_names: list[str] = field(default_factory=list)
    metadata: list[dict[str, Any]] = field(default_factory=list)
    issues: list[StrategyValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[StrategyValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[StrategyValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "path": self.path,
            "strategy_names": list(self.strategy_names),
            "metadata": list(self.metadata),
            "issues": [issue.as_dict() for issue in self.issues],
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
        }


def strategy_template_source(strategy_name: str = "custom_strategy_v1") -> str:
    """Return a ready-to-edit StrategyBase draft template."""
    safe_name = sanitize_strategy_name(strategy_name) or "custom_strategy_v1"
    class_name = "".join(part.capitalize() for part in safe_name.split("_")) + "Strategy"
    return f'''"""Draft strategy plugin.

Edit the metadata and signal logic, then validate before saving as a draft.
Drafts are backtest-only until reviewed and saved as pinned plugins.
"""

from __future__ import annotations

import pandas as pd

from strategy.base import StrategyBase
from strategy.regime import Regime


class {class_name}(StrategyBase):
    name = "{safe_name}"
    display_name = "{safe_name.replace("_", " ").title()}"
    description = "Describe the market hypothesis, entry logic, and risk assumptions."
    version = "1.0.0"
    sdk_version = "{STRATEGY_SDK_VERSION}"
    regimes = [Regime.RANGING]

    def default_params(self) -> dict:
        return {{
            "rsi_buy_threshold": 35.0,
            "rsi_sell_threshold": 65.0,
        }}

    def param_schema(self) -> list[dict]:
        return [
            {{
                "name": "rsi_buy_threshold",
                "label": "RSI Buy Threshold",
                "type": "number",
                "default": 35.0,
                "min": 5.0,
                "max": 50.0,
            }},
            {{
                "name": "rsi_sell_threshold",
                "label": "RSI Sell Threshold",
                "type": "number",
                "default": 65.0,
                "min": 50.0,
                "max": 95.0,
            }},
        ]

    def should_long(self, df: pd.DataFrame) -> bool:
        last = df.iloc[-1]
        return bool(last["rsi_14"] < self.params["rsi_buy_threshold"])

    def should_short(self, df: pd.DataFrame) -> bool:
        last = df.iloc[-1]
        return bool(last["rsi_14"] > self.params["rsi_sell_threshold"])
'''


def sanitize_strategy_name(value: str) -> str:
    """Return a safe strategy name stem."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if cleaned and cleaned[0].isdigit():
        cleaned = f"strategy_{cleaned}"
    return cleaned


def list_generated_draft_files(strategies_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """Return generated draft files available for dashboard editing."""
    target_dir = _strategies_dir(strategies_dir)
    if not target_dir.exists():
        return []
    rows = []
    for path in sorted(target_dir.glob("generated_*.py"), reverse=True):
        try:
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        except OSError:
            modified_at = ""
        rows.append(
            {
                "file_name": path.name,
                "path": str(path),
                "modified_at": modified_at,
                "editable": GENERATED_DRAFT_RE.match(path.name) is not None,
            }
        )
    return rows


def read_strategy_source_file(path: str | Path, *, strategies_dir: str | Path | None = None) -> str:
    """Read one strategy file after confirming it lives under strategies/."""
    file_path = _safe_strategy_path(path, strategies_dir=strategies_dir)
    return file_path.read_text(encoding="utf-8")


def suggest_next_strategy_name(strategy_name: str, existing_catalog: list[dict[str, Any]] | None = None) -> str:
    """Suggest a non-conflicting `_vN` strategy name."""
    clean_name = sanitize_strategy_name(strategy_name)
    if not clean_name:
        return "custom_strategy_v1"
    match = re.match(r"^(?P<prefix>.+)_v(?P<num>\d+)$", clean_name)
    prefix = match.group("prefix") if match else clean_name
    current_num = int(match.group("num")) if match else 0
    max_num = current_num
    for item in existing_catalog or []:
        candidate = sanitize_strategy_name(str(item.get("name") or ""))
        candidate_match = re.match(rf"^{re.escape(prefix)}_v(?P<num>\d+)$", candidate)
        if candidate_match:
            max_num = max(max_num, int(candidate_match.group("num")))
    return f"{prefix}_v{max_num + 1}"


def strategy_sdk_support() -> dict[str, Any]:
    """Return the current app-side strategy SDK compatibility contract."""
    return {
        "current_sdk_version": STRATEGY_SDK_VERSION,
        "supported_sdk_versions": list(SUPPORTED_STRATEGY_SDK_VERSIONS),
        "required_metadata": sorted(REQUIRED_METADATA),
        "required_methods": sorted(REQUIRED_METHODS),
        "signal_contract": "should_long+should_short or decide",
        "strategy_pack_format_version": STRATEGY_PACK_FORMAT_VERSION,
    }


def export_strategy_pack(
    item: dict[str, Any],
    *,
    notes: str = "",
    strategies_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Build a portable strategy pack zip from one local strategy file."""
    file_path = _safe_strategy_path(str(item.get("path") or ""), strategies_dir=strategies_dir)
    source = file_path.read_text(encoding="utf-8")
    validation = validate_strategy_source(source, file_name=str(file_path), existing_catalog=[item])
    manifest = {
        "pack_format_version": STRATEGY_PACK_FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_file": file_path.name,
        "notes_file": "notes.md" if notes.strip() else "",
        "strategy": {
            "name": item.get("name") or file_path.stem,
            "display_name": item.get("display_name") or "",
            "description": item.get("description") or "",
            "version": item.get("version") or "",
            "sdk_version": item.get("sdk_version") or STRATEGY_SDK_VERSION,
            "regimes": list(item.get("regimes") or []),
            "provenance": item.get("provenance") or "",
            "default_params": dict(item.get("default_params") or {}),
            "param_schema": list(item.get("param_schema") or []),
        },
        "validation": {
            "valid": validation.valid,
            "issues": [issue.as_dict() for issue in validation.issues],
        },
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        archive.writestr(file_path.name, source)
        if notes.strip():
            archive.writestr("notes.md", notes.strip() + "\n")
    pack_name = f"{sanitize_strategy_name(str(manifest['strategy']['name']) or file_path.stem)}__{manifest['strategy']['version'] or 'draft'}.zip"
    return {
        "file_name": pack_name,
        "bytes": buffer.getvalue(),
        "manifest": manifest,
        "validation": validation.as_dict(),
    }


def inspect_strategy_pack(pack_bytes: bytes, *, filename: str = "") -> dict[str, Any]:
    """Read one strategy pack zip without writing anything to disk."""
    issues: list[StrategyValidationIssue] = []
    try:
        with zipfile.ZipFile(io.BytesIO(pack_bytes)) as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names:
                issues.append(
                    StrategyValidationIssue(
                        "error",
                        "missing_pack_manifest",
                        "Strategy pack is missing manifest.json.",
                    )
                )
                return _pack_result(False, filename=filename, issues=issues)

            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            pack_version = str(manifest.get("pack_format_version") or "")
            if pack_version != STRATEGY_PACK_FORMAT_VERSION:
                issues.append(
                    StrategyValidationIssue(
                        "error",
                        "unsupported_pack_version",
                        f"Strategy pack format `{pack_version}` is not supported. "
                        f"Supported: {STRATEGY_PACK_FORMAT_VERSION}.",
                    )
                )
            source_file = str(manifest.get("source_file") or "")
            if not source_file or source_file not in names:
                issues.append(
                    StrategyValidationIssue(
                        "error",
                        "missing_pack_source",
                        f"Strategy pack source file `{source_file or 'unknown'}` is missing.",
                    )
                )
                return _pack_result(False, filename=filename, manifest=manifest, issues=issues)
            source = archive.read(source_file).decode("utf-8")
            notes_file = str(manifest.get("notes_file") or "")
            notes = archive.read(notes_file).decode("utf-8") if notes_file and notes_file in names else ""
    except zipfile.BadZipFile:
        issues.append(StrategyValidationIssue("error", "invalid_pack_zip", "Uploaded file is not a valid zip archive."))
        return _pack_result(False, filename=filename, issues=issues)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        issues.append(StrategyValidationIssue("error", "invalid_pack_payload", str(exc)))
        return _pack_result(False, filename=filename, issues=issues)

    return _pack_result(True, filename=filename, manifest=manifest, source=source, notes=notes, issues=issues)


def import_strategy_pack(
    pack_bytes: bytes,
    *,
    filename: str = "",
    existing_catalog: list[dict[str, Any]] | None = None,
    strategies_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Validate one strategy pack and save its source as a generated draft."""
    pack = inspect_strategy_pack(pack_bytes, filename=filename)
    if not pack["valid"]:
        return {
            "saved": False,
            "path": "",
            "file_name": "",
            "manifest": pack.get("manifest") or {},
            "notes": pack.get("notes") or "",
            "pack_validation": pack,
            "validation": {"valid": False, "issues": list(pack.get("issues") or [])},
        }

    label = str((pack["manifest"].get("strategy") or {}).get("name") or Path(str(pack["manifest"].get("source_file") or "draft.py")).stem)
    result = create_strategy_draft(
        str(pack["source"]),
        label=label,
        strategies_dir=strategies_dir,
        existing_catalog=existing_catalog,
    )
    result["manifest"] = pack["manifest"]
    result["notes"] = pack["notes"]
    result["pack_validation"] = pack
    return result


def validate_strategy_file(
    path: str | Path,
    *,
    existing_catalog: list[dict[str, Any]] | None = None,
) -> StrategyValidationResult:
    file_path = Path(path)
    try:
        source = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        issue = StrategyValidationIssue("error", "read_failed", str(exc))
        return StrategyValidationResult(False, path=str(file_path), issues=[issue])
    return validate_strategy_source(source, file_name=str(file_path), existing_catalog=existing_catalog)


def validate_strategy_source(
    source: str,
    *,
    file_name: str = "",
    existing_catalog: list[dict[str, Any]] | None = None,
) -> StrategyValidationResult:
    """Validate strategy source before it is discoverable by the runtime."""
    issues: list[StrategyValidationIssue] = []
    try:
        tree = ast.parse(source, filename=file_name or "<strategy>")
    except SyntaxError as exc:
        issues.append(StrategyValidationIssue("error", "syntax_error", f"{exc.msg} at line {exc.lineno}"))
        return StrategyValidationResult(False, path=file_name, issues=issues)

    class_nodes = [node for node in tree.body if isinstance(node, ast.ClassDef) and _is_strategy_subclass(node)]
    if not class_nodes:
        issues.append(StrategyValidationIssue("error", "missing_strategy_class", "No StrategyBase subclass found."))
        return StrategyValidationResult(False, path=file_name, issues=issues)

    for node in class_nodes:
        _validate_class_node(node, issues)
        _validate_indicator_columns(node, issues)

    strategy_instances = _instantiate_strategy_classes(source, file_name, issues)
    metadata: list[dict[str, Any]] = []
    names: list[str] = []
    for instance in strategy_instances:
        meta = instance.meta()
        metadata.append(meta)
        names.append(str(meta.get("name") or ""))
        _validate_runtime_metadata(meta, instance.__class__.__name__, issues)
        _validate_param_contract(meta, issues)
        _validate_duplicates(meta, existing_catalog or [], file_name, issues)

    valid = not any(issue.severity == "error" for issue in issues)
    return StrategyValidationResult(valid, path=file_name, strategy_names=names, metadata=metadata, issues=issues)


def create_strategy_draft(
    source: str,
    *,
    label: str = "",
    strategies_dir: str | Path | None = None,
    existing_catalog: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate and save source as a generated draft under strategies/."""
    validation = validate_strategy_source(source, file_name=f"{label or 'draft'}.py", existing_catalog=existing_catalog)
    if not validation.valid:
        return {"saved": False, "path": "", "file_name": "", "validation": validation.as_dict()}

    target_dir = Path(strategies_dir) if strategies_dir else Path(__file__).resolve().parents[1] / "strategies"
    target_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).replace(microsecond=0)
    for offset in range(120):
        candidate = target_dir / f"generated_{(created_at + timedelta(seconds=offset)).strftime('%Y%m%d_%H%M%S')}.py"
        if not candidate.exists():
            header = (
                "# GENERATED STRATEGY DRAFT\n"
                "# Backtest-only until reviewed and saved as a pinned plugin artifact.\n\n"
            )
            text = source if source.startswith("# GENERATED STRATEGY DRAFT") else header + source
            candidate.write_text(text, encoding="utf-8")
            return {
                "saved": True,
                "path": str(candidate),
                "file_name": candidate.name,
                "validation": validation.as_dict(),
            }

    issue = StrategyValidationIssue("error", "filename_collision", "Could not allocate a generated draft filename.")
    validation.issues.append(issue)
    validation.valid = False
    return {"saved": False, "path": "", "file_name": "", "validation": validation.as_dict()}


def _strategies_dir(strategies_dir: str | Path | None = None) -> Path:
    return Path(strategies_dir) if strategies_dir else Path(__file__).resolve().parents[1] / "strategies"


def _safe_strategy_path(path: str | Path, *, strategies_dir: str | Path | None = None) -> Path:
    base_dir = _strategies_dir(strategies_dir).resolve()
    file_path = Path(path).resolve()
    if base_dir != file_path.parent and base_dir not in file_path.parents:
        raise ValueError(f"Strategy file must be inside {base_dir}")
    if file_path.suffix != ".py":
        raise ValueError("Strategy file must be a .py file")
    if not file_path.exists():
        raise FileNotFoundError(str(file_path))
    return file_path


def _pack_result(
    valid: bool,
    *,
    filename: str = "",
    manifest: dict[str, Any] | None = None,
    source: str = "",
    notes: str = "",
    issues: list[StrategyValidationIssue] | None = None,
) -> dict[str, Any]:
    rows = [issue.as_dict() for issue in issues or []]
    return {
        "valid": valid and not rows,
        "filename": filename,
        "manifest": manifest or {},
        "source": source,
        "notes": notes,
        "issues": rows,
    }


def _is_strategy_subclass(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "StrategyBase":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "StrategyBase":
            return True
    return False


def _validate_class_node(node: ast.ClassDef, issues: list[StrategyValidationIssue]) -> None:
    assignments = _class_assignments(node)
    methods = _class_methods(node)
    for field_name in sorted(REQUIRED_METADATA):
        if field_name not in assignments:
            issues.append(
                StrategyValidationIssue(
                    "error",
                    "missing_metadata",
                    f"{node.name} must define class metadata `{field_name}`.",
                )
            )
    for method_name in sorted(REQUIRED_METHODS):
        if method_name not in methods:
            issues.append(
                StrategyValidationIssue(
                    "error",
                    "missing_method",
                    f"{node.name} must define `{method_name}()` for UI parameter metadata.",
                )
            )
    has_pair = {"should_long", "should_short"}.issubset(methods)
    has_decide = "decide" in methods
    if not has_pair and not has_decide:
        issues.append(
            StrategyValidationIssue(
                "error",
                "missing_signal_contract",
                f"{node.name} must define should_long+should_short or override decide().",
            )
        )


def _validate_indicator_columns(node: ast.ClassDef, issues: list[StrategyValidationIssue]) -> None:
    methods = {stmt.name: stmt for stmt in node.body if isinstance(stmt, ast.FunctionDef)}
    for method_name, method_node in methods.items():
        if method_name not in SIGNAL_METHODS and not method_name.startswith("_"):
            continue
        for subscript in ast.walk(method_node):
            if not isinstance(subscript, ast.Subscript):
                continue
            alias = _subscript_alias(subscript.value)
            if alias not in DATAFRAME_ALIASES:
                continue
            key = _subscript_key(subscript.slice)
            if key and key not in KNOWN_STRATEGY_COLUMNS:
                issues.append(
                    StrategyValidationIssue(
                        "error",
                        "unknown_indicator_column",
                        f"{node.name}.{method_name} references unknown candle/indicator column `{key}`.",
                    )
                )


def _instantiate_strategy_classes(
    source: str,
    file_name: str,
    issues: list[StrategyValidationIssue],
) -> list[StrategyBase]:
    try:
        code = compile(source, file_name or "<strategy>", "exec")
        module = ModuleType("_strategy_validation_module")
        module.__file__ = file_name
        exec(code, module.__dict__)  # noqa: S102
    except Exception as exc:
        issues.append(StrategyValidationIssue("error", "import_failed", str(exc)))
        return []

    instances: list[StrategyBase] = []
    for value in module.__dict__.values():
        if isinstance(value, type) and issubclass(value, StrategyBase) and value is not StrategyBase:
            try:
                instances.append(value())
            except Exception as exc:
                issues.append(StrategyValidationIssue("error", "instantiation_failed", f"{value.__name__}: {exc}"))
    return instances


def _validate_runtime_metadata(meta: dict[str, Any], class_name: str, issues: list[StrategyValidationIssue]) -> None:
    name = str(meta.get("name") or "")
    version = str(meta.get("version") or "")
    sdk_version = str(meta.get("sdk_version") or STRATEGY_SDK_VERSION)
    if not name or name == "unnamed":
        issues.append(StrategyValidationIssue("error", "invalid_name", f"{class_name} must set a unique name."))
    elif not STRATEGY_NAME_RE.match(name):
        issues.append(
            StrategyValidationIssue(
                "error",
                "invalid_name",
                f"{class_name} name `{name}` must use lowercase letters, numbers, and underscores.",
            )
        )
    if not version:
        issues.append(StrategyValidationIssue("error", "invalid_version", f"{class_name} must set a version."))
    if sdk_version not in SUPPORTED_STRATEGY_SDK_VERSIONS:
        issues.append(
            StrategyValidationIssue(
                "error",
                "unsupported_sdk_version",
                f"{class_name} sdk_version `{sdk_version}` is not supported by this app. "
                f"Supported: {', '.join(SUPPORTED_STRATEGY_SDK_VERSIONS)}.",
            )
        )
    if not meta.get("description"):
        issues.append(StrategyValidationIssue("error", "missing_description", f"{class_name} must describe its hypothesis."))


def _validate_param_contract(meta: dict[str, Any], issues: list[StrategyValidationIssue]) -> None:
    defaults = meta.get("default_params") or {}
    schema = meta.get("param_schema") or []
    if not isinstance(defaults, dict):
        issues.append(StrategyValidationIssue("error", "invalid_default_params", "default_params() must return a dict."))
        return
    if not isinstance(schema, list):
        issues.append(StrategyValidationIssue("error", "invalid_param_schema", "param_schema() must return a list."))
        return
    schema_names = {field.get("name") for field in schema if isinstance(field, dict)}
    default_names = set(defaults)
    missing_schema = default_names - schema_names
    if missing_schema:
        issues.append(
            StrategyValidationIssue(
                "error",
                "params_missing_schema",
                f"default_params keys missing from param_schema: {', '.join(sorted(missing_schema))}.",
            )
        )


def _validate_duplicates(
    meta: dict[str, Any],
    existing_catalog: list[dict[str, Any]],
    file_name: str,
    issues: list[StrategyValidationIssue],
) -> None:
    name = meta.get("name")
    version = meta.get("version")
    current = str(Path(file_name).resolve()) if file_name else ""
    for item in existing_catalog:
        if item.get("name") != name or item.get("version") != version:
            continue
        other = str(Path(str(item.get("path") or "")).resolve()) if item.get("path") else ""
        if current and other and current == other:
            continue
        issues.append(
            StrategyValidationIssue(
                "error",
                "duplicate_name_version",
                f"Strategy `{name}` version `{version}` already exists in the catalog.",
            )
        )


def _class_assignments(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            names.add(stmt.target.id)
    return names


def _class_methods(node: ast.ClassDef) -> set[str]:
    return {stmt.name for stmt in node.body if isinstance(stmt, ast.FunctionDef)}


def _subscript_alias(value: ast.AST) -> str:
    if isinstance(value, ast.Name):
        return value.id
    return ""


def _subscript_key(value: ast.AST) -> str:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return ""
