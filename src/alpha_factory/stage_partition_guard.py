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
    "StagePartitionHoldoutLengthError",
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


class StagePartitionHoldoutLengthError(StagePartitionError):
    """B-2 holdout 長違反 (config holdout_days vs 実態 calendar span 不整合).

    T091 cycle_phase1 段階 3 (2026-05-09): Stage C holdout の構造的不足を起動時
    fail-closed で検出。 二重 opt-in (`--allow-holdout-short` CLI flag AND
    `ZENIGAME_FX_SMOKE_TEST=1` env var) で smoke test 経路は WARN のみで通す。
    """


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


def _validate_holdout_length(
    bars_holdout: list[PriceBar],
    expected_days: int,
    *,
    tolerance: float = 0.8,
) -> None:
    """B-2 holdout 長検証 (T091 cycle_phase1 段階 3、 2026-05-09).

    bars_holdout の最初/最後の bar_time から実 calendar span を計算し、
    expected_days * tolerance (default 80%) 未満なら fail。 weekend/holiday
    考慮は単純化 (FX は 24x5 trading)、 buffer 20% で吸収。

    Args:
        bars_holdout: Stage C 評価用 bars (空であってはならない、 _validate_inputs で既に保証)。
        expected_days: config stage_c.holdout_days で要求される calendar 日数。
        tolerance: 実日数 / expected の最低比率 (default 0.8 = 80%)。

    Raises:
        StagePartitionHoldoutLengthError: 実日数 < expected_days * tolerance のとき。
    """
    span = bars_holdout[-1].bar_time - bars_holdout[0].bar_time
    actual_days = span.total_seconds() / 86400.0
    threshold = expected_days * tolerance
    if actual_days < threshold:
        raise StagePartitionHoldoutLengthError(
            f"B-2 violation: holdout actual span {actual_days:.1f} days "
            f"< expected {expected_days} days * {tolerance:.0%} = {threshold:.1f} days "
            f"(holdout_first={bars_holdout[0].bar_time}, "
            f"holdout_last={bars_holdout[-1].bar_time}). "
            f"Use --allow-holdout-short CLI flag AND ZENIGAME_FX_SMOKE_TEST=1 env var "
            f"for smoke tests, or extend dataset for production RUN."
        )


def validate_stage_partition(
    bars_stage_a: list[PriceBar],
    bars_stage_b: list[PriceBar],
    bars_holdout: list[PriceBar],
    *,
    expected_holdout_days: int | None = None,
    allow_holdout_short: bool = False,
) -> None:
    """Stage A↔B↔Holdout の partition integrity を起動時に検証する fail-closed guard.

    順序:
        1. :func:`_validate_inputs` (B-0 input healthcheck)
        2. :func:`_validate_chronological_partition` (B-1 cond. 1-3)
        3. :func:`_validate_timestamp_disjoint` (B-1 cond. 4-6)
        4. :func:`_validate_holdout_length` (B-2 holdout 長検証、 T091 段階 3)

    違反時は対応する例外型を raise し escape hatch なしで起動を停止する
    (B-2 のみ ``allow_holdout_short=True`` で WARN のみで通す escape hatch あり)。

    Args:
        bars_stage_a: Stage A 評価用 bars (末尾固定 / 本 TODO 前提)。
        bars_stage_b: Stage B fold + IS monitor 用 bars (Stage A 期間を除外)。
        bars_holdout: Stage C 評価用 bars (post dataset.end)。
        expected_holdout_days: config stage_c.holdout_days (T091 段階 3、
            None の場合 B-2 検証 skip = 後方互換)。
        allow_holdout_short: 二重 opt-in escape hatch (T091 段階 3、
            CLI `--allow-holdout-short` AND env `ZENIGAME_FX_SMOKE_TEST=1` で
            run_ga.py 側が True を渡す)。 True でも WARN log は残す。

    Raises:
        StagePartitionInputError: B-0 入力健全性違反。
        StagePartitionLeakError: B-1 partition 整合性違反。
        StagePartitionHoldoutLengthError: B-2 holdout 長違反 (allow_holdout_short=False 時のみ)。
    """
    _validate_inputs(bars_stage_a, bars_stage_b, bars_holdout)
    _validate_chronological_partition(bars_stage_a, bars_stage_b, bars_holdout)
    _validate_timestamp_disjoint(bars_stage_a, bars_stage_b, bars_holdout)
    if expected_holdout_days is not None:
        try:
            _validate_holdout_length(bars_holdout, expected_holdout_days)
        except StagePartitionHoldoutLengthError as e:
            if allow_holdout_short:
                import logging

                logging.warning(
                    "stage_partition_guard.holdout_short_override_active: %s", e
                )
                return
            raise
