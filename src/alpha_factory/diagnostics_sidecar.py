"""T033: Stage A diagnostics sidecar writer.

DiagnosticsCollector が蓄積した per-individual records を
``reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`` に
出力する。production GA からは fail-open で呼ばれる
(書き込みエラー時は warning ログのみ、GA は止めない)。

詳細: devnotes/20260425-0937-cost-pnl-ledger-eventsource/
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

import pyarrow as pa
import pyarrow.parquet as pq
import structlog

from src.alpha_factory.diagnostics_collector import DiagnosticsCollector

logger = structlog.get_logger(__name__)

__all__ = [
    "STAGE_A_PROVENANCE_SCHEMA",
    "build_sidecar_table",
    "sidecar_relative_path",
    "write_stage_a_provenance",
]

# sidecar Parquet schema (T033 SSOT)
# 主キー: (lane_id, generation, individual_name)
STAGE_A_PROVENANCE_SCHEMA: Final[pa.Schema] = pa.schema(
    [
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


def build_sidecar_table(rows: Sequence[dict[str, Any]]) -> pa.Table:
    """rows (DiagnosticsCollector.to_rows() 出力) から pyarrow Table を構築."""
    return pa.Table.from_pylist(list(rows), schema=STAGE_A_PROVENANCE_SCHEMA)


def write_stage_a_provenance(
    collector: DiagnosticsCollector,
    output_path: Path,
) -> Path | None:
    """sidecar Parquet を書き出す。

    fail-open: I/O エラー / schema mismatch 時は warning + None 返却で
    GA 完走を妨げない。

    Args:
        collector: GA run-level の DiagnosticsCollector。
        output_path: 出力 Parquet path (絶対 or 相対)。

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
        table = build_sidecar_table(rows)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, output_path)
    except Exception as exc:
        # fail-open: GA を止めない、warning のみ
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
