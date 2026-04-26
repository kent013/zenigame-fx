"""T033: DiagnosticsCollector unit tests.

詳細設計: devnotes/20260425-0937-cost-pnl-ledger-eventsource/detailed-design.md
"""

from __future__ import annotations

from typing import Any

import pytest

from src.alpha_factory.diagnostics_collector import (
    VALID_METRIC_STAGES,
    DiagnosticsCollector,
    IndividualDiagnostics,
)
from src.alpha_factory.stage_gate import StageResult


def _make_stage_a_result(
    *,
    passed: bool = True,
    trade_count: int = 50,
    total_pnl: float = 1234.5,
    trade_sharpe_raw: float | None = 0.3,
) -> StageResult:
    payload: dict[str, Any] = {
        "trade_count": trade_count,
        "total_pnl": total_pnl,
        "trade_sharpe_raw": trade_sharpe_raw,
        "fitness_pen": 0.27 if trade_sharpe_raw is not None else None,
    }
    return StageResult(
        stage="A",
        passed=passed,
        metrics={"stage": "A", "payload": payload},
    )


class TestRecordStageA:
    def test_records_stage_a_payload_correctly(self) -> None:
        c = DiagnosticsCollector()
        c.record_stage_a(
            "lane",
            0,
            "g0_i0",
            _make_stage_a_result(
                passed=True, trade_count=42, total_pnl=999.5, trade_sharpe_raw=0.5
            ),
        )
        assert len(c) == 1
        rec = c._records[("lane", 0, "g0_i0")]
        assert isinstance(rec, IndividualDiagnostics)
        assert rec.trade_count == 42
        assert rec.total_pnl_stage_a == pytest.approx(999.5)
        assert rec.sharpe_stage_a == pytest.approx(0.5)
        assert rec.stage_a_pass is True
        assert rec.stage_b_pass is None  # not evaluated
        assert rec.stage_c_pass is None

    def test_handles_missing_payload_fields(self) -> None:
        """旧 payload 形式でも crash せず default 値で記録."""
        c = DiagnosticsCollector()
        result = StageResult(
            stage="A",
            passed=False,
            metrics={"stage": "A", "payload": {}},  # 空 payload
        )
        c.record_stage_a("lane", 0, "g0_i0", result)
        rec = c._records[("lane", 0, "g0_i0")]
        assert rec.trade_count == 0
        assert rec.total_pnl_stage_a == 0.0
        assert rec.sharpe_stage_a is None
        assert rec.stage_a_pass is False

    def test_handles_nonfinite_total_pnl(self) -> None:
        """NaN/Inf total_pnl は 0.0 に正規化."""
        c = DiagnosticsCollector()
        c.record_stage_a(
            "lane",
            0,
            "g0_i0",
            _make_stage_a_result(total_pnl=float("nan")),
        )
        rec = c._records[("lane", 0, "g0_i0")]
        assert rec.total_pnl_stage_a == 0.0

        c.record_stage_a(
            "lane",
            0,
            "g0_i1",
            _make_stage_a_result(total_pnl=float("inf")),
        )
        rec2 = c._records[("lane", 0, "g0_i1")]
        assert rec2.total_pnl_stage_a == 0.0

    def test_handles_nonfinite_sharpe(self) -> None:
        """NaN/Inf sharpe は None に正規化."""
        c = DiagnosticsCollector()
        c.record_stage_a(
            "lane",
            0,
            "g0_i0",
            _make_stage_a_result(trade_sharpe_raw=float("nan")),
        )
        rec = c._records[("lane", 0, "g0_i0")]
        assert rec.sharpe_stage_a is None

    def test_idempotent_on_duplicate_key_last_write_wins(self) -> None:
        c = DiagnosticsCollector()
        c.record_stage_a("lane", 0, "g0_i0", _make_stage_a_result(trade_count=10))
        c.record_stage_a("lane", 0, "g0_i0", _make_stage_a_result(trade_count=99))
        assert len(c) == 1
        assert c._records[("lane", 0, "g0_i0")].trade_count == 99


class TestRecordStageBStageC:
    def test_record_stage_b_noop_without_stage_a(self) -> None:
        """Stage A 未記録なら Stage B は no-op (defensive)."""
        c = DiagnosticsCollector()
        c.record_stage_b("lane", 0, "g0_i0", passed=True)
        assert len(c) == 0  # 何も追加されない

    def test_record_stage_c_noop_without_stage_a(self) -> None:
        c = DiagnosticsCollector()
        c.record_stage_c("lane", 0, "g0_i0", passed=True)
        assert len(c) == 0

    def test_record_stage_b_updates_existing(self) -> None:
        c = DiagnosticsCollector()
        c.record_stage_a("lane", 0, "g0_i0", _make_stage_a_result(passed=True))
        c.record_stage_b("lane", 0, "g0_i0", passed=True)
        rec = c._records[("lane", 0, "g0_i0")]
        assert rec.stage_b_pass is True
        assert rec.stage_c_pass is None

    def test_record_stage_c_updates_existing(self) -> None:
        c = DiagnosticsCollector()
        c.record_stage_a("lane", 0, "g0_i0", _make_stage_a_result(passed=True))
        c.record_stage_b("lane", 0, "g0_i0", passed=True)
        c.record_stage_c("lane", 0, "g0_i0", passed=True)
        rec = c._records[("lane", 0, "g0_i0")]
        assert rec.stage_c_pass is True


class TestDeriveMetricStage:
    """metric_stage は post-hoc に flush 時確定 (stage_c > stage_b > stage_a > only)."""

    def _record(
        self,
        *,
        stage_a_pass: bool = False,
        stage_b_pass: bool | None = None,
        stage_c_pass: bool | None = None,
    ) -> IndividualDiagnostics:
        return IndividualDiagnostics(
            lane_id="lane",
            generation=0,
            individual_name="g",
            stage_a_pass=stage_a_pass,
            stage_b_pass=stage_b_pass,
            stage_c_pass=stage_c_pass,
        )

    def test_stage_a_only_when_stage_a_fails(self) -> None:
        c = DiagnosticsCollector()
        rec = self._record(stage_a_pass=False)
        assert c.derive_metric_stage(rec) == "stage_a_only"

    def test_stage_a_evaluated_when_stage_a_passes_no_b(self) -> None:
        c = DiagnosticsCollector()
        rec = self._record(stage_a_pass=True, stage_b_pass=None)
        assert c.derive_metric_stage(rec) == "stage_a_evaluated"

    def test_stage_a_evaluated_when_stage_a_passes_b_fails(self) -> None:
        c = DiagnosticsCollector()
        rec = self._record(stage_a_pass=True, stage_b_pass=False)
        assert c.derive_metric_stage(rec) == "stage_a_evaluated"

    def test_stage_b_evaluated_when_b_passes_no_c(self) -> None:
        c = DiagnosticsCollector()
        rec = self._record(
            stage_a_pass=True, stage_b_pass=True, stage_c_pass=None
        )
        assert c.derive_metric_stage(rec) == "stage_b_evaluated"

    def test_stage_b_evaluated_when_b_passes_c_fails(self) -> None:
        c = DiagnosticsCollector()
        rec = self._record(
            stage_a_pass=True, stage_b_pass=True, stage_c_pass=False
        )
        assert c.derive_metric_stage(rec) == "stage_b_evaluated"

    def test_stage_c_evaluated_when_c_passes(self) -> None:
        c = DiagnosticsCollector()
        rec = self._record(
            stage_a_pass=True, stage_b_pass=True, stage_c_pass=True
        )
        assert c.derive_metric_stage(rec) == "stage_c_evaluated"


class TestToRows:
    def test_returns_dict_per_record_with_metric_stage(self) -> None:
        c = DiagnosticsCollector()
        c.record_stage_a("lane", 0, "g0_i0", _make_stage_a_result(passed=True))
        c.record_stage_a(
            "lane", 0, "g0_i1", _make_stage_a_result(passed=False)
        )
        rows = c.to_rows()
        assert len(rows) == 2
        names = {r["individual_name"] for r in rows}
        assert names == {"g0_i0", "g0_i1"}
        for r in rows:
            assert r["metric_stage"] in VALID_METRIC_STAGES
            assert "lane_id" in r
            assert "trade_count" in r
            assert "total_pnl_stage_a" in r
            assert "sharpe_stage_a" in r
            assert "stage_a_pass" in r
            assert "stage_b_pass" in r
            assert "stage_c_pass" in r

    def test_empty_collector_returns_empty_rows(self) -> None:
        c = DiagnosticsCollector()
        assert c.to_rows() == []

    def test_metric_stage_enum_invariant(self) -> None:
        """to_rows は metric_stage が enum 内であることを assert (CI invariant I2)."""
        c = DiagnosticsCollector()
        c.record_stage_a("lane", 0, "g0_i0", _make_stage_a_result(passed=True))
        c.record_stage_b("lane", 0, "g0_i0", passed=True)
        c.record_stage_c("lane", 0, "g0_i0", passed=True)
        rows = c.to_rows()
        assert rows[0]["metric_stage"] == "stage_c_evaluated"
