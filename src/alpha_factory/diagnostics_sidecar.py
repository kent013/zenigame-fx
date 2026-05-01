"""T033: Stage A diagnostics sidecar writer.

DiagnosticsCollector が蓄積した per-individual records を
``reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`` に
出力する。production GA からは fail-open で呼ばれる
(書き込みエラー時は warning ログのみ、GA は止めない)。

T058: schema v2 propagate (詳細設計 § 施策 7)
- STAGE_A_PROVENANCE_SCHEMA に v2 必須 2 field を先頭追加
  (diagnostics_schema_version / dataset_epoch_id)
- ``build_sidecar_table`` / ``write_stage_a_provenance`` に optional
  ``run_context`` / ``mode`` kwargs を追加 (既存 caller 完全互換、
  default で旧挙動維持)
- ``run_context`` 未指定時は ``"epoch_legacy"`` を fallback として補完
- ``mode=LOG_ONLY`` default、 ``FAIL_CLOSED`` で必須 field 欠落 raise

詳細: devnotes/20260425-0937-cost-pnl-ledger-eventsource/
      devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md § 施策 7
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

import pyarrow as pa
import pyarrow.parquet as pq
import structlog

from src.alpha_factory.diagnostics_collector import DiagnosticsCollector
from src.alpha_factory.run_context import RunContext
from src.alpha_factory.schema_contract import (
    DIAGNOSTICS_SCHEMA_VERSION,
    SchemaEnforcementMode,
    assert_diagnostics_v2,
)

logger = structlog.get_logger(__name__)

__all__ = [
    "STAGE_A_PROVENANCE_SCHEMA",
    "build_sidecar_table",
    "sidecar_relative_path",
    "write_stage_a_provenance",
]

# sidecar Parquet schema (T033 SSOT + T058 v2)
# 主キー: (lane_id, generation, individual_name)
# T058: 先頭 2 field は schema v2 必須 (diagnostics_schema_version / dataset_epoch_id)
STAGE_A_PROVENANCE_SCHEMA: Final[pa.Schema] = pa.schema(
    [
        # T058 schema v2 必須 (詳細設計 行 1147-1164)
        pa.field("diagnostics_schema_version", pa.int32(), nullable=False),
        pa.field("dataset_epoch_id", pa.string(), nullable=False),
        # 既存 10 列 (T033)
        pa.field("lane_id", pa.string(), nullable=False),
        pa.field("generation", pa.int32(), nullable=False),
        pa.field("individual_name", pa.string(), nullable=False),
        pa.field("metric_stage", pa.string(), nullable=False),
        pa.field("trade_count", pa.int32(), nullable=False),
        pa.field("total_pnl_stage_a", pa.float64(), nullable=False),
        pa.field("sharpe_stage_a", pa.float64(), nullable=True),
        pa.field("stage_a_pass", pa.bool_(), nullable=False),
        pa.field("stage_b_pass", pa.bool_(), nullable=True),
        pa.field("stage_c_pass", pa.bool_(), nullable=True),
    ]
)


def sidecar_relative_path(run_number: int) -> Path:
    """sidecar Parquet の相対 path SSOT.

    summary.json の `diagnostics_sidecar` field と consumer (run-report skill)
    が同じ path を参照できるよう一元化する。
    """
    return Path(
        f"reports/run-reports/run-{run_number}/diagnostics/"
        "stage_a_provenance.parquet"
    )


def build_sidecar_table(
    rows: Sequence[dict[str, Any]],
    *,
    run_context: RunContext | None = None,
    mode: SchemaEnforcementMode = SchemaEnforcementMode.LOG_ONLY,
) -> pa.Table:
    """rows (DiagnosticsCollector.to_rows() 出力) から pyarrow Table を構築。

    T058: v2 必須 field (diagnostics_schema_version / dataset_epoch_id) を
    補完 + ``assert_diagnostics_v2`` で passive validation。

    Args:
        rows: DiagnosticsCollector が蓄積した per-individual record の list。
        run_context: T058 optional — 注入されていれば ``dataset_epoch_id`` を
            ここから補完。 ``None`` の場合は ``"epoch_legacy"`` fallback。
        mode: schema enforcement mode (LOG_ONLY default)。

    Returns:
        v2 必須 field を含む pyarrow Table。
    """
    enriched: list[dict[str, Any]] = []
    fallback_epoch_id = (
        run_context.dataset_epoch_id if run_context is not None else "epoch_legacy"
    )
    for row in rows:
        # caller 側 dict の mutate 防止のため shallow copy
        enriched_row = dict(row)
        if not enriched_row.get("dataset_epoch_id"):
            enriched_row["dataset_epoch_id"] = fallback_epoch_id
        enriched_row.setdefault(
            "diagnostics_schema_version", DIAGNOSTICS_SCHEMA_VERSION
        )
        # passive validation (LOG_ONLY: warning のみ / FAIL_CLOSED: raise)
        assert_diagnostics_v2(enriched_row, mode=mode)
        enriched.append(enriched_row)
    return pa.Table.from_pylist(enriched, schema=STAGE_A_PROVENANCE_SCHEMA)


def write_stage_a_provenance(
    collector: DiagnosticsCollector,
    output_path: Path,
    *,
    run_context: RunContext | None = None,
    mode: SchemaEnforcementMode = SchemaEnforcementMode.LOG_ONLY,
) -> Path | None:
    """sidecar Parquet を書き出す。

    fail-open: I/O エラー / schema mismatch 時は warning + None 返却で
    GA 完走を妨げない (既存挙動維持)。

    T058: v2 propagate (run_context / mode を ``build_sidecar_table`` に伝搬)。

    T067 移行ノート: T067 で FAIL_CLOSED を default 化する際、 本関数の
    既存 fail-open ガード (try/except: warning + None) は ``mode`` 引数だけ
    切替えても挙動が変わらない。 T067 切替時は (a) ``mode`` default を
    FAIL_CLOSED に変える、 もしくは (b) try/except の捕捉範囲を I/O 系のみに
    限定して ``SchemaContractError`` を再送出させる、 のいずれかが必要。
    詳細設計 行 1192-1203 を参照。

    Args:
        collector: GA run-level の DiagnosticsCollector。
        output_path: 出力 Parquet path (絶対 or 相対)。
        run_context: T058 optional — ``dataset_epoch_id`` 補完用。
        mode: schema enforcement mode (LOG_ONLY default)。

    Returns:
        書き込み成功時 ``output_path``、失敗時 ``None``。
    """
    rows = collector.to_rows()
    if not rows:
        logger.info(
            "diagnostics_sidecar.empty",
            reason="no_individuals_recorded",
            output_path=str(output_path),
        )
        return None
    try:
        table = build_sidecar_table(rows, run_context=run_context, mode=mode)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, output_path)
    except Exception as exc:
        # fail-open: GA を止めない、warning のみ
        # ただし FAIL_CLOSED 由来の SchemaContractError は意図的に表面化させたい
        # ところだが、 既存契約 (Path | None 返却) を破壊しないため warning に
        # 落として None 返却する (詳細設計 § 施策 7 行 1201-1203)。
        logger.warning(
            "diagnostics_sidecar.write_failure",
            output_path=str(output_path),
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return None
    logger.info(
        "diagnostics_sidecar.written",
        output_path=str(output_path),
        row_count=len(rows),
    )
    return output_path
