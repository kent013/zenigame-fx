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

    profile-optimize cycle 3/3 (T090): bid/ask 属性アクセスを 1 bar あたり
    1 回ずつ local 変数化 (b.bid → bid、b.ask → ask)、 中間変数
    (bo, bh, bl, bc, ao, ah, al, ac) を削除して直接 mid 計算に集約。
    LOAD_ATTR 削減のみが目的、 加算・乗算の演算順序および
    `float(...)` cast 回数 (8 回/bar) は完全同一。
    cast 順序は ``bo,bh,bl,bc,ao,ah,al,ac`` 一括先行 → mid 計算 から
    OHLC 単位で交互 (``open bid+ask → high bid+ask → ...``) へ変更されるが、
    各 mid 計算式 ``(float(bid.X) + float(ask.X)) * 0.5`` は **数値結果**
    (有限値の bit-identical / quiet NaN の同位置発生) に関して現行と一致する。
    例外発生タイミングは cast 順序変更により異なり得るため、 例外境界での
    完全同一性は保証しない (signal 値計算用 mid OHLC として影響なし)。
    """
    length = len(bars)
    o = np.empty(length, dtype=np.float64)
    h = np.empty(length, dtype=np.float64)
    low = np.empty(length, dtype=np.float64)
    c = np.empty(length, dtype=np.float64)
    for i, b in enumerate(bars):
        bid = b.bid  # was: b.bid.open / b.bid.high / b.bid.low / b.bid.close で 4 回
        ask = b.ask  # was: 4 回
        o[i] = (float(bid.open) + float(ask.open)) * 0.5
        h[i] = (float(bid.high) + float(ask.high)) * 0.5
        low[i] = (float(bid.low) + float(ask.low)) * 0.5
        c[i] = (float(bid.close) + float(ask.close)) * 0.5
    return o, h, low, c


def bars_to_mid_ohlc(
    bars: Sequence[PriceBar],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """mid OHLC を返す。同一 bars list に対しては cached 結果を再利用。

    key = (id(bars), len(bars))。`_REFS[key] is bars` で identity を
    二重検査して id 再利用 false hit を防ぐ。

    **呼び出し契約 (read-only)**:
        返却される 4 つの ndarray は cache に保持された共有 object である。
        in-place 変更 (`arr[i] = x` 等) は selection invariance を破壊し
        後続の cache hit でも汚染が伝搬するため**禁止**。
        書き換えが必要な場合は明示的に `arr.copy()` してから操作すること。
        既存 caller (directional_generic / modulator_generic / pair_specific)
        は全て read-only 利用で確認済み (T030)。

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
