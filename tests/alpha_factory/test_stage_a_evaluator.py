"""T063: Stage A evaluator — 振る舞いベース test.

詳細設計: ``devnotes/20260430-0130-todo-T063-stage-a-evaluator/detailed-design.md``

Test 計画 (詳細設計 § 施策 2):
- Constants
- StageAControllerState (immutable, frozen)
- derive_stage_a_thresholds (Round 2 [S2] 境界値)
- compute_q_force_base
- compute_q_force_with_divergence (詳細 Round 1 [W2] 入力ガード反映)
- update_divergence_state (詳細 Round 1 [C2] sample-size guard 反映)
- compute_gate_score
- is_hard_pass
- select_top_q_force_indices (Round 2 [Critical] / 詳細 Round 1 [W2], [W3])
- evaluate_generation (top-level、 4 代表ケース)
- Saturation + Recovery (Round 3 [S1])
- state immutability
- default-deny 不変条件 (詳細 Round 1 [S3])
- state 単一情報源 (詳細 Round 1 [C1])
- bucket_validator 配線 (詳細 Round 1 [W1])
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields

import pytest

from src.alpha_factory.canonical_metrics import (
    BarEquityPoint,
    BarEquitySeries,
    CanonicalFiveResult,
    InfeasibleReasonCode,
    InvariantFlags,
    SessionBucket,
    SessionBucketBoundaryProvider,
)
from src.alpha_factory.stage_a_evaluator import (
    BASELINE_DATASET_DAYS,
    CORR_SAMPLE_SIZE_INCONCLUSIVE_MIN,
    CORR_SAMPLE_SIZE_RELIABLE_MIN,
    DIVERGENCE_OFFSET_STEPS_MAX,
    HARD_FLOOR_MIN_TRADES,
    Q_FORCE_BASE,
    Q_FORCE_BASE_MAX,
    Q_FORCE_BASE_MIN,
    Q_FORCE_DIVERGENCE_MAX,
    Q_FORCE_DIVERGENCE_RECOVERY_CORRELATION,
    Q_FORCE_DIVERGENCE_STEP,
    Q_FORCE_FEASIBLE_RATIO_THRESHOLD,
    Q_FORCE_RANGE,
    STAGE_A_WINDOW_DAYS,
    StageAControllerState,
    StageAGenerationInput,
    StageAIndividualInput,
    StageAInputError,
    StageAResult,
    compute_gate_score,
    compute_q_force_base,
    compute_q_force_with_divergence,
    derive_stage_a_thresholds,
    evaluate_generation,
    is_hard_pass,
    select_top_q_force_indices,
    update_divergence_state,
)

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _live_criteria(
    *,
    sharpe_min: float = 1.0,
    total_pnl_min: float = 50000.0,
    max_drawdown_max: float = 0.20,
    trade_count_min: int = 50,
    trade_count_max: int = 5000,
    win_rate_min: float = 0.45,
) -> dict:
    return {
        "sharpe_min": sharpe_min,
        "total_pnl_min": total_pnl_min,
        "max_drawdown_max": max_drawdown_max,
        "trade_count_min": trade_count_min,
        "trade_count_max": trade_count_max,
        "win_rate_min": win_rate_min,
    }


def _make_canonical_five_result(
    *,
    is_feasible: bool = True,
    gate_worst_gap: float = 0.0,
    trade_count: int = 100,
) -> CanonicalFiveResult:
    """Test 用 CanonicalFiveResult fixture."""
    if is_feasible:
        codes: frozenset[InfeasibleReasonCode] = frozenset()
    else:
        codes = frozenset({InfeasibleReasonCode.INPUT_EMPTY_TRADE_LIST})
    invariants = InvariantFlags(
        session_close_drop_count=0,
        negative_equity_drop_open_count=0,
        infeasible_reason_codes=codes,
    )
    return CanonicalFiveResult(
        sr_session_worst_block_scale=0.1,
        sr_session_worst_annual_estimate=2.5,
        net_pnl_after_cost=100000.0,
        max_dd=0.1,
        trade_count=trade_count,
        session_block_win_rate_worst=0.5,
        per_bucket_sr={b: 0.1 for b in SessionBucket},
        per_bucket_wr={b: 0.5 for b in SessionBucket},
        low_sample_buckets=frozenset(),
        slack_sharpe=0.5,
        slack_pnl=0.5,
        slack_dd=0.5,
        slack_tc=0.5,
        slack_wr=0.5,
        gate_worst_gap=gate_worst_gap,
        gate_pass=is_feasible and gate_worst_gap <= 1e-9,
        log_pf_clip=0.0,
        bucket_validator_version="unvalidated",
        invariants=invariants,
    )


def _make_individual(index: int = 0) -> StageAIndividualInput:
    """空 trade list、 1 bar の最小限 Individual fixture (evaluate_fn は mock 想定)."""
    from datetime import UTC, datetime

    bar = BarEquityPoint(
        timestamp_utc=datetime(2026, 1, 1, tzinfo=UTC),
        equity=100000.0,
    )
    bars = BarEquitySeries(points=(bar,))
    universe = {b: frozenset({0}) for b in SessionBucket}
    return StageAIndividualInput(
        index=index,
        trades=(),
        bars=bars,
        business_day_universe=universe,
    )


def _make_eval_fn(
    results: dict[int, CanonicalFiveResult] | None = None,
    *,
    default: CanonicalFiveResult | None = None,
) -> Callable[..., CanonicalFiveResult]:
    """``evaluate_fn`` mock factory.

    Args:
        results: trade count を key とする CanonicalFiveResult 辞書 (使わなければ None)
        default: 全 call で同じ結果を返したい場合の default
    """
    if default is None:
        default = _make_canonical_five_result()

    def fn(
        trades: object,
        bars: object,
        thresholds: object,
        business_day_universe: object,
        *,
        bucket_validator: object | None = None,
        q_bartlett: int = 5,
    ) -> CanonicalFiveResult:
        # results がある場合 trades の id ベースで分岐 (test 用簡易)
        return default

    return fn


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_stage_a_window_days_is_56_eight_weeks(self) -> None:
        assert STAGE_A_WINDOW_DAYS == 56

    def test_baseline_dataset_days_is_730_for_24m(self) -> None:
        assert BASELINE_DATASET_DAYS == 730

    def test_q_force_base_min_is_0_15_max_is_0_30(self) -> None:
        assert Q_FORCE_BASE_MIN == 0.15
        assert Q_FORCE_BASE_MAX == 0.30
        assert Q_FORCE_BASE == 0.15
        assert Q_FORCE_RANGE == 0.15

    def test_q_force_divergence_max_is_0_40(self) -> None:
        assert Q_FORCE_DIVERGENCE_MAX == 0.40
        assert Q_FORCE_DIVERGENCE_STEP == 0.02
        assert Q_FORCE_DIVERGENCE_RECOVERY_CORRELATION == 0.5

    def test_divergence_offset_steps_max_is_derived_from_constants(self) -> None:
        # ceil((0.40 - 0.15) / 0.02) = ceil(12.5) = 13
        expected = math.ceil(
            (Q_FORCE_DIVERGENCE_MAX - Q_FORCE_BASE_MIN) / Q_FORCE_DIVERGENCE_STEP
        )
        assert expected == DIVERGENCE_OFFSET_STEPS_MAX
        assert DIVERGENCE_OFFSET_STEPS_MAX == 13

    def test_hard_floor_min_trades_is_2(self) -> None:
        assert HARD_FLOOR_MIN_TRADES == 2

    def test_q_force_feasible_ratio_threshold_is_0_10(self) -> None:
        assert Q_FORCE_FEASIBLE_RATIO_THRESHOLD == 0.10

    def test_corr_sample_size_constants_for_c7_guard(self) -> None:
        assert CORR_SAMPLE_SIZE_INCONCLUSIVE_MIN == 10
        assert CORR_SAMPLE_SIZE_RELIABLE_MIN == 30


# ---------------------------------------------------------------------------
# StageAControllerState (immutable, frozen)
# ---------------------------------------------------------------------------


class TestStageAControllerState:
    def test_state_initial_has_zero_steps_and_none_correlation(self) -> None:
        s = StageAControllerState.initial()
        assert s.divergence_offset_steps == 0
        assert s.last_a_b_correlation is None

    def test_state_rejects_negative_divergence_offset_steps(self) -> None:
        with pytest.raises(StageAInputError, match="divergence_offset_steps must be >= 0"):
            StageAControllerState(divergence_offset_steps=-1, last_a_b_correlation=None)

    def test_state_rejects_offset_steps_above_max(self) -> None:
        with pytest.raises(StageAInputError, match="must be <="):
            StageAControllerState(
                divergence_offset_steps=DIVERGENCE_OFFSET_STEPS_MAX + 1,
                last_a_b_correlation=None,
            )

    def test_state_rejects_correlation_outside_unit_interval(self) -> None:
        with pytest.raises(StageAInputError, match="must be in"):
            StageAControllerState(
                divergence_offset_steps=0, last_a_b_correlation=1.5
            )
        with pytest.raises(StageAInputError, match="must be in"):
            StageAControllerState(
                divergence_offset_steps=0, last_a_b_correlation=-1.5
            )

    def test_state_is_frozen_dataclass(self) -> None:
        s = StageAControllerState.initial()
        assert dataclasses.is_dataclass(s)
        # frozen は __setattr__ で FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            s.divergence_offset_steps = 5  # type: ignore[misc]

    def test_state_accepts_correlation_at_unit_interval_boundary(self) -> None:
        StageAControllerState(divergence_offset_steps=0, last_a_b_correlation=1.0)
        StageAControllerState(divergence_offset_steps=0, last_a_b_correlation=-1.0)
        StageAControllerState(divergence_offset_steps=0, last_a_b_correlation=0.0)


# ---------------------------------------------------------------------------
# derive_stage_a_thresholds (Round 2 [S2] 境界値)
# ---------------------------------------------------------------------------


class TestDeriveStageAThresholds:
    def test_derive_stage_a_thresholds_proportional_with_baseline_24m(self) -> None:
        # live={50, 5000} → window=8w → ceil(50*56/730)=4, floor(5000*56/730)=383
        thresholds = derive_stage_a_thresholds(_live_criteria())
        assert thresholds.trade_count_min == math.ceil(50 * 56 / 730)
        assert thresholds.trade_count_max == math.floor(5000 * 56 / 730)
        assert thresholds.trade_count_min == 4
        assert thresholds.trade_count_max == 383
        assert thresholds.net_pnl_min == pytest.approx(50000 * 56 / 730)
        assert thresholds.sharpe_min == 1.0
        assert thresholds.max_dd_max == 0.20
        assert thresholds.win_rate_min == 0.45

    def test_derive_stage_a_thresholds_at_boundary_window_equals_baseline(self) -> None:
        # window_days = baseline → trade_count 範囲 = live と同じ
        thresholds = derive_stage_a_thresholds(
            _live_criteria(),
            window_days=BASELINE_DATASET_DAYS,
            baseline_dataset_days=BASELINE_DATASET_DAYS,
        )
        assert thresholds.trade_count_min == 50
        assert thresholds.trade_count_max == 5000
        assert thresholds.net_pnl_min == pytest.approx(50000.0)

    def test_derive_stage_a_thresholds_at_boundary_window_equals_one_day(self) -> None:
        # window_days = 1 → trade_count_min=ceil(50/730)=1, but max=floor(5000/730)=6
        thresholds = derive_stage_a_thresholds(
            _live_criteria(),
            window_days=1,
            baseline_dataset_days=730,
        )
        assert thresholds.trade_count_min == 1
        assert thresholds.trade_count_max == math.floor(5000 / 730)

    def test_derive_stage_a_thresholds_when_trade_count_min_equals_max(self) -> None:
        # live trade_count_min == max → window 比例後も整合性確保
        # ratio = 56/730、 trade_min = ceil(100*56/730)=8、 trade_max = floor(100*56/730)=7
        # → 派生で min > max になる場合は raise
        with pytest.raises(StageAInputError, match="derived trade_count_max_window"):
            derive_stage_a_thresholds(
                _live_criteria(trade_count_min=100, trade_count_max=100)
            )

    def test_derive_stage_a_thresholds_rejects_zero_baseline_days(self) -> None:
        with pytest.raises(StageAInputError, match="baseline_dataset_days must be > 0"):
            derive_stage_a_thresholds(_live_criteria(), baseline_dataset_days=0)

    def test_derive_stage_a_thresholds_rejects_zero_window_days(self) -> None:
        with pytest.raises(StageAInputError, match="window_days must be > 0"):
            derive_stage_a_thresholds(_live_criteria(), window_days=0)

    def test_derive_stage_a_thresholds_rejects_window_exceeding_baseline(self) -> None:
        with pytest.raises(StageAInputError, match="must be <= baseline_dataset_days"):
            derive_stage_a_thresholds(
                _live_criteria(), window_days=1000, baseline_dataset_days=730
            )

    def test_derive_stage_a_thresholds_rejects_inverted_trade_count_range(self) -> None:
        with pytest.raises(StageAInputError, match="trade_count_max"):
            derive_stage_a_thresholds(
                _live_criteria(trade_count_min=100, trade_count_max=50)
            )

    def test_derive_stage_a_thresholds_rejects_missing_required_keys(self) -> None:
        bad = _live_criteria()
        del bad["sharpe_min"]
        with pytest.raises(StageAInputError, match="missing required keys"):
            derive_stage_a_thresholds(bad)

    def test_derive_stage_a_thresholds_rejects_when_window_too_small_yields_inverted_window_range(
        self,
    ) -> None:
        # live trade_count_min=10, max=12 + window_days=1, baseline=730
        # → ceil(10/730)=1, floor(12/730)=0 → raise
        with pytest.raises(StageAInputError, match="derived trade_count_max_window"):
            derive_stage_a_thresholds(
                _live_criteria(trade_count_min=10, trade_count_max=12),
                window_days=1,
                baseline_dataset_days=730,
            )


# ---------------------------------------------------------------------------
# compute_q_force_base
# ---------------------------------------------------------------------------


class TestComputeQForceBase:
    def test_q_force_base_high_feasible_ratio_yields_min_0_15(self) -> None:
        assert compute_q_force_base(0.5) == pytest.approx(0.15)
        assert compute_q_force_base(1.0) == pytest.approx(0.15)

    def test_q_force_base_zero_feasible_ratio_yields_max_0_30(self) -> None:
        assert compute_q_force_base(0.0) == pytest.approx(0.30)

    def test_q_force_base_at_threshold_0_10_yields_min_0_15(self) -> None:
        # threshold 上では deficit=0 → q_force=0.15
        assert compute_q_force_base(0.10) == pytest.approx(0.15)

    def test_q_force_base_below_threshold_scales_linearly(self) -> None:
        # ratio=0.05、 deficit=0.05、 raw = 0.15 + 0.15 * (0.05/0.10) = 0.225
        assert compute_q_force_base(0.05) == pytest.approx(0.225)

    def test_q_force_base_rejects_ratio_outside_unit_interval(self) -> None:
        with pytest.raises(StageAInputError, match="must be in"):
            compute_q_force_base(-0.1)
        with pytest.raises(StageAInputError, match="must be in"):
            compute_q_force_base(1.1)

    def test_q_force_base_rejects_nan_ratio(self) -> None:
        with pytest.raises(StageAInputError, match="finite"):
            compute_q_force_base(float("nan"))


# ---------------------------------------------------------------------------
# compute_q_force_with_divergence (詳細 Round 1 [W2] 入力ガード反映)
# ---------------------------------------------------------------------------


class TestComputeQForceWithDivergence:
    def test_q_force_with_divergence_zero_steps_returns_base(self) -> None:
        assert compute_q_force_with_divergence(0.15, 0) == pytest.approx(0.15)
        assert compute_q_force_with_divergence(0.30, 0) == pytest.approx(0.30)

    def test_q_force_with_divergence_step_increment_is_0_02(self) -> None:
        assert compute_q_force_with_divergence(0.15, 1) == pytest.approx(0.17)
        assert compute_q_force_with_divergence(0.15, 5) == pytest.approx(0.25)

    def test_q_force_with_divergence_capped_at_0_40(self) -> None:
        # base=0.30 + steps=10 → raw=0.50、 clamp 0.40
        assert compute_q_force_with_divergence(0.30, 10) == pytest.approx(0.40)
        assert compute_q_force_with_divergence(0.15, 13) == pytest.approx(0.40)

    def test_q_force_with_divergence_rejects_negative_steps(self) -> None:
        with pytest.raises(StageAInputError, match=">= 0"):
            compute_q_force_with_divergence(0.15, -1)

    def test_q_force_with_divergence_rejects_steps_above_max(self) -> None:
        with pytest.raises(StageAInputError, match="<="):
            compute_q_force_with_divergence(0.15, DIVERGENCE_OFFSET_STEPS_MAX + 1)

    def test_q_force_with_divergence_rejects_base_below_0_15(self) -> None:
        # 詳細 Round 1 [W2]: base < Q_FORCE_BASE_MIN → StageAInputError
        with pytest.raises(StageAInputError, match="base_q_force"):
            compute_q_force_with_divergence(0.10, 0)

    def test_q_force_with_divergence_rejects_base_above_0_40(self) -> None:
        with pytest.raises(StageAInputError, match="base_q_force"):
            compute_q_force_with_divergence(0.50, 0)

    def test_q_force_with_divergence_rejects_nan_base(self) -> None:
        with pytest.raises(StageAInputError, match="finite"):
            compute_q_force_with_divergence(float("nan"), 0)


# ---------------------------------------------------------------------------
# update_divergence_state (詳細 Round 1 [C2] sample-size guard 反映)
# ---------------------------------------------------------------------------


class TestUpdateDivergenceState:
    def test_update_divergence_state_corr_below_0_5_increments_steps_when_n_30(
        self,
    ) -> None:
        prev = StageAControllerState(divergence_offset_steps=2, last_a_b_correlation=0.6)
        new = update_divergence_state(prev, corr=0.3, corr_sample_size=30)
        assert new.divergence_offset_steps == 3
        assert new.last_a_b_correlation == 0.3

    def test_update_divergence_state_corr_at_or_above_0_5_decrements_steps_when_n_30(
        self,
    ) -> None:
        prev = StageAControllerState(divergence_offset_steps=2, last_a_b_correlation=0.3)
        new = update_divergence_state(prev, corr=0.5, corr_sample_size=30)
        assert new.divergence_offset_steps == 1
        new2 = update_divergence_state(prev, corr=0.7, corr_sample_size=30)
        assert new2.divergence_offset_steps == 1

    def test_update_divergence_state_step_increment_capped_at_max(self) -> None:
        prev = StageAControllerState(
            divergence_offset_steps=DIVERGENCE_OFFSET_STEPS_MAX,
            last_a_b_correlation=0.1,
        )
        new = update_divergence_state(prev, corr=0.0, corr_sample_size=30)
        assert new.divergence_offset_steps == DIVERGENCE_OFFSET_STEPS_MAX

    def test_update_divergence_state_step_decrement_floored_at_zero(self) -> None:
        prev = StageAControllerState(
            divergence_offset_steps=0, last_a_b_correlation=0.9
        )
        new = update_divergence_state(prev, corr=0.9, corr_sample_size=30)
        assert new.divergence_offset_steps == 0

    def test_update_divergence_state_records_last_correlation(self) -> None:
        prev = StageAControllerState.initial()
        new = update_divergence_state(prev, corr=0.42, corr_sample_size=30)
        assert new.last_a_b_correlation == 0.42

    def test_update_divergence_state_returns_new_instance_not_mutating_prev(
        self,
    ) -> None:
        prev = StageAControllerState(divergence_offset_steps=3, last_a_b_correlation=0.4)
        new = update_divergence_state(prev, corr=0.0, corr_sample_size=30)
        assert prev.divergence_offset_steps == 3
        assert prev.last_a_b_correlation == 0.4
        assert new is not prev

    def test_update_divergence_state_rejects_correlation_outside_unit_interval(
        self,
    ) -> None:
        prev = StageAControllerState.initial()
        with pytest.raises(StageAInputError, match="must be in"):
            update_divergence_state(prev, corr=1.5, corr_sample_size=30)
        with pytest.raises(StageAInputError, match="must be in"):
            update_divergence_state(prev, corr=-1.5, corr_sample_size=30)

    def test_update_divergence_state_low_sample_size_n_below_10_raises_error(
        self,
    ) -> None:
        # 詳細 Round 1 [C2]: n < 10 → ValueError raise
        prev = StageAControllerState.initial()
        with pytest.raises(StageAInputError, match="C7 sample size guard"):
            update_divergence_state(prev, corr=0.3, corr_sample_size=9)
        with pytest.raises(StageAInputError, match="C7 sample size guard"):
            update_divergence_state(prev, corr=0.3, corr_sample_size=0)

    def test_update_divergence_state_inconclusive_sample_size_n_10_to_29_keeps_steps_unchanged(
        self,
    ) -> None:
        # 詳細 Round 1 [C2] / [S2]: 10 <= n < 30 → state.divergence_offset_steps 不変
        prev = StageAControllerState(
            divergence_offset_steps=5, last_a_b_correlation=0.6
        )
        for n in (10, 15, 29):
            new = update_divergence_state(prev, corr=0.1, corr_sample_size=n)
            assert new.divergence_offset_steps == 5  # 不変
            assert new.last_a_b_correlation == 0.1  # 更新

    def test_update_divergence_state_n_below_inconclusive_min_does_not_mutate_step_offset(
        self,
    ) -> None:
        prev = StageAControllerState(
            divergence_offset_steps=5, last_a_b_correlation=None
        )
        with pytest.raises(StageAInputError):
            update_divergence_state(prev, corr=0.1, corr_sample_size=9)
        # prev は変更されていない
        assert prev.divergence_offset_steps == 5
        assert prev.last_a_b_correlation is None

    def test_update_divergence_state_rejects_nan_correlation(self) -> None:
        prev = StageAControllerState.initial()
        with pytest.raises(StageAInputError, match="finite"):
            update_divergence_state(prev, corr=float("nan"), corr_sample_size=30)


# ---------------------------------------------------------------------------
# compute_gate_score
# ---------------------------------------------------------------------------


class TestComputeGateScore:
    def test_gate_score_zero_worst_gap_yields_one(self) -> None:
        cf = _make_canonical_five_result(gate_worst_gap=0.0)
        assert compute_gate_score(cf) == pytest.approx(1.0)

    def test_gate_score_positive_worst_gap_yields_below_one(self) -> None:
        cf = _make_canonical_five_result(gate_worst_gap=0.5)
        assert compute_gate_score(cf) == pytest.approx(1.0 / 1.5)

    def test_gate_score_monotone_decreasing_with_worst_gap(self) -> None:
        cf_a = _make_canonical_five_result(gate_worst_gap=0.1)
        cf_b = _make_canonical_five_result(gate_worst_gap=0.5)
        cf_c = _make_canonical_five_result(gate_worst_gap=2.0)
        assert compute_gate_score(cf_a) > compute_gate_score(cf_b) > compute_gate_score(cf_c)


# ---------------------------------------------------------------------------
# is_hard_pass
# ---------------------------------------------------------------------------


class TestIsHardPass:
    def test_is_hard_pass_true_when_feasible_and_trades_above_floor(self) -> None:
        cf = _make_canonical_five_result(is_feasible=True, trade_count=10)
        assert is_hard_pass(cf, trade_count=10) is True

    def test_is_hard_pass_false_when_infeasible_invariant(self) -> None:
        cf = _make_canonical_five_result(is_feasible=False, trade_count=10)
        assert is_hard_pass(cf, trade_count=10) is False

    def test_is_hard_pass_false_when_trades_below_floor(self) -> None:
        cf = _make_canonical_five_result(is_feasible=True, trade_count=1)
        assert is_hard_pass(cf, trade_count=1) is False

    def test_is_hard_pass_false_when_trades_equal_zero(self) -> None:
        cf = _make_canonical_five_result(is_feasible=True, trade_count=0)
        assert is_hard_pass(cf, trade_count=0) is False

    def test_is_hard_pass_at_boundary_trades_equals_two(self) -> None:
        cf = _make_canonical_five_result(is_feasible=True, trade_count=2)
        assert is_hard_pass(cf, trade_count=2) is True


# ---------------------------------------------------------------------------
# select_top_q_force_indices (Round 2 [Critical] / 詳細 Round 1 [W2], [W3])
# ---------------------------------------------------------------------------


class TestSelectTopQForceIndices:
    def test_select_top_q_force_empty_input_returns_empty_set_and_none_threshold(
        self,
    ) -> None:
        # n_hard_pass=0 → 空集合 + threshold_score=None (修正 Round 2 [C])
        a_pass, threshold = select_top_q_force_indices([], q_force=0.15)
        assert a_pass == frozenset()
        assert threshold is None

    def test_select_top_q_force_single_individual_yields_single_pass(self) -> None:
        # n_hard_pass=1, q_force=0.15 → max(1, int(1*0.15))=1
        scores = [(0, 0.9)]
        a_pass, threshold = select_top_q_force_indices(scores, q_force=0.15)
        assert a_pass == frozenset({0})
        assert threshold == pytest.approx(0.9)

    def test_select_top_q_force_returns_top_n_descending_by_score(self) -> None:
        scores = [(i, float(i) / 10) for i in range(10)]  # index 0..9, score 0..0.9
        # q_force=0.30 → target_n = int(10*0.30)=3
        a_pass, threshold = select_top_q_force_indices(scores, q_force=0.30)
        assert a_pass == frozenset({9, 8, 7})  # 上位 3 = index 9, 8, 7
        assert threshold == pytest.approx(0.7)

    def test_select_top_q_force_rounding_uses_floor_with_minimum_one(self) -> None:
        # n_hard_pass=10, q_force=0.15 → int(1.5)=1 (floor with min 1)
        scores = [(i, float(i) / 10) for i in range(10)]
        a_pass, _threshold = select_top_q_force_indices(scores, q_force=0.15)
        assert len(a_pass) == 1
        assert a_pass == frozenset({9})

    def test_select_top_q_force_threshold_score_is_min_selected_score(self) -> None:
        scores = [(0, 0.1), (1, 0.5), (2, 0.9)]
        # q_force=0.40 → target_n=int(3*0.40)=1、 上位 1 = index 2 score 0.9
        a_pass, threshold = select_top_q_force_indices(scores, q_force=0.40)
        assert threshold == pytest.approx(0.9)
        assert a_pass == frozenset({2})

    def test_select_top_q_force_uses_deterministic_tie_break_by_index_ascending(
        self,
    ) -> None:
        # 詳細 Round 1 [W3]: 同 score の場合 index 昇順で選抜される
        # 入力順は意図的に逆向き: index 5,3,1,0 の順で渡しても sort key は (-score, index)
        scores = [(5, 0.5), (3, 0.5), (1, 0.5), (0, 0.5)]
        # q_force=0.40 → target_n=int(4*0.40)=1
        a_pass, threshold = select_top_q_force_indices(scores, q_force=0.40)
        assert a_pass == frozenset({0})  # 同点で index 最小
        assert threshold == pytest.approx(0.5)

        # n=2 を期待する場合、 q_force=0.40 で target_n=int(4*0.40)=1 だが
        # n_hard_pass=8 で確認 (target_n=int(8*0.40)=3、 同点なら index 0,1,2)
        scores2 = [(5, 0.5), (3, 0.5), (1, 0.5), (0, 0.5), (7, 0.5), (6, 0.5), (4, 0.5), (2, 0.5)]
        a_pass2, _ = select_top_q_force_indices(scores2, q_force=0.40)
        # target_n = int(8 * 0.40) = 3、 同点で index 昇順 → 0, 1, 2
        assert a_pass2 == frozenset({0, 1, 2})

    def test_select_top_q_force_rejects_q_force_outside_valid_range(self) -> None:
        # 詳細 Round 1 [W2]: q_force < 0.15 or > 0.40 → StageAInputError
        with pytest.raises(StageAInputError, match="q_force must be in"):
            select_top_q_force_indices([(0, 0.5)], q_force=0.10)
        with pytest.raises(StageAInputError, match="q_force must be in"):
            select_top_q_force_indices([(0, 0.5)], q_force=0.50)

    def test_select_top_q_force_rejects_nan_q_force(self) -> None:
        with pytest.raises(StageAInputError, match="finite"):
            select_top_q_force_indices([(0, 0.5)], q_force=float("nan"))


# ---------------------------------------------------------------------------
# evaluate_generation (top-level、 4 代表ケース + 補助 test)
# ---------------------------------------------------------------------------


class TestEvaluateGeneration:
    def test_evaluate_generation_perfect_run_yields_top_q_force_pass(self) -> None:
        # 代表ケース 1: 全個体 hard_pass、 top 15% が a_pass
        individuals = tuple(_make_individual(i) for i in range(10))
        inputs = StageAGenerationInput(
            generation=0,
            individuals=individuals,
            feasible_ratio_ema=0.5,  # → q_force_base=0.15
        )
        # 各個体に対し、 index に応じて gate_worst_gap が異なる結果を返す
        results_by_index: dict[int, CanonicalFiveResult] = {}
        for i in range(10):
            results_by_index[i] = _make_canonical_five_result(
                is_feasible=True,
                gate_worst_gap=float(9 - i) * 0.1,  # 大きい index ほど gap 小
                trade_count=10,
            )
        call_log: list[int] = []

        def fn(
            trades: object,
            bars: object,
            thresholds: object,
            business_day_universe: object,
            *,
            bucket_validator: object | None = None,
            q_bartlett: int = 5,
        ) -> CanonicalFiveResult:
            idx = len(call_log)
            call_log.append(idx)
            return results_by_index[idx]

        state = StageAControllerState.initial()
        result, new_state = evaluate_generation(
            state,
            inputs,
            evaluate_fn=fn,
            live_criteria=_live_criteria(),
        )
        # q_force=0.15 → target_n=int(10*0.15)=1、 上位 1 = index 9 (gap=0.0)
        assert result.a_pass_indices == frozenset({9})
        assert result.stats.n_total == 10
        assert result.stats.n_hard_pass == 10
        assert result.stats.n_selected == 1
        assert result.stats.q_force_base == pytest.approx(0.15)
        assert result.stats.q_force_with_divergence == pytest.approx(0.15)
        assert new_state == state  # state は変更しない

    def test_evaluate_generation_no_hard_pass_yields_empty_a_pass_set(self) -> None:
        # 代表ケース 2: 全個体 infeasible、 a_pass=空、 threshold=None
        individuals = tuple(_make_individual(i) for i in range(5))
        inputs = StageAGenerationInput(
            generation=0,
            individuals=individuals,
            feasible_ratio_ema=0.5,
        )
        cf_infeasible = _make_canonical_five_result(is_feasible=False, trade_count=10)
        fn = _make_eval_fn(default=cf_infeasible)
        state = StageAControllerState.initial()
        result, _ = evaluate_generation(
            state, inputs, evaluate_fn=fn, live_criteria=_live_criteria()
        )
        assert result.a_pass_indices == frozenset()
        assert result.stats.n_hard_pass == 0
        assert result.stats.n_selected == 0
        assert result.stats.threshold_score is None
        assert result.stats.min_selected_score is None
        assert result.stats.max_selected_score is None

    def test_evaluate_generation_low_feasible_ratio_increases_q_force(self) -> None:
        # 代表ケース 3: feasible_ratio_ema=0.05 → q_force_base=0.225 → top 22.5% pass
        # (target_n = int(10*0.225) = 2)
        individuals = tuple(_make_individual(i) for i in range(10))
        inputs = StageAGenerationInput(
            generation=0,
            individuals=individuals,
            feasible_ratio_ema=0.05,
        )
        results_by_index: dict[int, CanonicalFiveResult] = {
            i: _make_canonical_five_result(
                is_feasible=True, gate_worst_gap=float(9 - i) * 0.1, trade_count=10
            )
            for i in range(10)
        }
        call_log: list[int] = []

        def fn(
            trades: object,
            bars: object,
            thresholds: object,
            business_day_universe: object,
            *,
            bucket_validator: object | None = None,
            q_bartlett: int = 5,
        ) -> CanonicalFiveResult:
            idx = len(call_log)
            call_log.append(idx)
            return results_by_index[idx]

        state = StageAControllerState.initial()
        result, _ = evaluate_generation(
            state, inputs, evaluate_fn=fn, live_criteria=_live_criteria()
        )
        assert result.stats.q_force_base == pytest.approx(0.225)
        assert result.stats.q_force_with_divergence == pytest.approx(0.225)
        assert result.stats.n_selected == 2  # int(10 * 0.225) = 2
        assert result.a_pass_indices == frozenset({9, 8})

    def test_evaluate_generation_with_divergence_state_increases_q_force(self) -> None:
        # 代表ケース 4: state.steps=5 → q_force = 0.15 + 0.10 = 0.25
        individuals = tuple(_make_individual(i) for i in range(10))
        inputs = StageAGenerationInput(
            generation=0,
            individuals=individuals,
            feasible_ratio_ema=0.5,  # base=0.15
        )
        cf_pass = _make_canonical_five_result(is_feasible=True, trade_count=10)
        fn = _make_eval_fn(default=cf_pass)
        state = StageAControllerState(divergence_offset_steps=5, last_a_b_correlation=0.3)
        result, new_state = evaluate_generation(
            state, inputs, evaluate_fn=fn, live_criteria=_live_criteria()
        )
        assert result.stats.q_force_base == pytest.approx(0.15)
        assert result.stats.q_force_with_divergence == pytest.approx(0.25)
        # target_n = int(10 * 0.25) = 2
        assert result.stats.n_selected == 2
        assert result.stats.divergence_offset_steps == 5
        assert new_state == state

    def test_evaluate_generation_returns_state_unchanged(self) -> None:
        # state は本関数で変更しない
        individuals = (_make_individual(0),)
        inputs = StageAGenerationInput(
            generation=0,
            individuals=individuals,
            feasible_ratio_ema=0.5,
        )
        cf = _make_canonical_five_result(is_feasible=True, trade_count=10)
        fn = _make_eval_fn(default=cf)
        state = StageAControllerState(
            divergence_offset_steps=3, last_a_b_correlation=0.4
        )
        _, new_state = evaluate_generation(
            state, inputs, evaluate_fn=fn, live_criteria=_live_criteria()
        )
        assert new_state is state

    def test_evaluate_generation_rejects_individuals_with_inconsistent_index(
        self,
    ) -> None:
        # Round 2 [S1] index 安定性
        bad = _make_individual(index=99)  # i=0 の位置に index=99 を入れる
        with pytest.raises(StageAInputError, match="must equal i"):
            StageAGenerationInput(
                generation=0,
                individuals=(bad,),
                feasible_ratio_ema=0.5,
            )

    def test_evaluate_generation_uses_evaluate_fn_dependency_injection(self) -> None:
        # mock evaluate_fn で deterministic 動作確認
        individuals = (_make_individual(0),)
        inputs = StageAGenerationInput(
            generation=0,
            individuals=individuals,
            feasible_ratio_ema=0.5,
        )
        call_count = 0
        cf = _make_canonical_five_result(is_feasible=True, trade_count=10)

        def fn(
            trades: object,
            bars: object,
            thresholds: object,
            business_day_universe: object,
            *,
            bucket_validator: object | None = None,
            q_bartlett: int = 5,
        ) -> CanonicalFiveResult:
            nonlocal call_count
            call_count += 1
            return cf

        state = StageAControllerState.initial()
        evaluate_generation(
            state, inputs, evaluate_fn=fn, live_criteria=_live_criteria()
        )
        assert call_count == 1


# ---------------------------------------------------------------------------
# Saturation + Recovery (Round 3 [S1])
# ---------------------------------------------------------------------------


class TestSaturationAndRecovery:
    def test_q_force_divergence_cap_saturation_then_recovery(self) -> None:
        """シミュレーション: corr<0.5 を N 回連続 → cap 到達 → corr>=0.5 連続 → 0.02/Run で戻る.

        cap 飽和中の見かけ q_force 不変期間を確認 (Round 3 [W1] 反映).
        """
        state = StageAControllerState.initial()
        # Phase 1: corr<0.5 を 20 回 → MAX で saturate
        for _ in range(20):
            state = update_divergence_state(state, corr=0.0, corr_sample_size=30)
        assert state.divergence_offset_steps == DIVERGENCE_OFFSET_STEPS_MAX

        # Phase 2: 飽和中、 q_force_with_divergence は capped at 0.40
        # base=0.30 (feasible_ratio=0.0)、 0.30 + 0.02*13 = 0.56 → clamp 0.40
        capped = compute_q_force_with_divergence(0.30, state.divergence_offset_steps)
        assert capped == pytest.approx(0.40)

        # 連続 saturation 中も q_force = 0.40 で見かけ上不変
        capped2 = compute_q_force_with_divergence(
            0.30, min(state.divergence_offset_steps, DIVERGENCE_OFFSET_STEPS_MAX)
        )
        assert capped2 == pytest.approx(0.40)

        # Phase 3: corr>=0.5 連続 → 0.02/Run で回復
        for _ in range(5):
            state = update_divergence_state(state, corr=0.9, corr_sample_size=30)
        assert state.divergence_offset_steps == DIVERGENCE_OFFSET_STEPS_MAX - 5

        # Phase 4: 完全回復
        for _ in range(20):
            state = update_divergence_state(state, corr=0.9, corr_sample_size=30)
        assert state.divergence_offset_steps == 0


# ---------------------------------------------------------------------------
# state immutability (Round 1 [C3])
# ---------------------------------------------------------------------------


class TestStateImmutability:
    def test_state_is_frozen_dataclass_setattr_raises(self) -> None:
        s = StageAControllerState.initial()
        with pytest.raises(FrozenInstanceError):
            s.divergence_offset_steps = 99  # type: ignore[misc]
        with pytest.raises(FrozenInstanceError):
            s.last_a_b_correlation = 0.5  # type: ignore[misc]

    def test_evaluate_generation_does_not_mutate_state_argument(self) -> None:
        individuals = (_make_individual(0),)
        inputs = StageAGenerationInput(
            generation=0,
            individuals=individuals,
            feasible_ratio_ema=0.5,
        )
        fn = _make_eval_fn(default=_make_canonical_five_result(is_feasible=True, trade_count=10))
        state = StageAControllerState(divergence_offset_steps=4, last_a_b_correlation=0.3)
        prev_steps = state.divergence_offset_steps
        prev_corr = state.last_a_b_correlation
        evaluate_generation(state, inputs, evaluate_fn=fn, live_criteria=_live_criteria())
        assert state.divergence_offset_steps == prev_steps
        assert state.last_a_b_correlation == prev_corr

    def test_update_divergence_state_does_not_mutate_prev_state(self) -> None:
        prev = StageAControllerState(divergence_offset_steps=5, last_a_b_correlation=0.2)
        new = update_divergence_state(prev, corr=0.0, corr_sample_size=30)
        assert prev.divergence_offset_steps == 5
        assert prev.last_a_b_correlation == 0.2
        assert new is not prev
        assert new.divergence_offset_steps == 6


# ---------------------------------------------------------------------------
# default-deny 不変条件 (詳細 Round 1 [S3])
# ---------------------------------------------------------------------------


class TestDefaultDenyInvariant:
    def test_stage_a_result_does_not_have_a_fail_indices_field(self) -> None:
        """StageAResult に a_fail_indices field が無いことを assert (default-deny 契約強制)."""
        field_names = {f.name for f in fields(StageAResult)}
        assert "a_fail_indices" not in field_names
        assert "a_pass_indices" in field_names
        assert "stats" in field_names

    def test_evaluate_generation_does_not_emit_a_fail_indices_field(self) -> None:
        """top-level entry が a_fail_indices を返さない (default-deny 契約強制)."""
        individuals = (_make_individual(0),)
        inputs = StageAGenerationInput(
            generation=0,
            individuals=individuals,
            feasible_ratio_ema=0.5,
        )
        fn = _make_eval_fn(default=_make_canonical_five_result(is_feasible=True, trade_count=10))
        state = StageAControllerState.initial()
        result, _ = evaluate_generation(
            state, inputs, evaluate_fn=fn, live_criteria=_live_criteria()
        )
        # 反転の補集合を caller が暗黙に扱う設計
        assert hasattr(result, "a_pass_indices")
        assert not hasattr(result, "a_fail_indices")


# ---------------------------------------------------------------------------
# state 単一情報源 (詳細 Round 1 [C1])
# ---------------------------------------------------------------------------


class TestStateSingleSourceOfTruth:
    def test_stage_a_generation_input_does_not_have_state_field(self) -> None:
        """StageAGenerationInput に state field が無いことを assert (single source of truth)."""
        field_names = {f.name for f in fields(StageAGenerationInput)}
        assert "state" not in field_names
        assert "generation" in field_names
        assert "individuals" in field_names
        assert "feasible_ratio_ema" in field_names

    def test_evaluate_generation_takes_state_only_via_first_argument(self) -> None:
        """state は evaluate_generation の引数 (= 第 1 positional) のみで受け取る."""
        import inspect
        sig = inspect.signature(evaluate_generation)
        params = list(sig.parameters.values())
        assert params[0].name == "state"
        assert params[0].kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.POSITIONAL_ONLY,
        )
        # inputs は state 以外の経路では存在しない
        assert "state" in {p.name for p in params}


# ---------------------------------------------------------------------------
# bucket_validator 配線 (詳細 Round 1 [W1])
# ---------------------------------------------------------------------------


class TestBucketValidatorWiring:
    def test_evaluate_generation_passes_bucket_validator_to_evaluate_fn(self) -> None:
        """evaluate_fn に bucket_validator が keyword arg で渡されることを mock で確認."""

        class _DummyProvider(SessionBucketBoundaryProvider):
            @property
            def version(self) -> str:
                return "test_provider_v1"

            def expected_bucket(self, exit_time_utc: object) -> SessionBucket:  # type: ignore[override]
                return SessionBucket.TOKYO

            def expected_business_day_index(self, exit_time_utc: object) -> int:  # type: ignore[override]
                return 0

        provider = _DummyProvider()
        captured: dict[str, object] = {}

        def fn(
            trades: object,
            bars: object,
            thresholds: object,
            business_day_universe: object,
            *,
            bucket_validator: object | None = None,
            q_bartlett: int = 5,
        ) -> CanonicalFiveResult:
            captured["bucket_validator"] = bucket_validator
            return _make_canonical_five_result(is_feasible=True, trade_count=10)

        individuals = (_make_individual(0),)
        inputs = StageAGenerationInput(
            generation=0,
            individuals=individuals,
            feasible_ratio_ema=0.5,
        )
        state = StageAControllerState.initial()
        evaluate_generation(
            state,
            inputs,
            evaluate_fn=fn,
            live_criteria=_live_criteria(),
            bucket_validator=provider,
        )
        assert captured["bucket_validator"] is provider

    def test_evaluate_generation_passes_none_validator_when_omitted(self) -> None:
        captured: dict[str, object | None] = {"bucket_validator": "sentinel"}

        def fn(
            trades: object,
            bars: object,
            thresholds: object,
            business_day_universe: object,
            *,
            bucket_validator: object | None = None,
            q_bartlett: int = 5,
        ) -> CanonicalFiveResult:
            captured["bucket_validator"] = bucket_validator
            return _make_canonical_five_result(is_feasible=True, trade_count=10)

        individuals = (_make_individual(0),)
        inputs = StageAGenerationInput(
            generation=0,
            individuals=individuals,
            feasible_ratio_ema=0.5,
        )
        state = StageAControllerState.initial()
        evaluate_generation(
            state, inputs, evaluate_fn=fn, live_criteria=_live_criteria()
        )
        assert captured["bucket_validator"] is None
