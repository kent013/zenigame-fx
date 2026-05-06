"""Stage A top-fold robustness diagnostics sidecar (cycle 3, plan-and-design 由来).

archive Parquet から generation 別 Stage A pass 上位 20% (fitness_pen 基準) の
fold robustness 集計を sidecar Parquet として書き出す。

production GA からは fail-open で呼ばれる (書き込みエラー時は warning ログのみ、
GA は止めない)。

詳細: devnotes/20260506-1345-fx-improve-c3/detailed-design.md § C1
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Final

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import structlog

logger = structlog.get_logger(__name__)

__all__ = [
    "STAGE_A_TOP_FOLD_SCHEMA",
    "STAGE_A_TOP_FOLD_SCHEMA_VERSION",
    "TOP_PCT_DEFAULT",
    "TOP_SELECTOR_DEFAULT",
    "build_top_fold_table",
    "stage_a_top_fold_relative_path",
    "write_stage_a_top_fold",
]

STAGE_A_TOP_FOLD_SCHEMA_VERSION: Final[int] = 1
TOP_PCT_DEFAULT: Final[float] = 0.20
TOP_SELECTOR_DEFAULT: Final[str] = "fitness_pen"

STAGE_A_TOP_FOLD_SCHEMA: Final[pa.Schema] = pa.schema(
    [
        pa.field("diagnostics_schema_version", pa.int32(), nullable=False),
        pa.field("dataset_epoch_id", pa.string(), nullable=False),
        pa.field("run_id", pa.string(), nullable=False),
        pa.field("generation", pa.int32(), nullable=False),
        pa.field("top_selector", pa.string(), nullable=False),
        pa.field("top_pct", pa.float64(), nullable=False),
        pa.field("population_n", pa.int32(), nullable=False),
        pa.field("top_n", pa.int32(), nullable=False),
        pa.field("n_selected", pa.int32(), nullable=False),
        pa.field("fold_sign_n_valid", pa.int32(), nullable=False),
        pa.field("pfre_n_valid", pa.int32(), nullable=False),
        pa.field("fold_sign_mean", pa.float64(), nullable=True),
        pa.field("fold_sign_median", pa.float64(), nullable=True),
        pa.field("fold_sign_nonzero_ratio", pa.float64(), nullable=True),
        pa.field("positive_fold_ratio_effective_mean", pa.float64(), nullable=True),
        pa.field("positive_fold_ratio_effective_median", pa.float64(), nullable=True),
        pa.field(
            "positive_fold_ratio_effective_nan_ratio", pa.float64(), nullable=True
        ),
        pa.field("n_fold_effective_mean", pa.float64(), nullable=True),
        pa.field("fitness_pen_mean", pa.float64(), nullable=True),
        pa.field("fitness_pen_median", pa.float64(), nullable=True),
    ]
)


def stage_a_top_fold_relative_path(run_number: int) -> Path:
    """sidecar Parquet の相対 path SSOT."""
    return Path(
        f"reports/run-reports/run-{run_number}/diagnostics/"
        "stage_a_top_fold_robustness.parquet"
    )


def build_top_fold_table(
    archive_df: pd.DataFrame,
    run_id: str,
    dataset_epoch_id: str,
) -> pa.Table:
    """archive DataFrame から generation 別 Stage A 上位 20% fold 集計テーブルを構築する.

    Stage A pass=True 個体のみを対象とし、 generation 内で fitness_pen 降順
    上位 20% を集計する。 Stage A pass 0 の世代は row を出力しない。
    """
    rows: list[dict] = []
    if "stage_a_pass" not in archive_df.columns:
        return pa.Table.from_pylist([], schema=STAGE_A_TOP_FOLD_SCHEMA)

    sa_only = archive_df[
        archive_df["stage_a_pass"].fillna(False).astype(bool)
    ]
    if len(sa_only) == 0:
        return pa.Table.from_pylist([], schema=STAGE_A_TOP_FOLD_SCHEMA)

    for gen, grp in sa_only.groupby("generation", sort=True):
        pop_n = len(grp)
        if pop_n == 0:
            continue
        top_n = max(1, math.ceil(pop_n * TOP_PCT_DEFAULT))
        top = grp.nlargest(top_n, "fitness_pen")
        n_selected = len(top)

        if "fold_sign_ratio" in top.columns:
            fsr = top["fold_sign_ratio"].dropna()
        else:
            fsr = pd.Series(dtype=float)
        fsr_n_valid = len(fsr)
        fsr_mean = float(fsr.mean()) if fsr_n_valid > 0 else None
        fsr_median = float(fsr.median()) if fsr_n_valid > 0 else None
        fsr_nonzero_ratio = (
            float((fsr > 0.0).sum() / fsr_n_valid) if fsr_n_valid > 0 else None
        )

        if "positive_fold_ratio_effective" in top.columns:
            pfre = top["positive_fold_ratio_effective"]
        else:
            pfre = pd.Series(dtype=float)
        pfre_clean = pfre.dropna()
        pfre_n_valid = len(pfre_clean)
        pfre_mean = float(pfre_clean.mean()) if pfre_n_valid > 0 else None
        pfre_median = float(pfre_clean.median()) if pfre_n_valid > 0 else None
        pfre_nan_ratio = (
            float(1.0 - pfre_n_valid / n_selected) if n_selected > 0 else None
        )

        if "n_fold_effective" in top.columns:
            nfe = top["n_fold_effective"].dropna()
        else:
            nfe = pd.Series(dtype=float)
        nfe_mean = float(nfe.mean()) if len(nfe) > 0 else None

        fp = top["fitness_pen"]
        fp_mean = float(fp.mean())
        fp_median = float(fp.median())

        rows.append(
            {
                "diagnostics_schema_version": STAGE_A_TOP_FOLD_SCHEMA_VERSION,
                "dataset_epoch_id": dataset_epoch_id,
                "run_id": run_id,
                "generation": int(gen),
                "top_selector": TOP_SELECTOR_DEFAULT,
                "top_pct": TOP_PCT_DEFAULT,
                "population_n": pop_n,
                "top_n": top_n,
                "n_selected": n_selected,
                "fold_sign_n_valid": fsr_n_valid,
                "pfre_n_valid": pfre_n_valid,
                "fold_sign_mean": fsr_mean,
                "fold_sign_median": fsr_median,
                "fold_sign_nonzero_ratio": fsr_nonzero_ratio,
                "positive_fold_ratio_effective_mean": pfre_mean,
                "positive_fold_ratio_effective_median": pfre_median,
                "positive_fold_ratio_effective_nan_ratio": pfre_nan_ratio,
                "n_fold_effective_mean": nfe_mean,
                "fitness_pen_mean": fp_mean,
                "fitness_pen_median": fp_median,
            }
        )

    return pa.Table.from_pylist(rows, schema=STAGE_A_TOP_FOLD_SCHEMA)


def write_stage_a_top_fold(
    archive_path: Path,
    out_path: Path,
    run_id: str,
    dataset_epoch_id: str,
) -> Path | None:
    """archive Parquet を読んで sidecar parquet を書き出す。 fail-open 一貫化.

    read+build+write を 1 関数内に寄せて fail-open を一貫化する。
    archive_path の読込・build・write のいずれの段階で失敗しても
    warning + None 返却。
    """
    try:
        archive_df = pq.read_table(archive_path).to_pandas()
        table = build_top_fold_table(archive_df, run_id, dataset_epoch_id)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, out_path)
        logger.info(
            "diagnostics.stage_a_top_fold.written",
            path=str(out_path),
            n_generations=table.num_rows,
            run_id=run_id,
        )
        return out_path
    except Exception as exc:
        logger.warning(
            "diagnostics.stage_a_top_fold.write_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            run_id=run_id,
        )
        return None
