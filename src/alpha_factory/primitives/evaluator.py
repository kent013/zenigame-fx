"""RegistryEvaluator: PrimitiveEvaluator Protocol の registry ベース実装（T010 骨格）。

signal.name → registry lookup → EvaluationContext 構築 → spec.compute(ctx) の
薄い adapter。状態（キャッシュ等）は保持しない。

src/dsl/strategy.py の `PrimitiveEvaluator` Protocol を structural に満たす
（evaluate(bars, idx, signal) -> float）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from src.alpha_factory.primitives._base import EvaluationContext
from src.alpha_factory.primitives._registry import get_primitive
from src.domain.price import PriceBar
from src.dsl.genome import SignalConfig


class RegistryEvaluator:
    """PrimitiveEvaluator Protocol (src/dsl/strategy.py) の実装。

    registry に登録された PrimitiveSpec を lookup し、EvaluationContext を
    構築して compute を呼ぶ。

    Attributes:
        pair: 評価対象の通貨ペア名（pair_specific primitive が参照）。
        aux_series: 補助時系列 Mapping（本 TODO では呼び出し側が直接用意）。
    """

    def __init__(
        self,
        *,
        pair: str,
        aux_series: Mapping[str, Sequence[float]] | None = None,
    ) -> None:
        self._pair = pair
        # None → 空 dict（mutable shared state 回避のため毎 instance 新規作成）
        if aux_series is None:
            self._aux_series: Mapping[str, Sequence[float]] = {}
        else:
            self._aux_series = dict(aux_series)

    def evaluate(
        self, bars: list[PriceBar], idx: int, signal: SignalConfig
    ) -> float:
        """PrimitiveEvaluator Protocol の実装。

        Raises:
            KeyError: signal.name が registry に無い場合（get_primitive が raise）。
        """
        spec = get_primitive(signal.name)
        ctx = EvaluationContext(
            bars=bars,
            idx=idx,
            pair=self._pair,
            params=signal.params,
            aux_series=self._aux_series,
        )
        return spec.compute(ctx)
