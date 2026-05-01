"""T063: Stage A evaluator — synthesis § 5.1 / § 5.5 / § 8.7 確定式の実装.

詳細:
- 概念設計: devnotes/20260430-0130-todo-T063-stage-a-evaluator/conceptual-design.md
- synthesis § 5.1 (Stage A: hard gate + q_force) / § 5.5 (stage 別評価値の不混在) / § 8.7 (A→B 乖離監視)
- T061 依存: CanonicalFiveResult / CanonicalFiveThresholds / evaluate_canonical_five を消費

Phase 1 (本 TODO): 単体実装 + テストのみ、 stage_gate.py / swim_lane.py / run_ga.py 未変更。
Phase 2 (別 PR): T065 統合と同時、 8 箇所同時更新 (Phase 2 申し送り参照)。

責務:
- Stage A 用 thresholds 派生 (Decision 1, 2, 4): 8w window 比例で trade_count / net_pnl
- T061 evaluate_canonical_five 呼出 (dependency injection、 test 時 mock 可)
- 世代内 hard floor + ranking + top q_force% 選抜
- q_force 動的計算 (synthesis § 5.1 確定式) + A→B 乖離自動引き上げ (synthesis § 8.7)
- state immutability: pure function 化、 controller class 廃止

根拠 / 先行実装 (詳細 Round 1 [W4] 反映):
- synthesis § 5.1 / § 5.5 / § 8.7 / § 19 #4
- zenigame ``ga/nsga2/stage_a_gate.py`` (StageAGateController): 世代内 ranking 選択の元実装
- T061 詳細設計 APPROVED: canonical 5 worst gate_score の上位 contract
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from src.alpha_factory.canonical_metrics import (
    BarEquitySeries,
    CanonicalFiveResult,
    CanonicalFiveThresholds,
    SessionBucket,
    SessionBucketBoundaryProvider,
    TradeRecord,
)

__all__ = [
    "BASELINE_DATASET_DAYS",
    "CORR_SAMPLE_SIZE_INCONCLUSIVE_MIN",
    "CORR_SAMPLE_SIZE_RELIABLE_MIN",
    "DIVERGENCE_OFFSET_STEPS_MAX",
    "HARD_FLOOR_MIN_TRADES",
    "Q_FORCE_BASE",
    "Q_FORCE_BASE_MAX",
    "Q_FORCE_BASE_MIN",
    "Q_FORCE_DIVERGENCE_MAX",
    "Q_FORCE_DIVERGENCE_RECOVERY_CORRELATION",
    "Q_FORCE_DIVERGENCE_STEP",
    "Q_FORCE_FEASIBLE_RATIO_THRESHOLD",
    "Q_FORCE_RANGE",
    "STAGE_A_WINDOW_DAYS",
    "StageAControllerState",
    "StageAEvaluatorError",
    "StageAGateStats",
    "StageAGenerationInput",
    "StageAIndividualInput",
    "StageAInputError",
    "StageAResult",
    "compute_gate_score",
    "compute_q_force_base",
    "compute_q_force_with_divergence",
    "derive_stage_a_thresholds",
    "evaluate_generation",
    "is_hard_pass",
    "select_top_q_force_indices",
    "update_divergence_state",
]


# ---------------------------------------------------------------------------
# Constants (synthesis § 5.1 / § 8.7 厳密準拠 + Decision 1-4)
# ---------------------------------------------------------------------------

STAGE_A_WINDOW_DAYS: Final[int] = 56
"""Stage A 評価期間 = 8w 固定 (synthesis § 5.1 / T060 stage_a Period の length)."""

BASELINE_DATASET_DAYS: Final[int] = 730
"""24m baseline (synthesis § 4.1 dataset.start/end の想定スコープ).

Decision 1 / 2 の trade_count / net_pnl 比例計算で denominator として使用."""

# q_force 動的計算 (synthesis § 5.1)
Q_FORCE_BASE: Final[float] = 0.15
Q_FORCE_RANGE: Final[float] = 0.15
Q_FORCE_FEASIBLE_RATIO_THRESHOLD: Final[float] = 0.10
Q_FORCE_BASE_MIN: Final[float] = 0.15
Q_FORCE_BASE_MAX: Final[float] = 0.30

# A→B 乖離自動引き上げ (synthesis § 8.7)
Q_FORCE_DIVERGENCE_MAX: Final[float] = 0.40
Q_FORCE_DIVERGENCE_STEP: Final[float] = 0.02
Q_FORCE_DIVERGENCE_RECOVERY_CORRELATION: Final[float] = 0.5

DIVERGENCE_OFFSET_STEPS_MAX: Final[int] = math.ceil(
    (Q_FORCE_DIVERGENCE_MAX - Q_FORCE_BASE_MIN) / Q_FORCE_DIVERGENCE_STEP
)
"""定数から導出 (Round 2 [W1] 反映): ceil((0.40 - 0.15) / 0.02) = 13.

上限ガード: q_force_with_divergence の clamp により実効上限は 0.40 で保護.
Note (Round 3 [W1] 反映): cap 飽和中は見かけ上 0.02/Run で下がらない期間あり (回復時に
base_q_force が高い場合、 cap に張り付くため). 仕様許容、 監視 log で可視化."""

# hard floor (synthesis § 5.1)
HARD_FLOOR_MIN_TRADES: Final[int] = 2

# C7 sample-size guard (詳細 Round 1 [C2] 反映)
CORR_SAMPLE_SIZE_INCONCLUSIVE_MIN: Final[int] = 10
"""C7 適用 (詳細 Round 1 [C2] 反映): corr 計算の最低 sample 数.

n < 10 は ValueError raise (運用 bug indicator)、 n=10..29 は INCONCLUSIVE (state 不変)、
n >= 30 で通常更新."""

CORR_SAMPLE_SIZE_RELIABLE_MIN: Final[int] = 30
"""C7 適用: 通常更新の最低 sample 数 (synthesis § 16 / AGENTS.md C7 conformity)."""


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class StageAEvaluatorError(Exception):
    """Stage A evaluator 基底例外."""


class StageAInputError(StageAEvaluatorError):
    """入力契約違反 (live_criteria 不正、 individuals 不正、 etc.)."""


# ---------------------------------------------------------------------------
# DataClasses (frozen、 immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageAControllerState:
    """Stage A controller state — Run 跨ぎ persistence (immutable).

    field:
    - divergence_offset_steps: A→B 乖離 cycle counter (unsigned >= 0、
      clamp [0, DIVERGENCE_OFFSET_STEPS_MAX])
        - 0: 正常 (q_force = base のみ)
        - > 0: 乖離中 or 回復中の current step 数
    - last_a_b_correlation: 直近 Run の corr(A_proxy_score, B_pooled_score)
        - None for initial state

    Run 跨ぎ persistence は T067 (Loop closure) で archive metadata or run cache に保存する責務
    (Phase 2 申し送り)。 T063 PR 自体は in-memory のみ.
    """

    divergence_offset_steps: int
    last_a_b_correlation: float | None

    def __post_init__(self) -> None:
        if self.divergence_offset_steps < 0:
            raise StageAInputError(
                f"divergence_offset_steps must be >= 0 (unsigned): "
                f"{self.divergence_offset_steps}"
            )
        if self.divergence_offset_steps > DIVERGENCE_OFFSET_STEPS_MAX:
            raise StageAInputError(
                f"divergence_offset_steps must be <= {DIVERGENCE_OFFSET_STEPS_MAX} "
                f"(synthesis § 8.7 上限): {self.divergence_offset_steps}"
            )
        if self.last_a_b_correlation is not None:
            if not math.isfinite(self.last_a_b_correlation):
                raise StageAInputError(
                    f"last_a_b_correlation must be finite or None: "
                    f"{self.last_a_b_correlation}"
                )
            if not (-1.0 <= self.last_a_b_correlation <= 1.0):
                raise StageAInputError(
                    f"last_a_b_correlation must be in [-1, 1]: "
                    f"{self.last_a_b_correlation}"
                )

    @classmethod
    def initial(cls) -> StageAControllerState:
        """初期 state (divergence_offset_steps=0, last_corr=None)."""
        return cls(divergence_offset_steps=0, last_a_b_correlation=None)


@dataclass(frozen=True)
class StageAIndividualInput:
    """1 個体の評価入力.

    invariant (Round 2 [Suggestion] 1 反映): index は 0-origin、
    ``inputs.individuals[i].index == i`` を caller 責務で保証.
    """

    index: int
    trades: tuple[TradeRecord, ...]
    bars: BarEquitySeries
    business_day_universe: dict[SessionBucket, frozenset[int]]


@dataclass(frozen=True)
class StageAGenerationInput:
    """1 世代の評価入力.

    Note (詳細 Round 1 [C1] 反映): state は本 dataclass に持たない。
    evaluate_generation(state, inputs, ...) の引数で統一 (single source of truth).
    """

    generation: int
    individuals: tuple[StageAIndividualInput, ...]
    feasible_ratio_ema: float  # run-level state、 0.0-1.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.feasible_ratio_ema):
            raise StageAInputError(
                f"feasible_ratio_ema must be finite: {self.feasible_ratio_ema}"
            )
        if not (0.0 <= self.feasible_ratio_ema <= 1.0):
            raise StageAInputError(
                f"feasible_ratio_ema must be in [0, 1]: {self.feasible_ratio_ema}"
            )
        # index 安定性 (Round 2 [Suggestion] 1)
        for i, ind in enumerate(self.individuals):
            if ind.index != i:
                raise StageAInputError(
                    f"individuals[{i}].index ({ind.index}) must equal i "
                    f"(deterministic 0-origin index 必須、 caller=T065 責務)"
                )


@dataclass(frozen=True)
class StageAGateStats:
    """診断用 stats (T071 observability で消費)."""

    generation: int
    n_total: int                          # 入力個体総数
    n_hard_pass: int                      # hard floor 通過個体数
    n_selected: int                       # 最終的に a_pass_indices に含まれる個体数
    q_force_base: float                   # feasible_ratio_ema からの計算値
    q_force_with_divergence: float        # divergence offset 加算後 (= 実際使用 q_force)
    divergence_offset_steps: int          # 当世代の state.divergence_offset_steps
    threshold_score: float | None         # 選抜境界 gate_score (Round 1 [W5] 反映、 空集合時 None)
    min_selected_score: float | None
    max_selected_score: float | None


@dataclass(frozen=True)
class StageAResult:
    """1 世代の Stage A 評価結果.

    default-deny 契約 (Round 1 [W4] / Round 2 [W3] 反映):
    - **a_pass_indices に含まれない個体は selection / archive 全段階から既定で棄却される**
    - T063 は a_pass_indices のみ返す。 a_fail_indices は補集合として caller が暗黙に扱う
    - T065 PR DoD で「a_fail 個体は Pareto 圧計算に含めない」 を test で確認:
        - test_a_fail_individual_excluded_from_nsga_selection
        - test_a_fail_individual_excluded_from_archive_admission
    """

    a_pass_indices: frozenset[int]
    stats: StageAGateStats


# ---------------------------------------------------------------------------
# Helpers (pure functions、 synthesis § 5.1 / § 8.7 厳密準拠)
# ---------------------------------------------------------------------------


def derive_stage_a_thresholds(
    live_criteria: dict,
    window_days: int = STAGE_A_WINDOW_DAYS,
    baseline_dataset_days: int = BASELINE_DATASET_DAYS,
) -> CanonicalFiveThresholds:
    """synthesis § 5.1 / Decision 1, 2, 4 に従い Stage A 用 T061 thresholds を構築.

    Decision 1 (trade_rate proportional):
        trade_count_min_window = max(1, ceil(live_min * window/baseline))
        trade_count_max_window = floor(live_max * window/baseline)
    Decision 2 (net_pnl_min proportional):
        net_pnl_min_window = live_total_pnl_min * (window/baseline)
    Decision 4 (asymmetric rounding): 下限 ceil + 上限 floor

    前提ガード (Round 2 [Suggestion] 2 反映、 違反時 StageAInputError raise):
        - baseline_dataset_days > 0
        - window_days > 0
        - window_days <= baseline_dataset_days
        - live_criteria.trade_count_max >= live_criteria.trade_count_min
        - live_criteria 必須 keys 存在 (sharpe_min, total_pnl_min, max_drawdown_max,
          trade_count_min, trade_count_max, win_rate_min)
    """
    if baseline_dataset_days <= 0:
        raise StageAInputError(
            f"baseline_dataset_days must be > 0: {baseline_dataset_days}"
        )
    if window_days <= 0:
        raise StageAInputError(f"window_days must be > 0: {window_days}")
    if window_days > baseline_dataset_days:
        raise StageAInputError(
            f"window_days ({window_days}) must be <= baseline_dataset_days "
            f"({baseline_dataset_days})"
        )
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
        raise StageAInputError(
            f"live_criteria missing required keys: {sorted(missing)}"
        )
    if live_criteria["trade_count_max"] < live_criteria["trade_count_min"]:
        raise StageAInputError(
            f"live_criteria.trade_count_max ({live_criteria['trade_count_max']}) "
            f"must be >= trade_count_min ({live_criteria['trade_count_min']})"
        )

    ratio = window_days / baseline_dataset_days
    trade_min_window = max(1, math.ceil(live_criteria["trade_count_min"] * ratio))
    trade_max_window = math.floor(live_criteria["trade_count_max"] * ratio)
    if trade_max_window < trade_min_window:
        raise StageAInputError(
            f"derived trade_count_max_window ({trade_max_window}) < "
            f"trade_count_min_window ({trade_min_window}); "
            f"window {window_days} / baseline {baseline_dataset_days} 比率が小さすぎる"
        )

    return CanonicalFiveThresholds(
        sharpe_min=live_criteria["sharpe_min"],
        net_pnl_min=live_criteria["total_pnl_min"] * ratio,
        max_dd_max=live_criteria["max_drawdown_max"],
        trade_count_min=trade_min_window,
        trade_count_max=trade_max_window,
        win_rate_min=live_criteria["win_rate_min"],
    )


def compute_q_force_base(feasible_ratio_ema: float) -> float:
    """synthesis § 5.1 確定式: q_force_base = clamp(0.15 + 0.15 × max(0, 0.10 - ratio)/0.10, 0.15, 0.30).

    Args:
        feasible_ratio_ema: 0.0-1.0、 直近 Run の feasible 個体率 EWMA

    Returns:
        0.15 ~ 0.30
    """
    if not math.isfinite(feasible_ratio_ema):
        raise StageAInputError(
            f"feasible_ratio_ema must be finite: {feasible_ratio_ema}"
        )
    if not (0.0 <= feasible_ratio_ema <= 1.0):
        raise StageAInputError(
            f"feasible_ratio_ema must be in [0, 1]: {feasible_ratio_ema}"
        )
    deficit = max(0.0, Q_FORCE_FEASIBLE_RATIO_THRESHOLD - feasible_ratio_ema)
    raw = Q_FORCE_BASE + Q_FORCE_RANGE * (
        deficit / Q_FORCE_FEASIBLE_RATIO_THRESHOLD
    )
    return min(max(raw, Q_FORCE_BASE_MIN), Q_FORCE_BASE_MAX)


def compute_q_force_with_divergence(
    base_q_force: float,
    divergence_offset_steps: int,
) -> float:
    """synthesis § 8.7 確定式: q_force = min(base + 0.02 × steps, 0.40).

    Args:
        base_q_force: compute_q_force_base() からの値、
            [Q_FORCE_BASE_MIN, Q_FORCE_DIVERGENCE_MAX] 範囲
        divergence_offset_steps: state.divergence_offset_steps (unsigned [0, MAX])

    Returns:
        clamp(base + 0.02 * steps, base, 0.40)

    Raises:
        StageAInputError: 詳細 Round 1 [W2] 反映で前提ガード追加.
            - base_q_force outside [Q_FORCE_BASE_MIN, Q_FORCE_DIVERGENCE_MAX]
            - divergence_offset_steps < 0 or > DIVERGENCE_OFFSET_STEPS_MAX
    """
    if not math.isfinite(base_q_force):
        raise StageAInputError(
            f"base_q_force must be finite: {base_q_force}"
        )
    if not (Q_FORCE_BASE_MIN <= base_q_force <= Q_FORCE_DIVERGENCE_MAX):
        raise StageAInputError(
            f"base_q_force must be in [{Q_FORCE_BASE_MIN}, "
            f"{Q_FORCE_DIVERGENCE_MAX}]: {base_q_force}"
        )
    if divergence_offset_steps < 0:
        raise StageAInputError(
            f"divergence_offset_steps must be >= 0: {divergence_offset_steps}"
        )
    if divergence_offset_steps > DIVERGENCE_OFFSET_STEPS_MAX:
        raise StageAInputError(
            f"divergence_offset_steps must be <= {DIVERGENCE_OFFSET_STEPS_MAX}: "
            f"{divergence_offset_steps}"
        )
    offset = Q_FORCE_DIVERGENCE_STEP * divergence_offset_steps
    raw = base_q_force + offset
    return min(raw, Q_FORCE_DIVERGENCE_MAX)


def compute_gate_score(canonical_five_result: CanonicalFiveResult) -> float:
    """synthesis § 5.1: gate_score = 1 / (1 + worst_gap).

    is_feasible=False 個体は別経路で is_hard_pass=False になる前提。
    本関数は worst_gap が有限値 (T061 で sentinel +inf 撤廃済) を仮定.

    Returns:
        gate_score in (0, 1]、 全達成で 1.0
    """
    return 1.0 / (1.0 + canonical_five_result.gate_worst_gap)


def is_hard_pass(
    canonical_five_result: CanonicalFiveResult,
    trade_count: int,
    hard_floor_min_trades: int = HARD_FLOOR_MIN_TRADES,
) -> bool:
    """synthesis § 5.1 hard floor 判定: invariant feasible AND trades >= 2.

    Args:
        canonical_five_result: T061 評価結果
        trade_count: 当該個体の trade_count (T061 内の trade_count と同値)
        hard_floor_min_trades: synthesis § 5.1 「trades>=2」、 default 2

    Returns:
        True iff invariant feasible AND trade_count >= hard_floor_min_trades
    """
    return (
        canonical_five_result.invariants.is_feasible
        and trade_count >= hard_floor_min_trades
    )


def select_top_q_force_indices(
    scores: Sequence[tuple[int, float]],
    q_force: float,
) -> tuple[frozenset[int], float | None]:
    """世代内 top q_force% を選抜 (Decision 3、 Round 2 [Critical] 反映).

    deterministic tie-break (詳細 Round 1 [W3] 反映):
        sort key = (-score, index) で同点時は index 昇順 (= 入力順では**なく** index 順)

    Args:
        scores: [(index, gate_score), ...] (hard_pass 通過個体のみ)
        q_force: [Q_FORCE_BASE_MIN, Q_FORCE_DIVERGENCE_MAX] 範囲、 詳細 Round 1 [W2] 反映で
            前提ガード追加

    Returns:
        (a_pass_indices, threshold_score):
        - a_pass_indices: frozenset[int]
        - threshold_score: 選抜境界 gate_score (cutoff)、 空集合時 None

    Decision 3 (Round 2 [Critical] 反映):
        n_hard_pass=0 → target_n=0、 a_pass_indices=空、 threshold_score=None
        n_hard_pass>0 → target_n = max(1, int(n_hard_pass * q_force))

    Raises:
        StageAInputError: q_force outside [Q_FORCE_BASE_MIN, Q_FORCE_DIVERGENCE_MAX]
    """
    if not math.isfinite(q_force):
        raise StageAInputError(f"q_force must be finite: {q_force}")
    if not (Q_FORCE_BASE_MIN <= q_force <= Q_FORCE_DIVERGENCE_MAX):
        raise StageAInputError(
            f"q_force must be in [{Q_FORCE_BASE_MIN}, {Q_FORCE_DIVERGENCE_MAX}]: "
            f"{q_force}"
        )
    n_hard_pass = len(scores)
    if n_hard_pass == 0:
        return frozenset(), None
    target_n = max(1, int(n_hard_pass * q_force))
    # deterministic tie-break: (-score, index) で同点時 index 昇順
    sorted_scores = sorted(scores, key=lambda x: (-x[1], x[0]))
    selected = sorted_scores[:target_n]
    a_pass = frozenset(idx for idx, _ in selected)
    threshold_score = selected[-1][1] if selected else None
    return a_pass, threshold_score


def update_divergence_state(
    prev_state: StageAControllerState,
    corr: float,
    *,
    corr_sample_size: int,
) -> StageAControllerState:
    """A→B 乖離 corr を受け取り new_state を返す pure function (synthesis § 8.7).

    C7 / C8 sample-size guard (詳細 Round 1 [C2] 反映):
    - corr_sample_size < CORR_SAMPLE_SIZE_INCONCLUSIVE_MIN (=10):
        StageAInputError raise (運用 bug indicator、 caller=T071 が n>=10 を保証する責務)
    - CORR_SAMPLE_SIZE_INCONCLUSIVE_MIN <= n < CORR_SAMPLE_SIZE_RELIABLE_MIN (10-29):
        INCONCLUSIVE、 state.divergence_offset_steps は不変、
        last_a_b_correlation のみ更新 (監視ログ用)
    - n >= CORR_SAMPLE_SIZE_RELIABLE_MIN (>=30):
        通常更新 (corr<0.5 で +1、 corr>=0.5 で -1、 clamp [0, MAX])

    Args:
        prev_state: 前 Run 終了時の state
        corr: corr(A_proxy_score, B_pooled_score)、 [-1, 1]
        corr_sample_size: corr 計算で使われた個体数 (= 1 Run 内の (A_proxy, B_pooled) ペア数)

    Returns:
        new_state (state は immutable: prev_state を変えず new instance)

    Raises:
        StageAInputError: corr outside [-1, 1] / corr_sample_size < 10 (C7 違反)
    """
    if not math.isfinite(corr):
        raise StageAInputError(f"corr must be finite: {corr}")
    if not (-1.0 <= corr <= 1.0):
        raise StageAInputError(f"corr must be in [-1, 1]: {corr}")
    if corr_sample_size < CORR_SAMPLE_SIZE_INCONCLUSIVE_MIN:
        raise StageAInputError(
            f"corr_sample_size must be >= {CORR_SAMPLE_SIZE_INCONCLUSIVE_MIN} "
            f"(C7 sample size guard): {corr_sample_size}"
        )
    if corr_sample_size < CORR_SAMPLE_SIZE_RELIABLE_MIN:
        # INCONCLUSIVE: state.divergence_offset_steps 不変、 last_corr のみ更新
        return StageAControllerState(
            divergence_offset_steps=prev_state.divergence_offset_steps,
            last_a_b_correlation=corr,
        )
    # 通常更新 (n >= 30)
    if corr < Q_FORCE_DIVERGENCE_RECOVERY_CORRELATION:
        new_steps = min(
            prev_state.divergence_offset_steps + 1, DIVERGENCE_OFFSET_STEPS_MAX
        )
    else:
        new_steps = max(0, prev_state.divergence_offset_steps - 1)
    return StageAControllerState(
        divergence_offset_steps=new_steps,
        last_a_b_correlation=corr,
    )


# ---------------------------------------------------------------------------
# Top-level entry (pure function、 immutable state pass-through)
# ---------------------------------------------------------------------------


def evaluate_generation(
    state: StageAControllerState,
    inputs: StageAGenerationInput,
    *,
    evaluate_fn: Callable[
        ...,
        CanonicalFiveResult,
    ],
    live_criteria: dict,
    bucket_validator: SessionBucketBoundaryProvider | None = None,
) -> tuple[StageAResult, StageAControllerState]:
    """T063 high-level API: Stage A 評価 (orchestrator + ranking).

    詳細 Round 1 [C1] 反映: state は引数のみで受け取る (StageAGenerationInput.state は廃止).

    詳細 Round 1 [W1] 反映: bucket_validator は evaluate_fn に keyword arg で注入。
    evaluate_fn signature は T061.evaluate_canonical_five と一致させる:
        evaluate_fn(trades, bars, thresholds, business_day_universe, *,
        bucket_validator=None, q_bartlett=5)

    手順 (synthesis § 5.1 / § 5.5):
    1. derive_stage_a_thresholds(live_criteria) で T061 用 thresholds を構築
    2. 各 individual_input について evaluate_fn を呼び CanonicalFiveResult 取得
       (bucket_validator を keyword arg で注入)
    3. is_hard_pass(cf_result, trade_count) を判定
    4. hard_pass のみ gate_score = compute_gate_score(cf_result) を計算
    5. q_force_base = compute_q_force_base(inputs.feasible_ratio_ema)
       q_force = compute_q_force_with_divergence(q_force_base, state.divergence_offset_steps)
    6. (a_pass_indices, threshold_score) = select_top_q_force_indices(scores, q_force)
    7. StageAGateStats を構築
    8. (StageAResult, state) を返す
       (state は本関数では変更しない、 update_divergence_state で別途更新)

    Args:
        state: 前 Run 終了時の state (initial() で初期 state 取得)
        inputs: 1 世代の評価入力 (state は含まない、 詳細 Round 1 [C1] 反映)
        evaluate_fn: T061 評価関数の dependency injection (production 時 evaluate_canonical_five)
        live_criteria: config から渡される live_criteria dict
        bucket_validator: T072 で実装する provider、 None なら skip (evaluate_fn に注入)

    Returns:
        (StageAResult, state): state は本関数では変更しない (next Run で update_divergence_state)

    Raises:
        StageAInputError: 入力契約違反 (前提ガード違反 / individuals.index 不整合 etc.)
    """
    thresholds = derive_stage_a_thresholds(live_criteria)

    # 個体毎に T061 評価 (bucket_validator 配線、 詳細 Round 1 [W1])
    cf_results: list[tuple[int, CanonicalFiveResult, int]] = []
    for ind in inputs.individuals:
        cf_result = evaluate_fn(
            ind.trades,
            ind.bars,
            thresholds,
            ind.business_day_universe,
            bucket_validator=bucket_validator,
        )
        trade_count = cf_result.trade_count
        cf_results.append((ind.index, cf_result, trade_count))

    # hard_pass 判定 + gate_score 計算
    hard_pass_scores: list[tuple[int, float]] = []
    for index, cf_result, trade_count in cf_results:
        if is_hard_pass(cf_result, trade_count):
            hard_pass_scores.append((index, compute_gate_score(cf_result)))

    # q_force 計算
    q_force_base = compute_q_force_base(inputs.feasible_ratio_ema)
    q_force = compute_q_force_with_divergence(
        q_force_base, state.divergence_offset_steps
    )

    # 世代内 top q_force% 選抜
    a_pass_indices, threshold_score = select_top_q_force_indices(
        hard_pass_scores, q_force
    )
    selected_scores = [
        score for idx, score in hard_pass_scores if idx in a_pass_indices
    ]

    stats = StageAGateStats(
        generation=inputs.generation,
        n_total=len(inputs.individuals),
        n_hard_pass=len(hard_pass_scores),
        n_selected=len(a_pass_indices),
        q_force_base=q_force_base,
        q_force_with_divergence=q_force,
        divergence_offset_steps=state.divergence_offset_steps,
        threshold_score=threshold_score,
        min_selected_score=min(selected_scores) if selected_scores else None,
        max_selected_score=max(selected_scores) if selected_scores else None,
    )
    result = StageAResult(a_pass_indices=a_pass_indices, stats=stats)
    return result, state  # state は変更しない (immutability)
