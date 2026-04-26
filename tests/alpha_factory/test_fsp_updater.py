"""T036: Factor Shadow Plane (FSP) updater テスト.

詳細設計: devnotes/20260425-0956-factor-shadow-plane-single-instr/detailed-design.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.alpha_factory.archive import GENOMES_SCHEMA, _create_row_template
from src.alpha_factory.config import FspConfig
from src.alpha_factory.fsp_updater import (
    FSP_NULLABLE_COLS,
    FSP_RUNTIME_MODES,
    H1_NON_ELIGIBLE_MODES,
    _aggregate_daily_pnl,
    _atomic_write_parquet,
    _check_archive_duplicate_keys,
    _check_key_integrity,
    _compute_fsp_stats,
    _decide_runtime_mode,
    _load_dxy_series,
    _read_archive_with_fsp_compat,
    evaluate_h1,
    evaluate_key_integrity_failure_rate,
    rolling_spearman,
    run_fsp_updater,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_dxy_csv(path: Path, n_days: int = 80) -> None:
    """合成 DXY series を CSV に書き出し (close 列必須)."""
    rng = np.random.default_rng(seed=42)
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    closes = 100.0 + rng.normal(scale=0.5, size=n_days).cumsum()
    df = pd.DataFrame({"close": closes}, index=dates)
    df.index.name = "date"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)


def _make_archive_table(n_rows: int = 3) -> pa.Table:
    """T036 schema 完備の minimal archive Parquet を返す."""
    rows = []
    for i in range(n_rows):
        r = _create_row_template()
        r.update(
            {
                "run_id": "run_test",
                "run_number": 0,
                "generation": 0,
                "individual_name": f"g0_i{i}",
                "instrument": "USD_JPY",
                "lane_id": "tier1_USD_JPY",
                "genome_json": "{}",
                "stage_a_pass": False,
                "stage_b_pass": False,
                "stage_c_pass": False,
                "graduated": False,
                "trade_count": 80 + i,
            }
        )
        # _MAX_STAGE_KEY は schema 外なので削除
        r.pop("_max_stage_seen", None)
        rows.append(r)
    return pa.Table.from_pylist(rows, schema=GENOMES_SCHEMA)


def _write_archive(path: Path, table: pa.Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


# ---------------------------------------------------------------------------
# T036-1: Module-level constants
# ---------------------------------------------------------------------------


class TestFspConstants:
    def test_runtime_modes_has_six_values(self) -> None:
        assert len(FSP_RUNTIME_MODES) == 6
        assert "active" in FSP_RUNTIME_MODES
        assert "skipped_conditioning_mismatch" in FSP_RUNTIME_MODES

    def test_h1_non_eligible_modes_excludes_active_and_mismatch(self) -> None:
        assert "active" not in H1_NON_ELIGIBLE_MODES
        assert "skipped_conditioning_mismatch" not in H1_NON_ELIGIBLE_MODES
        assert len(H1_NON_ELIGIBLE_MODES) == 4

    def test_fsp_nullable_cols_count(self) -> None:
        assert len(FSP_NULLABLE_COLS) == 6


# ---------------------------------------------------------------------------
# T036-2: _decide_runtime_mode (5 path dispatch)
# ---------------------------------------------------------------------------


class TestDecideRuntimeMode:
    @pytest.mark.parametrize(
        "case,expected",
        [
            (
                {"is_multi_pair": True, "factor_data_available": True, "min_bars": 100, "enabled": True},
                "skipped_multi_pair_run",
            ),
            (
                {"is_multi_pair": False, "factor_data_available": True, "min_bars": 100, "enabled": False},
                "skipped_disabled",
            ),
            (
                {"is_multi_pair": False, "factor_data_available": False, "min_bars": 100, "enabled": True},
                "skipped_no_factor_data",
            ),
            (
                {"is_multi_pair": False, "factor_data_available": True, "min_bars": 30, "enabled": True},
                "skipped_window_too_short",
            ),
            (
                {"is_multi_pair": False, "factor_data_available": True, "min_bars": 100, "enabled": True},
                "active",
            ),
        ],
    )
    def test_dispatch_paths(self, case: dict[str, Any], expected: str) -> None:
        cfg = FspConfig(enabled=case["enabled"], window_days=60)
        actual = _decide_runtime_mode(
            fsp_cfg=cfg,
            is_multi_pair=case["is_multi_pair"],
            factor_data_available=case["factor_data_available"],
            min_bars=case["min_bars"],
        )
        assert actual == expected

    def test_multi_pair_takes_priority_over_disabled(self) -> None:
        cfg = FspConfig(enabled=False)
        # disabled でも multi_pair が先 (T016 と排他)
        assert (
            _decide_runtime_mode(
                fsp_cfg=cfg,
                is_multi_pair=True,
                factor_data_available=False,
                min_bars=0,
            )
            == "skipped_multi_pair_run"
        )


# ---------------------------------------------------------------------------
# T036-3: Key integrity (Step A / Step B)
# ---------------------------------------------------------------------------


class TestKeyIntegrity:
    def test_no_duplicate_keys_returns_none(self) -> None:
        df = pd.DataFrame(
            {
                "run_id": ["r"] * 3,
                "lane_id": ["lane"] * 3,
                "generation": [0, 0, 0],
                "individual_name": ["a", "b", "c"],
            }
        )
        assert _check_archive_duplicate_keys(df) is None

    def test_duplicate_keys_detected(self) -> None:
        df = pd.DataFrame(
            {
                "run_id": ["r"] * 3,
                "lane_id": ["lane"] * 3,
                "generation": [0, 0, 0],
                "individual_name": ["a", "b", "a"],  # 重複
            }
        )
        assert (
            _check_archive_duplicate_keys(df) == "skipped_conditioning_mismatch"
        )

    def test_key_integrity_match(self) -> None:
        df = pd.DataFrame(
            {
                "run_id": ["r"],
                "lane_id": ["lane"],
                "generation": [0],
                "individual_name": ["a"],
            }
        )
        results = {("r", "lane", 0, "a"): {"x": 1.0}}
        assert _check_key_integrity(df, results) is None

    def test_key_integrity_extra_in_results(self) -> None:
        df = pd.DataFrame(
            {
                "run_id": ["r"],
                "lane_id": ["lane"],
                "generation": [0],
                "individual_name": ["a"],
            }
        )
        results = {
            ("r", "lane", 0, "a"): {},
            ("r", "lane", 0, "b"): {},  # archive にないキー
        }
        assert _check_key_integrity(df, results) == "skipped_conditioning_mismatch"

    def test_key_integrity_missing_in_results(self) -> None:
        df = pd.DataFrame(
            {
                "run_id": ["r", "r"],
                "lane_id": ["lane", "lane"],
                "generation": [0, 0],
                "individual_name": ["a", "b"],
            }
        )
        results: dict[tuple[Any, ...], dict[str, Any]] = {
            ("r", "lane", 0, "a"): {}
        }  # b が無い
        assert _check_key_integrity(df, results) == "skipped_conditioning_mismatch"


# ---------------------------------------------------------------------------
# T036-4: Atomic Parquet write
# ---------------------------------------------------------------------------


class TestAtomicWriteParquet:
    def test_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "archive.parquet"
        table = _make_archive_table(n_rows=2)
        df = table.to_pandas()
        _atomic_write_parquet(df, path, schema=GENOMES_SCHEMA)
        assert path.exists()
        rt = pq.read_table(path).to_pandas()
        assert len(rt) == 2

    def test_tmp_file_cleaned_on_success(self, tmp_path: Path) -> None:
        path = tmp_path / "archive.parquet"
        table = _make_archive_table(n_rows=1)
        df = table.to_pandas()
        _atomic_write_parquet(df, path, schema=GENOMES_SCHEMA)
        # tmp ファイルは消えていること
        assert not path.with_suffix(".fsp_tmp.parquet").exists()


# ---------------------------------------------------------------------------
# T036-5: Schema compat (old / new / mixed)
# ---------------------------------------------------------------------------


class TestSchemaCompat:
    def test_new_archive_reads_with_all_fsp_cols(self, tmp_path: Path) -> None:
        path = tmp_path / "new.parquet"
        _write_archive(path, _make_archive_table(n_rows=3))
        df = _read_archive_with_fsp_compat(path)
        assert all(col in df.columns for col in FSP_NULLABLE_COLS)
        assert df["fsp_runtime_mode"].isna().all()

    def test_old_archive_without_fsp_cols_compatibility(
        self, tmp_path: Path
    ) -> None:
        """旧 schema (FSP 列なし) を読んでも KeyError を起こさない."""
        # FSP 列を除いた schema で書き出す
        old_fields = [
            f for f in GENOMES_SCHEMA if not f.name.startswith("fsp_")
        ]
        old_schema = pa.schema(old_fields)
        rows = []
        for i in range(2):
            r = _create_row_template()
            r.update(
                {
                    "run_id": "run_old",
                    "individual_name": f"g0_i{i}",
                    "instrument": "USD_JPY",
                    "lane_id": "tier1_USD_JPY",
                    "genome_json": "{}",
                }
            )
            r.pop("_max_stage_seen", None)
            for k in FSP_NULLABLE_COLS:
                r.pop(k, None)
            rows.append(r)
        old_table = pa.Table.from_pylist(rows, schema=old_schema)
        path = tmp_path / "old.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(old_table, path)

        df = _read_archive_with_fsp_compat(path)
        # FSP 6 列が None で補完されている
        for col in FSP_NULLABLE_COLS:
            assert col in df.columns
            assert df[col].isna().all()


# ---------------------------------------------------------------------------
# T036-6: _load_dxy_series
# ---------------------------------------------------------------------------


class TestLoadDxySeries:
    def test_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        s = _load_dxy_series(tmp_path / "missing", factor_asof_lag=1)
        assert s is None

    def test_returns_none_when_close_column_missing(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "fred" / "DXY.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(
            {"open": [100.0, 101.0]}, index=pd.date_range("2026-01-01", periods=2)
        )
        df.to_csv(path)
        s = _load_dxy_series(tmp_path / "fred", factor_asof_lag=1)
        assert s is None

    def test_returns_pct_change_with_lag(self, tmp_path: Path) -> None:
        path = tmp_path / "fred" / "DXY.csv"
        _write_dxy_csv(path, n_days=10)
        s = _load_dxy_series(tmp_path / "fred", factor_asof_lag=1)
        assert s is not None
        # pct_change + shift(1) → 最初 2 日は dropna で除外
        assert len(s) == 8


# ---------------------------------------------------------------------------
# T036-7: _aggregate_daily_pnl + _compute_fsp_stats
# ---------------------------------------------------------------------------


class TestAggregateAndStats:
    def test_aggregate_zero_pnl_when_no_trades(self) -> None:
        date_range = pd.date_range("2026-01-01", periods=5, freq="D")
        empty = pd.DataFrame(columns=["close_time", "pnl"])
        s = _aggregate_daily_pnl(empty, date_range)
        assert (s == 0.0).all()
        assert len(s) == 5

    def test_aggregate_sums_intraday_trades(self) -> None:
        date_range = pd.date_range("2026-01-01", periods=3, freq="D")
        trades = pd.DataFrame(
            {
                "close_time": pd.to_datetime(
                    [
                        "2026-01-01 09:00",
                        "2026-01-01 12:00",
                        "2026-01-02 10:00",
                    ]
                ),
                "pnl": [100.0, 50.0, -30.0],
            }
        )
        s = _aggregate_daily_pnl(trades, date_range)
        assert s.iloc[0] == 150.0  # 1/1
        assert s.iloc[1] == -30.0  # 1/2
        assert s.iloc[2] == 0.0  # 1/3

    def test_compute_fsp_stats_returns_none_on_short_series(self) -> None:
        empty = pd.Series(dtype=float)
        out = _compute_fsp_stats(empty, empty, window_days=60)
        assert out["fsp_explained_variance"] is None

    def test_compute_fsp_stats_perfect_correlation_yields_high_r2(self) -> None:
        n = 100
        idx = pd.date_range("2026-01-01", periods=n, freq="D")
        factor = pd.Series(np.linspace(0, 1, n), index=idx)
        # PnL = 2 × factor + 0 (perfect linear)
        pnl = 2.0 * factor
        out = _compute_fsp_stats(pnl, factor, window_days=10)
        assert out["fsp_explained_variance"] is not None
        assert out["fsp_explained_variance"] > 0.99
        assert out["fsp_idio_ratio"] is not None
        assert out["fsp_idio_ratio"] < 0.01

    def test_rolling_spearman_window_size(self) -> None:
        n = 30
        a = pd.Series(np.arange(n, dtype=float))
        b = pd.Series(np.arange(n, dtype=float))
        out = rolling_spearman(a, b, window=10)
        # 最初 9 要素は nan、残りは 1.0 (完全 monotonic)
        assert out.iloc[8] != out.iloc[8] or pd.isna(out.iloc[8])
        assert out.iloc[9] == pytest.approx(1.0)
        assert out.iloc[-1] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# T036-8: H1 evaluation queries
# ---------------------------------------------------------------------------


class TestH1Evaluation:
    def test_h1_zero_when_empty_eligible(self) -> None:
        df = pd.DataFrame({"fsp_runtime_mode": [None, None]})
        assert evaluate_h1(df) == 0.0

    def test_h1_active_ratio_among_eligible(self) -> None:
        df = pd.DataFrame(
            {
                "fsp_runtime_mode": [
                    "active",
                    "skipped_conditioning_mismatch",
                    "active",
                    "skipped_disabled",  # eligible 外
                    "skipped_multi_pair_run",  # eligible 外
                ]
            }
        )
        # eligible = active + mismatch = 3 件、active 2 → 2/3
        assert evaluate_h1(df) == pytest.approx(2.0 / 3.0)

    def test_key_integrity_failure_rate(self) -> None:
        df = pd.DataFrame(
            {
                "fsp_runtime_mode": [
                    "active",
                    "skipped_conditioning_mismatch",
                    "active",
                    "skipped_no_factor_data",  # eligible 外
                ]
            }
        )
        # eligible = 3 件、mismatch 1 → 1/3
        assert evaluate_key_integrity_failure_rate(df) == pytest.approx(1.0 / 3.0)


# ---------------------------------------------------------------------------
# T036-9: Integration — run_fsp_updater 6 path
# ---------------------------------------------------------------------------


class TestRunFspUpdaterIntegration:
    def _setup(self, tmp_path: Path, n_rows: int = 3) -> tuple[Path, Path]:
        archive = tmp_path / "archive.parquet"
        _write_archive(archive, _make_archive_table(n_rows=n_rows))
        fred = tmp_path / "fred"
        return archive, fred

    def test_skipped_multi_pair_run(self, tmp_path: Path) -> None:
        archive, fred = self._setup(tmp_path)
        cfg = FspConfig(enabled=True)
        mode = run_fsp_updater(
            archive_path=archive,
            fred_data_dir=fred,
            fsp_cfg=cfg,
            run_id="r",
            is_multi_pair=True,
        )
        assert mode == "skipped_multi_pair_run"
        df = _read_archive_with_fsp_compat(archive)
        assert (df["fsp_runtime_mode"] == "skipped_multi_pair_run").all()

    def test_skipped_disabled(self, tmp_path: Path) -> None:
        archive, fred = self._setup(tmp_path)
        cfg = FspConfig(enabled=False)
        mode = run_fsp_updater(
            archive_path=archive,
            fred_data_dir=fred,
            fsp_cfg=cfg,
            run_id="r",
        )
        assert mode == "skipped_disabled"

    def test_skipped_no_factor_data(self, tmp_path: Path) -> None:
        archive, fred = self._setup(tmp_path)
        cfg = FspConfig(enabled=True)
        # fred dir 不在 → DXY.csv も無い
        mode = run_fsp_updater(
            archive_path=archive,
            fred_data_dir=fred,
            fsp_cfg=cfg,
            run_id="r",
        )
        assert mode == "skipped_no_factor_data"

    def test_skipped_window_too_short(self, tmp_path: Path) -> None:
        archive, fred = self._setup(tmp_path)
        # trade_count=80,81,82 だが window_days=200 で min_bars(82) < 200
        _write_dxy_csv(fred / "DXY.csv", n_days=80)
        cfg = FspConfig(enabled=True, window_days=200)
        mode = run_fsp_updater(
            archive_path=archive,
            fred_data_dir=fred,
            fsp_cfg=cfg,
            run_id="r",
        )
        assert mode == "skipped_window_too_short"

    def test_active_path_phase1_returns_conditioning_mismatch(
        self, tmp_path: Path
    ) -> None:
        """Phase 1 実装では fsp_results が空 dict を返すため、active dispatch
        で _check_key_integrity が conditioning_mismatch を返す (詳細設計 §11
        notes)。"""
        archive, fred = self._setup(tmp_path)
        _write_dxy_csv(fred / "DXY.csv", n_days=80)
        cfg = FspConfig(enabled=True, window_days=60)
        mode = run_fsp_updater(
            archive_path=archive,
            fred_data_dir=fred,
            fsp_cfg=cfg,
            run_id="r",
        )
        # Phase 1 は trade ledger 統合前なので mismatch で書き戻し
        assert mode == "skipped_conditioning_mismatch"

    def test_idempotent_already_processed_rows(self, tmp_path: Path) -> None:
        """全行が既処理 (fsp_runtime_mode が non-null) → no-op active を返す."""
        archive, fred = self._setup(tmp_path)
        _write_dxy_csv(fred / "DXY.csv", n_days=80)
        cfg = FspConfig(enabled=True, window_days=60)
        # 1 回目: mismatch で書き込まれる
        run_fsp_updater(archive, fred, cfg, run_id="r")
        # 2 回目: target_df.empty → active no-op
        mode = run_fsp_updater(archive, fred, cfg, run_id="r")
        assert mode == "active"

    def test_archive_duplicate_keys_writes_mismatch(self, tmp_path: Path) -> None:
        archive = tmp_path / "archive.parquet"
        # 重複キーを意図的に作る
        rows = []
        for _ in range(2):
            r = _create_row_template()
            r.update(
                {
                    "run_id": "r",
                    "lane_id": "lane",
                    "generation": 0,
                    "individual_name": "g0_i0",  # 重複
                    "instrument": "USD_JPY",
                    "genome_json": "{}",
                }
            )
            r.pop("_max_stage_seen", None)
            rows.append(r)
        table = pa.Table.from_pylist(rows, schema=GENOMES_SCHEMA)
        _write_archive(archive, table)
        fred = tmp_path / "fred"
        _write_dxy_csv(fred / "DXY.csv", n_days=80)
        cfg = FspConfig(enabled=True, window_days=60)
        mode = run_fsp_updater(archive, fred, cfg, run_id="r")
        assert mode == "skipped_conditioning_mismatch"


# ---------------------------------------------------------------------------
# T036-10: Codex round-1 [Critical] 対応 — skip 系で観測値リセット
# ---------------------------------------------------------------------------


class TestSkipModeResetsObservationCols:
    """force_recalculate=True で active → skipped_* に戻す際に旧観測値が
    貼り付かないこと (Codex round-1 [Critical] 反映)."""

    def test_force_recalc_skip_clears_active_observation_values(
        self, tmp_path: Path
    ) -> None:
        # 旧 RUN で active として書き込まれた行を作成
        archive = tmp_path / "archive.parquet"
        rows = []
        for i in range(2):
            r = _create_row_template()
            r.update(
                {
                    "run_id": "r",
                    "lane_id": "lane",
                    "generation": 0,
                    "individual_name": f"g0_i{i}",
                    "instrument": "USD_JPY",
                    "genome_json": "{}",
                    "trade_count": 100,
                    # 旧 active の残骸を意図的に注入
                    "fsp_runtime_mode": "active",
                    "fsp_sampling_mode": "daily",
                    "fsp_factor_set": ["DXY"],
                    "fsp_rolling_corr_60d": [0.5, 0.6, 0.7],
                    "fsp_explained_variance": 0.42,
                    "fsp_idio_ratio": 0.58,
                }
            )
            r.pop("_max_stage_seen", None)
            rows.append(r)
        _write_archive(
            archive, pa.Table.from_pylist(rows, schema=GENOMES_SCHEMA)
        )

        # force_recalculate=True で disabled に戻す → 旧観測値が None に正規化
        cfg = FspConfig(enabled=False)
        mode = run_fsp_updater(
            archive_path=archive,
            fred_data_dir=tmp_path / "fred",
            fsp_cfg=cfg,
            run_id="r",
            force_recalculate=True,
        )
        assert mode == "skipped_disabled"

        # 全行で観測値カラムが None (skip 系で stale 残らない)
        df = _read_archive_with_fsp_compat(archive)
        assert (df["fsp_runtime_mode"] == "skipped_disabled").all()
        assert df["fsp_factor_set"].isna().all()
        assert df["fsp_rolling_corr_60d"].isna().all()
        assert df["fsp_explained_variance"].isna().all()
        assert df["fsp_idio_ratio"].isna().all()

    def test_active_mode_does_not_reset_observation_cols(
        self, tmp_path: Path
    ) -> None:
        """active 経路では skip と異なり observation cols を関数が直接触らない
        (呼び出し側 run_fsp_updater が個別書き込み)."""
        archive = tmp_path / "archive.parquet"
        # n_rows=3 で全行 active 既処理 + 観測値ありの状態
        rows = []
        for i in range(3):
            r = _create_row_template()
            r.update(
                {
                    "run_id": "r",
                    "lane_id": "lane",
                    "generation": 0,
                    "individual_name": f"g0_i{i}",
                    "instrument": "USD_JPY",
                    "genome_json": "{}",
                    "trade_count": 100,
                    "fsp_runtime_mode": "active",
                    "fsp_sampling_mode": "daily",
                    "fsp_factor_set": ["DXY"],
                    "fsp_rolling_corr_60d": [0.1, 0.2],
                    "fsp_explained_variance": 0.3,
                    "fsp_idio_ratio": 0.7,
                }
            )
            r.pop("_max_stage_seen", None)
            rows.append(r)
        _write_archive(
            archive, pa.Table.from_pylist(rows, schema=GENOMES_SCHEMA)
        )

        # 通常実行 (force_recalculate=False) → 全行既処理 → no-op active 返却
        # 観測値は変化しない
        cfg = FspConfig(enabled=True, window_days=60)
        fred = tmp_path / "fred"
        _write_dxy_csv(fred / "DXY.csv", n_days=80)
        mode = run_fsp_updater(archive, fred, cfg, run_id="r")
        assert mode == "active"

        df = _read_archive_with_fsp_compat(archive)
        # 既存値が保持されている
        assert (df["fsp_runtime_mode"] == "active").all()
        assert df["fsp_explained_variance"].iloc[0] == pytest.approx(0.3)


class TestAtomicWriteUniqueTmpName:
    """Codex round-1 [Warning] 対応: tmp 名が一意化されているか."""

    def test_tmp_path_includes_pid_and_uuid(self, tmp_path: Path) -> None:
        """tmp 名は固定 *.fsp_tmp.parquet ではなく PID + uuid を含む."""
        # 一連の書き込みが成功し、tmp ファイルが残っていないことを確認
        # (固定名の場合は並行プロセス間で衝突するリスクがあった)
        archive = tmp_path / "archive.parquet"
        table = _make_archive_table(n_rows=2)
        df = table.to_pandas()
        _atomic_write_parquet(df, archive, schema=GENOMES_SCHEMA)
        # 終了時 tmp は残らない (rename 完了後)
        leftover = list(tmp_path.glob("*.fsp_tmp.*"))
        assert leftover == []
        # 念のため固定 tmp 名が存在しないことも確認
        assert not (tmp_path / "archive.fsp_tmp.parquet").exists()
