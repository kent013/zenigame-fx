"""Unit tests for src/alpha_factory/calibrate_gate.py (T027)。

pure logic 部のテスト。CLI / yaml IO は tests/scripts/test_calibrate_gate_cli.py。
"""

from __future__ import annotations

from typing import Any

import pyarrow as pa
import pytest

from src.alpha_factory.calibrate_gate import (
    AGGREGATION_MODES,
    CalibrateConfig,
    ConfigError,
    SchemaMismatchError,
    aggregate_sample,
    compute_monitoring,
    decide,
    load_calibrate_config,
    validate_schema,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _row(
    *,
    generation: int,
    stage_a_pass: bool,
    fitness_pen: float,
    stage_b_pass: bool = False,
    stage_c_pass: bool = False,
    sharpe: float | None = None,
    total_pnl: float = 0.0,
    max_drawdown_pct: float = 0.0,
    trade_count: int = 0,
    # T-sharpe Phase 1A: trade_sharpe_raw (v2) を default で v2 archive 行とみなす
    trade_sharpe_raw: float | None = None,
    sharpe_calc_version: str | None = "v2_trade_level",
) -> dict[str, Any]:
    # T-sharpe Phase 1A: 旧 fixture 互換のため `sharpe` 引数を受けたら
    # trade_sharpe_raw=v2 として扱う (v2 archive 行をシミュレート)
    if trade_sharpe_raw is None and sharpe is not None:
        trade_sharpe_raw = sharpe
    return {
        "generation": generation,
        "stage_a_pass": stage_a_pass,
        "stage_b_pass": stage_b_pass,
        "stage_c_pass": stage_c_pass,
        "fitness_pen": fitness_pen,
        "sharpe": sharpe,
        "total_pnl": total_pnl,
        "max_drawdown_pct": max_drawdown_pct,
        "trade_count": trade_count,
        "trade_sharpe_raw": trade_sharpe_raw,
        "sharpe_calc_version": sharpe_calc_version,
    }


def _default_config(**overrides: Any) -> CalibrateConfig:
    base = {
        "enabled": True,
        "aggregation_mode": "last_k_generations",
        "aggregation_window": 5,
        "pass_rate_tolerance_abs": 0.05,
        "threshold_delta_abs_max": 0.5,
        "threshold_floor": -100.0,
        "threshold_ceiling": 100.0,
        "min_sample_size": 10,
        "eps_var": 1e-9,
        "target_pass_rate": 0.15,
        "prev_threshold": 0.0,
    }
    base.update(overrides)
    return CalibrateConfig(**base)


# ---------------------------------------------------------------------------
# aggregate_sample
# ---------------------------------------------------------------------------


def test_aggregate_last_k_generations_uses_only_late_gens() -> None:
    rows = [
        _row(generation=0, stage_a_pass=False, fitness_pen=-10.0),
        _row(generation=1, stage_a_pass=False, fitness_pen=-5.0),
        _row(generation=2, stage_a_pass=True, fitness_pen=1.0),
        _row(generation=3, stage_a_pass=True, fitness_pen=2.0),
        _row(generation=4, stage_a_pass=True, fitness_pen=3.0),
    ]
    s = aggregate_sample(rows, mode="last_k_generations", window=2)
    # gens 3, 4 のみ → n_used=2, pass=2, pool=(2.0, 3.0)
    assert s.n_rows_total == 5
    assert s.n_rows_used == 2
    assert s.pass_count_used == 2
    assert s.actual_pass_rate == 1.0
    assert s.fitness_pen_pool == (2.0, 3.0)


def test_aggregate_all_generations_uses_all() -> None:
    rows = [
        _row(generation=0, stage_a_pass=True, fitness_pen=1.0),
        _row(generation=1, stage_a_pass=False, fitness_pen=-1.0),
    ]
    s = aggregate_sample(rows, mode="all_generations", window=5)
    assert s.n_rows_used == 2
    assert s.pass_count_used == 1
    assert s.actual_pass_rate == 0.5
    assert s.fitness_pen_pool == (1.0, -1.0)


def test_aggregate_generation_weighted_mean_weights_late_more() -> None:
    # gen 0: pass_rate=0.0 (重み 1)
    # gen 1: pass_rate=1.0 (重み 2)
    # 加重平均 = (1*0 + 2*1) / 3 = 0.6667
    rows = [
        _row(generation=0, stage_a_pass=False, fitness_pen=-1.0),
        _row(generation=1, stage_a_pass=True, fitness_pen=2.0),
    ]
    s = aggregate_sample(rows, mode="generation_weighted_mean", window=5)
    assert abs(s.actual_pass_rate - (2.0 / 3.0)) < 1e-9
    # pool は全世代統一
    assert s.fitness_pen_pool == (-1.0, 2.0)
    assert s.n_rows_used == 2


def test_aggregate_empty_returns_zero() -> None:
    s = aggregate_sample([], mode="last_k_generations", window=5)
    assert s.n_rows_used == 0
    assert s.actual_pass_rate == 0.0
    assert s.fitness_pen_pool == ()


def test_aggregate_unknown_mode_raises() -> None:
    with pytest.raises(ValueError):
        aggregate_sample([], mode="bogus", window=5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# decide
# ---------------------------------------------------------------------------


def test_decide_in_band_returns_no_change() -> None:
    rows = [
        _row(generation=0, stage_a_pass=(i < 15), fitness_pen=float(i))
        for i in range(100)
    ]
    s = aggregate_sample(rows, mode="all_generations", window=5)
    cfg = _default_config(target_pass_rate=0.15, pass_rate_tolerance_abs=0.05)
    d = decide(s, cfg)
    assert d.decision == "in_band"
    assert d.new_threshold == cfg.prev_threshold
    assert d.delta == 0.0


def test_decide_tighten_when_pass_rate_above_target_plus_tol() -> None:
    # actual = 0.5, target = 0.15 → tighten
    rows = [
        _row(generation=0, stage_a_pass=(i < 50), fitness_pen=float(i))
        for i in range(100)
    ]
    s = aggregate_sample(rows, mode="all_generations", window=5)
    cfg = _default_config(target_pass_rate=0.15, threshold_delta_abs_max=10.0)
    d = decide(s, cfg)
    assert d.decision == "tighten"
    assert d.new_threshold > cfg.prev_threshold


def test_decide_loosen_when_pass_rate_below_target_minus_tol() -> None:
    # actual = 0.0, target = 0.15 → loosen
    rows = [
        _row(generation=0, stage_a_pass=False, fitness_pen=float(-i))
        for i in range(100)
    ]
    s = aggregate_sample(rows, mode="all_generations", window=5)
    cfg = _default_config(
        target_pass_rate=0.15, prev_threshold=0.0, threshold_delta_abs_max=200.0
    )
    d = decide(s, cfg)
    assert d.decision == "loosen"
    assert d.new_threshold < cfg.prev_threshold


def test_decide_clamps_delta() -> None:
    # 巨大な分布で q_target が prev から大きく乖離 → max_delta で clamp
    rows = [
        _row(generation=0, stage_a_pass=(i < 50), fitness_pen=float(i * 100))
        for i in range(100)
    ]
    s = aggregate_sample(rows, mode="all_generations", window=5)
    cfg = _default_config(
        target_pass_rate=0.15, threshold_delta_abs_max=0.5, prev_threshold=0.0
    )
    d = decide(s, cfg)
    assert d.decision == "tighten"
    assert d.clamped_by_delta is True
    assert d.delta == 0.5
    assert d.new_threshold == 0.5


def test_decide_clamps_floor_ceiling() -> None:
    # prev=99.9, max_delta=10 → new_after_delta=109.9 → ceiling=100 で clamp
    rows = [
        _row(generation=0, stage_a_pass=(i < 50), fitness_pen=float(i * 100))
        for i in range(100)
    ]
    s = aggregate_sample(rows, mode="all_generations", window=5)
    cfg = _default_config(
        target_pass_rate=0.15,
        threshold_delta_abs_max=10.0,
        prev_threshold=99.9,
        threshold_ceiling=100.0,
    )
    d = decide(s, cfg)
    assert d.clamped_by_floor_or_ceiling is True
    assert d.new_threshold == 100.0


def test_decide_skips_when_disabled() -> None:
    rows = [
        _row(generation=0, stage_a_pass=False, fitness_pen=0.0)
        for _ in range(100)
    ]
    s = aggregate_sample(rows, mode="all_generations", window=5)
    cfg = _default_config(enabled=False)
    d = decide(s, cfg)
    assert d.decision == "skip_disabled"
    assert d.new_threshold == cfg.prev_threshold


def test_decide_skips_when_sample_size_below_min() -> None:
    rows = [_row(generation=0, stage_a_pass=False, fitness_pen=0.0)]
    s = aggregate_sample(rows, mode="all_generations", window=5)
    cfg = _default_config(min_sample_size=30)
    d = decide(s, cfg)
    assert d.decision == "skip_sample_size"
    assert d.effective_sample_size == 1


def test_decide_skips_on_zero_variance() -> None:
    # 全行 fitness_pen=0.0 → var=0 → skip
    rows = [
        _row(generation=0, stage_a_pass=False, fitness_pen=0.0)
        for _ in range(100)
    ]
    s = aggregate_sample(rows, mode="all_generations", window=5)
    cfg = _default_config(target_pass_rate=0.15)
    d = decide(s, cfg)
    assert d.decision == "skip_zero_variance"
    assert d.var_fitness_pen == 0.0


# ---------------------------------------------------------------------------
# compute_monitoring
# ---------------------------------------------------------------------------


def test_compute_monitoring_gap_signs_are_non_negative() -> None:
    rows = [
        _row(
            generation=0,
            stage_a_pass=True,
            fitness_pen=0.0,
            stage_b_pass=True,
            stage_c_pass=False,
            sharpe=0.5,
            total_pnl=10000.0,
            max_drawdown_pct=15.0,
            trade_count=200,
        )
    ]
    live_criteria = {
        "sharpe_min": 1.0,
        "total_pnl_min": 50000.0,
        "max_drawdown_max": 0.2,
        "trade_count_min": 50,
        "trade_count_max": 5000,
    }
    m = compute_monitoring(rows, live_criteria=live_criteria)
    assert m.stage_b_pass_count == 1
    assert m.stage_c_pass_count == 0
    assert m.best_sharpe == 0.5
    assert m.live_criteria_gap["sharpe"] == 0.5
    assert m.live_criteria_gap["total_pnl"] == 40000.0
    # max_dd: best_max_dd=15% → 0.15, target=0.20 → gap=0 (achieved)
    assert m.live_criteria_gap["max_dd"] == 0.0
    # trade_count: tc=200, min=50, max=5000 → 両 gap=0
    assert m.live_criteria_gap["trade_count_min"] == 0.0
    assert m.live_criteria_gap["trade_count_max"] == 0.0


def test_compute_monitoring_handles_missing_optional_fields() -> None:
    rows = [_row(generation=0, stage_a_pass=False, fitness_pen=0.0)]
    m = compute_monitoring(rows, live_criteria={"sharpe_min": 1.0})
    assert m.best_sharpe is None
    # gap.sharpe: best=None→0 として、gap = max(0, 1 - 0) = 1.0
    assert m.live_criteria_gap["sharpe"] == 1.0


# ---------------------------------------------------------------------------
# CalibrateConfig validation
# ---------------------------------------------------------------------------


def test_config_rejects_invalid_target_pass_rate() -> None:
    with pytest.raises(ConfigError):
        _default_config(target_pass_rate=1.5)


def test_config_rejects_floor_greater_than_ceiling() -> None:
    with pytest.raises(ConfigError):
        _default_config(threshold_floor=10.0, threshold_ceiling=5.0)


def test_config_rejects_unknown_aggregation_mode() -> None:
    with pytest.raises(ConfigError):
        _default_config(aggregation_mode="bogus")


def test_config_rejects_invalid_window() -> None:
    with pytest.raises(ConfigError):
        _default_config(aggregation_window=0)


def test_config_rejects_non_positive_eps_var() -> None:
    with pytest.raises(ConfigError):
        _default_config(eps_var=0)


def test_aggregation_modes_constant_complete() -> None:
    assert set(AGGREGATION_MODES) == {
        "last_k_generations",
        "all_generations",
        "generation_weighted_mean",
    }


# ---------------------------------------------------------------------------
# load_calibrate_config
# ---------------------------------------------------------------------------


def test_load_calibrate_config_succeeds_on_complete_yaml() -> None:
    yaml_data = {
        "stage_gate": {
            "stage_a": {
                "target_pass_rate": 0.15,
                "threshold": 0.0,
                "calibrate": {
                    "enabled": True,
                    "aggregation_mode": "last_k_generations",
                    "aggregation_window": 5,
                    "pass_rate_tolerance_abs": 0.05,
                    "threshold_delta_abs_max": 0.5,
                    "threshold_floor": -100.0,
                    "threshold_ceiling": 100.0,
                    "min_sample_size": 30,
                    "eps_var": 1e-9,
                },
            }
        }
    }
    cfg = load_calibrate_config(yaml_data)
    assert cfg.enabled is True
    assert cfg.aggregation_mode == "last_k_generations"
    assert cfg.target_pass_rate == 0.15
    assert cfg.prev_threshold == 0.0


def test_load_calibrate_config_raises_on_missing_section() -> None:
    yaml_data = {
        "stage_gate": {
            "stage_a": {"target_pass_rate": 0.15, "threshold": 0.0}
        }
    }
    with pytest.raises(ConfigError, match="missing key path"):
        load_calibrate_config(yaml_data)


def test_load_calibrate_config_raises_on_missing_keys() -> None:
    yaml_data = {
        "stage_gate": {
            "stage_a": {
                "target_pass_rate": 0.15,
                "threshold": 0.0,
                "calibrate": {"enabled": True},
            }
        }
    }
    with pytest.raises(ConfigError, match="missing calibrate keys"):
        load_calibrate_config(yaml_data)


# ---------------------------------------------------------------------------
# validate_schema
# ---------------------------------------------------------------------------


def _make_table(**overrides: Any) -> pa.Table:
    base = {
        "generation": [0, 1],
        "stage_a_pass": [True, False],
        "fitness_pen": [1.0, 2.0],
        "stage_b_pass": [False, False],
        "stage_c_pass": [False, False],
        "sharpe": [0.5, None],
        "total_pnl": [100.0, 200.0],
        "max_drawdown_pct": [10.0, 20.0],
        "trade_count": [50, 60],
    }
    base.update(overrides)
    return pa.Table.from_pydict(base)


def test_validate_schema_passes_on_well_formed_table() -> None:
    table = _make_table()
    validate_schema(table)  # raises 無し


def test_validate_schema_raises_on_missing_column() -> None:
    base_dict = {
        "generation": [0],
        "stage_a_pass": [True],
        # fitness_pen 欠落
        "stage_b_pass": [False],
        "stage_c_pass": [False],
        "sharpe": [0.5],
        "total_pnl": [100.0],
        "max_drawdown_pct": [10.0],
        "trade_count": [50],
    }
    table = pa.Table.from_pydict(base_dict)
    with pytest.raises(SchemaMismatchError, match="missing columns"):
        validate_schema(table)


def test_validate_schema_raises_on_unexpected_null() -> None:
    table = pa.Table.from_pydict(
        {
            "generation": [0, 1],
            "stage_a_pass": pa.array([True, None], type=pa.bool_()),
            "fitness_pen": [1.0, 2.0],
            "stage_b_pass": [False, False],
            "stage_c_pass": [False, False],
            "sharpe": [0.5, None],
            "total_pnl": [100.0, 200.0],
            "max_drawdown_pct": [10.0, 20.0],
            "trade_count": [50, 60],
        }
    )
    with pytest.raises(SchemaMismatchError, match="unexpected nulls"):
        validate_schema(table)


def test_validate_schema_raises_on_nan_fitness_pen() -> None:
    table = pa.Table.from_pydict(
        {
            "generation": [0, 1],
            "stage_a_pass": [True, False],
            "fitness_pen": [1.0, float("nan")],
            "stage_b_pass": [False, False],
            "stage_c_pass": [False, False],
            "sharpe": [0.5, None],
            "total_pnl": [100.0, 200.0],
            "max_drawdown_pct": [10.0, 20.0],
            "trade_count": [50, 60],
        }
    )
    with pytest.raises(SchemaMismatchError, match="NaN"):
        validate_schema(table)


def test_validate_schema_raises_on_inf_total_pnl() -> None:
    table = pa.Table.from_pydict(
        {
            "generation": [0, 1],
            "stage_a_pass": [True, False],
            "fitness_pen": [1.0, 2.0],
            "stage_b_pass": [False, False],
            "stage_c_pass": [False, False],
            "sharpe": [0.5, None],
            "total_pnl": [100.0, float("inf")],
            "max_drawdown_pct": [10.0, 20.0],
            "trade_count": [50, 60],
        }
    )
    with pytest.raises(SchemaMismatchError, match="NaN or Inf"):
        validate_schema(table)


def test_validate_schema_raises_on_nan_in_trade_count_via_float_column() -> None:
    """上流が trade_count を float で構築した場合 NaN が混入し得るため弾く。"""
    table = pa.Table.from_pydict(
        {
            "generation": [0, 1],
            "stage_a_pass": [True, False],
            "fitness_pen": [1.0, 2.0],
            "stage_b_pass": [False, False],
            "stage_c_pass": [False, False],
            "sharpe": [0.5, None],
            "total_pnl": [100.0, 200.0],
            "max_drawdown_pct": [10.0, 20.0],
            # float64 で構築 → NaN 入れ可能
            "trade_count": pa.array([50.0, float("nan")], type=pa.float64()),
        }
    )
    with pytest.raises(SchemaMismatchError, match="NaN or Inf"):
        validate_schema(table)
