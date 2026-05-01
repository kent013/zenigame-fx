"""T058: Schema v2 contract — dataset_epoch_id 全経路必須化.

zenigame-fx の selection cascade を big-bang baseline で再構築する際の
最先頭 contract。 詳細:
- 概念設計: devnotes/20260429-1912-todo-T058-schema-v2-contract/conceptual-design.md
- synthesis: devnotes/20260428-2300-cascade-port-debate/synthesis.md § 9
- 後段 TODO (T059-T075) は本 schema に依存。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Schema versions (artifact 別)
# ---------------------------------------------------------------------------

GENOME_ENTRY_SCHEMA_VERSION: Final[int] = 2
CALIBRATE_HISTORY_SCHEMA_VERSION: Final[int] = 2
CASCADE_CONTRACT_VERSION: Final[int] = 2
DIAGNOSTICS_SCHEMA_VERSION: Final[int] = 2


# ---------------------------------------------------------------------------
# Enum (永続値 lower_snake_case)
# ---------------------------------------------------------------------------


class ArchiveRole(StrEnum):
    """Archive 流入 3 層の identifier (T066 で書込)."""

    MISSION_PASS = "mission_pass"
    PROGRESS_PASS = "progress_pass"
    SCORE_BYPASS = "score_bypass"


class SourceStage(StrEnum):
    """個体評価の最終 stage (T063-T064 で書込)."""

    A = "a"
    B = "b"
    C_LITE = "c_lite"
    C = "c"


class SchemaEnforcementMode(StrEnum):
    """Schema lint の enforcement mode.

    LOG_ONLY (T058 default): warning + Counter 計測、 fail させない。
    FAIL_CLOSED (T067 で切替): 必須 field 欠落で SchemaContractError raise。
    """

    LOG_ONLY = "log_only"
    FAIL_CLOSED = "fail_closed"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SchemaContractError(ValueError):
    """必須 field 欠落 (FAIL_CLOSED mode で raise)."""


class SchemaVersionError(ValueError):
    """schema_version 不一致 (T067 で v1 archive 検出時 raise)."""


# ---------------------------------------------------------------------------
# Grammar — dataset_epoch_id
# ---------------------------------------------------------------------------

DATASET_EPOCH_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_]+$")


def validate_epoch_id(value: str) -> None:
    """dataset_epoch_id の grammar 検証.

    Raises:
        SchemaContractError: 空文字 / pattern 不一致。
    """
    if not value:
        raise SchemaContractError("dataset_epoch_id must be non-empty")
    if not DATASET_EPOCH_ID_PATTERN.fullmatch(value):
        raise SchemaContractError(
            f"dataset_epoch_id violates grammar [a-z0-9_]+: {value!r}"
        )


# ---------------------------------------------------------------------------
# Required field sets (Tier 1: 9 経路)
# ---------------------------------------------------------------------------

COMMON_REQUIRED: Final[frozenset[str]] = frozenset({"dataset_epoch_id"})

GENOME_ENTRY_CONTRACT_V2: Final[frozenset[str]] = COMMON_REQUIRED | frozenset({
    "genome_entry_schema_version",
    "archive_role",
    "source_stage",
})

CALIBRATE_HISTORY_CONTRACT_V2: Final[frozenset[str]] = COMMON_REQUIRED | frozenset({
    "calibrate_history_schema_version",
})

RUN_REPORT_CONTRACT_V2: Final[frozenset[str]] = COMMON_REQUIRED | frozenset({
    "cascade_contract_version",
})

DIAGNOSTICS_CONTRACT_V2: Final[frozenset[str]] = COMMON_REQUIRED | frozenset({
    "diagnostics_schema_version",
})


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationResult:
    """Validator 返却型. LOG_ONLY mode で ``result.ok`` で集計に使う."""

    ok: bool
    missing: tuple[str, ...] = ()
    invalid: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Validators (Tier 1: 4 関数、 ValidationResult 返却統一、 Round 3 [Critical] 1 反映)
# ---------------------------------------------------------------------------


def _check_required(
    record: Mapping[str, Any],
    required: frozenset[str],
    *,
    artifact: str,
    mode: SchemaEnforcementMode,
) -> ValidationResult:
    """必須 field 欠落を mode に従って handle、 ValidationResult を返す."""
    missing = tuple(sorted(required - record.keys()))
    if not missing:
        return ValidationResult(ok=True)
    if mode == SchemaEnforcementMode.FAIL_CLOSED:
        raise SchemaContractError(
            f"{artifact}: missing required fields {list(missing)}"
        )
    logger.warning(
        "schema_contract.passive_validation_failed",
        artifact=artifact,
        missing=list(missing),
        record_keys=sorted(record.keys()),
    )
    return ValidationResult(ok=False, missing=missing)


def assert_genome_entry_v2(
    record: Mapping[str, Any],
    *,
    mode: SchemaEnforcementMode,
) -> ValidationResult:
    """Tier 1: Parquet archive entry の v2 contract 検証."""
    missing = tuple(sorted(GENOME_ENTRY_CONTRACT_V2 - record.keys()))
    invalid: list[str] = []
    epoch_id = record.get("dataset_epoch_id")
    if isinstance(epoch_id, str):
        try:
            validate_epoch_id(epoch_id)
        except SchemaContractError:
            if mode == SchemaEnforcementMode.FAIL_CLOSED:
                raise
            invalid.append("dataset_epoch_id")
            # SSOT (詳細設計 行 335): grammar 違反は専用 event で発火
            logger.warning(
                "schema_contract.invalid_epoch_id",
                artifact="genome_entry",
                value=epoch_id,
            )

    if missing or invalid:
        if mode == SchemaEnforcementMode.FAIL_CLOSED:
            raise SchemaContractError(
                f"genome_entry: missing={list(missing)} invalid={invalid}"
            )
        # 集約 event (LOG_ONLY mode、 Round 2 [Critical] 4 反映の集約 log)
        logger.warning(
            "schema_contract.passive_validation_failed",
            artifact="genome_entry",
            missing=list(missing),
            invalid=list(invalid),
            record_keys=sorted(record.keys()),
        )
        return ValidationResult(
            ok=False, missing=missing, invalid=tuple(invalid)
        )
    return ValidationResult(ok=True)


def assert_calibrate_history_v2(
    record: Mapping[str, Any],
    *,
    mode: SchemaEnforcementMode,
) -> ValidationResult:
    """Tier 1: calibrate-gate history JSONL の v2 contract 検証."""
    return _check_required(
        record,
        CALIBRATE_HISTORY_CONTRACT_V2,
        artifact="calibrate_history",
        mode=mode,
    )


def assert_run_report_v2(
    report: Mapping[str, Any],
    *,
    mode: SchemaEnforcementMode,
) -> ValidationResult:
    """Tier 1: summary.json の v2 contract 検証."""
    base = _check_required(
        report, RUN_REPORT_CONTRACT_V2, artifact="run_report", mode=mode
    )
    invalid: list[str] = []
    # 型分離: cascade_contract_version は int、 既存 schema_version は string
    ccv = report.get("cascade_contract_version")
    if ccv is not None and not isinstance(ccv, int):
        if mode == SchemaEnforcementMode.FAIL_CLOSED:
            raise SchemaContractError(
                f"cascade_contract_version must be int, got {type(ccv).__name__}"
            )
        invalid.append("cascade_contract_version")
        logger.warning(
            "schema_contract.type_violation",
            artifact="run_report",
            field="cascade_contract_version",
            type=type(ccv).__name__,
        )
    if invalid:
        return ValidationResult(
            ok=False, missing=base.missing, invalid=tuple(invalid)
        )
    return base


def assert_diagnostics_v2(
    record: Mapping[str, Any],
    *,
    mode: SchemaEnforcementMode,
) -> ValidationResult:
    """Tier 1: diagnostics sidecar / stage_a_provenance の v2 contract 検証."""
    return _check_required(
        record, DIAGNOSTICS_CONTRACT_V2, artifact="diagnostics", mode=mode
    )


# ---------------------------------------------------------------------------
# Tier 2 軽量ガード (non-blocking)
# ---------------------------------------------------------------------------


def assert_epoch_id_present_for_display(
    obj: Mapping[str, Any] | None,
    *,
    artifact: str,
) -> None:
    """Tier 2 派生表示 artifact 用の軽量 non-blocking ガード.

    ``dataset_epoch_id`` 引用漏れを log warning + Counter 計測。 fail させない
    (Tier 2 は表示用なので運用事故化を避ける、 Codex Round 3 [Suggestion])。
    """
    if obj is None or "dataset_epoch_id" not in obj:
        logger.warning(
            "schema_contract.tier2_epoch_id_missing",
            artifact=artifact,
            keys=sorted((obj or {}).keys()),
        )
