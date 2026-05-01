"""T036: Factor Shadow Plane (FSP) updater (single instrument 専用 diagnostic layer).

Phase 1 仕様:
- post-RUN で archive Parquet を読み込み、FSP 6 列を計算して書き戻す
- 選抜介入 / fitness への寄与は無し (observability only)
- dispatch matrix 6 modes:
    active / skipped_multi_pair_run / skipped_disabled / skipped_no_factor_data /
    skipped_window_too_short / skipped_conditioning_mismatch
- 冪等性: fsp_runtime_mode が null の行のみ再計算 (`force_recalculate=False`)
- POSIX atomic write (tmp → fsync → rename → fsync(parent dir)) で耐クラッシュ

詳細: devnotes/20260425-0956-factor-shadow-plane-single-instr/detailed-design.md
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import structlog

from src.alpha_factory.archive import GENOMES_SCHEMA
from src.alpha_factory.config import FspConfig
from src.alpha_factory.schema_contract import (
    GENOME_ENTRY_SCHEMA_VERSION,
    SchemaContractError,
    SchemaEnforcementMode,
    SchemaVersionError,
)

logger = structlog.get_logger(__name__)

__all__ = [
    "FSP_NULLABLE_COLS",
    "FSP_RUNTIME_MODES",
    "H1_NON_ELIGIBLE_MODES",
    "_aggregate_daily_pnl",
    "_atomic_write_parquet",
    "_check_archive_duplicate_keys",
    "_check_key_integrity",
    "_compute_fsp_stats",
    "_decide_runtime_mode",
    "_detect_archive_schema_version",
    "_load_dxy_series",
    "_read_archive_with_fsp_compat",
    "evaluate_h1",
    "evaluate_key_integrity_failure_rate",
    "rolling_spearman",
    "run_fsp_updater",
]

# T058: FSP archive write が要求する v2 必須 field (genome_entry contract と同期)
_FSP_V2_REQUIRED_COLUMNS: Final[frozenset[str]] = frozenset(
    {"genome_entry_schema_version", "dataset_epoch_id"}
)

FSP_RUNTIME_MODES: Final[frozenset[str]] = frozenset(
    {
        "active",
        "skipped_no_factor_data",
        "skipped_disabled",
        "skipped_multi_pair_run",
        "skipped_window_too_short",
        "skipped_conditioning_mismatch",
    }
)

H1_NON_ELIGIBLE_MODES: Final[frozenset[str]] = frozenset(
    {
        "skipped_multi_pair_run",
        "skipped_disabled",
        "skipped_no_factor_data",
        "skipped_window_too_short",
    }
)

FSP_NULLABLE_COLS: Final[tuple[str, ...]] = (
    "fsp_runtime_mode",
    "fsp_sampling_mode",
    "fsp_factor_set",
    "fsp_rolling_corr_60d",
    "fsp_explained_variance",
    "fsp_idio_ratio",
)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _decide_runtime_mode(
    fsp_cfg: FspConfig,
    is_multi_pair: bool,
    factor_data_available: bool,
    min_bars: int,
) -> str:
    """6 パスの dispatch matrix のうち最初の 5 パスを判定。

    `active` を返した場合でも下流の `_check_key_integrity()` が
    `skipped_conditioning_mismatch` を返す可能性がある (件数整合チェック)。
    """
    if is_multi_pair:
        return "skipped_multi_pair_run"
    if not fsp_cfg.enabled:
        return "skipped_disabled"
    if not factor_data_available:
        return "skipped_no_factor_data"
    if min_bars < fsp_cfg.window_days:
        return "skipped_window_too_short"
    return "active"


# ---------------------------------------------------------------------------
# Archive read with FSP-compat
# ---------------------------------------------------------------------------


def _detect_archive_schema_version(table: pa.Table) -> int | None:
    """T058: archive Parquet の genome_entry_schema_version を判定 helper.

    判定ロジック:
        - 列が存在しない → v1 archive とみなして ``None``
        - 列が存在 + 行 0 件 → schema 自体は v2 を宣言済み (PR 2 の SCHEMA で
          field 定義済) なので ``GENOME_ENTRY_SCHEMA_VERSION`` (= 2) を返す。
          これは「物理 schema は v2 だが書込が未実行な空 archive」を v1
          扱いで誤検出しないため (= ``None`` 返却 → FAIL_CLOSED で誤 raise を防ぐ)。
        - 列が存在 + 値が全て None → v1 互換 (None) を返す。
        - それ以外 → 値の最大値 (mixed-version archive 観測時の保守的見積もり)。

    Returns:
        ``None`` (v1 archive 検出時) または ``int`` (v2+ schema_version)。
    """
    if "genome_entry_schema_version" not in table.column_names:
        return None
    versions = table.column("genome_entry_schema_version").to_pylist()
    if not versions:
        # 空 table: 物理 schema は v2 (列が存在) なので v2 と宣言。
        # FAIL_CLOSED 経路でも誤 raise しない (空 archive は legitimate な
        # initial state)。
        return GENOME_ENTRY_SCHEMA_VERSION
    valid_versions = [int(v) for v in versions if v is not None]
    if not valid_versions:
        return None
    return max(valid_versions)


def _read_archive_with_fsp_compat(
    archive_path: Path,
    *,
    mode: SchemaEnforcementMode = SchemaEnforcementMode.LOG_ONLY,
) -> pd.DataFrame:
    """旧/新 両方の archive Parquet を読み込み、FSP 列を None 補完する。

    T058: schema_version 判定を ``_detect_archive_schema_version`` 経由で実施。
    既存返却契約 (df 単独) は維持。 v1 archive 検出時は ``mode`` に従い
    LOG_ONLY なら warning、 FAIL_CLOSED なら ``SchemaVersionError`` raise。
    """
    table = pq.read_table(archive_path)
    schema_version = _detect_archive_schema_version(table)
    if schema_version is None:
        if mode == SchemaEnforcementMode.FAIL_CLOSED:
            raise SchemaVersionError(
                f"FSP read: v1 archive (no genome_entry_schema_version): {archive_path}"
            )
        logger.warning(
            "fsp_updater.v1_archive_detected",
            archive_path=str(archive_path),
        )
    df = table.to_pandas()
    for col in FSP_NULLABLE_COLS:
        if col not in df.columns:
            df[col] = None
    return df


# ---------------------------------------------------------------------------
# Key integrity (Step A: 全件重複検知 / Step B: TARGET_ROWS 整合)
# ---------------------------------------------------------------------------


def _check_archive_duplicate_keys(archive_df: pd.DataFrame) -> str | None:
    """Step A: archive 全件で重複キー検知 (TARGET_ROWS によらず常時)."""
    all_keys = list(
        zip(
            archive_df["run_id"],
            archive_df["lane_id"],
            archive_df["generation"],
            archive_df["individual_name"],
            strict=True,
        )
    )
    if len(all_keys) != len(set(all_keys)):
        logger.warning(
            "fsp_duplicate_keys_in_archive",
            total=len(all_keys),
            unique=len(set(all_keys)),
        )
        return "skipped_conditioning_mismatch"
    return None


def _check_key_integrity(
    target_df: pd.DataFrame,
    fsp_results: Mapping[tuple[Any, ...], Mapping[str, Any]],
) -> str | None:
    """Step B: TARGET_ROWS と fsp_results のキー集合一致チェック."""
    target_keys = set(
        zip(
            target_df["run_id"],
            target_df["lane_id"],
            target_df["generation"],
            target_df["individual_name"],
            strict=True,
        )
    )
    fsp_keys = set(fsp_results.keys())
    if target_keys != fsp_keys:
        logger.warning(
            "fsp_key_mismatch",
            missing=len(fsp_keys - target_keys),
            extra=len(target_keys - fsp_keys),
        )
        return "skipped_conditioning_mismatch"
    return None


# ---------------------------------------------------------------------------
# Atomic Parquet write (POSIX rename + fsync)
# ---------------------------------------------------------------------------


def _atomic_write_parquet(
    df: pd.DataFrame,
    target_path: Path,
    schema: pa.Schema,
    *,
    mode: SchemaEnforcementMode = SchemaEnforcementMode.LOG_ONLY,
) -> None:
    """tmp → fsync(file) → atomic rename → fsync(dir) で耐クラッシュ書き出し.

    Codex round-1 [Warning] 対応: tmp 名は固定 (`*.fsp_tmp.parquet`) ではなく
    PID + uuid で一意化し、複数プロセス並行更新でも互いの tmp を踏まないように
    する。POSIX rename は atomic 保証されるため tmp が一意なら最終 archive
    の整合性も保たれる。

    T058: ``mode`` kwarg を default 付きで追加 (旧 caller 完全互換)。
    v2 必須 field (``genome_entry_schema_version`` / ``dataset_epoch_id``)
    が ``df`` に欠落していた場合:
      - LOG_ONLY: warning + grammar 適合 fallback で補完して書込続行
        (``epoch_legacy`` / ``GENOME_ENTRY_SCHEMA_VERSION``)。
      - FAIL_CLOSED: ``SchemaContractError`` raise (= 書込しない)。
    """
    missing = _FSP_V2_REQUIRED_COLUMNS - set(df.columns)
    if missing:
        if mode == SchemaEnforcementMode.FAIL_CLOSED:
            raise SchemaContractError(
                f"FSP archive write missing v2 fields: {sorted(missing)}"
            )
        logger.warning(
            "fsp_updater.write.v2_fields_missing",
            missing=sorted(missing),
            target_path=str(target_path),
        )
        # LOG_ONLY: 最善努力で書込 (grammar 適合 fallback 補完)
        # caller の DataFrame を mutate しないため shallow copy。
        df = df.copy()
        for col in missing:
            if col == "dataset_epoch_id":
                df[col] = "epoch_legacy"
            elif col == "genome_entry_schema_version":
                df[col] = GENOME_ENTRY_SCHEMA_VERSION

    tmp_token = f".fsp_tmp.{os.getpid()}.{uuid.uuid4().hex}.parquet"
    tmp_path = target_path.with_suffix(tmp_token)
    try:
        table = pa.Table.from_pandas(df, schema=schema, preserve_index=False)
        pq.write_table(table, tmp_path)
        with open(tmp_path, "rb") as f:
            os.fsync(f.fileno())
        tmp_path.rename(target_path)
        parent_fd = os.open(str(target_path.parent), os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# Factor data loading + statistics
# ---------------------------------------------------------------------------


def _load_dxy_series(
    fred_data_dir: Path, factor_asof_lag: int
) -> pd.Series | None:
    """data/raw/fred/DXY.csv から日次系列を読み込み lag 適用。

    factor_asof_lag=1 の場合: factor_return_t = (DXY_{t-1} - DXY_{t-2}) / DXY_{t-2}
    look-ahead bias 回避。

    ファイル不在 / `close` 列不在 / 空データなら None を返す。
    """
    dxy_path = fred_data_dir / "DXY.csv"
    if not dxy_path.exists():
        return None
    try:
        dxy = pd.read_csv(dxy_path, index_col=0, parse_dates=True)
    except Exception:
        return None
    if "close" not in dxy.columns or dxy.empty:
        return None
    series = dxy["close"].pct_change().shift(factor_asof_lag).dropna()
    if series.empty:
        return None
    return series


def _aggregate_daily_pnl(
    trades_df: pd.DataFrame,
    date_range: pd.DatetimeIndex,
) -> pd.Series:
    """UTC 日次境界で trades の pnl を集計。ゼロポジション日は 0.0 で補完."""
    if trades_df.empty:
        return pd.Series(0.0, index=date_range)
    work = trades_df.copy()
    work["date_utc"] = pd.to_datetime(work["close_time"]).dt.normalize()
    daily = work.groupby("date_utc")["pnl"].sum()
    return daily.reindex(date_range, fill_value=0.0)


def rolling_spearman(
    series_a: pd.Series, series_b: pd.Series, window: int
) -> pd.Series:
    """Phase 1 近似: 窓ごとに rank → Pearson 相関 (rank-Pearson 近似)."""
    result = pd.Series(index=series_a.index, dtype=float)
    n = len(series_a)
    if n < window:
        return result
    for end in range(window - 1, n):
        start = end - window + 1
        a_win = series_a.iloc[start : end + 1]
        b_win = series_b.iloc[start : end + 1]
        result.iloc[end] = a_win.rank().corr(b_win.rank())
    return result


def _compute_fsp_stats(
    daily_pnl: pd.Series,
    factor_return: pd.Series,
    window_days: int = 60,
) -> dict[str, Any]:
    """rolling 60d Spearman + 全期間 OLS R² (unclipped)."""
    aligned = pd.concat([daily_pnl, factor_return], axis=1).dropna()
    aligned.columns = ["pnl", "factor"]

    if len(aligned) < 2:
        return {
            "fsp_rolling_corr_60d": [],
            "fsp_explained_variance": None,
            "fsp_idio_ratio": None,
        }

    rolling_corr = rolling_spearman(
        aligned["pnl"], aligned["factor"], window_days
    )

    # OLS R² (numpy 直接、sklearn 依存を避ける)
    x = aligned["factor"].to_numpy()
    y = aligned["pnl"].to_numpy()
    if x.var() == 0.0 or y.var() == 0.0:
        r2 = 0.0
    else:
        a = np.column_stack([x, np.ones_like(x)])
        beta, *_ = np.linalg.lstsq(a, y, rcond=None)
        y_pred = a @ beta
        ss_res = float(((y - y_pred) ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum())
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return {
        "fsp_rolling_corr_60d": rolling_corr.dropna().tolist(),
        "fsp_explained_variance": float(r2),
        "fsp_idio_ratio": float(1.0 - r2),
    }


# ---------------------------------------------------------------------------
# H1 evaluation queries
# ---------------------------------------------------------------------------


def evaluate_h1(archive_df: pd.DataFrame) -> float:
    """eligible rows のうち active 比率."""
    eligible = archive_df[
        archive_df["fsp_runtime_mode"].notna()
        & (~archive_df["fsp_runtime_mode"].isin(H1_NON_ELIGIBLE_MODES))
    ]
    if len(eligible) == 0:
        return 0.0
    return float((eligible["fsp_runtime_mode"] == "active").mean())


def evaluate_key_integrity_failure_rate(archive_df: pd.DataFrame) -> float:
    """eligible rows のうち skipped_conditioning_mismatch 比率."""
    eligible = archive_df[
        archive_df["fsp_runtime_mode"].notna()
        & (~archive_df["fsp_runtime_mode"].isin(H1_NON_ELIGIBLE_MODES))
    ]
    if len(eligible) == 0:
        return 0.0
    return float(
        (eligible["fsp_runtime_mode"] == "skipped_conditioning_mismatch").mean()
    )


# ---------------------------------------------------------------------------
# Top-level updater
# ---------------------------------------------------------------------------


def _write_mode_to_targets(
    archive_df: pd.DataFrame,
    target_idx: pd.Index,
    mode: str,
    fsp_cfg: FspConfig,
) -> None:
    """target rows に mode + sampling_mode を書き込み、skip 系では旧 active 観測値を
    None に正規化する (Codex round-1 [Critical] 対応: force_recalculate で
    `active` → `skipped_*` に戻す際に旧 fsp_factor_set / fsp_rolling_corr_60d /
    fsp_explained_variance / fsp_idio_ratio が貼り付いたまま残る問題を防ぐ)."""
    archive_df.loc[target_idx, "fsp_runtime_mode"] = mode
    archive_df.loc[target_idx, "fsp_sampling_mode"] = fsp_cfg.sampling_mode
    # skip 系 (active 以外) は観測値カラムを必ず None にリセットして
    # 再実行時の stale observation を防ぐ。active 経路は呼び出し側
    # (run_fsp_updater) が個別に書き込むため本関数では触らない。
    if mode != "active":
        for col in (
            "fsp_factor_set",
            "fsp_rolling_corr_60d",
            "fsp_explained_variance",
            "fsp_idio_ratio",
        ):
            archive_df.loc[target_idx, col] = None


def _factor_data_available(fred_data_dir: Path, fsp_cfg: FspConfig) -> bool:
    """factor data の存在判定 (Phase 1 は DXY のみ)."""
    if "DXY" in fsp_cfg.factors:
        return (fred_data_dir / "DXY.csv").exists()
    return False


def _estimate_min_bars(target_df: pd.DataFrame) -> int:
    """個体ごとの bars 数を見積もる Phase 1 ヒューリスティック (trade_count で代用).

    archive には bars 数を直接持たないため `trade_count` で代用する
    (= 観測 window 中に発生した取引数の最低保証)。Phase 2 で run_ga 側から
    n_bars を渡す経路を整備する想定。
    """
    if "trade_count" not in target_df.columns or target_df.empty:
        return 0
    return int(target_df["trade_count"].max())


def run_fsp_updater(
    archive_path: Path,
    fred_data_dir: Path,
    fsp_cfg: FspConfig,
    run_id: str,
    is_multi_pair: bool = False,
    force_recalculate: bool = False,
    *,
    schema_mode: SchemaEnforcementMode = SchemaEnforcementMode.LOG_ONLY,
) -> str:
    """FSP を計算して archive Parquet を in-place 更新する。

    T058: schema v2 enforcement mode を ``schema_mode`` kwarg で受け取り、
    内部の ``_read_archive_with_fsp_compat`` / ``_atomic_write_parquet``
    呼出に伝搬する (旧 caller は default LOG_ONLY で従来挙動を維持)。

    Returns:
        ``fsp_runtime_mode`` (active or skipped_*).
    """
    archive_df = _read_archive_with_fsp_compat(archive_path, mode=schema_mode)

    # 再計算対象 (冪等性): fsp_runtime_mode が null の行のみ
    target_df = (
        archive_df.copy()
        if force_recalculate
        else archive_df[archive_df["fsp_runtime_mode"].isna()].copy()
    )

    # Step A: 全件重複検知
    dup_mismatch = _check_archive_duplicate_keys(archive_df)
    if dup_mismatch:
        runtime_mode = "skipped_conditioning_mismatch"
        _write_mode_to_targets(
            archive_df, target_df.index, runtime_mode, fsp_cfg
        )
        _atomic_write_parquet(
            archive_df, archive_path, schema=GENOMES_SCHEMA, mode=schema_mode
        )
        logger.warning("fsp_updater.skipped", mode=runtime_mode, run_id=run_id)
        return runtime_mode

    # 全行既処理 → no-op active (dispatch 判定の前にチェック、min_bars=0 で
    # 誤って skipped_window_too_short を返すことを防ぐ)
    if target_df.empty:
        logger.info(
            "fsp_updater.no_op",
            reason="all_rows_already_processed",
            rows_total=len(archive_df),
            rows_processed=0,
            run_id=run_id,
        )
        return "active"

    factor_data_available = _factor_data_available(fred_data_dir, fsp_cfg)
    min_bars = _estimate_min_bars(target_df)
    initial_mode = _decide_runtime_mode(
        fsp_cfg=fsp_cfg,
        is_multi_pair=is_multi_pair,
        factor_data_available=factor_data_available,
        min_bars=min_bars,
    )

    if initial_mode != "active":
        _write_mode_to_targets(
            archive_df, target_df.index, initial_mode, fsp_cfg
        )
        _atomic_write_parquet(
            archive_df, archive_path, schema=GENOMES_SCHEMA, mode=schema_mode
        )
        logger.info(
            "fsp_updater.skipped",
            mode=initial_mode,
            run_id=run_id,
            min_bars=min_bars,
            window=fsp_cfg.window_days,
        )
        return initial_mode

    # Phase 1: trade ledger 統合は別 TODO (Phase 2) で行う。
    # 現実装では fsp_results 空 dict → _check_key_integrity が conditioning_mismatch
    # を返し、target rows に書き戻して mismatch を返す (詳細設計 §11 notes)。
    # PnL 注入経路の本実装は次フェーズで整備する。
    fsp_results: dict[tuple[Any, ...], dict[str, Any]] = {}

    key_mismatch = _check_key_integrity(target_df, fsp_results)
    if key_mismatch:
        runtime_mode = key_mismatch
        _write_mode_to_targets(
            archive_df, target_df.index, runtime_mode, fsp_cfg
        )
        _atomic_write_parquet(
            archive_df, archive_path, schema=GENOMES_SCHEMA, mode=schema_mode
        )
        logger.warning(
            "fsp_updater.skipped",
            mode=runtime_mode,
            run_id=run_id,
            reason="empty_fsp_results_phase1",
        )
        return runtime_mode

    # Phase 2 で fsp_results が target_df と一致したらこの経路に来る
    for key, stats in fsp_results.items():
        mask = (
            (archive_df["run_id"] == key[0])
            & (archive_df["lane_id"] == key[1])
            & (archive_df["generation"] == key[2])
            & (archive_df["individual_name"] == key[3])
        )
        idx = archive_df.index[mask]
        archive_df.loc[idx, "fsp_runtime_mode"] = "active"
        archive_df.loc[idx, "fsp_sampling_mode"] = fsp_cfg.sampling_mode
        archive_df.loc[idx, "fsp_explained_variance"] = stats[
            "fsp_explained_variance"
        ]
        archive_df.loc[idx, "fsp_idio_ratio"] = stats["fsp_idio_ratio"]
        # list 列は object 経由で代入
        archive_df.at[idx[0], "fsp_factor_set"] = list(fsp_cfg.factors)
        archive_df.at[idx[0], "fsp_rolling_corr_60d"] = stats[
            "fsp_rolling_corr_60d"
        ]

    _atomic_write_parquet(
        archive_df, archive_path, schema=GENOMES_SCHEMA, mode=schema_mode
    )
    logger.info(
        "fsp_updater.completed",
        mode="active",
        rows_processed=len(target_df),
        run_id=run_id,
    )
    return "active"
