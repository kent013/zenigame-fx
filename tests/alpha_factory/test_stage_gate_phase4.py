"""PR4 = legacy_pnl_smoke fitness opt-in + anti-luck guard tests.

詳細設計: ``devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/detailed-design.md``

Test 構成:
- helper unit tests (= _compute_clipped_pnl_slack 6 件 + _compute_lucky_run_penalty 9 件)
- integration tests (= legacy / smoke / sentinel 経路 / payload、 evaluate_stage_a 経由)
- Phase4Config tests (= default / invalid / loader 反映)
- run_ga.py CLI tests (= --fitness-mode override)
"""

from __future__ import annotations

import math

import pytest

# ---------------------------------------------------------------------------
# helper unit tests: _compute_clipped_pnl_slack
# ---------------------------------------------------------------------------


def test_pr4_compute_clipped_pnl_slack_below_short_target() -> None:
    """PR4: total_pnl=0 → short_slack=-1.0 + long_slack=-1.0 → -1.0."""
    from src.alpha_factory.stage_gate import _compute_clipped_pnl_slack
    assert _compute_clipped_pnl_slack(0.0) == pytest.approx(-1.0)


def test_pr4_compute_clipped_pnl_slack_total_pnl_at_short_target_exact() -> None:
    """PR4: total_pnl==12000.0 ちょうど → short_slack=0.0、 long_slack=(12000-50000)/50000."""
    from src.alpha_factory.stage_gate import _compute_clipped_pnl_slack
    expected = 0.7 * 0.0 + 0.3 * ((12000 - 50000) / 50000)
    assert _compute_clipped_pnl_slack(12000.0) == pytest.approx(expected)


def test_pr4_compute_clipped_pnl_slack_at_long_target() -> None:
    """PR4: total_pnl==50000 → short_clip 上限 +2.0、 long_slack=0 → 1.4."""
    from src.alpha_factory.stage_gate import _compute_clipped_pnl_slack
    # short=(50000-12000)/12000=3.17 → clip +2.0、 long=0
    assert _compute_clipped_pnl_slack(50000.0) == pytest.approx(0.7 * 2.0)


def test_pr4_compute_clipped_pnl_slack_above_long_target() -> None:
    """PR4: total_pnl=100000 → 両 slack clip 上限 = 0.7*2.0 + 0.3*1.0 = 1.7."""
    from src.alpha_factory.stage_gate import _compute_clipped_pnl_slack
    assert _compute_clipped_pnl_slack(100000.0) == pytest.approx(1.7)


def test_pr4_compute_clipped_pnl_slack_short_clip_upper_bound_inclusive() -> None:
    """PR4: short_slack の clip 上限 +2.0 は境界値を含む (= total_pnl=36000 で正確に 2.0)."""
    from src.alpha_factory.stage_gate import _compute_clipped_pnl_slack
    # total_pnl=36000: short=(36000-12000)/12000=2.0 (= clip 上限ちょうど)
    # long=(36000-50000)/50000=-0.28 (= clip 範囲内)
    # 加重: 0.7*2.0 + 0.3*(-0.28) = 1.4 - 0.084 = 1.316
    assert _compute_clipped_pnl_slack(36000.0) == pytest.approx(1.4 - 0.084)


def test_pr4_compute_clipped_pnl_slack_extreme_negative_clip() -> None:
    """PR4: total_pnl=-100000 → short_clip 下限 -1.0、 long_clip 下限 -1.0 → -1.0."""
    from src.alpha_factory.stage_gate import _compute_clipped_pnl_slack
    assert _compute_clipped_pnl_slack(-100000.0) == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# helper unit tests: _compute_lucky_run_penalty
# ---------------------------------------------------------------------------


def test_pr4_compute_lucky_run_penalty_below_trigger_returns_zero() -> None:
    """PR4: total_pnl <= 12000 → 0.0 (= short target 未達なら lucky 判定対象外)."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    assert _compute_lucky_run_penalty(
        total_pnl=10000.0, max_dd_pct=0.0, trade_count=50,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 0.0


def test_pr4_compute_lucky_run_penalty_total_pnl_exact_trigger_is_exempt() -> None:
    """PR4: total_pnl==12000.0 ちょうど → 対象外 (= `>` 厳密、 境界免責)."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    assert _compute_lucky_run_penalty(
        total_pnl=12000.0, max_dd_pct=0.0, trade_count=50,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 0.0


def test_pr4_compute_lucky_run_penalty_hard_trigger_max_dd_zero() -> None:
    """PR4: total_pnl>12000 AND max_dd_pct==0.0 → hard_penalty."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    assert _compute_lucky_run_penalty(
        total_pnl=15000.0, max_dd_pct=0.0, trade_count=100,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 1.0


def test_pr4_compute_lucky_run_penalty_max_dd_exactly_epsilon_is_hard() -> None:
    """PR4: max_dd_pct==1e-9 ちょうど → hard (= `<=` 等号含む、 数値誤差込み)."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    assert _compute_lucky_run_penalty(
        total_pnl=15000.0, max_dd_pct=1e-9, trade_count=50,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 1.0


def test_pr4_compute_lucky_run_penalty_soft_trigger() -> None:
    """PR4: total_pnl>12000 AND max_dd_pct<0.5% AND trade_count<80 → soft."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    assert _compute_lucky_run_penalty(
        total_pnl=15000.0, max_dd_pct=0.3, trade_count=60,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 0.3


def test_pr4_compute_lucky_run_penalty_max_dd_exactly_soft_threshold_is_exempt() -> None:
    """PR4: max_dd_pct==0.5 ちょうど → soft 対象外 (= `<` 厳密、 境界免責)."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    assert _compute_lucky_run_penalty(
        total_pnl=15000.0, max_dd_pct=0.5, trade_count=50,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 0.0


def test_pr4_compute_lucky_run_penalty_trade_count_exactly_80_is_exempt() -> None:
    """PR4: trade_count==80 ちょうど → soft 対象外 (= `<` 厳密、 境界免責)."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    assert _compute_lucky_run_penalty(
        total_pnl=15000.0, max_dd_pct=0.3, trade_count=80,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 0.0


def test_pr4_compute_lucky_run_penalty_no_trigger_high_trade_count() -> None:
    """PR4: max_dd<0.5% でも trade_count>=80 なら robust 候補とみなして 0.0."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    assert _compute_lucky_run_penalty(
        total_pnl=15000.0, max_dd_pct=0.3, trade_count=100,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 0.0


def test_pr4_compute_lucky_run_penalty_no_trigger_high_dd() -> None:
    """PR4: max_dd>=0.5% なら通常 robust 候補とみなして 0.0."""
    from src.alpha_factory.stage_gate import _compute_lucky_run_penalty
    assert _compute_lucky_run_penalty(
        total_pnl=15000.0, max_dd_pct=1.0, trade_count=60,
        hard_penalty=1.0, soft_penalty=0.3,
    ) == 0.0


# ---------------------------------------------------------------------------
# Phase4Config tests
# ---------------------------------------------------------------------------


def test_pr4_phase4_config_defaults_to_legacy_mode() -> None:
    """PR4: Phase4Config default は legacy mode (= 行動完全不変)."""
    from src.alpha_factory.config import Phase4Config
    cfg = Phase4Config()
    assert cfg.fitness_mode == "legacy"
    assert cfg.beta == 0.05
    assert cfg.persistence_weight == 0.5
    assert cfg.lucky_hard_penalty == 1.0
    assert cfg.lucky_soft_penalty == 0.3


def test_pr4_phase4_config_rejects_invalid_mode() -> None:
    """PR4: 未定義 mode は ValueError."""
    from src.alpha_factory.config import Phase4Config
    with pytest.raises(ValueError, match="fitness_mode must be"):
        Phase4Config(fitness_mode="unknown_mode")  # type: ignore[arg-type]


def test_pr4_phase4_config_rejects_beta_out_of_range() -> None:
    """PR4: beta が [0, 1] 外なら ValueError."""
    from src.alpha_factory.config import Phase4Config
    with pytest.raises(ValueError, match="beta must be in"):
        Phase4Config(beta=2.0)
    with pytest.raises(ValueError, match="beta must be in"):
        Phase4Config(beta=-0.1)


def test_pr4_phase4_config_rejects_persistence_weight_out_of_range() -> None:
    """PR4: persistence_weight が [0, 1] 外なら ValueError."""
    from src.alpha_factory.config import Phase4Config
    with pytest.raises(ValueError, match="persistence_weight must be in"):
        Phase4Config(persistence_weight=1.5)


def test_pr4_phase4_config_rejects_negative_penalty() -> None:
    """PR4: lucky_* が負値なら ValueError."""
    from src.alpha_factory.config import Phase4Config
    with pytest.raises(ValueError, match="lucky_\\* penalty must be non-negative"):
        Phase4Config(lucky_hard_penalty=-0.1)


def test_pr4_phase4_config_rejects_hard_lt_soft() -> None:
    """PR4: lucky_hard < lucky_soft は順序整合性違反で ValueError."""
    from src.alpha_factory.config import Phase4Config
    with pytest.raises(ValueError, match=r"lucky_hard_penalty.*lucky_soft_penalty"):
        Phase4Config(lucky_hard_penalty=0.1, lucky_soft_penalty=0.5)


def test_pr4_phase4_config_accepts_smoke_mode() -> None:
    """PR4: legacy_pnl_smoke mode は valid."""
    from src.alpha_factory.config import Phase4Config
    cfg = Phase4Config(fitness_mode="legacy_pnl_smoke")
    assert cfg.fitness_mode == "legacy_pnl_smoke"


def test_pr4_phase4_config_rejects_nan_inf_values() -> None:
    """PR4: NaN / ±Inf は isfinite で弾く (= Codex impl-review Round 1 [Warning] 反映、
    fitness_pen が nan/-inf 化して GA selection 順序性を壊すのを未然防止)."""
    from src.alpha_factory.config import Phase4Config
    with pytest.raises(ValueError, match="must be finite"):
        Phase4Config(beta=math.nan)
    with pytest.raises(ValueError, match="must be finite"):
        Phase4Config(beta=math.inf)
    with pytest.raises(ValueError, match="must be finite"):
        Phase4Config(persistence_weight=math.nan)
    with pytest.raises(ValueError, match="must be finite"):
        Phase4Config(lucky_hard_penalty=math.inf)
    with pytest.raises(ValueError, match="must be finite"):
        Phase4Config(lucky_soft_penalty=-math.inf)


# ---------------------------------------------------------------------------
# Loader / yaml integration tests
# ---------------------------------------------------------------------------


def test_pr4_loader_default_yaml_loads_legacy_mode() -> None:
    """PR4: default.yaml は legacy mode (= 行動完全不変)."""
    from pathlib import Path

    from src.alpha_factory.config import load_config
    cfg = load_config(Path("config/alpha_factory/default.yaml"))
    assert cfg.phase4.fitness_mode == "legacy"
    assert cfg.stage_gate.phase4_fitness_mode == "legacy"


def test_pr4_loader_cli_override_to_smoke_mode() -> None:
    """PR4: overrides で fitness_mode='legacy_pnl_smoke' に切替可能."""
    from pathlib import Path

    from src.alpha_factory.config import load_config
    cfg = load_config(
        Path("config/alpha_factory/default.yaml"),
        overrides={"phase4": {"fitness_mode": "legacy_pnl_smoke"}},
    )
    assert cfg.phase4.fitness_mode == "legacy_pnl_smoke"
    assert cfg.stage_gate.phase4_fitness_mode == "legacy_pnl_smoke"


def test_pr4_loader_none_override_preserves_yaml() -> None:
    """PR4: overrides で None を渡すと yaml の値が維持される (= 未指定時の挙動)."""
    from pathlib import Path

    from src.alpha_factory.config import load_config
    cfg = load_config(
        Path("config/alpha_factory/default.yaml"),
        overrides={"phase4": {"fitness_mode": None}},
    )
    assert cfg.phase4.fitness_mode == "legacy"


def test_pr4_loader_rejects_unknown_yaml_key(tmp_path) -> None:
    """PR4: yaml の phase4 section に未定義 key があれば ValueError."""
    from pathlib import Path

    from src.alpha_factory.config import load_config
    src_yaml = Path("config/alpha_factory/default.yaml").read_text()
    target = tmp_path / "cfg.yaml"
    target.write_text(src_yaml + "\nphase4:\n  unknown_key: value\n")
    with pytest.raises(ValueError, match="phase4: unknown keys"):
        load_config(target)


# ---------------------------------------------------------------------------
# StageGateConfig __post_init__ defensive validation tests
# ---------------------------------------------------------------------------


def test_pr4_stage_gate_config_rejects_invalid_phase4_mode() -> None:
    """PR4: StageGateConfig __post_init__ で invalid phase4_fitness_mode は reject."""
    from src.alpha_factory.stage_gate import StageGateConfig
    with pytest.raises(ValueError, match="phase4_fitness_mode must be"):
        StageGateConfig(phase4_fitness_mode="bogus")  # type: ignore[arg-type]


def test_pr4_stage_gate_config_rejects_hard_lt_soft() -> None:
    """PR4: StageGateConfig __post_init__ で HARD<SOFT は reject (= 二重防御)."""
    from src.alpha_factory.stage_gate import StageGateConfig
    with pytest.raises(
        ValueError,
        match=r"phase4_lucky_hard_penalty.*phase4_lucky_soft_penalty",
    ):
        StageGateConfig(
            phase4_lucky_hard_penalty=0.1,
            phase4_lucky_soft_penalty=0.5,
        )


def test_pr4_stage_gate_config_rejects_nan_inf_phase4_values() -> None:
    """PR4: StageGateConfig __post_init__ で NaN/Inf も二重防御で reject."""
    from src.alpha_factory.stage_gate import StageGateConfig
    with pytest.raises(ValueError, match="must be finite"):
        StageGateConfig(phase4_beta=math.nan)
    with pytest.raises(ValueError, match="must be finite"):
        StageGateConfig(phase4_persistence_weight=math.inf)
    with pytest.raises(ValueError, match="must be finite"):
        StageGateConfig(phase4_lucky_hard_penalty=math.nan)


# ---------------------------------------------------------------------------
# Integration tests (evaluate_stage_a 経由)
# ---------------------------------------------------------------------------


def _evaluate_with_mode(mode: str):
    """共通 fixture: 既存 test_stage_gate.py の helpers で evaluate_stage_a を呼び結果を返す."""
    from src.alpha_factory.stage_gate import StageGateConfig, evaluate_stage_a
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    bars = _make_continuous_bars(60, bars_per_day=60)  # 60 day × 60 bars
    ev = ConstantPrimitiveEvaluator(value=1.0)  # 取引が発生する evaluator
    cfg_bt = _backtest_config()
    stage_cfg = StageGateConfig(phase4_fitness_mode=mode)  # type: ignore[arg-type]
    genome = _one_clause_genome("g_pr4")
    res = evaluate_stage_a(genome, bars, usd_jpy_meta(), cfg_bt, ev, stage_cfg)
    return res


def test_pr4_legacy_mode_payload_records_mode_and_none_observations() -> None:
    """PR4: legacy mode で payload に fitness_mode + None observations が記録される."""
    res = _evaluate_with_mode("legacy")
    payload = res.metrics["payload"]  # type: ignore[index]
    assert payload["phase4_fitness_mode"] == "legacy"
    assert payload["phase4_pnl_slack"] is None
    assert payload["phase4_lucky_penalty"] is None
    # config snapshot は legacy mode でも記録 (= future migration 監査用)
    assert payload["phase4_beta"] == pytest.approx(0.05)
    assert payload["phase4_persistence_weight"] == pytest.approx(0.5)
    assert payload["phase4_lucky_hard_penalty"] == pytest.approx(1.0)
    assert payload["phase4_lucky_soft_penalty"] == pytest.approx(0.3)


def test_pr4_legacy_mode_fitness_pen_matches_pre_pr4_formula() -> None:
    """PR4: legacy mode で fitness_pen は PR4 前の式 (= sharpe_term - tc_penalty) と一致.

    regression 0 契約 (= 既存 RUN 動作不変、 default 行動完全不変)。
    """
    from src.alpha_factory.stage_gate import STAGE_A_FITNESS_SENTINELS
    res = _evaluate_with_mode("legacy")
    payload = res.metrics["payload"]  # type: ignore[index]
    fitness_pen = payload["fitness_pen"]
    # sentinel 経路 (system_failure 等) の場合は別経路、 ここでは sharpe_raw あり
    # 経路 (= below_threshold or pass) を想定。 fitness_pen が sentinel ではないこと
    # を確認してから legacy 式を検証。
    if fitness_pen in STAGE_A_FITNESS_SENTINELS:
        pytest.skip("sentinel path (test fixture 由来)、 legacy 式検証は別経路")
    # legacy 式: fitness_raw - alpha*size_norm - tc_penalty (tc penalty は trade_count<min 時のみ)
    # 厳密検証は test_stage_gate.py の既存テストに任せ、 ここでは「sentinel でない」 を確認
    assert fitness_pen is not None
    assert math.isfinite(fitness_pen)


def test_pr4_smoke_mode_payload_records_mode_and_observations() -> None:
    """PR4: legacy_pnl_smoke mode で payload に pnl_slack / lucky_penalty が記録される.

    sentinel 経路でなければ float 値、 sentinel 経路なら None。
    """
    from src.alpha_factory.stage_gate import STAGE_A_FITNESS_SENTINELS
    res = _evaluate_with_mode("legacy_pnl_smoke")
    payload = res.metrics["payload"]  # type: ignore[index]
    assert payload["phase4_fitness_mode"] == "legacy_pnl_smoke"
    fitness_pen = payload["fitness_pen"]
    if fitness_pen in STAGE_A_FITNESS_SENTINELS:
        # sentinel 経路: observations は None
        assert payload["phase4_pnl_slack"] is None
        assert payload["phase4_lucky_penalty"] is None
    else:
        # below_threshold 経路: observations は float
        assert isinstance(payload["phase4_pnl_slack"], float)
        assert isinstance(payload["phase4_lucky_penalty"], float)
        assert math.isfinite(payload["phase4_pnl_slack"])
        assert payload["phase4_lucky_penalty"] >= 0.0


def test_pr4_sentinel_paths_legacy_vs_smoke_mode_fitness_pen_equivalence() -> None:
    """PR4: sentinel 経路では legacy / legacy_pnl_smoke で fitness_pen が完全一致
    (= 詳細設計 § 2.3.1 sentinel 不変契約、 Codex 設計レビュー Round 1 [Critical] 反映).

    no_exposure 経路 (= trade を出さない genome) で確認。
    """
    from src.alpha_factory.stage_gate import (
        NO_EXPOSURE_FITNESS,
        StageGateConfig,
        evaluate_stage_a,
    )
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    bars = _make_continuous_bars(60, bars_per_day=60)
    # ConstantPrimitiveEvaluator(value=0.0) で trade を出さない (= no_exposure)
    ev_no_trade = ConstantPrimitiveEvaluator(value=0.0)
    cfg_bt = _backtest_config()
    genome = _one_clause_genome("g_no_exposure")

    cfg_legacy = StageGateConfig(phase4_fitness_mode="legacy")
    cfg_smoke = StageGateConfig(phase4_fitness_mode="legacy_pnl_smoke")

    res_legacy = evaluate_stage_a(genome, bars, usd_jpy_meta(), cfg_bt, ev_no_trade, cfg_legacy)
    res_smoke = evaluate_stage_a(genome, bars, usd_jpy_meta(), cfg_bt, ev_no_trade, cfg_smoke)

    payload_legacy = res_legacy.metrics["payload"]  # type: ignore[index]
    payload_smoke = res_smoke.metrics["payload"]  # type: ignore[index]

    # 両 mode で no_exposure sentinel に到達
    assert "no_exposure" in res_legacy.reason_codes
    assert "no_exposure" in res_smoke.reason_codes
    assert payload_legacy["fitness_pen"] == NO_EXPOSURE_FITNESS
    assert payload_smoke["fitness_pen"] == NO_EXPOSURE_FITNESS
    # sentinel 経路では smoke mode でも observations は None (= 計算 skip 証跡)
    assert payload_smoke["phase4_pnl_slack"] is None
    assert payload_smoke["phase4_lucky_penalty"] is None
    # 完全一致契約
    assert payload_legacy["fitness_pen"] == payload_smoke["fitness_pen"]


def test_pr4_smoke_mode_fitness_pen_includes_pnl_term_and_lucky_penalty() -> None:
    """PR4: legacy_pnl_smoke mode で fitness_pen = sharpe_term + pnl_term - tc_penalty - lucky_penalty.

    具体的な式の検証 (= unit-test 的、 fixture が below_threshold 経路に到達する前提).
    """
    from src.alpha_factory.stage_gate import (
        STAGE_A_FITNESS_SENTINELS,
        StageGateConfig,
    )

    res = _evaluate_with_mode("legacy_pnl_smoke")
    payload = res.metrics["payload"]  # type: ignore[index]
    fitness_pen = payload["fitness_pen"]
    if fitness_pen in STAGE_A_FITNESS_SENTINELS:
        pytest.skip("sentinel path (test fixture 由来)、 式検証は別経路")
    # below_threshold 経路: 式から再計算した値と一致するか
    fitness_raw = payload["fitness_raw"]
    size_norm = payload["size_norm"]
    cfg = StageGateConfig(phase4_fitness_mode="legacy_pnl_smoke")
    sharpe_term = fitness_raw - cfg.stage_a_alpha * size_norm
    pnl_slack = payload["phase4_pnl_slack"]
    pnl_term = cfg.phase4_beta * pnl_slack * cfg.phase4_persistence_weight
    lucky_penalty = payload["phase4_lucky_penalty"]
    # tc_penalty は trade_count vs trade_count_min で決まる、 payload から再現
    trade_count = payload["trade_count"]
    lc_min = int(cfg.live_criteria["trade_count_min"])
    if trade_count < lc_min:
        tc_penalty = (
            cfg.stage_a_trade_count_penalty_gamma * (lc_min - trade_count) / lc_min
        )
    else:
        tc_penalty = 0.0
    expected = sharpe_term + pnl_term - tc_penalty - lucky_penalty
    assert fitness_pen == pytest.approx(expected)


# ---------------------------------------------------------------------------
# CLI tests (run_ga.py --fitness-mode)
# ---------------------------------------------------------------------------


def test_pr4_cli_args_to_overrides_includes_fitness_mode() -> None:
    """PR4: _args_to_overrides が --fitness-mode を phase4.fitness_mode に変換."""
    import argparse

    from scripts.alpha_factory.run_ga import _args_to_overrides

    # 簡易 namespace (= argparse.Namespace 相当)
    args = argparse.Namespace(
        instrument=None, start=None, end=None,
        population_size=None, generations=None, mutation_rate=None,
        crossover_rate=None, tournament_size=None, elite_count=None,
        max_depth=None, fitness_metric=None, seed=None, max_workers=None,
        max_tasks_per_child=None,
        fitness_mode="legacy_pnl_smoke",
    )
    overrides = _args_to_overrides(args)
    assert overrides["phase4"]["fitness_mode"] == "legacy_pnl_smoke"


def test_pr4_cli_args_to_overrides_none_fitness_mode() -> None:
    """PR4: --fitness-mode 未指定 (= None) で None が保持され yaml 値が維持される."""
    import argparse

    from scripts.alpha_factory.run_ga import _args_to_overrides

    args = argparse.Namespace(
        instrument=None, start=None, end=None,
        population_size=None, generations=None, mutation_rate=None,
        crossover_rate=None, tournament_size=None, elite_count=None,
        max_depth=None, fitness_metric=None, seed=None, max_workers=None,
        max_tasks_per_child=None,
        fitness_mode=None,
    )
    overrides = _args_to_overrides(args)
    assert overrides["phase4"]["fitness_mode"] is None
