"""T069: epoch 内 calibrate-gate freeze 判定 (3 Run freeze 規範).

`dataset_epoch_id` を scope key として、 同 epoch 内の最初 `freeze_window` 個
distinct Run は calibrate-gate を **freeze** (= threshold 適用なし、
``decision="skip_frozen"``)。 4 Run 目以降から通常の `tighten` / `loosen`
判定が有効化される。

T069 PR は **library 層のみ** を提供する純関数。 CLI 配線
(``scripts/alpha_factory/calibrate_gate.py``) は Phase 2 別 PR。

設計:
    - devnotes/20260430-1700-todo-T069-calibrate-gate-scope/conceptual-design.md
    - devnotes/20260430-1700-todo-T069-calibrate-gate-scope/detailed-design.md

主な公開 API:
    - :class:`FreezeStatus`
    - :func:`evaluate_freeze_status`
    - :func:`decide_with_freeze`
    - :data:`DEFAULT_FREEZE_WINDOW`
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

import structlog

from src.alpha_factory.calibrate_gate import (
    AggregatedSample,
    CalibrateConfig,
    Decision,
    decide,
)
from src.alpha_factory.calibrate_gate_history import HistoryRecord

__all__ = [
    "DEFAULT_FREEZE_WINDOW",
    "FreezeStatus",
    "decide_with_freeze",
    "evaluate_freeze_status",
]

logger = structlog.get_logger(__name__)


DEFAULT_FREEZE_WINDOW: Final[int] = 3
"""凍結窓サイズ (synthesis § 8.6 SSOT)."""


_FROZEN_DECISION_LABEL: Final[Literal["skip_frozen"]] = "skip_frozen"
"""freeze 判定時の Decision.decision ラベル (DecisionLabel と同期)."""


@dataclass(frozen=True)
class FreezeStatus:
    """epoch 内 calibrate-gate freeze 判定結果 (immutable, pure data).

    SSOT: 概念設計 §4.1.

    Attributes:
        is_frozen: epoch 内 distinct run count が freeze_window 未満なら True.
        epoch_distinct_run_count: 現 dataset_epoch_id にマッチした
            distinct ``applied_from_run_id`` 数 (T077 で必須化により None /
            空文字 record は HistoryRecord.__post_init__ で type level reject).
        freeze_window: 凍結窓サイズ (synthesis § 8.6 で 3 確定).
        next_run_index_in_epoch: 現 Run が epoch 内で何 Run 目になるか
            (1-indexed, = ``epoch_distinct_run_count + 1``).

    不変条件 (``__post_init__`` で検証):
        ``is_frozen`` ⇔ (``epoch_distinct_run_count < freeze_window``)
        ``next_run_index_in_epoch == epoch_distinct_run_count + 1``
        ``freeze_window >= 1``
        ``epoch_distinct_run_count >= 0``
    """

    is_frozen: bool
    epoch_distinct_run_count: int
    freeze_window: int
    next_run_index_in_epoch: int

    def __post_init__(self) -> None:
        if self.freeze_window < 1:
            raise ValueError(
                f"freeze_window must be >= 1, got {self.freeze_window}"
            )
        if self.epoch_distinct_run_count < 0:
            raise ValueError(
                "epoch_distinct_run_count must be >= 0, "
                f"got {self.epoch_distinct_run_count}"
            )
        expected_is_frozen = self.epoch_distinct_run_count < self.freeze_window
        if self.is_frozen != expected_is_frozen:
            raise ValueError(
                f"is_frozen ({self.is_frozen}) inconsistent with "
                f"epoch_distinct_run_count ({self.epoch_distinct_run_count}) "
                f"and freeze_window ({self.freeze_window})"
            )
        expected_next = self.epoch_distinct_run_count + 1
        if self.next_run_index_in_epoch != expected_next:
            raise ValueError(
                f"next_run_index_in_epoch ({self.next_run_index_in_epoch}) "
                f"must equal epoch_distinct_run_count + 1 ({expected_next})"
            )


def evaluate_freeze_status(
    records: Sequence[HistoryRecord],
    *,
    dataset_epoch_id: str,
    freeze_window: int = DEFAULT_FREEZE_WINDOW,
) -> FreezeStatus:
    """epoch 内 calibrate-gate freeze 判定 (pure function, no I/O).

    SSOT: 概念設計 §5.1 / §3.3 / §3.3.1.

    Args:
        records: 全 history record (caller で ``read_history`` 済 list).
            ``read_history`` で v1 record は skip 済前提 (T058 SSOT).
        dataset_epoch_id: 現 RUN の epoch 識別子 (T058 / T059 担当の値).
            空文字 / None は ``ValueError`` raise (caller 運用契約:
            ``dataset_epoch_id`` 空なら calibrate-gate 自体を起動しない).
        freeze_window: 凍結窓サイズ (synthesis § 8.6 で 3 確定).

    Returns:
        :class:`FreezeStatus`.

    Raises:
        ValueError: ``dataset_epoch_id`` が None / 非 str / 空文字、
            または ``freeze_window < 1``。
    """
    # 入力 validation
    if dataset_epoch_id is None or not isinstance(dataset_epoch_id, str):
        raise ValueError(
            "dataset_epoch_id must be non-empty str, "
            f"got {type(dataset_epoch_id).__name__}: {dataset_epoch_id!r}"
        )
    if not dataset_epoch_id:
        raise ValueError(
            "dataset_epoch_id must be non-empty (caller contract: "
            "do not start calibrate-gate when dataset_epoch_id is empty)"
        )
    if freeze_window < 1:
        raise ValueError(
            f"freeze_window must be >= 1, got {freeze_window}"
        )

    # scope match (synthesis § 8.6 1 軸 SSOT)
    matching_records = [
        r for r in records if r.dataset_epoch_id == dataset_epoch_id
    ]

    # distinct Run count (T077 で applied_from_run_id 必須化、 None / 空文字
    # の hot-fix 経路を削除. HistoryRecord.__post_init__ で type level fail-fast
    # するため、 ここに到達する record は applied_from_run_id が必ず非空文字 str.
    # ただし defense-in-depth で再検証 (= Codex Round 1 [Warning] 反映、 不正生成
    # オブジェクト混入時の silent miscount 防止).
    distinct_run_ids: set[str] = set()
    for r in matching_records:
        if not isinstance(r.applied_from_run_id, str) or not r.applied_from_run_id:
            raise ValueError(
                "calibrate_freeze.evaluate_freeze_status: HistoryRecord with "
                "invalid applied_from_run_id encountered (T077 invariant "
                f"violation, defense-in-depth reject): {r.applied_from_run_id!r}"
            )
        distinct_run_ids.add(r.applied_from_run_id)

    epoch_distinct_run_count = len(distinct_run_ids)

    is_frozen = epoch_distinct_run_count < freeze_window

    return FreezeStatus(
        is_frozen=is_frozen,
        epoch_distinct_run_count=epoch_distinct_run_count,
        freeze_window=freeze_window,
        next_run_index_in_epoch=epoch_distinct_run_count + 1,
    )


def decide_with_freeze(
    sample: AggregatedSample,
    config: CalibrateConfig,
    *,
    freeze_status: FreezeStatus,
) -> Decision:
    """freeze 判定込みで :func:`decide` を呼ぶ wrapper.

    SSOT: 概念設計 §5.2 / §4.2.

    ``freeze_status.is_frozen=True`` の場合、 ``sample`` / ``config`` 内容に
    かかわらず ``decision="skip_frozen"`` + ``new_threshold=config.prev_threshold``
    で即時返却。 ``False`` の場合、 既存 ``decide(sample, config)`` に委譲する
    (= 完全委譲、 sample / config の解釈は decide() 側に従う)。

    Args:
        sample: 集計結果。
        config: calibrate 設定 (``config.prev_threshold`` が freeze 中の
            ``new_threshold`` ソース)。
        freeze_status: :func:`evaluate_freeze_status` の戻り値。

    Returns:
        :class:`Decision`. freeze 中は以下の固定値:
            - ``decision="skip_frozen"``
            - ``new_threshold=config.prev_threshold``
            - ``delta=0.0``
            - ``q_target=None``
            - ``var_fitness_pen=None``
            - ``raw_target_threshold=None``
            - ``clamped_by_delta=False``
            - ``clamped_by_floor_or_ceiling=False``
            - ``effective_sample_size=sample.n_rows_used``
    """
    if freeze_status.is_frozen:
        return Decision(
            decision=_FROZEN_DECISION_LABEL,
            new_threshold=config.prev_threshold,
            delta=0.0,
            q_target=None,
            var_fitness_pen=None,
            raw_target_threshold=None,
            clamped_by_delta=False,
            clamped_by_floor_or_ceiling=False,
            effective_sample_size=sample.n_rows_used,
        )
    return decide(sample, config)
