"""T067: Loop closure (Warmstart engine + Emergency mode).

synthesis § 8.4 (Warmstart) + § 8.5 (Emergency mode) 確定式の単一実装.

詳細:

- 概念設計: ``devnotes/20260430-1310-todo-T067-loop-closure-warmstart-emergency/conceptual-design.md``
- 詳細設計: ``devnotes/20260430-1310-todo-T067-loop-closure-warmstart-emergency/detailed-design.md``
- T066 依存: :class:`~src.alpha_factory.cpps_archive.ArchiveState` /
  :class:`~src.alpha_factory.cpps_archive.ArchiveMember` /
  :class:`~src.alpha_factory.cpps_archive.ArchiveCandidate` /
  :func:`~src.alpha_factory.cpps_archive.archive_evict_da` /
  :func:`~src.alpha_factory.cpps_archive.compute_archive_capacities` /
  :func:`~src.alpha_factory.cpps_archive.determine_archive_role` /
  :data:`~src.alpha_factory.cpps_archive.SUPPORTED_POP_SIZES`
- T064 依存: :class:`~src.alpha_factory.stage_bc_evaluator.BCEvaluationResult` (含
  follow-up Phase 0 の ``c_pass_depth: float`` field)
- T062 依存: :class:`~src.alpha_factory.mission_inf_gap.MissionGapResult`
- T061 依存: :class:`~src.alpha_factory.canonical_metrics.InvariantFlags`

Phase 1 (本 TODO = T067 PR 1): 単体実装 + テストのみ、 GA / archive 配線未変更.
T067 PR 1 単独 merge で runtime に影響なし (新規 module で他 module から
import されない).

Phase 2 (別 PR): T065/T066/T070/T071 と同時、 10 箇所同時更新 (詳細設計 Phase 2
申し送り参照).

設計判断 (詳細設計 D1-D8):

- Emergency 1 run 限定 (synthesis § 8.5): mode + boost_consumed_run_id 2 変数分離
  (R2 確定).
- Metric SSOT: ``best_mission_signed_margin`` (大が良) で emergency 判定統一
  (R1 確定).
- ``WarmstartReuseRecord.recent_use_run_indices`` で rolling/cooldown/max_reuse
  全て導出 (R4 確定).
- DA admission 経路は :func:`admit_warmstart_to_da_with_eviction` が担当
  (synthesis Round 22 改訂候補).
- :func:`build_warmstart_candidates` = filter / :func:`select_warmstart_candidates`
  = selection + 制約 の責務分離 (詳細 Round 4 [C1] 案 B).

References:

- synthesis § 8.4 / § 8.5
- zenigame ``alpha_sieve/sieve_archive.py:605``
  (select_injection_candidates_with_split)

ファイル配置規範:
    詳細設計は ``src/alpha_factory/ga/loop_closure.py`` (= ga/ subdir) を指定する
    が、 既存 ``src/alpha_factory/`` は flat module 構成 (= ga/ subdir 不存在).
    ファイル配置規範 (= 既存 flat module との一貫性優先) に従い flat 配置
    ``src/alpha_factory/loop_closure.py`` を採用 (T065 ``nsga2_selection.py`` /
    T066 ``cpps_archive.py`` と同方針).
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final, Literal

from src.alpha_factory.canonical_metrics import InvariantFlags
from src.alpha_factory.cpps_archive import (
    SUPPORTED_POP_SIZES,
    ArchiveCandidate,
    ArchiveMember,
    ArchiveState,
    archive_evict_da,
    compute_archive_capacities,
    determine_archive_role,
)
from src.alpha_factory.mission_inf_gap import MissionGapResult
from src.alpha_factory.stage_bc_evaluator import BCEvaluationResult

__all__ = [
    "EMERGENCY_HISTORY_MAXLEN",
    "EMERGENCY_MA_DELTA_THRESHOLD",
    "EMERGENCY_TRIGGER_CONSECUTIVE",
    "RAMP_SHARES",
    "SENTINEL_REPLACEMENT_FOR_HISTORY",
    "WARMSTART_COOLDOWN_RUNS",
    "WARMSTART_EMERGENCY_CA_RATIO",
    "WARMSTART_EMERGENCY_SHARE",
    "WARMSTART_MAX_FAMILY",
    "WARMSTART_MAX_PER_SESSION_PATTERN",
    "WARMSTART_MAX_PER_SOURCE_RUN",
    "WARMSTART_MAX_REUSE",
    "WARMSTART_NORMAL_CA_RATIO",
    "WARMSTART_NORMAL_SHARE",
    "WARMSTART_PREV_EPOCH_CAP_RATIO",
    "WARMSTART_RELAXATION_ORDER",
    "WARMSTART_ROLLING_WINDOW",
    "EmergencyHistoryEntry",
    "EmergencyState",
    "SchemaV2Metadata",
    "WarmstartCandidate",
    "WarmstartFilterStats",
    "WarmstartReport",
    "WarmstartReuseRecord",
    "WarmstartSelection",
    "WarmstartState",
    "admit_warmstart_to_da_with_eviction",
    "build_archive_candidate",
    "build_warmstart_candidates",
    "compute_best_mission_signed_margin",
    "compute_warmstart_counts",
    "compute_warmstart_ramp_share",
    "compute_warmstart_share_and_ratio",
    "evaluate_emergency_release",
    "evaluate_emergency_trigger",
    "is_boost_applicable",
    "prepare_run_loop_closure",
    "select_warmstart_candidates",
    "update_emergency_state",
    "update_warmstart_state",
]


# ============================================================================
# Constants (synthesis § 8.4 / § 8.5 厳密準拠)
# ============================================================================


WARMSTART_NORMAL_SHARE: Final[float] = 0.20
"""通常時 warmstart share (synthesis § 8.4)."""

WARMSTART_EMERGENCY_SHARE: Final[float] = 0.25
"""emergency 時 warmstart share (synthesis § 8.5)."""

WARMSTART_NORMAL_CA_RATIO: Final[float] = 26 / (26 + 12)
"""通常時 CA 比率 (= 26 / 38 ≈ 0.6842)."""

WARMSTART_EMERGENCY_CA_RATIO: Final[float] = 0.5
"""emergency 時 CA 比率 (= 1:1)."""

RAMP_SHARES: Final[Mapping[int, float]] = {1: 0.00, 2: 0.10, 3: 0.15}
"""run_no → share の ramp テーブル. run_no >= 4 で WARMSTART_NORMAL_SHARE (= 0.20)."""

WARMSTART_ROLLING_WINDOW: Final[int] = 10
"""warmstart reuse 履歴の rolling window (Run 数)."""

WARMSTART_COOLDOWN_RUNS: Final[int] = 2
"""warmstart 再利用までの cooldown (Run 数). 直前 Run で利用された個体は次 Run のみ skip."""

WARMSTART_MAX_REUSE: Final[int] = 3
"""rolling window 内の同一個体最大再利用回数."""

WARMSTART_MAX_PER_SOURCE_RUN: Final[int] = 2
"""1 warmstart cohort 内で同一 source run_id を取り得る最大数 (制約 1)."""

WARMSTART_MAX_PER_SESSION_PATTERN: Final[int] = 2
"""1 warmstart cohort 内で同一 pattern_id を取り得る最大数 (制約 2)."""

WARMSTART_MAX_FAMILY: Final[int] = 2
"""1 warmstart cohort 内で同一 family_id を取り得る最大数 (制約 3)."""

WARMSTART_RELAXATION_ORDER: Final[tuple[str, ...]] = (
    "session_pattern",
    "source_run",
    "family",
)
"""制約緩和順序 (詳細設計 D8 / 仮 ×2 で smoke 後再校正)."""

WARMSTART_PREV_EPOCH_CAP_RATIO: Final[float] = 0.20
"""prev_epoch (epoch_age == 1) 個体が warmstart cohort 全体で取り得る割合上限."""

EMERGENCY_HISTORY_MAXLEN: Final[int] = 10
"""EmergencyState.history の最大長 (新が前)."""

EMERGENCY_TRIGGER_CONSECUTIVE: Final[int] = 3
"""mission_pass=0 連続 Run 数の trigger 閾値."""

EMERGENCY_MA_DELTA_THRESHOLD: Final[float] = 0.05
"""trigger MA3 < MA6 - 0.05 の delta 閾値."""

SENTINEL_REPLACEMENT_FOR_HISTORY: Final[float] = -1.0e6
"""T062 -inf sentinel を MA 計算で破綻させない finite 置換値 (R1 確定)."""


# ============================================================================
# dataclasses (frozen=True、 全 immutable)
# ============================================================================


@dataclass(frozen=True)
class WarmstartReuseRecord:
    """個体ごとの warmstart 利用履歴 (immutable).

    rolling=10 / cooldown=2 / max_reuse=3 を全て本 field から導出.

    field:

    - ``genome_id``: 対象 individual の identifier.
    - ``recent_use_run_indices``: rolling 内 use 時 run_history index 列 (新が前).
    """

    genome_id: str
    recent_use_run_indices: tuple[int, ...]

    @property
    def reuse_count(self) -> int:
        """rolling 内利用回数 (max_reuse=3 制限の比較対象)."""
        return len(self.recent_use_run_indices)

    @property
    def last_used_run_index(self) -> int | None:
        """最新利用の run_history index (cooldown 計算用、 未利用 None)."""
        return (
            self.recent_use_run_indices[0] if self.recent_use_run_indices else None
        )


@dataclass(frozen=True)
class WarmstartState:
    """Run 間継承の warmstart 状態 (immutable).

    ``reuse_records`` は **過去に warmstart 利用された member のみ** 記録 (R4 確定
    案 B). 未利用 member は record なし扱い (= reuse_count=0、
    last_used_run_index=None).
    """

    reuse_records: tuple[WarmstartReuseRecord, ...] = ()
    rolling_window: int = WARMSTART_ROLLING_WINDOW


@dataclass(frozen=True)
class EmergencyHistoryEntry:
    """1 Run 分の emergency 判定指標 (Round 1 [W1] Run 全体集計).

    ``n_mission_pass`` / ``n_progress_pass`` は Run 全体 BCEvaluationResult からの
    集計値 (capacity / CA/DA 影響なし、 synthesis § 8.5 厳密準拠).
    ``best_mission_signed_margin`` は :func:`compute_best_mission_signed_margin`
    で sentinel 置換済 (大が良).
    """

    run_id: str
    n_mission_pass: int
    n_progress_pass: int
    best_mission_signed_margin: float


@dataclass(frozen=True)
class EmergencyState:
    """Emergency mode 状態 (mode + boost 2 変数分離、 R2 確定).

    ``mode`` = 監視状態 (解除条件成立まで保持).
    ``boost_consumed_run_id`` = 25%/1:1 boost 消費済 run_id.
    boost 適用は当該 run_id 1 回限定 (synthesis § 8.5 「1 run のみ動作」 厳密準拠).
    """

    mode: Literal["normal", "emergency"] = "normal"
    activated_at_run_id: str | None = None
    boost_consumed_run_id: str | None = None
    history: tuple[EmergencyHistoryEntry, ...] = ()


@dataclass(frozen=True)
class WarmstartCandidate:
    """warmstart 候補 (archive member の view、 詳細 Round 1 [W2] / [W3] 反映).

    field:

    - ``member``: 対象の :class:`ArchiveMember`.
    - ``reuse_record``: 過去 reuse 履歴 (None = 未利用).
    - ``epoch_age``: 0=current / 1=prev / >=2=対象外 (caller 計算済).
    - ``ca_rank_score`` / ``da_rank_score``: caller 計算済 sort key (大が良).
    """

    member: ArchiveMember
    reuse_record: WarmstartReuseRecord | None
    epoch_age: int
    ca_rank_score: float
    da_rank_score: float


@dataclass(frozen=True)
class WarmstartSelection:
    """warmstart 抽出結果."""

    ca_candidates: tuple[WarmstartCandidate, ...]
    da_candidates: tuple[WarmstartCandidate, ...]
    target_total: int
    target_ca: int
    target_da: int
    actual_total: int
    actual_ca: int
    actual_da: int


@dataclass(frozen=True)
class WarmstartFilterStats:
    """:func:`build_warmstart_candidates` の filter drop 統計 (詳細 Round 1 [W2])."""

    cooldown_drops: int
    max_reuse_drops: int
    epoch_age_2_plus_drops: int


@dataclass(frozen=True)
class WarmstartReport:
    """warmstart observability.

    field 定義:

    - ``share`` / ``is_boost_applicable``: ramp / boost 反映後の値 (caller 受取).
    - ``selection``: 選抜結果.
    - ``relaxation_steps``: 緩和発動順 (発動順保持、 詳細 Round 1 [W1]).
    - ``filter_stats``: build 側 filter drop 実数 (詳細 Round 1 [W2]).
    - ``prev_epoch_filter_drops``: select 側 prev_epoch cap で drop された数.
    - ``prev_epoch_cap_passed``: cap 通過数 (= ``_apply_prev_epoch_cap_in_sort``
      通過、 最終選抜数とは別、 詳細 Round 3 [W1]).
    - ``prev_epoch_final_selected``: 最終選抜 (CA + DA selected) の prev_epoch
      数 (observability 名称ズレ防止、 詳細 Round 3 [W1]).
    """

    share: float
    is_boost_applicable: bool
    selection: WarmstartSelection
    relaxation_steps: tuple[str, ...]
    filter_stats: WarmstartFilterStats
    prev_epoch_filter_drops: int
    prev_epoch_cap_passed: int
    prev_epoch_final_selected: int


@dataclass(frozen=True)
class SchemaV2Metadata:
    """T058 schema v2 から caller (T067 Phase 2 run_ga.py) が構築する metadata.

    実装本体は T058 で確定済の dataclass を import する想定 (Phase 2 配線時に
    確定). T067 PR 1 では :func:`build_archive_candidate` が消費する field のみ
    宣言.
    """

    genome_id: str
    run_id: str
    generation_no: int
    dataset_epoch_id: str
    pattern_id: str
    family_id: str


# ============================================================================
# Emergency mode (synthesis § 8.5 厳密準拠)
# ============================================================================


def evaluate_emergency_trigger(state: EmergencyState) -> bool:
    """発動: ``mission_pass=0`` が 3 連続 AND ``MA3 < MA6 - 0.05``.

    詳細 Round 1 [W1] / [C3] 反映: 指標は ``best_mission_signed_margin`` (大が良)、
    Run 全体集計. ``len(history) < 6`` で MA6 計算不能なら False (sample size guard).

    Args:
        state: 直前 Run までの :class:`EmergencyState`.

    Returns:
        当 Run で trigger 条件を満たすなら True.
    """
    if len(state.history) < 6:
        return False
    last3 = state.history[:EMERGENCY_TRIGGER_CONSECUTIVE]
    last6 = state.history[:6]
    if not all(h.n_mission_pass == 0 for h in last3):
        return False
    ma3 = (
        sum(h.best_mission_signed_margin for h in last3)
        / EMERGENCY_TRIGGER_CONSECUTIVE
    )
    ma6 = sum(h.best_mission_signed_margin for h in last6) / 6.0
    return ma3 < ma6 - EMERGENCY_MA_DELTA_THRESHOLD


def evaluate_emergency_release(state: EmergencyState) -> bool:
    """解除: ``progress_pass >= 2`` OR ``best_mission_signed_margin >= MA6`` (latest 判定).

    Args:
        state: 直前 Run までの :class:`EmergencyState`.

    Returns:
        当 Run で release 条件を満たすなら True. ``mode != "emergency"`` または
        ``history`` が空なら常に False.
    """
    if state.mode != "emergency" or not state.history:
        return False
    latest = state.history[0]
    if latest.n_progress_pass >= 2:
        return True
    if len(state.history) >= 6:
        ma6 = sum(h.best_mission_signed_margin for h in state.history[:6]) / 6.0
        return latest.best_mission_signed_margin >= ma6
    return False


def is_boost_applicable(state: EmergencyState, current_run_id: str) -> bool:
    """当 Run で 25%/1:1 boost を適用すべきか.

    boost は emergency mode 中の **1 run 限定** (synthesis § 8.5).

    - ``mode == "normal"``: False (boost 不適用)
    - ``mode == "emergency"`` で ``boost_consumed_run_id is None``: True
      (未消費、 当 Run で消費)
    - ``mode == "emergency"`` で ``boost_consumed_run_id == current_run_id``: True
      (同 Run 内冪等)
    - ``mode == "emergency"`` で ``boost_consumed_run_id != current_run_id``: False
      (別 Run で消費済)

    Args:
        state: 直前 Run までの :class:`EmergencyState`.
        current_run_id: 当 Run の run_id (caller 規約でグローバル一意).

    Returns:
        当 Run で boost を適用すべきなら True.
    """
    if state.mode != "emergency":
        return False
    if state.boost_consumed_run_id is None:
        return True
    return state.boost_consumed_run_id == current_run_id


def update_emergency_state(
    prev: EmergencyState,
    *,
    new_run_id: str,
    n_mission_pass: int,
    n_progress_pass: int,
    best_mission_signed_margin: float,
    boost_consumed_in_this_run: bool,
) -> EmergencyState:
    """Run 終了時に history append + mode 遷移 + ``boost_consumed_run_id`` 更新.

    Args:
        prev: 直前までの :class:`EmergencyState`.
        new_run_id: 終了した Run の run_id (非空).
        n_mission_pass: 当 Run の mission_pass 体数 (>= 0).
        n_progress_pass: 当 Run の progress_pass 体数 (>= 0).
        best_mission_signed_margin: 当 Run の
            :func:`compute_best_mission_signed_margin` 出力.
        boost_consumed_in_this_run: 当 Run で boost が実際に適用されたか.

    Returns:
        更新された :class:`EmergencyState`.
    """
    if not new_run_id:
        raise ValueError("new_run_id must be non-empty")
    if n_mission_pass < 0 or n_progress_pass < 0:
        raise ValueError(
            "n_mission_pass/n_progress_pass must be non-negative, "
            f"got {n_mission_pass}/{n_progress_pass}"
        )

    new_entry = EmergencyHistoryEntry(
        run_id=new_run_id,
        n_mission_pass=n_mission_pass,
        n_progress_pass=n_progress_pass,
        best_mission_signed_margin=best_mission_signed_margin,
    )
    new_history = (new_entry, *prev.history)
    if len(new_history) > EMERGENCY_HISTORY_MAXLEN:
        new_history = new_history[:EMERGENCY_HISTORY_MAXLEN]

    new_boost = (
        new_run_id if boost_consumed_in_this_run else prev.boost_consumed_run_id
    )
    new_state_pre = replace(
        prev, history=new_history, boost_consumed_run_id=new_boost
    )

    if new_state_pre.mode == "normal":
        if evaluate_emergency_trigger(new_state_pre):
            return replace(
                new_state_pre,
                mode="emergency",
                activated_at_run_id=new_run_id,
                boost_consumed_run_id=None,
            )
        return new_state_pre

    if evaluate_emergency_release(new_state_pre):
        return replace(
            new_state_pre,
            mode="normal",
            activated_at_run_id=None,
            boost_consumed_run_id=None,
        )
    return new_state_pre


# ============================================================================
# Warmstart share / counts
# ============================================================================


def compute_warmstart_ramp_share(run_no: int) -> float:
    """``run_no`` (1-origin) に応じた ramp share.

    Args:
        run_no: 1-origin 連番.

    Returns:
        run_no=1 → 0.00、 2 → 0.10、 3 → 0.15、 >=4 →
        :data:`WARMSTART_NORMAL_SHARE` (0.20).
    """
    if run_no < 1:
        raise ValueError(f"run_no must be >= 1, got {run_no}")
    if run_no in RAMP_SHARES:
        return RAMP_SHARES[run_no]
    return WARMSTART_NORMAL_SHARE


def compute_warmstart_share_and_ratio(
    ramp_share: float,
    is_boost_applicable: bool,
) -> tuple[float, float]:
    """share と CA 比率を返す (詳細 Round 1 [C1] is_boost_applicable ベース).

    boost 適用時のみ 25% / CA:DA=1:1 を 1 run 限定で適用.

    Args:
        ramp_share: :func:`compute_warmstart_ramp_share` 出力 ([0, 1] 範囲).
        is_boost_applicable: emergency boost 適用フラグ.

    Returns:
        ``(share, ca_ratio)``.
    """
    if not (0.0 <= ramp_share <= 1.0):
        raise ValueError(f"ramp_share must be in [0, 1], got {ramp_share}")
    if is_boost_applicable:
        return WARMSTART_EMERGENCY_SHARE, WARMSTART_EMERGENCY_CA_RATIO
    return ramp_share, WARMSTART_NORMAL_CA_RATIO


def compute_warmstart_counts(
    pop_size: int,
    share: float,
    ca_ratio: float,
) -> tuple[int, int, int]:
    """warmstart 体数 ``(total, ca, da)`` を計算 (端数規約: ``round``).

    ``pop_size`` は :data:`SUPPORTED_POP_SIZES` (= 192 / 256) のみ正式サポート.

    Args:
        pop_size: 集団サイズ.
        share: warmstart share ([0, 1]).
        ca_ratio: CA 比率 ([0, 1]).

    Returns:
        ``(total, ca, da)``.
    """
    if pop_size not in SUPPORTED_POP_SIZES:
        raise ValueError(
            f"pop_size must be one of {SUPPORTED_POP_SIZES}, got {pop_size}"
        )
    if not (0.0 <= share <= 1.0):
        raise ValueError(f"share must be in [0, 1], got {share}")
    if not (0.0 <= ca_ratio <= 1.0):
        raise ValueError(f"ca_ratio must be in [0, 1], got {ca_ratio}")
    total = round(pop_size * share)
    ca = round(total * ca_ratio)
    da = total - ca
    return total, ca, da


# ============================================================================
# Warmstart 候補抽出 (詳細 Round 4 [C1] 案 B 責務分離)
# ============================================================================


def build_warmstart_candidates(
    archive: ArchiveState,
    warmstart_state: WarmstartState,
    *,
    new_run_history_index: int,
    new_dataset_epoch_id: str,
    epoch_age_by_genome_id: Mapping[str, int],
    ca_rank_score_by_genome_id: Mapping[str, float],
    da_rank_score_by_genome_id: Mapping[str, float],
) -> tuple[tuple[WarmstartCandidate, ...], WarmstartFilterStats]:
    """archive members から WarmstartCandidate を構築 + filter.

    filter 内訳 (詳細 Round 4 [C1] 案 B):

    - cooldown=2 (直前 Run で利用された個体は cooldown 経過まで除外)
    - max_reuse=3 (rolling 内 reuse count 上限)
    - epoch_age >= 2 (2 epoch 以上古い個体は対象外)

    詳細 Round 1 [W2]: filter drop 統計を :class:`WarmstartFilterStats` で返す.
    詳細 Round 1 [W4]: ``archive.dataset_epoch_id`` / ``new_dataset_epoch_id`` /
    ``epoch_age_by_genome_id`` の整合性検証 (defense-in-depth).

    Args:
        archive: 直前 Run までの :class:`ArchiveState`.
        warmstart_state: 直前までの :class:`WarmstartState`.
        new_run_history_index: 当 Run の run_history index (>= 0).
        new_dataset_epoch_id: 当 Run の dataset_epoch_id (非空).
        epoch_age_by_genome_id: caller 計算済 ``{genome_id: epoch_age}``.
        ca_rank_score_by_genome_id: caller 計算済 CA sort key.
        da_rank_score_by_genome_id: caller 計算済 DA sort key.

    Returns:
        ``(candidates, filter_stats)``.

    Raises:
        ValueError: 入口契約違反 (negative index、 空文字 epoch、 epoch_age 不整合).
        KeyError: ``epoch_age_by_genome_id`` に member の genome_id が無い場合.
    """
    if new_run_history_index < 0:
        raise ValueError(
            f"new_run_history_index must be >= 0, got {new_run_history_index}"
        )
    if not new_dataset_epoch_id:
        raise ValueError("new_dataset_epoch_id must be non-empty")

    reuse_by_id = {r.genome_id: r for r in warmstart_state.reuse_records}
    candidates: list[WarmstartCandidate] = []
    cooldown_drops = 0
    max_reuse_drops = 0
    epoch_age_drops = 0

    for m in archive.members:
        if m.genome_id not in epoch_age_by_genome_id:
            raise KeyError(
                f"epoch_age_by_genome_id missing genome_id={m.genome_id}"
            )
        epoch_age = epoch_age_by_genome_id[m.genome_id]
        # 詳細 Round 2 [W1] 反映: epoch_age 下限検証
        if epoch_age < 0:
            raise ValueError(
                f"epoch_age must be >= 0 for genome_id={m.genome_id}, "
                f"got {epoch_age}"
            )

        # 詳細 Round 1 [W4]: epoch_age と member.dataset_epoch_id の整合性検証
        same_epoch = m.dataset_epoch_id == new_dataset_epoch_id
        if same_epoch and epoch_age != 0:
            raise ValueError(
                f"epoch_age_by_genome_id inconsistent for {m.genome_id}: "
                "member.dataset_epoch_id matches new_dataset_epoch_id but "
                f"epoch_age={epoch_age}"
            )
        if (not same_epoch) and epoch_age == 0:
            raise ValueError(
                f"epoch_age_by_genome_id inconsistent for {m.genome_id}: "
                "member.dataset_epoch_id != new_dataset_epoch_id but "
                "epoch_age=0"
            )

        # epoch_age >= 2 filter
        if epoch_age >= 2:
            epoch_age_drops += 1
            continue

        record = reuse_by_id.get(m.genome_id)

        # cooldown filter (cooldown=2 Run): last_used 以降 cooldown_runs 経過必須
        if record is not None and record.last_used_run_index is not None:
            cooldown_age = new_run_history_index - record.last_used_run_index
            if cooldown_age < WARMSTART_COOLDOWN_RUNS:
                cooldown_drops += 1
                continue

        # max_reuse filter
        if record is not None and record.reuse_count >= WARMSTART_MAX_REUSE:
            max_reuse_drops += 1
            continue

        ca_score = ca_rank_score_by_genome_id.get(m.genome_id, 0.0)
        da_score = da_rank_score_by_genome_id.get(m.genome_id, 0.0)
        candidates.append(
            WarmstartCandidate(
                member=m,
                reuse_record=record,
                epoch_age=epoch_age,
                ca_rank_score=ca_score,
                da_rank_score=da_score,
            )
        )

    stats = WarmstartFilterStats(
        cooldown_drops=cooldown_drops,
        max_reuse_drops=max_reuse_drops,
        epoch_age_2_plus_drops=epoch_age_drops,
    )
    return tuple(candidates), stats


def select_warmstart_candidates(
    candidates: Sequence[WarmstartCandidate],
    *,
    pop_size: int,
    share: float,
    ca_ratio: float,
    prev_epoch_admitted_genome_ids: frozenset[str],
    is_boost_applicable: bool,
    filter_stats: WarmstartFilterStats,
) -> tuple[WarmstartSelection, WarmstartReport]:
    """target / 制約 / 緩和順 / prev_epoch 上限の選抜本体.

    詳細 Round 4 [C1]: cooldown / max_reuse / epoch_age >= 2 は
    :func:`build_warmstart_candidates` 側で実施済.

    詳細 Round 1 [C3]: prev_epoch cap を CA/DA sort 後に適用 (高スコア個体が
    cap 枠を優先取得).

    詳細 Round 1 [S1]: ``prev_epoch_cap = int(...)`` は floor を採用
    (例: 8 × 0.20 = 1).

    詳細 Round 2 [C1] / [C2]: prev_epoch 20% cap は **global budget**.
    CA で消費した分を DA で減算した残予算で適用、 さらに DA は ca_ids 除外後の
    プールで判定.

    Args:
        candidates: :func:`build_warmstart_candidates` 出力.
        pop_size: 集団サイズ.
        share: warmstart share.
        ca_ratio: CA 比率.
        prev_epoch_admitted_genome_ids: prev_epoch から再 admission 許可された
            genome_id 集合.
        is_boost_applicable: caller が確定済の boost フラグ
            (詳細 Round 1 [W3]、 ratio から推定しない).
        filter_stats: :func:`build_warmstart_candidates` の filter stats
            (pass-through、 詳細 Round 1 [W2]).

    Returns:
        ``(selection, report)``.
    """
    target_total, target_ca, target_da = compute_warmstart_counts(
        pop_size, share, ca_ratio
    )

    if target_total == 0:
        empty_sel = WarmstartSelection(
            ca_candidates=(),
            da_candidates=(),
            target_total=0,
            target_ca=0,
            target_da=0,
            actual_total=0,
            actual_ca=0,
            actual_da=0,
        )
        empty_report = WarmstartReport(
            share=share,
            is_boost_applicable=is_boost_applicable,
            selection=empty_sel,
            relaxation_steps=(),
            filter_stats=filter_stats,
            prev_epoch_filter_drops=0,
            prev_epoch_cap_passed=0,
            prev_epoch_final_selected=0,
        )
        return empty_sel, empty_report

    # CA / DA 別 sort (rank_score 降順 + genome_id 昇順 tie-break)
    ca_sorted = sorted(
        candidates, key=lambda c: (-c.ca_rank_score, c.member.genome_id)
    )
    da_sorted = sorted(
        candidates, key=lambda c: (-c.da_rank_score, c.member.genome_id)
    )

    # 詳細 Round 2 [C1]: prev_epoch 20% cap は **global budget**
    prev_epoch_cap_global = int(
        target_total * WARMSTART_PREV_EPOCH_CAP_RATIO
    )

    # CA 選抜 (sort 後に cap 適用、 緩和)
    ca_filtered, ca_drops, ca_prev_admitted = _apply_prev_epoch_cap_in_sort(
        ca_sorted,
        prev_epoch_admitted_genome_ids=prev_epoch_admitted_genome_ids,
        cap=prev_epoch_cap_global,
    )
    ca_selected, ca_relax = _select_with_relaxation(ca_filtered, target=target_ca)
    ca_ids = {c.member.genome_id for c in ca_selected}

    # CA 採用 prev_epoch 数を計算 (selected かつ epoch_age==1)
    ca_admitted_prev = sum(1 for c in ca_selected if c.epoch_age == 1)
    da_remaining_cap = max(0, prev_epoch_cap_global - ca_admitted_prev)

    # DA 選抜: ca_ids 除外後のプールで cap 適用 (詳細 Round 2 [C2])
    da_pool_excluded = [c for c in da_sorted if c.member.genome_id not in ca_ids]
    da_filtered, da_drops, da_prev_admitted = _apply_prev_epoch_cap_in_sort(
        da_pool_excluded,
        prev_epoch_admitted_genome_ids=prev_epoch_admitted_genome_ids,
        cap=da_remaining_cap,
    )
    da_selected, da_relax = _select_with_relaxation(da_filtered, target=target_da)

    actual_ca = len(ca_selected)
    actual_da = len(da_selected)
    selection = WarmstartSelection(
        ca_candidates=tuple(ca_selected),
        da_candidates=tuple(da_selected),
        target_total=target_total,
        target_ca=target_ca,
        target_da=target_da,
        actual_total=actual_ca + actual_da,
        actual_ca=actual_ca,
        actual_da=actual_da,
    )
    # 詳細 Round 3 [W1]: 最終選抜 prev_epoch 数 (cap 通過後さらに緩和ループで採用された数)
    final_prev_selected = sum(
        1 for c in ca_selected if c.epoch_age == 1
    ) + sum(1 for c in da_selected if c.epoch_age == 1)

    report = WarmstartReport(
        share=share,
        is_boost_applicable=is_boost_applicable,
        selection=selection,
        # 詳細 Round 1 [W1]: 発動順保持 union (sorted ではなく順序保存)
        relaxation_steps=_merge_preserve_order(ca_relax, da_relax),
        filter_stats=filter_stats,
        prev_epoch_filter_drops=ca_drops + da_drops,
        prev_epoch_cap_passed=ca_prev_admitted + da_prev_admitted,
        prev_epoch_final_selected=final_prev_selected,
    )
    return selection, report


def _apply_prev_epoch_cap_in_sort(
    sorted_candidates: Sequence[WarmstartCandidate],
    *,
    prev_epoch_admitted_genome_ids: frozenset[str],
    cap: int,
) -> tuple[list[WarmstartCandidate], int, int]:
    """sort 順を維持しつつ prev_epoch (epoch_age==1) 枠を ``cap`` 体まで通過、 残りは除外.

    詳細 Round 1 [C3]: 高スコア (sort 順) の prev_epoch 個体が cap 枠を優先取得.
    詳細 Round 2 [C1]: ``cap`` は **global budget の残予算** (caller が CA 採用後の
    残量を渡す). ``cap=0`` でも ``prev_epoch_admitted_genome_ids`` 通過個体は
    確認される (drops でカウント).

    Returns:
        ``(filtered_candidates, drops, prev_admitted)``.
    """
    filtered: list[WarmstartCandidate] = []
    drops = 0
    prev_admitted = 0
    for c in sorted_candidates:
        if c.epoch_age == 1:
            if c.member.genome_id not in prev_epoch_admitted_genome_ids:
                drops += 1
                continue
            if prev_admitted >= cap:
                drops += 1
                continue
            prev_admitted += 1
        filtered.append(c)
    return filtered, drops, prev_admitted


def _merge_preserve_order(a: Sequence[str], b: Sequence[str]) -> tuple[str, ...]:
    """発動順を保持した union (詳細 Round 1 [W1])."""
    seen: set[str] = set()
    result: list[str] = []
    for item in list(a) + list(b):
        if item not in seen:
            seen.add(item)
            result.append(item)
    return tuple(result)


def _select_with_relaxation(
    sorted_candidates: Sequence[WarmstartCandidate],
    *,
    target: int,
) -> tuple[list[WarmstartCandidate], tuple[str, ...]]:
    """段階的緩和ループ (詳細設計 D8、 仮 ×2 で smoke 後再校正).

    順序: ``WARMSTART_RELAXATION_ORDER`` ⇒ ``session_pattern`` →
    ``source_run`` → ``family``. 各 step で対応 cap を 2 倍.
    最終 step (全制約撤廃) でも target 未達なら可能な範囲で返す.

    Returns:
        ``(selected, relaxed_steps)``. ``relaxed_steps`` は実際に発動した
        制約名の tuple.
    """
    constraints_initial = {
        "session_pattern": WARMSTART_MAX_PER_SESSION_PATTERN,
        "source_run": WARMSTART_MAX_PER_SOURCE_RUN,
        "family": WARMSTART_MAX_FAMILY,
    }
    constraints = dict(constraints_initial)
    relaxed_steps: list[str] = []
    for cap_round in range(len(WARMSTART_RELAXATION_ORDER) + 1):
        selected = _try_select_with_constraints(
            sorted_candidates, target, constraints
        )
        if len(selected) >= target:
            return selected[:target], tuple(relaxed_steps)
        if cap_round < len(WARMSTART_RELAXATION_ORDER):
            key = WARMSTART_RELAXATION_ORDER[cap_round]
            constraints[key] = constraints[key] * 2
            relaxed_steps.append(key)
    return (
        _try_select_with_constraints(sorted_candidates, target, {})[:target],
        tuple(relaxed_steps),
    )


def _try_select_with_constraints(
    candidates: Sequence[WarmstartCandidate],
    target: int,
    constraints: Mapping[str, int],
) -> list[WarmstartCandidate]:
    """current 制約で ``target`` 体に達するまで貪欲選抜 (caller sort 順に従う)."""
    selected: list[WarmstartCandidate] = []
    pattern_count: Counter[str] = Counter()
    source_run_count: Counter[str] = Counter()
    family_count: Counter[str] = Counter()
    sp_cap: float = constraints.get("session_pattern", math.inf)
    sr_cap: float = constraints.get("source_run", math.inf)
    fa_cap: float = constraints.get("family", math.inf)
    for c in candidates:
        if len(selected) >= target:
            break
        m = c.member
        if pattern_count[m.pattern_id] >= sp_cap:
            continue
        if source_run_count[m.run_id] >= sr_cap:
            continue
        if family_count[m.family_id] >= fa_cap:
            continue
        selected.append(c)
        pattern_count[m.pattern_id] += 1
        source_run_count[m.run_id] += 1
        family_count[m.family_id] += 1
    return selected


def update_warmstart_state(
    prev: WarmstartState,
    *,
    selected_genome_ids: Iterable[str],
    new_run_history_index: int,
) -> WarmstartState:
    """warmstart selected genome の reuse_record を更新 (rolling window 適用).

    詳細 Round 1 [C2] 反映: 既存 records / 新規 records とも genome_id 昇順で
    走査・出力 (順序非決定性を排除).

    Args:
        prev: 直前までの :class:`WarmstartState`.
        selected_genome_ids: 当 Run で warmstart として選抜された genome_id 集合
            (Iterable、 重複は内部で set 化).
        new_run_history_index: 当 Run の run_history index (>= 0).

    Returns:
        更新された :class:`WarmstartState`.
    """
    if new_run_history_index < 0:
        raise ValueError(
            f"new_run_history_index must be >= 0, got {new_run_history_index}"
        )

    selected_ids = set(selected_genome_ids)
    existing_by_id = {r.genome_id: r for r in prev.reuse_records}

    rolling_floor = new_run_history_index - prev.rolling_window
    new_records: list[WarmstartReuseRecord] = []

    # 既存 records: rolling window で古いインデックスを削除 + selected なら最新追加
    for genome_id in sorted(existing_by_id.keys()):
        r = existing_by_id[genome_id]
        new_indices = tuple(
            i for i in r.recent_use_run_indices if i > rolling_floor
        )
        if genome_id in selected_ids:
            new_indices = (new_run_history_index, *new_indices)
        if new_indices:
            new_records.append(replace(r, recent_use_run_indices=new_indices))

    # 新規利用 (existing にない genome_id) も sorted で順序固定
    for genome_id in sorted(selected_ids):
        if genome_id not in existing_by_id:
            new_records.append(
                WarmstartReuseRecord(
                    genome_id=genome_id,
                    recent_use_run_indices=(new_run_history_index,),
                )
            )

    # 出力 tuple も genome_id 昇順で固定 (deterministic)
    new_records_sorted = sorted(new_records, key=lambda r: r.genome_id)
    return replace(prev, reuse_records=tuple(new_records_sorted))


# ============================================================================
# T064/T062/T061 → T066 ArchiveCandidate builder
# ============================================================================


def build_archive_candidate(
    bc_result: BCEvaluationResult,
    mission_gap: MissionGapResult,
    invariant_flags: InvariantFlags,
    metadata: SchemaV2Metadata,
    *,
    novelty: float,
    diversity_coverage: float,
    quality_floor_margin: float,
    margin_inf_passes_p70: bool,
) -> ArchiveCandidate:
    """T064 / T062 / T061 / T058 schema → T066 ArchiveCandidate 変換.

    ``archive_role`` は :func:`determine_archive_role` で確定.
    finite check は T066 入口契約と整合 (T067 では事前チェック実施しない、
    caller 責務).

    SSOT 整合性 (詳細設計 vs main 実装):
        詳細設計 (§ 施策 1) は ``bc_result.shadow_robustness_score`` 直アクセスを
        記述するが、 T064 main 実装では ``shadow_robustness_score`` は
        :class:`StageCResult` の field で、 :class:`BCEvaluationResult` 直下には
        存在しない. 規範 (= 詳細設計 vs main 実装の整合性検査、 不一致なら main
        実装を SSOT) に従い、 本実装では ``bc_result.c_result.shadow_robustness_score``
        を参照する. ``None`` の場合は ineligible 個体 (archive 対象外、 値は
        eviction lex で ``not_score_bypass`` 経路でしか参照されない) として
        ``0.0`` を設定.

    Args:
        bc_result: T064 :class:`BCEvaluationResult` (含 follow-up Phase 0 の
            ``c_pass_depth`` field).
        mission_gap: T062 :class:`MissionGapResult`.
        invariant_flags: T061 :class:`InvariantFlags`.
        metadata: T058 schema v2 metadata (caller 構築).
        novelty: caller 計算済 (DA eviction lex 用).
        diversity_coverage: caller 計算済.
        quality_floor_margin: caller 計算済.
        margin_inf_passes_p70: caller 計算済.

    Returns:
        T066 :class:`ArchiveCandidate`.
    """
    role = determine_archive_role(bc_result)
    if bc_result.b_pooled_cf is not None:
        gate_worst_gap = bc_result.b_pooled_cf.gate_worst_gap
        log_pf_clip = bc_result.b_pooled_cf.log_pf_clip
    else:
        gate_worst_gap = math.inf  # ineligible 個体は archive 対象外、 値は使われない
        log_pf_clip = 0.0

    shadow_score = bc_result.c_result.shadow_robustness_score
    if shadow_score is None:
        shadow_score = 0.0

    return ArchiveCandidate(
        genome_id=metadata.genome_id,
        run_id=metadata.run_id,
        generation_no=metadata.generation_no,
        dataset_epoch_id=metadata.dataset_epoch_id,
        pattern_id=metadata.pattern_id,
        family_id=metadata.family_id,
        archive_role=role,
        gate_worst_gap=gate_worst_gap,
        c_pass_depth=bc_result.c_pass_depth,
        mission_signed_margin=mission_gap.mission_signed_margin,
        shadow_robustness_score=shadow_score,
        log_pf_clip=log_pf_clip,
        invariant_feasible=invariant_flags.is_feasible,
        margin_inf=mission_gap.mission_inf_gap,
        margin_inf_passes_p70=margin_inf_passes_p70,
        novelty=novelty,
        diversity_coverage=diversity_coverage,
        quality_floor_margin=quality_floor_margin,
    )


# ============================================================================
# best_mission_signed_margin (詳細 Round 1 [C3] / R1 確定)
# ============================================================================


def compute_best_mission_signed_margin(
    mission_gaps: Mapping[str, MissionGapResult],
) -> float:
    """全候補の ``mission_signed_margin`` の最大値 (大が良).

    R1 確定: T062 ``-inf`` sentinel を :data:`SENTINEL_REPLACEMENT_FOR_HISTORY`
    (-1.0e6) で finite 化、 全 history MA 計算の安定性を保証. 全個体 infeasible
    でも MA 計算が壊れない.

    Args:
        mission_gaps: ``{genome_id: MissionGapResult}`` (空可).

    Returns:
        finite 化後の最大値 (空入力時は :data:`SENTINEL_REPLACEMENT_FOR_HISTORY`).
    """
    if not mission_gaps:
        return SENTINEL_REPLACEMENT_FOR_HISTORY
    finite_values = [
        g.mission_signed_margin
        if math.isfinite(g.mission_signed_margin)
        else SENTINEL_REPLACEMENT_FOR_HISTORY
        for g in mission_gaps.values()
    ]
    return max(finite_values)


# ============================================================================
# DA admission (詳細 Round 1 [C4] eviction まで 1 API)
# ============================================================================


def admit_warmstart_to_da_with_eviction(
    archive: ArchiveState,
    warmstart_da_candidates: Sequence[WarmstartCandidate],
    *,
    pop_size: int,
) -> ArchiveState:
    """warmstart 由来 DA candidates を archive DA に注入 + DA eviction まで 1 API で完結.

    手順:

    1. 各 ``warmstart_da_candidates`` の :class:`ArchiveMember` を
       ``archive_target="DA"`` に書換 (upsert).
    2. ``genome_id`` 一意制約維持 (T066 § 10).
    3. T066 :func:`archive_evict_da` で DA capacity 内に収める (戻り値は常に
       capacity 内、 詳細 Round 1 [C4]).

    Args:
        archive: 直前の :class:`ArchiveState`.
        warmstart_da_candidates: warmstart 選抜後の DA 注入候補
            (空可、 空なら archive 不変).
        pop_size: 集団サイズ (DA capacity 計算).

    Returns:
        更新された :class:`ArchiveState` (DA capacity 内不変条件成立).
    """
    if not warmstart_da_candidates:
        return archive

    existing_by_id: dict[str, ArchiveMember] = {
        m.genome_id: m for m in archive.members
    }
    for c in warmstart_da_candidates:
        m = c.member
        if m.archive_target != "DA":
            existing_by_id[m.genome_id] = replace(m, archive_target="DA")
        else:
            existing_by_id[m.genome_id] = m
    intermediate = replace(archive, members=tuple(existing_by_id.values()))

    _, _, da_capacity = compute_archive_capacities(pop_size)
    return archive_evict_da(intermediate, target_size=da_capacity)


# ============================================================================
# Top-level entry per-Run 開始時
# ============================================================================


def prepare_run_loop_closure(
    prev_warmstart_state: WarmstartState,
    prev_emergency_state: EmergencyState,
    prev_archive: ArchiveState,
    *,
    run_no: int,
    pop_size: int,
    current_run_id: str,
    new_dataset_epoch_id: str,
    new_run_history_index: int,
    epoch_age_by_genome_id: Mapping[str, int],
    ca_rank_score_by_genome_id: Mapping[str, float],
    da_rank_score_by_genome_id: Mapping[str, float],
    prev_epoch_admitted_genome_ids: frozenset[str],
) -> tuple[WarmstartSelection, WarmstartReport]:
    """Run 開始時 entry: warmstart selection + emergency boost 判定.

    Run 終了時の archive 更新 + emergency state 更新は別経路 (caller 責務 +
    :func:`update_warmstart_state` / :func:`update_emergency_state`).

    Args:
        prev_warmstart_state: 直前までの :class:`WarmstartState`.
        prev_emergency_state: 直前までの :class:`EmergencyState`.
        prev_archive: 直前までの :class:`ArchiveState`.
        run_no: 1-origin 連番.
        pop_size: 集団サイズ.
        current_run_id: 当 Run の run_id (非空).
        new_dataset_epoch_id: 当 Run の dataset_epoch_id (非空).
        new_run_history_index: 当 Run の run_history index (>= 0).
        epoch_age_by_genome_id: caller 計算済 ``{genome_id: epoch_age}``.
        ca_rank_score_by_genome_id: caller 計算済 CA sort key.
        da_rank_score_by_genome_id: caller 計算済 DA sort key.
        prev_epoch_admitted_genome_ids: prev_epoch から再 admission 許可された
            genome_id 集合.

    Returns:
        ``(selection, report)``.
    """
    if run_no < 1:
        raise ValueError(f"run_no must be >= 1, got {run_no}")
    if not current_run_id:
        raise ValueError("current_run_id must be non-empty")

    ramp_share = compute_warmstart_ramp_share(run_no)
    boost_applicable = is_boost_applicable(prev_emergency_state, current_run_id)
    share, ca_ratio = compute_warmstart_share_and_ratio(
        ramp_share, boost_applicable
    )

    # 詳細 Round 1 [W2]: build_warmstart_candidates は (candidates, stats) tuple を返す
    candidates, filter_stats = build_warmstart_candidates(
        prev_archive,
        prev_warmstart_state,
        new_run_history_index=new_run_history_index,
        new_dataset_epoch_id=new_dataset_epoch_id,
        epoch_age_by_genome_id=epoch_age_by_genome_id,
        ca_rank_score_by_genome_id=ca_rank_score_by_genome_id,
        da_rank_score_by_genome_id=da_rank_score_by_genome_id,
    )

    # 詳細 Round 1 [W3]: is_boost_applicable / filter_stats を明示引回し
    return select_warmstart_candidates(
        candidates,
        pop_size=pop_size,
        share=share,
        ca_ratio=ca_ratio,
        prev_epoch_admitted_genome_ids=prev_epoch_admitted_genome_ids,
        is_boost_applicable=boost_applicable,
        filter_stats=filter_stats,
    )
