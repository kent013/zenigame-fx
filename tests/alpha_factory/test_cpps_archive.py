"""T066 PR 1: tests for src/alpha_factory/cpps_archive.py.

詳細設計参照: devnotes/20260430-1200-todo-T066-cpps-fsm-and-archive/detailed-design.md § 施策 2.

13 sub-suite × 約 80 test、 fixtures は本ファイル内 builder helper として共通化.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import fields, is_dataclass

import pytest

from src.alpha_factory.cpps_archive import (
    ARCHIVE_ROLE_PRIORITY,
    PATTERN_MAX_SHARE,
    PULL_CA_RATIO,
    PUSH_CA_RATIO,
    RECENCY_FLOOR_COUNT,
    RECENCY_FLOOR_LAST_N_RUNS,
    RUN_HISTORY_MAXLEN,
    SUPPORTED_POP_SIZES,
    ArchiveCandidate,
    ArchiveMember,
    ArchiveState,
    PushPullState,
    archive_admit,
    archive_evict_ca,
    archive_evict_da,
    compute_archive_capacities,
    compute_ca_da_capacities,
    compute_inflow_targets,
    determine_archive_role,
    partition_survivors_to_ca_da,
    update_archive_per_run,
    update_push_pull_state,
)
from src.alpha_factory.stage_bc_evaluator import BCEvaluationResult, StagePassStatus

# ---------------------------------------------------------------------------
# Builders (test fixtures)
# ---------------------------------------------------------------------------


def make_candidate(
    genome_id: str = "g0",
    *,
    run_id: str = "run-1",
    generation_no: int = 0,
    dataset_epoch_id: str = "epoch-1",
    pattern_id: str | None = None,
    family_id: str = "fam-A",
    archive_role: str = "mission_pass",
    gate_worst_gap: float = 0.0,
    c_pass_depth: float = 1.0,
    mission_signed_margin: float = 0.0,
    shadow_robustness_score: float = 1.0,
    log_pf_clip: float = 0.0,
    invariant_feasible: bool = True,
    margin_inf: float = 0.0,
    margin_inf_passes_p70: bool = True,
    novelty: float = 0.5,
    diversity_coverage: float = 0.5,
    quality_floor_margin: float = 0.0,
) -> ArchiveCandidate:
    """ArchiveCandidate ビルダー (test 用、 各 field を独立して上書き可能)."""
    if pattern_id is None:
        pattern_id = f"pat-{genome_id}"
    return ArchiveCandidate(
        genome_id=genome_id,
        run_id=run_id,
        generation_no=generation_no,
        dataset_epoch_id=dataset_epoch_id,
        pattern_id=pattern_id,
        family_id=family_id,
        archive_role=archive_role,  # type: ignore[arg-type]
        gate_worst_gap=gate_worst_gap,
        c_pass_depth=c_pass_depth,
        mission_signed_margin=mission_signed_margin,
        shadow_robustness_score=shadow_robustness_score,
        log_pf_clip=log_pf_clip,
        invariant_feasible=invariant_feasible,
        margin_inf=margin_inf,
        margin_inf_passes_p70=margin_inf_passes_p70,
        novelty=novelty,
        diversity_coverage=diversity_coverage,
        quality_floor_margin=quality_floor_margin,
    )


def make_member(
    genome_id: str = "m0",
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


def make_state(
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


def candidates_dict(
    cs: Iterable[ArchiveCandidate],
) -> Mapping[str, ArchiveCandidate]:
    """genome_id をキーとする dict を構築."""
    return {c.genome_id: c for c in cs}


def initial_push_state() -> PushPullState:
    return PushPullState(
        phase="push",
        consecutive_count=0,
        switch_generation=None,
        last_feasible_ratio_ema=0.0,
        forced_switch=False,
    )


# ===========================================================================
# 2.1 PR DoD 必須 4 件
# ===========================================================================


def test_push_pull_one_way_transition_does_not_revert_to_push() -> None:
    """pull に遷移後、 feasible_ratio が下がっても push に戻らない."""
    state = initial_push_state()
    # consecutive_n=2 で素早く pull に遷移させる
    state = update_push_pull_state(
        state,
        generation_no=1,
        feasible_ratio_ema=0.9,
        force_g=100,
        theta_switch=0.4,
        consecutive_n=2,
    )
    state = update_push_pull_state(
        state,
        generation_no=2,
        feasible_ratio_ema=0.9,
        force_g=100,
        theta_switch=0.4,
        consecutive_n=2,
    )
    assert state.phase == "pull"
    # ratio を下げても pull 維持
    state = update_push_pull_state(
        state,
        generation_no=3,
        feasible_ratio_ema=0.0,
        force_g=100,
        theta_switch=0.4,
        consecutive_n=2,
    )
    assert state.phase == "pull"


def test_archive_admit_preserves_dataset_epoch_id() -> None:
    """admit 後も dataset_epoch_id が保たれる."""
    state = make_state(dataset_epoch_id="epoch-A")
    cs = [make_candidate("g1", archive_role="mission_pass")]
    new_state, _ = archive_admit(
        state, candidates_dict(cs), pop_size=192, mode="normal"
    )
    assert new_state.dataset_epoch_id == "epoch-A"


def test_archive_evict_ca_uses_round_21_lex_order_with_mission_signed_margin_at_position_5() -> None:
    """CA eviction で同 archive_role / 同 c_pass_depth なら mission_signed_margin が決定的."""
    # 2 体作成、 mission_signed_margin が異なる
    m_high = make_member(
        "m_high", archive_role="mission_pass", mission_signed_margin=0.5
    )
    m_low = make_member(
        "m_low", archive_role="mission_pass", mission_signed_margin=0.1
    )
    state = make_state([m_high, m_low])
    new_state = archive_evict_ca(state, target_size=1)
    # margin 大が残る
    survivors = [m.genome_id for m in new_state.members]
    assert survivors == ["m_high"]


def test_archive_admit_score_bypass_quality_floor_excludes_high_margin_inf() -> None:
    """score_bypass で margin_inf_passes_p70=False の候補は admit されない."""
    cs = [
        make_candidate(
            "g_pass",
            archive_role="score_bypass_candidate",
            invariant_feasible=True,
            margin_inf_passes_p70=True,
        ),
        make_candidate(
            "g_fail",
            archive_role="score_bypass_candidate",
            invariant_feasible=True,
            margin_inf_passes_p70=False,
        ),
    ]
    state = make_state()
    new_state, _report = archive_admit(
        state, candidates_dict(cs), pop_size=192, mode="normal"
    )
    admitted_ids = {m.genome_id for m in new_state.members}
    assert "g_pass" in admitted_ids
    assert "g_fail" not in admitted_ids


# ===========================================================================
# 2.2 PushPullState transitions
# ===========================================================================


def test_push_pull_state_initial_phase_is_push() -> None:
    state = initial_push_state()
    assert state.phase == "push"
    assert state.switch_generation is None


def test_push_pull_state_consecutive_count_increments_on_threshold_met() -> None:
    state = initial_push_state()
    state = update_push_pull_state(
        state,
        generation_no=1,
        feasible_ratio_ema=0.5,
        force_g=100,
        theta_switch=0.4,
        consecutive_n=3,
    )
    assert state.consecutive_count == 1
    assert state.phase == "push"


def test_push_pull_state_resets_consecutive_count_on_threshold_failure() -> None:
    state = initial_push_state()
    state = update_push_pull_state(
        state,
        generation_no=1,
        feasible_ratio_ema=0.5,
        force_g=100,
        theta_switch=0.4,
        consecutive_n=3,
    )
    state = update_push_pull_state(
        state,
        generation_no=2,
        feasible_ratio_ema=0.1,
        force_g=100,
        theta_switch=0.4,
        consecutive_n=3,
    )
    assert state.consecutive_count == 0


def test_push_pull_state_transitions_to_pull_after_consecutive_n_met() -> None:
    state = initial_push_state()
    for g in (1, 2, 3):
        state = update_push_pull_state(
            state,
            generation_no=g,
            feasible_ratio_ema=0.5,
            force_g=100,
            theta_switch=0.4,
            consecutive_n=3,
        )
    assert state.phase == "pull"
    assert state.switch_generation == 3
    assert not state.forced_switch


def test_push_pull_state_forces_pull_at_force_g() -> None:
    state = initial_push_state()
    state = update_push_pull_state(
        state,
        generation_no=10,
        feasible_ratio_ema=0.0,
        force_g=10,
        theta_switch=0.4,
        consecutive_n=3,
    )
    assert state.phase == "pull"
    assert state.forced_switch is True


def test_push_pull_state_pull_phase_remains_pull_regardless_of_feasible_ratio() -> None:
    state = PushPullState(
        phase="pull",
        consecutive_count=3,
        switch_generation=5,
        last_feasible_ratio_ema=0.5,
        forced_switch=False,
    )
    state = update_push_pull_state(
        state,
        generation_no=20,
        feasible_ratio_ema=0.0,
        force_g=100,
        theta_switch=0.4,
        consecutive_n=3,
    )
    assert state.phase == "pull"


def test_update_push_pull_state_raises_on_feasible_ratio_out_of_range() -> None:
    state = initial_push_state()
    with pytest.raises(ValueError):
        update_push_pull_state(
            state,
            generation_no=1,
            feasible_ratio_ema=1.5,
            force_g=100,
            theta_switch=0.4,
        )
    with pytest.raises(ValueError):
        update_push_pull_state(
            state,
            generation_no=1,
            feasible_ratio_ema=-0.1,
            force_g=100,
            theta_switch=0.4,
        )


def test_update_push_pull_state_raises_on_negative_generation_no() -> None:
    state = initial_push_state()
    with pytest.raises(ValueError):
        update_push_pull_state(
            state,
            generation_no=-1,
            feasible_ratio_ema=0.5,
            force_g=100,
            theta_switch=0.4,
        )


# ===========================================================================
# 2.3 CA/DA capacity
# ===========================================================================


def test_compute_ca_da_capacities_pop192_push_returns_84_108() -> None:
    ca, da = compute_ca_da_capacities(192, "push")
    assert (ca, da) == (round(192 * PUSH_CA_RATIO), 192 - round(192 * PUSH_CA_RATIO))
    assert ca == 84
    assert da == 108


def test_compute_ca_da_capacities_pop192_pull_returns_120_72() -> None:
    ca, da = compute_ca_da_capacities(192, "pull")
    assert ca == 120
    assert da == 72


def test_compute_ca_da_capacities_pop256_push_returns_112_144() -> None:
    ca, da = compute_ca_da_capacities(256, "push")
    assert ca == round(256 * PUSH_CA_RATIO)
    assert ca == 112
    assert da == 144


def test_compute_ca_da_capacities_pop256_pull_returns_160_96() -> None:
    ca, da = compute_ca_da_capacities(256, "pull")
    assert ca == 160
    assert da == 96


def test_compute_ca_da_capacities_sum_equals_pop_size_via_round() -> None:
    for pop in SUPPORTED_POP_SIZES:
        for phase in ("push", "pull"):
            ca, da = compute_ca_da_capacities(pop, phase)
            assert ca + da == pop


def test_compute_ca_da_capacities_unsupported_pop_size_raises_value_error() -> None:
    with pytest.raises(ValueError):
        compute_ca_da_capacities(100, "push")


def test_compute_archive_capacities_pop192_returns_120_72_48() -> None:
    assert compute_archive_capacities(192) == (120, 72, 48)


def test_compute_archive_capacities_pop256_returns_160_96_64() -> None:
    assert compute_archive_capacities(256) == (160, 96, 64)


def test_compute_archive_capacities_unsupported_pop_size_raises_value_error() -> None:
    with pytest.raises(ValueError):
        compute_archive_capacities(100)


# ===========================================================================
# 2.4 partition_survivors_to_ca_da
# ===========================================================================


def test_partition_survivors_top_ca_cap_to_ca_rest_to_da() -> None:
    indices = list(range(192))
    ca, da = partition_survivors_to_ca_da(indices, phase="push", pop_size=192)
    assert len(ca) == 84
    assert len(da) == 108
    assert ca == tuple(range(84))
    assert da == tuple(range(84, 192))


def test_partition_survivors_respects_t065_sort_order() -> None:
    # 入力順をそのまま反映 (再 sort しない)
    indices = [10, 5, 7, 3, 1, 0, 2, 4, 6, 8, 9]
    ca, da = partition_survivors_to_ca_da(indices, phase="push", pop_size=192)
    expected = tuple(indices)
    # ca + da の連結が入力順と同じ
    assert ca + da == expected


def test_partition_survivors_eligible_below_pop_size_returns_partial() -> None:
    indices = list(range(50))  # < pop_size=192
    ca, da = partition_survivors_to_ca_da(indices, phase="pull", pop_size=192)
    # CA capacity=120 だが入力は 50 のみ → CA に 50、 DA は空
    assert ca == tuple(range(50))
    assert da == ()


def test_partition_survivors_exceeds_pop_size_raises_value_error() -> None:
    with pytest.raises(ValueError):
        partition_survivors_to_ca_da(
            list(range(193)), phase="push", pop_size=192
        )


def test_partition_survivors_no_sort_keys_argument() -> None:
    """signature 統一: sort_keys 引数を受け取らない (詳細 Round 2 [W3])."""
    import inspect

    sig = inspect.signature(partition_survivors_to_ca_da)
    assert "sort_keys" not in sig.parameters


# ===========================================================================
# 2.5 determine_archive_role
# ===========================================================================


def _make_bc_result(
    *,
    mission_pass: StagePassStatus = StagePassStatus.FAIL,
    progress_pass: StagePassStatus = StagePassStatus.FAIL,
    pareto_axis_usable: bool = False,
    b_pooled_cf: object | None = None,
) -> object:
    """determine_archive_role で必要な field のみ持つ stub.

    BCEvaluationResult の完全構築は重いので、 必要 field のみ持つ簡易 stub を返す.
    determine_archive_role は ``mission_pass`` / ``c_lite_result.progress_pass`` /
    ``pareto_axis_usable`` / ``b_pooled_cf`` のみ参照する (T064 main 実装に
    準拠、 ``progress_pass`` は :class:`StageCLiteResult` 経由).
    """

    class _CLiteStub:
        def __init__(self, status: StagePassStatus) -> None:
            self.progress_pass = status

    class _Stub:
        def __init__(self) -> None:
            self.mission_pass = mission_pass
            self.c_lite_result = _CLiteStub(progress_pass)
            self.pareto_axis_usable = pareto_axis_usable
            self.b_pooled_cf = b_pooled_cf

    return _Stub()


def test_determine_archive_role_none_returns_ineligible() -> None:
    assert determine_archive_role(None) == "ineligible"


def test_determine_archive_role_mission_pass_returns_mission_pass() -> None:
    bc = _make_bc_result(mission_pass=StagePassStatus.PASS)
    assert determine_archive_role(bc) == "mission_pass"  # type: ignore[arg-type]


def test_determine_archive_role_progress_pass_returns_progress_pass() -> None:
    bc = _make_bc_result(progress_pass=StagePassStatus.PASS)
    assert determine_archive_role(bc) == "progress_pass"  # type: ignore[arg-type]


def test_determine_archive_role_pareto_axis_usable_returns_score_bypass_candidate() -> (
    None
):
    bc = _make_bc_result(pareto_axis_usable=True, b_pooled_cf=object())
    assert determine_archive_role(bc) == "score_bypass_candidate"  # type: ignore[arg-type]


def test_determine_archive_role_b_pooled_cf_none_returns_ineligible() -> None:
    bc = _make_bc_result(pareto_axis_usable=True, b_pooled_cf=None)
    assert determine_archive_role(bc) == "ineligible"  # type: ignore[arg-type]


def test_determine_archive_role_priority_mission_over_progress() -> None:
    bc = _make_bc_result(
        mission_pass=StagePassStatus.PASS,
        progress_pass=StagePassStatus.PASS,
    )
    assert determine_archive_role(bc) == "mission_pass"  # type: ignore[arg-type]


# ===========================================================================
# 2.6 compute_inflow_targets
# ===========================================================================


def test_compute_inflow_targets_pop192_normal_returns_target_8_per_run_max_12() -> None:
    t = compute_inflow_targets(192, 0, 0, mode="normal")
    assert t.target_inflow == 8
    assert t.per_run_max == 12
    assert t.mode == "normal"


def test_compute_inflow_targets_pop256_normal_returns_target_10_per_run_max_16() -> None:
    t = compute_inflow_targets(256, 0, 0, mode="normal")
    assert t.target_inflow == 10
    assert t.per_run_max == 16


def test_compute_inflow_targets_emergency_increases_target_and_bypass_max() -> None:
    t_normal = compute_inflow_targets(192, 0, 0, mode="normal")
    t_emer = compute_inflow_targets(192, 0, 0, mode="emergency")
    assert t_emer.target_inflow == t_normal.target_inflow + 2
    # emergency clamp [4, 8]
    assert t_emer.bypass_k <= 8
    assert t_emer.bypass_k >= 4


def test_compute_inflow_targets_bypass_k_clamps_to_2_6_normal() -> None:
    # n_mission + n_progress 大で残余が小 → 2 floor
    t = compute_inflow_targets(192, 100, 100, mode="normal")
    assert t.bypass_k == 2
    # n_mission=0, n_progress=0 → target=8 → clamp 6
    t2 = compute_inflow_targets(192, 0, 0, mode="normal")
    assert t2.bypass_k == 6


def test_compute_inflow_targets_bypass_k_clamps_to_4_8_emergency() -> None:
    t = compute_inflow_targets(192, 100, 100, mode="emergency")
    assert t.bypass_k == 4
    t2 = compute_inflow_targets(192, 0, 0, mode="emergency")
    # emergency target=10 → bypass 候補 10、 clamp 8
    assert t2.bypass_k == 8


def test_compute_inflow_targets_negative_n_mission_raises_value_error() -> None:
    with pytest.raises(ValueError):
        compute_inflow_targets(192, -1, 0, mode="normal")
    with pytest.raises(ValueError):
        compute_inflow_targets(192, 0, -1, mode="normal")


# ===========================================================================
# 2.7 archive_admit (3 層流入)
# ===========================================================================


def test_archive_admit_mission_pass_admitted_unconditionally_until_per_run_max() -> None:
    cs = [
        make_candidate(
            f"m{i}",
            archive_role="mission_pass",
            mission_signed_margin=0.5 - i * 0.01,
            pattern_id=f"pat-{i}",
        )
        for i in range(20)
    ]
    state = make_state()
    new_state, report = archive_admit(
        state, candidates_dict(cs), pop_size=192, mode="normal"
    )
    # per_run_max=12 が上限
    assert report.n_admitted_mission == 12
    assert len(new_state.members) == 12
    # mission_signed_margin の大が残る
    margins = sorted(
        (m.mission_signed_margin for m in new_state.members), reverse=True
    )
    assert margins[0] >= margins[-1]


def test_archive_admit_progress_pass_sorted_by_worst_gap_ascending() -> None:
    cs = [
        make_candidate(
            f"p{i}",
            archive_role="progress_pass",
            gate_worst_gap=0.5 - i * 0.05,
            pattern_id=f"pp-{i}",
        )
        for i in range(5)
    ]
    state = make_state()
    new_state, _report = archive_admit(
        state, candidates_dict(cs), pop_size=192, mode="normal"
    )
    # gate_worst_gap 小 (= 良好) が優先
    progress_in_state = [m for m in new_state.members if m.archive_role == "progress_pass"]
    assert all(
        progress_in_state[i].gate_worst_gap <= progress_in_state[i + 1].gate_worst_gap
        for i in range(len(progress_in_state) - 1)
    )


def test_archive_admit_score_bypass_quality_floor_invariant_feasible() -> None:
    cs = [
        make_candidate(
            "g_ok",
            archive_role="score_bypass_candidate",
            invariant_feasible=True,
            margin_inf_passes_p70=True,
        ),
        make_candidate(
            "g_inf",
            archive_role="score_bypass_candidate",
            invariant_feasible=False,
            margin_inf_passes_p70=True,
        ),
    ]
    state = make_state()
    new_state, _ = archive_admit(
        state, candidates_dict(cs), pop_size=192, mode="normal"
    )
    ids = {m.genome_id for m in new_state.members}
    assert "g_ok" in ids
    assert "g_inf" not in ids


def test_archive_admit_score_bypass_quality_floor_margin_inf_p70() -> None:
    cs = [
        make_candidate(
            "g_p70",
            archive_role="score_bypass_candidate",
            invariant_feasible=True,
            margin_inf_passes_p70=True,
        ),
        make_candidate(
            "g_no_p70",
            archive_role="score_bypass_candidate",
            invariant_feasible=True,
            margin_inf_passes_p70=False,
        ),
    ]
    state = make_state()
    new_state, _ = archive_admit(
        state, candidates_dict(cs), pop_size=192, mode="normal"
    )
    ids = {m.genome_id for m in new_state.members}
    assert "g_p70" in ids
    assert "g_no_p70" not in ids


def test_archive_admit_per_run_max_trims_excess_by_role_priority() -> None:
    # 13 mission を投入 → per_run_max=12 で 1 体 trim、 mission_signed_margin 小が落ちる
    cs = [
        make_candidate(
            f"m{i:02d}",
            archive_role="mission_pass",
            mission_signed_margin=float(i) * 0.01,
            pattern_id=f"pat-{i:02d}",
        )
        for i in range(13)
    ]
    state = make_state()
    new_state, _report = archive_admit(
        state, candidates_dict(cs), pop_size=192, mode="normal"
    )
    assert len(new_state.members) == 12
    # margin 最小の m00 が落ちる
    ids = {m.genome_id for m in new_state.members}
    assert "m00" not in ids


def test_archive_admit_pattern_max_share_25_percent() -> None:
    # archive_total=120, pattern_cap=120*0.25=30
    # 同 pattern_id で 35 体 mission_pass を投入 → per_run_max=12 で trim、
    # その後 pattern cap も適用. 同 pattern が 12 全部入るが pattern_count<30 で全通過.
    # pattern cap が効くシナリオ: 既存 archive に 30 体同 pattern がある場合.
    existing = tuple(
        make_member(
            f"e{i:02d}",
            run_id="run-old",
            pattern_id="pat-X",
            archive_role="progress_pass",
        )
        for i in range(30)
    )
    state = make_state(existing, run_history=("run-old",))
    cs = [
        make_candidate(
            f"new{i:02d}",
            archive_role="mission_pass",
            pattern_id="pat-X",
            mission_signed_margin=1.0 - i * 0.01,
        )
        for i in range(5)
    ]
    _new_state, report = archive_admit(
        state, candidates_dict(cs), pop_size=192, mode="normal"
    )
    # 既に 30 = pattern_cap、 同 pattern 新規は 0 admit
    assert report.n_admitted_mission == 0
    assert report.hard_constraint_drops == 5


def test_archive_admit_dataset_epoch_id_propagated() -> None:
    state = make_state(dataset_epoch_id="epoch-Z", run_history=())
    cs = [make_candidate("g1", dataset_epoch_id="epoch-Z")]
    new_state, _ = archive_admit(
        state, candidates_dict(cs), pop_size=192, mode="normal"
    )
    assert new_state.dataset_epoch_id == "epoch-Z"


def test_archive_admit_upsert_existing_genome_id_replaces_member() -> None:
    """同 genome_id 再 admission で member は上書き (詳細 Round 3 [C1])."""
    existing_member = make_member(
        "g_dup",
        archive_role="progress_pass",
        mission_signed_margin=0.0,
        pattern_id="pat-old",
    )
    state = make_state([existing_member])
    cs = [
        make_candidate(
            "g_dup",
            archive_role="mission_pass",
            mission_signed_margin=0.5,
            pattern_id="pat-old",
        )
    ]
    new_state, _ = archive_admit(
        state, candidates_dict(cs), pop_size=192, mode="normal"
    )
    members_with_gdup = [m for m in new_state.members if m.genome_id == "g_dup"]
    assert len(members_with_gdup) == 1
    assert members_with_gdup[0].archive_role == "mission_pass"
    assert members_with_gdup[0].mission_signed_margin == 0.5


def test_archive_admit_evicted_genome_ids_includes_admit_then_immediate_evict() -> None:
    """admit 後 即時 eviction で落ちた genome は evicted_genome_ids に含まれる (詳細 Round 3 [W1])."""
    # CA capacity=72 を超えるよう 80 体 mission を投入したいが per_run_max=12.
    # 既存 CA を 71 体置き、 13 体 mission を投入、 12 admit、 11 が新規残留 + 1 evict.
    existing = tuple(
        make_member(
            f"old{i:03d}",
            archive_role="mission_pass",
            mission_signed_margin=1.0,
            pattern_id=f"po-{i:03d}",
            run_id="run-old",
        )
        for i in range(71)
    )
    state = make_state(existing, run_history=("run-old",))
    cs = [
        make_candidate(
            f"new{i:02d}",
            archive_role="mission_pass",
            mission_signed_margin=2.0 - i * 0.01,  # 大きいので新規優先
            pattern_id=f"pn-{i:02d}",
        )
        for i in range(13)
    ]
    _new_state, report = archive_admit(
        state, candidates_dict(cs), pop_size=192, mode="normal"
    )
    # 71 + 12 = 83 → CA cap 72 → 11 体 evict、 evicted_genome_ids 反映
    assert len(report.evicted_genome_ids) >= 1


def test_archive_admit_admission_report_distinguishes_selected_and_admitted_counts() -> (
    None
):
    """selected と admitted の counts 分離."""
    cs = [
        make_candidate(f"m{i:02d}", archive_role="mission_pass", pattern_id=f"p-{i:02d}")
        for i in range(15)
    ]
    state = make_state()
    _new_state, report = archive_admit(
        state, candidates_dict(cs), pop_size=192, mode="normal"
    )
    assert report.n_selected_mission == 15
    assert report.n_admitted_mission == 12  # per_run_max=12
    assert report.hard_constraint_drops == 3


def test_archive_admit_recency_floor_unmet_when_below_12_in_last_3_runs() -> None:
    """直近 3 Run に 12 未満なら recency_floor_unmet=True."""
    # 5 体だけの archive、 全部新 run_id 由来 → recency_count=5 < 12 で True
    state = make_state(
        members=tuple(
            make_member(f"m{i}", run_id="run-1", pattern_id=f"p-{i}")
            for i in range(5)
        ),
        run_history=("run-1",),
    )
    # 投入候補なし
    _new_state, report = archive_admit(state, {}, pop_size=192, mode="normal")
    assert report.recency_floor_unmet is True


# ===========================================================================
# 2.8 archive_evict_ca / archive_evict_da
# ===========================================================================


def test_archive_evict_ca_keeps_mission_pass_at_top() -> None:
    members = [
        make_member("m_mission", archive_role="mission_pass"),
        make_member("p_progress", archive_role="progress_pass"),
        make_member("b_bypass", archive_role="score_bypass"),
    ]
    state = make_state(members)
    new_state = archive_evict_ca(state, target_size=1)
    assert new_state.members[0].genome_id == "m_mission"


def test_archive_evict_ca_uses_mission_signed_margin_at_position_5() -> None:
    # mission_pass 同士で c_pass_depth が同じ場合、 mission_signed_margin で決まる
    a = make_member(
        "a", archive_role="mission_pass", c_pass_depth=1.0, mission_signed_margin=0.1
    )
    b = make_member(
        "b", archive_role="mission_pass", c_pass_depth=1.0, mission_signed_margin=0.2
    )
    state = make_state([a, b])
    new_state = archive_evict_ca(state, target_size=1)
    assert new_state.members[0].genome_id == "b"


def test_archive_evict_ca_uses_shadow_robustness_at_position_6() -> None:
    a = make_member(
        "a",
        archive_role="mission_pass",
        c_pass_depth=1.0,
        mission_signed_margin=0.0,
        shadow_robustness_score=0.5,
    )
    b = make_member(
        "b",
        archive_role="mission_pass",
        c_pass_depth=1.0,
        mission_signed_margin=0.0,
        shadow_robustness_score=0.9,
    )
    state = make_state([a, b])
    new_state = archive_evict_ca(state, target_size=1)
    assert new_state.members[0].genome_id == "b"


def test_archive_evict_ca_log_pf_clip_is_position_8_not_final() -> None:
    """log_pf_clip は位置 8、 末尾は genome_id."""
    # 全 lex 位置 1-7 同一、 log_pf_clip 異なる、 genome_id も異なる → log_pf_clip 大が残る
    a = make_member(
        "a_logpf_low",
        archive_role="mission_pass",
        c_pass_depth=1.0,
        mission_signed_margin=0.0,
        shadow_robustness_score=0.5,
        log_pf_clip=0.1,
        run_id="run-1",
    )
    b = make_member(
        "b_logpf_high",
        archive_role="mission_pass",
        c_pass_depth=1.0,
        mission_signed_margin=0.0,
        shadow_robustness_score=0.5,
        log_pf_clip=0.9,
        run_id="run-1",
    )
    state = make_state([a, b], run_history=("run-1",))
    new_state = archive_evict_ca(state, target_size=1)
    assert new_state.members[0].genome_id == "b_logpf_high"


def test_archive_evict_ca_genome_id_is_final_tiebreak() -> None:
    """全 lex key 同一なら genome_id 昇順 (= 小が残る)."""
    a = make_member("a_id", archive_role="mission_pass", run_id="run-1")
    b = make_member("b_id", archive_role="mission_pass", run_id="run-1")
    state = make_state([a, b], run_history=("run-1",))
    new_state = archive_evict_ca(state, target_size=1)
    assert new_state.members[0].genome_id == "a_id"


def test_archive_evict_da_keeps_high_novelty_at_top() -> None:
    a = make_member("a", archive_target="DA", novelty=0.1)
    b = make_member("b", archive_target="DA", novelty=0.9)
    state = make_state([a, b])
    new_state = archive_evict_da(state, target_size=1)
    assert new_state.members[0].genome_id == "b"


def test_archive_evict_da_uses_diversity_coverage_at_position_2() -> None:
    a = make_member(
        "a", archive_target="DA", novelty=0.5, diversity_coverage=0.1
    )
    b = make_member(
        "b", archive_target="DA", novelty=0.5, diversity_coverage=0.9
    )
    state = make_state([a, b])
    new_state = archive_evict_da(state, target_size=1)
    assert new_state.members[0].genome_id == "b"


def test_archive_evict_da_genome_id_is_final_tiebreak() -> None:
    a = make_member("a_id", archive_target="DA", novelty=0.5, run_id="run-1")
    b = make_member("b_id", archive_target="DA", novelty=0.5, run_id="run-1")
    state = make_state([a, b], run_history=("run-1",))
    new_state = archive_evict_da(state, target_size=1)
    assert new_state.members[0].genome_id == "a_id"


def test_archive_evict_capacity_match_after_eviction() -> None:
    members = [
        make_member(f"m{i:02d}", archive_role="mission_pass") for i in range(80)
    ]
    state = make_state(members)
    new_state = archive_evict_ca(state, target_size=72)
    ca_count = sum(1 for m in new_state.members if m.archive_target == "CA")
    assert ca_count == 72


def test_archive_evict_recency_floor_reports_unmet_best_effort_when_below_12() -> None:
    # 強制保持しない、 単に warning. ここでは _check_recency_floor_unmet 直接 test.
    from src.alpha_factory.cpps_archive import _check_recency_floor_unmet

    state = make_state(
        members=tuple(
            make_member(f"m{i}", run_id="run-old") for i in range(5)
        ),
        run_history=("run-new", "run-mid"),
    )
    # 最近 3 Run に該当する members は 0 (= run-old 由来 5 体のみ)
    assert _check_recency_floor_unmet(state) is True


def test_archive_evict_uses_archive_role_derived_keys_not_stored_bool() -> None:
    """eviction key は archive_role から導出 (= bool 保存値ではない、 詳細 Round 2 [C2])."""
    m = make_member("a", archive_role="score_bypass")
    assert m.not_score_bypass is False
    m2 = make_member("b", archive_role="mission_pass")
    assert m2.not_score_bypass is True


# ===========================================================================
# 2.9 ArchiveState immutability
# ===========================================================================


def test_archive_state_members_is_tuple() -> None:
    state = make_state()
    assert isinstance(state.members, tuple)


def test_archive_state_run_history_is_tuple() -> None:
    state = make_state(run_history=("a", "b"))
    assert isinstance(state.run_history, tuple)


def test_archive_state_replace_returns_new_instance() -> None:
    from dataclasses import replace as dc_replace

    state = make_state()
    state2 = dc_replace(state, dataset_epoch_id="epoch-2")
    assert state is not state2
    assert state2.dataset_epoch_id == "epoch-2"
    assert state.dataset_epoch_id == "epoch-1"  # 元は変更されない


def test_archive_member_not_score_bypass_is_property_derived() -> None:
    m1 = make_member("g1", archive_role="score_bypass")
    m2 = make_member("g2", archive_role="mission_pass")
    m3 = make_member("g3", archive_role="progress_pass")
    assert m1.not_score_bypass is False
    assert m2.not_score_bypass is True
    assert m3.not_score_bypass is True


# ===========================================================================
# 2.10 update_archive_per_run (top-level) + 契約検証群
# ===========================================================================


def test_update_archive_per_run_normal_mode_admits_and_evicts() -> None:
    state = make_state(dataset_epoch_id="epoch-1", run_history=())
    cs = [
        make_candidate("g1", archive_role="mission_pass", run_id="run-A"),
        make_candidate("g2", archive_role="mission_pass", run_id="run-A"),
    ]
    new_state, report = update_archive_per_run(
        state,
        candidates_dict(cs),
        pop_size=192,
        mode="normal",
        new_dataset_epoch_id="epoch-1",
        new_run_id="run-A",
    )
    assert len(new_state.members) == 2
    assert report.n_admitted_mission == 2


def test_update_archive_per_run_emergency_mode_increases_bypass() -> None:
    state = make_state(dataset_epoch_id="epoch-1", run_history=())
    cs = [
        make_candidate(
            f"g{i:02d}",
            archive_role="score_bypass_candidate",
            invariant_feasible=True,
            margin_inf_passes_p70=True,
            run_id="run-A",
        )
        for i in range(10)
    ]
    _new_state, report = update_archive_per_run(
        state,
        candidates_dict(cs),
        pop_size=192,
        mode="emergency",
        new_dataset_epoch_id="epoch-1",
        new_run_id="run-A",
    )
    assert report.mode == "emergency"
    # emergency bypass clamp [4, 8]
    assert report.n_admitted_bypass <= 8
    assert report.n_admitted_bypass >= 4


def test_update_archive_per_run_dataset_epoch_id_changes_resets_archive() -> None:
    old_member = make_member("old_g", run_id="run-old")
    state = make_state(
        [old_member], dataset_epoch_id="epoch-1", run_history=("run-old",)
    )
    cs = [make_candidate("new_g", run_id="run-A", dataset_epoch_id="epoch-2")]
    new_state, report = update_archive_per_run(
        state,
        candidates_dict(cs),
        pop_size=192,
        mode="normal",
        new_dataset_epoch_id="epoch-2",
        new_run_id="run-A",
    )
    # 旧 member は消える、 新 member のみ
    ids = {m.genome_id for m in new_state.members}
    assert "old_g" not in ids
    assert "new_g" in ids
    assert report.dataset_epoch_reset is True
    assert new_state.dataset_epoch_id == "epoch-2"


def test_update_archive_per_run_returns_admission_report_with_counts() -> None:
    state = make_state(dataset_epoch_id="epoch-1", run_history=())
    cs = [
        make_candidate(
            "g1", archive_role="mission_pass", run_id="run-A", dataset_epoch_id="epoch-1"
        ),
        make_candidate(
            "g2", archive_role="progress_pass", run_id="run-A", dataset_epoch_id="epoch-1"
        ),
    ]
    _new_state, report = update_archive_per_run(
        state,
        candidates_dict(cs),
        pop_size=192,
        mode="normal",
        new_dataset_epoch_id="epoch-1",
        new_run_id="run-A",
    )
    assert report.n_selected_mission == 1
    assert report.n_selected_progress == 1


def test_update_archive_per_run_run_history_updated_before_eviction() -> None:
    """run_history は admission/eviction より先に新 run_id が反映される (詳細 Round 2 [C1])."""
    state = make_state(dataset_epoch_id="epoch-1", run_history=("run-old",))
    cs = [
        make_candidate(
            "g_new", archive_role="mission_pass", run_id="run-new",
            dataset_epoch_id="epoch-1",
        )
    ]
    new_state, _ = update_archive_per_run(
        state,
        candidates_dict(cs),
        pop_size=192,
        mode="normal",
        new_dataset_epoch_id="epoch-1",
        new_run_id="run-new",
    )
    # run-new が先頭、 run-old がその後
    assert new_state.run_history[0] == "run-new"
    assert "run-old" in new_state.run_history


def test_update_archive_per_run_candidate_epoch_mismatch_raises_value_error() -> None:
    state = make_state(dataset_epoch_id="epoch-1", run_history=())
    cs = [
        make_candidate(
            "g1", run_id="run-A", dataset_epoch_id="epoch-WRONG",
            archive_role="mission_pass",
        )
    ]
    with pytest.raises(ValueError, match="dataset_epoch_id"):
        update_archive_per_run(
            state,
            candidates_dict(cs),
            pop_size=192,
            mode="normal",
            new_dataset_epoch_id="epoch-1",
            new_run_id="run-A",
        )


def test_update_archive_per_run_run_history_max_length_10() -> None:
    history = tuple(f"run-{i}" for i in range(15))
    state = make_state(dataset_epoch_id="epoch-1", run_history=history)
    # ただし state.run_history[0] = "run-0" で再投入禁止に当たらない、 新 run_id を渡す
    cs = [
        make_candidate(
            "g_new", run_id="run-new", dataset_epoch_id="epoch-1",
            archive_role="mission_pass",
        )
    ]
    # state.run_history が既に 15 だが、 update 前は不変、 update 後 maxlen=10 で truncate
    new_state, _ = update_archive_per_run(
        state,
        candidates_dict(cs),
        pop_size=192,
        mode="normal",
        new_dataset_epoch_id="epoch-1",
        new_run_id="run-new",
    )
    assert len(new_state.run_history) == RUN_HISTORY_MAXLEN
    assert new_state.run_history[0] == "run-new"


def test_update_archive_per_run_candidate_run_id_mismatch_raises_value_error() -> None:
    state = make_state(dataset_epoch_id="epoch-1", run_history=())
    cs = [
        make_candidate(
            "g1",
            run_id="run-WRONG",
            dataset_epoch_id="epoch-1",
            archive_role="mission_pass",
        )
    ]
    with pytest.raises(ValueError, match="run_id"):
        update_archive_per_run(
            state,
            candidates_dict(cs),
            pop_size=192,
            mode="normal",
            new_dataset_epoch_id="epoch-1",
            new_run_id="run-A",
        )


def test_update_archive_per_run_same_run_id_re_submission_raises_value_error() -> None:
    state = make_state(dataset_epoch_id="epoch-1", run_history=("run-A",))
    cs = [
        make_candidate(
            "g1",
            run_id="run-A",
            dataset_epoch_id="epoch-1",
            archive_role="mission_pass",
        )
    ]
    with pytest.raises(ValueError, match="re-submission"):
        update_archive_per_run(
            state,
            candidates_dict(cs),
            pop_size=192,
            mode="normal",
            new_dataset_epoch_id="epoch-1",
            new_run_id="run-A",
        )


def test_archive_admit_candidates_key_genome_id_mismatch_raises_value_error() -> None:
    state = make_state()
    c = make_candidate("g_real")
    candidates: dict[str, ArchiveCandidate] = {"different_key": c}
    with pytest.raises(ValueError, match="genome_id"):
        archive_admit(state, candidates, pop_size=192, mode="normal")


def test_bc_evaluation_result_has_c_pass_depth_field() -> None:
    """T064 follow-up Phase 0 契約: BCEvaluationResult.c_pass_depth が存在.

    詳細 Round 1 [C3] / Round 2 [W1] 反映: ``__dataclass_fields__`` ベースで
    field 存在を検証 (mock 等で hasattr が false-positive にならないよう defensive).
    型は float 必須.

    Codex impl-review pr1 Round 1 Suggestion (H2) 反映: 詳細設計文言と厳密一致
    させるため ``__dataclass_fields__`` 直接参照と ``fields()`` 経由の両方を
    検証する.
    """
    assert is_dataclass(BCEvaluationResult)
    # 1. __dataclass_fields__ 直接参照 (詳細 Round 1 [C3] 文言厳密).
    assert "c_pass_depth" in BCEvaluationResult.__dataclass_fields__
    # 2. dataclass.fields() 経由 (機能等価、 二重防御).
    field_names = {f.name for f in fields(BCEvaluationResult)}
    assert "c_pass_depth" in field_names

    # 型注釈も検証 (typing.get_type_hints は relative import 解決失敗時に
    # 例外になり得るので、 dataclass.fields 経由で確認).
    cpd_field = next(f for f in fields(BCEvaluationResult) if f.name == "c_pass_depth")
    # type は文字列 ("float") か実型 (float). 文字列形式と type 形式の両方を許容.
    type_repr = repr(cpd_field.type)
    assert "float" in type_repr.lower()


# ===========================================================================
# 2.11 Determinism
# ===========================================================================


def test_archive_admit_deterministic_same_input_same_output() -> None:
    state = make_state()
    cs = [
        make_candidate(f"m{i:02d}", archive_role="mission_pass") for i in range(5)
    ]
    new1, _ = archive_admit(
        state, candidates_dict(cs), pop_size=192, mode="normal"
    )
    new2, _ = archive_admit(
        state, candidates_dict(cs), pop_size=192, mode="normal"
    )
    assert [m.genome_id for m in new1.members] == [m.genome_id for m in new2.members]


def test_archive_evict_lex_order_deterministic_with_ties() -> None:
    members = [
        make_member(f"m{i:02d}", archive_role="mission_pass", run_id="run-1")
        for i in range(5)
    ]
    state = make_state(members, run_history=("run-1",))
    s1 = archive_evict_ca(state, target_size=2)
    s2 = archive_evict_ca(state, target_size=2)
    assert [m.genome_id for m in s1.members] == [m.genome_id for m in s2.members]


def test_partition_survivors_deterministic() -> None:
    indices = list(range(50))
    a = partition_survivors_to_ca_da(indices, phase="push", pop_size=192)
    b = partition_survivors_to_ca_da(indices, phase="push", pop_size=192)
    assert a == b


def test_archive_admit_genome_id_ordering_independent_of_dict_iteration_order() -> None:
    state = make_state()
    cs1 = [
        make_candidate("m_b", archive_role="mission_pass", mission_signed_margin=0.5),
        make_candidate("m_a", archive_role="mission_pass", mission_signed_margin=0.5),
    ]
    cs2 = list(reversed(cs1))
    s1, _ = archive_admit(
        state, candidates_dict(cs1), pop_size=192, mode="normal"
    )
    s2, _ = archive_admit(
        state, candidates_dict(cs2), pop_size=192, mode="normal"
    )
    ids1 = sorted(m.genome_id for m in s1.members)
    ids2 = sorted(m.genome_id for m in s2.members)
    assert ids1 == ids2


# ===========================================================================
# 2.12 Edge cases
# ===========================================================================


def test_archive_admit_no_candidates_returns_empty_admission_report() -> None:
    state = make_state()
    _new_state, report = archive_admit(state, {}, pop_size=192, mode="normal")
    assert report.admitted_genome_ids == ()
    assert report.n_admitted_mission == 0
    assert report.n_admitted_progress == 0
    assert report.n_admitted_bypass == 0


def test_archive_admit_only_score_bypass_candidates_admits_bypass_k_at_most() -> None:
    cs = [
        make_candidate(
            f"b{i:02d}",
            archive_role="score_bypass_candidate",
            invariant_feasible=True,
            margin_inf_passes_p70=True,
            pattern_id=f"pb-{i:02d}",
        )
        for i in range(20)
    ]
    state = make_state()
    _new_state, report = archive_admit(
        state, candidates_dict(cs), pop_size=192, mode="normal"
    )
    # normal bypass clamp [2, 6] / target=8 → 8 (bypass_k = max(2, min(6, 8-0-0))) = 6
    assert report.n_admitted_bypass <= 6


def test_archive_evict_capacity_zero_returns_empty_archive() -> None:
    members = [
        make_member(f"m{i:02d}", archive_role="mission_pass") for i in range(5)
    ]
    state = make_state(members)
    new_state = archive_evict_ca(state, target_size=0)
    assert all(m.archive_target != "CA" for m in new_state.members)


def test_partition_survivors_pull_phase_uses_120_72_for_pop192() -> None:
    indices = list(range(192))
    ca, da = partition_survivors_to_ca_da(indices, phase="pull", pop_size=192)
    assert len(ca) == 120
    assert len(da) == 72


def test_archive_evict_ca_when_below_target_size_no_change() -> None:
    members = [
        make_member(f"m{i:02d}", archive_role="mission_pass") for i in range(5)
    ]
    state = make_state(members)
    new_state = archive_evict_ca(state, target_size=10)
    assert new_state == state


def test_archive_evict_da_target_size_negative_raises_value_error() -> None:
    state = make_state()
    with pytest.raises(ValueError):
        archive_evict_da(state, target_size=-1)
    with pytest.raises(ValueError):
        archive_evict_ca(state, target_size=-1)


# ===========================================================================
# 2.13 schema v2 / Round 21 整合性
# ===========================================================================


def test_archive_member_archive_role_matches_schema_v2_enum() -> None:
    """archive_role の取り得る値は 3 種類 (mission_pass / progress_pass / score_bypass)."""
    for role in ("mission_pass", "progress_pass", "score_bypass"):
        m = make_member("g", archive_role=role)
        assert m.archive_role == role


def test_archive_candidate_dataset_epoch_id_required() -> None:
    """ArchiveCandidate は dataset_epoch_id field を持つ."""
    f_names = {f.name for f in fields(ArchiveCandidate)}
    assert "dataset_epoch_id" in f_names


def test_archive_evict_ca_position_5_field_name_is_mission_signed_margin_not_mission_margin() -> (
    None
):
    """CA lex position 5 は mission_signed_margin (mission_margin ではない、 Round 21 改訂後)."""
    # ArchiveMember field name 検証
    f_names = {f.name for f in fields(ArchiveMember)}
    assert "mission_signed_margin" in f_names
    assert "mission_margin" not in f_names


def test_archive_evict_ca_lex_has_9_segments_with_genome_id_last() -> None:
    """CA lex key は 9 段、 末尾は genome_id."""
    from src.alpha_factory.cpps_archive import _ca_eviction_sort_key

    m = make_member("g_test", archive_role="mission_pass", run_id="run-1")
    key = _ca_eviction_sort_key(m, ("run-1",))
    assert len(key) == 9
    assert key[-1] == "g_test"


def test_archive_evict_da_lex_has_8_segments_with_genome_id_last() -> None:
    """DA lex key は 8 段、 末尾は genome_id."""
    from src.alpha_factory.cpps_archive import _da_eviction_sort_key

    m = make_member("g_test", archive_target="DA", run_id="run-1")
    key = _da_eviction_sort_key(m, ("run-1",))
    assert len(key) == 8
    assert key[-1] == "g_test"


# ===========================================================================
# Constants sanity
# ===========================================================================


def test_constants_match_synthesis_design() -> None:
    assert PUSH_CA_RATIO == 84 / 192
    assert PULL_CA_RATIO == 120 / 192
    assert PATTERN_MAX_SHARE == 0.25
    assert RECENCY_FLOOR_COUNT == 12
    assert RECENCY_FLOOR_LAST_N_RUNS == 3
    assert RUN_HISTORY_MAXLEN == 10
    assert SUPPORTED_POP_SIZES == (192, 256)
    assert ARCHIVE_ROLE_PRIORITY == {
        "mission_pass": 0,
        "progress_pass": 1,
        "score_bypass": 2,
    }
