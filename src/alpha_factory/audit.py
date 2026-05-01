"""Audit layer (T073 cascade port v2 Phase 2 配線、 Phase 1 純ライブラリ).

DSR 先行 + PBO/SPA scaffold (= status="not_implemented" 固定) を提供する。
runtime 未組込 (= 単体 test のみ)、 Phase 2 で T071 RunObservabilityReport.audit
field 配線時に runtime に組込予定 (申し送り).

責務 (詳細設計 § 0):
    - DSR 計算 (= 既存 statistics.deflated_sharpe_ratio を v2 SessionBlock 駆動
      で wrap、 数式不変)
    - AuditNullModel SSOT (= null_model_kind="standard_normal" /
      sr_scale="session_block_non_annualized" / trial_source="run_evaluated_genomes_unique_canonical"
      / trial_counting_policy_version="canonical-genome-v1" /
      n_trials=n_trial_candidates_unique / raw 別保持 / raw_count_status)
    - AuditDSRStatus (5 値) と AuditScaffoldStatus (1 値) の型分離
    - PBO/SPA scaffold (= status="not_implemented" + audit_calc_version="scaffold-v1"、
      数値 field なし)
    - stratification API guard (= marginal default + interaction allowlist、
      sparse strata 量産防止 + C7 規範 n>=30)

collider bias 規範継承 (詳細設計 § 1.4 / 概念設計 § 11.4):
    holiday_markets 単独で session_pass_pattern / SR 計算分母を drop / filter
    してはならない. compute_audit_dsr_for_genome の filter は `open_minutes > 0`
    のみ (= holiday は flag として観測情報を残し、 stratified audit は caller 責務).
    stratification は marginal default + interaction allowlist API で sparse strata
    の量産を防ぐ.

Phase 2 申し送り (詳細設計 § 1.3 / § 10.2):
    - T071 RunObservabilityReport に audit: RunAuditReport field 追加
    - archive `dsr` を `dsr_v1` に rename + `dsr_v2` 追加 (= sharpe_calc_version 同期)
    - PBO/SPA 計算実装 + AUDIT_REPORT_SCHEMA_VERSION MINOR bump
"""

from __future__ import annotations

import logging
import math
import statistics as _stats
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from decimal import Decimal
from typing import Any, Final, Literal

from src.alpha_factory.statistics import deflated_sharpe_ratio
from src.backtest.calendar import ObservabilityFlags
from src.backtest.session_block import SessionBlock

__all__ = [
    "AUDIT_DSR_CALC_VERSION",
    "AUDIT_DSR_MIN_OBSERVATIONS",
    "AUDIT_DSR_MIN_TRIALS",
    "AUDIT_REPORT_SCHEMA_VERSION",
    "AUDIT_SCAFFOLD_CALC_VERSION",
    "DSR_VALUE_SENTINEL",
    "MOMENT_SENTINEL",
    "TRIAL_COUNTING_POLICY_VERSION",
    "AuditDSRMetric",
    "AuditDSRStatus",
    "AuditGenomeRecord",
    "AuditNullModel",
    "AuditNullModelKind",
    "AuditPBOMetric",
    "AuditSPAMetric",
    "AuditSRScale",
    "AuditScaffoldStatus",
    "AuditTrialSource",
    "GenomeAuditInput",
    "RunAuditReport",
    "check_audit_record_schema_version",
    "compute_audit_dsr_for_genome",
    "compute_audit_pbo_scaffold",
    "compute_audit_spa_scaffold",
    "compute_dsr_strata_with_allowlist",
    "compute_marginal_dsr_strata",
    "compute_run_audit_report",
]


logger = logging.getLogger(__name__)


# Status Literal (詳細設計 § 3.1)
AuditDSRStatus = Literal[
    "ok",
    "insufficient_data",
    "insufficient_trials",
    "degenerate_variance",
    "input_non_finite",
]
AuditScaffoldStatus = Literal["not_implemented"]


# Null model SSOT (詳細設計 § 3.1)
AuditNullModelKind = Literal["standard_normal"]
AuditSRScale = Literal["session_block_non_annualized"]
AuditTrialSource = Literal["run_evaluated_genomes_unique_canonical"]


# 定数 (詳細設計 § 3.1)
AUDIT_DSR_MIN_OBSERVATIONS: Final[int] = 30
AUDIT_DSR_MIN_TRIALS: Final[int] = 2
AUDIT_REPORT_SCHEMA_VERSION: Final[str] = "1.0.0"
AUDIT_DSR_CALC_VERSION: Final[str] = "v2"
AUDIT_SCAFFOLD_CALC_VERSION: Final[str] = "scaffold-v1"
TRIAL_COUNTING_POLICY_VERSION: Final[str] = "canonical-genome-v1"


# Sentinel policy (詳細設計 § 3.1、 Round 3 [W1] [S2] 分離)
# - DSR_VALUE_SENTINEL: dsr_value 用、 値域 [0, 1] 外で fail-closed
# - MOMENT_SENTINEL: sharpe_ratio / skew / kurtosis 用、 「解釈禁止」 を invariant 明示
DSR_VALUE_SENTINEL: Final[Decimal] = Decimal("-1")
MOMENT_SENTINEL: Final[Decimal] = Decimal("0")


# ---------------------------------------------------------------------------
# Dataclasses (詳細設計 § 3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditNullModel:
    """DSR null model provenance (詳細設計 § 3.2、 Round 3 [S1] [W3] 反映).

    Phase 1 SSOT:
        null_model_kind = "standard_normal" (= placeholder null、 Bailey 原著
            null とは区別、 archive_sample null は Phase 2 で追加)
        sr_scale = "session_block_non_annualized"
        mean_sr_trials = 0
        std_sr_trials = 1
        trial_source = "run_evaluated_genomes_unique_canonical"
        trial_counting_policy_version = "canonical-genome-v1"
        n_trials = n_trial_candidates_unique
        n_trial_candidates_raw: int (= 評価 attempt 総数、 取得不能時は
            raw_count_status="unknown" で raw=unique を conservative lower-bound
            として保持)
        n_trial_candidates_unique: int

    canonical genome dedup の SSOT (詳細設計 § 5.1 F31-F35):
        - 同一 canonical genome_id の retry: raw=2 / unique=1 (= caller dedup)
        - cache hit は raw にも含めない (= "新たな評価 attempt" のみ raw に加算)
        - 同一 canonical genome_id の fold 別評価: unique=1 / raw=fold 数
        - 同一 canonical genome_id の seed 違い: unique=1 / raw=seed 数
        - 異 canonical genome_id (= 異 hash): unique=2 (= 異 trial)

    Phase 2 拡張: archive_sample null_model_kind 追加 + AUDIT_REPORT_SCHEMA_VERSION
        MINOR bump.
    """

    null_model_kind: AuditNullModelKind
    sr_scale: AuditSRScale
    mean_sr_trials: Decimal
    std_sr_trials: Decimal
    trial_source: AuditTrialSource
    trial_counting_policy_version: str
    n_trials: int
    n_trial_candidates_raw: int
    n_trial_candidates_unique: int
    raw_count_status: Literal["measured", "unknown"]

    def __post_init__(self) -> None:
        # I-1: null_model_kind == "standard_normal" → mean=0 / std=1
        if self.null_model_kind == "standard_normal":
            if self.mean_sr_trials != Decimal(0):
                raise ValueError(
                    f"standard_normal null requires mean_sr_trials == 0, "
                    f"got {self.mean_sr_trials}"
                )
            if self.std_sr_trials != Decimal(1):
                raise ValueError(
                    f"standard_normal null requires std_sr_trials == 1, "
                    f"got {self.std_sr_trials}"
                )
        else:  # pragma: no cover - Literal が Phase 1 では standard_normal のみ
            raise ValueError(
                f"null_model_kind must be 'standard_normal' (Phase 1 SSOT), "
                f"got {self.null_model_kind!r}"
            )
        # I-2: sr_scale / trial_source / trial_counting_policy_version SSOT
        if self.sr_scale != "session_block_non_annualized":
            raise ValueError(
                f"sr_scale must be 'session_block_non_annualized' (Phase 1 SSOT), "
                f"got {self.sr_scale!r}"
            )
        if self.trial_source != "run_evaluated_genomes_unique_canonical":
            raise ValueError(
                f"trial_source must be 'run_evaluated_genomes_unique_canonical' "
                f"(Phase 1 SSOT), got {self.trial_source!r}"
            )
        if self.trial_counting_policy_version != TRIAL_COUNTING_POLICY_VERSION:
            raise ValueError(
                f"trial_counting_policy_version must be "
                f"{TRIAL_COUNTING_POLICY_VERSION!r}, "
                f"got {self.trial_counting_policy_version!r}"
            )
        # I-3: std > 0
        if self.std_sr_trials <= Decimal(0):
            raise ValueError(
                f"std_sr_trials must be > 0, got {self.std_sr_trials}"
            )
        # I-4: n_trials == n_trial_candidates_unique
        if self.n_trials != self.n_trial_candidates_unique:
            raise ValueError(
                f"n_trials ({self.n_trials}) must equal "
                f"n_trial_candidates_unique ({self.n_trial_candidates_unique})"
            )
        # I-5: raw_count_status の value 制約
        if self.raw_count_status == "measured":
            if self.n_trial_candidates_raw < self.n_trial_candidates_unique:
                raise ValueError(
                    f"raw_count_status='measured' requires raw "
                    f"({self.n_trial_candidates_raw}) >= unique "
                    f"({self.n_trial_candidates_unique})"
                )
        elif self.raw_count_status == "unknown":
            if self.n_trial_candidates_raw != self.n_trial_candidates_unique:
                raise ValueError(
                    f"raw_count_status='unknown' requires raw == unique "
                    f"(conservative lower-bound), got raw="
                    f"{self.n_trial_candidates_raw}, unique="
                    f"{self.n_trial_candidates_unique}"
                )
        else:
            raise ValueError(
                f"raw_count_status must be 'measured' or 'unknown', "
                f"got {self.raw_count_status!r}"
            )
        # I-6: n_trial_candidates_unique >= 0
        if self.n_trial_candidates_unique < 0:
            raise ValueError(
                f"n_trial_candidates_unique must be >= 0, "
                f"got {self.n_trial_candidates_unique}"
            )


@dataclass(frozen=True)
class AuditDSRMetric:
    """genome ごとの DSR 監査結果 (詳細設計 § 3.3).

    AuditGenomeRecord 経由で参照する運用規範 (Round D1 [S3]):
        AuditDSRMetric は単独で hash/eq 比較せず、 genome_id key (= AuditGenomeRecord.genome_id)
        で参照する。 dsr_value のみ同値の異 genome を集合 / dict key に流す経路は
        意味的に bug を招くため、 caller は AuditGenomeRecord をキーに使う.

    Sentinel policy (Round 3 [W1] [S2] 分離):
        status="ok":
            dsr_value ∈ [0, 1]
            sharpe_ratio / skew / kurtosis = 観察値 (= 全 finite)
        status != "ok":
            dsr_value == DSR_VALUE_SENTINEL (= Decimal("-1"))
            sharpe_ratio / skew / kurtosis == MOMENT_SENTINEL (= Decimal("0"))
            n_observations は実測値 (= 観察事実として保持)
            **moment 系の MOMENT_SENTINEL 値は「解釈禁止」**:
                Decimal(0) は sharpe / skew で valid 値だが、 status check で
                除外する規範. caller は status=="ok" 確認後にのみ moment field
                を解釈する.
    """

    status: AuditDSRStatus
    dsr_value: Decimal
    n_observations: int
    sharpe_ratio: Decimal
    skew: Decimal
    kurtosis: Decimal
    null_model: AuditNullModel
    audit_calc_version: str

    def __post_init__(self) -> None:
        # I-1: audit_calc_version
        if self.audit_calc_version != AUDIT_DSR_CALC_VERSION:
            raise ValueError(
                f"audit_calc_version must be {AUDIT_DSR_CALC_VERSION!r}, "
                f"got {self.audit_calc_version!r}"
            )
        # I-2: n_observations >= 0
        if self.n_observations < 0:
            raise ValueError(
                f"n_observations must be >= 0, got {self.n_observations}"
            )
        # I-3: status 別 invariant (Round 3 [W1] [S2])
        if self.status == "ok":
            if not (Decimal(0) <= self.dsr_value <= Decimal(1)):
                raise ValueError(
                    f"status='ok' requires dsr_value in [0, 1], "
                    f"got {self.dsr_value}"
                )
            for name, val in (
                ("sharpe_ratio", self.sharpe_ratio),
                ("skew", self.skew),
                ("kurtosis", self.kurtosis),
            ):
                if not math.isfinite(float(val)):
                    raise ValueError(
                        f"status='ok' requires {name} finite, got {val}"
                    )
        elif self.status in (
            "insufficient_data",
            "insufficient_trials",
            "degenerate_variance",
            "input_non_finite",
        ):
            if self.dsr_value != DSR_VALUE_SENTINEL:
                raise ValueError(
                    f"status={self.status!r} requires dsr_value == "
                    f"DSR_VALUE_SENTINEL ({DSR_VALUE_SENTINEL}), "
                    f"got {self.dsr_value}"
                )
            for name, val in (
                ("sharpe_ratio", self.sharpe_ratio),
                ("skew", self.skew),
                ("kurtosis", self.kurtosis),
            ):
                if val != MOMENT_SENTINEL:
                    raise ValueError(
                        f"status={self.status!r} requires {name} == "
                        f"MOMENT_SENTINEL ({MOMENT_SENTINEL}, 解釈禁止), "
                        f"got {val}"
                    )
        else:
            raise ValueError(f"unknown AuditDSRStatus: {self.status!r}")


@dataclass(frozen=True)
class AuditPBOMetric:
    """PBO scaffold (詳細設計 § 3.4、 Round R2 [C4] [S3]、 数値 field なし).

    Phase 2 で field 追加予定 (= performance_matrix / cscv_n_splits /
    cscv_logit_estimate / pbo_value):
        AUDIT_REPORT_SCHEMA_VERSION 1.0.0 → 1.1.0 (= MINOR bump、 後方互換).
        ただし pbo_value 等を「実装済」 と判定するため status 拡張
        (= 別 Status Literal 追加 or AuditScaffoldStatus 拡張).
    """

    status: AuditScaffoldStatus
    audit_calc_version: str

    def __post_init__(self) -> None:
        if self.status != "not_implemented":
            raise ValueError(
                f"AuditPBOMetric.status must be 'not_implemented' (scaffold), "
                f"got {self.status!r}"
            )
        if self.audit_calc_version != AUDIT_SCAFFOLD_CALC_VERSION:
            raise ValueError(
                f"audit_calc_version must be {AUDIT_SCAFFOLD_CALC_VERSION!r}, "
                f"got {self.audit_calc_version!r}"
            )


@dataclass(frozen=True)
class AuditSPAMetric:
    """SPA scaffold (詳細設計 § 3.4、 同 SSOT)."""

    status: AuditScaffoldStatus
    audit_calc_version: str

    def __post_init__(self) -> None:
        if self.status != "not_implemented":
            raise ValueError(
                f"AuditSPAMetric.status must be 'not_implemented' (scaffold), "
                f"got {self.status!r}"
            )
        if self.audit_calc_version != AUDIT_SCAFFOLD_CALC_VERSION:
            raise ValueError(
                f"audit_calc_version must be {AUDIT_SCAFFOLD_CALC_VERSION!r}, "
                f"got {self.audit_calc_version!r}"
            )


@dataclass(frozen=True)
class AuditGenomeRecord:
    """genome 単位の audit record (詳細設計 § 3.5、 T058 join 可)."""

    genome_id: str
    archive_role: str
    source_stage: str
    dsr_metric: AuditDSRMetric

    def __post_init__(self) -> None:
        if not self.genome_id:
            raise ValueError("genome_id must be non-empty")


@dataclass(frozen=True)
class GenomeAuditInput:
    """compute_run_audit_report の per-genome 入力 (詳細設計 § 3.5、 Phase 1 in-memory transport).

    Phase 2 で T058 archive 経由 (= per-genome SessionBlock を Parquet 列から復元) で配線予定。
    """

    genome_id: str
    archive_role: str
    source_stage: str
    session_blocks: Sequence[SessionBlock]


@dataclass(frozen=True)
class RunAuditReport:
    """1 Run 全体の audit 集約 (詳細設計 § 3.5).

    Phase 2 で T071 RunObservabilityReport.audit field 配線対象。
    """

    run_id: str
    dataset_epoch_id: str
    n_genomes: int
    per_genome: tuple[AuditGenomeRecord, ...]
    pbo: AuditPBOMetric
    spa: AuditSPAMetric
    audit_report_schema_version: str

    def __post_init__(self) -> None:
        if self.audit_report_schema_version != AUDIT_REPORT_SCHEMA_VERSION:
            raise ValueError(
                f"audit_report_schema_version must be "
                f"{AUDIT_REPORT_SCHEMA_VERSION!r}, "
                f"got {self.audit_report_schema_version!r}"
            )
        if len(self.per_genome) != self.n_genomes:
            raise ValueError(
                f"len(per_genome) ({len(self.per_genome)}) != n_genomes "
                f"({self.n_genomes})"
            )
        for record in self.per_genome:
            if record.dsr_metric.audit_calc_version != AUDIT_DSR_CALC_VERSION:
                raise ValueError(
                    f"genome_id={record.genome_id!r}: "
                    f"dsr_metric.audit_calc_version mismatch "
                    f"(expected {AUDIT_DSR_CALC_VERSION!r}, "
                    f"got {record.dsr_metric.audit_calc_version!r})"
                )
        if self.per_genome:
            first_null = self.per_genome[0].dsr_metric.null_model
            for record in self.per_genome[1:]:
                if record.dsr_metric.null_model != first_null:
                    raise ValueError(
                        f"genome_id={record.genome_id!r}: null_model differs "
                        f"from run-level (Phase 1 invariant: Run 内一様)"
                    )
        if self.pbo.audit_calc_version != AUDIT_SCAFFOLD_CALC_VERSION:
            raise ValueError(
                f"pbo.audit_calc_version must be "
                f"{AUDIT_SCAFFOLD_CALC_VERSION!r}, "
                f"got {self.pbo.audit_calc_version!r}"
            )
        if self.spa.audit_calc_version != AUDIT_SCAFFOLD_CALC_VERSION:
            raise ValueError(
                f"spa.audit_calc_version must be "
                f"{AUDIT_SCAFFOLD_CALC_VERSION!r}, "
                f"got {self.spa.audit_calc_version!r}"
            )


# ---------------------------------------------------------------------------
# Algorithms (詳細設計 § 4)
# ---------------------------------------------------------------------------


_SENTINEL_DSR_STATUSES: Final[frozenset[AuditDSRStatus]] = frozenset(
    {
        "insufficient_data",
        "insufficient_trials",
        "degenerate_variance",
        "input_non_finite",
    }
)


def _make_sentinel_metric(
    *,
    status: AuditDSRStatus,
    null_model: AuditNullModel,
    n_observations: int,
) -> AuditDSRMetric:
    """sentinel AuditDSRMetric 構築 (詳細設計 § 4.1、 keyword-only).

    Round D1 [C1] [W2]:
        - keyword-only call (= 構造的強制).
        - status は AuditDSRStatus かつ "ok" 以外の sentinel status のみ受理.
        - "not_implemented" 等 AuditScaffoldStatus は受理しない.
        - dsr_value / moment 系は sentinel 固定、 n_observations は実測値.
    """
    if status not in _SENTINEL_DSR_STATUSES:
        raise ValueError(
            f"_make_sentinel_metric: status must be one of "
            f"{sorted(_SENTINEL_DSR_STATUSES)}, got {status!r}"
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


def compute_audit_dsr_for_genome(
    session_blocks: Sequence[SessionBlock],
    *,
    null_model: AuditNullModel,
) -> AuditDSRMetric:
    """SessionBlock 配列から genome の DSR 監査値を計算する (詳細設計 § 4.1).

    SSOT (概念設計 § 6.1):
        - filter は `open_minutes > 0` のみ (= holiday_markets 単独除外しない、
          collider bias 規範).
        - sentinel policy (Round 3 [W1] / Round D1 [C1] [C2]):
            status != "ok" → dsr_value = DSR_VALUE_SENTINEL,
            moment 系 = MOMENT_SENTINEL.
            n_observations は **常に実測値 (= filter 後の block 数)** を保持.

    Args:
        session_blocks: genome の session block sequence.
        null_model: AuditNullModel SSOT (Run 単位で一様).

    Returns:
        AuditDSRMetric (status と sentinel policy は __post_init__ で検証).
    """
    relevant = [b for b in session_blocks if b.open_minutes > 0]
    n = len(relevant)

    # Step 0: insufficient_trials (n_observations は実測値)
    if null_model.n_trials < AUDIT_DSR_MIN_TRIALS:
        return _make_sentinel_metric(
            status="insufficient_trials",
            null_model=null_model,
            n_observations=n,
        )

    # Step 1: insufficient_data
    if n < AUDIT_DSR_MIN_OBSERVATIONS:
        return _make_sentinel_metric(
            status="insufficient_data",
            null_model=null_model,
            n_observations=n,
        )

    # Step 2: pnl_net moment 推定
    pnls = [float(b.pnl_net) for b in relevant]

    # input_non_finite (pnl_net そのものが NaN/Inf の case)
    for v in pnls:
        if not math.isfinite(v):
            return _make_sentinel_metric(
                status="input_non_finite",
                null_model=null_model,
                n_observations=n,
            )

    mean = _stats.fmean(pnls)
    variance = _stats.variance(pnls)  # n-1 unbiased

    # Step 2a: degenerate_variance
    if variance < 1e-20:
        return _make_sentinel_metric(
            status="degenerate_variance",
            null_model=null_model,
            n_observations=n,
        )

    stdev = math.sqrt(variance)
    sharpe = mean / stdev
    skew_val = sum((r - mean) ** 3 for r in pnls) / (n * stdev**3)
    kurt_val = sum((r - mean) ** 4 for r in pnls) / (n * stdev**4)

    # Step 2b: input_non_finite (moment 計算後)
    for v in (sharpe, skew_val, kurt_val):
        if not math.isfinite(v):
            return _make_sentinel_metric(
                status="input_non_finite",
                null_model=null_model,
                n_observations=n,
            )

    # Step 3: deflated_sharpe_ratio 呼出
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

    # Step 4: 成功
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


def compute_audit_pbo_scaffold(
    *,
    audit_calc_version: str = AUDIT_SCAFFOLD_CALC_VERSION,
) -> AuditPBOMetric:
    """PBO scaffold factory (詳細設計 § 4.2、 status="not_implemented" 固定)."""
    return AuditPBOMetric(
        status="not_implemented",
        audit_calc_version=audit_calc_version,
    )


def compute_audit_spa_scaffold(
    *,
    audit_calc_version: str = AUDIT_SCAFFOLD_CALC_VERSION,
) -> AuditSPAMetric:
    """SPA scaffold factory (詳細設計 § 4.2、 status="not_implemented" 固定)."""
    return AuditSPAMetric(
        status="not_implemented",
        audit_calc_version=audit_calc_version,
    )


def compute_run_audit_report(
    *,
    run_id: str,
    dataset_epoch_id: str,
    per_genome: Mapping[str, GenomeAuditInput],
    null_model: AuditNullModel,
) -> RunAuditReport:
    """archive 全 genome を走査して RunAuditReport を構築 (詳細設計 § 4.3).

    deterministic order: genome_id (str sort).
    null_model は Run 内一様 (Phase 1 default).
    """
    records = tuple(
        AuditGenomeRecord(
            genome_id=inp.genome_id,
            archive_role=inp.archive_role,
            source_stage=inp.source_stage,
            dsr_metric=compute_audit_dsr_for_genome(
                inp.session_blocks, null_model=null_model
            ),
        )
        for _, inp in sorted(per_genome.items())
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


def check_audit_record_schema_version(
    record_schema_version: str,
    *,
    expected: str = AUDIT_REPORT_SCHEMA_VERSION,
) -> None:
    """audit_record_schema_version の整合性を確認 (詳細設計 § 4.4).

    bump 規約 (概念設計 § 11.6):
        MAJOR: 既存 field 削除 / 意味変更 (= 互換性破壊)
        MINOR: field 追加 (= 既存 caller は新 field を ignore)
        PATCH: 出力値 bug fix (= schema 不変)

    挙動 (Round D1 [W3]):
        - MAJOR mismatch (= received[0] != expected[0]) → ValueError raise
        - received[1] > expected[1] (= record newer than consumer) → warning log
        - received[1] < expected[1] (= record older than consumer) → warning log
        - received[2] != expected[2] (= PATCH 差) → silent
        - 不正フォーマット (= "1" / "1.a" / "1.0.0.1") → ValueError raise

    Raises:
        ValueError: MAJOR mismatch / 不正フォーマット.
    """
    received_parts = record_schema_version.split(".")
    expected_parts = expected.split(".")
    if len(received_parts) != 3:
        raise ValueError(
            f"audit_record_schema_version must be 'MAJOR.MINOR.PATCH', "
            f"got {record_schema_version!r}"
        )
    try:
        received = tuple(int(x) for x in received_parts)
        expected_int = tuple(int(x) for x in expected_parts)
    except ValueError as e:
        raise ValueError(
            f"audit_record_schema_version parse failed: "
            f"{record_schema_version!r}"
        ) from e

    if received[0] != expected_int[0]:
        raise ValueError(
            f"audit_record_schema_version MAJOR mismatch: "
            f"expected {expected}, got {record_schema_version}"
        )
    if received[1] > expected_int[1]:
        logger.warning(
            "audit_record_schema_version MINOR mismatch "
            "(record newer than consumer): expected=%s, got=%s. "
            "consumer may need update to read new fields.",
            expected,
            record_schema_version,
        )
    elif received[1] < expected_int[1]:
        logger.warning(
            "audit_record_schema_version MINOR mismatch "
            "(record older than consumer): expected=%s, got=%s. "
            "caller should know record may lack newer fields.",
            expected,
            record_schema_version,
        )
    # PATCH 差は silent


# ---------------------------------------------------------------------------
# Stratification API (詳細設計 § 4.5、 Round 3 [W5] / Round D1 [S1])
# ---------------------------------------------------------------------------


_STRATA_FLAG_NAMESPACE_PHASE1: Final[str] = "t072"
_STRATA_SCHEMA_VERSION_PHASE1: Final[str] = "1.0.0"


def _flag_value(flags: ObservabilityFlags, key: str) -> Any:
    """ObservabilityFlags の key で示される flag 値を取得 (= group_by 用 hashable).

    SSOT:
        "holiday_markets":         frozenset[MarketCode]
        "dst_transition_markets":  frozenset[MarketCode]
        "schedule_status":         flags 自体には無い (= SessionBlock.schedule_status
                                   経由)。 stratification API では未対応.

    Raises:
        ValueError: 未対応 key.
    """
    if key == "holiday_markets":
        return flags.holiday_markets
    if key == "dst_transition_markets":
        return flags.dst_transition_markets
    raise ValueError(
        f"unsupported flag key for stratification: {key!r}. "
        f"Supported: 'holiday_markets', 'dst_transition_markets'."
    )


_MARGINAL_KEYS_PHASE1: Final[tuple[str, ...]] = (
    "holiday_markets",
    "dst_transition_markets",
)


def compute_marginal_dsr_strata(
    report: RunAuditReport,
    *,
    flag_lookup: Mapping[str, ObservabilityFlags],
) -> dict[str, dict[Any, list[AuditGenomeRecord]]]:
    """marginal stratification (詳細設計 § 4.5、 概念 § 11.4).

    SSOT: marginal 集計のみ (= 各 key 独立 1 軸 group_by).
        各 group_by key に対し {flag_value: [AuditGenomeRecord, ...]} を返す.
    interaction (= 2 軸以上 cross product) は本関数では計算しない。
    interaction が必要な caller は compute_dsr_strata_with_allowlist を使う.

    Phase 1 では holiday_markets / dst_transition_markets の 2 軸を提供。
    schedule_status は SessionBlock 経由でしか取得できないため stratification
    API では Phase 2 申し送り (= per-genome aggregate を caller 側で計算).

    Args:
        report: RunAuditReport.
        flag_lookup: genome_id -> ObservabilityFlags (= caller が aggregate 済).

    Returns:
        {marginal_key: {flag_value: [AuditGenomeRecord, ...]}}.
        deterministic: report.per_genome の order を維持.

    Raises:
        ValueError: flag_lookup に genome_id が見つからない.
    """
    result: dict[str, dict[Any, list[AuditGenomeRecord]]] = {
        f"by_{key}": {} for key in _MARGINAL_KEYS_PHASE1
    }
    for record in report.per_genome:
        if record.genome_id not in flag_lookup:
            raise ValueError(
                f"flag_lookup missing genome_id={record.genome_id!r}"
            )
        flags = flag_lookup[record.genome_id]
        for key in _MARGINAL_KEYS_PHASE1:
            value = _flag_value(flags, key)
            buckets = result[f"by_{key}"]
            buckets.setdefault(value, []).append(record)
    return result


def compute_dsr_strata_with_allowlist(
    report: RunAuditReport,
    *,
    flag_lookup: Mapping[str, ObservabilityFlags],
    allowlist: Sequence[tuple[str, ...]],
    schema_version: str = _STRATA_SCHEMA_VERSION_PHASE1,
    flag_namespace: str = _STRATA_FLAG_NAMESPACE_PHASE1,
) -> dict[tuple[str, ...], dict[Any, list[AuditGenomeRecord]]]:
    """interaction allowlist API (詳細設計 § 4.5、 Round 3 [W5] / Round D1 [S1]).

    SSOT: allowlist で指定された key tuple (= 2 軸以上 cross product) のみ計算.
        各 stratum で C7 規範 n >= 30 不充足の場合は warning log emit.

    Phase 1 で受理する key:
        "holiday_markets", "dst_transition_markets" のみ.

    Args:
        report: RunAuditReport.
        flag_lookup: genome_id -> ObservabilityFlags.
        allowlist: 例 (("holiday_markets", "dst_transition_markets"),).
            空 tuple () は禁止 (= 各 element は >= 1 key).
            重複 key を含む tuple (= ("a", "a")) も禁止.
        schema_version: stratification API SSOT (Phase 1 で "1.0.0" 固定).
        flag_namespace: flag namespace (Phase 1 で "t072" 固定).

    Returns:
        {key tuple: {flag value tuple: [AuditGenomeRecord, ...]}}.

    Raises:
        ValueError: schema_version / flag_namespace mismatch、 allowlist に
            未対応 key / 空 tuple / 重複 key、 flag_lookup に genome_id 欠落.
    """
    if schema_version != _STRATA_SCHEMA_VERSION_PHASE1:
        raise ValueError(
            f"stratification schema_version must be "
            f"{_STRATA_SCHEMA_VERSION_PHASE1!r} (Phase 1), "
            f"got {schema_version!r}"
        )
    if flag_namespace != _STRATA_FLAG_NAMESPACE_PHASE1:
        raise ValueError(
            f"flag_namespace must be {_STRATA_FLAG_NAMESPACE_PHASE1!r} "
            f"(Phase 1), got {flag_namespace!r}"
        )

    # allowlist 検証
    for keys in allowlist:
        if len(keys) == 0:
            raise ValueError(
                "allowlist tuple must contain >= 1 key, got empty tuple"
            )
        if len(set(keys)) != len(keys):
            raise ValueError(
                f"allowlist tuple must not contain duplicate keys, got {keys}"
            )
        for key in keys:
            if key not in _MARGINAL_KEYS_PHASE1:
                raise ValueError(
                    f"allowlist contains unsupported key {key!r}. "
                    f"Supported (Phase 1): {_MARGINAL_KEYS_PHASE1}"
                )

    result: dict[tuple[str, ...], dict[Any, list[AuditGenomeRecord]]] = {
        keys: {} for keys in allowlist
    }
    for record in report.per_genome:
        if record.genome_id not in flag_lookup:
            raise ValueError(
                f"flag_lookup missing genome_id={record.genome_id!r}"
            )
        flags = flag_lookup[record.genome_id]
        for keys in allowlist:
            value_tuple = tuple(_flag_value(flags, k) for k in keys)
            result[keys].setdefault(value_tuple, []).append(record)

    # C7 規範 n >= 30 warning emit
    for keys, strata in result.items():
        for value_tuple, records in strata.items():
            if len(records) < AUDIT_DSR_MIN_OBSERVATIONS:
                logger.warning(
                    "stratum_insufficient_n",
                    extra={
                        "keys": keys,
                        "value_tuple": value_tuple,
                        "n_records": len(records),
                        "min_required": AUDIT_DSR_MIN_OBSERVATIONS,
                    },
                )

    return result


# ---------------------------------------------------------------------------
# Module-level invariants (= dataclass 列の自己整合 check、 import 時に実行)
# ---------------------------------------------------------------------------


def _verify_pbo_metric_no_numeric_fields() -> None:
    """AuditPBOMetric / AuditSPAMetric が status + audit_calc_version 以外の
    数値 field を持たないことを invariant 検証 (詳細設計 § 5.1 F24)."""
    expected_fields = {"status", "audit_calc_version"}
    for cls in (AuditPBOMetric, AuditSPAMetric):
        actual = {f.name for f in fields(cls)}
        if actual != expected_fields:
            raise RuntimeError(
                f"{cls.__name__} fields invariant violation: "
                f"expected {expected_fields}, got {actual}"
            )


_verify_pbo_metric_no_numeric_fields()
