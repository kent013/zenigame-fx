"""_bars_cache の LRU + id/len key + identity guard invariance tests (T030)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from src.alpha_factory.primitives import _bars_cache
from src.domain.price import Ohlc, PriceBar


@pytest.fixture(autouse=True)
def _cache_isolation():
    """各 test で cache を空から始め、teardown でも空にする。"""
    _bars_cache.clear_cache()
    yield
    _bars_cache.clear_cache()


def _bar(i: int, base: Decimal = Decimal("154.00")) -> PriceBar:
    bt = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC) + timedelta(minutes=i)
    b = base + Decimal(str(round(i * 0.01, 4)))
    a = b + Decimal("0.01")
    return PriceBar(
        pair_name="USD_JPY",
        bar_time=bt,
        bid=Ohlc(b, b, b, b),
        ask=Ohlc(a, a, a, a),
        volume=1,
        complete=True,
    )


def _bars(n: int) -> list[PriceBar]:
    return [_bar(i) for i in range(n)]


def test_cache_hit_returns_identical_arrays() -> None:
    bars = _bars(100)
    r1 = _bars_cache.bars_to_mid_ohlc(bars)
    r2 = _bars_cache.bars_to_mid_ohlc(bars)
    for a1, a2 in zip(r1, r2, strict=True):
        assert a1 is a2, "cache hit must return same ndarray object"


def test_cache_miss_on_different_bars_object() -> None:
    """同一内容でも別 list object なら cache miss (id が異なる)。"""
    bars1 = _bars(100)
    bars2 = _bars(100)
    assert bars1 is not bars2
    r1 = _bars_cache.bars_to_mid_ohlc(bars1)
    r2 = _bars_cache.bars_to_mid_ohlc(bars2)
    # 別 entry として cache される (内容は同一だが object 違う)
    for a1, a2 in zip(r1, r2, strict=True):
        assert a1 is not a2
        np.testing.assert_array_equal(a1, a2)  # 値は一致


def test_cache_miss_on_length_change() -> None:
    """同一 list に append → len 変化で cache miss。"""
    bars = _bars(50)
    r1 = _bars_cache.bars_to_mid_ohlc(bars)
    bars.append(_bar(50))  # len 変化
    r2 = _bars_cache.bars_to_mid_ohlc(bars)
    for a1, a2 in zip(r1, r2, strict=True):
        assert a1 is not a2  # 別 array
    assert len(r2[0]) == 51


def test_cache_correctness_vs_direct_compute() -> None:
    """cache 経由と直接計算 (_compute) で bit-identical."""
    bars = _bars(100)
    cached = _bars_cache.bars_to_mid_ohlc(bars)
    _bars_cache.clear_cache()
    direct = _bars_cache._compute(bars)
    for c, d in zip(cached, direct, strict=True):
        np.testing.assert_array_equal(c, d)


def test_lru_eviction_at_max_entries() -> None:
    """MAX_ENTRIES を超えたら LRU で古いエントリが evict される。"""
    bars_list = [_bars(10 + i) for i in range(_bars_cache.MAX_ENTRIES + 2)]
    for bars in bars_list:
        _bars_cache.bars_to_mid_ohlc(bars)
    # 最初の 2 エントリは evict されているはず
    assert len(_bars_cache._CACHE) == _bars_cache.MAX_ENTRIES
    # 最後に追加した bars が最新 (move_to_end 済み)
    last_key = (id(bars_list[-1]), len(bars_list[-1]))
    assert last_key in _bars_cache._CACHE


def test_lru_hit_updates_order() -> None:
    """hit した entry は末尾へ move_to_end され、eviction 対象から外れる。"""
    bars_list = [_bars(10 + i) for i in range(_bars_cache.MAX_ENTRIES)]
    for bars in bars_list:
        _bars_cache.bars_to_mid_ohlc(bars)
    # 最初の bars に hit させて末尾へ移動
    _bars_cache.bars_to_mid_ohlc(bars_list[0])
    # 新しい bars を追加
    new_bars = _bars(100)
    _bars_cache.bars_to_mid_ohlc(new_bars)
    # MAX_ENTRIES 維持、bars_list[0] は残っている (最新 hit したため)
    assert len(_bars_cache._CACHE) == _bars_cache.MAX_ENTRIES
    key0 = (id(bars_list[0]), len(bars_list[0]))
    assert key0 in _bars_cache._CACHE
    # bars_list[1] が evict されたはず (bars_list[0] 以外で最古)
    key1 = (id(bars_list[1]), len(bars_list[1]))
    assert key1 not in _bars_cache._CACHE


def test_cache_and_refs_lockstep() -> None:
    """_CACHE と _REFS は常に同じ key 集合を保持する invariant。"""
    bars_list = [_bars(10 + i) for i in range(_bars_cache.MAX_ENTRIES + 3)]
    for bars in bars_list:
        _bars_cache.bars_to_mid_ohlc(bars)
    assert set(_bars_cache._CACHE.keys()) == set(_bars_cache._REFS.keys())


def test_identity_guard_rejects_id_reuse() -> None:
    """id 衝突 (別 list object が同じ id を持つ) を人為的に再現し、
    `_REFS[key] is bars` 検査が False のとき cache miss として
    recompute されることを検証する。

    手順: bars1 を cache 投入後、人為的に `_REFS[key]` を別 object
    (sentinel) に差し替えてから、新 bars を同 key で呼ぶ。_REFS[key]
    is bars1_new が False なので miss path に入り、新しい array が返る。
    """
    bars1 = _bars(50)
    r1 = _bars_cache.bars_to_mid_ohlc(bars1)
    key = (id(bars1), 50)
    assert _bars_cache._REFS[key] is bars1
    assert _bars_cache._CACHE[key] is r1

    # _REFS を別 sentinel に差し替え (id 衝突 + 別 object を模擬)
    sentinel: list[PriceBar] = []
    _bars_cache._REFS[key] = sentinel  # type: ignore[assignment]

    # 同じ key を引いても _REFS[key] is bars1 = False なので miss path へ
    # (bars1 で呼ぶ → _REFS.get(key) is bars1 は False、recompute)
    r2 = _bars_cache.bars_to_mid_ohlc(bars1)
    # recompute されて新しい array が cache にセットされる
    # (値は同一、オブジェクトは別)
    for a1, a2 in zip(r1, r2, strict=True):
        assert a1 is not a2
        np.testing.assert_array_equal(a1, a2)
    # 再投入後は _REFS[key] is bars1 に戻っている
    assert _bars_cache._REFS[key] is bars1


def test_clear_cache_empties_both_dicts() -> None:
    bars = _bars(50)
    _bars_cache.bars_to_mid_ohlc(bars)
    assert len(_bars_cache._CACHE) > 0
    assert len(_bars_cache._REFS) > 0
    _bars_cache.clear_cache()
    assert len(_bars_cache._CACHE) == 0
    assert len(_bars_cache._REFS) == 0
