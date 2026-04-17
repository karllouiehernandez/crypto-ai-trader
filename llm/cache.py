"""llm/cache.py — Thread-safe in-process TTL cache for LLM responses.

Keyed by SHA-256 of (system_prompt + user_prompt) to prevent cross-prompt
collisions. TTL enforced at infrastructure level — callers cannot bypass it.

This is intentionally dependency-free (no Redis, no external services).
Multiple processes each maintain their own cache; that is acceptable because
LLM calls are rare by design (5-min minimum between identical prompts).
"""

import hashlib
import threading
import time
from typing import Any, Optional

from config import LLM_CACHE_TTL_SECONDS


class TTLCache:
    """Thread-safe TTL cache.

    Usage:
        cache = TTLCache(ttl_seconds=300)
        cached = cache.get(system, user)
        if cached is None:
            result = expensive_call()
            cache.set(system, user, result)
    """

    def __init__(self, ttl_seconds: int = LLM_CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()

    # ── Key ────────────────────────────────────────────────────────────────

    @staticmethod
    def make_key(system: str, user: str) -> str:
        """SHA-256 of concatenated prompts — unique per (system, user) pair."""
        return hashlib.sha256(f"{system}\x00{user}".encode()).hexdigest()

    # ── Read / write ───────────────────────────────────────────────────────

    def get(self, system: str, user: str) -> Optional[Any]:
        """Return cached value or None if missing / expired."""
        key = self.make_key(system, user)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, ts = entry
            if time.monotonic() - ts >= self._ttl:
                del self._store[key]
                return None
            return value

    def set(self, system: str, user: str, value: Any) -> None:
        """Store value with current timestamp."""
        key = self.make_key(system, user)
        with self._lock:
            self._store[key] = (value, time.monotonic())

    # ── Maintenance ────────────────────────────────────────────────────────

    def clear(self) -> None:
        """Remove all entries. Used in tests."""
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        """Current number of entries (including expired not yet evicted)."""
        with self._lock:
            return len(self._store)

    def evict_expired(self) -> int:
        """Remove expired entries. Returns count evicted."""
        now = time.monotonic()
        with self._lock:
            expired = [k for k, (_, ts) in self._store.items()
                       if now - ts >= self._ttl]
            for k in expired:
                del self._store[k]
        return len(expired)


# Module-level default cache shared across all llm/* modules
_default_cache = TTLCache()
