"""v4E: in-process TTL cache primitives.

Used to deduplicate expensive computations (e.g. `_analysis_context`) across
dashboard / intelligence / market endpoints in the same short window.

Design:
- Thread-safe via `cachetools.TTLCache` + lock.
- Fail-soft: any cache exception is swallowed; caller gets the fresh value.
- No Redis. Each worker has its own cache; acceptable for MVP.
"""

from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Any, Callable

try:
    from cachetools import TTLCache
except ImportError:  # pragma: no cover
    TTLCache = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class TTLMemoCache:
    """Thread-safe TTL memo. ``get_or_compute`` runs the loader on a miss
    and stores the result. Loader exceptions propagate (caller's choice).
    """

    def __init__(self, maxsize: int = 256, ttl_seconds: float = 30.0) -> None:
        self.ttl_seconds = float(ttl_seconds)
        self._lock = Lock()
        if TTLCache is not None:
            self._store: dict[Any, Any] = TTLCache(maxsize=maxsize, ttl=ttl_seconds)
        else:  # pragma: no cover
            self._store = {}

    def get(self, key: Any) -> Any:
        try:
            with self._lock:
                return self._store.get(key)
        except Exception:
            logger.exception("cache get failed", extra={"cache_key": str(key)[:80]})
            return None

    def set(self, key: Any, value: Any) -> None:
        try:
            with self._lock:
                self._store[key] = value
        except Exception:
            logger.exception("cache set failed", extra={"cache_key": str(key)[:80]})

    def invalidate(self, key: Any) -> None:
        try:
            with self._lock:
                self._store.pop(key, None)
        except Exception:
            pass

    def clear(self) -> None:
        try:
            with self._lock:
                self._store.clear()
        except Exception:
            pass

    def get_or_compute(self, key: Any, loader: Callable[[], Any]) -> Any:
        """Return cached value or invoke ``loader`` and store. Loader errors
        are propagated unchanged so callers can apply their own fallback."""
        existing = self.get(key)
        if existing is not None:
            return existing
        value = loader()
        if value is not None:
            self.set(key, value)
        return value


# Module-level singleton used by IntelligenceEngineService. Process-local;
# multi-worker deployments each maintain their own copy.
analysis_context_cache = TTLMemoCache(maxsize=128, ttl_seconds=30.0)
engine_summary_cache = TTLMemoCache(maxsize=128, ttl_seconds=30.0)


def now_monotonic() -> float:
    return time.monotonic()
