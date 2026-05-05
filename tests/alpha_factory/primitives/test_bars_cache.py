"""_bars_cache の LRU + id/len key + identity guard invariance tests (T030)."""
from __future__ import annotations

import os
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


# ---------------------------------------------------------------------------
# T090: _compute bid/ask local 変数化 + 中間変数削除 の数値同値性 / 非退行 test
# ---------------------------------------------------------------------------


def _bar_custom(
    i: int,
    bid_o: Decimal,
    bid_h: Decimal,
    bid_l: Decimal,
    bid_c: Decimal,
    ask_o: Decimal,
    ask_h: Decimal,
    ask_l: Decimal,
    ask_c: Decimal,
) -> PriceBar:
    """OHLC 各値を独立に指定できる test 用 PriceBar factory。"""
    bt = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC) + timedelta(minutes=i)
    return PriceBar(
        pair_name="USD_JPY",
        bar_time=bt,
        bid=Ohlc(bid_o, bid_h, bid_l, bid_c),
        ask=Ohlc(ask_o, ask_h, ask_l, ask_c),
        volume=1,
        complete=True,
    )


def _compute_oracle(
    bars,
):
    """T090 リファクタ前の現行 _compute 実装 (test 内 self-contained oracle)。

    `_bars_cache._compute` の数値同値性を検証するための参照実装。
    bid/ask の attribute access は最適化前の 8 回/bar 形式、
    中間変数 (bo, bh, bl, bc, ao, ah, al, ac) も保持する。
    """
    length = len(bars)
    o = np.empty(length, dtype=np.float64)
    h = np.empty(length, dtype=np.float64)
    low = np.empty(length, dtype=np.float64)
    c = np.empty(length, dtype=np.float64)
    for i, b in enumerate(bars):
        bo = float(b.bid.open)
        bh = float(b.bid.high)
        bl = float(b.bid.low)
        bc = float(b.bid.close)
        ao = float(b.ask.open)
        ah = float(b.ask.high)
        al = float(b.ask.low)
        ac = float(b.ask.close)
        o[i] = (bo + ao) * 0.5
        h[i] = (bh + ah) * 0.5
        low[i] = (bl + al) * 0.5
        c[i] = (bc + ac) * 0.5
    return o, h, low, c


def _assert_compute_identical(
    actual: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    expected: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
) -> None:
    """non-NaN 要素は np.array_equal、NaN 要素は同位置で一致を assert。"""
    assert len(actual) == 4
    assert len(expected) == 4
    for a, e in zip(actual, expected, strict=True):
        assert a.shape == e.shape
        assert a.dtype == e.dtype == np.float64
        nan_a = np.isnan(a)
        nan_e = np.isnan(e)
        # NaN 位置完全一致
        assert np.array_equal(nan_a, nan_e), "NaN 位置が不一致"
        # non-NaN 要素は完全一致 (bit-identical 期待)
        assert np.array_equal(a[~nan_a], e[~nan_e]), "non-NaN 値が不一致"


def test_compute_local_var_refactor_numerically_identical() -> None:
    """T090: 軽量版 `_compute` が現行 oracle と全 case で完全一致することを保証。

    cases:
      1. 通常 case (10 bars)
      2. 1 bar (edge)
      3. 異なる bid/ask 値の bar (open != high != low != close、bid != ask)
      4. NaN を含む bar (Decimal('NaN') が float() で nan に変換される)
    """
    # case 1: 通常 case (10 bars)
    bars1 = _bars(10)
    _assert_compute_identical(_bars_cache._compute(bars1), _compute_oracle(bars1))

    # case 2: 1 bar (edge)
    bars2 = _bars(1)
    _assert_compute_identical(_bars_cache._compute(bars2), _compute_oracle(bars2))

    # case 3: 異なる bid/ask 値の bar (open != high != low != close、bid != ask)
    bars3 = [
        _bar_custom(
            0,
            bid_o=Decimal("154.001"),
            bid_h=Decimal("154.250"),
            bid_l=Decimal("153.870"),
            bid_c=Decimal("154.123"),
            ask_o=Decimal("154.011"),
            ask_h=Decimal("154.262"),
            ask_l=Decimal("153.881"),
            ask_c=Decimal("154.135"),
        ),
        _bar_custom(
            1,
            bid_o=Decimal("100.000001"),
            bid_h=Decimal("999.999999"),
            bid_l=Decimal("0.000001"),
            bid_c=Decimal("12345.6789"),
            ask_o=Decimal("100.000002"),
            ask_h=Decimal("1000.000000"),
            ask_l=Decimal("0.000002"),
            ask_c=Decimal("12345.6790"),
        ),
        _bar_custom(
            2,
            bid_o=Decimal("-1.5"),
            bid_h=Decimal("0.0"),
            bid_l=Decimal("-2.0"),
            bid_c=Decimal("-0.75"),
            ask_o=Decimal("-1.4"),
            ask_h=Decimal("0.1"),
            ask_l=Decimal("-1.9"),
            ask_c=Decimal("-0.65"),
        ),
    ]
    _assert_compute_identical(_bars_cache._compute(bars3), _compute_oracle(bars3))

    # case 4: NaN を含む bar (Decimal('NaN') が float() で nan に変換される)
    nan_d = Decimal("NaN")
    bars4 = [
        _bar(0),  # 正常 bar
        _bar_custom(
            1,
            bid_o=nan_d,
            bid_h=Decimal("154.25"),
            bid_l=Decimal("153.87"),
            bid_c=Decimal("154.12"),
            ask_o=Decimal("154.01"),
            ask_h=nan_d,
            ask_l=Decimal("153.88"),
            ask_c=Decimal("154.13"),
        ),
        _bar(2),  # 正常 bar
    ]
    actual = _bars_cache._compute(bars4)
    expected = _compute_oracle(bars4)
    _assert_compute_identical(actual, expected)
    # bar index 1 の open / high が NaN になることを別途確認
    assert np.isnan(actual[0][1])  # mid open: bid NaN → NaN
    assert np.isnan(actual[1][1])  # mid high: ask NaN → NaN
    assert not np.isnan(actual[2][1])  # mid low: 両方有限
    assert not np.isnan(actual[3][1])  # mid close: 両方有限


@pytest.mark.skipif(
    not os.environ.get("ZENIGAME_FX_RUN_BENCH"),
    reason=(
        "microbenchmark は観測目的 (Codex Round 1 推奨)。 共有 CI 環境では "
        "ジッタによる false positive を避けるため default skip。 ローカル観測は "
        "`ZENIGAME_FX_RUN_BENCH=1` 設定で実行可能。"
    ),
)
def test_compute_microbenchmark_non_regression() -> None:
    """T090: 軽量版 `_compute` が現行 oracle に対して退行していないことを観測。

    Codex Round 1 推奨 + Round 2 反映: 必須 gate ではなく観測 (default skip)。
    `ZENIGAME_FX_RUN_BENCH=1` 設定時のみ実行され、 軽量版が oracle の
    median × 1.10 倍を超えないことを assert。 timing は `perf_counter_ns`
    で 25 回 median (warmup 3 回除外) + 順序効果緩和のため interleave。

    本 test の目的は「軽量版が確実に遅くないこと」の最低限観測であり、
    具体的な高速化倍率は profile 再計測で評価する (本 test 範囲外)。
    """
    import statistics
    from time import perf_counter_ns

    bars = _bars(2000)  # 軽量 microbenchmark; 数 ms 規模
    n_warmup = 3
    n_iter = 25

    # warmup (cold cache / first-touch 回避)
    for _ in range(n_warmup):
        _compute_oracle(bars)
        _bars_cache._compute(bars)

    oracle_times: list[int] = []
    light_times: list[int] = []
    # interleave で system load を平均化
    for _ in range(n_iter):
        t0 = perf_counter_ns()
        _compute_oracle(bars)
        t1 = perf_counter_ns()
        oracle_times.append(t1 - t0)

        t2 = perf_counter_ns()
        _bars_cache._compute(bars)
        t3 = perf_counter_ns()
        light_times.append(t3 - t2)

    oracle_median = statistics.median(oracle_times)
    light_median = statistics.median(light_times)

    # 軽量版 ≤ oracle × 1.10 (退行 gate、 緩め)
    assert light_median <= oracle_median * 1.10, (
        f"_compute regression: light={light_median}ns, "
        f"oracle={oracle_median}ns, ratio={light_median / oracle_median:.3f}"
    )
