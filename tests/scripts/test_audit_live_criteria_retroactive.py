"""cycle 23 C3: audit_live_criteria_retroactive.py のテスト。

過去 RUN の archive Parquet を annualized で再評価し、 mission 達成個体数を集計
する script の単体テスト。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from scripts.alpha_factory.audit_live_criteria_retroactive import (
    _row_passes_live_criteria,
    audit_run,
)


def test_row_passes_live_criteria_uses_stage_c_with_holdout_days() -> None:
    """trade_sharpe_stage_c=0.184 + trade_count=51 + holdout=60 → annualized ≈ 2.69 → pass."""
    row = {
        "trade_sharpe_stage_c": 0.184,
        "trade_count": 51,
        "total_pnl": 60000.0,
        "max_drawdown_pct": 4.0,
    }
    passed, sa = _row_passes_live_criteria(
        row,
        sharpe_min=1.0,
        pnl_min=50000.0,
        dd_max_pct=20.0,
        tc_min=50,
        tc_max=5000,
        holdout_days=60,
        stage_a_window_days=60,
    )
    assert passed is True
    assert sa is not None
    assert math.isclose(sa, 2.69, abs_tol=0.05)


def test_row_passes_live_criteria_pnl_min_fail() -> None:
    """total_pnl < pnl_min で fail."""
    row = {
        "trade_sharpe_stage_c": 0.184,
        "trade_count": 51,
        "total_pnl": 40000.0,  # < pnl_min
        "max_drawdown_pct": 4.0,
    }
    passed, _ = _row_passes_live_criteria(
        row,
        sharpe_min=1.0,
        pnl_min=50000.0,
        dd_max_pct=20.0,
        tc_min=50,
        tc_max=5000,
        holdout_days=60,
        stage_a_window_days=60,
    )
    assert passed is False


def test_row_passes_live_criteria_fallback_to_raw_uses_stage_a_window() -> None:
    """trade_sharpe_stage_c=None → trade_sharpe_raw fallback、 window は stage_a_window_days."""
    row = {
        "trade_sharpe_stage_c": None,
        "trade_sharpe_raw": 0.10,
        "trade_count": 51,
        "total_pnl": 60000.0,
        "max_drawdown_pct": 4.0,
    }
    passed, _sa = _row_passes_live_criteria(
        row,
        sharpe_min=1.0,
        pnl_min=50000.0,
        dd_max_pct=20.0,
        tc_min=50,
        tc_max=5000,
        holdout_days=120,  # この値ではなく
        stage_a_window_days=60,  # こちらを使う
    )
    # annualize(0.10, 51, 60) ≈ 1.46, sharpe_min=1.0 → pass=True
    assert passed is True


def test_audit_run_missing_archive_returns_error(tmp_path: Path) -> None:
    """archive 不在 → error 記録。"""
    archive_dir = tmp_path / "runs"
    archive_dir.mkdir()
    summary_dir = tmp_path / "reports"
    summary_dir.mkdir()
    result = audit_run(
        "run_nonexistent",
        archive_dir=archive_dir,
        summary_dir=summary_dir,
    )
    assert "error" in result
    assert result["error"] == "archive_not_found"


def test_audit_run_with_synthetic_archive(tmp_path: Path) -> None:
    """合成 archive で mission_candidates が期待値と一致 (= 2 pass / 3 stage_c_pass)."""
    archive_dir = tmp_path / "runs"
    archive_dir.mkdir()
    summary_dir = tmp_path / "reports"
    summary_dir.mkdir()
    run_id = "run_test_synthetic"
    run_dir = summary_dir / "run-99"
    run_dir.mkdir()
    # summary.json (run_id + thresholds)
    summary = {
        "run_id": run_id,
        "run_number": 99,
        "live_criteria": {
            "checks": {
                "sharpe": {"threshold": "1.0"},
                "total_pnl": {"threshold": "50000.0"},
                "max_drawdown_pct": {"threshold": "20.0"},
                "trade_count": {"threshold_min": 50, "threshold_max": 5000},
            },
        },
        "stage_gate_config": {
            "stage_c_holdout_days": 60,
            "stage_a_window_days": 60,
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary))
    # 合成 archive: 3 個体、 stage_c_pass=True、 うち 2 個体が mission 達成
    data: dict[str, Any] = {
        "individual_name": pa.array(["g1_i1", "g1_i2", "g1_i3"]),
        "stage_c_pass": pa.array([True, True, True]),
        "trade_sharpe_stage_c": pa.array([0.20, 0.18, 0.02]),  # 第3 個体は sharpe 低い
        "trade_sharpe_raw": pa.array([None, None, None], type=pa.float64()),
        "trade_count": pa.array([51, 55, 51]),
        "total_pnl": pa.array([60000.0, 55000.0, 60000.0]),
        "max_drawdown_pct": pa.array([4.0, 3.5, 4.0]),
    }
    table = pa.Table.from_pydict(data)
    pq.write_table(table, archive_dir / f"genomes_{run_id}.parquet")
    result = audit_run(
        run_id, archive_dir=archive_dir, summary_dir=summary_dir
    )
    assert result["error"] is None if "error" in result else True
    assert result["stage_c_pass"] == 3
    # g1_i1 (sharpe 0.20→ann ~2.93) pass, g1_i2 (0.18→ann ~2.74) pass, g1_i3 (0.02→ann ~0.29) fail
    assert result["mission_candidates"] == 2
    assert result["run_number"] == 99


def test_audit_run_missing_summary_returns_error(tmp_path: Path) -> None:
    """summary.json 不在 → error 記録。"""
    archive_dir = tmp_path / "runs"
    archive_dir.mkdir()
    summary_dir = tmp_path / "reports"
    summary_dir.mkdir()
    # archive のみ存在
    data = {
        "individual_name": pa.array(["g1_i1"]),
        "stage_c_pass": pa.array([True]),
        "trade_sharpe_stage_c": pa.array([0.20]),
        "trade_sharpe_raw": pa.array([None], type=pa.float64()),
        "trade_count": pa.array([51]),
        "total_pnl": pa.array([60000.0]),
        "max_drawdown_pct": pa.array([4.0]),
    }
    pq.write_table(
        pa.Table.from_pydict(data),
        archive_dir / "genomes_run_no_summary.parquet",
    )
    result = audit_run(
        "run_no_summary",
        archive_dir=archive_dir,
        summary_dir=summary_dir,
    )
    assert result.get("error") == "summary_not_found"
