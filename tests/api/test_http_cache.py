from __future__ import annotations

from src.api.cache.http_cache import HttpCache


def test_key_is_stable_regardless_of_param_order(tmp_path) -> None:
    cache = HttpCache(tmp_path)
    key_a = cache.build_key("/v3/x", {"a": 1, "b": 2})
    key_b = cache.build_key("/v3/x", {"b": 2, "a": 1})
    assert key_a == key_b
    cache.close()


def test_set_and_get_roundtrip(tmp_path) -> None:
    cache = HttpCache(tmp_path)
    cache.set("/v3/x", {"k": "v"}, {"payload": 42})
    assert cache.get("/v3/x", {"k": "v"}) == {"payload": 42}
    assert cache.get("/v3/x", {"k": "other"}) is None
    cache.close()
