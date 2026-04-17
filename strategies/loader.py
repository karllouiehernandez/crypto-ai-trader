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
from pathlib import Path
from typing import Dict, Optional

_load_counter = itertools.count()

from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from strategy.base import StrategyBase

log = logging.getLogger(__name__)

_registry: Dict[str, StrategyBase] = {}
_lock = threading.Lock()

STRATEGIES_DIR = Path(__file__).parent


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
                with _lock:
                    _registry[instance.name] = instance
                loaded.append(instance.name)

        if loaded:
            log.info(
                "strategies loaded",
                extra={"file": path.name, "strategies": loaded},
            )
    except Exception as exc:
        log.error(
            "strategy load failed",
            extra={"file": path.name, "error": str(exc)},
        )


def _boot_load() -> None:
    """Import all existing .py files in strategies/ at startup."""
    for path in sorted(STRATEGIES_DIR.glob("*.py")):
        _load_file(path)


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


def list_strategies() -> list:
    """Return metadata dicts for all registered strategies (for dashboard display)."""
    with _lock:
        return [s.meta() for s in _registry.values()]


def registry_snapshot() -> Dict[str, StrategyBase]:
    """Return a shallow copy of the registry (for testing)."""
    with _lock:
        return dict(_registry)


def clear_registry() -> None:
    """Clear all registered strategies. Used in tests only."""
    with _lock:
        _registry.clear()
