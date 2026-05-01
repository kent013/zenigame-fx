# 詳細設計: T064 — Stage B + C-lite + C evaluator

## 使命・制約 (絶対遵守)

zenigame-fx Alpha Factory 使命: live_criteria 全指標同時充足 + (ii-lite) 通過。 絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。 禁止事項 1-7 (synthesis § 1.3) + 8 (archive スキーマ伝搬漏れ、 T058 対応済)。 コーディングルール: バグ修正テストファースト / 全施策テスト必須・振る舞いベース命名 / uv 必須 / ruff & mypy 通過 / Python 3.13。

## 概念設計リファレンス

`devnotes/20260430-0230-todo-T064-stage-bc-evaluator/conceptual-design.md` (Round 3 で APPROVED)

## Round 3 review 反映 (Codex 概念レビュー)

| 概念 Round 3 [Suggestion] | 詳細設計での吸収 |
|---|---|
| [S1] cross_pair_pass を Stage C では PASS/FAIL 二値前提を assert で固定 | `evaluate_stage_c` 内で `if cross_pair_pass not in (PASS, FAIL): raise StageBCInputError(...)` で実装 (詳細 Round 1 [C4] で assert→raise 置換) |
| [S2] mission_pass=FAIL 理由を mission_fail_reason で保持 | `StageCResult.mission_fail_reason: MissionFailReason \| None` (Enum: LIVE_CRITERIA / CROSS_PAIR / STRESS / NONE) を新設、 T071 observability 用 |
| [S3] pooled DD = per-fold DD max の test 名 | `test_build_pooled_oos_input_pooled_dd_equals_max_of_per_fold_dd` を確定 |

## 詳細 Round 1 review 反映 (Codex 詳細レビュー)

| 詳細 Round 1 [Critical] | 修正対応 |
|---|---|
| [C1] Stage B fold 境界仕様自己矛盾 (StageBFoldResult に test なし、 pooled_dd_per_fold_max が dataclass 定義に存在しない) | StageBFoldResult に `fold_period_start: datetime` / `fold_period_end: datetime` 追加 (or fold reference 経由)、 StageBResult / PoolFoldedInput に `pooled_dd_per_fold_max: float` 明示追加。 fold 境界 invariant 検証は `individual_input.folds[i].test` 由来で実施 |
| [C2] synthesis § 5.2 DD 集約準拠崩れ (concat DD で判定) | `is_b_pass` 判定で `pooled_dd_per_fold_max` を優先するロジックに固定。 b_pooled_cf_result.max_dd は記録用、 stage B pass 判定の DD 軸は per-fold max 採用 |
| [C3] cross-pair provenance guard 不十分 (bundle.pair のみ検証) | PairBacktestBundle.validate_against(anchor_bundle: PairBacktestBundle) method 追加 (Round 1 [Suggestion] 2)、 `genome_id` / `config_hash` / `partition_label` 一致検証必須、 不一致で StageBCInputError raise |
| [C4] assert 依存契約は -O で無効化 | `assert cross_pair_pass in (PASS, FAIL)` を `if cross_pair_pass not in (PASS, FAIL): raise StageBCInputError(...)` に置換 |
| [C5] compute_a_b_correlation 定数系列で StatisticsError | try/except で StatisticsError を catch、 `(0.0, sample_size)` 固定 contract に。 Pearson 計算不能時 (定数系列、 NaN、 Inf) も同様に `(0.0, n)` で deterministic 戻り値 |

## 詳細 Round 2 review 反映 (Codex 詳細レビュー Round 2)

| 詳細 Round 2 [Critical/Warning] | 修正対応 |
|---|---|
| [C] Stage B で concat DD が gate_pass 経由で再流入 | `compute_gate_pass_excluding_dd(cf_result, thresholds)` 新設、 max_dd 軸を除いた 4 指標 (sharpe/pnl/tc/wr) の worst gap で gate_pass を判定。 `is_b_pass = gate_pass_ex_dd AND dd_pass` で per-fold DD max を採用、 concat DD 経路完全遮断 |
| [W1] 閾値 INCONCLUSIVE と「厳密準拠」 文言の混在 | docstring で「synthesis § 5.2 数式厳密準拠 + § 5.3/§ 5.4 閾値は smoke 後再校正候補 (INCONCLUSIVE タグ)」 と明確分離 |
| [W2] truth table 優先順位衝突全列挙 | テスト計画に追加: `test_stage_c_live_fail_and_cross_pair_fail_yields_reason_live_criteria` (live=False が cross_pair=FAIL より優先)、 `test_stage_c_cross_pair_fail_and_stress_fail_yields_reason_cross_pair` (cross_pair > stress) |
| [W3] anchor_bundle 自体の妥当性チェック未記載 | evaluate_stage_c で `if individual_input.anchor_bundle.pair != STAGE_C_ANCHOR_PAIR: raise StageBCInputError(...)` を追加、 anchor pair 整合性確保 |

## Follow-up review 反映 (T066 c_pass_depth field 追加、 Phase 0 dependency 解消)

T066 概念 Round 4 [R4] / [R9] および詳細 Round 1 [C3] / Round 2 で確定した「BCEvaluationResult への `c_pass_depth: float` field 追加」 を本 follow-up で T064 詳細設計に反映する。 計算式は T066 設計時に確定済 (CA eviction lex key #4 で必要)。 本 follow-up は Phase 0 として T066/T067/T068 Phase 2 配線実装より先に着地必須 (T064 PR は設計改訂のみ、 実装は Phase 2 で T064 evaluate_bc_for_a_pass を src/ に配線する際に実装)。

| Follow-up review [反映元] | 修正対応 |
|---|---|
| [T066 概念 R4] BCEvaluationResult.c_pass_depth field 追加 | BCEvaluationResult dataclass に `c_pass_depth: float` 追加 (値域 [0.0, 1.75])、 計算式: `c_pass_depth = c_lite_n_pass_windows × 0.25 + (1.0 if c_result.mission_pass==PASS else 0.5 if PENDING else 0.0)` |
| [T066 概念 R4] c_lite_n_pass_windows の SSOT | StageCLiteResult dataclass に `n_pass_windows: int` 追加 (値域 [0, 3])、 evaluate_stage_c_lite 内で `sum(1 for w in per_window_results if w.cf_result.gate_pass)` で deterministic 計算 |
| [T066 概念 R9] Phase 0 として先着地 | 本 follow-up は T064 設計改訂 PR のみ (実装なし)、 T066/T067/T068 Phase 2 配線時に T064 evaluate_bc_for_a_pass の実装が `c_pass_depth` を BCEvaluationResult に注入する責務 |
| [T066 詳細 C3] T064 follow-up 不成立を T066 単体で早期検知 | T066 contract test (`test_bc_evaluation_result_has_c_pass_depth_field`) は T064 PR/Phase 2 に同期済の前提を明文化 |
| [T066 詳細 R2 W1] hasattr 偽陰性回避 | contract test の判定ロジックは `__dataclass_fields__` または `typing.get_type_hints` ベースで実装する旨を Phase 2 申し送りに明記 |

### Follow-up Round 1 review 反映 (Codex 詳細レビュー、 follow-up セッション)

| Follow-up Round 1 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [Critical] テスト計画「4 status × 4 n = 12」 算術不整合 (StagePassStatus は PASS/PENDING/FAIL の 3 値) | テスト計画を **「3 StagePassStatus × 4 n_pass_windows = 12 組合せ」** で再明記 (`test_compute_c_pass_depth_value_range_inclusive_zero_and_one_point_seven_five`)、 status 母集合を designed 表現で明示固定 |
| [Warning 1] `compute_c_pass_depth` の `else: 0.0` で未知 enum 値が silent FAIL 等価扱い、 契約逸脱検知が弱い | StagePassStatus の 3 値を全て明示分岐 (PASS=1.0 / PENDING=0.5 / FAIL=0.0)、 未知値は `ValueError` raise (将来 enum 拡張時 fail-fast)、 contract test `test_compute_c_pass_depth_rejects_unknown_status` 追加 |
| [Warning 2] `n_pass_windows ∈ [0, 3]` の dataclass 生成時 invariant 検証なし | `StageCLiteResult.__post_init__` で `0 <= n_pass_windows <= STAGE_C_LITE_NUM_WINDOWS` + `n_pass_windows <= len(per_window_results)` の二重検証、 contract test `test_stage_c_lite_result_rejects_n_pass_windows_out_of_range` 追加。 加えて `compute_c_pass_depth` 入口でも guard (mock dataclass bypass test 用) |
| [Suggestion 2] T072 collider bias 規範との独立性を一文で明示 | `compute_c_pass_depth` docstring + Follow-up section に「c_lite_result.n_pass_windows と c_result.mission_pass のみに依存、 holiday_markets / dst_transition_markets / observability_flags 系には触れない、 stratified audit は本 module で扱わない」 を明記 |

**Collider bias 独立性 (T072 規範継承、 Round 1 [S2] 反映)**: `c_pass_depth` および `n_pass_windows` の計算経路は **`StageCLiteResult.per_window_results.cf_result.gate_pass` と `StageCResult.mission_pass` の 2 input のみ**に依存する。 holiday_markets / dst_transition_markets / observability_flags / schedule_status 系の boundary observability 情報は `compute_c_pass_depth` および `evaluate_stage_c_lite.n_pass_windows` 計算で参照しない (= T072 で確立した「stratified audit は T071 RunObservabilityReport 経由」 規範を継承)。 Phase 2 配線時 (T065/T066) も同規範を維持し、 `c_pass_depth` を condition variable として使った直接 stratification は禁止 (= caller の上流で T071 経由 audit する)。

**Phase 0 着地基準**: 本 follow-up は detailed-design.md / conceptual-design.md の改訂 + Codex 詳細レビュー APPROVED まで。 src/ 実装は Phase 2 (T064 配線) で実施。 T066 Phase 2 配線着手時には T064 詳細設計の `c_pass_depth` field 定義が固定済であることが必須前提 (= T066 CA eviction lex key の意味論が SSOT 確定)。

## 施策一覧 (Phase 1: T064 PR、 Phase 2 は別 PR)

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | `stage_bc_evaluator.py` 新規 (Enum 3 + 11 dataclass + 8 helper + 4 top-level + Constants + 例外) | `src/alpha_factory/stage_bc_evaluator.py` (新規) | Critical |
| 2 | `tests/alpha_factory/test_stage_bc_evaluator.py` 新規 (3 stage 各々 + truth table + pooled OOS + cross-pair + sample-size flag + 4 代表ケース + 境界値) | (新規) | Critical |

**Phase 1 (T064 PR) スコープ = 上記 2 施策**。 既存 `stage_gate.py` への置換は **Phase 2 (T065 統合と同時)** で実施。 T064 PR 単独 merge で runtime に影響なし。

---

## 施策 1: `stage_bc_evaluator.py` 新規作成

### 変更箇所

- ファイル: `src/alpha_factory/stage_bc_evaluator.py` (新規)

### 波及変更

- `AGENTS.md`: なし
- `config/alpha_factory/default.yaml`: なし (Phase 2 で旧 stage_b/c 全廃 + 新 cross-pair list 反映)
- `docs/alpha_factory/*.md`: なし (Phase 2 で stage-gates.md 更新)

### 主要コード (フルコードは長いため、 重要部分のみ抜粋。 残りは概念設計に従う)

```python
"""T064: Stage B + C-lite + C evaluator — synthesis § 5.2 / § 5.3 / § 5.4 / § 6.7 / § 8.3 確定式の実装.

Phase 1 (本 TODO): 単体実装 + テストのみ。
Phase 2 (別 PR): T065 統合と同時、 11 箇所同時更新 + spread_cost field 追加 (T070)。
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from src.alpha_factory.canonical_metrics import (
    BarEquityPoint,
    BarEquitySeries,
    CanonicalFiveResult,
    CanonicalFiveThresholds,
    SessionBucket,
    TradeRecord,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StagePassStatus(StrEnum):
    """Round 1 [C1] 反映: tri-state pass status."""
    PASS = "pass"
    FAIL = "fail"
    PENDING = "pending"


class SampleSizeFlag(StrEnum):
    """Round 1 [W5] 反映: sample size diagnostic flag."""
    OK = "ok"                    # n >= 30
    BOUNDARY = "boundary"        # 25 <= n < 30
    INSUFFICIENT = "insufficient"  # n < 25


class MissionFailReason(StrEnum):
    """Round 3 [S2] 反映: mission_pass=FAIL 理由."""
    LIVE_CRITERIA = "live_criteria"
    CROSS_PAIR = "cross_pair"
    STRESS = "stress"


# ---------------------------------------------------------------------------
# Constants (synthesis § 5.2 / § 5.3 / § 5.4 厳密準拠)
# ---------------------------------------------------------------------------

STAGE_B_NUM_FOLDS: Final[int] = 5

STAGE_C_LITE_NUM_WINDOWS: Final[int] = 3
STAGE_C_LITE_FORCED_PASS_RATIO: Final[float] = 0.30
STAGE_C_LITE_PROGRESS_PASS_MIN_WINDOWS: Final[int] = 2
STAGE_C_LITE_SAMPLE_SIZE_OK_MIN_BLOCKS: Final[int] = 30
STAGE_C_LITE_SAMPLE_SIZE_BOUNDARY_MIN_BLOCKS: Final[int] = 25

STAGE_C_SPREAD_STRESS_MULTIPLIER: Final[float] = 1.5

STAGE_C_ANCHOR_PAIR: Final[str] = "EUR_JPY"
STAGE_C_SHADOW_PAIR_LIST: Final[tuple[str, ...]] = (
    "USD_JPY", "EUR_USD", "AUD_JPY", "USD_CAD", "USD_ZAR"
)
STAGE_C_SHADOW_REQUIRED_COUNT: Final[int] = 5  # 5/5 全通過 (synthesis § 5.4)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class StageBCEvaluatorError(Exception):
    """Stage B/C evaluator 基底例外."""


class StageBCInputError(StageBCEvaluatorError):
    """入力契約違反 (PairBacktestBundle provenance / fold 構成 / etc.)."""


# ---------------------------------------------------------------------------
# DataClasses (frozen、 immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PairBacktestBundle:
    """Round 1 [W4] / [S4] / 詳細 Round 1 [C3] 反映: cross-pair backtest 結果の provenance guard."""
    pair: str
    genome_id: str
    config_hash: str
    partition_label: str  # T060 Period.label or epoch_id
    trades: tuple[TradeRecord, ...]
    bars: BarEquitySeries
    business_day_universe: dict[SessionBucket, frozenset[int]]

    def validate_against(self, anchor_bundle: "PairBacktestBundle") -> None:
        """詳細 Round 1 [C3] 反映: 詳細 Round 1 [Suggestion] 2 反映で method 化.

        anchor_bundle と genome_id / config_hash / partition_label 一致を検証.
        pair 自体は別 (anchor != self.pair が前提)、 pair field は別経路で照合.

        Raises:
            StageBCInputError: いずれか不一致
        """
        if self.genome_id != anchor_bundle.genome_id:
            raise StageBCInputError(
                f"PairBacktestBundle({self.pair}).genome_id ({self.genome_id}) != "
                f"anchor.genome_id ({anchor_bundle.genome_id})"
            )
        if self.config_hash != anchor_bundle.config_hash:
            raise StageBCInputError(
                f"PairBacktestBundle({self.pair}).config_hash mismatch with anchor"
            )
        if self.partition_label != anchor_bundle.partition_label:
            raise StageBCInputError(
                f"PairBacktestBundle({self.pair}).partition_label "
                f"({self.partition_label}) != anchor.partition_label "
                f"({anchor_bundle.partition_label})"
            )


@dataclass(frozen=True)
class StageBFoldResult:
    """1 fold の評価結果 + fold period (詳細 Round 1 [C1] 反映で fold_period 追加)."""
    fold_index: int
    fold_period_start: datetime  # fold.test.start
    fold_period_end: datetime    # fold.test.end
    cf_result: CanonicalFiveResult
    is_feasible_invariant: bool

    @property
    def fold_max_dd(self) -> float:
        """この fold の max_dd (per-fold DD = pooled_DD source、 詳細 Round 1 [C2])."""
        return self.cf_result.max_dd


@dataclass(frozen=True)
class StageBResult:
    """Stage B 評価結果.

    Pareto 軸 source 契約 (Round 1 [C2] 反映):
    is_feasible_invariant=False の場合、 b_pooled_cf_result=None を設定。
    GA 主選抜 (T065 Pareto 3 軸) は b_pooled_cf_result is not None の個体のみ消費する責務。

    DD 集約 (詳細 Round 1 [C1] / [C2] 反映、 synthesis § 5.2 厳密準拠):
    - b_pooled_cf_result.max_dd は concat bars で T061 が計算 (記録用)
    - **pooled_dd_per_fold_max** は per-fold max_dd の max (synthesis § 5.2 準拠、 stage B pass 判定で採用)
    - is_b_pass は b_pooled_cf_result.gate_pass + pooled_dd_per_fold_max を組合せた判定
      (concat DD で擬似 DD を含む b_pooled_cf_result.max_dd は使わない)
    """
    b_pooled_cf_result: CanonicalFiveResult | None     # None = invariant_fail
    pooled_dd_per_fold_max: float | None               # 詳細 Round 1 [C1] / [C2]: per-fold DD max
    per_fold_results: tuple[StageBFoldResult, ...]
    is_feasible_invariant: bool                         # 全 fold OK で True
    is_b_pass: bool                                     # 詳細 Round 1 [C2]: gate_pass AND pooled_dd_per_fold_max <= max_dd_max


@dataclass(frozen=True)
class StageCLiteWindowResult:
    window_index: int
    cf_result: CanonicalFiveResult


@dataclass(frozen=True)
class StageCLiteResult:
    per_window_results: tuple[StageCLiteWindowResult, ...]
    cells_worst: float                                # 15 セル worst (= max over 3 windows of gate_worst_gap)
    mission_pass: StagePassStatus                     # 全 3 windows AND
    progress_pass: StagePassStatus                    # 2/3 windows pass
    sample_size_flag: SampleSizeFlag                  # Round 1 [W5]
    n_pass_windows: int                               # Follow-up: per_window_results のうち cf_result.gate_pass が True の数 (値域 [0, STAGE_C_LITE_NUM_WINDOWS=3])。 c_pass_depth 計算 SSOT (T066 CA eviction lex key #4 で消費)

    def __post_init__(self) -> None:
        """Follow-up Round 1 [W2] 反映: n_pass_windows 値域 invariant 検証.

        生成時に [0, STAGE_C_LITE_NUM_WINDOWS=3] 外なら ValueError raise.
        len(per_window_results) との整合性 (= n_pass_windows <= len) も検証 (caller bug 早期検知).
        """
        if not 0 <= self.n_pass_windows <= STAGE_C_LITE_NUM_WINDOWS:
            raise ValueError(
                f"n_pass_windows must be in [0, {STAGE_C_LITE_NUM_WINDOWS}], "
                f"got {self.n_pass_windows}"
            )
        if self.n_pass_windows > len(self.per_window_results):
            raise ValueError(
                f"n_pass_windows ({self.n_pass_windows}) cannot exceed "
                f"len(per_window_results)={len(self.per_window_results)}"
            )


@dataclass(frozen=True)
class StageCResult:
    c_cf_result: CanonicalFiveResult                  # 12w main
    stress_cf_result: CanonicalFiveResult | None      # spread stress (1.5x)、 PENDING で None
    per_pair_results: dict[str, CanonicalFiveResult]  # shadow 5 pair
    live_criteria_pass: bool
    stress_pass: StagePassStatus
    cross_pair_pass: StagePassStatus                  # PASS/FAIL 二値 (PENDING なし、 Round 3 [S1] assert)
    mission_pass: StagePassStatus
    mission_fail_reason: MissionFailReason | None     # Round 3 [S2]、 PASS/PENDING で None
    shadow_robustness_score: float | None             # Round 1 [W3]


@dataclass(frozen=True)
class PoolFoldedInput:
    """Round 1 [C3] / 詳細 Round 1 [C1] 反映: build_pooled_oos_input 出力."""
    pooled_trades: tuple[TradeRecord, ...]
    pooled_bars: BarEquitySeries
    pooled_business_day_universe: dict[SessionBucket, frozenset[int]]
    fold_boundaries: tuple[int, ...]                  # 各 fold trades 終端の index (診断用)
    pooled_dd_per_fold_max: float                     # 詳細 Round 1 [C1]: 明示 field 追加


@dataclass(frozen=True)
class BCEvaluationInput:
    """1 個体の評価入力 (詳細 Round 1 [C3] で anchor_bundle 追加).

    anchor_bundle は anchor pair (EUR_JPY) の PairBacktestBundle。
    shadow_pairs の各 bundle が genome_id / config_hash / partition_label で
    anchor と一致することを validate_against で検証する責務.
    """
    individual_index: int
    trades: tuple[TradeRecord, ...]                   # anchor pair の trades (Stage B/C-lite/C 評価で使用)
    bars: BarEquitySeries
    business_day_universe: dict[SessionBucket, frozenset[int]]
    folds: tuple["Fold", ...]                         # T060 Fold (forward ref)
    stage_c_lite_periods: tuple["Period", "Period", "Period"]  # T060 c_lite_1/2/3
    stage_c_period: "Period"                          # T060 stage_c (12w)
    anchor_bundle: PairBacktestBundle                 # 詳細 Round 1 [C3]: provenance guard 用
    shadow_pairs: dict[str, PairBacktestBundle]       # 5 pair (anchor 除く)


@dataclass(frozen=True)
class BCEvaluationResult:
    individual_index: int
    b_result: StageBResult
    c_lite_result: StageCLiteResult
    c_result: StageCResult
    mission_pass: StagePassStatus
    b_pooled_cf: CanonicalFiveResult | None           # GA Pareto 軸 source、 None で除外
    pareto_axis_usable: bool                          # b_pooled_cf is not None で True
    c_pass_depth: float                               # Follow-up (T066 Phase 0): 値域 [0.0, 1.75]、 計算式: c_lite_result.n_pass_windows × 0.25 + (1.0 if c_result.mission_pass==PASS else 0.5 if c_result.mission_pass==PENDING else 0.0)。 T066 CA eviction lex key #4 で消費 (大が上位)


# ---------------------------------------------------------------------------
# Helpers (pure functions)
# ---------------------------------------------------------------------------


def evaluate_stage_b(
    individual_input: BCEvaluationInput,
    *,
    evaluate_fn: Callable[..., CanonicalFiveResult],
    live_criteria: dict,
) -> StageBResult:
    """5 fold rolling-origin pooled OOS canonical 5 worst aggregation.

    手順 (synthesis § 5.2):
    1. 各 fold で trades / bars をフィルタ + evaluate_fn 呼出 → StageBFoldResult
    2. 1 fold でも is_feasible=False → is_feasible_invariant=False
    3. is_feasible_invariant=False → b_pooled_cf_result=None で early return (Round 1 [C2])
    4. is_feasible_invariant=True → build_pooled_oos_input → 1 回 evaluate_fn 呼出
    """
    thresholds = derive_stage_b_thresholds(live_criteria)
    per_fold_results = []
    for fold in individual_input.folds:
        fold_trades, fold_bars, fold_universe = filter_to_period(
            individual_input.trades,
            individual_input.bars,
            individual_input.business_day_universe,
            fold.test,
        )
        cf_result = evaluate_fn(
            fold_trades, fold_bars, thresholds, fold_universe,
        )
        per_fold_results.append(StageBFoldResult(
            fold_index=fold.fold_index,
            fold_period_start=fold.test.start,  # 詳細 Round 1 [C1]
            fold_period_end=fold.test.end,
            cf_result=cf_result,
            is_feasible_invariant=cf_result.invariants.is_feasible,
        ))

    is_feasible_invariant = all(f.is_feasible_invariant for f in per_fold_results)
    if not is_feasible_invariant:
        return StageBResult(
            b_pooled_cf_result=None,
            pooled_dd_per_fold_max=None,  # invariant_fail 時は None
            per_fold_results=tuple(per_fold_results),
            is_feasible_invariant=False,
            is_b_pass=False,
        )

    pooled = build_pooled_oos_input(per_fold_results, individual_input)
    b_pooled_cf = evaluate_fn(
        pooled.pooled_trades,
        pooled.pooled_bars,
        thresholds,
        pooled.pooled_business_day_universe,
    )
    # 詳細 Round 1 [C1] / [C2] / Round 2 [Critical] 反映:
    # concat DD 再流入を防ぐため gate_pass_ex_dd を明示計算
    # b_pooled_cf.gate_pass は max_dd 含む総合判定なので、 DD 軸のみ per-fold max で再評価
    pooled_dd_per_fold_max = pooled.pooled_dd_per_fold_max
    max_dd_max_threshold = thresholds.max_dd_max
    dd_pass = pooled_dd_per_fold_max <= max_dd_max_threshold
    # gate_pass_ex_dd: max_dd を除いた 4 軸 (sharpe / pnl / tc / wr) の worst gap で gate_pass 判定
    # = max(0, -slack_sharpe, -slack_pnl, -slack_tc, -slack_wr) <= GATE_PASS_TOLERANCE
    # AND invariants.is_feasible
    gate_pass_ex_dd = compute_gate_pass_excluding_dd(b_pooled_cf, thresholds)
    is_b_pass = gate_pass_ex_dd and dd_pass
    return StageBResult(
        b_pooled_cf_result=b_pooled_cf,
        pooled_dd_per_fold_max=pooled_dd_per_fold_max,
        per_fold_results=tuple(per_fold_results),
        is_feasible_invariant=True,
        is_b_pass=is_b_pass,
    )


def build_pooled_oos_input(
    fold_results: list[StageBFoldResult],
    individual_input: BCEvaluationInput,
) -> PoolFoldedInput:
    """fold 境界 aware の pooled input builder (Round 1 [C3] / Round 2 [W1] 反映).

    手順 (詳細 Round 2 [W1] 反映、 数式レベル明記):
    1. fold.test 非重複・時系列順 assert (StageBCInputError raise)
    2. trades: 各 fold.test の trades を時系列順 concat (重複なし)
    3. bars: 各 fold.test の bars を時系列順 concat、 **fold 境界で running_max を reset**
        (擬似 DD 防止、 各 fold 内でのみ DD を計算する経路)
        実装: pooled_bars は通常 concat、 ただし fold_boundaries metadata で fold 境界 index を保持。
        実際の DD 計算は T061 max_dd 内で fold_boundaries を参照しない (T061 改修なし)。
        擬似 DD 防止は **per-fold cf_result.max_dd の集約** で代替する.
    4. **重要 (Round 2 [W1] 反映、 詳細 [S3]): pooled_DD = max over folds of fold.max_dd**
        この pooled_DD は build_pooled_oos_input 内で metadata として計算するが、
        b_pooled_cf_result.max_dd は通常 concat の bars で T061 が計算する。 後者は擬似 DD を含む。
        詳細設計の決定: **pooled_DD は build_pooled_oos_input が独立計算**、
        StageBResult に `pooled_dd_per_fold_max: float` を追加 (T065 archive metadata 用)。
    5. business_day_universe: 各 fold の universe を union 集合に
    6. fold_boundaries: tuple[int, ...] (trades index 境界)

    Round 2 [W1] 詳細仕様の再確定:
    実装上は (a) 通常 concat で T061 を呼ぶ、 (b) per-fold cf_result.max_dd の max を別途集計、
    の併用。 b_pooled_cf_result.max_dd は (a)、 pooled_dd_per_fold_max は (b)。
    archive admission は (b) を消費 (DD 過小評価 防止)。

    invariant 検証 (raise StageBCInputError、 詳細 Round 1 [C1] で StageBFoldResult.fold_period_* 経由):
    - len(fold_results) == STAGE_B_NUM_FOLDS (=5)
    - fold_results[i].fold_index == i
    - fold_results[i].fold_period_start <= fold_results[i+1].fold_period_start (時系列順)
    - fold_results[i].fold_period_end <= fold_results[i+1].fold_period_start (非重複)

    pooled_dd_per_fold_max の計算 (詳細 Round 1 [C1] / [C2]):
        pooled_dd_per_fold_max = max(f.fold_max_dd for f in fold_results)
    """


def evaluate_stage_c_lite(
    individual_input: BCEvaluationInput,
    *,
    evaluate_fn: Callable[..., CanonicalFiveResult],
    live_criteria: dict,
) -> StageCLiteResult:
    """3 disjoint windows × canonical 5 worst → 15 セル worst.

    Round 1 [W2] 反映: 15 セル worst = max over 3 windows of gate_worst_gap (T061 contract で
    gate_worst_gap = window 内 5 指標 max で確定済).

    Round 1 [W5] 反映: sample_size_flag を計算
        n_blocks = 各 bucket の block 数 (≈ 30 for 6w window)
        n >= 30: OK
        25 <= n < 30: BOUNDARY
        n < 25: INSUFFICIENT

    Round 2 [W4] 反映: INSUFFICIENT 時は mission_pass / progress_pass を PENDING 強制
    """
    thresholds = derive_stage_c_lite_thresholds(live_criteria)
    per_window_results = []
    min_blocks_per_bucket: int = float("inf")
    for i, window in enumerate(individual_input.stage_c_lite_periods):
        window_trades, window_bars, window_universe = filter_to_period(
            individual_input.trades, individual_input.bars,
            individual_input.business_day_universe, window,
        )
        cf_result = evaluate_fn(window_trades, window_bars, thresholds, window_universe)
        per_window_results.append(StageCLiteWindowResult(
            window_index=i, cf_result=cf_result,
        ))
        # sample size guard
        for bucket, blocks in window_universe.items():
            min_blocks_per_bucket = min(min_blocks_per_bucket, len(blocks))

    # 15 cells worst = max over 3 windows of gate_worst_gap
    cells_worst = max(w.cf_result.gate_worst_gap for w in per_window_results)

    # sample_size_flag
    if min_blocks_per_bucket >= STAGE_C_LITE_SAMPLE_SIZE_OK_MIN_BLOCKS:
        flag = SampleSizeFlag.OK
    elif min_blocks_per_bucket >= STAGE_C_LITE_SAMPLE_SIZE_BOUNDARY_MIN_BLOCKS:
        flag = SampleSizeFlag.BOUNDARY
    else:
        flag = SampleSizeFlag.INSUFFICIENT

    # mission_pass / progress_pass (Round 2 [W4] 反映)
    if flag == SampleSizeFlag.INSUFFICIENT:
        mission_pass = StagePassStatus.PENDING
        progress_pass = StagePassStatus.PENDING
    else:
        n_pass_windows = sum(1 for w in per_window_results if w.cf_result.gate_pass)
        mission_pass = (
            StagePassStatus.PASS if n_pass_windows == STAGE_C_LITE_NUM_WINDOWS
            else StagePassStatus.FAIL
        )
        progress_pass = (
            StagePassStatus.PASS if n_pass_windows >= STAGE_C_LITE_PROGRESS_PASS_MIN_WINDOWS
            else StagePassStatus.FAIL
        )

    return StageCLiteResult(
        per_window_results=tuple(per_window_results),
        cells_worst=cells_worst,
        mission_pass=mission_pass,
        progress_pass=progress_pass,
        sample_size_flag=flag,
    )


def evaluate_stage_c(
    individual_input: BCEvaluationInput,
    *,
    evaluate_fn: Callable[..., CanonicalFiveResult],
    live_criteria: dict,
    spread_stress_supported: bool = False,
) -> StageCResult:
    """12w + spread stress + cross-pair shadow validation (synthesis § 5.4).

    Round 2 [Critical] 1 反映: 完全 truth table 適用 (FAIL 優先).
    Round 3 [S1] 反映: cross_pair_pass は PASS/FAIL 二値前提 (assert で固定).
    Round 3 [S2] 反映: mission_fail_reason 保持.
    """
    thresholds = derive_stage_c_thresholds(live_criteria)

    # anchor_bundle 妥当性チェック (Round 2 [W3])
    if individual_input.anchor_bundle.pair != STAGE_C_ANCHOR_PAIR:
        raise StageBCInputError(
            f"anchor_bundle.pair ({individual_input.anchor_bundle.pair}) "
            f"!= STAGE_C_ANCHOR_PAIR ({STAGE_C_ANCHOR_PAIR})"
        )

    # 12w main
    c_trades, c_bars, c_universe = filter_to_period(
        individual_input.trades, individual_input.bars,
        individual_input.business_day_universe, individual_input.stage_c_period,
    )
    c_cf_result = evaluate_fn(c_trades, c_bars, thresholds, c_universe)
    live_criteria_pass = c_cf_result.gate_pass

    # spread stress (Round 1 [C1])
    if spread_stress_supported:
        stressed_trades = apply_spread_stress(c_trades, STAGE_C_SPREAD_STRESS_MULTIPLIER)
        stress_cf_result = evaluate_fn(stressed_trades, c_bars, thresholds, c_universe)
        stress_pass = (
            StagePassStatus.PASS if stress_cf_result.gate_pass
            else StagePassStatus.FAIL
        )
    else:
        stress_cf_result = None
        stress_pass = StagePassStatus.PENDING

    # cross-pair shadow (Round 1 [C4])
    per_pair_results: dict[str, CanonicalFiveResult] = {}
    for pair in STAGE_C_SHADOW_PAIR_LIST:
        if pair not in individual_input.shadow_pairs:
            raise StageBCInputError(
                f"shadow_pairs missing required pair: {pair}"
            )
        bundle = individual_input.shadow_pairs[pair]
        # provenance guard (Round 1 [W4] / 詳細 Round 1 [C3] 完全化)
        if bundle.pair != pair:
            raise StageBCInputError(
                f"PairBacktestBundle.pair ({bundle.pair}) != requested pair ({pair})"
            )
        # 詳細 Round 1 [C3]: anchor との genome_id / config_hash / partition_label 一致検証
        bundle.validate_against(individual_input.anchor_bundle)
        per_pair_results[pair] = evaluate_fn(
            bundle.trades, bundle.bars, thresholds, bundle.business_day_universe,
        )

    n_pair_pass = sum(1 for cf in per_pair_results.values() if cf.gate_pass)
    cross_pair_pass = (
        StagePassStatus.PASS if n_pair_pass >= STAGE_C_SHADOW_REQUIRED_COUNT
        else StagePassStatus.FAIL
    )
    # 詳細 Round 1 [C4]: assert→raise 置換 (-O 対策)
    if cross_pair_pass not in (StagePassStatus.PASS, StagePassStatus.FAIL):
        raise StageBCInputError(
            f"cross_pair_pass must be PASS or FAIL (binary contract): {cross_pair_pass}"
        )

    shadow_robustness_score = compute_cross_pair_shadow_score(per_pair_results)

    # mission_pass: 完全 truth table (Round 2 [C1])
    if not live_criteria_pass:
        mission_pass = StagePassStatus.FAIL
        mission_fail_reason = MissionFailReason.LIVE_CRITERIA
    elif cross_pair_pass == StagePassStatus.FAIL:
        mission_pass = StagePassStatus.FAIL
        mission_fail_reason = MissionFailReason.CROSS_PAIR
    elif stress_pass == StagePassStatus.FAIL:
        mission_pass = StagePassStatus.FAIL
        mission_fail_reason = MissionFailReason.STRESS
    elif live_criteria_pass and cross_pair_pass == StagePassStatus.PASS \
            and stress_pass == StagePassStatus.PASS:
        mission_pass = StagePassStatus.PASS
        mission_fail_reason = None
    else:
        # live=True, cross_pair=PASS, stress=PENDING のみ到達
        mission_pass = StagePassStatus.PENDING
        mission_fail_reason = None

    return StageCResult(
        c_cf_result=c_cf_result,
        stress_cf_result=stress_cf_result,
        per_pair_results=per_pair_results,
        live_criteria_pass=live_criteria_pass,
        stress_pass=stress_pass,
        cross_pair_pass=cross_pair_pass,
        mission_pass=mission_pass,
        mission_fail_reason=mission_fail_reason,
        shadow_robustness_score=shadow_robustness_score,
    )


def apply_spread_stress(
    trades: tuple[TradeRecord, ...],
    multiplier: float,
) -> tuple[TradeRecord, ...]:
    """Phase 1 では NotImplementedError raise (T070 で TradeRecord.spread_cost 追加後実装)."""
    raise NotImplementedError(
        "apply_spread_stress requires TradeRecord.spread_cost field "
        "(T070 Phase 2 申し送り)"
    )


def compute_cross_pair_shadow_score(
    per_pair_results: dict[str, CanonicalFiveResult],
) -> float | None:
    """shadow 5 pair の通過強度 (Round 1 [W3] / [C4]).

    現案 (詳細設計確定):
    - 全 pair が gate_pass=True なら 1.0 (完全 robust)
    - 1 pair でも fail なら通過率 (= n_pass / total_n)
    - per_pair_results が空なら None
    - 詳細案: 通過率 + 平均 (1 / (1 + gate_worst_gap)) で重み付け、 ただし Phase 1 では通過率のみ
        (smoke 後再校正候補)
    """
    if not per_pair_results:
        return None
    n_total = len(per_pair_results)
    n_pass = sum(1 for cf in per_pair_results.values() if cf.gate_pass)
    return n_pass / n_total


def compute_a_b_correlation_source_score(
    cf_result: CanonicalFiveResult,
) -> float:
    """higher-is-better の単一スカラー (Round 1 [C5] / Round 2 [W2]).

    定義: 1 / (1 + max(0, gate_worst_gap))
    値域: (0, 1]、 全達成で 1.0、 worst_gap 大で 0 に近づく
    """
    safe_gap = max(0.0, cf_result.gate_worst_gap)
    return 1.0 / (1.0 + safe_gap)


def compute_a_b_correlation(
    a_proxy_scores: dict[int, float],
    b_pooled_scores: dict[int, float],
) -> tuple[float, int]:
    """corr(A_proxy, B_pooled) を Run 終了時に計算 (synthesis § 8.7).

    両 score とも higher-is-better で正規化済前提。
    invariant: 共通 index でのみ corr 計算 (片方欠損は除外)。
    sample_size = len(共通 index 集合)。

    詳細 Round 1 [C5] 反映: 定数系列 / NaN / Inf で StatisticsError catch、
    deterministic に (0.0, sample_size) 戻り値固定。 caller (T071) が runtime 停止しない契約.
    """
    import statistics
    common_indices = set(a_proxy_scores.keys()) & set(b_pooled_scores.keys())
    if len(common_indices) < 2:
        return 0.0, len(common_indices)
    a_values = [a_proxy_scores[i] for i in sorted(common_indices)]
    b_values = [b_pooled_scores[i] for i in sorted(common_indices)]
    try:
        corr = statistics.correlation(a_values, b_values)
    except statistics.StatisticsError:
        # 定数系列 (variance=0) / 計算不能で 0.0 を返す (deterministic contract)
        return 0.0, len(common_indices)
    if not math.isfinite(corr):
        return 0.0, len(common_indices)
    return corr, len(common_indices)


def select_top_clite_forced_pass_indices(
    per_individual_clite_results: dict[int, StageCLiteResult],
    ratio: float = STAGE_C_LITE_FORCED_PASS_RATIO,
) -> frozenset[int]:
    """世代内 top 30% 強制通過 (synthesis § 5.3).

    Round 1 [W1] / Round 2 [W3] 反映: deterministic ranking key 確定:
    1. mission_pass desc (PASS > PENDING > FAIL)
    2. progress_pass desc (PASS > PENDING > FAIL)
    3. invariant_ok desc (per_window 全 invariant OK > NG)
    4. cells_worst asc (小さい = 良い)
    5. individual_id asc (deterministic tie-break)

    forced 数 = max(1, ceil(n_eligible * ratio))
    ただし n_eligible = mission_pass != FAIL の個体数 (FAIL 個体は除外)

    Round 2 [W3] / [W4] 反映: invariant_fail (= sample_size INSUFFICIENT) 個体は ranking 対象外
    (PENDING 扱いだが、 forced 通過候補から除外)
    """


def compute_gate_pass_excluding_dd(
    cf_result: CanonicalFiveResult,
    thresholds: CanonicalFiveThresholds,
) -> bool:
    """Round 2 [Critical] 反映: max_dd 軸を除いた gate_pass を計算.

    is_b_pass = gate_pass_ex_dd ∧ dd_pass の数式:
        gate_pass_ex_dd = max(max(0, -slack_m) for m in [sharpe, pnl, tc, wr]) <= GATE_PASS_TOLERANCE
                         AND cf_result.invariants.is_feasible

    DD 軸は per-fold DD max で別途判定するため、 b_pooled_cf.max_dd (concat 擬似 DD 含む) は使わない.
    """
    from src.alpha_factory.canonical_metrics import GATE_PASS_TOLERANCE
    if not cf_result.invariants.is_feasible:
        return False
    worst_ex_dd = max(
        max(0.0, -cf_result.slack_sharpe),
        max(0.0, -cf_result.slack_pnl),
        max(0.0, -cf_result.slack_tc),
        max(0.0, -cf_result.slack_wr),
    )
    return worst_ex_dd <= GATE_PASS_TOLERANCE


def derive_stage_b_thresholds(live_criteria: dict) -> CanonicalFiveThresholds:
    """Stage B (62w) 用 thresholds. live_criteria 通り (24m baseline と等値想定)。"""

def derive_stage_c_lite_thresholds(live_criteria: dict) -> CanonicalFiveThresholds:
    """Stage C-lite (6w window) 用 thresholds. window 比例 (Decision Pending、 Phase 2 で確定)."""

def derive_stage_c_thresholds(live_criteria: dict) -> CanonicalFiveThresholds:
    """Stage C (12w) 用 thresholds. window 比例 (12w / 24m)."""


def compute_c_pass_depth(
    c_lite_result: StageCLiteResult,
    c_result: StageCResult,
) -> float:
    """Follow-up (T066 Phase 0) 反映: c_pass_depth 計算 SSOT.

    計算式 (T066 概念 R4 確定):
        c_pass_depth = c_lite_result.n_pass_windows × 0.25
                     + bonus(c_result.mission_pass)
        bonus(PASS) = 1.0 / bonus(PENDING) = 0.5 / bonus(FAIL) = 0.0

    値域: [0.0, 1.75]
        - n_pass_windows: 0..3 (× 0.25 = [0.0, 0.75])
        - mission_pass status: PASS=1.0 / PENDING=0.5 / FAIL=0.0
        - 合計: [0.0, 0.75] + [0.0, 1.0] = [0.0, 1.75]

    用途 (T066 CA eviction lex key #4): 大が上位.
    Stage C-lite を多く通過 ∧ Stage C で mission_pass に近い個体ほど archive 残留優先.

    Determinism: pure function、 入力同値で出力同値. 浮動小数点誤差なし
    (整数 × 0.25 + 整数定数 のみで構成、 IEEE 754 で exact).

    Round 1 [W1] 反映: StagePassStatus 3 値全てを明示分岐、 未知値は ValueError raise
    (将来 enum 拡張時の silent FAIL 同等扱いを早期検知).

    Collider bias 独立性 (T072 規範継承): 本関数は c_lite_result.n_pass_windows と
    c_result.mission_pass のみに依存し、 holiday_markets / dst_transition_markets /
    observability_flags 系には触れない. stratified audit は本 module で扱わない.
    """
    # Round 2 [W1] 反映: SSOT 一貫性のため STAGE_C_LITE_NUM_WINDOWS 参照
    # (StageCLiteResult.__post_init__ と同一定数を共有、 literal 3 を散在させない)
    if not 0 <= c_lite_result.n_pass_windows <= STAGE_C_LITE_NUM_WINDOWS:
        raise ValueError(
            f"n_pass_windows must be in [0, {STAGE_C_LITE_NUM_WINDOWS}], "
            f"got {c_lite_result.n_pass_windows}"
        )
    base = c_lite_result.n_pass_windows * 0.25
    if c_result.mission_pass == StagePassStatus.PASS:
        bonus = 1.0
    elif c_result.mission_pass == StagePassStatus.PENDING:
        bonus = 0.5
    elif c_result.mission_pass == StagePassStatus.FAIL:
        bonus = 0.0
    else:
        raise ValueError(
            f"unknown StagePassStatus: {c_result.mission_pass!r} "
            "(expected PASS / PENDING / FAIL)"
        )
    return base + bonus


def filter_to_period(
    trades: tuple[TradeRecord, ...],
    bars: BarEquitySeries,
    universe: dict[SessionBucket, frozenset[int]],
    period: "Period",
) -> tuple[tuple[TradeRecord, ...], BarEquitySeries, dict[SessionBucket, frozenset[int]]]:
    """T060 Period に含まれる trades / bars / universe をフィルタ."""


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------


def evaluate_bc_for_a_pass(
    a_pass_inputs: dict[int, BCEvaluationInput],
    *,
    evaluate_fn: Callable[..., CanonicalFiveResult],
    live_criteria: dict,
    spread_stress_supported: bool = False,
) -> dict[int, BCEvaluationResult]:
    """全 a_pass 個体について Stage B/C-lite/C を一括評価.

    手順 (per individual):
    1. b_result = evaluate_stage_b(input, evaluate_fn, live_criteria)
    2. c_lite_result = evaluate_stage_c_lite(input, evaluate_fn, live_criteria)
       (StageCLiteResult.n_pass_windows = sum(1 for w in per_window_results
        if w.cf_result.gate_pass) を deterministic に同時計算、 値域 [0, 3])
    3. c_result = evaluate_stage_c(input, evaluate_fn, live_criteria, spread_stress_supported)
    4. mission_pass: c_result.mission_pass を採用 (Stage C が最終 mission gate、 synthesis § 5.4)
    5. b_pooled_cf = b_result.b_pooled_cf_result (None possible)
    6. pareto_axis_usable = b_pooled_cf is not None
    7. c_pass_depth = compute_c_pass_depth(c_lite_result, c_result)
       (Follow-up (T066 Phase 0): 値域 [0.0, 1.75]、 T066 CA eviction lex key #4 で消費)
    8. BCEvaluationResult を返す (c_pass_depth field 同梱)
    """
```

### ルックアヘッドバイアスチェック

- 各 stage 評価期間 = T060 Period (deterministic)、 lookback 操作なし
- pooled OOS の fold 境界 reset で擬似 DD 過小評価防止 (Round 1 [C3])
- cross-pair pair 別 backtest は caller (T070) が provide、 T064 内では再 backtest しない

### C3 / C7 適用

- **C3**: 該当なし
- **C7**: Stage C-lite 6w で 30 blocks/bucket 境界、 SampleSizeFlag (OK/BOUNDARY/INSUFFICIENT) で diagnostic、 INSUFFICIENT は PENDING 強制

### パフォーマンスチェック

- 1 個体当り T061 呼出回数: 5 fold (Stage B per-fold) + 1 (Stage B pooled) + 3 (Stage C-lite) + 1 (Stage C 12w) + (1 stress) + 5 (cross-pair) = 16 回 (stress 除けば 15 回)
- pop=192 × stage_a pass rate ~0.15-0.40 = 29-77 個体 → 464-1232 T061 呼出 / 世代
- 1 評価 ~0.5ms × 1232 = 0.6 sec / 世代、 64 gen / Run = 40 sec / Run
- 並列 4 worker で ~10 sec / Run、 全体性能内

### テスト計画 (施策 2 で詳述)

### リスク

- T061 マージ前は本 PR を merge しない (`from src.alpha_factory.canonical_metrics import ...`)
- T060 マージ前は影響なし、 ただし Period/Fold 型 reference は forward ref で対応
- 既存 stage_gate.py に touch しないため Phase 1 単体では runtime に影響なし

---

## 施策 2: `tests/alpha_factory/test_stage_bc_evaluator.py` 新規作成

### テスト計画 (主要のみ抜粋、 全項目は概念設計の Round 2 改訂表 + Round 3 [S3] 反映)

#### Constants
- `test_stage_b_num_folds_is_5`
- `test_stage_c_lite_num_windows_is_3`
- `test_stage_c_lite_forced_pass_ratio_is_0_30`
- `test_stage_c_spread_stress_multiplier_is_1_5`
- `test_stage_c_shadow_pair_list_excludes_anchor`
  (anchor=EUR_JPY が STAGE_C_SHADOW_PAIR_LIST に含まれない、 5 pair、 Round 1 [C4])
- `test_stage_c_shadow_required_count_is_5`

#### StagePassStatus
- `test_stage_pass_status_has_pass_fail_pending_three_values`

#### Stage B
- `test_stage_b_all_folds_feasible_yields_b_pooled_cf_not_none`
- `test_stage_b_one_fold_invariant_fail_yields_b_pooled_cf_none`
  (Round 1 [C2]: 1 fold 違反で b_pooled_cf_result=None)
- `test_stage_b_pareto_axis_usable_false_when_b_pooled_cf_none`
- `test_stage_b_pareto_axis_usable_true_when_b_pooled_cf_not_none`

#### build_pooled_oos_input (Round 1 [C3] / Round 2 [W1] / 概念 Round 3 [S3])
- `test_build_pooled_oos_input_pooled_dd_equals_max_of_per_fold_dd`
  (詳細 Round 3 [S3]: pooled_DD = per-fold DD max を確認)
- `test_build_pooled_oos_input_rejects_overlapping_fold_test_periods`
- `test_build_pooled_oos_input_rejects_non_chronological_fold_order`
- `test_build_pooled_oos_input_business_day_universe_is_union_of_per_fold`
- `test_build_pooled_oos_input_fold_boundaries_metadata_recorded`

#### Stage C-lite (Round 1 [W2] / [W5] / Round 2 [W4])
- `test_stage_c_lite_three_windows_all_pass_yields_mission_pass`
- `test_stage_c_lite_two_windows_pass_yields_progress_pass`
- `test_stage_c_lite_zero_windows_pass_yields_fail`
- `test_stage_c_lite_cells_worst_is_max_of_three_window_gate_worst_gaps`
  (Round 1 [W2])
- `test_stage_c_lite_sample_size_ok_when_blocks_above_30`
- `test_stage_c_lite_sample_size_boundary_when_blocks_25_to_29`
- `test_stage_c_lite_sample_size_insufficient_when_blocks_below_25`
- `test_stage_c_lite_insufficient_sample_yields_mission_pass_pending`
  (Round 2 [W4]: INSUFFICIENT で PENDING 強制)
- `test_stage_c_lite_insufficient_sample_yields_progress_pass_pending`

#### Stage C truth table (Round 2 [Critical] 1)
- `test_stage_c_live_fail_yields_mission_fail_with_reason_live_criteria`
- `test_stage_c_cross_pair_fail_yields_mission_fail_with_reason_cross_pair`
- `test_stage_c_stress_fail_yields_mission_fail_with_reason_stress`
- `test_stage_c_all_pass_yields_mission_pass`
- `test_stage_c_stress_pending_with_live_pass_yields_mission_pending`
- `test_stage_c_stress_pending_with_live_fail_yields_mission_fail_not_pending`
  (重要 truth table: live=False > stress=PENDING)
- `test_stage_c_cross_pair_pass_is_binary_pass_or_fail_never_pending`
  (Round 3 [S1] assert)
- `test_stage_c_mission_fail_reason_is_none_when_pass_or_pending`

#### Stage C cross-pair (Round 1 [C4] / [W4])
- `test_stage_c_shadow_5_pairs_all_pass_yields_cross_pair_pass`
- `test_stage_c_shadow_4_of_5_pairs_pass_yields_cross_pair_fail`
- `test_stage_c_rejects_missing_shadow_pair_in_input`
- `test_stage_c_rejects_pair_bundle_with_mismatched_pair_field`
  (provenance guard、 Round 1 [W4])
- `test_stage_c_anchor_pair_not_in_shadow_evaluation`

#### apply_spread_stress (Round 1 [C1])
- `test_apply_spread_stress_phase_1_raises_not_implemented_error`

#### compute_cross_pair_shadow_score (Round 1 [W3])
- `test_shadow_robustness_score_all_pass_yields_one`
- `test_shadow_robustness_score_partial_pass_yields_pass_ratio`
- `test_shadow_robustness_score_empty_pairs_yields_none`

#### compute_a_b_correlation (Round 1 [C5] / Round 2 [W2])
- `test_a_b_correlation_source_score_higher_is_better`
- `test_a_b_correlation_source_score_full_achievement_yields_one`
- `test_a_b_correlation_source_score_handles_negative_gap_with_clip`
  (Round 2 [W2] domain ガード defensive clip)
- `test_a_b_correlation_returns_pearson_with_sample_size`
- `test_a_b_correlation_excludes_individuals_missing_from_either_dict`

#### select_top_clite_forced_pass_indices (Round 1 [W1] / Round 2 [W3])
- `test_forced_pass_uses_deterministic_ranking_key`
- `test_forced_pass_excludes_invariant_fail_individuals`
- `test_forced_pass_count_is_max_one_or_ceil_of_eligible_times_ratio`

#### evaluate_bc_for_a_pass (top-level、 4 代表ケース)
- `test_evaluate_bc_perfect_individual_yields_mission_pass`
- `test_evaluate_bc_b_invariant_fail_yields_pareto_axis_unusable`
- `test_evaluate_bc_c_lite_insufficient_sample_yields_mission_pending_at_clite`
- `test_evaluate_bc_stress_unsupported_default_yields_stage_c_mission_pending`

#### Follow-up (T066 Phase 0): n_pass_windows / c_pass_depth contract + 計算
- `test_stage_c_lite_result_has_n_pass_windows_field`
  (`__dataclass_fields__` ベースで存在検証、 `int` annotation 確認 / Round 2 W1 hasattr 偽陰性回避)
- `test_stage_c_lite_n_pass_windows_matches_per_window_gate_pass_count`
  (per_window_results の gate_pass=True 数と一致、 値域 [0, 3])
- `test_stage_c_lite_n_pass_windows_zero_when_all_windows_fail`
- `test_stage_c_lite_n_pass_windows_three_when_all_windows_pass`
- `test_bc_evaluation_result_has_c_pass_depth_field`
  (T066 詳細 Round 1 [C3] 反映の contract test 同型、 `__dataclass_fields__` ベースで存在検証 + `float` annotation 確認)
- `test_compute_c_pass_depth_pass_n3_yields_one_point_seven_five`
  (上限境界: c_lite_n_pass_windows=3 + mission_pass=PASS → 0.75 + 1.0 = 1.75)
- `test_compute_c_pass_depth_fail_n0_yields_zero`
  (下限境界: n=0 + FAIL → 0.0)
- `test_compute_c_pass_depth_pending_n1_yields_zero_point_seven_five`
  (PENDING 中間: n=1 + PENDING → 0.25 + 0.5 = 0.75)
- `test_compute_c_pass_depth_fail_n2_yields_zero_point_five`
  (FAIL でも c_lite 通過分は加点: n=2 + FAIL → 0.5 + 0.0 = 0.5)
- `test_compute_c_pass_depth_deterministic_for_same_input`
  (pure function、 同入力で同出力、 浮動小数点 exact 比較で確認)
- `test_compute_c_pass_depth_value_range_inclusive_zero_and_one_point_seven_five`
  (全組合せ **3 StagePassStatus (PASS/PENDING/FAIL) × 4 n (0/1/2/3) = 12 ケース** で `0.0 <= depth <= 1.75`、 status=FAIL は 0.0..0.75、 PENDING は 0.5..1.25、 PASS は 1.0..1.75. Round 1 [Critical] 反映で組合せ数を再明記)
- `test_compute_c_pass_depth_rejects_unknown_status`
  (Round 1 [W1] 反映: StagePassStatus 互換だが PASS/PENDING/FAIL 以外の値 (= mock enum) を渡すと ValueError raise)
- `test_compute_c_pass_depth_rejects_n_pass_windows_out_of_range`
  (Round 1 [W2] 反映: c_lite_result.n_pass_windows < 0 または > 3 で ValueError raise. ただし StageCLiteResult __post_init__ で先に弾かれるため、 mock dataclass で迂回した bypass パスのみ test)
- `test_stage_c_lite_result_rejects_n_pass_windows_out_of_range`
  (Round 1 [W2] 反映: StageCLiteResult dataclass 生成時に n_pass_windows ∈ [0, 3] 外で ValueError raise、 n_pass_windows > len(per_window_results) でも ValueError raise)
- `test_evaluate_bc_for_a_pass_yields_c_pass_depth_consistent_with_compute_c_pass_depth`
  (top-level 経由で c_pass_depth が compute_c_pass_depth(c_lite, c) と一致)

### リスク

- (テストのみ、 リスク軽微)

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **standalone** (T058-T063 マージ後前提、 Phase 2 で 11 箇所同時更新を別 PR) |
| 判断根拠 | T064 PR は単体テストのみで既存経路に touch しない |
| 競合リスク | T058-T063 マージ済前提、 直接 import は T060 (Period/Fold) と T061 (canonical_metrics) のみ |
| 想定実装時間 | 大 (2 施策、 2-3 day 想定。 3 stage + cross-pair + truth table + sample-size flag のテスト工数が主) |

## 実装順序

T064 PR で 2 施策を 1 PR で着地。 Phase 2 (11 箇所同時更新 + spread_cost field 追加) は T065 統合 + T070 と同時に別 PR (別 TODO)。

---

## DoD (Definition of Done)

T064 PR 完了基準:

### コード DoD

- [ ] `src/alpha_factory/stage_bc_evaluator.py` 新規作成 (Enum 3 + dataclass 11 + helper 8 + top-level 1 + 例外 2)
- [ ] `tests/alpha_factory/test_stage_bc_evaluator.py` 新規作成 (上記 test 全 pass、 4 代表ケース + truth table 完全網羅 + 境界値)
- [ ] `uv run pytest tests/alpha_factory/test_stage_bc_evaluator.py` 全 pass
- [ ] `uv run ruff check src/ tests/` clean
- [ ] `uv run mypy src/` clean
- [ ] `stage_gate.py` / `swim_lane.py` / `cross_pair.py` / `archive.py` / `config.py` / `default.yaml` / `docs/alpha_factory/stage-gates.md` を変更しない

### Phase 1 (T064 PR) C2 parallel-path 確認 DoD (5 段階、 T063 同様)

- [ ] 段階 1 (直 import): `grep -rn "from src.alpha_factory.stage_bc_evaluator" scripts/ src/ tests/` が 自身 + tests のみ
- [ ] 段階 2 (alias import): `grep -rn -E "import\s+src\.alpha_factory\.stage_bc_evaluator" src/ scripts/ tests/` が 自身 + tests のみ
- [ ] 段階 3 (relative import): `grep -rn -E "from\s+\.+\s*stage_bc_evaluator" src/ scripts/ tests/` が 自身 + tests のみ
- [ ] 段階 4 (再エクスポート): 0 hit
- [ ] 段階 5 (runtime シンボル): `grep -rn -E "evaluate_bc_for_a_pass|BCEvaluationResult|StagePassStatus|MissionFailReason" src/alpha_factory/stage_gate.py src/alpha_factory/swim_lane.py src/alpha_factory/cross_pair.py scripts/alpha_factory/run_ga.py` が 0 hit

### Phase 2 (T065 統合 + T070 と同時、 別 PR) DoD (申し送り、 13 箇所)

- [ ] `stage_gate.py:evaluate_stage_b` 全廃 → T064 evaluate_stage_b に置換 (T065)
- [ ] `stage_gate.py:evaluate_stage_c` 全廃 → T064 evaluate_stage_c に置換 (T065)
- [ ] (新規) `stage_gate.py:evaluate_stage_c_lite` 新規実装 (T064 evaluate_stage_c_lite 呼出) (T065)
- [ ] `cross_pair.py` を T064 per_pair_results 統合に置換 (T065)
- [ ] (新規) `src/alpha_factory/observability/a_b_divergence.py` で T064 compute_a_b_correlation 呼出 + T063 update_divergence_state 注入 (T071)
- [ ] `scripts/alpha_factory/run_ga.py` で per-generation T063 → T064 → T062 chain orchestration (T065)
- [ ] `src/alpha_factory/config.py:StageGateConfig` 旧 stage_b/c.* 全廃、 新仕様反映 (T065)
- [ ] `config/alpha_factory/default.yaml` 旧 stage_b/c.* 全廃、 新仕様 + cross-pair list 反映 (T065)
- [ ] `archive.py` で 3 層流入 (mission_pass / progress_pass / score_bypass) を BCEvaluationResult から識別 (T067)
- [ ] **(別 TODO) `TradeRecord.spread_cost` field 追加 + apply_spread_stress 正式実装** (T070)
- [ ] `docs/alpha_factory/stage-gates.md` を新仕様に書き換え (T065)
- [ ] **runtime wiring smoke** (T061-T063 と同型): `evaluate_stage_*` を実際に呼んで T064 が configured に走ることを確認 (T065 PR DoD)
- [ ] **(Follow-up Phase 2)** evaluate_stage_c_lite 実装で `n_pass_windows = sum(1 for w in per_window_results if w.cf_result.gate_pass)` を deterministic 計算 + StageCLiteResult 注入、 evaluate_bc_for_a_pass 実装で `c_pass_depth = compute_c_pass_depth(c_lite_result, c_result)` を BCEvaluationResult 注入 (T065 統合 PR で T066 CA eviction 配線と同期確認)
- [ ] **(Follow-up Phase 2)** T066 archive admission 実装が `BCEvaluationResult.c_pass_depth` を CA eviction lex key #4 として消費する箇所を 1 経路に集約 (`src/alpha_factory/archive.py` 内、 grep -rn "c_pass_depth" src/ で T064 実装 + T066 archive のみ hit、 重複定義禁止)

---

## 関連 / 後段 TODO

- T058-T063: 依存先 (Schema v2 / EpochManager / Partition+Fold / canonical 5 / mission_inf_gap / Stage A)
- T065-T066: NSGA-II + CPPS (T064 b_pooled_cf を Pareto 軸、 T062 mission_inf_gap で Pareto f3、 T064 mission_pass で archive 流入、 **T064 c_pass_depth で T066 CA eviction lex key #4 = Follow-up Phase 0 依存**)
- T067: Loop closure (T064 BCEvaluationResult の 3 層流入を archive admission で消費、 forced_pass の T064 出力消費)
- T070: backtest engine (cross-pair 出力 + spread_cost field、 Phase 2 申し送り)
- T071: observability (compute_a_b_correlation 計算 + T063 注入 orchestration)

### Follow-up (T066 Phase 0) merge 順序契約

T064 follow-up PR (本設計改訂) は **T066/T067/T068 Phase 2 配線 PR より先 merge 必須**。 理由:

1. T066 詳細設計が `BCEvaluationResult.c_pass_depth` field を CA eviction lex key #4 として消費 (T066 R4 / R9)
2. T066 PR の contract test (`test_bc_evaluation_result_has_c_pass_depth_field`) は T064 PR で field 定義された前提で fail-fast 動作
3. T067 archive admission 実装も `c_pass_depth` を indirect 消費 (T066 経由)、 T068 graceful failure handling で `c_pass_depth` 不整合は import error or contract test fail で早期検知
4. T064 follow-up は detailed-design.md / conceptual-design.md 改訂のみの **設計 PR** (Phase 1 範囲)、 src/ 実装は T065 統合 + T070 と同時 (Phase 2)

**T064 follow-up Phase 1 (= 本 PR) 着地基準**: detailed + conceptual design 改訂、 Codex 詳細レビュー APPROVED、 1 commit、 src/ touch なし.

## 根拠 / 先行実装

- synthesis § 5.2 / § 5.3 / § 5.4 / § 6.7 / § 8.3 / § 11
- Tashman (2000) "Out-of-sample tests of forecasting accuracy": rolling-origin pooled OOS の理論基盤
- Bailey et al. (2014) CSCV: fold 集約の理論的根拠
- zenigame `evaluation/stage_gate.py`: 元実装、 fx 側で 5 fold pooled + 15 セル worst + cross-pair shadow を新規追加
- T061 詳細設計 APPROVED / T062 詳細設計 APPROVED / T063 詳細設計 APPROVED
