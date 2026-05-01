"""T058 PR 6: Tier 2 軽量ガード — display 系 4 scripts への伝搬テスト.

詳細設計: devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md
§ 施策 11 (Tier 2 軽量ガード、 行 1443-1470)。

検証対象 (5 ケース、 詳細設計 行 1462-1467):
- run_report.md (generate_run_report.py) header に dataset_epoch_id を含む
- batch_summary.json (compare_batch_runs.py) が per-run dataset_epoch_id を保持
- comparison_report.md (compare_batch_runs.py) が dataset_epoch_id を参照
- analysis-claude.md (analyze_run.py) が dataset_epoch_id を参照
- extract_batch_metrics report.md (extract_batch_metrics.py) が dataset_epoch_id を含む

これらは fail-open guard で、 dataset_epoch_id が欠落していても処理は成功するが、
出力に epoch_id が embed されることを担保することで PR 1-5 で integrate された
upstream propagation が display layer まで到達することを検証する。
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
GENERATE_PATH = REPO_ROOT / "scripts" / "alpha_factory" / "generate_run_report.py"
ANALYZE_PATH = REPO_ROOT / "scripts" / "alpha_factory" / "analyze_run.py"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


EXTRACT = _load("_extract_batch_metrics_t2", EXTRACT_PATH)
COMPARE = _load("_compare_batch_runs_t2", COMPARE_PATH)
GENERATE = _load("_generate_run_report_t2", GENERATE_PATH)
ANALYZE = _load("_analyze_run_t2", ANALYZE_PATH)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _write_summary_with_epoch_id(
    run_dir: Path,
    *,
    run_id: str,
    run_number: int,
    dataset_epoch_id: str,
    archive_path: str | None = None,
) -> None:
    """summary.json に dataset_epoch_id 付きで書き出す."""
    run_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "run_id": run_id,
        "run_number": run_number,
        "dataset_epoch_id": dataset_epoch_id,
        "cascade_contract_version": 2,
        "generated_at": "2026-04-25T00:00:00+00:00",
        "dataset": {
            "instrument": "EUR_USD",
            "start": "2026-03-01",
            "end": "2026-03-15",
            "bars": 14000,
        },
        "ga_config": {
            "population_size": 96,
            "generations": 60,
            "mutation_rate": 0.3,
            "crossover_rate": 0.7,
            "fitness_metric": "sharpe",
            "seed": 42,
        },
        "best": {
            "name": "g60_i00",
            "generation": 60,
            "fitness": "1.5",
            "fitness_finite": True,
            "stage_a_pass": True,
            "stage_b_pass": True,
            "stage_c_pass": True,
            "metrics": {
                "total_pnl": "1234.5",
                "sharpe": "2.0",
                "max_drawdown_pct": "0.1",
                "trade_count": 100,
                "win_rate": "0.55",
            },
        },
        "live_criteria": {
            "checks": {
                "sharpe": {"value": "2.0", "threshold": "1.0", "pass": True},
                "trade_count": {
                    "value": 100,
                    "threshold_min": 50,
                    "threshold_max": 5000,
                    "pass": True,
                },
            },
            "all_pass": True,
        },
        "graduation_count": 1,
        "archive_parquet": archive_path,
    }
    (run_dir / "summary.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_history(run_dir: Path) -> None:
    """history.json (analyze_run / generate_run_report 用)."""
    history = [
        {"generation": 1, "best_fitness": "1.0"},
        {"generation": 2, "best_fitness": "1.2"},
        {"generation": 3, "best_fitness": "1.5"},
    ]
    (run_dir / "history.json").write_text(json.dumps(history), encoding="utf-8")


def _write_minimal_archive(path: Path) -> None:
    """generate_run_report が optional に読む archive Parquet."""
    rows = [
        {
            "individual_name": "g60_i00",
            "generation": 60,
            "instrument": "EUR_USD",
            "lane_id": "L1",
            "stage_a_pass": True,
            "stage_b_pass": True,
            "stage_c_pass": True,
            "fitness_pen": 1.5,
            "fitness_raw": 1.5,
            "sharpe": 2.0,
            "trade_count": 100,
        }
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)


# ---------------------------------------------------------------------------
# Test 1: run_report.md (generate_run_report.py) が header に dataset_epoch_id を含む
# ---------------------------------------------------------------------------


def test_run_report_md_includes_dataset_epoch_id_in_header(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """generate_run_report.py が summary.dataset_epoch_id を run-{N}.md の
    header に書き出すこと (Tier 2 propagation の到達点)."""
    run_reports = tmp_path / "reports" / "run-reports"
    run_dir = run_reports / "run-7"
    archive = tmp_path / "archive" / "g.parquet"
    _write_summary_with_epoch_id(
        run_dir,
        run_id="run_TEST",
        run_number=7,
        dataset_epoch_id="epoch_2026_q1",
        archive_path=str(archive),
    )
    _write_history(run_dir)
    _write_minimal_archive(archive)

    monkeypatch.setattr(GENERATE, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(GENERATE, "RUN_REPORTS_DIR", run_reports)

    rc = GENERATE.main(["--run-number", "7"])
    assert rc == 0
    out = (run_reports / "run-7.md").read_text(encoding="utf-8")
    assert "dataset_epoch_id" in out
    assert "epoch_2026_q1" in out


# ---------------------------------------------------------------------------
# Test 2: extract_batch_metrics.py が JSON output に per-run dataset_epoch_id を保持
# ---------------------------------------------------------------------------


def test_batch_summary_json_preserves_per_run_dataset_epoch_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """extract_batch_metrics の JSON output が summary.dataset_epoch_id を
    そのまま保持し、 後段 compare_batch_runs に渡せるようになっていること."""
    run_reports = tmp_path / "reports" / "run-reports"
    run_dir = run_reports / "run-1"
    _write_summary_with_epoch_id(
        run_dir,
        run_id="run_TEST",
        run_number=1,
        dataset_epoch_id="epoch_legacy",
    )

    monkeypatch.setattr(EXTRACT, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(EXTRACT, "RUN_REPORTS_DIR", run_reports)

    metrics = EXTRACT.extract("run_TEST", None)
    assert metrics["dataset_epoch_id"] == "epoch_legacy"

    # CLI 経由でも JSON に書き出されること
    out_json = tmp_path / "out" / "metrics.json"
    rc = EXTRACT.main(["run_TEST", "--output", str(out_json)])
    assert rc == 0
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["dataset_epoch_id"] == "epoch_legacy"


# ---------------------------------------------------------------------------
# Test 3: comparison_report.md (compare_batch_runs.py) が dataset_epoch_id を参照
# ---------------------------------------------------------------------------


def test_comparison_report_md_references_dataset_epoch_id(tmp_path: Path) -> None:
    """compare_batch_runs.py が per-run dataset_epoch_id を batch_summary.json
    と comparison_report.md の両方に表示すること."""
    batch_dir = tmp_path / "batch_001"
    metrics_dir = batch_dir / "metrics"
    metrics_dir.mkdir(parents=True)

    payload_template: dict[str, Any] = {
        "run_id": "r1",
        "run_number": 1,
        "dataset_epoch_id": "epoch_2026_q1",
        "best": {
            "name": "best_r1",
            "generation": 60,
            "fitness": 1.5,
            "sharpe": 2.0,
            "trade_count": 100,
            "total_pnl": 1000.0,
            "max_drawdown_pct": 0.1,
            "win_rate": 0.5,
            "profit_factor": 1.2,
            "stage_a_pass": True,
            "stage_b_pass": True,
            "stage_c_pass": False,
        },
        "stage_pass": {
            "stage_a_pass": 10,
            "stage_b_pass": 2,
            "stage_c_pass": 0,
            "total": 12,
        },
        "best_b_sharpe": 2.0,
        "best_c_sharpe": None,
        "live_criteria_all_pass": False,
        "live_criteria_failed": [],
        "graduation_count": 0,
    }
    (metrics_dir / "r1.json").write_text(json.dumps(payload_template), encoding="utf-8")

    rc = COMPARE.main(["--batch-dir", str(batch_dir)])
    assert rc == 0

    # batch_summary.json
    summary = json.loads(
        (batch_dir / "batch_summary.json").read_text(encoding="utf-8")
    )
    assert summary["dataset_epoch_ids"] == ["epoch_2026_q1"]

    # comparison_report.md
    md = (batch_dir / "comparison_report.md").read_text(encoding="utf-8")
    assert "dataset_epoch_id" in md
    assert "epoch_2026_q1" in md


# ---------------------------------------------------------------------------
# Test 4: analyze_run.py の analysis-claude.md が dataset_epoch_id を参照
# ---------------------------------------------------------------------------


def test_analyze_run_md_references_dataset_epoch_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """analyze_run.py が summary.dataset_epoch_id を analysis-claude.md に書き出すこと."""
    run_reports = tmp_path / "reports" / "run-reports"
    run_dir = run_reports / "run-3"
    _write_summary_with_epoch_id(
        run_dir,
        run_id="run_TEST",
        run_number=3,
        dataset_epoch_id="epoch_2026_q2",
    )
    _write_history(run_dir)

    monkeypatch.setattr(ANALYZE, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ANALYZE, "RUN_REPORTS_DIR", run_reports)

    tmp_dir = tmp_path / "tmp_analyze"
    rc = ANALYZE.main(["--run-number", "3", "--tmp-dir", str(tmp_dir)])
    assert rc == 0
    out = (tmp_dir / "analysis-claude.md").read_text(encoding="utf-8")
    assert "dataset_epoch_id" in out
    assert "epoch_2026_q2" in out


# ---------------------------------------------------------------------------
# Test 5: extract_batch_metrics.py の report.md が dataset_epoch_id を含む
# ---------------------------------------------------------------------------


def test_extract_batch_metrics_report_md_includes_dataset_epoch_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """extract_batch_metrics の軽量 Markdown report に dataset_epoch_id を含むこと."""
    run_reports = tmp_path / "reports" / "run-reports"
    run_dir = run_reports / "run-2"
    _write_summary_with_epoch_id(
        run_dir,
        run_id="run_TEST",
        run_number=2,
        dataset_epoch_id="epoch_2026_q3",
    )

    monkeypatch.setattr(EXTRACT, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(EXTRACT, "RUN_REPORTS_DIR", run_reports)

    out_json = tmp_path / "out" / "metrics.json"
    out_md = tmp_path / "out" / "metrics.md"
    rc = EXTRACT.main([
        "run_TEST",
        "--output", str(out_json),
        "--report", str(out_md),
    ])
    assert rc == 0
    md = out_md.read_text(encoding="utf-8")
    assert "dataset_epoch_id" in md
    assert "epoch_2026_q3" in md


# ---------------------------------------------------------------------------
# Tier 2 軽量ガードの fail-open 性 (dataset_epoch_id 欠落でも処理は成功)
# ---------------------------------------------------------------------------


def test_tier2_guard_does_not_fail_when_dataset_epoch_id_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """summary.json から dataset_epoch_id が欠落していても、 display 系 4 scripts
    は warning を出すだけで exit 1 を返さない (詳細設計 行 1469-1470 fail-open)."""
    run_reports = tmp_path / "reports" / "run-reports"
    run_dir = run_reports / "run-9"
    archive = tmp_path / "archive" / "g.parquet"
    _write_summary_with_epoch_id(
        run_dir,
        run_id="run_TEST",
        run_number=9,
        dataset_epoch_id="epoch_dummy",
        archive_path=str(archive),
    )
    _write_history(run_dir)
    _write_minimal_archive(archive)

    # dataset_epoch_id を summary から除去
    summary_path = run_dir / "summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    payload.pop("dataset_epoch_id", None)
    summary_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(GENERATE, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(GENERATE, "RUN_REPORTS_DIR", run_reports)
    monkeypatch.setattr(ANALYZE, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ANALYZE, "RUN_REPORTS_DIR", run_reports)
    monkeypatch.setattr(EXTRACT, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(EXTRACT, "RUN_REPORTS_DIR", run_reports)

    # 全 script が rc == 0 を返すこと
    rc = GENERATE.main(["--run-number", "9"])
    assert rc == 0

    tmp_dir = tmp_path / "tmp_analyze"
    rc = ANALYZE.main(["--run-number", "9", "--tmp-dir", str(tmp_dir)])
    assert rc == 0

    out_json = tmp_path / "out" / "metrics.json"
    rc = EXTRACT.main(["run_TEST", "--output", str(out_json)])
    assert rc == 0
