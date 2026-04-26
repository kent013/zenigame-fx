"""T033: diagnostics_sidecar writer unit tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from src.alpha_factory.diagnostics_collector import DiagnosticsCollector
from src.alpha_factory.diagnostics_sidecar import (
    STAGE_A_PROVENANCE_SCHEMA,
    build_sidecar_table,
    sidecar_relative_path,
    write_stage_a_provenance,
)
from src.alpha_factory.stage_gate import StageResult


def _make_stage_a_result(
    *, passed: bool = True, trade_count: int = 50, total_pnl: float = 1234.5
) -> StageResult:
    payload: dict[str, Any] = {
        "trade_count": trade_count,
        "total_pnl": total_pnl,
        "trade_sharpe_raw": 0.3,
    }
    return StageResult(
        stage="A",
        passed=passed,
        metrics={"stage": "A", "payload": payload},
    )


class TestSidecarRelativePath:
    def test_path_format(self) -> None:
        assert sidecar_relative_path(19) == Path(
            "reports/run-reports/run-19/diagnostics/stage_a_provenance.parquet"
        )

    def test_different_run_numbers(self) -> None:
        assert "run-100" in str(sidecar_relative_path(100))


class TestBuildSidecarTable:
    def test_schema_matches(self) -> None:
        rows = [
            {
                "lane_id": "lane",
                "generation": 0,
                "individual_name": "g",
                "metric_stage": "stage_a_only",
                "trade_count": 10,
                "total_pnl_stage_a": 1.5,
                "sharpe_stage_a": 0.2,
                "stage_a_pass": False,
                "stage_b_pass": None,
                "stage_c_pass": None,
            }
        ]
        table = build_sidecar_table(rows)
        assert table.schema == STAGE_A_PROVENANCE_SCHEMA

    def test_schema_field_count(self) -> None:
        assert len(STAGE_A_PROVENANCE_SCHEMA.names) == 10


class TestWriteStageAProvenance:
    def test_writes_parquet_with_collector_records(
        self, tmp_path: Path
    ) -> None:
        c = DiagnosticsCollector()
        c.record_stage_a(
            "lane", 0, "g0_i0", _make_stage_a_result(passed=True)
        )
        out = tmp_path / "diag" / "stage_a_provenance.parquet"
        result = write_stage_a_provenance(c, out)
        assert result == out
        assert out.exists()

        # round-trip
        loaded = pq.read_table(out).to_pylist()
        assert len(loaded) == 1
        assert loaded[0]["lane_id"] == "lane"
        assert loaded[0]["individual_name"] == "g0_i0"
        assert loaded[0]["metric_stage"] == "stage_a_evaluated"

    def test_empty_collector_returns_none_no_write(
        self, tmp_path: Path
    ) -> None:
        c = DiagnosticsCollector()
        out = tmp_path / "stage_a_provenance.parquet"
        result = write_stage_a_provenance(c, out)
        assert result is None
        assert not out.exists()

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        c = DiagnosticsCollector()
        c.record_stage_a("lane", 0, "g", _make_stage_a_result(passed=True))
        nested = tmp_path / "deep" / "nested" / "dir" / "out.parquet"
        result = write_stage_a_provenance(c, nested)
        assert result == nested
        assert nested.exists()

    def test_fail_open_on_io_error(self, tmp_path: Path) -> None:
        """書き込み不能 path でも GA を止めず None を返す (fail-open)."""
        c = DiagnosticsCollector()
        c.record_stage_a("lane", 0, "g", _make_stage_a_result(passed=True))
        # 既存ファイルをディレクトリ扱いさせる: 書き込み不能 path
        bad = tmp_path / "file.txt"
        bad.write_text("blocker")
        # bad/ の下に書こうとする (file をディレクトリとして開けない)
        target = bad / "stage_a_provenance.parquet"
        result = write_stage_a_provenance(c, target)
        assert result is None  # fail-open
        # 例外は raise しない (caller の GA flow を止めない)


class TestRowSchemaInvariant:
    """sidecar 行数 == backtest 評価された個体数 (I1) 等の invariant."""

    def test_row_count_matches_records(self, tmp_path: Path) -> None:
        c = DiagnosticsCollector()
        for i in range(5):
            c.record_stage_a(
                "lane", 0, f"g0_i{i}", _make_stage_a_result(passed=(i % 2 == 0))
            )
        out = tmp_path / "stage_a_provenance.parquet"
        write_stage_a_provenance(c, out)
        loaded = pq.read_table(out)
        assert loaded.num_rows == 5
        assert len(c) == 5

    def test_total_pnl_finite_invariant(self, tmp_path: Path) -> None:
        """I3: total_pnl_stage_a が finite (NaN/Inf は collector で 0.0 化)."""
        c = DiagnosticsCollector()
        c.record_stage_a(
            "lane", 0, "g", _make_stage_a_result(total_pnl=float("nan"))
        )
        out = tmp_path / "stage_a_provenance.parquet"
        write_stage_a_provenance(c, out)
        loaded = pq.read_table(out).to_pylist()
        assert loaded[0]["total_pnl_stage_a"] == 0.0
