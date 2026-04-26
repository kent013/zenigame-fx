"""T033: Per-individual diagnostics collector for sidecar emission.

Stage A/B/C 評価結果を generation 中に蓄積し、GA 完了時に sidecar Parquet として
flush する。production GA 経路から fail-open で利用される。

archive Parquet schema は touch しない。post-RUN で
``reports/run-reports/run-{N}/diagnostics/stage_a_provenance.parquet`` に出力する。

詳細: devnotes/20260425-0937-cost-pnl-ledger-eventsource/
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final

from src.alpha_factory.stage_gate import StageResult

__all__ = [
    "VALID_METRIC_STAGES",
    "DiagnosticsCollector",
    "IndividualDiagnostics",
]

# metric_stage の解釈: 「到達した最高通過段」(pass-based)
# stage_a_only      = Stage A 不通過 (または Stage B/C 未評価)
# stage_a_evaluated = Stage A 通過 (Stage B 未評価 / 不通過)
# stage_b_evaluated = Stage B 通過 (Stage C 未評価 / 不通過)
# stage_c_evaluated = Stage C 通過
VALID_METRIC_STAGES: Final[frozenset[str]] = frozenset(
    {
        "stage_a_only",
        "stage_a_evaluated",
        "stage_b_evaluated",
        "stage_c_evaluated",
    }
)


@dataclass
class IndividualDiagnostics:
    """Per-individual diagnostics record (mutable during a generation)."""

    lane_id: str
    generation: int
    individual_name: str
    trade_count: int = 0
    total_pnl_stage_a: float = 0.0
    sharpe_stage_a: float | None = None
    stage_a_pass: bool = False
    stage_b_pass: bool | None = None  # None = not evaluated
    stage_c_pass: bool | None = None  # None = not evaluated


class DiagnosticsCollector:
    """In-memory collector for per-individual stage diagnostics.

    Lifecycle:
    - Created in run_ga.py with run-level scope
    - Updated by stage_gate / swim_lane after each StageResult is produced
    - Flushed to Parquet sidecar at GA completion (writer は別モジュール)

    主キー: ``(lane_id, generation, individual_name)`` の複合キー
    (既存 archive と整合)。同一キーの再記録は last-write-wins。
    """

    def __init__(self) -> None:
        self._records: dict[tuple[str, int, str], IndividualDiagnostics] = {}

    def _key(
        self, lane_id: str, generation: int, individual_name: str
    ) -> tuple[str, int, str]:
        return (lane_id, generation, individual_name)

    def record_stage_a(
        self,
        lane_id: str,
        generation: int,
        individual_name: str,
        result: StageResult,
    ) -> None:
        """Stage A 結果を記録。同一キー再記録は last-write-wins (idempotent)."""
        payload_obj: Any = (
            result.metrics.get("payload", {})
            if hasattr(result, "metrics")
            else {}
        )
        if not isinstance(payload_obj, dict):
            payload: dict[str, Any] = {}
        else:
            payload = payload_obj
        # Defensive read: payload may lack new fields if older code path
        trade_count = int(payload.get("trade_count", 0) or 0)
        total_pnl_raw = payload.get("total_pnl", 0.0)
        try:
            total_pnl = float(total_pnl_raw) if total_pnl_raw is not None else 0.0
        except (TypeError, ValueError):
            total_pnl = 0.0
        if not math.isfinite(total_pnl):
            total_pnl = 0.0
        sharpe_raw = payload.get("trade_sharpe_raw")
        sharpe_stage_a: float | None = None
        if sharpe_raw is not None:
            try:
                v = float(sharpe_raw)
                if math.isfinite(v):
                    sharpe_stage_a = v
            except (TypeError, ValueError):
                sharpe_stage_a = None
        self._records[self._key(lane_id, generation, individual_name)] = (
            IndividualDiagnostics(
                lane_id=lane_id,
                generation=generation,
                individual_name=individual_name,
                trade_count=trade_count,
                total_pnl_stage_a=total_pnl,
                sharpe_stage_a=sharpe_stage_a,
                stage_a_pass=bool(result.passed),
            )
        )

    def record_stage_b(
        self,
        lane_id: str,
        generation: int,
        individual_name: str,
        passed: bool,
    ) -> None:
        """Stage B pass/fail を記録。Stage A 未記録なら no-op (defensive)."""
        rec = self._records.get(
            self._key(lane_id, generation, individual_name)
        )
        if rec is None:
            return
        rec.stage_b_pass = bool(passed)

    def record_stage_c(
        self,
        lane_id: str,
        generation: int,
        individual_name: str,
        passed: bool,
    ) -> None:
        """Stage C pass/fail を記録。Stage A 未記録なら no-op (defensive)."""
        rec = self._records.get(
            self._key(lane_id, generation, individual_name)
        )
        if rec is None:
            return
        rec.stage_c_pass = bool(passed)

    def derive_metric_stage(self, rec: IndividualDiagnostics) -> str:
        """post-hoc metric_stage 確定 (collector 側で flush 時に決定)."""
        if rec.stage_c_pass is True:
            return "stage_c_evaluated"
        if rec.stage_b_pass is True:
            return "stage_b_evaluated"
        if rec.stage_a_pass:
            return "stage_a_evaluated"
        return "stage_a_only"

    def to_rows(self) -> list[dict[str, Any]]:
        """Materialize records as plain dicts for Parquet writing.

        sidecar 出力の SSOT。CI invariant I2 を assert で保護
        (metric_stage が enum 内であること)。
        """
        rows: list[dict[str, Any]] = []
        for rec in self._records.values():
            metric_stage = self.derive_metric_stage(rec)
            assert metric_stage in VALID_METRIC_STAGES, (
                f"metric_stage out of enum: {metric_stage!r} "
                f"(rec={rec})"
            )
            rows.append(
                {
                    "lane_id": rec.lane_id,
                    "generation": rec.generation,
                    "individual_name": rec.individual_name,
                    "metric_stage": metric_stage,
                    "trade_count": rec.trade_count,
                    "total_pnl_stage_a": rec.total_pnl_stage_a,
                    "sharpe_stage_a": rec.sharpe_stage_a,
                    "stage_a_pass": rec.stage_a_pass,
                    "stage_b_pass": rec.stage_b_pass,
                    "stage_c_pass": rec.stage_c_pass,
                }
            )
        return rows

    def __len__(self) -> int:
        return len(self._records)
