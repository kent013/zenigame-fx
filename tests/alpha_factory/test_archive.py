"""Tests for src.alpha_factory.archive (T015 GenomeArchive + Parquet)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
from structlog.testing import capture_logs

from src.alpha_factory.archive import (
    _MAX_STAGE_KEY,
    GENOMES_SCHEMA,
    GenomeArchive,
    _compute_n_nodes,
    _create_row_template,
    _read_active_clause_from_payload,
)
from src.alpha_factory.stage_gate import CrossPairResult, StageResult
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.serialize import genome_to_dict

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _stub_genome(name: str = "g0_i0", *, n_clauses: int = 1) -> Genome:
    """最小構造の Genome (n_clauses 個 × 1 directional × 1 local_gate)."""
    clauses: list[ClauseConfig] = []
    for _ in range(n_clauses):
        clauses.append(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=1.0, params={}),),
                local_gate=(SignalConfig(name="M1", weight=0.5, params={}),),
                weight=1.0,
            )
        )
    return Genome(
        name=name,
        units=1,
        clauses=tuple(clauses),
        position=PositionConfig(
            entry_threshold=0.5, exit_threshold=0.2, max_pos=1, time_stop_min=0
        ),
        risk=RiskConfig(stop_atr=1.0, take_atr=2.0),
    )


def _stage_a_result(
    passed: bool = True, **payload_overrides: Any
) -> StageResult:
    payload: dict[str, Any] = {
        "fitness_raw": 0.3,
        "fitness_pen": 0.27,
        "size_norm": 0.1,
        "alpha_a": 0.03,
        "threshold": 0.0,
        "trade_count": 25,
        # T-sharpe Phase 1A: payload key を sharpe_raw → trade_sharpe_raw にリネーム
        "trade_sharpe_raw": 0.3,
        # T037: stage_a payload に active_clause が必ず入る契約。テストでも default で付与。
        "active_clause": 0,
    }
    payload.update(payload_overrides)
    return StageResult(
        stage="A",
        passed=passed,
        metrics={
            "stage": "A",
            "genome_name": "g0_i0",
            "n_bars": 60,
            "wall_time_seconds": 0.1,
            "payload": payload,
        },
    )


def _stage_b_result(
    passed: bool = True, **payload_overrides: Any
) -> StageResult:
    payload: dict[str, Any] = {
        "n_fold": 5,
        "n_fold_unavailable": 0,
        "oos_sharpes": (0.1, -0.2, 0.3, -0.1, 0.4),
        "median_oos_sharpe": 0.1,
        "positive_fold_ratio": 0.6,
        "dsr": None,
        "is_full_sharpe": 0.5,
        "is_full_total_pnl": 12000.0,
        "is_full_trade_count": 200,
    }
    payload.update(payload_overrides)
    return StageResult(
        stage="B",
        passed=passed,
        metrics={
            "stage": "B",
            "genome_name": "g0_i0",
            "n_bars": 7000,
            "wall_time_seconds": 1.2,
            "payload": payload,
        },
    )


def _stage_c_result(
    passed: bool = True,
    cross_pair_skipped: bool = True,
    cross_pair_passed: bool | None = None,
    **payload_overrides: Any,
) -> StageResult:
    cp: dict[str, Any] = {"skipped": True, "result": None}
    if not cross_pair_skipped:
        cp["skipped"] = False
        cp["result"] = CrossPairResult(
            target_pair="USD_JPY",
            anchor_pairs=("EUR_JPY", "AUD_JPY"),
            aggregator_name="median",
            window=(datetime(2026, 1, 1), datetime(2026, 2, 1)),
            passed=bool(cross_pair_passed),
            metrics={},
            reason_codes=(),
        )
    payload: dict[str, Any] = {
        # T-sharpe Phase 1A: Stage C の payload key も "sharpe" → "trade_sharpe_raw"
        "trade_sharpe_raw": 1.2,
        "total_pnl": 60000.0,
        "max_drawdown_frac": 0.15,
        "trade_count": 80,
        "live_criteria_pass": {},
        "intraday_compliant": True,
        "overnight_violations": 0,
        "stress": {"skipped": False},
        "cross_pair": cp,
    }
    payload.update(payload_overrides)
    return StageResult(
        stage="C",
        passed=passed,
        metrics={
            "stage": "C",
            "genome_name": "g0_i0",
            "n_bars": 1500,
            "wall_time_seconds": 0.8,
            "payload": payload,
        },
    )


def _make_archive() -> GenomeArchive:
    return GenomeArchive(run_id="run_test_20260423_180000", run_number=1)


# ---------------------------------------------------------------------------
# 1-3 schema / template
# ---------------------------------------------------------------------------


def test_schema_has_47_columns() -> None:
    # T-sharpe Phase 1A: trade_sharpe_raw + sharpe_calc_version (28→30)
    # T035: n_fold_effective + positive_fold_ratio_effective + stage_b_reason_codes (30→33)
    # T043: mission_score (33→34)
    # T036: FSP 6 列 (34→40)
    # T044: trade_sharpe_stage_b + trade_sharpe_stage_c (40→42)
    # T054: stage_b_unavailable_reason_counts (42→43)
    # T058: schema v2 4 field (genome_entry_schema_version / dataset_epoch_id
    #       / archive_role / source_stage) (43→47)
    assert len(GENOMES_SCHEMA.names) == 47
    expected = {
        "run_id", "run_number", "generation", "individual_name",
        "instrument", "lane_id", "parent_a", "parent_b", "genome_json",
        "fitness_raw", "fitness_pen", "stage_a_pass", "stage_b_pass",
        "stage_c_pass", "trade_count", "total_pnl", "sharpe", "sortino",
        "calmar", "max_drawdown_pct", "active_clause", "n_nodes",
        "bootstrap_ci_lower", "bootstrap_ci_upper", "fold_sign_ratio",
        "dsr", "ii_lite_pass", "graduated",
        # T-sharpe Phase 1A
        "trade_sharpe_raw", "sharpe_calc_version",
        # T044: stage 別 sharpe (selection と切り離した観測列)
        "trade_sharpe_stage_b", "trade_sharpe_stage_c",
        # T035: Stage B 観察可能性
        "n_fold_effective", "positive_fold_ratio_effective",
        "stage_b_reason_codes",
        # T054: Stage B fold unavailable reason 別カウント
        "stage_b_unavailable_reason_counts",
        # T043: live_criteria 4 軸 soft 合算スコア
        "mission_score",
        # T036: Factor Shadow Plane (FSP) 6 列
        "fsp_runtime_mode", "fsp_sampling_mode", "fsp_factor_set",
        "fsp_rolling_corr_60d", "fsp_explained_variance", "fsp_idio_ratio",
        # T058: schema v2 必須 4 field
        "genome_entry_schema_version", "dataset_epoch_id",
        "archive_role", "source_stage",
    }
    assert set(GENOMES_SCHEMA.names) == expected


def test_template_matches_schema_keys() -> None:
    template = _create_row_template()
    assert set(template.keys()) == set(GENOMES_SCHEMA.names)


def test_template_default_values() -> None:
    t = _create_row_template()
    # nullable -> None
    for k in (
        "parent_a", "parent_b", "sharpe", "sortino", "calmar",
        "bootstrap_ci_lower", "bootstrap_ci_upper", "fold_sign_ratio",
        "dsr", "ii_lite_pass",
        # T-sharpe Phase 1A: trade_sharpe_raw も nullable -> None
        "trade_sharpe_raw",
        # T044: stage 別 sharpe
        "trade_sharpe_stage_b", "trade_sharpe_stage_c",
        # T035
        "n_fold_effective", "positive_fold_ratio_effective",
        "stage_b_reason_codes",
        # T043: mission_score (Stage C 評価時のみ書き込み)
        "mission_score",
        # T058: archive_role / source_stage は T066 / T063-T064 で書込、 default None
        "archive_role", "source_stage",
    ):
        assert t[k] is None, f"{k} should default to None"
    # non-null bool -> False
    for k in ("stage_a_pass", "stage_b_pass", "stage_c_pass", "graduated"):
        assert t[k] is False
    # non-null int -> 0
    for k in (
        "run_number", "generation", "trade_count", "active_clause", "n_nodes",
    ):
        assert t[k] == 0
    # non-null float -> 0.0
    for k in (
        "fitness_raw", "fitness_pen", "total_pnl", "max_drawdown_pct",
    ):
        assert t[k] == 0.0
    # non-null string -> ""
    for k in (
        "run_id", "individual_name", "instrument", "lane_id", "genome_json",
    ):
        assert t[k] == ""


# ---------------------------------------------------------------------------
# 4-7 collect_stage_a
# ---------------------------------------------------------------------------


def test_collect_stage_a_partial_fill() -> None:
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "tier1_USD_JPY", 0, _stage_a_result(),
                         instrument="USD_JPY")
    row = arc._rows[("tier1_USD_JPY", 0, "g0_i0")]
    assert row["run_id"] == "run_test_20260423_180000"
    assert row["run_number"] == 1
    assert row["generation"] == 0
    assert row["individual_name"] == "g0_i0"
    assert row["instrument"] == "USD_JPY"
    assert row["lane_id"] == "tier1_USD_JPY"
    assert row["fitness_raw"] == pytest.approx(0.3)
    assert row["fitness_pen"] == pytest.approx(0.27)
    assert row["stage_a_pass"] is True
    assert row["trade_count"] == 25
    # T-sharpe Phase 1A: trade_sharpe_raw に書き込み、legacy sharpe は v2 archive で None
    assert row["trade_sharpe_raw"] == pytest.approx(0.3)
    assert row["sharpe_calc_version"] == "v2_trade_level"
    assert row["sharpe"] is None
    # 上書きされていない列は default のまま
    assert row["stage_b_pass"] is False
    assert row["stage_c_pass"] is False


def test_collect_stage_a_n_nodes_computed() -> None:
    arc = _make_archive()
    g = _stub_genome(n_clauses=2)  # 2 clauses × (1 dir + 1 gate) = 4 nodes
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(), instrument="USD_JPY")
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["n_nodes"] == 4
    # _compute_n_nodes 単体テスト
    assert _compute_n_nodes(g) == 4


def test_collect_stage_a_active_clause_from_payload() -> None:
    """T037: archive `active_clause` 列は Stage A payload の値を書き写す。"""
    arc = _make_archive()
    arc.collect_stage_a(
        _stub_genome(), "lane", 0,
        _stage_a_result(active_clause=3),
        instrument="USD_JPY",
    )
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["active_clause"] == 3


def test_collect_stage_a_active_clause_zero_when_payload_missing() -> None:
    """T037: payload に active_clause が無い場合は 0 (defensive)."""
    arc = _make_archive()
    # _stage_a_result の default に active_clause=0 が入るが、明示削除して検証
    sa = _stage_a_result()
    payload = sa.metrics["payload"]
    assert isinstance(payload, dict)
    payload.pop("active_clause", None)
    arc.collect_stage_a(_stub_genome(), "lane", 0, sa, instrument="USD_JPY")
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["active_clause"] == 0


def test_read_active_clause_from_payload_handles_invalid_inputs() -> None:
    """T037: payload helper は bool/non-int/負値 を 0 にクリップ."""
    assert _read_active_clause_from_payload({"active_clause": 5}) == 5
    assert _read_active_clause_from_payload({"active_clause": 0}) == 0
    assert _read_active_clause_from_payload({"active_clause": -1}) == 0
    assert _read_active_clause_from_payload({"active_clause": True}) == 0
    assert _read_active_clause_from_payload({"active_clause": "3"}) == 0
    assert _read_active_clause_from_payload({}) == 0


def test_collect_stage_a_genome_json_roundtrip() -> None:
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    row = arc._rows[("lane", 0, "g0_i0")]
    parsed = json.loads(row["genome_json"])
    assert parsed == genome_to_dict(g)


# ---------------------------------------------------------------------------
# 8-10 collect_stage_b
# ---------------------------------------------------------------------------


def test_collect_stage_b_records_to_separate_columns() -> None:
    """T044: Stage B の is_full_sharpe は trade_sharpe_stage_b に書き込み、
    trade_sharpe_raw (= Stage A 値) は不変、total_pnl / trade_count も Stage A
    値を保持する (selection 基準と整合)。"""
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    # Stage A 値を確認
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["trade_sharpe_raw"] == pytest.approx(0.3)  # Stage A 値
    assert row["total_pnl"] == 0.0  # Stage A 期間では未集計 (新規行 default)
    arc.collect_stage_b(g, "lane", 0, _stage_b_result())
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["stage_b_pass"] is True
    # T044: Stage A 値は不変
    assert row["trade_sharpe_raw"] == pytest.approx(0.3)
    assert row["sharpe_calc_version"] == "v2_trade_level"
    # T044: Stage B IS sharpe は新列で観測可能
    assert row["trade_sharpe_stage_b"] == pytest.approx(0.5)


def test_collect_stage_b_fold_sign_ratio_from_oos_sharpes() -> None:
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    # oos_sharpes = (0.1, -0.2, 0.3, -0.1, 0.4) → 反転 4 / (5-1) = 1.0
    arc.collect_stage_b(g, "lane", 0, _stage_b_result())
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["fold_sign_ratio"] == pytest.approx(1.0)


def test_collect_stage_b_no_oos_sharpes_yields_none() -> None:
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    arc.collect_stage_b(g, "lane", 0, _stage_b_result(oos_sharpes=()))
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["fold_sign_ratio"] is None


# ---------------------------------------------------------------------------
# 11-14 collect_stage_c
# ---------------------------------------------------------------------------


def test_collect_stage_c_max_drawdown_pct_x100() -> None:
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    arc.collect_stage_c(g, "lane", 0, _stage_c_result())
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["max_drawdown_pct"] == pytest.approx(15.0)  # 0.15 * 100
    assert row["stage_c_pass"] is True


def test_collect_stage_c_writes_sharpe_to_stage_c_column() -> None:
    """T044: Stage C base sharpe は trade_sharpe_stage_c 列に書き込み、
    trade_sharpe_raw (= Stage A 値) は不変。"""
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    arc.collect_stage_c(g, "lane", 0, _stage_c_result())
    row = arc._rows[("lane", 0, "g0_i0")]
    # Stage A 値が固定
    assert row["trade_sharpe_raw"] == pytest.approx(0.3)
    # Stage C base sharpe (= _stage_c_result default 1.2) が新列に
    assert row["trade_sharpe_stage_c"] == pytest.approx(1.2)


def test_collect_stage_b_then_c_sharpe_columns_independent() -> None:
    """T044: Stage A → B → C の sharpe が 3 列で独立に保持される (selection
    基準 trade_sharpe_raw = Stage A 値が一貫して保たれる)。"""
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    arc.collect_stage_b(g, "lane", 0, _stage_b_result())
    arc.collect_stage_c(g, "lane", 0, _stage_c_result())
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["trade_sharpe_raw"] == pytest.approx(0.3)  # Stage A
    assert row["trade_sharpe_stage_b"] == pytest.approx(0.5)  # Stage B
    assert row["trade_sharpe_stage_c"] == pytest.approx(1.2)  # Stage C


def test_collect_stage_c_ii_lite_pass_skipped() -> None:
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    arc.collect_stage_c(g, "lane", 0,
                        _stage_c_result(cross_pair_skipped=True))
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["ii_lite_pass"] is None


def test_collect_stage_c_ii_lite_pass_true() -> None:
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    arc.collect_stage_c(g, "lane", 0,
                        _stage_c_result(cross_pair_skipped=False,
                                        cross_pair_passed=True))
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["ii_lite_pass"] is True


def test_collect_stage_c_ii_lite_pass_false() -> None:
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    arc.collect_stage_c(g, "lane", 0,
                        _stage_c_result(cross_pair_skipped=False,
                                        cross_pair_passed=False))
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["ii_lite_pass"] is False


# T043: mission_score 伝搬テスト ===============================================


def test_collect_stage_c_writes_mission_score_from_payload() -> None:
    """Stage C payload に mission_score があれば archive 行に書き写される。"""
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    arc.collect_stage_c(
        g, "lane", 0,
        _stage_c_result(mission_score=0.42),
    )
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["mission_score"] == pytest.approx(0.42, abs=1e-9)


def test_collect_stage_c_mission_score_none_when_payload_missing() -> None:
    """payload に mission_score が無ければ None (Stage A のみで終わる行と同等)."""
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    # _stage_c_result は default で mission_score を入れていない
    arc.collect_stage_c(g, "lane", 0, _stage_c_result())
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["mission_score"] is None


def test_collect_stage_a_only_leaves_mission_score_none() -> None:
    """Stage C を呼ばなければ mission_score は default の None のまま."""
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["mission_score"] is None


# ---------------------------------------------------------------------------
# 15-16 mark_graduated
# ---------------------------------------------------------------------------


def test_mark_graduated_sets_flag() -> None:
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    arc.mark_graduated("lane", 0, "g0_i0")
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["graduated"] is True


def test_mark_graduated_unknown_individual_raises() -> None:
    arc = _make_archive()
    with pytest.raises(KeyError):
        arc.mark_graduated("lane", 0, "missing")


# ---------------------------------------------------------------------------
# 17-19 flush / load
# ---------------------------------------------------------------------------


def test_flush_creates_parquet_file(tmp_path: Path) -> None:
    arc = _make_archive()
    arc.collect_stage_a(_stub_genome(), "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    out = arc.flush(tmp_path)
    assert out == tmp_path / "genomes_run_test_20260423_180000.parquet"
    assert out.exists()


def test_flush_load_roundtrip(tmp_path: Path) -> None:
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY", parent_a="p_a", parent_b="p_b")
    arc.collect_stage_b(g, "lane", 0, _stage_b_result())
    arc.collect_stage_c(g, "lane", 0,
                        _stage_c_result(cross_pair_skipped=False,
                                        cross_pair_passed=True))
    arc.mark_graduated("lane", 0, "g0_i0")
    out = arc.flush(tmp_path)

    table = GenomeArchive.load(out)
    assert table.num_rows == 1
    d = table.to_pylist()[0]
    assert d["individual_name"] == "g0_i0"
    assert d["lane_id"] == "lane"
    assert d["instrument"] == "USD_JPY"
    assert d["parent_a"] == "p_a"
    assert d["parent_b"] == "p_b"
    assert d["stage_a_pass"] is True
    assert d["stage_b_pass"] is True
    assert d["stage_c_pass"] is True
    assert d["ii_lite_pass"] is True
    assert d["graduated"] is True
    assert d["max_drawdown_pct"] == pytest.approx(15.0)
    assert d["fold_sign_ratio"] == pytest.approx(1.0)
    # T044: trade_sharpe_raw は Stage A 値で固定 (上書きされない)
    assert d["trade_sharpe_raw"] == pytest.approx(0.3)
    # T044: stage 別 sharpe は別列で観測可能
    assert d["trade_sharpe_stage_b"] == pytest.approx(0.5)
    assert d["trade_sharpe_stage_c"] == pytest.approx(1.2)
    assert d["sharpe_calc_version"] == "v2_trade_level"
    assert d["total_pnl"] == pytest.approx(60000.0)
    assert d["trade_count"] == 80


def test_flush_excludes_max_stage_seen(tmp_path: Path) -> None:
    arc = _make_archive()
    arc.collect_stage_a(_stub_genome(), "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    out = arc.flush(tmp_path)
    table = GenomeArchive.load(out)
    assert _MAX_STAGE_KEY not in table.column_names
    assert set(table.column_names) == set(GENOMES_SCHEMA.names)


# ---------------------------------------------------------------------------
# 20-22 monotonic enrich (重複 collect ポリシー)
# ---------------------------------------------------------------------------


def test_same_stage_recollect_overwrites_with_warn() -> None:
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(fitness_raw=0.1),
                         instrument="USD_JPY")
    with capture_logs() as logs:
        arc.collect_stage_a(g, "lane", 0, _stage_a_result(fitness_raw=0.5),
                             instrument="USD_JPY")
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["fitness_raw"] == pytest.approx(0.5)
    assert any(
        log["event"] == "archive.same_stage_recollect" for log in logs
    )


def test_stage_regression_ignored_with_warn() -> None:
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    arc.collect_stage_b(g, "lane", 0, _stage_b_result())
    with capture_logs() as logs:
        arc.collect_stage_a(g, "lane", 0, _stage_a_result(fitness_raw=99.0),
                             instrument="USD_JPY")
    # T044: trade_sharpe_raw は Stage A 値 (0.3) で確定、Stage A 再記録は ignored
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["trade_sharpe_raw"] == pytest.approx(0.3)
    # T044: Stage B 値は別列で保持
    assert row["trade_sharpe_stage_b"] == pytest.approx(0.5)
    # fitness_raw は 99.0 で上書きされていない
    assert row["fitness_raw"] != pytest.approx(99.0)
    assert any(
        log["event"] == "archive.stage_regression_ignored" for log in logs
    )


def test_stage_enrich_progresses() -> None:
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    arc.collect_stage_b(g, "lane", 0, _stage_b_result())
    arc.collect_stage_c(g, "lane", 0, _stage_c_result())
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["stage_a_pass"] is True
    assert row["stage_b_pass"] is True
    assert row["stage_c_pass"] is True
    # T044: trade_sharpe_raw は Stage A 値で固定、stage 別 sharpe は別列
    assert row["trade_sharpe_raw"] == pytest.approx(0.3)
    assert row["trade_sharpe_stage_b"] == pytest.approx(0.5)
    assert row["trade_sharpe_stage_c"] == pytest.approx(1.2)
    assert row["sharpe_calc_version"] == "v2_trade_level"
    # Stage C の total_pnl / trade_count / max_drawdown_pct は live_criteria 評価対象
    # のため Stage C 値で上書き継続 (T044 の scope は trade_sharpe_raw のみ)
    assert row["total_pnl"] == pytest.approx(60000.0)
    assert row["trade_count"] == 80
    # Stage B の fold_sign_ratio は保持
    assert row["fold_sign_ratio"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 23 composite key
# ---------------------------------------------------------------------------


def test_composite_key_separates_generations() -> None:
    arc = _make_archive()
    g0 = _stub_genome("g0_i0")
    g1 = _stub_genome("g0_i0")  # 同名だが別 generation
    arc.collect_stage_a(g0, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    arc.collect_stage_a(g1, "lane", 1, _stage_a_result(fitness_raw=0.9),
                         instrument="USD_JPY")
    assert ("lane", 0, "g0_i0") in arc._rows
    assert ("lane", 1, "g0_i0") in arc._rows
    assert arc._rows[("lane", 0, "g0_i0")]["fitness_raw"] != pytest.approx(0.9)
    assert arc._rows[("lane", 1, "g0_i0")]["fitness_raw"] == pytest.approx(0.9)


def test_composite_key_separates_lanes() -> None:
    arc = _make_archive()
    g = _stub_genome("g0_i0")
    arc.collect_stage_a(g, "tier1_USD_JPY", 0, _stage_a_result(),
                         instrument="USD_JPY")
    arc.collect_stage_a(g, "tier1_EUR_JPY", 0,
                        _stage_a_result(fitness_raw=0.7),
                         instrument="EUR_JPY")
    assert ("tier1_USD_JPY", 0, "g0_i0") in arc._rows
    assert ("tier1_EUR_JPY", 0, "g0_i0") in arc._rows


def test_collect_stage_b_new_row_requires_instrument() -> None:
    arc = _make_archive()
    g = _stub_genome()
    with pytest.raises(ValueError, match="instrument is required"):
        arc.collect_stage_b(g, "lane", 0, _stage_b_result(), instrument=None)


def test_collect_stage_c_new_row_requires_instrument() -> None:
    arc = _make_archive()
    g = _stub_genome()
    with pytest.raises(ValueError, match="instrument is required"):
        arc.collect_stage_c(g, "lane", 0, _stage_c_result(), instrument=None)


def test_mark_graduated_takes_lane_id() -> None:
    arc = _make_archive()
    g = _stub_genome("g0_i0")
    arc.collect_stage_a(g, "lane_a", 0, _stage_a_result(),
                         instrument="USD_JPY")
    arc.collect_stage_a(g, "lane_b", 0, _stage_a_result(),
                         instrument="EUR_JPY")
    arc.mark_graduated("lane_a", 0, "g0_i0")
    assert arc._rows[("lane_a", 0, "g0_i0")]["graduated"] is True
    assert arc._rows[("lane_b", 0, "g0_i0")]["graduated"] is False


# ---------------------------------------------------------------------------
# 24-26 wrong-stage exceptions
# ---------------------------------------------------------------------------


def test_collect_stage_a_wrong_stage_raises() -> None:
    arc = _make_archive()
    g = _stub_genome()
    with pytest.raises(ValueError, match="expected stage='A'"):
        arc.collect_stage_a(g, "lane", 0, _stage_b_result(),
                             instrument="USD_JPY")


def test_collect_stage_b_wrong_stage_raises() -> None:
    arc = _make_archive()
    g = _stub_genome()
    with pytest.raises(ValueError, match="expected stage='B'"):
        arc.collect_stage_b(g, "lane", 0, _stage_a_result(),
                             instrument="USD_JPY")
    with pytest.raises(ValueError, match="expected stage='B'"):
        arc.collect_stage_b(g, "lane", 0, _stage_c_result(),
                             instrument="USD_JPY")


def test_collect_stage_c_wrong_stage_raises() -> None:
    arc = _make_archive()
    g = _stub_genome()
    with pytest.raises(ValueError, match="expected stage='C'"):
        arc.collect_stage_c(g, "lane", 0, _stage_a_result(),
                             instrument="USD_JPY")
    with pytest.raises(ValueError, match="expected stage='C'"):
        arc.collect_stage_c(g, "lane", 0, _stage_b_result(),
                             instrument="USD_JPY")


# ---------------------------------------------------------------------------
# 27-30 defensive get / type guards
# ---------------------------------------------------------------------------


def test_payload_missing_keys_defensive_get() -> None:
    """payload に key が無い場合、default 値（0.0 / 0 / None）が入って例外なし."""
    arc = _make_archive()
    g = _stub_genome()
    sr = StageResult(
        stage="A", passed=False,
        metrics={"stage": "A", "genome_name": "g0_i0",
                 "n_bars": 0, "wall_time_seconds": 0.0,
                 "payload": {}},  # 全キー欠落
    )
    arc.collect_stage_a(g, "lane", 0, sr, instrument="USD_JPY")
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["fitness_raw"] == 0.0
    assert row["fitness_pen"] == 0.0
    assert row["trade_count"] == 0
    assert row["sharpe"] is None


def test_cross_pair_result_invalid_type_yields_none() -> None:
    """cross_pair.result が CrossPairResult でない型なら ii_lite_pass=None."""
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    sr = StageResult(
        stage="C", passed=True,
        metrics={
            "stage": "C", "genome_name": "g0_i0",
            "n_bars": 1500, "wall_time_seconds": 0.8,
            "payload": {
                "sharpe": 1.0, "total_pnl": 100.0,
                "max_drawdown_frac": 0.1, "trade_count": 50,
                "cross_pair": {"skipped": False, "result": "not_a_result_obj"},
            },
        },
    )
    arc.collect_stage_c(g, "lane", 0, sr)
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["ii_lite_pass"] is None


def test_oos_sharpes_invalid_element_type_yields_none() -> None:
    """oos_sharpes に文字列要素が混ざると fold_sign_ratio=None."""
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    sr = _stage_b_result(oos_sharpes=(0.1, "bad", 0.3))
    arc.collect_stage_b(g, "lane", 0, sr)
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["fold_sign_ratio"] is None


def test_flush_extra_key_in_row_raises(tmp_path: Path) -> None:
    arc = _make_archive()
    arc.collect_stage_a(_stub_genome(), "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    # 強制的に schema 外 key を注入
    arc._rows[("lane", 0, "g0_i0")]["__rogue"] = 1
    with pytest.raises(ValueError, match="row keys mismatch"):
        arc.flush(tmp_path)


# ---------------------------------------------------------------------------
# Schema attribute checks
# ---------------------------------------------------------------------------


def test_schema_nullable_attributes() -> None:
    """nullable 設定が schema doc と整合しているか."""
    nullable_cols = {
        "parent_a", "parent_b", "sharpe", "sortino", "calmar",
        "bootstrap_ci_lower", "bootstrap_ci_upper", "fold_sign_ratio",
        "dsr", "ii_lite_pass",
        # T-sharpe Phase 1A
        "trade_sharpe_raw", "sharpe_calc_version",
        # T044: stage 別 sharpe (Stage B/C 評価時のみ書き込み)
        "trade_sharpe_stage_b", "trade_sharpe_stage_c",
        # T035
        "n_fold_effective", "positive_fold_ratio_effective",
        "stage_b_reason_codes",
        # T054: Stage B fold unavailable reason 別カウント (JSON string, nullable)
        "stage_b_unavailable_reason_counts",
        # T043: Stage C 評価時のみ書き込まれるため nullable
        "mission_score",
        # T036: FSP 6 列 (post-RUN updater が書き込む、collect_stage_* では null)
        "fsp_runtime_mode", "fsp_sampling_mode", "fsp_factor_set",
        "fsp_rolling_corr_60d", "fsp_explained_variance", "fsp_idio_ratio",
        # T058: archive_role (T066 で書込) / source_stage (T063-T064 で書込) は
        # null 許容。 genome_entry_schema_version / dataset_epoch_id は non-null。
        "archive_role", "source_stage",
    }
    for f in GENOMES_SCHEMA:
        if f.name in nullable_cols:
            assert f.nullable, f"{f.name} should be nullable"
        else:
            assert not f.nullable, f"{f.name} should be non-null"


def test_schema_field_types() -> None:
    """主要カラムの型を spot-check."""
    type_map: dict[str, pa.DataType] = {
        "run_id": pa.string(),
        "run_number": pa.int32(),
        "generation": pa.int32(),
        "fitness_raw": pa.float64(),
        "stage_a_pass": pa.bool_(),
        "ii_lite_pass": pa.bool_(),
    }
    for name, expected in type_map.items():
        assert GENOMES_SCHEMA.field(name).type == expected


# ---------------------------------------------------------------------------
# T018: get_row_snapshot
# ---------------------------------------------------------------------------


def test_get_row_snapshot_returns_none_for_unknown_key() -> None:
    arc = GenomeArchive(run_id="run_x", run_number=1)
    assert arc.get_row_snapshot("tier1_EUR_JPY", 0, "nope") is None


def test_get_row_snapshot_returns_row_copy_excluding_internal_key() -> None:
    arc = GenomeArchive(run_id="run_x", run_number=1)
    g = _stub_genome("g0_i0")
    arc.collect_stage_a(
        g, "tier1_EUR_JPY", 0, _stage_a_result(),
        instrument="EUR_JPY",
        parent_a="parent_a",
        parent_b="parent_b",
    )
    snap = arc.get_row_snapshot("tier1_EUR_JPY", 0, "g0_i0")
    assert snap is not None
    assert snap["individual_name"] == "g0_i0"
    assert snap["parent_a"] == "parent_a"
    assert snap["parent_b"] == "parent_b"
    assert snap["stage_a_pass"] is True
    assert _MAX_STAGE_KEY not in snap
    # snap はコピーであり、mutate しても internal dict に影響しない
    snap["stage_a_pass"] = False
    snap2 = arc.get_row_snapshot("tier1_EUR_JPY", 0, "g0_i0")
    assert snap2 is not None
    assert snap2["stage_a_pass"] is True


# ---------------------------------------------------------------------------
# T-sharpe Phase 1A: canonical accessor (get_trade_sharpe / get_legacy_bar_sharpe)
# ---------------------------------------------------------------------------


def test_get_trade_sharpe_returns_value_for_v2_archive() -> None:
    row = {
        "trade_sharpe_raw": 0.42,
        "sharpe_calc_version": "v2_trade_level",
    }
    assert GenomeArchive.get_trade_sharpe(row) == pytest.approx(0.42)


def test_get_trade_sharpe_returns_none_when_value_missing() -> None:
    row = {
        "trade_sharpe_raw": None,
        "sharpe_calc_version": "v2_trade_level",
    }
    assert GenomeArchive.get_trade_sharpe(row) is None


def test_get_trade_sharpe_raises_for_v1_archive() -> None:
    row = {"sharpe": 18.0, "sharpe_calc_version": "v1_bar_annualized"}
    with pytest.raises(ValueError, match="v1"):
        GenomeArchive.get_trade_sharpe(row)


def test_get_trade_sharpe_treats_missing_version_as_v1() -> None:
    """sharpe_calc_version 不在 (旧 archive) → v1 として例外."""
    row = {"sharpe": 18.0}
    with pytest.raises(ValueError):
        GenomeArchive.get_trade_sharpe(row)


def test_get_legacy_bar_sharpe_returns_value_for_v1_archive() -> None:
    row = {"sharpe": 18.0, "sharpe_calc_version": "v1_bar_annualized"}
    assert GenomeArchive.get_legacy_bar_sharpe(row) == pytest.approx(18.0)


def test_get_legacy_bar_sharpe_raises_for_v2_archive() -> None:
    row = {
        "trade_sharpe_raw": 0.42,
        "sharpe_calc_version": "v2_trade_level",
    }
    with pytest.raises(ValueError, match="v2"):
        GenomeArchive.get_legacy_bar_sharpe(row)


def test_get_legacy_bar_sharpe_returns_value_when_version_missing() -> None:
    """旧 archive (sharpe_calc_version 列なし) は v1 とみなして読める."""
    row = {"sharpe": 18.0}
    assert GenomeArchive.get_legacy_bar_sharpe(row) == pytest.approx(18.0)


# T035 ========================================================================


def test_collect_stage_b_writes_reason_codes_string() -> None:
    """stage_b_reason_codes が ';' 区切り文字列として archive 行に書かれる."""
    from src.alpha_factory.archive import GenomeArchive
    from src.alpha_factory.stage_gate import StageResult

    arc = GenomeArchive(run_id="test_run", run_number=1)
    g = _stub_genome("g0_i0")
    sr = StageResult(
        stage="B",
        passed=False,
        metrics={
            "stage": "B",
            "genome_name": "g0_i0",
            "n_bars": 100,
            "wall_time_seconds": 0.1,
            "payload": {
                "n_fold": 2,
                "n_fold_unavailable": 1,
                "n_fold_effective": 1,
                "oos_sharpes": (0.5, 0.0),
                "median_oos_sharpe": 0.25,
                "positive_fold_ratio": 0.5,
                "positive_fold_ratio_effective": 1.0,
                "dsr": None,
                "is_full_sharpe": None,
                "is_full_total_pnl": None,
                "is_full_trade_count": None,
            },
        },
        reason_codes=("median_oos_sharpe<min", "all_folds_unavailable"),
    )
    arc.collect_stage_b(g, lane_id="lane1", generation=0, stage_result=sr, instrument="EUR_JPY")
    rows = list(arc._rows.values())
    assert len(rows) == 1
    row = rows[0]
    assert row["stage_b_reason_codes"] == "median_oos_sharpe<min;all_folds_unavailable"
    assert row["n_fold_effective"] == 1
    assert row["positive_fold_ratio_effective"] == 1.0


def test_collect_stage_b_writes_none_reason_codes_when_passed() -> None:
    """passed=True で reason_codes が空タプル → archive で None."""
    from src.alpha_factory.archive import GenomeArchive
    from src.alpha_factory.stage_gate import StageResult

    arc = GenomeArchive(run_id="test_run", run_number=1)
    g = _stub_genome("g0_i0")
    sr = StageResult(
        stage="B",
        passed=True,
        metrics={
            "stage": "B",
            "genome_name": "g0_i0",
            "n_bars": 100,
            "wall_time_seconds": 0.1,
            "payload": {
                "n_fold": 3,
                "n_fold_unavailable": 0,
                "n_fold_effective": 3,
                "oos_sharpes": (0.5, 0.6, 0.4),
                "median_oos_sharpe": 0.5,
                "positive_fold_ratio": 1.0,
                "positive_fold_ratio_effective": 1.0,
                "dsr": None,
                "is_full_sharpe": 0.5,
                "is_full_total_pnl": 1000.0,
                "is_full_trade_count": 50,
            },
        },
        reason_codes=(),
    )
    arc.collect_stage_b(g, lane_id="lane1", generation=0, stage_result=sr, instrument="EUR_JPY")
    rows = list(arc._rows.values())
    assert rows[0]["stage_b_reason_codes"] is None


# ---------------------------------------------------------------------------
# T058: schema v2 contract — 4 field 追加 + flush lint 連動
# ---------------------------------------------------------------------------


def _make_run_context(
    *,
    run_id: str = "run_test_20260423_180000",
    run_number: int = 1,
    dataset_epoch_id: str = "epoch_20260101_20260401",
    base_config_hash: str = "deadbeef",
    instrument: str = "USD_JPY",
):
    from src.alpha_factory.run_context import RunContext

    return RunContext(
        run_id=run_id,
        run_number=run_number,
        dataset_epoch_id=dataset_epoch_id,
        base_config_hash=base_config_hash,
        instrument=instrument,
    )


def test_t058_genomes_schema_includes_v2_required_fields() -> None:
    """T058: GENOMES_SCHEMA に v2 必須 4 field が存在する."""
    names = set(GENOMES_SCHEMA.names)
    assert "genome_entry_schema_version" in names
    assert "dataset_epoch_id" in names
    assert "archive_role" in names
    assert "source_stage" in names

    # 型検証: schema_version=int32 / 他=string
    assert GENOMES_SCHEMA.field("genome_entry_schema_version").type == pa.int32()
    assert GENOMES_SCHEMA.field("dataset_epoch_id").type == pa.string()
    assert GENOMES_SCHEMA.field("archive_role").type == pa.string()
    assert GENOMES_SCHEMA.field("source_stage").type == pa.string()

    # nullability:
    # - genome_entry_schema_version / dataset_epoch_id は non-null (必須 contract)
    # - archive_role / source_stage は T066 / T063-T064 で書込、 T058 では None 許容
    assert not GENOMES_SCHEMA.field("genome_entry_schema_version").nullable
    assert not GENOMES_SCHEMA.field("dataset_epoch_id").nullable
    assert GENOMES_SCHEMA.field("archive_role").nullable
    assert GENOMES_SCHEMA.field("source_stage").nullable


def test_t058_create_row_template_initializes_v2_fields_with_defaults() -> None:
    """T058: row template が v2 4 field を default 値で初期化する."""
    from src.alpha_factory.schema_contract import GENOME_ENTRY_SCHEMA_VERSION

    t = _create_row_template()
    assert t["genome_entry_schema_version"] == GENOME_ENTRY_SCHEMA_VERSION
    # epoch_legacy stub: T059 で deterministic 値に置換されるが、 grammar
    # [a-z0-9_]+ には適合させる (validator が grammar 違反として警告しないように)。
    assert t["dataset_epoch_id"] == "epoch_legacy"
    assert t["archive_role"] is None
    assert t["source_stage"] is None


def test_t058_genome_archive_init_with_legacy_signature_works_without_run_context() -> None:
    """T058: 既存 caller (run_context / enforcement_mode 省略) で構築可能."""
    arc = GenomeArchive(run_id="run_x", run_number=1)
    assert arc.run_context is None
    # default は LOG_ONLY
    from src.alpha_factory.schema_contract import SchemaEnforcementMode

    assert arc.enforcement_mode == SchemaEnforcementMode.LOG_ONLY


def test_t058_genome_archive_init_accepts_run_context_kwarg() -> None:
    """T058: 新 caller が run_context / enforcement_mode を kwarg で渡せる."""
    from src.alpha_factory.schema_contract import SchemaEnforcementMode

    ctx = _make_run_context()
    arc = GenomeArchive(
        run_id="run_x",
        run_number=1,
        run_context=ctx,
        enforcement_mode=SchemaEnforcementMode.FAIL_CLOSED,
    )
    assert arc.run_context is ctx
    assert arc.enforcement_mode == SchemaEnforcementMode.FAIL_CLOSED


def test_t058_flush_injects_dataset_epoch_id_from_run_context(
    tmp_path: Path,
) -> None:
    """T058: flush 時に template の "epoch_legacy" stub が RunContext の値で
    上書きされる (run_context 注入時)。"""
    ctx = _make_run_context(dataset_epoch_id="epoch_20260101_20260401")
    arc = GenomeArchive(
        run_id="run_test_20260423_180000",
        run_number=1,
        run_context=ctx,
    )
    # template default では dataset_epoch_id="epoch_legacy" だが flush で上書き
    # されるためには row が "epoch_legacy" or empty/None である必要がある。
    # _create_row_template の default が "epoch_legacy" のため、 collect_stage_a
    # で行を作った直後は "epoch_legacy"。 flush で run_context 値に上書きしたい
    # ので、 まず row を作って明示的に空文字に落としておく (実環境では legacy
    # stub と空の両方を補完したい意図、 詳細設計 行 737)。
    arc.collect_stage_a(
        _stub_genome(), "lane", 0, _stage_a_result(), instrument="USD_JPY"
    )
    arc._rows[("lane", 0, "g0_i0")]["dataset_epoch_id"] = ""
    out = arc.flush(tmp_path)

    table = GenomeArchive.load(out)
    d = table.to_pylist()[0]
    assert d["dataset_epoch_id"] == "epoch_20260101_20260401"


def test_t058_flush_keeps_epoch_legacy_when_run_context_none(
    tmp_path: Path,
) -> None:
    """T058: run_context 注入なしなら template の "epoch_legacy" stub のまま
    permanent (= T059 で deterministic 値に置換される予定)。"""
    arc = GenomeArchive(
        run_id="run_test_20260423_180000", run_number=1
    )
    arc.collect_stage_a(
        _stub_genome(), "lane", 0, _stage_a_result(), instrument="USD_JPY"
    )
    out = arc.flush(tmp_path)
    table = GenomeArchive.load(out)
    d = table.to_pylist()[0]
    # template default のまま flush
    assert d["dataset_epoch_id"] == "epoch_legacy"
    # archive_role / source_stage は T066 / T063-T064 で書込のため None
    assert d["archive_role"] is None
    assert d["source_stage"] is None
    # genome_entry_schema_version は常に 2
    assert d["genome_entry_schema_version"] == 2


def test_t058_flush_log_only_does_not_raise_for_grammar_violation(
    tmp_path: Path,
) -> None:
    """T058: LOG_ONLY mode で dataset_epoch_id grammar 違反があっても raise
    せず、 schema_lint_summary log を出して flush 完了する."""
    arc = GenomeArchive(
        run_id="run_test_20260423_180000", run_number=1
    )
    arc.collect_stage_a(
        _stub_genome(), "lane", 0, _stage_a_result(), instrument="USD_JPY"
    )
    # grammar 違反 (大文字を含む) を意図的に注入
    arc._rows[("lane", 0, "g0_i0")]["dataset_epoch_id"] = "EPOCH_BAD"

    with capture_logs() as logs:
        out = arc.flush(tmp_path)
    assert out.exists()
    # LOG_ONLY mode → schema_lint_summary が出る
    summary_logs = [
        log for log in logs if log["event"] == "archive.flush.schema_lint_summary"
    ]
    assert len(summary_logs) == 1
    assert summary_logs[0]["warning_count"] == 1
    assert summary_logs[0]["mode"] == "log_only"
    assert summary_logs[0]["run_id"] == "run_test_20260423_180000"
    # warning lint 自体も発火している (validator 内 + invalid_epoch_id event)
    assert any(
        log["event"] == "schema_contract.invalid_epoch_id" for log in logs
    )


def test_t058_flush_log_only_summary_aggregates_multiple_warnings(
    tmp_path: Path,
) -> None:
    """T058: 同一 flush で複数 row の lint warning が per-run summary に集約."""
    arc = GenomeArchive(
        run_id="run_test_20260423_180000", run_number=1
    )
    g0 = _stub_genome("g0_i0")
    g1 = _stub_genome("g0_i1")
    arc.collect_stage_a(g0, "lane", 0, _stage_a_result(), instrument="USD_JPY")
    arc.collect_stage_a(g1, "lane", 0, _stage_a_result(), instrument="USD_JPY")
    arc._rows[("lane", 0, "g0_i0")]["dataset_epoch_id"] = "BAD-1"
    arc._rows[("lane", 0, "g0_i1")]["dataset_epoch_id"] = "BAD-2"

    with capture_logs() as logs:
        arc.flush(tmp_path)
    summary_logs = [
        log for log in logs if log["event"] == "archive.flush.schema_lint_summary"
    ]
    assert len(summary_logs) == 1
    assert summary_logs[0]["warning_count"] == 2


def test_t058_flush_log_only_no_summary_when_no_warnings(
    tmp_path: Path,
) -> None:
    """T058: lint warning 0 件なら schema_lint_summary log は出ない."""
    ctx = _make_run_context(dataset_epoch_id="epoch_20260101_20260401")
    arc = GenomeArchive(
        run_id="run_test_20260423_180000",
        run_number=1,
        run_context=ctx,
    )
    arc.collect_stage_a(
        _stub_genome(), "lane", 0, _stage_a_result(), instrument="USD_JPY"
    )

    with capture_logs() as logs:
        arc.flush(tmp_path)
    summary_logs = [
        log for log in logs if log["event"] == "archive.flush.schema_lint_summary"
    ]
    assert len(summary_logs) == 0


def test_t058_flush_fail_closed_raises_on_grammar_violation(
    tmp_path: Path,
) -> None:
    """T058: FAIL_CLOSED mode で grammar 違反は SchemaContractError raise."""
    from src.alpha_factory.schema_contract import (
        SchemaContractError,
        SchemaEnforcementMode,
    )

    arc = GenomeArchive(
        run_id="run_test_20260423_180000",
        run_number=1,
        enforcement_mode=SchemaEnforcementMode.FAIL_CLOSED,
    )
    arc.collect_stage_a(
        _stub_genome(), "lane", 0, _stage_a_result(), instrument="USD_JPY"
    )
    # grammar 違反 (大文字を含む) を注入
    arc._rows[("lane", 0, "g0_i0")]["dataset_epoch_id"] = "EPOCH_BAD"
    with pytest.raises(SchemaContractError):
        arc.flush(tmp_path)


def test_t058_flush_fail_closed_passes_when_all_v2_fields_valid(
    tmp_path: Path,
) -> None:
    """T058: FAIL_CLOSED mode で v2 4 field 全部揃っていれば raise しない."""
    from src.alpha_factory.schema_contract import SchemaEnforcementMode

    ctx = _make_run_context(dataset_epoch_id="epoch_20260101_20260401")
    arc = GenomeArchive(
        run_id="run_test_20260423_180000",
        run_number=1,
        run_context=ctx,
        enforcement_mode=SchemaEnforcementMode.FAIL_CLOSED,
    )
    arc.collect_stage_a(
        _stub_genome(), "lane", 0, _stage_a_result(), instrument="USD_JPY"
    )
    out = arc.flush(tmp_path)
    assert out.exists()


def test_t058_flush_persists_v2_field_values_through_parquet_roundtrip(
    tmp_path: Path,
) -> None:
    """T058: archive_role / source_stage に手動で値を設定すると Parquet 経由
    で読み戻せる (T063-T064 / T066 で本書込される値の経路確認)."""
    arc = GenomeArchive(
        run_id="run_test_20260423_180000", run_number=1
    )
    arc.collect_stage_a(
        _stub_genome(), "lane", 0, _stage_a_result(), instrument="USD_JPY"
    )
    arc._rows[("lane", 0, "g0_i0")]["archive_role"] = "mission_pass"
    arc._rows[("lane", 0, "g0_i0")]["source_stage"] = "c"
    out = arc.flush(tmp_path)

    table = GenomeArchive.load(out)
    d = table.to_pylist()[0]
    assert d["archive_role"] == "mission_pass"
    assert d["source_stage"] == "c"
    assert d["genome_entry_schema_version"] == 2


def test_t058_flush_resets_lint_warning_count_between_flushes(
    tmp_path: Path,
) -> None:
    """T058 (Codex Round 1 [Warning] 1): 同一 GenomeArchive で連続 flush しても
    _lint_warning_count が累積汚染しないこと (= flush 開始時に reset)。"""
    arc = GenomeArchive(
        run_id="run_test_20260423_180000", run_number=1
    )
    arc.collect_stage_a(
        _stub_genome(), "lane", 0, _stage_a_result(), instrument="USD_JPY"
    )
    # 1 回目: grammar 違反を入れて summary log warning_count=1 を期待
    arc._rows[("lane", 0, "g0_i0")]["dataset_epoch_id"] = "BAD-FIRST"
    with capture_logs() as logs1:
        arc.flush(tmp_path)
    summary1 = [
        log for log in logs1 if log["event"] == "archive.flush.schema_lint_summary"
    ]
    assert len(summary1) == 1
    assert summary1[0]["warning_count"] == 1

    # 2 回目: 違反を解消、 同一 archive instance で再 flush。
    # _lint_warning_count が前回値に累積していれば 2 になるはず → reset 動作で 0 期待
    arc._rows[("lane", 0, "g0_i0")]["dataset_epoch_id"] = "epoch_legacy"
    with capture_logs() as logs2:
        arc.flush(tmp_path / "second")
    # warning 0 件なら summary log は出ない設計
    summary2 = [
        log for log in logs2 if log["event"] == "archive.flush.schema_lint_summary"
    ]
    assert len(summary2) == 0
    # 内部 counter も 0 にリセットされている
    assert arc._lint_warning_count == 0


def test_t058_genomes_schema_column_order_keeps_v2_fields_at_head() -> None:
    """T058 (Codex Round 1 [Warning] 2): set ではなく順序で v2 4 field の相対
    位置を確認 (= 詳細設計 行 672-688 の通り schema 先頭 4 列に配置)。
    schema 順序の意図しないドリフトを検知する。"""
    names = GENOMES_SCHEMA.names
    # 詳細設計通り、 schema 先頭 4 列に v2 必須 field が配置される
    assert names[0] == "genome_entry_schema_version"
    assert names[1] == "dataset_epoch_id"
    assert names[2] == "archive_role"
    assert names[3] == "source_stage"
    # v2 4 field の直後に既存 run_id 列が来る (= 既存列の相対順序を破壊しない)
    assert names[4] == "run_id"


# ---------------------------------------------------------------------------
# T058 PR 5: GenomeArchive.load tuple 受取 + v1 archive 検出
# ---------------------------------------------------------------------------


def _build_v1_archive(tmp_path: Path) -> Path:
    """T058 PR 5 test helper: v1 archive (genome_entry_schema_version 列なし) を作成."""
    import pyarrow.parquet as pq

    # v1 (legacy) schema: v2 必須 4 field を含まない最低限の table を作成
    minimal_schema = pa.schema(
        [
            pa.field("run_id", pa.string()),
            pa.field("run_number", pa.int32()),
            pa.field("individual_name", pa.string()),
        ]
    )
    table = pa.Table.from_pylist(
        [{"run_id": "run_legacy", "run_number": 1, "individual_name": "g0_i0"}],
        schema=minimal_schema,
    )
    out = tmp_path / "v1_archive.parquet"
    pq.write_table(table, out)
    return out


def test_load_backward_compat_returns_table_only_when_kwargs_omitted(
    tmp_path: Path,
) -> None:
    """既存 caller (1-arg, return_schema_version=False default) は Table 単独返却."""
    arc = _make_archive()
    arc.collect_stage_a(_stub_genome(), "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    out = arc.flush(tmp_path)

    table = GenomeArchive.load(out)
    # 旧 caller は Table 単独 (tuple ではない)
    assert isinstance(table, pa.Table)
    assert table.num_rows == 1


def test_load_mode_kwarg_alone_keeps_table_only_return_for_backward_compat(
    tmp_path: Path,
) -> None:
    """T058 PR 5 (Codex Warning 1 反映): mode 指定 + return_schema_version=False
    (default) では Table 単独返却が維持される (= 旧 caller 完全互換)。
    意図: 「mode だけ指定して fail-closed 期待」誤用を test で固定して
    将来の signature 誤理解 regression を防ぐ。"""
    from src.alpha_factory.schema_contract import SchemaEnforcementMode

    arc = _make_archive()
    arc.collect_stage_a(_stub_genome(), "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    out = arc.flush(tmp_path)
    table = GenomeArchive.load(out, mode=SchemaEnforcementMode.FAIL_CLOSED)
    # return_schema_version=False default のため Table 単独返却 (tuple ではない)
    assert isinstance(table, pa.Table)
    assert table.num_rows == 1


def test_load_with_return_schema_version_returns_tuple_for_v2_archive(
    tmp_path: Path,
) -> None:
    """v2 archive (新規 flush) は (Table, 2) を返す."""
    from src.alpha_factory.schema_contract import SchemaEnforcementMode

    arc = _make_archive()
    arc.collect_stage_a(_stub_genome(), "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    out = arc.flush(tmp_path)

    result = GenomeArchive.load(
        out, mode=SchemaEnforcementMode.LOG_ONLY, return_schema_version=True
    )
    assert isinstance(result, tuple)
    table, sv = result
    assert isinstance(table, pa.Table)
    assert sv == 2  # GENOME_ENTRY_SCHEMA_VERSION


def test_load_log_only_warns_and_returns_none_sv_for_v1_archive(
    tmp_path: Path,
) -> None:
    """LOG_ONLY mode で v1 archive を読むと warning + sv=None 返却."""
    from src.alpha_factory.schema_contract import SchemaEnforcementMode

    v1_path = _build_v1_archive(tmp_path)
    with capture_logs() as logs:
        result = GenomeArchive.load(
            v1_path,
            mode=SchemaEnforcementMode.LOG_ONLY,
            return_schema_version=True,
        )
    assert isinstance(result, tuple)
    table, sv = result
    assert sv is None
    assert table.num_rows == 1
    # warning 発火
    events = [log for log in logs if log["event"] == "archive.load.v1_archive_detected"]
    assert len(events) == 1
    assert events[0]["mode"] == "log_only"


def test_load_fail_closed_raises_on_v1_archive(tmp_path: Path) -> None:
    """FAIL_CLOSED mode で v1 archive を読むと SchemaVersionError raise."""
    from src.alpha_factory.schema_contract import (
        SchemaEnforcementMode,
        SchemaVersionError,
    )

    v1_path = _build_v1_archive(tmp_path)
    with pytest.raises(SchemaVersionError, match="v1 archive"):
        GenomeArchive.load(
            v1_path,
            mode=SchemaEnforcementMode.FAIL_CLOSED,
            return_schema_version=True,
        )


def test_load_empty_v2_archive_returns_v2_schema_version(tmp_path: Path) -> None:
    """空の v2 archive (genome_entry_schema_version 列が存在、 行 0 件) は
    fsp_updater の helper と同型の判定で v2 を返す (= FAIL_CLOSED で raise しない)."""
    import pyarrow.parquet as pq

    from src.alpha_factory.schema_contract import SchemaEnforcementMode

    # 空の v2 archive を作成 (= GENOMES_SCHEMA で 0 行 table)
    empty_table = pa.Table.from_pylist([], schema=GENOMES_SCHEMA)
    out = tmp_path / "empty_v2.parquet"
    pq.write_table(empty_table, out)

    result = GenomeArchive.load(
        out,
        mode=SchemaEnforcementMode.FAIL_CLOSED,
        return_schema_version=True,
    )
    assert isinstance(result, tuple)
    _table, sv = result
    assert sv == 2  # 物理 schema は v2 なので空でも raise しない
