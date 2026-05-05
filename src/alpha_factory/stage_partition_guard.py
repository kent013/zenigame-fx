"""Stage Partition Integrity Guard (T087).

zenigame ``src/trading/alpha_factory/runner/_holdout.py`` 相当だが、
zenigame-fx では holdout 単独ではなく Stage A↔B↔Holdout 三者の partition
integrity を扱うため命名を ``stage_partition_guard`` に統一する。

仕様根拠:
- 概念設計: ``devnotes/20260505-1039-stage-ab-disjoint-and-holdout-guard/conceptual-design.md``
- 詳細設計: ``devnotes/20260505-1039-stage-ab-disjoint-and-holdout-guard/detailed-design.md``
- 学術根拠: López de Prado (2018) Ch.7 (purged k-fold + embargo)

将来の Stage A 確率化 TODO 着手時には、 :func:`_validate_chronological_partition`
を撤去して :func:`_validate_timestamp_disjoint` のみで disjoint を担保する設計に
切り替える前提（concept design B-3）。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from src.domain.price import PriceBar

__all__ = [
    "StagePartitionError",
    "StagePartitionInputError",
    "StagePartitionLeakError",
    "validate_stage_partition",
]


class StagePartitionError(RuntimeError):
    """Stage Partition Guard が検出した違反の共通基底クラス."""


class StagePartitionInputError(StagePartitionError):
    """B-0 入力健全性違反 (non_empty / timezone / not_null / monotonic / unique)."""


class StagePartitionLeakError(StagePartitionError):
    """B-1 partition 整合性違反 (chronological order / timestamp disjoint)."""


def _validate_inputs(
    bars_stage_a: list[PriceBar],
    bars_stage_b: list[PriceBar],
    bars_holdout: list[PriceBar],
) -> None:
    """B-0 入力健全性検査 (StagePartitionInputError raise)."""
    for label, bars in (
        ("stage_a", bars_stage_a),
        ("stage_b", bars_stage_b),
        ("holdout", bars_holdout),
    ):
        if not bars:
            raise StagePartitionInputError(
                f"B-0 violation: {label} is empty (3 stages all required)"
            )
        prev: datetime | None = None
        seen: set[datetime] = set()
        for i, bar in enumerate(bars):
            t = bar.bar_time
            if t is None:
                raise StagePartitionInputError(
                    f"B-0 violation: {label}[{i}].bar_time is None"
                )
            if t.tzinfo is None or t.utcoffset() != timedelta(0):
                raise StagePartitionInputError(
                    f"B-0 violation: {label}[{i}].bar_time not UTC: {t}"
                )
            if prev is not None and t < prev:
                raise StagePartitionInputError(
                    f"B-0 violation: {label}[{i}].bar_time not monotonic: "
                    f"{prev} -> {t}"
                )
            if t in seen:
                raise StagePartitionInputError(
                    f"B-0 violation: {label}[{i}].bar_time duplicate: {t}"
                )
            seen.add(t)
            prev = t


def _validate_chronological_partition(
    bars_stage_a: list[PriceBar],
    bars_stage_b: list[PriceBar],
    bars_holdout: list[PriceBar],
) -> None:
    """B-1 境界条件 1-3 (chronological partition).

    本 TODO は Stage A 末尾固定を前提に B が A より前であることを検証する。
    将来 Stage A 確率化時は本関数を撤去し、 :func:`_validate_timestamp_disjoint`
    のみで disjoint 検証する設計に切り替える。
    """
    a_min = bars_stage_a[0].bar_time
    a_max = bars_stage_a[-1].bar_time
    b_max = bars_stage_b[-1].bar_time
    h_min = bars_holdout[0].bar_time
    # 1: max(B) < min(A)
    if not (b_max < a_min):
        raise StagePartitionLeakError(
            f"B-1 cond.1 violated: max(stage_b)={b_max} >= min(stage_a)={a_min}"
        )
    # 2: max(A) < min(holdout)
    if not (a_max < h_min):
        raise StagePartitionLeakError(
            f"B-1 cond.2 violated: max(stage_a)={a_max} >= min(holdout)={h_min}"
        )
    # 3: max(B) < min(holdout) (1+2 から導出可だが冗長 fail-fast)
    if not (b_max < h_min):
        raise StagePartitionLeakError(
            f"B-1 cond.3 violated: max(stage_b)={b_max} >= min(holdout)={h_min}"
        )


def _validate_timestamp_disjoint(
    bars_stage_a: list[PriceBar],
    bars_stage_b: list[PriceBar],
    bars_holdout: list[PriceBar],
) -> None:
    """B-1 集合条件 4-6 (exact timestamp contamination)."""
    a_set = {bar.bar_time for bar in bars_stage_a}
    b_set = {bar.bar_time for bar in bars_stage_b}
    h_set = {bar.bar_time for bar in bars_holdout}
    pairs = (
        (4, "stage_a", a_set, "stage_b", b_set),
        (5, "stage_a", a_set, "holdout", h_set),
        (6, "stage_b", b_set, "holdout", h_set),
    )
    for cond_no, l1, s1, l2, s2 in pairs:
        overlap = s1 & s2
        if overlap:
            sample = sorted(overlap)[:3]
            raise StagePartitionLeakError(
                f"B-1 cond.{cond_no} violated: |{l1} ∩ {l2}|={len(overlap)} "
                f"sample={sample}"
            )


def validate_stage_partition(
    bars_stage_a: list[PriceBar],
    bars_stage_b: list[PriceBar],
    bars_holdout: list[PriceBar],
) -> None:
    """Stage A↔B↔Holdout の partition integrity を起動時に検証する fail-closed guard.

    順序:
        1. :func:`_validate_inputs` (B-0 input healthcheck)
        2. :func:`_validate_chronological_partition` (B-1 cond. 1-3)
        3. :func:`_validate_timestamp_disjoint` (B-1 cond. 4-6)

    違反時は対応する例外型を raise し escape hatch なしで起動を停止する。

    Args:
        bars_stage_a: Stage A 評価用 bars (末尾固定 / 本 TODO 前提)。
        bars_stage_b: Stage B fold + IS monitor 用 bars (Stage A 期間を除外)。
        bars_holdout: Stage C 評価用 bars (post dataset.end)。

    Raises:
        StagePartitionInputError: B-0 入力健全性違反。
        StagePartitionLeakError: B-1 partition 整合性違反。
    """
    _validate_inputs(bars_stage_a, bars_stage_b, bars_holdout)
    _validate_chronological_partition(bars_stage_a, bars_stage_b, bars_holdout)
    _validate_timestamp_disjoint(bars_stage_a, bars_stage_b, bars_holdout)
