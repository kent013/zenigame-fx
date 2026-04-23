"""RegistryEvaluator: PrimitiveEvaluator Protocol の registry ベース実装（T010 骨格）。

signal.name → registry lookup → EvaluationContext 構築 → spec.compute(ctx) の
薄い adapter。状態（キャッシュ等）は保持しない。

src/dsl/strategy.py の `PrimitiveEvaluator` Protocol を structural に満たす
（evaluate(bars, idx, signal) -> float）。

T013 拡張:
- aux_pair_bars / event_snapshot / vix_snapshot を kwarg で保持し、EvaluationContext に流す
- strict_aux_required + selected_primitive_ids で起動時 preflight verify
- preflight verify は selected primitive の required_data + optional_data_groups を
  union し、provider の有無を確認 (RuntimeError fail-fast)
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from src.alpha_factory.primitives._base import (
    EconomicEventSnapshot,
    EvaluationContext,
    VixSeriesSnapshot,
)
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
        aux_pair_bars: cross-pair 別ペアの aligned bar 列（T013 追加）。
        event_snapshot/vix_snapshot: snapshot を流すためのフィールド (T012/T013)。
        strict_snapshot_required: True なら snapshot/aux 欠損時に compute 内で
                                  RuntimeError raise（per-call strict）。
        strict_aux_required: True なら __init__ 時に selected primitive の
                             required_data / optional_data_groups を preflight verify。
                             不足あれば RuntimeError fail-fast。
        selected_primitive_ids: preflight verify 対象の primitive ID 群
                                （strict_aux_required=True なら必須）。
    """

    # bars 自体で provide される key 集合 (preflight でスキップ)
    _BARS_PROVIDED_KEYS: frozenset[str] = frozenset(
        {"ohlc", "atr", "spread", "swap", "calendar.session"}
    )

    def __init__(
        self,
        *,
        pair: str,
        aux_series: Mapping[str, Sequence[float]] | None = None,
        aux_pair_bars: Mapping[str, Sequence[PriceBar | None]] | None = None,
        event_snapshot: EconomicEventSnapshot | None = None,
        vix_snapshot: VixSeriesSnapshot | None = None,
        strict_snapshot_required: bool = False,
        strict_aux_required: bool = False,
        selected_primitive_ids: Iterable[str] | None = None,
    ) -> None:
        self._pair = pair
        # None → 空 dict（mutable shared state 回避のため毎 instance 新規作成）
        self._aux_series: Mapping[str, Sequence[float]] = (
            dict(aux_series) if aux_series is not None else {}
        )
        self._aux_pair_bars: Mapping[str, Sequence[PriceBar | None]] = (
            dict(aux_pair_bars) if aux_pair_bars is not None else {}
        )
        self._event_snapshot = event_snapshot
        self._vix_snapshot = vix_snapshot
        self._strict_snapshot_required = strict_snapshot_required
        self._strict_aux_required = strict_aux_required
        if strict_aux_required:
            if selected_primitive_ids is None:
                raise ValueError(
                    "strict_aux_required=True requires selected_primitive_ids "
                    "to be provided (preflight verify input)"
                )
            self._preflight_verify(tuple(selected_primitive_ids))

    def _is_aux_provided(self, key: str) -> bool:
        """単一 key が現 evaluator で provide されるか判定 (optional group 用)。"""
        if key in self._BARS_PROVIDED_KEYS:
            return True
        if key == "calendar.economic_event":
            return self._event_snapshot is not None
        if key == "macro.vix":
            return (
                self._vix_snapshot is not None
                and bool(self._vix_snapshot.observations)
            )
        if key.startswith("cross_pair."):
            return key[len("cross_pair."):] in self._aux_pair_bars
        if key.startswith("macro."):
            return key in self._aux_series
        return False

    def _preflight_verify(self, ids: tuple[str, ...]) -> None:
        """selected primitive 群の required_data + optional_data_groups が現 evaluator
        で provide されるか起動時に verify。不足があれば RuntimeError fail-fast。
        """
        required: set[str] = set()
        optional_groups: list[tuple[str, ...]] = []
        for pid in ids:
            spec = get_primitive(pid)
            required.update(spec.required_data)
            optional_groups.extend(spec.optional_data_groups)

        # required: 必須 key
        for key in required:
            if self._is_aux_provided(key):
                continue
            raise RuntimeError(
                f"required aux missing for selected primitives: {key} "
                "(not provided by current evaluator)"
            )

        # optional_data_groups: 各 group につき 1 つ以上 provide
        for group in optional_groups:
            if not any(self._is_aux_provided(k) for k in group):
                raise RuntimeError(
                    f"required aux missing for selected primitives: "
                    f"none of {group} is provided "
                    f"(at least one required by optional_data_groups)"
                )

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
            event_snapshot=self._event_snapshot,
            vix_snapshot=self._vix_snapshot,
            strict_snapshot_required=self._strict_snapshot_required,
            aux_pair_bars=self._aux_pair_bars,
        )
        return spec.compute(ctx)
