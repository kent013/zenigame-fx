# 詳細設計: T075 — Big-bang cleanup + smoke

**作成日時**: 2026-05-01 03:35 JST
**設計者**: Claude
**前提**: 概念設計 `conceptual-design.md` Round 4 APPROVED 済 (`conceptual-review-round-4.md`)
**SSOT 規約 (§ 11.2)**: 本詳細設計 §3 / §4 の擬似コードは概念設計 §4 / §5 / §6 と同期。 不一致時は概念設計を正本として優先。
**main 基準**: `b591988` (T074 commit 後)

**改訂履歴 (Round 2 詳細レビュー反映、 2026-05-01 04:30 JST)**: 2 Critical / 5 Warning / 5 Suggestion を全反映:
- Round D2 [C1]: docs/runbook / PR template / CI meta check を **Phase 2 申し送りに格下げ** (= Round 4 「Phase 1 純ライブラリ + 単体テストのみ」 SSOT 整合)。 Phase 1 では `ReleaseActionRecommendation` docstring + PR description (= 手動チェックリスト) のみ
- Round D2 [C2]: `F40b_pr_template_round22_blockers` test を **Phase 1 test list から削除**、 Phase 2 別 TODO で CI meta check として実装
- Round D2 [W1] [S3]: `DUAL_PATH_ENFORCE_TARGETS` に **path normalization rule** 追加 (= repository-root relative + POSIX separator + symlink follow なし)、 PurePosixPath 正規化
- Round D2 [W2]: `tests-prod/**` の取扱明示 (= dual-path enforce 対象外、 設計判断値、 Phase 1 では存在しない前提)
- Round D2 [W3]: `CleanupCategorySlug` 対応表 § 3.5 に追加 (= synthesis § 12.1 / § 12.2 bullet → category 1 対 1 マッピング)
- Round D2 [W4]: F26c を **AST FunctionDef.name + public method + call target** 検査に specification 強化、 raw grep 禁止
- Round D2 [W5] [S4]: conformance fixture の error message を **error code 固定** (= "T075_UNSUPPORTED_METRIC" stable prefix)、 metric_name dump は補助情報のみ
- Round D2 [S1]: 採用 (= C1 と同義)
- Round D2 [S2]: 採用 (= C2 と同義)
- Round D2 [S5]: F26b に positive case 明示 (= 一致 case で construct 可能なケース追加)

**改訂履歴 (Round 1 詳細レビュー反映、 2026-05-01 04:00 JST)**: 2 Critical / 5 Warning / 5 Suggestion を全反映:
- Round D1 [C1]: `SmokeOutcomeClassification.__post_init__` の `overall_severity == aggregate_evidence.severity` invariant を **詳細擬似コードで明示** + F26b test 追加
- Round D1 [C2]: dual-path enforce 仕様固定 (= 対象パス表 / allowlist glob / parser 失敗時 fail-closed / 境界 test 拡充)
- Round D1 [W1]: `change_group_id` の `{category}` を **`CleanupCategorySlug` Literal で固定** (= "cleanup" / "config" / "script" / "module" / "schema" の 5 値)
- Round D1 [W2]: `InconclusiveReason` dedup を **source + reason_code + message** の 3 軸に拡張 (= 異なる message が落ちないよう監査可能性確保)
- Round D1 [W3]: runbook section を詳細設計に追加、 review_hint "no_blocker_observed でも reviewer 承認必須" の運用検証 test 追加
- Round D1 [W4]: Round 22 blockers listed の **CI meta check** (= PR template 必須項目検査) 規定
- Round D1 [W5]: conformance fixture の **assert 粒度** (= ValueError message 文言、 metric_name 一覧 dump 等) を fixture docstring で固定
- Round D1 [S1-S5]: 上記 W に統合

**改訂履歴 (旧)**: 概念設計 Round 1-4 で出た指摘 (= 10 Critical / 23 Warning / 18 Suggestion) は概念設計に全反映済。 概念 Round 4 で残った Warning (W1-W3) / Suggestion (S1-S4) を本詳細設計で反映:
- Round 4 [W1]: `select_rollback_relevant_failure_modes` の Phase 1 誤使用防止 (= NotImplementedError + docstring + 単体 test 固定)
- Round 4 [W2]: `inconclusive_reasons` を **structured reason** dataclass に変更 (= source / reason_code / message)
- Round 4 [W3]: `no_blocker_observed` 規約を dataclass docstring + runbook に明記
- Round 4 [S1]: AggregateEvidence invariant に `has_inconclusive == bool(inconclusive_reasons)` 追加
- Round 4 [S2]: supported_metric_names conformance test に「supported metric が ok 等を返してもよい」 を明示
- Round 4 [S3]: `change_group_id` 命名規則 (= "T075-{category}-{stable_slug}") を詳細設計で固定
- Round 4 [S4]: Round 22 blocked-by 状況での T075 PR 先 merge 条件 3 点 (= runtime unreachable tests / no release decision authority tests / Round 22 blockers listed) 明示

## 0. 詳細設計の責務

概念設計で確定した SSOT (= synthesis local projection / DoD 二層 / threshold-free / classify-decide 2 段階 / typed projection / manifest schema / collider bias non-goal) を **コード単位** に展開:
- 完全な擬似コード
- structured InconclusiveReason dataclass (Round 4 [W2])
- conformance test fixture 規範 (Round 4 [S2])
- change_group_id 命名規則 (Round 4 [S3])
- T075 PR merge 条件 (Round 4 [S4])

## 1. ファイル / 関数 / クラス完全リスト

### 1.1 新規ファイル

| Path | 主シンボル | LOC 概算 |
|---|---|---|
| `src/alpha_factory/smoke.py` | 概念 § 5 全 SSOT 群 | +500 |
| `tests/alpha_factory/test_smoke.py` | F1-F40 + happy path + conformance fixture | +600 |

### 1.2 既存ファイル変更

| Path | 関数 / 行 | 変更内容 | LOC 増減 |
|---|---|---|---|
| (なし) | T075 PR (Phase 1) は新規 module + 単体テストのみ | 既存ファイルへの影響なし | 0 |

### 1.3 Phase 2 申し送り

- T071 詳細設計改訂: RunObservabilityReport に `smoke: BigBangCleanupReport` field 追加
- run_ga.py 詳細設計改訂申し送り: 唯一の SSOT adapter として archive 集計 → SmokeRunSummary 構築
- synthesis Round 22 改訂候補 5 件 (= new_cascade / FM SSOT / DoD 分離 / threshold / stable clause anchor)
- 別 TODO (= synthesis Round 22 改訂後): `select_rollback_relevant_failure_modes` 実装、 数値 threshold 確定

### 1.4 collider bias non-goal (T072-T074 継承、 概念 § 7.3)

下流 caller 詳細設計改訂申し送り:
> T075 module は collider bias を判定しない。 holiday_markets / dst_transition_markets / schedule_status の stratified audit / 因果解釈 / 比率差判定は **Phase 2 で T071 RunObservabilityReport 経由** で出力する責務。 T075 module 内では observability_flags を参照しない (= AST grep DoD で確認)。

## 2. 既存 caller signature 完全展開

### 2.1 既存挙動への影響なし

T075 PR は新規 module 追加のみ。 既存 caller には影響しない。

### 2.2 dual-path enforce grep DoD 4 経路 (Round R2 [W5] / Round R3 [S3])

```bash
# (1) source import (AST 解析)
# AST で src/**/*.py の ast.ImportFrom / ast.Import を検査、 forbidden module substring 検出

# (2) CLI / scripts (AST + shebang + __main__)
# AST で scripts/**/*.py を検査、 shebang 行 + if __name__ == "__main__": block 解析

# (3) config key (yaml parse + dot-notation)
# yaml.safe_load(config/**/*.yaml)、 dot-notation key を再帰的に検査

# (4) docs runbook (substring match、 warning level)
# docs/runbook/**/*.md substring match、 warning emit のみ raise しない
# 除外 (allowlist、 Round R3 [S3]):
#   - docs/historical/**     (= 設計記録)
#   - devnotes/**            (= 履歴記録)
```

### 2.3 grep DoD test 化 (10 検索語、 Round R2 [W5])

T072-T074 と同 pattern で AST 解析:

```python
def test_smoke_module_no_existing_module_imports():
    """T075 module は archive / swim_lane / cross_pair / stage_gate / etc. を import しない."""
    import ast, src.alpha_factory.smoke as s
    with open(s.__file__, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    forbidden_module_substrings = (
        "archive", "swim_lane", "cross_pair", "stage_gate",
        "calibrate_gate", "calibrate_state",
    )
    forbidden_exact_names = (
        "ANCHOR_PAIRS", "promote_graduates", "mark_graduated",
        "GraduationLane", "Tier1Lane",
    )
    forbidden_substrings = ("holiday", "DST", "observability_flags", "stratified")

    # 詳細実装は T072-T074 と同 pattern (= ImportFrom / Import / Name / Attribute / string literal、 docstring 除外)
    ...
```

## 3. データモデル詳細 (擬似コード)

### 3.1 型 / 定数

```python
# src/alpha_factory/smoke.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Final, Literal, Protocol, runtime_checkable


__all__ = [
    "EvidenceClass", "Severity", "FailureModeKind",
    "DoDIdPerRun", "DoDIdCrossRun", "RemovalMode", "MigrationMode",
    "SMOKE_RUNS_REQUIRED", "PER_RUN_DOD_ITEMS_COUNT", "CROSS_RUN_DOD_ITEMS_COUNT",
    "SMOKE_REPORT_SCHEMA_VERSION",
    "InconclusiveReason", "AggregateEvidence",
    "EvidenceClassifierProtocol",
    "DeletionTarget", "DeletionTargetCategory", "MigrationTarget",
    "SmokeDoDItem", "PerRunSmokeDoDResult", "CrossRunSmokeDoDResult",
    "SmokeObservabilityProjection", "CrossRunSmokeObservabilityProjection",
    "SmokeRunSummary", "FiveRunConsistencyResult",
    "SmokeOutcomeClassification", "ReleaseActionRecommendation",
    "BigBangCleanupReport",
    "enumerate_deletion_targets", "enumerate_migration_targets",
    "check_per_run_smoke_dod", "check_cross_run_smoke_dod",
    "check_five_run_consistency",
    "classify_smoke_outcome", "decide_release_action",
    "compose_bigbang_cleanup_report",
    "select_rollback_relevant_failure_modes",
]


# Status Literal
EvidenceClass = Literal["hard_fail", "warning", "inconclusive", "ok"]
Severity = Literal["hard_fail", "warning", "inconclusive", "ok"]   # = EvidenceClass 同型
FailureModeKind = Literal["FM1", "FM2", "FM3", "FM4", "FM5"]
DoDIdPerRun = Literal["DoD1", "DoD2", "DoD3", "DoD4", "DoD5", "DoD6", "DoD7"]
DoDIdCrossRun = Literal["DoD8"]
RemovalMode = Literal["git_rm", "yaml_key_delete"]
MigrationMode = Literal["yaml_value_replace"]
CleanupCategorySlug = Literal["cleanup", "config", "script", "module", "schema"]   # Round D1 [W1]


# 定数
SMOKE_RUNS_REQUIRED: Final[int] = 5
PER_RUN_DOD_ITEMS_COUNT: Final[int] = 7
CROSS_RUN_DOD_ITEMS_COUNT: Final[int] = 1
SMOKE_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"

# EvidenceClass 順序 (Round R2 [S1]): "hard_fail" > "warning" > "inconclusive" > "ok"
_EVIDENCE_CLASS_ORDER: Final[dict[EvidenceClass, int]] = {
    "hard_fail": 3,
    "warning": 2,
    "inconclusive": 1,
    "ok": 0,
}
```

### 3.2 InconclusiveReason (Round 4 [W2] structured reason)

```python
@dataclass(frozen=True)
class InconclusiveReason:
    """inconclusive 観測の構造化 reason (Round 4 [W2] 反映).

    SSOT:
        source: 観測元 (= "DoD3" / "ab_divergence_class" / "cross_run_epoch_pollution_class" 等)
        reason_code: 機械可読 code (= "missing_metric" / "classifier_unsupported" / "data_too_short" 等)
        message: 人間可読の 1 行説明 (= reviewer 用)

    集計時に source / reason_code で重複排除可能.
    """
    source: str
    reason_code: str
    message: str

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("InconclusiveReason.source must be non-empty")
        if not self.reason_code:
            raise ValueError("InconclusiveReason.reason_code must be non-empty")
```

### 3.3 AggregateEvidence (Round R3 [C1] [S1] / Round 4 [S1] invariant 追加)

```python
@dataclass(frozen=True)
class AggregateEvidence:
    """集約 evidence (= severity と inconclusive を別軸保持).

    SSOT (Round R3 [C1] / Round 4 [S1] invariant):
        severity: Severity (= 4 値、 max 集約は hard_fail / warning / ok の 3 値階層)
        has_inconclusive: bool
        inconclusive_reasons: tuple[InconclusiveReason, ...]
        invariant: has_inconclusive == bool(inconclusive_reasons)
    """
    severity: Severity
    has_inconclusive: bool
    inconclusive_reasons: tuple[InconclusiveReason, ...]

    def __post_init__(self) -> None:
        # I-1: severity is valid Severity Literal (Python type checker enforces)
        # I-2: invariant has_inconclusive == bool(inconclusive_reasons) (Round 4 [S1])
        if self.has_inconclusive != bool(self.inconclusive_reasons):
            raise ValueError(
                f"AggregateEvidence invariant violated: "
                f"has_inconclusive ({self.has_inconclusive}) != "
                f"bool(inconclusive_reasons) ({bool(self.inconclusive_reasons)})"
            )
```

### 3.4 EvidenceClassifierProtocol (Round R2 [C3] / Round R3 [W1] / Round 4 [S2])

```python
@runtime_checkable
class EvidenceClassifierProtocol(Protocol):
    """T071 metric → EvidenceClass 分類 Protocol (caller-supplied).

    SSOT:
        T075 module は instance を持たない、 caller (= Phase 2 別 TODO) が実装

    Conformance test fixture (Round 4 [S2]):
        1. supported_metric_names() の戻り値は frozenset[str]、 サポートする metric name 集合
        2. supported_metric_names() に **含まれない** metric_name で __call__ → "inconclusive" 必須 (= 暗黙 ok 禁止、 fail-closed)
        3. supported_metric_names() に **含まれる** metric_name で __call__ → "ok" / "warning" / "hard_fail" / "inconclusive" のいずれも許容 (= 実装者の自由、 ただし inconclusive で済ますのは推奨しない)
        4. provenance: str は audit log 用、 戻り値の detail に source / version 等を含めることを推奨
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
```

### 3.5 DeletionTarget / MigrationTarget (Round R3 [W4] / Round 4 [S3])

```python
@dataclass(frozen=True)
class DeletionTarget:
    """削除対象 manifest (Round R1 [C6] / Round R2 [W3] [W4] / Round R3 [W4] / Round 4 [S3]).

    Round 4 [S3] / Round D1 [W1] change_group_id 命名規則:
        "T075-{category_slug}-{stable_slug}"
        category_slug ∈ CleanupCategorySlug (= 5 値: cleanup / config / script / module / schema)
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
        change_group_id matches "^T075-(cleanup|config|script|module|schema)-[a-z0-9_]+$"
            (= regex + Literal の二重化、 Round D1 [S2])
    """
    path: str
    category: str
    source_section: str
    source_clause_id: str         # synthesis 改訂後の stable anchor、 Round R2 [W3]
    source_excerpt_hash: str       # synthesis 該当 bullet の hash (= 改訂検出用)
    removal_mode: RemovalMode
    owner: str                     # 削除責務 PR 参照
    change_group_id: str           # Round 4 [S3] 命名規則
    supersedes: tuple[str, ...]    # Round R3 [W4]、 新 module 参照


@dataclass(frozen=True)
class MigrationTarget:
    """移行対象 manifest (Round R2 [W4] cleanup と分離).

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
    new_value_reference: str       # 移行先 SSOT 参照 (= 新 schema docstring 等)
    change_group_id: str
    supersedes: tuple[str, ...]


@dataclass(frozen=True)
class DeletionTargetCategory:
    name: str
    targets: tuple[DeletionTarget, ...]
```

### 3.6 SmokeDoDItem (Round R2 [W1] scope 追加)

```python
@dataclass(frozen=True)
class SmokeDoDItem:
    """smoke DoD 1 項目.

    SSOT (synthesis § 18.3 + Round R1 [C2] 二層 + Round R2 [W1] scope):
        scope = "per_run" → DoD1-DoD7
        scope = "cross_run" → DoD8
    """
    dod_id: DoDIdPerRun | DoDIdCrossRun
    scope: Literal["per_run", "cross_run"]
    synthesis_text: str
    check_function_name: str
    status: EvidenceClass
    detail: str

    def __post_init__(self) -> None:
        # invariant:
        #   scope=="per_run" → dod_id ∈ {DoD1..DoD7}
        #   scope=="cross_run" → dod_id == "DoD8"
        per_run_ids = {"DoD1", "DoD2", "DoD3", "DoD4", "DoD5", "DoD6", "DoD7"}
        if self.scope == "per_run":
            if self.dod_id not in per_run_ids:
                raise ValueError(f"scope='per_run' requires dod_id ∈ {per_run_ids}, got {self.dod_id!r}")
        elif self.scope == "cross_run":
            if self.dod_id != "DoD8":
                raise ValueError(f"scope='cross_run' requires dod_id='DoD8', got {self.dod_id!r}")
        else:
            raise ValueError(f"unknown scope: {self.scope!r}")
```

### 3.7 PerRunSmokeDoDResult / CrossRunSmokeDoDResult / SmokeObservabilityProjection / CrossRunSmokeObservabilityProjection

(概念設計 § 4 と同一の構造、 詳細省略。 各 dataclass の `__post_init__` は概念設計 § 4 / § 8 invariant を実装)

### 3.8 ReleaseActionRecommendation (Round R3 [W5] / Round 4 [W3])

```python
@dataclass(frozen=True)
class ReleaseActionRecommendation:
    """運用判断 hint (= manual review 前段、 自動切替指示ではない).

    Round R3 [W5] / Round 4 [W3] 反映:
        review_hint は **hint only**:
            - "no_blocker_observed": ブロッカー観測なし、 reviewer が承認可と判断する候補
              **ただし reviewer の手動承認は必須** (= 自動承認は禁止、 docstring 規約)
            - "hold_for_delay": warning level、 1 cycle 後再 smoke 推奨
            - "hold_for_review": hard_fail / inconclusive / FM 観測、 manual review で原因分析

        decide_release_action は本値を返すが、 切替コミットの **実行権限を持たない**。
        Phase 2 で run_ga.py / human reviewer が本値を判断材料として使う.
    """
    outcome_classification: SmokeOutcomeClassification
    review_hint: Literal["no_blocker_observed", "hold_for_delay", "hold_for_review"]
    rationale: str
    requires_manual_review: bool
```

### 3.9 SmokeOutcomeClassification (Round R1 [C4] [S5] / Round R3 [C1])

```python
@dataclass(frozen=True)
class SmokeOutcomeClassification:
    """smoke 結果の事実認定 (Round R1 [C4]、 自動判定の硬い truth table 廃止).

    Round R3 [C1] aggregate_evidence で inconclusive を warning に隠さず保持.
    """
    aggregate_evidence: AggregateEvidence
    observed_failure_modes: frozenset[FailureModeKind]
    per_run_severity: Severity
    cross_run_severity: Severity
    overall_severity: Severity   # = aggregate_evidence.severity と一致

    def __post_init__(self) -> None:
        # Round D1 [C1] / Round 4 [S1] cross-field invariant 明示:
        if self.overall_severity != self.aggregate_evidence.severity:
            raise ValueError(
                f"overall_severity ({self.overall_severity!r}) must match "
                f"aggregate_evidence.severity ({self.aggregate_evidence.severity!r})"
            )
        # 各 severity 値が Severity Literal に含まれるかは type checker 任せ
        # (= 実行時 Literal 型検証は dataclass 標準で行われない、 mypy / ruff で検出)
```

## 3.10 dual-path enforce 仕様 (Round D1 [C2] 仕様固定)

```python
# 4 経路の対象パス表 (Round D1 [C2] / Round R3 [S3])

DUAL_PATH_ENFORCE_TARGETS: Final[dict[str, dict[str, object]]] = {
    "source_import": {
        "globs": ("src/**/*.py",),
        "method": "ast",                    # ast.ImportFrom / ast.Import / ast.Name / ast.Attribute / ast.Constant(str) docstring 除外
        "parser_failure_mode": "fail_closed",  # parse 失敗で test fail
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
        "method": "yaml_dot_notation",      # yaml.safe_load + 再帰的 dot-notation key 検査
        "parser_failure_mode": "fail_closed",
        "severity": "fail",
    },
    "docs_runbook": {
        "globs": ("docs/runbook/**/*.md",),
        "method": "substring_match",        # 自然言語、 forbidden substring 検出
        "parser_failure_mode": "fail_open",  # parse 失敗 (= 通常起きない) は warning
        "severity": "warning",              # raise しない、 warning emit only
    },
}

DUAL_PATH_ENFORCE_ALLOWLIST: Final[tuple[str, ...]] = (
    "docs/historical/**",            # 設計記録、 旧 path 言及あっても OK
    "devnotes/**",                   # 履歴記録、 同上
    "tests/**",                      # tests は forbidden module を mock 経由で参照可
    ".git/**",                       # git 内部ファイル
    "**/__pycache__/**",             # bytecode
)

# Round D2 [W1] [S3] path normalization rule:
# - すべての path は repository-root relative (= "src/alpha_factory/audit.py" 形式、 絶対 path 不可)
# - POSIX separator ("/") のみ、 Windows backslash 禁止
# - symlink は follow しない (= os.lstat、 symlink 先は対象外)
# - 正規化は PurePosixPath で実施
```

**parser_failure_mode = "fail_closed"** (= source / scripts / config): parse 失敗 (= syntax error / 不正 yaml) は test FAIL、 fail-open で見逃さない。

**parser_failure_mode = "fail_open"** (= docs/runbook): markdown 自然言語のため parse 失敗は通常発生せず、 起きても warning emit only (= raise しない)。

**Round D2 [W2] tests-prod 取扱**: `tests-prod/**` は Phase 1 では存在しない前提、 dual-path enforce 対象 globs に含めない (= 設計判断値)。 将来 production tests directory が必要な場合は Round 22 改訂候補で別途検討。

### 3.5b CleanupCategorySlug → synthesis 対応表 (Round D2 [W3])

| CleanupCategorySlug | synthesis section | 該当 deletion target 種別 | 例 |
|---|---|---|---|
| "cleanup" | § 12.1 並走機構 | 並走機構・fallback 系全般、 旧 schema 分岐 | one-switch flag / NSGA-II↔CPPS 切替 / multi-state FSM |
| "config" | § 12.1 旧 config キー | default.yaml の旧キー | swim_lane.tier1.population_size / stage_gate.stage_a.target_pass_rate |
| "script" | § 12.1 旧 script | scripts/alpha_factory 配下の旧 CLI | scripts/alpha_factory/run_alpha_sieve.py |
| "module" | § 12.2 全面置換 (module) | src/alpha_factory 配下の置換対象 module | src/alpha_factory/calibrate_gate.py |
| "schema" | § 12.2 全面置換 (schema) | archive Parquet schema v1 → v2 等 | archive_schema_version=1 read 経路 |

**全件列挙生成手順** (詳細設計フェーズ):
1. synthesis.md § 12.1 / § 12.2 全 bullet を grep 抽出
2. 各 bullet を上表で category にマッピング
3. config/alpha_factory/default.yaml を yaml.safe_load → 全 key dump、 旧 key を "config" category に分類
4. T058-T074 詳細設計の Phase 2 申し送りから "module" / "schema" category 抽出
5. 集約結果を `enumerate_deletion_targets()` の戻り値 fixture として固定

## 4. アルゴリズム詳細 (擬似コード)

### 4.1 classify_smoke_outcome (Round R3 [C1] [S1] [S2])

```python
def classify_smoke_outcome(*, per_run_results, cross_run_result, five_run_result):
    """事実認定 (= severity + inconclusive 別軸).

    severity 集約 (Round R3 [C1] 反映): inconclusive を warning に隠さず別軸:
        max_severity = max(per_run_severity, cross_run_severity, five_run_severity)
            ただし max は "hard_fail" > "warning" > "ok" のみ集約 (= inconclusive は別軸)
        has_inconclusive = 任意の per_run / cross_run / five_run で inconclusive あり
        inconclusive_reasons = 各経路から InconclusiveReason 集約 + 重複排除
    """
    per_run_severity_no_inc = _max_severity_excluding_inconclusive(
        p.overall_evidence_class for p in per_run_results
    )
    cross_run_severity_no_inc = _evidence_class_to_severity_excluding_inconclusive(
        cross_run_result.item.status
    )
    five_run_severity_no_inc = _strip_inconclusive(five_run_result.overall_severity)

    overall_severity = _max_severity_3value((
        per_run_severity_no_inc, cross_run_severity_no_inc, five_run_severity_no_inc,
    ))

    inconclusive_reasons: list[InconclusiveReason] = []
    for p in per_run_results:
        for item in p.items:
            if item.status == "inconclusive":
                inconclusive_reasons.append(InconclusiveReason(
                    source=item.dod_id, reason_code="dod_inconclusive", message=item.detail,
                ))
    if cross_run_result.item.status == "inconclusive":
        inconclusive_reasons.append(InconclusiveReason(
            source=cross_run_result.item.dod_id, reason_code="cross_run_dod_inconclusive",
            message=cross_run_result.item.detail,
        ))
    has_inconclusive = bool(inconclusive_reasons)
    # 重複排除 (= source + reason_code 単位)
    # Round D1 [W2] / [S3] 反映: dedup を source + reason_code + message の 3 軸 (= message 異なれば保持)
    inconclusive_reasons_dedup = _dedup_reasons_by_full_key(inconclusive_reasons)

    aggregate_evidence = AggregateEvidence(
        severity=overall_severity,
        has_inconclusive=has_inconclusive,
        inconclusive_reasons=tuple(inconclusive_reasons_dedup),
    )

    observed_failure_modes = frozenset()
    for p in per_run_results:
        observed_failure_modes |= p.observed_failure_modes
    observed_failure_modes |= cross_run_result.observed_failure_modes

    return SmokeOutcomeClassification(
        aggregate_evidence=aggregate_evidence,
        observed_failure_modes=observed_failure_modes,
        per_run_severity=per_run_severity_no_inc,
        cross_run_severity=cross_run_severity_no_inc,
        overall_severity=overall_severity,
    )
```

### 4.2 decide_release_action (概念 § 6.4 厳密準拠)

(概念設計 § 6.4 の擬似コードと同一、 詳細省略。 優先順位: hard_fail → has_inconclusive → FM observed → warning → ok)

### 4.3 select_rollback_relevant_failure_modes (Round R3 [S4] / Round 4 [W1] API 名予約)

```python
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
        observed: T075 module で観測された全 FM (= SmokeOutcomeClassification.observed_failure_modes)
        policy: synthesis Round 22 改訂後の policy オブジェクト (= 詳細は別 TODO)

    Returns:
        rollback 判定対象の FM 集合.

    Raises:
        NotImplementedError: Phase 1 では常に raise.
    """
    raise NotImplementedError(
        "select_rollback_relevant_failure_modes is Phase 2 only. "
        "synthesis Round 22 改訂後に別 TODO で実装. "
        "T075 module は observed_failure_modes のみ提供、 rollback_relevant の判定責務は持たない."
    )
```

## 5. テスト計画 (Fxxx_<behavior> 命名)

### 5.1 `tests/alpha_factory/test_smoke.py` 新規

#### F1-F4: 定数 / Literal tests
- F1_constants: 全定数値 SSOT 一致
- F2_evidence_class_values: EvidenceClass 4 値
- F3_severity_values: Severity 4 値 (= EvidenceClass 同型)
- F4_failure_mode_kind_values: FailureModeKind 5 値 (FM1-FM5)

#### F5-F7: InconclusiveReason tests (Round 4 [W2])
- F5_inconclusive_reason_source_non_empty: source="" → ValueError
- F6_inconclusive_reason_code_non_empty: reason_code="" → ValueError
- F7_inconclusive_reason_dataclass_eq: 同 source / reason_code / message で eq 等価

#### F8-F11: AggregateEvidence tests (Round 4 [S1])
- F8_aggregate_evidence_invariant: has_inconclusive=False + inconclusive_reasons 非空 → ValueError
- F8b_aggregate_evidence_positive_match: has_inconclusive=True + inconclusive_reasons 非空 → 正常構築 (= positive case、 Round D2 [S5])
- F8c_aggregate_evidence_positive_no_inc: has_inconclusive=False + inconclusive_reasons 空 → 正常構築 (= positive case)
- F9_aggregate_evidence_invariant_reverse: has_inconclusive=True + inconclusive_reasons 空 → ValueError
- F10_aggregate_evidence_severity_4_values: severity ∈ {"hard_fail", "warning", "inconclusive", "ok"}
- F11_aggregate_evidence_happy: 各 invariant 満たす値で正常構築

#### F12-F15: EvidenceClassifierProtocol conformance tests (Round 4 [S2])
- F12_classifier_supported_metric_names_returns_frozenset: 戻り値型確認
- F13_classifier_unsupported_returns_inconclusive: supported_metric_names() に含まれない metric_name → "inconclusive" 必須、 detail prefix "T075_UNSUPPORTED_METRIC:" (Round D2 [W5] [S4] error code 固定)
- F14_classifier_supported_can_return_any_class: supported に含まれる metric_name → "ok" / "warning" / "hard_fail" / "inconclusive" すべて許容 (Round 4 [S2])
- F15_classifier_protocol_runtime_check: `isinstance(classifier, EvidenceClassifierProtocol)` で True

(= Phase 1 では mock classifier fixture を test ディレクトリ内に置く、 Phase 2 で Phase 2 別 TODO の classifier 実装に対して再利用可能)

#### F16-F19: DeletionTarget / MigrationTarget tests (Round 4 [S3] change_group_id 規則)
- F16_deletion_target_path_non_empty: path="" → ValueError
- F17_deletion_target_change_group_id_pattern: change_group_id が "^T075-[a-z_]+-[a-z0-9_]+$" で match (Round 4 [S3])
- F18_deletion_target_supersedes_tuple: supersedes は tuple (= 順序保持)
- F19_migration_target_change_group_id_same_as_deletion: 同一論理変更で DeletionTarget と MigrationTarget が同 change_group_id 持つ場合の grouping (= Round R3 [W4])

#### F20-F25: SmokeDoDItem / PerRunSmokeDoDResult / CrossRunSmokeDoDResult tests
- F20_smoke_dod_item_scope_per_run_dod_id: scope="per_run" + dod_id="DoD8" → ValueError
- F21_smoke_dod_item_scope_cross_run_dod_id: scope="cross_run" + dod_id="DoD1" → ValueError
- F22_per_run_dod_result_items_count: items len != 7 → ValueError
- F23_per_run_dod_result_items_unique_dod_id: items の dod_id 重複 → ValueError
- F24_cross_run_dod_result_dod8: item.dod_id != "DoD8" → ValueError
- F25_smoke_dod_item_no_numeric_field: dataclasses.fields(SmokeDoDItem) で numeric field 不在 (T073 / T074 SSOT 継承)

#### F26-F30: classify_smoke_outcome / decide_release_action tests (Round R3 [C1] [S2])
- F26_classify_warning_with_inconclusive: per_run="warning" + cross_run="inconclusive" → severity="warning"、 has_inconclusive=True
- F27_decide_inconclusive_priority: severity="warning" + has_inconclusive=True → review_hint="hold_for_review" (= warning に隠れない)
- F28_decide_priority_hard_fail: severity="hard_fail" → "hold_for_review"
- F29_decide_priority_fm_observed: severity="ok" + observed_fms 非空 → "hold_for_review"
- F30_decide_no_blocker_observed: severity="ok" + observed_fms 空 + has_inconclusive=False → "no_blocker_observed"
- F26b_classification_invariant_severity_match: SmokeOutcomeClassification(overall_severity="warning", aggregate_evidence.severity="ok") → ValueError (Round D1 [C1] cross-field invariant)
- F26c_classification_review_hint_authority: review_hint="no_blocker_observed" 取得後、 caller が自動切替実行可能なメソッドが T075 module に存在しないこと確認 (= **AST FunctionDef.name + public method name + ast.Call.func.id を検査**、 Round D2 [W4] raw grep 禁止、 docstring/comment は AST で除外。 forbidden_function_names = ("auto_proceed", "execute_release", "trigger_release", "commit_switchover" 等)

#### F31-F33: select_rollback_relevant_failure_modes tests (Round 4 [W1] 誤使用防止)
- F31_select_rollback_phase1_raises: Phase 1 では常に NotImplementedError raise
- F32_select_rollback_message_phase2_only: error message に "Phase 2 only" 文字列含む
- F33_select_rollback_docstring_warns: function docstring に "do not call in T075" 文字列含む

#### F34-F36: dual-path enforce 4 経路 tests (Round R2 [W5])
- F34_grep_dod_source_imports: src 配下の forbidden module imports 0 件
- F35_grep_dod_scripts_no_old_path: scripts 配下の旧 path 言及 0 件
- F36_grep_dod_config_no_old_keys: config 配下の旧 key 0 件

#### F37-F38: docs runbook allowlist tests (Round R3 [S3])
- F37_docs_runbook_warning_only: docs/runbook substring match で warning emit、 raise しない
- F38_docs_historical_devnotes_excluded: docs/historical / devnotes は allowlist で skip
- F38b_dual_path_parser_failure_fail_closed: source / scripts / config の parse 失敗 (= syntax error / 不正 yaml) は test FAIL (Round D1 [C2] fail-closed)
- F38c_dual_path_parser_failure_fail_open: docs/runbook の parse 失敗は warning emit only、 raise しない (= fail-open)
- F38d_dual_path_glob_boundary: target glob と allowlist glob の境界 (= `tests/**` は allowlist、 `tests-prod/**` は対象 等の例) で誤判定なし
<!-- F40b_pr_template_round22_blockers: Phase 2 申し送り (= CI meta check)、 Phase 1 test list から削除、 Round D2 [C2] 反映 -->

#### F39-F40: BigBangCleanupReport tests
- F39_bigbang_cleanup_report_schema_version: schema_version != "1.0.0" → ValueError
- F40_bigbang_cleanup_report_runs_count: per_run_smoke_results len != 5 → ValueError

### 5.2 conformance test fixture (Round 4 [S2])

```python
# tests/alpha_factory/test_smoke.py 内 fixture

@pytest.fixture
def mock_evidence_classifier() -> EvidenceClassifierProtocol:
    """Phase 2 別 TODO で実装する classifier の mock fixture (Round 4 [S2] / Round D1 [W5]).

    Conformance test 規約:
        1. supported_metric_names() の戻り値:
            - 型 frozenset[str]、 5 metric (FM1-FM5 対応) を必ず含む:
              "ab_divergence" / "epoch_consistency" / "warmstart_shortfall" /
              "bypass_ratio" / "session_entropy"
        2. unsupported metric_name で __call__:
            - 戻り値 (evidence_class, detail) で **evidence_class == "inconclusive" 必須**
            - detail は f"unsupported metric: {metric_name}" 形式 (= 統一文言)
            - assert 失敗時 message: "classifier returned {evidence_class!r} for unsupported metric {metric_name!r}, expected 'inconclusive'"
        3. supported metric_name で __call__:
            - 戻り値 evidence_class ∈ {"ok", "warning", "hard_fail", "inconclusive"} のいずれも許容 (= 実装者自由)
            - detail に provenance + metric_value 概要を含めることを推奨
        4. 失敗時 metric_name 一覧 dump (= debugging 用): supported_metric_names() の戻り値を pytest --tb=short で表示
    """
    class MockClassifier:
        _SUPPORTED = frozenset({
            "ab_divergence", "epoch_consistency",
            "warmstart_shortfall", "bypass_ratio", "session_entropy",
        })

        def supported_metric_names(self) -> frozenset[str]:
            return self._SUPPORTED

        def __call__(self, metric_value, metric_name, provenance):
            if metric_name not in self._SUPPORTED:
                return ("inconclusive", f"unsupported metric: {metric_name}")
            # mock 実装、 metric_value から evidence_class を返す (= test scenario で値を変える)
            ...

    return MockClassifier()
```

## 6. 失敗モード / fail-closed 経路

| ID | 失敗パターン | 対応 |
|---|---|---|
| FC1 | EvidenceClassifierProtocol 未対応 metric_name | conformance fixture で "inconclusive" 必須 |
| FC2 | AggregateEvidence invariant violation (Round 4 [S1]) | __post_init__ ValueError |
| FC3 | InconclusiveReason source / reason_code 空 | __post_init__ ValueError |
| FC4 | DeletionTarget change_group_id pattern violation (Round 4 [S3]) | __post_init__ ValueError |
| FC5 | SmokeDoDItem scope と dod_id 不整合 | __post_init__ ValueError |
| FC6 | PerRunSmokeDoDResult items count != 7 | __post_init__ ValueError |
| FC7 | CrossRunSmokeDoDResult item.dod_id != "DoD8" | __post_init__ ValueError |
| FC8 | SmokeOutcomeClassification overall_severity と aggregate_evidence.severity 不一致 | __post_init__ ValueError |
| FC9 | BigBangCleanupReport schema_version mismatch | __post_init__ ValueError |
| FC10 | select_rollback_relevant_failure_modes Phase 1 呼出 | NotImplementedError raise (Round 4 [W1]) |

## 7. backward-compat 互換性 (4 面)

T075 PR は新規 module + 単体テストのみ、 既存ファイル touch なし、 4 面とも影響なし。

## 8. DoD (Definition of Done)

### 8.1 実装完了

- [ ] `src/alpha_factory/smoke.py` 新規、 § 3 全 dataclass + § 4 全関数 + 全 Literal / Final 定数実装
- [ ] `EvidenceClassifierProtocol` Protocol 定義 + supported_metric_names method (Round R3 [W1])
- [ ] `InconclusiveReason` structured reason dataclass (Round 4 [W2])
- [ ] `AggregateEvidence` invariant `has_inconclusive == bool(inconclusive_reasons)` (Round 4 [S1])
- [ ] `DeletionTarget` / `MigrationTarget` の change_group_id 命名規則 "^T075-[a-z_]+-[a-z0-9_]+$" (Round 4 [S3])
- [ ] `select_rollback_relevant_failure_modes` Phase 1 NotImplementedError + docstring 警告 (Round 4 [W1])
- [ ] `decide_release_action` 優先順位: hard_fail → has_inconclusive → FM observed → warning → ok (Round R3 [S2])
- [ ] `review_hint` 値: "no_blocker_observed" / "hold_for_delay" / "hold_for_review" (Round R3 [W5])
- [ ] `enumerate_deletion_targets` で synthesis § 12.1 / § 12.2 全網羅 (= 詳細設計で synthesis grep + yaml dump で全件列挙)

### 8.2 テスト

- [ ] `tests/alpha_factory/test_smoke.py` 新規、 F1-F40 全 pass
- [ ] mock_evidence_classifier conformance fixture (Round 4 [S2])
- [ ] mypy / ruff pass

### 8.3 互換性 / 監査

- [ ] **C2 parallel-path grep DoD** 実行 (= AST 解析 + yaml parse + substring match):
  - smoke.py を src/ から import する経路 0 件 (= tests のみ)
  - 既存 archive / swim_lane / cross_pair / stage_gate / calibrate_gate / calibrate_state 参照なし
  - collider bias non-goal: holiday / DST / observability_flags / stratified 参照なし
- [ ] PR description に **collider bias 規範テンプレート** (T072 / T073 / T074 継承) を Phase 2 申し送りとして明記
- [ ] PR description に **synthesis Round 22 改訂 blocked-by 5 件** (= new_cascade / FM SSOT / DoD 分離 / threshold / stable clause anchor) を明記

### 8.4 T075 PR 先 merge 条件 (Round 4 [S4] / Round D2 [C1] [C2] Phase 1 制約反映)

synthesis Round 22 改訂が長期化した場合、 T075 PR を先 merge する条件:
1. **runtime unreachable tests pass** (= grep DoD test F34 / F35 / F36 / F38 全 pass)
2. **no release decision authority tests pass** (= F31 / F32 / F33 で `select_rollback_relevant_failure_modes` の Phase 1 raise 確認)
3. **PR description に Round 22 blockers リスト 5 件記載** (= 手動チェックリスト、 Round D2 [C1] 反映で Phase 1 純ライブラリ制約):
   - `Round 22 blockers:` heading + 5 件 (= new_cascade / FM SSOT / DoD 分離 / threshold / stable clause anchor) の手動記載
   - **CI meta check / PR template / runbook は Phase 2 別 TODO に格下げ** (Round D2 [C1] [C2])

Phase 2 で実施 (= 別 TODO):
- `.github/PULL_REQUEST_TEMPLATE.md` に T075 用 section 追加
- CI workflow で PR description 正規表現検出
- `docs/runbook/big-bang-cleanup-smoke.md` 新設

3 条件達成で先 merge 可、 evidence collection only mode で運用、 Round 22 改訂後別 TODO で完了化。

### 8.6 runbook section (Round D1 [W3] / Round D2 [C1] Phase 2 申し送り)

**Round D2 [C1] 反映で Phase 2 申し送り格下げ**: T075 Phase 1 PR では runbook 新設しない。 Phase 1 では `ReleaseActionRecommendation` の **dataclass docstring** に review_hint 規約を記述:
- review_hint="no_blocker_observed" でも reviewer の手動承認必須
- review_hint="hold_for_delay" は warning level
- review_hint="hold_for_review" は hard_fail / inconclusive / FM observed のいずれか

Phase 2 で `docs/runbook/big-bang-cleanup-smoke.md` 新設、 上記規約を runbook 形式で明文化。

### 8.5 collider bias 規範テンプレート (PR description 用)

```markdown
## T075 collider bias 回避規範 (Phase 2 申し送り、 T071 経由)

T075 smoke harness は collider bias を判定しない:
- holiday_markets / dst_transition_markets / schedule_status の stratified audit
- 因果解釈 (= "FM1 trigger は X が原因" 等)
- 比率差の有意性検定

これらは Phase 2 で T071 RunObservabilityReport 経由で別 caller (= manual review or 後段別 TODO) が判定。
T075 module 内では observability_flags を参照しない (= AST grep DoD で確認)。

### Fact (T075 SSOT)
- check_per_run_smoke_dod は T071 RunObservabilityReport 駆動、 EvidenceClass 分類のみ
- check_cross_run_smoke_dod は 5 Run 集約 epoch 汚染検出のみ
- classify_smoke_outcome は事実認定 (severity + has_inconclusive + observed_fms)
- decide_release_action は manual review hint (= 自動切替指示ではない)

### Phase 2 申し送り
- T071 RunObservabilityReport.smoke field 配線時に stratified audit 経路を別途確保
- run_ga.py adapter で archive read-only 集計
- synthesis Round 22 改訂 5 件 (new_cascade / FM SSOT / DoD 分離 / threshold / stable clause anchor)
```

## 9. Phase 1 / Phase 2 切り分け

### 9.1 Phase 1 (T075 PR)

§ 1.1 全範囲。 単体テストのみで runtime 未組込。

### 9.2 Phase 2 (別 TODO)

- T071 RunObservabilityReport.smoke field 配線
- run_ga.py 唯一の SSOT adapter
- synthesis Round 22 改訂 (5 件)
- 切替コミット (= big-bang 1-shot)
- 旧 src / scripts / config 同日削除

### 9.3 Phase 2 別 TODO (synthesis Round 22 後)

- `select_rollback_relevant_failure_modes` 実装
- 数値 threshold 確定 (= FM1-FM5)
- 自動 rollback / proceed 判定強化

## 10. 参考文献

T075 は数式実装ではなく cleanup + smoke。 補助参照:
- Bailey, D. H., Borwein, J. M., López de Prado, M. M., & Zhu, Q. J. (2015). *The Probability of Backtest Overfitting.* (= 5 Run smoke を性能評価に流用しない牽制)
- Lo, A. W. (2002). *The Statistics of Sharpe Ratios.* (同上)
- Site Reliability Engineering (Beyer et al. 2016) Chap. 8 / Chap. 27 (= release engineering、 manual review、 runtime reachability)

---

これで T075 詳細設計は完成。 概念設計 Round 4 APPROVED 状態を起点に、 Round 4 [W1-W3] / [S1-S4] を全反映。 Codex 詳細レビュー (gpt-5.3-codex / high) で最終確認。
