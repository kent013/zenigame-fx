"""Stage B inconclusive 判定 helper (T087).

`n_fold_effective < 3` を inconclusive と判定する shared utility。
summary 生成 / run report 表示 / archive consumer の三層で同じ規則を共有する。

仕様根拠:
- 概念設計: ``devnotes/20260505-1039-stage-ab-disjoint-and-holdout-guard/conceptual-design.md``
- 詳細設計: ``devnotes/20260505-1039-stage-ab-disjoint-and-holdout-guard/detailed-design.md``
"""
from __future__ import annotations

import math
from numbers import Integral

__all__ = ["is_stage_b_inconclusive"]


def is_stage_b_inconclusive(n_fold_effective: object) -> bool:
    """``n_fold_effective < 3`` を inconclusive と判定する.

    - ``None`` / 非整数 / NaN / ``bool`` は保守的に True (inconclusive)。
    - ``numpy.integer`` (``np.int64`` 等) は :class:`numbers.Integral` として
      正常に扱う。
    - ``bool`` は :class:`Integral` のサブクラスだが意図しないため明示除外。

    Args:
        n_fold_effective: Stage B fold の effective 数 (型は archive 行 / summary
            value / 実数値 など caller に依存し、 object として受ける)。

    Returns:
        ``True`` なら inconclusive (Stage B 判定の統計的弱さを示す)。
    """
    if n_fold_effective is None:
        return True
    if isinstance(n_fold_effective, bool):
        return True
    if isinstance(n_fold_effective, float) and math.isnan(n_fold_effective):
        return True
    if not isinstance(n_fold_effective, Integral):
        return True
    return int(n_fold_effective) < 3
