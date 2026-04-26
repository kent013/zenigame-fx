"""T040: calibrate_gate_drift CLI tests (subprocess + tmp history)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "alpha_factory" / "calibrate_gate_drift.py"


def _record_dict(
    *,
    run_id: str = "run_test",
    decision: str = "in_band",
    actual: float = 0.15,
    target: float = 0.15,
    clamped: bool = False,
) -> dict:
    return {
        "run_id": run_id,
        "applied_at": "2026-04-26T00:00:00+09:00",
        "n_rows_total": 96,
        "n_rows_used": 80,
        "aggregation_mode": "last_k_generations",
        "aggregation_window": 5,
        "actual_pass_rate": actual,
        "target_pass_rate": target,
        "tol": 0.05,
        "prev_threshold": 0.10,
        "new_threshold": 0.10,
        "delta": 0.0,
        "decision": decision,
        "var_fitness_pen": 0.01,
        "clamped_by_delta": False,
        "clamped_by_floor_or_ceiling": clamped,
        "stage_b_pass_count": 0,
        "stage_c_pass_count": 0,
        "live_criteria_gap": {"sharpe": 0.3, "total_pnl": 0.0},
    }


def _write_history(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


class TestCli:
    def test_missing_history_returns_3(self, tmp_path: Path) -> None:
        result = _run_cli(
            ["--last", "5", "--history", str(tmp_path / "missing.jsonl")]
        )
        assert result.returncode == 3
        assert "not found" in result.stderr

    def test_invalid_last_returns_2(self, tmp_path: Path) -> None:
        history = tmp_path / "history.jsonl"
        _write_history(history, [_record_dict()])
        result = _run_cli(
            ["--last", "0", "--history", str(history)]
        )
        assert result.returncode == 2

    def test_no_alert_returns_0(self, tmp_path: Path) -> None:
        history = tmp_path / "history.jsonl"
        records = [
            _record_dict(run_id=f"run_{i}", decision="in_band")
            for i in range(3)
        ]
        _write_history(history, records)
        result = _run_cli(
            ["--last", "5", "--history", str(history)]
        )
        assert result.returncode == 0
        assert "Calibrate Gate Drift" in result.stdout
        assert "Alerts:" in result.stdout

    def test_monotone_tighten_returns_10(self, tmp_path: Path) -> None:
        history = tmp_path / "history.jsonl"
        records = [
            _record_dict(run_id=f"run_{i}", decision="tighten")
            for i in range(5)
        ]
        _write_history(history, records)
        result = _run_cli(
            ["--last", "5", "--history", str(history)]
        )
        assert result.returncode == 10  # drift detected
        assert "ALERT" in result.stdout

    def test_table_includes_run_ids(self, tmp_path: Path) -> None:
        history = tmp_path / "history.jsonl"
        records = [_record_dict(run_id=f"run_{i:03d}") for i in range(3)]
        _write_history(history, records)
        result = _run_cli(
            ["--last", "5", "--history", str(history)]
        )
        for r in records:
            assert r["run_id"] in result.stdout

    def test_empty_history_returns_0_with_message(
        self, tmp_path: Path
    ) -> None:
        history = tmp_path / "history.jsonl"
        history.parent.mkdir(parents=True, exist_ok=True)
        history.touch()  # 空ファイル
        result = _run_cli(
            ["--last", "5", "--history", str(history)]
        )
        assert result.returncode == 0
        assert "(history is empty)" in result.stdout
