"""T064: Stage B/C-lite/C evaluator — 振る舞いベース test.

詳細設計: ``devnotes/20260430-0230-todo-T064-stage-bc-evaluator/detailed-design.md``

Test 計画 (詳細設計 § 施策 2 + Follow-up Phase 0):
- Constants
- StagePassStatus / SampleSizeFlag / MissionFailReason
- Stage B (5 fold pooled OOS)
- build_pooled_oos_input (Round 1 [C3] / Round 2 [W1] / 概念 Round 3 [S3])
- Stage C-lite (3 windows × 15 セル worst、 sample-size flag)
- Stage C truth table (Round 2 [Critical] 1)
- Stage C cross-pair (provenance guard)
- apply_spread_stress (Phase 1 NotImplementedError)
- compute_cross_pair_shadow_score
- compute_a_b_correlation (定数系列 / NaN handling)
- select_top_clite_forced_pass_indices
- evaluate_bc_for_a_pass (top-level、 4 代表ケース)
- Follow-up: n_pass_windows / c_pass_depth (3 status × 4 n = 12 ケース)
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, fields
from datetime import UTC, datetime, timedelta

import pytest

from src.alpha_factory.canonical_metrics import (
    BarEquityPoint,
    BarEquitySeries,
    CanonicalFiveResult,
    InfeasibleReasonCode,
    InvariantFlags,
    SessionBucket,
    TradeRecord,
)
from src.alpha_factory.partition import Fold, Period
from src.alpha_factory.stage_bc_evaluator import (
    STAGE_B_NUM_FOLDS,
    STAGE_C_ANCHOR_PAIR,
    STAGE_C_LITE_FORCED_PASS_RATIO,
    STAGE_C_LITE_NUM_WINDOWS,
    STAGE_C_LITE_PROGRESS_PASS_MIN_WINDOWS,
    STAGE_C_LITE_SAMPLE_SIZE_BOUNDARY_MIN_BLOCKS,
    STAGE_C_LITE_SAMPLE_SIZE_OK_MIN_BLOCKS,
    STAGE_C_SHADOW_PAIR_LIST,
    STAGE_C_SHADOW_REQUIRED_COUNT,
    STAGE_C_SPREAD_STRESS_MULTIPLIER,
    BCEvaluationInput,
    BCEvaluationResult,
    MissionFailReason,
    PairBacktestBundle,
    SampleSizeFlag,
    StageBCInputError,
    StageBFoldResult,
    StageCLiteResult,
    StageCLiteWindowResult,
    StageCResult,
    StagePassStatus,
    apply_spread_stress,
    build_pooled_oos_input,
    compute_a_b_correlation,
    compute_a_b_correlation_source_score,
    compute_c_pass_depth,
    compute_cross_pair_shadow_score,
    compute_gate_pass_excluding_dd,
    derive_stage_b_thresholds,
    derive_stage_c_lite_thresholds,
    derive_stage_c_thresholds,
    evaluate_bc_for_a_pass,
    evaluate_stage_b,
    evaluate_stage_c,
    evaluate_stage_c_lite,
    filter_to_period,
    select_top_clite_forced_pass_indices,
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
    gate_pass: bool | None = None,
    trade_count: int = 100,
    max_dd: float = 0.1,
    slack_sharpe: float = 0.5,
    slack_pnl: float = 0.5,
    slack_dd: float = 0.5,
    slack_tc: float = 0.5,
    slack_wr: float = 0.5,
) -> CanonicalFiveResult:
    """Test 用 :class:`CanonicalFiveResult` fixture."""
    if is_feasible:
        codes: frozenset[InfeasibleReasonCode] = frozenset()
    else:
        codes = frozenset({InfeasibleReasonCode.INPUT_EMPTY_TRADE_LIST})
    invariants = InvariantFlags(
        session_close_drop_count=0,
        negative_equity_drop_open_count=0,
        infeasible_reason_codes=codes,
    )
    if gate_pass is None:
        gate_pass = is_feasible and gate_worst_gap <= 1e-9
    return CanonicalFiveResult(
        sr_session_worst_block_scale=0.1,
        sr_session_worst_annual_estimate=2.5,
        net_pnl_after_cost=100000.0,
        max_dd=max_dd,
        trade_count=trade_count,
        session_block_win_rate_worst=0.5,
        per_bucket_sr={b: 0.1 for b in SessionBucket},
        per_bucket_wr={b: 0.5 for b in SessionBucket},
        low_sample_buckets=frozenset(),
        slack_sharpe=slack_sharpe,
        slack_pnl=slack_pnl,
        slack_dd=slack_dd,
        slack_tc=slack_tc,
        slack_wr=slack_wr,
        gate_worst_gap=gate_worst_gap,
        gate_pass=gate_pass,
        log_pf_clip=0.0,
        bucket_validator_version="unvalidated",
        invariants=invariants,
    )


def _make_period(
    start: datetime,
    end: datetime,
    label: str = "stage_c",
) -> Period:
    return Period(start=start, end=end, label=label)


def _make_fold(
    fold_index: int,
    train_start: datetime,
    *,
    train_weeks: int = 36,
    embargo_weeks: int = 1,
    test_weeks: int = 5,
) -> Fold:
    train_end = train_start + timedelta(weeks=train_weeks)
    embargo_end = train_end + timedelta(weeks=embargo_weeks)
    test_end = embargo_end + timedelta(weeks=test_weeks)
    return Fold(
        fold_index=fold_index,
        train=Period(
            start=train_start, end=train_end, label=f"fold_{fold_index}_fold_train"
        ),
        embargo=Period(
            start=train_end, end=embargo_end, label=f"fold_{fold_index}_fold_embargo"
        ),
        test=Period(
            start=embargo_end, end=test_end, label=f"fold_{fold_index}_fold_test"
        ),
    )


def _five_folds(epoch_start: datetime) -> tuple[Fold, ...]:
    """5 fold rolling-origin (T060 FoldGenerator と同等)."""
    folds: list[Fold] = []
    for k in range(5):
        train_start = epoch_start + timedelta(weeks=k * 5)
        folds.append(_make_fold(k, train_start))
    return tuple(folds)


def _make_bars_for_period(start: datetime, end: datetime) -> BarEquitySeries:
    """1 day-step bars for [start, end)."""
    points: list[BarEquityPoint] = []
    cur = start
    eq = 100000.0
    while cur < end:
        points.append(BarEquityPoint(timestamp_utc=cur, equity=eq))
        cur = cur + timedelta(days=1)
        eq += 10.0
    if not points:
        points.append(BarEquityPoint(timestamp_utc=start, equity=eq))
    return BarEquitySeries(points=tuple(points))


def _make_universe(num_days: int = 365) -> dict[SessionBucket, frozenset[int]]:
    return {b: frozenset(range(num_days)) for b in SessionBucket}


def _make_pair_bundle(
    pair: str,
    *,
    genome_id: str = "g1",
    config_hash: str = "c1",
    partition_label: str = "epoch_2026",
    bars: BarEquitySeries | None = None,
    universe: dict[SessionBucket, frozenset[int]] | None = None,
) -> PairBacktestBundle:
    if bars is None:
        bars = BarEquitySeries(
            points=(BarEquityPoint(timestamp_utc=datetime(2026, 1, 1, tzinfo=UTC), equity=100.0),)
        )
    if universe is None:
        universe = {b: frozenset({0}) for b in SessionBucket}
    return PairBacktestBundle(
        pair=pair,
        genome_id=genome_id,
        config_hash=config_hash,
        partition_label=partition_label,
        trades=(),
        bars=bars,
        business_day_universe=universe,
    )


def _make_eval_fn(
    *,
    default: CanonicalFiveResult | None = None,
    by_call: list[CanonicalFiveResult] | None = None,
    by_pair: dict[str, CanonicalFiveResult] | None = None,
) -> Callable[..., CanonicalFiveResult]:
    """``evaluate_fn`` mock factory.

    Args:
        default: default result for all calls (when by_call/by_pair not given)
        by_call: ordered list, one per call (for sequential expectations)
        by_pair: keyed by anchor reference id (`id(trades)`-based fallback)
    """
    if default is None:
        default = _make_canonical_five_result()
    state: dict[str, int] = {"i": 0}

    def fn(
        trades: object,
        bars: object,
        thresholds: object,
        business_day_universe: object,
        *,
        bucket_validator: object | None = None,
        q_bartlett: int = 5,
    ) -> CanonicalFiveResult:
        if by_call is not None:
            i = state["i"]
            state["i"] += 1
            if i < len(by_call):
                return by_call[i]
            return default
        if by_pair is not None and isinstance(trades, tuple) and trades:
            # not used: keep by_pair semantic on caller side (they pass by_call)
            pass
        return default

    return fn


def _make_bc_input(
    *,
    individual_index: int = 0,
    epoch_start: datetime | None = None,
) -> BCEvaluationInput:
    """1 個体の最小限 BCEvaluationInput fixture.

    24m epoch: stage_b 62w + stage_a 8w + emb1 + c_lite_1 6w + emb1 + c_lite_2 6w +
    emb1 + c_lite_3 6w + emb1 + stage_c 12w = 104w.
    本 fixture では Stage A 後の (c_lite_1 / c_lite_2 / c_lite_3 / stage_c) と
    folds (stage_b 62w 内) を返す.
    """
    if epoch_start is None:
        epoch_start = datetime(2026, 1, 5, tzinfo=UTC)  # Mon
    folds = _five_folds(epoch_start)
    stage_b_end = epoch_start + timedelta(weeks=62)
    # stage_a: 8w, embargo_after_a: 1w → c_lite_1 starts at 71w
    c_lite_1_start = stage_b_end + timedelta(weeks=9)
    c_lite_1 = _make_period(
        c_lite_1_start,
        c_lite_1_start + timedelta(weeks=6),
        "stage_c_lite_1",
    )
    c_lite_2_start = c_lite_1.end + timedelta(weeks=1)
    c_lite_2 = _make_period(
        c_lite_2_start,
        c_lite_2_start + timedelta(weeks=6),
        "stage_c_lite_2",
    )
    c_lite_3_start = c_lite_2.end + timedelta(weeks=1)
    c_lite_3 = _make_period(
        c_lite_3_start,
        c_lite_3_start + timedelta(weeks=6),
        "stage_c_lite_3",
    )
    stage_c_start = c_lite_3.end + timedelta(weeks=1)
    stage_c = _make_period(
        stage_c_start,
        stage_c_start + timedelta(weeks=12),
        "stage_c",
    )
    full_end = stage_c.end
    bars = _make_bars_for_period(epoch_start, full_end)
    universe = _make_universe(num_days=(full_end - epoch_start).days + 10)

    anchor = _make_pair_bundle(STAGE_C_ANCHOR_PAIR)
    shadow = {
        pair: _make_pair_bundle(pair) for pair in STAGE_C_SHADOW_PAIR_LIST
    }

    return BCEvaluationInput(
        individual_index=individual_index,
        trades=(),
        bars=bars,
        business_day_universe=universe,
        folds=folds,
        stage_c_lite_periods=(c_lite_1, c_lite_2, c_lite_3),
        stage_c_period=stage_c,
        anchor_bundle=anchor,
        shadow_pairs=shadow,
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_stage_b_num_folds_is_5(self) -> None:
        assert STAGE_B_NUM_FOLDS == 5

    def test_stage_c_lite_num_windows_is_3(self) -> None:
        assert STAGE_C_LITE_NUM_WINDOWS == 3

    def test_stage_c_lite_forced_pass_ratio_is_0_30(self) -> None:
        assert pytest.approx(0.30) == STAGE_C_LITE_FORCED_PASS_RATIO

    def test_stage_c_lite_progress_pass_min_windows_is_2(self) -> None:
        assert STAGE_C_LITE_PROGRESS_PASS_MIN_WINDOWS == 2

    def test_stage_c_lite_sample_size_min_blocks(self) -> None:
        assert STAGE_C_LITE_SAMPLE_SIZE_OK_MIN_BLOCKS == 30
        assert STAGE_C_LITE_SAMPLE_SIZE_BOUNDARY_MIN_BLOCKS == 25

    def test_stage_c_spread_stress_multiplier_is_1_5(self) -> None:
        assert pytest.approx(1.5) == STAGE_C_SPREAD_STRESS_MULTIPLIER

    def test_stage_c_anchor_pair_is_eur_jpy(self) -> None:
        assert STAGE_C_ANCHOR_PAIR == "EUR_JPY"

    def test_stage_c_shadow_pair_list_excludes_anchor(self) -> None:
        assert STAGE_C_ANCHOR_PAIR not in STAGE_C_SHADOW_PAIR_LIST
        assert len(STAGE_C_SHADOW_PAIR_LIST) == 5

    def test_stage_c_shadow_required_count_is_5(self) -> None:
        assert STAGE_C_SHADOW_REQUIRED_COUNT == 5
        assert len(STAGE_C_SHADOW_PAIR_LIST) == STAGE_C_SHADOW_REQUIRED_COUNT


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_stage_pass_status_has_pass_fail_pending_three_values(self) -> None:
        assert StagePassStatus.PASS.value == "pass"
        assert StagePassStatus.FAIL.value == "fail"
        assert StagePassStatus.PENDING.value == "pending"
        assert len(list(StagePassStatus)) == 3

    def test_sample_size_flag_three_values(self) -> None:
        assert SampleSizeFlag.OK.value == "ok"
        assert SampleSizeFlag.BOUNDARY.value == "boundary"
        assert SampleSizeFlag.INSUFFICIENT.value == "insufficient"

    def test_mission_fail_reason_three_values(self) -> None:
        assert MissionFailReason.LIVE_CRITERIA.value == "live_criteria"
        assert MissionFailReason.CROSS_PAIR.value == "cross_pair"
        assert MissionFailReason.STRESS.value == "stress"


# ---------------------------------------------------------------------------
# derive_*_thresholds
# ---------------------------------------------------------------------------


class TestDeriveThresholds:
    def test_derive_stage_b_thresholds_uses_live_criteria_directly(self) -> None:
        t = derive_stage_b_thresholds(_live_criteria())
        assert t.sharpe_min == 1.0
        assert t.net_pnl_min == 50000.0
        assert t.max_dd_max == 0.20
        assert t.trade_count_min == 50
        assert t.trade_count_max == 5000
        assert t.win_rate_min == 0.45

    def test_derive_stage_c_thresholds_proportional_12w(self) -> None:
        # 12w = 84 days, baseline = 730
        t = derive_stage_c_thresholds(_live_criteria())
        ratio = 84 / 730
        assert t.trade_count_min == max(1, math.ceil(50 * ratio))
        assert t.trade_count_max == math.floor(5000 * ratio)
        assert t.net_pnl_min == pytest.approx(50000.0 * ratio)

    def test_derive_stage_c_lite_thresholds_proportional_6w(self) -> None:
        t = derive_stage_c_lite_thresholds(_live_criteria())
        ratio = 42 / 730
        assert t.trade_count_min == max(1, math.ceil(50 * ratio))
        assert t.trade_count_max == math.floor(5000 * ratio)

    def test_derive_thresholds_rejects_missing_keys(self) -> None:
        bad = _live_criteria()
        del bad["sharpe_min"]
        with pytest.raises(StageBCInputError, match="missing required keys"):
            derive_stage_b_thresholds(bad)


# ---------------------------------------------------------------------------
# PairBacktestBundle provenance guard
# ---------------------------------------------------------------------------


class TestPairBacktestBundleValidate:
    def test_validate_against_passes_when_all_provenance_match(self) -> None:
        a = _make_pair_bundle("EUR_JPY", genome_id="g1", config_hash="c1", partition_label="p1")
        b = _make_pair_bundle("USD_JPY", genome_id="g1", config_hash="c1", partition_label="p1")
        b.validate_against(a)  # should not raise

    def test_validate_against_rejects_mismatched_genome_id(self) -> None:
        a = _make_pair_bundle("EUR_JPY", genome_id="g1")
        b = _make_pair_bundle("USD_JPY", genome_id="g2")
        with pytest.raises(StageBCInputError, match="genome_id"):
            b.validate_against(a)

    def test_validate_against_rejects_mismatched_config_hash(self) -> None:
        a = _make_pair_bundle("EUR_JPY", config_hash="c1")
        b = _make_pair_bundle("USD_JPY", config_hash="c2")
        with pytest.raises(StageBCInputError, match="config_hash"):
            b.validate_against(a)

    def test_validate_against_rejects_mismatched_partition_label(self) -> None:
        a = _make_pair_bundle("EUR_JPY", partition_label="p1")
        b = _make_pair_bundle("USD_JPY", partition_label="p2")
        with pytest.raises(StageBCInputError, match="partition_label"):
            b.validate_against(a)


# ---------------------------------------------------------------------------
# filter_to_period
# ---------------------------------------------------------------------------


class TestFilterToPeriod:
    def test_filter_to_period_uses_half_open_interval_for_trades(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 1, 10, tzinfo=UTC)
        period = _make_period(start, end, "test")
        # trades: one at start (included), one just before end (included),
        # one at end (excluded), one after (excluded)
        t_in_start = TradeRecord(
            entry_time_utc=start - timedelta(hours=1),
            exit_time_utc=start,
            pnl_net=10.0,
            session_bucket=SessionBucket.TOKYO,
            business_day_index=0,
            is_session_close_drop=False,
            is_negative_equity_drop_open=False,
        )
        t_in_mid = TradeRecord(
            entry_time_utc=start + timedelta(days=1),
            exit_time_utc=start + timedelta(days=2),
            pnl_net=10.0,
            session_bucket=SessionBucket.TOKYO,
            business_day_index=2,
            is_session_close_drop=False,
            is_negative_equity_drop_open=False,
        )
        t_at_end_excluded = TradeRecord(
            entry_time_utc=end - timedelta(hours=1),
            exit_time_utc=end,
            pnl_net=10.0,
            session_bucket=SessionBucket.TOKYO,
            business_day_index=10,
            is_session_close_drop=False,
            is_negative_equity_drop_open=False,
        )
        bars = _make_bars_for_period(start - timedelta(days=1), end + timedelta(days=2))
        universe = _make_universe(num_days=20)
        ftrades, fbars, _funiverse = filter_to_period(
            (t_in_start, t_in_mid, t_at_end_excluded), bars, universe, period
        )
        assert t_in_start in ftrades
        assert t_in_mid in ftrades
        assert t_at_end_excluded not in ftrades
        # bars: only those with timestamp in [start, end)
        for p in fbars.points:
            assert start <= p.timestamp_utc < end

    def test_filter_to_period_raises_when_period_yields_empty_bars(self) -> None:
        start = datetime(2026, 6, 1, tzinfo=UTC)
        end = datetime(2026, 6, 10, tzinfo=UTC)
        period = _make_period(start, end, "test")
        # bars all before period
        bars = _make_bars_for_period(
            datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 5, tzinfo=UTC)
        )
        universe = _make_universe(num_days=10)
        with pytest.raises(StageBCInputError, match="no bars in period"):
            filter_to_period((), bars, universe, period)


# ---------------------------------------------------------------------------
# Stage B
# ---------------------------------------------------------------------------


class TestStageB:
    def test_stage_b_all_folds_feasible_yields_b_pooled_cf_not_none(self) -> None:
        bc_input = _make_bc_input()
        feasible = _make_canonical_five_result(is_feasible=True)
        eval_fn = _make_eval_fn(default=feasible)
        result = evaluate_stage_b(
            bc_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )
        assert result.is_feasible_invariant is True
        assert result.b_pooled_cf_result is not None
        assert result.pooled_dd_per_fold_max is not None

    def test_stage_b_one_fold_invariant_fail_yields_b_pooled_cf_none(self) -> None:
        bc_input = _make_bc_input()
        feasible = _make_canonical_five_result(is_feasible=True)
        infeasible = _make_canonical_five_result(is_feasible=False)
        # 5 folds + maybe 1 pooled call. fold 2 fails.
        eval_fn = _make_eval_fn(
            by_call=[feasible, feasible, infeasible, feasible, feasible],
            default=feasible,
        )
        result = evaluate_stage_b(
            bc_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )
        assert result.is_feasible_invariant is False
        assert result.b_pooled_cf_result is None
        assert result.pooled_dd_per_fold_max is None
        assert result.is_b_pass is False

    def test_stage_b_pareto_axis_usable_false_when_b_pooled_cf_none(self) -> None:
        bc_input = _make_bc_input()
        infeasible = _make_canonical_five_result(is_feasible=False)
        eval_fn = _make_eval_fn(default=infeasible)
        result = evaluate_stage_b(
            bc_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )
        assert result.b_pooled_cf_result is None

    def test_stage_b_is_b_pass_excludes_concat_dd_via_per_fold_max(self) -> None:
        bc_input = _make_bc_input()
        # per-fold cf with high max_dd (0.5) but pooled cf with lower max_dd (0.05)
        # → concat DD would suggest pass, but per_fold_max should fail dd_pass.
        per_fold = _make_canonical_five_result(
            is_feasible=True, gate_pass=True, max_dd=0.5
        )
        pooled = _make_canonical_five_result(
            is_feasible=True, gate_pass=True, max_dd=0.05
        )
        eval_fn = _make_eval_fn(
            by_call=[per_fold] * 5 + [pooled],
            default=pooled,
        )
        result = evaluate_stage_b(
            bc_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )
        # max_dd_max=0.20、 pooled_dd_per_fold_max=0.5 > 0.20 → dd_pass=False → is_b_pass=False
        assert result.pooled_dd_per_fold_max == pytest.approx(0.5)
        assert result.is_b_pass is False


# ---------------------------------------------------------------------------
# build_pooled_oos_input
# ---------------------------------------------------------------------------


def _make_fold_result(
    fold_index: int,
    period_start: datetime,
    period_end: datetime,
    *,
    max_dd: float = 0.05,
    is_feasible: bool = True,
) -> StageBFoldResult:
    cf = _make_canonical_five_result(is_feasible=is_feasible, max_dd=max_dd)
    return StageBFoldResult(
        fold_index=fold_index,
        fold_period_start=period_start,
        fold_period_end=period_end,
        cf_result=cf,
        is_feasible_invariant=is_feasible,
    )


class TestBuildPooledOosInput:
    def _setup(self) -> tuple[BCEvaluationInput, list[StageBFoldResult]]:
        bc_input = _make_bc_input()
        fold_results = [
            _make_fold_result(
                f.fold_index, f.test.start, f.test.end, max_dd=0.01 * (f.fold_index + 1)
            )
            for f in bc_input.folds
        ]
        return bc_input, fold_results

    def test_build_pooled_oos_input_pooled_dd_equals_max_of_per_fold_dd(self) -> None:
        bc_input, fold_results = self._setup()
        out = build_pooled_oos_input(fold_results, bc_input)
        # max_dd values: 0.01, 0.02, 0.03, 0.04, 0.05 → max = 0.05
        assert out.pooled_dd_per_fold_max == pytest.approx(0.05)

    def test_build_pooled_oos_input_rejects_overlapping_fold_test_periods(
        self,
    ) -> None:
        bc_input, fold_results = self._setup()
        # break invariant: fold 1 overlaps fold 2 (fold 1.end pushed forward)
        f1 = fold_results[1]
        bad = StageBFoldResult(
            fold_index=f1.fold_index,
            fold_period_start=f1.fold_period_start,
            fold_period_end=fold_results[2].fold_period_start + timedelta(days=1),
            cf_result=f1.cf_result,
            is_feasible_invariant=True,
        )
        fold_results[1] = bad
        with pytest.raises(StageBCInputError, match="overlapping"):
            build_pooled_oos_input(fold_results, bc_input)

    def test_build_pooled_oos_input_rejects_non_chronological_fold_order(self) -> None:
        bc_input, fold_results = self._setup()
        # swap fold 0 and fold 1 starts (still keep fold_index=k for k position)
        f0 = fold_results[0]
        f1 = fold_results[1]
        fold_results[0] = StageBFoldResult(
            fold_index=0,
            fold_period_start=f1.fold_period_start,
            fold_period_end=f1.fold_period_end,
            cf_result=f0.cf_result,
            is_feasible_invariant=True,
        )
        fold_results[1] = StageBFoldResult(
            fold_index=1,
            fold_period_start=f0.fold_period_start,
            fold_period_end=f0.fold_period_end,
            cf_result=f1.cf_result,
            is_feasible_invariant=True,
        )
        with pytest.raises(StageBCInputError, match=r"non-chronological|overlapping"):
            build_pooled_oos_input(fold_results, bc_input)

    def test_build_pooled_oos_input_rejects_wrong_fold_count(self) -> None:
        bc_input, fold_results = self._setup()
        with pytest.raises(StageBCInputError, match="5 folds"):
            build_pooled_oos_input(fold_results[:3], bc_input)

    def test_build_pooled_oos_input_rejects_wrong_fold_index(self) -> None:
        bc_input, fold_results = self._setup()
        # mutate fold_results[2].fold_index to wrong
        f2 = fold_results[2]
        fold_results[2] = StageBFoldResult(
            fold_index=99,
            fold_period_start=f2.fold_period_start,
            fold_period_end=f2.fold_period_end,
            cf_result=f2.cf_result,
            is_feasible_invariant=True,
        )
        with pytest.raises(StageBCInputError, match="fold_index"):
            build_pooled_oos_input(fold_results, bc_input)

    def test_build_pooled_oos_input_business_day_universe_is_union_of_per_fold(
        self,
    ) -> None:
        bc_input, fold_results = self._setup()
        out = build_pooled_oos_input(fold_results, bc_input)
        # union should at least contain elements from each fold's universe (each fold passes
        # universe through filter_to_period as no-op)
        for bucket in SessionBucket:
            assert bucket in out.pooled_business_day_universe

    def test_build_pooled_oos_input_fold_boundaries_metadata_recorded(self) -> None:
        bc_input, fold_results = self._setup()
        out = build_pooled_oos_input(fold_results, bc_input)
        assert isinstance(out.fold_boundaries, tuple)
        assert len(out.fold_boundaries) == STAGE_B_NUM_FOLDS


# ---------------------------------------------------------------------------
# Stage C-lite
# ---------------------------------------------------------------------------


class TestStageCLite:
    def test_stage_c_lite_three_windows_all_pass_yields_mission_pass(self) -> None:
        bc_input = _make_bc_input()
        cf_pass = _make_canonical_five_result(is_feasible=True, gate_pass=True)
        eval_fn = _make_eval_fn(default=cf_pass)
        result = evaluate_stage_c_lite(
            bc_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )
        assert result.mission_pass == StagePassStatus.PASS
        assert result.progress_pass == StagePassStatus.PASS
        assert result.n_pass_windows == 3

    def test_stage_c_lite_two_windows_pass_yields_progress_pass(self) -> None:
        bc_input = _make_bc_input()
        cf_pass = _make_canonical_five_result(is_feasible=True, gate_pass=True)
        cf_fail = _make_canonical_five_result(
            is_feasible=True, gate_pass=False, gate_worst_gap=0.5
        )
        eval_fn = _make_eval_fn(by_call=[cf_pass, cf_pass, cf_fail])
        result = evaluate_stage_c_lite(
            bc_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )
        assert result.mission_pass == StagePassStatus.FAIL
        assert result.progress_pass == StagePassStatus.PASS
        assert result.n_pass_windows == 2

    def test_stage_c_lite_zero_windows_pass_yields_fail(self) -> None:
        bc_input = _make_bc_input()
        cf_fail = _make_canonical_five_result(
            is_feasible=True, gate_pass=False, gate_worst_gap=0.5
        )
        eval_fn = _make_eval_fn(default=cf_fail)
        result = evaluate_stage_c_lite(
            bc_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )
        assert result.mission_pass == StagePassStatus.FAIL
        assert result.progress_pass == StagePassStatus.FAIL
        assert result.n_pass_windows == 0

    def test_stage_c_lite_cells_worst_is_max_of_three_window_gate_worst_gaps(
        self,
    ) -> None:
        bc_input = _make_bc_input()
        cf1 = _make_canonical_five_result(gate_worst_gap=0.1)
        cf2 = _make_canonical_five_result(gate_worst_gap=0.5)
        cf3 = _make_canonical_five_result(gate_worst_gap=0.3)
        eval_fn = _make_eval_fn(by_call=[cf1, cf2, cf3])
        result = evaluate_stage_c_lite(
            bc_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )
        assert result.cells_worst == pytest.approx(0.5)

    def _eval_with_universe_size(
        self, num_days: int, gate_pass: bool = True
    ) -> StageCLiteResult:
        bc_input = _make_bc_input()
        # override universe size on bc_input (mutate via dataclasses.replace would
        # be ideal but BCEvaluationInput is frozen → reconstruct)
        small_universe = {b: frozenset(range(num_days)) for b in SessionBucket}
        new_input = BCEvaluationInput(
            individual_index=bc_input.individual_index,
            trades=bc_input.trades,
            bars=bc_input.bars,
            business_day_universe=small_universe,
            folds=bc_input.folds,
            stage_c_lite_periods=bc_input.stage_c_lite_periods,
            stage_c_period=bc_input.stage_c_period,
            anchor_bundle=bc_input.anchor_bundle,
            shadow_pairs=bc_input.shadow_pairs,
        )
        cf = _make_canonical_five_result(gate_pass=gate_pass)
        eval_fn = _make_eval_fn(default=cf)
        return evaluate_stage_c_lite(
            new_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )

    def test_stage_c_lite_sample_size_ok_when_blocks_above_30(self) -> None:
        result = self._eval_with_universe_size(50)
        assert result.sample_size_flag == SampleSizeFlag.OK

    def test_stage_c_lite_sample_size_boundary_when_blocks_25_to_29(self) -> None:
        result = self._eval_with_universe_size(27)
        assert result.sample_size_flag == SampleSizeFlag.BOUNDARY

    def test_stage_c_lite_sample_size_insufficient_when_blocks_below_25(self) -> None:
        result = self._eval_with_universe_size(20)
        assert result.sample_size_flag == SampleSizeFlag.INSUFFICIENT

    def test_stage_c_lite_insufficient_sample_yields_mission_pass_pending(
        self,
    ) -> None:
        result = self._eval_with_universe_size(20, gate_pass=True)
        assert result.mission_pass == StagePassStatus.PENDING

    def test_stage_c_lite_insufficient_sample_yields_progress_pass_pending(
        self,
    ) -> None:
        result = self._eval_with_universe_size(20, gate_pass=True)
        assert result.progress_pass == StagePassStatus.PENDING


# ---------------------------------------------------------------------------
# Stage C truth table
# ---------------------------------------------------------------------------


class TestStageCTruthTable:
    def _eval_stage_c(
        self,
        *,
        c_main_pass: bool,
        shadow_all_pass: bool,
        spread_stress_supported: bool = False,
        stress_pass: bool = True,
    ) -> StageCResult:
        bc_input = _make_bc_input()
        c_main = _make_canonical_five_result(
            is_feasible=True,
            gate_pass=c_main_pass,
            gate_worst_gap=0.0 if c_main_pass else 0.5,
        )
        shadow_cf = _make_canonical_five_result(
            is_feasible=True,
            gate_pass=shadow_all_pass,
            gate_worst_gap=0.0 if shadow_all_pass else 0.5,
        )
        stress_cf = _make_canonical_five_result(
            is_feasible=True,
            gate_pass=stress_pass,
            gate_worst_gap=0.0 if stress_pass else 0.5,
        )
        # call order: 12w main → (stress if supported) → 5 shadow pairs
        seq = (
            [c_main, stress_cf] + [shadow_cf] * 5
            if spread_stress_supported
            else [c_main] + [shadow_cf] * 5
        )
        eval_fn = _make_eval_fn(by_call=seq)
        return evaluate_stage_c(
            bc_input,
            evaluate_fn=eval_fn,
            live_criteria=_live_criteria(),
            spread_stress_supported=spread_stress_supported,
        )

    def test_stage_c_live_fail_yields_mission_fail_with_reason_live_criteria(
        self,
    ) -> None:
        r = self._eval_stage_c(c_main_pass=False, shadow_all_pass=True)
        assert r.mission_pass == StagePassStatus.FAIL
        assert r.mission_fail_reason == MissionFailReason.LIVE_CRITERIA

    def test_stage_c_cross_pair_fail_yields_mission_fail_with_reason_cross_pair(
        self,
    ) -> None:
        r = self._eval_stage_c(c_main_pass=True, shadow_all_pass=False)
        assert r.mission_pass == StagePassStatus.FAIL
        assert r.mission_fail_reason == MissionFailReason.CROSS_PAIR

    def test_stage_c_stress_fail_via_evaluate_path_yields_reason_stress(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Codex Round 2 W3 反映: evaluate_stage_c 経路で stress=FAIL truth table 検証.

        ``apply_spread_stress`` を pass-through に monkeypatch して
        ``spread_stress_supported=True`` 経路を通す.
        ``live=True, cross_pair=PASS, stress=FAIL`` → ``MissionFailReason.STRESS``.
        """
        from src.alpha_factory import stage_bc_evaluator as mod

        monkeypatch.setattr(
            mod,
            "apply_spread_stress",
            lambda trades, multiplier: trades,
        )
        r = self._eval_stage_c(
            c_main_pass=True,
            shadow_all_pass=True,
            spread_stress_supported=True,
            stress_pass=False,
        )
        assert r.live_criteria_pass is True
        assert r.cross_pair_pass == StagePassStatus.PASS
        assert r.stress_pass == StagePassStatus.FAIL
        assert r.mission_pass == StagePassStatus.FAIL
        assert r.mission_fail_reason == MissionFailReason.STRESS

    def test_stage_c_cross_pair_fail_and_stress_fail_yields_reason_cross_pair(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Codex Round 2 W2 反映: cross_pair > stress 優先順位衝突テスト.

        ``apply_spread_stress`` を pass-through に monkeypatch して
        ``spread_stress_supported=True`` 経路を通す.
        ``live=True, cross_pair=FAIL, stress=FAIL`` → ``MissionFailReason.CROSS_PAIR``
        (cross_pair が stress より優先).
        """
        from src.alpha_factory import stage_bc_evaluator as mod

        monkeypatch.setattr(
            mod,
            "apply_spread_stress",
            lambda trades, multiplier: trades,
        )
        r = self._eval_stage_c(
            c_main_pass=True,
            shadow_all_pass=False,
            spread_stress_supported=True,
            stress_pass=False,
        )
        assert r.cross_pair_pass == StagePassStatus.FAIL
        assert r.stress_pass == StagePassStatus.FAIL
        assert r.mission_pass == StagePassStatus.FAIL
        assert r.mission_fail_reason == MissionFailReason.CROSS_PAIR

    def test_stage_c_all_pass_via_evaluate_path_yields_mission_pass(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All-pass + spread_stress_supported=True で mission_pass=PASS.

        Codex Round 2 W2/W3 反映の monkeypatch 経路で正常系も検証.
        """
        from src.alpha_factory import stage_bc_evaluator as mod

        monkeypatch.setattr(
            mod,
            "apply_spread_stress",
            lambda trades, multiplier: trades,
        )
        r = self._eval_stage_c(
            c_main_pass=True,
            shadow_all_pass=True,
            spread_stress_supported=True,
            stress_pass=True,
        )
        assert r.mission_pass == StagePassStatus.PASS
        assert r.mission_fail_reason is None

    def test_stage_c_all_pass_yields_mission_pass_when_stress_supported(self) -> None:
        # we cannot run stress because apply_spread_stress raises;
        # default Phase 1 path: stress_pass=PENDING.
        # All-pass on Phase 1 path → mission_pass=PENDING (not PASS)
        r = self._eval_stage_c(c_main_pass=True, shadow_all_pass=True)
        assert r.mission_pass == StagePassStatus.PENDING
        assert r.mission_fail_reason is None

    def test_stage_c_stress_pending_with_live_pass_yields_mission_pending(
        self,
    ) -> None:
        r = self._eval_stage_c(c_main_pass=True, shadow_all_pass=True)
        assert r.stress_pass == StagePassStatus.PENDING
        assert r.mission_pass == StagePassStatus.PENDING

    def test_stage_c_stress_pending_with_live_fail_yields_mission_fail_not_pending(
        self,
    ) -> None:
        # live=False, stress=PENDING → mission=FAIL, reason=LIVE_CRITERIA
        r = self._eval_stage_c(c_main_pass=False, shadow_all_pass=True)
        assert r.mission_pass == StagePassStatus.FAIL
        assert r.mission_fail_reason == MissionFailReason.LIVE_CRITERIA

    def test_stage_c_live_fail_and_cross_pair_fail_yields_reason_live_criteria(
        self,
    ) -> None:
        # priority: LIVE_CRITERIA > CROSS_PAIR
        r = self._eval_stage_c(c_main_pass=False, shadow_all_pass=False)
        assert r.mission_fail_reason == MissionFailReason.LIVE_CRITERIA

    def test_stage_c_cross_pair_pass_is_binary_pass_or_fail_never_pending(self) -> None:
        r = self._eval_stage_c(c_main_pass=True, shadow_all_pass=True)
        assert r.cross_pair_pass in (StagePassStatus.PASS, StagePassStatus.FAIL)

    def test_stage_c_mission_fail_reason_is_none_when_pass_or_pending(self) -> None:
        # PENDING case
        r = self._eval_stage_c(c_main_pass=True, shadow_all_pass=True)
        assert r.mission_pass == StagePassStatus.PENDING
        assert r.mission_fail_reason is None


# ---------------------------------------------------------------------------
# Stage C cross-pair
# ---------------------------------------------------------------------------


class TestStageCCrossPair:
    def test_stage_c_shadow_5_pairs_all_pass_yields_cross_pair_pass(self) -> None:
        bc_input = _make_bc_input()
        cf_pass = _make_canonical_five_result(is_feasible=True, gate_pass=True)
        eval_fn = _make_eval_fn(default=cf_pass)
        r = evaluate_stage_c(
            bc_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )
        assert r.cross_pair_pass == StagePassStatus.PASS

    def test_stage_c_shadow_4_of_5_pairs_pass_yields_cross_pair_fail(self) -> None:
        bc_input = _make_bc_input()
        cf_pass = _make_canonical_five_result(is_feasible=True, gate_pass=True)
        cf_fail = _make_canonical_five_result(
            is_feasible=True, gate_pass=False, gate_worst_gap=0.5
        )
        # call order: 12w main → 5 shadow pairs (one fails)
        seq = [cf_pass, cf_pass, cf_pass, cf_pass, cf_pass, cf_fail]
        eval_fn = _make_eval_fn(by_call=seq)
        r = evaluate_stage_c(
            bc_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )
        assert r.cross_pair_pass == StagePassStatus.FAIL

    def test_stage_c_rejects_missing_shadow_pair_in_input(self) -> None:
        bc_input = _make_bc_input()
        bad_shadow = dict(bc_input.shadow_pairs)
        del bad_shadow["USD_JPY"]
        bad_input = BCEvaluationInput(
            individual_index=bc_input.individual_index,
            trades=bc_input.trades,
            bars=bc_input.bars,
            business_day_universe=bc_input.business_day_universe,
            folds=bc_input.folds,
            stage_c_lite_periods=bc_input.stage_c_lite_periods,
            stage_c_period=bc_input.stage_c_period,
            anchor_bundle=bc_input.anchor_bundle,
            shadow_pairs=bad_shadow,
        )
        cf_pass = _make_canonical_five_result(gate_pass=True)
        eval_fn = _make_eval_fn(default=cf_pass)
        with pytest.raises(StageBCInputError, match="missing required pair"):
            evaluate_stage_c(
                bad_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
            )

    def test_stage_c_rejects_pair_bundle_with_mismatched_pair_field(self) -> None:
        bc_input = _make_bc_input()
        # USD_JPY key but bundle.pair is "WRONG"
        bad_shadow = dict(bc_input.shadow_pairs)
        bad_shadow["USD_JPY"] = _make_pair_bundle("WRONG_PAIR")
        bad_input = BCEvaluationInput(
            individual_index=bc_input.individual_index,
            trades=bc_input.trades,
            bars=bc_input.bars,
            business_day_universe=bc_input.business_day_universe,
            folds=bc_input.folds,
            stage_c_lite_periods=bc_input.stage_c_lite_periods,
            stage_c_period=bc_input.stage_c_period,
            anchor_bundle=bc_input.anchor_bundle,
            shadow_pairs=bad_shadow,
        )
        cf_pass = _make_canonical_five_result(gate_pass=True)
        eval_fn = _make_eval_fn(default=cf_pass)
        with pytest.raises(StageBCInputError, match="!= requested pair"):
            evaluate_stage_c(
                bad_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
            )

    def test_stage_c_rejects_anchor_bundle_with_wrong_pair(self) -> None:
        bc_input = _make_bc_input()
        bad_anchor = _make_pair_bundle("USD_JPY")
        bad_input = BCEvaluationInput(
            individual_index=bc_input.individual_index,
            trades=bc_input.trades,
            bars=bc_input.bars,
            business_day_universe=bc_input.business_day_universe,
            folds=bc_input.folds,
            stage_c_lite_periods=bc_input.stage_c_lite_periods,
            stage_c_period=bc_input.stage_c_period,
            anchor_bundle=bad_anchor,
            shadow_pairs=bc_input.shadow_pairs,
        )
        cf_pass = _make_canonical_five_result(gate_pass=True)
        eval_fn = _make_eval_fn(default=cf_pass)
        with pytest.raises(StageBCInputError, match="STAGE_C_ANCHOR_PAIR"):
            evaluate_stage_c(
                bad_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
            )

    def test_stage_c_anchor_pair_not_in_shadow_evaluation(self) -> None:
        bc_input = _make_bc_input()
        cf_pass = _make_canonical_five_result(gate_pass=True)
        eval_fn = _make_eval_fn(default=cf_pass)
        r = evaluate_stage_c(
            bc_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )
        assert STAGE_C_ANCHOR_PAIR not in r.per_pair_results
        for pair in STAGE_C_SHADOW_PAIR_LIST:
            assert pair in r.per_pair_results


# ---------------------------------------------------------------------------
# apply_spread_stress
# ---------------------------------------------------------------------------


class TestApplySpreadStress:
    def test_apply_spread_stress_phase_1_raises_not_implemented_error(self) -> None:
        with pytest.raises(NotImplementedError, match="T070"):
            apply_spread_stress((), 1.5)


# ---------------------------------------------------------------------------
# compute_cross_pair_shadow_score
# ---------------------------------------------------------------------------


class TestShadowScore:
    def test_shadow_robustness_score_all_pass_yields_one(self) -> None:
        cf_pass = _make_canonical_five_result(gate_pass=True)
        score = compute_cross_pair_shadow_score(
            {f"P{i}": cf_pass for i in range(5)}
        )
        assert score == pytest.approx(1.0)

    def test_shadow_robustness_score_partial_pass_yields_pass_ratio(self) -> None:
        cf_pass = _make_canonical_five_result(gate_pass=True)
        cf_fail = _make_canonical_five_result(
            is_feasible=True, gate_pass=False, gate_worst_gap=0.5
        )
        d = {"P1": cf_pass, "P2": cf_pass, "P3": cf_fail, "P4": cf_fail, "P5": cf_pass}
        score = compute_cross_pair_shadow_score(d)
        assert score == pytest.approx(3 / 5)

    def test_shadow_robustness_score_empty_pairs_yields_none(self) -> None:
        assert compute_cross_pair_shadow_score({}) is None


# ---------------------------------------------------------------------------
# compute_a_b_correlation
# ---------------------------------------------------------------------------


class TestComputeABCorrelation:
    def test_a_b_correlation_source_score_higher_is_better(self) -> None:
        cf_low = _make_canonical_five_result(gate_worst_gap=0.0)
        cf_high = _make_canonical_five_result(gate_worst_gap=2.0)
        s_low = compute_a_b_correlation_source_score(cf_low)
        s_high = compute_a_b_correlation_source_score(cf_high)
        assert s_low > s_high

    def test_a_b_correlation_source_score_full_achievement_yields_one(self) -> None:
        cf = _make_canonical_five_result(gate_worst_gap=0.0)
        assert compute_a_b_correlation_source_score(cf) == pytest.approx(1.0)

    def test_a_b_correlation_source_score_handles_negative_gap_with_clip(self) -> None:
        cf = _make_canonical_five_result(gate_worst_gap=-0.5)
        # negative gap defensive-clipped to 0 → 1.0
        assert compute_a_b_correlation_source_score(cf) == pytest.approx(1.0)

    def test_a_b_correlation_returns_pearson_with_sample_size(self) -> None:
        a = {0: 0.1, 1: 0.5, 2: 0.9}
        b = {0: 0.2, 1: 0.6, 2: 1.0}
        corr, n = compute_a_b_correlation(a, b)
        assert n == 3
        assert corr == pytest.approx(1.0, abs=1e-9)

    def test_a_b_correlation_excludes_individuals_missing_from_either_dict(
        self,
    ) -> None:
        a = {0: 0.1, 1: 0.5, 2: 0.9, 3: 0.2}
        b = {0: 0.2, 1: 0.6}
        corr, n = compute_a_b_correlation(a, b)
        assert n == 2
        # at least 2 common indices, corr computable
        assert math.isfinite(corr)

    def test_a_b_correlation_constant_series_returns_zero_corr(self) -> None:
        # constant series → StatisticsError → (0.0, n)
        a = {0: 0.5, 1: 0.5, 2: 0.5}
        b = {0: 0.1, 1: 0.5, 2: 0.9}
        corr, n = compute_a_b_correlation(a, b)
        assert n == 3
        assert corr == 0.0

    def test_a_b_correlation_below_two_samples_returns_zero(self) -> None:
        corr, n = compute_a_b_correlation({0: 0.1}, {0: 0.5})
        assert n == 1
        assert corr == 0.0


# ---------------------------------------------------------------------------
# select_top_clite_forced_pass_indices
# ---------------------------------------------------------------------------


def _make_clite_result(
    *,
    mission_pass: StagePassStatus,
    progress_pass: StagePassStatus,
    cells_worst: float,
    n_pass_windows: int,
    sample_size_flag: SampleSizeFlag = SampleSizeFlag.OK,
    invariant_ok: bool = True,
) -> StageCLiteResult:
    cf = _make_canonical_five_result(is_feasible=invariant_ok, gate_pass=True)
    windows = tuple(
        StageCLiteWindowResult(window_index=i, cf_result=cf) for i in range(3)
    )
    return StageCLiteResult(
        per_window_results=windows,
        cells_worst=cells_worst,
        mission_pass=mission_pass,
        progress_pass=progress_pass,
        sample_size_flag=sample_size_flag,
        n_pass_windows=n_pass_windows,
    )


class TestForcedPass:
    def test_forced_pass_uses_deterministic_ranking_key(self) -> None:
        # All same status → tie-break by cells_worst asc, then index asc
        results = {
            5: _make_clite_result(
                mission_pass=StagePassStatus.PASS,
                progress_pass=StagePassStatus.PASS,
                cells_worst=0.5,
                n_pass_windows=3,
            ),
            1: _make_clite_result(
                mission_pass=StagePassStatus.PASS,
                progress_pass=StagePassStatus.PASS,
                cells_worst=0.3,
                n_pass_windows=3,
            ),
            3: _make_clite_result(
                mission_pass=StagePassStatus.PASS,
                progress_pass=StagePassStatus.PASS,
                cells_worst=0.3,
                n_pass_windows=3,
            ),
        }
        forced = select_top_clite_forced_pass_indices(results, ratio=0.34)
        # ceil(3 * 0.34) = 2; ranking by cells_worst asc → 1 and 3 (1 < 3 tie-break)
        assert 1 in forced
        assert 3 in forced
        assert 5 not in forced

    def test_forced_pass_excludes_invariant_fail_individuals(self) -> None:
        # INSUFFICIENT == invariant_fail equivalent
        results = {
            0: _make_clite_result(
                mission_pass=StagePassStatus.PENDING,
                progress_pass=StagePassStatus.PENDING,
                cells_worst=0.0,
                n_pass_windows=0,
                sample_size_flag=SampleSizeFlag.INSUFFICIENT,
            ),
            1: _make_clite_result(
                mission_pass=StagePassStatus.PASS,
                progress_pass=StagePassStatus.PASS,
                cells_worst=0.5,
                n_pass_windows=3,
            ),
        }
        forced = select_top_clite_forced_pass_indices(results, ratio=0.5)
        assert 0 not in forced
        assert 1 in forced

    def test_forced_pass_excludes_mission_fail_individuals(self) -> None:
        results = {
            0: _make_clite_result(
                mission_pass=StagePassStatus.FAIL,
                progress_pass=StagePassStatus.FAIL,
                cells_worst=0.1,
                n_pass_windows=0,
            ),
            1: _make_clite_result(
                mission_pass=StagePassStatus.PASS,
                progress_pass=StagePassStatus.PASS,
                cells_worst=0.5,
                n_pass_windows=3,
            ),
        }
        forced = select_top_clite_forced_pass_indices(results, ratio=1.0)
        assert 0 not in forced
        assert 1 in forced

    def test_forced_pass_count_is_max_one_or_ceil_of_eligible_times_ratio(self) -> None:
        # 1 eligible, ratio 0.30 → max(1, ceil(1*0.3)=1) = 1
        results = {
            0: _make_clite_result(
                mission_pass=StagePassStatus.PASS,
                progress_pass=StagePassStatus.PASS,
                cells_worst=0.0,
                n_pass_windows=3,
            ),
        }
        forced = select_top_clite_forced_pass_indices(
            results, ratio=STAGE_C_LITE_FORCED_PASS_RATIO
        )
        assert len(forced) == 1

    def test_forced_pass_empty_input_yields_empty(self) -> None:
        assert select_top_clite_forced_pass_indices({}) == frozenset()

    def test_forced_pass_rejects_invalid_ratio(self) -> None:
        with pytest.raises(StageBCInputError, match="ratio"):
            select_top_clite_forced_pass_indices({}, ratio=-0.1)
        with pytest.raises(StageBCInputError, match="ratio"):
            select_top_clite_forced_pass_indices({}, ratio=1.1)

    def test_forced_pass_rejects_unknown_status_in_status_rank(self) -> None:
        """Codex Round 2 W1 反映: _status_rank が未知 StagePassStatus を ValueError raise.

        eligible filter は ``mission_pass != FAIL`` でも、 ``progress_pass`` 値が未知の場合に
        _status_rank で raise する経路を mock dataclass で test.
        """

        @dataclass(frozen=True)
        class _StubCLite:
            mission_pass: object
            progress_pass: object
            sample_size_flag: SampleSizeFlag
            per_window_results: tuple
            cells_worst: float

        # status field 方式の規範: 未知値は silent FAIL 同等扱いを禁止 → ValueError raise
        bad = _StubCLite(
            mission_pass=StagePassStatus.PASS,
            progress_pass="UNKNOWN_STATUS",
            sample_size_flag=SampleSizeFlag.OK,
            per_window_results=(),
            cells_worst=0.0,
        )
        with pytest.raises(ValueError, match="unknown StagePassStatus"):
            select_top_clite_forced_pass_indices(
                {0: bad}  # type: ignore[dict-item]
            )


# ---------------------------------------------------------------------------
# evaluate_bc_for_a_pass (top-level)
# ---------------------------------------------------------------------------


class TestEvaluateBcForAPass:
    def test_evaluate_bc_perfect_individual_yields_mission_pass(self) -> None:
        # All canonical_five results pass → c_lite mission=PASS,
        # but stress=PENDING (Phase 1), so c_result.mission=PENDING
        bc_input = _make_bc_input()
        cf_pass = _make_canonical_five_result(is_feasible=True, gate_pass=True)
        eval_fn = _make_eval_fn(default=cf_pass)
        results = evaluate_bc_for_a_pass(
            {0: bc_input},
            evaluate_fn=eval_fn,
            live_criteria=_live_criteria(),
        )
        assert 0 in results
        r = results[0]
        # Stage C without spread_stress_supported → PENDING
        assert r.mission_pass == StagePassStatus.PENDING
        assert r.pareto_axis_usable is True

    def test_evaluate_bc_b_invariant_fail_yields_pareto_axis_unusable(self) -> None:
        bc_input = _make_bc_input()
        infeasible = _make_canonical_five_result(is_feasible=False)
        eval_fn = _make_eval_fn(default=infeasible)
        results = evaluate_bc_for_a_pass(
            {0: bc_input},
            evaluate_fn=eval_fn,
            live_criteria=_live_criteria(),
        )
        r = results[0]
        assert r.pareto_axis_usable is False
        assert r.b_pooled_cf is None

    def test_evaluate_bc_c_lite_insufficient_sample_yields_mission_pending_at_clite(
        self,
    ) -> None:
        bc_input = _make_bc_input()
        # Override universe to be small so c_lite gets INSUFFICIENT
        small_universe = {b: frozenset(range(20)) for b in SessionBucket}
        new_input = BCEvaluationInput(
            individual_index=bc_input.individual_index,
            trades=bc_input.trades,
            bars=bc_input.bars,
            business_day_universe=small_universe,
            folds=bc_input.folds,
            stage_c_lite_periods=bc_input.stage_c_lite_periods,
            stage_c_period=bc_input.stage_c_period,
            anchor_bundle=bc_input.anchor_bundle,
            shadow_pairs=bc_input.shadow_pairs,
        )
        cf_pass = _make_canonical_five_result(is_feasible=True, gate_pass=True)
        eval_fn = _make_eval_fn(default=cf_pass)
        results = evaluate_bc_for_a_pass(
            {0: new_input},
            evaluate_fn=eval_fn,
            live_criteria=_live_criteria(),
        )
        r = results[0]
        assert r.c_lite_result.mission_pass == StagePassStatus.PENDING
        assert r.c_lite_result.sample_size_flag == SampleSizeFlag.INSUFFICIENT

    def test_evaluate_bc_stress_unsupported_default_yields_stage_c_mission_pending(
        self,
    ) -> None:
        bc_input = _make_bc_input()
        cf_pass = _make_canonical_five_result(is_feasible=True, gate_pass=True)
        eval_fn = _make_eval_fn(default=cf_pass)
        results = evaluate_bc_for_a_pass(
            {0: bc_input},
            evaluate_fn=eval_fn,
            live_criteria=_live_criteria(),
            spread_stress_supported=False,
        )
        r = results[0]
        assert r.c_result.stress_pass == StagePassStatus.PENDING
        assert r.c_result.mission_pass == StagePassStatus.PENDING


# ---------------------------------------------------------------------------
# Follow-up (T066 Phase 0): n_pass_windows / c_pass_depth
# ---------------------------------------------------------------------------


class TestFollowUpNPassWindowsContract:
    def test_stage_c_lite_result_has_n_pass_windows_field(self) -> None:
        # __dataclass_fields__ ベース存在検証
        flds = {f.name: f for f in fields(StageCLiteResult)}
        assert "n_pass_windows" in flds
        # type annotation 確認 (string due to from __future__ import annotations)
        assert flds["n_pass_windows"].type in ("int", int)

    def test_stage_c_lite_n_pass_windows_matches_per_window_gate_pass_count(
        self,
    ) -> None:
        bc_input = _make_bc_input()
        cf_pass = _make_canonical_five_result(is_feasible=True, gate_pass=True)
        cf_fail = _make_canonical_five_result(
            is_feasible=True, gate_pass=False, gate_worst_gap=0.5
        )
        # 2 pass + 1 fail
        eval_fn = _make_eval_fn(by_call=[cf_pass, cf_fail, cf_pass])
        result = evaluate_stage_c_lite(
            bc_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )
        assert result.n_pass_windows == 2

    def test_stage_c_lite_n_pass_windows_zero_when_all_windows_fail(self) -> None:
        bc_input = _make_bc_input()
        cf_fail = _make_canonical_five_result(
            is_feasible=True, gate_pass=False, gate_worst_gap=0.5
        )
        eval_fn = _make_eval_fn(default=cf_fail)
        result = evaluate_stage_c_lite(
            bc_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )
        assert result.n_pass_windows == 0

    def test_stage_c_lite_n_pass_windows_three_when_all_windows_pass(self) -> None:
        bc_input = _make_bc_input()
        cf_pass = _make_canonical_five_result(is_feasible=True, gate_pass=True)
        eval_fn = _make_eval_fn(default=cf_pass)
        result = evaluate_stage_c_lite(
            bc_input, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )
        assert result.n_pass_windows == 3

    def test_stage_c_lite_result_rejects_n_pass_windows_out_of_range(self) -> None:
        cf = _make_canonical_five_result(gate_pass=True)
        windows = tuple(
            StageCLiteWindowResult(window_index=i, cf_result=cf) for i in range(3)
        )
        with pytest.raises(ValueError, match="n_pass_windows must be in"):
            StageCLiteResult(
                per_window_results=windows,
                cells_worst=0.0,
                mission_pass=StagePassStatus.PASS,
                progress_pass=StagePassStatus.PASS,
                sample_size_flag=SampleSizeFlag.OK,
                n_pass_windows=-1,
            )
        with pytest.raises(ValueError, match="n_pass_windows must be in"):
            StageCLiteResult(
                per_window_results=windows,
                cells_worst=0.0,
                mission_pass=StagePassStatus.PASS,
                progress_pass=StagePassStatus.PASS,
                sample_size_flag=SampleSizeFlag.OK,
                n_pass_windows=4,
            )

    def test_stage_c_lite_result_rejects_n_pass_exceeds_per_window_count(
        self,
    ) -> None:
        cf = _make_canonical_five_result(gate_pass=True)
        # only 2 windows but n_pass_windows=3
        windows = (
            StageCLiteWindowResult(window_index=0, cf_result=cf),
            StageCLiteWindowResult(window_index=1, cf_result=cf),
        )
        with pytest.raises(ValueError, match="cannot exceed"):
            StageCLiteResult(
                per_window_results=windows,
                cells_worst=0.0,
                mission_pass=StagePassStatus.PASS,
                progress_pass=StagePassStatus.PASS,
                sample_size_flag=SampleSizeFlag.OK,
                n_pass_windows=3,
            )


# ---------------------------------------------------------------------------
# c_pass_depth contract + 計算 (12 ケース 3 status × 4 n)
# ---------------------------------------------------------------------------


def _make_stage_c_result(mission_pass: StagePassStatus) -> StageCResult:
    cf = _make_canonical_five_result(gate_pass=True)
    return StageCResult(
        c_cf_result=cf,
        stress_cf_result=None,
        per_pair_results={},
        live_criteria_pass=mission_pass != StagePassStatus.FAIL,
        stress_pass=StagePassStatus.PENDING,
        cross_pair_pass=StagePassStatus.PASS,
        mission_pass=mission_pass,
        mission_fail_reason=None
        if mission_pass != StagePassStatus.FAIL
        else MissionFailReason.LIVE_CRITERIA,
        shadow_robustness_score=1.0,
    )


def _make_clite_with_n(n_pass_windows: int) -> StageCLiteResult:
    return _make_clite_result(
        mission_pass=StagePassStatus.PASS,
        progress_pass=StagePassStatus.PASS,
        cells_worst=0.0,
        n_pass_windows=n_pass_windows,
    )


class TestComputeCPassDepth:
    def test_bc_evaluation_result_has_c_pass_depth_field(self) -> None:
        flds = {f.name: f for f in fields(BCEvaluationResult)}
        assert "c_pass_depth" in flds
        assert flds["c_pass_depth"].type in ("float", float)

    def test_compute_c_pass_depth_pass_n3_yields_one_point_seven_five(self) -> None:
        depth = compute_c_pass_depth(
            _make_clite_with_n(3), _make_stage_c_result(StagePassStatus.PASS)
        )
        assert depth == pytest.approx(1.75)

    def test_compute_c_pass_depth_fail_n0_yields_zero(self) -> None:
        depth = compute_c_pass_depth(
            _make_clite_with_n(0), _make_stage_c_result(StagePassStatus.FAIL)
        )
        assert depth == pytest.approx(0.0)

    def test_compute_c_pass_depth_pending_n1_yields_zero_point_seven_five(self) -> None:
        depth = compute_c_pass_depth(
            _make_clite_with_n(1), _make_stage_c_result(StagePassStatus.PENDING)
        )
        assert depth == pytest.approx(0.75)

    def test_compute_c_pass_depth_fail_n2_yields_zero_point_five(self) -> None:
        depth = compute_c_pass_depth(
            _make_clite_with_n(2), _make_stage_c_result(StagePassStatus.FAIL)
        )
        assert depth == pytest.approx(0.5)

    def test_compute_c_pass_depth_deterministic_for_same_input(self) -> None:
        c_lite = _make_clite_with_n(2)
        c_result = _make_stage_c_result(StagePassStatus.PENDING)
        d1 = compute_c_pass_depth(c_lite, c_result)
        d2 = compute_c_pass_depth(c_lite, c_result)
        assert d1 == d2

    def test_compute_c_pass_depth_value_range_inclusive_zero_and_one_point_seven_five(
        self,
    ) -> None:
        # 3 status × 4 n = 12 cases
        for status in (
            StagePassStatus.PASS,
            StagePassStatus.PENDING,
            StagePassStatus.FAIL,
        ):
            for n in (0, 1, 2, 3):
                depth = compute_c_pass_depth(
                    _make_clite_with_n(n), _make_stage_c_result(status)
                )
                assert 0.0 <= depth <= 1.75
                if status == StagePassStatus.FAIL:
                    assert 0.0 <= depth <= 0.75
                elif status == StagePassStatus.PENDING:
                    assert 0.5 <= depth <= 1.25
                else:
                    assert 1.0 <= depth <= 1.75

    def test_compute_c_pass_depth_rejects_unknown_status(self) -> None:
        # mock with a status that is StagePassStatus-compatible but unknown.
        # Use a non-StagePassStatus enum-like sentinel via a stub dataclass.
        @dataclass(frozen=True)
        class _StubStageCResult:
            mission_pass: object

        bad_c = _StubStageCResult(mission_pass="UNKNOWN_VALUE")
        with pytest.raises(ValueError, match="unknown StagePassStatus"):
            compute_c_pass_depth(_make_clite_with_n(0), bad_c)  # type: ignore[arg-type]

    def test_compute_c_pass_depth_rejects_n_pass_windows_out_of_range(self) -> None:
        # bypass StageCLiteResult.__post_init__ by stub dataclass
        @dataclass(frozen=True)
        class _StubCLite:
            n_pass_windows: int

        bad_lite = _StubCLite(n_pass_windows=99)
        with pytest.raises(ValueError, match="n_pass_windows must be in"):
            compute_c_pass_depth(
                bad_lite,  # type: ignore[arg-type]
                _make_stage_c_result(StagePassStatus.PASS),
            )

    def test_evaluate_bc_for_a_pass_yields_c_pass_depth_consistent_with_compute_c_pass_depth(
        self,
    ) -> None:
        bc_input = _make_bc_input()
        cf_pass = _make_canonical_five_result(is_feasible=True, gate_pass=True)
        eval_fn = _make_eval_fn(default=cf_pass)
        results = evaluate_bc_for_a_pass(
            {0: bc_input}, evaluate_fn=eval_fn, live_criteria=_live_criteria()
        )
        r = results[0]
        expected = compute_c_pass_depth(r.c_lite_result, r.c_result)
        assert r.c_pass_depth == expected


# ---------------------------------------------------------------------------
# compute_gate_pass_excluding_dd
# ---------------------------------------------------------------------------


class TestGatePassExcludingDD:
    def test_gate_pass_ex_dd_true_when_all_non_dd_axes_pass(self) -> None:
        cf = _make_canonical_five_result(
            is_feasible=True,
            slack_sharpe=0.1,
            slack_pnl=0.1,
            slack_dd=-100.0,  # would fail full gate, but we exclude it
            slack_tc=0.1,
            slack_wr=0.1,
        )
        from src.alpha_factory.canonical_metrics import CanonicalFiveThresholds

        thresholds = CanonicalFiveThresholds(
            sharpe_min=1.0,
            net_pnl_min=50000.0,
            max_dd_max=0.20,
            trade_count_min=50,
            trade_count_max=5000,
            win_rate_min=0.45,
        )
        assert compute_gate_pass_excluding_dd(cf, thresholds) is True

    def test_gate_pass_ex_dd_false_when_invariants_fail(self) -> None:
        cf = _make_canonical_five_result(is_feasible=False)
        from src.alpha_factory.canonical_metrics import CanonicalFiveThresholds

        thresholds = CanonicalFiveThresholds(
            sharpe_min=1.0,
            net_pnl_min=50000.0,
            max_dd_max=0.20,
            trade_count_min=50,
            trade_count_max=5000,
            win_rate_min=0.45,
        )
        assert compute_gate_pass_excluding_dd(cf, thresholds) is False

    def test_gate_pass_ex_dd_false_when_non_dd_axis_fails(self) -> None:
        cf = _make_canonical_five_result(
            is_feasible=True,
            slack_sharpe=-0.5,  # negative gap on non-DD axis → fail
            slack_pnl=0.5,
            slack_tc=0.5,
            slack_wr=0.5,
        )
        from src.alpha_factory.canonical_metrics import CanonicalFiveThresholds

        thresholds = CanonicalFiveThresholds(
            sharpe_min=1.0,
            net_pnl_min=50000.0,
            max_dd_max=0.20,
            trade_count_min=50,
            trade_count_max=5000,
            win_rate_min=0.45,
        )
        assert compute_gate_pass_excluding_dd(cf, thresholds) is False
