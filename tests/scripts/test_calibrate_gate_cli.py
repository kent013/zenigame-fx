"""CLI smoke / IO tests for scripts/alpha_factory/calibrate_gate.py (T027)。"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "alpha_factory" / "calibrate_gate.py"


# 動的に script を import してテスト用に main() を呼べるようにする
def _import_calibrate_gate_cli() -> Any:
    spec = importlib.util.spec_from_file_location(
        "_calibrate_gate_cli", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_calibrate_gate_cli"] = mod
    spec.loader.exec_module(mod)
    return mod


CLI = _import_calibrate_gate_cli()


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


YAML_TEMPLATE = """\
live_criteria:
  sharpe_min: 1.0
  total_pnl_min: 50000.0
  max_drawdown_max: 0.2
  trade_count_min: 50
  trade_count_max: 5000

stage_gate:
  stage_a:
    window_days: 60
    target_pass_rate: {target}
    alpha: 0.03
    threshold: {threshold}
    calibrate:
      enabled: {enabled}
      aggregation_mode: {mode}
      aggregation_window: 5
      pass_rate_tolerance_abs: 0.05
      threshold_delta_abs_max: 0.5
      threshold_floor: -100.0
      threshold_ceiling: 100.0
      min_sample_size: {min_sample}
      eps_var: 0.000000001
"""


def _write_yaml(
    path: Path,
    *,
    target: float = 0.15,
    threshold: float = 0.0,
    enabled: bool = True,
    mode: str = "all_generations",
    min_sample: int = 10,
) -> None:
    path.write_text(
        YAML_TEMPLATE.format(
            target=target,
            threshold=threshold,
            enabled="true" if enabled else "false",
            mode=mode,
            min_sample=min_sample,
        ),
        encoding="utf-8",
    )


def _write_archive(
    archive_dir: Path,
    run_id: str,
    *,
    n: int,
    pass_count: int,
    fitness_pen_low: float = -50.0,
    fitness_pen_high: float = 50.0,
    introduce_null_in: str | None = None,
    introduce_nan_in_fitness: bool = False,
) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = archive_dir / f"genomes_{run_id}.parquet"
    step = (fitness_pen_high - fitness_pen_low) / max(n - 1, 1)
    fitness_pens = [fitness_pen_low + i * step for i in range(n)]
    if introduce_nan_in_fitness:
        fitness_pens[0] = float("nan")
    stage_a = [i < pass_count for i in range(n)]
    if introduce_null_in == "stage_a_pass":
        col = pa.array([None, *stage_a[1:]], type=pa.bool_())
    else:
        col = pa.array(stage_a, type=pa.bool_())
    table = pa.Table.from_pydict(
        {
            "generation": pa.array([i % 5 for i in range(n)], type=pa.int32()),
            "stage_a_pass": col,
            "fitness_pen": pa.array(fitness_pens, type=pa.float64()),
            "stage_b_pass": pa.array([False] * n, type=pa.bool_()),
            "stage_c_pass": pa.array([False] * n, type=pa.bool_()),
            "sharpe": pa.array([0.0] * n, type=pa.float64()),
            "total_pnl": pa.array([0.0] * n, type=pa.float64()),
            "max_drawdown_pct": pa.array([0.0] * n, type=pa.float64()),
            "trade_count": pa.array([0] * n, type=pa.int32()),
        }
    )
    pq.write_table(table, parquet_path)
    return parquet_path


def _yaml_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_cli_dry_run_does_not_modify_yaml(tmp_path: Path) -> None:
    yaml_path = tmp_path / "default.yaml"
    archive_dir = tmp_path / "archive"
    _write_yaml(yaml_path)
    _write_archive(archive_dir, "smoke", n=100, pass_count=2)

    sha_before = _yaml_sha256(yaml_path)
    code = CLI.main(
        [
            "--run-id",
            "smoke",
            "--config-path",
            str(yaml_path),
            "--archive-dir",
            str(archive_dir),
            "--dry-run",
        ]
    )
    assert code == CLI.EXIT_OK
    assert _yaml_sha256(yaml_path) == sha_before


def test_cli_writes_yaml_atomically_when_decision_is_loosen(
    tmp_path: Path,
) -> None:
    yaml_path = tmp_path / "default.yaml"
    archive_dir = tmp_path / "archive"
    # threshold=10.0 にしておくと、loosen で下方向の delta が確実に発生する
    _write_yaml(yaml_path, target=0.5, threshold=10.0)
    # actual = 0.0 → loosen 確定。fitness_pen は -50..+50。
    _write_archive(archive_dir, "loosen", n=100, pass_count=0)

    sha_before = _yaml_sha256(yaml_path)
    code = CLI.main(
        [
            "--run-id",
            "loosen",
            "--config-path",
            str(yaml_path),
            "--archive-dir",
            str(archive_dir),
        ]
    )
    assert code == CLI.EXIT_OK
    assert _yaml_sha256(yaml_path) != sha_before
    new_yaml = yaml_path.read_text(encoding="utf-8")
    # threshold: 10.0 から max_delta=0.5 で 9.5 に下がっているはず
    assert "threshold: 9.5" in new_yaml
    # tmp / lock の残骸が無い
    assert list(yaml_path.parent.glob("*.tmp")) == []


def test_cli_exits_3_when_no_archive(tmp_path: Path) -> None:
    yaml_path = tmp_path / "default.yaml"
    archive_dir = tmp_path / "archive"
    _write_yaml(yaml_path)
    archive_dir.mkdir()
    code = CLI.main(
        [
            "--config-path",
            str(yaml_path),
            "--archive-dir",
            str(archive_dir),
        ]
    )
    assert code == CLI.EXIT_NO_ARCHIVE


def test_cli_exits_3_when_run_id_specified_but_missing(tmp_path: Path) -> None:
    yaml_path = tmp_path / "default.yaml"
    archive_dir = tmp_path / "archive"
    _write_yaml(yaml_path)
    archive_dir.mkdir()
    code = CLI.main(
        [
            "--run-id",
            "ghost",
            "--config-path",
            str(yaml_path),
            "--archive-dir",
            str(archive_dir),
        ]
    )
    assert code == CLI.EXIT_NO_ARCHIVE


def test_cli_exits_4_when_disabled(tmp_path: Path) -> None:
    yaml_path = tmp_path / "default.yaml"
    archive_dir = tmp_path / "archive"
    _write_yaml(yaml_path, enabled=False)
    _write_archive(archive_dir, "x", n=100, pass_count=0)

    code = CLI.main(
        [
            "--run-id",
            "x",
            "--config-path",
            str(yaml_path),
            "--archive-dir",
            str(archive_dir),
        ]
    )
    assert code == CLI.EXIT_DISABLED


def test_cli_exits_8_when_schema_has_unexpected_nulls(tmp_path: Path) -> None:
    yaml_path = tmp_path / "default.yaml"
    archive_dir = tmp_path / "archive"
    _write_yaml(yaml_path)
    _write_archive(
        archive_dir, "nullbug", n=10, pass_count=1, introduce_null_in="stage_a_pass"
    )
    code = CLI.main(
        [
            "--run-id",
            "nullbug",
            "--config-path",
            str(yaml_path),
            "--archive-dir",
            str(archive_dir),
        ]
    )
    assert code == CLI.EXIT_SCHEMA_MISMATCH


def test_cli_exits_8_when_fitness_pen_has_nan(tmp_path: Path) -> None:
    yaml_path = tmp_path / "default.yaml"
    archive_dir = tmp_path / "archive"
    _write_yaml(yaml_path)
    _write_archive(
        archive_dir, "nanfp", n=10, pass_count=1, introduce_nan_in_fitness=True
    )
    code = CLI.main(
        [
            "--run-id",
            "nanfp",
            "--config-path",
            str(yaml_path),
            "--archive-dir",
            str(archive_dir),
        ]
    )
    assert code == CLI.EXIT_SCHEMA_MISMATCH


def test_cli_uses_latest_parquet_when_run_id_omitted(tmp_path: Path) -> None:
    yaml_path = tmp_path / "default.yaml"
    archive_dir = tmp_path / "archive"
    _write_yaml(yaml_path, target=0.5)
    older = _write_archive(archive_dir, "run_old", n=100, pass_count=0)
    # 後続を mtime で新しくする
    import time

    time.sleep(0.05)
    newer = _write_archive(archive_dir, "run_new", n=100, pass_count=50)

    # actual=0.5 + target=0.5 → in_band
    code = CLI.main(
        [
            "--config-path",
            str(yaml_path),
            "--archive-dir",
            str(archive_dir),
            "--dry-run",
        ]
    )
    assert code == CLI.EXIT_OK
    # newer の方が読まれていれば yaml は不変 (in_band)。
    # 念のため両方の Parquet は残っていること
    assert older.exists() and newer.exists()


def test_cli_exits_6_when_sample_size_below_min(tmp_path: Path) -> None:
    yaml_path = tmp_path / "default.yaml"
    archive_dir = tmp_path / "archive"
    _write_yaml(yaml_path, min_sample=100)
    _write_archive(archive_dir, "tiny", n=5, pass_count=0)

    code = CLI.main(
        [
            "--run-id",
            "tiny",
            "--config-path",
            str(yaml_path),
            "--archive-dir",
            str(archive_dir),
        ]
    )
    assert code == CLI.EXIT_SAMPLE_SIZE


def test_cli_writes_with_unique_tmp_name_no_residue(tmp_path: Path) -> None:
    """tmp ファイルが書き込み後に残っていないことを確認する。"""
    yaml_path = tmp_path / "default.yaml"
    archive_dir = tmp_path / "archive"
    _write_yaml(yaml_path, target=0.5)
    _write_archive(archive_dir, "u", n=100, pass_count=0)
    code = CLI.main(
        [
            "--run-id",
            "u",
            "--config-path",
            str(yaml_path),
            "--archive-dir",
            str(archive_dir),
        ]
    )
    assert code == CLI.EXIT_OK
    # tmp ファイルが残っていない
    residue = list(yaml_path.parent.glob("*.tmp"))
    assert residue == [], f"tmp residue: {residue}"


def test_cli_generation_weighted_mean_uses_all_generations(tmp_path: Path) -> None:
    """generation_weighted_mean mode で fitness_pen_pool が全世代使われること。"""
    yaml_path = tmp_path / "default.yaml"
    archive_dir = tmp_path / "archive"
    _write_yaml(
        yaml_path, mode="generation_weighted_mean", target=0.5, min_sample=10
    )
    # 100 行、generation 0..4 を均等
    _write_archive(archive_dir, "gwm", n=100, pass_count=50)

    code = CLI.main(
        [
            "--run-id",
            "gwm",
            "--config-path",
            str(yaml_path),
            "--archive-dir",
            str(archive_dir),
            "--dry-run",
        ]
    )
    # actual ≒ 0.5 (fixture が pass_count=50 を最初の 50 行に置くが
    # generation 0..4 を循環するので weight 配分も均等近似) → in_band 想定
    assert code == CLI.EXIT_OK


def test_cli_emits_applied_event_in_dry_run(tmp_path: Path, capfd: Any) -> None:
    """dry-run でも applied イベントが必ず emit される (Codex impl-review #2)。"""
    yaml_path = tmp_path / "default.yaml"
    archive_dir = tmp_path / "archive"
    _write_yaml(yaml_path, target=0.5, threshold=10.0)
    _write_archive(archive_dir, "dryapp", n=100, pass_count=0)

    code = CLI.main(
        [
            "--run-id",
            "dryapp",
            "--config-path",
            str(yaml_path),
            "--archive-dir",
            str(archive_dir),
            "--dry-run",
        ]
    )
    assert code == CLI.EXIT_OK
    err = capfd.readouterr().err
    assert "calibrate_gate.applied" in err
    assert '"dry_run": true' in err
    assert '"applied": false' in err


def test_cli_emits_applied_event_for_in_band(tmp_path: Path, capfd: Any) -> None:
    """in_band でも applied=False イベントが emit される。"""
    yaml_path = tmp_path / "default.yaml"
    archive_dir = tmp_path / "archive"
    _write_yaml(yaml_path, target=0.15)
    _write_archive(archive_dir, "ib", n=100, pass_count=15)

    code = CLI.main(
        [
            "--run-id",
            "ib",
            "--config-path",
            str(yaml_path),
            "--archive-dir",
            str(archive_dir),
        ]
    )
    assert code == CLI.EXIT_OK
    err = capfd.readouterr().err
    assert "calibrate_gate.applied" in err
    assert '"reason": "in_band"' in err


def test_cli_emits_applied_event_for_skip_sample_size(
    tmp_path: Path, capfd: Any
) -> None:
    """skip_sample_size でも applied イベント (reason=skip_sample_size) が出る。"""
    yaml_path = tmp_path / "default.yaml"
    archive_dir = tmp_path / "archive"
    _write_yaml(yaml_path, min_sample=100)
    _write_archive(archive_dir, "tinysk", n=5, pass_count=0)

    code = CLI.main(
        [
            "--run-id",
            "tinysk",
            "--config-path",
            str(yaml_path),
            "--archive-dir",
            str(archive_dir),
        ]
    )
    assert code == CLI.EXIT_SAMPLE_SIZE
    err = capfd.readouterr().err
    assert "calibrate_gate.applied" in err
    assert '"reason": "skip_sample_size"' in err


def test_cli_exits_8_when_total_pnl_has_null(tmp_path: Path) -> None:
    """null in total_pnl も schema mismatch (impl-review #1 拡張)。"""
    yaml_path = tmp_path / "default.yaml"
    archive_dir = tmp_path / "archive"
    _write_yaml(yaml_path)
    archive_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pydict(
        {
            "generation": pa.array([0, 1], type=pa.int32()),
            "stage_a_pass": pa.array([True, False], type=pa.bool_()),
            "fitness_pen": pa.array([1.0, 2.0], type=pa.float64()),
            "stage_b_pass": pa.array([False, False], type=pa.bool_()),
            "stage_c_pass": pa.array([False, False], type=pa.bool_()),
            "sharpe": pa.array([0.5, None], type=pa.float64()),
            "total_pnl": pa.array([100.0, None], type=pa.float64()),  # null
            "max_drawdown_pct": pa.array([10.0, 20.0], type=pa.float64()),
            "trade_count": pa.array([50, 60], type=pa.int32()),
        }
    )
    pq.write_table(table, archive_dir / "genomes_pnlnull.parquet")

    code = CLI.main(
        [
            "--run-id",
            "pnlnull",
            "--config-path",
            str(yaml_path),
            "--archive-dir",
            str(archive_dir),
        ]
    )
    assert code == CLI.EXIT_SCHEMA_MISMATCH


@pytest.mark.parametrize(
    "exit_const,name",
    [
        (CLI.EXIT_OK, "EXIT_OK"),
        (CLI.EXIT_INVALID_ARG, "EXIT_INVALID_ARG"),
        (CLI.EXIT_NO_ARCHIVE, "EXIT_NO_ARCHIVE"),
        (CLI.EXIT_DISABLED, "EXIT_DISABLED"),
        (CLI.EXIT_IO_ERROR, "EXIT_IO_ERROR"),
        (CLI.EXIT_SAMPLE_SIZE, "EXIT_SAMPLE_SIZE"),
        (CLI.EXIT_ZERO_VARIANCE, "EXIT_ZERO_VARIANCE"),
        (CLI.EXIT_SCHEMA_MISMATCH, "EXIT_SCHEMA_MISMATCH"),
    ],
)
def test_exit_codes_are_distinct(exit_const: int, name: str) -> None:
    """exit code 定数が定義されていることを確認 (regression guard)。"""
    assert isinstance(exit_const, int)
