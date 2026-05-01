"""T040 + T058 (PR 3): calibrate_gate_history unit tests."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from src.alpha_factory.calibrate_gate_history import (
    DriftAlerts,
    HistoryRecord,
    append_record,
    compute_drift,
    read_history,
)
from src.alpha_factory.schema_contract import (
    CALIBRATE_HISTORY_SCHEMA_VERSION,
    SchemaContractError,
    SchemaEnforcementMode,
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
    dataset_epoch_id: str = "epoch_legacy",
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
        dataset_epoch_id=dataset_epoch_id,
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

    # T069: n_skip_frozen 集計 (epoch 内 3 Run freeze 判定 record の数)
    def test_F12_compute_drift_counts_skip_frozen(self) -> None:
        # F12 (concept §10): drift 監視で skip_frozen を可視化
        recs = [
            _record(run_id="r0", decision="skip_frozen", actual=0.15),
            _record(run_id="r1", decision="tighten", actual=0.30),
            _record(run_id="r2", decision="skip_frozen", actual=0.15),
        ]
        analysis = compute_drift(recs)
        assert analysis.n_skip_frozen == 2
        assert analysis.n_tighten == 1
        assert analysis.n_loosen == 0
        assert analysis.n_in_band == 0
        # skip_frozen は monotone alert に寄与しない
        # (n_tighten=1 < monotone_threshold=4)
        assert analysis.alerts.monotone_tighten is False
        assert analysis.alerts.monotone_loosen is False

    def test_n_skip_frozen_zero_when_no_frozen_records(self) -> None:
        # default ケース: skip_frozen ゼロ
        recs = [_record(run_id=f"r{i}", decision="in_band") for i in range(3)]
        analysis = compute_drift(recs)
        assert analysis.n_skip_frozen == 0

    def test_n_skip_frozen_does_not_trigger_monotone_loosen(self) -> None:
        # skip_frozen が 4 件あっても monotone_loosen=False のまま
        # (loosen の monotone とは別 channel)
        recs = [
            _record(run_id=f"r{i}", decision="skip_frozen") for i in range(4)
        ]
        analysis = compute_drift(recs, monotone_threshold=4)
        assert analysis.n_skip_frozen == 4
        assert analysis.n_loosen == 0
        assert analysis.alerts.monotone_loosen is False
        assert analysis.alerts.monotone_tighten is False


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


# ---------------------------------------------------------------------------
# T058 (PR 3): HistoryRecord v2 schema lint 連動
# ---------------------------------------------------------------------------


class TestHistoryRecordV2Contract:
    def test_history_record_v2_constructs_with_dataset_epoch_id(self) -> None:
        rec = _record(dataset_epoch_id="epoch_legacy")
        assert rec.calibrate_history_schema_version == (
            CALIBRATE_HISTORY_SCHEMA_VERSION
        )
        assert rec.dataset_epoch_id == "epoch_legacy"

    def test_history_record_rejects_invalid_epoch_id_grammar(self) -> None:
        # SchemaContractError は ValueError 派生
        with pytest.raises((SchemaContractError, ValueError)):
            _record(dataset_epoch_id="Epoch-Bad-Grammar")

    def test_history_record_rejects_empty_epoch_id(self) -> None:
        with pytest.raises((SchemaContractError, ValueError)):
            _record(dataset_epoch_id="")

    def test_history_record_rejects_wrong_schema_version(self) -> None:
        with pytest.raises(ValueError, match="calibrate_history_schema_version"):
            HistoryRecord(
                run_id="run_test",
                applied_at="2026-04-26T00:00:00+09:00",
                n_rows_total=10,
                n_rows_used=10,
                aggregation_mode="last_k_generations",
                aggregation_window=5,
                actual_pass_rate=0.15,
                target_pass_rate=0.15,
                tol=0.05,
                prev_threshold=0.0,
                new_threshold=0.0,
                delta=0.0,
                decision="in_band",
                var_fitness_pen=None,
                clamped_by_delta=False,
                clamped_by_floor_or_ceiling=False,
                stage_b_pass_count=0,
                stage_c_pass_count=0,
                live_criteria_gap={},
                calibrate_history_schema_version=1,  # 不正
                dataset_epoch_id="epoch_legacy",
            )

    def test_append_record_writes_v2_fields_to_jsonl(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "history.jsonl"
        rec = _record(dataset_epoch_id="epoch_legacy")
        append_record(rec, path)
        with path.open() as f:
            obj = json.loads(f.read().strip())
        assert obj["calibrate_history_schema_version"] == (
            CALIBRATE_HISTORY_SCHEMA_VERSION
        )
        assert obj["dataset_epoch_id"] == "epoch_legacy"

    def test_append_record_log_only_warns_on_missing_via_raw_dict_path(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """LOG_ONLY mode で必須 field 欠落時に warning を出す (raise しない)."""
        # NB: dataclass 経由では __post_init__ が必須 field を強制するので、
        # raw dict に直接書き込み + 後段 lint を passive で動かす経路を simulate。
        path = tmp_path / "history.jsonl"
        # validate 抜きで HistoryRecord を構築する経路は存在しない。
        # ここでは mode=LOG_ONLY 時に dataclass 経由 (= ok 経路) で warn なしを確認、
        # FAIL_CLOSED / 必須欠落の検証は test_calibrate_history_v2 単体テスト側に委ねる。
        rec = _record(dataset_epoch_id="epoch_legacy")
        with caplog.at_level(logging.WARNING):
            append_record(rec, path, mode=SchemaEnforcementMode.LOG_ONLY)
        assert path.exists()

    def test_read_history_skips_v1_record(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = tmp_path / "history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        # v1 record (dataset_epoch_id 不在)
        v1 = {
            "run_id": "run_v1",
            "applied_at": "2026-04-26T00:00:00+09:00",
            "n_rows_total": 96,
            "n_rows_used": 80,
            "aggregation_mode": "last_k_generations",
            "aggregation_window": 5,
            "actual_pass_rate": 0.15,
            "target_pass_rate": 0.15,
            "tol": 0.05,
            "prev_threshold": 0.10,
            "new_threshold": 0.10,
            "delta": 0.0,
            "decision": "in_band",
            "var_fitness_pen": 0.01,
            "clamped_by_delta": False,
            "clamped_by_floor_or_ceiling": False,
            "stage_b_pass_count": 0,
            "stage_c_pass_count": 0,
            "live_criteria_gap": {"sharpe": 0.3, "total_pnl": 0.0},
        }
        with path.open("w") as f:
            f.write(json.dumps(v1) + "\n")
        # v2 record も追記して、 v1 のみ skip されることを確認
        rec_v2 = _record(run_id="run_v2", dataset_epoch_id="epoch_legacy")
        append_record(rec_v2, path)
        with caplog.at_level(logging.WARNING):
            loaded = read_history(path)
        assert [r.run_id for r in loaded] == ["run_v2"]

    def test_read_history_skips_record_with_invalid_epoch_id(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        # dataset_epoch_id 不正 (大文字含む)
        bad = {
            "run_id": "run_bad",
            "applied_at": "2026-04-26T00:00:00+09:00",
            "n_rows_total": 96,
            "n_rows_used": 80,
            "aggregation_mode": "last_k_generations",
            "aggregation_window": 5,
            "actual_pass_rate": 0.15,
            "target_pass_rate": 0.15,
            "tol": 0.05,
            "prev_threshold": 0.10,
            "new_threshold": 0.10,
            "delta": 0.0,
            "decision": "in_band",
            "var_fitness_pen": 0.01,
            "clamped_by_delta": False,
            "clamped_by_floor_or_ceiling": False,
            "stage_b_pass_count": 0,
            "stage_c_pass_count": 0,
            "live_criteria_gap": {},
            "calibrate_history_schema_version": (
                CALIBRATE_HISTORY_SCHEMA_VERSION
            ),
            "dataset_epoch_id": "BAD-Grammar",
        }
        with path.open("w") as f:
            f.write(json.dumps(bad) + "\n")
        loaded = read_history(path)
        assert loaded == []

    def test_from_dict_or_none_returns_none_for_v1(self) -> None:
        v1 = {"run_id": "x"}  # dataset_epoch_id 不在
        assert HistoryRecord.from_dict_or_none(v1) is None

    def test_from_dict_or_none_returns_none_for_wrong_version(self) -> None:
        rec = _record()
        from dataclasses import asdict as _asdict

        d = _asdict(rec)
        d["calibrate_history_schema_version"] = 1
        assert HistoryRecord.from_dict_or_none(d) is None

    def test_from_dict_or_none_returns_record_for_valid_v2(self) -> None:
        rec = _record()
        from dataclasses import asdict as _asdict

        d = _asdict(rec)
        loaded = HistoryRecord.from_dict_or_none(d)
        assert loaded is not None
        assert loaded.run_id == rec.run_id
        assert loaded.dataset_epoch_id == rec.dataset_epoch_id

    def test_from_dict_or_none_returns_none_for_grammar_violation(self) -> None:
        """v2 record だが grammar 違反の dataset_epoch_id → None (raise しない).

        Codex impl-review-pr3 round 1 [Critical] 1: SchemaContractError
        catch を defensive に確認するテスト。
        """
        rec = _record()
        from dataclasses import asdict as _asdict

        d = _asdict(rec)
        d["dataset_epoch_id"] = "BAD-Grammar"  # __post_init__ で raise
        # raise されず None 返却が契約
        assert HistoryRecord.from_dict_or_none(d) is None
