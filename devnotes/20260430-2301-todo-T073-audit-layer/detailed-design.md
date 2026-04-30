# 詳細設計: T073 — Audit layer (DSR 先行 + PBO/SPA scaffold)

**作成日時**: 2026-04-30 23:55 JST
**設計者**: Claude
**前提**: 概念設計 `conceptual-design.md` Round 3 APPROVED 済 (`conceptual-review-round-3.md`)
**SSOT 規約 (§ 11.2)**: 本詳細設計 §3 / §4 の擬似コードは概念設計 §4 / §5 / §6 と同期。 不一致時は概念設計を正本として優先。
**main 基準**: `975a7ea` (T072 commit 後)
**改訂履歴**: 概念設計 Round 1-3 で出た指摘 (= 13 Critical / 10 Warning / 10 Suggestion) は概念設計に全反映済。
**Round 1 詳細レビュー反映 (2026-05-01 00:25 JST)**: C1-C2 / W1-W6 / S1-S3 を全反映:
- Round D1 [C1]: `_make_sentinel_metric` を keyword-only call SSOT で統一 (= 4.1 全 step で `status=...` keyword 形式)
- Round D1 [C2]: `insufficient_trials` 時の n_observations を「**relevant block 数 (= filter 後)**」 に変更、 「n_observations は実測値」 SSOT 整合
- Round D1 [W1]: AuditNullModel.__post_init__ の invariant 順序を test (= F5_invariant_order_priority) で機械検証
- Round D1 [W2]: `_make_sentinel_metric` の status 型を `AuditDSRStatus` のみに限定 (= not_implemented 静的防止)
- Round D1 [W3]: schema_version helper で MINOR < expected (= consumer 新版で record 旧版) → warning + 不正フォーマット (= "1" / "1.a" / "1.0.0.1") は ValueError
- Round D1 [W4]: cache hit 非加算契約を AuditNullModel docstring + F32 test で明示
- Round D1 [W5]: C2 parallel-path grep DoD 検索語を 11 語に拡張 (= sharpe_ratio / Sharpe / deflated / audit_calc_version / trial_counting_policy_version 追加)
- Round D1 [W6]: collider bias DoD を grep 検証可能な形に強化 (= 「PR description に collider bias 規範文字列を含む」 を CI lint 候補)
- Round D1 [S1]: compute_dsr_strata_with_allowlist に schema_version / flag_namespace 将来拡張点
- Round D1 [S2]: statistics.py docstring 同期更新と audit.py 実装は **同 PR 内別 commit** に分割
- Round D1 [S3]: AuditDSRMetric を genome_id キー原則化 (= AuditGenomeRecord 経由で参照、 単体での hash/eq 衝突を避ける運用規範を docstring 化)

**改訂履歴 (旧)**: 概念 Round 3 で残った Warning (W1-W5) / Suggestion (S1-S4) は本詳細設計で反映:
- Round 3 [W1]: dsr_value と moment 系で sentinel policy 分離 (= DSR_VALUE_SENTINEL / MOMENT_SENTINEL_POLICY)
- Round 3 [W2]: canonical genome dedup の test case 化 (= retry / cache hit / fold 別評価 / seed 違い)
- Round 3 [W3]: `n_trial_candidates_raw` 取得不能時の `raw_count_status` field
- Round 3 [W4]: schema_version check helper を同時提供
- Round 3 [W5]: stratification API guard (= `stratification_mode="marginal"` default + interaction allowlist)
- Round 3 [S1]: `trial_counting_policy_version = "canonical-genome-v1"` field 追加
- Round 3 [S2]: 非 ok field の sentinel policy を field ごとに分離 + docstring
- Round 3 [S3]: 既存 statistics.py docstring 同 PR で更新 (= 別 PR 不可)
- Round 3 [S4]: C2 parallel-path grep の検索語明示 (= deflated_sharpe_ratio / dsr / sharpe_calc_version / archive_role / RunObservabilityReport / audit)

## 0. 詳細設計の責務

概念設計で確定した SSOT (= 純ライブラリ / null model provenance / DSR 6 status / scaffold scaffold-only / stratification marginal) を **コード単位** に展開:
- 完全な擬似コード
- sentinel policy (Round 3 [W1] [S2]) を field ごとに固定
- canonical genome dedup の test 計画 (Round 3 [W2])
- raw_count_status (Round 3 [W3])
- schema_version check helper (Round 3 [W4])
- stratification API guard (Round 3 [W5])
- C2 parallel-path grep DoD (Round 3 [S4])

## 1. ファイル / 関数 / クラス完全リスト

### 1.1 新規ファイル

| Path | 主シンボル | LOC 概算 |
|---|---|---|
| `src/alpha_factory/audit.py` | `AuditDSRStatus`, `AuditScaffoldStatus`, `AuditNullModelKind`, `AuditSRScale`, `AuditTrialSource`, `AUDIT_DSR_MIN_OBSERVATIONS`, `AUDIT_DSR_MIN_TRIALS`, `AUDIT_REPORT_SCHEMA_VERSION`, `AUDIT_DSR_CALC_VERSION`, `AUDIT_SCAFFOLD_CALC_VERSION`, `TRIAL_COUNTING_POLICY_VERSION`, `DSR_VALUE_SENTINEL`, `MOMENT_SENTINEL`, `AuditNullModel`, `AuditDSRMetric`, `AuditPBOMetric`, `AuditSPAMetric`, `AuditGenomeRecord`, `GenomeAuditInput`, `RunAuditReport`, `compute_audit_dsr_for_genome`, `compute_audit_pbo_scaffold`, `compute_audit_spa_scaffold`, `compute_run_audit_report`, `check_audit_record_schema_version`, `compute_marginal_dsr_strata`, `compute_dsr_strata_with_allowlist` | +400 |
| `tests/alpha_factory/test_audit.py` | F1-F40 + happy path | +500 |

### 1.2 既存ファイル変更 (Round 3 [S3])

| Path | 関数 / 行 | 変更内容 | LOC 増減 |
|---|---|---|---|
| `src/alpha_factory/statistics.py:148-238` | `deflated_sharpe_ratio` docstring | "Phase 1A monitor only" 注記を「T073 audit layer (Phase 2 配線後) で v2 SessionBlock SR + AuditNullModel 経由で再呼出。 数式 (Bailey 2014 Eq.(7) (9)) は不変、 v1 archive `dsr` field との sharpe_calc_version 同期は Phase 2」 に更新 (Round 3 [C5] [S3]) | +15 |

### 1.3 Phase 2 申し送り (T073 PR では touch しない)

- T071 詳細設計改訂: RunObservabilityReport に `audit: RunAuditReport` field 追加
- T058 詳細設計改訂: archive `dsr` を `dsr_v1` に rename + 新 `dsr_v2` 追加 (= 履歴比較互換)、 SessionBlock 列を Parquet 列として保存する schema 拡張
- run_ga.py / backtest_runner: compute_run_audit_report 呼出 + RunObservabilityReport 同梱
- PBO / SPA 計算実装は smoke 後別 TODO + AUDIT_REPORT_SCHEMA_VERSION MINOR bump

### 1.4 collider bias 規範 (Round 3 [W5] / 概念 § 11.4)

下流 evaluator (T071 / 後段 analytic) 詳細設計改訂申し送り:
> stratification API は `stratification_mode="marginal"` default、 interaction は allowlist 指定時のみ。 単独 key で drop / filter 禁止、 各 stratum の n を audit log に出力 (Round 3 [W5])。

## 2. 既存 caller signature 完全展開

### 2.1 既存 deflated_sharpe_ratio caller (T073 PR で影響確認)

```bash
grep -rn "deflated_sharpe_ratio\|from.*statistics import" src/ tests/ scripts/ --include="*.py"
```

T073 PR は:
- `audit.py` から `deflated_sharpe_ratio` を import (新規 caller)
- 既存 caller (= archive admission 経路) は touch しない (= Phase 2 で sharpe_calc_version 同期時に v2 切替)

### 2.2 archive `dsr` field caller (T073 PR で touch しない)

```bash
grep -rn '"dsr"\|\.dsr\b' src/alpha_factory/archive.py
```

archive.py:81 (field 定義) / archive.py:169 (template) / archive.py:459 (write) は v1 入力経路のまま、 T073 PR では touch しない。 Phase 2 で `dsr_v1` rename + `dsr_v2` 追加。

### 2.3 grep DoD (Round 3 [S4] / [W5] PR review check)

```bash
# T073 PR 実装時の確認 (= C2 parallel-path)

# audit.py / 既存 archive 経路の干渉なし
grep -rn "from src.alpha_factory.audit import\|import src.alpha_factory.audit" src/ tests/ --include="*.py"
# → Phase 1 では tests のみ、 src/ 配下に T073 module の import が存在しないことを確認

# 検索語 (Round 3 [S4]):
grep -rn "deflated_sharpe_ratio" src/ tests/ --include="*.py"  # 数式 caller
grep -rn '\bdsr\b\|"dsr"' src/ tests/ --include="*.py"          # field 名
grep -rn "sharpe_calc_version" src/ tests/ --include="*.py"     # version 連動
grep -rn "archive_role" src/ tests/ --include="*.py"            # T058 join 鍵
grep -rn "RunObservabilityReport" src/ tests/ --include="*.py"  # T071 拡張点
grep -rn "audit" src/ tests/ --include="*.py"                   # 一般 audit 経路
```

## 3. データモデル詳細 (擬似コード)

### 3.1 型 / 定数 (Round 3 [W1] [S1] 反映)

```python
# src/alpha_factory/audit.py

from __future__ import annotations
import logging
import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

from src.alpha_factory.statistics import deflated_sharpe_ratio
from src.backtest.session_block import SessionBlock


__all__ = [
    "AuditDSRStatus",
    "AuditScaffoldStatus",
    "AuditNullModelKind",
    "AuditSRScale",
    "AuditTrialSource",
    "AUDIT_DSR_MIN_OBSERVATIONS",
    "AUDIT_DSR_MIN_TRIALS",
    "AUDIT_REPORT_SCHEMA_VERSION",
    "AUDIT_DSR_CALC_VERSION",
    "AUDIT_SCAFFOLD_CALC_VERSION",
    "TRIAL_COUNTING_POLICY_VERSION",
    "DSR_VALUE_SENTINEL",
    "MOMENT_SENTINEL",
    "AuditNullModel",
    "AuditDSRMetric",
    "AuditPBOMetric",
    "AuditSPAMetric",
    "AuditGenomeRecord",
    "GenomeAuditInput",
    "RunAuditReport",
    "compute_audit_dsr_for_genome",
    "compute_audit_pbo_scaffold",
    "compute_audit_spa_scaffold",
    "compute_run_audit_report",
    "check_audit_record_schema_version",
    "compute_marginal_dsr_strata",
    "compute_dsr_strata_with_allowlist",
]


logger = logging.getLogger(__name__)


# Status Literal (Round R2 [W4] 分離)
AuditDSRStatus = Literal[
    "ok",
    "insufficient_data",
    "insufficient_trials",
    "degenerate_variance",
    "input_non_finite",
]
AuditScaffoldStatus = Literal["not_implemented"]


# Null model SSOT (Round R2 [C2] [C3] / [S1])
AuditNullModelKind = Literal["standard_normal"]               # Phase 1 のみ
AuditSRScale = Literal["session_block_non_annualized"]
AuditTrialSource = Literal["run_evaluated_genomes_unique_canonical"]


# 定数
AUDIT_DSR_MIN_OBSERVATIONS: Final[int] = 30      # 運用最低観測数 (Round 1 [W1])
AUDIT_DSR_MIN_TRIALS: Final[int] = 2             # 既存 deflated_sharpe_ratio invariant
AUDIT_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"
AUDIT_DSR_CALC_VERSION: Final[str] = "v2"
AUDIT_SCAFFOLD_CALC_VERSION: Final[str] = "scaffold-v1"
TRIAL_COUNTING_POLICY_VERSION: Final[str] = "canonical-genome-v1"   # Round 3 [S1]


# Sentinel policy (Round 3 [W1] [S2] 分離)
# - DSR_VALUE_SENTINEL: dsr_value 用、 値域 [0, 1] 外で fail-closed
# - MOMENT_SENTINEL: sharpe_ratio / skew / kurtosis 用、 「解釈禁止」 を invariant 明示
#   moment 系は sharpe ∈ R / skew ∈ R / kurtosis >= 1 で値域広い、 sentinel は 0 固定で
#   「観察事実保持しない」 を docstring 明示
DSR_VALUE_SENTINEL: Final[Decimal] = Decimal("-1")    # 値域外
MOMENT_SENTINEL: Final[Decimal] = Decimal("0")         # 解釈禁止 sentinel
```

### 3.2 AuditNullModel (Round 3 [S1] [W3] 反映)

```python
@dataclass(frozen=True)
class AuditNullModel:
    """DSR null model provenance (Round R2 [C3] [S1] [S2] / Round 3 [S1] [W3]).

    Phase 1 SSOT:
        null_model_kind = "standard_normal" (= placeholder null、 Bailey 原著 null とは区別)
        sr_scale = "session_block_non_annualized"
        mean_sr_trials = 0
        std_sr_trials = 1
        trial_source = "run_evaluated_genomes_unique_canonical"
        trial_counting_policy_version = "canonical-genome-v1" (Round 3 [S1])
        n_trials = n_trial_candidates_unique
        n_trial_candidates_raw: int (= 評価 attempt 総数、 取得不能時は raw_count_status="unknown" で raw=unique を conservative lower-bound、 Round 3 [W3])
        n_trial_candidates_unique: int

    Phase 2 拡張: archive_sample null_model_kind 追加 + AUDIT_REPORT_SCHEMA_VERSION MINOR bump.
    """

    null_model_kind: AuditNullModelKind
    sr_scale: AuditSRScale
    mean_sr_trials: Decimal
    std_sr_trials: Decimal
    trial_source: AuditTrialSource
    trial_counting_policy_version: str             # Round 3 [S1]
    n_trials: int
    n_trial_candidates_raw: int                    # Round R2 [S2]
    n_trial_candidates_unique: int
    raw_count_status: Literal["measured", "unknown"]   # Round 3 [W3]

    def __post_init__(self) -> None:
        # I-1: null_model_kind == "standard_normal" → mean_sr_trials == 0, std_sr_trials == 1
        if self.null_model_kind == "standard_normal":
            if self.mean_sr_trials != Decimal(0):
                raise ValueError(
                    f"standard_normal null requires mean_sr_trials == 0, got {self.mean_sr_trials}"
                )
            if self.std_sr_trials != Decimal(1):
                raise ValueError(
                    f"standard_normal null requires std_sr_trials == 1, got {self.std_sr_trials}"
                )
        # I-2: sr_scale, trial_source, trial_counting_policy_version は SSOT 値のみ
        if self.sr_scale != "session_block_non_annualized":
            raise ValueError(f"sr_scale must be 'session_block_non_annualized' (Phase 1 SSOT), got {self.sr_scale!r}")
        if self.trial_source != "run_evaluated_genomes_unique_canonical":
            raise ValueError(f"trial_source must be 'run_evaluated_genomes_unique_canonical', got {self.trial_source!r}")
        if self.trial_counting_policy_version != TRIAL_COUNTING_POLICY_VERSION:
            raise ValueError(f"trial_counting_policy_version must be {TRIAL_COUNTING_POLICY_VERSION!r}, got {self.trial_counting_policy_version!r}")
        # I-3: std > 0
        if self.std_sr_trials <= Decimal(0):
            raise ValueError(f"std_sr_trials must be > 0, got {self.std_sr_trials}")
        # I-4: n_trials == n_trial_candidates_unique (重複除外後)
        if self.n_trials != self.n_trial_candidates_unique:
            raise ValueError(
                f"n_trials ({self.n_trials}) must equal n_trial_candidates_unique "
                f"({self.n_trial_candidates_unique})"
            )
        # I-5: raw >= unique (raw=unknown の場合は raw=unique conservative)
        if self.raw_count_status == "measured":
            if self.n_trial_candidates_raw < self.n_trial_candidates_unique:
                raise ValueError(
                    f"raw ({self.n_trial_candidates_raw}) >= unique ({self.n_trial_candidates_unique}) required"
                )
        elif self.raw_count_status == "unknown":
            # raw_count_status="unknown" → raw=unique (conservative lower-bound)
            if self.n_trial_candidates_raw != self.n_trial_candidates_unique:
                raise ValueError(
                    f"raw_count_status='unknown' requires raw == unique (conservative lower-bound)"
                )
        else:
            raise ValueError(f"raw_count_status must be 'measured' or 'unknown', got {self.raw_count_status!r}")
        # I-6: n_trial_candidates_unique >= 0
        if self.n_trial_candidates_unique < 0:
            raise ValueError(f"n_trial_candidates_unique >= 0 required")
        # 注: n_trials >= AUDIT_DSR_MIN_TRIALS は AuditDSRMetric.__post_init__ で
        #     "insufficient_trials" status で表現 (= AuditNullModel 自体は n=0/1 も保持可能、 詳細設計判断)
```

### 3.3 AuditDSRMetric (Round 3 [W1] [S2] 反映の sentinel policy 分離)

```python
@dataclass(frozen=True)
class AuditDSRMetric:
    """genome ごとの DSR 監査結果.

    Sentinel policy (Round 3 [W1] [S2] 分離):
        status="ok":
            dsr_value ∈ [0, 1]
            sharpe_ratio / skew / kurtosis = 観察値 (= 全 finite)
        status != "ok":
            dsr_value == DSR_VALUE_SENTINEL (= Decimal("-1"))
            sharpe_ratio / skew / kurtosis == MOMENT_SENTINEL (= Decimal("0"))
            n_observations は実測値 (= 観察事実として保持)
            **moment 系の MOMENT_SENTINEL 値は「解釈禁止」**:
              0 は sharpe / skew で valid 値だが、 status check で除外する規範.
              docstring で「status != 'ok' 時の moment field は解釈禁止」 明記.
    """

    status: AuditDSRStatus
    dsr_value: Decimal               # status="ok" 以外は DSR_VALUE_SENTINEL (Round 3 [W1])
    n_observations: int              # 実測値、 sentinel ではない
    sharpe_ratio: Decimal            # status="ok" 以外は MOMENT_SENTINEL (解釈禁止)
    skew: Decimal                    # 同上
    kurtosis: Decimal                # 同上
    null_model: AuditNullModel
    audit_calc_version: str          # = AUDIT_DSR_CALC_VERSION = "v2"

    def __post_init__(self) -> None:
        # I-1: audit_calc_version
        if self.audit_calc_version != AUDIT_DSR_CALC_VERSION:
            raise ValueError(
                f"audit_calc_version must be {AUDIT_DSR_CALC_VERSION!r}, got {self.audit_calc_version!r}"
            )
        # I-2: n_observations >= 0
        if self.n_observations < 0:
            raise ValueError(f"n_observations >= 0 required, got {self.n_observations}")
        # I-3: status 別 invariant (Round 3 [W1] [S2])
        if self.status == "ok":
            # 観察値 invariant
            if not (Decimal(0) <= self.dsr_value <= Decimal(1)):
                raise ValueError(
                    f"status='ok' requires dsr_value ∈ [0, 1], got {self.dsr_value}"
                )
            for name, val in (
                ("sharpe_ratio", self.sharpe_ratio),
                ("skew", self.skew),
                ("kurtosis", self.kurtosis),
            ):
                if not math.isfinite(float(val)):
                    raise ValueError(f"status='ok' requires {name} finite, got {val}")
        elif self.status in (
            "insufficient_data",
            "insufficient_trials",
            "degenerate_variance",
            "input_non_finite",
        ):
            # sentinel invariant (Round 3 [W1])
            if self.dsr_value != DSR_VALUE_SENTINEL:
                raise ValueError(
                    f"status={self.status!r} requires dsr_value == DSR_VALUE_SENTINEL "
                    f"(= {DSR_VALUE_SENTINEL}), got {self.dsr_value}"
                )
            for name, val in (
                ("sharpe_ratio", self.sharpe_ratio),
                ("skew", self.skew),
                ("kurtosis", self.kurtosis),
            ):
                if val != MOMENT_SENTINEL:
                    raise ValueError(
                        f"status={self.status!r} requires {name} == MOMENT_SENTINEL "
                        f"(= {MOMENT_SENTINEL}, 解釈禁止), got {val}"
                    )
        else:
            raise ValueError(f"unknown AuditDSRStatus: {self.status!r}")
```

### 3.4 AuditPBOMetric / AuditSPAMetric (scaffold)

```python
@dataclass(frozen=True)
class AuditPBOMetric:
    """PBO scaffold (Round R2 [C4] [S3]、 数値 field なし).

    Phase 2 で field 追加 (= performance_matrix / cscv_n_splits / cscv_logit_estimate / pbo_value):
        AUDIT_REPORT_SCHEMA_VERSION 1.0.0 → 1.1.0 (= MINOR bump、 後方互換)
        ただし pbo_value 等を「実装済」 と判定するため status 拡張 (= AuditScaffoldStatus に "implemented" 追加 or 別 Status Literal)
    """
    status: AuditScaffoldStatus    # = "not_implemented" 固定
    audit_calc_version: str         # = "scaffold-v1"

    def __post_init__(self) -> None:
        if self.status != "not_implemented":
            raise ValueError(
                f"AuditPBOMetric.status must be 'not_implemented' (scaffold), got {self.status!r}"
            )
        if self.audit_calc_version != AUDIT_SCAFFOLD_CALC_VERSION:
            raise ValueError(
                f"audit_calc_version must be {AUDIT_SCAFFOLD_CALC_VERSION!r}, got {self.audit_calc_version!r}"
            )


@dataclass(frozen=True)
class AuditSPAMetric:
    """SPA scaffold (同 SSOT)."""
    status: AuditScaffoldStatus
    audit_calc_version: str

    def __post_init__(self) -> None:
        if self.status != "not_implemented":
            raise ValueError(...)
        if self.audit_calc_version != AUDIT_SCAFFOLD_CALC_VERSION:
            raise ValueError(...)
```

### 3.5 AuditGenomeRecord / GenomeAuditInput / RunAuditReport

```python
@dataclass(frozen=True)
class AuditGenomeRecord:
    """genome 単位の audit record (T058 join 可)."""
    genome_id: str
    archive_role: str
    source_stage: str
    dsr_metric: AuditDSRMetric

    def __post_init__(self) -> None:
        if not self.genome_id:
            raise ValueError("genome_id must be non-empty")


@dataclass(frozen=True)
class GenomeAuditInput:
    """compute_run_audit_report の per-genome 入力 (Phase 1 in-memory transport)."""
    genome_id: str
    archive_role: str
    source_stage: str
    session_blocks: Sequence[SessionBlock]


@dataclass(frozen=True)
class RunAuditReport:
    """1 Run 全体の audit 集約 (Phase 2 で T071 RunObservabilityReport.audit field 配線対象)."""
    run_id: str
    dataset_epoch_id: str
    n_genomes: int
    per_genome: tuple[AuditGenomeRecord, ...]
    pbo: AuditPBOMetric
    spa: AuditSPAMetric
    audit_report_schema_version: str   # = AUDIT_REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.audit_report_schema_version != AUDIT_REPORT_SCHEMA_VERSION:
            raise ValueError(
                f"audit_report_schema_version must be {AUDIT_REPORT_SCHEMA_VERSION!r}, "
                f"got {self.audit_report_schema_version!r}"
            )
        if len(self.per_genome) != self.n_genomes:
            raise ValueError(
                f"len(per_genome) ({len(self.per_genome)}) != n_genomes ({self.n_genomes})"
            )
        # 全 dsr_metric の audit_calc_version 整合
        for record in self.per_genome:
            if record.dsr_metric.audit_calc_version != AUDIT_DSR_CALC_VERSION:
                raise ValueError(
                    f"genome_id={record.genome_id!r}: dsr_metric.audit_calc_version mismatch"
                )
        # 全 dsr_metric.null_model が同一 (= Run 内一様、 Phase 1 default)
        if self.per_genome:
            first_null = self.per_genome[0].dsr_metric.null_model
            for record in self.per_genome[1:]:
                if record.dsr_metric.null_model != first_null:
                    raise ValueError(
                        f"genome_id={record.genome_id!r}: null_model differs from run-level (Phase 1 invariant)"
                    )
        # PBO / SPA scaffold version 整合
        if self.pbo.audit_calc_version != AUDIT_SCAFFOLD_CALC_VERSION:
            raise ValueError(...)
        if self.spa.audit_calc_version != AUDIT_SCAFFOLD_CALC_VERSION:
            raise ValueError(...)
```

## 4. アルゴリズム詳細 (擬似コード)

### 4.1 compute_audit_dsr_for_genome (Round 3 [W1] [S2] sentinel policy)

```python
def compute_audit_dsr_for_genome(
    session_blocks: Sequence[SessionBlock],
    *,
    null_model: AuditNullModel,
) -> AuditDSRMetric:
    """SSOT: 概念設計 § 6.1.

    sentinel policy (Round 3 [W1] / Round D1 [C1] [C2]):
        status != "ok" → dsr_value=DSR_VALUE_SENTINEL, moment 系=MOMENT_SENTINEL.
        n_observations は **常に実測値 (= filter 後の block 数)** を保持 (Round D1 [C2]).
        `_make_sentinel_metric` は **keyword-only 呼出** (Round D1 [C1]).
    """
    # Round D1 [C2]: relevant filter を Step 0 より前に行い、 n を全 step で実測値として渡す
    relevant = [b for b in session_blocks if b.open_minutes > 0]
    n = len(relevant)

    # Step 0: insufficient_trials (Round R2 [W3] / Round D1 [C1] [C2])
    if null_model.n_trials < AUDIT_DSR_MIN_TRIALS:
        return _make_sentinel_metric(
            status="insufficient_trials",
            null_model=null_model,
            n_observations=n,    # Round D1 [C2]: 実測値、 0 固定でない
        )

    # Step 2: insufficient_data
    if n < AUDIT_DSR_MIN_OBSERVATIONS:
        return _make_sentinel_metric(
            status="insufficient_data",
            null_model=null_model,
            n_observations=n,
        )

    # Step 3: pnl_net 列の moment 推定
    pnls = [float(b.pnl_net) for b in relevant]
    mean = statistics.fmean(pnls)
    variance = statistics.variance(pnls)  # n-1 unbiased

    # Step 3a: degenerate_variance
    if variance < 1e-20:
        return _make_sentinel_metric(
            status="degenerate_variance",
            null_model=null_model,
            n_observations=n,
        )

    stdev = math.sqrt(variance)
    sharpe = mean / stdev
    skew_val = sum((r - mean) ** 3 for r in pnls) / (n * stdev ** 3)
    kurt_val = sum((r - mean) ** 4 for r in pnls) / (n * stdev ** 4)  # non-excess

    # Step 3b: input_non_finite check
    for v in (sharpe, skew_val, kurt_val):
        if not math.isfinite(v):
            return _make_sentinel_metric(
                status="input_non_finite",
                null_model=null_model,
                n_observations=n,
            )

    # Step 4: 既存 deflated_sharpe_ratio 呼出
    try:
        dsr = deflated_sharpe_ratio(
            sharpe_ratio=sharpe,
            n_trials=null_model.n_trials,
            n_observations=n,
            skew=skew_val,
            kurtosis=kurt_val,
            mean_sr_trials=float(null_model.mean_sr_trials),
            std_sr_trials=float(null_model.std_sr_trials),
        )
    except ValueError:
        return _make_sentinel_metric(
            status="input_non_finite",
            null_model=null_model,
            n_observations=n,
        )

    # Step 5: 成功 case
    return AuditDSRMetric(
        status="ok",
        dsr_value=Decimal(str(dsr)),
        n_observations=n,
        sharpe_ratio=Decimal(str(sharpe)),
        skew=Decimal(str(skew_val)),
        kurtosis=Decimal(str(kurt_val)),
        null_model=null_model,
        audit_calc_version=AUDIT_DSR_CALC_VERSION,
    )


_SENTINEL_DSR_STATUSES: Final[frozenset[AuditDSRStatus]] = frozenset({
    "insufficient_data",
    "insufficient_trials",
    "degenerate_variance",
    "input_non_finite",
})


def _make_sentinel_metric(
    *,
    status: AuditDSRStatus,    # Round D1 [W2]: AuditDSRStatus に限定 (= not_implemented 流入防止)
    null_model: AuditNullModel,
    n_observations: int,
) -> AuditDSRMetric:
    """Round 3 [W1] [S2] / Round D1 [C1] [W2] sentinel policy:
    - keyword-only call (= 構造的強制)
    - status は AuditDSRStatus かつ "ok" 以外の sentinel status のみ受理
    - dsr_value / moment 系を sentinel 固定、 n_observations は実測値.
    """
    if status not in _SENTINEL_DSR_STATUSES:
        raise ValueError(
            f"_make_sentinel_metric: status must be in _SENTINEL_DSR_STATUSES "
            f"(= {sorted(_SENTINEL_DSR_STATUSES)}), got {status!r}"
        )
    return AuditDSRMetric(
        status=status,
        dsr_value=DSR_VALUE_SENTINEL,
        n_observations=n_observations,
        sharpe_ratio=MOMENT_SENTINEL,
        skew=MOMENT_SENTINEL,
        kurtosis=MOMENT_SENTINEL,
        null_model=null_model,
        audit_calc_version=AUDIT_DSR_CALC_VERSION,
    )
```

### 4.2 compute_audit_pbo_scaffold / compute_audit_spa_scaffold

```python
def compute_audit_pbo_scaffold(*, audit_calc_version: str = AUDIT_SCAFFOLD_CALC_VERSION) -> AuditPBOMetric:
    return AuditPBOMetric(
        status="not_implemented",
        audit_calc_version=audit_calc_version,
    )


def compute_audit_spa_scaffold(*, audit_calc_version: str = AUDIT_SCAFFOLD_CALC_VERSION) -> AuditSPAMetric:
    return AuditSPAMetric(
        status="not_implemented",
        audit_calc_version=audit_calc_version,
    )
```

### 4.3 compute_run_audit_report

```python
def compute_run_audit_report(
    *,
    run_id: str,
    dataset_epoch_id: str,
    per_genome: Mapping[str, GenomeAuditInput],
    null_model: AuditNullModel,
) -> RunAuditReport:
    """archive 全 genome を走査して RunAuditReport を構築.

    deterministic order: genome_id (str sort).
    null_model は Run 内一様 (Phase 1 default).
    """
    records = tuple(
        AuditGenomeRecord(
            genome_id=inp.genome_id,
            archive_role=inp.archive_role,
            source_stage=inp.source_stage,
            dsr_metric=compute_audit_dsr_for_genome(
                inp.session_blocks, null_model=null_model,
            ),
        )
        for genome_id, inp in sorted(per_genome.items())
    )
    return RunAuditReport(
        run_id=run_id,
        dataset_epoch_id=dataset_epoch_id,
        n_genomes=len(records),
        per_genome=records,
        pbo=compute_audit_pbo_scaffold(),
        spa=compute_audit_spa_scaffold(),
        audit_report_schema_version=AUDIT_REPORT_SCHEMA_VERSION,
    )
```

### 4.4 schema_version check helper (Round 3 [W4])

```python
def check_audit_record_schema_version(
    record_schema_version: str,
    *,
    expected: str = AUDIT_REPORT_SCHEMA_VERSION,
) -> None:
    """Round 3 [W4] / Round D1 [W3] 反映: consumer 側で schema バージョン整合を確認.

    bump 規約 (概念 § 11.6):
        MAJOR: 既存 field 削除 / 意味変更 (= 互換性破壊)
        MINOR: field 追加 (= 既存 caller は新 field を ignore)
        PATCH: 出力値 bug fix (= schema 不変)

    挙動 (Round D1 [W3]):
        - MAJOR mismatch (= received[0] != expected[0]) → ValueError raise
        - received[1] > expected[1] (= consumer 旧版で record 新版) → warning log emit
        - received[1] < expected[1] (= consumer 新版で record 旧版) → warning log emit
          (= 旧版 record に新 field が無いことを caller が認識すべき)
        - received[2] != expected[2] (= PATCH 差) → silent (= schema 不変)
        - 不正フォーマット (= "1" / "1.a" / "1.0.0.1" 等) → ValueError raise

    Args:
        record_schema_version: 受信 record の schema_version 文字列.
        expected: 期待する schema_version (default = AUDIT_REPORT_SCHEMA_VERSION).

    Raises:
        ValueError: MAJOR mismatch / 不正フォーマット.
    """
    # Round D1 [W3]: 不正フォーマット reject
    received_parts = record_schema_version.split(".")
    expected_parts = expected.split(".")
    if len(received_parts) != 3:
        raise ValueError(
            f"audit_record_schema_version must be 'MAJOR.MINOR.PATCH', got {record_schema_version!r}"
        )
    try:
        received = tuple(int(x) for x in received_parts)
        expected_int = tuple(int(x) for x in expected_parts)
    except ValueError as e:
        raise ValueError(
            f"audit_record_schema_version parse failed: {record_schema_version!r}"
        ) from e

    # MAJOR mismatch
    if received[0] != expected_int[0]:
        raise ValueError(
            f"audit_record_schema_version MAJOR mismatch: expected {expected}, got {record_schema_version}"
        )
    # MINOR diff (両方向)
    if received[1] > expected_int[1]:
        logger.warning(
            "audit_record_schema_version MINOR mismatch (record newer than consumer): "
            "expected=%s, got=%s. consumer may need update to read new fields.",
            expected, record_schema_version,
        )
    elif received[1] < expected_int[1]:
        logger.warning(
            "audit_record_schema_version MINOR mismatch (record older than consumer): "
            "expected=%s, got=%s. caller should know record may lack newer fields.",
            expected, record_schema_version,
        )
    # PATCH 差は silent
```

### 4.5 stratification API guard (Round 3 [W5])

```python
def compute_marginal_dsr_strata(
    report: RunAuditReport,
    *,
    flag_lookup: Mapping[str, ObservabilityFlags],   # genome_id -> flags (= caller が aggregate)
) -> dict[str, dict[Any, list[AuditGenomeRecord]]]:
    """Round 3 [W5] / 概念 § 11.4 stratification marginal default.

    SSOT: marginal 集計のみ (= 各 key 独立 1 軸 group_by).
        - "by_holiday_markets":         {holiday_markets: [records...]}
        - "by_dst_transition_markets":  {dst_transition_markets: [records...]}
        - "by_schedule_status":         {schedule_status: [records...]}
    interaction (= 2 軸以上 cross product) は本関数では計算しない.
    interaction が必要な caller は compute_dsr_strata_with_allowlist を使う.
    """
    ...


def compute_dsr_strata_with_allowlist(
    report: RunAuditReport,
    *,
    flag_lookup: Mapping[str, ObservabilityFlags],
    allowlist: Sequence[tuple[str, ...]],   # 例: (("holiday_markets", "schedule_status"),)
    schema_version: str = "1.0.0",          # Round D1 [S1] 将来拡張点
    flag_namespace: str = "t072",           # Round D1 [S1] 将来拡張点
) -> dict[tuple[str, ...], dict[Any, list[AuditGenomeRecord]]]:
    """Round 3 [W5] / Round D1 [S1] interaction allowlist API.

    SSOT: allowlist で指定された 2 軸以上の cross product のみ計算.
    各 stratum で C7 規範 n >= 30 不充足の場合は warning log emit.

    Round D1 [S1] 将来拡張点:
        schema_version: stratification API SSOT。 Phase 2 で T058 archive 経由切替時に bump.
        flag_namespace: T072 ObservabilityFlags 以外の flag namespace (= "t072" / "t074" 等) を caller が指定可能。
            Phase 1 では "t072" のみ受理.

    Raises:
        ValueError: schema_version mismatch / flag_namespace 不正.
    """
    if schema_version != "1.0.0":
        raise ValueError(f"stratification schema_version must be '1.0.0' (Phase 1), got {schema_version!r}")
    if flag_namespace != "t072":
        raise ValueError(f"flag_namespace must be 't072' (Phase 1), got {flag_namespace!r}")
    ...
```

注: `flag_lookup` の入力源は Phase 2 で T058 archive 経由 (= per-genome SessionBlock から flags 集約) で配線。 Phase 1 では caller が手動で渡す in-memory transport。

## 5. テスト計画 (詳細、 概念 § 10 + Round 3 [W2] [W4] [W5] 反映)

### 5.0 命名規約

`Fxxx_<behavior>` 形式で pytest 関数名と 1:1 対応 (T072 detailed-design § 5.0 と同様)。

### 5.1 `tests/alpha_factory/test_audit.py` (新規)

#### F1-F4: 定数 / Literal tests

| test_id | 内容 | pytest 関数名 |
|---|---|---|
| F1_constants | AUDIT_DSR_MIN_OBSERVATIONS=30 / AUDIT_DSR_MIN_TRIALS=2 / AUDIT_REPORT_SCHEMA_VERSION="1.0.0" / AUDIT_DSR_CALC_VERSION="v2" / AUDIT_SCAFFOLD_CALC_VERSION="scaffold-v1" / TRIAL_COUNTING_POLICY_VERSION="canonical-genome-v1" / DSR_VALUE_SENTINEL=Decimal("-1") / MOMENT_SENTINEL=Decimal("0") | `test_audit_constants_match_ssot` |
| F2_dsr_status_values | AuditDSRStatus は 5 値、 not_implemented を含まない | `test_audit_dsr_status_excludes_not_implemented` |
| F3_scaffold_status_values | AuditScaffoldStatus は "not_implemented" 1 値 | `test_audit_scaffold_status_only_not_implemented` |
| F4_null_model_kind_phase1 | AuditNullModelKind Phase 1 = "standard_normal" のみ | `test_audit_null_model_kind_phase1_standard_normal_only` |

#### F5-F12: AuditNullModel tests (Round 3 [S1] [W3])

| F5_invariant_order_priority | Round D1 [W1]: __post_init__ 検証順序 (= I-1 → I-2 → ... → I-6) を test で固定。 例: null_model_kind 不正 + sr_scale 不正 + n_trials 不一致 を全部 violate した object 構築試行 → 最初の I-1 が raise する error message を assert | `test_null_model_invariant_order_priority` |
| F5b_standard_normal_invariant | null_model_kind="standard_normal" + mean=1 → ValueError | `test_null_model_standard_normal_requires_mean_zero` |
| F6_standard_normal_std_invariant | null_model_kind="standard_normal" + std=2 → ValueError | `test_null_model_standard_normal_requires_std_one` |
| F7_sr_scale_invariant | sr_scale="annualized" → ValueError | `test_null_model_sr_scale_phase1_invariant` |
| F8_trial_source_invariant | trial_source="archive_cardinality" → ValueError | `test_null_model_trial_source_invariant` |
| F9_trial_counting_policy_version | trial_counting_policy_version="canonical-genome-v2" → ValueError | `test_null_model_trial_counting_policy_version_invariant` |
| F10_n_trials_equals_unique | n_trials != n_trial_candidates_unique → ValueError | `test_null_model_n_trials_equals_unique` |
| F11_raw_count_measured | raw_count_status="measured" + raw < unique → ValueError | `test_null_model_raw_count_measured_lower_bound` |
| F12_raw_count_unknown | raw_count_status="unknown" + raw != unique → ValueError、 raw==unique → pass | `test_null_model_raw_count_unknown_conservative` |

#### F13-F22: AuditDSRMetric tests (Round 3 [W1] [S2] sentinel policy)

| F13_dsr_status_ok_dsr_in_range | status="ok" + dsr_value=1.5 → ValueError | `test_audit_dsr_metric_ok_dsr_in_zero_one_range` |
| F14_dsr_status_ok_finite_moments | status="ok" + sharpe=NaN → ValueError | `test_audit_dsr_metric_ok_requires_finite_moments` |
| F15_dsr_status_sentinel_value | status="insufficient_data" + dsr_value=Decimal("0.5") → ValueError | `test_audit_dsr_metric_status_non_ok_dsr_sentinel` |
| F16_dsr_status_sentinel_moments | status="insufficient_data" + sharpe=Decimal("0.1") → ValueError | `test_audit_dsr_metric_status_non_ok_moment_sentinel` |
| F17_dsr_audit_calc_version | audit_calc_version="v1" → ValueError | `test_audit_dsr_metric_calc_version_invariant` |
| F18_dsr_n_observations_non_negative | n_observations=-1 → ValueError | `test_audit_dsr_metric_n_observations_non_negative` |
| F19_unknown_status | status="bad_status" → ValueError | `test_audit_dsr_metric_unknown_status_raises` |
| F19b_dsr_metric_rejects_not_implemented | Round D1 [W2]: AuditDSRMetric(status="not_implemented", ...) → ValueError (= AuditDSRStatus 5 値外) | `test_audit_dsr_metric_rejects_not_implemented_status` |
| F19c_make_sentinel_rejects_ok | Round D1 [W2]: _make_sentinel_metric(status="ok", ...) → ValueError (= _SENTINEL_DSR_STATUSES 外) | `test_make_sentinel_metric_rejects_ok_status` |
| F19d_make_sentinel_keyword_only | Round D1 [C1]: _make_sentinel_metric を位置引数で呼出 → TypeError | `test_make_sentinel_metric_requires_keyword_args` |
| F21b_compute_dsr_insufficient_trials_n_obs_preserved | Round D1 [C2]: insufficient_trials 時に n_observations は filter 後の実測値を保持 (= 0 固定でない) | `test_compute_audit_dsr_insufficient_trials_preserves_n_observations` |
| F20_compute_dsr_happy | n=100、 random returns、 status="ok"、 dsr_value ∈ [0, 1] | `test_compute_audit_dsr_for_genome_happy_path` |
| F21_compute_dsr_insufficient_trials | n_trials=1 → status="insufficient_trials" | `test_compute_audit_dsr_for_genome_insufficient_trials` |
| F22_compute_dsr_insufficient_data | open_minutes>0 が 5 個のみ → status="insufficient_data" | `test_compute_audit_dsr_for_genome_insufficient_data` |
| F22b_compute_dsr_degenerate_variance | 全 pnl_net=0 → status="degenerate_variance" | `test_compute_audit_dsr_for_genome_degenerate_variance` |
| F22c_compute_dsr_input_non_finite | pnl_net に NaN → status="input_non_finite" | `test_compute_audit_dsr_for_genome_input_non_finite` |

#### F23-F26: PBO/SPA scaffold tests (Round R2 [C4] [S3])

| F23_pbo_scaffold_factory | compute_audit_pbo_scaffold() → status="not_implemented" / audit_calc_version="scaffold-v1" | `test_compute_audit_pbo_scaffold_factory` |
| F24_pbo_scaffold_no_value_field | AuditPBOMetric の field 列に pbo_value 等の数値 field なし (= dataclasses.fields() 列確認) | `test_audit_pbo_metric_has_no_numeric_fields` |
| F25_spa_scaffold_factory | 同 (SPA) | `test_compute_audit_spa_scaffold_factory` |
| F26_scaffold_no_raise | scaffold 関数は NotImplementedError raise しない (= status return SSOT) | `test_audit_scaffold_does_not_raise` |

#### F27-F30: AuditGenomeRecord / GenomeAuditInput / RunAuditReport tests

| F27_genome_record_id_non_empty | genome_id="" → ValueError | `test_audit_genome_record_id_non_empty` |
| F28_run_audit_schema_version | audit_report_schema_version="9.9.9" → ValueError | `test_run_audit_report_schema_version_invariant` |
| F29_run_audit_n_genomes_match | len(per_genome) != n_genomes → ValueError | `test_run_audit_report_n_genomes_match` |
| F30_run_audit_uniform_null_model | per_genome[0].null_model != per_genome[1].null_model → ValueError | `test_run_audit_report_uniform_null_model_invariant` |

#### F31-F35: canonical genome dedup tests (Round 3 [W2])

| F31_dedup_retry_same_id | 同一 canonical genome_id の retry を raw=2 / unique=1 で dedup (= SSOT: caller が retry 別 trial にしない) | `test_canonical_genome_dedup_retry_counted_once` |
| F32_dedup_cache_hit_excluded | **cache hit は raw にも含めない** (Round D1 [W4] 契約境界明示): 一度評価済 genome の cache replay は raw=1 / unique=1。 caller dedup の SSOT を mock で固定 | `test_canonical_genome_dedup_cache_hit_excluded_from_raw_and_unique` |
| F33_dedup_fold_evaluation | 同一 canonical genome_id の fold 別評価は unique=1 / raw=fold 数 (= raw に fold 数含む) | `test_canonical_genome_dedup_fold_evaluation_counts_raw` |
| F34_dedup_seed_variation | 同一 canonical genome_id (= seed 違いだが genome hash 同) を unique=1 で dedup | `test_canonical_genome_dedup_seed_variation_unique` |
| F35_dedup_unique_canonical_id | 異なる canonical genome_id (= 異 hash) を unique=2 でカウント | `test_canonical_genome_dedup_distinct_canonical_ids` |

注: F31-F35 は **caller (= GA runner) 側の dedup 実装責務**、 T073 の AuditNullModel は受け取った n_trials / n_trial_candidates_raw / unique を __post_init__ で invariant 検証するのみ。 caller dedup の test は本 T073 PR では「invariant が caller dedup 結果を正しく受領する」 ことを mock で検証。

#### F36-F38: schema_version helper tests (Round 3 [W4])

| F36_schema_check_match | check_audit_record_schema_version("1.0.0") → 正常 (= log emit なし) | `test_check_audit_record_schema_version_match` |
| F37_schema_check_minor_newer | check_audit_record_schema_version("1.1.0") → warning log emit (= record newer)、 raise しない | `test_check_audit_record_schema_version_minor_newer_warns` |
| F37b_schema_check_minor_older | Round D1 [W3]: caller が consumer 新版 + record 旧版 case (= "0.5.0" を expected="1.0.0" で受信) → ValueError MAJOR mismatch | `test_check_audit_record_schema_version_minor_older_when_major_differs_raises` |
| F37c_schema_check_minor_older_same_major | expected="1.5.0" / received="1.0.0" → warning (= record older)、 raise しない | `test_check_audit_record_schema_version_minor_older_same_major_warns` |
| F38_schema_check_major_mismatch | check_audit_record_schema_version("2.0.0") → ValueError | `test_check_audit_record_schema_version_major_mismatch_raises` |
| F38b_schema_check_invalid_format | "1" / "1.a" / "1.0.0.1" / "" → ValueError (Round D1 [W3]) | `test_check_audit_record_schema_version_invalid_format_raises` |

#### F39-F40: stratification tests (Round 3 [W5])

| F39_marginal_strata | compute_marginal_dsr_strata: 3 軸 marginal 集計のみ、 interaction 計算しない | `test_compute_marginal_dsr_strata_no_interaction` |
| F40_allowlist_strata | compute_dsr_strata_with_allowlist: allowlist 内の 2 軸 cross product のみ集計 | `test_compute_dsr_strata_with_allowlist_only_listed` |
| F40b_allowlist_empty_no_interaction | allowlist=() (= empty) → interaction 計算なし、 各 stratum に record なし | `test_compute_dsr_strata_with_allowlist_empty_returns_empty` |
| F40c_allowlist_insufficient_n_warns | n<30 の stratum で warning log emit (= C7 規範、 Round 3 [W5]) | `test_compute_dsr_strata_with_allowlist_warns_on_small_stratum` |
| F40d_allowlist_schema_version_mismatch | schema_version="2.0.0" → ValueError | `test_compute_dsr_strata_schema_version_invariant` |
| F40e_allowlist_flag_namespace_mismatch | flag_namespace="t074" → ValueError (Phase 1 では "t072" のみ) | `test_compute_dsr_strata_flag_namespace_invariant` |

### 5.2 collider bias 規範 tests (T072 申し送り、 概念 § 11.4)

`F22d_collider_bias_holiday_inclusive`: bucket="ny" / Tokyo holiday の block も `open_minutes > 0` なら DSR 計算に含める (= 単独除外しない、 stratified audit responsibility は caller)

```python
def test_compute_audit_dsr_includes_holiday_blocks_for_collider_bias_avoidance():
    """T072 collider bias 規範継承 (概念 § 11.4)."""
    blocks = [
        SessionBlock(..., bucket="ny", open_minutes=480,
                     observability_flags=ObservabilityFlags(
                         dst_transition_markets=frozenset(),
                         holiday_markets=frozenset({"tokyo"}),  # Tokyo holiday
                     )),
        ...
    ]
    metric = compute_audit_dsr_for_genome(blocks, null_model=null_model)
    assert metric.n_observations == len(blocks)  # holiday block も含む
```

### 5.3 既存 statistics.py との整合 tests

| F41_statistics_consistency | compute_audit_dsr_for_genome の出力 dsr_value は同 input で deflated_sharpe_ratio 直呼出と一致 | `test_compute_audit_dsr_matches_statistics_direct_call` |
| F42_archive_dsr_field_untouched | T073 PR で archive.py:81 の `dsr` field 計算経路が変更されていない (= grep DoD) | `test_archive_dsr_field_untouched_by_t073` |

## 6. 既存挙動への影響 (C2 parallel-path、 Round 3 [S4] grep DoD)

### 6.1 既存 statistics.py docstring 同期更新 (Round 3 [C5] [S3])

T073 PR で同 PR 更新:

```python
# src/alpha_factory/statistics.py:148-238 docstring 更新

def deflated_sharpe_ratio(...) -> float:
    """Bailey & Lopez de Prado (2014) の Deflated Sharpe Ratio。

    値域 [0, 1]。 観測 Sharpe Ratio が N 個の独立試行の最大値 (null hypothesis: 真の SR=0)
    を有意に上回る確率。

    NOTE (Phase 1A monitor only / T073 audit layer):
        Phase 1A: 本関数は v1 bar-level annualized Sharpe を入力前提、 archive `dsr` field
        は v1 経路で計算済 (sharpe_calc_version v1)。

        T073 audit layer (Phase 2 配線後): src/alpha_factory/audit.py の
        compute_audit_dsr_for_genome 経由で、 v2 SessionBlock pnl_net (= non-annualized)
        + AuditNullModel 駆動で本関数を呼出。 数式 (Eq.(7)/(9)) は不変、 入力尺度は
        AuditNullModel.sr_scale="session_block_non_annualized" SSOT で固定。

        archive `dsr` field の v1 → v2 切替は Phase 2 別 PR で sharpe_calc_version 同期 +
        `dsr_v1` rename + `dsr_v2` 追加 (= 履歴比較互換)。
    """
```

### 6.2 grep DoD (Round 3 [S4] / Round D1 [W5] PR review check、 11 検索語)

```bash
# T073 PR 実装時の確認

# 1. audit.py / 既存 archive 経路の干渉なし (= Phase 1 では tests のみが import)
grep -rn "from src.alpha_factory.audit import\|import src.alpha_factory.audit" src/ --include="*.py"
# 期待: 0 件 (= src/ 配下に T073 module の import が存在しない)

grep -rn "from src.alpha_factory.audit import\|import src.alpha_factory.audit" tests/ --include="*.py"
# 期待: 1 件 (= tests/alpha_factory/test_audit.py のみ)

# 2. 検索語 (Round 3 [S4] / Round D1 [W5] で 11 語に拡張):
grep -rn "deflated_sharpe_ratio" src/ tests/ --include="*.py"          # (1) 数式関数名
grep -rn '\bdsr\b\|"dsr"\b' src/ tests/ --include="*.py"               # (2) field 名
grep -rn "sharpe_calc_version" src/ tests/ --include="*.py"            # (3) version 連動
grep -rn "archive_role" src/ tests/ --include="*.py"                   # (4) T058 join 鍵
grep -rn "RunObservabilityReport" src/ tests/ --include="*.py"         # (5) T071 拡張点
grep -rn "\baudit\b" src/ tests/ --include="*.py"                      # (6) 一般 audit
grep -rn "sharpe_ratio\|\bSharpe\b" src/ tests/ --include="*.py"        # (7)(8) Sharpe 表記揺れ (Round D1 [W5])
grep -rn "deflated" src/ tests/ --include="*.py"                       # (9) 派生表記 (Round D1 [W5])
grep -rn "audit_calc_version" src/ tests/ --include="*.py"             # (10) audit version 連動 (Round D1 [W5])
grep -rn "trial_counting_policy_version" src/ tests/ --include="*.py"  # (11) policy version 連動 (Round D1 [W5])
```

期待挙動:
- (1) 既存 statistics.py 自体 + 既存 archive `dsr` 経路 caller + 新規 audit.py wrapper + tests
- (2) 既存 archive `dsr` field 経路 + audit.py docstring のみ (= field 名衝突なし)
- (3) 既存 archive 経路のみ、 audit.py は touch しない (= Phase 2 で v2 同期)
- (4) T058 (= archive.py) + 新規 AuditGenomeRecord
- (5) T071 (= 設計のみ、 src 未実装)、 audit.py は touch しない (= Phase 2)
- (6) 新規 audit.py + 既存 docstring のみ
- (7)(8)(9) 既存実装のみ、 audit.py は wrapper 経由
- (10)(11) 新規 audit.py + tests のみ

## 7. 失敗モード / fail-closed 経路

| ID | 失敗パターン | 対応 |
|---|---|---|
| FC1 | AuditNullModel.null_model_kind != "standard_normal" (Phase 1) | __post_init__ ValueError |
| FC2 | AuditNullModel の sr_scale / trial_source / trial_counting_policy_version SSOT 違反 | __post_init__ ValueError |
| FC3 | n_trials != n_trial_candidates_unique | __post_init__ ValueError (Round 3 [S2]) |
| FC4 | raw_count_status="measured" + raw < unique | __post_init__ ValueError |
| FC5 | raw_count_status="unknown" + raw != unique | __post_init__ ValueError (= conservative lower-bound 違反) |
| FC6 | AuditDSRMetric の status / dsr_value / moment 系の sentinel policy 違反 | __post_init__ ValueError |
| FC7 | AuditPBOMetric.status != "not_implemented" | __post_init__ ValueError |
| FC8 | RunAuditReport.audit_report_schema_version SSOT 違反 | __post_init__ ValueError |
| FC9 | RunAuditReport の per_genome len != n_genomes | __post_init__ ValueError |
| FC10 | RunAuditReport の per_genome null_model 不一致 (= Run 内非一様) | __post_init__ ValueError |
| FC11 | check_audit_record_schema_version で MAJOR mismatch | ValueError |
| FC12 | check_audit_record_schema_version で MINOR mismatch | warning log emit (= 後方互換、 raise しない) |

## 8. backward-compat 互換性 (T072 § 11 同様の 4 面)

T073 は新規 module + 既存 statistics.py docstring 更新のみ:

### 8.1 constructor 互換
- 既存 `deflated_sharpe_ratio` は signature 不変、 既存 caller は影響なし
- 既存 archive `dsr` field 経路は touch しない (= grep 確認済)

### 8.2 eq / hash 互換
- 新規 dataclass は frozen + eq/hash auto、 既存型との衝突なし

### 8.3 serialization / asdict / repr 互換
- 既存 archive Parquet schema は touch しない (= dsr field の type / 値経路不変)
- audit.py の dataclass は to_record メソッド未実装 (= Phase 2 で T058 join 時に追加検討)

### 8.4 既存 fixture / snapshot 互換
- 既存 deflated_sharpe_ratio test は signature 不変で touch なし
- archive snapshot test は touch しない

## 9. DoD (Definition of Done)

T073 PR が完了するための最小条件:

### 9.1 実装完了

- [ ] `src/alpha_factory/audit.py` 新規、 § 3 / § 4 全関数 + 全 dataclass + 全定数実装
- [ ] `src/alpha_factory/statistics.py:148-238` docstring 同期更新 (Round 3 [C5] [S3])
- [ ] dsr_value 用 `DSR_VALUE_SENTINEL = Decimal("-1")` / moment 用 `MOMENT_SENTINEL = Decimal("0")` の sentinel policy 分離 (Round 3 [W1] [S2])
- [ ] AuditNullModel に `trial_counting_policy_version="canonical-genome-v1"` + `raw_count_status: Literal["measured", "unknown"]` (Round 3 [S1] [W3])
- [ ] `check_audit_record_schema_version` helper 実装 (Round 3 [W4])
- [ ] `compute_marginal_dsr_strata` / `compute_dsr_strata_with_allowlist` API 実装 (Round 3 [W5])

### 9.2 テスト

- [ ] `tests/alpha_factory/test_audit.py` 新規、 § 5 全 test pass (= F1-F42)
- [ ] mypy / ruff pass

### 9.3 互換性 / 監査

- [ ] **C2 parallel-path grep DoD** 実行 (Round 3 [S4]):
  - audit.py を src/ から import する経路 0 件 (= tests のみ)
  - 既存 archive `dsr` field 経路は touch しない
  - 検索語 (deflated_sharpe_ratio / dsr / sharpe_calc_version / archive_role / RunObservabilityReport / audit) 各々で grep 結果整合
- [ ] PR description に **collider bias 規範テンプレート** (= T072 § 9.6 継承) を T071 / 後段 analytic 詳細設計改訂申し送りとして明記
- [ ] PR description に **Phase 2 配線時の OANDA / archive `dsr` 切替ゲート** (= sharpe_calc_version="v2" 同期 + dsr_v1/dsr_v2 併存) を明記
- [ ] PR description に **canonical genome dedup の SSOT** (= TRIAL_COUNTING_POLICY_VERSION="canonical-genome-v1") を明記、 GA runner 側の dedup 実装責務を T071 / GA 詳細設計改訂申し送り

### 9.4 collider bias 規範テンプレート (PR description 用、 T072 継承)

```markdown
## T073 collider bias 回避規範 (T071 / 後段 analytic 詳細設計改訂申し送り)

T073 audit layer は session block の `holiday_markets` (= 観測情報) を expected_bar_count
に touch せず、 caller (= T071 / 後段 analytic) が任意の condition として stratified audit
で消費する責務を維持する。

### Fact (= T073 SSOT)
- DSR は AuditNullModel SSOT 駆動 (= standard_normal placeholder null + session_block_non_annualized SR)
- compute_audit_dsr_for_genome の filter は `open_minutes > 0` のみ (= holiday_markets 単独除外しない)
- stratification は marginal default (= 3 軸独立 1 軸 group_by)、 interaction は事前登録 allowlist のみ
- C7 規範: 各 stratum で n >= 30 不充足は status="insufficient_data" sentinel

### Conditioning set 明記例
- T071 audit consumer: `holiday_markets` を condition variable として明示し、
  `compute_marginal_dsr_strata` の戻り値を log/report に出力。
  単独で drop しない、 stratified report で集計
- 後段 analytic: interaction 必要時は allowlist 経由 (= API レベル guard)

### Phase 2 申し送り
- T071 RunObservabilityReport.audit field 配線時に collider bias 規範を継承
- archive `dsr` field の v2 切替時 (= sharpe_calc_version="v2" 同期) は dsr_v1/dsr_v2 併存
```

## 10. Phase 1 / Phase 2 切り分け

### 10.1 Phase 1 (T073 PR)

§ 1.1 全範囲 + § 1.2 docstring 更新。 単体テストのみで runtime 未組込 (= Phase 1 共通原則)。

### 10.2 Phase 2 (別 TODO、 cascade port 切替時 + smoke 後)

§ 1.3 申し送り全項目。 主要:
- T071 RunObservabilityReport.audit field 配線
- archive `dsr` の v1 → v2 切替 (= sharpe_calc_version="v2" 同期 + dsr_v1 rename + dsr_v2 追加)
- run_ga.py で compute_run_audit_report 呼出 + RunObservabilityReport 同梱
- PBO / SPA 計算実装 (= smoke 後別 TODO + AUDIT_REPORT_SCHEMA_VERSION MINOR bump)
- T058 schema 拡張 (= SessionBlock 列を Parquet 列として保存)
- archive_sample null_model_kind 追加 (= AUDIT_REPORT_SCHEMA_VERSION MINOR bump)

### 10.3 同期 PR 候補

- 既存 statistics.py docstring 更新は本 T073 PR と **同 PR、 別 commit** で merge (Round 3 [C5] [S3] / Round D1 [S2]、 別 PR 不可、 docstring 同期と audit 実装で commit を分けてレビュー衝突を減らす):
  - commit 1: `docs(T073): statistics.py docstring を audit layer 文脈で同期更新`
  - commit 2: `feat(T073): audit.py 新規 module + tests 追加 (Phase 1 純ライブラリ)`
- T071 詳細設計改訂申し送り (= Phase 2 配線時)
- T058 詳細設計改訂申し送り (= Phase 2 archive schema 拡張時)

## 11. 参考文献

- Bailey, D. H. & López de Prado, M. M. (2014). *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality.* Journal of Portfolio Management 40(5).
- Bailey, D. H. & López de Prado, M. M. (2012). *The Sharpe Ratio Efficient Frontier.* Journal of Risk 15(2). (PSR 参照)
- Bailey, D. H., Borwein, J. M., López de Prado, M. M., & Zhu, Q. J. (2015). *The Probability of Backtest Overfitting.* Journal of Computational Finance 20(4). (PBO / CSCV、 Phase 2 scaffold field 追加候補)
- Hansen, P. R. (2005). *A Test for Superior Predictive Ability.* Journal of Business & Economic Statistics 23(4). (SPA、 Phase 2)
- Politis, D. N. & White, H. (2004). *Automatic Block-Length Selection for the Dependent Bootstrap.* Econometric Reviews 23(1). (Phase 2 SPA 実装時の dependent bootstrap)
- White, H. (2000). *A Reality Check for Data Snooping.* Econometrica 68(5). (SPA との比較対象)

---

これで T073 詳細設計は完成。 概念設計 Round 3 APPROVED 状態を起点に、 Round 3 [W1-W5] / [S1-S4] を全反映。 Codex 詳細レビュー (gpt-5.3-codex / high) で最終確認。
