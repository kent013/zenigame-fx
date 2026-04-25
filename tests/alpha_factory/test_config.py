"""Alpha Factory config loader テスト (T031: GAFeasibilityConfig 関連)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.alpha_factory.config import (
    GAConfig,
    GAFeasibilityConfig,
    load_config,
)


def test_ga_feasibility_default_values() -> None:
    """default で entry_count_min=1, apply_from_generation=0, fallback=True."""
    cfg = GAFeasibilityConfig()
    assert cfg.entry_count_min == 1
    assert cfg.apply_from_generation == 0
    assert cfg.enable_fallback_when_all_infeasible is True


def test_ga_feasibility_invalid_negative_entry_count_min() -> None:
    with pytest.raises(ValueError, match="entry_count_min must be >= 0"):
        GAFeasibilityConfig(entry_count_min=-1)


def test_ga_feasibility_invalid_negative_apply_from_generation() -> None:
    with pytest.raises(ValueError, match="apply_from_generation must be >= 0"):
        GAFeasibilityConfig(apply_from_generation=-1)


def test_ga_feasibility_hard_cap_enforced() -> None:
    with pytest.raises(ValueError, match="exceeds hard cap"):
        GAFeasibilityConfig(entry_count_min=10001)


def test_ga_config_default_includes_feasibility() -> None:
    """GAConfig の default で feasibility が default_factory で復元される."""
    ga = GAConfig(
        population_size=10,
        generations=5,
        crossover_rate=0.7,
        mutation_rate=0.3,
        tournament_size=3,
        elite_count=2,
        max_depth=4,
    )
    assert ga.feasibility.entry_count_min == 1
    assert ga.feasibility.apply_from_generation == 0


def test_ga_config_apply_from_generation_must_be_le_generations() -> None:
    """apply_from_generation > generations は ValueError."""
    with pytest.raises(
        ValueError,
        match=r"apply_from_generation .* must be <= ga\.generations",
    ):
        GAConfig(
            population_size=10,
            generations=2,
            crossover_rate=0.7,
            mutation_rate=0.3,
            tournament_size=3,
            elite_count=2,
            max_depth=4,
            feasibility=GAFeasibilityConfig(apply_from_generation=5),
        )


def test_load_config_yaml_with_feasibility_section(tmp_path: Path) -> None:
    """yaml の ga.feasibility section が正しく読み込まれる."""
    yaml_text = textwrap.dedent(
        """
        dataset:
          instrument: EUR_JPY
          start: "2025-10-01T00:00:00Z"
          end: "2026-04-01T00:00:00Z"
        backtest:
          initial_cash: "1000000"
          leverage: 25
          units: 10000
        ga:
          population_size: 8
          generations: 2
          crossover_rate: 0.7
          mutation_rate: 0.3
          tournament_size: 3
          elite_count: 2
          max_depth: 4
          feasibility:
            entry_count_min: 5
            apply_from_generation: 1
            enable_fallback_when_all_infeasible: false
        live_criteria:
          sharpe_min: 1.0
          total_pnl_min: 50000
          max_drawdown_max: 0.2
          trade_count_min: 50
          trade_count_max: 5000
        stage_gate:
          stage_a:
            window_days: 60
            target_pass_rate: 0.15
            alpha: 0.03
            threshold: 0.0
          stage_b:
            window_months: 18
          stage_c:
            holdout_days: 60
            spread_stress_multiplier: 1.5
        cross_pair:
          mode: shadow
          aggregator_lambda: 0.5
        stage_windows:
          stage_a_window_days: 60
          stage_c_holdout_days: 60
        """
    )
    p = tmp_path / "test.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    cfg = load_config(p)
    assert cfg.ga.feasibility.entry_count_min == 5
    assert cfg.ga.feasibility.apply_from_generation == 1
    assert cfg.ga.feasibility.enable_fallback_when_all_infeasible is False


def test_load_config_yaml_without_feasibility_section_uses_defaults(
    tmp_path: Path,
) -> None:
    """yaml に feasibility 欠落時、default で復元される."""
    yaml_text = textwrap.dedent(
        """
        dataset:
          instrument: EUR_JPY
          start: "2025-10-01T00:00:00Z"
          end: "2026-04-01T00:00:00Z"
        backtest:
          initial_cash: "1000000"
          leverage: 25
          units: 10000
        ga:
          population_size: 8
          generations: 2
          crossover_rate: 0.7
          mutation_rate: 0.3
          tournament_size: 3
          elite_count: 2
          max_depth: 4
        live_criteria:
          sharpe_min: 1.0
          total_pnl_min: 50000
          max_drawdown_max: 0.2
          trade_count_min: 50
          trade_count_max: 5000
        stage_gate:
          stage_a:
            window_days: 60
            target_pass_rate: 0.15
            alpha: 0.03
            threshold: 0.0
          stage_b:
            window_months: 18
          stage_c:
            holdout_days: 60
            spread_stress_multiplier: 1.5
        cross_pair:
          mode: shadow
          aggregator_lambda: 0.5
        stage_windows:
          stage_a_window_days: 60
          stage_c_holdout_days: 60
        """
    )
    p = tmp_path / "test.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    cfg = load_config(p)
    assert cfg.ga.feasibility.entry_count_min == 1
    assert cfg.ga.feasibility.apply_from_generation == 0


def test_strict_bool_string_false_is_false() -> None:
    """`bool("false")` の罠を回避."""
    from src.alpha_factory.config import _strict_bool

    assert _strict_bool("false", default=True) is False
    assert _strict_bool("False", default=True) is False
    assert _strict_bool("FALSE", default=True) is False
    assert _strict_bool("true", default=False) is True
    assert _strict_bool(None, default=True) is True
    assert _strict_bool(None, default=False) is False
