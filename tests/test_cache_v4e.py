"""v4E: in-process TTL cache tests."""
from __future__ import annotations

import time

from app.core.cache import TTLMemoCache, analysis_context_cache


def test_ttl_memo_hits_within_window():
    cache = TTLMemoCache(maxsize=8, ttl_seconds=60)
    calls: list[int] = []

    def loader():
        calls.append(1)
        return {"value": 42}

    a = cache.get_or_compute("k1", loader)
    b = cache.get_or_compute("k1", loader)
    assert a == b == {"value": 42}
    assert sum(calls) == 1, "loader should only run once on hit"


def test_ttl_memo_misses_after_ttl_expires():
    cache = TTLMemoCache(maxsize=8, ttl_seconds=0.2)
    cache.set("ephem", "x")
    assert cache.get("ephem") == "x"
    time.sleep(0.3)
    assert cache.get("ephem") is None


def test_ttl_memo_invalidate_removes_value():
    cache = TTLMemoCache(maxsize=4, ttl_seconds=60)
    cache.set("rm", 1)
    assert cache.get("rm") == 1
    cache.invalidate("rm")
    assert cache.get("rm") is None


def test_ttl_memo_clear_drops_all():
    cache = TTLMemoCache(maxsize=4, ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None


def test_ttl_memo_none_loader_result_not_cached():
    """If the loader returns None we don't pin a misleading miss."""
    cache = TTLMemoCache(maxsize=4, ttl_seconds=60)
    calls = []

    def loader():
        calls.append(1)
        return None

    cache.get_or_compute("none", loader)
    cache.get_or_compute("none", loader)
    assert sum(calls) == 2


def test_ttl_memo_loader_exception_propagates():
    cache = TTLMemoCache(maxsize=4, ttl_seconds=60)

    def loader():
        raise RuntimeError("boom")

    try:
        cache.get_or_compute("err", loader)
    except RuntimeError:
        pass
    else:
        raise AssertionError("loader exception must propagate")
    # nothing cached on failure
    assert cache.get("err") is None


def test_module_singletons_exist():
    assert analysis_context_cache is not None
    analysis_context_cache.clear()
