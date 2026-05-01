"""T060: Partition + Fold generator — 24m EpochWindow を canonical 10 領域 + 5 folds に分割.

詳細:
- 概念設計: ``devnotes/20260429-2210-todo-T060-partition-fold-generator/conceptual-design.md``
- 詳細設計: ``devnotes/20260429-2210-todo-T060-partition-fold-generator/detailed-design.md``
- synthesis § 4.3 (Partition) + § 4.4 (Stage B fold)
- T059 依存: :class:`~src.alpha_factory.epoch_manager.EpochWindow` (start, end は 00:00 UTC 固定)

Phase 1 (本 TODO = T060 PR 1): 単体実装 + テストのみ。
``walk_forward.py`` / ``stage_gate.py`` / ``swim_lane.py`` / ``run_ga.py`` /
``default.yaml`` / ``config.py`` / ``calibrate_state.py`` / ``aux_preflight.py`` /
``docs/alpha_factory/stage-gates.md`` の 9 箇所同時更新は **Phase 2 (別 PR、 T061-T064 と同時)**
で実施。 T060 PR 1 単独 merge で runtime に影響なし。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import ClassVar

# T059 EpochWindow を import (T059 merge 後前提)
from src.alpha_factory.epoch_manager import EpochWindow

__all__ = [
    "Fold",
    "FoldGenerator",
    "FoldMismatchError",
    "Partition",
    "PartitionGenerator",
    "PartitionMismatchError",
    "Period",
    "PeriodLabel",
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PartitionMismatchError(ValueError):
    """24m EpochWindow と 10 領域合計の長さ不一致 / cursor != window.end."""


class FoldMismatchError(ValueError):
    """B 62w と 5 folds の長さ不一致 / 末端 fold test.end != stage_b.end."""


# ---------------------------------------------------------------------------
# PeriodLabel — Period 命名 SSOT
# ---------------------------------------------------------------------------


class PeriodLabel(StrEnum):
    """Period 命名 SSOT (string literal 依存回避).

    Partition 用 10 ラベル + Fold suffix 構築用 3 ラベル。
    Fold ラベルは ``f"fold_{k}_{train|embargo|test}"`` の形で
    :class:`FoldGenerator` が動的に組み立てる (= Period.label に直接代入される)。
    """

    STAGE_B = "stage_b"
    STAGE_A = "stage_a"
    EMBARGO_AFTER_A = "embargo_after_a"
    STAGE_C_LITE_1 = "stage_c_lite_1"
    EMBARGO_AFTER_C_LITE_1 = "embargo_after_c_lite_1"
    STAGE_C_LITE_2 = "stage_c_lite_2"
    EMBARGO_AFTER_C_LITE_2 = "embargo_after_c_lite_2"
    STAGE_C_LITE_3 = "stage_c_lite_3"
    EMBARGO_AFTER_C_LITE_3 = "embargo_after_c_lite_3"
    STAGE_C = "stage_c"
    # Fold 用 suffix base (FoldGenerator が ``fold_{k}_{train|embargo|test}`` を生成)
    FOLD_TRAIN = "fold_train"
    FOLD_EMBARGO = "fold_embargo"
    FOLD_TEST = "fold_test"


# ---------------------------------------------------------------------------
# Period — 半開区間 [start, end)、 UTC-aware
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Period:
    """時系列上の半開区間 ``[start, end)``. UTC-aware datetime 限定.

    Round 1 [Warning] 反映: tzinfo あり に加えて ``utcoffset() == timedelta(0)``
    を要求 (= JST ``+09:00`` 等の他 timezone-aware datetime も reject)。
    T072 規範でも採用される半開区間 ``[start, end)`` を T060 でも踏襲する。
    """

    start: datetime
    end: datetime
    label: str  # PeriodLabel.value or "fold_{k}_{train|embargo|test}"

    def __post_init__(self) -> None:
        # UTC 厳密性 (Round 1 [Warning] 反映)
        for name, dt in (("start", self.start), ("end", self.end)):
            if dt.tzinfo is None:
                raise ValueError(
                    f"Period {self.label!r}: {name} must be timezone-aware datetime"
                )
            offset = dt.utcoffset()
            if offset is None or offset != timedelta(0):
                raise ValueError(
                    f"Period {self.label!r}: {name} must be UTC (utcoffset=0), "
                    f"got offset={offset}"
                )
        if self.end <= self.start:
            raise ValueError(
                f"Period {self.label!r}: end ({self.end}) must be > start ({self.start})"
            )


# ---------------------------------------------------------------------------
# Partition — 24m EpochWindow の 10 領域
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Partition:
    """24m epoch window の canonical partition (10 領域).

    時系列順:
    ``[B 62w][A 8w][emb 1w][C-lite 6w][emb 1w][C-lite 6w][emb 1w][C-lite 6w][emb 1w][C 12w]``

    合計 = 104w = 24m。 領域間に gap / overlap なし
    (= ``PartitionGenerator.generate`` で cursor 連続性を強制)。
    """

    epoch_window: EpochWindow
    stage_b: Period       # 62w
    stage_a: Period       # 8w
    embargo_after_a: Period  # 1w
    c_lite_1: Period      # 6w
    embargo_1: Period     # 1w
    c_lite_2: Period      # 6w
    embargo_2: Period     # 1w
    c_lite_3: Period      # 6w
    embargo_3: Period     # 1w
    stage_c: Period       # 12w

    @property
    def all_periods(self) -> list[Period]:
        """時系列順の全 10 領域 (overlap なし、 隙間なし)."""
        return [
            self.stage_b,
            self.stage_a,
            self.embargo_after_a,
            self.c_lite_1,
            self.embargo_1,
            self.c_lite_2,
            self.embargo_2,
            self.c_lite_3,
            self.embargo_3,
            self.stage_c,
        ]

    @property
    def c_lite_periods(self) -> tuple[Period, Period, Period]:
        """3 disjoint C-lite windows."""
        return (self.c_lite_1, self.c_lite_2, self.c_lite_3)


# ---------------------------------------------------------------------------
# PartitionGenerator
# ---------------------------------------------------------------------------


class PartitionGenerator:
    """EpochWindow から canonical Partition を生成.

    synthesis § 4.3 確定の 10 領域構造を deterministic に生成:
    ``[B 62w][A 8w][emb 1w][C-lite 6w][emb 1w][C-lite 6w][emb 1w][C-lite 6w][emb 1w][C 12w]``
    合計 = 104w
    """

    STAGE_B_WEEKS: ClassVar[int] = 62
    STAGE_A_WEEKS: ClassVar[int] = 8
    EMBARGO_WEEKS: ClassVar[int] = 1
    C_LITE_WEEKS: ClassVar[int] = 6
    STAGE_C_WEEKS: ClassVar[int] = 12

    @classmethod
    def generate(cls, window: EpochWindow) -> Partition:
        """``window.start`` を起点に時系列順で 10 領域を切り出す.

        Args:
            window: 24m (= 104w) の :class:`EpochWindow`。

        Raises:
            PartitionMismatchError: window 長と 10 領域合計が不一致、
                または cursor != window.end (gap / overlap)。
        """
        # 不変条件: 10 領域合計 == window 長 (timedelta 厳密一致)
        total_weeks = (
            cls.STAGE_B_WEEKS + cls.STAGE_A_WEEKS + cls.EMBARGO_WEEKS
            + cls.C_LITE_WEEKS + cls.EMBARGO_WEEKS
            + cls.C_LITE_WEEKS + cls.EMBARGO_WEEKS
            + cls.C_LITE_WEEKS + cls.EMBARGO_WEEKS
            + cls.STAGE_C_WEEKS
        )
        expected_span = timedelta(weeks=total_weeks)
        actual_span = window.end - window.start
        if actual_span != expected_span:
            raise PartitionMismatchError(
                f"window span {actual_span} != expected {expected_span} "
                f"({total_weeks}w)"
            )

        cursor = window.start

        def _slice(weeks: int, label: PeriodLabel) -> Period:
            nonlocal cursor
            end = cursor + timedelta(weeks=weeks)
            p = Period(start=cursor, end=end, label=label.value)
            cursor = end
            return p

        partition = Partition(
            epoch_window=window,
            stage_b=_slice(cls.STAGE_B_WEEKS, PeriodLabel.STAGE_B),
            stage_a=_slice(cls.STAGE_A_WEEKS, PeriodLabel.STAGE_A),
            embargo_after_a=_slice(cls.EMBARGO_WEEKS, PeriodLabel.EMBARGO_AFTER_A),
            c_lite_1=_slice(cls.C_LITE_WEEKS, PeriodLabel.STAGE_C_LITE_1),
            embargo_1=_slice(cls.EMBARGO_WEEKS, PeriodLabel.EMBARGO_AFTER_C_LITE_1),
            c_lite_2=_slice(cls.C_LITE_WEEKS, PeriodLabel.STAGE_C_LITE_2),
            embargo_2=_slice(cls.EMBARGO_WEEKS, PeriodLabel.EMBARGO_AFTER_C_LITE_2),
            c_lite_3=_slice(cls.C_LITE_WEEKS, PeriodLabel.STAGE_C_LITE_3),
            embargo_3=_slice(cls.EMBARGO_WEEKS, PeriodLabel.EMBARGO_AFTER_C_LITE_3),
            stage_c=_slice(cls.STAGE_C_WEEKS, PeriodLabel.STAGE_C),
        )
        if cursor != window.end:
            raise PartitionMismatchError(
                f"partition cursor {cursor} != window.end {window.end} "
                "(gap or overlap)"
            )
        return partition


# ---------------------------------------------------------------------------
# Fold — Stage B 1 fold (train, embargo, test)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fold:
    """Stage B 1 fold の (train, embargo, test) 区間.

    連続性: ``train.end == embargo.start`` / ``embargo.end == test.start``。
    """

    fold_index: int
    train: Period
    embargo: Period
    test: Period

    def __post_init__(self) -> None:
        if self.fold_index < 0:
            raise ValueError(f"fold_index must be >= 0: {self.fold_index}")
        # 連続性 (gap なし): train.end == embargo.start, embargo.end == test.start
        if self.train.end != self.embargo.start:
            raise ValueError(
                f"fold {self.fold_index}: train.end ({self.train.end}) "
                f"!= embargo.start ({self.embargo.start})"
            )
        if self.embargo.end != self.test.start:
            raise ValueError(
                f"fold {self.fold_index}: embargo.end ({self.embargo.end}) "
                f"!= test.start ({self.test.start})"
            )


# ---------------------------------------------------------------------------
# FoldGenerator
# ---------------------------------------------------------------------------


class FoldGenerator:
    """Stage B 62w から rolling-origin で 5 folds を生成.

    fold 構造: ``train 36w + embargo 1w + test 5w + step 5w → 5 folds``。

    fold ``k`` (k=0..4):
        train  = ``[k*5w, k*5w + 36w)``
        embargo = ``[k*5w + 36w, k*5w + 37w)``
        test   = ``[k*5w + 37w, k*5w + 42w)``

    最終 fold (k=4) ``test.end = 4*5 + 42 = 62w`` → ``stage_b.end`` と一致。
    """

    TRAIN_WEEKS: ClassVar[int] = 36
    EMBARGO_WEEKS: ClassVar[int] = 1
    TEST_WEEKS: ClassVar[int] = 5
    STEP_WEEKS: ClassVar[int] = 5
    NUM_FOLDS: ClassVar[int] = 5

    @classmethod
    def generate(cls, stage_b: Period) -> tuple[Fold, ...]:
        """Stage B period から 5 folds を時系列順で生成.

        Args:
            stage_b: ``label == "stage_b"`` の :class:`Period` (62w)。

        Raises:
            ValueError: ``stage_b.label`` が ``"stage_b"`` 以外。
            FoldMismatchError: ``stage_b`` 長が期待値と不一致、
                または末端 fold ``test.end != stage_b.end``。
        """
        if stage_b.label != PeriodLabel.STAGE_B.value:
            raise ValueError(
                f"FoldGenerator expects {PeriodLabel.STAGE_B.value!r} period, "
                f"got {stage_b.label!r}"
            )
        # 不変条件: 5 fold 合計 = 62w (timedelta 厳密一致)
        last_fold_end_weeks = (
            (cls.NUM_FOLDS - 1) * cls.STEP_WEEKS
            + cls.TRAIN_WEEKS + cls.EMBARGO_WEEKS + cls.TEST_WEEKS
        )
        expected_b_span = timedelta(weeks=last_fold_end_weeks)
        actual_b_span = stage_b.end - stage_b.start
        if actual_b_span != expected_b_span:
            raise FoldMismatchError(
                f"stage_b span {actual_b_span} != expected {expected_b_span} "
                f"(5-fold structure spans {last_fold_end_weeks}w)"
            )

        folds: list[Fold] = []
        for k in range(cls.NUM_FOLDS):
            train_start = stage_b.start + timedelta(weeks=k * cls.STEP_WEEKS)
            train_end = train_start + timedelta(weeks=cls.TRAIN_WEEKS)
            embargo_end = train_end + timedelta(weeks=cls.EMBARGO_WEEKS)
            test_end = embargo_end + timedelta(weeks=cls.TEST_WEEKS)
            folds.append(
                Fold(
                    fold_index=k,
                    train=Period(
                        start=train_start,
                        end=train_end,
                        label=f"fold_{k}_{PeriodLabel.FOLD_TRAIN.value}",
                    ),
                    embargo=Period(
                        start=train_end,
                        end=embargo_end,
                        label=f"fold_{k}_{PeriodLabel.FOLD_EMBARGO.value}",
                    ),
                    test=Period(
                        start=embargo_end,
                        end=test_end,
                        label=f"fold_{k}_{PeriodLabel.FOLD_TEST.value}",
                    ),
                )
            )
        if folds[-1].test.end != stage_b.end:
            raise FoldMismatchError(
                f"last fold test.end {folds[-1].test.end} "
                f"!= stage_b.end {stage_b.end}"
            )
        return tuple(folds)
