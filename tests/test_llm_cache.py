"""tests/test_llm_cache.py — Unit tests for llm/cache.py TTLCache."""

import time

import pytest

from llm.cache import TTLCache


@pytest.fixture
def cache():
    return TTLCache(ttl_seconds=1)   # 1s TTL for fast expiry tests


def test_cache_miss_returns_none(cache):
    assert cache.get("sys", "user") is None


def test_cache_hit_returns_value(cache):
    cache.set("sys", "user", "hello")
    assert cache.get("sys", "user") == "hello"


def test_cache_stores_different_types(cache):
    cache.set("s", "u1", {"key": "value"})
    cache.set("s", "u2", [1, 2, 3])
    assert cache.get("s", "u1") == {"key": "value"}
    assert cache.get("s", "u2") == [1, 2, 3]


def test_cache_key_collision_different_system(cache):
    cache.set("sys_a", "user", "a")
    cache.set("sys_b", "user", "b")
    assert cache.get("sys_a", "user") == "a"
    assert cache.get("sys_b", "user") == "b"


def test_cache_key_collision_different_user(cache):
    cache.set("sys", "user_a", "a")
    cache.set("sys", "user_b", "b")
    assert cache.get("sys", "user_a") == "a"
    assert cache.get("sys", "user_b") == "b"


def test_cache_expiry_returns_none(cache):
    cache.set("sys", "user", "value")
    time.sleep(1.1)
    assert cache.get("sys", "user") is None


def test_cache_clear_removes_all(cache):
    cache.set("s1", "u1", "v1")
    cache.set("s2", "u2", "v2")
    cache.clear()
    assert cache.get("s1", "u1") is None
    assert cache.get("s2", "u2") is None


def test_cache_size(cache):
    assert cache.size() == 0
    cache.set("s", "u1", "v")
    cache.set("s", "u2", "v")
    assert cache.size() == 2


def test_cache_evict_expired(cache):
    cache.set("s", "u1", "v")
    time.sleep(1.1)
    cache.set("s", "u2", "v")   # fresh entry
    evicted = cache.evict_expired()
    assert evicted == 1
    assert cache.size() == 1


def test_cache_overwrite_resets_ttl(cache):
    cache.set("sys", "user", "v1")
    time.sleep(0.7)
    cache.set("sys", "user", "v2")   # overwrite, resets TTL
    time.sleep(0.5)                   # 0.5s after overwrite — should still be valid
    assert cache.get("sys", "user") == "v2"


def test_make_key_is_deterministic():
    k1 = TTLCache.make_key("system", "user")
    k2 = TTLCache.make_key("system", "user")
    assert k1 == k2


def test_make_key_separator_prevents_collision():
    # "ab" + "cd" != "a" + "bcd" because of \x00 separator
    k1 = TTLCache.make_key("ab", "cd")
    k2 = TTLCache.make_key("a", "bcd")
    assert k1 != k2
