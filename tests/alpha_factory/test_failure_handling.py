"""T068 PR 1: tests for src/alpha_factory/failure_handling.py.

詳細設計参照:
``devnotes/20260430-1430-todo-T068-failure-handling/detailed-design.md`` § 施策 2.

11 sub-suite × 約 75 件、 builders は本ファイル内で共通化.
"""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from src.alpha_factory.canonical_metrics import (
    BarEquityPoint,
    BarEquitySeries,
    CanonicalFiveResult,
    InfeasibleReasonCode,
    InvariantFlags,
    SessionBucket,
)
from src.alpha_factory.failure_handling import (
    DEGRADED_LOG_PF_CLIP_FLOOR,
    EXCEPTION_MESSAGE_MAX_LENGTH,
    EvaluationOutcome,
    FailureRecord,
    FailureSummary,
    _make_failure_record,
    _truncate_exception_message,
    aggregate_failures,
    build_degraded_bc_result,
    build_degraded_canonical_five,
    build_degraded_mission_gap,
    build_run_failure_summary,
    decide_run_abort,
    evaluate_bc_safe,
    evaluate_canonical_five_safe,
    evaluate_mission_inf_gap_safe,
    validate_finite_bc_result,
    validate_finite_canonical_five,
    validate_finite_mission_gap,
    validate_state_invariant_bc_result,
    validate_state_invariant_canonical_five,
    validate_state_invariant_mission_gap,
)
from src.alpha_factory.mission_inf_gap import MissionGapResult
from src.alpha_factory.stage_bc_evaluator import (
    BCEvaluationResult,
    MissionFailReason,
    SampleSizeFlag,
    StageBFoldResult,
    StageBResult,
    StageCLiteResult,
    StageCLiteWindowResult,
    StageCResult,
    StagePassStatus,
)

# ---------------------------------------------------------------------------
# Builders (test fixtures) — main 実装 SSOT 準拠
# ---------------------------------------------------------------------------


def _make_invariants(*, is_feasible: bool = True) -> InvariantFlags:
    if is_feasible:
        return InvariantFlags(
            session_close_drop_count=0,
            negative_equity_drop_open_count=0,
            infeasible_reason_codes=frozenset(),
        )
    return InvariantFlags(
        session_close_drop_count=0,
        negative_equity_drop_open_count=0,
        infeasible_reason_codes=frozenset(
            {InfeasibleReasonCode.INPUT_EMPTY_TRADE_LIST}
        ),
    )


def _make_cf(
    *,
    is_feasible: bool = True,
    gate_pass: bool | None = None,
    gate_worst_gap: float = 0.0,
    max_dd: float = 0.1,
    slack_sharpe: float = 0.5,
    slack_pnl: float = 0.5,
    slack_dd: float = 0.5,
    slack_tc: float = 0.5,
    slack_wr: float = 0.5,
    log_pf_clip: float = 0.0,
    sr_session_worst_block_scale: float = 0.1,
    sr_session_worst_annual_estimate: float = 2.5,
    net_pnl_after_cost: float = 100000.0,
    session_block_win_rate_worst: float = 0.5,
    trade_count: int = 100,
    per_bucket_sr_value: float = 0.1,
    per_bucket_wr_value: float = 0.5,
) -> CanonicalFiveResult:
    invariants = _make_invariants(is_feasible=is_feasible)
    if gate_pass is None:
        gate_pass = is_feasible and gate_worst_gap <= 1e-9
    return CanonicalFiveResult(
        sr_session_worst_block_scale=sr_session_worst_block_scale,
        sr_session_worst_annual_estimate=sr_session_worst_annual_estimate,
        net_pnl_after_cost=net_pnl_after_cost,
        max_dd=max_dd,
        trade_count=trade_count,
        session_block_win_rate_worst=session_block_win_rate_worst,
        per_bucket_sr={b: per_bucket_sr_value for b in SessionBucket},
        per_bucket_wr={b: per_bucket_wr_value for b in SessionBucket},
        low_sample_buckets=frozenset(),
        slack_sharpe=slack_sharpe,
        slack_pnl=slack_pnl,
        slack_dd=slack_dd,
        slack_tc=slack_tc,
        slack_wr=slack_wr,
        gate_worst_gap=gate_worst_gap,
        gate_pass=gate_pass,
        log_pf_clip=log_pf_clip,
        bucket_validator_version="unvalidated",
        invariants=invariants,
    )


def _make_mg(
    *,
    is_feasible: bool = True,
    mission_inf_gap: float | None = None,
    constraint_violation: float | None = None,
    mission_margin: float | None = None,
    mission_signed_margin: float | None = None,
    per_metric_shortfall: dict[str, float] | None = None,
) -> MissionGapResult:
    if is_feasible:
        mig = 0.0 if mission_inf_gap is None else mission_inf_gap
        cv = 0.0 if constraint_violation is None else constraint_violation
        mm = 0.0 if mission_margin is None else mission_margin
        msm = 0.5 if mission_signed_margin is None else mission_signed_margin
    else:
        mig = math.inf if mission_inf_gap is None else mission_inf_gap
        cv = math.inf if constraint_violation is None else constraint_violation
        mm = -math.inf if mission_margin is None else mission_margin
        msm = -math.inf if mission_signed_margin is None else mission_signed_margin
    if per_metric_shortfall is None:
        pms: dict[str, float] = {}
    else:
        pms = per_metric_shortfall
    return MissionGapResult(
        mission_inf_gap=mig,
        constraint_violation=cv,
        mission_margin=mm,
        mission_signed_margin=msm,
        per_metric_shortfall=MappingProxyType(pms),
        is_feasible=is_feasible,
    )


def _make_bars(num: int = 3) -> BarEquitySeries:
    points = tuple(
        BarEquityPoint(
            timestamp_utc=datetime(2026, 1, 1 + i, tzinfo=UTC), equity=100.0 + i
        )
        for i in range(num)
    )
    return BarEquitySeries(points=points)


def _make_stage_b_result(
    *, b_pooled_cf_result: CanonicalFiveResult | None = None,
    pooled_dd_per_fold_max: float | None = 0.0,
    is_feasible_invariant: bool = True,
    is_b_pass: bool = True,
    fold_cf: CanonicalFiveResult | None = None,
) -> StageBResult:
    if fold_cf is None:
        fold_cf = _make_cf()
    fold = StageBFoldResult(
        fold_index=0,
        fold_period_start=datetime(2026, 1, 1, tzinfo=UTC),
        fold_period_end=datetime(2026, 2, 1, tzinfo=UTC),
        cf_result=fold_cf,
        is_feasible_invariant=True,
    )
    return StageBResult(
        b_pooled_cf_result=b_pooled_cf_result,
        pooled_dd_per_fold_max=pooled_dd_per_fold_max,
        per_fold_results=(fold,),
        is_feasible_invariant=is_feasible_invariant,
        is_b_pass=is_b_pass,
    )


def _make_stage_c_lite_result(
    *,
    cells_worst: float = 0.0,
    mission_pass: StagePassStatus = StagePassStatus.PASS,
    progress_pass: StagePassStatus = StagePassStatus.PASS,
    sample_size_flag: SampleSizeFlag = SampleSizeFlag.OK,
    n_pass_windows: int = 3,
    window_cf: CanonicalFiveResult | None = None,
) -> StageCLiteResult:
    if window_cf is None:
        window_cf = _make_cf(gate_pass=True)
    windows = tuple(
        StageCLiteWindowResult(window_index=i, cf_result=window_cf) for i in range(3)
    )
    return StageCLiteResult(
        per_window_results=windows,
        cells_worst=cells_worst,
        mission_pass=mission_pass,
        progress_pass=progress_pass,
        sample_size_flag=sample_size_flag,
        n_pass_windows=n_pass_windows,
    )


def _make_stage_c_result(
    *,
    c_cf: CanonicalFiveResult | None = None,
    stress_cf: CanonicalFiveResult | None = None,
    per_pair_results: dict[str, CanonicalFiveResult] | None = None,
    live_criteria_pass: bool = True,
    stress_pass: StagePassStatus = StagePassStatus.PENDING,
    cross_pair_pass: StagePassStatus = StagePassStatus.PASS,
    mission_pass: StagePassStatus = StagePassStatus.PASS,
    mission_fail_reason: MissionFailReason | None = None,
    shadow_robustness_score: float | None = 1.0,
) -> StageCResult:
    if c_cf is None:
        c_cf = _make_cf(gate_pass=True)
    if per_pair_results is None:
        per_pair_results = {}
    return StageCResult(
        c_cf_result=c_cf,
        stress_cf_result=stress_cf,
        per_pair_results=per_pair_results,
        live_criteria_pass=live_criteria_pass,
        stress_pass=stress_pass,
        cross_pair_pass=cross_pair_pass,
        mission_pass=mission_pass,
        mission_fail_reason=mission_fail_reason,
        shadow_robustness_score=shadow_robustness_score,
    )


_UNSET: object = object()


def _make_bc_result(
    *,
    individual_index: int = 0,
    mission_pass: StagePassStatus = StagePassStatus.PASS,
    b_pooled_cf: CanonicalFiveResult | None | object = _UNSET,
    pareto_axis_usable: bool | None = None,
    c_pass_depth: float = 1.75,
    b_result: StageBResult | None = None,
    c_lite_result: StageCLiteResult | None = None,
    c_result: StageCResult | None = None,
) -> BCEvaluationResult:
    if b_pooled_cf is _UNSET:
        b_pooled_cf = _make_cf(gate_pass=True)
    # b_pooled_cf may now be CanonicalFiveResult or None (explicit); narrow type
    assert b_pooled_cf is None or isinstance(b_pooled_cf, CanonicalFiveResult)
    if pareto_axis_usable is None:
        pareto_axis_usable = b_pooled_cf is not None
    if b_result is None:
        b_result = _make_stage_b_result(b_pooled_cf_result=b_pooled_cf)
    if c_lite_result is None:
        # mission_pass=PASS は progress_pass=PASS を要求
        c_lite_result = _make_stage_c_lite_result(
            mission_pass=mission_pass if mission_pass != StagePassStatus.FAIL else StagePassStatus.PASS,
            progress_pass=StagePassStatus.PASS,
        )
    if c_result is None:
        c_result = _make_stage_c_result(mission_pass=mission_pass)
    return BCEvaluationResult(
        individual_index=individual_index,
        b_result=b_result,
        c_lite_result=c_lite_result,
        c_result=c_result,
        mission_pass=mission_pass,
        b_pooled_cf=b_pooled_cf,
        pareto_axis_usable=pareto_axis_usable,
        c_pass_depth=c_pass_depth,
    )


def _make_record(
    *,
    genome_id: str = "g0",
    run_id: str = "run-1",
    generation_no: int = 0,
    stage: str = "canonical_five",
    failure_reason: str = "exception_raised",
    exception_class: str | None = "Exception",
    exception_message: str | None = "boom",
) -> FailureRecord:
    return FailureRecord(
        genome_id=genome_id,
        run_id=run_id,
        generation_no=generation_no,
        stage=stage,  # type: ignore[arg-type]
        failure_reason=failure_reason,  # type: ignore[arg-type]
        exception_class=exception_class,
        exception_message=exception_message,
        detected_field=None,
        detected_value=None,
        exception_fingerprint=f"{exception_class}@{stage}:{(exception_message or '')[:80]}",
    )


# ---------------------------------------------------------------------------
# Sub-suite 2.2 — evaluator wrappers
# ---------------------------------------------------------------------------


class TestEvaluateCanonicalFiveSafe:
    def test_returns_outcome_with_none_failure_on_success(self) -> None:
        cf = _make_cf()
        outcome = evaluate_canonical_five_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="canonical_five",
            evaluate_fn=lambda: cf,
        )
        assert outcome.result is cf
        assert outcome.failure_record is None
        assert outcome.should_skip_downstream is False

    def test_value_error_returns_contract_violation(self) -> None:
        def fn() -> CanonicalFiveResult:
            raise ValueError("invalid input")

        outcome = evaluate_canonical_five_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="canonical_five",
            evaluate_fn=fn,
        )
        assert outcome.failure_record is not None
        assert outcome.failure_record.failure_reason == "contract_violation"
        assert outcome.failure_record.exception_class == "ValueError"
        assert outcome.should_skip_downstream is True

    def test_generic_exception_returns_exception_raised(self) -> None:
        def fn() -> CanonicalFiveResult:
            raise RuntimeError("crash")

        outcome = evaluate_canonical_five_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="canonical_five",
            evaluate_fn=fn,
        )
        assert outcome.failure_record is not None
        assert outcome.failure_record.failure_reason == "exception_raised"
        assert outcome.failure_record.exception_class == "RuntimeError"

    def test_keyboard_interrupt_propagates(self) -> None:
        def fn() -> CanonicalFiveResult:
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            evaluate_canonical_five_safe(
                genome_id="g1",
                run_id="r1",
                generation_no=0,
                stage="canonical_five",
                evaluate_fn=fn,
            )

    def test_system_exit_propagates(self) -> None:
        def fn() -> CanonicalFiveResult:
            raise SystemExit(1)

        with pytest.raises(SystemExit):
            evaluate_canonical_five_safe(
                genome_id="g1",
                run_id="r1",
                generation_no=0,
                stage="canonical_five",
                evaluate_fn=fn,
            )

    def test_generator_exit_propagates(self) -> None:
        def fn() -> CanonicalFiveResult:
            raise GeneratorExit

        with pytest.raises(GeneratorExit):
            evaluate_canonical_five_safe(
                genome_id="g1",
                run_id="r1",
                generation_no=0,
                stage="canonical_five",
                evaluate_fn=fn,
            )

    def test_truncates_long_exception_message_at_500(self) -> None:
        long_msg = "x" * 1000

        def fn() -> CanonicalFiveResult:
            raise RuntimeError(long_msg)

        outcome = evaluate_canonical_five_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="canonical_five",
            evaluate_fn=fn,
        )
        assert outcome.failure_record is not None
        assert outcome.failure_record.exception_message is not None
        assert len(outcome.failure_record.exception_message) == EXCEPTION_MESSAGE_MAX_LENGTH

    def test_should_skip_downstream_true_on_failure(self) -> None:
        outcome = evaluate_canonical_five_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="canonical_five",
            evaluate_fn=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        assert outcome.should_skip_downstream is True

    def test_should_skip_downstream_false_on_success(self) -> None:
        outcome = evaluate_canonical_five_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="canonical_five",
            evaluate_fn=lambda: _make_cf(),
        )
        assert outcome.should_skip_downstream is False

    def test_failure_record_has_genome_run_generation(self) -> None:
        outcome = evaluate_canonical_five_safe(
            genome_id="g42",
            run_id="run-99",
            generation_no=7,
            stage="stage_b",
            evaluate_fn=lambda: (_ for _ in ()).throw(RuntimeError("x")),
        )
        rec = outcome.failure_record
        assert rec is not None
        assert rec.genome_id == "g42"
        assert rec.run_id == "run-99"
        assert rec.generation_no == 7
        assert rec.stage == "stage_b"

    def test_non_finite_in_result_yields_non_finite_detected(self) -> None:
        bad = _make_cf(slack_pnl=math.nan)

        outcome = evaluate_canonical_five_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="canonical_five",
            evaluate_fn=lambda: bad,
        )
        assert outcome.failure_record is not None
        assert outcome.failure_record.failure_reason == "non_finite_detected"
        assert outcome.failure_record.detected_field == "slack_pnl"

    def test_state_inconsistency_in_result_yields_state_inconsistency(self) -> None:
        # is_feasible=True (空 reason_codes) だが slack_sharpe=-inf → invariant 違反
        bad = _make_cf(is_feasible=True, slack_sharpe=-math.inf)
        outcome = evaluate_canonical_five_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="canonical_five",
            evaluate_fn=lambda: bad,
        )
        # finite check が先に走り non_finite_detected になる (slack_sharpe is -inf)
        assert outcome.failure_record is not None
        assert outcome.failure_record.failure_reason == "non_finite_detected"

    def test_state_inconsistency_with_negative_finite_slack(self) -> None:
        # is_feasible=True だが slack_sharpe=-0.1 (finite) → state_inconsistency
        bad = _make_cf(is_feasible=True, slack_sharpe=-0.1)
        outcome = evaluate_canonical_five_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="canonical_five",
            evaluate_fn=lambda: bad,
        )
        assert outcome.failure_record is not None
        assert outcome.failure_record.failure_reason == "state_inconsistency"
        assert outcome.failure_record.exception_message is not None
        assert "slack_sharpe" in outcome.failure_record.exception_message


class TestEvaluateMissionInfGapSafe:
    def test_returns_outcome_with_none_failure_on_success(self) -> None:
        mg = _make_mg()
        outcome = evaluate_mission_inf_gap_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="mission_inf_gap",
            evaluate_fn=lambda: mg,
        )
        assert outcome.result is mg
        assert outcome.failure_record is None

    def test_value_error_returns_contract_violation(self) -> None:
        def fn() -> MissionGapResult:
            raise ValueError("bad slacks")

        outcome = evaluate_mission_inf_gap_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="mission_inf_gap",
            evaluate_fn=fn,
        )
        assert outcome.failure_record is not None
        assert outcome.failure_record.failure_reason == "contract_violation"

    def test_generic_exception_returns_exception_raised(self) -> None:
        def fn() -> MissionGapResult:
            raise RuntimeError("oops")

        outcome = evaluate_mission_inf_gap_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="mission_inf_gap",
            evaluate_fn=fn,
        )
        assert outcome.failure_record is not None
        assert outcome.failure_record.failure_reason == "exception_raised"

    def test_keyboard_interrupt_propagates(self) -> None:
        def fn() -> MissionGapResult:
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            evaluate_mission_inf_gap_safe(
                genome_id="g1",
                run_id="r1",
                generation_no=0,
                stage="mission_inf_gap",
                evaluate_fn=fn,
            )

    def test_system_exit_propagates(self) -> None:
        def fn() -> MissionGapResult:
            raise SystemExit

        with pytest.raises(SystemExit):
            evaluate_mission_inf_gap_safe(
                genome_id="g1",
                run_id="r1",
                generation_no=0,
                stage="mission_inf_gap",
                evaluate_fn=fn,
            )

    def test_generator_exit_propagates(self) -> None:
        def fn() -> MissionGapResult:
            raise GeneratorExit

        with pytest.raises(GeneratorExit):
            evaluate_mission_inf_gap_safe(
                genome_id="g1",
                run_id="r1",
                generation_no=0,
                stage="mission_inf_gap",
                evaluate_fn=fn,
            )

    def test_truncates_long_exception_message_at_500(self) -> None:
        long_msg = "z" * 800

        def fn() -> MissionGapResult:
            raise RuntimeError(long_msg)

        outcome = evaluate_mission_inf_gap_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="mission_inf_gap",
            evaluate_fn=fn,
        )
        assert outcome.failure_record is not None
        assert outcome.failure_record.exception_message is not None
        assert len(outcome.failure_record.exception_message) == EXCEPTION_MESSAGE_MAX_LENGTH

    def test_non_finite_nan_detected(self) -> None:
        bad = _make_mg(is_feasible=True, mission_signed_margin=math.nan)
        outcome = evaluate_mission_inf_gap_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="mission_inf_gap",
            evaluate_fn=lambda: bad,
        )
        assert outcome.failure_record is not None
        assert outcome.failure_record.failure_reason == "non_finite_detected"

    def test_state_inconsistency_detected(self) -> None:
        # is_feasible=True だが mission_signed_margin=-inf → invariant 違反
        # ただし NaN check で先に -inf も isnan で False、 finite check は通り、
        # state invariant でキャッチ
        bad = _make_mg(
            is_feasible=True,
            mission_inf_gap=0.0,
            constraint_violation=0.0,
            mission_margin=0.0,
            mission_signed_margin=-math.inf,
        )
        outcome = evaluate_mission_inf_gap_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="mission_inf_gap",
            evaluate_fn=lambda: bad,
        )
        assert outcome.failure_record is not None
        assert outcome.failure_record.failure_reason == "state_inconsistency"

    def test_should_skip_downstream_true_on_failure(self) -> None:
        outcome = evaluate_mission_inf_gap_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="mission_inf_gap",
            evaluate_fn=lambda: (_ for _ in ()).throw(RuntimeError("x")),
        )
        assert outcome.should_skip_downstream is True


class TestEvaluateBCSafe:
    def test_returns_outcome_with_none_failure_on_success(self) -> None:
        bc = _make_bc_result()
        outcome = evaluate_bc_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="bc_eval",
            evaluate_fn=lambda **_kw: bc,
        )
        assert outcome.result is bc
        assert outcome.failure_record is None

    def test_value_error_returns_contract_violation(self) -> None:
        def fn(**_kw: object) -> BCEvaluationResult:
            raise ValueError("bad bundle")

        outcome = evaluate_bc_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="bc_eval",
            evaluate_fn=fn,
            individual_index=5,
        )
        assert outcome.failure_record is not None
        assert outcome.failure_record.failure_reason == "contract_violation"
        # degraded result の individual_index が kwargs から伝搬
        assert outcome.result.individual_index == 5

    def test_generic_exception_returns_exception_raised(self) -> None:
        def fn(**_kw: object) -> BCEvaluationResult:
            raise RuntimeError("crash")

        outcome = evaluate_bc_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="bc_eval",
            evaluate_fn=fn,
        )
        assert outcome.failure_record is not None
        assert outcome.failure_record.failure_reason == "exception_raised"

    def test_keyboard_interrupt_propagates(self) -> None:
        def fn(**_kw: object) -> BCEvaluationResult:
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            evaluate_bc_safe(
                genome_id="g1",
                run_id="r1",
                generation_no=0,
                stage="bc_eval",
                evaluate_fn=fn,
            )

    def test_system_exit_propagates(self) -> None:
        def fn(**_kw: object) -> BCEvaluationResult:
            raise SystemExit

        with pytest.raises(SystemExit):
            evaluate_bc_safe(
                genome_id="g1",
                run_id="r1",
                generation_no=0,
                stage="bc_eval",
                evaluate_fn=fn,
            )

    def test_generator_exit_propagates(self) -> None:
        def fn(**_kw: object) -> BCEvaluationResult:
            raise GeneratorExit

        with pytest.raises(GeneratorExit):
            evaluate_bc_safe(
                genome_id="g1",
                run_id="r1",
                generation_no=0,
                stage="bc_eval",
                evaluate_fn=fn,
            )

    def test_individual_index_non_int_falls_back_to_zero(self) -> None:
        # no-raise contract 維持: int() 失敗時 0 fallback (Codex pr1-r1 [Warning H8])
        def fn(**_kw: object) -> BCEvaluationResult:
            raise RuntimeError("crash")

        outcome = evaluate_bc_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="bc_eval",
            evaluate_fn=fn,
            individual_index="not-a-number",
        )
        # wrapper 外に例外が漏れないことを確認 + degraded result.individual_index=0
        assert outcome.result.individual_index == 0
        assert outcome.failure_record is not None

    def test_truncates_long_exception_message_at_500(self) -> None:
        def fn(**_kw: object) -> BCEvaluationResult:
            raise RuntimeError("y" * 700)

        outcome = evaluate_bc_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="bc_eval",
            evaluate_fn=fn,
        )
        assert outcome.failure_record is not None
        assert outcome.failure_record.exception_message is not None
        assert len(outcome.failure_record.exception_message) == EXCEPTION_MESSAGE_MAX_LENGTH

    def test_non_finite_in_result_yields_non_finite_detected(self) -> None:
        bad = _make_bc_result(c_pass_depth=math.nan)
        outcome = evaluate_bc_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="bc_eval",
            evaluate_fn=lambda **_kw: bad,
        )
        assert outcome.failure_record is not None
        assert outcome.failure_record.failure_reason == "non_finite_detected"
        assert outcome.failure_record.detected_field == "c_pass_depth"

    def test_state_inconsistency_in_result_yields_state_inconsistency(self) -> None:
        # b_pooled_cf=None だが pareto_axis_usable=True → invariant 違反
        bad = _make_bc_result(b_pooled_cf=None, pareto_axis_usable=True)
        outcome = evaluate_bc_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="bc_eval",
            evaluate_fn=lambda **_kw: bad,
        )
        assert outcome.failure_record is not None
        assert outcome.failure_record.failure_reason == "state_inconsistency"

    def test_should_skip_downstream_true_on_failure(self) -> None:
        outcome = evaluate_bc_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="bc_eval",
            evaluate_fn=lambda **_kw: (_ for _ in ()).throw(RuntimeError("x")),
        )
        assert outcome.should_skip_downstream is True

    def test_individual_index_default_zero(self) -> None:
        def fn(**_kw: object) -> BCEvaluationResult:
            raise RuntimeError("x")

        outcome = evaluate_bc_safe(
            genome_id="g1",
            run_id="r1",
            generation_no=0,
            stage="bc_eval",
            evaluate_fn=fn,
        )
        assert outcome.result.individual_index == 0


# ---------------------------------------------------------------------------
# Sub-suite 2.3 — finite check (Round 1 [W2])
# ---------------------------------------------------------------------------


class TestValidateFiniteCanonicalFive:
    def test_detects_nan_in_slack_pnl(self) -> None:
        cf = _make_cf(slack_pnl=math.nan)
        result = validate_finite_canonical_five(cf)
        assert result is not None
        assert result[0] == "slack_pnl"
        assert math.isnan(result[1])

    def test_detects_inf_in_max_dd(self) -> None:
        cf = _make_cf(max_dd=math.inf)
        result = validate_finite_canonical_five(cf)
        assert result is not None
        assert result[0] == "max_dd"

    def test_returns_none_for_all_finite(self) -> None:
        cf = _make_cf()
        assert validate_finite_canonical_five(cf) is None

    def test_excludes_trade_count_int_field(self) -> None:
        # trade_count は int で finite check 対象外
        cf = _make_cf(trade_count=10**9)
        assert validate_finite_canonical_five(cf) is None

    def test_detects_neg_inf_in_log_pf_clip(self) -> None:
        cf = _make_cf(log_pf_clip=-math.inf)
        result = validate_finite_canonical_five(cf)
        assert result is not None
        assert result[0] == "log_pf_clip"

    def test_detects_nan_in_per_bucket_sr(self) -> None:
        cf = _make_cf(per_bucket_sr_value=math.nan)
        result = validate_finite_canonical_five(cf)
        assert result is not None
        assert result[0].startswith("per_bucket_sr[")


class TestValidateFiniteMissionGap:
    def test_detects_nan_in_mission_inf_gap(self) -> None:
        mg = _make_mg(mission_inf_gap=math.nan)
        result = validate_finite_mission_gap(mg)
        assert result is not None
        assert result[0] == "mission_inf_gap"

    def test_allows_neg_inf_signed_margin_when_infeasible(self) -> None:
        mg = _make_mg(is_feasible=False, mission_signed_margin=-math.inf)
        # NaN のみ failure 化、 -inf sentinel は許容
        assert validate_finite_mission_gap(mg) is None

    def test_allows_pos_inf_constraint_violation_when_infeasible(self) -> None:
        mg = _make_mg(is_feasible=False, constraint_violation=math.inf)
        assert validate_finite_mission_gap(mg) is None

    def test_detects_nan_in_per_metric_shortfall(self) -> None:
        mg = _make_mg(
            is_feasible=False,
            per_metric_shortfall={"sharpe": math.nan},
        )
        result = validate_finite_mission_gap(mg)
        assert result is not None
        assert result[0] == "per_metric_shortfall[sharpe]"

    def test_returns_none_for_all_finite_feasible(self) -> None:
        mg = _make_mg(is_feasible=True)
        assert validate_finite_mission_gap(mg) is None


class TestValidateFiniteBCResult:
    def test_detects_nan_in_c_pass_depth(self) -> None:
        bc = _make_bc_result(c_pass_depth=math.nan)
        result = validate_finite_bc_result(bc)
        assert result is not None
        assert result[0] == "c_pass_depth"

    def test_recurses_into_b_pooled_cf(self) -> None:
        bad_cf = _make_cf(slack_pnl=math.nan)
        bc = _make_bc_result(b_pooled_cf=bad_cf)
        result = validate_finite_bc_result(bc)
        assert result is not None
        assert result[0].startswith("b_pooled_cf.slack_pnl")

    def test_recurses_into_b_result_per_fold(self) -> None:
        bad_cf = _make_cf(max_dd=math.inf)
        b_result = _make_stage_b_result(
            b_pooled_cf_result=_make_cf(),
            fold_cf=bad_cf,
        )
        bc = _make_bc_result(b_result=b_result)
        result = validate_finite_bc_result(bc)
        assert result is not None
        assert "b_result.per_fold_results[0].cf_result.max_dd" in result[0]

    def test_detects_inf_in_pooled_dd(self) -> None:
        b_result = _make_stage_b_result(
            b_pooled_cf_result=_make_cf(),
            pooled_dd_per_fold_max=math.inf,
        )
        bc = _make_bc_result(b_result=b_result)
        result = validate_finite_bc_result(bc)
        assert result is not None
        assert result[0] == "b_result.pooled_dd_per_fold_max"

    def test_recurses_into_c_lite_window(self) -> None:
        bad_cf = _make_cf(net_pnl_after_cost=math.nan)
        cl = _make_stage_c_lite_result(window_cf=bad_cf)
        bc = _make_bc_result(c_lite_result=cl)
        result = validate_finite_bc_result(bc)
        assert result is not None
        assert "c_lite_result.per_window_results" in result[0]

    def test_recurses_into_c_result_c_cf(self) -> None:
        bad_cf = _make_cf(slack_dd=math.nan)
        cr = _make_stage_c_result(c_cf=bad_cf)
        bc = _make_bc_result(c_result=cr)
        result = validate_finite_bc_result(bc)
        assert result is not None
        assert "c_result.c_cf_result.slack_dd" in result[0]

    def test_returns_none_for_all_finite(self) -> None:
        bc = _make_bc_result()
        assert validate_finite_bc_result(bc) is None


# ---------------------------------------------------------------------------
# Sub-suite 2.4 — state invariant check (Round 3 [C1])
# ---------------------------------------------------------------------------


class TestValidateStateInvariantCanonicalFive:
    def test_is_feasible_true_with_neg_inf_slack_inconsistent(self) -> None:
        cf = _make_cf(is_feasible=True, slack_sharpe=-math.inf)
        result = validate_state_invariant_canonical_five(cf)
        assert result is not None
        assert "slack_sharpe" in result

    def test_is_feasible_true_with_negative_finite_slack_inconsistent(self) -> None:
        cf = _make_cf(is_feasible=True, slack_pnl=-0.1)
        result = validate_state_invariant_canonical_five(cf)
        assert result is not None
        assert "slack_pnl" in result

    def test_is_feasible_true_with_all_positive_slacks_passes(self) -> None:
        cf = _make_cf(is_feasible=True)
        assert validate_state_invariant_canonical_five(cf) is None

    def test_is_feasible_false_with_negative_slack_passes(self) -> None:
        cf = _make_cf(is_feasible=False, slack_sharpe=-0.5)
        assert validate_state_invariant_canonical_five(cf) is None

    def test_is_feasible_false_with_neg_inf_slack_passes(self) -> None:
        cf = _make_cf(is_feasible=False, slack_pnl=-math.inf)
        assert validate_state_invariant_canonical_five(cf) is None


class TestValidateStateInvariantMissionGap:
    def test_is_feasible_true_neg_inf_signed_margin_inconsistent(self) -> None:
        mg = _make_mg(
            is_feasible=True,
            mission_inf_gap=0.0,
            constraint_violation=0.0,
            mission_margin=0.0,
            mission_signed_margin=-math.inf,
        )
        result = validate_state_invariant_mission_gap(mg)
        assert result is not None
        assert "mission_signed_margin" in result

    def test_is_feasible_true_with_finite_positive_margin_passes(self) -> None:
        mg = _make_mg(is_feasible=True, mission_signed_margin=0.5)
        assert validate_state_invariant_mission_gap(mg) is None

    def test_is_feasible_false_with_zero_gap_and_zero_violation_inconsistent(self) -> None:
        mg = _make_mg(
            is_feasible=False,
            mission_inf_gap=0.0,
            constraint_violation=0.0,
            mission_margin=0.0,
            mission_signed_margin=-math.inf,
        )
        result = validate_state_invariant_mission_gap(mg)
        assert result is not None
        assert "both mission_inf_gap and constraint_violation are 0" in result

    def test_is_feasible_false_with_neg_inf_passes(self) -> None:
        mg = _make_mg(
            is_feasible=False,
            mission_inf_gap=math.inf,
            constraint_violation=math.inf,
            mission_margin=-math.inf,
            mission_signed_margin=-math.inf,
        )
        assert validate_state_invariant_mission_gap(mg) is None

    def test_is_feasible_true_with_nonzero_inf_gap_inconsistent(self) -> None:
        mg = _make_mg(
            is_feasible=True,
            mission_inf_gap=0.5,
            constraint_violation=0.0,
            mission_margin=0.0,
            mission_signed_margin=0.5,
        )
        result = validate_state_invariant_mission_gap(mg)
        assert result is not None
        assert "mission_inf_gap" in result

    def test_truth_table_full_coverage(self) -> None:
        # is_feasible=True で全 0 + signed_margin=0 → 整合
        mg_ok_feasible = _make_mg(
            is_feasible=True,
            mission_inf_gap=0.0,
            constraint_violation=0.0,
            mission_margin=0.0,
            mission_signed_margin=0.0,
        )
        assert validate_state_invariant_mission_gap(mg_ok_feasible) is None

        # is_feasible=False で full sentinel → 整合
        mg_ok_infeasible = _make_mg(
            is_feasible=False,
            mission_inf_gap=math.inf,
            constraint_violation=math.inf,
            mission_margin=-math.inf,
            mission_signed_margin=-math.inf,
        )
        assert validate_state_invariant_mission_gap(mg_ok_infeasible) is None


class TestValidateStateInvariantBCResult:
    def test_pareto_usable_true_with_b_pooled_cf_none_inconsistent(self) -> None:
        bc = _make_bc_result(b_pooled_cf=None, pareto_axis_usable=True)
        result = validate_state_invariant_bc_result(bc)
        assert result is not None
        assert "pareto_axis_usable=True but b_pooled_cf is None" in result

    def test_pareto_usable_false_with_b_pooled_cf_present_inconsistent(self) -> None:
        bc = _make_bc_result(
            b_pooled_cf=_make_cf(),
            pareto_axis_usable=False,
        )
        result = validate_state_invariant_bc_result(bc)
        assert result is not None
        assert "pareto_axis_usable=False but b_pooled_cf is not None" in result

    def test_mission_pass_with_progress_fail_inconsistent(self) -> None:
        cl = _make_stage_c_lite_result(
            mission_pass=StagePassStatus.PASS,
            progress_pass=StagePassStatus.FAIL,
            n_pass_windows=2,
        )
        bc = _make_bc_result(
            mission_pass=StagePassStatus.PASS,
            c_lite_result=cl,
        )
        result = validate_state_invariant_bc_result(bc)
        assert result is not None
        assert "progress_pass" in result

    def test_c_pass_depth_out_of_range_inconsistent(self) -> None:
        bc = _make_bc_result(c_pass_depth=2.0)
        result = validate_state_invariant_bc_result(bc)
        assert result is not None
        assert "c_pass_depth" in result

    def test_valid_bc_result_passes(self) -> None:
        bc = _make_bc_result()
        assert validate_state_invariant_bc_result(bc) is None


# ---------------------------------------------------------------------------
# Sub-suite 2.5 — degraded builders
# ---------------------------------------------------------------------------


class TestBuildDegradedCanonicalFive:
    def test_invariant_feasible_false(self) -> None:
        cf = build_degraded_canonical_five()
        assert cf.invariants.is_feasible is False

    def test_all_slacks_neg_inf(self) -> None:
        cf = build_degraded_canonical_five()
        assert cf.slack_sharpe == -math.inf
        assert cf.slack_pnl == -math.inf
        assert cf.slack_dd == -math.inf
        assert cf.slack_tc == -math.inf
        assert cf.slack_wr == -math.inf

    def test_log_pf_clip_at_floor(self) -> None:
        cf = build_degraded_canonical_five()
        assert cf.log_pf_clip == DEGRADED_LOG_PF_CLIP_FLOOR

    def test_gate_pass_false_and_gate_worst_gap_inf(self) -> None:
        cf = build_degraded_canonical_five()
        assert cf.gate_pass is False
        assert cf.gate_worst_gap == math.inf


class TestBuildDegradedMissionGap:
    def test_is_feasible_false(self) -> None:
        mg = build_degraded_mission_gap()
        assert mg.is_feasible is False

    def test_signed_margin_neg_inf(self) -> None:
        mg = build_degraded_mission_gap()
        assert mg.mission_signed_margin == -math.inf

    def test_constraint_violation_inf(self) -> None:
        mg = build_degraded_mission_gap()
        assert mg.constraint_violation == math.inf

    def test_per_metric_shortfall_is_mapping_proxy(self) -> None:
        mg = build_degraded_mission_gap()
        assert isinstance(mg.per_metric_shortfall, MappingProxyType)
        assert len(mg.per_metric_shortfall) == 0


class TestBuildDegradedBCResult:
    def test_mission_pass_fail(self) -> None:
        bc = build_degraded_bc_result(0)
        assert bc.mission_pass == StagePassStatus.FAIL

    def test_b_pooled_cf_none(self) -> None:
        bc = build_degraded_bc_result(0)
        assert bc.b_pooled_cf is None

    def test_pareto_axis_usable_false(self) -> None:
        bc = build_degraded_bc_result(0)
        assert bc.pareto_axis_usable is False

    def test_individual_index_preserved(self) -> None:
        bc = build_degraded_bc_result(99)
        assert bc.individual_index == 99

    def test_c_pass_depth_zero(self) -> None:
        bc = build_degraded_bc_result(0)
        assert bc.c_pass_depth == 0.0

    def test_passes_state_invariant(self) -> None:
        bc = build_degraded_bc_result(0)
        assert validate_state_invariant_bc_result(bc) is None

    def test_finite_check_returns_non_finite_for_dummy_subresults(self) -> None:
        # degraded BCEvaluationResult は dummy sub-result (c_lite_result.cells_worst=+inf
        # / c_result.c_cf_result.slack_*=-inf 等) を持つため、 finite check は
        # 必ず non-finite を検出する (NaN check は通るが Inf も walk する).
        # これは「degraded 個体が downstream に流れたら検出して再排除する」 安全網として機能.
        bc = build_degraded_bc_result(0)
        result = validate_finite_bc_result(bc)
        assert result is not None
        # 検出されるのは最初に walk される field (c_lite_result.cells_worst=+inf).
        assert "c_lite_result.cells_worst" in result[0]
        assert math.isinf(result[1])


# ---------------------------------------------------------------------------
# Sub-suite 2.6 — aggregate_failures (stage-local)
# ---------------------------------------------------------------------------


class TestAggregateFailures:
    def test_filters_records_by_stage(self) -> None:
        records = [
            _make_record(genome_id="g1", stage="canonical_five"),
            _make_record(genome_id="g2", stage="stage_b"),
            _make_record(genome_id="g3", stage="canonical_five"),
        ]
        summary = aggregate_failures(
            records, stage="canonical_five", eligible_count=10
        )
        assert summary.n_failure_records == 2
        assert summary.n_failed_genomes == 2
        assert summary.failed_genome_ids == ("g1", "g3")

    def test_collects_failed_genome_ids_sorted(self) -> None:
        records = [
            _make_record(genome_id="zeta"),
            _make_record(genome_id="alpha"),
            _make_record(genome_id="beta"),
        ]
        summary = aggregate_failures(
            records, stage="canonical_five", eligible_count=10
        )
        assert summary.failed_genome_ids == ("alpha", "beta", "zeta")

    def test_groups_by_reason(self) -> None:
        records = [
            _make_record(genome_id="g1", failure_reason="exception_raised"),
            _make_record(genome_id="g2", failure_reason="contract_violation"),
            _make_record(genome_id="g3", failure_reason="exception_raised"),
        ]
        summary = aggregate_failures(
            records, stage="canonical_five", eligible_count=10
        )
        assert summary.failures_by_reason["exception_raised"] == 2
        assert summary.failures_by_reason["contract_violation"] == 1

    def test_failure_rate_computed_with_eligible_count_denominator(self) -> None:
        records = [
            _make_record(genome_id="g1"),
            _make_record(genome_id="g2"),
        ]
        summary = aggregate_failures(
            records, stage="canonical_five", eligible_count=4
        )
        assert summary.failure_rate == pytest.approx(0.5)

    def test_eligible_count_zero_returns_failure_rate_zero(self) -> None:
        summary = aggregate_failures([], stage="canonical_five", eligible_count=0)
        assert summary.failure_rate == 0.0
        assert summary.all_failed is False

    def test_raises_on_n_failed_genomes_exceeding_eligible_count(self) -> None:
        records = [
            _make_record(genome_id="g1"),
            _make_record(genome_id="g2"),
        ]
        with pytest.raises(ValueError, match="exceeds eligible_count"):
            aggregate_failures(records, stage="canonical_five", eligible_count=1)

    def test_raises_on_negative_eligible_count(self) -> None:
        with pytest.raises(ValueError, match="must be >= 0"):
            aggregate_failures([], stage="canonical_five", eligible_count=-1)

    def test_n_failed_genomes_unique_when_same_genome_multiple_records(self) -> None:
        records = [
            _make_record(genome_id="g1", failure_reason="exception_raised"),
            _make_record(genome_id="g1", failure_reason="non_finite_detected"),
        ]
        summary = aggregate_failures(
            records, stage="canonical_five", eligible_count=2
        )
        assert summary.n_failed_genomes == 1
        assert summary.n_failure_records == 2


# ---------------------------------------------------------------------------
# Sub-suite 2.7 — decide_run_abort
# ---------------------------------------------------------------------------


class TestDecideRunAbort:
    def _summary(
        self,
        *,
        eligible: int,
        failed_ids: tuple[str, ...],
        n_records: int | None = None,
    ) -> FailureSummary:
        n_records = n_records or len(failed_ids)
        return FailureSummary(
            stage="canonical_five",
            eligible_individuals=eligible,
            n_failure_records=n_records,
            n_failed_genomes=len(failed_ids),
            n_succeeded_genomes=eligible - len(failed_ids),
            all_failed=(eligible > 0 and len(failed_ids) == eligible),
            failed_genome_ids=failed_ids,
            failures_by_reason=MappingProxyType({}),
            failure_rate=(len(failed_ids) / max(eligible, 1)),
        )

    def test_eligible_zero_returns_false(self) -> None:
        s = self._summary(eligible=0, failed_ids=())
        assert decide_run_abort(s) is False

    def test_all_succeeded_returns_false(self) -> None:
        s = self._summary(eligible=5, failed_ids=())
        assert decide_run_abort(s) is False

    def test_some_failed_returns_false(self) -> None:
        s = self._summary(eligible=5, failed_ids=("g1", "g2"))
        assert decide_run_abort(s) is False

    def test_all_failed_returns_true(self) -> None:
        s = self._summary(eligible=3, failed_ids=("g1", "g2", "g3"))
        assert decide_run_abort(s) is True

    def test_uses_n_failed_genomes_not_record_count(self) -> None:
        # 1 個体だが 5 records (重複) で eligible=2 → all_failed=False
        s = self._summary(eligible=2, failed_ids=("g1",), n_records=5)
        assert decide_run_abort(s) is False


# ---------------------------------------------------------------------------
# Sub-suite 2.8 — build_run_failure_summary
# ---------------------------------------------------------------------------


class TestBuildRunFailureSummary:
    def test_aggregates_per_stage_summaries(self) -> None:
        s_a = aggregate_failures(
            [_make_record(stage="stage_a")],
            stage="stage_a",
            eligible_count=10,
        )
        s_b = aggregate_failures(
            [_make_record(stage="stage_b")],
            stage="stage_b",
            eligible_count=5,
        )
        run_summary = build_run_failure_summary("run-1", [s_a, s_b])
        assert run_summary.run_id == "run-1"
        assert run_summary.per_stage_summaries == (s_a, s_b)

    def test_any_stage_all_failed_true_when_any_summary_all_failed(self) -> None:
        s_a = aggregate_failures(
            [_make_record(genome_id="g1", stage="stage_a")],
            stage="stage_a",
            eligible_count=1,
        )
        assert s_a.all_failed is True
        s_b = aggregate_failures([], stage="stage_b", eligible_count=5)
        run_summary = build_run_failure_summary("run-1", [s_a, s_b])
        assert run_summary.any_stage_all_failed is True

    def test_any_stage_all_failed_false_when_no_summary_all_failed(self) -> None:
        s_a = aggregate_failures([], stage="stage_a", eligible_count=10)
        run_summary = build_run_failure_summary("run-1", [s_a])
        assert run_summary.any_stage_all_failed is False

    def test_raises_on_empty_run_id(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            build_run_failure_summary("", [])


# ---------------------------------------------------------------------------
# Sub-suite 2.9 — Determinism + immutability
# ---------------------------------------------------------------------------


class TestDeterminismImmutability:
    def test_failure_record_is_frozen_dataclass(self) -> None:
        rec = _make_record()
        with pytest.raises(FrozenInstanceError):
            rec.genome_id = "x"  # type: ignore[misc]

    def test_failure_summary_failures_by_reason_is_mapping_proxy(self) -> None:
        summary = aggregate_failures(
            [_make_record()], stage="canonical_five", eligible_count=10
        )
        assert isinstance(summary.failures_by_reason, MappingProxyType)

    def test_aggregate_failures_deterministic_with_unsorted_input(self) -> None:
        records_1 = [
            _make_record(genome_id="g3"),
            _make_record(genome_id="g1"),
            _make_record(genome_id="g2"),
        ]
        records_2 = [
            _make_record(genome_id="g1"),
            _make_record(genome_id="g2"),
            _make_record(genome_id="g3"),
        ]
        s1 = aggregate_failures(records_1, stage="canonical_five", eligible_count=10)
        s2 = aggregate_failures(records_2, stage="canonical_five", eligible_count=10)
        assert s1.failed_genome_ids == s2.failed_genome_ids

    def test_evaluation_outcome_is_frozen_dataclass(self) -> None:
        outcome: EvaluationOutcome[CanonicalFiveResult] = EvaluationOutcome(
            result=_make_cf(),
            failure_record=None,
            should_skip_downstream=False,
        )
        with pytest.raises(FrozenInstanceError):
            outcome.should_skip_downstream = True  # type: ignore[misc]

    def test_failure_summary_is_frozen_dataclass(self) -> None:
        s = aggregate_failures([], stage="canonical_five", eligible_count=0)
        with pytest.raises(FrozenInstanceError):
            s.eligible_individuals = 1  # type: ignore[misc]

    def test_run_failure_summary_is_frozen_dataclass(self) -> None:
        rs = build_run_failure_summary("run-1", [])
        with pytest.raises(FrozenInstanceError):
            rs.run_id = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Sub-suite 2.10 — sentinel 許容 invariant (§ 8.4 truth table)
# ---------------------------------------------------------------------------


class TestSentinelAllowanceInvariant:
    def test_neg_inf_signed_margin_with_is_feasible_false_is_valid(self) -> None:
        mg = _make_mg(
            is_feasible=False,
            mission_inf_gap=math.inf,
            constraint_violation=math.inf,
            mission_margin=-math.inf,
            mission_signed_margin=-math.inf,
        )
        assert validate_finite_mission_gap(mg) is None
        assert validate_state_invariant_mission_gap(mg) is None

    def test_state_invariant_is_feasible_false_with_neg_inf_passes(self) -> None:
        mg = build_degraded_mission_gap()
        assert validate_state_invariant_mission_gap(mg) is None

    def test_state_invariant_truth_table_full_coverage(self) -> None:
        # is_feasible=True: 全 0 で signed_margin=0 → ok
        mg_ok = _make_mg(
            is_feasible=True,
            mission_inf_gap=0.0,
            constraint_violation=0.0,
            mission_margin=0.0,
            mission_signed_margin=0.0,
        )
        assert validate_state_invariant_mission_gap(mg_ok) is None

        # is_feasible=True で signed_margin=-inf → bad
        mg_bad_signed = _make_mg(
            is_feasible=True,
            mission_inf_gap=0.0,
            constraint_violation=0.0,
            mission_margin=0.0,
            mission_signed_margin=-math.inf,
        )
        assert validate_state_invariant_mission_gap(mg_bad_signed) is not None

        # is_feasible=False で signed_margin=+inf → bad (sign violation)
        mg_bad_sign = _make_mg(
            is_feasible=False,
            mission_inf_gap=math.inf,
            constraint_violation=math.inf,
            mission_margin=-math.inf,
            mission_signed_margin=math.inf,
        )
        assert validate_state_invariant_mission_gap(mg_bad_sign) is not None


# ---------------------------------------------------------------------------
# Sub-suite 2.11 — Edge cases + schema v2 整合性
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_truncate_exception_message_handles_unicode_correctly(self) -> None:
        # 日本語 + emoji を含む長 string
        msg = "あ" * 600 + "🎌"
        truncated = _truncate_exception_message(msg)
        assert len(truncated) == EXCEPTION_MESSAGE_MAX_LENGTH
        # surrogate pair / 結合文字を破壊しない (str slice = code point 単位)
        # 単純に最初の 500 code point になる
        assert truncated == "あ" * 500

    def test_truncate_exception_message_short_unchanged(self) -> None:
        msg = "short"
        assert _truncate_exception_message(msg) == "short"

    def test_failure_record_stage_enum_matches_synthesis_terms(self) -> None:
        # StageType の Literal 値が synthesis 用語と一致していることを構造的に検証
        valid_stages = {
            "canonical_five",
            "mission_inf_gap",
            "bc_eval",
            "stage_a",
            "stage_b",
            "stage_c_lite",
            "stage_c",
        }
        for stage in valid_stages:
            rec = _make_record(stage=stage)
            assert rec.stage == stage

    def test_make_failure_record_fingerprint_dedup_key_format(self) -> None:
        exc = RuntimeError("test message")
        rec = _make_failure_record(
            "g1",
            "r1",
            0,
            "canonical_five",
            reason="exception_raised",
            exception=exc,
        )
        assert rec.exception_fingerprint is not None
        assert rec.exception_fingerprint.startswith("RuntimeError@canonical_five:")

    def test_evaluation_outcome_generic_type_canonical_five_vs_mission_gap(
        self,
    ) -> None:
        # Generic[T] が独立 specialization できる
        cf_outcome: EvaluationOutcome[CanonicalFiveResult] = EvaluationOutcome(
            result=_make_cf(),
            failure_record=None,
            should_skip_downstream=False,
        )
        mg_outcome: EvaluationOutcome[MissionGapResult] = EvaluationOutcome(
            result=_make_mg(),
            failure_record=None,
            should_skip_downstream=False,
        )
        assert isinstance(cf_outcome.result, CanonicalFiveResult)
        assert isinstance(mg_outcome.result, MissionGapResult)

    def test_aggregate_failures_total_individuals_zero_failure_rate_zero(self) -> None:
        summary = aggregate_failures([], stage="canonical_five", eligible_count=0)
        assert summary.failure_rate == 0.0
        assert summary.n_failed_genomes == 0
