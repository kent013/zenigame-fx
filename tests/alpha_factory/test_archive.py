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
    _compute_active_clause_placeholder,
    _compute_n_nodes,
    _create_row_template,
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


def test_schema_has_33_columns() -> None:
    # T-sharpe Phase 1A: trade_sharpe_raw + sharpe_calc_version (28→30)
    # T035: n_fold_effective + positive_fold_ratio_effective + stage_b_reason_codes (30→33)
    assert len(GENOMES_SCHEMA.names) == 33
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
        # T035: Stage B 観察可能性
        "n_fold_effective", "positive_fold_ratio_effective",
        "stage_b_reason_codes",
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
        # T035
        "n_fold_effective", "positive_fold_ratio_effective",
        "stage_b_reason_codes",
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


def test_collect_stage_a_active_clause_placeholder() -> None:
    arc = _make_archive()
    arc.collect_stage_a(_stub_genome(), "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["active_clause"] == 0
    assert _compute_active_clause_placeholder() == 0


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


def test_collect_stage_b_updates_overrides_sharpe_pnl_tc() -> None:
    arc = _make_archive()
    g = _stub_genome()
    arc.collect_stage_a(g, "lane", 0, _stage_a_result(),
                         instrument="USD_JPY")
    arc.collect_stage_b(g, "lane", 0, _stage_b_result())
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["stage_b_pass"] is True
    # T-sharpe Phase 1A: is_full_sharpe (Stage B IS monitor の trade_sharpe_raw) は
    # archive の trade_sharpe_raw 列に上書きされる
    assert row["trade_sharpe_raw"] == pytest.approx(0.5)
    assert row["sharpe_calc_version"] == "v2_trade_level"
    assert row["total_pnl"] == pytest.approx(12000.0)
    assert row["trade_count"] == 200


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
    # T-sharpe Phase 1A: trade_sharpe_raw を Stage C で最終上書き
    assert d["trade_sharpe_raw"] == pytest.approx(1.2)
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
    # T-sharpe Phase 1A: B 値が保持される (trade_sharpe_raw = 0.5 = is_full_sharpe)
    row = arc._rows[("lane", 0, "g0_i0")]
    assert row["trade_sharpe_raw"] == pytest.approx(0.5)
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
    # T-sharpe Phase 1A: Stage C の trade_sharpe_raw / total_pnl / trade_count が最終上書き
    assert row["trade_sharpe_raw"] == pytest.approx(1.2)
    assert row["sharpe_calc_version"] == "v2_trade_level"
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
        # T035
        "n_fold_effective", "positive_fold_ratio_effective",
        "stage_b_reason_codes",
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
