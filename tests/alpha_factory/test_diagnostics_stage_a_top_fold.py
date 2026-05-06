"""tests for diagnostics_stage_a_top_fold (cycle 3)."""

from __future__ import annotations

import pandas as pd
import pyarrow.parquet as pq
import pytest

from src.alpha_factory.diagnostics_stage_a_top_fold import (
    STAGE_A_TOP_FOLD_SCHEMA,
    STAGE_A_TOP_FOLD_SCHEMA_VERSION,
    build_top_fold_table,
    stage_a_top_fold_relative_path,
    write_stage_a_top_fold,
)


def _archive_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        df = pd.DataFrame(
            columns=[
                "generation",
                "stage_a_pass",
                "fitness_pen",
                "fold_sign_ratio",
                "positive_fold_ratio_effective",
                "n_fold_effective",
            ]
        )
        df["stage_a_pass"] = df["stage_a_pass"].astype(bool)
        return df
    return pd.DataFrame(rows)


def test_relative_path_format():
    p = stage_a_top_fold_relative_path(35)
    assert (
        str(p)
        == "reports/run-reports/run-35/diagnostics/stage_a_top_fold_robustness.parquet"
    )


def test_build_top_fold_table_empty_returns_empty_table():
    """archive が空の場合、 空 table を返す."""
    df = _archive_df([])
    table = build_top_fold_table(df, "run_test", "epoch_test")
    assert table.num_rows == 0
    assert table.schema == STAGE_A_TOP_FOLD_SCHEMA


def test_build_top_fold_table_no_stage_a_pass_returns_empty():
    """Stage A pass 0 件の場合、 空 table を返す."""
    df = _archive_df(
        [
            {
                "generation": 0,
                "stage_a_pass": False,
                "fitness_pen": 0.1,
                "fold_sign_ratio": 0.2,
                "positive_fold_ratio_effective": 0.5,
                "n_fold_effective": 9,
            }
        ]
    )
    table = build_top_fold_table(df, "run_test", "epoch_test")
    assert table.num_rows == 0


def test_build_top_fold_table_basic():
    """Stage A pass 群で fitness_pen 降順 top 20% を集計する."""
    rows = []
    # generation 0: 10 個体 (5 Stage A pass), top 20% = ceil(5*0.2)=1 個体
    for i in range(10):
        rows.append(
            {
                "generation": 0,
                "stage_a_pass": i < 5,
                "fitness_pen": 0.1 * i,
                "fold_sign_ratio": 0.2 if i < 5 else 0.0,
                "positive_fold_ratio_effective": 0.4 if i < 5 else None,
                "n_fold_effective": 9 if i < 5 else 0,
            }
        )
    df = _archive_df(rows)
    table = build_top_fold_table(df, "run_test", "epoch_test")
    assert table.num_rows == 1
    d = table.to_pylist()[0]
    assert d["generation"] == 0
    assert d["population_n"] == 5  # Stage A pass のみ
    assert d["top_n"] == 1  # ceil(5 * 0.20) = 1
    assert d["n_selected"] == 1
    assert d["fold_sign_n_valid"] == 1
    assert d["pfre_n_valid"] == 1
    assert d["fold_sign_mean"] == pytest.approx(0.2)
    assert d["positive_fold_ratio_effective_mean"] == pytest.approx(0.4)
    assert d["fitness_pen_mean"] == pytest.approx(0.4)  # i=4 が top, fitness_pen=0.4
    assert d["diagnostics_schema_version"] == STAGE_A_TOP_FOLD_SCHEMA_VERSION
    assert d["dataset_epoch_id"] == "epoch_test"
    assert d["run_id"] == "run_test"
    assert d["top_selector"] == "fitness_pen"


def test_build_top_fold_table_multi_generation():
    """複数 generation を separate row で集計する."""
    rows = []
    for gen in [0, 1, 2]:
        for i in range(10):
            rows.append(
                {
                    "generation": gen,
                    "stage_a_pass": i < 5,
                    "fitness_pen": 0.1 * i + gen * 0.05,
                    "fold_sign_ratio": 0.2,
                    "positive_fold_ratio_effective": 0.4,
                    "n_fold_effective": 9,
                }
            )
    df = _archive_df(rows)
    table = build_top_fold_table(df, "run_test", "epoch_test")
    assert table.num_rows == 3
    gens = sorted([r["generation"] for r in table.to_pylist()])
    assert gens == [0, 1, 2]


def test_build_top_fold_table_nan_handling():
    """NaN 混入時に分母監査列が正しく計算される."""
    rows = []
    # 10 個体 (全員 Stage A pass), top 20% = 2 個体
    # 後半 (i>=5) は fold_sign_ratio / pfre が NaN
    # fitness_pen は i に比例なので top 2 = i=8, 9 (両方 NaN)
    for i in range(10):
        rows.append(
            {
                "generation": 0,
                "stage_a_pass": True,
                "fitness_pen": 0.1 * i,
                "fold_sign_ratio": 0.2 if i < 5 else None,
                "positive_fold_ratio_effective": 0.4 if i < 5 else None,
                "n_fold_effective": 9,
            }
        )
    df = _archive_df(rows)
    table = build_top_fold_table(df, "run_test", "epoch_test")
    d = table.to_pylist()[0]
    assert d["population_n"] == 10
    assert d["top_n"] == 2  # ceil(10 * 0.20) = 2
    assert d["n_selected"] == 2
    assert d["fold_sign_n_valid"] == 0  # top 2 とも NaN
    assert d["pfre_n_valid"] == 0
    assert d["fold_sign_mean"] is None
    assert d["fold_sign_nonzero_ratio"] is None
    assert d["positive_fold_ratio_effective_mean"] is None
    assert d["positive_fold_ratio_effective_nan_ratio"] == pytest.approx(1.0)


def test_build_top_fold_table_handles_missing_columns():
    """archive に positive_fold_ratio_effective / fold_sign_ratio 列不在で None で埋まる."""
    # 旧 schema 想定: stage_a_pass / fitness_pen / generation のみ
    rows = [
        {"generation": 0, "stage_a_pass": True, "fitness_pen": 0.5},
        {"generation": 0, "stage_a_pass": True, "fitness_pen": 0.3},
    ]
    df = pd.DataFrame(rows)
    table = build_top_fold_table(df, "run_test", "epoch_test")
    assert table.num_rows == 1
    d = table.to_pylist()[0]
    assert d["fold_sign_n_valid"] == 0
    assert d["pfre_n_valid"] == 0
    assert d["fold_sign_mean"] is None
    assert d["positive_fold_ratio_effective_mean"] is None
    assert d["n_fold_effective_mean"] is None
    # fitness_pen 集計は available
    assert d["fitness_pen_mean"] == pytest.approx(0.5)


def test_build_top_fold_table_nonzero_ratio_uses_strict_gt():
    """fold_sign_nonzero_ratio は > 0.0 (Stage B 契約と一致)."""
    rows = []
    # 10 個体全員 Stage A pass、 top 20% = 2 個体 (i=8, 9)
    # i=8: fold_sign=0.0, i=9: fold_sign=0.5
    for i in range(10):
        rows.append(
            {
                "generation": 0,
                "stage_a_pass": True,
                "fitness_pen": 0.1 * i,
                "fold_sign_ratio": 0.0 if i == 8 else 0.5,
                "positive_fold_ratio_effective": 0.4,
                "n_fold_effective": 9,
            }
        )
    df = _archive_df(rows)
    table = build_top_fold_table(df, "run_test", "epoch_test")
    d = table.to_pylist()[0]
    # top 2 = i=8 (0.0) + i=9 (0.5) → nonzero (>0) は 1 件 / 2 件 = 0.5
    assert d["fold_sign_nonzero_ratio"] == pytest.approx(0.5)


def test_write_stage_a_top_fold_creates_parquet(tmp_path):
    """write_stage_a_top_fold が parquet ファイルを作る."""
    rows = [
        {
            "generation": 0,
            "stage_a_pass": True,
            "fitness_pen": 0.5,
            "fold_sign_ratio": 0.3,
            "positive_fold_ratio_effective": 0.4,
            "n_fold_effective": 9,
        },
    ]
    df = _archive_df(rows)
    archive_path = tmp_path / "archive.parquet"
    # archive_df を archive.parquet として保存して、 write_stage_a_top_fold に渡す
    import pyarrow as pa

    pq.write_table(pa.Table.from_pandas(df), archive_path)

    out_path = tmp_path / "diagnostics" / "stage_a_top_fold_robustness.parquet"
    result = write_stage_a_top_fold(
        archive_path, out_path, "run_test", "epoch_test"
    )
    assert result == out_path
    assert out_path.exists()
    table = pq.read_table(out_path)
    assert table.schema == STAGE_A_TOP_FOLD_SCHEMA
    assert table.num_rows == 1


def test_write_stage_a_top_fold_fail_open_on_missing_archive(tmp_path):
    """archive_path 不在時に None を返し、 GA を止めない."""
    missing_path = tmp_path / "nonexistent.parquet"
    out_path = tmp_path / "diagnostics" / "out.parquet"
    result = write_stage_a_top_fold(
        missing_path, out_path, "run_test", "epoch_test"
    )
    assert result is None
    assert not out_path.exists()


def test_write_stage_a_top_fold_fail_open_on_build_error(tmp_path, monkeypatch):
    """build 段階で例外発生時に None を返す (fail-open 一貫化検証)."""
    rows = [
        {
            "generation": 0,
            "stage_a_pass": True,
            "fitness_pen": 0.5,
            "fold_sign_ratio": 0.3,
            "positive_fold_ratio_effective": 0.4,
            "n_fold_effective": 9,
        },
    ]
    df = _archive_df(rows)
    import pyarrow as pa

    archive_path = tmp_path / "archive.parquet"
    pq.write_table(pa.Table.from_pandas(df), archive_path)

    out_path = tmp_path / "diagnostics" / "out.parquet"

    def bad_build(*args, **kwargs):
        raise RuntimeError("test build failure")

    monkeypatch.setattr(
        "src.alpha_factory.diagnostics_stage_a_top_fold.build_top_fold_table",
        bad_build,
    )
    result = write_stage_a_top_fold(
        archive_path, out_path, "run_test", "epoch_test"
    )
    assert result is None
