# 詳細設計: bars-mid-ohlc-cache

## 使命・制約

zenigame-fx 使命・絶対制約・禁止事項は概念設計参照。コーディングルール:
- 全施策にテスト必須
- `uv run pytest tests/alpha_factory/ tests/broker/ tests/backtest/ tests/dsl/ -x` 合格
- `uv run ruff check src/ tests/` / `uv run mypy src/` 合格
- テスト命名は振る舞い汎用名

## 概念設計リファレンス

[devnotes/20260425-0351-bars-mid-ohlc-cache/conceptual-design.md](./conceptual-design.md) — APPROVED (Round 2)

## 前提 verify 完了

| # | 前提 | 状態 |
|---|---|---|
| P1-P8 | (概念設計 §前提表) | **Verified** |
| P9 | `_bars_cache.py` の依存境界 | **To implement** (施策 1 で enforce) |

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | `_bars_cache.py` 新規モジュール (id+len LRU cache) | `src/alpha_factory/primitives/_bars_cache.py` (新規) | High |
| 2 | 3 モジュールの `_bars_to_mid_ohlc` 重複削除 | `src/alpha_factory/primitives/{directional_generic,modulator_generic,pair_specific}.py` | High |
| 3 | cache invariance / LRU / identity / len 検証テスト | `tests/alpha_factory/primitives/test_bars_cache.py` (新規) | High |

## 施策 1: `_bars_cache.py` 新規モジュール

### 変更箇所
`src/alpha_factory/primitives/_bars_cache.py` (新規)

### 波及変更
- `AGENTS.md` / skills / config / docs: 不要

### 実装

```python
"""bars → mid OHLC 変換の shared cache (Cycle 3 / T030).

背景:
    `_bars_to_mid_ohlc` が directional_generic / modulator_generic /
    pair_specific で複製定義されており、profile で 27 calls × 11ms の
    hotspot を形成していた。Stage A の 16 genome が同じ bars_60d を
    共有するため、同一 list object に対する重複変換が大半を占めていた。

方針:
    - LRU cache (MAX_ENTRIES=8) で (id(bars), len(bars)) をキーに変換結果を保持
    - id 再利用は bars list への強参照保持でガード (cache 生存中は object
      が GC されないため id が再利用されない)
    - len 変化 (bars.append 等) は自動的に cache miss
    - 要素置換 (list[i]=new_bar、len 不変) は検知できない運用契約
      (concept-design §制約参照、primitive/engine は read-only 利用)

依存制約 (P9):
    numpy, collections, src.domain.price のみ import。
    primitives.__init__ / _registry / 各 primitive module は import 禁止。
    import 循環を構造的に排除する。

thread safety:
    backtest path は thread-parallel 不可 (P8 Verified)。GA 並列は
    process-level のみのため module-level cache は process-local で
    単一 thread。並列化が導入される場合は別 TODO で lock 追加。
"""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence

import numpy as np

from src.domain.price import PriceBar

__all__ = ["MAX_ENTRIES", "bars_to_mid_ohlc", "clear_cache"]

#: cache に保持する最大エントリ数。
#:
#: 現行 topology は Stage A/B/C の 3 本 bars を 1 process で
#: 使い回す (run_ga.py の単一 Tier1Lane)。余裕をもって 8。
#: multi-pair 並列同居が導入される場合は config 化を検討。
MAX_ENTRIES: int = 8

#: (id(bars), len(bars)) → (o, h, l, c) ndarray tuple。
#: _REFS と lockstep で更新 (同じ key 集合を必ず維持)。
_CACHE: OrderedDict[
    tuple[int, int],
    tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
] = OrderedDict()

#: (id(bars), len(bars)) → bars sequence の強参照。cache 生存中 object を
#: 保持することで id 再利用を防ぐ (同 key で `_REFS[key] is bars` を
#: 検査して二重ガード)。EvaluationContext.bars は `Sequence[PriceBar]` な
#: ため、list 以外の Sequence も受け入れる。
_REFS: OrderedDict[tuple[int, int], Sequence[PriceBar]] = OrderedDict()


def _compute(
    bars: Sequence[PriceBar],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """mid OHLC (bid/ask 平均) を float64 配列で返す。cache 無しの pure compute。

    元の 3 モジュールに複製されていた実装を統合した canonical 実装。
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


def bars_to_mid_ohlc(
    bars: Sequence[PriceBar],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """mid OHLC を返す。同一 bars list に対しては cached 結果を再利用。

    key = (id(bars), len(bars))。`_REFS[key] is bars` で identity を
    二重検査して id 再利用 false hit を防ぐ。

    Returns:
        (open, high, low, close) の 4 つの float64 ndarray。長さは len(bars)。
    """
    key = (id(bars), len(bars))
    cached = _CACHE.get(key)
    if cached is not None and _REFS.get(key) is bars:
        # hit: LRU 順序更新 (lockstep で 2 dict とも move_to_end)
        _CACHE.move_to_end(key)
        _REFS.move_to_end(key)
        return cached

    # miss: compute + cache insert
    result = _compute(bars)
    _CACHE[key] = result
    _REFS[key] = bars

    # eviction: 2 dict を lockstep で popitem(last=False)
    while len(_CACHE) > MAX_ENTRIES:
        evicted_key, _ = _CACHE.popitem(last=False)
        _REFS.pop(evicted_key, None)
    return result


def clear_cache() -> None:
    """cache を空にする (主に test 用)。"""
    _CACHE.clear()
    _REFS.clear()
```

### 変更対象の依存境界 (P9 enforce)

`src/alpha_factory/primitives/_bars_cache.py` は:
- import: `numpy` / `collections.OrderedDict` / `src.domain.price.PriceBar` のみ
- **import 禁止**: `src.alpha_factory.primitives.{_base,_registry,directional_generic,modulator_generic,pair_specific,evaluator,_indicators}`

これにより primitive 登録 bootstrap (`ensure_registered()`) との循環を構造的に排除。

### ルックアヘッドバイアス
- N/A（bars → 配列変換のみ、look-ahead なし）

### パフォーマンスチェック
- cache hit は `OrderedDict.get` + `is` 比較 + `move_to_end` で O(1)
- miss 時は従来と同じ compute
- メモリ: 1 entry ≈ 32 × len(bars) bytes × MAX_ENTRIES 8 ≤ 22 MB / process (本番 86k bars)

### テスト計画
- 施策 3 で展開

### リスク
- 同一 list 内の要素置換 (len 不変) は検知不可 → 運用契約で対処 (docstring に明記済み)
- process 間 cache 共有なし → GA worker 並列では各 worker が独立 cache を持つ (問題なし、メモリは worker 数倍)

## 施策 2: 3 モジュールの重複削除

### 変更箇所
- `src/alpha_factory/primitives/directional_generic.py:66-88` 削除
- `src/alpha_factory/primitives/modulator_generic.py:53-85` 削除 (複製理由コメント含む)
- `src/alpha_factory/primitives/pair_specific.py:52-77` 削除 (複製理由コメント含む)

各モジュールで:
```python
# 削除前
def _bars_to_mid_ohlc(bars) -> tuple[...]: ...

# 削除後: import 差し替え
from src.alpha_factory.primitives._bars_cache import bars_to_mid_ohlc as _bars_to_mid_ohlc
```

`_bars_to_mid_ohlc` という local alias を維持することで、既存 primitive の `_compute_all` 関数内部の呼び出し箇所は変更不要（全て `_bars_to_mid_ohlc(ctx.bars)` のまま）。

### 波及変更
- `AGENTS.md` / skills / config / docs: 不要

### テスト計画
- 既存 primitive tests（`tests/alpha_factory/primitives/test_directional_generic.py` 等）が全合格 = 等価性の retrospective 検証

### リスク
- alias rename ミスがあれば NameError で即発覚（import 時に raise）→ low risk

## 施策 3: cache invariance テスト

### 変更箇所
`tests/alpha_factory/primitives/test_bars_cache.py` (新規)

### 波及変更
- AGENTS.md / skills / config / docs: 不要

### テスト構造

```python
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
```

### リスク
- `_bars_cache._CACHE` 等の private 属性直接参照は implementation detail テスト。module refactor で壊れ得るが、本 TODO では invariance の強制が目的なので許容

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | incremental |
| 判断根拠 | 3 ファイル統合 + 1 新規モジュール + 1 test file。影響範囲限定 |
| 競合リスク | 低（directional_generic / modulator_generic / pair_specific は primitive 群、頻繁に変更されない） |
| 想定実装時間 | 短（本体 ~30min + test ~1h + review ~30min = 合計 2h） |

## コミット計画
1. `feat(primitives): T030 bars_to_mid_ohlc shared cache (DRY + LRU)`

## Phase 7 検証
1. 再プロファイルで `_bars_to_mid_ohlc` 合計 tottime 60%+ 削減確認
2. RUN 全体 4%+ 短縮
3. Selection invariance bit-identical
4. n=1 なので INCONCLUSIVE ルール適用
