"""T060: ``partition.py`` の振る舞いテスト.

詳細設計: ``devnotes/20260429-2210-todo-T060-partition-fold-generator/detailed-design.md``
施策 2 (行 392-451)。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from itertools import pairwise

import pytest

from src.alpha_factory.epoch_manager import EpochWindow
from src.alpha_factory.partition import (
    Fold,
    FoldGenerator,
    FoldMismatchError,
    Partition,
    PartitionGenerator,
    PartitionMismatchError,
    Period,
    PeriodLabel,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _utc(year: int, month: int, day: int) -> datetime:
    """UTC midnight 固定 datetime."""
    return datetime(year, month, day, tzinfo=UTC)


def _canonical_24m_window() -> EpochWindow:
    """24m (= 104w) の canonical EpochWindow."""
    start = _utc(2024, 4, 1)
    return EpochWindow(start=start, end=start + timedelta(weeks=104))


def _canonical_stage_b(window: EpochWindow | None = None) -> Period:
    """canonical 62w Stage B period."""
    win = window or _canonical_24m_window()
    return Period(
        start=win.start,
        end=win.start + timedelta(weeks=62),
        label=PeriodLabel.STAGE_B.value,
    )


# ---------------------------------------------------------------------------
# Period
# ---------------------------------------------------------------------------


def test_period_rejects_naive_datetime_for_start_or_end() -> None:
    naive = datetime(2024, 4, 1)
    aware = _utc(2024, 4, 8)
    with pytest.raises(ValueError, match=r"timezone-aware"):
        Period(start=naive, end=aware, label="stage_a")
    with pytest.raises(ValueError, match=r"timezone-aware"):
        Period(start=aware, end=datetime(2024, 4, 15), label="stage_a")


def test_period_rejects_end_le_start() -> None:
    same = _utc(2024, 4, 1)
    with pytest.raises(ValueError, match=r"end .* must be > start"):
        Period(start=same, end=same, label="stage_a")
    with pytest.raises(ValueError, match=r"end .* must be > start"):
        Period(
            start=_utc(2024, 4, 8),
            end=_utc(2024, 4, 1),
            label="stage_a",
        )


def test_period_accepts_utc_aware_datetime() -> None:
    p = Period(
        start=_utc(2024, 4, 1),
        end=_utc(2024, 4, 8),
        label="stage_a",
    )
    assert p.label == "stage_a"
    assert p.end - p.start == timedelta(weeks=1)


def test_period_rejects_jst_aware_datetime() -> None:
    """Round 1 [Suggestion] 2: JST (+09:00) は UTC ではないため reject."""
    jst = timezone(timedelta(hours=9))
    start = datetime(2024, 4, 1, tzinfo=jst)
    end = datetime(2024, 4, 8, tzinfo=jst)
    with pytest.raises(ValueError, match=r"UTC"):
        Period(start=start, end=end, label="stage_a")


def test_period_rejects_pacific_aware_datetime() -> None:
    """Round 1 [Suggestion] 2: 任意 non-UTC timezone-aware も reject."""
    pacific = timezone(timedelta(hours=-8))
    start = datetime(2024, 4, 1, tzinfo=pacific)
    end = datetime(2024, 4, 8, tzinfo=pacific)
    with pytest.raises(ValueError, match=r"UTC"):
        Period(start=start, end=end, label="stage_a")


def test_period_label_string_value_is_period_label_value() -> None:
    p = Period(
        start=_utc(2024, 4, 1),
        end=_utc(2024, 4, 8),
        label=PeriodLabel.STAGE_A.value,
    )
    assert p.label == "stage_a"
    assert p.label == PeriodLabel.STAGE_A


# ---------------------------------------------------------------------------
# PeriodLabel
# ---------------------------------------------------------------------------


def test_period_label_values_are_lowercase_alphanumeric_underscore() -> None:
    import re
    pattern = re.compile(r"^[a-z0-9_]+$")
    for member in PeriodLabel:
        assert pattern.fullmatch(member.value), member.value


def test_all_partition_labels_distinct() -> None:
    """全 13 値の重複なし (Partition 10 + Fold suffix base 3)."""
    values = [member.value for member in PeriodLabel]
    assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# Partition
# ---------------------------------------------------------------------------


def test_all_periods_returns_ten_periods_in_chronological_order() -> None:
    partition = PartitionGenerator.generate(_canonical_24m_window())
    periods = partition.all_periods
    assert len(periods) == 10
    for prev, nxt in pairwise(periods):
        assert prev.end <= nxt.start


def test_all_periods_have_no_gap_or_overlap() -> None:
    partition = PartitionGenerator.generate(_canonical_24m_window())
    periods = partition.all_periods
    for prev, nxt in pairwise(periods):
        assert prev.end == nxt.start


def test_c_lite_periods_returns_three_disjoint_windows() -> None:
    partition = PartitionGenerator.generate(_canonical_24m_window())
    c1, c2, c3 = partition.c_lite_periods
    assert c1.end <= c2.start
    assert c2.end <= c3.start
    for c in (c1, c2, c3):
        assert c.end - c.start == timedelta(weeks=PartitionGenerator.C_LITE_WEEKS)


# ---------------------------------------------------------------------------
# PartitionGenerator
# ---------------------------------------------------------------------------


def test_generate_24m_window_produces_canonical_10_region_partition() -> None:
    window = _canonical_24m_window()
    partition = PartitionGenerator.generate(window)
    assert isinstance(partition, Partition)
    assert partition.epoch_window == window
    assert len(partition.all_periods) == 10
    assert partition.stage_b.label == PeriodLabel.STAGE_B.value
    assert partition.stage_a.label == PeriodLabel.STAGE_A.value
    assert partition.embargo_after_a.label == PeriodLabel.EMBARGO_AFTER_A.value
    assert partition.c_lite_1.label == PeriodLabel.STAGE_C_LITE_1.value
    assert partition.embargo_1.label == PeriodLabel.EMBARGO_AFTER_C_LITE_1.value
    assert partition.c_lite_2.label == PeriodLabel.STAGE_C_LITE_2.value
    assert partition.embargo_2.label == PeriodLabel.EMBARGO_AFTER_C_LITE_2.value
    assert partition.c_lite_3.label == PeriodLabel.STAGE_C_LITE_3.value
    assert partition.embargo_3.label == PeriodLabel.EMBARGO_AFTER_C_LITE_3.value
    assert partition.stage_c.label == PeriodLabel.STAGE_C.value


def test_generate_total_length_equals_window_span_104w() -> None:
    window = _canonical_24m_window()
    partition = PartitionGenerator.generate(window)
    total = partition.stage_c.end - partition.stage_b.start
    assert total == timedelta(weeks=104)
    assert total == window.end - window.start


def test_generate_raises_partition_mismatch_when_window_too_short() -> None:
    start = _utc(2024, 4, 1)
    short_window = EpochWindow(start=start, end=start + timedelta(weeks=100))
    with pytest.raises(PartitionMismatchError, match=r"window span"):
        PartitionGenerator.generate(short_window)


def test_generate_raises_partition_mismatch_when_window_too_long() -> None:
    start = _utc(2024, 4, 1)
    long_window = EpochWindow(start=start, end=start + timedelta(weeks=110))
    with pytest.raises(PartitionMismatchError, match=r"window span"):
        PartitionGenerator.generate(long_window)


def test_generate_stage_b_is_first_62w_after_window_start() -> None:
    window = _canonical_24m_window()
    partition = PartitionGenerator.generate(window)
    assert partition.stage_b.start == window.start
    assert partition.stage_b.end - partition.stage_b.start == timedelta(weeks=62)


def test_generate_stage_a_follows_stage_b_with_no_gap() -> None:
    partition = PartitionGenerator.generate(_canonical_24m_window())
    assert partition.stage_a.start == partition.stage_b.end
    assert partition.stage_a.end - partition.stage_a.start == timedelta(weeks=8)


def test_generate_stage_c_is_final_12w_ending_at_window_end() -> None:
    window = _canonical_24m_window()
    partition = PartitionGenerator.generate(window)
    assert partition.stage_c.end == window.end
    assert partition.stage_c.end - partition.stage_c.start == timedelta(weeks=12)


def test_generate_three_c_lite_windows_separated_by_1w_embargo() -> None:
    partition = PartitionGenerator.generate(_canonical_24m_window())
    # c_lite_1 → embargo_1 (1w) → c_lite_2 → embargo_2 (1w) → c_lite_3
    assert partition.embargo_1.start == partition.c_lite_1.end
    assert partition.embargo_1.end == partition.c_lite_2.start
    assert partition.embargo_1.end - partition.embargo_1.start == timedelta(weeks=1)
    assert partition.embargo_2.start == partition.c_lite_2.end
    assert partition.embargo_2.end == partition.c_lite_3.start
    assert partition.embargo_2.end - partition.embargo_2.start == timedelta(weeks=1)


def test_generate_periods_match_expected_label_order_and_week_lengths() -> None:
    """Codex Round 1 H2 反映: 10 領域の label 順 + 期待週数 (62/8/1/6/1/6/1/6/1/12)
    を fix list で固定検証. 順序入替 / 週数誤りで fail.
    """
    partition = PartitionGenerator.generate(_canonical_24m_window())
    expected: tuple[tuple[PeriodLabel, int], ...] = (
        (PeriodLabel.STAGE_B, 62),
        (PeriodLabel.STAGE_A, 8),
        (PeriodLabel.EMBARGO_AFTER_A, 1),
        (PeriodLabel.STAGE_C_LITE_1, 6),
        (PeriodLabel.EMBARGO_AFTER_C_LITE_1, 1),
        (PeriodLabel.STAGE_C_LITE_2, 6),
        (PeriodLabel.EMBARGO_AFTER_C_LITE_2, 1),
        (PeriodLabel.STAGE_C_LITE_3, 6),
        (PeriodLabel.EMBARGO_AFTER_C_LITE_3, 1),
        (PeriodLabel.STAGE_C, 12),
    )
    actual = partition.all_periods
    assert len(actual) == len(expected)
    for period, (expected_label, expected_weeks) in zip(actual, expected, strict=True):
        assert period.label == expected_label.value, (
            f"label {period.label} != {expected_label.value}"
        )
        assert period.end - period.start == timedelta(weeks=expected_weeks), (
            f"{expected_label.value}: "
            f"span {period.end - period.start} != {expected_weeks}w"
        )


def test_generate_period_starts_match_cumulative_week_offsets_inline_window() -> None:
    """Codex Round 1 H5 反映 (helper 非依存): inline で datetime 直接構築した
    window から partition 生成し、 各 period の start を window.start からの
    累積週数オフセットと比較. _canonical_24m_window helper を使わず独立検証.
    """
    # 2025-01-01T00:00 UTC 起点、 + 104 週 (= 2026-12-31T00:00)
    window_start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
    window_end = window_start + timedelta(weeks=104)
    partition = PartitionGenerator.generate(
        EpochWindow(start=window_start, end=window_end)
    )
    # 期待累積オフセット (週、 0 始点): [0, 62, 70, 71, 77, 78, 84, 85, 91, 92]
    # 各 period の start は window_start + offset 週
    expected_offsets_weeks = (0, 62, 70, 71, 77, 78, 84, 85, 91, 92)
    actual = partition.all_periods
    assert len(actual) == len(expected_offsets_weeks)
    for period, offset_weeks in zip(actual, expected_offsets_weeks, strict=True):
        expected_start = window_start + timedelta(weeks=offset_weeks)
        assert period.start == expected_start, (
            f"{period.label}: "
            f"start {period.start} != {expected_start} "
            f"(window_start + {offset_weeks}w)"
        )
    # 末尾 period (stage_c) end が window.end と一致
    assert actual[-1].end == window_end


# ---------------------------------------------------------------------------
# Fold
# ---------------------------------------------------------------------------


def test_fold_rejects_negative_fold_index() -> None:
    train = Period(
        start=_utc(2024, 4, 1),
        end=_utc(2024, 4, 8),
        label="fold_-1_train",
    )
    embargo = Period(start=train.end, end=train.end + timedelta(weeks=1), label="fold_-1_embargo")
    test = Period(start=embargo.end, end=embargo.end + timedelta(weeks=1), label="fold_-1_test")
    with pytest.raises(ValueError, match=r"fold_index must be >= 0"):
        Fold(fold_index=-1, train=train, embargo=embargo, test=test)


def test_fold_rejects_train_end_not_equal_to_embargo_start() -> None:
    train = Period(
        start=_utc(2024, 4, 1),
        end=_utc(2024, 4, 8),
        label="fold_0_train",
    )
    # embargo.start が train.end からズレている (gap)
    embargo = Period(
        start=_utc(2024, 4, 9),
        end=_utc(2024, 4, 16),
        label="fold_0_embargo",
    )
    test = Period(
        start=embargo.end,
        end=embargo.end + timedelta(weeks=1),
        label="fold_0_test",
    )
    with pytest.raises(ValueError, match=r"train\.end .* != embargo\.start"):
        Fold(fold_index=0, train=train, embargo=embargo, test=test)


def test_fold_rejects_embargo_end_not_equal_to_test_start() -> None:
    train = Period(
        start=_utc(2024, 4, 1),
        end=_utc(2024, 4, 8),
        label="fold_0_train",
    )
    embargo = Period(
        start=train.end,
        end=_utc(2024, 4, 15),
        label="fold_0_embargo",
    )
    # test.start が embargo.end からズレている (gap)
    test = Period(
        start=_utc(2024, 4, 22),
        end=_utc(2024, 4, 29),
        label="fold_0_test",
    )
    with pytest.raises(ValueError, match=r"embargo\.end .* != test\.start"):
        Fold(fold_index=0, train=train, embargo=embargo, test=test)


# ---------------------------------------------------------------------------
# FoldGenerator
# ---------------------------------------------------------------------------


def test_generate_produces_5_folds_for_62w_stage_b() -> None:
    folds = FoldGenerator.generate(_canonical_stage_b())
    assert len(folds) == FoldGenerator.NUM_FOLDS == 5
    for k, fold in enumerate(folds):
        assert fold.fold_index == k


def test_generate_raises_value_error_when_label_is_not_stage_b() -> None:
    bad = Period(
        start=_utc(2024, 4, 1),
        end=_utc(2024, 4, 1) + timedelta(weeks=62),
        label="stage_a",  # 不正 label
    )
    with pytest.raises(ValueError, match=r"FoldGenerator expects"):
        FoldGenerator.generate(bad)


def test_generate_raises_fold_mismatch_when_stage_b_too_short() -> None:
    short = Period(
        start=_utc(2024, 4, 1),
        end=_utc(2024, 4, 1) + timedelta(weeks=50),
        label=PeriodLabel.STAGE_B.value,
    )
    with pytest.raises(FoldMismatchError, match=r"stage_b span"):
        FoldGenerator.generate(short)


def test_generate_raises_fold_mismatch_when_stage_b_too_long() -> None:
    long = Period(
        start=_utc(2024, 4, 1),
        end=_utc(2024, 4, 1) + timedelta(weeks=70),
        label=PeriodLabel.STAGE_B.value,
    )
    with pytest.raises(FoldMismatchError, match=r"stage_b span"):
        FoldGenerator.generate(long)


def test_fold_train_length_is_36_weeks_for_each_fold() -> None:
    folds = FoldGenerator.generate(_canonical_stage_b())
    for fold in folds:
        assert fold.train.end - fold.train.start == timedelta(weeks=36)


def test_fold_embargo_length_is_1_week_for_each_fold() -> None:
    folds = FoldGenerator.generate(_canonical_stage_b())
    for fold in folds:
        assert fold.embargo.end - fold.embargo.start == timedelta(weeks=1)


def test_fold_test_length_is_5_weeks_for_each_fold() -> None:
    folds = FoldGenerator.generate(_canonical_stage_b())
    for fold in folds:
        assert fold.test.end - fold.test.start == timedelta(weeks=5)


def test_fold_step_is_5_weeks_between_consecutive_folds() -> None:
    folds = FoldGenerator.generate(_canonical_stage_b())
    for prev, nxt in pairwise(folds):
        assert nxt.train.start - prev.train.start == timedelta(weeks=5)
        assert nxt.test.start - prev.test.start == timedelta(weeks=5)


def test_first_fold_train_starts_at_stage_b_start() -> None:
    stage_b = _canonical_stage_b()
    folds = FoldGenerator.generate(stage_b)
    assert folds[0].train.start == stage_b.start


def test_last_fold_test_ends_at_stage_b_end() -> None:
    stage_b = _canonical_stage_b()
    folds = FoldGenerator.generate(stage_b)
    assert folds[-1].test.end == stage_b.end


def test_consecutive_fold_test_periods_are_disjoint() -> None:
    """rolling-origin: 5w step + 5w test なので test 期間は隣接 (gap=0)、 重複なし."""
    folds = FoldGenerator.generate(_canonical_stage_b())
    for prev, nxt in pairwise(folds):
        # test 期間は重複しない (= 半開区間 [start, end) で end <= start なら disjoint)
        assert prev.test.end <= nxt.test.start


# ---------------------------------------------------------------------------
# 統合 (Partition → Fold)
# ---------------------------------------------------------------------------


def test_partition_generator_then_fold_generator_chain_produces_104w_with_5_folds() -> None:
    window = _canonical_24m_window()
    partition = PartitionGenerator.generate(window)
    folds = FoldGenerator.generate(partition.stage_b)

    # Partition: 24m = 104w span が成立
    total_partition_span = partition.stage_c.end - partition.stage_b.start
    assert total_partition_span == timedelta(weeks=104)

    # Fold: stage_b 内に 5 folds 全部収まる
    assert len(folds) == 5
    assert folds[0].train.start == partition.stage_b.start
    assert folds[-1].test.end == partition.stage_b.end

    # Fold test 期間は stage_a 開始より手前 (= stage_b.end と一致)
    assert folds[-1].test.end == partition.stage_a.start
