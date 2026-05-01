"""Big-bang cleanup + smoke (T075 cascade port v2 Phase 1 純ライブラリ).

概念設計 § 5 全 SSOT 群 + 詳細設計 § 3 / § 4 の擬似コードを実装する。
runtime 未組込 (= 単体 test のみ)、 Phase 2 で T071 RunObservabilityReport.smoke
field 配線時に runtime に組込予定 (申し送り).

責務 (詳細設計 § 0):
    - synthesis local projection 限定 (= 親 SSOT を T075 module で再定義しない、
      FM1-FM5 / new_cascade 採用しない / DoD 機械検証形式 等は synthesis Round 22
      改訂 blocked-by)
    - DoD 二層分離 (= PerRunSmokeDoDResult = DoD1-DoD7 / CrossRunSmokeDoDResult
      = DoD8)
    - EvidenceClass threshold-free 4 値 (= 数値 threshold を T075 で SSOT 化しない)
    - classify_smoke_outcome (事実認定) と decide_release_action (運用判断 hint)
      を 2 段階分離
    - AggregateEvidence 二軸保持 (= severity 4 値 + has_inconclusive)
    - review_hint 3 値 (no_blocker_observed / hold_for_delay / hold_for_review)
    - typed projection (SmokeObservabilityProjection /
      CrossRunSmokeObservabilityProjection)
    - DeletionTarget / MigrationTarget 分離
    - dual-path operational definition (= 並走 = runtime 到達 OR feature flag OR
      二経路出力、 同居 = source tree のみ)
    - dual-path enforce 4 経路 + path normalization (PurePosixPath +
      repository-root relative + symlink follow なし)

collider bias non-goal (詳細設計 § 1.4 / 概念設計 § 7.3):
    T075 module は collider bias を判定しない. holiday_markets /
    dst_transition_markets / schedule_status の stratified audit / 因果解釈 /
    比率差判定は **Phase 2 で T071 RunObservabilityReport 経由** で出力する責務.
    T075 module 内では observability_flags を参照しない (= AST grep DoD で確認、
    詳細設計 § 2.3 の 10 検索語).

scaffold 規範 (T072-T074 SSOT 継承):
    - SmokeDoDItem は status + detail (= 文字列) のみ、 数値 field なし
    - 既存 src は touch しない (= 純ライブラリ)
    - select_rollback_relevant_failure_modes は Phase 1 で NotImplementedError
      raise、 Phase 2 別 TODO で実装

Phase 2 申し送り (詳細設計 § 1.3 / § 9.2):
    - T071 RunObservabilityReport に smoke: BigBangCleanupReport field 追加
    - run_ga.py 唯一の SSOT adapter として archive 集計 → SmokeRunSummary 構築
    - synthesis Round 22 改訂候補 5 件 (= new_cascade / FM SSOT / DoD 分離 /
      threshold / stable clause anchor)
    - select_rollback_relevant_failure_modes 実装、 数値 threshold 確定
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, Protocol, runtime_checkable

__all__ = [
    "CROSS_RUN_DOD_ITEMS_COUNT",
    "DUAL_PATH_ENFORCE_ALLOWLIST",
    "DUAL_PATH_ENFORCE_TARGETS",
    "PER_RUN_DOD_ITEMS_COUNT",
    "SMOKE_REPORT_SCHEMA_VERSION",
    "SMOKE_RUNS_REQUIRED",
    "AggregateEvidence",
    "BigBangCleanupReport",
    "CleanupCategorySlug",
    "CrossRunSmokeDoDResult",
    "CrossRunSmokeObservabilityProjection",
    "DeletionTarget",
    "DeletionTargetCategory",
    "DoDIdCrossRun",
    "DoDIdPerRun",
    "EvidenceClass",
    "EvidenceClassifierProtocol",
    "FailureModeKind",
    "FiveRunConsistencyResult",
    "InconclusiveReason",
    "MigrationMode",
    "MigrationTarget",
    "PerRunSmokeDoDResult",
    "ReleaseActionRecommendation",
    "RemovalMode",
    "Severity",
    "SmokeDoDItem",
    "SmokeObservabilityProjection",
    "SmokeOutcomeClassification",
    "SmokeRunSummary",
    "classify_smoke_outcome",
    "decide_release_action",
    "select_rollback_relevant_failure_modes",
]


# ---------------------------------------------------------------------------
# Status Literal (詳細設計 § 3.1)
# ---------------------------------------------------------------------------


EvidenceClass = Literal["hard_fail", "warning", "inconclusive", "ok"]
"""threshold-free 4 値 (= 数値 threshold を T075 module で SSOT 化しない)."""

Severity = Literal["hard_fail", "warning", "inconclusive", "ok"]
"""EvidenceClass と同型 4 値 (Round R2 [C1] inconclusive 型落ち排除)."""

FailureModeKind = Literal["FM1", "FM2", "FM3", "FM4", "FM5"]
"""synthesis § 16 enum 5 値 (= 数値 threshold は T075 範囲外、 別 TODO で確定)."""

DoDIdPerRun = Literal["DoD1", "DoD2", "DoD3", "DoD4", "DoD5", "DoD6", "DoD7"]
"""1 Run 単位 DoD (synthesis § 18.3 + Round R1 [C2] 二層分離)."""

DoDIdCrossRun = Literal["DoD8"]
"""5 Run 集約単位 DoD (synthesis § 18.3 + Round R1 [C2] 二層分離)."""

RemovalMode = Literal["git_rm", "yaml_key_delete"]
"""削除 mode (Round R2 [W4] cleanup 専用、 migrate は MigrationMode に分離)."""

MigrationMode = Literal["yaml_value_replace"]
"""移行 mode (Round R2 [W4] cleanup と分離、 yaml 値の更新)."""

CleanupCategorySlug = Literal["cleanup", "config", "script", "module", "schema"]
"""change_group_id の category slug 5 値 (Round D1 [W1] / Round D2 [W3])."""


# ---------------------------------------------------------------------------
# 定数 (詳細設計 § 3.1)
# ---------------------------------------------------------------------------

SMOKE_RUNS_REQUIRED: Final[int] = 5
"""synthesis § 18.3: 5 Run 連続検証."""

PER_RUN_DOD_ITEMS_COUNT: Final[int] = 7
"""DoD1-DoD7 (per-run)."""

CROSS_RUN_DOD_ITEMS_COUNT: Final[int] = 1
"""DoD8 (cross-run)."""

SMOKE_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"
"""BigBangCleanupReport の schema version (Phase 2 で MINOR bump 予定)."""


# EvidenceClass 順序 (Round R2 [S1]):
#   "hard_fail" > "warning" > "inconclusive" > "ok"
# severity 集約は 3 値階層 (= "hard_fail" / "warning" / "ok")、
# inconclusive は別軸 (= AggregateEvidence.has_inconclusive).
_EVIDENCE_CLASS_ORDER: Final[dict[EvidenceClass, int]] = {
    "hard_fail": 3,
    "warning": 2,
    "inconclusive": 1,
    "ok": 0,
}

# severity 集約用の 3 値 order (= inconclusive を除外した max 集約用).
_SEVERITY_3VALUE_ORDER: Final[dict[Severity, int]] = {
    "hard_fail": 3,
    "warning": 2,
    "ok": 0,
}


def _aggregate_evidence_class(
    statuses: tuple[EvidenceClass, ...],
) -> EvidenceClass:
    """EvidenceClass 4 値の max 集約 (Round R2 [S1] / 詳細設計 § 3.1).

    順序: "hard_fail" > "warning" > "inconclusive" > "ok"
    空入力時は "ok" を返す.
    """
    best_rank = 0
    best_cls: EvidenceClass = "ok"
    found_any = False
    for s in statuses:
        rank = _EVIDENCE_CLASS_ORDER.get(s)
        if rank is None:
            raise ValueError(f"unknown EvidenceClass: {s!r}")
        if not found_any or rank > best_rank:
            best_rank = rank
            best_cls = s
            found_any = True
    return best_cls


# ---------------------------------------------------------------------------
# dual-path enforce 仕様 (詳細設計 § 3.10、 Round D1 [C2] / Round D2 [W1] [S3])
# ---------------------------------------------------------------------------


DUAL_PATH_ENFORCE_TARGETS: Final[dict[str, dict[str, object]]] = {
    "source_import": {
        "globs": ("src/**/*.py",),
        "method": "ast",
        "parser_failure_mode": "fail_closed",
        "severity": "fail",
    },
    "scripts": {
        "globs": ("scripts/**/*.py",),
        "method": "ast",
        "parser_failure_mode": "fail_closed",
        "severity": "fail",
    },
    "config_yaml": {
        "globs": ("config/**/*.yaml", "config/**/*.yml"),
        "method": "yaml_dot_notation",
        "parser_failure_mode": "fail_closed",
        "severity": "fail",
    },
    "docs_runbook": {
        "globs": ("docs/runbook/**/*.md",),
        "method": "substring_match",
        "parser_failure_mode": "fail_open",
        "severity": "warning",
    },
}
"""4 経路の対象パス表 (Round D1 [C2] / Round R3 [S3]).

parser_failure_mode = "fail_closed":
    source / scripts / config: parse 失敗 (= syntax error / 不正 yaml) は
    test FAIL、 fail-open で見逃さない.
parser_failure_mode = "fail_open":
    docs/runbook: markdown 自然言語のため parse 失敗は通常発生せず、
    起きても warning emit only (= raise しない).

path normalization rule (Round D2 [W1] [S3]):
    - すべての path は repository-root relative (= "src/alpha_factory/audit.py"
      形式、 絶対 path 不可)
    - POSIX separator ("/") のみ、 Windows backslash 禁止
    - symlink は follow しない (= os.lstat、 symlink 先は対象外)
    - 正規化は PurePosixPath で実施

Round D2 [W2] tests-prod 取扱:
    `tests-prod/**` は Phase 1 では存在しない前提、 dual-path enforce 対象 globs
    に含めない (= 設計判断値). 将来 production tests directory が必要な場合は
    Round 22 改訂候補で別途検討.
"""


DUAL_PATH_ENFORCE_ALLOWLIST: Final[tuple[str, ...]] = (
    "docs/historical/**",
    "devnotes/**",
    "tests/**",
    ".git/**",
    "**/__pycache__/**",
)
"""dual-path enforce allowlist (Round R3 [S3]).

設計記録 / 履歴 / mock import / git 内部 / bytecode は除外.
"""


# ---------------------------------------------------------------------------
# InconclusiveReason (詳細設計 § 3.2、 Round 4 [W2] structured reason)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InconclusiveReason:
    """inconclusive 観測の構造化 reason (Round 4 [W2] 反映).

    SSOT:
        source: 観測元 (= "DoD3" / "ab_divergence_class" /
            "cross_run_epoch_pollution_class" 等)
        reason_code: 機械可読 code (= "missing_metric" / "classifier_unsupported"
            / "data_too_short" 等)
        message: 人間可読の 1 行説明 (= reviewer 用)

    集計時に source + reason_code + message の 3 軸で重複排除可能 (Round D1 [W2] /
    [S3]、 異なる message が落ちないよう監査可能性確保).
    """

    source: str
    reason_code: str
    message: str

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("InconclusiveReason.source must be non-empty")
        if not self.reason_code:
            raise ValueError("InconclusiveReason.reason_code must be non-empty")


# ---------------------------------------------------------------------------
# AggregateEvidence (詳細設計 § 3.3、 Round R3 [C1] [S1] / Round 4 [S1] invariant)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AggregateEvidence:
    """集約 evidence (= severity と inconclusive を別軸保持).

    SSOT (Round R3 [C1] / Round 4 [S1] invariant):
        severity: Severity (= 4 値、 max 集約は hard_fail / warning / ok の 3 値階層)
        has_inconclusive: bool
        inconclusive_reasons: tuple[InconclusiveReason, ...]
        invariant: has_inconclusive == bool(inconclusive_reasons)

    SmokeOutcomeClassification.aggregate_evidence として保持され、
    decide_release_action で manual review hint を導出する基底値.
    """

    severity: Severity
    has_inconclusive: bool
    inconclusive_reasons: tuple[InconclusiveReason, ...]

    def __post_init__(self) -> None:
        # I-1: severity Literal validity is enforced by static typecheck.
        # I-2: invariant has_inconclusive == bool(inconclusive_reasons)
        if self.has_inconclusive != bool(self.inconclusive_reasons):
            raise ValueError(
                f"AggregateEvidence invariant violated: "
                f"has_inconclusive ({self.has_inconclusive}) != "
                f"bool(inconclusive_reasons) ({bool(self.inconclusive_reasons)})"
            )


# ---------------------------------------------------------------------------
# EvidenceClassifierProtocol (詳細設計 § 3.4、 Round R2 [C3] / Round R3 [W1])
# ---------------------------------------------------------------------------


@runtime_checkable
class EvidenceClassifierProtocol(Protocol):
    """T071 metric → EvidenceClass 分類 Protocol (caller-supplied).

    SSOT:
        T075 module は instance を持たない、 caller (= Phase 2 別 TODO) が実装.

    Conformance test fixture (Round 4 [S2]):
        1. supported_metric_names() の戻り値は frozenset[str]、
           サポートする metric name 集合
        2. supported_metric_names() に **含まれない** metric_name で __call__ →
           "inconclusive" 必須 (= 暗黙 ok 禁止、 fail-closed)
        3. supported_metric_names() に **含まれる** metric_name で __call__ →
           "ok" / "warning" / "hard_fail" / "inconclusive" のいずれも許容
        4. provenance: str は audit log 用、 戻り値の detail に source / version
           等を含めることを推奨

    詳細設計 § 5.2 の mock_evidence_classifier fixture を Phase 2 別 TODO で
    本実装の conformance test として再利用.
    """

    def supported_metric_names(self) -> frozenset[str]:
        """サポートする metric name 集合."""
        ...

    def __call__(
        self,
        metric_value: object,
        metric_name: str,
        provenance: str,
    ) -> tuple[EvidenceClass, str]:
        """metric_value を EvidenceClass + detail に分類.

        Returns:
            (evidence_class, detail) tuple.
        Raises:
            なし (= 未対応 metric_name は inconclusive 返却で fail-closed).
        """
        ...


# ---------------------------------------------------------------------------
# DeletionTarget / MigrationTarget (詳細設計 § 3.5、 Round R3 [W4] / Round 4 [S3])
# ---------------------------------------------------------------------------


# change_group_id pattern (Round 4 [S3] / Round D1 [S2]):
#   "^T075-(cleanup|config|script|module|schema)-[a-z0-9_]+$"
# Literal 5 値の正規表現 + snake_case suffix.
_CHANGE_GROUP_ID_CATEGORIES: Final[frozenset[str]] = frozenset(
    {"cleanup", "config", "script", "module", "schema"}
)


def _validate_change_group_id(change_group_id: str, *, owner: str) -> None:
    """change_group_id の SSOT pattern 検証 (Round 4 [S3] / Round D1 [S2]).

    pattern: "^T075-(cleanup|config|script|module|schema)-[a-z0-9_]+$"
    """
    parts = change_group_id.split("-", 2)
    if len(parts) != 3 or parts[0] != "T075":
        raise ValueError(
            f"{owner}.change_group_id must match "
            f"'^T075-(cleanup|config|script|module|schema)-[a-z0-9_]+$', "
            f"got {change_group_id!r}"
        )
    category, stable_slug = parts[1], parts[2]
    if category not in _CHANGE_GROUP_ID_CATEGORIES:
        raise ValueError(
            f"{owner}.change_group_id category must be one of "
            f"{sorted(_CHANGE_GROUP_ID_CATEGORIES)}, got {category!r}"
        )
    if not stable_slug:
        raise ValueError(
            f"{owner}.change_group_id stable_slug must be non-empty"
        )
    for ch in stable_slug:
        if not (ch.islower() and ch.isascii()) and not (
            ch.isdigit() and ch.isascii()
        ) and ch != "_":
            raise ValueError(
                f"{owner}.change_group_id stable_slug must match "
                f"'^[a-z0-9_]+$', got {stable_slug!r}"
            )


_DELETION_CATEGORIES_SSOT: Final[frozenset[str]] = frozenset(
    {
        "並走機構",
        "旧 config キー",
        "旧 script",
        "全面置換",
    }
)
_SOURCE_SECTIONS_SSOT: Final[frozenset[str]] = frozenset({"12.1", "12.2"})


@dataclass(frozen=True)
class DeletionTarget:
    """削除対象 manifest (詳細設計 § 3.5、 Round R1 [C6] / Round R2 [W3] [W4] /
    Round R3 [W4] / Round 4 [S3]).

    Round 4 [S3] / Round D1 [W1] change_group_id 命名規則:
        "T075-{category_slug}-{stable_slug}"
        category_slug ∈ CleanupCategorySlug
            (= 5 値: cleanup / config / script / module / schema)
        stable_slug は "[a-z0-9_]+" (= snake_case)
        例:
            "T075-cleanup-stage_a_replacement"  (= cleanup category)
            "T075-config-calibrate_v2_migration"  (= config category)
            "T075-script-run_alpha_sieve_archive_integration"  (= script category)
            "T075-module-archive_v1_read_path_removal"  (= module category)
            "T075-schema-archive_parquet_v2"  (= schema category)

    invariant:
        path non-empty
        category ∈ {"並走機構", "旧 config キー", "旧 script", "全面置換"}
        source_section ∈ {"12.1", "12.2"}
        change_group_id matches
            "^T075-(cleanup|config|script|module|schema)-[a-z0-9_]+$"
    """

    path: str
    category: str
    source_section: str
    source_clause_id: str
    source_excerpt_hash: str
    removal_mode: RemovalMode
    owner: str
    change_group_id: str
    supersedes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("DeletionTarget.path must be non-empty")
        if self.category not in _DELETION_CATEGORIES_SSOT:
            raise ValueError(
                f"DeletionTarget.category must be one of "
                f"{sorted(_DELETION_CATEGORIES_SSOT)}, got {self.category!r}"
            )
        if self.source_section not in _SOURCE_SECTIONS_SSOT:
            raise ValueError(
                f"DeletionTarget.source_section must be one of "
                f"{sorted(_SOURCE_SECTIONS_SSOT)}, got {self.source_section!r}"
            )
        if not self.source_clause_id:
            raise ValueError(
                "DeletionTarget.source_clause_id must be non-empty"
            )
        if not self.source_excerpt_hash:
            raise ValueError(
                "DeletionTarget.source_excerpt_hash must be non-empty"
            )
        if not self.owner:
            raise ValueError("DeletionTarget.owner must be non-empty")
        _validate_change_group_id(
            self.change_group_id, owner="DeletionTarget"
        )


@dataclass(frozen=True)
class MigrationTarget:
    """移行対象 manifest (詳細設計 § 3.5、 Round R2 [W4] cleanup と分離).

    cleanup (= path 削除) ではなく value replace (= yaml 値の更新)。
    例: stage_gate.stage_a の旧 schema を新 schema に値変換するケース.
    """

    path: str
    category: str
    source_section: str
    source_clause_id: str
    source_excerpt_hash: str
    migration_mode: MigrationMode
    owner: str
    new_value_reference: str
    change_group_id: str
    supersedes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("MigrationTarget.path must be non-empty")
        if self.category not in _DELETION_CATEGORIES_SSOT:
            raise ValueError(
                f"MigrationTarget.category must be one of "
                f"{sorted(_DELETION_CATEGORIES_SSOT)}, got {self.category!r}"
            )
        if self.source_section not in _SOURCE_SECTIONS_SSOT:
            raise ValueError(
                f"MigrationTarget.source_section must be one of "
                f"{sorted(_SOURCE_SECTIONS_SSOT)}, got {self.source_section!r}"
            )
        if not self.source_clause_id:
            raise ValueError(
                "MigrationTarget.source_clause_id must be non-empty"
            )
        if not self.source_excerpt_hash:
            raise ValueError(
                "MigrationTarget.source_excerpt_hash must be non-empty"
            )
        if not self.owner:
            raise ValueError("MigrationTarget.owner must be non-empty")
        if not self.new_value_reference:
            raise ValueError(
                "MigrationTarget.new_value_reference must be non-empty"
            )
        _validate_change_group_id(
            self.change_group_id, owner="MigrationTarget"
        )


@dataclass(frozen=True)
class DeletionTargetCategory:
    """同一 category の DeletionTarget 集約 (詳細設計 § 3.5)."""

    name: str
    targets: tuple[DeletionTarget, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("DeletionTargetCategory.name must be non-empty")


# ---------------------------------------------------------------------------
# SmokeDoDItem (詳細設計 § 3.6、 Round R2 [W1] scope 追加)
# ---------------------------------------------------------------------------


_PER_RUN_DOD_IDS: Final[frozenset[str]] = frozenset(
    {"DoD1", "DoD2", "DoD3", "DoD4", "DoD5", "DoD6", "DoD7"}
)


@dataclass(frozen=True)
class SmokeDoDItem:
    """smoke DoD 1 項目.

    SSOT (synthesis § 18.3 + Round R1 [C2] 二層 + Round R2 [W1] scope):
        scope = "per_run" → DoD1-DoD7
        scope = "cross_run" → DoD8

    数値 field なし (T073 / T074 SSOT 継承、 detail は文字列のみ).
    """

    dod_id: str
    scope: Literal["per_run", "cross_run"]
    synthesis_text: str
    check_function_name: str
    status: EvidenceClass
    detail: str

    def __post_init__(self) -> None:
        if self.scope == "per_run":
            if self.dod_id not in _PER_RUN_DOD_IDS:
                raise ValueError(
                    f"scope='per_run' requires dod_id ∈ "
                    f"{sorted(_PER_RUN_DOD_IDS)}, got {self.dod_id!r}"
                )
        elif self.scope == "cross_run":
            if self.dod_id != "DoD8":
                raise ValueError(
                    "scope='cross_run' requires dod_id='DoD8', "
                    f"got {self.dod_id!r}"
                )
        else:
            raise ValueError(f"unknown scope: {self.scope!r}")
        if not self.synthesis_text:
            raise ValueError("SmokeDoDItem.synthesis_text must be non-empty")
        if not self.check_function_name:
            raise ValueError(
                "SmokeDoDItem.check_function_name must be non-empty"
            )


# ---------------------------------------------------------------------------
# PerRunSmokeDoDResult / CrossRunSmokeDoDResult (詳細設計 § 3.7、
# Round R1 [C2] 二層分離)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PerRunSmokeDoDResult:
    """1 Run 単位の DoD1-DoD7 集約 (Round R1 [C2] [S2])."""

    items: tuple[SmokeDoDItem, ...]
    overall_evidence_class: EvidenceClass
    observed_failure_modes: frozenset[FailureModeKind]
    smoke_report_schema_version: str

    def __post_init__(self) -> None:
        if len(self.items) != PER_RUN_DOD_ITEMS_COUNT:
            raise ValueError(
                f"PerRunSmokeDoDResult.items must have len == "
                f"{PER_RUN_DOD_ITEMS_COUNT}, got {len(self.items)}"
            )
        seen: set[str] = set()
        for item in self.items:
            if item.scope != "per_run":
                raise ValueError(
                    f"PerRunSmokeDoDResult.items must contain only scope="
                    f"'per_run' items, got {item.scope!r} for "
                    f"{item.dod_id!r}"
                )
            if item.dod_id in seen:
                raise ValueError(
                    f"PerRunSmokeDoDResult.items duplicate dod_id: "
                    f"{item.dod_id!r}"
                )
            seen.add(item.dod_id)
        if seen != _PER_RUN_DOD_IDS:
            raise ValueError(
                f"PerRunSmokeDoDResult.items must cover DoD1-DoD7 exactly, "
                f"got {sorted(seen)}"
            )
        # Round R1 Codex C-01: items.status から overall_evidence_class を再集約
        # して一致 invariant を強制 (= 概念 § 4 / 詳細 § 3.1 _EVIDENCE_CLASS_ORDER
        # 厳格適用、 inconclusive を warning に隠さない).
        expected_overall = _aggregate_evidence_class(
            tuple(item.status for item in self.items)
        )
        if self.overall_evidence_class != expected_overall:
            raise ValueError(
                f"PerRunSmokeDoDResult.overall_evidence_class "
                f"({self.overall_evidence_class!r}) must equal aggregated "
                f"items.status max ({expected_overall!r}, "
                "order: hard_fail > warning > inconclusive > ok)"
            )
        if self.smoke_report_schema_version != SMOKE_REPORT_SCHEMA_VERSION:
            raise ValueError(
                f"smoke_report_schema_version must be "
                f"{SMOKE_REPORT_SCHEMA_VERSION!r}, "
                f"got {self.smoke_report_schema_version!r}"
            )


@dataclass(frozen=True)
class CrossRunSmokeDoDResult:
    """5 Run 集約単位の DoD8 (Round R1 [C2])."""

    item: SmokeDoDItem
    observed_failure_modes: frozenset[FailureModeKind]
    smoke_report_schema_version: str

    def __post_init__(self) -> None:
        if self.item.scope != "cross_run":
            raise ValueError(
                f"CrossRunSmokeDoDResult.item.scope must be 'cross_run', "
                f"got {self.item.scope!r}"
            )
        if self.item.dod_id != "DoD8":
            raise ValueError(
                f"CrossRunSmokeDoDResult.item.dod_id must be 'DoD8', "
                f"got {self.item.dod_id!r}"
            )
        if self.smoke_report_schema_version != SMOKE_REPORT_SCHEMA_VERSION:
            raise ValueError(
                f"smoke_report_schema_version must be "
                f"{SMOKE_REPORT_SCHEMA_VERSION!r}, "
                f"got {self.smoke_report_schema_version!r}"
            )


# ---------------------------------------------------------------------------
# SmokeObservabilityProjection / CrossRunSmokeObservabilityProjection
# (詳細設計 § 3.7、 Round R1 [C5] / Round R2 [W6] / Round R3 [W2])
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SmokeObservabilityProjection:
    """T071 RunObservabilityReport の per-run typed projection.

    各 metric は EvidenceClass で表現 (= 数値 threshold 持たない、 caller が
    evidence_class から FM 導出).

    Round R1 [C5] 反映: Mapping[str, Decimal] を排除、 typed field で SSOT 漏れ防止.
    """

    ab_divergence_class: EvidenceClass
    epoch_consistency_class: EvidenceClass
    warmstart_shortfall_class: EvidenceClass
    bypass_ratio_class: EvidenceClass
    session_entropy_class: EvidenceClass
    dataset_epoch_id_present: bool
    report_ref: str

    def __post_init__(self) -> None:
        if not self.report_ref:
            raise ValueError(
                "SmokeObservabilityProjection.report_ref must be non-empty"
            )


@dataclass(frozen=True)
class CrossRunSmokeObservabilityProjection:
    """5 Run 集約単位の typed projection (Round R3 [W2])."""

    cross_run_epoch_pollution_class: EvidenceClass
    report_ref: str

    def __post_init__(self) -> None:
        if not self.report_ref:
            raise ValueError(
                "CrossRunSmokeObservabilityProjection.report_ref "
                "must be non-empty"
            )


# ---------------------------------------------------------------------------
# SmokeRunSummary / FiveRunConsistencyResult (詳細設計 § 3.7)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SmokeRunSummary:
    """1 Run 単位の smoke summary (Phase 2 で run_ga.py adapter 構築).

    Round R2 [S3]: observed_failure_modes に rename (旧 observed_fms).
    """

    run_id: str
    dataset_epoch_id: str
    run_succeeded: bool
    per_run_dod: PerRunSmokeDoDResult
    observability_projection: SmokeObservabilityProjection
    observed_failure_modes: frozenset[FailureModeKind]

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("SmokeRunSummary.run_id must be non-empty")
        if not self.dataset_epoch_id:
            raise ValueError(
                "SmokeRunSummary.dataset_epoch_id must be non-empty"
            )


@dataclass(frozen=True)
class FiveRunConsistencyResult:
    """5 Run 連続検証 (synthesis § 18.3、 詳細設計 § 3.7)."""

    runs: tuple[SmokeRunSummary, ...]
    cross_run_dod: CrossRunSmokeDoDResult
    epoch_pollution_observed: bool
    config_drift_observed: bool
    schema_version_consistent: bool
    overall_severity: Severity

    def __post_init__(self) -> None:
        if len(self.runs) != SMOKE_RUNS_REQUIRED:
            raise ValueError(
                f"FiveRunConsistencyResult.runs must have len == "
                f"{SMOKE_RUNS_REQUIRED}, got {len(self.runs)}"
            )


# ---------------------------------------------------------------------------
# SmokeOutcomeClassification (詳細設計 § 3.9、 Round R1 [C4] [S5] / Round R3 [C1])
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SmokeOutcomeClassification:
    """smoke 結果の事実認定 (Round R1 [C4]、 自動判定の硬い truth table 廃止).

    Round R3 [C1] aggregate_evidence で inconclusive を warning に隠さず保持.

    Round D1 [C1] / Round 4 [S1] cross-field invariant:
        overall_severity == aggregate_evidence.severity
    """

    aggregate_evidence: AggregateEvidence
    observed_failure_modes: frozenset[FailureModeKind]
    per_run_severity: Severity
    cross_run_severity: Severity
    overall_severity: Severity

    def __post_init__(self) -> None:
        if self.overall_severity != self.aggregate_evidence.severity:
            raise ValueError(
                f"SmokeOutcomeClassification.overall_severity "
                f"({self.overall_severity!r}) must match "
                f"aggregate_evidence.severity "
                f"({self.aggregate_evidence.severity!r})"
            )


# ---------------------------------------------------------------------------
# ReleaseActionRecommendation (詳細設計 § 3.8、 Round R3 [W5] / Round 4 [W3])
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReleaseActionRecommendation:
    """運用判断 hint (= manual review 前段、 自動切替指示ではない).

    Round R3 [W5] / Round 4 [W3] / Round D2 [C1] 反映:
        review_hint は **hint only**:
            - "no_blocker_observed": ブロッカー観測なし、 reviewer が承認可と
              判断する候補. **ただし reviewer の手動承認は必須**
              (= 自動承認は禁止、 docstring 規約).
            - "hold_for_delay": warning level、 1 cycle 後再 smoke 推奨.
            - "hold_for_review": hard_fail / inconclusive / FM 観測、
              manual review で原因分析.

        decide_release_action は本値を返すが、 切替コミットの **実行権限を
        持たない**. Phase 2 で run_ga.py / human reviewer が本値を判断材料として
        使う.

    Round D2 [C1] (Phase 1 制約):
        runbook section は Phase 2 申し送り (Phase 1 では本 docstring に SSOT 集約).
        - review_hint="no_blocker_observed" でも reviewer の手動承認必須
        - review_hint="hold_for_delay" は warning level
        - review_hint="hold_for_review" は hard_fail / inconclusive / FM observed
          のいずれか
    """

    outcome_classification: SmokeOutcomeClassification
    review_hint: Literal[
        "no_blocker_observed", "hold_for_delay", "hold_for_review"
    ]
    rationale: str
    requires_manual_review: bool

    def __post_init__(self) -> None:
        if not self.rationale:
            raise ValueError(
                "ReleaseActionRecommendation.rationale must be non-empty"
            )


# ---------------------------------------------------------------------------
# BigBangCleanupReport (詳細設計 § 3、 § 8 全集約)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BigBangCleanupReport:
    """big-bang cleanup + smoke の最終 report.

    Phase 2 で T071 RunObservabilityReport.smoke field に配線予定.
    """

    deletion_targets: tuple[DeletionTargetCategory, ...]
    per_run_smoke_results: tuple[PerRunSmokeDoDResult, ...]
    cross_run_smoke_result: CrossRunSmokeDoDResult
    five_run_consistency_result: FiveRunConsistencyResult
    outcome_classification: SmokeOutcomeClassification
    release_action_recommendation: ReleaseActionRecommendation
    report_schema_version: str

    def __post_init__(self) -> None:
        if self.report_schema_version != SMOKE_REPORT_SCHEMA_VERSION:
            raise ValueError(
                f"BigBangCleanupReport.report_schema_version must be "
                f"{SMOKE_REPORT_SCHEMA_VERSION!r}, "
                f"got {self.report_schema_version!r}"
            )
        if len(self.per_run_smoke_results) != SMOKE_RUNS_REQUIRED:
            raise ValueError(
                f"BigBangCleanupReport.per_run_smoke_results must have len == "
                f"{SMOKE_RUNS_REQUIRED}, got {len(self.per_run_smoke_results)}"
            )


# ---------------------------------------------------------------------------
# Helpers (詳細設計 § 4.1)
# ---------------------------------------------------------------------------


def _max_severity_3value(severities: tuple[Severity, ...]) -> Severity:
    """severity の 3 値 max 集約 (= "hard_fail" / "warning" / "ok"、
    inconclusive は別軸).

    入力が "inconclusive" を含む場合は除外して max を取り、 全 inconclusive の
    場合は "ok" にフォールバック (= severity 軸では blocker なし、 inconclusive
    は AggregateEvidence.has_inconclusive で別軸保持).
    """
    best: int = 0
    found_any = False
    for s in severities:
        if s == "inconclusive":
            continue
        rank = _SEVERITY_3VALUE_ORDER.get(s)
        if rank is None:
            raise ValueError(f"unknown severity: {s!r}")
        if rank > best:
            best = rank
        found_any = True
    if not found_any:
        return "ok"
    for name, rank in _SEVERITY_3VALUE_ORDER.items():
        if rank == best:
            return name
    raise RuntimeError(f"_max_severity_3value: no match for rank={best}")


def _evidence_class_to_severity_excluding_inconclusive(
    cls: EvidenceClass,
) -> Severity:
    """EvidenceClass を Severity に変換 (inconclusive は別軸のため "ok" に下げる).

    inconclusive は has_inconclusive 軸で保持されるため severity 軸では "ok"
    扱い (= severity 集約で隠れない、 別軸で manual review hint に反映).
    """
    if cls == "inconclusive":
        return "ok"
    return cls


def _max_per_run_severity(
    per_run_results: tuple[PerRunSmokeDoDResult, ...],
) -> Severity:
    """全 per-run の overall_evidence_class を集約 (3 値 max)."""
    severities = tuple(
        _evidence_class_to_severity_excluding_inconclusive(p.overall_evidence_class)
        for p in per_run_results
    )
    return _max_severity_3value(severities)


def _dedup_inconclusive_reasons(
    reasons: tuple[InconclusiveReason, ...],
) -> tuple[InconclusiveReason, ...]:
    """source + reason_code + message の 3 軸で重複排除 (Round D1 [W2] / [S3]).

    順序を保持 (= 最初の出現を残す).
    """
    seen: set[tuple[str, str, str]] = set()
    out: list[InconclusiveReason] = []
    for r in reasons:
        key = (r.source, r.reason_code, r.message)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return tuple(out)


# ---------------------------------------------------------------------------
# classify_smoke_outcome (詳細設計 § 4.1、 Round R3 [C1] [S1] [S2])
# ---------------------------------------------------------------------------


def classify_smoke_outcome(
    *,
    per_run_results: tuple[PerRunSmokeDoDResult, ...],
    cross_run_result: CrossRunSmokeDoDResult,
    five_run_result: FiveRunConsistencyResult,
) -> SmokeOutcomeClassification:
    """smoke 結果の事実認定 (= severity + inconclusive 別軸).

    SSOT (Round R3 [C1] [S1]):
        severity 集約: max("hard_fail", "warning", "ok") の 3 値
            (= inconclusive は別軸).
        has_inconclusive = 任意の per_run / cross_run で inconclusive あり.
        inconclusive_reasons = 各経路から InconclusiveReason 集約 + 重複排除
            (source + reason_code + message の 3 軸).
        observed_failure_modes = per_run 全 ∪ cross_run の和集合.

    Args:
        per_run_results: 5 Run の per-run 結果 (= len は SMOKE_RUNS_REQUIRED 推奨
            だが本関数では len 制約は課さず、 任意の N に対し集約).
        cross_run_result: 5 Run 集約の DoD8 結果.
        five_run_result: 5 Run consistency 結果 (severity 集約に使用).

    Returns:
        SmokeOutcomeClassification: 事実認定結果.
    """
    per_run_severity = _max_per_run_severity(per_run_results)
    cross_run_severity = _evidence_class_to_severity_excluding_inconclusive(
        cross_run_result.item.status
    )
    five_run_severity = _evidence_class_to_severity_excluding_inconclusive(
        five_run_result.overall_severity
    )

    overall_severity = _max_severity_3value(
        (per_run_severity, cross_run_severity, five_run_severity)
    )

    inconclusive_reasons: list[InconclusiveReason] = []
    for p in per_run_results:
        for item in p.items:
            if item.status == "inconclusive":
                inconclusive_reasons.append(
                    InconclusiveReason(
                        source=item.dod_id,
                        reason_code="dod_inconclusive",
                        message=item.detail or "(no detail)",
                    )
                )
    if cross_run_result.item.status == "inconclusive":
        inconclusive_reasons.append(
            InconclusiveReason(
                source=cross_run_result.item.dod_id,
                reason_code="cross_run_dod_inconclusive",
                message=cross_run_result.item.detail or "(no detail)",
            )
        )
    if five_run_result.overall_severity == "inconclusive":
        inconclusive_reasons.append(
            InconclusiveReason(
                source="five_run_consistency",
                reason_code="five_run_consistency_inconclusive",
                message="five_run_consistency overall_severity=inconclusive",
            )
        )

    deduped = _dedup_inconclusive_reasons(tuple(inconclusive_reasons))
    has_inconclusive = bool(deduped)

    aggregate_evidence = AggregateEvidence(
        severity=overall_severity,
        has_inconclusive=has_inconclusive,
        inconclusive_reasons=deduped,
    )

    observed_failure_modes: frozenset[FailureModeKind] = frozenset()
    for p in per_run_results:
        observed_failure_modes = observed_failure_modes | p.observed_failure_modes
    observed_failure_modes = (
        observed_failure_modes | cross_run_result.observed_failure_modes
    )

    return SmokeOutcomeClassification(
        aggregate_evidence=aggregate_evidence,
        observed_failure_modes=observed_failure_modes,
        per_run_severity=per_run_severity,
        cross_run_severity=cross_run_severity,
        overall_severity=overall_severity,
    )


# ---------------------------------------------------------------------------
# decide_release_action (詳細設計 § 4.2、 概念設計 § 6.4 厳密準拠)
# ---------------------------------------------------------------------------


def decide_release_action(
    *,
    classification: SmokeOutcomeClassification,
) -> ReleaseActionRecommendation:
    """運用判断 hint (= manual review 前段、 自動切替指示ではない).

    優先順位 (Round R3 [S2]):
        1. severity == "hard_fail"            → "hold_for_review"
        2. has_inconclusive == True           → "hold_for_review" (C8 規範)
        3. observed_failure_modes 観測あり    → "hold_for_review"
        4. severity == "warning" AND 上記不在 → "hold_for_delay"
        5. severity == "ok" AND 上記すべて不在 → "no_blocker_observed"
            (Round R3 [W5])

    Args:
        classification: 事実認定 (classify_smoke_outcome の出力).

    Returns:
        ReleaseActionRecommendation: 運用判断 hint (= 自動切替指示ではない).
    """
    severity = classification.aggregate_evidence.severity
    has_inconclusive = classification.aggregate_evidence.has_inconclusive
    has_fms = bool(classification.observed_failure_modes)

    # Round R1 Codex S-01 fail-closed: severity が想定外 ("inconclusive" 等、
    # classify_smoke_outcome 通常経路では発生しないが外部からの不整合入力に対する
    # 防御として明示) の場合は hold_for_review に倒す.
    if severity not in ("hard_fail", "warning", "ok"):
        return ReleaseActionRecommendation(
            outcome_classification=classification,
            review_hint="hold_for_review",
            rationale=(
                f"unexpected severity={severity!r} (fail-closed)、 "
                "manual review 必要"
            ),
            requires_manual_review=True,
        )

    if severity == "hard_fail":
        return ReleaseActionRecommendation(
            outcome_classification=classification,
            review_hint="hold_for_review",
            rationale=(
                f"hard_fail (severity={severity!r})、 manual review 必要"
            ),
            requires_manual_review=True,
        )
    if has_inconclusive:
        sample = classification.aggregate_evidence.inconclusive_reasons[:3]
        return ReleaseActionRecommendation(
            outcome_classification=classification,
            review_hint="hold_for_review",
            rationale=(
                f"inconclusive 観測 (= データ不足: {sample!r})、 "
                "C8 規範で manual review 必要"
            ),
            requires_manual_review=True,
        )
    if has_fms:
        sorted_fms = sorted(classification.observed_failure_modes)
        return ReleaseActionRecommendation(
            outcome_classification=classification,
            review_hint="hold_for_review",
            rationale=f"FM 観測 ({sorted_fms})、 manual review 必要",
            requires_manual_review=True,
        )
    if severity == "warning":
        return ReleaseActionRecommendation(
            outcome_classification=classification,
            review_hint="hold_for_delay",
            rationale=(
                "warning level + FM 不在 + inconclusive 不在、 "
                "1 cycle 後再 smoke 推奨"
            ),
            requires_manual_review=False,
        )
    return ReleaseActionRecommendation(
        outcome_classification=classification,
        review_hint="no_blocker_observed",
        rationale=(
            "全 DoD ok + FM 不在 + inconclusive 不在、 切替コミット blocker "
            "観測なし (= reviewer が最終判断)"
        ),
        requires_manual_review=False,
    )


# ---------------------------------------------------------------------------
# select_rollback_relevant_failure_modes (詳細設計 § 4.3、 Round R3 [S4] /
# Round 4 [W1] API 名予約)
# ---------------------------------------------------------------------------


def select_rollback_relevant_failure_modes(
    *,
    observed: frozenset[FailureModeKind],
    policy: object,
) -> frozenset[FailureModeKind]:
    """rollback 対象 FM 集合の決定 (Phase 2 別 TODO で実装).

    Round R3 [S4] / Round 4 [W1] 反映:
        Phase 1 (T075 PR): NotImplementedError raise
        Phase 2 (synthesis Round 22 改訂後): 別 TODO で実装

    **!!! Phase 2 only / do not call in T075 !!!** (Round 4 [W1])

    Args:
        observed: T075 module で観測された全 FM
            (= SmokeOutcomeClassification.observed_failure_modes).
        policy: synthesis Round 22 改訂後の policy オブジェクト
            (= 詳細は別 TODO).

    Returns:
        rollback 判定対象の FM 集合.

    Raises:
        NotImplementedError: Phase 1 では常に raise.
    """
    raise NotImplementedError(
        "select_rollback_relevant_failure_modes is Phase 2 only. "
        "synthesis Round 22 改訂後に別 TODO で実装. "
        "T075 module は observed_failure_modes のみ提供、 "
        "rollback_relevant の判定責務は持たない. "
        "do not call in T075."
    )
