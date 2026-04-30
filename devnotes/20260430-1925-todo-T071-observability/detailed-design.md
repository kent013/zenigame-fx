# 詳細設計: T071 — Observability (A→B 乖離 / archive churn / front1 / FailureSummary 消費)

**作成日時**: 2026-04-30 19:50 JST (Round 2 改訂: 20:08 JST、 Round 3 改訂: 20:25 JST)
**設計者**: Claude
**前提**: 概念設計 `conceptual-design.md` Round 2 APPROVED 済 (`conceptual-review-round-2.md`)
**SSOT 規約 (§ 11.2)**: 本詳細設計 §3 (data model) / §4 (algorithm) は概念設計 §3 / §5 と同期。 不一致時は概念設計を正本として優先。
**main 基準**: `04aa271` (T070 commit 後)
**改訂履歴**: Round 1 [C1-C5] / [W1-W4] / [S1-S4] + Round 2 [C1-C7] / [W1-W5] / [S1-S5] 全反映

## 0. 詳細設計の責務

概念設計で確定した Observability layer の library 基盤を **コード単位** に展開:
- 全 metric dataclass の field + status enum + invariant
- 全関数の擬似コード (Pearson corr / Shannon entropy 等)
- F1-F15 と test_id の 1:1 対応
- T065-T068 hard dependency の field grep DoD
- Phase 1 / Phase 2 切り分け

## 1. ファイル / 関数 / クラス 完全リスト

### 1.1 新規ファイル

| Path | 主シンボル | LOC 概算 |
|---|---|---|
| `src/alpha_factory/observability/__init__.py` | 公開 API export | +30 |
| `src/alpha_factory/observability/run_metrics.py` | **11 dataclass + 9 関数** (Round 1 [C1] 反映で SSOT 統一) | +450 |
| `tests/alpha_factory/observability/test_run_metrics.py` | F1-F15 unit test | +400 |
| `tests/alpha_factory/observability/__init__.py` | 空ファイル (pytest 認識) | +1 |

### 1.2 既存ファイル変更

| Path | 変更内容 | LOC 増減 |
|---|---|---|
| `docs/alpha_factory/stage-gates.md` | T071 セクション追記 (observability 仕様、 status field 規約、 hard dependency) | +50 |

### 1.3 Phase 2 申し送り (T071 PR では touch しない)

- `scripts/alpha_factory/run_ga.py`: build_run_observability_report 呼び出し + log/report 出力 + 連続乖離 Run カウント保持 (state file)
- `src/alpha_factory/stage_a_evaluator.py` (T063): q_force_recommendation の caller 配線
- `docs/alpha_factory/observability.md` 新設: RunObservabilityReport の Markdown 表現 + 監視運用ガイド
- T073 audit layer: DSR/PBO/SPA は別 layer
- run report (Phase 2 配線): RunObservabilityReport を Markdown 化

## 2. Hard dependency (cross-PR)

T071 単独 merge 不可。 以下の T065-T068 PR が **先行 merge** されていることが必須:

| 依存 PR | 必要 シンボル | T071 import 経路 |
|---|---|---|
| T065 | `GenerationSelectionResult` (field: `pareto_front1_size`, `feasible_ratio`, `mean_constraint_violation`, `generation`) | `from src.alpha_factory.ga.nsga2_selection import GenerationSelectionResult` |
| T066 | `AdmissionReport`, `ArchiveState`, `ArchiveMember`, `ArchiveRole` | `from src.alpha_factory.ga.cpps_archive import AdmissionReport, ArchiveState, ArchiveMember, ArchiveRole` |
| T067 | `WarmstartReport`, `WarmstartConfig` | `from src.alpha_factory.ga.loop_closure import WarmstartReport, WarmstartConfig` |
| T068 | `RunFailureSummary`, `FailureSummary`, `StageName` | `from src.alpha_factory.ga.failure_handling import RunFailureSummary, FailureSummary, StageName` |

T071 PR description 必須記載:
- 「T065 merge: <commit hash>」
- 「T066 merge: <commit hash>」
- 「T067 merge: <commit hash>」
- 「T068 merge: <commit hash>」

field grep DoD (PR review check、 Round 2 [C4] / [S2] 反映で §4 実参照 field と完全同期):
```bash
# T065: GenerationSelectionResult (= §4.6 extract_selection_metrics で読む field)
grep -rn "pareto_front1_size\|feasible_ratio\|mean_constraint_violation\|generation" src/alpha_factory/ga/nsga2_selection.py
# T066: AdmissionReport / ArchiveMember / ArchiveRole (= §4.3 / §4.4 / §4.6 で読む field)
grep -rn "n_admitted_ca\|n_admitted_da\|n_evicted_ca\|n_evicted_da\|n_admitted_by_role" src/alpha_factory/ga/cpps_archive.py
grep -rn "session_pass_pattern" src/alpha_factory/ga/cpps_archive.py
grep -rn "MISSION_PASS\|PROGRESS_PASS\|SCORE_BYPASS" src/alpha_factory/ga/cpps_archive.py
# T067: WarmstartReport / WarmstartConfig (= §4.6 extract_inflow_consistency で読む field)
grep -rn "warmstart_share_actual\|relaxation_steps\|per_source_run_violations" src/alpha_factory/ga/loop_closure.py
grep -rn "warmstart_share_target" src/alpha_factory/ga/loop_closure.py
# T068: RunFailureSummary / FailureSummary / StageName (= §4.6 extract_failure_metrics で読む field)
grep -rn "n_failure_records\|n_failed_genomes\|eligible_individuals\|stage" src/alpha_factory/ga/failure_handling.py
grep -rn "fingerprint_dedup_top_n\|run_aborted\|per_stage_summaries\|run_id" src/alpha_factory/ga/failure_handling.py
```
全 field がヒットすることを T071 PR 実装時に確認。 grep 対象 field と §4 実参照 field の同期は Round 2 [C4] 反映の DoD 要件。

## 3. データモデル詳細 (擬似コード)

### 3.1 Imports + Module Header

```python
# src/alpha_factory/observability/run_metrics.py

from __future__ import annotations
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final, Literal

from src.alpha_factory.ga.cpps_archive import (
    AdmissionReport,
    ArchiveMember,
    ArchiveRole,
)
from src.alpha_factory.ga.failure_handling import (
    FailureSummary,
    RunFailureSummary,
    StageName,
)
from src.alpha_factory.ga.loop_closure import (
    WarmstartConfig,
    WarmstartReport,
)
from src.alpha_factory.ga.nsga2_selection import GenerationSelectionResult

# synthesis § 8.7 確定値
DELTA_PER_RUN: Final[Decimal] = Decimal("0.02")
Q_FORCE_MAX: Final[Decimal] = Decimal("0.40")
RESTORE_THRESHOLD: Final[Decimal] = Decimal("0.50")

# T071 仮説値 (Round 1 [C3] 反映、 synthesis 未明示)
Q_FORCE_MIN: Final[Decimal] = Decimal("0.15")
DIVERGENCE_THRESHOLD: Final[Decimal] = Decimal("0.30")

# AB 相関の actionable 最小サンプルサイズ (Round 1 [C3] / [S2] 反映、 C7 規範準拠)
# n<10 で「相関 claim 禁止」 の C7 規範を統合し、 q_force 補正アクションを抑止
AB_MIN_ACTIONABLE_PAIRS: Final[int] = 10

# session_pass_pattern 入力 contract (Round 1 [C4] 反映、 3 bit string 固定)
SESSION_PATTERN_REGEX: Final[str] = r"^[01]{3}$"   # "000", "001", ..., "111"

# session bucket (T070 BLOCK_BUCKET_RANGES_UTC と整合、 3 bit パターン空間)
SESSION_PATTERN_BITS: Final[int] = 3  # Tokyo/London/NY
SESSION_PATTERN_SPACE_SIZE: Final[int] = 2 ** SESSION_PATTERN_BITS  # 8
WEEKLY_WINDOW_SIZE: Final[int] = 7  # weekly = 7 Run

# warmstart consistency tolerance
WARMSTART_SHARE_TOLERANCE: Final[Decimal] = Decimal("0.01")
```

### 3.2 ABDivergenceMetric

```python
ABDivergenceStatus = Literal["ok", "insufficient_data", "zero_variance"]


@dataclass(frozen=True)
class ABDivergenceMetric:
    """A→B 乖離 Pearson correlation (B 評価対象個体集合に conditioning).

    SSOT: 概念設計 §3.2 / 詳細設計 §3.2 (Round 1 [C2] / [C3] / [S2] 反映で invariant 強化).

    属性:
        status: 計算可否 (Round 2 [W2] 反映、 None 経路排除).
        corr: Pearson correlation. status="ok" 以外では sentinel value 0
              (使用禁止、 status を確認すること).
        n_pairs: 計算に使った個体組数 (= B 評価済個体数).

    invariant (Round 1 [C2] / [S1] 反映、 status 別 完全強制):
        status="ok"               → corr ∈ [-1, 1] AND n_pairs >= AB_MIN_ACTIONABLE_PAIRS (= 10)
        status="insufficient_data" → corr == Decimal(0) sentinel AND n_pairs < AB_MIN_ACTIONABLE_PAIRS
        status="zero_variance"    → corr == Decimal(0) sentinel
    """

    status: ABDivergenceStatus
    corr: Decimal
    n_pairs: int

    def __post_init__(self) -> None:
        if self.n_pairs < 0:
            raise ValueError(f"n_pairs must be >= 0, got {self.n_pairs}")

        if self.status == "ok":
            # Round 1 [C2] / [C3] 反映: ok 時の完全 invariant
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
            # Round 1 [C2] 反映: sentinel 強制
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
            # Round 2 [C2] / [S1] 反映: 未知 status / None を runtime で拒否
            raise ValueError(f"unknown status: {self.status!r}")
```

### 3.3 QForceRecommendation

```python
QForceReason = Literal["raise", "hold", "restore", "insufficient_data", "zero_variance"]


@dataclass(frozen=True)
class QForceRecommendation:
    """A→B 乖離に応じた q_force 補正推奨 (synthesis § 8.7 + T071 仮説値).

    SSOT: 概念設計 §3.3.
    """

    new_q_force: Decimal
    delta: Decimal               # +0.02 / 0 / -0.02
    reason: QForceReason
    clamped_at_max: bool
    clamped_at_min: bool
    consecutive_divergent_runs: int   # caller 注入の値を report 用に保持

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
```

### 3.4 ArchiveChurnMetric

```python
ArchiveChurnStatus = Literal["ok", "insufficient_runs"]


@dataclass(frozen=True)
class ArchiveChurnMetric:
    """直近 N Run (max 3) の eviction 率 (synthesis § 10.1).

    SSOT: 概念設計 §3.4.
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
        # Round 1 [C2] 反映: status 別 invariant 完全強制
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
            # Round 2 [C2] / [S1] 反映
            raise ValueError(f"unknown status: {self.status!r}")
```

### 3.5 BypassRatioMetric

```python
@dataclass(frozen=True)
class BypassRatioMetric:
    """archive 流入のうち score_bypass 経由の割合 (synthesis § 10.1)."""

    bypass_ratio: Decimal
    n_admitted_by_role: dict[ArchiveRole, int]  # ArchiveRole -> count
    n_total_admissions: int

    def __post_init__(self) -> None:
        if not (Decimal(0) <= self.bypass_ratio <= Decimal(1)):
            raise ValueError(
                f"bypass_ratio must be in [0, 1], got {self.bypass_ratio}"
            )
```

### 3.6 SessionEntropyMetric

```python
SessionEntropyStatus = Literal["ok", "insufficient_window", "empty_archive"]


@dataclass(frozen=True)
class SessionEntropyMetric:
    """archive 内 session_pass_pattern 分布の Shannon entropy.

    SSOT: 概念設計 §3.6.
    """

    status: SessionEntropyStatus
    shannon_entropy: Decimal
    relative_entropy: Decimal   # = shannon_entropy / log2(8)
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
        if self.n_unique_patterns < 0 or self.n_unique_patterns > SESSION_PATTERN_SPACE_SIZE:
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
        # Round 1 [C2] 反映: status 別 invariant 完全強制
        if self.status == "ok":
            if self.n_runs_aggregated < WEEKLY_WINDOW_SIZE:
                raise ValueError(
                    f"status='ok' requires n_runs_aggregated >= {WEEKLY_WINDOW_SIZE}, "
                    f"got {self.n_runs_aggregated}"
                )
            if self.n_archive_members == 0:
                raise ValueError(
                    f"status='ok' requires n_archive_members > 0, got 0"
                )
        elif self.status == "insufficient_window":
            if self.n_runs_aggregated >= WEEKLY_WINDOW_SIZE:
                raise ValueError(
                    f"status='insufficient_window' requires "
                    f"n_runs_aggregated < {WEEKLY_WINDOW_SIZE}, "
                    f"got {self.n_runs_aggregated}"
                )
            # Round 2 [C3] 反映: sentinel 完全強制
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
            # Round 2 [C2] / [S1] 反映
            raise ValueError(f"unknown status: {self.status!r}")
```

### 3.7 FeasibleRatioMetric

```python
@dataclass(frozen=True)
class FeasibleRatioMetric:
    """Push/Pull FSM 切替指標 (T063 既存値の観測記録)."""

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
        if self.n_feasible_individuals > self.n_total_individuals:
            raise ValueError(
                f"n_feasible ({self.n_feasible_individuals}) > "
                f"n_total ({self.n_total_individuals})"
            )
```

### 3.8 SelectionMetric

```python
@dataclass(frozen=True)
class SelectionMetric:
    """T065 GenerationSelectionResult からの抽出."""

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
```

### 3.9 InflowConsistencyMetric (Round 1 [C4] 命名統一)

```python
@dataclass(frozen=True)
class InflowConsistencyMetric:
    """warmstart + admission の inflow 設定通り動作確認."""

    warmstart_share_target: Decimal
    warmstart_share_actual: Decimal
    share_drift: Decimal             # = actual - target
    within_tolerance: bool           # |share_drift| <= WARMSTART_SHARE_TOLERANCE
    relaxation_steps_count: int
    per_source_run_violations: int   # max_per_source_run cap 越え件数
    ca_inflow_actual: int
    da_inflow_actual: int
    bypass_inflow_actual: int
    inflow_summary_by_role: dict[ArchiveRole, int]
```

### 3.10 FailureMetric / FailureMetricStage

```python
@dataclass(frozen=True)
class FailureMetricStage:
    """per-stage failure metric."""

    stage: StageName
    n_failure_records: int
    n_failed_genomes: int
    eligible_individuals: int
    failure_rate: Decimal           # = n_failed_genomes / max(eligible_individuals, 1)
    fingerprint_top_3: tuple[tuple[str, int], ...]   # (fingerprint, count) top 3

    def __post_init__(self) -> None:
        if not (Decimal(0) <= self.failure_rate <= Decimal(1)):
            raise ValueError(
                f"failure_rate must be in [0, 1], got {self.failure_rate}"
            )


@dataclass(frozen=True)
class FailureMetric:
    """T068 RunFailureSummary からの抽出."""

    run_id: str
    run_aborted: bool
    per_stage: tuple[FailureMetricStage, ...]
```

### 3.11 RunObservabilityReport (集約)

```python
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
        if not self.dataset_epoch_id or not isinstance(self.dataset_epoch_id, str):
            raise ValueError(
                f"dataset_epoch_id must be non-empty str, "
                f"got {self.dataset_epoch_id!r}"
            )
        if self.generation_count < 0:
            raise ValueError(
                f"generation_count must be >= 0, got {self.generation_count}"
            )
```

## 4. アルゴリズム詳細 (擬似コード)

### 4.1 compute_ab_divergence_on_b_evaluated

```python
def compute_ab_divergence_on_b_evaluated(
    a_proxy_scores_b_evaluated: Sequence[Decimal],
    b_pooled_scores: Sequence[Decimal],
) -> ABDivergenceMetric:
    """A→B 乖離 Pearson correlation を計算 (B 評価対象個体集合に conditioning).

    SSOT: 概念設計 §3.2 / §5.1.
    """
    if len(a_proxy_scores_b_evaluated) != len(b_pooled_scores):
        raise ValueError(
            f"length mismatch: a_proxy={len(a_proxy_scores_b_evaluated)} "
            f"vs b_pooled={len(b_pooled_scores)}"
        )
    n = len(a_proxy_scores_b_evaluated)
    # Round 1 [C3] / [S2] 反映: C7 規範準拠で n<10 を非アクション化 (= insufficient_data)
    if n < AB_MIN_ACTIONABLE_PAIRS:
        return ABDivergenceMetric(
            status="insufficient_data", corr=Decimal(0), n_pairs=n,
        )

    a_mean = sum(a_proxy_scores_b_evaluated) / Decimal(n)
    b_mean = sum(b_pooled_scores) / Decimal(n)
    a_dev = [a - a_mean for a in a_proxy_scores_b_evaluated]
    b_dev = [b - b_mean for b in b_pooled_scores]
    cov = sum(ad * bd for ad, bd in zip(a_dev, b_dev)) / Decimal(n)
    var_a = sum(ad * ad for ad in a_dev) / Decimal(n)
    var_b = sum(bd * bd for bd in b_dev) / Decimal(n)

    # Round 2 [W2] 反映: zero_variance 判定 (epsilon 不使用、 厳密 0 判定)
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
```

### 4.2 recommend_q_force_adjust

```python
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

    # status 経路: 計算不能なら hold
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
```

### 4.3 compute_archive_churn

```python
def compute_archive_churn(
    recent_admission_reports: Sequence[AdmissionReport],
) -> ArchiveChurnMetric:
    """直近 N Run (max 3) の eviction 率を計算.

    SSOT: 概念設計 §3.4 / §5.3.
    """
    if len(recent_admission_reports) == 0:
        raise ValueError("recent_admission_reports must be non-empty")
    n_runs_used = min(len(recent_admission_reports), 3)
    reports = recent_admission_reports[-n_runs_used:]  # 直近 N 件

    total_admissions = sum(
        r.n_admitted_ca + r.n_admitted_da for r in reports
    )
    total_evictions = sum(
        r.n_evicted_ca + r.n_evicted_da for r in reports
    )

    churn_rate = (
        Decimal(total_evictions) / Decimal(total_admissions)
        if total_admissions > 0
        else Decimal(0)
    )

    status: ArchiveChurnStatus = "ok" if n_runs_used == 3 else "insufficient_runs"

    return ArchiveChurnMetric(
        status=status,
        churn_rate=churn_rate,
        n_total_admissions=total_admissions,
        n_total_evictions=total_evictions,
        n_runs_used=n_runs_used,
    )
```

### 4.4 compute_bypass_ratio

```python
def compute_bypass_ratio(report: AdmissionReport) -> BypassRatioMetric:
    """1 Run の bypass 比率.

    SSOT: 概念設計 §3.5 / §5.4.
    """
    role_counts = dict(report.n_admitted_by_role)  # shallow copy
    total = sum(role_counts.values())
    bypass_count = role_counts.get(ArchiveRole.SCORE_BYPASS, 0)
    bypass_ratio = (
        Decimal(bypass_count) / Decimal(total) if total > 0 else Decimal(0)
    )
    return BypassRatioMetric(
        bypass_ratio=bypass_ratio,
        n_admitted_by_role=role_counts,
        n_total_admissions=total,
    )
```

### 4.5 compute_session_entropy

```python
def compute_session_entropy(
    archive_members: Sequence[ArchiveMember],
    n_runs_aggregated: int,
    *,
    weekly_window_size: int = WEEKLY_WINDOW_SIZE,
) -> SessionEntropyMetric:
    """archive 内 session_pass_pattern 分布の Shannon entropy.

    SSOT: 概念設計 §3.6 / §5.5.
    """
    if n_runs_aggregated < 0:
        raise ValueError(
            f"n_runs_aggregated must be >= 0, got {n_runs_aggregated}"
        )

    # status 判定 1: weekly window 未到達
    if n_runs_aggregated < weekly_window_size:
        return SessionEntropyMetric(
            status="insufficient_window",
            shannon_entropy=Decimal(0),
            relative_entropy=Decimal(0),
            n_unique_patterns=0,
            n_archive_members=len(archive_members),
            n_runs_aggregated=n_runs_aggregated,
        )

    # status 判定 2: empty archive
    if len(archive_members) == 0:
        return SessionEntropyMetric(
            status="empty_archive",
            shannon_entropy=Decimal(0),
            relative_entropy=Decimal(0),
            n_unique_patterns=0,
            n_archive_members=0,
            n_runs_aggregated=n_runs_aggregated,
        )

    # 出現頻度を集計 (= Shannon entropy 計算)
    # Round 1 [C4] / [S3] 反映: session_pass_pattern は 3 bit string ("000"-"111") 固定
    import re
    pattern_counts: dict[str, int] = {}
    for member in archive_members:
        pattern = member.session_pass_pattern  # T064 / T066 由来
        if not re.match(SESSION_PATTERN_REGEX, pattern):
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

    max_entropy = Decimal(SESSION_PATTERN_BITS)  # log2(8) = 3
    relative = h / max_entropy if max_entropy > 0 else Decimal(0)

    return SessionEntropyMetric(
        status="ok",
        shannon_entropy=h,
        relative_entropy=relative,
        n_unique_patterns=len(pattern_counts),
        n_archive_members=len(archive_members),
        n_runs_aggregated=n_runs_aggregated,
    )
```

### 4.6 extract_selection_metrics / extract_inflow_consistency / extract_failure_metrics

```python
def extract_selection_metrics(
    result: GenerationSelectionResult,
) -> SelectionMetric:
    return SelectionMetric(
        front1_cardinality=result.pareto_front1_size,
        feasible_ratio=result.feasible_ratio,
        mean_constraint_violation=result.mean_constraint_violation,
        generation=result.generation,
    )


def extract_inflow_consistency(
    warmstart_report: WarmstartReport,
    admission_report: AdmissionReport,
    config: WarmstartConfig,
    *,
    tolerance: Decimal = WARMSTART_SHARE_TOLERANCE,
) -> InflowConsistencyMetric:
    target = config.warmstart_share_target
    actual = warmstart_report.warmstart_share_actual
    drift = actual - target

    return InflowConsistencyMetric(
        warmstart_share_target=target,
        warmstart_share_actual=actual,
        share_drift=drift,
        within_tolerance=(abs(drift) <= tolerance),
        relaxation_steps_count=len(warmstart_report.relaxation_steps),
        per_source_run_violations=warmstart_report.per_source_run_violations,
        ca_inflow_actual=admission_report.n_admitted_ca,
        da_inflow_actual=admission_report.n_admitted_da,
        bypass_inflow_actual=admission_report.n_admitted_by_role.get(
            ArchiveRole.SCORE_BYPASS, 0
        ),
        inflow_summary_by_role=dict(admission_report.n_admitted_by_role),
    )


def extract_failure_metrics(summary: RunFailureSummary) -> FailureMetric:
    per_stage = tuple(
        FailureMetricStage(
            stage=s.stage,
            n_failure_records=s.n_failure_records,
            n_failed_genomes=s.n_failed_genomes,
            eligible_individuals=s.eligible_individuals,
            failure_rate=(
                Decimal(s.n_failed_genomes) / Decimal(max(s.eligible_individuals, 1))
            ),
            fingerprint_top_3=s.fingerprint_dedup_top_n[:3],
        )
        for s in summary.per_stage_summaries
    )
    return FailureMetric(
        run_id=summary.run_id,
        run_aborted=summary.run_aborted,
        per_stage=per_stage,
    )
```

### 4.7 build_run_observability_report

```python
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
```

## 5. テスト計画詳細 (F1-F15 1:1 対応)

### 5.1 `tests/alpha_factory/observability/test_run_metrics.py`

```python
class TestComputeABDivergence:
    def test_F1a_n_zero_returns_insufficient_data(self):
        result = compute_ab_divergence_on_b_evaluated([], [])
        assert result.status == "insufficient_data"
        assert result.n_pairs == 0
        assert result.corr == Decimal(0)

    def test_F1b_n_below_min_actionable_returns_insufficient_data(self):
        # Round 1 [C3] 反映: n<10 で insufficient_data
        result = compute_ab_divergence_on_b_evaluated(
            [Decimal(i) for i in range(5)],
            [Decimal(2 * i) for i in range(5)],
        )
        assert result.status == "insufficient_data"
        assert result.n_pairs == 5

    def test_F2a_zero_variance_a(self):
        # n>=10 (= AB_MIN_ACTIONABLE_PAIRS) で var(a)=0 を作る
        result = compute_ab_divergence_on_b_evaluated(
            [Decimal("1.0")] * 10,
            [Decimal(i) for i in range(10)],
        )
        assert result.status == "zero_variance"

    def test_F2b_zero_variance_b(self):
        result = compute_ab_divergence_on_b_evaluated(
            [Decimal(i) for i in range(10)],
            [Decimal("3.0")] * 10,
        )
        assert result.status == "zero_variance"

    def test_F3a_perfect_positive_correlation(self):
        result = compute_ab_divergence_on_b_evaluated(
            [Decimal(i) for i in range(10)],
            [Decimal(2 * i) for i in range(10)],
        )
        assert result.status == "ok"
        assert abs(result.corr - Decimal(1)) < Decimal("0.001")

    def test_F3b_perfect_negative_correlation(self):
        result = compute_ab_divergence_on_b_evaluated(
            [Decimal(i) for i in range(10)],
            [Decimal(-2 * i) for i in range(10)],
        )
        assert abs(result.corr - Decimal(-1)) < Decimal("0.001")

    def test_F12_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="length mismatch"):
            compute_ab_divergence_on_b_evaluated(
                [Decimal(1)], [Decimal(1), Decimal(2)]
            )


class TestRecommendQForceAdjust:
    def _ab_ok(self, corr: Decimal) -> ABDivergenceMetric:
        return ABDivergenceMetric(status="ok", corr=corr, n_pairs=10)

    def test_F4a_raise_when_below_threshold(self):
        # corr < 0.30 で raise
        rec = recommend_q_force_adjust(
            current_q_force=Decimal("0.20"),
            divergence=self._ab_ok(Decimal("0.10")),
            consecutive_divergent_runs=1,
        )
        assert rec.reason == "raise"
        assert rec.delta == DELTA_PER_RUN
        assert rec.new_q_force == Decimal("0.22")

    def test_F4b_restore_when_above_threshold(self):
        # corr >= 0.50 で restore
        rec = recommend_q_force_adjust(
            current_q_force=Decimal("0.30"),
            divergence=self._ab_ok(Decimal("0.60")),
            consecutive_divergent_runs=0,
        )
        assert rec.reason == "restore"
        assert rec.delta == -DELTA_PER_RUN

    def test_F4c_clamped_at_max(self):
        rec = recommend_q_force_adjust(
            current_q_force=Decimal("0.39"),
            divergence=self._ab_ok(Decimal("0.05")),
            consecutive_divergent_runs=10,
        )
        assert rec.reason == "raise"
        assert rec.new_q_force == Q_FORCE_MAX  # 0.40 clamp
        assert rec.clamped_at_max is True

    def test_F4d_clamped_at_min(self):
        rec = recommend_q_force_adjust(
            current_q_force=Decimal("0.16"),
            divergence=self._ab_ok(Decimal("0.80")),
            consecutive_divergent_runs=0,
        )
        assert rec.reason == "restore"
        assert rec.new_q_force == Q_FORCE_MIN
        assert rec.clamped_at_min is True

    def test_F5a_hold_in_hysteresis(self):
        # 0.30 <= corr < 0.50 で hold
        rec = recommend_q_force_adjust(
            current_q_force=Decimal("0.25"),
            divergence=self._ab_ok(Decimal("0.40")),
            consecutive_divergent_runs=0,
        )
        assert rec.reason == "hold"
        assert rec.delta == Decimal(0)

    def test_F5b_no_oscillation_at_boundary(self):
        # corr=0.30: hold (= raise threshold は < で判定、 振動なし)
        rec1 = recommend_q_force_adjust(
            current_q_force=Decimal("0.20"),
            divergence=self._ab_ok(Decimal("0.30")),
            consecutive_divergent_runs=0,
        )
        assert rec1.reason == "hold"
        # corr=0.50: restore (= restore threshold は >= で判定、 hysteresis 端で restore)
        rec2 = recommend_q_force_adjust(
            current_q_force=Decimal("0.20"),
            divergence=self._ab_ok(Decimal("0.50")),
            consecutive_divergent_runs=0,
        )
        assert rec2.reason == "restore"

    def test_F15a_delta_applied_before_clamp(self):
        # F15: delta 適用 → clamp の順序、 clamp 結果が clamped_at_* 経由で観測可能
        rec = recommend_q_force_adjust(
            current_q_force=Decimal("0.40"),
            divergence=self._ab_ok(Decimal("0.05")),
            consecutive_divergent_runs=10,
        )
        # current=0.40 + delta=0.02 → 0.42 → clamp to 0.40
        assert rec.new_q_force == Q_FORCE_MAX
        assert rec.clamped_at_max is True
        assert rec.delta == Decimal(0)  # = new_q_force - current = 0

    def test_F15b_clamp_after_delta_for_max(self):
        # 既に max 付近で raise: clamp 後 delta=0 を観測
        rec = recommend_q_force_adjust(
            current_q_force=Q_FORCE_MAX,
            divergence=self._ab_ok(Decimal("0.05")),
            consecutive_divergent_runs=10,
        )
        assert rec.new_q_force == Q_FORCE_MAX
        assert rec.delta == Decimal(0)

    def test_F15c_clamp_after_delta_for_min(self):
        rec = recommend_q_force_adjust(
            current_q_force=Q_FORCE_MIN,
            divergence=self._ab_ok(Decimal("0.80")),
            consecutive_divergent_runs=0,
        )
        assert rec.new_q_force == Q_FORCE_MIN
        assert rec.delta == Decimal(0)

    def test_F4e_insufficient_data_holds(self):
        rec = recommend_q_force_adjust(
            current_q_force=Decimal("0.20"),
            divergence=ABDivergenceMetric(
                status="insufficient_data", corr=Decimal(0), n_pairs=0,
            ),
            consecutive_divergent_runs=0,
        )
        assert rec.reason == "insufficient_data"
        assert rec.delta == Decimal(0)


class TestComputeArchiveChurn:
    def test_F6a_empty_input_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            compute_archive_churn([])

    def test_F6b_one_run_returns_insufficient(self):
        result = compute_archive_churn([_make_admission(admit=10, evict=2)])
        assert result.status == "insufficient_runs"
        assert result.n_runs_used == 1
        assert result.churn_rate == Decimal("0.2")

    def test_F6c_three_runs_ok(self):
        result = compute_archive_churn([
            _make_admission(admit=10, evict=2) for _ in range(3)
        ])
        assert result.status == "ok"
        assert result.n_runs_used == 3

    def test_F6d_zero_admissions(self):
        # total_admissions=0 → churn_rate=0
        result = compute_archive_churn([_make_admission(admit=0, evict=0)])
        assert result.churn_rate == Decimal(0)


class TestComputeBypassRatio:
    def test_F7a_zero_total_returns_zero(self):
        report = _make_admission(admit=0, evict=0, by_role={})
        result = compute_bypass_ratio(report)
        assert result.bypass_ratio == Decimal(0)

    def test_F7b_normal(self):
        report = _make_admission(
            admit=10, evict=0,
            by_role={
                ArchiveRole.MISSION_PASS: 5,
                ArchiveRole.PROGRESS_PASS: 3,
                ArchiveRole.SCORE_BYPASS: 2,
            },
        )
        result = compute_bypass_ratio(report)
        assert result.bypass_ratio == Decimal("0.2")


class TestComputeSessionEntropy:
    def test_F8a_insufficient_window(self):
        members = [_make_archive_member(pattern="111") for _ in range(10)]
        result = compute_session_entropy(members, n_runs_aggregated=3)
        assert result.status == "insufficient_window"
        assert result.shannon_entropy == Decimal(0)

    def test_F8b_empty_archive(self):
        result = compute_session_entropy([], n_runs_aggregated=7)
        assert result.status == "empty_archive"
        assert result.n_archive_members == 0

    def test_F8c_uniform_distribution(self):
        # 全 8 パターン等頻度 → entropy = log2(8) = 3
        members = []
        for i in range(8):
            pattern = format(i, "03b")
            members.extend(
                [_make_archive_member(pattern=pattern) for _ in range(10)]
            )
        result = compute_session_entropy(members, n_runs_aggregated=7)
        assert result.status == "ok"
        assert abs(result.shannon_entropy - Decimal(3)) < Decimal("0.01")
        assert abs(result.relative_entropy - Decimal(1)) < Decimal("0.01")

    def test_F8d_single_pattern(self):
        # 1 パターンのみ → entropy = 0
        members = [_make_archive_member(pattern="111") for _ in range(10)]
        result = compute_session_entropy(members, n_runs_aggregated=7)
        assert result.status == "ok"
        assert result.shannon_entropy == Decimal(0)

    def test_F8e_invalid_pattern_raises(self):
        # Round 1 [C4] 反映: SESSION_PATTERN_REGEX 違反は ValueError
        members = [_make_archive_member(pattern="1,1,0")]  # 3 bit string でない
        with pytest.raises(ValueError, match="session_pass_pattern"):
            compute_session_entropy(members, n_runs_aggregated=7)


class TestExtractInflowConsistency:
    def test_F9a_within_tolerance(self):
        warmstart = _make_warmstart_report(actual_share=Decimal("0.205"))
        admission = _make_admission(admit=100, evict=10)
        config = _make_warmstart_config(target_share=Decimal("0.200"))
        result = extract_inflow_consistency(warmstart, admission, config)
        assert result.share_drift == Decimal("0.005")
        assert result.within_tolerance is True

    def test_F9b_drift_exceeds_tolerance(self):
        warmstart = _make_warmstart_report(actual_share=Decimal("0.250"))
        admission = _make_admission(admit=100, evict=10)
        config = _make_warmstart_config(target_share=Decimal("0.200"))
        result = extract_inflow_consistency(warmstart, admission, config)
        assert result.within_tolerance is False


class TestStatusInvariantViolations:
    """Round 1 [C2] 反映: status 別 invariant 完全強制 (= F10)."""

    def test_F10a_ab_status_invariant_violation_raises(self):
        # status="ok" with n_pairs<10 で ValueError
        with pytest.raises(ValueError, match="n_pairs >= 10"):
            ABDivergenceMetric(status="ok", corr=Decimal("0.5"), n_pairs=5)

    def test_F10a_ab_status_insufficient_with_nonzero_corr_raises(self):
        # status="insufficient_data" with corr != 0 で ValueError
        with pytest.raises(ValueError, match="sentinel"):
            ABDivergenceMetric(
                status="insufficient_data", corr=Decimal("0.5"), n_pairs=2,
            )

    def test_F10b_archive_churn_status_invariant_violation_raises(self):
        # status="ok" with n_runs_used != 3 で ValueError
        with pytest.raises(ValueError, match="n_runs_used == 3"):
            ArchiveChurnMetric(
                status="ok",
                churn_rate=Decimal("0.1"),
                n_total_admissions=10,
                n_total_evictions=1,
                n_runs_used=2,
            )

    def test_F10c_session_entropy_status_invariant_violation_raises(self):
        # status="ok" with n_runs_aggregated < 7 で ValueError
        with pytest.raises(ValueError, match="n_runs_aggregated >="):
            SessionEntropyMetric(
                status="ok",
                shannon_entropy=Decimal("1.5"),
                relative_entropy=Decimal("0.5"),
                n_unique_patterns=4,
                n_archive_members=10,
                n_runs_aggregated=3,
            )


class TestExtractFunctionsFieldGrep:
    """Round 1 [S4] 反映: F11 cross-PR field rename 検出 unit test.

    各 extract 関数を mock fixture で叩き、 期待 field 名を抽出していることを確認.
    T065-T068 PR で field 名が rename された場合、 mock との不整合で test 失敗.
    """

    def test_F11_extract_selection_uses_pareto_front1_size(self):
        result = _make_generation_selection_result(
            pareto_front1_size=20,
            feasible_ratio=Decimal("0.6"),
            mean_constraint_violation=Decimal("0.0"),
            generation=10,
        )
        m = extract_selection_metrics(result)
        assert m.front1_cardinality == 20

    def test_F11_extract_inflow_uses_admission_role_counts(self):
        warmstart = _make_warmstart_report(actual_share=Decimal("0.20"))
        admission = _make_admission(
            admit=100, evict=10,
            by_role={
                ArchiveRole.MISSION_PASS: 50,
                ArchiveRole.PROGRESS_PASS: 30,
                ArchiveRole.SCORE_BYPASS: 20,
            },
        )
        config = _make_warmstart_config(target_share=Decimal("0.20"))
        m = extract_inflow_consistency(warmstart, admission, config)
        assert m.bypass_inflow_actual == 20

    def test_F11_extract_failure_uses_per_stage_summaries(self):
        summary = _make_run_failure_summary(per_stage=[
            _make_failure_summary(stage="A", n_failed=3, eligible=10),
        ])
        m = extract_failure_metrics(summary)
        assert m.per_stage[0].failure_rate == Decimal("0.3")


class TestRunObservabilityReportInvariants:
    def test_F14_run_observability_report_invariants(self):
        # F14: empty run_id / generation_count<0 で ValueError (Round 2 [C7] 反映)
        with pytest.raises(ValueError, match="run_id"):
            RunObservabilityReport(
                run_id="",
                dataset_epoch_id="ep_001",
                generation_count=10,
                ab_divergence=_default_ab_metric(),
                # ... (他 metric)
            )
        with pytest.raises(ValueError, match="dataset_epoch_id"):
            RunObservabilityReport(
                run_id="run_001",
                dataset_epoch_id="",
                generation_count=10,
                ab_divergence=_default_ab_metric(),
                # ... (他 metric)
            )
```

## 6. F1-F15 失敗モード対応マトリクス (Round 1 [C5] 反映、 厳密 1:1 + Phase 1 / Phase 2 分離)

| failure | 対応 | test_id (Phase 1) | Phase 2 IT / PR check |
|---|---|---|---|
| F1 Pearson corr n<10 で actionable 抑止 (Round 1 [C3]) | n<AB_MIN_ACTIONABLE_PAIRS で status="insufficient_data" | `test_F1a_n_zero_returns_insufficient_data` / `test_F1b_n_below_min_actionable_returns_insufficient_data` | — |
| F2 var=0 で nan | var=0 check で status="zero_variance" | `test_F2a_zero_variance_a` / `test_F2b_zero_variance_b` | — |
| F3 数値誤差で corr が [-1, 1] 越境 | clamp([-1, 1]) を post compute で適用 | `test_F3a_perfect_positive_correlation` / `test_F3b_perfect_negative_correlation` (= 完全相関が clamp 内で安定することを確認、 Round 2 [C6] 反映で F3c 削除) | — |
| F4 q_force max/min 越境 | clamp + clamped_at_max / min field | `test_F4a_raise_when_below_threshold` / `test_F4b_restore_when_above_threshold` / `test_F4c_clamped_at_max` / `test_F4d_clamped_at_min` / `test_F4e_insufficient_data_holds` | — |
| F5 hysteresis 振動 | divergence_threshold (0.30) < restore_threshold (0.50) | `test_F5a_hold_in_hysteresis` / `test_F5b_no_oscillation_at_boundary` | — |
| F6 archive_churn denom 0 / 入力空 / 不足 | zero check で churn_rate=0、 status 別判定 | `test_F6a_empty_input_raises` / `test_F6b_one_run_returns_insufficient` / `test_F6c_three_runs_ok` / `test_F6d_zero_admissions` | — |
| F7 bypass_ratio denom 0 | zero check で bypass_ratio=0 | `test_F7a_zero_total_returns_zero` / `test_F7b_normal` | — |
| F8 session_entropy archive 空 / window 不足 | status="empty_archive" / "insufficient_window" | `test_F8a_insufficient_window` / `test_F8b_empty_archive` / `test_F8c_uniform_distribution` / `test_F8d_single_pattern` / `test_F8e_invalid_pattern_raises` (Round 1 [C4]) | — |
| F9 InflowConsistencyMetric tolerance | tolerance=0.01 SSOT | `test_F9a_within_tolerance` / `test_F9b_drift_exceeds_tolerance` | — |
| F10 status 不整合で caller 誤読 | status 別 invariant を __post_init__ で完全強制 (Round 1 [C2]) | `test_F10a_ab_status_invariant_violation_raises` / `test_F10b_archive_churn_status_invariant_violation_raises` / `test_F10c_session_entropy_status_invariant_violation_raises` | — |
| F11 T065-T068 field rename | §2 hard dependency + grep DoD + extract function 期待値テスト (Round 1 [S4]) | `test_F11_extract_selection_uses_pareto_front1_size` / `test_F11_extract_inflow_uses_admission_role_counts` / `test_F11_extract_failure_uses_per_stage_summaries` (= 各 extract 関数を mock fixture で叩いて期待 field 名を抽出していることを確認、 Round 2 [C6] 反映で test 名 §5 と一致) | `Phase1-PR-CHECK-F11` (PR review で grep DoD 実行) |
| F12 a/b 個体対応ずれ | length 一致 check | `test_F12_length_mismatch_raises` | — |
| F13 divergence_threshold synthesis 未明示 | T071 仮説値として明文化 (Round 1 [C3]) | (concept-level、 unit test なし) | `Phase2-IT-F13` (実測 corr 分布で再校正検討) |
| F14 連続乖離 Run カウント保持責務 | T071 は input、 caller 保持、 docstring で明示 | `test_F14_run_observability_report_invariants` (= RunObservabilityReport の field invariant test、 Round 2 [C7] 反映で命名統一) | `Phase2-IT-F14` (run_ga state file) |
| F15 q_force delta 適用順序 (clamp 順序) | delta 適用 → max/min clamp の順、 clamped_at_* で報告 (F5 とは別概念) | `test_F15a_delta_applied_before_clamp` / `test_F15b_clamp_after_delta_for_max` / `test_F15c_clamp_after_delta_for_min` | — |

## 7. Backward-compat 確認

T071 PR は **新設 layer のみ**、 既存 module への signature 変更なし:
- 新 module 追加で既存 import 経路に影響なし
- T065-T068 PR の dataclass を import 経由で参照、 schema 変更時は cross-PR review (= §2 hard dependency)

## 8. DoD (Definition of Done)

### 8.1 Implementation
- [ ] `src/alpha_factory/observability/__init__.py` 新規 (公開 API export)
- [ ] `src/alpha_factory/observability/run_metrics.py` 新規 (**11 dataclass + 9 関数**、 Round 2 [C1] / [S5] 反映)
- [ ] `docs/alpha_factory/stage-gates.md` T071 セクション追加

### 8.2 Tests
- [ ] `tests/alpha_factory/observability/__init__.py` 空ファイル
- [ ] `tests/alpha_factory/observability/test_run_metrics.py` F1-F15 unit test
- [ ] 全既存 test 通過 (新 module 追加で破壊なし確認)
- [ ] ruff / pyright clean

### 8.3 Cross-PR / PR review checklist
- [ ] T065 / T066 / T067 / T068 PR が先行 merge されていることを確認 (= §2 hard dependency、 PR description に各 merge commit hash 記載)
- [ ] §2 field grep DoD 実行 + 全 field ヒット確認
- [ ] PR description に「Phase 1 範囲 / Phase 2 申し送り」 を明記
- [ ] PR description に T071 仮説値 (divergence_threshold=0.30 / q_force_min=0.15) を明示

## 9. Phase 2 申し送り (Round 1 [W4] 反映で §1.3 と整合)

### 9.1 Phase 2 配線項目

| # | 箇所 | 変更内容 | 担当 |
|---|---|---|---|
| 5 | `scripts/alpha_factory/run_ga.py` | build_run_observability_report 呼び出し + log/report 出力 + 連続乖離 Run state file 保持 | Phase 2 |
| 6 | `src/alpha_factory/stage_a_evaluator.py` (T063) | q_force_recommendation の caller 配線 (StageAControllerState 更新) | T063 詳細設計改訂 / Phase 2 |
| 7 | `docs/alpha_factory/observability.md` (新規) | RunObservabilityReport の Markdown 表現 + 監視運用ガイド | Phase 2 |
| 8 | run report Markdown 化 | RunObservabilityReport を report.md に整形 | Phase 2 |
| 9 | T073 audit layer | DSR/PBO/SPA + T071 metric 一部 (ab_divergence) を audit input | T073 |
| 10 | pop promotion (192→256) trigger | front1<20 連続 2 Run 検出 → run_ga.py で promotion 実行 | Phase 2 |

### 9.2 継続/再校正項目

| # | 箇所 | 変更内容 | 担当 |
|---|---|---|---|
| 11 | divergence_threshold 再校正 | 実測 corr 分布から T071 仮説値を再校正 (Phase2-IT-F13) | Phase 2 (smoke 後) |
| 12 | T065-T068 schema 変更時の T071 調整 | cross-PR review で field rename 検出 + T071 PR で同期更新 | Phase 2 / 継続 |

## 10. 重要な設計判断 SSOT (詳細設計内、 概念設計と同期)

1. **status field 方式で None 経路完全排除**: Round 2 [W2] / [C1] 反映、 全 metric 常時存在
2. **A→B 乖離関数名で conditioning 明示**: `compute_ab_divergence_on_b_evaluated` (Round 1 [C2])
3. **synthesis 確定値 vs T071 仮説値の Final 定数分離**: §3.1 で `DELTA_PER_RUN` / `Q_FORCE_MAX` / `RESTORE_THRESHOLD` (synthesis) と `Q_FORCE_MIN` / `DIVERGENCE_THRESHOLD` (T071 仮説) を別グループ
4. **T065-T068 hard dependency**: §2 で先行 merge 必須化 + field grep DoD
5. **連続乖離 Run カウントは caller 保持、 delta 判定不使用**: report/log 用途のみ、 idempotent recommendation
6. **session entropy weekly 窓は caller 管理**: T071 履歴を持たず、 n_runs_aggregated を caller 注入
7. **inflow_consistency に AdmissionReport も統合**: WarmstartReport + AdmissionReport + config を 1 関数で受け、 ca/da/bypass inflow を網羅

## 11. open issues (詳細実装時に再確認、 Round 2 [C5] / [S4] 反映で session_pass_pattern を hard dependency 昇格)

- T065-T068 dataclass field 名が概念設計と一致するか実装時に確認 (= §2 hard dependency grep)
- math.sqrt / math.log2 を Decimal で扱う際の精度 (= float 経由で十分か、 mpmath 等の検討、 Phase 2 で再校正余地)

### 11.1 Hard dependency 昇格 (Round 2 [C5] / [S4] 反映)

`ArchiveMember.session_pass_pattern` field の値表現 (= 3 bit string `"^[01]{3}$"`) は、
T064 / T066 PR で確定する必要があり、 **T071 PR の hard dependency** として §2 grep DoD に
含める:
```bash
grep -rn "session_pass_pattern" src/alpha_factory/ga/cpps_archive.py
grep -rn "session_pass_pattern" src/alpha_factory/stage_bc_evaluator.py
```
T064 / T066 で異なる表現 (= "1,1,0" 形式 / 8 値整数) が採用されている場合、 T071 PR は
**修正なしでは merge しない** (= T064 / T066 PR で 3 bit string への揃えが必要、 T071 PR と
同期 merge)。

T071 が SESSION_PATTERN_REGEX で contract 違反値を ValueError raise することは contract 強制
として正しい (= 異常値を黙って通さない)。 ただし「caller (T064/T066) が 3 bit string で値を
作る」 という上流 contract が必要、 これを T064 / T066 詳細設計改訂申し送りに加える。
