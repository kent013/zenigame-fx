"""T058: SchemaContractConfig + load_config schema_contract parse のテスト.

詳細設計: devnotes/20260429-1912-todo-T058-schema-v2-contract/detailed-design.md § 施策 3。
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.alpha_factory.config import SchemaContractConfig, load_config
from src.alpha_factory.schema_contract import SchemaEnforcementMode

# ---------------------------------------------------------------------------
# SchemaContractConfig dataclass
# ---------------------------------------------------------------------------


def test_schema_contract_config_default_is_log_only() -> None:
    """default で enforcement_mode='log_only' (T058 段階)."""
    cfg = SchemaContractConfig()
    assert cfg.enforcement_mode == "log_only"


def test_schema_contract_config_rejects_invalid_enforcement_mode() -> None:
    """未知の enforcement_mode は ValueError."""
    with pytest.raises(ValueError, match="enforcement_mode must be one of"):
        SchemaContractConfig(enforcement_mode="strict")


def test_schema_contract_config_to_mode_returns_strenum_member() -> None:
    """to_mode() で SchemaEnforcementMode を返す."""
    cfg_log = SchemaContractConfig(enforcement_mode="log_only")
    assert cfg_log.to_mode() is SchemaEnforcementMode.LOG_ONLY

    cfg_fail = SchemaContractConfig(enforcement_mode="fail_closed")
    assert cfg_fail.to_mode() is SchemaEnforcementMode.FAIL_CLOSED


# ---------------------------------------------------------------------------
# load_config integration
# ---------------------------------------------------------------------------

_BASE_YAML = """
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


def _write_yaml(tmp_path: Path, extra: str = "") -> Path:
    p = tmp_path / "test.yaml"
    p.write_text(textwrap.dedent(_BASE_YAML + extra), encoding="utf-8")
    return p


def test_load_config_default_yaml_parses_schema_contract_log_only() -> None:
    """既定 default.yaml が schema_contract.enforcement_mode='log_only' を読む."""
    repo_yaml = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "alpha_factory"
        / "default.yaml"
    )
    cfg = load_config(repo_yaml)
    assert cfg.schema_contract.enforcement_mode == "log_only"
    assert cfg.schema_contract.to_mode() is SchemaEnforcementMode.LOG_ONLY


def test_load_config_overrides_schema_contract_to_fail_closed(
    tmp_path: Path,
) -> None:
    """yaml で fail_closed に上書きできる."""
    p = _write_yaml(
        tmp_path,
        extra="\nschema_contract:\n  enforcement_mode: fail_closed\n",
    )
    cfg = load_config(p)
    assert cfg.schema_contract.enforcement_mode == "fail_closed"
    assert cfg.schema_contract.to_mode() is SchemaEnforcementMode.FAIL_CLOSED


def test_load_config_without_schema_contract_section_uses_default(
    tmp_path: Path,
) -> None:
    """yaml に schema_contract が無くても default で復元される."""
    p = _write_yaml(tmp_path)
    cfg = load_config(p)
    assert cfg.schema_contract.enforcement_mode == "log_only"


def test_load_config_rejects_unknown_schema_contract_key(
    tmp_path: Path,
) -> None:
    """unknown key (typo 含む) は ValueError で reject."""
    p = _write_yaml(
        tmp_path,
        extra=(
            "\nschema_contract:\n"
            "  enforcement_mode: log_only\n"
            "  enforce_modus: typo\n"
        ),
    )
    with pytest.raises(ValueError, match="unknown keys"):
        load_config(p)


def test_load_config_rejects_invalid_enforcement_mode_value(
    tmp_path: Path,
) -> None:
    """SchemaContractConfig __post_init__ で invalid 値を reject."""
    p = _write_yaml(
        tmp_path,
        extra="\nschema_contract:\n  enforcement_mode: strict\n",
    )
    with pytest.raises(ValueError, match="enforcement_mode must be one of"):
        load_config(p)
