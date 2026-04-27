"""Unit tests for batch GA helper scripts.

- scripts/alpha_factory/extract_batch_metrics.py
- scripts/alpha_factory/compare_batch_runs.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXTRACT_PATH = REPO_ROOT / "scripts" / "alpha_factory" / "extract_batch_metrics.py"
COMPARE_PATH = REPO_ROOT / "scripts" / "alpha_factory" / "compare_batch_runs.py"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


EXTRACT = _load("_extract_batch_metrics", EXTRACT_PATH)
COMPARE = _load("_compare_batch_runs", COMPARE_PATH)


# ---------------------------------------------------------------------------
# fixtures: 擬似 run-{N} ディレクトリ
# ---------------------------------------------------------------------------


def _write_summary(run_dir: Path, run_id: str, run_number: int, *, archive_path: str | None) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "run_number": run_number,
        "generated_at": "2026-04-25T00:00:00+00:00",
        "dataset": {"instrument": "EUR_JPY", "start": "2026-03-01", "end": "2026-03-15", "bars": 14000},
        "ga_config": {
            "population_size": 96, "generations": 60,
            "mutation_rate": 0.3, "crossover_rate": 0.7,
            "fitness_metric": "sharpe", "seed": None,
        },
        "best": {
            "name": "g60_i00", "generation": 60,
            "fitness": "1.5", "fitness_finite": True,
            "stage_a_pass": True, "stage_b_pass": False, "stage_c_pass": False,
            "metrics": {
                "total_pnl": "1234.5", "sharpe": "2.0",
                "max_drawdown_pct": "0.1", "trade_count": 100,
            },
        },
        "live_criteria": {
            "checks": {
                "sharpe": {"value": "2.0", "threshold": "1.0", "pass": True},
                "trade_count": {"value": 100, "threshold_min": 50, "threshold_max": 5000, "pass": True},
            },
            "all_pass": True,
        },
        "graduation_count": 2,
        "archive_parquet": archive_path,
    }
    (run_dir / "summary.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_archive(path: Path, *, n_a: int, n_b: int, n_c: int, b_sharpes: list[float]) -> None:
    rows: list[dict[str, Any]] = []
    for i in range(n_a):
        rows.append({
            "individual_name": f"a_{i}", "generation": 1, "instrument": "EUR_JPY", "lane_id": "L1",
            "stage_a_pass": True, "stage_b_pass": False, "stage_c_pass": False,
            "sharpe": 0.5, "trade_count": 30,
        })
    for i, sh in enumerate(b_sharpes[:n_b]):
        rows.append({
            "individual_name": f"b_{i}", "generation": 2, "instrument": "EUR_JPY", "lane_id": "L1",
            "stage_a_pass": True, "stage_b_pass": True, "stage_c_pass": False,
            "sharpe": sh, "trade_count": 100,
        })
    for i in range(n_c):
        rows.append({
            "individual_name": f"c_{i}", "generation": 3, "instrument": "EUR_JPY", "lane_id": "L1",
            "stage_a_pass": True, "stage_b_pass": True, "stage_c_pass": True,
            "sharpe": 3.0, "trade_count": 200,
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)


@pytest.fixture()
def run_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    run_reports = tmp_path / "reports" / "run-reports"
    archive_dir = tmp_path / "archive"

    run_dir = run_reports / "run-1"
    archive_path = archive_dir / "g_run_TEST.parquet"
    _write_summary(run_dir, "run_TEST", 1, archive_path=str(archive_path))
    _write_archive(archive_path, n_a=10, n_b=3, n_c=1, b_sharpes=[1.1, 2.2, 1.5])

    monkeypatch.setattr(EXTRACT, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(EXTRACT, "RUN_REPORTS_DIR", run_reports)
    return tmp_path


# ---------------------------------------------------------------------------
# extract_batch_metrics
# ---------------------------------------------------------------------------


def test_extract_by_run_id(run_env: Path) -> None:
    m = EXTRACT.extract("run_TEST", None)
    assert m["run_id"] == "run_TEST"
    assert m["run_number"] == 1
    assert m["best"]["sharpe"] == pytest.approx(2.0)
    assert m["best"]["fitness"] == pytest.approx(1.5)
    assert m["stage_pass"] == {"stage_a_pass": 14, "stage_b_pass": 4, "stage_c_pass": 1, "total": 14}
    # B-PASS の sharpe の最大値 (b_sharpes 最大 + C-PASS sharpe 3.0 のうち大きい方)
    assert m["best_b_sharpe"] == pytest.approx(3.0)
    assert m["best_c_sharpe"] == pytest.approx(3.0)
    assert m["live_criteria_all_pass"] is True
    assert m["live_criteria_failed"] == []
    assert m["archive_loaded"] is True


def test_extract_by_run_number(run_env: Path) -> None:
    m = EXTRACT.extract(None, 1)
    assert m["run_id"] == "run_TEST"
    assert m["run_number"] == 1


def test_extract_unknown_run_id(run_env: Path) -> None:
    with pytest.raises(FileNotFoundError):
        EXTRACT.extract("run_DOES_NOT_EXIST", None)


def test_extract_missing_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_reports = tmp_path / "reports" / "run-reports"
    run_dir = run_reports / "run-2"
    _write_summary(run_dir, "run_NOAR", 2, archive_path=str(tmp_path / "missing.parquet"))
    monkeypatch.setattr(EXTRACT, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(EXTRACT, "RUN_REPORTS_DIR", run_reports)

    m = EXTRACT.extract("run_NOAR", None)
    assert m["archive_loaded"] is False
    assert m["stage_pass"]["total"] is None
    assert m["best_b_sharpe"] is None


def test_extract_cli_writes_files(run_env: Path, tmp_path: Path) -> None:
    out_json = tmp_path / "out" / "metrics.json"
    out_md = tmp_path / "out" / "metrics.md"
    rc = EXTRACT.main([
        "run_TEST", "--output", str(out_json), "--report", str(out_md),
    ])
    assert rc == 0
    assert out_json.exists()
    assert out_md.exists()
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["run_id"] == "run_TEST"
    assert "Best 個体" in out_md.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# compare_batch_runs
# ---------------------------------------------------------------------------


def _write_metrics(metrics_dir: Path, name: str, payload: dict[str, Any]) -> None:
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


def _metric_payload(
    run_id: str, run_number: int, *,
    best_fitness: float, best_sharpe: float | None,
    a: int, b: int, c: int, all_pass: bool,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_number": run_number,
        "best": {
            "name": f"best_{run_id}", "generation": 60,
            "fitness": best_fitness, "sharpe": best_sharpe,
            "trade_count": 50, "total_pnl": 1000.0,
            "max_drawdown_pct": 0.1, "win_rate": None, "profit_factor": None,
            "stage_a_pass": True, "stage_b_pass": b > 0, "stage_c_pass": c > 0,
        },
        "stage_pass": {"stage_a_pass": a, "stage_b_pass": b, "stage_c_pass": c, "total": a + b + c},
        "best_b_sharpe": best_sharpe if b > 0 else None,
        "best_c_sharpe": best_sharpe if c > 0 else None,
        "live_criteria_all_pass": all_pass,
        "live_criteria_failed": [],
        "graduation_count": 0,
    }


def test_compare_single_batch(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch_001"
    metrics_dir = batch_dir / "metrics"
    _write_metrics(metrics_dir, "r1", _metric_payload("r1", 1, best_fitness=1.0, best_sharpe=1.5, a=10, b=2, c=0, all_pass=False))
    _write_metrics(metrics_dir, "r2", _metric_payload("r2", 2, best_fitness=2.0, best_sharpe=2.5, a=20, b=4, c=1, all_pass=True))
    _write_metrics(metrics_dir, "r3", _metric_payload("r3", 3, best_fitness=3.0, best_sharpe=None, a=30, b=0, c=0, all_pass=False))
    (batch_dir / "batch_state.json").write_text(json.dumps({"label": "smoke"}), encoding="utf-8")

    rc = COMPARE.main(["--batch-dir", str(batch_dir)])
    assert rc == 0
    summary = json.loads((batch_dir / "batch_summary.json").read_text(encoding="utf-8"))
    assert summary["batch_id"] == "batch_001"
    assert summary["label"] == "smoke"
    assert summary["n_runs"] == 3
    assert summary["metrics"]["best_fitness"]["mean"] == pytest.approx(2.0)
    # best_sharpe は r3 が None なので n=2
    assert summary["metrics"]["best_sharpe"]["n"] == 2
    assert summary["metrics"]["best_sharpe"]["mean"] == pytest.approx(2.0)
    assert summary["live_criteria_all_pass"]["n_pass"] == 1
    assert summary["live_criteria_all_pass"]["n_known"] == 3
    assert summary["live_criteria_all_pass"]["rate"] == pytest.approx(1 / 3)
    md = (batch_dir / "comparison_report.md").read_text(encoding="utf-8")
    assert "batch_001" in md
    assert "best_fitness" in md


def test_compare_baseline_treatment(tmp_path: Path) -> None:
    bl = tmp_path / "bl"
    tr = tmp_path / "tr"
    _write_metrics(bl / "metrics", "r1", _metric_payload("r1", 1, best_fitness=1.0, best_sharpe=1.0, a=10, b=0, c=0, all_pass=False))
    _write_metrics(bl / "metrics", "r2", _metric_payload("r2", 2, best_fitness=2.0, best_sharpe=2.0, a=20, b=0, c=0, all_pass=False))
    _write_metrics(tr / "metrics", "r1", _metric_payload("r1", 1, best_fitness=3.0, best_sharpe=3.0, a=30, b=2, c=0, all_pass=True))
    _write_metrics(tr / "metrics", "r2", _metric_payload("r2", 2, best_fitness=4.0, best_sharpe=4.0, a=40, b=4, c=1, all_pass=True))

    out = tmp_path / "compare.md"
    rc = COMPARE.main([
        "--baseline", str(bl), "--treatment", str(tr), "--output", str(out),
    ])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "baseline:" in text
    assert "treatment:" in text
    # baseline mean=1.5, treatment mean=3.5, Δ=2.0
    assert "1.5000" in text
    assert "3.5000" in text


def test_compare_empty_batch_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    batch_dir = tmp_path / "empty"
    (batch_dir / "metrics").mkdir(parents=True)
    rc = COMPARE.main(["--batch-dir", str(batch_dir)])
    assert rc == 1
    assert "no metrics" in capsys.readouterr().err


def test_compare_arg_validation(capsys: pytest.CaptureFixture[str]) -> None:
    rc = COMPARE.main([])
    assert rc == 2
    rc = COMPARE.main(["--batch-dir", "/tmp/x", "--baseline", "/tmp/y"])
    assert rc == 2
