"""T075 big-bang cleanup + smoke (smoke.py 新規) tests.

詳細設計 § 5 + DoD § 8 + AST grep DoD § 2.3.

命名規約 (詳細設計 § 5.1): Fxxx_<behavior> 形式で pytest 関数名と 1:1 対応.
"""

from __future__ import annotations

import ast
import dataclasses
import os
import re
from typing import get_args

import pytest

from src.alpha_factory.smoke import (
    CROSS_RUN_DOD_ITEMS_COUNT,
    DUAL_PATH_ENFORCE_ALLOWLIST,
    DUAL_PATH_ENFORCE_TARGETS,
    PER_RUN_DOD_ITEMS_COUNT,
    SMOKE_REPORT_SCHEMA_VERSION,
    SMOKE_RUNS_REQUIRED,
    AggregateEvidence,
    BigBangCleanupReport,
    CleanupCategorySlug,
    CrossRunSmokeDoDResult,
    CrossRunSmokeObservabilityProjection,
    DeletionTarget,
    DeletionTargetCategory,
    DoDIdCrossRun,
    DoDIdPerRun,
    EvidenceClass,
    EvidenceClassifierProtocol,
    FailureModeKind,
    FiveRunConsistencyResult,
    InconclusiveReason,
    MigrationMode,
    MigrationTarget,
    PerRunSmokeDoDResult,
    ReleaseActionRecommendation,
    RemovalMode,
    Severity,
    SmokeDoDItem,
    SmokeObservabilityProjection,
    SmokeOutcomeClassification,
    SmokeRunSummary,
    classify_smoke_outcome,
    decide_release_action,
    select_rollback_relevant_failure_modes,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_per_run_item(
    dod_id: str,
    *,
    status: EvidenceClass = "ok",
    detail: str = "ok",
) -> SmokeDoDItem:
    return SmokeDoDItem(
        dod_id=dod_id,
        scope="per_run",
        synthesis_text=f"synthesis text for {dod_id}",
        check_function_name=f"_check_{dod_id.lower()}",
        status=status,
        detail=detail,
    )


def _make_cross_run_item(
    *,
    status: EvidenceClass = "ok",
    detail: str = "ok",
) -> SmokeDoDItem:
    return SmokeDoDItem(
        dod_id="DoD8",
        scope="cross_run",
        synthesis_text="synthesis text for DoD8",
        check_function_name="_check_dod8",
        status=status,
        detail=detail,
    )


_AGGREGATION_ORDER: dict[EvidenceClass, int] = {
    "hard_fail": 3,
    "warning": 2,
    "inconclusive": 1,
    "ok": 0,
}


def _aggregate_test_statuses(
    statuses: tuple[EvidenceClass, ...],
) -> EvidenceClass:
    """test helper: items.status max 集約 (smoke._aggregate_evidence_class と
    同 order)."""
    best_rank = -1
    best: EvidenceClass = "ok"
    for s in statuses:
        rank = _AGGREGATION_ORDER[s]
        if rank > best_rank:
            best_rank = rank
            best = s
    return best


def _make_per_run_result(
    *,
    statuses: tuple[EvidenceClass, ...] | None = None,
    overall: EvidenceClass | None = None,
    observed_fms: frozenset[FailureModeKind] = frozenset(),
) -> PerRunSmokeDoDResult:
    statuses_resolved: tuple[EvidenceClass, ...] = (
        statuses
        if statuses is not None
        else (("ok",) * PER_RUN_DOD_ITEMS_COUNT)  # type: ignore[assignment]
    )
    assert len(statuses_resolved) == PER_RUN_DOD_ITEMS_COUNT
    items = tuple(
        _make_per_run_item(f"DoD{i + 1}", status=s, detail=f"d{i + 1}")
        for i, s in enumerate(statuses_resolved)
    )
    overall_resolved: EvidenceClass = (
        overall if overall is not None else _aggregate_test_statuses(statuses_resolved)
    )
    return PerRunSmokeDoDResult(
        items=items,
        overall_evidence_class=overall_resolved,
        observed_failure_modes=observed_fms,
        smoke_report_schema_version=SMOKE_REPORT_SCHEMA_VERSION,
    )


def _make_cross_run_result(
    *,
    status: EvidenceClass = "ok",
    detail: str = "ok",
    observed_fms: frozenset[FailureModeKind] = frozenset(),
) -> CrossRunSmokeDoDResult:
    return CrossRunSmokeDoDResult(
        item=_make_cross_run_item(status=status, detail=detail),
        observed_failure_modes=observed_fms,
        smoke_report_schema_version=SMOKE_REPORT_SCHEMA_VERSION,
    )


def _make_observability_projection(
    *, ab: EvidenceClass = "ok"
) -> SmokeObservabilityProjection:
    return SmokeObservabilityProjection(
        ab_divergence_class=ab,
        epoch_consistency_class="ok",
        warmstart_shortfall_class="ok",
        bypass_ratio_class="ok",
        session_entropy_class="ok",
        dataset_epoch_id_present=True,
        report_ref="run-1/observability.json",
    )


def _make_run_summary(run_id: str = "r1") -> SmokeRunSummary:
    return SmokeRunSummary(
        run_id=run_id,
        dataset_epoch_id="epoch-1",
        run_succeeded=True,
        per_run_dod=_make_per_run_result(),
        observability_projection=_make_observability_projection(),
        observed_failure_modes=frozenset(),
    )


def _make_five_run_result(
    *,
    cross_run: CrossRunSmokeDoDResult | None = None,
    overall: Severity = "ok",
) -> FiveRunConsistencyResult:
    runs = tuple(_make_run_summary(f"r{i + 1}") for i in range(SMOKE_RUNS_REQUIRED))
    if cross_run is None:
        cross_run = _make_cross_run_result()
    return FiveRunConsistencyResult(
        runs=runs,
        cross_run_dod=cross_run,
        epoch_pollution_observed=False,
        config_drift_observed=False,
        schema_version_consistent=True,
        overall_severity=overall,
    )


def _build_module_ast() -> ast.Module:
    import src.alpha_factory.smoke as s

    with open(s.__file__, encoding="utf-8") as f:
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


# ---------------------------------------------------------------------------
# F1-F4: 定数 / Literal tests
# ---------------------------------------------------------------------------


def test_constants_match_ssot() -> None:
    """F1: 定数値 SSOT 一致."""
    assert SMOKE_RUNS_REQUIRED == 5
    assert PER_RUN_DOD_ITEMS_COUNT == 7
    assert CROSS_RUN_DOD_ITEMS_COUNT == 1
    assert SMOKE_REPORT_SCHEMA_VERSION == "1.0.0"


def test_evidence_class_values() -> None:
    """F2: EvidenceClass 4 値."""
    assert set(get_args(EvidenceClass)) == {
        "hard_fail",
        "warning",
        "inconclusive",
        "ok",
    }


def test_severity_values() -> None:
    """F3: Severity 4 値 (= EvidenceClass 同型)."""
    assert set(get_args(Severity)) == set(get_args(EvidenceClass))


def test_failure_mode_kind_values() -> None:
    """F4: FailureModeKind 5 値 (FM1-FM5)."""
    assert set(get_args(FailureModeKind)) == {
        "FM1",
        "FM2",
        "FM3",
        "FM4",
        "FM5",
    }


def test_dod_id_per_run_values() -> None:
    """F4b: DoDIdPerRun 7 値 / DoDIdCrossRun 1 値."""
    assert set(get_args(DoDIdPerRun)) == {
        "DoD1",
        "DoD2",
        "DoD3",
        "DoD4",
        "DoD5",
        "DoD6",
        "DoD7",
    }
    assert set(get_args(DoDIdCrossRun)) == {"DoD8"}


def test_removal_and_migration_mode_values() -> None:
    """F4c: RemovalMode / MigrationMode SSOT (Round R2 [W4] 分離)."""
    assert set(get_args(RemovalMode)) == {"git_rm", "yaml_key_delete"}
    assert set(get_args(MigrationMode)) == {"yaml_value_replace"}


def test_cleanup_category_slug_values() -> None:
    """F4d: CleanupCategorySlug 5 値 (Round D1 [W1])."""
    assert set(get_args(CleanupCategorySlug)) == {
        "cleanup",
        "config",
        "script",
        "module",
        "schema",
    }


# ---------------------------------------------------------------------------
# F5-F7: InconclusiveReason tests (Round 4 [W2])
# ---------------------------------------------------------------------------


def test_inconclusive_reason_source_non_empty() -> None:
    """F5: source="" → ValueError."""
    with pytest.raises(ValueError, match="source"):
        InconclusiveReason(source="", reason_code="x", message="m")


def test_inconclusive_reason_code_non_empty() -> None:
    """F6: reason_code="" → ValueError."""
    with pytest.raises(ValueError, match="reason_code"):
        InconclusiveReason(source="DoD3", reason_code="", message="m")


def test_inconclusive_reason_dataclass_eq() -> None:
    """F7: 同 source / reason_code / message で eq 等価."""
    a = InconclusiveReason(source="DoD3", reason_code="x", message="m")
    b = InconclusiveReason(source="DoD3", reason_code="x", message="m")
    assert a == b
    assert hash(a) == hash(b)


# ---------------------------------------------------------------------------
# F8-F11: AggregateEvidence tests (Round 4 [S1] / Round D2 [S5])
# ---------------------------------------------------------------------------


def test_aggregate_evidence_invariant_has_inc_false_with_reasons() -> None:
    """F8: has_inconclusive=False + inconclusive_reasons 非空 → ValueError."""
    r = (InconclusiveReason(source="DoD3", reason_code="x", message="m"),)
    with pytest.raises(ValueError, match="invariant"):
        AggregateEvidence(
            severity="ok", has_inconclusive=False, inconclusive_reasons=r
        )


def test_aggregate_evidence_positive_match() -> None:
    """F8b (Round D2 [S5]): has_inconclusive=True + inconclusive_reasons 非空 →
    正常構築 (= positive case)."""
    r = (InconclusiveReason(source="DoD3", reason_code="x", message="m"),)
    ev = AggregateEvidence(
        severity="ok", has_inconclusive=True, inconclusive_reasons=r
    )
    assert ev.has_inconclusive is True
    assert ev.inconclusive_reasons == r


def test_aggregate_evidence_positive_no_inc() -> None:
    """F8c: has_inconclusive=False + inconclusive_reasons 空 → 正常構築."""
    ev = AggregateEvidence(
        severity="ok", has_inconclusive=False, inconclusive_reasons=()
    )
    assert ev.has_inconclusive is False
    assert ev.inconclusive_reasons == ()


def test_aggregate_evidence_invariant_reverse() -> None:
    """F9: has_inconclusive=True + inconclusive_reasons 空 → ValueError."""
    with pytest.raises(ValueError, match="invariant"):
        AggregateEvidence(
            severity="warning", has_inconclusive=True, inconclusive_reasons=()
        )


def test_aggregate_evidence_severity_4_values() -> None:
    """F10: severity ∈ EvidenceClass 4 値で構築可能."""
    for s in get_args(Severity):
        ev = AggregateEvidence(
            severity=s, has_inconclusive=False, inconclusive_reasons=()
        )
        assert ev.severity == s


def test_aggregate_evidence_happy() -> None:
    """F11: 各 invariant 満たす値で正常構築."""
    r = (
        InconclusiveReason(source="DoD3", reason_code="x", message="m1"),
        InconclusiveReason(source="DoD5", reason_code="y", message="m2"),
    )
    ev = AggregateEvidence(
        severity="warning", has_inconclusive=True, inconclusive_reasons=r
    )
    assert len(ev.inconclusive_reasons) == 2


# ---------------------------------------------------------------------------
# F12-F15: EvidenceClassifierProtocol conformance tests (Round 4 [S2] /
# Round D2 [W5] [S4] / Round D1 [W5])
# ---------------------------------------------------------------------------


class _MockClassifier:
    """conformance test mock (詳細設計 § 5.2 fixture).

    Round D2 [W5] [S4] error code 固定: detail prefix "T075_UNSUPPORTED_METRIC:".
    """

    _SUPPORTED = frozenset(
        {
            "ab_divergence",
            "epoch_consistency",
            "warmstart_shortfall",
            "bypass_ratio",
            "session_entropy",
        }
    )

    def supported_metric_names(self) -> frozenset[str]:
        return self._SUPPORTED

    def __call__(
        self,
        metric_value: object,
        metric_name: str,
        provenance: str,
    ) -> tuple[EvidenceClass, str]:
        if metric_name not in self._SUPPORTED:
            return (
                "inconclusive",
                f"T075_UNSUPPORTED_METRIC: unsupported metric: {metric_name}",
            )
        # mock impl: any supported -> ok with provenance
        return ("ok", f"mock ok ({provenance})")


@pytest.fixture
def mock_evidence_classifier() -> EvidenceClassifierProtocol:
    """conformance test fixture (詳細設計 § 5.2)."""
    return _MockClassifier()


def test_classifier_supported_metric_names_returns_frozenset(
    mock_evidence_classifier: EvidenceClassifierProtocol,
) -> None:
    """F12 (詳細設計 § 5.2 / Round 1 Codex W-02): 戻り値型 frozenset[str] +
    5 metric 必須完全一致."""
    result = mock_evidence_classifier.supported_metric_names()
    assert isinstance(result, frozenset)
    assert all(isinstance(x, str) for x in result)
    # Round 1 Codex W-02: 5 metric 必須完全一致 (詳細設計 § 5.2 fixture 規範)
    expected_5_metrics = frozenset(
        {
            "ab_divergence",
            "epoch_consistency",
            "warmstart_shortfall",
            "bypass_ratio",
            "session_entropy",
        }
    )
    assert result == expected_5_metrics, (
        f"mock classifier supported_metric_names() must equal "
        f"{sorted(expected_5_metrics)}, got {sorted(result)}"
    )


def test_classifier_unsupported_returns_inconclusive(
    mock_evidence_classifier: EvidenceClassifierProtocol,
) -> None:
    """F13 (Round D2 [W5] [S4]): unsupported metric_name → "inconclusive" 必須、
    detail prefix "T075_UNSUPPORTED_METRIC:"."""
    bogus_name = "not_a_real_metric_xyz"
    cls, detail = mock_evidence_classifier(
        metric_value=42, metric_name=bogus_name, provenance="test"
    )
    assert cls == "inconclusive", (
        f"classifier returned {cls!r} for unsupported metric "
        f"{bogus_name!r}, expected 'inconclusive'. "
        f"supported = {sorted(mock_evidence_classifier.supported_metric_names())}"
    )
    assert detail.startswith("T075_UNSUPPORTED_METRIC:"), (
        f"detail must start with 'T075_UNSUPPORTED_METRIC:', got {detail!r}"
    )


def test_classifier_supported_can_return_any_class(
    mock_evidence_classifier: EvidenceClassifierProtocol,
) -> None:
    """F14: supported metric_name → 4 値いずれも許容 (Round 4 [S2])."""
    for name in mock_evidence_classifier.supported_metric_names():
        cls, _ = mock_evidence_classifier(
            metric_value=0, metric_name=name, provenance="test"
        )
        assert cls in get_args(EvidenceClass)


def test_classifier_protocol_runtime_check(
    mock_evidence_classifier: EvidenceClassifierProtocol,
) -> None:
    """F15: isinstance(classifier, EvidenceClassifierProtocol) で True."""
    assert isinstance(mock_evidence_classifier, EvidenceClassifierProtocol)


# ---------------------------------------------------------------------------
# F16-F19: DeletionTarget / MigrationTarget tests (Round 4 [S3] /
# Round D1 [S2])
# ---------------------------------------------------------------------------


_VALID_CHANGE_GROUP_ID_PATTERN = re.compile(
    r"^T075-(cleanup|config|script|module|schema)-[a-z0-9_]+$"
)


def _valid_deletion_target(
    *,
    path: str = "src/alpha_factory/calibrate_gate.py",
    category: str = "全面置換",
    source_section: str = "12.2",
    change_group_id: str = "T075-module-archive_v1_read_path_removal",
    removal_mode: RemovalMode = "git_rm",
) -> DeletionTarget:
    return DeletionTarget(
        path=path,
        category=category,
        source_section=source_section,
        source_clause_id="synth-12-2-bullet-1",
        source_excerpt_hash="deadbeef",
        removal_mode=removal_mode,
        owner="T075 PR",
        change_group_id=change_group_id,
        supersedes=("src/alpha_factory/smoke.py",),
    )


def test_deletion_target_path_non_empty() -> None:
    """F16: path="" → ValueError."""
    with pytest.raises(ValueError, match="path"):
        _valid_deletion_target(path="")


def test_deletion_target_change_group_id_pattern() -> None:
    """F17 (Round 4 [S3] / Round D1 [S2]): change_group_id pattern 検証."""
    valid = _valid_deletion_target()
    assert _VALID_CHANGE_GROUP_ID_PATTERN.match(valid.change_group_id)

    # invalid: missing T075 prefix
    with pytest.raises(ValueError, match="change_group_id"):
        _valid_deletion_target(change_group_id="T076-module-x")
    # invalid: unknown category
    with pytest.raises(ValueError, match="change_group_id"):
        _valid_deletion_target(change_group_id="T075-unknown-x")
    # invalid: empty stable_slug
    with pytest.raises(ValueError, match="change_group_id"):
        _valid_deletion_target(change_group_id="T075-module-")
    # invalid: uppercase letter in stable_slug
    with pytest.raises(ValueError, match="change_group_id"):
        _valid_deletion_target(change_group_id="T075-module-ArchiveV1")


def test_deletion_target_supersedes_tuple() -> None:
    """F18: supersedes は tuple (= 順序保持)."""
    target = DeletionTarget(
        path="src/alpha_factory/calibrate_gate.py",
        category="全面置換",
        source_section="12.2",
        source_clause_id="synth-12-2-bullet-1",
        source_excerpt_hash="deadbeef",
        removal_mode="git_rm",
        owner="T075 PR",
        change_group_id="T075-module-test_x",
        supersedes=("a.py", "b.py", "c.py"),
    )
    assert isinstance(target.supersedes, tuple)
    assert target.supersedes == ("a.py", "b.py", "c.py")


def test_migration_target_change_group_id_same_as_deletion() -> None:
    """F19 (Round R3 [W4]): 同一論理変更で DeletionTarget と MigrationTarget が
    同 change_group_id 持つ場合の grouping."""
    cg_id = "T075-config-calibrate_v2_migration"
    deletion = _valid_deletion_target(
        category="旧 config キー",
        source_section="12.1",
        change_group_id=cg_id,
        removal_mode="yaml_key_delete",
        path="config/alpha_factory/default.yaml#stage_gate.stage_a.threshold_legacy",
    )
    migration = MigrationTarget(
        path="config/alpha_factory/default.yaml#stage_gate.stage_a.threshold",
        category="旧 config キー",
        source_section="12.1",
        source_clause_id="synth-12-1-bullet-x",
        source_excerpt_hash="cafebabe",
        migration_mode="yaml_value_replace",
        owner="T075 PR",
        new_value_reference="docs/alpha_factory/stage-gates.md#new-schema",
        change_group_id=cg_id,
        supersedes=(),
    )
    assert deletion.change_group_id == migration.change_group_id


def test_migration_target_required_fields() -> None:
    """F19b: MigrationTarget の必須 field 検証."""
    with pytest.raises(ValueError, match="path"):
        MigrationTarget(
            path="",
            category="旧 config キー",
            source_section="12.1",
            source_clause_id="x",
            source_excerpt_hash="h",
            migration_mode="yaml_value_replace",
            owner="o",
            new_value_reference="r",
            change_group_id="T075-config-x",
            supersedes=(),
        )
    with pytest.raises(ValueError, match="new_value_reference"):
        MigrationTarget(
            path="p",
            category="旧 config キー",
            source_section="12.1",
            source_clause_id="x",
            source_excerpt_hash="h",
            migration_mode="yaml_value_replace",
            owner="o",
            new_value_reference="",
            change_group_id="T075-config-x",
            supersedes=(),
        )


def test_deletion_target_category_validation() -> None:
    """F19c: DeletionTarget.category SSOT 4 値."""
    with pytest.raises(ValueError, match="category"):
        _valid_deletion_target(category="unknown")


def test_deletion_target_source_section_validation() -> None:
    """F19d: DeletionTarget.source_section ∈ {"12.1", "12.2"}."""
    with pytest.raises(ValueError, match="source_section"):
        _valid_deletion_target(source_section="13.0")


def test_deletion_target_category_aggregation() -> None:
    """F19e: DeletionTargetCategory 構築."""
    t = _valid_deletion_target()
    cat = DeletionTargetCategory(name="全面置換", targets=(t,))
    assert cat.name == "全面置換"
    assert len(cat.targets) == 1
    with pytest.raises(ValueError, match="name"):
        DeletionTargetCategory(name="", targets=())


# ---------------------------------------------------------------------------
# F20-F25: SmokeDoDItem / PerRunSmokeDoDResult / CrossRunSmokeDoDResult tests
# ---------------------------------------------------------------------------


def test_smoke_dod_item_scope_per_run_dod_id() -> None:
    """F20: scope='per_run' + dod_id='DoD8' → ValueError."""
    with pytest.raises(ValueError, match="per_run"):
        SmokeDoDItem(
            dod_id="DoD8",
            scope="per_run",
            synthesis_text="t",
            check_function_name="f",
            status="ok",
            detail="d",
        )


def test_smoke_dod_item_scope_cross_run_dod_id() -> None:
    """F21: scope='cross_run' + dod_id='DoD1' → ValueError."""
    with pytest.raises(ValueError, match="cross_run"):
        SmokeDoDItem(
            dod_id="DoD1",
            scope="cross_run",
            synthesis_text="t",
            check_function_name="f",
            status="ok",
            detail="d",
        )


def test_smoke_dod_item_unknown_scope() -> None:
    """F21b: 未知の scope → ValueError."""
    with pytest.raises(ValueError, match="scope"):
        SmokeDoDItem(
            dod_id="DoD1",
            scope="unknown",  # type: ignore[arg-type]
            synthesis_text="t",
            check_function_name="f",
            status="ok",
            detail="d",
        )


def test_per_run_dod_result_items_count() -> None:
    """F22: items len != 7 → ValueError."""
    items = tuple(_make_per_run_item(f"DoD{i + 1}") for i in range(6))
    with pytest.raises(ValueError, match="7"):
        PerRunSmokeDoDResult(
            items=items,
            overall_evidence_class="ok",
            observed_failure_modes=frozenset(),
            smoke_report_schema_version=SMOKE_REPORT_SCHEMA_VERSION,
        )


def test_per_run_dod_result_items_unique_dod_id() -> None:
    """F23: items の dod_id 重複 → ValueError."""
    items = tuple(_make_per_run_item("DoD1") for _ in range(7))
    with pytest.raises(ValueError, match="duplicate"):
        PerRunSmokeDoDResult(
            items=items,
            overall_evidence_class="ok",
            observed_failure_modes=frozenset(),
            smoke_report_schema_version=SMOKE_REPORT_SCHEMA_VERSION,
        )


def test_per_run_dod_result_schema_version_mismatch() -> None:
    """F23b: schema_version mismatch → ValueError."""
    items = tuple(_make_per_run_item(f"DoD{i + 1}") for i in range(7))
    with pytest.raises(ValueError, match="smoke_report_schema_version"):
        PerRunSmokeDoDResult(
            items=items,
            overall_evidence_class="ok",
            observed_failure_modes=frozenset(),
            smoke_report_schema_version="9.9.9",
        )


def test_per_run_dod_result_happy() -> None:
    """F23c: 正常構築."""
    result = _make_per_run_result()
    assert len(result.items) == PER_RUN_DOD_ITEMS_COUNT
    assert result.overall_evidence_class == "ok"


def test_per_run_dod_result_overall_aggregation_invariant() -> None:
    """F23d (Round 1 Codex C-01): items.status 集約と overall_evidence_class
    の不一致 → ValueError.

    順序: hard_fail > warning > inconclusive > ok (詳細設計 § 3.1).
    """
    # 1 個でも hard_fail があれば overall は hard_fail でなければならない
    items = tuple(
        _make_per_run_item(f"DoD{i + 1}", status="ok") for i in range(7)
    )
    hf_item = SmokeDoDItem(
        dod_id="DoD4",
        scope="per_run",
        synthesis_text="t",
        check_function_name="f",
        status="hard_fail",
        detail="d",
    )
    items_with_hf = (*items[:3], hf_item, *items[4:])
    # overall_evidence_class="ok" は不正 (= hard_fail を隠蔽)
    with pytest.raises(ValueError, match="overall_evidence_class"):
        PerRunSmokeDoDResult(
            items=items_with_hf,
            overall_evidence_class="ok",
            observed_failure_modes=frozenset(),
            smoke_report_schema_version=SMOKE_REPORT_SCHEMA_VERSION,
        )

    # warning + inconclusive 混在 → max は "warning"
    warning_item = SmokeDoDItem(
        dod_id="DoD1",
        scope="per_run",
        synthesis_text="t",
        check_function_name="f",
        status="warning",
        detail="d",
    )
    inc_item = SmokeDoDItem(
        dod_id="DoD2",
        scope="per_run",
        synthesis_text="t",
        check_function_name="f",
        status="inconclusive",
        detail="d",
    )
    rest_ok = tuple(
        _make_per_run_item(f"DoD{i + 3}", status="ok") for i in range(5)
    )
    items_w_inc = (warning_item, inc_item, *rest_ok)
    # overall_evidence_class="inconclusive" は不正 (= warning が落ちる)
    with pytest.raises(ValueError, match="overall_evidence_class"):
        PerRunSmokeDoDResult(
            items=items_w_inc,
            overall_evidence_class="inconclusive",
            observed_failure_modes=frozenset(),
            smoke_report_schema_version=SMOKE_REPORT_SCHEMA_VERSION,
        )

    # warning が正しく集約された case → 構築可能
    ok_construction = PerRunSmokeDoDResult(
        items=items_w_inc,
        overall_evidence_class="warning",
        observed_failure_modes=frozenset(),
        smoke_report_schema_version=SMOKE_REPORT_SCHEMA_VERSION,
    )
    assert ok_construction.overall_evidence_class == "warning"


def test_cross_run_dod_result_dod8() -> None:
    """F24: item.dod_id != 'DoD8' → ValueError."""
    bad_item = SmokeDoDItem(
        dod_id="DoD8",  # 正しい値で構築
        scope="cross_run",
        synthesis_text="t",
        check_function_name="f",
        status="ok",
        detail="d",
    )
    # CrossRunSmokeDoDResult 自体は item.dod_id が "DoD8" であることを要求。
    # SmokeDoDItem 側で scope/dod_id 整合は既に enforce 済なので、
    # ここでは CrossRunSmokeDoDResult が cross-run scope を要求することを確認する.
    bad_per_run = SmokeDoDItem(
        dod_id="DoD1",
        scope="per_run",
        synthesis_text="t",
        check_function_name="f",
        status="ok",
        detail="d",
    )
    with pytest.raises(ValueError, match="cross_run"):
        CrossRunSmokeDoDResult(
            item=bad_per_run,
            observed_failure_modes=frozenset(),
            smoke_report_schema_version=SMOKE_REPORT_SCHEMA_VERSION,
        )
    # happy case
    ok = CrossRunSmokeDoDResult(
        item=bad_item,
        observed_failure_modes=frozenset(),
        smoke_report_schema_version=SMOKE_REPORT_SCHEMA_VERSION,
    )
    assert ok.item.dod_id == "DoD8"


def test_smoke_dod_item_no_numeric_field() -> None:
    """F25 (T073/T074 SSOT 継承): SmokeDoDItem に numeric field 不在."""
    field_types = {f.name: f.type for f in dataclasses.fields(SmokeDoDItem)}
    # 値が Decimal / int / float 型注釈で含まれていないこと (string repr 確認)
    forbidden_type_tokens = ("Decimal", "int", "float")
    for fname, ftype in field_types.items():
        type_str = str(ftype)
        for tok in forbidden_type_tokens:
            assert tok not in type_str, (
                f"SmokeDoDItem.{fname} contains forbidden numeric type token "
                f"{tok!r}: {type_str!r}"
            )


# ---------------------------------------------------------------------------
# F26-F30: classify_smoke_outcome / decide_release_action tests (Round R3
# [C1] [S2])
# ---------------------------------------------------------------------------


def test_classify_warning_with_inconclusive() -> None:
    """F26 (Round R3 [C1]): per_run='warning' + cross_run='inconclusive' →
    severity='warning'、 has_inconclusive=True."""
    statuses: tuple[EvidenceClass, ...] = (
        "warning",
        "ok",
        "ok",
        "ok",
        "ok",
        "ok",
        "ok",
    )
    pr = _make_per_run_result(statuses=statuses, overall="warning")
    cr = _make_cross_run_result(status="inconclusive", detail="data short")
    five = _make_five_run_result(cross_run=cr, overall="warning")
    classification = classify_smoke_outcome(
        per_run_results=(pr,), cross_run_result=cr, five_run_result=five
    )
    assert classification.overall_severity == "warning"
    assert classification.aggregate_evidence.severity == "warning"
    assert classification.aggregate_evidence.has_inconclusive is True
    sources = {
        r.source for r in classification.aggregate_evidence.inconclusive_reasons
    }
    assert "DoD8" in sources


def test_decide_inconclusive_priority() -> None:
    """F27 (Round R3 [C1]): warning + has_inconclusive → hold_for_review."""
    classification = SmokeOutcomeClassification(
        aggregate_evidence=AggregateEvidence(
            severity="warning",
            has_inconclusive=True,
            inconclusive_reasons=(
                InconclusiveReason(
                    source="DoD3", reason_code="x", message="m"
                ),
            ),
        ),
        observed_failure_modes=frozenset(),
        per_run_severity="warning",
        cross_run_severity="ok",
        overall_severity="warning",
    )
    rec = decide_release_action(classification=classification)
    assert rec.review_hint == "hold_for_review"
    assert rec.requires_manual_review is True


def test_decide_priority_hard_fail() -> None:
    """F28: severity='hard_fail' → 'hold_for_review'."""
    classification = SmokeOutcomeClassification(
        aggregate_evidence=AggregateEvidence(
            severity="hard_fail",
            has_inconclusive=False,
            inconclusive_reasons=(),
        ),
        observed_failure_modes=frozenset(),
        per_run_severity="hard_fail",
        cross_run_severity="ok",
        overall_severity="hard_fail",
    )
    rec = decide_release_action(classification=classification)
    assert rec.review_hint == "hold_for_review"
    assert rec.requires_manual_review is True


def test_decide_priority_fm_observed() -> None:
    """F29: severity='ok' + observed_fms 非空 → 'hold_for_review'."""
    classification = SmokeOutcomeClassification(
        aggregate_evidence=AggregateEvidence(
            severity="ok", has_inconclusive=False, inconclusive_reasons=()
        ),
        observed_failure_modes=frozenset({"FM2"}),
        per_run_severity="ok",
        cross_run_severity="ok",
        overall_severity="ok",
    )
    rec = decide_release_action(classification=classification)
    assert rec.review_hint == "hold_for_review"
    assert rec.requires_manual_review is True


def test_decide_no_blocker_observed() -> None:
    """F30: severity='ok' + observed_fms 空 + has_inconclusive=False →
    'no_blocker_observed'."""
    classification = SmokeOutcomeClassification(
        aggregate_evidence=AggregateEvidence(
            severity="ok", has_inconclusive=False, inconclusive_reasons=()
        ),
        observed_failure_modes=frozenset(),
        per_run_severity="ok",
        cross_run_severity="ok",
        overall_severity="ok",
    )
    rec = decide_release_action(classification=classification)
    assert rec.review_hint == "no_blocker_observed"
    assert rec.requires_manual_review is False


def test_decide_unexpected_severity_fail_closed() -> None:
    """F30c (Round 1 Codex S-01): severity が "hard_fail" / "warning" / "ok"
    以外 (= "inconclusive" 等の外部不整合入力) → 'hold_for_review' に倒す
    (fail-closed)."""
    # AggregateEvidence 経由で severity="inconclusive" を構築
    classification = SmokeOutcomeClassification(
        aggregate_evidence=AggregateEvidence(
            severity="inconclusive",
            has_inconclusive=True,
            inconclusive_reasons=(
                InconclusiveReason(
                    source="DoD3", reason_code="x", message="m"
                ),
            ),
        ),
        observed_failure_modes=frozenset(),
        per_run_severity="ok",
        cross_run_severity="ok",
        overall_severity="inconclusive",
    )
    rec = decide_release_action(classification=classification)
    assert rec.review_hint == "hold_for_review"
    assert rec.requires_manual_review is True


def test_decide_warning_only_hold_for_delay() -> None:
    """F30b: warning level + FM 不在 + inconclusive 不在 → 'hold_for_delay'."""
    classification = SmokeOutcomeClassification(
        aggregate_evidence=AggregateEvidence(
            severity="warning",
            has_inconclusive=False,
            inconclusive_reasons=(),
        ),
        observed_failure_modes=frozenset(),
        per_run_severity="warning",
        cross_run_severity="ok",
        overall_severity="warning",
    )
    rec = decide_release_action(classification=classification)
    assert rec.review_hint == "hold_for_delay"
    assert rec.requires_manual_review is False


def test_classification_invariant_severity_match() -> None:
    """F26b (Round D1 [C1]): overall_severity != aggregate_evidence.severity →
    ValueError."""
    with pytest.raises(ValueError, match="overall_severity"):
        SmokeOutcomeClassification(
            aggregate_evidence=AggregateEvidence(
                severity="ok",
                has_inconclusive=False,
                inconclusive_reasons=(),
            ),
            observed_failure_modes=frozenset(),
            per_run_severity="ok",
            cross_run_severity="ok",
            overall_severity="warning",
        )


# F26c (Round D2 [W4]): review_hint authority - no auto release execution
_FORBIDDEN_AUTO_RELEASE_NAMES = (
    "auto_proceed",
    "execute_release",
    "trigger_release",
    "commit_switchover",
    "auto_switchover",
    "perform_release",
    "perform_switchover",
)


def test_classification_review_hint_authority() -> None:
    """F26c (Round D2 [W4]): review_hint='no_blocker_observed' 取得後、
    caller が自動切替実行可能なメソッドが T075 module に存在しないこと確認.

    AST FunctionDef.name + public method name + ast.Call.func.id を検査
    (raw grep 禁止、 docstring/comment は AST で除外).
    """
    tree = _build_module_ast()

    # Function / method definitions
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert node.name not in _FORBIDDEN_AUTO_RELEASE_NAMES, (
                f"T075 module defines forbidden auto-release function "
                f"{node.name!r} at line {node.lineno}"
            )

    # Call targets (= ast.Call.func.id / .attr)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                assert func.id not in _FORBIDDEN_AUTO_RELEASE_NAMES, (
                    f"T075 module calls forbidden auto-release function "
                    f"{func.id!r} at line {node.lineno}"
                )
            elif isinstance(func, ast.Attribute):
                assert func.attr not in _FORBIDDEN_AUTO_RELEASE_NAMES, (
                    f"T075 module calls forbidden auto-release method "
                    f"{func.attr!r} at line {node.lineno}"
                )


# ---------------------------------------------------------------------------
# F31-F33: select_rollback_relevant_failure_modes tests (Round 4 [W1])
# ---------------------------------------------------------------------------


def test_select_rollback_phase1_raises() -> None:
    """F31: Phase 1 では常に NotImplementedError raise."""
    with pytest.raises(NotImplementedError):
        select_rollback_relevant_failure_modes(
            observed=frozenset({"FM1", "FM4"}), policy=object()
        )


def test_select_rollback_message_phase2_only() -> None:
    """F32: error message に 'Phase 2 only' 文字列含む."""
    with pytest.raises(NotImplementedError, match="Phase 2 only"):
        select_rollback_relevant_failure_modes(
            observed=frozenset(), policy=None
        )


def test_select_rollback_docstring_warns() -> None:
    """F33: function docstring に 'do not call in T075' 文字列含む."""
    doc = select_rollback_relevant_failure_modes.__doc__
    assert doc is not None
    # error message にも含まれるが、 docstring も含むことを確認
    assert "do not call in T075" in doc


# ---------------------------------------------------------------------------
# F34-F36 + F38b-F38d: dual-path enforce 4 経路 tests (Round R2 [W5] /
# Round D1 [C2])
# ---------------------------------------------------------------------------

# T075 module 自体が実装する forbidden module substrings (= AST grep 対象)
_T075_FORBIDDEN_MODULES_SUBSTRINGS = (
    "archive",
    "swim_lane",
    "cross_pair",
    "stage_gate",
    "calibrate_gate",
    "calibrate_state",
)
_T075_FORBIDDEN_EXACT_NAMES = (
    "ANCHOR_PAIRS",
    "promote_graduates",
    "mark_graduated",
    "GraduationLane",
    "Tier1Lane",
)
# Round D3 [W4]: case-sensitive substring (= "DST" 大文字)
_T075_FORBIDDEN_SUBSTRINGS = (
    "holiday",
    "DST",
    "observability_flags",
    "stratified",
)


def test_smoke_module_no_existing_module_imports() -> None:
    """F34: T075 module は archive / swim_lane / cross_pair / stage_gate /
    calibrate_gate / calibrate_state を import しない (詳細設計 § 2.3 grep DoD)."""
    tree = _build_module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                for sub in _T075_FORBIDDEN_MODULES_SUBSTRINGS:
                    assert sub not in node.module, (
                        f"T075 module imports forbidden module "
                        f"{node.module!r} (matched {sub!r})"
                    )
            for alias in node.names:
                for sub in _T075_FORBIDDEN_MODULES_SUBSTRINGS:
                    assert sub not in alias.name, (
                        f"T075 module ImportFrom alias {alias.name!r} "
                        f"matched {sub!r}"
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for sub in _T075_FORBIDDEN_MODULES_SUBSTRINGS:
                    assert sub not in alias.name, (
                        f"T075 module Import {alias.name!r} matched {sub!r}"
                    )


def test_smoke_module_no_collider_bias_references() -> None:
    """F35 (collider bias non-goal): observability_flags / holiday / DST /
    stratified 参照なし (詳細設計 § 2.3 / § 1.4)."""
    tree = _build_module_ast()
    docstring_ids = _docstring_node_ids(tree)

    def _check(token: str, context: str) -> None:
        assert token not in _T075_FORBIDDEN_EXACT_NAMES, (
            f"T075 module references forbidden exact name {token!r} "
            f"({context})"
        )
        for sub in _T075_FORBIDDEN_SUBSTRINGS:
            assert sub not in token, (
                f"T075 module references identifier containing {sub!r} "
                f"({context}): {token!r}"
            )

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            _check(node.id, f"Name at line {node.lineno}")
        elif isinstance(node, ast.Attribute):
            _check(node.attr, f"Attribute at line {node.lineno}")

    # string literal、 docstring 除外
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstring_ids:
                continue
            _check(node.value, f"string literal at line {node.lineno}")


def test_smoke_module_no_runtime_import_from_src() -> None:
    """F36 (詳細設計 § 8.3): T075 module は src/ 配下の他 module から import
    されていない (= 純ライブラリ、 Phase 1 evidence collection only)."""
    src_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
                "from src.alpha_factory.smoke import" in content
                or "import src.alpha_factory.smoke" in content
            ):
                referencing_files.append(fpath)
    assert not referencing_files, (
        f"T075 smoke.py is imported from src/ (expected 0 files): "
        f"{referencing_files}"
    )


def _repo_root() -> str:
    """tests/alpha_factory/ から repository root の絶対 path."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(here))


def test_smoke_module_no_runtime_import_from_scripts() -> None:
    """F35 (Round 1 Codex W-01 / 詳細設計 § 5.1 / § 3.10):
    scripts/**/*.py を AST 解析、 src.alpha_factory.smoke を import する経路
    0 件 (= Phase 1 純ライブラリ、 dual-path enforce route='scripts').

    parser_failure_mode='fail_closed' (= syntax error / 不正な scripts は test
    FAIL で見逃さない).
    """
    repo_root = _repo_root()
    scripts_dir = os.path.join(repo_root, "scripts")
    if not os.path.isdir(scripts_dir):
        pytest.skip("scripts/ directory not present (Phase 1 設計判断値)")

    referencing_files: list[str] = []
    parse_failures: list[tuple[str, str]] = []
    for dirpath, _dirnames, filenames in os.walk(scripts_dir):
        # __pycache__ は allowlist (Round R3 [S3])
        if "__pycache__" in dirpath:
            continue
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            with open(fpath, encoding="utf-8") as f:
                content = f.read()
            try:
                tree = ast.parse(content, filename=fpath)
            except SyntaxError as e:
                # fail_closed: parse 失敗を test FAIL に倒す
                parse_failures.append((fpath, str(e)))
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    # Round 2 Codex S-01 改善: alias.name に依存せず module path
                    # ".smoke" 終端 + module path "src.alpha_factory" / "alpha_factory"
                    # を堅く検出する.
                    mod = node.module or ""
                    if mod == "src.alpha_factory.smoke" or mod == "alpha_factory.smoke":
                        referencing_files.append(fpath)
                        continue
                    # `from src.alpha_factory import smoke` 形の検出
                    if mod in ("src.alpha_factory", "alpha_factory"):
                        for alias in node.names:
                            if alias.name == "smoke":
                                referencing_files.append(fpath)
                                break
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in (
                            "src.alpha_factory.smoke",
                            "alpha_factory.smoke",
                        ):
                            referencing_files.append(fpath)
                            break

    assert not parse_failures, (
        f"scripts/**/*.py parse failures (fail_closed): {parse_failures}"
    )
    assert not referencing_files, (
        f"scripts/ 配下から src.alpha_factory.smoke を import する経路 "
        f"(expected 0 files for Phase 1 純ライブラリ): {referencing_files}"
    )


def test_smoke_module_no_config_yaml_keys() -> None:
    """F36 (Round 1 Codex W-01 / 詳細設計 § 5.1 / § 3.10):
    config/**/*.yaml / *.yml を yaml parse、 smoke 関連 key 0 件
    (= Phase 1 純ライブラリ、 dual-path enforce route='config_yaml').

    parser_failure_mode='fail_closed' (= 不正 yaml は test FAIL).
    """
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        pytest.skip("PyYAML not available")

    repo_root = _repo_root()
    config_dir = os.path.join(repo_root, "config")
    if not os.path.isdir(config_dir):
        pytest.skip("config/ directory not present")

    forbidden_keys = ("smoke", "bigbang_cleanup", "release_action_recommendation")
    referencing_files: list[tuple[str, str]] = []
    parse_failures: list[tuple[str, str]] = []

    def _walk(node: object, path: str, src_file: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                key_str = str(k)
                cur_path = f"{path}.{key_str}" if path else key_str
                for fk in forbidden_keys:
                    if fk in key_str.lower():
                        referencing_files.append((src_file, cur_path))
                _walk(v, cur_path, src_file)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                _walk(item, f"{path}[{i}]", src_file)

    for dirpath, _dirnames, filenames in os.walk(config_dir):
        if "__pycache__" in dirpath:
            continue
        for fname in filenames:
            if not (fname.endswith(".yaml") or fname.endswith(".yml")):
                continue
            fpath = os.path.join(dirpath, fname)
            with open(fpath, encoding="utf-8") as f:
                content = f.read()
            try:
                doc = yaml.safe_load(content)
            except yaml.YAMLError as e:
                parse_failures.append((fpath, str(e)))
                continue
            _walk(doc, "", fpath)

    assert not parse_failures, (
        f"config/**/*.yaml parse failures (fail_closed): {parse_failures}"
    )
    assert not referencing_files, (
        f"config/ 配下に T075 smoke 関連 key が存在 (Phase 1 で 0 件期待、 "
        f"切替は Phase 2): {referencing_files}"
    )


def test_dual_path_enforce_targets_ssot_4_routes() -> None:
    """F37 (Round D1 [C2] / Round D2 [W1] [S3]): DUAL_PATH_ENFORCE_TARGETS
    の 4 経路 SSOT 確認."""
    expected = {"source_import", "scripts", "config_yaml", "docs_runbook"}
    assert set(DUAL_PATH_ENFORCE_TARGETS.keys()) == expected
    for spec in DUAL_PATH_ENFORCE_TARGETS.values():
        assert "globs" in spec
        assert "method" in spec
        assert "parser_failure_mode" in spec
        assert "severity" in spec


def test_dual_path_enforce_parser_failure_fail_closed() -> None:
    """F38b (Round D1 [C2]): source / scripts / config_yaml の parser_failure_mode
    は fail_closed."""
    for route in ("source_import", "scripts", "config_yaml"):
        assert (
            DUAL_PATH_ENFORCE_TARGETS[route]["parser_failure_mode"]
            == "fail_closed"
        )
        assert DUAL_PATH_ENFORCE_TARGETS[route]["severity"] == "fail"


def test_dual_path_enforce_docs_runbook_fail_open() -> None:
    """F38c (Round R3 [S3]): docs/runbook の parser_failure_mode は fail_open、
    severity は warning."""
    spec = DUAL_PATH_ENFORCE_TARGETS["docs_runbook"]
    assert spec["parser_failure_mode"] == "fail_open"
    assert spec["severity"] == "warning"
    assert spec["method"] == "substring_match"


def test_dual_path_allowlist_includes_required() -> None:
    """F38d-1 (Round R3 [S3]): allowlist に docs/historical / devnotes / tests
    が含まれる."""
    required = ("docs/historical/**", "devnotes/**", "tests/**")
    for r in required:
        assert r in DUAL_PATH_ENFORCE_ALLOWLIST


def test_dual_path_glob_boundary_tests_prod_not_allowlisted() -> None:
    """F38d-2 (Round D2 [W2]): tests-prod/** は allowlist に含まれない
    (= Phase 1 では存在しない前提、 設計判断値)."""
    for entry in DUAL_PATH_ENFORCE_ALLOWLIST:
        assert "tests-prod" not in entry, (
            f"tests-prod must NOT be in DUAL_PATH_ENFORCE_ALLOWLIST "
            f"(Phase 1 設計判断値、 Round D2 [W2]), got {entry!r}"
        )


def test_dual_path_path_normalization_posix_separator() -> None:
    """F38d-3 (Round D2 [W1] [S3]): 全 path は POSIX separator のみ."""
    all_globs: list[str] = []
    for spec in DUAL_PATH_ENFORCE_TARGETS.values():
        all_globs.extend(spec["globs"])  # type: ignore[arg-type]
    for g in all_globs + list(DUAL_PATH_ENFORCE_ALLOWLIST):
        assert "\\" not in g, (
            f"Windows backslash not allowed in path glob, got {g!r}"
        )
        # path normalization rule: repository-root relative (= no leading "/")
        assert not g.startswith("/"), (
            f"path glob must be repository-root relative (no leading '/'), "
            f"got {g!r}"
        )


# ---------------------------------------------------------------------------
# F39-F40: BigBangCleanupReport tests
# ---------------------------------------------------------------------------


def test_bigbang_cleanup_report_schema_version() -> None:
    """F39: schema_version != '1.0.0' → ValueError."""
    five_runs_pr = tuple(_make_per_run_result() for _ in range(SMOKE_RUNS_REQUIRED))
    cr = _make_cross_run_result()
    five = _make_five_run_result(cross_run=cr)
    classification = SmokeOutcomeClassification(
        aggregate_evidence=AggregateEvidence(
            severity="ok", has_inconclusive=False, inconclusive_reasons=()
        ),
        observed_failure_modes=frozenset(),
        per_run_severity="ok",
        cross_run_severity="ok",
        overall_severity="ok",
    )
    rec = decide_release_action(classification=classification)
    with pytest.raises(ValueError, match="report_schema_version"):
        BigBangCleanupReport(
            deletion_targets=(),
            per_run_smoke_results=five_runs_pr,
            cross_run_smoke_result=cr,
            five_run_consistency_result=five,
            outcome_classification=classification,
            release_action_recommendation=rec,
            report_schema_version="9.9.9",
        )


def test_bigbang_cleanup_report_runs_count() -> None:
    """F40: per_run_smoke_results len != 5 → ValueError."""
    four_runs_pr = tuple(_make_per_run_result() for _ in range(4))
    cr = _make_cross_run_result()
    five = _make_five_run_result(cross_run=cr)
    classification = SmokeOutcomeClassification(
        aggregate_evidence=AggregateEvidence(
            severity="ok", has_inconclusive=False, inconclusive_reasons=()
        ),
        observed_failure_modes=frozenset(),
        per_run_severity="ok",
        cross_run_severity="ok",
        overall_severity="ok",
    )
    rec = decide_release_action(classification=classification)
    with pytest.raises(ValueError, match="per_run_smoke_results"):
        BigBangCleanupReport(
            deletion_targets=(),
            per_run_smoke_results=four_runs_pr,
            cross_run_smoke_result=cr,
            five_run_consistency_result=five,
            outcome_classification=classification,
            release_action_recommendation=rec,
            report_schema_version=SMOKE_REPORT_SCHEMA_VERSION,
        )


def test_bigbang_cleanup_report_happy() -> None:
    """F40b: 正常構築."""
    five_runs_pr = tuple(_make_per_run_result() for _ in range(SMOKE_RUNS_REQUIRED))
    cr = _make_cross_run_result()
    five = _make_five_run_result(cross_run=cr)
    classification = SmokeOutcomeClassification(
        aggregate_evidence=AggregateEvidence(
            severity="ok", has_inconclusive=False, inconclusive_reasons=()
        ),
        observed_failure_modes=frozenset(),
        per_run_severity="ok",
        cross_run_severity="ok",
        overall_severity="ok",
    )
    rec = decide_release_action(classification=classification)
    report = BigBangCleanupReport(
        deletion_targets=(),
        per_run_smoke_results=five_runs_pr,
        cross_run_smoke_result=cr,
        five_run_consistency_result=five,
        outcome_classification=classification,
        release_action_recommendation=rec,
        report_schema_version=SMOKE_REPORT_SCHEMA_VERSION,
    )
    assert len(report.per_run_smoke_results) == SMOKE_RUNS_REQUIRED


# ---------------------------------------------------------------------------
# happy path: end-to-end classify -> decide
# ---------------------------------------------------------------------------


def test_classify_and_decide_happy_path() -> None:
    """end-to-end happy path (= 全 ok / FM 不在 / inconclusive 不在 →
    no_blocker_observed)."""
    pr_results = tuple(_make_per_run_result() for _ in range(SMOKE_RUNS_REQUIRED))
    cr = _make_cross_run_result()
    five = _make_five_run_result(cross_run=cr)
    classification = classify_smoke_outcome(
        per_run_results=pr_results,
        cross_run_result=cr,
        five_run_result=five,
    )
    assert classification.overall_severity == "ok"
    assert classification.aggregate_evidence.has_inconclusive is False
    assert classification.observed_failure_modes == frozenset()
    rec = decide_release_action(classification=classification)
    assert rec.review_hint == "no_blocker_observed"


def test_classify_dedup_inconclusive_reasons() -> None:
    """重複 InconclusiveReason は source + reason_code + message の 3 軸で dedup
    (Round D1 [W2] / [S3])."""
    # 同 dod_id で 2 つの per_run に inconclusive を入れて (= 同 source / reason_code / message)
    statuses_a: tuple[EvidenceClass, ...] = (
        "inconclusive",
        "ok",
        "ok",
        "ok",
        "ok",
        "ok",
        "ok",
    )
    # overall は helper が items.status max で自動算出 (= "inconclusive")
    pr_a = _make_per_run_result(statuses=statuses_a)
    pr_b = _make_per_run_result(statuses=statuses_a)
    cr = _make_cross_run_result()
    five = _make_five_run_result(cross_run=cr)
    classification = classify_smoke_outcome(
        per_run_results=(pr_a, pr_b),
        cross_run_result=cr,
        five_run_result=five,
    )
    # 同一 (source=DoD1, reason_code=dod_inconclusive, message=d1) の組は 1 つに
    sources = [
        (r.source, r.reason_code, r.message)
        for r in classification.aggregate_evidence.inconclusive_reasons
    ]
    assert len(sources) == len(set(sources)), (
        f"inconclusive_reasons must be deduplicated, got {sources}"
    )


def test_observability_projection_typed_fields() -> None:
    """typed projection (Round R1 [C5]): 各 *_class field が EvidenceClass 4 値."""
    proj = SmokeObservabilityProjection(
        ab_divergence_class="warning",
        epoch_consistency_class="ok",
        warmstart_shortfall_class="hard_fail",
        bypass_ratio_class="inconclusive",
        session_entropy_class="ok",
        dataset_epoch_id_present=True,
        report_ref="run-1",
    )
    assert proj.ab_divergence_class == "warning"


def test_observability_projection_report_ref_non_empty() -> None:
    """SmokeObservabilityProjection.report_ref non-empty 検証."""
    with pytest.raises(ValueError, match="report_ref"):
        SmokeObservabilityProjection(
            ab_divergence_class="ok",
            epoch_consistency_class="ok",
            warmstart_shortfall_class="ok",
            bypass_ratio_class="ok",
            session_entropy_class="ok",
            dataset_epoch_id_present=True,
            report_ref="",
        )


def test_cross_run_observability_projection_typed() -> None:
    """CrossRunSmokeObservabilityProjection (Round R3 [W2])."""
    proj = CrossRunSmokeObservabilityProjection(
        cross_run_epoch_pollution_class="ok",
        report_ref="cross-run",
    )
    assert proj.cross_run_epoch_pollution_class == "ok"
    with pytest.raises(ValueError, match="report_ref"):
        CrossRunSmokeObservabilityProjection(
            cross_run_epoch_pollution_class="ok",
            report_ref="",
        )


def test_smoke_run_summary_validation() -> None:
    """SmokeRunSummary の必須 field 検証."""
    with pytest.raises(ValueError, match="run_id"):
        SmokeRunSummary(
            run_id="",
            dataset_epoch_id="e1",
            run_succeeded=True,
            per_run_dod=_make_per_run_result(),
            observability_projection=_make_observability_projection(),
            observed_failure_modes=frozenset(),
        )
    with pytest.raises(ValueError, match="dataset_epoch_id"):
        SmokeRunSummary(
            run_id="r1",
            dataset_epoch_id="",
            run_succeeded=True,
            per_run_dod=_make_per_run_result(),
            observability_projection=_make_observability_projection(),
            observed_failure_modes=frozenset(),
        )


def test_five_run_consistency_result_runs_count() -> None:
    """FiveRunConsistencyResult.runs len != 5 → ValueError."""
    runs = tuple(_make_run_summary(f"r{i + 1}") for i in range(4))
    cr = _make_cross_run_result()
    with pytest.raises(ValueError, match="runs"):
        FiveRunConsistencyResult(
            runs=runs,
            cross_run_dod=cr,
            epoch_pollution_observed=False,
            config_drift_observed=False,
            schema_version_consistent=True,
            overall_severity="ok",
        )


def test_release_action_rationale_non_empty() -> None:
    """ReleaseActionRecommendation.rationale non-empty 検証."""
    classification = SmokeOutcomeClassification(
        aggregate_evidence=AggregateEvidence(
            severity="ok", has_inconclusive=False, inconclusive_reasons=()
        ),
        observed_failure_modes=frozenset(),
        per_run_severity="ok",
        cross_run_severity="ok",
        overall_severity="ok",
    )
    with pytest.raises(ValueError, match="rationale"):
        ReleaseActionRecommendation(
            outcome_classification=classification,
            review_hint="no_blocker_observed",
            rationale="",
            requires_manual_review=False,
        )


def test_classify_severity_max_aggregation() -> None:
    """severity 集約は 3 値階層 (= hard_fail > warning > ok、 inconclusive は別軸)."""
    pr_warning = _make_per_run_result(
        statuses=("warning", "ok", "ok", "ok", "ok", "ok", "ok"),
        overall="warning",
    )
    pr_hard_fail = _make_per_run_result(
        statuses=("hard_fail", "ok", "ok", "ok", "ok", "ok", "ok"),
        overall="hard_fail",
    )
    cr = _make_cross_run_result()
    five = _make_five_run_result(cross_run=cr)
    classification = classify_smoke_outcome(
        per_run_results=(pr_warning, pr_hard_fail),
        cross_run_result=cr,
        five_run_result=five,
    )
    # max(warning, hard_fail, ok) → hard_fail
    assert classification.overall_severity == "hard_fail"


def test_classify_inconclusive_does_not_promote_severity() -> None:
    """C8 規範: per_run inconclusive のみで severity が hard_fail に昇格しない
    (= severity 軸では ok、 has_inconclusive で別軸保持)."""
    # overall は helper 自動 ("inconclusive")
    pr_inc = _make_per_run_result(
        statuses=("inconclusive", "ok", "ok", "ok", "ok", "ok", "ok"),
    )
    cr = _make_cross_run_result()
    five = _make_five_run_result(cross_run=cr)
    classification = classify_smoke_outcome(
        per_run_results=(pr_inc,),
        cross_run_result=cr,
        five_run_result=five,
    )
    # severity 軸では ok (= inconclusive は別軸)
    assert classification.overall_severity == "ok"
    # has_inconclusive は True
    assert classification.aggregate_evidence.has_inconclusive is True
    # decide_release_action では inconclusive priority で hold_for_review
    rec = decide_release_action(classification=classification)
    assert rec.review_hint == "hold_for_review"


def test_classify_observed_failure_modes_union() -> None:
    """observed_failure_modes は per_run 全 ∪ cross_run の和集合."""
    pr_a = _make_per_run_result(observed_fms=frozenset({"FM1"}))
    pr_b = _make_per_run_result(observed_fms=frozenset({"FM2", "FM3"}))
    cr = _make_cross_run_result(observed_fms=frozenset({"FM4"}))
    five = _make_five_run_result(cross_run=cr)
    classification = classify_smoke_outcome(
        per_run_results=(pr_a, pr_b),
        cross_run_result=cr,
        five_run_result=five,
    )
    assert classification.observed_failure_modes == frozenset(
        {"FM1", "FM2", "FM3", "FM4"}
    )
