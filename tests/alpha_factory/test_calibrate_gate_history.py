"""T040: calibrate_gate_history unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.alpha_factory.calibrate_gate_history import (
    DriftAlerts,
    HistoryRecord,
    append_record,
    compute_drift,
    read_history,
)


def _record(
    *,
    run_id: str = "run_test",
    decision: str = "in_band",
    actual: float = 0.15,
    target: float = 0.15,
    tol: float = 0.05,
    prev_t: float = 0.10,
    new_t: float = 0.10,
    delta: float = 0.0,
    clamped_floor_or_ceiling: bool = False,
    var_fitness_pen: float | None = 0.01,
) -> HistoryRecord:
    return HistoryRecord(
        run_id=run_id,
        applied_at="2026-04-26T00:00:00+09:00",
        n_rows_total=96,
        n_rows_used=80,
        aggregation_mode="last_k_generations",
        aggregation_window=5,
        actual_pass_rate=actual,
        target_pass_rate=target,
        tol=tol,
        prev_threshold=prev_t,
        new_threshold=new_t,
        delta=delta,
        decision=decision,
        var_fitness_pen=var_fitness_pen,
        clamped_by_delta=False,
        clamped_by_floor_or_ceiling=clamped_floor_or_ceiling,
        stage_b_pass_count=0,
        stage_c_pass_count=0,
        live_criteria_gap={"sharpe": 0.3, "total_pnl": 0.0},
    )


class TestAppendAndRead:
    def test_append_creates_parent_dir(self, tmp_path: Path) -> None:
        path = tmp_path / "deep" / "nested" / "history.jsonl"
        rec = _record(run_id="run_001")
        append_record(rec, path)
        assert path.exists()

    def test_round_trip_single_record(self, tmp_path: Path) -> None:
        path = tmp_path / "history.jsonl"
        rec = _record(run_id="run_001", decision="tighten")
        append_record(rec, path)
        loaded = read_history(path)
        assert len(loaded) == 1
        assert loaded[0].run_id == "run_001"
        assert loaded[0].decision == "tighten"

    def test_append_multiple_preserves_order(self, tmp_path: Path) -> None:
        path = tmp_path / "history.jsonl"
        for i in range(5):
            append_record(_record(run_id=f"run_{i:03d}"), path)
        loaded = read_history(path)
        assert [r.run_id for r in loaded] == [f"run_{i:03d}" for i in range(5)]

    def test_read_history_missing_file_returns_empty(
        self, tmp_path: Path
    ) -> None:
        loaded = read_history(tmp_path / "missing.jsonl")
        assert loaded == []

    def test_read_history_skips_corrupted_lines(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        good = json.dumps({**_record(run_id="ok").__dict__})
        with path.open("w") as f:
            f.write("not-json\n")
            f.write(good + "\n")
            f.write("\n")  # 空行も無視
        loaded = read_history(path)
        assert len(loaded) == 1
        assert loaded[0].run_id == "ok"

    def test_read_history_skips_schema_mismatch(self, tmp_path: Path) -> None:
        path = tmp_path / "history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            # 必須 field 欠落 (古い record format)
            f.write(json.dumps({"run_id": "incomplete"}) + "\n")
            f.write(
                json.dumps({**_record(run_id="ok").__dict__}) + "\n"
            )
        loaded = read_history(path)
        assert len(loaded) == 1
        assert loaded[0].run_id == "ok"

    def test_last_n_filtering(self, tmp_path: Path) -> None:
        path = tmp_path / "history.jsonl"
        for i in range(10):
            append_record(_record(run_id=f"run_{i:03d}"), path)
        loaded = read_history(path, last_n=3)
        assert len(loaded) == 3
        assert [r.run_id for r in loaded] == [
            "run_007", "run_008", "run_009"
        ]


class TestComputeDrift:
    def test_no_records_returns_no_alerts(self) -> None:
        analysis = compute_drift([])
        assert analysis.alerts.any_alert is False
        assert analysis.n_tighten == 0
        assert analysis.n_loosen == 0
        assert analysis.max_abs_gap == 0.0

    def test_monotone_tighten_alerts_when_threshold_reached(self) -> None:
        recs = [
            _record(run_id=f"r{i}", decision="tighten") for i in range(4)
        ]
        recs.append(_record(run_id="r4", decision="in_band"))
        analysis = compute_drift(recs, monotone_threshold=4)
        assert analysis.alerts.monotone_tighten is True
        assert analysis.alerts.monotone_loosen is False
        assert analysis.alerts.any_alert is True

    def test_monotone_loosen_alerts(self) -> None:
        recs = [
            _record(run_id=f"r{i}", decision="loosen") for i in range(5)
        ]
        analysis = compute_drift(recs, monotone_threshold=4)
        assert analysis.alerts.monotone_loosen is True

    def test_threshold_clamp_alerts(self) -> None:
        recs = [
            _record(run_id=f"r{i}", clamped_floor_or_ceiling=True)
            for i in range(3)
        ]
        analysis = compute_drift(recs, clamp_threshold=3)
        assert analysis.alerts.threshold_clamp is True

    def test_band_excess_alerts_when_actual_outside(self) -> None:
        # tol=0.05, target=0.15, actual=0.30 → gap=0.15 > 2*0.05=0.10
        recs = [_record(actual=0.30, target=0.15, tol=0.05)]
        analysis = compute_drift(recs)
        assert analysis.alerts.pass_rate_band_excess is True

    def test_no_alert_when_all_in_band_and_no_clamp(self) -> None:
        recs = [
            _record(run_id=f"r{i}", decision="in_band", actual=0.16)
            for i in range(5)
        ]
        analysis = compute_drift(recs)
        assert analysis.alerts.any_alert is False

    def test_max_abs_gap_computed(self) -> None:
        recs = [
            _record(actual=0.10, target=0.15),  # gap -0.05
            _record(actual=0.25, target=0.15),  # gap +0.10
            _record(actual=0.18, target=0.15),  # gap +0.03
        ]
        analysis = compute_drift(recs)
        assert analysis.max_abs_gap == pytest.approx(0.10)


class TestDriftAlertsAnyAlert:
    def test_all_false_means_no_alert(self) -> None:
        a = DriftAlerts(False, False, False, False)
        assert a.any_alert is False

    def test_single_true_triggers_alert(self) -> None:
        for fn in [
            lambda: DriftAlerts(True, False, False, False),
            lambda: DriftAlerts(False, True, False, False),
            lambda: DriftAlerts(False, False, True, False),
            lambda: DriftAlerts(False, False, False, True),
        ]:
            assert fn().any_alert is True
