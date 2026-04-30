# 詳細設計: T063 — Stage A evaluator

## 使命・制約 (絶対遵守)

zenigame-fx Alpha Factory 使命: live_criteria 全指標同時充足 + (ii-lite) 通過。 絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。 禁止事項 1-7 (synthesis § 1.3) + 8 (archive スキーマ伝搬漏れ、 T058 対応済)。 コーディングルール: バグ修正テストファースト / 全施策テスト必須・振る舞いベース命名 / uv 必須 / ruff & mypy 通過 / Python 3.13。

## 概念設計リファレンス

`devnotes/20260430-0130-todo-T063-stage-a-evaluator/conceptual-design.md` (Round 3 で APPROVED)

## Round 3 review 反映 (Codex 概念レビュー)

| 概念 Round 3 [Warning/Suggestion] | 詳細設計での吸収 |
|---|---|
| [W1] divergence cap 飽和中は実効 q_force が 0.02/Run で下がらない期間がある | docstring に「cap 飽和中は見かけ上下がらない期間あり」 を明記、 該当 test 追加 (Round 3 [S1]) |
| [W2] Decision 1/2 INCONCLUSIVE smoke 後再校正の判定基準先固定 | synthesis § 15 追記候補に「smoke 観測で a_pass_indices 比率 < 5% が 3 Run 連続なら Decision 2 (net_pnl_min) を full mission に切替検討」 等の判定基準を明記 |
| [S1] q_force 飽和・回復テスト | テスト計画に `test_q_force_divergence_cap_saturation_then_recovery` 追加 |
| [S2] derive_stage_a_thresholds 境界値テスト | テスト計画に `test_derive_stage_a_thresholds_at_boundary_window_equals_baseline` / `_window_equals_one_day` / `_trade_count_min_equals_max` 追加 |

## 詳細 Round 1 review 反映 (Codex 詳細レビュー)

| 詳細 Round 1 [Critical/Warning/Suggestion] | 修正対応 |
|---|---|
| [C1] state の単一情報源が崩れている (`StageAGenerationInput.state` と `evaluate_generation(state, ...)` で二重化) | **`StageAGenerationInput.state` を削除**、 `evaluate_generation(state, inputs, ...)` の引数のみに統一。 single source of truth |
| [C2] 乖離更新がサンプルサイズ無視で C7/C8 に抵触 (低標本 corr で機械的更新リスク) | `update_divergence_state(prev, corr, *, corr_sample_size)` シグネチャに変更。 `n < 10`: ValueError raise (運用 bug indicator)。 `10 <= n < 30`: INCONCLUSIVE、 step 不変 (state.last_a_b_correlation のみ更新)。 `n >= 30`: 通常更新。 docstring に C7 適用明記 |
| [W1] `bucket_validator` が未配線 (引数にあるが evaluate_fn へ渡してない) | `evaluate_fn` の Callable signature に `bucket_validator` を含め、 evaluate_generation で keyword arg として渡す経路を明記 |
| [W2] Helper の入力ガード不足 (compute_q_force_with_divergence の base_q_force 範囲検証なし、 select_top_q_force_indices の q_force 範囲検証なし) | 各 helper に前提ガード追加 (base_q_force ∈ [Q_FORCE_BASE_MIN, Q_FORCE_DIVERGENCE_MAX]、 q_force ∈ [Q_FORCE_BASE_MIN, Q_FORCE_DIVERGENCE_MAX]) |
| [W3] 同点 tie-break が仕様化されていない (sorted(..., reverse=True) は入力順依存) | `select_top_q_force_indices` の sort key を `(-score, index)` で確定的に。 deterministic tie-break、 docstring 明記 |
| [W4] 「学術引用」 節のラベル不一致 | 節名を「根拠 / 先行実装」 に変更 (実体は synthesis + 既存コード参照、 学術文献引用なし) |
| [S1] evaluate_generation 契約簡素化 ([C1] 統合済) | [C1] と統合 |
| [S2] テスト追加 (state 二重指定 reject / tie-break 決定性 / corr n 不足 state 据え置き) | テスト計画に追加: `test_evaluate_generation_state_is_only_argument_not_in_inputs` (型レベル)、 `test_select_top_q_force_indices_uses_deterministic_tie_break_by_index`、 `test_update_divergence_state_low_sample_size_keeps_steps_unchanged` |
| [S3] T063 側に default-deny 不変条件テスト | テスト計画に `test_evaluate_generation_does_not_emit_a_fail_indices_field` (StageAResult に a_fail_indices field が無いことを assert) |

## 施策一覧 (Phase 1: T063 PR、 Phase 2 は別 PR)

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | `stage_a_evaluator.py` 新規 (5 dataclass + helper 群 + Constants + evaluate_generation + update_divergence_state) | `src/alpha_factory/stage_a_evaluator.py` (新規) | Critical |
| 2 | `tests/alpha_factory/test_stage_a_evaluator.py` 新規 (q_force 動的計算 / divergence saturation+recovery / hard floor / 世代内 ranking / state immutability / 4 代表ケース / 境界値) | (新規) | Critical |

**Phase 1 (T063 PR) スコープ = 上記 2 施策**。 既存 `stage_gate.py:evaluate_stage_a` への置換は **Phase 2 (T065 統合と同時)** で実施。 T063 PR 単独 merge で runtime に影響なし。

---

## 施策 1: `stage_a_evaluator.py` 新規作成

### 変更箇所

- ファイル: `src/alpha_factory/stage_a_evaluator.py` (新規)

### 波及変更

- `AGENTS.md`: なし
- `config/alpha_factory/default.yaml`: なし (Phase 2 で旧 `stage_a.*` 全廃 + `stage_a.window_days: 56` のみ反映)
- `docs/alpha_factory/*.md`: なし (Phase 2 で stage-gates.md 更新)

### 変更後コード

```python
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
    # DataClasses
    "StageAControllerState",
    "StageAIndividualInput",
    "StageAGenerationInput",
    "StageAGateStats",
    "StageAResult",
    # Constants
    "STAGE_A_WINDOW_DAYS",
    "BASELINE_DATASET_DAYS",
    "Q_FORCE_BASE",
    "Q_FORCE_RANGE",
    "Q_FORCE_FEASIBLE_RATIO_THRESHOLD",
    "Q_FORCE_BASE_MIN",
    "Q_FORCE_BASE_MAX",
    "Q_FORCE_DIVERGENCE_MAX",
    "Q_FORCE_DIVERGENCE_STEP",
    "Q_FORCE_DIVERGENCE_RECOVERY_CORRELATION",
    "DIVERGENCE_OFFSET_STEPS_MAX",
    "HARD_FLOOR_MIN_TRADES",
    # Helpers
    "derive_stage_a_thresholds",
    "compute_q_force_base",
    "compute_q_force_with_divergence",
    "compute_gate_score",
    "is_hard_pass",
    "select_top_q_force_indices",
    "update_divergence_state",
    # Top-level entry
    "evaluate_generation",
    # Exceptions
    "StageAEvaluatorError",
    "StageAInputError",
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
            if not (-1.0 <= self.last_a_b_correlation <= 1.0):
                raise StageAInputError(
                    f"last_a_b_correlation must be in [-1, 1]: "
                    f"{self.last_a_b_correlation}"
                )

    @classmethod
    def initial(cls) -> "StageAControllerState":
        """初期 state (divergence_offset_steps=0, last_corr=None)."""
        return cls(divergence_offset_steps=0, last_a_b_correlation=None)


@dataclass(frozen=True)
class StageAIndividualInput:
    """1 個体の評価入力.

    invariant (Round 2 [Suggestion] 1 反映): index は 0-origin、
    `inputs.individuals[i].index == i` を caller 責務で保証.
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
        base_q_force: compute_q_force_base() からの値、 [Q_FORCE_BASE_MIN, Q_FORCE_DIVERGENCE_MAX] 範囲
        divergence_offset_steps: state.divergence_offset_steps (unsigned [0, MAX])

    Returns:
        clamp(base + 0.02 * steps, base, 0.40)

    Raises:
        StageAInputError: 詳細 Round 1 [W2] 反映で前提ガード追加.
            - base_q_force outside [Q_FORCE_BASE_MIN, Q_FORCE_DIVERGENCE_MAX]
            - divergence_offset_steps < 0 or > DIVERGENCE_OFFSET_STEPS_MAX
    """
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


CORR_SAMPLE_SIZE_INCONCLUSIVE_MIN: Final[int] = 10
"""C7 適用 (詳細 Round 1 [C2] 反映): corr 計算の最低 sample 数.
n < 10 は ValueError raise (運用 bug indicator)、 n=10..29 は INCONCLUSIVE (state 不変)、
n >= 30 で通常更新."""

CORR_SAMPLE_SIZE_RELIABLE_MIN: Final[int] = 30
"""C7 適用: 通常更新の最低 sample 数 (synthesis § 16 / AGENTS.md C7 conformity)."""


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
        evaluate_fn(trades, bars, thresholds, business_day_universe, *, bucket_validator=None, q_bartlett=5)

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
    8. (StageAResult, state) を返す (state は本関数では変更しない、 update_divergence_state で別途更新)

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
```

### ルックアヘッドバイアスチェック

- 評価期間 = 末尾 8w (recent proxy)、 T060 stage_a Period の length 56 days を使用
- T061 内部の bar slice は upstream (T070) の責務
- T063 自体は trade list / bars を集計するのみで lookback 操作なし

### C3 / C7 適用

- **C3**: 該当なし (相関分析は T071 observability で外部計算、 T063 は corr を受け取るのみ)
- **C7**:
  - feasible_ratio_ema は run-level (各 Run 12,288 評価) → C7 OK
  - top q_force% 選抜は世代内 (各世代 192 個体) → C7 OK

### パフォーマンスチェック

- 計算量: O(N + N log N) (N=pop_size=192、 各個体で T061 呼出 O(?))
- 1 世代当り T061 呼出 192 回が支配的、 sort O(N log N) ≈ 1500 ops は無視できる
- pop=192 × gen=64 = 12,288 評価 / Run、 全 RUN ~ 10 sec (T061 1 評価 ~0.5ms 想定)

### テスト計画 (施策 2 で詳述)

### リスク

- T061 マージ前は本 PR を merge しない (`from src.alpha_factory.canonical_metrics import ...`)
- T060 マージ前は影響なし (T063 は T060 の Period dataclass を直接使わず、 8w days の int 値のみ const で固定)
- 既存 stage_gate.py に touch しないため Phase 1 単体では runtime に影響なし

---

## 施策 2: `tests/alpha_factory/test_stage_a_evaluator.py` 新規作成

### 変更箇所

- ファイル: `tests/alpha_factory/test_stage_a_evaluator.py` (新規)

### テスト計画

振る舞いベース test 名:

#### Constants
- `test_stage_a_window_days_is_56_eight_weeks`
- `test_baseline_dataset_days_is_730_for_24m`
- `test_q_force_base_min_is_0_15_max_is_0_30`
- `test_q_force_divergence_max_is_0_40`
- `test_divergence_offset_steps_max_is_derived_from_constants`
- `test_hard_floor_min_trades_is_2`

#### StageAControllerState (immutable, frozen)
- `test_state_initial_has_zero_steps_and_none_correlation`
- `test_state_rejects_negative_divergence_offset_steps`
- `test_state_rejects_offset_steps_above_max`
- `test_state_rejects_correlation_outside_unit_interval`
- `test_state_is_frozen_dataclass`

#### derive_stage_a_thresholds (Round 2 [S2] 境界値)
- `test_derive_stage_a_thresholds_proportional_with_baseline_24m`
  (live={50, 5000} → window=8w → ceil(50*56/730)=4, floor(5000*56/730)=383)
- `test_derive_stage_a_thresholds_at_boundary_window_equals_baseline`
  (window_days = baseline → trade_count 範囲 = live と同じ)
- `test_derive_stage_a_thresholds_at_boundary_window_equals_one_day`
  (window_days = 1 → trade_count_min=1 or ceil(1*1/730)=1)
- `test_derive_stage_a_thresholds_when_trade_count_min_equals_max`
  (live trade_count_min == max → window 比例後も整合性確保)
- `test_derive_stage_a_thresholds_rejects_zero_baseline_days`
- `test_derive_stage_a_thresholds_rejects_zero_window_days`
- `test_derive_stage_a_thresholds_rejects_window_exceeding_baseline`
- `test_derive_stage_a_thresholds_rejects_inverted_trade_count_range`
- `test_derive_stage_a_thresholds_rejects_missing_required_keys`
- `test_derive_stage_a_thresholds_rejects_when_window_too_small_yields_inverted_window_range`

#### compute_q_force_base
- `test_q_force_base_high_feasible_ratio_yields_min_0_15`
  (feasible_ratio=0.5 → q_force=0.15)
- `test_q_force_base_zero_feasible_ratio_yields_max_0_30`
  (feasible_ratio=0.0 → q_force=0.30)
- `test_q_force_base_at_threshold_0_10_yields_min_0_15`
- `test_q_force_base_below_threshold_scales_linearly`
  (feasible_ratio=0.05 → q_force=0.225)
- `test_q_force_base_rejects_ratio_outside_unit_interval`

#### compute_q_force_with_divergence (詳細 Round 1 [W2] 入力ガード反映)
- `test_q_force_with_divergence_zero_steps_returns_base`
- `test_q_force_with_divergence_step_increment_is_0_02`
- `test_q_force_with_divergence_capped_at_0_40`
  (base=0.30 + steps=10 = 0.50 raw → clamp 0.40)
- `test_q_force_with_divergence_rejects_negative_steps`
- `test_q_force_with_divergence_rejects_steps_above_max`
- `test_q_force_with_divergence_rejects_base_below_0_15`
  (詳細 Round 1 [W2]: base < Q_FORCE_BASE_MIN → StageAInputError)
- `test_q_force_with_divergence_rejects_base_above_0_40`

#### update_divergence_state (詳細 Round 1 [C2] sample-size guard 反映)
- `test_update_divergence_state_corr_below_0_5_increments_steps_when_n_30`
- `test_update_divergence_state_corr_at_or_above_0_5_decrements_steps_when_n_30`
- `test_update_divergence_state_step_increment_capped_at_max`
- `test_update_divergence_state_step_decrement_floored_at_zero`
- `test_update_divergence_state_records_last_correlation`
- `test_update_divergence_state_returns_new_instance_not_mutating_prev`
- `test_update_divergence_state_rejects_correlation_outside_unit_interval`
- `test_update_divergence_state_low_sample_size_n_below_10_raises_error`
  (詳細 Round 1 [C2]: n < 10 → ValueError)
- `test_update_divergence_state_inconclusive_sample_size_n_10_to_29_keeps_steps_unchanged`
  (詳細 Round 1 [C2] / [S2]: 10 <= n < 30 → state.divergence_offset_steps 不変、
  last_correlation のみ更新)
- `test_update_divergence_state_n_below_inconclusive_min_does_not_mutate_step_offset`

#### compute_gate_score
- `test_gate_score_zero_worst_gap_yields_one`
- `test_gate_score_positive_worst_gap_yields_below_one`
- `test_gate_score_monotone_decreasing_with_worst_gap`

#### is_hard_pass
- `test_is_hard_pass_true_when_feasible_and_trades_above_floor`
- `test_is_hard_pass_false_when_infeasible_invariant`
- `test_is_hard_pass_false_when_trades_below_floor`
- `test_is_hard_pass_false_when_trades_equal_zero`
- `test_is_hard_pass_at_boundary_trades_equals_two`

#### select_top_q_force_indices (Round 2 [Critical] / 詳細 Round 1 [W2], [W3])
- `test_select_top_q_force_empty_input_returns_empty_set_and_none_threshold`
  (n_hard_pass=0 → 空集合 + threshold_score=None、 修正 Round 2 [C])
- `test_select_top_q_force_single_individual_yields_single_pass`
  (n_hard_pass=1, q_force=0.15 → max(1, int(1*0.15))=1)
- `test_select_top_q_force_returns_top_n_descending_by_score`
- `test_select_top_q_force_rounding_uses_floor_with_minimum_one`
  (n_hard_pass=10, q_force=0.15 → int(1.5)=1)
- `test_select_top_q_force_threshold_score_is_min_selected_score`
- `test_select_top_q_force_uses_deterministic_tie_break_by_index_ascending`
  (詳細 Round 1 [W3]: 同 score の場合 index 昇順で選抜される)
- `test_select_top_q_force_rejects_q_force_outside_valid_range`
  (詳細 Round 1 [W2]: q_force < 0.15 or > 0.40 → StageAInputError)

#### evaluate_generation (top-level、 4 代表ケース)
- `test_evaluate_generation_perfect_run_yields_top_q_force_pass`
  (代表ケース 1: 全個体 hard_pass、 top 15% が a_pass)
- `test_evaluate_generation_no_hard_pass_yields_empty_a_pass_set`
  (代表ケース 2: 全個体 infeasible、 a_pass=空、 threshold=None)
- `test_evaluate_generation_low_feasible_ratio_increases_q_force`
  (代表ケース 3: feasible_ratio_ema=0.05 → q_force=0.225 → top 22.5% pass)
- `test_evaluate_generation_with_divergence_state_increases_q_force`
  (代表ケース 4: state.steps=5 → q_force = base + 0.10 = max 0.40)
- `test_evaluate_generation_returns_state_unchanged`
  (state は本関数で変更しない)
- `test_evaluate_generation_rejects_individuals_with_inconsistent_index`
  (Round 2 [S1] index 安定性)
- `test_evaluate_generation_uses_evaluate_fn_dependency_injection`
  (mock evaluate_fn で deterministic 動作確認)

#### Saturation + Recovery (Round 3 [S1])
- `test_q_force_divergence_cap_saturation_then_recovery`
  (シミュレーション: corr<0.5 を N 回連続 → cap 到達 → corr>=0.5 連続 → 0.02/Run で戻る、
  cap 飽和中の見かけ q_force 不変期間を確認)

#### state immutability (Round 1 [C3])
- `test_state_is_frozen_dataclass_setattr_raises`
- `test_evaluate_generation_does_not_mutate_state_argument`
- `test_update_divergence_state_does_not_mutate_prev_state`

#### default-deny 不変条件 (詳細 Round 1 [S3])
- `test_stage_a_result_does_not_have_a_fail_indices_field`
  (StageAResult に a_fail_indices field がないことを assert、 default-deny 契約強制)

#### state 単一情報源 (詳細 Round 1 [C1])
- `test_stage_a_generation_input_does_not_have_state_field`
  (StageAGenerationInput に state field がないことを assert、 single source of truth)
- `test_evaluate_generation_takes_state_only_via_first_argument`
  (state は evaluate_generation の引数 のみで受け取る)

#### bucket_validator 配線 (詳細 Round 1 [W1])
- `test_evaluate_generation_passes_bucket_validator_to_evaluate_fn`
  (evaluate_fn に bucket_validator が keyword arg で渡されることを mock で確認)

### リスク

- (テストのみ、 リスク軽微)

---

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | **standalone** (T061 マージ後前提、 単体実装可、 Phase 2 で 8 箇所同時更新を別 PR) |
| 判断根拠 | T063 PR は単体テストのみで既存 stage_gate / swim_lane 経路に touch しない |
| 競合リスク | T058-T062 マージ済前提、 直接 import は T061 のみ |
| 想定実装時間 | 中 (2 施策、 1 day 想定) |

## 実装順序

T063 PR で 2 施策を 1 PR で着地。 Phase 2 (8 箇所同時更新) は T065 統合と同時に別 PR (別 TODO)。

---

## DoD (Definition of Done)

T063 PR 完了基準:

### コード DoD

- [ ] `src/alpha_factory/stage_a_evaluator.py` 新規作成 (5 dataclass + Constants + 7 helper + top-level entry + 例外 2)
- [ ] `tests/alpha_factory/test_stage_a_evaluator.py` 新規作成 (上記 test 全 pass、 4 代表ケース + saturation/recovery + 境界値)
- [ ] `uv run pytest tests/alpha_factory/test_stage_a_evaluator.py` 全 pass
- [ ] `uv run ruff check src/ tests/` clean
- [ ] `uv run mypy src/` clean
- [ ] `stage_gate.py` / `swim_lane.py` / `archive.py` / `cross_pair.py` / `config.py` / `default.yaml` を変更しない

### Phase 1 (T063 PR) C2 parallel-path 確認 DoD (T062 同様 5 段階)

- [ ] 段階 1 (直 import): `grep -rn "from src.alpha_factory.stage_a_evaluator" scripts/ src/ tests/` が 自身 + tests のみ
- [ ] 段階 2 (alias import): `grep -rn -E "import\s+src\.alpha_factory\.stage_a_evaluator" src/ scripts/ tests/` が 自身 + tests のみ
- [ ] 段階 3 (relative import): `grep -rn -E "from\s+\.+\s*stage_a_evaluator" src/ scripts/ tests/` が 自身 + tests のみ
- [ ] 段階 4 (再エクスポート): `grep -rn "stage_a_evaluator" src/alpha_factory/__init__.py src/alpha_factory/*.py | grep -v "src/alpha_factory/stage_a_evaluator.py:"` が 0 hit
- [ ] 段階 5 (runtime シンボル): `grep -rn -E "evaluate_generation|StageAResult|StageAGateController|StageAControllerState" src/alpha_factory/stage_gate.py src/alpha_factory/swim_lane.py scripts/alpha_factory/run_ga.py` が 0 hit

### Phase 2 (T065 統合と同時、 別 PR) DoD (申し送り、 8 箇所同時更新)

- [ ] `stage_gate.py:evaluate_stage_a` を **全廃** (旧 Sharpe + complexity penalty 経路)、 caller を T063 evaluate_generation に置換 (T065)
- [ ] (新規) `src/alpha_factory/ga/stage_a_orchestrator.py`: T065 NSGA-II loop が T061 → T063 を呼ぶ orchestration (T065)
- [ ] `scripts/alpha_factory/run_ga.py`: per-generation で T063 evaluate_generation 呼出、 Run 終了時に update_divergence_state (T065)
- [ ] (新規) `src/alpha_factory/observability/a_b_divergence.py`: corr(A_proxy_score, B_pooled_score) を Run 終了時計算 (T071)
- [ ] `src/alpha_factory/config.py:StageGateConfig` 旧 `stage_a.{target_pass_rate, alpha, threshold, calibrate.*, min_exposure_trade_count}` 全廃、 `stage_a.window_days: int = 56` のみ (T065)
- [ ] `config/alpha_factory/default.yaml`: 旧 `stage_gate.stage_a.*` 全廃、 `stage_gate.stage_a.window_days: 56` のみ (T065)
- [ ] `src/alpha_factory/archive.py`: A-fail 個体を archive admission 全段階から排除、 default-deny test 追加 (T067)
- [ ] T063 controller state (`divergence_offset_steps`, `last_a_b_correlation`) を archive metadata or run cache に保存 (T067)
- [ ] **default-deny 検証 test** (Round 2 [W3]):
  - `test_a_fail_individual_excluded_from_nsga_selection` (T065 PR DoD)
  - `test_a_fail_individual_excluded_from_archive_admission` (T067 PR DoD)
- [ ] **runtime wiring smoke** (T061-T062 と同型): `evaluate_stage_a` を実際に呼んで T063 / T061 が configured に走ることを確認する E2E smoke

---

## 関連 / 後段 TODO

- T058: Schema v2 contract (依存先、 設計 APPROVED)
- T059: EpochManager (依存先、 設計 APPROVED)
- T060: Partition + Fold generator (依存先、 設計 APPROVED、 stage_a Period の length 56 days を const で参照)
- T061: canonical 5 engine (依存先、 設計 APPROVED、 直接 import)
- T062: mission_inf_gap engine (T063 では使わない、 Stage A は canonical 5 worst gate のみ)
- T064: Stage B/C-lite/C evaluator (本 TODO と並列、 別 module)
- T065-T066: NSGA-II + CPPS (T063 evaluate_generation を消費)
- T067: Loop closure (T063 controller state の persistence + archive A-fail 排除)
- T071: observability (corr(A_proxy, B_pooled) 計算、 T063 update_divergence_state に注入)

---

## 根拠 / 先行実装 (詳細 Round 1 [W4] 反映、 節名修正)

- synthesis § 5.1 (Stage A: hard gate + q_force) / § 5.5 (stage 別評価値の不混在) / § 8.7 (A→B 乖離自動引き上げ) / § 19 #4 (逆輸入候補)
- zenigame `ga/nsga2/stage_a_gate.py` (`StageAGateController`): 世代内 ranking 選択の元実装。 fx 側で q_force 動的化 + A→B 乖離自動引き上げを新規追加
- zenigame `ga/nsga2/optimize.py:950, 1006/1195`: GA optimize loop での Stage A pass 経路 (Phase 2 で T065 が再実装)
- T061 詳細設計 APPROVED: canonical 5 worst gate_score の上位 contract

(本 TODO は内部 synthesis + 既存実装参照が主体、 学術文献引用なし — 詳細 Round 1 [W4] 反映で節名を「学術引用」 から「根拠 / 先行実装」 に修正)
