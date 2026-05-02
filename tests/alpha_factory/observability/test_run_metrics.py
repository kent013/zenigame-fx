"""T071 Observability hub unit tests (F1-F15 厳密 1:1 対応).

設計参照: devnotes/20260430-1925-todo-T071-observability/detailed-design.md § 5 / § 6.

main 実装 SSOT 規範 (T058-T070 で確立) で詳細設計と実装の field が乖離する箇所
は run_metrics.py docstring 参照。 本 test は main 実装の dataclass を直接構築
するか、 必要 field のみを保持する dummy 表現で代替して T071 の振る舞いを検証する。
"""

from __future__ import annotations

import types
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

import pytest

from src.alpha_factory.cpps_archive import AdmissionReport
from src.alpha_factory.failure_handling import (
    FailureSummary,
    RunFailureSummary,
    StageType,
)
from src.alpha_factory.nsga2_selection import GenerationSelectionResult
from src.alpha_factory.observability.run_metrics import (
    AB_MIN_ACTIONABLE_PAIRS,
    DELTA_PER_RUN,
    DIVERGENCE_THRESHOLD,
    Q_FORCE_MAX,
    Q_FORCE_MIN,
    RESTORE_THRESHOLD,
    SESSION_PATTERN_BITS,
    WARMSTART_SHARE_TOLERANCE,
    WEEKLY_WINDOW_SIZE,
    ABDivergenceMetric,
    ArchiveChurnMetric,
    BypassRatioMetric,
    FailureMetric,
    FailureMetricStage,
    FeasibleRatioMetric,
    InflowConsistencyMetric,
    QForceRecommendation,
    RunObservabilityReport,
    SelectionMetric,
    SessionEntropyMetric,
    build_run_observability_report,
    build_stub_run_observability_report,
    compute_ab_divergence_on_b_evaluated,
    compute_archive_churn,
    compute_bypass_ratio,
    compute_session_entropy,
    extract_failure_metrics,
    extract_inflow_consistency,
    extract_selection_metrics,
    recommend_q_force_adjust,
    serialize_run_observability_report,
)

# ============================================================================
# Test fixtures (main 実装 SSOT で必要 field のみを満たす最小コンストラクタ)
# ============================================================================


def _make_admission_report(
    *,
    n_admitted_mission: int = 0,
    n_admitted_progress: int = 0,
    n_admitted_bypass: int = 0,
    evicted_count: int = 0,
    mode: str = "normal",
) -> AdmissionReport:
    """T066 main 実装 ``AdmissionReport`` を最小 field で構築."""
    return AdmissionReport(
        admitted_genome_ids=tuple(
            f"adm_{i}"
            for i in range(
                n_admitted_mission + n_admitted_progress + n_admitted_bypass
            )
        ),
        evicted_genome_ids=tuple(f"ev_{i}" for i in range(evicted_count)),
        n_selected_mission=n_admitted_mission,
        n_selected_progress=n_admitted_progress,
        n_selected_bypass=n_admitted_bypass,
        n_admitted_mission=n_admitted_mission,
        n_admitted_progress=n_admitted_progress,
        n_admitted_bypass=n_admitted_bypass,
        mode=mode,  # type: ignore[arg-type]
        hard_constraint_drops=0,
        recency_floor_unmet=False,
        dataset_epoch_reset=False,
    )


@dataclass(frozen=True)
class _DummyWarmstartReport:
    """T071 ``extract_inflow_consistency`` が必要とする field のみを持つ dummy.

    main 実装 ``WarmstartReport`` は ``WarmstartSelection`` (= ``WarmstartCandidate``
    列) を要求し、 完全構築は煩雑なため、 T071 が読む 2 field
    (``share`` / ``relaxation_steps``) のみを持つ duck-typed dummy を使用する。
    """

    share: float
    relaxation_steps: tuple[str, ...] = ()


def _make_failure_summary(
    *,
    stage: StageType = "stage_a",
    n_failed_genomes: int = 0,
    eligible_individuals: int = 10,
    n_failure_records: int | None = None,
) -> FailureSummary:
    n_records = (
        n_failure_records if n_failure_records is not None else n_failed_genomes
    )
    succeeded = max(eligible_individuals - n_failed_genomes, 0)
    all_failed = (
        n_failed_genomes == eligible_individuals and eligible_individuals > 0
    )
    failure_rate = n_failed_genomes / max(eligible_individuals, 1)
    return FailureSummary(
        stage=stage,
        eligible_individuals=eligible_individuals,
        n_failure_records=n_records,
        n_failed_genomes=n_failed_genomes,
        n_succeeded_genomes=succeeded,
        all_failed=all_failed,
        failed_genome_ids=tuple(f"g_{i}" for i in range(n_failed_genomes)),
        failures_by_reason=types.MappingProxyType({}),
        failure_rate=failure_rate,
    )


def _make_run_failure_summary(
    *,
    run_id: str = "run_001",
    per_stage: tuple[FailureSummary, ...] = (),
) -> RunFailureSummary:
    any_stage_all_failed = any(s.all_failed for s in per_stage)
    return RunFailureSummary(
        run_id=run_id,
        per_stage_summaries=per_stage,
        any_stage_all_failed=any_stage_all_failed,
    )


def _make_generation_selection_result(
    *,
    front_assignments: dict[int, int] | None = None,
    crowding_distances: dict[int, float] | None = None,
    survivor_indices: tuple[int, ...] = (),
    parent_pairs: tuple[tuple[int, int], ...] = (),
    excluded_indices: frozenset[int] = frozenset(),
    sample_size_warnings: tuple[str, ...] = (),
) -> GenerationSelectionResult:
    fa = front_assignments if front_assignments is not None else {}
    cd = crowding_distances if crowding_distances is not None else {}
    return GenerationSelectionResult(
        front_assignments=types.MappingProxyType(fa),
        crowding_distances=types.MappingProxyType(cd),
        survivor_indices=survivor_indices,
        parent_pairs=parent_pairs,
        excluded_indices=excluded_indices,
        sample_size_warnings=sample_size_warnings,
    )


# ============================================================================
# F1 / F2 / F3 / F12: compute_ab_divergence_on_b_evaluated
# ============================================================================


class TestComputeABDivergence:
    def test_F1a_n_zero_returns_insufficient_data(self) -> None:
        result = compute_ab_divergence_on_b_evaluated([], [])
        assert result.status == "insufficient_data"
        assert result.n_pairs == 0
        assert result.corr == Decimal(0)

    def test_F1b_n_below_min_actionable_returns_insufficient_data(self) -> None:
        # Round 1 [C3] 反映: n<10 で insufficient_data
        result = compute_ab_divergence_on_b_evaluated(
            [Decimal(i) for i in range(5)],
            [Decimal(2 * i) for i in range(5)],
        )
        assert result.status == "insufficient_data"
        assert result.n_pairs == 5
        assert result.corr == Decimal(0)

    def test_F2a_zero_variance_a(self) -> None:
        # n>=10 (= AB_MIN_ACTIONABLE_PAIRS) で var(a)=0 を作る
        result = compute_ab_divergence_on_b_evaluated(
            [Decimal("1.0")] * 10,
            [Decimal(i) for i in range(10)],
        )
        assert result.status == "zero_variance"
        assert result.n_pairs == 10

    def test_F2b_zero_variance_b(self) -> None:
        result = compute_ab_divergence_on_b_evaluated(
            [Decimal(i) for i in range(10)],
            [Decimal("3.0")] * 10,
        )
        assert result.status == "zero_variance"

    def test_F3a_perfect_positive_correlation(self) -> None:
        result = compute_ab_divergence_on_b_evaluated(
            [Decimal(i) for i in range(10)],
            [Decimal(2 * i) for i in range(10)],
        )
        assert result.status == "ok"
        assert abs(result.corr - Decimal(1)) < Decimal("0.001")

    def test_F3b_perfect_negative_correlation(self) -> None:
        result = compute_ab_divergence_on_b_evaluated(
            [Decimal(i) for i in range(10)],
            [Decimal(-2 * i) for i in range(10)],
        )
        assert result.status == "ok"
        assert abs(result.corr - Decimal(-1)) < Decimal("0.001")

    def test_F3_clamp_keeps_corr_in_range(self) -> None:
        # 完全相関が clamp 内で安定 (= [-1, 1] 越境しない)
        result = compute_ab_divergence_on_b_evaluated(
            [Decimal(i) for i in range(10)],
            [Decimal(i) for i in range(10)],
        )
        assert Decimal(-1) <= result.corr <= Decimal(1)

    def test_F12_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="length mismatch"):
            compute_ab_divergence_on_b_evaluated(
                [Decimal(1)], [Decimal(1), Decimal(2)],
            )


# ============================================================================
# F4 / F5 / F15: recommend_q_force_adjust
# ============================================================================


def _ab_ok(corr: Decimal, n_pairs: int = 10) -> ABDivergenceMetric:
    return ABDivergenceMetric(status="ok", corr=corr, n_pairs=n_pairs)


class TestRecommendQForceAdjust:
    def test_F4a_raise_when_below_threshold(self) -> None:
        # corr < 0.30 で raise
        rec = recommend_q_force_adjust(
            current_q_force=Decimal("0.20"),
            divergence=_ab_ok(Decimal("0.10")),
            consecutive_divergent_runs=1,
        )
        assert rec.reason == "raise"
        assert rec.delta == DELTA_PER_RUN
        assert rec.new_q_force == Decimal("0.22")
        assert rec.consecutive_divergent_runs == 1

    def test_F4b_restore_when_above_threshold(self) -> None:
        # corr >= 0.50 で restore
        rec = recommend_q_force_adjust(
            current_q_force=Decimal("0.30"),
            divergence=_ab_ok(Decimal("0.60")),
            consecutive_divergent_runs=0,
        )
        assert rec.reason == "restore"
        assert rec.delta == -DELTA_PER_RUN
        assert rec.new_q_force == Decimal("0.28")

    def test_F4c_clamped_at_max(self) -> None:
        rec = recommend_q_force_adjust(
            current_q_force=Decimal("0.39"),
            divergence=_ab_ok(Decimal("0.05")),
            consecutive_divergent_runs=10,
        )
        assert rec.reason == "raise"
        assert rec.new_q_force == Q_FORCE_MAX  # 0.40 clamp
        assert rec.clamped_at_max is True

    def test_F4d_clamped_at_min(self) -> None:
        rec = recommend_q_force_adjust(
            current_q_force=Decimal("0.16"),
            divergence=_ab_ok(Decimal("0.80")),
            consecutive_divergent_runs=0,
        )
        assert rec.reason == "restore"
        assert rec.new_q_force == Q_FORCE_MIN
        assert rec.clamped_at_min is True

    def test_F5a_hold_in_hysteresis(self) -> None:
        # 0.30 <= corr < 0.50 で hold
        rec = recommend_q_force_adjust(
            current_q_force=Decimal("0.25"),
            divergence=_ab_ok(Decimal("0.40")),
            consecutive_divergent_runs=0,
        )
        assert rec.reason == "hold"
        assert rec.delta == Decimal(0)
        assert rec.new_q_force == Decimal("0.25")

    def test_F5b_no_oscillation_at_boundary(self) -> None:
        # corr=0.30: hold (raise threshold は < 判定、 振動なし)
        rec1 = recommend_q_force_adjust(
            current_q_force=Decimal("0.20"),
            divergence=_ab_ok(Decimal("0.30")),
            consecutive_divergent_runs=0,
        )
        assert rec1.reason == "hold"
        # corr=0.50: restore (>= 判定、 hysteresis 端)
        rec2 = recommend_q_force_adjust(
            current_q_force=Decimal("0.20"),
            divergence=_ab_ok(Decimal("0.50")),
            consecutive_divergent_runs=0,
        )
        assert rec2.reason == "restore"

    def test_F15a_delta_applied_before_clamp(self) -> None:
        # F15: delta 適用 → clamp の順序、 clamp 結果が clamped_at_* 経由で観測可能
        rec = recommend_q_force_adjust(
            current_q_force=Decimal("0.40"),
            divergence=_ab_ok(Decimal("0.05")),
            consecutive_divergent_runs=10,
        )
        # current=0.40 + delta=0.02 → 0.42 → clamp to 0.40
        assert rec.new_q_force == Q_FORCE_MAX
        assert rec.clamped_at_max is True
        assert rec.delta == Decimal(0)  # = new_q_force - current = 0

    def test_F15b_clamp_after_delta_for_max(self) -> None:
        # 既に max で raise: clamp 後 delta=0
        rec = recommend_q_force_adjust(
            current_q_force=Q_FORCE_MAX,
            divergence=_ab_ok(Decimal("0.05")),
            consecutive_divergent_runs=10,
        )
        assert rec.new_q_force == Q_FORCE_MAX
        assert rec.delta == Decimal(0)

    def test_F15c_clamp_after_delta_for_min(self) -> None:
        rec = recommend_q_force_adjust(
            current_q_force=Q_FORCE_MIN,
            divergence=_ab_ok(Decimal("0.80")),
            consecutive_divergent_runs=0,
        )
        assert rec.new_q_force == Q_FORCE_MIN
        assert rec.delta == Decimal(0)

    def test_F4e_insufficient_data_holds(self) -> None:
        rec = recommend_q_force_adjust(
            current_q_force=Decimal("0.20"),
            divergence=ABDivergenceMetric(
                status="insufficient_data", corr=Decimal(0), n_pairs=0,
            ),
            consecutive_divergent_runs=0,
        )
        assert rec.reason == "insufficient_data"
        assert rec.delta == Decimal(0)
        assert rec.new_q_force == Decimal("0.20")

    def test_F4f_zero_variance_holds(self) -> None:
        rec = recommend_q_force_adjust(
            current_q_force=Decimal("0.20"),
            divergence=ABDivergenceMetric(
                status="zero_variance", corr=Decimal(0), n_pairs=20,
            ),
            consecutive_divergent_runs=2,
        )
        assert rec.reason == "zero_variance"
        assert rec.delta == Decimal(0)
        assert rec.consecutive_divergent_runs == 2

    def test_recommend_invalid_q_force_raises(self) -> None:
        with pytest.raises(ValueError, match="current_q_force"):
            recommend_q_force_adjust(
                current_q_force=Decimal("0.50"),  # > Q_FORCE_MAX
                divergence=_ab_ok(Decimal("0.10")),
                consecutive_divergent_runs=0,
            )


# ============================================================================
# F6: compute_archive_churn
# ============================================================================


class TestComputeArchiveChurn:
    def test_F6a_empty_input_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            compute_archive_churn([])

    def test_F6b_one_run_returns_insufficient(self) -> None:
        result = compute_archive_churn(
            [_make_admission_report(n_admitted_mission=10, evicted_count=2)]
        )
        assert result.status == "insufficient_runs"
        assert result.n_runs_used == 1
        assert result.churn_rate == Decimal("0.2")

    def test_F6c_three_runs_ok(self) -> None:
        result = compute_archive_churn([
            _make_admission_report(n_admitted_mission=10, evicted_count=2)
            for _ in range(3)
        ])
        assert result.status == "ok"
        assert result.n_runs_used == 3
        # total_evictions / total_admissions = 6 / 30 = 0.2
        assert result.churn_rate == Decimal("0.2")

    def test_F6c_more_than_three_uses_last_three(self) -> None:
        # 4 件渡しても直近 3 件のみ使用
        reports = [
            _make_admission_report(n_admitted_mission=100, evicted_count=0),
            _make_admission_report(n_admitted_mission=10, evicted_count=2),
            _make_admission_report(n_admitted_mission=10, evicted_count=2),
            _make_admission_report(n_admitted_mission=10, evicted_count=2),
        ]
        result = compute_archive_churn(reports)
        assert result.n_runs_used == 3
        assert result.n_total_admissions == 30  # 直近 3 件のみ

    def test_F6d_zero_admissions(self) -> None:
        # total_admissions=0 → churn_rate=0
        result = compute_archive_churn([_make_admission_report()])
        assert result.churn_rate == Decimal(0)
        assert result.n_total_admissions == 0


# ============================================================================
# F7: compute_bypass_ratio
# ============================================================================


class TestComputeBypassRatio:
    def test_F7a_zero_total_returns_zero(self) -> None:
        report = _make_admission_report()
        result = compute_bypass_ratio(report)
        assert result.bypass_ratio == Decimal(0)
        assert result.n_total_admissions == 0

    def test_F7b_normal(self) -> None:
        report = _make_admission_report(
            n_admitted_mission=5,
            n_admitted_progress=3,
            n_admitted_bypass=2,
        )
        result = compute_bypass_ratio(report)
        assert result.bypass_ratio == Decimal("0.2")
        assert result.n_total_admissions == 10
        assert result.n_admitted_by_role["score_bypass"] == 2

    def test_F7c_all_bypass(self) -> None:
        report = _make_admission_report(n_admitted_bypass=5)
        result = compute_bypass_ratio(report)
        assert result.bypass_ratio == Decimal(1)


# ============================================================================
# F8: compute_session_entropy
# ============================================================================


class TestComputeSessionEntropy:
    def test_F8a_insufficient_window(self) -> None:
        patterns = ["111"] * 10
        result = compute_session_entropy(patterns, n_runs_aggregated=3)
        assert result.status == "insufficient_window"
        assert result.shannon_entropy == Decimal(0)
        assert result.n_archive_members == 10
        assert result.n_unique_patterns == 0

    def test_F8b_empty_archive(self) -> None:
        result = compute_session_entropy([], n_runs_aggregated=7)
        assert result.status == "empty_archive"
        assert result.n_archive_members == 0
        assert result.shannon_entropy == Decimal(0)

    def test_F8c_uniform_distribution(self) -> None:
        # 全 8 パターン等頻度 → entropy = log2(8) = 3
        patterns: list[str] = []
        for i in range(8):
            patterns.extend([format(i, "03b")] * 10)
        result = compute_session_entropy(patterns, n_runs_aggregated=7)
        assert result.status == "ok"
        assert abs(result.shannon_entropy - Decimal(3)) < Decimal("0.01")
        assert abs(result.relative_entropy - Decimal(1)) < Decimal("0.01")
        assert result.n_unique_patterns == 8

    def test_F8d_single_pattern(self) -> None:
        # 1 パターンのみ → entropy = 0
        patterns = ["111"] * 10
        result = compute_session_entropy(patterns, n_runs_aggregated=7)
        assert result.status == "ok"
        assert result.shannon_entropy == Decimal(0)
        assert result.relative_entropy == Decimal(0)
        assert result.n_unique_patterns == 1

    def test_F8e_invalid_pattern_raises(self) -> None:
        # Round 1 [C4] 反映: SESSION_PATTERN_REGEX 違反は ValueError
        patterns = ["1,1,0"]  # 3 bit string でない
        with pytest.raises(ValueError, match="session_pass_pattern"):
            compute_session_entropy(patterns, n_runs_aggregated=7)

    def test_F8f_invalid_pattern_too_long_raises(self) -> None:
        patterns = ["1111"]  # 4 bit
        with pytest.raises(ValueError, match="session_pass_pattern"):
            compute_session_entropy(patterns, n_runs_aggregated=7)

    def test_F8g_negative_n_runs_raises(self) -> None:
        with pytest.raises(ValueError, match="n_runs_aggregated"):
            compute_session_entropy([], n_runs_aggregated=-1)


# ============================================================================
# F9: extract_inflow_consistency
# ============================================================================


class TestExtractInflowConsistency:
    def test_F9a_within_tolerance(self) -> None:
        warmstart = _DummyWarmstartReport(share=0.205)
        admission = _make_admission_report(
            n_admitted_mission=80,
            n_admitted_progress=15,
            n_admitted_bypass=5,
        )
        result = extract_inflow_consistency(
            warmstart,  # type: ignore[arg-type]
            admission,
            warmstart_share_target=Decimal("0.200"),
        )
        # drift = 0.205 - 0.200 = 0.005 (<= 0.01 tolerance)
        assert abs(result.share_drift - Decimal("0.005")) < Decimal("1e-9")
        assert result.within_tolerance is True
        assert result.bypass_inflow_actual == 5
        assert result.ca_inflow_actual == 100

    def test_F9b_drift_exceeds_tolerance(self) -> None:
        warmstart = _DummyWarmstartReport(
            share=0.250, relaxation_steps=("mode_relax",)
        )
        admission = _make_admission_report(n_admitted_mission=100)
        result = extract_inflow_consistency(
            warmstart,  # type: ignore[arg-type]
            admission,
            warmstart_share_target=Decimal("0.200"),
        )
        assert result.within_tolerance is False
        assert result.relaxation_steps_count == 1

    def test_F9c_per_source_run_violations_caller_injected(self) -> None:
        warmstart = _DummyWarmstartReport(share=0.20)
        admission = _make_admission_report(n_admitted_mission=10)
        result = extract_inflow_consistency(
            warmstart,  # type: ignore[arg-type]
            admission,
            warmstart_share_target=Decimal("0.20"),
            per_source_run_violations=3,
        )
        assert result.per_source_run_violations == 3

    def test_F9d_negative_per_source_run_violations_raises(self) -> None:
        warmstart = _DummyWarmstartReport(share=0.20)
        admission = _make_admission_report(n_admitted_mission=10)
        with pytest.raises(ValueError, match="per_source_run_violations"):
            extract_inflow_consistency(
                warmstart,  # type: ignore[arg-type]
                admission,
                warmstart_share_target=Decimal("0.20"),
                per_source_run_violations=-1,
            )


# ============================================================================
# F10: status invariant violations
# ============================================================================


class TestStatusInvariantViolations:
    """Round 1 [C2] 反映: status 別 invariant 完全強制 (= F10)."""

    def test_F10a_ab_status_ok_with_low_n_pairs_raises(self) -> None:
        # status="ok" with n_pairs<10 で ValueError
        with pytest.raises(ValueError, match="n_pairs"):
            ABDivergenceMetric(
                status="ok", corr=Decimal("0.5"), n_pairs=5,
            )

    def test_F10a_ab_insufficient_with_nonzero_corr_raises(self) -> None:
        # status="insufficient_data" with corr != 0 で ValueError
        with pytest.raises(ValueError, match="sentinel"):
            ABDivergenceMetric(
                status="insufficient_data",
                corr=Decimal("0.5"),
                n_pairs=2,
            )

    def test_F10a_ab_zero_variance_with_nonzero_corr_raises(self) -> None:
        with pytest.raises(ValueError, match="sentinel"):
            ABDivergenceMetric(
                status="zero_variance",
                corr=Decimal("0.5"),
                n_pairs=20,
            )

    def test_F10a_ab_unknown_status_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown status"):
            ABDivergenceMetric(
                status="bogus",  # type: ignore[arg-type]
                corr=Decimal(0),
                n_pairs=0,
            )

    def test_F10b_archive_churn_ok_with_n_runs_used_2_raises(self) -> None:
        with pytest.raises(ValueError, match="n_runs_used == 3"):
            ArchiveChurnMetric(
                status="ok",
                churn_rate=Decimal("0.1"),
                n_total_admissions=10,
                n_total_evictions=1,
                n_runs_used=2,
            )

    def test_F10b_archive_churn_insufficient_with_3_raises(self) -> None:
        with pytest.raises(ValueError, match="insufficient_runs"):
            ArchiveChurnMetric(
                status="insufficient_runs",
                churn_rate=Decimal("0.1"),
                n_total_admissions=10,
                n_total_evictions=1,
                n_runs_used=3,
            )

    def test_F10c_session_entropy_ok_with_low_n_runs_raises(self) -> None:
        with pytest.raises(ValueError, match="n_runs_aggregated"):
            SessionEntropyMetric(
                status="ok",
                shannon_entropy=Decimal("1.5"),
                relative_entropy=Decimal("0.5"),
                n_unique_patterns=4,
                n_archive_members=10,
                n_runs_aggregated=3,
            )

    def test_F10c_session_entropy_insufficient_with_nonzero_entropy_raises(
        self,
    ) -> None:
        with pytest.raises(ValueError, match="shannon_entropy=0"):
            SessionEntropyMetric(
                status="insufficient_window",
                shannon_entropy=Decimal("1.0"),
                relative_entropy=Decimal(0),
                n_unique_patterns=0,
                n_archive_members=10,
                n_runs_aggregated=3,
            )

    def test_F10c_session_entropy_empty_with_members_raises(self) -> None:
        with pytest.raises(ValueError, match="n_archive_members"):
            SessionEntropyMetric(
                status="empty_archive",
                shannon_entropy=Decimal(0),
                relative_entropy=Decimal(0),
                n_unique_patterns=0,
                n_archive_members=5,
                n_runs_aggregated=10,
            )

    def test_q_force_invalid_new_q_force_raises(self) -> None:
        with pytest.raises(ValueError, match="new_q_force"):
            QForceRecommendation(
                new_q_force=Decimal("0.10"),  # < Q_FORCE_MIN
                delta=Decimal(0),
                reason="hold",
                clamped_at_max=False,
                clamped_at_min=False,
                consecutive_divergent_runs=0,
            )

    def test_q_force_negative_consecutive_runs_raises(self) -> None:
        with pytest.raises(ValueError, match="consecutive_divergent_runs"):
            QForceRecommendation(
                new_q_force=Decimal("0.20"),
                delta=Decimal(0),
                reason="hold",
                clamped_at_max=False,
                clamped_at_min=False,
                consecutive_divergent_runs=-1,
            )

    def test_selection_metric_invalid_feasible_ratio_raises(self) -> None:
        with pytest.raises(ValueError, match="feasible_ratio"):
            SelectionMetric(
                front1_cardinality=10,
                feasible_ratio=Decimal("1.5"),
                mean_constraint_violation=Decimal(0),
                generation=1,
            )

    def test_selection_metric_negative_mean_violation_raises(self) -> None:
        with pytest.raises(ValueError, match="mean_constraint_violation"):
            SelectionMetric(
                front1_cardinality=10,
                feasible_ratio=Decimal("0.5"),
                mean_constraint_violation=Decimal("-0.1"),
                generation=1,
            )

    def test_feasible_ratio_metric_n_feasible_exceeds_total_raises(self) -> None:
        with pytest.raises(ValueError, match="n_feasible"):
            FeasibleRatioMetric(
                feasible_ratio_ema=Decimal("0.5"),
                fsm_state="push",
                n_feasible_individuals=20,
                n_total_individuals=10,
            )

    def test_feasible_ratio_metric_invalid_fsm_state_raises(self) -> None:
        with pytest.raises(ValueError, match="fsm_state"):
            FeasibleRatioMetric(
                feasible_ratio_ema=Decimal("0.5"),
                fsm_state="bogus",  # type: ignore[arg-type]
                n_feasible_individuals=5,
                n_total_individuals=10,
            )

    def test_failure_metric_stage_invalid_failure_rate_raises(self) -> None:
        with pytest.raises(ValueError, match="failure_rate"):
            FailureMetricStage(
                stage="stage_a",
                n_failure_records=10,
                n_failed_genomes=10,
                eligible_individuals=5,
                failure_rate=Decimal("2.0"),
                fingerprint_top_3=(),
            )


# ============================================================================
# F11: extract function field grep (cross-PR rename detector)
# ============================================================================


class TestExtractFunctionsFieldGrep:
    """Round 1 [S4] 反映: F11 cross-PR field rename 検出 unit test.

    各 extract 関数を fixture で叩き、 main 実装の field 名を抽出していることを
    確認。 T065-T068 の field が rename された場合、 fixture との不整合で test 失敗。
    """

    def test_F11_extract_selection_uses_front_assignments(self) -> None:
        result = _make_generation_selection_result(
            front_assignments={0: 1, 1: 1, 2: 1, 3: 2, 4: 3},
        )
        m = extract_selection_metrics(
            result,
            feasible_ratio=Decimal("0.6"),
            mean_constraint_violation=Decimal("0.0"),
            generation=10,
        )
        # front_no==1 が 3 個
        assert m.front1_cardinality == 3
        assert m.feasible_ratio == Decimal("0.6")
        assert m.generation == 10

    def test_F11_extract_inflow_uses_admission_role_counts(self) -> None:
        warmstart = _DummyWarmstartReport(share=0.20)
        admission = _make_admission_report(
            n_admitted_mission=50,
            n_admitted_progress=30,
            n_admitted_bypass=20,
        )
        m = extract_inflow_consistency(
            warmstart,  # type: ignore[arg-type]
            admission,
            warmstart_share_target=Decimal("0.20"),
        )
        assert m.bypass_inflow_actual == 20
        assert m.ca_inflow_actual == 100
        assert m.inflow_summary_by_role["mission_pass"] == 50
        assert m.inflow_summary_by_role["progress_pass"] == 30
        assert m.inflow_summary_by_role["score_bypass"] == 20

    def test_F11_extract_failure_uses_per_stage_summaries(self) -> None:
        summary = _make_run_failure_summary(
            per_stage=(
                _make_failure_summary(
                    stage="stage_a",
                    n_failed_genomes=3,
                    eligible_individuals=10,
                ),
            ),
        )
        m = extract_failure_metrics(summary)
        assert m.per_stage[0].failure_rate == Decimal("0.3")
        assert m.per_stage[0].stage == "stage_a"
        assert m.per_stage[0].n_failed_genomes == 3
        # main 実装に run_aborted 不在のため any_stage_all_failed を抽出
        assert m.run_aborted is False

    def test_F11_extract_failure_run_aborted_when_all_failed(self) -> None:
        summary = _make_run_failure_summary(
            per_stage=(
                _make_failure_summary(
                    stage="stage_a",
                    n_failed_genomes=10,
                    eligible_individuals=10,
                ),
            ),
        )
        m = extract_failure_metrics(summary)
        # any_stage_all_failed が True → run_aborted=True 相当
        assert m.run_aborted is True

    def test_F11_extract_failure_with_fingerprint_injection(self) -> None:
        summary = _make_run_failure_summary(
            per_stage=(
                _make_failure_summary(
                    stage="bc_eval",
                    n_failed_genomes=5,
                    eligible_individuals=10,
                ),
            ),
        )
        fp: dict[StageType, tuple[tuple[str, int], ...]] = {
            "bc_eval": (
                ("fp_aaa", 3),
                ("fp_bbb", 2),
                ("fp_ccc", 1),
                ("fp_ddd", 1),
            )
        }
        m = extract_failure_metrics(summary, fingerprint_top_n_by_stage=fp)
        # top_3 truncation
        assert len(m.per_stage[0].fingerprint_top_3) == 3
        assert m.per_stage[0].fingerprint_top_3[0] == ("fp_aaa", 3)


# ============================================================================
# F14: RunObservabilityReport invariant
# ============================================================================


def _default_metrics() -> Mapping[str, object]:
    return {
        "ab_divergence": ABDivergenceMetric(
            status="insufficient_data", corr=Decimal(0), n_pairs=0,
        ),
        "q_force_recommendation": QForceRecommendation(
            new_q_force=Decimal("0.20"),
            delta=Decimal(0),
            reason="hold",
            clamped_at_max=False,
            clamped_at_min=False,
            consecutive_divergent_runs=0,
        ),
        "archive_churn": ArchiveChurnMetric(
            status="insufficient_runs",
            churn_rate=Decimal(0),
            n_total_admissions=0,
            n_total_evictions=0,
            n_runs_used=1,
        ),
        "bypass_ratio": BypassRatioMetric(
            bypass_ratio=Decimal(0),
            n_admitted_by_role={
                "mission_pass": 0,
                "progress_pass": 0,
                "score_bypass": 0,
            },
            n_total_admissions=0,
        ),
        "session_entropy": SessionEntropyMetric(
            status="insufficient_window",
            shannon_entropy=Decimal(0),
            relative_entropy=Decimal(0),
            n_unique_patterns=0,
            n_archive_members=0,
            n_runs_aggregated=0,
        ),
        "feasible_ratio": FeasibleRatioMetric(
            feasible_ratio_ema=Decimal("0.5"),
            fsm_state="push",
            n_feasible_individuals=5,
            n_total_individuals=10,
        ),
        "selection": SelectionMetric(
            front1_cardinality=10,
            feasible_ratio=Decimal("0.5"),
            mean_constraint_violation=Decimal(0),
            generation=0,
        ),
        "inflow_consistency": InflowConsistencyMetric(
            warmstart_share_target=Decimal("0.20"),
            warmstart_share_actual=Decimal("0.20"),
            share_drift=Decimal(0),
            within_tolerance=True,
            relaxation_steps_count=0,
            per_source_run_violations=0,
            ca_inflow_actual=10,
            da_inflow_actual=0,
            bypass_inflow_actual=0,
            inflow_summary_by_role={
                "mission_pass": 10,
                "progress_pass": 0,
                "score_bypass": 0,
            },
        ),
        "failure": FailureMetric(
            run_id="run_001",
            run_aborted=False,
            per_stage=(),
        ),
    }


class TestRunObservabilityReportInvariants:
    def test_F14_empty_run_id_raises(self) -> None:
        with pytest.raises(ValueError, match="run_id"):
            RunObservabilityReport(
                run_id="",
                dataset_epoch_id="ep_001",
                generation_count=10,
                **_default_metrics(),  # type: ignore[arg-type]
            )

    def test_F14_empty_dataset_epoch_id_raises(self) -> None:
        with pytest.raises(ValueError, match="dataset_epoch_id"):
            RunObservabilityReport(
                run_id="run_001",
                dataset_epoch_id="",
                generation_count=10,
                **_default_metrics(),  # type: ignore[arg-type]
            )

    def test_F14_negative_generation_count_raises(self) -> None:
        with pytest.raises(ValueError, match="generation_count"):
            RunObservabilityReport(
                run_id="run_001",
                dataset_epoch_id="ep_001",
                generation_count=-1,
                **_default_metrics(),  # type: ignore[arg-type]
            )

    def test_build_run_observability_report_minimal(self) -> None:
        report = build_run_observability_report(
            run_id="run_001",
            dataset_epoch_id="ep_001",
            generation_count=20,
            **_default_metrics(),  # type: ignore[arg-type]
        )
        assert report.run_id == "run_001"
        assert report.dataset_epoch_id == "ep_001"
        assert report.generation_count == 20
        assert report.q_force_recommendation.reason == "hold"


# ============================================================================
# constants sanity (synthesis 確定値 vs T071 仮説値)
# ============================================================================


class TestModuleConstants:
    def test_synthesis_constants(self) -> None:
        assert Decimal("0.02") == DELTA_PER_RUN
        assert Decimal("0.40") == Q_FORCE_MAX
        assert Decimal("0.50") == RESTORE_THRESHOLD

    def test_T071_hypothesis_constants(self) -> None:
        assert Decimal("0.15") == Q_FORCE_MIN
        assert Decimal("0.30") == DIVERGENCE_THRESHOLD
        assert AB_MIN_ACTIONABLE_PAIRS == 10

    def test_session_pattern_space(self) -> None:
        assert SESSION_PATTERN_BITS == 3
        assert WEEKLY_WINDOW_SIZE == 7

    def test_warmstart_tolerance(self) -> None:
        assert Decimal("0.01") == WARMSTART_SHARE_TOLERANCE


# ============================================================================
# T080a: Stub builder + JSON serialization tests
# ============================================================================


class TestStubRunObservabilityReportBuilder:
    """T080a build_stub_run_observability_report unit tests.

    stub builder は run_ga.py から build_run_observability_report 呼出経路を
    確立するための first step. 後続別 TODO (T080b-g) で各 metric を実値配線に
    置換予定. 本 test は stub 値の妥当性 (= dataclass invariant 全 PASS) と
    field 値の期待を検証する.
    """

    def test_stub_report_constructs_with_valid_inputs(self) -> None:
        report = build_stub_run_observability_report(
            run_id="test-run-001",
            dataset_epoch_id="AUDJPY-2024-Q1-Q2",
            generation_count=64,
        )
        assert report.run_id == "test-run-001"
        assert report.dataset_epoch_id == "AUDJPY-2024-Q1-Q2"
        assert report.generation_count == 64

    def test_stub_ab_divergence_status_is_insufficient_data(self) -> None:
        report = build_stub_run_observability_report(
            run_id="r", dataset_epoch_id="e", generation_count=0
        )
        assert report.ab_divergence.status == "insufficient_data"
        assert report.ab_divergence.corr == Decimal(0)
        assert report.ab_divergence.n_pairs == 0

    def test_stub_q_force_recommendation_at_min(self) -> None:
        report = build_stub_run_observability_report(
            run_id="r", dataset_epoch_id="e", generation_count=0
        )
        assert report.q_force_recommendation.new_q_force == Q_FORCE_MIN
        assert report.q_force_recommendation.delta == Decimal(0)
        assert report.q_force_recommendation.reason == "insufficient_data"

    def test_stub_archive_churn_status_is_insufficient_runs(self) -> None:
        report = build_stub_run_observability_report(
            run_id="r", dataset_epoch_id="e", generation_count=0
        )
        assert report.archive_churn.status == "insufficient_runs"
        assert report.archive_churn.n_runs_used == 1
        assert report.archive_churn.n_total_admissions == 0
        assert report.archive_churn.n_total_evictions == 0

    def test_stub_bypass_ratio_zero(self) -> None:
        report = build_stub_run_observability_report(
            run_id="r", dataset_epoch_id="e", generation_count=0
        )
        assert report.bypass_ratio.bypass_ratio == Decimal(0)
        assert report.bypass_ratio.n_total_admissions == 0
        assert report.bypass_ratio.n_admitted_by_role == {
            "mission_pass": 0,
            "progress_pass": 0,
            "score_bypass": 0,
        }

    def test_stub_session_entropy_status_is_empty_archive(self) -> None:
        report = build_stub_run_observability_report(
            run_id="r", dataset_epoch_id="e", generation_count=0
        )
        assert report.session_entropy.status == "empty_archive"
        assert report.session_entropy.shannon_entropy == Decimal(0)
        assert report.session_entropy.n_archive_members == 0

    def test_stub_feasible_ratio_default_push(self) -> None:
        report = build_stub_run_observability_report(
            run_id="r", dataset_epoch_id="e", generation_count=0
        )
        assert report.feasible_ratio.fsm_state == "push"
        assert report.feasible_ratio.feasible_ratio_ema == Decimal(0)
        assert report.feasible_ratio.n_feasible_individuals == 0
        assert report.feasible_ratio.n_total_individuals == 0

    def test_stub_selection_zero_front1(self) -> None:
        report = build_stub_run_observability_report(
            run_id="r", dataset_epoch_id="e", generation_count=0
        )
        assert report.selection.front1_cardinality == 0
        assert report.selection.feasible_ratio == Decimal(0)
        assert report.selection.mean_constraint_violation == Decimal(0)
        assert report.selection.generation == 0

    def test_stub_inflow_consistency_within_tolerance(self) -> None:
        report = build_stub_run_observability_report(
            run_id="r", dataset_epoch_id="e", generation_count=0
        )
        assert report.inflow_consistency.warmstart_share_target == Decimal(0)
        assert report.inflow_consistency.warmstart_share_actual == Decimal(0)
        assert report.inflow_consistency.share_drift == Decimal(0)
        assert report.inflow_consistency.within_tolerance is True
        assert report.inflow_consistency.relaxation_steps_count == 0
        assert report.inflow_consistency.ca_inflow_actual == 0
        assert report.inflow_consistency.da_inflow_actual == 0
        assert report.inflow_consistency.bypass_inflow_actual == 0

    def test_stub_failure_run_not_aborted(self) -> None:
        report = build_stub_run_observability_report(
            run_id="r", dataset_epoch_id="e", generation_count=0
        )
        assert report.failure.run_id == "r"
        assert report.failure.run_aborted is False
        assert report.failure.per_stage == ()

    def test_stub_run_id_propagates_to_failure_metric(self) -> None:
        report = build_stub_run_observability_report(
            run_id="propagated-id", dataset_epoch_id="e", generation_count=0
        )
        assert report.failure.run_id == "propagated-id"

    def test_stub_rejects_empty_run_id(self) -> None:
        with pytest.raises(ValueError, match="run_id"):
            build_stub_run_observability_report(
                run_id="", dataset_epoch_id="e", generation_count=0
            )

    def test_stub_rejects_empty_dataset_epoch_id(self) -> None:
        with pytest.raises(ValueError, match="dataset_epoch_id"):
            build_stub_run_observability_report(
                run_id="r", dataset_epoch_id="", generation_count=0
            )

    def test_stub_rejects_negative_generation_count(self) -> None:
        with pytest.raises(ValueError, match="generation_count"):
            build_stub_run_observability_report(
                run_id="r", dataset_epoch_id="e", generation_count=-1
            )


class TestSerializeRunObservabilityReport:
    """T080a serialize_run_observability_report unit tests."""

    def test_serialize_outputs_valid_json(self) -> None:
        import json

        report = build_stub_run_observability_report(
            run_id="r1", dataset_epoch_id="ep1", generation_count=10
        )
        js = serialize_run_observability_report(report)
        parsed = json.loads(js)
        assert parsed["run_id"] == "r1"
        assert parsed["dataset_epoch_id"] == "ep1"
        assert parsed["generation_count"] == 10

    def test_serialize_decimal_to_str(self) -> None:
        import json

        report = build_stub_run_observability_report(
            run_id="r", dataset_epoch_id="e", generation_count=0
        )
        js = serialize_run_observability_report(report)
        parsed = json.loads(js)
        # Decimal field は str 化されている
        assert isinstance(parsed["ab_divergence"]["corr"], str)
        assert isinstance(parsed["q_force_recommendation"]["new_q_force"], str)
        assert parsed["q_force_recommendation"]["new_q_force"] == "0.15"
        # int / bool は そのまま
        assert isinstance(parsed["generation_count"], int)
        assert isinstance(
            parsed["q_force_recommendation"]["clamped_at_max"], bool
        )

    def test_serialize_tuple_to_list(self) -> None:
        import json

        report = build_stub_run_observability_report(
            run_id="r", dataset_epoch_id="e", generation_count=0
        )
        js = serialize_run_observability_report(report)
        parsed = json.loads(js)
        # FailureMetric.per_stage は tuple → list 化される
        assert isinstance(parsed["failure"]["per_stage"], list)
        assert parsed["failure"]["per_stage"] == []

    def test_serialize_mapping_to_dict(self) -> None:
        import json

        report = build_stub_run_observability_report(
            run_id="r", dataset_epoch_id="e", generation_count=0
        )
        js = serialize_run_observability_report(report)
        parsed = json.loads(js)
        # BypassRatioMetric.n_admitted_by_role は Mapping → dict 化
        assert isinstance(parsed["bypass_ratio"]["n_admitted_by_role"], dict)
        assert parsed["bypass_ratio"]["n_admitted_by_role"]["mission_pass"] == 0

    def test_serialize_indent_2(self) -> None:
        report = build_stub_run_observability_report(
            run_id="r", dataset_epoch_id="e", generation_count=0
        )
        js = serialize_run_observability_report(report)
        # indent=2 の確認 (= 行頭スペース)
        assert "  " in js  # 2-space indent
        assert "\n" in js  # 改行あり

    def test_serialize_dict_with_decimal_keys(self) -> None:
        """Round 1 [Warning] 1 反映: dict キーが Decimal でも str 化される."""
        import json

        from src.alpha_factory.observability.run_metrics import (
            _convert_for_json,
        )

        # Decimal key を含む dict (= 直接 _convert_for_json)
        result = _convert_for_json({Decimal("0.30"): "low", Decimal("0.50"): "high"})
        assert isinstance(result, dict)
        # キーが str 化されている
        assert "0.30" in result
        assert "0.50" in result
        # JSON 化可能
        json.dumps(result)

    def test_serialize_dict_with_int_keys(self) -> None:
        """Round 1 [Warning] 1 反映: int キーも str 化."""
        import json

        from src.alpha_factory.observability.run_metrics import (
            _convert_for_json,
        )

        result = _convert_for_json({1: "a", 2: "b"})
        assert "1" in result
        assert "2" in result
        json.dumps(result)

    def test_serialize_frozenset_mixed_types_no_typeerror(self) -> None:
        """Round 1 [Warning] 2 反映: frozenset 比較不能混在型でも sort fallback."""
        import json

        from src.alpha_factory.observability.run_metrics import (
            _convert_for_json,
        )

        # str と int の混在 frozenset (= sorted で TypeError 出る境界)
        result = _convert_for_json(frozenset({1, "a", 2, "b"}))
        assert isinstance(result, list)
        assert len(result) == 4
        # str fallback で順序保証 (= 全要素が str() で比較可能)
        json.dumps(result)

    def test_serialize_frozenset_homogeneous_int_sorted(self) -> None:
        """frozenset 同型は sort される."""
        from src.alpha_factory.observability.run_metrics import (
            _convert_for_json,
        )

        result = _convert_for_json(frozenset({3, 1, 2}))
        assert result == [1, 2, 3]

    def test_serialize_full_real_metrics_roundtrip(self) -> None:
        """実値 metric (= stub ではない正式構築) でも serialize 可能."""
        import json

        # 実値 metric を直接構築 (= stub ではなく test 経路)
        report = build_run_observability_report(
            run_id="real-run",
            dataset_epoch_id="real-ep",
            generation_count=32,
            ab_divergence=ABDivergenceMetric(
                status="ok",
                corr=Decimal("0.45"),
                n_pairs=15,
            ),
            q_force_recommendation=QForceRecommendation(
                new_q_force=Decimal("0.20"),
                delta=Decimal("0.05"),
                reason="raise",
                clamped_at_max=False,
                clamped_at_min=False,
                consecutive_divergent_runs=2,
            ),
            archive_churn=ArchiveChurnMetric(
                status="ok",
                churn_rate=Decimal("0.30"),
                n_total_admissions=100,
                n_total_evictions=30,
                n_runs_used=3,
            ),
            bypass_ratio=BypassRatioMetric(
                bypass_ratio=Decimal("0.20"),
                n_admitted_by_role={
                    "mission_pass": 5,
                    "progress_pass": 3,
                    "score_bypass": 2,
                },
                n_total_admissions=10,
            ),
            session_entropy=SessionEntropyMetric(
                status="ok",
                shannon_entropy=Decimal("2.5"),
                relative_entropy=Decimal("0.83"),
                n_unique_patterns=6,
                n_archive_members=120,
                n_runs_aggregated=7,
            ),
            feasible_ratio=FeasibleRatioMetric(
                feasible_ratio_ema=Decimal("0.45"),
                fsm_state="pull",
                n_feasible_individuals=86,
                n_total_individuals=192,
            ),
            selection=SelectionMetric(
                front1_cardinality=12,
                feasible_ratio=Decimal("0.45"),
                mean_constraint_violation=Decimal("0.10"),
                generation=64,
            ),
            inflow_consistency=InflowConsistencyMetric(
                warmstart_share_target=Decimal("0.20"),
                warmstart_share_actual=Decimal("0.21"),
                share_drift=Decimal("0.01"),
                within_tolerance=True,
                relaxation_steps_count=2,
                per_source_run_violations=0,
                ca_inflow_actual=10,
                da_inflow_actual=0,
                bypass_inflow_actual=2,
                inflow_summary_by_role={"mission_pass": 5, "progress_pass": 3},
            ),
            failure=FailureMetric(
                run_id="real-run",
                run_aborted=False,
                per_stage=(),
            ),
        )
        js = serialize_run_observability_report(report)
        parsed = json.loads(js)
        assert parsed["run_id"] == "real-run"
        assert parsed["ab_divergence"]["status"] == "ok"
        assert parsed["ab_divergence"]["corr"] == "0.45"
        assert parsed["q_force_recommendation"]["reason"] == "raise"
        assert parsed["bypass_ratio"]["bypass_ratio"] == "0.20"
        assert parsed["selection"]["front1_cardinality"] == 12
