"""T066: CPPS 2-state FSM + CA/DA archive admission/eviction.

synthesis § 7.2-7.4 + § 8.1-8.3 (Round 21 改訂後) 確定式の単一実装.

詳細:

- 概念設計: ``devnotes/20260430-1200-todo-T066-cpps-fsm-and-archive/conceptual-design.md``
- 詳細設計: ``devnotes/20260430-1200-todo-T066-cpps-fsm-and-archive/detailed-design.md``
- synthesis § 7.2 (Push/Pull FSM)、 § 7.3 (CA/DA 配分)、 § 7.4 (offspring → CA/DA)
- synthesis § 8.1 (Archive 構成)、 § 8.2 (Inflow)、 § 8.3 (Eviction、 Round 21 改訂後)
- T065 依存: ``GenerationSelectionResult.survivor_indices`` (CA/DA partition source)
- T064 依存: :class:`~src.alpha_factory.stage_bc_evaluator.BCEvaluationResult`
  (``mission_pass``, ``progress_pass``, ``b_pooled_cf``, ``pareto_axis_usable``,
  ``shadow_robustness_score``、 ``c_pass_depth`` は T064 follow-up Phase 0 で追加済).
- T062 依存: :class:`~src.alpha_factory.mission_inf_gap.MissionGapResult`
  (``mission_signed_margin`` = CA eviction lex key #5)
- T061 依存: :class:`~src.alpha_factory.canonical_metrics.CanonicalFiveResult`
  (``log_pf_clip`` = eviction lex 末端) /
  :class:`~src.alpha_factory.canonical_metrics.InvariantFlags`
  (``is_feasible`` = 品質床)

Phase 1 (本 TODO = T066 PR 1): 単体実装 + テストのみ、 GA / archive 未変更.
T066 PR 1 単独 merge で runtime に影響なし (新規 module で他 module から import されない).

Phase 2 (別 PR): T067 / T070 / T071 と同時、 10 箇所同時更新 (詳細設計 Phase 2 申し送り参照).

設計判断 (CA only admission、 概念 Round 1 [C3]):
T066 ``archive_admit`` は CA admission のみ実施。 DA admission は T067 warmstart 経路で別途.

References:

- Fan, Z., Li, W., Cai, X., et al. (2019). Push and pull search for solving constrained
  multi-objective optimization problems. Swarm Evol. Comput., 44, 665-679.
- Li, K., Chen, R., Min, G., & Yao, X. (2019). Two-Archive Evolutionary Algorithm for
  Constrained Multiobjective Optimization. IEEE TEC, 23(2), 303-315.
- Wang, H., Jiao, L., & Yao, X. (2015). Two_Arch2: An Improved Two-Archive Algorithm for
  Many-Objective Optimization. IEEE TEC, 19(4), 524-541.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final, Literal

# BCEvaluationResult は :func:`determine_archive_role` の引数型注釈で参照されるため
# runtime でも import する (T066 PR 1 の Phase 0 contract test も同 import を消費).
from src.alpha_factory.stage_bc_evaluator import BCEvaluationResult, StagePassStatus

__all__ = [
    "ARCHIVE_ROLE_PRIORITY",
    "PATTERN_MAX_SHARE",
    "PULL_CA_RATIO",
    "PUSH_CA_RATIO",
    "RECENCY_FLOOR_COUNT",
    "RECENCY_FLOOR_LAST_N_RUNS",
    "RUN_HISTORY_MAXLEN",
    "SUPPORTED_POP_SIZES",
    "AdmissionReport",
    "ArchiveCandidate",
    "ArchiveMember",
    "ArchiveState",
    "InflowTargets",
    "PushPullState",
    "archive_admit",
    "archive_evict_ca",
    "archive_evict_da",
    "compute_archive_capacities",
    "compute_ca_da_capacities",
    "compute_inflow_targets",
    "determine_archive_role",
    "partition_survivors_to_ca_da",
    "update_archive_per_run",
    "update_push_pull_state",
]


# ============================================================================
# Constants (synthesis § 7.2-7.4 + § 8.1-8.3 厳密準拠)
# ============================================================================

PUSH_CA_RATIO: Final[float] = 84 / 192   # = 0.4375 (synthesis § 7.2)
"""push 状態における CA 比率 (= 84 / 192)."""

PULL_CA_RATIO: Final[float] = 120 / 192  # = 0.625 (synthesis § 7.2)
"""pull 状態における CA 比率 (= 120 / 192)."""

SUPPORTED_POP_SIZES: Final[tuple[int, ...]] = (192, 256)
"""正式サポートする pop_size (synthesis § 8.1)."""

# Archive 容量 (synthesis § 8.1): pop_size -> (total, ca, da)
_ARCHIVE_CAPS: Final[dict[int, tuple[int, int, int]]] = {
    192: (120, 72, 48),
    256: (160, 96, 64),
}

# Inflow targets (synthesis § 8.2): pop_size -> (target, per_run_max)
_INFLOW_TARGETS: Final[dict[int, tuple[int, int]]] = {
    192: (8, 12),
    256: (10, 16),
}

PATTERN_MAX_SHARE: Final[float] = 0.25
"""archive 全体に占める同一 pattern_id の上限比率 (synthesis § 8.3)."""

RECENCY_FLOOR_COUNT: Final[int] = 12
"""直近 :data:`RECENCY_FLOOR_LAST_N_RUNS` Run 由来 members の最低保持数 (best-effort)."""

RECENCY_FLOOR_LAST_N_RUNS: Final[int] = 3
"""recency floor の参照 Run 数."""

RUN_HISTORY_MAXLEN: Final[int] = 10
"""``ArchiveState.run_history`` の最大長 (= 直近 10 Run、 新が前)."""

ARCHIVE_ROLE_PRIORITY: Final[dict[str, int]] = {
    "mission_pass": 0,
    "progress_pass": 1,
    "score_bypass": 2,
}
"""per_run_max trim での階層優先 (synthesis § 8.3、 0 が高優先)."""


# ============================================================================
# dataclasses (frozen で immutable)
# ============================================================================


@dataclass(frozen=True)
class PushPullState:
    """CPPS 2-state FSM の状態 (immutable、 synthesis § 7.2).

    field:

    - ``phase``: ``"push"`` または ``"pull"``
    - ``consecutive_count``: 直近 ``feasible_ratio_ema >= theta_switch`` を連続満たした世代数
    - ``switch_generation``: ``pull`` への遷移が確定した世代 (None=未遷移)
    - ``last_feasible_ratio_ema``: 直近の feasible_ratio_ema (観測用)
    - ``forced_switch``: ``generation_no >= force_g`` による強制遷移なら True
    """

    phase: Literal["push", "pull"]
    consecutive_count: int
    switch_generation: int | None
    last_feasible_ratio_ema: float
    forced_switch: bool


@dataclass(frozen=True)
class ArchiveCandidate:
    """archive admission 前の候補 (caller 構築、 全 source field を持つ).

    caller (T067 / Phase 2 ``run_ga.py``) は T064 :class:`BCEvaluationResult` /
    T062 :class:`~src.alpha_factory.mission_inf_gap.MissionGapResult` /
    T061 :class:`~src.alpha_factory.canonical_metrics.InvariantFlags` /
    T058 schema v2 metadata から本 dataclass を構築して T066 に渡す.

    invariant: ``archive_role`` は 4 状態 (admission 前提のため
    ``score_bypass_candidate`` を含む).

    Note:
        finite (``math.isfinite``) 性検証は **caller 責務** (T067 が
        :class:`ArchiveCandidate` 構築時に検証)。 本 dataclass は受け取った値を
        そのまま保持し、 NaN/inf であっても raise しない (詳細 Round 1 [W2] 反映).
    """

    # identity (T058 schema v2 必須)
    genome_id: str
    run_id: str
    generation_no: int
    dataset_epoch_id: str
    pattern_id: str
    family_id: str

    # archive_role 判定材料
    archive_role: Literal[
        "mission_pass", "progress_pass", "score_bypass_candidate", "ineligible"
    ]
    gate_worst_gap: float

    # CA eviction lex 4-7 用
    c_pass_depth: float
    mission_signed_margin: float
    shadow_robustness_score: float
    log_pf_clip: float

    # 品質床
    invariant_feasible: bool
    margin_inf: float
    margin_inf_passes_p70: bool

    # DA eviction lex 1-2, 5 用
    novelty: float
    diversity_coverage: float
    quality_floor_margin: float


@dataclass(frozen=True)
class ArchiveMember:
    """archive 登録後の不変メタデータ (admission 経て確定).

    :class:`ArchiveCandidate` の admission 経路で生成、 ``archive_role`` は 3 状態
    (``score_bypass_candidate`` → ``score_bypass`` に変換済)、 ``archive_target`` は
    T066 が決定.

    ``not_score_bypass`` は保存値ではなく ``archive_role != "score_bypass"`` の
    property で導出 (詳細 Round 1 [S4] / 詳細 Round 2 [Suggestion 2] 反映、
    保存値 inconsistency 防止).
    """

    genome_id: str
    run_id: str
    generation_no: int
    dataset_epoch_id: str
    pattern_id: str
    family_id: str

    archive_role: Literal["mission_pass", "progress_pass", "score_bypass"]
    archive_target: Literal["CA", "DA"]

    # eviction lex 用 (ArchiveCandidate からコピー)
    gate_worst_gap: float
    c_pass_depth: float
    mission_signed_margin: float
    shadow_robustness_score: float
    log_pf_clip: float
    novelty: float
    diversity_coverage: float
    quality_floor_margin: float
    margin_inf: float
    invariant_feasible: bool

    @property
    def not_score_bypass(self) -> bool:
        """CA / DA eviction lex 第 3 段の導出値.

        ``archive_role != "score_bypass"`` の真偽を返す.
        """
        return self.archive_role != "score_bypass"


@dataclass(frozen=True)
class ArchiveState:
    """CA + DA を保持する状態オブジェクト (immutable).

    invariant (詳細 Round 3 [C1] / 詳細 Round 4 [Suggestion]):

    - ``members`` 内の ``m.genome_id`` は重複禁止 (uniqueness invariant)
    - :func:`archive_admit` / eviction は invariant 維持責務、 同一 ``genome_id``
      の再 admission は upsert 扱い
    - 同一 genome を CA / DA 同時保持しない (Phase 1 では CA only で自動成立、
      Phase 2 でも維持)

    field:

    - ``members``: :class:`ArchiveMember` の tuple (genome_id 一意)
    - ``dataset_epoch_id``: archive 全体の epoch (各 member の epoch と整合)
    - ``run_history``: 直近順 / 新が前、 ``RUN_HISTORY_MAXLEN`` まで
    """

    members: tuple[ArchiveMember, ...] = ()
    dataset_epoch_id: str = ""
    run_history: tuple[str, ...] = ()


@dataclass(frozen=True)
class InflowTargets:
    """:func:`compute_inflow_targets` の戻り値 (synthesis § 8.2).

    field:

    - ``target_inflow``: 当 Run の目標流入数 (mission + progress 寄与)
    - ``per_run_max``: ハード上限 (これを超えたら trim)
    - ``bypass_k``: score_bypass 採用上限 (mode で決まる min/max に clamp)
    - ``mode``: ``"normal"`` / ``"emergency"``
    """

    target_inflow: int
    per_run_max: int
    bypass_k: int
    mode: Literal["normal", "emergency"]


@dataclass(frozen=True)
class AdmissionReport:
    """:func:`archive_admit` 結果サマリ.

    詳細 Round 3 [W1] 反映: ``selected`` (hard constraint 前) と ``admitted``
    (実流入) を分離.

    field:

    - ``admitted_genome_ids``: 実流入した genome_id (hard constraint 通過後).
    - ``evicted_genome_ids``: eviction で archive から消えた genome_id
      (新規流入 + 既存合算で重複は除く).
    - ``n_selected_*``: hard constraint 前の階層別選抜数.
    - ``n_admitted_*``: hard constraint 後の階層別実流入数.
    - ``mode``: 当 Run の inflow mode.
    - ``hard_constraint_drops``: per_run_max / pattern_max_share による drop 数.
    - ``recency_floor_unmet``: 直近 :data:`RECENCY_FLOOR_LAST_N_RUNS` Run 由来 members が
      :data:`RECENCY_FLOOR_COUNT` 未満なら True (best-effort warning).
    - ``dataset_epoch_reset``: epoch 切替で archive がリセットされた場合 True.
    """

    admitted_genome_ids: tuple[str, ...]
    evicted_genome_ids: tuple[str, ...]
    n_selected_mission: int
    n_selected_progress: int
    n_selected_bypass: int
    n_admitted_mission: int
    n_admitted_progress: int
    n_admitted_bypass: int
    mode: Literal["normal", "emergency"]
    hard_constraint_drops: int
    recency_floor_unmet: bool
    dataset_epoch_reset: bool


# ============================================================================
# CPPS 2-state FSM (synthesis § 7.2)
# ============================================================================


def update_push_pull_state(
    prev: PushPullState,
    *,
    generation_no: int,
    feasible_ratio_ema: float,
    force_g: int,
    theta_switch: float,
    consecutive_n: int = 3,
) -> PushPullState:
    """``push`` → ``pull`` 一方向遷移を更新 (synthesis § 7.2).

    一方向性 (thrash 防止): 一度 ``pull`` に入ったら ``pull`` 維持.
    強制遷移: ``generation_no >= force_g`` なら ``pull`` (``forced_switch=True``).
    通常遷移: ``feasible_ratio_ema >= theta_switch`` が ``consecutive_n`` 世代連続で True.

    入口契約:

    - ``0.0 <= feasible_ratio_ema <= 1.0`` 必須 (範囲外で :class:`ValueError`)
    - ``generation_no >= 0``
    - ``consecutive_n >= 1``
    - ``force_g >= 0``
    - ``0.0 <= theta_switch <= 1.0``

    Args:
        prev: 直前世代の :class:`PushPullState`.
        generation_no: 現世代番号 (0-origin).
        feasible_ratio_ema: feasible 個体比率の EMA (caller=T071 観測値).
        force_g: 強制 ``pull`` 遷移世代.
        theta_switch: ``feasible_ratio_ema`` の遷移閾値.
        consecutive_n: 連続成立必要世代数.

    Returns:
        更新された :class:`PushPullState`.
    """
    if not (0.0 <= feasible_ratio_ema <= 1.0):
        raise ValueError(
            f"feasible_ratio_ema must be in [0, 1], got {feasible_ratio_ema}"
        )
    if generation_no < 0:
        raise ValueError(f"generation_no must be >= 0, got {generation_no}")
    if consecutive_n < 1:
        raise ValueError(f"consecutive_n must be >= 1, got {consecutive_n}")
    if force_g < 0:
        raise ValueError(f"force_g must be >= 0, got {force_g}")
    if not (0.0 <= theta_switch <= 1.0):
        raise ValueError(f"theta_switch must be in [0, 1], got {theta_switch}")

    # phase の未知値は status field 方式 (T058-T065 規範) で fail-fast.
    if prev.phase not in ("push", "pull"):
        raise ValueError(
            f"prev.phase must be 'push' or 'pull', got {prev.phase!r}"
        )
    if prev.phase == "pull":
        return replace(prev, last_feasible_ratio_ema=feasible_ratio_ema)

    # push → pull 判定 (forced 優先)
    if generation_no >= force_g:
        return PushPullState(
            phase="pull",
            consecutive_count=0,
            switch_generation=generation_no,
            last_feasible_ratio_ema=feasible_ratio_ema,
            forced_switch=True,
        )

    if feasible_ratio_ema >= theta_switch:
        new_count = prev.consecutive_count + 1
        if new_count >= consecutive_n:
            return PushPullState(
                phase="pull",
                consecutive_count=new_count,
                switch_generation=generation_no,
                last_feasible_ratio_ema=feasible_ratio_ema,
                forced_switch=False,
            )
        return replace(
            prev,
            consecutive_count=new_count,
            last_feasible_ratio_ema=feasible_ratio_ema,
        )
    return replace(
        prev,
        consecutive_count=0,
        last_feasible_ratio_ema=feasible_ratio_ema,
    )


def compute_ca_da_capacities(
    pop_size: int,
    phase: Literal["push", "pull"],
) -> tuple[int, int]:
    """state 依存 CA/DA capacity を返す.

    端数規約: ``CA = round(pop_size * ratio)``、 ``DA = pop_size - CA``.
    ``pop_size`` は :data:`SUPPORTED_POP_SIZES` (= 192 / 256) のみ正式サポート
    (詳細 Round 2 [C5]).

    Args:
        pop_size: 集団サイズ (192 or 256).
        phase: ``"push"`` or ``"pull"``.

    Returns:
        ``(ca_capacity, da_capacity)``.
    """
    if pop_size not in SUPPORTED_POP_SIZES:
        raise ValueError(
            f"pop_size must be one of {SUPPORTED_POP_SIZES}, got {pop_size}"
        )
    if phase not in ("push", "pull"):
        raise ValueError(f"phase must be 'push' or 'pull', got {phase!r}")
    ratio = PUSH_CA_RATIO if phase == "push" else PULL_CA_RATIO
    ca = round(pop_size * ratio)
    da = pop_size - ca
    return ca, da


def compute_archive_capacities(pop_size: int) -> tuple[int, int, int]:
    """archive ``(total, ca, da)`` 容量を返す (synthesis § 8.1).

    ``pop_size`` は :data:`SUPPORTED_POP_SIZES` (= 192 / 256) のみ正式サポート.

    Args:
        pop_size: 集団サイズ (192 or 256).

    Returns:
        ``(archive_total, ca_capacity, da_capacity)``.
    """
    if pop_size not in SUPPORTED_POP_SIZES:
        raise ValueError(
            f"pop_size must be one of {SUPPORTED_POP_SIZES}, got {pop_size}"
        )
    return _ARCHIVE_CAPS[pop_size]


# ============================================================================
# Survivor → CA/DA partition
# ============================================================================


def partition_survivors_to_ca_da(
    survivor_indices: Sequence[int],
    *,
    phase: Literal["push", "pull"],
    pop_size: int,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """state 依存比率で survivor を CA / DA に分割.

    入口契約 (T065 sort 順前提): ``survivor_indices`` は T065
    ``GenerationSelectionResult.survivor_indices`` で
    ``(rank, -crowding, genome_hash, index)`` の lex 昇順にソート済前提。
    T066 は **再 sort しない**.

    分割:

    - CA = 先頭 ``ca_cap`` 体 (rank/crowding 優位).
    - DA = 続く ``da_cap`` 体 (多様性保持).
    - eligible が ``pop_size`` 未満なら ``ca_indices + da_indices < pop_size``
      (caller 認識).

    Args:
        survivor_indices: T065 sort 済の生存個体 index 列.
        phase: 現状態 (``"push"`` / ``"pull"``).
        pop_size: 集団サイズ.

    Returns:
        ``(ca_indices, da_indices)``.
    """
    ca_cap, da_cap = compute_ca_da_capacities(pop_size, phase)
    survivors_list = list(survivor_indices)
    if len(survivors_list) > pop_size:
        raise ValueError(
            f"survivor count {len(survivors_list)} exceeds pop_size {pop_size}"
        )
    ca_indices = tuple(survivors_list[:ca_cap])
    da_indices = tuple(survivors_list[ca_cap : ca_cap + da_cap])
    return ca_indices, da_indices


# ============================================================================
# archive_role 判定 + Inflow targets
# ============================================================================


def determine_archive_role(
    bc_result: BCEvaluationResult | None,
) -> Literal[
    "mission_pass", "progress_pass", "score_bypass_candidate", "ineligible"
]:
    """T064 出力から ``archive_role`` を一意決定 (synthesis § 8.2).

    階層: ``mission_pass`` > ``progress_pass`` > ``score_bypass_candidate``
    > ``ineligible``.

    SSOT 整合性 (詳細設計 vs main 実装):
        詳細設計 (§ 11.2 / 施策 1) は ``bc_result.progress_pass`` 直アクセスを記述するが、
        T064 main 実装では ``progress_pass`` は :class:`StageCLiteResult` の field で、
        :class:`BCEvaluationResult` 直下には存在しない. 規範
        (= 詳細設計 vs main 実装の整合性検査、 不一致なら main 実装を SSOT) に従い、
        本実装では ``bc_result.c_lite_result.progress_pass`` を参照する.

    score_bypass 候補は ``pareto_axis_usable=True`` かつ ``b_pooled_cf is not None``
    の双方を要求 (synthesis § 8.2 仕様準拠). NaN / inf finite 性検証は **caller
    責務** (詳細 Round 1 [W2]).

    Args:
        bc_result: T064 :class:`BCEvaluationResult` (None 可、 個体非評価時).

    Returns:
        4 状態のいずれか.
    """
    if bc_result is None:
        return "ineligible"
    if bc_result.mission_pass == StagePassStatus.PASS:
        return "mission_pass"
    if bc_result.c_lite_result.progress_pass == StagePassStatus.PASS:
        return "progress_pass"
    if bc_result.pareto_axis_usable and bc_result.b_pooled_cf is not None:
        return "score_bypass_candidate"
    return "ineligible"


def compute_inflow_targets(
    pop_size: int,
    n_mission: int,
    n_progress: int,
    *,
    mode: Literal["normal", "emergency"],
) -> InflowTargets:
    """synthesis § 8.2 確定式で :class:`InflowTargets` を計算.

    ``pop_size`` は :data:`SUPPORTED_POP_SIZES` (= 192 / 256) のみ正式サポート.
    ``mode == "emergency"`` で ``target_inflow`` を +2、 ``bypass_k`` の clamp
    範囲を ``[4, 8]`` に拡張 (normal は ``[2, 6]``).

    Args:
        pop_size: 集団サイズ.
        n_mission: 当 Run の mission_pass 候補数.
        n_progress: 当 Run の progress_pass 候補数.
        mode: ``"normal"`` / ``"emergency"``.

    Returns:
        :class:`InflowTargets`.
    """
    if pop_size not in SUPPORTED_POP_SIZES:
        raise ValueError(
            f"pop_size must be one of {SUPPORTED_POP_SIZES}, got {pop_size}"
        )
    if n_mission < 0 or n_progress < 0:
        raise ValueError(
            f"n_mission/n_progress must be non-negative, "
            f"got {n_mission}/{n_progress}"
        )
    if mode not in ("normal", "emergency"):
        raise ValueError(f"mode must be 'normal' or 'emergency', got {mode!r}")

    target, per_run_max = _INFLOW_TARGETS[pop_size]
    if mode == "emergency":
        target += 2  # synthesis § 8.2 emergency
        bypass_min, bypass_max = 4, 8
    else:
        bypass_min, bypass_max = 2, 6

    bypass_k = max(bypass_min, min(bypass_max, target - n_mission - n_progress))
    return InflowTargets(
        target_inflow=target,
        per_run_max=per_run_max,
        bypass_k=bypass_k,
        mode=mode,
    )


# ============================================================================
# Private helpers (DRY)
# ============================================================================


def _to_member(
    c: ArchiveCandidate,
    *,
    archive_role: Literal["mission_pass", "progress_pass", "score_bypass"],
    archive_target: Literal["CA", "DA"],
) -> ArchiveMember:
    """:class:`ArchiveCandidate` → :class:`ArchiveMember` 変換."""
    return ArchiveMember(
        genome_id=c.genome_id,
        run_id=c.run_id,
        generation_no=c.generation_no,
        dataset_epoch_id=c.dataset_epoch_id,
        pattern_id=c.pattern_id,
        family_id=c.family_id,
        archive_role=archive_role,
        archive_target=archive_target,
        gate_worst_gap=c.gate_worst_gap,
        c_pass_depth=c.c_pass_depth,
        mission_signed_margin=c.mission_signed_margin,
        shadow_robustness_score=c.shadow_robustness_score,
        log_pf_clip=c.log_pf_clip,
        novelty=c.novelty,
        diversity_coverage=c.diversity_coverage,
        quality_floor_margin=c.quality_floor_margin,
        margin_inf=c.margin_inf,
        invariant_feasible=c.invariant_feasible,
    )


def _apply_hard_constraints(
    admitted: Sequence[ArchiveMember],
    archive_state: ArchiveState,
    pop_size: int,
    targets: InflowTargets,
) -> list[ArchiveMember]:
    """``per_run_max`` / ``pattern_max_share=0.25`` を適用 (synthesis § 8.3).

    手順:

    1. ``len(admitted) > targets.per_run_max`` なら role priority + 内部スコア
       (mission は ``mission_signed_margin`` 降順 / 他は ``gate_worst_gap`` 昇順)
       + ``genome_id`` 昇順で先頭 ``per_run_max`` 件に trim.
    2. ``pattern_max_share`` で archive 全体の同 ``pattern_id`` 上限まで filter.

    Args:
        admitted: trim/filter 前の :class:`ArchiveMember` 列.
        archive_state: 既存 archive (pattern count baseline).
        pop_size: 集団サイズ (archive_total 計算).
        targets: :class:`InflowTargets`.

    Returns:
        hard constraint 適用後の :class:`ArchiveMember` リスト.
    """
    if len(admitted) > targets.per_run_max:
        admitted = sorted(
            admitted,
            key=lambda m: (
                ARCHIVE_ROLE_PRIORITY[m.archive_role],
                -m.mission_signed_margin
                if m.archive_role == "mission_pass"
                else m.gate_worst_gap,
                m.genome_id,
            ),
        )[: targets.per_run_max]

    archive_total, _, _ = compute_archive_capacities(pop_size)
    pattern_cap = int(archive_total * PATTERN_MAX_SHARE)
    pattern_count: Counter[str] = Counter(
        m.pattern_id for m in archive_state.members
    )
    filtered: list[ArchiveMember] = []
    for m in admitted:
        if pattern_count[m.pattern_id] < pattern_cap:
            filtered.append(m)
            pattern_count[m.pattern_id] += 1
    return filtered


def _check_recency_floor_unmet(
    state: ArchiveState,
    *,
    floor_count: int = RECENCY_FLOOR_COUNT,
    last_n_runs: int = RECENCY_FLOOR_LAST_N_RUNS,
) -> bool:
    """直近 ``last_n_runs`` Run 由来 members が ``floor_count`` 未満なら True.

    Args:
        state: :class:`ArchiveState`.
        floor_count: 最低保持数.
        last_n_runs: 参照 Run 数.

    Returns:
        条件を満たさない (= warning) なら True.
    """
    last_runs = set(state.run_history[:last_n_runs])
    if not last_runs:
        return floor_count > 0
    recency_count = sum(1 for m in state.members if m.run_id in last_runs)
    return recency_count < floor_count


def _ca_eviction_sort_key(
    m: ArchiveMember,
    run_history: Sequence[str],
) -> tuple[
    bool, bool, bool, float, float, float, int, float, str
]:
    """CA lex eviction key 9 段 (synthesis Round 21 改訂後 + 概念 Round 1 [C5] genome_id 末尾).

    順:

    1. ``not is_mission`` (mission_pass を最優先で保持).
    2. ``not is_progress``.
    3. ``not m.not_score_bypass`` (= ``score_bypass`` を最後尾に).
    4. ``-m.c_pass_depth`` (大が上位、 T064 follow-up).
    5. ``-m.mission_signed_margin`` (大が上位).
    6. ``-m.shadow_robustness_score``.
    7. ``run_id_index`` (新が小、 = 上位).
    8. ``-m.log_pf_clip``.
    9. ``m.genome_id`` (deterministic tie-break).
    """
    is_mission = m.archive_role == "mission_pass"
    is_progress = m.archive_role == "progress_pass"
    run_id_index = (
        run_history.index(m.run_id) if m.run_id in run_history else len(run_history)
    )
    return (
        not is_mission,
        not is_progress,
        not m.not_score_bypass,
        -m.c_pass_depth,
        -m.mission_signed_margin,
        -m.shadow_robustness_score,
        run_id_index,
        -m.log_pf_clip,
        m.genome_id,
    )


def _da_eviction_sort_key(
    m: ArchiveMember,
    run_history: Sequence[str],
) -> tuple[float, float, bool, bool, float, int, float, str]:
    """DA lex eviction key 8 段.

    順:

    1. ``-m.novelty`` (大が上位).
    2. ``-m.diversity_coverage``.
    3. ``not is_progress``.
    4. ``not m.not_score_bypass``.
    5. ``-m.quality_floor_margin``.
    6. ``run_id_index``.
    7. ``-m.log_pf_clip``.
    8. ``m.genome_id``.
    """
    is_progress = m.archive_role == "progress_pass"
    run_id_index = (
        run_history.index(m.run_id) if m.run_id in run_history else len(run_history)
    )
    return (
        -m.novelty,
        -m.diversity_coverage,
        not is_progress,
        not m.not_score_bypass,
        -m.quality_floor_margin,
        run_id_index,
        -m.log_pf_clip,
        m.genome_id,
    )


# ============================================================================
# Archive admission (CA only、 詳細 Round 1 [C3])
# ============================================================================


def archive_admit(
    archive_state: ArchiveState,
    candidates: Mapping[str, ArchiveCandidate],
    *,
    pop_size: int,
    mode: Literal["normal", "emergency"],
) -> tuple[ArchiveState, AdmissionReport]:
    """CA admission 3 層流入 + ハード制約 + eviction を一括実施.

    Phase 1 では CA admission のみ実装 (DA admission は T067 warmstart 経路で別途、
    概念 Round 1 [C3]).

    入口契約 (詳細 Round 1 [C1] 反映):

    - ``candidates`` の各 ``(key, c)`` は ``key == c.genome_id`` 必須.
    - ``candidates`` 内で ``c.genome_id`` 重複は :class:`Mapping` 構造で禁止
      (key 重複は元から不可)。 ただし key と genome_id の不一致は明示 raise.
    - 違反は :class:`ValueError` raise (caller 責務違反 indicator).

    Args:
        archive_state: 既存 :class:`ArchiveState`.
        candidates: ``{genome_id: ArchiveCandidate}``.
        pop_size: 集団サイズ.
        mode: ``"normal"`` / ``"emergency"``.

    Returns:
        ``(new_state, AdmissionReport)``.
    """
    if pop_size not in SUPPORTED_POP_SIZES:
        raise ValueError(
            f"pop_size must be one of {SUPPORTED_POP_SIZES}, got {pop_size}"
        )

    # 入口契約: key == c.genome_id 検証 (詳細 Round 1 [C1])
    for key, c in candidates.items():
        if key != c.genome_id:
            raise ValueError(
                f"candidates key {key!r} does not match "
                f"candidate.genome_id {c.genome_id!r}"
            )

    # 0. 入力順固定 (genome_id 昇順、 dict iter 順依存性排除).
    sorted_candidates = sorted(candidates.items(), key=lambda kv: kv[0])

    # 1. 階層別カウント.
    n_mission = sum(
        1 for _, c in sorted_candidates if c.archive_role == "mission_pass"
    )
    n_progress = sum(
        1 for _, c in sorted_candidates if c.archive_role == "progress_pass"
    )
    targets = compute_inflow_targets(pop_size, n_mission, n_progress, mode=mode)

    # 2. mission_pass 全件 (mission_signed_margin 降順 + genome_id 昇順).
    mission_pool = [
        c for _, c in sorted_candidates if c.archive_role == "mission_pass"
    ]
    mission_admits = sorted(
        mission_pool,
        key=lambda c: (-c.mission_signed_margin, c.genome_id),
    )

    # 3. progress_pass: gate_worst_gap 昇順 + genome_id 昇順 で remaining inflow まで.
    remaining = max(0, targets.target_inflow - len(mission_admits))
    progress_pool = [
        c for _, c in sorted_candidates if c.archive_role == "progress_pass"
    ]
    progress_admits = sorted(
        progress_pool,
        key=lambda c: (c.gate_worst_gap, c.genome_id),
    )[:remaining]

    # 4. score_bypass: bypass_k 体、 品質床 (invariant_feasible ∧ margin_inf_passes_p70) 通過のみ.
    bypass_pool = [
        c
        for _, c in sorted_candidates
        if c.archive_role == "score_bypass_candidate"
        and c.invariant_feasible
        and c.margin_inf_passes_p70
    ]
    bypass_pool_sorted = sorted(
        bypass_pool,
        key=lambda c: (c.gate_worst_gap, c.genome_id),
    )[: targets.bypass_k]

    # 5. ArchiveCandidate → ArchiveMember 変換 (archive_target="CA"、 score_bypass_candidate → score_bypass).
    admitted_members: list[ArchiveMember] = []
    for c in mission_admits:
        admitted_members.append(
            _to_member(c, archive_role="mission_pass", archive_target="CA")
        )
    for c in progress_admits:
        admitted_members.append(
            _to_member(c, archive_role="progress_pass", archive_target="CA")
        )
    for c in bypass_pool_sorted:
        admitted_members.append(
            _to_member(c, archive_role="score_bypass", archive_target="CA")
        )

    # 6. ハード制約適用 (per_run_max + pattern_max_share).
    admitted_filtered = _apply_hard_constraints(
        admitted_members, archive_state, pop_size, targets
    )
    hard_drops = len(admitted_members) - len(admitted_filtered)

    # 7. archive merge (genome_id upsert で一意制約保持、 詳細 Round 3 [C1]).
    existing_by_id: dict[str, ArchiveMember] = {
        m.genome_id: m for m in archive_state.members
    }
    for nm in admitted_filtered:
        existing_by_id[nm.genome_id] = nm
    new_members_after_merge = tuple(existing_by_id.values())
    merged_state = replace(archive_state, members=new_members_after_merge)

    # 8. eviction (CA / DA capacity 超過時).
    _, ca_capacity, da_capacity = compute_archive_capacities(pop_size)
    state_after_ca = archive_evict_ca(merged_state, target_size=ca_capacity)
    new_state = archive_evict_da(state_after_ca, target_size=da_capacity)

    # 9. AdmissionReport 構築 (詳細 Round 2 [W1] + Round 3 [W1]).
    new_state_ids = {nm.genome_id for nm in new_state.members}
    evicted_pool: list[ArchiveMember] = list(archive_state.members) + list(
        admitted_filtered
    )
    seen_evicted: set[str] = set()
    evicted_ids: list[str] = []
    for m in evicted_pool:
        if m.genome_id in new_state_ids:
            continue
        if m.genome_id in seen_evicted:
            continue
        seen_evicted.add(m.genome_id)
        evicted_ids.append(m.genome_id)
    admitted_ids = tuple(m.genome_id for m in admitted_filtered)
    recency_unmet = _check_recency_floor_unmet(new_state)
    admitted_by_role: Counter[str] = Counter(
        m.archive_role for m in admitted_filtered
    )

    report = AdmissionReport(
        admitted_genome_ids=admitted_ids,
        evicted_genome_ids=tuple(evicted_ids),
        n_selected_mission=len(mission_admits),
        n_selected_progress=len(progress_admits),
        n_selected_bypass=len(bypass_pool_sorted),
        n_admitted_mission=admitted_by_role.get("mission_pass", 0),
        n_admitted_progress=admitted_by_role.get("progress_pass", 0),
        n_admitted_bypass=admitted_by_role.get("score_bypass", 0),
        mode=mode,
        hard_constraint_drops=hard_drops,
        recency_floor_unmet=recency_unmet,
        dataset_epoch_reset=False,
    )
    return new_state, report


# ============================================================================
# Archive eviction (CA / DA 別 lex)
# ============================================================================


def archive_evict_ca(
    state: ArchiveState, *, target_size: int
) -> ArchiveState:
    """CA capacity 超過時、 lex 末尾から削除して ``target_size`` 体に絞る.

    DA member は変更しない. ``target_size < 0`` で :class:`ValueError`.

    Args:
        state: :class:`ArchiveState`.
        target_size: CA 目標サイズ.

    Returns:
        新しい :class:`ArchiveState`.
    """
    if target_size < 0:
        raise ValueError(f"target_size must be >= 0, got {target_size}")
    ca_members = [m for m in state.members if m.archive_target == "CA"]
    if len(ca_members) <= target_size:
        return state
    sorted_ca = sorted(
        ca_members, key=lambda m: _ca_eviction_sort_key(m, state.run_history)
    )
    survivors = sorted_ca[:target_size]
    survivor_ids = {m.genome_id for m in survivors}
    new_members = tuple(
        m
        for m in state.members
        if m.archive_target != "CA" or m.genome_id in survivor_ids
    )
    return replace(state, members=new_members)


def archive_evict_da(
    state: ArchiveState, *, target_size: int
) -> ArchiveState:
    """DA capacity 超過時、 lex 末尾から削除して ``target_size`` 体に絞る.

    CA member は変更しない. ``target_size < 0`` で :class:`ValueError`.

    Args:
        state: :class:`ArchiveState`.
        target_size: DA 目標サイズ.

    Returns:
        新しい :class:`ArchiveState`.
    """
    if target_size < 0:
        raise ValueError(f"target_size must be >= 0, got {target_size}")
    da_members = [m for m in state.members if m.archive_target == "DA"]
    if len(da_members) <= target_size:
        return state
    sorted_da = sorted(
        da_members, key=lambda m: _da_eviction_sort_key(m, state.run_history)
    )
    survivors = sorted_da[:target_size]
    survivor_ids = {m.genome_id for m in survivors}
    new_members = tuple(
        m
        for m in state.members
        if m.archive_target != "DA" or m.genome_id in survivor_ids
    )
    return replace(state, members=new_members)


# ============================================================================
# Top-level entry per Run
# ============================================================================


def update_archive_per_run(
    prev_archive: ArchiveState,
    candidates: Mapping[str, ArchiveCandidate],
    *,
    pop_size: int,
    mode: Literal["normal", "emergency"],
    new_dataset_epoch_id: str,
    new_run_id: str,
) -> tuple[ArchiveState, AdmissionReport]:
    """top-level: epoch reset 検出 + run_history 先反映 + admission + eviction.

    詳細 Round 2 [C1] (recency 順序) + [W2] (epoch 汚染検証) 反映.

    入口契約 (詳細 Round 1 [C2] / [W1] / Round 2 [W2] 反映):

    - ``new_dataset_epoch_id`` / ``new_run_id`` 非空必須.
    - ``run_id`` は実質グローバル一意前提: caller (T067) は ``run_id`` を実行 ID 等で
      グローバル一意化する責務 (詳細 Round 2 [W2])。 T066 の同 run_id 再投入ガードは
      ``run_history[0]`` との一致のみ拒否、 古い ``run_id`` の再使用は caller 規約で防ぐ.
    - 全 candidate の ``c.dataset_epoch_id == new_dataset_epoch_id`` (epoch 一致).
    - 全 candidate の ``c.run_id == new_run_id`` (cross-run contamination guard).
    - ``prev_archive.run_history[0] == new_run_id`` は禁止 (同 ``run_id`` 再投入は
      :class:`ValueError`、 リトライ/再実行は caller 責務で異なる ``run_id`` を渡す).

    Args:
        prev_archive: 直前 Run までの :class:`ArchiveState`.
        candidates: 当 Run の ``{genome_id: ArchiveCandidate}``.
        pop_size: 集団サイズ.
        mode: ``"normal"`` / ``"emergency"``.
        new_dataset_epoch_id: 当 Run の dataset_epoch_id.
        new_run_id: 当 Run の run_id.

    Returns:
        ``(new_state, AdmissionReport)``. epoch reset 時は report.dataset_epoch_reset=True.
    """
    if not new_dataset_epoch_id:
        raise ValueError("new_dataset_epoch_id must be non-empty")
    if not new_run_id:
        raise ValueError("new_run_id must be non-empty")

    # 1. candidates 全件の epoch + run_id 一致検証 (詳細 Round 1 [C2]).
    for genome_id, c in candidates.items():
        if c.dataset_epoch_id != new_dataset_epoch_id:
            raise ValueError(
                f"candidate {genome_id} dataset_epoch_id={c.dataset_epoch_id!r} "
                f"does not match new_dataset_epoch_id={new_dataset_epoch_id!r}"
            )
        if c.run_id != new_run_id:
            raise ValueError(
                f"candidate {genome_id} run_id={c.run_id!r} "
                f"does not match new_run_id={new_run_id!r} "
                "(cross-run contamination)"
            )

    # 2. 同 run_id 再投入禁止 (詳細 Round 1 [W1]).
    if prev_archive.run_history and prev_archive.run_history[0] == new_run_id:
        raise ValueError(
            f"new_run_id={new_run_id!r} matches most recent run_history[0]; "
            "same run_id re-submission is not allowed "
            "(use a fresh run_id for retries)"
        )

    # 3. epoch 切替検出.
    epoch_reset = prev_archive.dataset_epoch_id != new_dataset_epoch_id
    if epoch_reset:
        base_archive = ArchiveState(
            members=(),
            dataset_epoch_id=new_dataset_epoch_id,
            run_history=(),
        )
    else:
        base_archive = prev_archive

    # 4. run_history 先反映 (詳細 Round 2 [C1]).
    new_run_history = (new_run_id, *base_archive.run_history)
    if len(new_run_history) > RUN_HISTORY_MAXLEN:
        new_run_history = new_run_history[:RUN_HISTORY_MAXLEN]
    base_with_history = replace(base_archive, run_history=new_run_history)

    # 5. archive_admit.
    new_state, report = archive_admit(
        base_with_history,
        candidates,
        pop_size=pop_size,
        mode=mode,
    )
    if epoch_reset:
        report = replace(report, dataset_epoch_reset=True)
    return new_state, report
