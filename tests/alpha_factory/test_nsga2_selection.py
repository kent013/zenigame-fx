"""T065: NSGA-II core + 主選抜 (B-pooled) — 振る舞いベース test.

詳細設計: ``devnotes/20260430-1100-todo-T065-nsga2-core-and-main-selection/detailed-design.md``

Test 計画 (詳細設計 § 施策 2、 13 sub-suite):

- 2.1 PR DoD 必須 (handoff § 3.2 + 概念設計 § 7.2)
- 2.2 ParetoAxis / extract_pareto_axis (Round 1 [S3] / [C3])
- 2.3 compute_effective_constraint_violation (Round 1 [C2])
- 2.4 constrained_dominates (Deb 2000)
- 2.5 non_dominated_sort
- 2.6 crowding_distance (Round 1 [W5] / [C3])
- 2.7 select_survivors (Round 1 [W3])
- 2.8 binary_tournament (Round 2 [Critical] crowded-comparison only)
- 2.9 select_parent_pair
- 2.10 run_generation_selection (top-level)
- 2.11 Determinism (Round 1 [C1] / 詳細 Round 1 [C2])
- 2.12 GenerationSelectionResult immutability
- 2.13 sample_size_warnings 列挙 (Round 1 [W4] operational)
"""

from __future__ import annotations

import inspect
import math
import random
import types
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from src.alpha_factory.canonical_metrics import (
    BarEquityPoint,
    BarEquitySeries,
    CanonicalFiveResult,
    InvariantFlags,
    SessionBucket,
)
from src.alpha_factory.mission_inf_gap import MissionGapResult
from src.alpha_factory.nsga2_selection import (
    INVARIANT_VIOLATION_PENALTY,
    GenerationSelectionResult,
    IndividualEvaluation,
    ParetoAxis,
    binary_tournament,
    compute_effective_constraint_violation,
    constrained_dominates,
    crowding_distance,
    extract_pareto_axis,
    make_selection_seed,
    non_dominated_sort,
    run_generation_selection,
    select_parent_pair,
    select_survivors,
)
from src.alpha_factory.stage_bc_evaluator import (
    BCEvaluationResult,
    MissionFailReason,
    SampleSizeFlag,
    StageBResult,
    StageCLiteResult,
    StageCResult,
    StagePassStatus,
)

# ---------------------------------------------------------------------------
# Builders / fixtures
# ---------------------------------------------------------------------------


def _make_invariants(
    *,
    session_close_drop_count: int = 0,
    negative_equity_drop_open_count: int = 0,
) -> InvariantFlags:
    return InvariantFlags(
        session_close_drop_count=session_close_drop_count,
        negative_equity_drop_open_count=negative_equity_drop_open_count,
        infeasible_reason_codes=frozenset(),
    )


def _make_canonical_five(
    *,
    net_pnl: float = 1000.0,
    max_dd: float = 0.05,
    invariants: InvariantFlags | None = None,
) -> CanonicalFiveResult:
    if invariants is None:
        invariants = _make_invariants()
    return CanonicalFiveResult(
        sr_session_worst_block_scale=0.1,
        sr_session_worst_annual_estimate=0.1 * math.sqrt(756),
        net_pnl_after_cost=net_pnl,
        max_dd=max_dd,
        trade_count=200,
        session_block_win_rate_worst=0.55,
        per_bucket_sr={b: 0.1 for b in SessionBucket},
        per_bucket_wr={b: 0.55 for b in SessionBucket},
        low_sample_buckets=frozenset(),
        slack_sharpe=0.1,
        slack_pnl=0.1,
        slack_dd=0.1,
        slack_tc=0.1,
        slack_wr=0.1,
        gate_worst_gap=0.0,
        gate_pass=True,
        log_pf_clip=0.5,
        bucket_validator_version="unvalidated",
        invariants=invariants,
    )


def _make_mission_gap(
    *,
    mission_inf_gap: float = 0.0,
    constraint_violation: float = 0.0,
    is_feasible: bool = True,
) -> MissionGapResult:
    return MissionGapResult(
        mission_inf_gap=mission_inf_gap,
        constraint_violation=constraint_violation,
        mission_margin=-mission_inf_gap,
        mission_signed_margin=0.1 if is_feasible else float("-inf"),
        per_metric_shortfall=types.MappingProxyType(
            {"sharpe": 0.0, "pnl": 0.0, "dd": 0.0, "tc": 0.0}
        ),
        is_feasible=is_feasible,
    )


_DEFAULT_BARS = BarEquitySeries(
    points=(
        BarEquityPoint(timestamp_utc=datetime(2025, 1, 1, tzinfo=UTC), equity=10000.0),
        BarEquityPoint(
            timestamp_utc=datetime(2025, 1, 1, tzinfo=UTC) + timedelta(hours=1),
            equity=10010.0,
        ),
    )
)


def _make_stage_b_result(
    cf: CanonicalFiveResult | None,
    *,
    pooled_dd_per_fold_max: float | None = 0.05,
) -> StageBResult:
    return StageBResult(
        b_pooled_cf_result=cf,
        pooled_dd_per_fold_max=pooled_dd_per_fold_max if cf is not None else None,
        per_fold_results=(),
        is_feasible_invariant=cf is not None,
        is_b_pass=cf is not None,
    )


def _make_stage_c_lite_result() -> StageCLiteResult:
    return StageCLiteResult(
        per_window_results=(),
        cells_worst=0.0,
        mission_pass=StagePassStatus.PENDING,
        progress_pass=StagePassStatus.PENDING,
        sample_size_flag=SampleSizeFlag.OK,
        n_pass_windows=0,
    )


def _make_stage_c_result(cf_pass: bool = True) -> StageCResult:
    cf = _make_canonical_five()
    return StageCResult(
        c_cf_result=cf,
        stress_cf_result=None,
        per_pair_results={},
        live_criteria_pass=cf_pass,
        stress_pass=StagePassStatus.PENDING,
        cross_pair_pass=StagePassStatus.PASS,
        mission_pass=StagePassStatus.PASS if cf_pass else StagePassStatus.FAIL,
        mission_fail_reason=None if cf_pass else MissionFailReason.LIVE_CRITERIA,
        shadow_robustness_score=1.0,
    )


def _make_bc_result(
    *,
    individual_index: int = 0,
    net_pnl: float = 1000.0,
    pooled_dd_per_fold_max: float = 0.05,
    pareto_axis_usable: bool = True,
    invariants: InvariantFlags | None = None,
) -> BCEvaluationResult:
    if pareto_axis_usable:
        cf = _make_canonical_five(net_pnl=net_pnl, invariants=invariants)
        return BCEvaluationResult(
            individual_index=individual_index,
            b_result=_make_stage_b_result(cf, pooled_dd_per_fold_max=pooled_dd_per_fold_max),
            c_lite_result=_make_stage_c_lite_result(),
            c_result=_make_stage_c_result(),
            mission_pass=StagePassStatus.PASS,
            b_pooled_cf=cf,
            pareto_axis_usable=True,
            c_pass_depth=1.0,
        )
    return BCEvaluationResult(
        individual_index=individual_index,
        b_result=_make_stage_b_result(None, pooled_dd_per_fold_max=None),
        c_lite_result=_make_stage_c_lite_result(),
        c_result=_make_stage_c_result(cf_pass=False),
        mission_pass=StagePassStatus.FAIL,
        b_pooled_cf=None,
        pareto_axis_usable=False,
        c_pass_depth=0.0,
    )


def _make_individual(
    *,
    index: int,
    genome_hash: str | None = None,
    stage_a_pass: bool = True,
    bc_result: BCEvaluationResult | None | object = ...,
    mission_inf_gap: float = 0.0,
    constraint_violation: float = 0.0,
    is_feasible: bool = True,
    invariants: InvariantFlags | None = None,
    net_pnl: float = 1000.0,
    pooled_dd_per_fold_max: float = 0.05,
    pareto_axis_usable: bool = True,
) -> IndividualEvaluation:
    if invariants is None:
        invariants = _make_invariants()
    if bc_result is ...:
        if stage_a_pass:
            bc_result = _make_bc_result(
                individual_index=index,
                net_pnl=net_pnl,
                pooled_dd_per_fold_max=pooled_dd_per_fold_max,
                pareto_axis_usable=pareto_axis_usable,
                invariants=invariants,
            )
        else:
            bc_result = None
    if genome_hash is None:
        genome_hash = f"hash_{index:04x}_{'a' * 56}"[:64]
    return IndividualEvaluation(
        index=index,
        genome_hash=genome_hash,
        stage_a_pass=stage_a_pass,
        bc_result=bc_result,  # type: ignore[arg-type]
        mission_gap=_make_mission_gap(
            mission_inf_gap=mission_inf_gap,
            constraint_violation=constraint_violation,
            is_feasible=is_feasible,
        ),
        invariant_flags=invariants,
    )


# ---------------------------------------------------------------------------
# 2.1 PR DoD 必須
# ---------------------------------------------------------------------------


class TestPRDoD:
    def test_a_fail_individual_excluded_from_nsga_selection(self):
        a_pass = _make_individual(index=0)
        a_fail = _make_individual(index=1, stage_a_pass=False)
        population = {0: a_pass, 1: a_fail}
        rng = random.Random(0)
        result = run_generation_selection(population, pop_size=2, rng=rng)
        assert 1 in result.excluded_indices
        assert 1 not in result.survivor_indices
        for p1, p2 in result.parent_pairs:
            assert p1 != 1
            assert p2 != 1

    def test_b_invariant_fail_individual_excluded_from_pareto_axis_source(self):
        a_pass = _make_individual(index=0)
        b_invariant_fail = _make_individual(index=1, pareto_axis_usable=False)
        population = {0: a_pass, 1: b_invariant_fail}
        rng = random.Random(0)
        result = run_generation_selection(population, pop_size=2, rng=rng)
        assert 1 in result.excluded_indices
        assert 1 not in result.survivor_indices
        for p1, p2 in result.parent_pairs:
            assert p1 != 1
            assert p2 != 1


# ---------------------------------------------------------------------------
# 2.2 extract_pareto_axis
# ---------------------------------------------------------------------------


class TestExtractParetoAxis:
    def test_extract_pareto_axis_uses_t064_b_pooled_cf_net_pnl_after_cost(self):
        bc = _make_bc_result(net_pnl=1234.5)
        gap = _make_mission_gap()
        ax = extract_pareto_axis(bc, gap)
        assert ax.net_pnl == 1234.5

    def test_extract_pareto_axis_uses_pooled_dd_per_fold_max_not_concat_dd(self):
        bc = _make_bc_result(pooled_dd_per_fold_max=0.07)
        gap = _make_mission_gap()
        ax = extract_pareto_axis(bc, gap)
        assert ax.max_dd == 0.07
        # b_result.pooled_dd_per_fold_max source であり、 b_pooled_cf.max_dd とは別経路
        assert bc.b_result.pooled_dd_per_fold_max == 0.07

    def test_extract_pareto_axis_uses_t062_mission_inf_gap(self):
        bc = _make_bc_result()
        gap = _make_mission_gap(mission_inf_gap=0.42)
        ax = extract_pareto_axis(bc, gap)
        assert ax.mission_inf_gap == 0.42

    def test_extract_pareto_axis_rejects_b_pooled_cf_max_dd_as_f2_source(self):
        # b_pooled_cf.max_dd (= 0.05 default) と pooled_dd_per_fold_max=0.99 を意図的に分離
        # f2 が pooled_dd_per_fold_max 由来であることを確認
        bc = _make_bc_result(pooled_dd_per_fold_max=0.99)
        gap = _make_mission_gap()
        ax = extract_pareto_axis(bc, gap)
        assert ax.max_dd == 0.99
        assert bc.b_pooled_cf.max_dd != 0.99  # b_pooled_cf.max_dd は別経路 (= 0.05)

    def test_extract_pareto_axis_raises_value_error_when_b_pooled_cf_is_none(self):
        bc = _make_bc_result(pareto_axis_usable=False)
        gap = _make_mission_gap()
        with pytest.raises(ValueError, match="b_pooled_cf"):
            extract_pareto_axis(bc, gap)

    def test_extract_pareto_axis_raises_value_error_on_non_finite_net_pnl(self):
        bc = _make_bc_result()
        bc = replace(bc, b_pooled_cf=replace(bc.b_pooled_cf, net_pnl_after_cost=float("inf")))
        gap = _make_mission_gap()
        with pytest.raises(ValueError, match="net_pnl"):
            extract_pareto_axis(bc, gap)

    def test_extract_pareto_axis_raises_value_error_on_non_finite_max_dd(self):
        bc = _make_bc_result()
        # pooled_dd_per_fold_max は b_result 内、 NaN に差し替え
        bc = replace(bc, b_result=replace(bc.b_result, pooled_dd_per_fold_max=float("nan")))
        gap = _make_mission_gap()
        with pytest.raises(ValueError, match="max_dd"):
            extract_pareto_axis(bc, gap)

    def test_extract_pareto_axis_raises_value_error_on_non_finite_mission_inf_gap(self):
        bc = _make_bc_result()
        gap = _make_mission_gap()
        gap = replace(gap, mission_inf_gap=float("inf"))
        with pytest.raises(ValueError, match="mission_inf_gap"):
            extract_pareto_axis(bc, gap)


# ---------------------------------------------------------------------------
# 2.3 compute_effective_constraint_violation
# ---------------------------------------------------------------------------


class TestEffectiveConstraintViolation:
    def test_zero_when_fully_feasible(self):
        gap = _make_mission_gap(constraint_violation=0.0)
        inv = _make_invariants()
        assert compute_effective_constraint_violation(gap, inv) == 0.0

    def test_invariant_violation_dominates_slack(self):
        gap = _make_mission_gap(constraint_violation=10.0)
        inv = _make_invariants(session_close_drop_count=1)
        result = compute_effective_constraint_violation(gap, inv)
        assert result == 10.0 + INVARIANT_VIOLATION_PENALTY
        # invariant 1 件 = どんな slack 由来 violation (上界 ~1e2) より大きい
        assert result > 1.0e3  # 上界目安 1.0e2 を圧倒

    def test_raises_value_error_on_inf_constraint_violation(self):
        gap = _make_mission_gap(constraint_violation=float("inf"))
        inv = _make_invariants()
        with pytest.raises(ValueError, match="constraint_violation"):
            compute_effective_constraint_violation(gap, inv)

    def test_raises_value_error_on_negative_invariant_count(self):
        gap = _make_mission_gap(constraint_violation=0.0)
        # Bypass dataclass __post_init__ により直接 negative count を作るのは難しいので
        # types.SimpleNamespace で代替
        import types as _types

        fake_inv = _types.SimpleNamespace(
            session_close_drop_count=-1,
            negative_equity_drop_open_count=0,
        )
        with pytest.raises(ValueError, match="invariant_count"):
            compute_effective_constraint_violation(gap, fake_inv)  # type: ignore[arg-type]

    def test_session_close_drop_count_increases_violation(self):
        gap = _make_mission_gap(constraint_violation=0.0)
        inv = _make_invariants(session_close_drop_count=2)
        result = compute_effective_constraint_violation(gap, inv)
        assert result == 2 * INVARIANT_VIOLATION_PENALTY

    def test_negative_equity_drop_open_count_increases_violation(self):
        gap = _make_mission_gap(constraint_violation=0.0)
        inv = _make_invariants(negative_equity_drop_open_count=3)
        result = compute_effective_constraint_violation(gap, inv)
        assert result == 3 * INVARIANT_VIOLATION_PENALTY


# ---------------------------------------------------------------------------
# 2.4 constrained_dominates
# ---------------------------------------------------------------------------


class TestConstrainedDominates:
    def _ax(self, net_pnl=100.0, max_dd=0.05, mig=0.0):
        return ParetoAxis(net_pnl=net_pnl, max_dd=max_dd, mission_inf_gap=mig)

    def test_feasible_vs_infeasible_returns_true(self):
        # feasible (worse axis) ≻ infeasible (better axis)
        assert constrained_dominates(
            self._ax(net_pnl=10),
            self._ax(net_pnl=100),
            p_violation=0.0,
            q_violation=5.0,
            p_feasible=True,
            q_feasible=False,
        )

    def test_infeasible_vs_feasible_returns_false(self):
        assert not constrained_dominates(
            self._ax(net_pnl=100),
            self._ax(net_pnl=10),
            p_violation=5.0,
            q_violation=0.0,
            p_feasible=False,
            q_feasible=True,
        )

    def test_both_feasible_uses_pareto_three_axes(self):
        # p strictly dominates q on all three axes
        p = self._ax(net_pnl=200, max_dd=0.01, mig=0.0)
        q = self._ax(net_pnl=100, max_dd=0.05, mig=0.5)
        assert constrained_dominates(
            p, q,
            p_violation=0.0, q_violation=0.0,
            p_feasible=True, q_feasible=True,
        )
        assert not constrained_dominates(
            q, p,
            p_violation=0.0, q_violation=0.0,
            p_feasible=True, q_feasible=True,
        )

    def test_both_infeasible_smaller_violation_dominates(self):
        assert constrained_dominates(
            self._ax(), self._ax(),
            p_violation=1.0, q_violation=2.0,
            p_feasible=False, q_feasible=False,
        )
        assert not constrained_dominates(
            self._ax(), self._ax(),
            p_violation=2.0, q_violation=1.0,
            p_feasible=False, q_feasible=False,
        )

    def test_equal_violation_returns_false(self):
        # both infeasible, equal violation → neither dominates
        assert not constrained_dominates(
            self._ax(), self._ax(),
            p_violation=1.0, q_violation=1.0,
            p_feasible=False, q_feasible=False,
        )

    def test_equal_pareto_axes_returns_false(self):
        # both feasible, identical axes → not strictly better
        p = self._ax(net_pnl=100, max_dd=0.05, mig=0.0)
        q = self._ax(net_pnl=100, max_dd=0.05, mig=0.0)
        assert not constrained_dominates(
            p, q,
            p_violation=0.0, q_violation=0.0,
            p_feasible=True, q_feasible=True,
        )


# ---------------------------------------------------------------------------
# 2.5 non_dominated_sort
# ---------------------------------------------------------------------------


class TestNonDominatedSort:
    def test_three_axis_separates_pareto_fronts(self):
        # Front 1 = idx 0 (best on net_pnl); Front 2 = idx 1 (dominated)
        axes = {
            0: ParetoAxis(net_pnl=200, max_dd=0.01, mission_inf_gap=0.0),
            1: ParetoAxis(net_pnl=100, max_dd=0.05, mission_inf_gap=0.5),
        }
        violations = {0: 0.0, 1: 0.0}
        feasibility = {0: True, 1: True}
        result = non_dominated_sort([0, 1], axes, violations, feasibility)
        assert result[0] == 1
        assert result[1] == 2

    def test_constrained_domination_propagates(self):
        # feasible vs infeasible: feasible is front 1
        axes = {
            0: ParetoAxis(net_pnl=10, max_dd=0.5, mission_inf_gap=1.0),
            1: ParetoAxis(net_pnl=200, max_dd=0.01, mission_inf_gap=0.0),
        }
        violations = {0: 0.0, 1: 5.0}
        feasibility = {0: True, 1: False}
        result = non_dominated_sort([0, 1], axes, violations, feasibility)
        assert result[0] == 1
        assert result[1] == 2

    def test_single_individual_returns_front_one(self):
        axes = {0: ParetoAxis(net_pnl=10, max_dd=0.05, mission_inf_gap=0.0)}
        violations = {0: 0.0}
        feasibility = {0: True}
        result = non_dominated_sort([0], axes, violations, feasibility)
        assert result == {0: 1}

    def test_all_non_dominated_returns_one_front(self):
        # 3 mutually non-dominated points
        axes = {
            0: ParetoAxis(net_pnl=100, max_dd=0.10, mission_inf_gap=0.0),
            1: ParetoAxis(net_pnl=200, max_dd=0.20, mission_inf_gap=0.5),
            2: ParetoAxis(net_pnl=150, max_dd=0.05, mission_inf_gap=0.3),
        }
        violations = dict.fromkeys([0, 1, 2], 0.0)
        feasibility = dict.fromkeys([0, 1, 2], True)
        result = non_dominated_sort([0, 1, 2], axes, violations, feasibility)
        assert all(v == 1 for v in result.values())

    def test_total_order_assigns_sequential_fronts(self):
        # Strictly dominated chain: 0 dominates 1 dominates 2
        axes = {
            0: ParetoAxis(net_pnl=300, max_dd=0.01, mission_inf_gap=0.0),
            1: ParetoAxis(net_pnl=200, max_dd=0.05, mission_inf_gap=0.5),
            2: ParetoAxis(net_pnl=100, max_dd=0.10, mission_inf_gap=1.0),
        }
        violations = dict.fromkeys([0, 1, 2], 0.0)
        feasibility = dict.fromkeys([0, 1, 2], True)
        result = non_dominated_sort([0, 1, 2], axes, violations, feasibility)
        assert result[0] == 1
        assert result[1] == 2
        assert result[2] == 3

    def test_empty_input_returns_empty_dict(self):
        assert non_dominated_sort([], {}, {}, {}) == {}


# ---------------------------------------------------------------------------
# 2.6 crowding_distance
# ---------------------------------------------------------------------------


class TestCrowdingDistance:
    def test_three_axis_normalized_endpoints_inf(self):
        axes = {
            0: ParetoAxis(net_pnl=100, max_dd=0.01, mission_inf_gap=0.0),
            1: ParetoAxis(net_pnl=150, max_dd=0.05, mission_inf_gap=0.5),
            2: ParetoAxis(net_pnl=200, max_dd=0.10, mission_inf_gap=1.0),
        }
        result = crowding_distance([0, 1, 2], axes)
        # 端点は全軸 sort でも端 → +inf
        assert result[0] == math.inf
        assert result[2] == math.inf
        # 中間は finite
        assert math.isfinite(result[1])

    def test_front_size_one_returns_inf(self):
        axes = {0: ParetoAxis(net_pnl=100, max_dd=0.05, mission_inf_gap=0.0)}
        assert crowding_distance([0], axes) == {0: math.inf}

    def test_front_size_two_all_inf(self):
        axes = {
            0: ParetoAxis(net_pnl=100, max_dd=0.05, mission_inf_gap=0.0),
            1: ParetoAxis(net_pnl=200, max_dd=0.10, mission_inf_gap=0.5),
        }
        result = crowding_distance([0, 1], axes)
        assert result == {0: math.inf, 1: math.inf}

    def test_zero_range_axis_contributes_zero(self):
        # All same net_pnl → that axis contributes 0
        axes = {
            0: ParetoAxis(net_pnl=100, max_dd=0.01, mission_inf_gap=0.0),
            1: ParetoAxis(net_pnl=100, max_dd=0.05, mission_inf_gap=0.5),
            2: ParetoAxis(net_pnl=100, max_dd=0.10, mission_inf_gap=1.0),
        }
        result = crowding_distance([0, 1, 2], axes)
        # 中間 idx=1: max_dd 軸寄与 = (0.10-0.01)/(0.10-0.01) = 1.0、
        # mig 軸寄与 = (1.0-0.0)/(1.0-0.0) = 1.0、 net_pnl 軸寄与 = 0 (range 0)
        assert math.isfinite(result[1])
        assert result[1] == pytest.approx(2.0)

    def test_uniform_distribution_equal_internal_distances(self):
        # 5 points uniform along 1 axis only (others fixed)
        axes = {
            i: ParetoAxis(net_pnl=float(i * 10), max_dd=0.05, mission_inf_gap=0.0)
            for i in range(5)
        }
        result = crowding_distance(list(range(5)), axes)
        # 中間 3 個 (idx 1,2,3) は同じ crowding (uniform spacing)
        # axis range = 40、 各中間の net_pnl 寄与 = (next-prev)/range = 20/40 = 0.5
        # other 2 軸は range 0 (寄与 0)
        assert result[1] == pytest.approx(0.5)
        assert result[2] == pytest.approx(0.5)
        assert result[3] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# 2.7 select_survivors
# ---------------------------------------------------------------------------


class TestSelectSurvivors:
    def test_uses_rank_then_crowding_then_genome_hash(self):
        # 2 体が同 front (mutual non-dominate)、 idx 2 は dominated
        ind0 = _make_individual(index=0, net_pnl=200.0, pooled_dd_per_fold_max=0.10, genome_hash="hash_a")
        ind1 = _make_individual(index=1, net_pnl=100.0, pooled_dd_per_fold_max=0.01, genome_hash="hash_b")
        ind2 = _make_individual(index=2, net_pnl=50.0, pooled_dd_per_fold_max=0.30, genome_hash="hash_c")
        population = {0: ind0, 1: ind1, 2: ind2}
        result = select_survivors(population, target_size=2)
        # Front 1 = {0, 1} (mutual non-dominate), Front 2 = {2}
        # Both 0,1 are endpoints with +inf crowding → tie-broken by genome_hash ascending
        # hash_a < hash_b → idx 0 first
        assert result == (0, 1)

    def test_excludes_a_fail_and_b_invariant_fail(self):
        a_pass = _make_individual(index=0)
        a_fail = _make_individual(index=1, stage_a_pass=False)
        b_inv_fail = _make_individual(index=2, pareto_axis_usable=False)
        population = {0: a_pass, 1: a_fail, 2: b_inv_fail}
        result = select_survivors(population, target_size=10)
        assert result == (0,)

    def test_does_not_require_rng_argument(self):
        sig = inspect.signature(select_survivors)
        assert "rng" not in sig.parameters

    def test_returns_empty_tuple_when_all_excluded(self):
        a_fail = _make_individual(index=0, stage_a_pass=False)
        population = {0: a_fail}
        assert select_survivors(population, target_size=5) == ()

    def test_returns_full_eligible_when_below_target_size(self):
        ind0 = _make_individual(index=0)
        ind1 = _make_individual(index=1)
        population = {0: ind0, 1: ind1}
        result = select_survivors(population, target_size=10)
        assert len(result) == 2
        assert set(result) == {0, 1}

    def test_raises_value_error_on_t064_contract_violation_a_pass_no_bc(self):
        bad = _make_individual(index=0, stage_a_pass=True, bc_result=None)
        with pytest.raises(ValueError, match="a_pass=True but bc_result is None"):
            select_survivors({0: bad}, target_size=1)

    def test_raises_value_error_on_t064_contract_violation_a_fail_with_bc(self):
        bc = _make_bc_result()
        bad = _make_individual(index=0, stage_a_pass=False, bc_result=bc)
        with pytest.raises(ValueError, match="a_fail but bc_result is not None"):
            select_survivors({0: bad}, target_size=1)

    def test_raises_value_error_on_target_size_below_one(self):
        with pytest.raises(ValueError, match="target_size"):
            select_survivors({}, target_size=0)


# ---------------------------------------------------------------------------
# 2.8 binary_tournament
# ---------------------------------------------------------------------------


class TestBinaryTournament:
    def test_deterministic_with_seeded_rng(self):
        sort_keys = {
            0: (1, -10.0, "hash_a", 0),
            1: (1, -5.0, "hash_b", 1),
            2: (2, -10.0, "hash_c", 2),
        }
        survivors = [0, 1, 2]
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        # Run multiple tournaments to check sequence determinism
        seq1 = [binary_tournament(survivors, sort_keys, rng=rng1) for _ in range(10)]
        seq2 = [binary_tournament(survivors, sort_keys, rng=rng2) for _ in range(10)]
        assert seq1 == seq2

    def test_uses_crowded_comparison_operator_not_constrained_domination(self):
        # 違法な ParetoAxis でも sort_keys 経由なら影響なし → tournament は sort_keys lex 比較のみ
        # idx 0: front 1 with high crowding, idx 1: front 1 with low crowding
        sort_keys = {
            0: (1, -100.0, "hash_a", 0),  # 高 crowding
            1: (1, -1.0, "hash_b", 1),    # 低 crowding
        }
        rng = random.Random(0)
        # 確実に両者を引き出す → 何回試行しても idx 0 が勝つ
        winners = {binary_tournament([0, 1], sort_keys, rng=rng) for _ in range(50)}
        # サンプルが両方含む十分な試行で winner は一意 (sort_keys[0] < sort_keys[1])
        assert winners == {0}

    def test_lower_rank_wins_over_higher_rank(self):
        sort_keys = {
            0: (1, 0.0, "h0", 0),  # front 1
            1: (2, -math.inf, "h1", 1),  # front 2 (rank 値は大きい)
        }
        rng = random.Random(0)
        # idx 0 が常に勝つ
        winners = {binary_tournament([0, 1], sort_keys, rng=rng) for _ in range(30)}
        assert winners == {0}

    def test_higher_crowding_wins_when_rank_equal(self):
        sort_keys = {
            0: (1, -100.0, "h0", 0),  # 高 crowding (-100)
            1: (1, -1.0, "h1", 1),    # 低 crowding (-1)
        }
        rng = random.Random(0)
        winners = {binary_tournament([0, 1], sort_keys, rng=rng) for _ in range(30)}
        assert winners == {0}

    def test_smaller_genome_hash_wins_when_rank_and_crowding_equal(self):
        sort_keys = {
            0: (1, -1.0, "hash_a", 0),
            1: (1, -1.0, "hash_z", 1),
        }
        rng = random.Random(0)
        winners = {binary_tournament([0, 1], sort_keys, rng=rng) for _ in range(30)}
        assert winners == {0}


# ---------------------------------------------------------------------------
# 2.9 select_parent_pair
# ---------------------------------------------------------------------------


class TestSelectParentPair:
    def test_avoids_self_mating_within_max_retry(self):
        # 2 different genome hashes, ample retries → must select distinct genomes
        ind0 = _make_individual(index=0, genome_hash="hash_a")
        ind1 = _make_individual(index=1, genome_hash="hash_b")
        evals = {0: ind0, 1: ind1}
        sort_keys = {
            0: (1, -1.0, "hash_a", 0),
            1: (1, -1.0, "hash_b", 1),
        }
        rng = random.Random(0)
        # rng.sample で常に [0, 1] 抽出、 distinct hash → (p1, p2) は genome 異
        for _ in range(20):
            p1, p2 = select_parent_pair([0, 1], evals, sort_keys, rng=rng, max_retry=3)
            # 両者 genome が異なるか、 fallback の (p1, p1)
            if p1 != p2:
                assert evals[p1].genome_hash != evals[p2].genome_hash

    def test_falls_back_to_self_when_pool_exhausted(self):
        # 全員同じ genome hash → fallback (p1, p1)
        ind0 = _make_individual(index=0, genome_hash="hash_dup")
        ind1 = _make_individual(index=1, genome_hash="hash_dup")
        evals = {0: ind0, 1: ind1}
        sort_keys = {
            0: (1, -1.0, "hash_dup", 0),
            1: (1, -1.0, "hash_dup", 1),
        }
        rng = random.Random(0)
        p1, p2 = select_parent_pair([0, 1], evals, sort_keys, rng=rng, max_retry=3)
        assert p1 == p2

    def test_uses_sort_keys_for_tournament_not_re_evaluating(self):
        # binary_tournament は sort_keys lex 比較のみ
        ind0 = _make_individual(index=0, genome_hash="hash_a")
        ind1 = _make_individual(index=1, genome_hash="hash_b")
        evals = {0: ind0, 1: ind1}
        # sort_keys を意図的に flipped (idx 0 が「悪い」 ように)
        sort_keys = {
            0: (2, 0.0, "hash_a", 0),  # rank 2 (悪)
            1: (1, 0.0, "hash_b", 1),  # rank 1 (優)
        }
        rng = random.Random(0)
        p1, _ = select_parent_pair([0, 1], evals, sort_keys, rng=rng, max_retry=3)
        # rank 1 の idx 1 が p1 として勝つ
        assert p1 == 1

    def test_deterministic_with_seeded_rng(self):
        ind0 = _make_individual(index=0, genome_hash="hash_a")
        ind1 = _make_individual(index=1, genome_hash="hash_b")
        ind2 = _make_individual(index=2, genome_hash="hash_c")
        evals = {0: ind0, 1: ind1, 2: ind2}
        sort_keys = {
            0: (1, -3.0, "hash_a", 0),
            1: (1, -2.0, "hash_b", 1),
            2: (1, -1.0, "hash_c", 2),
        }
        rng1 = random.Random(7)
        rng2 = random.Random(7)
        seq1 = [select_parent_pair([0, 1, 2], evals, sort_keys, rng=rng1) for _ in range(10)]
        seq2 = [select_parent_pair([0, 1, 2], evals, sort_keys, rng=rng2) for _ in range(10)]
        assert seq1 == seq2

    def test_single_survivor_returns_self_pair(self):
        ind0 = _make_individual(index=0)
        evals = {0: ind0}
        sort_keys = {0: (1, -1.0, "hash_a", 0)}
        rng = random.Random(0)
        p1, p2 = select_parent_pair([0], evals, sort_keys, rng=rng)
        assert p1 == 0
        assert p2 == 0

    def test_empty_survivors_raises_value_error(self):
        rng = random.Random(0)
        with pytest.raises(ValueError, match="non-empty survivors"):
            select_parent_pair([], {}, {}, rng=rng)

    def test_duplicate_genome_hash_falls_back_to_self_pair(self):
        # 3 体すべて duplicate genome hash → fallback
        ind0 = _make_individual(index=0, genome_hash="dup")
        ind1 = _make_individual(index=1, genome_hash="dup")
        ind2 = _make_individual(index=2, genome_hash="dup")
        evals = {0: ind0, 1: ind1, 2: ind2}
        sort_keys = {
            0: (1, -1.0, "dup", 0),
            1: (1, -1.0, "dup", 1),
            2: (1, -1.0, "dup", 2),
        }
        rng = random.Random(0)
        p1, p2 = select_parent_pair([0, 1, 2], evals, sort_keys, rng=rng, max_retry=3)
        assert p1 == p2


# ---------------------------------------------------------------------------
# 2.10 run_generation_selection
# ---------------------------------------------------------------------------


class TestRunGenerationSelection:
    def test_eligible_set_empty_warns_and_returns_empty(self):
        a_fail = _make_individual(index=0, stage_a_pass=False)
        population = {0: a_fail}
        rng = random.Random(0)
        result = run_generation_selection(population, pop_size=2, rng=rng)
        assert result.survivor_indices == ()
        assert result.parent_pairs == ()
        assert "eligible_set_empty" in result.sample_size_warnings
        assert result.excluded_indices == frozenset({0})

    def test_eligible_below_pop_size_warns(self):
        ind0 = _make_individual(index=0)
        ind1 = _make_individual(index=1)
        population = {0: ind0, 1: ind1}
        rng = random.Random(0)
        result = run_generation_selection(population, pop_size=5, rng=rng)
        # eligible=2 < pop_size=5
        assert any("below_pop_size" in w for w in result.sample_size_warnings)

    def test_single_eligible_uses_self_mating_fallback(self):
        ind0 = _make_individual(index=0)
        a_fail = _make_individual(index=1, stage_a_pass=False)
        population = {0: ind0, 1: a_fail}
        rng = random.Random(0)
        result = run_generation_selection(population, pop_size=4, rng=rng)
        assert result.survivor_indices == (0,)
        # All parent pairs are (0, 0)
        for pair in result.parent_pairs:
            assert pair == (0, 0)
        assert len(result.parent_pairs) == 4

    def test_all_infeasible_uses_violation_ordering(self):
        # 3 infeasible individuals with different violations
        ind0 = _make_individual(
            index=0, mission_inf_gap=0.5, constraint_violation=0.5, is_feasible=False,
        )
        ind1 = _make_individual(
            index=1, mission_inf_gap=0.1, constraint_violation=0.1, is_feasible=False,
        )
        ind2 = _make_individual(
            index=2, mission_inf_gap=1.0, constraint_violation=1.0, is_feasible=False,
        )
        population = {0: ind0, 1: ind1, 2: ind2}
        rng = random.Random(0)
        result = run_generation_selection(population, pop_size=3, rng=rng)
        # ind1 (violation 0.1) は front 1、 ind0 (0.5) は front 2、 ind2 (1.0) は front 3
        assert result.front_assignments[1] == 1
        assert result.front_assignments[0] == 2
        assert result.front_assignments[2] == 3
        assert "no_feasible_individuals" in result.sample_size_warnings

    def test_parent_pairs_length_equals_pop_size(self):
        ind0 = _make_individual(index=0, genome_hash="hash_a")
        ind1 = _make_individual(index=1, genome_hash="hash_b")
        population = {0: ind0, 1: ind1}
        rng = random.Random(0)
        result = run_generation_selection(population, pop_size=10, rng=rng)
        assert len(result.parent_pairs) == 10

    def test_excluded_indices_complement_eligible(self):
        ind0 = _make_individual(index=0)
        ind1 = _make_individual(index=1, stage_a_pass=False)
        ind2 = _make_individual(index=2, pareto_axis_usable=False)
        population = {0: ind0, 1: ind1, 2: ind2}
        rng = random.Random(0)
        result = run_generation_selection(population, pop_size=3, rng=rng)
        assert result.excluded_indices == frozenset({1, 2})
        assert 0 not in result.excluded_indices

    def test_raises_value_error_on_pop_size_below_one(self):
        ind0 = _make_individual(index=0)
        rng = random.Random(0)
        with pytest.raises(ValueError, match="pop_size"):
            run_generation_selection({0: ind0}, pop_size=0, rng=rng)

    def test_raises_value_error_on_empty_population(self):
        rng = random.Random(0)
        with pytest.raises(ValueError, match="non-empty"):
            run_generation_selection({}, pop_size=2, rng=rng)

    def test_raises_value_error_on_t064_contract_violation_a_pass_no_bc(self):
        bad = _make_individual(index=0, stage_a_pass=True, bc_result=None)
        rng = random.Random(0)
        with pytest.raises(ValueError, match="a_pass=True but bc_result is None"):
            run_generation_selection({0: bad}, pop_size=1, rng=rng)

    def test_raises_value_error_on_t064_contract_violation_a_fail_with_bc(self):
        bc = _make_bc_result()
        bad = _make_individual(index=0, stage_a_pass=False, bc_result=bc)
        rng = random.Random(0)
        with pytest.raises(ValueError, match="a_fail but bc_result is not None"):
            run_generation_selection({0: bad}, pop_size=1, rng=rng)


# ---------------------------------------------------------------------------
# 2.11 Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_run_generation_selection_same_seed_same_result_byte_for_byte(self):
        ind0 = _make_individual(index=0, genome_hash="hash_a")
        ind1 = _make_individual(index=1, genome_hash="hash_b")
        ind2 = _make_individual(index=2, genome_hash="hash_c")
        population = {0: ind0, 1: ind1, 2: ind2}
        seed = make_selection_seed("run_test", 0)
        r1 = run_generation_selection(population, pop_size=3, rng=random.Random(seed))
        r2 = run_generation_selection(population, pop_size=3, rng=random.Random(seed))
        assert r1.survivor_indices == r2.survivor_indices
        assert r1.parent_pairs == r2.parent_pairs
        assert dict(r1.front_assignments) == dict(r2.front_assignments)
        assert dict(r1.crowding_distances) == dict(r2.crowding_distances)

    def test_run_generation_selection_different_seed_different_result(self):
        # 大きな pop で異なる seed なら parent_pairs シーケンスが異なる
        inds = {
            i: _make_individual(
                index=i,
                genome_hash=f"hash_{i:04d}",
                net_pnl=100.0 + i,
                pooled_dd_per_fold_max=0.05 + i * 0.001,
            )
            for i in range(10)
        }
        r1 = run_generation_selection(inds, pop_size=10, rng=random.Random(1))
        r2 = run_generation_selection(inds, pop_size=10, rng=random.Random(2))
        # survivor_indices は deterministic (rng 不要) なので同じ
        assert r1.survivor_indices == r2.survivor_indices
        # parent_pairs は rng 依存なので異なる可能性が高い
        assert r1.parent_pairs != r2.parent_pairs

    def test_make_selection_seed_uses_blake2b_not_python_hash(self):
        # blake2b hash output range should be 0 to 2^64-1
        seed = make_selection_seed("run_x", 5)
        assert 0 <= seed < 2**64
        # Python hash() would be process-salt dependent, but blake2b is stable
        # Thus calling twice yields exactly same result (process-salt independent)
        seed2 = make_selection_seed("run_x", 5)
        assert seed == seed2

    def test_make_selection_seed_run_id_change_changes_seed(self):
        s1 = make_selection_seed("run_a", 0)
        s2 = make_selection_seed("run_b", 0)
        assert s1 != s2

    def test_make_selection_seed_gen_no_change_changes_seed(self):
        s1 = make_selection_seed("run_a", 0)
        s2 = make_selection_seed("run_a", 1)
        assert s1 != s2

    def test_make_selection_seed_run_id_with_pipe_does_not_collide(self):
        # JSON serialization avoids "|" delimiter collision
        s1 = make_selection_seed("run|a", 0)
        s2 = make_selection_seed("run", 0)  # potential collision under "|" delimiter
        assert s1 != s2

    def test_make_selection_seed_returns_unsigned_64bit_integer(self):
        seed = make_selection_seed("run_x", 0)
        assert isinstance(seed, int)
        assert 0 <= seed < 2**64

    def test_run_generation_selection_population_iteration_order_does_not_affect_result(self):
        # Same individuals, different dict insertion orders → same result (eligible sorted internally)
        ind0 = _make_individual(index=0, genome_hash="hash_a")
        ind1 = _make_individual(index=1, genome_hash="hash_b")
        ind2 = _make_individual(index=2, genome_hash="hash_c")
        pop_a = {0: ind0, 1: ind1, 2: ind2}
        pop_b = {2: ind2, 0: ind0, 1: ind1}
        seed = 42
        r_a = run_generation_selection(pop_a, pop_size=3, rng=random.Random(seed))
        r_b = run_generation_selection(pop_b, pop_size=3, rng=random.Random(seed))
        assert r_a.survivor_indices == r_b.survivor_indices
        assert r_a.parent_pairs == r_b.parent_pairs

    def test_run_generation_selection_duplicate_genome_hash_uses_index_as_final_tiebreak(self):
        # 2 体 front 1 で同じ genome_hash + 同じ Pareto axes (front_size <= 2 → 全員 +inf)
        # → tie-break は genome_hash → index の昇順 (4-tuple 末尾)
        common_kwargs = {
            "genome_hash": "dup",
            "net_pnl": 100.0,
            "pooled_dd_per_fold_max": 0.05,
        }
        ind5 = _make_individual(index=5, **common_kwargs)
        ind3 = _make_individual(index=3, **common_kwargs)
        # population dict insertion order を意図的に逆順に
        population = {5: ind5, 3: ind3}
        rng = random.Random(0)
        result = run_generation_selection(population, pop_size=2, rng=rng)
        # front_size=2 → 全員 +inf crowding、 genome_hash は同じ
        # 最終 tie-break は index → 3 が先 (昇順)
        assert result.survivor_indices == (3, 5)

    def test_run_generation_selection_sort_keys_is_4_tuple_with_index_last(self):
        # 直接 _build_sort_keys を呼び出して 4-tuple であることを確認
        from src.alpha_factory.nsga2_selection import _build_sort_keys
        ind0 = _make_individual(index=0, genome_hash="hash_a")
        population = {0: ind0}
        front_no = {0: 1}
        crowding = {0: math.inf}
        sk = _build_sort_keys([0], front_no, crowding, population)
        assert isinstance(sk[0], tuple)
        assert len(sk[0]) == 4
        # 最後の要素は index
        assert sk[0][3] == 0
        # 2 番目は -crowding
        assert sk[0][1] == -math.inf
        # 3 番目は genome_hash
        assert sk[0][2] == "hash_a"

    def test_individual_evaluation_index_must_match_population_dict_key(self):
        # index 不一致で fail-fast (詳細 Round 2 [W3])
        ind = _make_individual(index=0)
        # population dict key は 99 だが ev.index=0 → mismatch
        bad_population = {99: ind}
        rng = random.Random(0)
        with pytest.raises(ValueError, match="must match population dict key"):
            run_generation_selection(bad_population, pop_size=1, rng=rng)

    def test_run_generation_selection_population_with_inconsistent_index_value_raises_value_error(self):
        # 重複した index field を持つ 2 体 → caller bug
        ind_a = _make_individual(index=0)
        ind_b = _make_individual(index=0)  # 同じ index!
        bad_population = {0: ind_a, 1: ind_b}
        rng = random.Random(0)
        with pytest.raises(ValueError, match="must match population dict key"):
            run_generation_selection(bad_population, pop_size=2, rng=rng)


# ---------------------------------------------------------------------------
# 2.12 GenerationSelectionResult immutability
# ---------------------------------------------------------------------------


class TestImmutability:
    def _build(self) -> GenerationSelectionResult:
        ind0 = _make_individual(index=0)
        rng = random.Random(0)
        return run_generation_selection({0: ind0}, pop_size=1, rng=rng)

    def test_front_assignments_is_mapping_proxy(self):
        result = self._build()
        assert isinstance(result.front_assignments, types.MappingProxyType)
        with pytest.raises(TypeError):
            result.front_assignments[42] = 99  # type: ignore[index]

    def test_crowding_distances_is_mapping_proxy(self):
        result = self._build()
        assert isinstance(result.crowding_distances, types.MappingProxyType)
        with pytest.raises(TypeError):
            result.crowding_distances[42] = 0.5  # type: ignore[index]

    def test_excluded_indices_is_frozenset(self):
        result = self._build()
        assert isinstance(result.excluded_indices, frozenset)

    def test_parent_pairs_is_tuple(self):
        result = self._build()
        assert isinstance(result.parent_pairs, tuple)

    def test_survivor_indices_is_tuple(self):
        result = self._build()
        assert isinstance(result.survivor_indices, tuple)


# ---------------------------------------------------------------------------
# 2.13 sample_size_warnings 列挙
# ---------------------------------------------------------------------------


class TestSampleSizeWarnings:
    def test_eligible_below_thirty_emits_operational_threshold_warning(self):
        # eligible=20 (< 30)
        inds = {i: _make_individual(index=i, genome_hash=f"h_{i:04d}") for i in range(20)}
        rng = random.Random(0)
        result = run_generation_selection(inds, pop_size=20, rng=rng)
        assert "eligible_below_operational_threshold" in result.sample_size_warnings

    def test_eligible_below_ten_emits_critically_low_warning(self):
        inds = {i: _make_individual(index=i, genome_hash=f"h_{i:04d}") for i in range(5)}
        rng = random.Random(0)
        result = run_generation_selection(inds, pop_size=5, rng=rng)
        assert "eligible_critically_low" in result.sample_size_warnings
        assert "eligible_below_operational_threshold" in result.sample_size_warnings

    def test_eligible_zero_emits_set_empty_warning(self):
        a_fail = _make_individual(index=0, stage_a_pass=False)
        rng = random.Random(0)
        result = run_generation_selection({0: a_fail}, pop_size=2, rng=rng)
        assert "eligible_set_empty" in result.sample_size_warnings

    def test_no_feasible_individuals_emits_warning(self):
        ind0 = _make_individual(
            index=0, mission_inf_gap=0.5, constraint_violation=0.5, is_feasible=False,
        )
        rng = random.Random(0)
        result = run_generation_selection({0: ind0}, pop_size=1, rng=rng)
        assert "no_feasible_individuals" in result.sample_size_warnings

    def test_warning_codes_independent_of_c7_correlation_guard(self):
        # operational warning は selection 母集団サイズの話、 C7 (相関規律) と独立
        # eligible=15 (< 30) で operational warning は出るが「相関 claim」 ではない
        inds = {i: _make_individual(index=i, genome_hash=f"h_{i:04d}") for i in range(15)}
        rng = random.Random(0)
        result = run_generation_selection(inds, pop_size=15, rng=rng)
        # operational warning が出る
        assert "eligible_below_operational_threshold" in result.sample_size_warnings
        # critically_low は < 10 のみ → 出ない
        assert "eligible_critically_low" not in result.sample_size_warnings
