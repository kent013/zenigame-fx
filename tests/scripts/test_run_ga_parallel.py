"""GA 並列実行の決定論性 (L1 selection / L2 row-order) 同値性テスト (T052).

設計根拠:
- devnotes/20260427-1114-ga-parallel-workers/conceptual-design.md §4.0
- devnotes/20260427-1114-ga-parallel-workers/detailed-design.md §6 施策6

検証契約:
- L1 selection determinism: best_name / fitness_pen / live_criteria_passed が
  worker 数に依存しない
- L2 row-order determinism: archive Parquet 数値 column を
  (lane_id, generation, genome_name) ソート下で一致
- L3 artifact bit equivalence は **保証外** (timestamp / wall_time_seconds 等)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import scripts.alpha_factory.run_ga as run_ga_module
from tests.scripts.test_alpha_factory_run_ga import (
    CONFIG_PATH,
    _generate_bar_rows,
    _install_mock_session,
    _make_currency_pair,
)

# L2 contract: archive Parquet で完全一致を要求する数値 column
# (実 column 名は GENOMES_SCHEMA に従う; 存在チェックして比較)
NUMERIC_L2_COLUMNS = [
    "fitness_pen_stage_a",
    "fitness_raw_stage_a",
    "trade_count_stage_a",
    "stage_a_pass",
    "stage_b_pass",
    "stage_c_pass",
    "trade_sharpe_raw_stage_a",
    "total_pnl_stage_a",
    "median_oos_sharpe_stage_b",
    "stage_a_genome_size",
]


def _setup_smoke_run_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    sub_dir: str,
) -> Path:
    """smoke run の DB mock + 出力 path setup を行い、出力 root を返す."""
    from src.alpha_factory.archive import GenomeArchive as _Archive

    pair = _make_currency_pair("EUR_JPY")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 8, tzinfo=UTC)
    stage_b_rows = _generate_bar_rows(pair, start, end, step_minutes=60)
    holdout_rows = _generate_bar_rows(
        pair, end, end + timedelta(days=1), step_minutes=60,
    )
    _install_mock_session(
        monkeypatch, pair, stage_b_rows, holdout_rows,
        datetime(2026, 1, 8, tzinfo=UTC),
    )
    out_root = tmp_path / sub_dir
    monkeypatch.setattr(run_ga_module, "RUN_REPORTS_DIR", out_root / "reports")
    monkeypatch.setattr(run_ga_module, "RUN_CACHE_DIR", out_root / "cache")
    monkeypatch.setattr(run_ga_module, "get_latest_run_number", lambda: 0)
    monkeypatch.setattr(_Archive, "DEFAULT_OUTPUT_DIR", out_root / "archive")
    return out_root


def _run_with_workers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    sub_dir: str,
    max_workers: int,
    seed: int = 42,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """1 RUN を実行し summary + archive DataFrame を返す."""
    out_root = _setup_smoke_run_env(monkeypatch, tmp_path, sub_dir=sub_dir)
    rc = run_ga_module.main(
        [
            "--config", str(CONFIG_PATH),
            "--run-id", f"run_parallel_test_{max_workers}",
            "--population-size", "4",
            "--generations", "1",
            "--seed", str(seed),
            "--max-workers", str(max_workers),
        ]
    )
    assert rc == 0
    summary = json.loads(
        (out_root / "reports" / "run-1" / "summary.json").read_text(encoding="utf-8")
    )
    # archive parquet path は summary に書かれている
    archive_path = Path(summary["archive_parquet"])
    df = pd.read_parquet(archive_path)
    return summary, df


def test_parallel_evaluation_preserves_l1_selection_determinism(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """L1: max_workers=1 と max_workers=2 で best.name / fitness / live_criteria_passed 一致."""
    seq_summary, _ = _run_with_workers(
        monkeypatch, tmp_path, sub_dir="seq", max_workers=1
    )
    par_summary, _ = _run_with_workers(
        monkeypatch, tmp_path, sub_dir="par", max_workers=2
    )
    # L1: best name / fitness の数値表現 / live_criteria 判定
    assert seq_summary["best"]["name"] == par_summary["best"]["name"]
    assert seq_summary["best"]["fitness"] == par_summary["best"]["fitness"]
    assert seq_summary["best"]["fitness_finite"] == par_summary["best"]["fitness_finite"]
    assert seq_summary["best"]["selection_score"] == par_summary["best"]["selection_score"]
    # live_criteria 判定: schema は {"checks": {...}, "all_pass": bool}
    # 各 check の値 (value / threshold / pass) と all_pass が一致することを保証
    seq_lc = seq_summary["live_criteria"]
    par_lc = par_summary["live_criteria"]
    assert seq_lc["all_pass"] == par_lc["all_pass"], "live_criteria.all_pass mismatch"
    seq_checks = seq_lc.get("checks", {})
    par_checks = par_lc.get("checks", {})
    expected_keys = ("sharpe", "total_pnl", "max_drawdown_pct", "trade_count")
    found_keys = [k for k in expected_keys if k in seq_checks]
    assert found_keys, (
        f"live_criteria.checks has no expected keys. "
        f"seq keys: {list(seq_checks.keys())}"
    )
    for key in found_keys:
        assert seq_checks[key] == par_checks[key], (
            f"live_criteria.checks.{key} mismatch: "
            f"seq={seq_checks[key]} par={par_checks[key]}"
        )


def test_parallel_evaluation_preserves_l2_row_order_determinism(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """L2: archive Parquet の数値 column が (lane_id, generation, genome_name) ソート下で一致."""
    _, seq_df = _run_with_workers(
        monkeypatch, tmp_path, sub_dir="seq", max_workers=1
    )
    _, par_df = _run_with_workers(
        monkeypatch, tmp_path, sub_dir="par", max_workers=2
    )
    sort_keys = ["lane_id", "generation", "individual_name"]
    seq_sorted = seq_df.sort_values(sort_keys).reset_index(drop=True)
    par_sorted = par_df.sort_values(sort_keys).reset_index(drop=True)
    # 行数一致
    assert len(seq_sorted) == len(par_sorted)
    # キー列一致
    for k in sort_keys:
        pd.testing.assert_series_equal(
            seq_sorted[k], par_sorted[k], check_names=False
        )
    # L2 数値 column を限定して比較 (列存在確認後)
    available_cols = [c for c in NUMERIC_L2_COLUMNS if c in seq_df.columns]
    assert available_cols, "no L2 columns found in archive Parquet"
    for col in available_cols:
        # NaN 安全な比較 (両方 NaN も equal とみなす)
        assert seq_sorted[col].equals(par_sorted[col]), (
            f"column '{col}' mismatch between sequential and parallel run"
        )


def test_summary_contains_parallel_config_and_schema_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """T052: summary.json に schema_version / parallel_config / max_rss_mb_per_worker が含まれる."""
    summary, _ = _run_with_workers(
        monkeypatch, tmp_path, sub_dir="schema", max_workers=2
    )
    assert summary.get("schema_version") == "1.1"
    assert "parallel_config" in summary
    assert summary["parallel_config"]["max_workers"] == 2
    assert summary["parallel_config"]["mode"] == "parallel"
    assert "max_rss_mb_per_worker" in summary
    # per_generation[*] に stage 別 timing
    assert summary["per_generation"], "per_generation should be non-empty"
    pg0 = summary["per_generation"][0]
    for key in (
        "stage_a_seconds_total", "stage_a_seconds_max",
        "stage_b_seconds_total", "stage_b_seconds_max",
        "stage_c_seconds_total", "stage_c_seconds_max",
    ):
        assert key in pg0, f"per_generation[0] missing {key}"


def test_existing_summary_contract_preserved_under_parallel_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """T052 後方互換: 既存 summary key (run_id / dataset / best 等) が保持される."""
    summary, _ = _run_with_workers(
        monkeypatch, tmp_path, sub_dir="compat", max_workers=2
    )
    for key in (
        "run_id", "run_number", "generated_at", "dataset",
        "ga_config", "backtest_config", "best", "live_criteria",
        "population_size", "graduation_count", "archive_parquet",
        "per_generation",
    ):
        assert key in summary, f"existing summary key '{key}' missing"


# ---------------------------------------------------------------------------
# T058 PR 5: RunContext / dataset_epoch_id propagation
# ---------------------------------------------------------------------------


def _run_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, sub_dir: str
) -> tuple[Path, dict[str, Any]]:
    """1 RUN を実行して (run_dir, summary) を返す T058 用 helper."""
    out_root = _setup_smoke_run_env(monkeypatch, tmp_path, sub_dir=sub_dir)
    rc = run_ga_module.main(
        [
            "--config", str(CONFIG_PATH),
            "--run-id", "run_t058_pr5_artifact",
            "--population-size", "4",
            "--generations", "1",
            "--seed", "42",
            "--max-workers", "1",
        ]
    )
    assert rc == 0
    run_dir = out_root / "reports" / "run-1"
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    return run_dir, summary


_EXPECTED_EPOCH_ID = "epoch_20260101_20260108"
"""T059: smoke run fixture (``alpha_factory_min_config.yaml``) の dataset
(start=2026-01-01, end=2026-01-08) から ``make_epoch_id`` で生成される
deterministic 値。 T058 段階の ``"epoch_legacy"`` から切替。"""


def test_summary_json_includes_cascade_contract_version_and_dataset_epoch_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """T059: summary.json に cascade_contract_version + deterministic dataset_epoch_id が入る."""
    _run_dir, summary = _run_artifacts(
        monkeypatch, tmp_path, sub_dir="t058_summary"
    )
    assert summary["cascade_contract_version"] == 2
    assert summary["dataset_epoch_id"] == _EXPECTED_EPOCH_ID


def test_summary_json_schema_version_remains_string_one_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """T058 PR 5: schema_version は **string "1.1"** のまま (test 互換性維持)."""
    _run_dir, summary = _run_artifacts(
        monkeypatch, tmp_path, sub_dir="t058_schema_string"
    )
    sv = summary["schema_version"]
    assert isinstance(sv, str)
    assert sv == "1.1"


def test_cascade_contract_version_is_int_in_summary_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """T058 PR 5 (型固定): cascade_contract_version は **int**, schema_version は str."""
    _run_dir, summary = _run_artifacts(
        monkeypatch, tmp_path, sub_dir="t058_int_type"
    )
    ccv = summary["cascade_contract_version"]
    assert isinstance(ccv, int)
    assert not isinstance(ccv, bool)  # bool は int subclass なので除外
    assert ccv == 2


def test_history_json_each_entry_includes_dataset_epoch_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """T059: history.json の各 entry に deterministic dataset_epoch_id 付与."""
    run_dir, _ = _run_artifacts(monkeypatch, tmp_path, sub_dir="t058_history")
    history = json.loads((run_dir / "history.json").read_text(encoding="utf-8"))
    assert isinstance(history, list)
    assert history, "history.json should be non-empty"
    for entry in history:
        assert entry["dataset_epoch_id"] == _EXPECTED_EPOCH_ID


def test_best_genome_json_includes_dataset_epoch_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """T059: best_genome.json に deterministic dataset_epoch_id field 付与."""
    run_dir, _ = _run_artifacts(monkeypatch, tmp_path, sub_dir="t058_best")
    bg = json.loads((run_dir / "best_genome.json").read_text(encoding="utf-8"))
    assert bg["dataset_epoch_id"] == _EXPECTED_EPOCH_ID
    # 既存 genome_to_dict 構造 (name 等) も維持
    assert "name" in bg


def test_population_jsonl_each_line_includes_dataset_epoch_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """T059: population.jsonl の各 line に deterministic dataset_epoch_id 付与."""
    run_dir, _ = _run_artifacts(monkeypatch, tmp_path, sub_dir="t058_pop")
    lines = (run_dir / "population.jsonl").read_text(encoding="utf-8").splitlines()
    assert lines, "population.jsonl should be non-empty"
    for raw in lines:
        d = json.loads(raw)
        assert d["dataset_epoch_id"] == _EXPECTED_EPOCH_ID
        assert "name" in d
        assert "fitness" in d


def test_run_cache_json_includes_dataset_epoch_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """T059: .cache/alpha_factory/runs/{run_id}.json に deterministic dataset_epoch_id 付与."""
    out_root = _setup_smoke_run_env(monkeypatch, tmp_path, sub_dir="t058_cache")
    rc = run_ga_module.main(
        [
            "--config", str(CONFIG_PATH),
            "--run-id", "run_t058_pr5_cache_check",
            "--population-size", "4",
            "--generations", "1",
            "--seed", "42",
            "--max-workers", "1",
        ]
    )
    assert rc == 0
    cache_path = out_root / "cache" / "run_t058_pr5_cache_check.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cache["run_id"] == "run_t058_pr5_cache_check"
    assert cache["dataset_epoch_id"] == _EXPECTED_EPOCH_ID
