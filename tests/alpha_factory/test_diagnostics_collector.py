"""T033: DiagnosticsCollector unit tests.

詳細設計: devnotes/20260425-0937-cost-pnl-ledger-eventsource/detailed-design.md
"""

from __future__ import annotations

from typing import Any

import pytest

from src.alpha_factory.diagnostics_collector import (
    VALID_METRIC_STAGES,
    VALID_STAGE_C_GAP_CLASSES,
    DiagnosticsCollector,
    IndividualDiagnostics,
    _derive_stage_c_gap,
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


def _make_stage_c_result(
    *,
    passed: bool = True,
    total_pnl: float = 51000.0,
    trade_count: int = 60,
    lc_pass: dict[str, bool] | None = None,
    reason_codes: tuple[str, ...] = (),
    stress: dict[str, Any] | None = None,
    payload_override: Any = None,
) -> StageResult:
    """T109: Stage C StageResult を合成 (gap diagnostic テスト用)."""
    if payload_override is not None:
        payload: Any = payload_override
    else:
        if lc_pass is None:
            lc_pass = {
                "sharpe": True,
                "total_pnl": True,
                "max_drawdown": True,
                "trade_count_min": True,
                "trade_count_max": True,
            }
        if stress is None:
            stress = {
                "skipped": False,
                "pnl_degradation": 1500.0,
                "trade_count": trade_count - 5,
            }
        payload = {
            "total_pnl": total_pnl,
            "trade_count": trade_count,
            "live_criteria_pass": lc_pass,
            "stress": stress,
        }
    return StageResult(
        stage="C",
        passed=passed,
        metrics={"stage": "C", "payload": payload},
        reason_codes=reason_codes,
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
        c.record_stage_c("lane", 0, "g0_i0", _make_stage_c_result(passed=True))
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
        c.record_stage_c("lane", 0, "g0_i0", _make_stage_c_result(passed=True))
        rec = c._records[("lane", 0, "g0_i0")]
        assert rec.stage_c_pass is True
        assert rec.stage_c_gap_class == "pass"


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
        c.record_stage_c("lane", 0, "g0_i0", _make_stage_c_result(passed=True))
        rows = c.to_rows()
        assert rows[0]["metric_stage"] == "stage_c_evaluated"


class TestDeriveStageCGap:
    """T109: Stage B→C gap diagnostic v1 の分類ロジック."""

    def _lc(
        self,
        *,
        sharpe: bool = True,
        total_pnl: bool = True,
        max_drawdown: bool = True,
        trade_count_min: bool = True,
        trade_count_max: bool = True,
    ) -> dict[str, bool]:
        return {
            "sharpe": sharpe,
            "total_pnl": total_pnl,
            "max_drawdown": max_drawdown,
            "trade_count_min": trade_count_min,
            "trade_count_max": trade_count_max,
        }

    def test_pass(self) -> None:
        r = _make_stage_c_result(passed=True)
        assert _derive_stage_c_gap(r)["gap_class"] == "pass"

    def test_pnl_only(self) -> None:
        r = _make_stage_c_result(
            passed=False, lc_pass=self._lc(total_pnl=False)
        )
        assert _derive_stage_c_gap(r)["gap_class"] == "pnl_only"

    def test_count_only_min(self) -> None:
        r = _make_stage_c_result(
            passed=False, lc_pass=self._lc(trade_count_min=False)
        )
        assert _derive_stage_c_gap(r)["gap_class"] == "count_only"

    def test_count_only_max(self) -> None:
        r = _make_stage_c_result(
            passed=False, lc_pass=self._lc(trade_count_max=False)
        )
        assert _derive_stage_c_gap(r)["gap_class"] == "count_only"

    def test_both_pnl_count(self) -> None:
        r = _make_stage_c_result(
            passed=False,
            lc_pass=self._lc(total_pnl=False, trade_count_min=False),
        )
        assert _derive_stage_c_gap(r)["gap_class"] == "both_pnl_count"

    def test_sharpe_involved(self) -> None:
        r = _make_stage_c_result(
            passed=False, lc_pass=self._lc(sharpe=False)
        )
        assert _derive_stage_c_gap(r)["gap_class"] == "sharpe_involved"

    def test_sharpe_involved_with_pnl(self) -> None:
        # sharpe ∧ pnl 両方 fail (count なし) → sharpe_involved 優先
        r = _make_stage_c_result(
            passed=False, lc_pass=self._lc(sharpe=False, total_pnl=False)
        )
        assert _derive_stage_c_gap(r)["gap_class"] == "sharpe_involved"

    def test_mixed_dd_and_pnl(self) -> None:
        # dd ∧ pnl fail (sharpe/count なし) → mixed
        r = _make_stage_c_result(
            passed=False,
            lc_pass=self._lc(max_drawdown=False, total_pnl=False),
        )
        assert _derive_stage_c_gap(r)["gap_class"] == "mixed"

    def test_stress_or_other(self) -> None:
        # base lc 全通過だが passed=False (stress / intraday 等で fail)
        r = _make_stage_c_result(
            passed=False,
            lc_pass=self._lc(),
            reason_codes=("spread_stress.trade_count<min",),
        )
        assert _derive_stage_c_gap(r)["gap_class"] == "stress_or_other"

    def test_system_fail_system_failure(self) -> None:
        r = _make_stage_c_result(
            passed=False,
            lc_pass=self._lc(total_pnl=False),
            reason_codes=("system_failure",),
        )
        assert _derive_stage_c_gap(r)["gap_class"] == "system_fail"

    def test_system_fail_worker_error(self) -> None:
        # 並列パスの worker_error 代替 StageResult: live_criteria_pass を
        # 持たない payload + reason_codes=("worker_error",)。
        r = StageResult(
            stage="C",
            passed=False,
            metrics={
                "stage": "C",
                "payload": {
                    "worker_error_code": "X",
                    "worker_error_message": "boom",
                },
            },
            reason_codes=("worker_error",),
        )
        assert _derive_stage_c_gap(r)["gap_class"] == "system_fail"

    def test_raw_values_captured(self) -> None:
        r = _make_stage_c_result(
            passed=False,
            total_pnl=1234.0,
            trade_count=42,
            lc_pass=self._lc(total_pnl=False),
            stress={
                "skipped": False,
                "pnl_degradation": 800.0,
                "trade_count": 37,
            },
        )
        out = _derive_stage_c_gap(r)
        assert out["base_total_pnl"] == pytest.approx(1234.0)
        assert out["base_trade_count"] == 42
        assert out["stress_pnl_degradation"] == pytest.approx(800.0)
        assert out["stress_trade_count"] == 37

    def test_stress_skipped_yields_none(self) -> None:
        r = _make_stage_c_result(
            passed=False,
            lc_pass=self._lc(total_pnl=False),
            stress={"skipped": True, "pnl_degradation": 0.0, "trade_count": 0},
        )
        out = _derive_stage_c_gap(r)
        assert out["stress_pnl_degradation"] is None
        assert out["stress_trade_count"] is None
        assert out["gap_class"] == "pnl_only"

    def test_inf_trade_count_does_not_collapse_diagnostic(self) -> None:
        # trade_count=inf (壊れた payload) でも int(inf) の OverflowError を
        # 握り、gap_class は live_criteria_pass から正しく算出される
        # (Codex impl-review Round 1 [Suggestion])。
        r = _make_stage_c_result(
            passed=False,
            total_pnl=1000.0,
            lc_pass=self._lc(total_pnl=False),
            payload_override={
                "total_pnl": 1000.0,
                "trade_count": float("inf"),
                "live_criteria_pass": self._lc(total_pnl=False),
                "stress": {
                    "skipped": False,
                    "pnl_degradation": 100.0,
                    "trade_count": float("inf"),
                },
            },
        )
        out = _derive_stage_c_gap(r)
        assert out["gap_class"] == "pnl_only"
        assert out["base_trade_count"] is None
        assert out["stress_trade_count"] is None
        assert out["base_total_pnl"] == pytest.approx(1000.0)

    def test_missing_payload_is_unknown(self) -> None:
        r = StageResult(
            stage="C",
            passed=False,
            metrics={"stage": "C", "payload": "not-a-dict"},
            reason_codes=(),
        )
        assert _derive_stage_c_gap(r)["gap_class"] == "unknown"

    def test_missing_live_criteria_pass_is_unknown(self) -> None:
        r = _make_stage_c_result(
            passed=False, payload_override={"total_pnl": 1.0, "trade_count": 2}
        )
        assert _derive_stage_c_gap(r)["gap_class"] == "unknown"

    def test_all_gap_classes_in_enum(self) -> None:
        # 代表ケースで返る gap_class が enum 集合内であること
        for r in (
            _make_stage_c_result(passed=True),
            _make_stage_c_result(passed=False, lc_pass=self._lc(total_pnl=False)),
        ):
            assert _derive_stage_c_gap(r)["gap_class"] in VALID_STAGE_C_GAP_CLASSES


class TestToRowsStageCGapColumns:
    """T109: to_rows が gap diagnostic 列を出力すること."""

    def test_stage_c_gap_columns_present(self) -> None:
        c = DiagnosticsCollector()
        c.record_stage_a("lane", 0, "g0_i0", _make_stage_a_result(passed=True))
        c.record_stage_b("lane", 0, "g0_i0", passed=True)
        c.record_stage_c(
            "lane",
            0,
            "g0_i0",
            _make_stage_c_result(
                passed=False,
                total_pnl=1000.0,
                trade_count=20,
                lc_pass={
                    "sharpe": True,
                    "total_pnl": True,
                    "max_drawdown": True,
                    "trade_count_min": False,
                    "trade_count_max": True,
                },
            ),
        )
        row = c.to_rows()[0]
        assert row["stage_c_gap_class"] == "count_only"
        assert row["stage_c_base_total_pnl"] == pytest.approx(1000.0)
        assert row["stage_c_base_trade_count"] == 20
        assert "stage_c_stress_pnl_degradation" in row
        assert "stage_c_stress_trade_count" in row

    def test_stage_a_only_rows_have_null_gap_columns(self) -> None:
        c = DiagnosticsCollector()
        c.record_stage_a("lane", 0, "g0_i0", _make_stage_a_result(passed=False))
        row = c.to_rows()[0]
        assert row["stage_c_gap_class"] is None
        assert row["stage_c_base_total_pnl"] is None
        assert row["stage_c_base_trade_count"] is None


class TestRecordParetoFeaturesLite:
    """T111: ParetoFeaturesLite (NSGA-II selection 用 Stage B 完結軸) の記録."""

    def test_record_stage_b_stores_pareto_lite(self) -> None:
        from src.alpha_factory.pareto_features import ParetoFeaturesLite

        c = DiagnosticsCollector()
        c.record_stage_a("lane", 0, "g0_i0", _make_stage_a_result(passed=True))
        lite = ParetoFeaturesLite(
            net_pnl_after_cost=61000.0,
            pooled_dd_per_fold_max=0.07,
            mission_inf_gap=0.0,
            is_feasible_invariant=True,
            pareto_axis_usable=True,
            source_stage="B",
        )
        c.record_stage_b("lane", 0, "g0_i0", passed=True, pareto_lite=lite)
        row = c.to_rows()[0]
        assert row["pareto_net_pnl_after_cost"] == 61000.0
        assert row["pareto_pooled_dd_per_fold_max"] == 0.07
        assert row["pareto_mission_inf_gap"] == 0.0
        assert row["pareto_axis_usable"] is True
        assert row["pareto_source_stage"] == "B"

    def test_record_stage_b_without_pareto_leaves_columns_none(self) -> None:
        c = DiagnosticsCollector()
        c.record_stage_a("lane", 0, "g0_i0", _make_stage_a_result(passed=True))
        c.record_stage_b("lane", 0, "g0_i0", passed=True)
        row = c.to_rows()[0]
        assert row["pareto_axis_usable"] is None
        assert row["pareto_source_stage"] is None
        assert row["pareto_net_pnl_after_cost"] is None

    def test_to_rows_invariant_usable_requires_source_b(self) -> None:
        from src.alpha_factory.pareto_features import ParetoFeaturesLite

        c = DiagnosticsCollector()
        c.record_stage_a("lane", 0, "g0_i0", _make_stage_a_result(passed=True))
        # usable=True なのに source_stage != "B" は invariant 違反 (assert)
        bad = ParetoFeaturesLite(
            net_pnl_after_cost=1.0,
            pooled_dd_per_fold_max=0.1,
            mission_inf_gap=0.0,
            is_feasible_invariant=True,
            pareto_axis_usable=True,
            source_stage=None,  # invariant violation
        )
        c.record_stage_b("lane", 0, "g0_i0", passed=True, pareto_lite=bad)
        with pytest.raises(AssertionError):
            c.to_rows()


class TestArchiveSchemaUnchangedByPareto:
    """T111: ParetoFeaturesLite は sidecar 専用、 archive schema には流さない."""

    def test_genomes_schema_has_no_pareto_columns(self) -> None:
        from src.alpha_factory.archive import GENOMES_SCHEMA

        pareto_cols = [n for n in GENOMES_SCHEMA.names if n.startswith("pareto_")]
        assert pareto_cols == []
