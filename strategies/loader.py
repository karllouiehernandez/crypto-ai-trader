"""strategies/loader.py — Hot-reload engine for strategy plugins.

Usage:
    observer = start_watcher()   # call once at application boot
    strategy = get_strategy("rsi_mean_reversion_v1")
    all_meta  = list_strategies()
    observer.stop()              # call at shutdown

How it works:
    1. On start_watcher(), all existing .py files in strategies/ are imported.
    2. watchdog monitors the directory; on file create/modify, _load_file() runs.
    3. Each .py file is inspected for StrategyBase subclasses and registered in
       a thread-safe in-memory _registry dict keyed by strategy.name.
    4. Files prefixed with _ (including __init__.py and loader.py itself) are skipped.
    5. Import errors are logged but never crash the application.
"""

import importlib.util
import itertools
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

_load_counter = itertools.count()

from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from strategy.base import StrategyBase
from strategy.plugin_sdk import validate_strategy_file

log = logging.getLogger(__name__)

_registry: Dict[str, StrategyBase] = {}
_errors: Dict[str, dict] = {}
_bootstrapped = False
_lock = threading.Lock()

STRATEGIES_DIR = Path(__file__).parent


def _parse_generated_timestamp(path: Path) -> str:
    stem = path.stem
    if not stem.startswith("generated_"):
        return ""

    raw_ts = stem.removeprefix("generated_")
    try:
        generated_at = datetime.strptime(raw_ts, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return ""
    return generated_at.isoformat()


def _file_meta(path: Path, source: str = "plugin") -> dict:
    try:
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        modified_at = ""

    is_generated = path.stem.startswith("generated_")
    provenance = "generated" if is_generated else source
    return {
        "source": source,
        "path": str(path),
        "file_name": path.name,
        "is_generated": is_generated,
        "provenance": provenance,
        "generated_at": _parse_generated_timestamp(path),
        "modified_at": modified_at,
    }


def _registry_catalog_snapshot() -> list[dict]:
    """Return minimal registry metadata for duplicate validation."""
    with _lock:
        return [
            {
                "name": strategy.name,
                "version": strategy.version,
                "path": getattr(strategy, "_source_path", ""),
            }
            for strategy in _registry.values()
        ]


def _unregister_path(path: Path) -> None:
    """Remove registry entries loaded from a file that is now invalid."""
    resolved = str(path)
    with _lock:
        stale = [
            name
            for name, strategy in _registry.items()
            if getattr(strategy, "_source_path", "") == resolved
        ]
        for name in stale:
            _registry.pop(name, None)


# ── File system event handler ──────────────────────────────────────────────

class _StrategyFileHandler(FileSystemEventHandler):
    def on_created(self, event: FileCreatedEvent) -> None:
        if not event.is_directory and str(event.src_path).endswith(".py"):
            _load_file(Path(str(event.src_path)))

    def on_modified(self, event: FileModifiedEvent) -> None:
        if not event.is_directory and str(event.src_path).endswith(".py"):
            _load_file(Path(str(event.src_path)))


# ── Core loader ────────────────────────────────────────────────────────────

def _load_file(path: Path) -> None:
    """Dynamically import a strategy file and register all StrategyBase subclasses.

    Uses importlib.util (not importlib.import_module) so the strategies/ dir
    does not need to be on sys.path — works regardless of deployment layout.
    Skips files prefixed with _ to avoid processing __init__.py and loader.py.
    """
    if path.name.startswith("_"):
        return
    if path.name == "loader.py":
        return

    try:
        validation = validate_strategy_file(path, existing_catalog=_registry_catalog_snapshot())
        if not validation.valid:
            _unregister_path(path)
            issues = validation.as_dict()["issues"]
            with _lock:
                _errors[path.name] = {
                    **_file_meta(path),
                    "error": "; ".join(issue["message"] for issue in issues if issue["severity"] == "error")
                    or "Strategy validation failed.",
                    "error_type": "StrategyValidationError",
                    "load_status": "error",
                    "validation_status": "invalid",
                    "issues": issues,
                }
            log.error(
                "strategy validation failed",
                extra={"file": path.name, "issues": issues},
            )
            return

        # Read source text directly and compile/exec it to bypass __pycache__.
        # This guarantees hot-reload picks up the latest file content on Windows
        # where pyc caches can outlive the source modification.
        mod_name = f"_strategy_plugin_{path.stem}_{next(_load_counter)}"
        source = path.read_text(encoding="utf-8")
        code = compile(source, str(path), "exec")
        module = type(importlib.util)(mod_name)
        module.__file__ = str(path)
        exec(code, module.__dict__)  # noqa: S102

        loaded = []
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, StrategyBase)
                and obj is not StrategyBase
            ):
                instance = obj()
                instance._source_path = str(path)   # type: ignore[attr-defined]
                instance._source_type = "plugin"    # type: ignore[attr-defined]
                instance._file_name = path.name     # type: ignore[attr-defined]
                instance._is_generated = path.stem.startswith("generated_")  # type: ignore[attr-defined]
                with _lock:
                    _registry[instance.name] = instance
                loaded.append(instance.name)

        if loaded:
            with _lock:
                _errors.pop(path.name, None)
            log.info(
                "strategies loaded",
                extra={"file": path.name, "strategies": loaded},
            )
        else:
            with _lock:
                _errors[path.name] = {
                **_file_meta(path),
                "error": "No StrategyBase subclass found in plugin file.",
                "error_type": "StrategyValidationError",
                "load_status": "error",
                "validation_status": "invalid",
            }
            log.error(
                "strategy load failed",
                extra={"file": path.name, "error": "No StrategyBase subclass found in plugin file."},
            )
    except Exception as exc:
        with _lock:
            _errors[path.name] = {
                **_file_meta(path),
                "error": str(exc),
                "error_type": type(exc).__name__,
                "load_status": "error",
                "validation_status": "invalid",
            }
        log.error(
            "strategy load failed",
            extra={"file": path.name, "error": str(exc)},
        )


def _boot_load() -> None:
    """Import all existing .py files in strategies/ at startup."""
    global _bootstrapped
    for path in sorted(STRATEGIES_DIR.glob("*.py")):
        _load_file(path)
    _bootstrapped = True


def load_all(force: bool = False) -> None:
    """Load all plugin strategy files into the in-memory registry."""
    if force or not _bootstrapped:
        _boot_load()


# ── Public API ─────────────────────────────────────────────────────────────

def start_watcher() -> Observer:
    """Boot-load all existing strategy files and start the watchdog observer.

    Returns the Observer so the caller can stop() it at shutdown.
    """
    _boot_load()
    observer = Observer()
    observer.schedule(_StrategyFileHandler(), str(STRATEGIES_DIR), recursive=False)
    observer.start()
    log.info("strategy watcher started", extra={"dir": str(STRATEGIES_DIR)})
    return observer


def get_strategy(name: str) -> Optional[StrategyBase]:
    """Return the registered strategy instance by name, or None if not found."""
    with _lock:
        return _registry.get(name)


def load_strategy_path(path: str | Path) -> None:
    """Load or reload one plugin file directly."""
    _load_file(Path(path))


def list_strategies() -> list:
    """Return metadata dicts for all registered strategies (for dashboard display)."""
    with _lock:
        items = []
        for strategy in _registry.values():
            source_path = getattr(strategy, "_source_path", "")
            if source_path:
                file_meta = _file_meta(Path(source_path), source=getattr(strategy, "_source_type", "plugin"))
            else:
                source_type = getattr(strategy, "_source_type", "plugin")
                file_meta = {
                    "source": source_type,
                    "path": "",
                    "file_name": getattr(strategy, "_file_name", ""),
                    "is_generated": getattr(strategy, "_is_generated", False),
                    "provenance": "builtin" if source_type == "builtin" else "plugin",
                    "generated_at": "",
                    "modified_at": "",
                }

            items.append(
                {
                    **strategy.meta(),
                    **file_meta,
                    "load_status": "loaded",
                    "validation_status": "valid",
                }
            )
        return items


def list_strategy_errors() -> list[dict]:
    """Return plugin load errors for dashboard display."""
    with _lock:
        return [
            error
            for _, error in sorted(_errors.items())
        ]


def registry_snapshot() -> Dict[str, StrategyBase]:
    """Return a shallow copy of the registry (for testing)."""
    with _lock:
        return dict(_registry)


def clear_registry() -> None:
    """Clear all registered strategies. Used in tests only."""
    global _bootstrapped
    with _lock:
        _registry.clear()
        _errors.clear()
    _bootstrapped = False
