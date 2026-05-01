"""T074 graduation lane scaffold (evaluate_graduation_trigger + 6 batch pair
frozenset + GraduationEpochSummary + Phase 4 NotImplementedError) tests.

詳細設計 § 5 + DoD § 8.

命名規約 (詳細設計 § 5.0): Fxxx_<behavior> 形式で pytest 関数名と 1:1 対応.
"""

from __future__ import annotations

import ast
from typing import Any, get_args

import pytest

from src.alpha_factory.graduation import (
    GRADUATION_AGGREGATION_CALC_VERSION,
    GRADUATION_BATCH_PAIRS,
    GRADUATION_REPORT_SCHEMA_VERSION,
    GRADUATION_TRIGGER_CALC_VERSION,
    GRADUATION_TRIGGER_MIN_EPOCHS,
    GRADUATION_TRIGGER_MIN_GRADUATES,
    LANE_PARALLELISM,
    GraduationArchiveSummary,
    GraduationEpochSummary,
    GraduationTriggerEvaluation,
    GraduationTriggerStatus,
    MultiPairAggregationKind,
    MultiPairAggregationSketch,
    MultiPairAggregationStatus,
    compute_multi_pair_aggregation_sketch,
    evaluate_graduation_trigger,
)
from src.alpha_factory.stage_bc_evaluator import (
    STAGE_C_ANCHOR_PAIR,
    STAGE_C_SHADOW_PAIR_LIST,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _epoch_summary(
    epoch_id: str,
    *,
    observed: tuple[str, ...] | None = None,
    mission_pass: tuple[str, ...] = (),
) -> GraduationEpochSummary:
    if observed is None:
        observed = (f"{epoch_id}_run_a",)
    return GraduationEpochSummary(
        dataset_epoch_id=epoch_id,
        observed_run_ids=frozenset(observed),
        mission_pass_run_ids=frozenset(mission_pass),
    )


def _archive_summary(
    *,
    n_graduates: int = 24,
    distinct_epochs: tuple[str, ...] = ("e3", "e2", "e1"),
    recent_epochs: tuple[GraduationEpochSummary, ...] | None = None,
    archive_active: str | None = "e3",
) -> GraduationArchiveSummary:
    if recent_epochs is None:
        # 新しい順 [0]=active
        recent_epochs = (
            _epoch_summary("e3", mission_pass=("e3_run_a",)),
            _epoch_summary("e2", mission_pass=("e2_run_a",)),
            _epoch_summary("e1", mission_pass=("e1_run_a",)),
        )
    return GraduationArchiveSummary(
        n_graduates=n_graduates,
        distinct_dataset_epoch_ids=frozenset(distinct_epochs),
        recent_epoch_summaries=recent_epochs,
        archive_epoch_id_active=archive_active,
    )


# ---------------------------------------------------------------------------
# F1-F3: 定数 / Literal tests
# ---------------------------------------------------------------------------


def test_graduation_constants_match_ssot() -> None:
    """F1: 定数値が SSOT 一致 (= 24 / 3 / 6 pair frozenset / LANE_PARALLELISM=1
    / version 文字列)."""
    assert GRADUATION_TRIGGER_MIN_GRADUATES == 24
    assert GRADUATION_TRIGGER_MIN_EPOCHS == 3
    assert LANE_PARALLELISM == 1
    assert GRADUATION_REPORT_SCHEMA_VERSION == "1.0.0"
    assert GRADUATION_TRIGGER_CALC_VERSION == "v1"
    assert GRADUATION_AGGREGATION_CALC_VERSION == "scaffold-v1"
    assert isinstance(GRADUATION_BATCH_PAIRS, frozenset)
    assert len(GRADUATION_BATCH_PAIRS) == 6


def test_graduation_status_literal_values() -> None:
    """F2: GraduationTriggerStatus 4 値 / MultiPairAggregationStatus 1 値 /
    MultiPairAggregationKind 2 値."""
    assert set(get_args(GraduationTriggerStatus)) == {
        "ready",
        "insufficient_graduates",
        "insufficient_epochs",
        "no_recent_mission_pass",
    }
    assert set(get_args(MultiPairAggregationStatus)) == {"not_implemented"}
    assert set(get_args(MultiPairAggregationKind)) == {"worst_pair", "mean"}


def test_graduation_batch_pairs_is_frozenset() -> None:
    """F3: GRADUATION_BATCH_PAIRS が frozenset、 順序非依存等価."""
    assert isinstance(GRADUATION_BATCH_PAIRS, frozenset)
    # 順序非依存等価 (= frozenset 性質)
    assert frozenset(
        ("USD_ZAR", "USD_CAD", "AUD_JPY", "EUR_USD", "USD_JPY", "EUR_JPY")
    ) == GRADUATION_BATCH_PAIRS
    # immutable
    with pytest.raises(AttributeError):
        GRADUATION_BATCH_PAIRS.add("XXX")  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# F4-F8: GraduationEpochSummary tests (Round 3 [W1] issubset)
# ---------------------------------------------------------------------------


def test_epoch_summary_observed_non_empty() -> None:
    """F4: observed_run_ids=frozenset() → ValueError."""
    with pytest.raises(ValueError, match="observed_run_ids must be non-empty"):
        GraduationEpochSummary(
            dataset_epoch_id="e1",
            observed_run_ids=frozenset(),
            mission_pass_run_ids=frozenset(),
        )


def test_epoch_summary_dataset_epoch_id_non_empty() -> None:
    """F5: dataset_epoch_id="" → ValueError."""
    with pytest.raises(ValueError, match="dataset_epoch_id must be non-empty"):
        GraduationEpochSummary(
            dataset_epoch_id="",
            observed_run_ids=frozenset({"r1"}),
            mission_pass_run_ids=frozenset(),
        )


def test_epoch_summary_mission_pass_must_be_subset() -> None:
    """F6: mission_pass_run_ids ⊄ observed_run_ids → ValueError."""
    with pytest.raises(ValueError, match="must be subset of observed_run_ids"):
        GraduationEpochSummary(
            dataset_epoch_id="e1",
            observed_run_ids=frozenset({"r1"}),
            mission_pass_run_ids=frozenset({"r1", "r2"}),  # r2 not in observed
        )


def test_epoch_summary_mission_pass_equal_observed_allowed() -> None:
    """F6b (Round 3 [W1] inclusive subset): mission_pass == observed → 正常."""
    s = GraduationEpochSummary(
        dataset_epoch_id="e1",
        observed_run_ids=frozenset({"r1", "r2"}),
        mission_pass_run_ids=frozenset({"r1", "r2"}),
    )
    assert s.has_mission_pass is True


def test_epoch_summary_has_mission_pass_property() -> None:
    """F7: mission_pass_run_ids non-empty → has_mission_pass=True、 空 → False."""
    s_empty = GraduationEpochSummary(
        dataset_epoch_id="e1",
        observed_run_ids=frozenset({"r1"}),
        mission_pass_run_ids=frozenset(),
    )
    assert s_empty.has_mission_pass is False
    s_pass = GraduationEpochSummary(
        dataset_epoch_id="e1",
        observed_run_ids=frozenset({"r1"}),
        mission_pass_run_ids=frozenset({"r1"}),
    )
    assert s_pass.has_mission_pass is True


def test_epoch_summary_frozen_eq_hash() -> None:
    """F8: 同 instance (= 同 epoch_id / observed / mission_pass) で eq/hash 等価."""
    a = GraduationEpochSummary(
        dataset_epoch_id="e1",
        observed_run_ids=frozenset({"r1"}),
        mission_pass_run_ids=frozenset({"r1"}),
    )
    b = GraduationEpochSummary(
        dataset_epoch_id="e1",
        observed_run_ids=frozenset({"r1"}),
        mission_pass_run_ids=frozenset({"r1"}),
    )
    assert a == b
    assert hash(a) == hash(b)
    # frozen check
    with pytest.raises((AttributeError, Exception)):
        a.dataset_epoch_id = "e2"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# F9-F14: GraduationArchiveSummary tests
# ---------------------------------------------------------------------------


def test_archive_summary_n_graduates_non_negative() -> None:
    """F9: n_graduates=-1 → ValueError."""
    with pytest.raises(ValueError, match="n_graduates >= 0 required"):
        GraduationArchiveSummary(
            n_graduates=-1,
            distinct_dataset_epoch_ids=frozenset(),
            recent_epoch_summaries=tuple(),
            archive_epoch_id_active=None,
        )


def test_archive_summary_recent_summaries_unique_epoch() -> None:
    """F10: recent_epoch_summaries で同 dataset_epoch_id 重複 → ValueError."""
    s1 = _epoch_summary("e1")
    s2 = _epoch_summary("e1")  # 同 epoch_id
    with pytest.raises(ValueError, match="duplicate dataset_epoch_id"):
        GraduationArchiveSummary(
            n_graduates=0,
            distinct_dataset_epoch_ids=frozenset({"e1"}),
            recent_epoch_summaries=(s1, s2),
            archive_epoch_id_active="e1",
        )


def test_archive_summary_recent_in_distinct() -> None:
    """F11: recent[i].dataset_epoch_id ∉ distinct_dataset_epoch_ids → ValueError."""
    s1 = _epoch_summary("e_unknown")
    with pytest.raises(ValueError, match="not in"):
        GraduationArchiveSummary(
            n_graduates=0,
            distinct_dataset_epoch_ids=frozenset({"e1"}),
            recent_epoch_summaries=(s1,),
            archive_epoch_id_active="e1",
        )


def test_archive_summary_active_none_empty() -> None:
    """F12: archive_epoch_id_active=None / distinct=空 / recent=空 → 正常."""
    s = GraduationArchiveSummary(
        n_graduates=0,
        distinct_dataset_epoch_ids=frozenset(),
        recent_epoch_summaries=tuple(),
        archive_epoch_id_active=None,
    )
    assert s.archive_epoch_id_active is None
    assert s.n_graduates == 0


def test_archive_summary_active_none_requires_empty_distinct() -> None:
    """F12b: archive_epoch_id_active=None + distinct 非空 → ValueError."""
    with pytest.raises(
        ValueError, match="empty distinct_dataset_epoch_ids"
    ):
        GraduationArchiveSummary(
            n_graduates=0,
            distinct_dataset_epoch_ids=frozenset({"e1"}),
            recent_epoch_summaries=tuple(),
            archive_epoch_id_active=None,
        )


def test_archive_summary_active_none_requires_empty_recent() -> None:
    """F12c: archive_epoch_id_active=None + recent 非空 → ValueError.

    distinct 空 + recent 非空 は I-3 で先に raise されるため、
    distinct 非空 + recent 非空 + active=None で I-3 を通過させると I-4
    の empty-distinct 違反が先に raise される (= 順序仕様 I-1→I-2→I-3→I-4).

    本 test は **active=None で recent 非空** の組合せが必ず ValueError に
    なることを示す (= raise message は distinct/recent いずれかで OK).
    """
    s1 = _epoch_summary("e1")
    with pytest.raises(ValueError):
        GraduationArchiveSummary(
            n_graduates=0,
            distinct_dataset_epoch_ids=frozenset({"e1"}),
            recent_epoch_summaries=(s1,),
            archive_epoch_id_active=None,
        )


def test_archive_summary_active_must_be_in_distinct() -> None:
    """F13: archive_epoch_id_active ∉ distinct_dataset_epoch_ids → ValueError."""
    with pytest.raises(
        ValueError, match=r"not in.*distinct_dataset_epoch_ids"
    ):
        GraduationArchiveSummary(
            n_graduates=0,
            distinct_dataset_epoch_ids=frozenset({"e1"}),
            recent_epoch_summaries=tuple(),
            archive_epoch_id_active="e_unknown",
        )


def test_archive_summary_active_matches_recent_head() -> None:
    """F14: recent[0].dataset_epoch_id != archive_epoch_id_active → ValueError."""
    s1 = _epoch_summary("e1")
    s2 = _epoch_summary("e2")
    with pytest.raises(
        ValueError, match="!= archive_epoch_id_active"
    ):
        GraduationArchiveSummary(
            n_graduates=0,
            distinct_dataset_epoch_ids=frozenset({"e1", "e2"}),
            recent_epoch_summaries=(s1, s2),  # head=e1
            archive_epoch_id_active="e2",  # active=e2 mismatch
        )


# ---------------------------------------------------------------------------
# F15-F22: evaluate_graduation_trigger tests
# ---------------------------------------------------------------------------


def test_evaluate_trigger_happy_path_ready() -> None:
    """F15: 全 3 条件達成 → status="ready" / has_recent_mission_pass=True."""
    archive = _archive_summary(n_graduates=24)
    res = evaluate_graduation_trigger(
        archive_summary=archive,
        recent_epochs_with_mission_pass_required=3,
    )
    assert res.status == "ready"
    assert res.has_recent_mission_pass is True
    assert res.n_graduates == 24
    assert res.n_distinct_epochs == 3
    assert res.recent_epochs_required == 3
    assert res.calc_version == GRADUATION_TRIGGER_CALC_VERSION
    assert set(res.recent_mission_pass_epoch_ids) == {"e1", "e2", "e3"}


def test_evaluate_trigger_insufficient_graduates() -> None:
    """F16: n_graduates=23 → status="insufficient_graduates"."""
    archive = _archive_summary(n_graduates=23)
    res = evaluate_graduation_trigger(
        archive_summary=archive,
        recent_epochs_with_mission_pass_required=3,
    )
    assert res.status == "insufficient_graduates"
    assert res.has_recent_mission_pass is False
    assert res.recent_mission_pass_epoch_ids == tuple()
    assert res.n_graduates == 23


def test_evaluate_trigger_insufficient_epochs() -> None:
    """F17: distinct=2 → status="insufficient_epochs"."""
    recent = (
        _epoch_summary("e2", mission_pass=("e2_run_a",)),
        _epoch_summary("e1", mission_pass=("e1_run_a",)),
    )
    archive = _archive_summary(
        n_graduates=24,
        distinct_epochs=("e1", "e2"),
        recent_epochs=recent,
        archive_active="e2",
    )
    res = evaluate_graduation_trigger(
        archive_summary=archive,
        recent_epochs_with_mission_pass_required=3,
    )
    assert res.status == "insufficient_epochs"
    assert res.has_recent_mission_pass is False
    assert res.recent_mission_pass_epoch_ids == tuple()
    assert res.n_distinct_epochs == 2


def test_evaluate_trigger_no_recent_mission_pass_short() -> None:
    """F18: recent_epoch_summaries が required 未満 → "no_recent_mission_pass"."""
    # required=3 だが recent は 2 件のみ
    recent = (
        _epoch_summary("e3", mission_pass=("e3_run_a",)),
        _epoch_summary("e2", mission_pass=("e2_run_a",)),
    )
    archive = _archive_summary(
        n_graduates=24,
        distinct_epochs=("e1", "e2", "e3"),
        recent_epochs=recent,
        archive_active="e3",
    )
    res = evaluate_graduation_trigger(
        archive_summary=archive,
        recent_epochs_with_mission_pass_required=3,
    )
    assert res.status == "no_recent_mission_pass"
    assert res.has_recent_mission_pass is False
    # short 経路は早期 return で空 tuple
    assert res.recent_mission_pass_epoch_ids == tuple()


def test_evaluate_trigger_no_recent_mission_pass_partial() -> None:
    """F19: 直近 N epoch 中 1 epoch のみ has_mission_pass → "no_recent_mission_pass".

    Round D2 [W1]: partial pass diagnostic 保持.
    """
    recent = (
        _epoch_summary("e3", mission_pass=()),
        _epoch_summary("e2", mission_pass=("e2_run_a",)),  # 1 epoch のみ pass
        _epoch_summary("e1", mission_pass=()),
    )
    archive = _archive_summary(
        n_graduates=24,
        distinct_epochs=("e1", "e2", "e3"),
        recent_epochs=recent,
        archive_active="e3",
    )
    res = evaluate_graduation_trigger(
        archive_summary=archive,
        recent_epochs_with_mission_pass_required=3,
    )
    assert res.status == "no_recent_mission_pass"
    assert res.has_recent_mission_pass is False
    # partial diagnostic = pass した epoch のみ保持
    assert res.recent_mission_pass_epoch_ids == ("e2",)


def test_evaluate_trigger_priority_graduates_over_epochs() -> None:
    """F20: n_graduates=23 + distinct=2 → "insufficient_graduates" (= 最優先)."""
    recent = (
        _epoch_summary("e2", mission_pass=("e2_run_a",)),
        _epoch_summary("e1", mission_pass=("e1_run_a",)),
    )
    archive = _archive_summary(
        n_graduates=23,
        distinct_epochs=("e1", "e2"),
        recent_epochs=recent,
        archive_active="e2",
    )
    res = evaluate_graduation_trigger(
        archive_summary=archive,
        recent_epochs_with_mission_pass_required=3,
    )
    assert res.status == "insufficient_graduates"


def test_evaluate_trigger_priority_epochs_over_recent() -> None:
    """F21: n_graduates=24 + distinct=2 + recent OK → "insufficient_epochs"."""
    recent = (
        _epoch_summary("e2", mission_pass=("e2_run_a",)),
        _epoch_summary("e1", mission_pass=("e1_run_a",)),
    )
    archive = _archive_summary(
        n_graduates=24,
        distinct_epochs=("e1", "e2"),
        recent_epochs=recent,
        archive_active="e2",
    )
    res = evaluate_graduation_trigger(
        archive_summary=archive,
        recent_epochs_with_mission_pass_required=2,  # recent 自体は OK
    )
    assert res.status == "insufficient_epochs"


def test_evaluate_trigger_required_lt_one_raises() -> None:
    """F22: recent_epochs_with_mission_pass_required=0 → ValueError."""
    archive = _archive_summary()
    with pytest.raises(
        ValueError,
        match="recent_epochs_with_mission_pass_required >= 1",
    ):
        evaluate_graduation_trigger(
            archive_summary=archive,
            recent_epochs_with_mission_pass_required=0,
        )


def test_evaluate_trigger_required_is_caller_argument() -> None:
    """F22b: required を 1 / 2 / 3 で渡して結果が引数依存に変わる
    (= 定数化していない、 Round R1 [C1])."""
    # 直近 1 epoch のみ pass、 残りは pass なし → required=1 で ready
    recent = (
        _epoch_summary("e3", mission_pass=("e3_run_a",)),  # pass
        _epoch_summary("e2", mission_pass=()),  # not pass
        _epoch_summary("e1", mission_pass=()),  # not pass
    )
    archive = _archive_summary(
        n_graduates=24,
        distinct_epochs=("e1", "e2", "e3"),
        recent_epochs=recent,
        archive_active="e3",
    )
    res_1 = evaluate_graduation_trigger(
        archive_summary=archive,
        recent_epochs_with_mission_pass_required=1,
    )
    assert res_1.status == "ready"
    assert res_1.recent_mission_pass_epoch_ids == ("e3",)

    res_2 = evaluate_graduation_trigger(
        archive_summary=archive,
        recent_epochs_with_mission_pass_required=2,
    )
    assert res_2.status == "no_recent_mission_pass"
    # partial: 直近 2 epoch 中 e3 のみ pass
    assert res_2.recent_mission_pass_epoch_ids == ("e3",)

    res_3 = evaluate_graduation_trigger(
        archive_summary=archive,
        recent_epochs_with_mission_pass_required=3,
    )
    assert res_3.status == "no_recent_mission_pass"
    assert res_3.recent_mission_pass_epoch_ids == ("e3",)


def test_evaluate_trigger_has_recent_mission_pass_status_dependent() -> None:
    """F22c: status != "ready" 時の has_recent_mission_pass=False (Round 3 [W3])."""
    archive = _archive_summary(n_graduates=23)
    res = evaluate_graduation_trigger(
        archive_summary=archive,
        recent_epochs_with_mission_pass_required=3,
    )
    assert res.status == "insufficient_graduates"
    # status 従属 (= 実データに mission_pass 多数あっても early return で False)
    assert res.has_recent_mission_pass is False


def test_trigger_evaluation_dataclass_required_lt_one_raises() -> None:
    """F22d (Round D1 [C1]): GraduationTriggerEvaluation を直接構築して
    recent_epochs_required=0 → ValueError."""
    with pytest.raises(
        ValueError, match="recent_epochs_required >= 1 required"
    ):
        GraduationTriggerEvaluation(
            status="insufficient_graduates",
            n_graduates=0,
            n_distinct_epochs=0,
            recent_mission_pass_epoch_ids=tuple(),
            has_recent_mission_pass=False,
            recent_epochs_required=0,
            calc_version=GRADUATION_TRIGGER_CALC_VERSION,
        )


@pytest.mark.parametrize(
    "status,override_field,override_value,match_pattern",
    [
        # ready: n_graduates 不足 (= I-3 ready 専用 invariant)
        # baseline required=1 / recent_pass len=1 で I-2b cross-field を回避し、
        # I-3 で n_graduates < 24 を発火させる.
        (
            "ready",
            "n_graduates",
            23,
            r"status='ready' requires n_graduates >=",
        ),
        # ready: n_distinct_epochs 不足 (= I-3 ready 専用 invariant)
        # baseline required=1 / recent_pass len=1 で I-2b cross-field
        # (n_distinct >= len(recent_pass) = 1) を override 後も維持し、
        # I-3 で n_distinct_epochs < 3 を発火させる. override=2 < 3 OK.
        (
            "ready",
            "n_distinct_epochs",
            2,
            r"status='ready' requires n_distinct_epochs >=",
        ),
        # insufficient_graduates: n_graduates が閾値以上 (status と矛盾)
        (
            "insufficient_graduates",
            "n_graduates",
            24,
            "requires n_graduates <",
        ),
        # insufficient_epochs: n_graduates 不足 (status と矛盾)
        (
            "insufficient_epochs",
            "n_graduates",
            23,
            "implies graduates condition OK",
        ),
        # insufficient_epochs: n_distinct_epochs が閾値以上 (status と矛盾)
        (
            "insufficient_epochs",
            "n_distinct_epochs",
            3,
            "requires n_distinct_epochs <",
        ),
        # no_recent_mission_pass: n_graduates 不足
        (
            "no_recent_mission_pass",
            "n_graduates",
            23,
            "implies graduates condition OK",
        ),
        # no_recent_mission_pass: n_distinct_epochs 不足
        (
            "no_recent_mission_pass",
            "n_distinct_epochs",
            2,
            "implies epochs condition OK",
        ),
    ],
)
def test_trigger_evaluation_status_invariant_complete(
    status: GraduationTriggerStatus,
    override_field: str,
    override_value: int,
    match_pattern: str,
) -> None:
    """F22e (Round D1 [W3] / Round D2 [S3] parametrize): status 別 invariant 違反.

    valid baseline + 1 field override matrix.

    ready baseline は **required=1 / recent_pass len=1** で構築 (= I-2b cross-field
    invariant `n_distinct_epochs >= len(recent_pass)` を override 後も維持).
    これにより override=2 で I-2b より先に I-3 ready 専用 invariant
    (`n_distinct_epochs < GRADUATION_TRIGGER_MIN_EPOCHS=3`) が発火.
    """
    # baseline (status 別の valid 構築)
    baseline: dict[str, Any]
    if status == "ready":
        baseline = {
            "status": "ready",
            "n_graduates": 24,
            "n_distinct_epochs": 3,
            "recent_mission_pass_epoch_ids": ("e1",),
            "has_recent_mission_pass": True,
            "recent_epochs_required": 1,
            "calc_version": GRADUATION_TRIGGER_CALC_VERSION,
        }
    elif status == "insufficient_graduates":
        baseline = {
            "status": "insufficient_graduates",
            "n_graduates": 23,
            "n_distinct_epochs": 0,
            "recent_mission_pass_epoch_ids": tuple(),
            "has_recent_mission_pass": False,
            "recent_epochs_required": 3,
            "calc_version": GRADUATION_TRIGGER_CALC_VERSION,
        }
    elif status == "insufficient_epochs":
        baseline = {
            "status": "insufficient_epochs",
            "n_graduates": 24,
            "n_distinct_epochs": 2,
            "recent_mission_pass_epoch_ids": tuple(),
            "has_recent_mission_pass": False,
            "recent_epochs_required": 3,
            "calc_version": GRADUATION_TRIGGER_CALC_VERSION,
        }
    elif status == "no_recent_mission_pass":
        baseline = {
            "status": "no_recent_mission_pass",
            "n_graduates": 24,
            "n_distinct_epochs": 3,
            "recent_mission_pass_epoch_ids": tuple(),
            "has_recent_mission_pass": False,
            "recent_epochs_required": 3,
            "calc_version": GRADUATION_TRIGGER_CALC_VERSION,
        }
    else:
        raise AssertionError(f"unknown status {status!r}")
    # baseline は valid 構築できることを確認
    GraduationTriggerEvaluation(**baseline)
    # override で invariant 違反
    bad = {**baseline, override_field: override_value}
    with pytest.raises(ValueError, match=match_pattern):
        GraduationTriggerEvaluation(**bad)


def test_trigger_no_recent_mission_pass_partial_zero() -> None:
    """F22f (Round D2 [W1] / Round D3 [S3]): status="no_recent_mission_pass" +
    len=0 → 正常 (= 全 fail)."""
    s = GraduationTriggerEvaluation(
        status="no_recent_mission_pass",
        n_graduates=24,
        n_distinct_epochs=3,
        recent_mission_pass_epoch_ids=tuple(),
        has_recent_mission_pass=False,
        recent_epochs_required=3,
        calc_version=GRADUATION_TRIGGER_CALC_VERSION,
    )
    assert len(s.recent_mission_pass_epoch_ids) == 0


def test_trigger_no_recent_mission_pass_partial_max() -> None:
    """F22f (Round D3 [S3]): status="no_recent_mission_pass" + len=required-1 →
    正常 (= partial 最大値)."""
    s = GraduationTriggerEvaluation(
        status="no_recent_mission_pass",
        n_graduates=24,
        n_distinct_epochs=3,
        recent_mission_pass_epoch_ids=("e1", "e2"),  # required-1 = 2
        has_recent_mission_pass=False,
        recent_epochs_required=3,
        calc_version=GRADUATION_TRIGGER_CALC_VERSION,
    )
    assert len(s.recent_mission_pass_epoch_ids) == 2


def test_trigger_no_recent_mission_pass_full_pass_invalid() -> None:
    """F22g (Round D2 [W1]): status="no_recent_mission_pass" + len=required →
    ValueError (= ready のはず)."""
    with pytest.raises(
        ValueError,
        match=r"0 <= len\(recent_mission_pass_epoch_ids\) < recent_epochs_required",
    ):
        GraduationTriggerEvaluation(
            status="no_recent_mission_pass",
            n_graduates=24,
            n_distinct_epochs=3,
            recent_mission_pass_epoch_ids=("e1", "e2", "e3"),  # = required
            has_recent_mission_pass=False,
            recent_epochs_required=3,
            calc_version=GRADUATION_TRIGGER_CALC_VERSION,
        )


def test_trigger_no_recent_mission_pass_overflow_invalid() -> None:
    """F22g (Round D3 [S3]): status="no_recent_mission_pass" + len>required →
    ValueError (= 0 <= len < required 違反)."""
    with pytest.raises(
        ValueError,
        match=r"0 <= len\(recent_mission_pass_epoch_ids\) < recent_epochs_required",
    ):
        GraduationTriggerEvaluation(
            status="no_recent_mission_pass",
            n_graduates=24,
            n_distinct_epochs=4,
            recent_mission_pass_epoch_ids=("e1", "e2", "e3", "e4"),  # > required
            has_recent_mission_pass=False,
            recent_epochs_required=3,
            calc_version=GRADUATION_TRIGGER_CALC_VERSION,
        )


def test_trigger_evaluation_duplicate_epoch_ids_invalid() -> None:
    """F22h (Round D3 [W1]): recent_mission_pass_epoch_ids に duplicate →
    ValueError."""
    with pytest.raises(
        ValueError, match="must be unique"
    ):
        GraduationTriggerEvaluation(
            status="ready",
            n_graduates=24,
            n_distinct_epochs=3,
            recent_mission_pass_epoch_ids=("e1", "e1", "e3"),  # duplicate e1
            has_recent_mission_pass=True,
            recent_epochs_required=3,
            calc_version=GRADUATION_TRIGGER_CALC_VERSION,
        )


def test_trigger_evaluation_n_distinct_epochs_lt_recent_pass_invalid() -> None:
    """F22i (Round D3 [W1]): n_distinct_epochs < len(recent_mission_pass_epoch_ids)
    → ValueError."""
    with pytest.raises(
        ValueError, match="mission pass epochs subset of distinct epochs"
    ):
        GraduationTriggerEvaluation(
            status="no_recent_mission_pass",
            n_graduates=24,
            n_distinct_epochs=2,  # < len(recent) = 3
            recent_mission_pass_epoch_ids=("e1", "e2", "e3"),
            has_recent_mission_pass=False,
            recent_epochs_required=4,
            calc_version=GRADUATION_TRIGGER_CALC_VERSION,
        )


def test_trigger_evaluation_ready_n_distinct_lt_required_invalid() -> None:
    """F22j (Round D3 [W1]): status="ready" + n_distinct_epochs <
    recent_epochs_required → ValueError (= 上記 I-2b cross-field invariant の派生).

    n_distinct_epochs=4 + required=5 + recent_pass len=5 で I-2b cross-field
    invariant 違反 (= n_distinct_epochs < len(recent_pass)).
    """
    with pytest.raises(
        ValueError, match="mission pass epochs subset of distinct epochs"
    ):
        GraduationTriggerEvaluation(
            status="ready",
            n_graduates=24,
            n_distinct_epochs=4,
            recent_mission_pass_epoch_ids=("e1", "e2", "e3", "e4", "e5"),
            has_recent_mission_pass=True,
            recent_epochs_required=5,
            calc_version=GRADUATION_TRIGGER_CALC_VERSION,
        )


def test_trigger_evaluation_calc_version_invalid() -> None:
    """calc_version != GRADUATION_TRIGGER_CALC_VERSION → ValueError."""
    with pytest.raises(ValueError, match="calc_version must be 'v1'"):
        GraduationTriggerEvaluation(
            status="insufficient_graduates",
            n_graduates=0,
            n_distinct_epochs=0,
            recent_mission_pass_epoch_ids=tuple(),
            has_recent_mission_pass=False,
            recent_epochs_required=3,
            calc_version="bad",
        )


# ---------------------------------------------------------------------------
# F23-F25: MultiPairAggregationSketch / scaffold tests
# ---------------------------------------------------------------------------


def test_compute_multi_pair_aggregation_sketch_factory() -> None:
    """F23: compute_multi_pair_aggregation_sketch(kind="worst_pair") →
    status="not_implemented" / calc_version="scaffold-v1"."""
    s = compute_multi_pair_aggregation_sketch(kind="worst_pair")
    assert s.kind == "worst_pair"
    assert s.status == "not_implemented"
    assert s.calc_version == GRADUATION_AGGREGATION_CALC_VERSION
    assert s.calc_version == "scaffold-v1"


def test_compute_multi_pair_aggregation_sketch_kind_mean() -> None:
    """F24: kind="mean" → 同上."""
    s = compute_multi_pair_aggregation_sketch(kind="mean")
    assert s.kind == "mean"
    assert s.status == "not_implemented"
    assert s.calc_version == GRADUATION_AGGREGATION_CALC_VERSION


def test_multi_pair_aggregation_sketch_does_not_raise() -> None:
    """F25: scaffold 関数は NotImplementedError raise しない."""
    # raise しないことを確認
    s_worst = compute_multi_pair_aggregation_sketch(kind="worst_pair")
    s_mean = compute_multi_pair_aggregation_sketch(kind="mean")
    assert isinstance(s_worst, MultiPairAggregationSketch)
    assert isinstance(s_mean, MultiPairAggregationSketch)


def test_multi_pair_aggregation_sketch_status_invalid() -> None:
    """F25b: status="ok" → ValueError."""
    with pytest.raises(ValueError, match="status must be 'not_implemented'"):
        MultiPairAggregationSketch(
            kind="worst_pair",
            status="ok",  # type: ignore[arg-type]
            calc_version=GRADUATION_AGGREGATION_CALC_VERSION,
        )


def test_multi_pair_aggregation_sketch_calc_version_invalid() -> None:
    """F25c: calc_version="v1" → ValueError."""
    with pytest.raises(ValueError, match="calc_version must be 'scaffold-v1'"):
        MultiPairAggregationSketch(
            kind="worst_pair",
            status="not_implemented",
            calc_version="v1",
        )


# ---------------------------------------------------------------------------
# F26-F27: 既存 SSOT 整合 / collider bias tests
# ---------------------------------------------------------------------------


def test_graduation_batch_pairs_set_equal_to_t064() -> None:
    """F26: GRADUATION_BATCH_PAIRS == frozenset({STAGE_C_ANCHOR_PAIR} ∪
    STAGE_C_SHADOW_PAIR_LIST) (= test 側のみ T064 import、 Round R2 [S4]).

    既存 stage_bc_evaluator.py の constants と集合等価 (順序非依存) であることを
    確認. production module 側は STAGE_C_ANCHOR_PAIR を import しない (=
    F27 grep DoD で確認).
    """
    expected = frozenset({STAGE_C_ANCHOR_PAIR}) | frozenset(
        STAGE_C_SHADOW_PAIR_LIST
    )
    assert expected == GRADUATION_BATCH_PAIRS
    assert len(GRADUATION_BATCH_PAIRS) == 6


def _build_module_ast() -> ast.Module:
    import src.alpha_factory.graduation as g

    with open(g.__file__, encoding="utf-8") as f:
        return ast.parse(f.read())


def _docstring_node_ids(tree: ast.Module) -> set[int]:
    """docstring node 集合 (= 除外対象、 ast.Module / FunctionDef / ClassDef
    の最初の statement)."""
    ids: set[int] = set()
    for parent in ast.walk(tree):
        if isinstance(
            parent,
            (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            body = getattr(parent, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


# Round D2 [W3] / Round D3 [W2]: forbidden 識別子は exact name と substring 分離
FORBIDDEN_MODULES_SUBSTRINGS = ("archive", "swim_lane", "cross_pair")
FORBIDDEN_EXACT_NAMES = (
    "ANCHOR_PAIRS",
    "promote_graduates",
    "mark_graduated",
    "GraduationLane",
    "seed_graduates",
    "Tier1Lane",
    "tier1",
    "tier_1",
)
# Round D3 [W4]: case-sensitive substring (= "DST" 大文字、 "dst_xxx" 小文字は許容)
FORBIDDEN_SUBSTRINGS = ("holiday", "DST", "observability_flags")


def test_graduation_module_no_collider_bias_imports() -> None:
    """F27 (Round 3 [S3] / Round D2 [W2] [W3] / Round D3 [W2] [W3]):
    AST 解析 + 完全一致 + substring 分離.

    T074 module 内に observability_flags / holiday / DST 参照なし.
    """
    tree = _build_module_ast()
    docstring_ids = _docstring_node_ids(tree)

    def _check(token: str, context: str) -> None:
        assert token not in FORBIDDEN_EXACT_NAMES, (
            f"T074 module references forbidden exact name {token!r} ({context})"
        )
        for sub in FORBIDDEN_SUBSTRINGS:
            assert sub not in token, (
                f"T074 module references identifier containing {sub!r} "
                f"({context}): {token!r}"
            )

    # ImportFrom / Import (Round D3 [W3]: alias.name も対象、
    # 例 `from . import archive`)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                for sub in FORBIDDEN_MODULES_SUBSTRINGS:
                    assert sub not in node.module, (
                        f"T074 module imports forbidden module "
                        f"{node.module!r} (matched substring {sub!r})"
                    )
            for alias in node.names:
                for sub in FORBIDDEN_MODULES_SUBSTRINGS:
                    assert sub not in alias.name, (
                        f"T074 module ImportFrom alias {alias.name!r} "
                        f"matched {sub!r}"
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for sub in FORBIDDEN_MODULES_SUBSTRINGS:
                    assert sub not in alias.name, (
                        f"T074 module Import {alias.name!r} matched {sub!r}"
                    )

    # Name / Attribute
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            _check(node.id, f"Name at line {node.lineno}")
        elif isinstance(node, ast.Attribute):
            _check(node.attr, f"Attribute at line {node.lineno}")

    # string literal (Round D2 [W2])、 docstring 除外
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstring_ids:
                continue
            _check(node.value, f"string literal at line {node.lineno}")


def test_graduation_module_grep_dod_detects_relative_import_alias() -> None:
    """F27 (Round D3 [W3]): `from . import archive` の検出
    (= ImportFrom alias.name 経由)、 mock module で raise 確認."""
    src = "from . import archive\n"
    tree = ast.parse(src)
    detected = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                for sub in FORBIDDEN_MODULES_SUBSTRINGS:
                    if sub in alias.name:
                        detected = True
                        break
    assert detected, "relative import alias.name 'archive' must be detected"


def test_graduation_module_grep_dod_substring_case_sensitive() -> None:
    """F27 (Round D3 [W4]): forbidden_substrings は case-sensitive
    (= "DST" 大文字 substring は検出、 "dst_xxx" 小文字は許容)."""
    # "DST" 大文字 substring は検出
    assert "DST" in "DST_TRANSITION"
    assert any(sub in "DST_TRANSITION" for sub in FORBIDDEN_SUBSTRINGS)
    # "dst_xxx" 小文字は検出されない (= case-sensitive)
    assert "DST" not in "dst_transition"
    # "DST" 以外の forbidden substring は "dst_transition" に含まれない
    assert not any(sub in "dst_transition" for sub in FORBIDDEN_SUBSTRINGS)


def test_graduation_module_grep_dod_tier1_substring_allowed() -> None:
    """F27 (Round D3 [W2]): `tier1_event` のような substring は許容、 `tier1`
    (exact name) のみ reject."""
    # exact name "tier1" は reject 対象
    assert "tier1" in FORBIDDEN_EXACT_NAMES
    # `tier1_event` 自身は exact name に含まれない
    assert "tier1_event" not in FORBIDDEN_EXACT_NAMES
    # `tier1_event` は forbidden substring 経路でも検出されない
    # (= tier1 は exact name のみ、 substring としては許容)
    assert not any(sub in "tier1_event" for sub in FORBIDDEN_SUBSTRINGS)


def test_graduation_module_no_existing_swim_lane_archive_imports() -> None:
    """T074 module は `archive` / `swim_lane` / `cross_pair` を import しない
    (Round R2 [S3])."""
    tree = _build_module_ast()
    forbidden = ("archive", "swim_lane", "cross_pair")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                for sub in forbidden:
                    assert sub not in node.module, (
                        f"T074 module imports {node.module!r} "
                        f"(matched {sub!r})"
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for sub in forbidden:
                    assert sub not in alias.name, (
                        f"T074 module imports {alias.name!r} "
                        f"(matched {sub!r})"
                    )


def test_graduation_module_no_runtime_import_from_src() -> None:
    """T074 module は src/ 配下の他 module から import されていない (= 純ライブラリ).

    devnotes 詳細設計 § 2.2 grep DoD 1.
    """
    import os

    src_root = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )  # tests/alpha_factory/.. = tests/
    repo_src = os.path.join(os.path.dirname(src_root), "src")
    referencing_files: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(repo_src):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            with open(fpath, encoding="utf-8") as f:
                content = f.read()
            if (
                "from src.alpha_factory.graduation import" in content
                or "import src.alpha_factory.graduation" in content
            ):
                referencing_files.append(fpath)
    assert not referencing_files, (
        f"T074 graduation.py is imported from src/ (expected 0 files): "
        f"{referencing_files}"
    )
