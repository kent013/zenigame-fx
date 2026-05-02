"""T064: Stage B + C-lite + C evaluator — synthesis § 5.2 / § 5.3 / § 5.4 / § 6.7 / § 8.3 確定式の実装.

詳細:
- 概念設計: ``devnotes/20260430-0230-todo-T064-stage-bc-evaluator/conceptual-design.md``
- 詳細設計: ``devnotes/20260430-0230-todo-T064-stage-bc-evaluator/detailed-design.md``
- synthesis § 5.2 (Stage B 5 fold rolling-origin pooled OOS) / § 5.3 (Stage C-lite 3
  windows × 15 セル worst) / § 5.4 (Stage C 12w + spread stress + cross-pair shadow)
  / § 6.7 (gate aggregation) / § 8.3 (archive eviction lex)
- T060 依存: :class:`~src.alpha_factory.partition.Period` / :class:`~src.alpha_factory.partition.Fold`
- T061 依存: :class:`~src.alpha_factory.canonical_metrics.CanonicalFiveResult` /
  :class:`~src.alpha_factory.canonical_metrics.CanonicalFiveThresholds` /
  :func:`~src.alpha_factory.canonical_metrics.evaluate_canonical_five` を消費.

Phase 1 (本 TODO = T064 PR 1): 単体実装 + テストのみ、 ``stage_gate.py`` /
``swim_lane.py`` / ``cross_pair.py`` への置換は **Phase 2 (別 PR、 T065 統合と同時)**
で実施。 T064 PR 1 単独 merge で runtime に影響なし。

Follow-up (T066 Phase 0 反映):
- :attr:`StageCLiteResult.n_pass_windows` (値域 [0, 3])
- :attr:`BCEvaluationResult.c_pass_depth` (値域 [0.0, 1.75])
- :func:`compute_c_pass_depth` (T066 CA eviction lex key #4 SSOT)

Collider bias 独立性 (T072 規範継承): ``c_pass_depth`` および ``n_pass_windows`` の計算経路は
``StageCLiteResult.per_window_results.cf_result.gate_pass`` と ``StageCResult.mission_pass``
の 2 input のみに依存し、 holiday_markets / dst_transition_markets / observability_flags 系
には触れない (= stratified audit は T071 RunObservabilityReport 経由)。

学術引用:
- Tashman, L. J. (2000). "Out-of-sample tests of forecasting accuracy."
  International Journal of Forecasting, 16(4), 437-450.
- Bailey, D. H., Borwein, J., Lopez de Prado, M., & Zhu, Q. J. (2014).
  "The probability of backtest overfitting." Journal of Computational Finance.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Final

from src.alpha_factory.canonical_metrics import (
    GATE_PASS_TOLERANCE,
    BarEquityPoint,
    BarEquitySeries,
    CanonicalFiveResult,
    CanonicalFiveThresholds,
    SessionBucket,
    TradeRecord,
)
from src.alpha_factory.partition import Fold, Period

__all__ = [
    "STAGE_B_NUM_FOLDS",
    "STAGE_C_ANCHOR_PAIR",
    "STAGE_C_LITE_FORCED_PASS_RATIO",
    "STAGE_C_LITE_NUM_WINDOWS",
    "STAGE_C_LITE_PROGRESS_PASS_MIN_WINDOWS",
    "STAGE_C_LITE_SAMPLE_SIZE_BOUNDARY_MIN_BLOCKS",
    "STAGE_C_LITE_SAMPLE_SIZE_OK_MIN_BLOCKS",
    "STAGE_C_SHADOW_PAIR_LIST",
    "STAGE_C_SHADOW_REQUIRED_COUNT",
    "STAGE_C_SPREAD_STRESS_MULTIPLIER",
    "BCEvaluationInput",
    "BCEvaluationResult",
    "MissionFailReason",
    "PairBacktestBundle",
    "PoolFoldedInput",
    "SampleSizeFlag",
    "StageBCEvaluatorError",
    "StageBCInputError",
    "StageBFoldResult",
    "StageBResult",
    "StageCLiteResult",
    "StageCLiteWindowResult",
    "StageCResult",
    "StagePassStatus",
    "apply_spread_stress",
    "build_pooled_oos_input",
    "compute_a_b_correlation",
    "compute_a_b_correlation_source_score",
    "compute_c_pass_depth",
    "compute_cross_pair_shadow_score",
    "compute_gate_pass_excluding_dd",
    "derive_stage_b_thresholds",
    "derive_stage_c_lite_thresholds",
    "derive_stage_c_thresholds",
    "evaluate_bc_for_a_pass",
    "evaluate_stage_b",
    "evaluate_stage_c",
    "evaluate_stage_c_lite",
    "filter_to_period",
    "select_top_clite_forced_pass_indices",
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StagePassStatus(StrEnum):
    """Tri-state pass status (詳細 Round 1 [C1] 反映).

    PASS / FAIL / PENDING の 3 値。 Follow-up Round 1 [W1] に従い、 ``compute_c_pass_depth``
    では 3 値を全て明示分岐し、 未知値は ``ValueError`` raise する.
    """

    PASS = "pass"
    FAIL = "fail"
    PENDING = "pending"


class SampleSizeFlag(StrEnum):
    """Sample size diagnostic flag (Round 1 [W5] 反映).

    OK: bucket 内 block 数 >= 30 (synthesis § 5.3 確定値)
    BOUNDARY: 25 <= block 数 < 30
    INSUFFICIENT: block 数 < 25 (= mission_pass / progress_pass 強制 PENDING)
    """

    OK = "ok"
    BOUNDARY = "boundary"
    INSUFFICIENT = "insufficient"


class MissionFailReason(StrEnum):
    """Mission_pass=FAIL 理由 (概念 Round 3 [S2] 反映).

    truth table 優先順位 (Round 2 [Critical] 1):
    LIVE_CRITERIA > CROSS_PAIR > STRESS。 PASS / PENDING は ``None`` (mission_fail_reason field).
    """

    LIVE_CRITERIA = "live_criteria"
    CROSS_PAIR = "cross_pair"
    STRESS = "stress"


# ---------------------------------------------------------------------------
# Constants (synthesis § 5.2 / § 5.3 / § 5.4 厳密準拠)
# ---------------------------------------------------------------------------

STAGE_B_NUM_FOLDS: Final[int] = 5
"""synthesis § 5.2: 5 fold rolling-origin pooled OOS."""

STAGE_C_LITE_NUM_WINDOWS: Final[int] = 3
"""synthesis § 5.3: 3 disjoint C-lite windows × canonical 5 worst → 15 セル worst.

Follow-up Round 2 [W1] 反映 SSOT: ``StageCLiteResult.n_pass_windows`` の上限値 +
``compute_c_pass_depth`` の base 上限の SSOT.
"""

STAGE_C_LITE_FORCED_PASS_RATIO: Final[float] = 0.30
"""synthesis § 5.3: 世代内 top 30% 強制通過 ratio."""

STAGE_C_LITE_PROGRESS_PASS_MIN_WINDOWS: Final[int] = 2
"""progress_pass = 2/3 windows pass (synthesis § 5.3)."""

STAGE_C_LITE_SAMPLE_SIZE_OK_MIN_BLOCKS: Final[int] = 30
"""sample_size_flag=OK の最低 block 数 (synthesis § 5.3)."""

STAGE_C_LITE_SAMPLE_SIZE_BOUNDARY_MIN_BLOCKS: Final[int] = 25
"""sample_size_flag=BOUNDARY の最低 block 数 (synthesis § 5.3)."""

STAGE_C_SPREAD_STRESS_MULTIPLIER: Final[float] = 1.5
"""synthesis § 5.4: spread cost を 1.5x した stress test multiplier."""

STAGE_C_ANCHOR_PAIR: Final[str] = "EUR_JPY"
"""synthesis § 5.4: anchor pair (Stage B/C-lite/C 評価対象)."""

STAGE_C_SHADOW_PAIR_LIST: Final[tuple[str, ...]] = (
    "USD_JPY",
    "EUR_USD",
    "AUD_JPY",
    "USD_CAD",
    "USD_ZAR",
)
"""synthesis § 5.4: cross-pair shadow validation 対象 5 pair (anchor 除く)."""

STAGE_C_SHADOW_REQUIRED_COUNT: Final[int] = 5
"""synthesis § 5.4: 5/5 全通過で cross_pair_pass=PASS."""


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
    """Cross-pair backtest 結果の provenance guard (Round 1 [W4] / [S4] /
    詳細 Round 1 [C3] 反映).

    field:
    - ``pair``: 評価対象 pair 識別子 (例 ``"USD_JPY"``)
    - ``genome_id``: 個体 genome ID (anchor と一致必須)
    - ``config_hash``: config 構成 hash (anchor と一致必須)
    - ``partition_label``: T060 :attr:`~src.alpha_factory.partition.Period.label`
      または epoch_id (anchor と一致必須)
    - ``trades`` / ``bars`` / ``business_day_universe``: T061 評価入力 (該当 pair の)

    invariant: ``validate_against`` で anchor との provenance 一致を保証する.
    """

    pair: str
    genome_id: str
    config_hash: str
    partition_label: str
    trades: tuple[TradeRecord, ...]
    bars: BarEquitySeries
    business_day_universe: dict[SessionBucket, frozenset[int]]

    def validate_against(self, anchor_bundle: PairBacktestBundle) -> None:
        """anchor_bundle と provenance 整合性を検証 (詳細 Round 1 [C3] / [Suggestion] 2).

        ``genome_id`` / ``config_hash`` / ``partition_label`` の 3 axis 一致を要求.
        ``pair`` field 自体は別 (anchor != self.pair が前提)、 caller が別経路で照合.

        Raises:
            StageBCInputError: いずれか不一致.
        """
        if self.genome_id != anchor_bundle.genome_id:
            raise StageBCInputError(
                f"PairBacktestBundle({self.pair}).genome_id ({self.genome_id}) != "
                f"anchor.genome_id ({anchor_bundle.genome_id})"
            )
        if self.config_hash != anchor_bundle.config_hash:
            raise StageBCInputError(
                f"PairBacktestBundle({self.pair}).config_hash "
                f"({self.config_hash}) != anchor.config_hash "
                f"({anchor_bundle.config_hash})"
            )
        if self.partition_label != anchor_bundle.partition_label:
            raise StageBCInputError(
                f"PairBacktestBundle({self.pair}).partition_label "
                f"({self.partition_label}) != anchor.partition_label "
                f"({anchor_bundle.partition_label})"
            )


@dataclass(frozen=True)
class StageBFoldResult:
    """1 fold の評価結果 + fold period (詳細 Round 1 [C1] 反映で fold_period 追加).

    field:
    - ``fold_index``: fold 番号 (0-origin)
    - ``fold_period_start`` / ``fold_period_end``: T060 ``fold.test`` 期間境界
      (build_pooled_oos_input が時系列順 / 非重複検証で参照)
    - ``cf_result``: T061 :class:`CanonicalFiveResult` (per-fold 評価結果)
    - ``is_feasible_invariant``: cf_result.invariants.is_feasible のキャッシュ
    """

    fold_index: int
    fold_period_start: datetime
    fold_period_end: datetime
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
    is_feasible_invariant=False の場合、 ``b_pooled_cf_result=None`` を設定.
    GA 主選抜 (T065 Pareto 3 軸) は ``b_pooled_cf_result is not None`` の個体のみ消費する責務.

    DD 集約 (詳細 Round 1 [C1] / [C2] 反映、 synthesis § 5.2 厳密準拠):
    - ``b_pooled_cf_result.max_dd`` は concat bars で T061 が計算 (記録用)
    - ``pooled_dd_per_fold_max`` は per-fold max_dd の max (synthesis § 5.2 準拠、
      stage B pass 判定で採用)
    - ``is_b_pass`` は ``gate_pass_ex_dd ∧ dd_pass`` で組合せ判定
      (concat DD で擬似 DD を含む ``b_pooled_cf_result.max_dd`` は使わない)
    """

    b_pooled_cf_result: CanonicalFiveResult | None
    pooled_dd_per_fold_max: float | None
    per_fold_results: tuple[StageBFoldResult, ...]
    is_feasible_invariant: bool
    is_b_pass: bool


@dataclass(frozen=True)
class StageCLiteWindowResult:
    """Stage C-lite 1 window の評価結果."""

    window_index: int
    cf_result: CanonicalFiveResult


@dataclass(frozen=True)
class StageCLiteResult:
    """Stage C-lite 評価結果 (3 windows × canonical 5 worst).

    field:
    - ``per_window_results``: 各 window の :class:`StageCLiteWindowResult`
    - ``cells_worst``: 15 セル worst = max over 3 windows of gate_worst_gap
      (Round 1 [W2] 反映)
    - ``mission_pass``: 全 3 windows AND (= ``StagePassStatus.PASS`` if 3/3 pass)
    - ``progress_pass``: 2/3 windows pass で PASS (synthesis § 5.3)
    - ``sample_size_flag``: Round 1 [W5] / Round 2 [W4] (INSUFFICIENT で
      mission_pass / progress_pass を PENDING 強制)
    - ``n_pass_windows``: per_window_results のうち ``cf_result.gate_pass=True`` の数.
      値域 ``[0, STAGE_C_LITE_NUM_WINDOWS=3]``.
      Follow-up (T066 Phase 0): ``compute_c_pass_depth`` 計算 SSOT
      (T066 CA eviction lex key #4 で消費).

    invariant (Follow-up Round 1 [W2]): ``__post_init__`` で
    ``0 <= n_pass_windows <= STAGE_C_LITE_NUM_WINDOWS`` および
    ``n_pass_windows <= len(per_window_results)`` を二重検証.
    """

    per_window_results: tuple[StageCLiteWindowResult, ...]
    cells_worst: float
    mission_pass: StagePassStatus
    progress_pass: StagePassStatus
    sample_size_flag: SampleSizeFlag
    n_pass_windows: int

    def __post_init__(self) -> None:
        """Follow-up Round 1 [W2] 反映: n_pass_windows 値域 invariant 検証.

        生成時に ``[0, STAGE_C_LITE_NUM_WINDOWS=3]`` 外なら ``ValueError`` raise.
        ``len(per_window_results)`` との整合性 (= n_pass_windows <= len) も検証
        (caller bug 早期検知).
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
    """Stage C 評価結果 (12w + spread stress + cross-pair shadow).

    field:
    - ``c_cf_result``: 12w main 評価結果
    - ``stress_cf_result``: spread stress (1.5x) 評価結果。 ``spread_stress_supported=False``
      時は ``None`` (stress_pass=PENDING)
    - ``per_pair_results``: cross-pair shadow 5 pair の評価結果
    - ``live_criteria_pass``: c_cf_result.gate_pass のキャッシュ
    - ``stress_pass``: PASS / FAIL / PENDING
    - ``cross_pair_pass``: PASS / FAIL 二値 (PENDING なし、 概念 Round 3 [S1])
    - ``mission_pass``: truth table 適用結果
    - ``mission_fail_reason``: ``MissionFailReason`` (PASS / PENDING 時 None)
    - ``shadow_robustness_score``: per_pair_results の通過率 (Round 1 [W3])
    """

    c_cf_result: CanonicalFiveResult
    stress_cf_result: CanonicalFiveResult | None
    per_pair_results: dict[str, CanonicalFiveResult]
    live_criteria_pass: bool
    stress_pass: StagePassStatus
    cross_pair_pass: StagePassStatus
    mission_pass: StagePassStatus
    mission_fail_reason: MissionFailReason | None
    shadow_robustness_score: float | None


@dataclass(frozen=True)
class PoolFoldedInput:
    """``build_pooled_oos_input`` 出力 (Round 1 [C3] / 詳細 Round 1 [C1] 反映).

    field:
    - ``pooled_trades``: fold.test を時系列順 concat した trades
    - ``pooled_bars``: fold.test を時系列順 concat した bars
    - ``pooled_business_day_universe``: 各 fold の universe を union 集合
    - ``fold_boundaries``: 各 fold trades 終端の index (診断用)
    - ``pooled_dd_per_fold_max``: per-fold ``cf_result.max_dd`` の max
      (synthesis § 5.2 準拠、 stage B pass 判定で採用)
    """

    pooled_trades: tuple[TradeRecord, ...]
    pooled_bars: BarEquitySeries
    pooled_business_day_universe: dict[SessionBucket, frozenset[int]]
    fold_boundaries: tuple[int, ...]
    pooled_dd_per_fold_max: float


@dataclass(frozen=True)
class BCEvaluationInput:
    """1 個体の評価入力 (詳細 Round 1 [C3] で anchor_bundle 追加).

    ``anchor_bundle`` は anchor pair (``EUR_JPY``) の :class:`PairBacktestBundle`.
    ``shadow_pairs`` の各 bundle が genome_id / config_hash / partition_label で
    anchor と一致することを ``validate_against`` で検証する責務.
    """

    individual_index: int
    trades: tuple[TradeRecord, ...]
    bars: BarEquitySeries
    business_day_universe: dict[SessionBucket, frozenset[int]]
    folds: tuple[Fold, ...]
    stage_c_lite_periods: tuple[Period, Period, Period]
    stage_c_period: Period
    anchor_bundle: PairBacktestBundle
    shadow_pairs: dict[str, PairBacktestBundle]


@dataclass(frozen=True)
class BCEvaluationResult:
    """1 個体の Stage B/C-lite/C 評価結果.

    field:
    - ``individual_index``: 個体識別 (caller= T065 入力と整合)
    - ``b_result`` / ``c_lite_result`` / ``c_result``: 各 stage 評価結果
    - ``mission_pass``: 最終 mission gate (synthesis § 5.4、 c_result.mission_pass を採用)
    - ``b_pooled_cf``: GA Pareto 軸 source、 ``None`` で除外 (= invariant_fail)
    - ``pareto_axis_usable``: ``b_pooled_cf is not None`` で True
    - ``c_pass_depth``: Follow-up (T066 Phase 0)、 値域 ``[0.0, 1.75]``
      (T066 CA eviction lex key #4 で消費、 大が上位)
    """

    individual_index: int
    b_result: StageBResult
    c_lite_result: StageCLiteResult
    c_result: StageCResult
    mission_pass: StagePassStatus
    b_pooled_cf: CanonicalFiveResult | None
    pareto_axis_usable: bool
    c_pass_depth: float


# ---------------------------------------------------------------------------
# Helpers (pure functions)
# ---------------------------------------------------------------------------


def derive_stage_b_thresholds(
    live_criteria: dict,
) -> CanonicalFiveThresholds:
    """Stage B (62w) 用 thresholds を構築.

    synthesis § 5.2: Stage B 評価期間は 62w で、 24m baseline と等値想定で live_criteria を
    そのまま使用 (smoke 後再校正候補、 INCONCLUSIVE タグ).

    Args:
        live_criteria: ``sharpe_min`` / ``total_pnl_min`` / ``max_drawdown_max`` /
            ``trade_count_min`` / ``trade_count_max`` / ``win_rate_min`` を含む dict

    Returns:
        :class:`CanonicalFiveThresholds`
    """
    _validate_live_criteria_keys(live_criteria)
    return CanonicalFiveThresholds(
        sharpe_min=live_criteria["sharpe_min"],
        net_pnl_min=live_criteria["total_pnl_min"],
        max_dd_max=live_criteria["max_drawdown_max"],
        trade_count_min=live_criteria["trade_count_min"],
        trade_count_max=live_criteria["trade_count_max"],
        win_rate_min=live_criteria["win_rate_min"],
    )


def derive_stage_c_lite_thresholds(
    live_criteria: dict,
) -> CanonicalFiveThresholds:
    """Stage C-lite (6w window) 用 thresholds を構築.

    synthesis § 5.3: Stage C-lite 評価期間は 6w (= 42 days)、 24m baseline (730 days)
    との window 比例で trade_count / net_pnl を縮小. ``win_rate_min`` / ``sharpe_min`` /
    ``max_drawdown_max`` は変更しない (smoke 後再校正候補、 INCONCLUSIVE タグ).
    """
    _validate_live_criteria_keys(live_criteria)
    window_days = 42  # 6w
    baseline_days = 730  # 24m
    ratio = window_days / baseline_days
    trade_min_window = max(1, math.ceil(live_criteria["trade_count_min"] * ratio))
    trade_max_window = math.floor(live_criteria["trade_count_max"] * ratio)
    if trade_max_window < trade_min_window:
        raise StageBCInputError(
            f"derive_stage_c_lite_thresholds: derived trade_count_max_window "
            f"({trade_max_window}) < trade_count_min_window ({trade_min_window})"
        )
    return CanonicalFiveThresholds(
        sharpe_min=live_criteria["sharpe_min"],
        net_pnl_min=live_criteria["total_pnl_min"] * ratio,
        max_dd_max=live_criteria["max_drawdown_max"],
        trade_count_min=trade_min_window,
        trade_count_max=trade_max_window,
        win_rate_min=live_criteria["win_rate_min"],
    )


def derive_stage_c_thresholds(
    live_criteria: dict,
) -> CanonicalFiveThresholds:
    """Stage C (12w) 用 thresholds を構築.

    synthesis § 5.4: Stage C 評価期間は 12w (= 84 days)、 24m baseline (730 days)
    との window 比例で trade_count / net_pnl を縮小.
    """
    _validate_live_criteria_keys(live_criteria)
    window_days = 84  # 12w
    baseline_days = 730  # 24m
    ratio = window_days / baseline_days
    trade_min_window = max(1, math.ceil(live_criteria["trade_count_min"] * ratio))
    trade_max_window = math.floor(live_criteria["trade_count_max"] * ratio)
    if trade_max_window < trade_min_window:
        raise StageBCInputError(
            f"derive_stage_c_thresholds: derived trade_count_max_window "
            f"({trade_max_window}) < trade_count_min_window ({trade_min_window})"
        )
    return CanonicalFiveThresholds(
        sharpe_min=live_criteria["sharpe_min"],
        net_pnl_min=live_criteria["total_pnl_min"] * ratio,
        max_dd_max=live_criteria["max_drawdown_max"],
        trade_count_min=trade_min_window,
        trade_count_max=trade_max_window,
        win_rate_min=live_criteria["win_rate_min"],
    )


def _validate_live_criteria_keys(live_criteria: dict) -> None:
    """``live_criteria`` 必須 keys 存在を検証 (T063 同型)."""
    required_keys = {
        "sharpe_min",
        "total_pnl_min",
        "max_drawdown_max",
        "trade_count_min",
        "trade_count_max",
        "win_rate_min",
    }
    missing = required_keys - set(live_criteria.keys())
    if missing:
        raise StageBCInputError(
            f"live_criteria missing required keys: {sorted(missing)}"
        )


def filter_to_period(
    trades: tuple[TradeRecord, ...],
    bars: BarEquitySeries,
    universe: dict[SessionBucket, frozenset[int]],
    period: Period,
) -> tuple[
    tuple[TradeRecord, ...],
    BarEquitySeries,
    dict[SessionBucket, frozenset[int]],
]:
    """T060 :class:`Period` ``[start, end)`` に含まれる trades / bars / universe をフィルタ.

    半開区間 ``[start, end)`` (T060 / T072 規範):
    - trade: ``period.start <= trade.exit_time_utc < period.end``
    - bar: ``period.start <= bar.timestamp_utc < period.end``
    - universe: そのまま継承 (caller=T070 が period 単位で生成済前提、 ただし
      filter_to_period 内では universe を変えない、 bars / trades 期間外要素のみ除く)

    Note: bars 結果は :class:`BarEquitySeries` ``__post_init__`` で
    ``len(points) >= 1`` 検証されるため、 期間内 bars が空の場合は caller 側で対処
    (= 該当 fold は INPUT_INVALID_BAR_SERIES reason に変換される、 T061 上流契約).

    Returns:
        ``(filtered_trades, filtered_bars, universe)`` (universe は無変更で pass-through).

    Raises:
        StageBCInputError: 期間内 bars が空 (= BarEquitySeries 構築不可).
    """
    filtered_trades = tuple(
        t
        for t in trades
        if period.start <= t.exit_time_utc < period.end
    )
    filtered_bar_points = tuple(
        p
        for p in bars.points
        if period.start <= p.timestamp_utc < period.end
    )
    if len(filtered_bar_points) == 0:
        raise StageBCInputError(
            f"filter_to_period({period.label!r}): no bars in period "
            f"[{period.start}, {period.end})"
        )
    filtered_bars = BarEquitySeries(points=filtered_bar_points)
    return filtered_trades, filtered_bars, universe


def evaluate_stage_b(
    individual_input: BCEvaluationInput,
    *,
    evaluate_fn: Callable[..., CanonicalFiveResult],
    live_criteria: dict,
) -> StageBResult:
    """5 fold rolling-origin pooled OOS canonical 5 worst aggregation.

    手順 (synthesis § 5.2):
    1. 各 fold で trades / bars をフィルタ + ``evaluate_fn`` 呼出 → :class:`StageBFoldResult`
    2. 1 fold でも ``is_feasible=False`` → ``is_feasible_invariant=False``
    3. ``is_feasible_invariant=False`` → ``b_pooled_cf_result=None`` で early return
       (Round 1 [C2])
    4. ``is_feasible_invariant=True`` → :func:`build_pooled_oos_input` → 1 回
       ``evaluate_fn`` 呼出
    5. ``is_b_pass = gate_pass_ex_dd ∧ dd_pass`` (詳細 Round 1 [C1] / [C2] /
       Round 2 [Critical]、 concat DD 経路完全遮断)

    Args:
        individual_input: 1 個体の評価入力 (anchor pair の trades / bars + folds)
        evaluate_fn: T061 評価関数 (production: ``evaluate_canonical_five``)
        live_criteria: config から渡される live_criteria dict

    Returns:
        :class:`StageBResult`
    """
    thresholds = derive_stage_b_thresholds(live_criteria)
    per_fold_results: list[StageBFoldResult] = []
    for fold in individual_input.folds:
        fold_trades, fold_bars, fold_universe = filter_to_period(
            individual_input.trades,
            individual_input.bars,
            individual_input.business_day_universe,
            fold.test,
        )
        cf_result = evaluate_fn(
            fold_trades,
            fold_bars,
            thresholds,
            fold_universe,
        )
        per_fold_results.append(
            StageBFoldResult(
                fold_index=fold.fold_index,
                fold_period_start=fold.test.start,
                fold_period_end=fold.test.end,
                cf_result=cf_result,
                is_feasible_invariant=cf_result.invariants.is_feasible,
            )
        )

    is_feasible_invariant = all(
        f.is_feasible_invariant for f in per_fold_results
    )
    if not is_feasible_invariant:
        return StageBResult(
            b_pooled_cf_result=None,
            pooled_dd_per_fold_max=None,
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
    pooled_dd_per_fold_max = pooled.pooled_dd_per_fold_max
    dd_pass = pooled_dd_per_fold_max <= thresholds.max_dd_max
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
    1. fold.test 非重複・時系列順 invariant 検証 (StageBCInputError raise)
    2. trades: 各 fold.test の trades を時系列順 concat (重複なし)
    3. bars: 各 fold.test の bars を時系列順 concat (通常 concat、 fold 境界 metadata で記録)
    4. **pooled_DD = max over folds of fold.max_dd** (synthesis § 5.2 / 詳細 Round 3 [S3]):
       per-fold cf_result.max_dd の max を独立計算、 b_pooled_cf_result.max_dd は概念上
       通常 concat の bars で T061 が計算 (擬似 DD 含む) → archive admission は
       pooled_dd_per_fold_max を消費する責務.
    5. business_day_universe: 各 fold の universe を union 集合に
    6. fold_boundaries: tuple[int, ...] (trades index 境界、 診断用)

    invariant 検証 (StageBCInputError raise):
    - ``len(fold_results) == STAGE_B_NUM_FOLDS (=5)``
    - ``fold_results[i].fold_index == i``
    - ``fold_results[i].fold_period_start <= fold_results[i+1].fold_period_start``
      (時系列順)
    - ``fold_results[i].fold_period_end <= fold_results[i+1].fold_period_start``
      (非重複)

    Args:
        fold_results: 5 fold の :class:`StageBFoldResult` リスト
        individual_input: 1 個体の評価入力 (anchor pair の trades / bars / universe を持つ)

    Returns:
        :class:`PoolFoldedInput` with ``pooled_dd_per_fold_max``.

    Raises:
        StageBCInputError: invariant 違反 (fold 数 / 順序 / 重複).
    """
    if len(fold_results) != STAGE_B_NUM_FOLDS:
        raise StageBCInputError(
            f"build_pooled_oos_input expects {STAGE_B_NUM_FOLDS} folds, "
            f"got {len(fold_results)}"
        )
    for i, f in enumerate(fold_results):
        if f.fold_index != i:
            raise StageBCInputError(
                f"build_pooled_oos_input: fold_results[{i}].fold_index "
                f"({f.fold_index}) != {i}"
            )
    for i in range(len(fold_results) - 1):
        cur = fold_results[i]
        nxt = fold_results[i + 1]
        if cur.fold_period_start > nxt.fold_period_start:
            raise StageBCInputError(
                f"build_pooled_oos_input: non-chronological fold order "
                f"at index {i}: {cur.fold_period_start} > {nxt.fold_period_start}"
            )
        if cur.fold_period_end > nxt.fold_period_start:
            raise StageBCInputError(
                f"build_pooled_oos_input: overlapping fold.test periods "
                f"at index {i}: end {cur.fold_period_end} > "
                f"next start {nxt.fold_period_start}"
            )

    # trades + bars + universe を fold 単位で集約
    pooled_trades_list: list[TradeRecord] = []
    pooled_bar_points_list: list[BarEquityPoint] = []
    fold_boundaries_list: list[int] = []
    union_universe: dict[SessionBucket, set[int]] = {}
    for f in fold_results:
        # Reconstruct fold.test Period from fold result for filter_to_period.
        # We need a Period instance; build a temporary one matching contract.
        # fold_period_start / end are already validated UTC by Fold.test.
        fold_test_period = Period(
            start=f.fold_period_start,
            end=f.fold_period_end,
            label=f"fold_{f.fold_index}_fold_test",
        )
        fold_trades, fold_bars, fold_universe = filter_to_period(
            individual_input.trades,
            individual_input.bars,
            individual_input.business_day_universe,
            fold_test_period,
        )
        pooled_trades_list.extend(fold_trades)
        pooled_bar_points_list.extend(fold_bars.points)
        fold_boundaries_list.append(len(pooled_trades_list))
        for bucket, day_set in fold_universe.items():
            if bucket not in union_universe:
                union_universe[bucket] = set()
            union_universe[bucket].update(day_set)

    if len(pooled_bar_points_list) == 0:
        raise StageBCInputError(
            "build_pooled_oos_input: pooled bars empty across all folds"
        )

    pooled_bars = BarEquitySeries(points=tuple(pooled_bar_points_list))
    pooled_universe: dict[SessionBucket, frozenset[int]] = {
        bucket: frozenset(day_set) for bucket, day_set in union_universe.items()
    }
    pooled_dd_per_fold_max = max(f.fold_max_dd for f in fold_results)
    return PoolFoldedInput(
        pooled_trades=tuple(pooled_trades_list),
        pooled_bars=pooled_bars,
        pooled_business_day_universe=pooled_universe,
        fold_boundaries=tuple(fold_boundaries_list),
        pooled_dd_per_fold_max=pooled_dd_per_fold_max,
    )


def evaluate_stage_c_lite(
    individual_input: BCEvaluationInput,
    *,
    evaluate_fn: Callable[..., CanonicalFiveResult],
    live_criteria: dict,
) -> StageCLiteResult:
    """3 disjoint windows × canonical 5 worst → 15 セル worst 評価.

    Round 1 [W2] / [W5] / Round 2 [W4] 反映:
    - 15 セル worst = max over 3 windows of gate_worst_gap
    - sample_size_flag (OK/BOUNDARY/INSUFFICIENT) 判定
    - INSUFFICIENT 時は mission_pass / progress_pass を PENDING 強制

    Follow-up (T066 Phase 0):
    ``n_pass_windows = sum(1 for w in per_window_results if w.cf_result.gate_pass)``
    で deterministic 計算、 値域 ``[0, 3]``.

    Args:
        individual_input: 1 個体の評価入力 (anchor pair)
        evaluate_fn: T061 評価関数
        live_criteria: config から渡される live_criteria dict

    Returns:
        :class:`StageCLiteResult` (n_pass_windows 同梱).
    """
    if len(individual_input.stage_c_lite_periods) != STAGE_C_LITE_NUM_WINDOWS:
        raise StageBCInputError(
            f"evaluate_stage_c_lite expects {STAGE_C_LITE_NUM_WINDOWS} windows, "
            f"got {len(individual_input.stage_c_lite_periods)}"
        )
    thresholds = derive_stage_c_lite_thresholds(live_criteria)
    per_window_results: list[StageCLiteWindowResult] = []
    min_blocks_per_bucket: float = math.inf
    for i, window in enumerate(individual_input.stage_c_lite_periods):
        window_trades, window_bars, window_universe = filter_to_period(
            individual_input.trades,
            individual_input.bars,
            individual_input.business_day_universe,
            window,
        )
        cf_result = evaluate_fn(
            window_trades,
            window_bars,
            thresholds,
            window_universe,
        )
        per_window_results.append(
            StageCLiteWindowResult(window_index=i, cf_result=cf_result)
        )
        for blocks in window_universe.values():
            min_blocks_per_bucket = min(min_blocks_per_bucket, len(blocks))

    cells_worst = max(w.cf_result.gate_worst_gap for w in per_window_results)

    if min_blocks_per_bucket >= STAGE_C_LITE_SAMPLE_SIZE_OK_MIN_BLOCKS:
        flag = SampleSizeFlag.OK
    elif min_blocks_per_bucket >= STAGE_C_LITE_SAMPLE_SIZE_BOUNDARY_MIN_BLOCKS:
        flag = SampleSizeFlag.BOUNDARY
    else:
        flag = SampleSizeFlag.INSUFFICIENT

    n_pass_windows = sum(
        1 for w in per_window_results if w.cf_result.gate_pass
    )

    if flag == SampleSizeFlag.INSUFFICIENT:
        mission_pass = StagePassStatus.PENDING
        progress_pass = StagePassStatus.PENDING
    else:
        mission_pass = (
            StagePassStatus.PASS
            if n_pass_windows == STAGE_C_LITE_NUM_WINDOWS
            else StagePassStatus.FAIL
        )
        progress_pass = (
            StagePassStatus.PASS
            if n_pass_windows >= STAGE_C_LITE_PROGRESS_PASS_MIN_WINDOWS
            else StagePassStatus.FAIL
        )

    return StageCLiteResult(
        per_window_results=tuple(per_window_results),
        cells_worst=cells_worst,
        mission_pass=mission_pass,
        progress_pass=progress_pass,
        sample_size_flag=flag,
        n_pass_windows=n_pass_windows,
    )


def evaluate_stage_c(
    individual_input: BCEvaluationInput,
    *,
    evaluate_fn: Callable[..., CanonicalFiveResult],
    live_criteria: dict,
    spread_stress_supported: bool = False,
) -> StageCResult:
    """12w + spread stress + cross-pair shadow validation (synthesis § 5.4).

    Round 2 [Critical] 1 / 概念 Round 3 [S1] / [S2] 反映:
    - mission_pass: 完全 truth table (FAIL 優先順位 LIVE_CRITERIA > CROSS_PAIR > STRESS)
    - cross_pair_pass は PASS / FAIL 二値 (PENDING なし、 詳細 Round 1 [C4] で raise)
    - mission_fail_reason 保持

    Args:
        individual_input: 1 個体の評価入力 (anchor + shadow_pairs)
        evaluate_fn: T061 評価関数
        live_criteria: config から渡される live_criteria dict
        spread_stress_supported: True で spread stress 評価 (Phase 1 では False で
            stress_pass=PENDING、 Phase 2 で True に)

    Returns:
        :class:`StageCResult`

    Raises:
        StageBCInputError: anchor_bundle.pair が STAGE_C_ANCHOR_PAIR と不一致 /
            shadow_pairs に必須 pair 欠損 / bundle.pair が要求 pair と不一致 /
            cross_pair_pass が PASS/FAIL 二値以外.
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
        individual_input.trades,
        individual_input.bars,
        individual_input.business_day_universe,
        individual_input.stage_c_period,
    )
    c_cf_result = evaluate_fn(c_trades, c_bars, thresholds, c_universe)
    live_criteria_pass = c_cf_result.gate_pass

    # spread stress (Round 1 [C1])
    stress_cf_result: CanonicalFiveResult | None
    if spread_stress_supported:
        stressed_trades = apply_spread_stress(
            c_trades, STAGE_C_SPREAD_STRESS_MULTIPLIER
        )
        stress_cf = evaluate_fn(
            stressed_trades, c_bars, thresholds, c_universe
        )
        stress_cf_result = stress_cf
        stress_pass = (
            StagePassStatus.PASS
            if stress_cf.gate_pass
            else StagePassStatus.FAIL
        )
    else:
        stress_cf_result = None
        stress_pass = StagePassStatus.PENDING

    # cross-pair shadow (Round 1 [C4] / [W4] / 詳細 Round 1 [C3])
    per_pair_results: dict[str, CanonicalFiveResult] = {}
    for pair in STAGE_C_SHADOW_PAIR_LIST:
        if pair not in individual_input.shadow_pairs:
            raise StageBCInputError(
                f"shadow_pairs missing required pair: {pair}"
            )
        bundle = individual_input.shadow_pairs[pair]
        if bundle.pair != pair:
            raise StageBCInputError(
                f"PairBacktestBundle.pair ({bundle.pair}) "
                f"!= requested pair ({pair})"
            )
        bundle.validate_against(individual_input.anchor_bundle)
        per_pair_results[pair] = evaluate_fn(
            bundle.trades,
            bundle.bars,
            thresholds,
            bundle.business_day_universe,
        )

    n_pair_pass = sum(
        1 for cf in per_pair_results.values() if cf.gate_pass
    )
    cross_pair_pass = (
        StagePassStatus.PASS
        if n_pair_pass >= STAGE_C_SHADOW_REQUIRED_COUNT
        else StagePassStatus.FAIL
    )
    # 詳細 Round 1 [C4] / 概念 Round 3 [S1] 反映: assert→raise 置換 (-O 対策).
    # PENDING になり得ない契約を runtime で固定.
    if cross_pair_pass not in (StagePassStatus.PASS, StagePassStatus.FAIL):
        raise StageBCInputError(
            f"cross_pair_pass must be PASS or FAIL "
            f"(binary contract): {cross_pair_pass}"
        )

    shadow_robustness_score = compute_cross_pair_shadow_score(per_pair_results)

    # mission_pass: 完全 truth table (Round 2 [Critical] 1 / 概念 Round 3 [S2])
    mission_fail_reason: MissionFailReason | None
    if not live_criteria_pass:
        mission_pass = StagePassStatus.FAIL
        mission_fail_reason = MissionFailReason.LIVE_CRITERIA
    elif cross_pair_pass == StagePassStatus.FAIL:
        mission_pass = StagePassStatus.FAIL
        mission_fail_reason = MissionFailReason.CROSS_PAIR
    elif stress_pass == StagePassStatus.FAIL:
        mission_pass = StagePassStatus.FAIL
        mission_fail_reason = MissionFailReason.STRESS
    elif (
        live_criteria_pass
        and cross_pair_pass == StagePassStatus.PASS
        and stress_pass == StagePassStatus.PASS
    ):
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
    """spread stress を trades に適用 (T078 で skeleton から正式実装に置換).

    T070 で TradeRecord に ``spread_cost`` field 追加 + T078 で本関数の
    NotImplementedError raise を正式実装に置換. concept 改訂 1 / 詳細設計 § 4.2
    option 2 (= TradeRecord に直接適用するロジック展開、 broker 経路の
    ``src/backtest/session_block.apply_spread_stress`` とは型が異なるため統合せず
    用途分離).

    Stress 適用式 (= 元 broker は spread を pnl に控除済前提、 stress 倍率の
    余計分のみを pnl_net から控除する):

        delta_factor = multiplier - 1.0
        new_pnl_net = pnl_net - spread_cost * delta_factor
        new_spread_cost = spread_cost * multiplier

    本式は broker 経路の ``session_block.apply_spread_stress`` (Decimal 型) と
    **代数的に等価** (= 同じ入力で同じ出力、 ただし type 差で丸め誤差は発生し得る、
    test 経路で ulp 誤差検証).

    **Caller 配線注意 (Round 1 [Warning] 1 反映)**:
        spread_cost が全 trade で 0.0 (= default、 trade 生成経路で伝搬未配線)
        の状態では multiplier > 1.0 でも stress 効果ゼロ (silent no-op).
        caller (= run_ga.py / Stage C 評価) 側で trade 生成経路の spread_cost
        伝搬を確立する責任あり (= 後続別 TODO で配線、 T078 のスコープ外).

    Args:
        trades: original trades (TradeRecord tuple).
        multiplier: spread cost multiplier (= 1.0 で no-op, 1.5 で 50% 増加).

    Returns:
        stress 適用後の TradeRecord tuple (= 入力と同じ長さ、 同じ順序).

    Raises:
        ValueError: multiplier < 1.0 OR finite でない.
        TradeRecordInvalidError: 結果の new_pnl_net / new_spread_cost が
            non-finite (= overflow) または new_spread_cost < 0 (= 数値誤差で発生).
    """
    if not math.isfinite(multiplier):
        raise ValueError(
            f"apply_spread_stress: multiplier must be finite, got {multiplier}"
        )
    if multiplier < 1.0:
        raise ValueError(
            f"apply_spread_stress: multiplier must be >= 1.0, got {multiplier}"
        )

    delta_factor = multiplier - 1.0
    return tuple(
        replace(
            t,
            pnl_net=t.pnl_net - t.spread_cost * delta_factor,
            spread_cost=t.spread_cost * multiplier,
        )
        for t in trades
    )


def compute_cross_pair_shadow_score(
    per_pair_results: dict[str, CanonicalFiveResult],
) -> float | None:
    """shadow 5 pair の通過強度 (Round 1 [W3] / [C4]).

    Phase 1 仕様 (smoke 後再校正候補):
    - 全 pair が ``gate_pass=True`` なら 1.0 (完全 robust)
    - 1 pair でも fail なら通過率 (= n_pass / total_n)
    - per_pair_results が空なら ``None``

    Args:
        per_pair_results: ``{pair: CanonicalFiveResult}``

    Returns:
        ``[0.0, 1.0]`` の float または ``None`` (空集合).
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

    定義: ``1 / (1 + max(0, gate_worst_gap))``
    値域: ``(0, 1]``、 全達成で 1.0、 worst_gap 大で 0 に近づく.

    Round 2 [W2] domain ガード: ``gate_worst_gap`` が負値でも defensive clip で
    0 floor を適用し、 1.0 を超える値が出ない.
    """
    safe_gap = max(0.0, cf_result.gate_worst_gap)
    return 1.0 / (1.0 + safe_gap)


def compute_a_b_correlation(
    a_proxy_scores: dict[int, float],
    b_pooled_scores: dict[int, float],
) -> tuple[float, int]:
    """corr(A_proxy, B_pooled) を Run 終了時に計算 (synthesis § 8.7).

    両 score とも higher-is-better で正規化済前提.
    invariant: 共通 index でのみ corr 計算 (片方欠損は除外).
    sample_size = ``len(共通 index 集合)``.

    詳細 Round 1 [C5] 反映: 定数系列 / NaN / Inf で StatisticsError catch、
    deterministic に ``(0.0, sample_size)`` 戻り値固定. caller (T071) が
    runtime 停止しない契約.

    Args:
        a_proxy_scores: ``{individual_index: float}`` (Stage A proxy score)
        b_pooled_scores: ``{individual_index: float}`` (Stage B pooled OOS score)

    Returns:
        ``(pearson_corr, sample_size)``. sample_size < 2 で ``(0.0, n)``.
    """
    common_indices = set(a_proxy_scores.keys()) & set(b_pooled_scores.keys())
    if len(common_indices) < 2:
        return 0.0, len(common_indices)
    sorted_indices = sorted(common_indices)
    a_values = [a_proxy_scores[i] for i in sorted_indices]
    b_values = [b_pooled_scores[i] for i in sorted_indices]
    try:
        corr = statistics.correlation(a_values, b_values)
    except statistics.StatisticsError:
        return 0.0, len(common_indices)
    if not math.isfinite(corr):
        return 0.0, len(common_indices)
    return corr, len(common_indices)


def compute_gate_pass_excluding_dd(
    cf_result: CanonicalFiveResult,
    thresholds: CanonicalFiveThresholds,
) -> bool:
    """max_dd 軸を除いた gate_pass を計算 (Round 2 [Critical] 反映).

    ``is_b_pass = gate_pass_ex_dd ∧ dd_pass`` の数式:
        ``gate_pass_ex_dd = max(max(0, -slack_m) for m in [sharpe, pnl, tc, wr])
        <= GATE_PASS_TOLERANCE AND cf_result.invariants.is_feasible``

    DD 軸は per-fold DD max で別途判定するため、 ``b_pooled_cf.max_dd``
    (concat 擬似 DD 含む) は使わない.

    Args:
        cf_result: T061 :class:`CanonicalFiveResult`
        thresholds: caller 互換性のため保持 (本実装では未使用、 caller signature 維持)

    Returns:
        ``True`` if max_dd 軸を除いた 4 軸 + invariant が全て pass.
    """
    del thresholds  # caller signature 互換用 (将来 threshold-aware で消費可能)
    if not cf_result.invariants.is_feasible:
        return False
    slacks = (
        cf_result.slack_sharpe,
        cf_result.slack_pnl,
        cf_result.slack_tc,
        cf_result.slack_wr,
    )
    # 非有限値 (-inf) は無限大 gap、 +inf は 0 gap で扱う (T061 と同等)
    worst_ex_dd = 0.0
    for v in slacks:
        if math.isfinite(v):
            gap = max(0.0, -v)
        elif v == float("-inf"):
            gap = math.inf
        else:
            gap = 0.0
        if gap > worst_ex_dd:
            worst_ex_dd = gap
    return math.isfinite(worst_ex_dd) and worst_ex_dd <= GATE_PASS_TOLERANCE


def select_top_clite_forced_pass_indices(
    per_individual_clite_results: dict[int, StageCLiteResult],
    ratio: float = STAGE_C_LITE_FORCED_PASS_RATIO,
) -> frozenset[int]:
    """世代内 top 30% 強制通過 (synthesis § 5.3).

    Round 1 [W1] / Round 2 [W3] 反映: deterministic ranking key:
    1. mission_pass desc (PASS > PENDING > FAIL)
    2. progress_pass desc (PASS > PENDING > FAIL)
    3. invariant_ok desc (per_window 全 invariant OK > NG)
    4. cells_worst asc (小さい = 良い)
    5. individual_id asc (deterministic tie-break)

    forced 数 = ``max(1, ceil(n_eligible * ratio))``、 ただし
    ``n_eligible = mission_pass != FAIL`` の個体数 (FAIL 個体は除外).

    Round 2 [W3] / [W4] 反映: invariant_fail (= sample_size INSUFFICIENT) 個体は
    PENDING 扱いだが forced 通過候補から除外 (= eligible に含めない).

    Args:
        per_individual_clite_results: ``{individual_index: StageCLiteResult}``
        ratio: 強制通過率 (default ``STAGE_C_LITE_FORCED_PASS_RATIO``=0.30)

    Returns:
        forced_pass_indices: ``frozenset[int]``

    Raises:
        StageBCInputError: ``ratio`` が ``[0.0, 1.0]`` 外.
    """
    if not math.isfinite(ratio):
        raise StageBCInputError(f"ratio must be finite: {ratio}")
    if not (0.0 <= ratio <= 1.0):
        raise StageBCInputError(f"ratio must be in [0, 1]: {ratio}")

    # eligible = mission_pass != FAIL かつ sample_size != INSUFFICIENT
    eligible: list[tuple[int, StageCLiteResult]] = [
        (idx, r)
        for idx, r in per_individual_clite_results.items()
        if r.mission_pass != StagePassStatus.FAIL
        and r.sample_size_flag != SampleSizeFlag.INSUFFICIENT
    ]
    if not eligible:
        return frozenset()
    n_eligible = len(eligible)
    forced_n = max(1, math.ceil(n_eligible * ratio))

    def _status_rank(s: StagePassStatus) -> int:
        # Round 1 [W1] 規範継承: 3 値全てを明示分岐、 未知値は ValueError raise
        # (将来 enum 拡張時 silent FAIL 相当扱いを早期検知).
        if s == StagePassStatus.PASS:
            return 0
        if s == StagePassStatus.PENDING:
            return 1
        if s == StagePassStatus.FAIL:
            return 2
        raise ValueError(
            f"unknown StagePassStatus: {s!r} (expected PASS / PENDING / FAIL)"
        )

    def _invariant_ok_rank(r: StageCLiteResult) -> int:
        # 全 window invariant OK で 0、 NG ありで 1
        all_ok = all(
            w.cf_result.invariants.is_feasible
            for w in r.per_window_results
        )
        return 0 if all_ok else 1

    sorted_eligible = sorted(
        eligible,
        key=lambda item: (
            _status_rank(item[1].mission_pass),
            _status_rank(item[1].progress_pass),
            _invariant_ok_rank(item[1]),
            item[1].cells_worst,
            item[0],
        ),
    )
    return frozenset(idx for idx, _ in sorted_eligible[:forced_n])


def compute_c_pass_depth(
    c_lite_result: StageCLiteResult,
    c_result: StageCResult,
) -> float:
    """Follow-up (T066 Phase 0) 反映: c_pass_depth 計算 SSOT.

    計算式 (T066 概念 R4 確定):
        ``c_pass_depth = c_lite_result.n_pass_windows × 0.25
                       + bonus(c_result.mission_pass)``
        ``bonus(PASS) = 1.0 / bonus(PENDING) = 0.5 / bonus(FAIL) = 0.0``

    値域: ``[0.0, 1.75]``
        - n_pass_windows: 0..3 (× 0.25 = ``[0.0, 0.75]``)
        - mission_pass status: PASS=1.0 / PENDING=0.5 / FAIL=0.0
        - 合計: ``[0.0, 0.75] + [0.0, 1.0] = [0.0, 1.75]``

    用途 (T066 CA eviction lex key #4): 大が上位.
    Stage C-lite を多く通過 ∧ Stage C で mission_pass に近い個体ほど archive 残留優先.

    Determinism: pure function、 入力同値で出力同値. 浮動小数点誤差なし
    (整数 × 0.25 + 整数定数 のみで構成、 IEEE 754 で exact).

    Round 1 [W1] 反映: StagePassStatus 3 値全てを明示分岐、 未知値は ``ValueError``
    raise (将来 enum 拡張時の silent FAIL 同等扱いを早期検知).

    Round 1 [W2] 反映: ``c_lite_result.n_pass_windows`` 値域 guard を本関数入口でも
    実施 (mock dataclass で ``__post_init__`` を bypass した bypass パス test 用).

    Collider bias 独立性 (T072 規範継承): 本関数は ``c_lite_result.n_pass_windows`` と
    ``c_result.mission_pass`` のみに依存し、 holiday_markets / dst_transition_markets /
    observability_flags 系には触れない. stratified audit は本 module で扱わない.

    Args:
        c_lite_result: :class:`StageCLiteResult`
        c_result: :class:`StageCResult`

    Returns:
        ``[0.0, 1.75]`` の float.

    Raises:
        ValueError: ``n_pass_windows`` が値域外 / ``mission_pass`` が未知 enum 値.
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
    1. ``b_result = evaluate_stage_b(input, evaluate_fn, live_criteria)``
    2. ``c_lite_result = evaluate_stage_c_lite(input, evaluate_fn, live_criteria)``
       (``StageCLiteResult.n_pass_windows`` を deterministic に同時計算、 値域 ``[0, 3]``)
    3. ``c_result = evaluate_stage_c(input, evaluate_fn, live_criteria,
       spread_stress_supported)``
    4. ``mission_pass = c_result.mission_pass`` を採用 (synthesis § 5.4 で
       Stage C が最終 mission gate)
    5. ``b_pooled_cf = b_result.b_pooled_cf_result`` (None possible)
    6. ``pareto_axis_usable = b_pooled_cf is not None``
    7. ``c_pass_depth = compute_c_pass_depth(c_lite_result, c_result)``
       (Follow-up Phase 0、 T066 CA eviction lex key #4 で消費)
    8. :class:`BCEvaluationResult` を返す (c_pass_depth field 同梱)

    Args:
        a_pass_inputs: ``{individual_index: BCEvaluationInput}`` (Stage A 通過個体のみ)
        evaluate_fn: T061 評価関数 (production: ``evaluate_canonical_five``)
        live_criteria: config から渡される live_criteria dict
        spread_stress_supported: True で spread stress 評価 (Phase 1 では False)

    Returns:
        ``{individual_index: BCEvaluationResult}``
    """
    results: dict[int, BCEvaluationResult] = {}
    for idx, individual_input in a_pass_inputs.items():
        b_result = evaluate_stage_b(
            individual_input,
            evaluate_fn=evaluate_fn,
            live_criteria=live_criteria,
        )
        c_lite_result = evaluate_stage_c_lite(
            individual_input,
            evaluate_fn=evaluate_fn,
            live_criteria=live_criteria,
        )
        c_result = evaluate_stage_c(
            individual_input,
            evaluate_fn=evaluate_fn,
            live_criteria=live_criteria,
            spread_stress_supported=spread_stress_supported,
        )
        b_pooled_cf = b_result.b_pooled_cf_result
        pareto_axis_usable = b_pooled_cf is not None
        c_pass_depth = compute_c_pass_depth(c_lite_result, c_result)
        results[idx] = BCEvaluationResult(
            individual_index=idx,
            b_result=b_result,
            c_lite_result=c_lite_result,
            c_result=c_result,
            mission_pass=c_result.mission_pass,
            b_pooled_cf=b_pooled_cf,
            pareto_axis_usable=pareto_axis_usable,
            c_pass_depth=c_pass_depth,
        )
    return results
