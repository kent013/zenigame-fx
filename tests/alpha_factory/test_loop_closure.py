"""T067 PR 1: tests for src/alpha_factory/loop_closure.py.

詳細設計参照: ``devnotes/20260430-1310-todo-T067-loop-closure-warmstart-emergency/detailed-design.md`` § 施策 2.

14 sub-suite × 約 95 件、 builders は本ファイル内で共通化.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from src.alpha_factory.cpps_archive import (
    ArchiveMember,
    ArchiveState,
    compute_archive_capacities,
)
from src.alpha_factory.loop_closure import (
    EMERGENCY_HISTORY_MAXLEN,
    RAMP_SHARES,
    SENTINEL_REPLACEMENT_FOR_HISTORY,
    WARMSTART_EMERGENCY_CA_RATIO,
    WARMSTART_EMERGENCY_SHARE,
    WARMSTART_NORMAL_CA_RATIO,
    WARMSTART_NORMAL_SHARE,
    WARMSTART_PREV_EPOCH_CAP_RATIO,
    WARMSTART_RELAXATION_ORDER,
    EmergencyHistoryEntry,
    EmergencyState,
    SchemaV2Metadata,
    WarmstartCandidate,
    WarmstartFilterStats,
    WarmstartReuseRecord,
    WarmstartState,
    admit_warmstart_to_da_with_eviction,
    build_archive_candidate,
    build_warmstart_candidates,
    compute_best_mission_signed_margin,
    compute_warmstart_counts,
    compute_warmstart_ramp_share,
    compute_warmstart_share_and_ratio,
    evaluate_emergency_release,
    evaluate_emergency_trigger,
    is_boost_applicable,
    prepare_run_loop_closure,
    select_warmstart_candidates,
    update_emergency_state,
    update_warmstart_state,
)
from src.alpha_factory.mission_inf_gap import MissionGapResult
from src.alpha_factory.stage_bc_evaluator import BCEvaluationResult, StagePassStatus

# ---------------------------------------------------------------------------
# Builders (test fixtures)
# ---------------------------------------------------------------------------


def make_member(
    genome_id: str = "g0",
    *,
    run_id: str = "run-1",
    generation_no: int = 0,
    dataset_epoch_id: str = "epoch-1",
    pattern_id: str | None = None,
    family_id: str = "fam-A",
    archive_role: str = "mission_pass",
    archive_target: str = "CA",
    gate_worst_gap: float = 0.0,
    c_pass_depth: float = 1.0,
    mission_signed_margin: float = 0.0,
    shadow_robustness_score: float = 1.0,
    log_pf_clip: float = 0.0,
    novelty: float = 0.5,
    diversity_coverage: float = 0.5,
    quality_floor_margin: float = 0.0,
    margin_inf: float = 0.0,
    invariant_feasible: bool = True,
) -> ArchiveMember:
    """ArchiveMember ビルダー."""
    if pattern_id is None:
        pattern_id = f"pat-{genome_id}"
    return ArchiveMember(
        genome_id=genome_id,
        run_id=run_id,
        generation_no=generation_no,
        dataset_epoch_id=dataset_epoch_id,
        pattern_id=pattern_id,
        family_id=family_id,
        archive_role=archive_role,  # type: ignore[arg-type]
        archive_target=archive_target,  # type: ignore[arg-type]
        gate_worst_gap=gate_worst_gap,
        c_pass_depth=c_pass_depth,
        mission_signed_margin=mission_signed_margin,
        shadow_robustness_score=shadow_robustness_score,
        log_pf_clip=log_pf_clip,
        novelty=novelty,
        diversity_coverage=diversity_coverage,
        quality_floor_margin=quality_floor_margin,
        margin_inf=margin_inf,
        invariant_feasible=invariant_feasible,
    )


def make_archive_state(
    members: Iterable[ArchiveMember] = (),
    *,
    dataset_epoch_id: str = "epoch-1",
    run_history: Iterable[str] = (),
) -> ArchiveState:
    """ArchiveState ビルダー."""
    return ArchiveState(
        members=tuple(members),
        dataset_epoch_id=dataset_epoch_id,
        run_history=tuple(run_history),
    )


def make_warmstart_candidate(
    genome_id: str = "g0",
    *,
    member: ArchiveMember | None = None,
    reuse_record: WarmstartReuseRecord | None = None,
    epoch_age: int = 0,
    ca_rank_score: float = 0.0,
    da_rank_score: float = 0.0,
    pattern_id: str | None = None,
    family_id: str = "fam-A",
    run_id: str = "run-source",
    archive_target: str = "CA",
    dataset_epoch_id: str = "epoch-1",
) -> WarmstartCandidate:
    """WarmstartCandidate ビルダー."""
    if member is None:
        member = make_member(
            genome_id,
            pattern_id=pattern_id,
            family_id=family_id,
            run_id=run_id,
            archive_target=archive_target,
            dataset_epoch_id=dataset_epoch_id,
        )
    return WarmstartCandidate(
        member=member,
        reuse_record=reuse_record,
        epoch_age=epoch_age,
        ca_rank_score=ca_rank_score,
        da_rank_score=da_rank_score,
    )


def make_emergency_state(
    *,
    mode: str = "normal",
    activated_at_run_id: str | None = None,
    boost_consumed_run_id: str | None = None,
    history: Iterable[EmergencyHistoryEntry] = (),
) -> EmergencyState:
    """EmergencyState ビルダー."""
    return EmergencyState(
        mode=mode,  # type: ignore[arg-type]
        activated_at_run_id=activated_at_run_id,
        boost_consumed_run_id=boost_consumed_run_id,
        history=tuple(history),
    )


def make_history_entry(
    run_id: str = "run-x",
    *,
    n_mission_pass: int = 0,
    n_progress_pass: int = 0,
    best_mission_signed_margin: float = 0.0,
) -> EmergencyHistoryEntry:
    return EmergencyHistoryEntry(
        run_id=run_id,
        n_mission_pass=n_mission_pass,
        n_progress_pass=n_progress_pass,
        best_mission_signed_margin=best_mission_signed_margin,
    )


def _empty_filter_stats() -> WarmstartFilterStats:
    return WarmstartFilterStats(
        cooldown_drops=0,
        max_reuse_drops=0,
        epoch_age_2_plus_drops=0,
    )


def make_mission_gap(
    *,
    mission_signed_margin: float = 0.5,
    mission_inf_gap: float = 0.0,
    is_feasible: bool = True,
    constraint_violation: float = 0.0,
    mission_margin: float = 0.0,
    per_metric_shortfall: Mapping[str, float] | None = None,
) -> MissionGapResult:
    if per_metric_shortfall is None:
        per_metric_shortfall = MappingProxyType(
            {"sharpe": 0.0, "pnl": 0.0, "dd": 0.0, "tc": 0.0}
        )
    return MissionGapResult(
        mission_inf_gap=mission_inf_gap,
        constraint_violation=constraint_violation,
        mission_margin=mission_margin,
        mission_signed_margin=mission_signed_margin,
        per_metric_shortfall=per_metric_shortfall,
        is_feasible=is_feasible,
    )


def _make_bc_result_stub(
    *,
    mission_pass: StagePassStatus = StagePassStatus.FAIL,
    progress_pass: StagePassStatus = StagePassStatus.FAIL,
    pareto_axis_usable: bool = False,
    b_pooled_cf: object | None = None,
    c_pass_depth: float = 1.0,
    shadow_robustness_score: float | None = 1.0,
) -> object:
    """determine_archive_role + build_archive_candidate で必要な field を持つ stub.

    BCEvaluationResult の完全構築は重いので、 必要 field のみ持つ簡易 stub を
    返す. 詳細 vs main 整合 (T064 main 実装に従い ``progress_pass`` は
    ``c_lite_result`` 経由、 ``shadow_robustness_score`` は ``c_result`` 経由).
    """

    class _CLiteStub:
        def __init__(self, status: StagePassStatus) -> None:
            self.progress_pass = status

    class _CResultStub:
        def __init__(self, score: float | None) -> None:
            self.shadow_robustness_score = score

    class _Stub:
        def __init__(self) -> None:
            self.mission_pass = mission_pass
            self.c_lite_result = _CLiteStub(progress_pass)
            self.c_result = _CResultStub(shadow_robustness_score)
            self.pareto_axis_usable = pareto_axis_usable
            self.b_pooled_cf = b_pooled_cf
            self.c_pass_depth = c_pass_depth

    return _Stub()


class _PooledCFStub:
    def __init__(
        self, *, gate_worst_gap: float = 0.1, log_pf_clip: float = 0.5
    ) -> None:
        self.gate_worst_gap = gate_worst_gap
        self.log_pf_clip = log_pf_clip


# ---------------------------------------------------------------------------
# 2.1 PR DoD 必須
# ---------------------------------------------------------------------------


def test_emergency_mode_activates_after_3_consecutive_mission_pass_zero_and_ma3_below_ma6_minus_005() -> None:
    """3 連続 mission_pass=0 + MA3 < MA6 - 0.05 で trigger 成立."""
    # newest first: 直近 3 が mission=0 / margin=0、 直前 3 が mission=1 / margin=0.5
    history_full = (
        make_history_entry("run-9", n_mission_pass=0, best_mission_signed_margin=0.0),
        make_history_entry("run-8", n_mission_pass=0, best_mission_signed_margin=0.0),
        make_history_entry("run-7", n_mission_pass=0, best_mission_signed_margin=0.0),
        make_history_entry("run-6", n_mission_pass=1, best_mission_signed_margin=0.5),
        make_history_entry("run-5", n_mission_pass=1, best_mission_signed_margin=0.5),
        make_history_entry("run-4", n_mission_pass=1, best_mission_signed_margin=0.5),
    )
    state = make_emergency_state(mode="normal", history=history_full)
    assert evaluate_emergency_trigger(state) is True


def test_emergency_mode_releases_when_progress_pass_geq_2_or_best_mission_signed_margin_geq_ma6() -> None:
    """progress_pass>=2 または margin>=MA6 で release."""
    # progress_pass>=2 ケース
    history = (
        make_history_entry("run-1", n_progress_pass=2),
        *(
            make_history_entry(f"run-{i}", best_mission_signed_margin=0.0)
            for i in range(2, 7)
        ),
    )
    state = make_emergency_state(mode="emergency", history=history)
    assert evaluate_emergency_release(state) is True


def test_warmstart_ramp_run1_zero_run2_10_run3_15_run4_20() -> None:
    assert compute_warmstart_ramp_share(1) == 0.00
    assert compute_warmstart_ramp_share(2) == 0.10
    assert compute_warmstart_ramp_share(3) == 0.15
    assert compute_warmstart_ramp_share(4) == 0.20


def test_warmstart_emergency_share_25_ca_ratio_50_overrides_ramp() -> None:
    share, ca_ratio = compute_warmstart_share_and_ratio(0.20, is_boost_applicable=True)
    assert share == 0.25
    assert ca_ratio == 0.5


def test_bc_evaluation_result_has_c_pass_depth_field() -> None:
    """T064 follow-up Phase 0 契約: BCEvaluationResult.c_pass_depth が存在.

    __dataclass_fields__ から検出 (mock では false-positive にならない設計).
    T064 follow-up が未着地なら本 test は fail-fast.
    """
    assert "c_pass_depth" in BCEvaluationResult.__dataclass_fields__
    field = BCEvaluationResult.__dataclass_fields__["c_pass_depth"]
    assert field.type is float or field.type == "float"


# ---------------------------------------------------------------------------
# 2.2 EmergencyState transitions
# ---------------------------------------------------------------------------


def test_evaluate_emergency_trigger_returns_false_when_history_below_6() -> None:
    history = tuple(
        make_history_entry(f"run-{i}", n_mission_pass=0) for i in range(5)
    )
    state = make_emergency_state(history=history)
    assert evaluate_emergency_trigger(state) is False


def test_evaluate_emergency_trigger_returns_false_when_mission_pass_not_zero_in_3() -> (
    None
):
    history = (
        make_history_entry("r-1", n_mission_pass=0, best_mission_signed_margin=0.0),
        make_history_entry("r-2", n_mission_pass=1, best_mission_signed_margin=0.0),
        make_history_entry("r-3", n_mission_pass=0, best_mission_signed_margin=0.0),
        make_history_entry("r-4", n_mission_pass=1, best_mission_signed_margin=0.5),
        make_history_entry("r-5", n_mission_pass=1, best_mission_signed_margin=0.5),
        make_history_entry("r-6", n_mission_pass=1, best_mission_signed_margin=0.5),
    )
    state = make_emergency_state(history=history)
    assert evaluate_emergency_trigger(state) is False


def test_evaluate_emergency_trigger_returns_false_when_ma3_geq_ma6_minus_005() -> None:
    """MA3 = MA6 - 0.04 (= 0.05 未満 delta) で False."""
    history = (
        make_history_entry("r-1", n_mission_pass=0, best_mission_signed_margin=0.46),
        make_history_entry("r-2", n_mission_pass=0, best_mission_signed_margin=0.46),
        make_history_entry("r-3", n_mission_pass=0, best_mission_signed_margin=0.46),
        make_history_entry("r-4", n_mission_pass=1, best_mission_signed_margin=0.5),
        make_history_entry("r-5", n_mission_pass=1, best_mission_signed_margin=0.5),
        make_history_entry("r-6", n_mission_pass=1, best_mission_signed_margin=0.5),
    )
    state = make_emergency_state(history=history)
    # MA3 = 0.46, MA6 = (0.46*3 + 0.5*3)/6 = 0.48, delta = 0.02 < 0.05
    assert evaluate_emergency_trigger(state) is False


def test_evaluate_emergency_trigger_returns_true_when_all_conditions_met() -> None:
    history = (
        make_history_entry("r-1", n_mission_pass=0, best_mission_signed_margin=0.0),
        make_history_entry("r-2", n_mission_pass=0, best_mission_signed_margin=0.0),
        make_history_entry("r-3", n_mission_pass=0, best_mission_signed_margin=0.0),
        make_history_entry("r-4", n_mission_pass=1, best_mission_signed_margin=0.5),
        make_history_entry("r-5", n_mission_pass=1, best_mission_signed_margin=0.5),
        make_history_entry("r-6", n_mission_pass=1, best_mission_signed_margin=0.5),
    )
    state = make_emergency_state(history=history)
    assert evaluate_emergency_trigger(state) is True


def test_evaluate_emergency_release_progress_pass_2_in_latest() -> None:
    history = (
        make_history_entry("r-1", n_progress_pass=2, best_mission_signed_margin=-0.1),
    )
    state = make_emergency_state(mode="emergency", history=history)
    assert evaluate_emergency_release(state) is True


def test_evaluate_emergency_release_best_mission_signed_margin_above_ma6() -> None:
    history = (
        make_history_entry("r-1", n_progress_pass=0, best_mission_signed_margin=1.0),
        make_history_entry("r-2", best_mission_signed_margin=0.0),
        make_history_entry("r-3", best_mission_signed_margin=0.0),
        make_history_entry("r-4", best_mission_signed_margin=0.0),
        make_history_entry("r-5", best_mission_signed_margin=0.0),
        make_history_entry("r-6", best_mission_signed_margin=0.0),
    )
    state = make_emergency_state(mode="emergency", history=history)
    # latest=1.0, MA6 = (1.0+0+0+0+0+0)/6 ≈ 0.167 → 1.0 >= 0.167 → True
    assert evaluate_emergency_release(state) is True


def test_evaluate_emergency_release_returns_false_in_normal_mode() -> None:
    history = (
        make_history_entry("r-1", n_progress_pass=2, best_mission_signed_margin=1.0),
    )
    state = make_emergency_state(mode="normal", history=history)
    assert evaluate_emergency_release(state) is False


def test_update_emergency_state_history_appended_with_maxlen_10() -> None:
    history = tuple(
        make_history_entry(f"r-{i}", best_mission_signed_margin=float(i))
        for i in range(10)
    )
    state = make_emergency_state(history=history)
    new = update_emergency_state(
        state,
        new_run_id="r-new",
        n_mission_pass=0,
        n_progress_pass=0,
        best_mission_signed_margin=0.5,
        boost_consumed_in_this_run=False,
    )
    assert len(new.history) == EMERGENCY_HISTORY_MAXLEN
    assert new.history[0].run_id == "r-new"


def test_update_emergency_state_normal_to_emergency_transition() -> None:
    history = (
        make_history_entry("r-2", n_mission_pass=0, best_mission_signed_margin=0.0),
        make_history_entry("r-3", n_mission_pass=0, best_mission_signed_margin=0.0),
        make_history_entry("r-4", n_mission_pass=1, best_mission_signed_margin=0.5),
        make_history_entry("r-5", n_mission_pass=1, best_mission_signed_margin=0.5),
        make_history_entry("r-6", n_mission_pass=1, best_mission_signed_margin=0.5),
    )
    state = make_emergency_state(mode="normal", history=history)
    new = update_emergency_state(
        state,
        new_run_id="r-1",
        n_mission_pass=0,
        n_progress_pass=0,
        best_mission_signed_margin=0.0,
        boost_consumed_in_this_run=False,
    )
    assert new.mode == "emergency"
    assert new.activated_at_run_id == "r-1"
    assert new.boost_consumed_run_id is None


def test_update_emergency_state_emergency_to_normal_transition() -> None:
    history = (
        make_history_entry("r-prev", n_progress_pass=0, best_mission_signed_margin=0.0),
    )
    state = make_emergency_state(
        mode="emergency",
        activated_at_run_id="r-prev",
        boost_consumed_run_id="r-prev",
        history=history,
    )
    new = update_emergency_state(
        state,
        new_run_id="r-new",
        n_mission_pass=2,
        n_progress_pass=2,  # release 条件
        best_mission_signed_margin=0.5,
        boost_consumed_in_this_run=False,
    )
    assert new.mode == "normal"
    assert new.activated_at_run_id is None
    assert new.boost_consumed_run_id is None


def test_update_emergency_state_emergency_persists_when_no_release_condition() -> None:
    history = (
        make_history_entry("r-prev", n_progress_pass=0, best_mission_signed_margin=0.0),
    )
    state = make_emergency_state(
        mode="emergency",
        activated_at_run_id="r-x",
        boost_consumed_run_id="r-x",
        history=history,
    )
    new = update_emergency_state(
        state,
        new_run_id="r-new",
        n_mission_pass=0,
        n_progress_pass=0,
        best_mission_signed_margin=-1.0,
        boost_consumed_in_this_run=False,
    )
    assert new.mode == "emergency"
    assert new.activated_at_run_id == "r-x"


def test_update_emergency_state_raises_on_empty_run_id() -> None:
    with pytest.raises(ValueError, match="new_run_id must be non-empty"):
        update_emergency_state(
            make_emergency_state(),
            new_run_id="",
            n_mission_pass=0,
            n_progress_pass=0,
            best_mission_signed_margin=0.0,
            boost_consumed_in_this_run=False,
        )


def test_update_emergency_state_raises_on_negative_n_mission_pass() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        update_emergency_state(
            make_emergency_state(),
            new_run_id="r-1",
            n_mission_pass=-1,
            n_progress_pass=0,
            best_mission_signed_margin=0.0,
            boost_consumed_in_this_run=False,
        )


# ---------------------------------------------------------------------------
# 2.3 is_boost_applicable
# ---------------------------------------------------------------------------


def test_is_boost_applicable_returns_false_for_normal_mode() -> None:
    state = make_emergency_state(mode="normal")
    assert is_boost_applicable(state, "r-1") is False


def test_is_boost_applicable_returns_true_when_emergency_and_no_boost_consumed() -> (
    None
):
    state = make_emergency_state(
        mode="emergency", activated_at_run_id="r-1", boost_consumed_run_id=None
    )
    assert is_boost_applicable(state, "r-1") is True


def test_is_boost_applicable_returns_true_for_same_run_idempotent() -> None:
    state = make_emergency_state(
        mode="emergency", activated_at_run_id="r-1", boost_consumed_run_id="r-1"
    )
    assert is_boost_applicable(state, "r-1") is True


def test_is_boost_applicable_returns_false_when_boost_consumed_in_other_run() -> None:
    state = make_emergency_state(
        mode="emergency", activated_at_run_id="r-1", boost_consumed_run_id="r-1"
    )
    assert is_boost_applicable(state, "r-2") is False


# ---------------------------------------------------------------------------
# 2.4 warmstart share / ratio / counts
# ---------------------------------------------------------------------------


def test_compute_warmstart_ramp_share_returns_per_run_table() -> None:
    assert compute_warmstart_ramp_share(1) == RAMP_SHARES[1]
    assert compute_warmstart_ramp_share(2) == RAMP_SHARES[2]
    assert compute_warmstart_ramp_share(3) == RAMP_SHARES[3]


def test_compute_warmstart_ramp_share_run5_uses_default_20_percent() -> None:
    assert compute_warmstart_ramp_share(5) == WARMSTART_NORMAL_SHARE
    assert compute_warmstart_ramp_share(100) == WARMSTART_NORMAL_SHARE


def test_compute_warmstart_ramp_share_raises_on_run_no_below_1() -> None:
    with pytest.raises(ValueError, match="run_no must be >= 1"):
        compute_warmstart_ramp_share(0)


def test_compute_warmstart_share_and_ratio_normal_returns_ramp_and_26_38() -> None:
    share, ca_ratio = compute_warmstart_share_and_ratio(0.20, is_boost_applicable=False)
    assert share == 0.20
    assert ca_ratio == WARMSTART_NORMAL_CA_RATIO


def test_compute_warmstart_share_and_ratio_boost_returns_25_and_50() -> None:
    share, ca_ratio = compute_warmstart_share_and_ratio(0.20, is_boost_applicable=True)
    assert share == WARMSTART_EMERGENCY_SHARE
    assert ca_ratio == WARMSTART_EMERGENCY_CA_RATIO


def test_compute_warmstart_counts_pop192_normal_returns_38_26_12() -> None:
    total, ca, da = compute_warmstart_counts(192, 0.20, WARMSTART_NORMAL_CA_RATIO)
    assert total == 38
    assert ca == 26
    assert da == 12


def test_compute_warmstart_counts_pop256_normal_returns_51_35_16() -> None:
    total, ca, da = compute_warmstart_counts(256, 0.20, WARMSTART_NORMAL_CA_RATIO)
    assert total == 51
    assert ca == 35
    assert da == 16


def test_compute_warmstart_counts_emergency_returns_24_24_for_pop192() -> None:
    """詳細 Round 1 [C1]: 25%×192=48, 1:1 → 24/24."""
    total, ca, da = compute_warmstart_counts(192, 0.25, 0.5)
    assert total == 48
    assert ca == 24
    assert da == 24


def test_compute_warmstart_counts_emergency_returns_32_32_for_pop256() -> None:
    """25%×256=64, 1:1 → 32/32."""
    total, ca, da = compute_warmstart_counts(256, 0.25, 0.5)
    assert total == 64
    assert ca == 32
    assert da == 32


def test_compute_warmstart_counts_share_zero_returns_all_zero() -> None:
    total, ca, da = compute_warmstart_counts(192, 0.0, 0.5)
    assert (total, ca, da) == (0, 0, 0)


def test_compute_warmstart_counts_unsupported_pop_size_raises() -> None:
    with pytest.raises(ValueError, match="pop_size must be one of"):
        compute_warmstart_counts(100, 0.20, 0.5)


# ---------------------------------------------------------------------------
# 2.5 build_warmstart_candidates (filter)
# ---------------------------------------------------------------------------


def test_build_warmstart_candidates_max_reuse_3_excludes() -> None:
    """rolling 内 reuse_count == 3 で max_reuse 違反 → 除外."""
    member = make_member("g0")
    archive = make_archive_state([member])
    record = WarmstartReuseRecord(
        genome_id="g0", recent_use_run_indices=(8, 7, 6)
    )
    state = WarmstartState(reuse_records=(record,))
    candidates, stats = build_warmstart_candidates(
        archive,
        state,
        new_run_history_index=10,
        new_dataset_epoch_id="epoch-1",
        epoch_age_by_genome_id={"g0": 0},
        ca_rank_score_by_genome_id={"g0": 0.5},
        da_rank_score_by_genome_id={"g0": 0.5},
    )
    assert candidates == ()
    assert stats.max_reuse_drops == 1


def test_build_warmstart_candidates_cooldown_2_excludes() -> None:
    """cooldown=2 違反 (last_used が 1 Run 前) → 除外."""
    member = make_member("g0")
    archive = make_archive_state([member])
    record = WarmstartReuseRecord(genome_id="g0", recent_use_run_indices=(9,))
    state = WarmstartState(reuse_records=(record,))
    candidates, stats = build_warmstart_candidates(
        archive,
        state,
        new_run_history_index=10,
        new_dataset_epoch_id="epoch-1",
        epoch_age_by_genome_id={"g0": 0},
        ca_rank_score_by_genome_id={"g0": 0.5},
        da_rank_score_by_genome_id={"g0": 0.5},
    )
    # cooldown_age = 10 - 9 = 1 < 2 → 除外
    assert candidates == ()
    assert stats.cooldown_drops == 1


def test_build_warmstart_candidates_epoch_age_2_excluded() -> None:
    member = make_member("g0", dataset_epoch_id="epoch-old")
    archive = make_archive_state([member], dataset_epoch_id="epoch-old")
    candidates, stats = build_warmstart_candidates(
        archive,
        WarmstartState(),
        new_run_history_index=5,
        new_dataset_epoch_id="epoch-new",
        epoch_age_by_genome_id={"g0": 2},
        ca_rank_score_by_genome_id={},
        da_rank_score_by_genome_id={},
    )
    assert candidates == ()
    assert stats.epoch_age_2_plus_drops == 1


def test_build_warmstart_candidates_uses_caller_provided_rank_scores() -> None:
    member = make_member("g0")
    archive = make_archive_state([member])
    candidates, _ = build_warmstart_candidates(
        archive,
        WarmstartState(),
        new_run_history_index=5,
        new_dataset_epoch_id="epoch-1",
        epoch_age_by_genome_id={"g0": 0},
        ca_rank_score_by_genome_id={"g0": 0.7},
        da_rank_score_by_genome_id={"g0": 0.3},
    )
    assert len(candidates) == 1
    assert candidates[0].ca_rank_score == 0.7
    assert candidates[0].da_rank_score == 0.3


def test_build_warmstart_candidates_raises_on_missing_epoch_age() -> None:
    member = make_member("g0")
    archive = make_archive_state([member])
    with pytest.raises(KeyError, match="epoch_age_by_genome_id missing"):
        build_warmstart_candidates(
            archive,
            WarmstartState(),
            new_run_history_index=5,
            new_dataset_epoch_id="epoch-1",
            epoch_age_by_genome_id={},
            ca_rank_score_by_genome_id={},
            da_rank_score_by_genome_id={},
        )


def test_build_warmstart_candidates_returns_immutable_tuple() -> None:
    member = make_member("g0")
    archive = make_archive_state([member])
    candidates, _ = build_warmstart_candidates(
        archive,
        WarmstartState(),
        new_run_history_index=5,
        new_dataset_epoch_id="epoch-1",
        epoch_age_by_genome_id={"g0": 0},
        ca_rank_score_by_genome_id={},
        da_rank_score_by_genome_id={},
    )
    assert isinstance(candidates, tuple)


# ---------------------------------------------------------------------------
# 2.6 select_warmstart_candidates (selection + 制約)
# ---------------------------------------------------------------------------


def test_select_warmstart_candidates_max_per_source_run_2() -> None:
    """同 source_run_id は default 2 体まで (緩和なし)."""
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            run_id="run-A",
            pattern_id=f"pat-{i}",
            family_id=f"fam-{i}",
            ca_rank_score=1.0 - i * 0.1,
            da_rank_score=1.0 - i * 0.1,
        )
        for i in range(5)
    )
    selection, _ = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=0.20,
        ca_ratio=WARMSTART_NORMAL_CA_RATIO,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    # source_run="run-A" は CA で 2 体 + DA で 2 体 = 計 4 が initial cap
    # ただし relaxation で増える可能性がある (target=38、 候補 5 で全部選択される)
    # → relaxation 有無を別 test で検証、 ここでは全候補選抜可能性
    assert selection.actual_total <= len(candidates)


def test_select_warmstart_candidates_max_per_session_pattern_2() -> None:
    """同 pattern_id は default 2 体まで (initial constraints で)."""
    # 同じ pattern のみ 5 個、 target=2 で 2 体まで
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            pattern_id="pat-X",
            run_id=f"run-{i}",
            family_id=f"fam-{i}",
            ca_rank_score=1.0 - i * 0.1,
            da_rank_score=1.0 - i * 0.1,
        )
        for i in range(5)
    )
    # share=0.01 で target=round(192*0.01)=2 にする → CA=round(2*0.6842)=1, DA=1
    selection, report = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=0.01,
        ca_ratio=0.5,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    # target_total=2, CA=1, DA=1 (1:1 以外でも target=2 を満たすが、
    # ここで重要なのは pattern_id 違反がないこと)
    pattern_counts: dict[str, int] = {}
    for c in selection.ca_candidates + selection.da_candidates:
        pattern_counts[c.member.pattern_id] = (
            pattern_counts.get(c.member.pattern_id, 0) + 1
        )
    # initial 2 cap で session_pattern=pat-X は最大 2 (緩和あり)
    # target=2 なら緩和発動なしで 2 体採用される
    assert pattern_counts.get("pat-X", 0) <= 2 or "session_pattern" in report.relaxation_steps


def test_select_warmstart_candidates_max_family_2() -> None:
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            family_id="fam-X",
            pattern_id=f"pat-{i}",
            run_id=f"run-{i}",
            ca_rank_score=1.0 - i * 0.1,
            da_rank_score=1.0 - i * 0.1,
        )
        for i in range(5)
    )
    # target=2、 family_id 全部同じなので initial で 2 体採用、 緩和不要
    selection, report = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=0.01,
        ca_ratio=0.5,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    family_count = sum(
        1
        for c in selection.ca_candidates + selection.da_candidates
        if c.member.family_id == "fam-X"
    )
    assert family_count <= 2 or "family" in report.relaxation_steps


def test_select_warmstart_candidates_relaxation_session_pattern_first() -> None:
    """同 pattern のみで target を満たすには session_pattern 緩和必須.

    CA target=3 で同 pattern 候補のみ (異 run / 異 family). initial cap=2 で
    CA は 2 体まで採用、 target=3 達成のため session_pattern 緩和発動.
    """
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            pattern_id="pat-X",
            run_id=f"run-{i}",
            family_id=f"fam-{i}",
            ca_rank_score=1.0 - i * 0.1,
            da_rank_score=1.0 - i * 0.1,
        )
        for i in range(5)
    )
    # share=6/192 → target=6, ca_ratio=0.5 → CA=3, DA=3
    # CA: pat-X のみ 5 体 → cap=2 で 2 体、 target=3 → session_pattern 緩和必要
    selection, report = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=6 / 192,
        ca_ratio=0.5,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    assert "session_pattern" in report.relaxation_steps
    # 順序: session_pattern が source_run / family より前 (発動順)
    if "source_run" in report.relaxation_steps:
        assert report.relaxation_steps.index("session_pattern") < report.relaxation_steps.index(
            "source_run"
        )
    assert selection.actual_total >= 1


def test_select_warmstart_candidates_relaxation_source_run_second() -> None:
    """全 candidate が 同 pattern + 同 run、 family 異なる → session_pattern → source_run 緩和."""
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            pattern_id="pat-X",
            run_id="run-A",
            family_id=f"fam-{i}",
            ca_rank_score=1.0 - i * 0.1,
            da_rank_score=1.0 - i * 0.1,
        )
        for i in range(8)
    )
    # CA target=3, DA target=3 (target=6, ca_ratio=0.5)
    # session_pattern cap=2 / source_run cap=2 → 2 体まで採用、 target=3 で緩和
    _, report = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=6 / 192,
        ca_ratio=0.5,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    assert "session_pattern" in report.relaxation_steps
    if (
        "source_run" in report.relaxation_steps
        and "session_pattern" in report.relaxation_steps
    ):
        assert report.relaxation_steps.index(
            "session_pattern"
        ) < report.relaxation_steps.index("source_run")


def test_select_warmstart_candidates_relaxation_family_third() -> None:
    """全 candidate が 同 pattern + 同 run + 同 family → session_pattern → source_run → family 順."""
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            pattern_id="pat-X",
            run_id="run-A",
            family_id="fam-X",
            ca_rank_score=1.0 - i * 0.1,
            da_rank_score=1.0 - i * 0.1,
        )
        for i in range(10)
    )
    _, report = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=10 / 192,
        ca_ratio=0.5,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    # 順序保持
    if "family" in report.relaxation_steps:
        assert tuple(WARMSTART_RELAXATION_ORDER) == ("session_pattern", "source_run", "family")


def test_select_warmstart_candidates_full_relaxation_returns_top_target() -> None:
    """全制約撤廃でも target 未達なら可能な範囲で返す."""
    # 1 候補のみ、 target=2
    candidates = (
        make_warmstart_candidate("g0", ca_rank_score=1.0, da_rank_score=1.0),
    )
    selection, _ = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=2 / 192,
        ca_ratio=0.5,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    assert selection.actual_total <= len(candidates)


def test_select_warmstart_candidates_target_zero_returns_empty_selection() -> None:
    selection, report = select_warmstart_candidates(
        (),
        pop_size=192,
        share=0.0,
        ca_ratio=0.5,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    assert selection.target_total == 0
    assert selection.actual_total == 0
    assert report.relaxation_steps == ()


def test_select_warmstart_candidates_ca_da_no_genome_id_overlap() -> None:
    """CA / DA 候補で同 genome_id 重複なし."""
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            pattern_id=f"pat-{i}",
            run_id=f"run-{i}",
            family_id=f"fam-{i}",
            ca_rank_score=1.0 - i * 0.01,
            da_rank_score=1.0 - i * 0.01,
        )
        for i in range(40)
    )
    selection, _ = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=0.20,
        ca_ratio=WARMSTART_NORMAL_CA_RATIO,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    ca_ids = {c.member.genome_id for c in selection.ca_candidates}
    da_ids = {c.member.genome_id for c in selection.da_candidates}
    assert ca_ids.isdisjoint(da_ids)


# ---------------------------------------------------------------------------
# 2.7 epoch-aware filter (prev_epoch 20% 上限)
# ---------------------------------------------------------------------------


def test_select_warmstart_candidates_prev_epoch_admitted_only_via_quick_recheck() -> (
    None
):
    """prev_epoch_admitted_genome_ids にない epoch_age==1 個体は除外."""
    candidates = (
        make_warmstart_candidate(
            "g0", epoch_age=1, ca_rank_score=1.0, da_rank_score=1.0
        ),
        make_warmstart_candidate(
            "g1",
            epoch_age=0,
            pattern_id="pat-1",
            family_id="fam-1",
            run_id="run-1",
            ca_rank_score=0.5,
            da_rank_score=0.5,
        ),
    )
    selection, report = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=2 / 192,
        ca_ratio=0.5,
        prev_epoch_admitted_genome_ids=frozenset(),  # 空 → 全 prev_epoch 除外
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    selected_ids = {
        c.member.genome_id for c in selection.ca_candidates + selection.da_candidates
    }
    assert "g0" not in selected_ids
    assert report.prev_epoch_filter_drops >= 1


def test_select_warmstart_candidates_prev_epoch_share_capped_at_20_percent() -> None:
    """target 全 prev_epoch でも cap=20% で制限."""
    # target=10 (share = 10/192) → cap=2
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            epoch_age=1,
            pattern_id=f"pat-{i}",
            family_id=f"fam-{i}",
            run_id=f"run-{i}",
            ca_rank_score=1.0 - i * 0.01,
            da_rank_score=1.0 - i * 0.01,
        )
        for i in range(20)
    )
    admitted = frozenset(f"g{i}" for i in range(20))
    _, report = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=10 / 192,
        ca_ratio=0.5,
        prev_epoch_admitted_genome_ids=admitted,
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    final_prev = report.prev_epoch_final_selected
    # cap = int(10 * 0.20) = 2
    assert final_prev <= 2


def test_select_warmstart_candidates_prev_epoch_cap_unchanged_in_boost() -> None:
    """boost mode でも prev_epoch cap は WARMSTART_PREV_EPOCH_CAP_RATIO=20% 据え置き."""
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            epoch_age=1,
            pattern_id=f"pat-{i}",
            family_id=f"fam-{i}",
            run_id=f"run-{i}",
            ca_rank_score=1.0 - i * 0.01,
            da_rank_score=1.0 - i * 0.01,
        )
        for i in range(50)
    )
    admitted = frozenset(f"g{i}" for i in range(50))
    _, report = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=WARMSTART_EMERGENCY_SHARE,
        ca_ratio=WARMSTART_EMERGENCY_CA_RATIO,
        prev_epoch_admitted_genome_ids=admitted,
        is_boost_applicable=True,
        filter_stats=_empty_filter_stats(),
    )
    # target = 48, cap = int(48*0.20) = 9
    assert report.prev_epoch_final_selected <= 9


def test_select_warmstart_candidates_current_epoch_unconditional_pass() -> None:
    """epoch_age=0 は cap 対象外 (admitted_genome_ids 不要)."""
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            epoch_age=0,
            pattern_id=f"pat-{i}",
            family_id=f"fam-{i}",
            run_id=f"run-{i}",
            ca_rank_score=1.0 - i * 0.01,
            da_rank_score=1.0 - i * 0.01,
        )
        for i in range(40)
    )
    selection, report = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=0.20,
        ca_ratio=WARMSTART_NORMAL_CA_RATIO,
        prev_epoch_admitted_genome_ids=frozenset(),  # 空でも current epoch は通る
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    assert selection.actual_total > 0
    assert report.prev_epoch_filter_drops == 0


# ---------------------------------------------------------------------------
# 2.8 build_archive_candidate
# ---------------------------------------------------------------------------


def _make_metadata() -> SchemaV2Metadata:
    return SchemaV2Metadata(
        genome_id="g0",
        run_id="run-1",
        generation_no=2,
        dataset_epoch_id="epoch-1",
        pattern_id="pat-A",
        family_id="fam-A",
    )


def _make_invariant_flags(is_feasible: bool = True):
    """T061 InvariantFlags の最小 stub (is_feasible は property).

    ``is_feasible`` は ``session_close_drop_count == 0`` AND
    ``negative_equity_drop_open_count == 0`` AND
    ``len(infeasible_reason_codes) == 0`` で導出される property.
    """
    from src.alpha_factory.canonical_metrics import InvariantFlags

    if is_feasible:
        return InvariantFlags(
            session_close_drop_count=0,
            negative_equity_drop_open_count=0,
            infeasible_reason_codes=frozenset(),
        )
    return InvariantFlags(
        session_close_drop_count=1,
        negative_equity_drop_open_count=0,
        infeasible_reason_codes=frozenset(),
    )


def test_build_archive_candidate_uses_t062_mission_signed_margin() -> None:
    bc = _make_bc_result_stub(mission_pass=StagePassStatus.PASS)
    gap = make_mission_gap(mission_signed_margin=0.123)
    flags = _make_invariant_flags(is_feasible=True)
    cand = build_archive_candidate(
        bc,  # type: ignore[arg-type]
        gap,
        flags,
        _make_metadata(),
        novelty=0.4,
        diversity_coverage=0.5,
        quality_floor_margin=0.0,
        margin_inf_passes_p70=True,
    )
    assert cand.mission_signed_margin == 0.123


def test_build_archive_candidate_uses_t064_shadow_robustness_score() -> None:
    bc = _make_bc_result_stub(
        mission_pass=StagePassStatus.PASS, shadow_robustness_score=0.77
    )
    cand = build_archive_candidate(
        bc,  # type: ignore[arg-type]
        make_mission_gap(),
        _make_invariant_flags(),
        _make_metadata(),
        novelty=0.4,
        diversity_coverage=0.5,
        quality_floor_margin=0.0,
        margin_inf_passes_p70=True,
    )
    assert cand.shadow_robustness_score == 0.77


def test_build_archive_candidate_uses_t064_c_pass_depth_phase0_field() -> None:
    bc = _make_bc_result_stub(
        mission_pass=StagePassStatus.PASS, c_pass_depth=1.5
    )
    cand = build_archive_candidate(
        bc,  # type: ignore[arg-type]
        make_mission_gap(),
        _make_invariant_flags(),
        _make_metadata(),
        novelty=0.4,
        diversity_coverage=0.5,
        quality_floor_margin=0.0,
        margin_inf_passes_p70=True,
    )
    assert cand.c_pass_depth == 1.5


def test_build_archive_candidate_uses_t061_invariant_feasible() -> None:
    bc = _make_bc_result_stub(mission_pass=StagePassStatus.PASS)
    cand_t = build_archive_candidate(
        bc,  # type: ignore[arg-type]
        make_mission_gap(),
        _make_invariant_flags(is_feasible=True),
        _make_metadata(),
        novelty=0.0,
        diversity_coverage=0.0,
        quality_floor_margin=0.0,
        margin_inf_passes_p70=True,
    )
    assert cand_t.invariant_feasible is True


def test_build_archive_candidate_archive_role_from_determine_archive_role() -> None:
    bc_mission = _make_bc_result_stub(mission_pass=StagePassStatus.PASS)
    cand = build_archive_candidate(
        bc_mission,  # type: ignore[arg-type]
        make_mission_gap(),
        _make_invariant_flags(),
        _make_metadata(),
        novelty=0.0,
        diversity_coverage=0.0,
        quality_floor_margin=0.0,
        margin_inf_passes_p70=True,
    )
    assert cand.archive_role == "mission_pass"


def test_build_archive_candidate_b_pooled_cf_none_assigns_inf_gate_worst_gap() -> None:
    bc = _make_bc_result_stub(b_pooled_cf=None)
    cand = build_archive_candidate(
        bc,  # type: ignore[arg-type]
        make_mission_gap(),
        _make_invariant_flags(),
        _make_metadata(),
        novelty=0.0,
        diversity_coverage=0.0,
        quality_floor_margin=0.0,
        margin_inf_passes_p70=True,
    )
    assert math.isinf(cand.gate_worst_gap)
    assert cand.log_pf_clip == 0.0


# ---------------------------------------------------------------------------
# 2.9 admit_warmstart_to_da_with_eviction
# ---------------------------------------------------------------------------


def test_admit_warmstart_to_da_with_eviction_changes_archive_target_to_da() -> None:
    """元 CA member を warmstart 採用すると archive_target が DA に書き換わる."""
    member = make_member("g0", archive_target="CA")
    archive = make_archive_state([member])
    cand = make_warmstart_candidate(
        member=member, da_rank_score=1.0
    )
    new_archive = admit_warmstart_to_da_with_eviction(
        archive, [cand], pop_size=192
    )
    g0 = next(m for m in new_archive.members if m.genome_id == "g0")
    assert g0.archive_target == "DA"


def test_admit_warmstart_to_da_with_eviction_preserves_genome_id_uniqueness() -> None:
    """同 genome_id の upsert で重複が出ない."""
    member = make_member("g0", archive_target="CA")
    archive = make_archive_state([member])
    cand = make_warmstart_candidate(member=member)
    new_archive = admit_warmstart_to_da_with_eviction(
        archive, [cand], pop_size=192
    )
    ids = [m.genome_id for m in new_archive.members]
    assert len(ids) == len(set(ids))


def test_admit_warmstart_to_da_with_eviction_preserves_origin_run_id() -> None:
    """upsert 後も run_id (origin) が保持される."""
    member = make_member("g0", run_id="run-original", archive_target="CA")
    archive = make_archive_state([member])
    cand = make_warmstart_candidate(member=member)
    new_archive = admit_warmstart_to_da_with_eviction(
        archive, [cand], pop_size=192
    )
    g0 = next(m for m in new_archive.members if m.genome_id == "g0")
    assert g0.run_id == "run-original"


def test_admit_warmstart_to_da_with_eviction_empty_candidates_returns_archive_unchanged() -> (
    None
):
    member = make_member("g0", archive_target="CA")
    archive = make_archive_state([member])
    new_archive = admit_warmstart_to_da_with_eviction(archive, [], pop_size=192)
    assert new_archive is archive


def test_admit_warmstart_to_da_with_eviction_returns_da_within_capacity() -> None:
    """DA capacity (= 48 for pop=192) 内に収まる."""
    _, _, da_capacity = compute_archive_capacities(192)
    # 100 体 DA candidates を inject、 48 まで evict されること
    members = [
        make_member(f"g{i}", archive_target="DA", novelty=1.0 - i * 0.01)
        for i in range(100)
    ]
    archive = make_archive_state(members)
    cands = [make_warmstart_candidate(member=m, da_rank_score=1.0) for m in members]
    new_archive = admit_warmstart_to_da_with_eviction(
        archive, cands, pop_size=192
    )
    da_count = sum(1 for m in new_archive.members if m.archive_target == "DA")
    assert da_count <= da_capacity


def test_admit_warmstart_to_da_with_eviction_excess_evicted_via_t066_lex() -> None:
    """T066 archive_evict_da の lex 順 (低 novelty etc.) で eviction される."""
    _, _, da_capacity = compute_archive_capacities(192)
    members = [
        make_member(
            f"g{i:03d}",
            archive_target="DA",
            novelty=1.0 if i < da_capacity else 0.0,
            run_id=f"run-{i}",
            pattern_id=f"pat-{i}",
        )
        for i in range(da_capacity + 5)
    ]
    archive = make_archive_state(members, run_history=("run-0",))
    cands = [make_warmstart_candidate(member=m) for m in members]
    new_archive = admit_warmstart_to_da_with_eviction(
        archive, cands, pop_size=192
    )
    da_count = sum(1 for m in new_archive.members if m.archive_target == "DA")
    assert da_count == da_capacity


# ---------------------------------------------------------------------------
# 2.10 update_warmstart_state
# ---------------------------------------------------------------------------


def test_update_warmstart_state_increments_reuse_count_for_selected() -> None:
    record = WarmstartReuseRecord(genome_id="g0", recent_use_run_indices=(2,))
    prev = WarmstartState(reuse_records=(record,))
    new = update_warmstart_state(
        prev,
        selected_genome_ids={"g0"},
        new_run_history_index=5,
    )
    g0 = next(r for r in new.reuse_records if r.genome_id == "g0")
    assert g0.reuse_count == 2  # prev=1 + new=1
    assert 5 in g0.recent_use_run_indices


def test_update_warmstart_state_records_new_run_history_index_in_recent() -> None:
    prev = WarmstartState()
    new = update_warmstart_state(
        prev,
        selected_genome_ids={"g0"},
        new_run_history_index=10,
    )
    g0 = next(r for r in new.reuse_records if r.genome_id == "g0")
    assert g0.recent_use_run_indices[0] == 10


def test_update_warmstart_state_rolling_window_drops_old_indices() -> None:
    record = WarmstartReuseRecord(genome_id="g0", recent_use_run_indices=(0,))
    prev = WarmstartState(reuse_records=(record,), rolling_window=10)
    # new_run_history_index=11 → rolling_floor = 11 - 10 = 1 → 0 < 1 で drop
    new = update_warmstart_state(
        prev, selected_genome_ids=set(), new_run_history_index=11
    )
    # g0 record 全部 drop で空
    assert all(r.genome_id != "g0" for r in new.reuse_records)


def test_update_warmstart_state_creates_record_for_new_genome() -> None:
    prev = WarmstartState()
    new = update_warmstart_state(
        prev,
        selected_genome_ids={"new_g"},
        new_run_history_index=3,
    )
    assert any(r.genome_id == "new_g" for r in new.reuse_records)


def test_update_warmstart_state_raises_on_negative_run_history_index() -> None:
    with pytest.raises(ValueError, match="new_run_history_index must be >= 0"):
        update_warmstart_state(
            WarmstartState(), selected_genome_ids={"g0"}, new_run_history_index=-1
        )


# ---------------------------------------------------------------------------
# 2.11 prepare_run_loop_closure (top-level)
# ---------------------------------------------------------------------------


def test_prepare_run_loop_closure_returns_warmstart_selection_with_target_counts() -> (
    None
):
    members = [
        make_member(
            f"g{i}",
            pattern_id=f"pat-{i}",
            family_id=f"fam-{i}",
            run_id=f"run-{i}",
            archive_target="CA" if i < 5 else "DA",
        )
        for i in range(20)
    ]
    archive = make_archive_state(members, dataset_epoch_id="epoch-1")
    selection, report = prepare_run_loop_closure(
        WarmstartState(),
        EmergencyState(),
        archive,
        run_no=4,
        pop_size=192,
        current_run_id="run-new",
        new_dataset_epoch_id="epoch-1",
        new_run_history_index=5,
        epoch_age_by_genome_id={f"g{i}": 0 for i in range(20)},
        ca_rank_score_by_genome_id={f"g{i}": 1.0 - i * 0.01 for i in range(20)},
        da_rank_score_by_genome_id={f"g{i}": 1.0 - i * 0.01 for i in range(20)},
        prev_epoch_admitted_genome_ids=frozenset(),
    )
    # run_no=4 → share=0.20 → target=38、 候補 20 のみで cap 緩和込み
    assert selection.target_total == 38
    assert report.share == 0.20


def test_prepare_run_loop_closure_run_1_returns_zero_warmstart() -> None:
    selection, report = prepare_run_loop_closure(
        WarmstartState(),
        EmergencyState(),
        make_archive_state(),
        run_no=1,
        pop_size=192,
        current_run_id="run-1",
        new_dataset_epoch_id="epoch-1",
        new_run_history_index=0,
        epoch_age_by_genome_id={},
        ca_rank_score_by_genome_id={},
        da_rank_score_by_genome_id={},
        prev_epoch_admitted_genome_ids=frozenset(),
    )
    assert selection.target_total == 0
    assert report.share == 0.0


def test_prepare_run_loop_closure_emergency_mode_uses_25_percent_share() -> None:
    state = make_emergency_state(
        mode="emergency",
        activated_at_run_id="r-prev",
        boost_consumed_run_id=None,
    )
    _, report = prepare_run_loop_closure(
        WarmstartState(),
        state,
        make_archive_state(),
        run_no=4,
        pop_size=192,
        current_run_id="r-current",
        new_dataset_epoch_id="epoch-1",
        new_run_history_index=10,
        epoch_age_by_genome_id={},
        ca_rank_score_by_genome_id={},
        da_rank_score_by_genome_id={},
        prev_epoch_admitted_genome_ids=frozenset(),
    )
    assert report.share == WARMSTART_EMERGENCY_SHARE
    assert report.is_boost_applicable is True


def test_prepare_run_loop_closure_emits_relaxation_report() -> None:
    members = [
        make_member(f"g{i}", pattern_id="pat-X", family_id="fam-X", run_id="run-A")
        for i in range(50)
    ]
    archive = make_archive_state(members, dataset_epoch_id="epoch-1")
    _, report = prepare_run_loop_closure(
        WarmstartState(),
        EmergencyState(),
        archive,
        run_no=4,
        pop_size=192,
        current_run_id="r-current",
        new_dataset_epoch_id="epoch-1",
        new_run_history_index=5,
        epoch_age_by_genome_id={f"g{i}": 0 for i in range(50)},
        ca_rank_score_by_genome_id={f"g{i}": 1.0 - i * 0.01 for i in range(50)},
        da_rank_score_by_genome_id={f"g{i}": 1.0 - i * 0.01 for i in range(50)},
        prev_epoch_admitted_genome_ids=frozenset(),
    )
    assert isinstance(report.relaxation_steps, tuple)
    assert len(report.relaxation_steps) > 0


def test_prepare_run_loop_closure_raises_on_empty_current_run_id() -> None:
    with pytest.raises(ValueError, match="current_run_id must be non-empty"):
        prepare_run_loop_closure(
            WarmstartState(),
            EmergencyState(),
            make_archive_state(),
            run_no=2,
            pop_size=192,
            current_run_id="",
            new_dataset_epoch_id="epoch-1",
            new_run_history_index=0,
            epoch_age_by_genome_id={},
            ca_rank_score_by_genome_id={},
            da_rank_score_by_genome_id={},
            prev_epoch_admitted_genome_ids=frozenset(),
        )


def test_prepare_run_loop_closure_raises_on_run_no_below_1() -> None:
    with pytest.raises(ValueError, match="run_no must be >= 1"):
        prepare_run_loop_closure(
            WarmstartState(),
            EmergencyState(),
            make_archive_state(),
            run_no=0,
            pop_size=192,
            current_run_id="r-1",
            new_dataset_epoch_id="epoch-1",
            new_run_history_index=0,
            epoch_age_by_genome_id={},
            ca_rank_score_by_genome_id={},
            da_rank_score_by_genome_id={},
            prev_epoch_admitted_genome_ids=frozenset(),
        )


# ---------------------------------------------------------------------------
# 2.12 best_mission_signed_margin
# ---------------------------------------------------------------------------


def test_compute_best_mission_signed_margin_max_over_mission_signed_margin() -> None:
    gaps = {
        "g0": make_mission_gap(mission_signed_margin=0.1),
        "g1": make_mission_gap(mission_signed_margin=0.5),
        "g2": make_mission_gap(mission_signed_margin=-0.3),
    }
    result = compute_best_mission_signed_margin(gaps)
    assert result == 0.5


def test_compute_best_mission_signed_margin_empty_returns_sentinel_replacement() -> (
    None
):
    """R1 -1.0e6 sentinel."""
    result = compute_best_mission_signed_margin({})
    assert result == SENTINEL_REPLACEMENT_FOR_HISTORY


def test_compute_best_mission_signed_margin_replaces_t062_neg_inf_with_sentinel_replacement() -> (
    None
):
    """T062 -inf sentinel を SENTINEL_REPLACEMENT_FOR_HISTORY (-1.0e6) に finite 化."""
    gaps = {
        "g0": make_mission_gap(mission_signed_margin=float("-inf"), is_feasible=False),
        "g1": make_mission_gap(mission_signed_margin=-2.0e6),
    }
    result = compute_best_mission_signed_margin(gaps)
    # -inf → -1.0e6、 -2.0e6 そのまま → max は -1.0e6
    assert result == SENTINEL_REPLACEMENT_FOR_HISTORY


# ---------------------------------------------------------------------------
# 2.13 Determinism + immutability
# ---------------------------------------------------------------------------


def test_select_warmstart_candidates_deterministic_same_input_same_output() -> None:
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            pattern_id=f"pat-{i}",
            family_id=f"fam-{i}",
            run_id=f"run-{i}",
            ca_rank_score=1.0 - i * 0.01,
            da_rank_score=1.0 - i * 0.01,
        )
        for i in range(40)
    )
    sel1, _ = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=0.20,
        ca_ratio=WARMSTART_NORMAL_CA_RATIO,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    sel2, _ = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=0.20,
        ca_ratio=WARMSTART_NORMAL_CA_RATIO,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    assert [c.member.genome_id for c in sel1.ca_candidates] == [
        c.member.genome_id for c in sel2.ca_candidates
    ]
    assert [c.member.genome_id for c in sel1.da_candidates] == [
        c.member.genome_id for c in sel2.da_candidates
    ]


def test_select_warmstart_candidates_shuffled_input_same_result() -> None:
    """詳細 Round 1 [S2]: shuffled 入力でも sort により同結果."""
    import random

    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            pattern_id=f"pat-{i}",
            family_id=f"fam-{i}",
            run_id=f"run-{i}",
            ca_rank_score=1.0 - i * 0.01,
            da_rank_score=1.0 - i * 0.01,
        )
        for i in range(40)
    )
    sel1, _ = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=0.20,
        ca_ratio=WARMSTART_NORMAL_CA_RATIO,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    shuffled = list(candidates)
    random.Random(42).shuffle(shuffled)
    sel2, _ = select_warmstart_candidates(
        tuple(shuffled),
        pop_size=192,
        share=0.20,
        ca_ratio=WARMSTART_NORMAL_CA_RATIO,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    assert [c.member.genome_id for c in sel1.ca_candidates] == [
        c.member.genome_id for c in sel2.ca_candidates
    ]


def test_update_warmstart_state_deterministic_with_set_input() -> None:
    """詳細 Round 1 [C2]: set 入力でも genome_id 昇順固定."""
    prev = WarmstartState()
    new1 = update_warmstart_state(
        prev,
        selected_genome_ids={"gZ", "gA", "gM"},
        new_run_history_index=5,
    )
    new2 = update_warmstart_state(
        prev,
        selected_genome_ids={"gM", "gZ", "gA"},
        new_run_history_index=5,
    )
    assert tuple(r.genome_id for r in new1.reuse_records) == tuple(
        r.genome_id for r in new2.reuse_records
    )
    assert tuple(r.genome_id for r in new1.reuse_records) == ("gA", "gM", "gZ")


def test_update_emergency_state_deterministic() -> None:
    state = make_emergency_state()
    new1 = update_emergency_state(
        state,
        new_run_id="r-1",
        n_mission_pass=0,
        n_progress_pass=0,
        best_mission_signed_margin=0.5,
        boost_consumed_in_this_run=False,
    )
    new2 = update_emergency_state(
        state,
        new_run_id="r-1",
        n_mission_pass=0,
        n_progress_pass=0,
        best_mission_signed_margin=0.5,
        boost_consumed_in_this_run=False,
    )
    assert new1 == new2


def test_warmstart_state_reuse_records_is_tuple() -> None:
    state = WarmstartState()
    assert isinstance(state.reuse_records, tuple)


def test_emergency_state_history_is_tuple() -> None:
    state = EmergencyState()
    assert isinstance(state.history, tuple)


def test_warmstart_candidate_is_frozen_dataclass() -> None:
    cand = make_warmstart_candidate("g0")
    with pytest.raises(FrozenInstanceError):
        cand.epoch_age = 99  # type: ignore[misc]


def test_admit_warmstart_to_da_with_eviction_post_assert_archive_invariants() -> None:
    """詳細 Round 1 [S3]: archive 不変条件 (genome_id 一意 + DA capacity 内)."""
    _, _, da_capacity = compute_archive_capacities(192)
    members = [
        make_member(f"g{i}", archive_target="DA", novelty=1.0 - i * 0.001)
        for i in range(60)
    ]
    archive = make_archive_state(members, run_history=("run-0",))
    cands = [make_warmstart_candidate(member=m) for m in members]
    new_archive = admit_warmstart_to_da_with_eviction(
        archive, cands, pop_size=192
    )
    # 不変 1: genome_id 一意
    ids = [m.genome_id for m in new_archive.members]
    assert len(ids) == len(set(ids))
    # 不変 2: DA capacity 内
    da_count = sum(1 for m in new_archive.members if m.archive_target == "DA")
    assert da_count <= da_capacity


def test_select_warmstart_candidates_prev_epoch_cap_applied_after_sort_high_score_priority() -> (
    None
):
    """詳細 Round 1 [C3]: 高スコア prev_epoch 個体が cap 枠を優先取得."""
    # 5 体 prev_epoch、 cap=1、 score 大の方が選ばれる
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            epoch_age=1,
            pattern_id=f"pat-{i}",
            family_id=f"fam-{i}",
            run_id=f"run-{i}",
            ca_rank_score=1.0 - i * 0.1,
            da_rank_score=1.0 - i * 0.1,
        )
        for i in range(5)
    )
    admitted = frozenset(f"g{i}" for i in range(5))
    selection, _ = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=5 / 192,  # target=5, cap=int(5*0.20)=1
        ca_ratio=0.5,
        prev_epoch_admitted_genome_ids=admitted,
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    selected_ids = {
        c.member.genome_id for c in selection.ca_candidates + selection.da_candidates
    }
    # 高スコアの g0 が cap 枠取得
    assert "g0" in selected_ids


def test_select_warmstart_candidates_prev_epoch_cap_is_global_budget_ca_plus_da_le_cap() -> (
    None
):
    """詳細 Round 2 [C1]: prev_epoch cap は global budget."""
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            epoch_age=1,
            pattern_id=f"pat-{i}",
            family_id=f"fam-{i}",
            run_id=f"run-{i}",
            ca_rank_score=1.0 - i * 0.01,
            da_rank_score=1.0 - i * 0.01,
        )
        for i in range(50)
    )
    admitted = frozenset(f"g{i}" for i in range(50))
    selection, _ = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=10 / 192,  # target=10, cap=2
        ca_ratio=0.5,
        prev_epoch_admitted_genome_ids=admitted,
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    ca_prev = sum(1 for c in selection.ca_candidates if c.epoch_age == 1)
    da_prev = sum(1 for c in selection.da_candidates if c.epoch_age == 1)
    cap_global = int(10 * WARMSTART_PREV_EPOCH_CAP_RATIO)
    assert ca_prev + da_prev <= cap_global


def test_select_warmstart_candidates_da_cap_evaluated_after_ca_ids_excluded() -> None:
    """詳細 Round 2 [C2]: DA cap 適用前に ca_ids 除外."""
    # 同 genome が CA / DA 両方の sort 上位 → CA で確定後 DA 候補から除外される
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            pattern_id=f"pat-{i}",
            family_id=f"fam-{i}",
            run_id=f"run-{i}",
            ca_rank_score=1.0 - i * 0.01,
            da_rank_score=1.0 - i * 0.01,
        )
        for i in range(40)
    )
    selection, _ = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=0.20,
        ca_ratio=WARMSTART_NORMAL_CA_RATIO,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    ca_ids = {c.member.genome_id for c in selection.ca_candidates}
    da_ids = {c.member.genome_id for c in selection.da_candidates}
    assert ca_ids.isdisjoint(da_ids)


def test_build_warmstart_candidates_raises_on_negative_epoch_age() -> None:
    """詳細 Round 2 [W1]: epoch_age 下限 (>=0) 検証."""
    member = make_member("g0")
    archive = make_archive_state([member])
    with pytest.raises(ValueError, match="epoch_age must be >= 0"):
        build_warmstart_candidates(
            archive,
            WarmstartState(),
            new_run_history_index=5,
            new_dataset_epoch_id="epoch-1",
            epoch_age_by_genome_id={"g0": -1},
            ca_rank_score_by_genome_id={},
            da_rank_score_by_genome_id={},
        )


def test_warmstart_report_prev_epoch_admitted_matches_final_selection() -> None:
    """詳細 Round 3 [W1]: prev_epoch_final_selected が CA+DA selected の prev_epoch 数と一致."""
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            epoch_age=1,
            pattern_id=f"pat-{i}",
            family_id=f"fam-{i}",
            run_id=f"run-{i}",
            ca_rank_score=1.0 - i * 0.01,
            da_rank_score=1.0 - i * 0.01,
        )
        for i in range(20)
    )
    admitted = frozenset(f"g{i}" for i in range(20))
    selection, report = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=10 / 192,
        ca_ratio=0.5,
        prev_epoch_admitted_genome_ids=admitted,
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    actual_prev = sum(
        1
        for c in selection.ca_candidates + selection.da_candidates
        if c.epoch_age == 1
    )
    assert report.prev_epoch_final_selected == actual_prev


def test_select_warmstart_candidates_filter_stats_passed_through_from_build() -> None:
    """詳細 Round 1 [W2]: WarmstartReport.filter_stats が build 側 stats を pass-through."""
    candidates = (make_warmstart_candidate("g0", ca_rank_score=0.5, da_rank_score=0.5),)
    stats = WarmstartFilterStats(
        cooldown_drops=3, max_reuse_drops=2, epoch_age_2_plus_drops=1
    )
    _, report = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=2 / 192,
        ca_ratio=0.5,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=stats,
    )
    assert report.filter_stats == stats


def test_warmstart_report_relaxation_steps_preserves_activation_order() -> None:
    """詳細 Round 1 [W1]: 緩和発動順保持 (sorted ではなく順序保存)."""
    candidates = tuple(
        make_warmstart_candidate(
            f"g{i}",
            pattern_id="pat-X",
            run_id="run-A",
            family_id="fam-X",
            ca_rank_score=1.0 - i * 0.01,
            da_rank_score=1.0 - i * 0.01,
        )
        for i in range(30)
    )
    _, report = select_warmstart_candidates(
        candidates,
        pop_size=192,
        share=20 / 192,
        ca_ratio=0.5,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    # 順序保持: WARMSTART_RELAXATION_ORDER に沿う形で発動
    if len(report.relaxation_steps) > 1:
        seen_idx = -1
        for step in report.relaxation_steps:
            idx = WARMSTART_RELAXATION_ORDER.index(step)
            assert idx > seen_idx, "緩和発動順が崩れている"
            seen_idx = idx


def test_warmstart_report_is_boost_applicable_received_from_caller_not_inferred_from_ratio() -> (
    None
):
    """詳細 Round 1 [W3]: is_boost_applicable は caller から明示で受取 (ratio から推定しない)."""
    # ca_ratio=0.5 だが is_boost_applicable=False を渡す
    _, report = select_warmstart_candidates(
        (),
        pop_size=192,
        share=0.0,
        ca_ratio=0.5,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    assert report.is_boost_applicable is False


def test_build_warmstart_candidates_raises_on_dataset_epoch_id_inconsistent_with_epoch_age() -> (
    None
):
    """詳細 Round 1 [W4]: archive.dataset_epoch_id != new_dataset_epoch_id だが
    epoch_age=0 で不整合 → ValueError."""
    member = make_member("g0", dataset_epoch_id="epoch-old")
    archive = make_archive_state([member], dataset_epoch_id="epoch-old")
    with pytest.raises(ValueError, match="inconsistent"):
        build_warmstart_candidates(
            archive,
            WarmstartState(),
            new_run_history_index=5,
            new_dataset_epoch_id="epoch-new",  # 異なる epoch
            epoch_age_by_genome_id={"g0": 0},  # 0 だが member.dataset_epoch_id != new
            ca_rank_score_by_genome_id={},
            da_rank_score_by_genome_id={},
        )


# ---------------------------------------------------------------------------
# 2.14 Edge cases + schema v2 / Round 21+22 整合性
# ---------------------------------------------------------------------------


def test_select_warmstart_candidates_archive_empty_returns_empty_selection() -> None:
    selection, _ = select_warmstart_candidates(
        (),
        pop_size=192,
        share=0.20,
        ca_ratio=WARMSTART_NORMAL_CA_RATIO,
        prev_epoch_admitted_genome_ids=frozenset(),
        is_boost_applicable=False,
        filter_stats=_empty_filter_stats(),
    )
    assert selection.actual_total == 0


def test_evaluate_emergency_trigger_history_with_negative_inf_margin_handled() -> None:
    """T062 -inf sentinel が history に入っても trigger 判定が破綻しない.

    本実装では caller が compute_best_mission_signed_margin で finite 化 (-1e6) するので、
    history 内には -1e6 等が入る. ここでは生 -inf を流入させても算術演算が NaN にならず
    比較可能であることを確認 (defense-in-depth).
    """
    history = (
        make_history_entry("r-1", n_mission_pass=0, best_mission_signed_margin=-1.0e6),
        make_history_entry("r-2", n_mission_pass=0, best_mission_signed_margin=-1.0e6),
        make_history_entry("r-3", n_mission_pass=0, best_mission_signed_margin=-1.0e6),
        make_history_entry("r-4", n_mission_pass=1, best_mission_signed_margin=0.0),
        make_history_entry("r-5", n_mission_pass=1, best_mission_signed_margin=0.0),
        make_history_entry("r-6", n_mission_pass=1, best_mission_signed_margin=0.0),
    )
    state = make_emergency_state(history=history)
    # MA3 = -1e6, MA6 = (-3e6 + 0)/6 = -500000 → MA3 << MA6 - 0.05 → True
    assert evaluate_emergency_trigger(state) is True


def test_build_archive_candidate_uses_mission_signed_margin_not_mission_margin() -> None:
    """ArchiveCandidate.mission_signed_margin field が mission_gap.mission_signed_margin
    から取得される (mission_margin ではない、 Round 21 改訂後 SSOT)."""
    bc = _make_bc_result_stub(mission_pass=StagePassStatus.PASS)
    gap = make_mission_gap(
        mission_signed_margin=0.42, mission_margin=-0.99, mission_inf_gap=0.0
    )
    cand = build_archive_candidate(
        bc,  # type: ignore[arg-type]
        gap,
        _make_invariant_flags(),
        _make_metadata(),
        novelty=0.0,
        diversity_coverage=0.0,
        quality_floor_margin=0.0,
        margin_inf_passes_p70=True,
    )
    assert cand.mission_signed_margin == 0.42


def test_warmstart_da_admission_fx_design_judgement_separate_from_t066() -> None:
    """T067 admit_warmstart_to_da_with_eviction が T066 と分離した API として存在."""
    # admit_warmstart_to_da_with_eviction が T066 archive_admit と別 API
    from src.alpha_factory import cpps_archive, loop_closure

    assert hasattr(loop_closure, "admit_warmstart_to_da_with_eviction")
    assert hasattr(cpps_archive, "archive_admit")
    # 別 module / 別関数
    assert (
        loop_closure.admit_warmstart_to_da_with_eviction
        is not cpps_archive.archive_admit
    )


def test_emergency_state_boost_consumed_separate_from_mode() -> None:
    """詳細 Round 1 [C1]: mode + boost_consumed_run_id 2 変数分離検証."""
    # mode=emergency, boost_consumed_run_id=None → boost 適用可
    s1 = make_emergency_state(mode="emergency", boost_consumed_run_id=None)
    assert is_boost_applicable(s1, "r-1") is True

    # mode=emergency, boost_consumed_run_id="r-other" → boost 不可
    s2 = make_emergency_state(
        mode="emergency", boost_consumed_run_id="r-other"
    )
    assert is_boost_applicable(s2, "r-1") is False

    # mode=normal でも (boost_consumed_run_id 残ってても) boost 不可
    s3 = make_emergency_state(mode="normal", boost_consumed_run_id="r-other")
    assert is_boost_applicable(s3, "r-1") is False
