"""T071 Observability hub: RunObservabilityReport (A→B 乖離 / archive churn / bypass /
session entropy / feasible ratio / selection / inflow consistency / failure 集約).

設計参照:
    devnotes/20260430-1925-todo-T071-observability/detailed-design.md (Round 3 APPROVED)
    devnotes/20260430-1925-todo-T071-observability/conceptual-design.md (Round 2 APPROVED)

main 実装 SSOT 規範 (T058-T070 で確立):
    詳細設計の前提と main 実装の field 名/存在に乖離がある場合、 main 実装を SSOT
    として T071 側を調整。 具体的に以下の field は main 実装に **存在しない** ため、
    caller 注入式 (= 関数引数) に変更した:

    - T065 GenerationSelectionResult: ``pareto_front1_size`` / ``feasible_ratio`` /
      ``mean_constraint_violation`` / ``generation`` 不在。 ``front_assignments``
      (eligible のみの ``{idx: front_no (1-origin)}``) と ``survivor_indices`` は存在
      するため、 caller (Phase 2 run_ga.py) が front1 cardinality 等を事前計算して
      :func:`extract_selection_metrics` の引数として注入する。

    - T066 AdmissionReport: ``n_admitted_ca`` / ``n_admitted_da`` / ``n_evicted_ca``
      / ``n_evicted_da`` / ``n_admitted_by_role`` 不在。 main 実装は role 別 (=
      ``n_admitted_mission`` / ``n_admitted_progress`` / ``n_admitted_bypass``) と
      ``evicted_genome_ids`` を保持。 T071 は role 別 count から bypass ratio を計算、
      eviction count は ``len(evicted_genome_ids)`` で代替。

    - T066 ArchiveRole enum: 存在せず。 ``archive_role`` は Literal 文字列
      (``"mission_pass"`` / ``"progress_pass"`` / ``"score_bypass"``)。 T071 は
      ``ArchiveRole`` enum import を削除、 文字列 key で count 集計。

    - T066 ArchiveMember.session_pass_pattern: 不在。 caller (Phase 2 で T064
      result から計算) が pattern list (3 bit string ``"^[01]{3}$"``) を事前計算し
      :func:`compute_session_entropy` の引数として注入。

    - T067 WarmstartReport / WarmstartConfig: ``warmstart_share_target`` /
      ``warmstart_share_actual`` / ``per_source_run_violations`` 不在 (=
      ``WarmstartConfig`` 自体存在せず)。 main 実装の ``WarmstartReport.share`` を
      actual share として参照、 target は caller 注入。 ``per_source_run_violations``
      も caller 注入 (= 0 default)。

    - T068 RunFailureSummary: ``run_aborted`` field 不在。 main 実装は
      ``any_stage_all_failed`` を保持するため、 これを ``run_aborted`` 相当として
      抽出 (Phase 2 で run_ga.py の abort 判定と一致確認)。 ``fingerprint_dedup_top_n``
      は FailureSummary に不在のため caller 注入 (= 空 tuple default)。

T071 PR 1 範囲:
    - 本 module + ``__init__.py`` 公開 API export
    - F1-F15 unit test (``tests/alpha_factory/observability/test_run_metrics.py``)
    - ``docs/alpha_factory/stage-gates.md`` T071 セクション追記

Phase 2 申し送り:
    - ``scripts/alpha_factory/run_ga.py``: build_run_observability_report 呼び出し
      + 連続乖離 Run state file 保持 + log/report 出力
    - ``src/alpha_factory/stage_a_evaluator.py``: q_force_recommendation の caller
      配線 (StageAControllerState 更新)
    - ``docs/alpha_factory/observability.md`` 新設: 監視運用ガイド
    - run report Markdown 化: RunObservabilityReport を report.md に整形
    - divergence_threshold 再校正 (実測 corr 分布から、 T071 仮説値 0.30 を更新検討)
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Final, Literal

from src.alpha_factory.cpps_archive import AdmissionReport
from src.alpha_factory.failure_handling import (
    FailureSummary,
    RunFailureSummary,
    StageType,
)
from src.alpha_factory.loop_closure import WarmstartReport
from src.alpha_factory.nsga2_selection import GenerationSelectionResult

# ============================================================================
# 定数 (synthesis 確定値 + T071 仮説値、 Round 1 [C3] 反映で分離)
# ============================================================================

# synthesis § 8.7 確定値
DELTA_PER_RUN: Final[Decimal] = Decimal("0.02")
Q_FORCE_MAX: Final[Decimal] = Decimal("0.40")
RESTORE_THRESHOLD: Final[Decimal] = Decimal("0.50")

# T071 仮説値 (Round 1 [C3] 反映、 synthesis 未明示、 Phase 2 で再校正余地あり)
Q_FORCE_MIN: Final[Decimal] = Decimal("0.15")
DIVERGENCE_THRESHOLD: Final[Decimal] = Decimal("0.30")

# AB 相関の actionable 最小サンプルサイズ (Round 1 [C3] / [S2] 反映、 C7 規範準拠)
# n<10 で「相関 claim 禁止」 の C7 規範を統合し、 q_force 補正アクションを抑止
AB_MIN_ACTIONABLE_PAIRS: Final[int] = 10

# session_pass_pattern 入力 contract (Round 1 [C4] 反映、 3 bit string 固定)
SESSION_PATTERN_REGEX: Final[str] = r"^[01]{3}$"  # "000", "001", ..., "111"

# session bucket (T070 BLOCK_BUCKET_RANGES_UTC と整合、 3 bit パターン空間)
SESSION_PATTERN_BITS: Final[int] = 3  # Tokyo/London/NY
SESSION_PATTERN_SPACE_SIZE: Final[int] = 2**SESSION_PATTERN_BITS  # 8
WEEKLY_WINDOW_SIZE: Final[int] = 7  # weekly = 7 Run

# warmstart consistency tolerance
WARMSTART_SHARE_TOLERANCE: Final[Decimal] = Decimal("0.01")

# archive role 文字列 (= main 実装 SSOT、 ArchiveRole enum は不在)
ARCHIVE_ROLE_MISSION_PASS: Final[str] = "mission_pass"
ARCHIVE_ROLE_PROGRESS_PASS: Final[str] = "progress_pass"
ARCHIVE_ROLE_SCORE_BYPASS: Final[str] = "score_bypass"

_SESSION_PATTERN_RE: Final[re.Pattern[str]] = re.compile(SESSION_PATTERN_REGEX)


# ============================================================================
# AB Divergence
# ============================================================================

ABDivergenceStatus = Literal["ok", "insufficient_data", "zero_variance"]


@dataclass(frozen=True)
class ABDivergenceMetric:
    """A→B 乖離 Pearson correlation (B 評価対象個体集合に conditioning).

    SSOT: 概念設計 §3.2 / 詳細設計 §3.2 (Round 1 [C2] / [C3] / [S2] 反映で invariant
    強化).

    Attributes:
        status: 計算可否 (Round 2 [W2] 反映、 None 経路排除)。
        corr: Pearson correlation. ``status="ok"`` 以外では sentinel ``Decimal(0)``
            (使用禁止、 status を確認すること)。
        n_pairs: 計算に使った個体組数 (= B 評価済個体数)。

    invariant (Round 1 [C2] / [S1] 反映、 status 別 完全強制):
        ``status="ok"`` → ``corr ∈ [-1, 1]`` AND ``n_pairs >= AB_MIN_ACTIONABLE_PAIRS``
        ``status="insufficient_data"`` → ``corr == Decimal(0)`` AND
            ``n_pairs < AB_MIN_ACTIONABLE_PAIRS``
        ``status="zero_variance"`` → ``corr == Decimal(0)``
    """

    status: ABDivergenceStatus
    corr: Decimal
    n_pairs: int

    def __post_init__(self) -> None:
        if self.n_pairs < 0:
            raise ValueError(f"n_pairs must be >= 0, got {self.n_pairs}")

        if self.status == "ok":
            if not (Decimal(-1) <= self.corr <= Decimal(1)):
                raise ValueError(
                    f"corr must be in [-1, 1] when status='ok', got {self.corr}"
                )
            if self.n_pairs < AB_MIN_ACTIONABLE_PAIRS:
                raise ValueError(
                    f"status='ok' requires n_pairs >= {AB_MIN_ACTIONABLE_PAIRS} "
                    f"(C7 規範準拠), got {self.n_pairs}"
                )
        elif self.status == "insufficient_data":
            if self.corr != Decimal(0):
                raise ValueError(
                    f"status='insufficient_data' requires corr=0 sentinel, "
                    f"got {self.corr}"
                )
            if self.n_pairs >= AB_MIN_ACTIONABLE_PAIRS:
                raise ValueError(
                    f"status='insufficient_data' requires "
                    f"n_pairs < {AB_MIN_ACTIONABLE_PAIRS}, got {self.n_pairs}"
                )
        elif self.status == "zero_variance":
            if self.corr != Decimal(0):
                raise ValueError(
                    f"status='zero_variance' requires corr=0 sentinel, "
                    f"got {self.corr}"
                )
        else:
            raise ValueError(f"unknown status: {self.status!r}")


# ============================================================================
# Q Force Recommendation
# ============================================================================

QForceReason = Literal[
    "raise", "hold", "restore", "insufficient_data", "zero_variance"
]


@dataclass(frozen=True)
class QForceRecommendation:
    """A→B 乖離に応じた q_force 補正推奨 (synthesis § 8.7 + T071 仮説値).

    SSOT: 概念設計 §3.3.

    ``consecutive_divergent_runs`` は **caller 注入** (T071 側で履歴を保持しない)。
    Phase 2 で run_ga.py が state file 経由で連続乖離 Run カウントを更新し、
    本 dataclass に埋め込む。
    """

    new_q_force: Decimal
    delta: Decimal  # +0.02 / 0 / -0.02
    reason: QForceReason
    clamped_at_max: bool
    clamped_at_min: bool
    consecutive_divergent_runs: int  # caller 注入の値を report 用に保持

    def __post_init__(self) -> None:
        if not (Q_FORCE_MIN <= self.new_q_force <= Q_FORCE_MAX):
            raise ValueError(
                f"new_q_force must be in [{Q_FORCE_MIN}, {Q_FORCE_MAX}], "
                f"got {self.new_q_force}"
            )
        if self.consecutive_divergent_runs < 0:
            raise ValueError(
                f"consecutive_divergent_runs must be >= 0, "
                f"got {self.consecutive_divergent_runs}"
            )


# ============================================================================
# Archive Churn
# ============================================================================

ArchiveChurnStatus = Literal["ok", "insufficient_runs"]


@dataclass(frozen=True)
class ArchiveChurnMetric:
    """直近 N Run (max 3) の eviction 率 (synthesis § 10.1).

    SSOT: 概念設計 §3.4.

    main 実装 SSOT 注釈: T066 ``AdmissionReport`` には ``n_evicted_ca`` /
    ``n_evicted_da`` field 不在のため、 ``len(evicted_genome_ids)`` を eviction
    count として使う。 admission count は ``n_admitted_mission`` +
    ``n_admitted_progress`` + ``n_admitted_bypass`` の合算 (= 全 role 合計)。
    """

    status: ArchiveChurnStatus
    churn_rate: Decimal
    n_total_admissions: int
    n_total_evictions: int
    n_runs_used: int  # 1, 2, 3 のいずれか

    def __post_init__(self) -> None:
        if self.n_runs_used not in (1, 2, 3):
            raise ValueError(
                f"n_runs_used must be in (1, 2, 3), got {self.n_runs_used}"
            )
        if self.n_total_admissions < 0 or self.n_total_evictions < 0:
            raise ValueError("admission / eviction counts must be >= 0")
        if self.churn_rate < 0:
            raise ValueError(f"churn_rate must be >= 0, got {self.churn_rate}")
        if self.status == "ok":
            if self.n_runs_used != 3:
                raise ValueError(
                    f"status='ok' requires n_runs_used == 3, got {self.n_runs_used}"
                )
        elif self.status == "insufficient_runs":
            if self.n_runs_used not in (1, 2):
                raise ValueError(
                    f"status='insufficient_runs' requires n_runs_used in (1, 2), "
                    f"got {self.n_runs_used}"
                )
        else:
            raise ValueError(f"unknown status: {self.status!r}")


# ============================================================================
# Bypass Ratio
# ============================================================================


@dataclass(frozen=True)
class BypassRatioMetric:
    """archive 流入のうち score_bypass 経由の割合 (synthesis § 10.1).

    main 実装 SSOT 注釈: ``ArchiveRole`` enum 不在のため、 role 別 count は
    str key (``"mission_pass"`` / ``"progress_pass"`` / ``"score_bypass"``) で
    保持。
    """

    bypass_ratio: Decimal
    n_admitted_by_role: Mapping[str, int]
    n_total_admissions: int

    def __post_init__(self) -> None:
        if not (Decimal(0) <= self.bypass_ratio <= Decimal(1)):
            raise ValueError(
                f"bypass_ratio must be in [0, 1], got {self.bypass_ratio}"
            )
        if self.n_total_admissions < 0:
            raise ValueError(
                f"n_total_admissions must be >= 0, got {self.n_total_admissions}"
            )


# ============================================================================
# Session Entropy
# ============================================================================

SessionEntropyStatus = Literal["ok", "insufficient_window", "empty_archive"]


@dataclass(frozen=True)
class SessionEntropyMetric:
    """archive 内 session_pass_pattern 分布の Shannon entropy.

    SSOT: 概念設計 §3.6.

    main 実装 SSOT 注釈: ``ArchiveMember.session_pass_pattern`` field 不在のため、
    caller (Phase 2 で T064 result から計算) が pattern list (3 bit string
    ``"^[01]{3}$"``) を事前計算し :func:`compute_session_entropy` の引数として
    注入する。
    """

    status: SessionEntropyStatus
    shannon_entropy: Decimal
    relative_entropy: Decimal  # = shannon_entropy / log2(8)
    n_unique_patterns: int
    n_archive_members: int
    n_runs_aggregated: int

    def __post_init__(self) -> None:
        max_entropy = Decimal(SESSION_PATTERN_BITS)  # log2(8) = 3
        if not (Decimal(0) <= self.shannon_entropy <= max_entropy):
            raise ValueError(
                f"shannon_entropy must be in [0, {max_entropy}], "
                f"got {self.shannon_entropy}"
            )
        if not (Decimal(0) <= self.relative_entropy <= Decimal(1)):
            raise ValueError(
                f"relative_entropy must be in [0, 1], "
                f"got {self.relative_entropy}"
            )
        if (
            self.n_unique_patterns < 0
            or self.n_unique_patterns > SESSION_PATTERN_SPACE_SIZE
        ):
            raise ValueError(
                f"n_unique_patterns must be in [0, {SESSION_PATTERN_SPACE_SIZE}], "
                f"got {self.n_unique_patterns}"
            )
        if self.n_archive_members < 0:
            raise ValueError(
                f"n_archive_members must be >= 0, got {self.n_archive_members}"
            )
        if self.n_runs_aggregated < 0:
            raise ValueError(
                f"n_runs_aggregated must be >= 0, got {self.n_runs_aggregated}"
            )
        if self.status == "ok":
            if self.n_runs_aggregated < WEEKLY_WINDOW_SIZE:
                raise ValueError(
                    f"status='ok' requires n_runs_aggregated >= "
                    f"{WEEKLY_WINDOW_SIZE}, got {self.n_runs_aggregated}"
                )
            if self.n_archive_members == 0:
                raise ValueError(
                    "status='ok' requires n_archive_members > 0, got 0"
                )
        elif self.status == "insufficient_window":
            if self.n_runs_aggregated >= WEEKLY_WINDOW_SIZE:
                raise ValueError(
                    f"status='insufficient_window' requires "
                    f"n_runs_aggregated < {WEEKLY_WINDOW_SIZE}, "
                    f"got {self.n_runs_aggregated}"
                )
            if self.shannon_entropy != Decimal(0):
                raise ValueError(
                    f"status='insufficient_window' requires shannon_entropy=0, "
                    f"got {self.shannon_entropy}"
                )
            if self.relative_entropy != Decimal(0):
                raise ValueError(
                    f"status='insufficient_window' requires relative_entropy=0, "
                    f"got {self.relative_entropy}"
                )
            if self.n_unique_patterns != 0:
                raise ValueError(
                    f"status='insufficient_window' requires n_unique_patterns=0, "
                    f"got {self.n_unique_patterns}"
                )
        elif self.status == "empty_archive":
            if self.n_archive_members != 0:
                raise ValueError(
                    f"status='empty_archive' requires n_archive_members == 0, "
                    f"got {self.n_archive_members}"
                )
            if self.shannon_entropy != Decimal(0):
                raise ValueError(
                    f"status='empty_archive' requires shannon_entropy=0, "
                    f"got {self.shannon_entropy}"
                )
            if self.relative_entropy != Decimal(0):
                raise ValueError(
                    f"status='empty_archive' requires relative_entropy=0, "
                    f"got {self.relative_entropy}"
                )
            if self.n_unique_patterns != 0:
                raise ValueError(
                    f"status='empty_archive' requires n_unique_patterns=0, "
                    f"got {self.n_unique_patterns}"
                )
        else:
            raise ValueError(f"unknown status: {self.status!r}")


# ============================================================================
# Feasible Ratio
# ============================================================================


@dataclass(frozen=True)
class FeasibleRatioMetric:
    """Push/Pull FSM 切替指標 (T063 既存値の観測記録).

    main 実装 SSOT 注釈: T063 ``StageAControllerState`` から caller が値を
    抽出して T071 へ注入する想定 (T071 側では計算しない)。
    """

    feasible_ratio_ema: Decimal
    fsm_state: Literal["push", "pull"]
    n_feasible_individuals: int
    n_total_individuals: int

    def __post_init__(self) -> None:
        if not (Decimal(0) <= self.feasible_ratio_ema <= Decimal(1)):
            raise ValueError(
                f"feasible_ratio_ema must be in [0, 1], "
                f"got {self.feasible_ratio_ema}"
            )
        if self.n_feasible_individuals < 0 or self.n_total_individuals < 0:
            raise ValueError("individual counts must be >= 0")
        if self.n_feasible_individuals > self.n_total_individuals:
            raise ValueError(
                f"n_feasible ({self.n_feasible_individuals}) > "
                f"n_total ({self.n_total_individuals})"
            )
        if self.fsm_state not in ("push", "pull"):
            raise ValueError(
                f"fsm_state must be 'push' or 'pull', got {self.fsm_state!r}"
            )


# ============================================================================
# Selection Metric
# ============================================================================


@dataclass(frozen=True)
class SelectionMetric:
    """T065 GenerationSelectionResult からの抽出.

    main 実装 SSOT 注釈: T065 ``GenerationSelectionResult`` には
    ``pareto_front1_size`` / ``feasible_ratio`` / ``mean_constraint_violation`` /
    ``generation`` field 不在。 caller (Phase 2 run_ga.py) が
    ``front_assignments`` 等から事前計算して :func:`extract_selection_metrics`
    の引数として注入する。
    """

    front1_cardinality: int
    feasible_ratio: Decimal
    mean_constraint_violation: Decimal
    generation: int

    def __post_init__(self) -> None:
        if self.front1_cardinality < 0:
            raise ValueError(
                f"front1_cardinality must be >= 0, got {self.front1_cardinality}"
            )
        if not (Decimal(0) <= self.feasible_ratio <= Decimal(1)):
            raise ValueError(
                f"feasible_ratio must be in [0, 1], got {self.feasible_ratio}"
            )
        if self.mean_constraint_violation < Decimal(0):
            raise ValueError(
                f"mean_constraint_violation must be >= 0, "
                f"got {self.mean_constraint_violation}"
            )
        if self.generation < 0:
            raise ValueError(f"generation must be >= 0, got {self.generation}")


# ============================================================================
# Inflow Consistency
# ============================================================================


@dataclass(frozen=True)
class InflowConsistencyMetric:
    """warmstart + admission の inflow 設定通り動作確認 (Round 1 [C4] 命名統一).

    main 実装 SSOT 注釈:
        - ``WarmstartConfig`` 不在のため、 ``warmstart_share_target`` は caller
          注入 (= 設定値直接渡し)。
        - ``WarmstartReport.warmstart_share_actual`` 不在のため、 main 実装の
          ``WarmstartReport.share`` (float) を Decimal 化して actual 扱い。
        - ``per_source_run_violations`` 不在のため caller 注入 (= default 0)。
        - ``ArchiveRole`` enum 不在のため、 ``inflow_summary_by_role`` は str key。
    """

    warmstart_share_target: Decimal
    warmstart_share_actual: Decimal
    share_drift: Decimal  # = actual - target
    within_tolerance: bool  # |share_drift| <= WARMSTART_SHARE_TOLERANCE
    relaxation_steps_count: int
    per_source_run_violations: int  # max_per_source_run cap 越え件数
    ca_inflow_actual: int
    da_inflow_actual: int
    bypass_inflow_actual: int
    inflow_summary_by_role: Mapping[str, int]


# ============================================================================
# Failure Metric
# ============================================================================


@dataclass(frozen=True)
class FailureMetricStage:
    """per-stage failure metric (T068 FailureSummary 抽出).

    main 実装 SSOT 注釈: T068 ``FailureSummary`` には ``fingerprint_dedup_top_n``
    field 不在。 :func:`extract_failure_metrics` 引数で caller が注入する想定 (=
    default 空 tuple)。
    """

    stage: StageType
    n_failure_records: int
    n_failed_genomes: int
    eligible_individuals: int
    failure_rate: Decimal  # = n_failed_genomes / max(eligible_individuals, 1)
    fingerprint_top_3: tuple[tuple[str, int], ...]  # (fingerprint, count) top 3

    def __post_init__(self) -> None:
        if not (Decimal(0) <= self.failure_rate <= Decimal(1)):
            raise ValueError(
                f"failure_rate must be in [0, 1], got {self.failure_rate}"
            )
        if self.n_failure_records < 0 or self.n_failed_genomes < 0:
            raise ValueError("failure counts must be >= 0")
        if self.eligible_individuals < 0:
            raise ValueError(
                f"eligible_individuals must be >= 0, got {self.eligible_individuals}"
            )


@dataclass(frozen=True)
class FailureMetric:
    """T068 RunFailureSummary からの抽出.

    main 実装 SSOT 注釈: ``run_aborted`` field 不在のため、
    ``any_stage_all_failed`` を ``run_aborted`` 相当として抽出する。
    """

    run_id: str
    run_aborted: bool
    per_stage: tuple[FailureMetricStage, ...]


# ============================================================================
# RunObservabilityReport (集約)
# ============================================================================


@dataclass(frozen=True)
class RunObservabilityReport:
    """1 Run 全体の observability 集約 (Round 2 [W2] 反映で None 排除)."""

    run_id: str
    dataset_epoch_id: str
    generation_count: int

    ab_divergence: ABDivergenceMetric
    q_force_recommendation: QForceRecommendation
    archive_churn: ArchiveChurnMetric
    bypass_ratio: BypassRatioMetric
    session_entropy: SessionEntropyMetric
    feasible_ratio: FeasibleRatioMetric
    selection: SelectionMetric
    inflow_consistency: InflowConsistencyMetric
    failure: FailureMetric

    def __post_init__(self) -> None:
        if not self.run_id or not isinstance(self.run_id, str):
            raise ValueError(f"run_id must be non-empty str, got {self.run_id!r}")
        if not self.dataset_epoch_id or not isinstance(
            self.dataset_epoch_id, str
        ):
            raise ValueError(
                f"dataset_epoch_id must be non-empty str, "
                f"got {self.dataset_epoch_id!r}"
            )
        if self.generation_count < 0:
            raise ValueError(
                f"generation_count must be >= 0, got {self.generation_count}"
            )


# ============================================================================
# Algorithm: A→B Divergence
# ============================================================================


def compute_ab_divergence_on_b_evaluated(
    a_proxy_scores_b_evaluated: Sequence[Decimal],
    b_pooled_scores: Sequence[Decimal],
) -> ABDivergenceMetric:
    """A→B 乖離 Pearson correlation を計算 (B 評価対象個体集合に conditioning).

    SSOT: 概念設計 §3.2 / §5.1.

    Round 1 [C3] / [S2] 反映: C7 規範準拠で n<10 を非アクション化 (=
    insufficient_data)。 zero variance は status="zero_variance" sentinel。
    数値誤差での [-1, 1] 越境は clamp。
    """
    if len(a_proxy_scores_b_evaluated) != len(b_pooled_scores):
        raise ValueError(
            f"length mismatch: a_proxy={len(a_proxy_scores_b_evaluated)} "
            f"vs b_pooled={len(b_pooled_scores)}"
        )
    n = len(a_proxy_scores_b_evaluated)
    if n < AB_MIN_ACTIONABLE_PAIRS:
        return ABDivergenceMetric(
            status="insufficient_data", corr=Decimal(0), n_pairs=n,
        )

    a_mean = sum(a_proxy_scores_b_evaluated, Decimal(0)) / Decimal(n)
    b_mean = sum(b_pooled_scores, Decimal(0)) / Decimal(n)
    a_dev = [a - a_mean for a in a_proxy_scores_b_evaluated]
    b_dev = [b - b_mean for b in b_pooled_scores]
    cov = sum(
        (ad * bd for ad, bd in zip(a_dev, b_dev, strict=True)), Decimal(0)
    ) / Decimal(n)
    var_a = sum((ad * ad for ad in a_dev), Decimal(0)) / Decimal(n)
    var_b = sum((bd * bd for bd in b_dev), Decimal(0)) / Decimal(n)

    if var_a == Decimal(0) or var_b == Decimal(0):
        return ABDivergenceMetric(
            status="zero_variance", corr=Decimal(0), n_pairs=n,
        )

    # Decimal で sqrt: math.sqrt 経由 (= float 経由)、 結果を Decimal に戻す
    denom_float = math.sqrt(float(var_a) * float(var_b))
    corr_raw = cov / Decimal(repr(denom_float))

    # 数値誤差で [-1, 1] 越境時は clamp
    corr = max(Decimal(-1), min(Decimal(1), corr_raw))

    return ABDivergenceMetric(status="ok", corr=corr, n_pairs=n)


# ============================================================================
# Algorithm: Q Force Recommendation
# ============================================================================


def recommend_q_force_adjust(
    current_q_force: Decimal,
    divergence: ABDivergenceMetric,
    consecutive_divergent_runs: int,
    *,
    delta_per_run: Decimal = DELTA_PER_RUN,
    q_force_max: Decimal = Q_FORCE_MAX,
    restore_threshold: Decimal = RESTORE_THRESHOLD,
    q_force_min: Decimal = Q_FORCE_MIN,
    divergence_threshold: Decimal = DIVERGENCE_THRESHOLD,
) -> QForceRecommendation:
    """A→B 乖離に応じた q_force 補正推奨.

    SSOT: 概念設計 §3.3 / §5.2.

    delta 適用 → max/min clamp の順 (F15)。 hysteresis: divergence_threshold (0.30)
    < restore_threshold (0.50) で振動防止 (F5)。
    """
    if not (q_force_min <= current_q_force <= q_force_max):
        raise ValueError(
            f"current_q_force must be in [{q_force_min}, {q_force_max}], "
            f"got {current_q_force}"
        )
    if consecutive_divergent_runs < 0:
        raise ValueError(
            f"consecutive_divergent_runs must be >= 0, "
            f"got {consecutive_divergent_runs}"
        )

    if divergence.status == "insufficient_data":
        return QForceRecommendation(
            new_q_force=current_q_force,
            delta=Decimal(0),
            reason="insufficient_data",
            clamped_at_max=False,
            clamped_at_min=False,
            consecutive_divergent_runs=consecutive_divergent_runs,
        )
    if divergence.status == "zero_variance":
        return QForceRecommendation(
            new_q_force=current_q_force,
            delta=Decimal(0),
            reason="zero_variance",
            clamped_at_max=False,
            clamped_at_min=False,
            consecutive_divergent_runs=consecutive_divergent_runs,
        )

    # status == "ok"
    corr = divergence.corr
    if corr < divergence_threshold:
        # raise (= q_force 引き上げ)
        new_raw = current_q_force + delta_per_run
        new_q_force = min(new_raw, q_force_max)
        return QForceRecommendation(
            new_q_force=new_q_force,
            delta=new_q_force - current_q_force,
            reason="raise",
            clamped_at_max=(new_raw > q_force_max),
            clamped_at_min=False,
            consecutive_divergent_runs=consecutive_divergent_runs,
        )
    if corr >= restore_threshold:
        # restore (= q_force 戻し)
        new_raw = current_q_force - delta_per_run
        new_q_force = max(new_raw, q_force_min)
        return QForceRecommendation(
            new_q_force=new_q_force,
            delta=new_q_force - current_q_force,
            reason="restore",
            clamped_at_max=False,
            clamped_at_min=(new_raw < q_force_min),
            consecutive_divergent_runs=consecutive_divergent_runs,
        )
    # hysteresis 中間: hold
    return QForceRecommendation(
        new_q_force=current_q_force,
        delta=Decimal(0),
        reason="hold",
        clamped_at_max=False,
        clamped_at_min=False,
        consecutive_divergent_runs=consecutive_divergent_runs,
    )


# ============================================================================
# Algorithm: Archive Churn
# ============================================================================


def _admission_total(report: AdmissionReport) -> int:
    """1 ``AdmissionReport`` の全 role 合算 admission count."""
    return (
        report.n_admitted_mission
        + report.n_admitted_progress
        + report.n_admitted_bypass
    )


def compute_archive_churn(
    recent_admission_reports: Sequence[AdmissionReport],
) -> ArchiveChurnMetric:
    """直近 N Run (max 3) の eviction 率を計算.

    SSOT: 概念設計 §3.4 / §5.3.

    main 実装 SSOT 注釈: ``n_evicted_ca`` / ``n_evicted_da`` 不在のため、
    ``len(evicted_genome_ids)`` を eviction count とする。 admission count は
    全 role 合算。
    """
    if len(recent_admission_reports) == 0:
        raise ValueError("recent_admission_reports must be non-empty")
    n_runs_used = min(len(recent_admission_reports), 3)
    reports = list(recent_admission_reports[-n_runs_used:])  # 直近 N 件

    total_admissions = sum(_admission_total(r) for r in reports)
    total_evictions = sum(len(r.evicted_genome_ids) for r in reports)

    churn_rate = (
        Decimal(total_evictions) / Decimal(total_admissions)
        if total_admissions > 0
        else Decimal(0)
    )

    status: ArchiveChurnStatus = (
        "ok" if n_runs_used == 3 else "insufficient_runs"
    )

    return ArchiveChurnMetric(
        status=status,
        churn_rate=churn_rate,
        n_total_admissions=total_admissions,
        n_total_evictions=total_evictions,
        n_runs_used=n_runs_used,
    )


# ============================================================================
# Algorithm: Bypass Ratio
# ============================================================================


def compute_bypass_ratio(report: AdmissionReport) -> BypassRatioMetric:
    """1 Run の bypass 比率.

    SSOT: 概念設計 §3.5 / §5.4.

    main 実装 SSOT 注釈: ``n_admitted_by_role`` 不在のため、 main 実装の role 別
    field (``n_admitted_mission`` / ``n_admitted_progress`` / ``n_admitted_bypass``)
    を str key dict に集約する。
    """
    role_counts: dict[str, int] = {
        ARCHIVE_ROLE_MISSION_PASS: report.n_admitted_mission,
        ARCHIVE_ROLE_PROGRESS_PASS: report.n_admitted_progress,
        ARCHIVE_ROLE_SCORE_BYPASS: report.n_admitted_bypass,
    }
    total = sum(role_counts.values())
    bypass_count = role_counts[ARCHIVE_ROLE_SCORE_BYPASS]
    bypass_ratio = (
        Decimal(bypass_count) / Decimal(total) if total > 0 else Decimal(0)
    )
    return BypassRatioMetric(
        bypass_ratio=bypass_ratio,
        n_admitted_by_role=role_counts,
        n_total_admissions=total,
    )


# ============================================================================
# Algorithm: Session Entropy
# ============================================================================


def compute_session_entropy(
    session_pass_patterns: Sequence[str],
    n_runs_aggregated: int,
    *,
    weekly_window_size: int = WEEKLY_WINDOW_SIZE,
) -> SessionEntropyMetric:
    """archive 内 session_pass_pattern 分布の Shannon entropy.

    SSOT: 概念設計 §3.6 / §5.5.

    main 実装 SSOT 注釈: ``ArchiveMember.session_pass_pattern`` field 不在のため、
    caller (Phase 2 で T064 result から計算) が pattern list (3 bit string
    ``"^[01]{3}$"``) を事前計算して **本関数の引数** で注入する。 pattern が
    SESSION_PATTERN_REGEX に違反する場合は :class:`ValueError`。

    Args:
        session_pass_patterns: archive member 由来の 3 bit string 列。
        n_runs_aggregated: caller 管理の weekly window 数 (= aggregate された
            Run 数)。 weekly_window_size 未到達なら status="insufficient_window"。
        weekly_window_size: weekly window 閾値 (default 7)。

    Returns:
        :class:`SessionEntropyMetric`.
    """
    if n_runs_aggregated < 0:
        raise ValueError(
            f"n_runs_aggregated must be >= 0, got {n_runs_aggregated}"
        )

    n_members = len(session_pass_patterns)

    # status 判定 1: weekly window 未到達
    if n_runs_aggregated < weekly_window_size:
        return SessionEntropyMetric(
            status="insufficient_window",
            shannon_entropy=Decimal(0),
            relative_entropy=Decimal(0),
            n_unique_patterns=0,
            n_archive_members=n_members,
            n_runs_aggregated=n_runs_aggregated,
        )

    # status 判定 2: empty archive
    if n_members == 0:
        return SessionEntropyMetric(
            status="empty_archive",
            shannon_entropy=Decimal(0),
            relative_entropy=Decimal(0),
            n_unique_patterns=0,
            n_archive_members=0,
            n_runs_aggregated=n_runs_aggregated,
        )

    # 出現頻度を集計 (= Shannon entropy 計算)
    # Round 1 [C4] / [S3] 反映: session_pass_pattern は 3 bit string 固定
    pattern_counts: dict[str, int] = {}
    for pattern in session_pass_patterns:
        if not _SESSION_PATTERN_RE.match(pattern):
            raise ValueError(
                f"session_pass_pattern must match {SESSION_PATTERN_REGEX} "
                f"(3 bit string '000'-'111'), got {pattern!r}"
            )
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

    total = sum(pattern_counts.values())
    # Shannon entropy: H = -sum(p_i * log2(p_i))
    h = Decimal(0)
    for count in pattern_counts.values():
        if count > 0:
            p = Decimal(count) / Decimal(total)
            # log2(p) を float 経由で計算、 Decimal に戻す
            log2_p = Decimal(repr(math.log2(float(p))))
            h -= p * log2_p

    # 数値誤差で max_entropy をわずかに超える場合 clamp
    max_entropy = Decimal(SESSION_PATTERN_BITS)  # log2(8) = 3
    if h < Decimal(0):
        h = Decimal(0)
    if h > max_entropy:
        h = max_entropy
    relative = h / max_entropy if max_entropy > 0 else Decimal(0)
    if relative > Decimal(1):
        relative = Decimal(1)

    return SessionEntropyMetric(
        status="ok",
        shannon_entropy=h,
        relative_entropy=relative,
        n_unique_patterns=len(pattern_counts),
        n_archive_members=n_members,
        n_runs_aggregated=n_runs_aggregated,
    )


# ============================================================================
# Algorithm: Extract Functions (T065-T068 dataclass → T071 metric)
# ============================================================================


def extract_selection_metrics(
    result: GenerationSelectionResult,
    *,
    feasible_ratio: Decimal,
    mean_constraint_violation: Decimal,
    generation: int,
) -> SelectionMetric:
    """T065 ``GenerationSelectionResult`` から SelectionMetric を抽出.

    main 実装 SSOT 注釈: T065 main 実装には ``pareto_front1_size`` /
    ``feasible_ratio`` / ``mean_constraint_violation`` / ``generation`` field
    不在のため、 caller (Phase 2 run_ga.py) が ``front_assignments`` から
    front1 cardinality (= ``front_no=1`` の件数) を事前計算しない代わりに、
    本関数内で ``front_assignments`` の値が 1 のものを数える。 残り 3 field は
    caller 注入 (引数) で受ける。

    Args:
        result: T065 :class:`GenerationSelectionResult`.
        feasible_ratio: caller 注入 (T063 / T065 評価結果から計算)。
        mean_constraint_violation: caller 注入 (T063 / T064 評価結果から計算)。
        generation: caller 注入 (現世代番号)。

    Returns:
        :class:`SelectionMetric`.
    """
    # front_assignments は eligible のみの dict[idx, front_no (1-origin)]
    # front1 cardinality = front_no==1 の件数
    front1_cardinality = sum(
        1 for fno in result.front_assignments.values() if fno == 1
    )
    return SelectionMetric(
        front1_cardinality=front1_cardinality,
        feasible_ratio=feasible_ratio,
        mean_constraint_violation=mean_constraint_violation,
        generation=generation,
    )


def extract_inflow_consistency(
    warmstart_report: WarmstartReport,
    admission_report: AdmissionReport,
    *,
    warmstart_share_target: Decimal,
    per_source_run_violations: int = 0,
    tolerance: Decimal = WARMSTART_SHARE_TOLERANCE,
) -> InflowConsistencyMetric:
    """warmstart + admission の inflow 整合性を抽出.

    main 実装 SSOT 注釈:
        - ``WarmstartConfig`` 不在のため、 ``warmstart_share_target`` を caller
          注入 (= 設定値直接渡し)。
        - ``WarmstartReport.warmstart_share_actual`` 不在のため、 main 実装の
          ``WarmstartReport.share`` (float) を Decimal 化して actual 扱い。
        - ``WarmstartReport.per_source_run_violations`` 不在のため caller 注入
          (= default 0)。
        - ``AdmissionReport.n_admitted_ca`` / ``n_admitted_da`` 不在のため、
          mission_pass + progress_pass + score_bypass の合算を CA inflow 相当
          として扱う (= main 実装の T066 archive は CA only、 詳細設計 §
          partition_survivors_to_ca_da の CA-first 規範準拠)。 ``da_inflow_actual``
          は 0 default (Phase 2 で DA inflow が分離された場合 caller 側で
          override)。

    Args:
        warmstart_report: T067 :class:`WarmstartReport`.
        admission_report: T066 :class:`AdmissionReport`.
        warmstart_share_target: 設定 target share (caller 注入)。
        per_source_run_violations: source-run cap 越え件数 (caller 注入)。
        tolerance: drift 許容範囲 (default 0.01)。

    Returns:
        :class:`InflowConsistencyMetric`.
    """
    if per_source_run_violations < 0:
        raise ValueError(
            f"per_source_run_violations must be >= 0, "
            f"got {per_source_run_violations}"
        )
    target = warmstart_share_target
    actual = Decimal(repr(warmstart_report.share))
    drift = actual - target

    role_counts: dict[str, int] = {
        ARCHIVE_ROLE_MISSION_PASS: admission_report.n_admitted_mission,
        ARCHIVE_ROLE_PROGRESS_PASS: admission_report.n_admitted_progress,
        ARCHIVE_ROLE_SCORE_BYPASS: admission_report.n_admitted_bypass,
    }
    ca_inflow_actual = sum(role_counts.values())
    bypass_inflow_actual = role_counts[ARCHIVE_ROLE_SCORE_BYPASS]

    return InflowConsistencyMetric(
        warmstart_share_target=target,
        warmstart_share_actual=actual,
        share_drift=drift,
        within_tolerance=(abs(drift) <= tolerance),
        relaxation_steps_count=len(warmstart_report.relaxation_steps),
        per_source_run_violations=per_source_run_violations,
        ca_inflow_actual=ca_inflow_actual,
        da_inflow_actual=0,
        bypass_inflow_actual=bypass_inflow_actual,
        inflow_summary_by_role=role_counts,
    )


def extract_failure_metrics(
    summary: RunFailureSummary,
    *,
    fingerprint_top_n_by_stage: (
        Mapping[StageType, tuple[tuple[str, int], ...]] | None
    ) = None,
) -> FailureMetric:
    """T068 ``RunFailureSummary`` から FailureMetric を抽出.

    main 実装 SSOT 注釈:
        - ``RunFailureSummary.run_aborted`` 不在のため、 ``any_stage_all_failed``
          を ``run_aborted`` 相当として抽出 (Phase 2 で run_ga.py の abort 判定
          と一致確認)。
        - ``FailureSummary.fingerprint_dedup_top_n`` 不在のため、 caller 注入
          (= per-stage の top fingerprint dict、 default 空)。

    Args:
        summary: T068 :class:`RunFailureSummary`.
        fingerprint_top_n_by_stage: stage→top fingerprint mapping (caller 注入)。

    Returns:
        :class:`FailureMetric`.
    """
    fp_map: Mapping[StageType, tuple[tuple[str, int], ...]] = (
        fingerprint_top_n_by_stage if fingerprint_top_n_by_stage is not None
        else {}
    )

    per_stage = tuple(
        _build_failure_metric_stage(s, fp_map.get(s.stage, ()))
        for s in summary.per_stage_summaries
    )
    return FailureMetric(
        run_id=summary.run_id,
        run_aborted=summary.any_stage_all_failed,
        per_stage=per_stage,
    )


def _build_failure_metric_stage(
    s: FailureSummary,
    fingerprint_top_n: tuple[tuple[str, int], ...],
) -> FailureMetricStage:
    """FailureSummary → FailureMetricStage 変換 (内部 helper)."""
    failure_rate = (
        Decimal(s.n_failed_genomes) / Decimal(max(s.eligible_individuals, 1))
    )
    # 数値誤差で 1 を超えた場合は clamp (= eligible == 0 で分母 1 fallback の場合)
    if failure_rate > Decimal(1):
        failure_rate = Decimal(1)
    return FailureMetricStage(
        stage=s.stage,
        n_failure_records=s.n_failure_records,
        n_failed_genomes=s.n_failed_genomes,
        eligible_individuals=s.eligible_individuals,
        failure_rate=failure_rate,
        fingerprint_top_3=fingerprint_top_n[:3],
    )


# ============================================================================
# Aggregator: build_run_observability_report
# ============================================================================


def build_run_observability_report(
    run_id: str,
    dataset_epoch_id: str,
    generation_count: int,
    *,
    ab_divergence: ABDivergenceMetric,
    q_force_recommendation: QForceRecommendation,
    archive_churn: ArchiveChurnMetric,
    bypass_ratio: BypassRatioMetric,
    session_entropy: SessionEntropyMetric,
    feasible_ratio: FeasibleRatioMetric,
    selection: SelectionMetric,
    inflow_consistency: InflowConsistencyMetric,
    failure: FailureMetric,
) -> RunObservabilityReport:
    """1 Run の集約 report を構築する pure function."""
    return RunObservabilityReport(
        run_id=run_id,
        dataset_epoch_id=dataset_epoch_id,
        generation_count=generation_count,
        ab_divergence=ab_divergence,
        q_force_recommendation=q_force_recommendation,
        archive_churn=archive_churn,
        bypass_ratio=bypass_ratio,
        session_entropy=session_entropy,
        feasible_ratio=feasible_ratio,
        selection=selection,
        inflow_consistency=inflow_consistency,
        failure=failure,
    )


# ============================================================================
# T080a: Stub builder for Phase 2 配線 first step
# ============================================================================


# ============================================================================
# T081 step 1: 個別 metric default constructor (= stub builder の DRY 化)
# ============================================================================
#
# T080a の build_stub_run_observability_report が monolithic に 9 metric を構築
# していたのを、 metric 単位の default constructor 8 件 + ABDivergence default 1 件
# (= 計 9 件) に分解する。 step 1 caller (run_ga.py) が ABDivergence のみ実値で
# 構築し、 残り 8 件は default constructor で stub default を取得する用途。
# 後続 step 2-6 で各 default constructor が実値に置換される。
#
# 互換性契約 (Codex Round 2 [Suggestion] 1 取込): default constructor 8 件 +
# ABDivergence default の combine 戻り値が、 既存 build_stub_run_observability_report
# の戻り値と完全 equality (= JSON serialize で byte-for-byte 一致)。


def build_default_ab_divergence_metric() -> ABDivergenceMetric:
    """T080a stub default の ABDivergenceMetric (= n_pairs=0 / insufficient_data)."""
    return ABDivergenceMetric(
        status="insufficient_data",
        corr=Decimal(0),
        n_pairs=0,
    )


def build_default_q_force_recommendation() -> QForceRecommendation:
    """T080a stub default の QForceRecommendation (= 連続乖離 Run カウント 0)."""
    return QForceRecommendation(
        new_q_force=Q_FORCE_MIN,
        delta=Decimal(0),
        reason="insufficient_data",
        clamped_at_max=False,
        clamped_at_min=False,
        consecutive_divergent_runs=0,
    )


def build_default_archive_churn_metric() -> ArchiveChurnMetric:
    """T080a stub default の ArchiveChurnMetric (= 直近 Run 1 件のみ、 insufficient_runs)."""
    return ArchiveChurnMetric(
        status="insufficient_runs",
        churn_rate=Decimal(0),
        n_total_admissions=0,
        n_total_evictions=0,
        n_runs_used=1,
    )


def build_default_bypass_ratio_metric() -> BypassRatioMetric:
    """T080a stub default の BypassRatioMetric (= 全 role count 0)."""
    return BypassRatioMetric(
        bypass_ratio=Decimal(0),
        n_admitted_by_role={
            ARCHIVE_ROLE_MISSION_PASS: 0,
            ARCHIVE_ROLE_PROGRESS_PASS: 0,
            ARCHIVE_ROLE_SCORE_BYPASS: 0,
        },
        n_total_admissions=0,
    )


def build_default_session_entropy_metric() -> SessionEntropyMetric:
    """T080a stub default の SessionEntropyMetric (= empty_archive)."""
    return SessionEntropyMetric(
        status="empty_archive",
        shannon_entropy=Decimal(0),
        relative_entropy=Decimal(0),
        n_unique_patterns=0,
        n_archive_members=0,
        n_runs_aggregated=0,
    )


def build_default_feasible_ratio_metric() -> FeasibleRatioMetric:
    """T080a stub default の FeasibleRatioMetric (= n_total=0、 fsm push)."""
    return FeasibleRatioMetric(
        feasible_ratio_ema=Decimal(0),
        fsm_state="push",
        n_feasible_individuals=0,
        n_total_individuals=0,
    )


def build_default_selection_metric() -> SelectionMetric:
    """T080a stub default の SelectionMetric (= front1=0 / 全 0)."""
    return SelectionMetric(
        front1_cardinality=0,
        feasible_ratio=Decimal(0),
        mean_constraint_violation=Decimal(0),
        generation=0,
    )


def build_default_inflow_consistency_metric() -> InflowConsistencyMetric:
    """T080a stub default の InflowConsistencyMetric (= 全 0、 within_tolerance)."""
    return InflowConsistencyMetric(
        warmstart_share_target=Decimal(0),
        warmstart_share_actual=Decimal(0),
        share_drift=Decimal(0),
        within_tolerance=True,
        relaxation_steps_count=0,
        per_source_run_violations=0,
        ca_inflow_actual=0,
        da_inflow_actual=0,
        bypass_inflow_actual=0,
        inflow_summary_by_role={},
    )


def build_default_failure_metric(run_id: str) -> FailureMetric:
    """T080a stub default の FailureMetric (= run_aborted=False / per_stage 空)."""
    return FailureMetric(
        run_id=run_id,
        run_aborted=False,
        per_stage=(),
    )


def build_stub_run_observability_report(
    *,
    run_id: str,
    dataset_epoch_id: str,
    generation_count: int,
) -> RunObservabilityReport:
    """T080a Phase 2 配線 first step: 9 metric を stub 値で構築する.

    後続別 TODO (T080b-g 相当 = T081 step 1-6) で各 metric を実値配線に置換予定.
    本 stub builder は run_ga.py から ``build_run_observability_report`` を
    呼び出して ``RunObservabilityReport`` を JSON 出力する経路を確立するための
    first step として機能する (= 経路があることを先に保証し、 実値は段階的に
    差し替える).

    T081 step 1 (本改訂): 個別 default constructor 9 件 (上記関数群) を
    combine する形に refactor。 step 1 caller (run_ga.py) は ABDivergence のみ
    実値、 残り 8 件は default constructor で取得し、 同 build_run_observability_report
    に注入する。 byte-for-byte equality は維持 (= test 16 で固定).

    各 stub 値は status enum / Literal type の **valid な** "insufficient_data" /
    "insufficient_runs" / "insufficient_window" / "empty_archive" / 0 default を
    使用 (= dataclass __post_init__ invariant 全 PASS).

    後続別 TODO 担当範囲 (= T081 6 step segmentation):
        - step 1: ABDivergenceMetric 実値配線 (本 step、 caller 計算)
        - step 2: ArchiveChurnMetric / BypassRatioMetric 実値配線 (AdmissionReport)
        - step 3: SessionEntropyMetric / FeasibleRatioMetric 実値配線
        - step 4: SelectionMetric 実値配線 (GenerationSelectionResult)
        - step 5: InflowConsistencyMetric / FailureMetric 実値配線
        - step 6: QForceRecommendation 実値配線 (recommend_q_force_adjust)

    Args:
        run_id: 1 Run identifier (non-empty str).
        dataset_epoch_id: epoch identifier (non-empty str).
        generation_count: GA 世代数 (>=0).

    Returns:
        :class:`RunObservabilityReport` (全 metric stub 値).
    """
    return build_run_observability_report(
        run_id=run_id,
        dataset_epoch_id=dataset_epoch_id,
        generation_count=generation_count,
        ab_divergence=build_default_ab_divergence_metric(),
        q_force_recommendation=build_default_q_force_recommendation(),
        archive_churn=build_default_archive_churn_metric(),
        bypass_ratio=build_default_bypass_ratio_metric(),
        session_entropy=build_default_session_entropy_metric(),
        feasible_ratio=build_default_feasible_ratio_metric(),
        selection=build_default_selection_metric(),
        inflow_consistency=build_default_inflow_consistency_metric(),
        failure=build_default_failure_metric(run_id),
    )


# ============================================================================
# T080a: JSON serialization for RunObservabilityReport
# ============================================================================


def _convert_for_json_key(key: Any) -> str:
    """JSON object key 用の str 化 (Round 1 [Warning] 1 反映).

    JSON object key は str 必須のため、 Decimal / int / Enum 系は str() 化.
    """
    if isinstance(key, str):
        return key
    if isinstance(key, (int, float, bool, Decimal)):
        return str(key)
    return repr(key)


def _convert_for_json(obj: Any) -> Any:
    """Decimal / Mapping / tuple / frozenset を JSON-friendly に再帰変換.

    asdict() は dataclass を dict に / tuple を list に / Mapping を dict に
    変換するが、 Decimal はそのまま残るため本 helper で str 化.

    Round 1 [Warning] 反映:
        - dict キーも再帰変換 (= Decimal/int/Enum キー対応、 JSON object key
          str 必須制約準拠)
        - frozenset 混在型は str() 比較で sort fallback (= TypeError 回避)
    """
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, dict):
        return {
            _convert_for_json_key(k): _convert_for_json(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_convert_for_json(v) for v in obj]
    if isinstance(obj, tuple):
        return [_convert_for_json(v) for v in obj]
    if isinstance(obj, frozenset):
        converted = [_convert_for_json(v) for v in obj]
        try:
            return sorted(converted)
        except TypeError:
            # 比較不能な混在型 → str 化して sort fallback (Round 1 [Warning] 2)
            return sorted(converted, key=str)
    return obj


def serialize_run_observability_report(
    report: RunObservabilityReport,
) -> str:
    """T080a: ``RunObservabilityReport`` を JSON 文字列に serialize する.

    asdict() で再帰 dict 化 → ``_convert_for_json`` で Decimal を str 化 →
    ``json.dumps`` で encode (ensure_ascii=False / indent=2).

    Args:
        report: 1 Run の集約 :class:`RunObservabilityReport`.

    Returns:
        JSON 文字列 (UTF-8、 indent=2).
    """
    return json.dumps(
        _convert_for_json(asdict(report)),
        ensure_ascii=False,
        indent=2,
    )
