"""Tests for ``scripts/alpha_factory/run_alpha_sieve.py`` (T025).

Phase 2 alpha-sieve OOS validation framework のユニット + 統合 smoke テスト。
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scripts.alpha_factory import run_alpha_sieve as sieve_mod
from src.alpha_factory.archive import GENOMES_SCHEMA
from src.backtest.engine import BacktestConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "alpha_factory" / "default.yaml"


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_archive_row(
    *,
    individual_name: str,
    lane_id: str = "tier1_EUR_JPY",
    instrument: str = "EUR_JPY",
    generation: int = 0,
    stage_c_pass: bool = True,
    sharpe: float | None = 1.5,
    total_pnl: float = 60_000.0,
    trade_count: int = 80,
    genome_json: str = '{"name":"g0_i0"}',
) -> dict[str, Any]:
    row: dict[str, Any] = {
        # T058: schema v2 必須 4 field (GENOMES_SCHEMA non-null)
        "genome_entry_schema_version": 2,
        "dataset_epoch_id": "epoch_legacy",
        "archive_role": None,
        "source_stage": None,
        "run_id": "run_test",
        "run_number": 99,
        "generation": generation,
        "individual_name": individual_name,
        "instrument": instrument,
        "lane_id": lane_id,
        "parent_a": None,
        "parent_b": None,
        "genome_json": genome_json,
        "fitness_raw": 0.0,
        "fitness_pen": 0.0,
        "stage_a_pass": True,
        "stage_b_pass": True,
        "stage_c_pass": stage_c_pass,
        "trade_count": trade_count,
        "total_pnl": total_pnl,
        "sharpe": sharpe,
        "sortino": None,
        "calmar": None,
        "max_drawdown_pct": 5.0,
        "active_clause": 0,
        "n_nodes": 3,
        "bootstrap_ci_lower": None,
        "bootstrap_ci_upper": None,
        "fold_sign_ratio": None,
        "dsr": None,
        "ii_lite_pass": None,
        "graduated": False,
    }
    return row


def _write_archive(parquet_path: Path, rows: Iterable[dict[str, Any]]) -> None:
    table = pa.Table.from_pylist(list(rows), schema=GENOMES_SCHEMA)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, parquet_path)


def _make_summary(
    *,
    run_id: str = "run_test",
    run_number: int = 99,
    instrument: str = "EUR_JPY",
    dataset_end: str = "2026-04-01T00:00:00+00:00",
    stage_c_holdout_days: int = 60,
    initial_cash: str = "1000000",
    leverage: int = 25,
    units: int = 10000,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_number": run_number,
        "generated_at": "2026-04-23T19:59:17.899088+00:00",
        "dataset": {
            "instrument": instrument,
            "start": "2025-10-01T00:00:00+00:00",
            "end": dataset_end,
            "bars": 1000,
        },
        "ga_config": {"population_size": 4, "generations": 2},
        "backtest_config": {
            "initial_cash": initial_cash,
            "leverage": leverage,
            "units": units,
        },
        "stage_gate_config": {
            "stage_c_holdout_days": stage_c_holdout_days,
        },
    }


@pytest.fixture
def tmp_run_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """archive Parquet + summary.json を tmp に整備し path を返す。"""
    archive_dir = tmp_path / ".cache" / "alpha_factory" / "runs"
    run_reports_dir = tmp_path / "reports" / "run-reports"
    output_dir = tmp_path / "reports" / "alpha-sieve"
    monkeypatch.setattr(sieve_mod, "ARCHIVE_DIR", archive_dir)
    monkeypatch.setattr(sieve_mod, "RUN_REPORTS_DIR", run_reports_dir)
    monkeypatch.setattr(sieve_mod, "OUTPUT_DIR", output_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    run_reports_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        tmp_path=tmp_path,
        archive_dir=archive_dir,
        run_reports_dir=run_reports_dir,
        output_dir=output_dir,
    )


# ---------------------------------------------------------------------------
# 1-5: _judge boundary tests
# ---------------------------------------------------------------------------


def test_judge_pass() -> None:
    cfg = sieve_mod.SieveConfig()
    passed, reasons = sieve_mod._judge(
        sharpe=0.6, total_pnl=1.0, trade_count=30, sieve_config=cfg
    )
    assert passed is True
    assert reasons == ()


def test_judge_sharpe_fail_at_boundary() -> None:
    """sharpe == 0.5 は strict gt のため不通過。"""
    cfg = sieve_mod.SieveConfig()
    passed, reasons = sieve_mod._judge(
        sharpe=0.5, total_pnl=1.0, trade_count=30, sieve_config=cfg
    )
    assert passed is False
    assert any("sharpe" in r for r in reasons)


def test_judge_trade_count_fail_below_30() -> None:
    cfg = sieve_mod.SieveConfig()
    passed, reasons = sieve_mod._judge(
        sharpe=0.6, total_pnl=1.0, trade_count=29, sieve_config=cfg
    )
    assert passed is False
    assert any("trade_count" in r for r in reasons)


def test_judge_pnl_fail_at_boundary() -> None:
    """total_pnl == 0.0 は strict gt のため不通過。"""
    cfg = sieve_mod.SieveConfig()
    passed, reasons = sieve_mod._judge(
        sharpe=0.6, total_pnl=0.0, trade_count=30, sieve_config=cfg
    )
    assert passed is False
    assert any("total_pnl" in r for r in reasons)


def test_judge_sharpe_none() -> None:
    cfg = sieve_mod.SieveConfig()
    passed, reasons = sieve_mod._judge(
        sharpe=None, total_pnl=1.0, trade_count=30, sieve_config=cfg
    )
    assert passed is False
    assert "sharpe_unavailable" in reasons


# ---------------------------------------------------------------------------
# 6-7: archive loader
# ---------------------------------------------------------------------------


def test_load_stage_c_passers_filters_correctly(tmp_path: Path) -> None:
    parquet_path = tmp_path / "test.parquet"
    rows = [
        _make_archive_row(individual_name="g0_i0", stage_c_pass=True),
        _make_archive_row(individual_name="g0_i1", stage_c_pass=False),
        _make_archive_row(individual_name="g0_i2", stage_c_pass=True),
    ]
    _write_archive(parquet_path, rows)
    candidates = sieve_mod._load_stage_c_passers(parquet_path)
    names = sorted(c.individual_name for c in candidates)
    assert names == ["g0_i0", "g0_i2"]


def test_load_stage_c_passers_empty_when_no_pass(tmp_path: Path) -> None:
    parquet_path = tmp_path / "test.parquet"
    rows = [
        _make_archive_row(individual_name="g0_i0", stage_c_pass=False),
        _make_archive_row(individual_name="g0_i1", stage_c_pass=False),
    ]
    _write_archive(parquet_path, rows)
    assert sieve_mod._load_stage_c_passers(parquet_path) == []


# ---------------------------------------------------------------------------
# 8-10: main flow (no archive / no_candidates / no_data)
# ---------------------------------------------------------------------------


def test_main_no_archive_returns_1(
    tmp_run_setup: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # summary を作るが archive は作らない
    run_dir = tmp_run_setup.run_reports_dir / "run-99"
    run_dir.mkdir(parents=True)
    summary_path = run_dir / "summary.json"
    summary_path.write_text(
        json.dumps(_make_summary()), encoding="utf-8"
    )
    rc = sieve_mod.main(
        ["--run-number", "99", "--config", str(DEFAULT_CONFIG_PATH)]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "archive not found" in err


def test_main_no_candidates_writes_report(
    tmp_run_setup: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_dir = tmp_run_setup.run_reports_dir / "run-99"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(
        json.dumps(_make_summary()), encoding="utf-8"
    )
    archive_path = (
        tmp_run_setup.archive_dir / "genomes_run_test.parquet"
    )
    _write_archive(
        archive_path,
        [_make_archive_row(individual_name="g0_i0", stage_c_pass=False)],
    )
    rc = sieve_mod.main(
        ["--run-number", "99", "--config", str(DEFAULT_CONFIG_PATH)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "no_candidates" in out
    # report ファイルが存在
    reports = list(tmp_run_setup.output_dir.rglob("sieve-R99.md"))
    assert len(reports) == 1
    text = reports[0].read_text(encoding="utf-8")
    assert "status: no_candidates" in text
    assert "criteria_snapshot" in text


def test_main_no_oos_bars_writes_report(
    tmp_run_setup: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_dir = tmp_run_setup.run_reports_dir / "run-99"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(
        json.dumps(_make_summary()), encoding="utf-8"
    )
    archive_path = (
        tmp_run_setup.archive_dir / "genomes_run_test.parquet"
    )
    _write_archive(
        archive_path,
        [_make_archive_row(individual_name="g0_i0", stage_c_pass=True)],
    )
    # _load_oos_bars を空 list 返却にモック
    monkeypatch.setattr(
        sieve_mod, "_load_oos_bars", lambda *a, **k: ([], None)
    )
    rc = sieve_mod.main(
        ["--run-number", "99", "--config", str(DEFAULT_CONFIG_PATH)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "no_data" in out
    reports = list(tmp_run_setup.output_dir.rglob("sieve-R99.md"))
    text = reports[0].read_text(encoding="utf-8")
    assert "status: no_data" in text


# ---------------------------------------------------------------------------
# 11: evaluate_one exception handling
# ---------------------------------------------------------------------------


def test_evaluate_one_handles_exception() -> None:
    candidate = sieve_mod.CandidateRow(
        individual_name="g0_i0",
        lane_id="tier1_EUR_JPY",
        instrument="EUR_JPY",
        generation=0,
        genome_json="not a valid json{{{",
        stage_c_sharpe=1.5,
        stage_c_total_pnl=60000.0,
        stage_c_trade_count=80,
    )
    bars = [_dummy_bar()]  # non-empty so we go past the no_data path
    meta = _dummy_meta()
    bt_cfg = _dummy_backtest_config()
    cfg = sieve_mod.SieveConfig()
    result = sieve_mod._evaluate_one(
        candidate=candidate,
        bars=bars,
        meta=meta,
        backtest_config=bt_cfg,
        primitive_evaluator=_NullEvaluator(),
        sieve_config=cfg,
    )
    assert result.status == "system_failure"
    assert "system_failure" in result.reason_codes
    assert result.passed is False


# ---------------------------------------------------------------------------
# 12: report rendering
# ---------------------------------------------------------------------------


def test_render_report_includes_required_sections() -> None:
    cfg = sieve_mod.SieveConfig()
    bt = _dummy_backtest_config()
    text = sieve_mod._render_report(
        status="ok",
        run_id="run_test",
        run_number=99,
        archive_path=Path("/tmp/genomes_run_test.parquet"),
        instrument="EUR_JPY",
        holdout_end=datetime(2026, 5, 31, tzinfo=UTC),
        sieve_config=cfg,
        sieve_start=datetime(2026, 6, 5, tzinfo=UTC),
        sieve_end=datetime(2026, 9, 3, tzinfo=UTC),
        bars_loaded=129600,
        backtest_config=bt,
        candidates=[],
        eval_results=[],
        generated_at=datetime(2026, 4, 24, 14, 44, tzinfo=UTC),
    )
    assert "status: ok" in text
    assert "criteria_snapshot" in text
    assert "cost_model" in text
    assert "sharpe_min: 0.5" in text
    assert "trade_count_min: 30" in text


# ---------------------------------------------------------------------------
# 13: SieveConfig validation
# ---------------------------------------------------------------------------


def test_sieve_config_validates_negative_embargo() -> None:
    with pytest.raises(ValueError, match="sieve_embargo_days"):
        sieve_mod.SieveConfig(sieve_embargo_days=-1)


def test_sieve_config_validates_window_days() -> None:
    with pytest.raises(ValueError, match="sieve_window_days"):
        sieve_mod.SieveConfig(sieve_window_days=0)


# ---------------------------------------------------------------------------
# 14-15: _evaluate_one happy path / no_data
# ---------------------------------------------------------------------------


def test_evaluate_one_success_with_real_backtest() -> None:
    """実 bars + 実 evaluator + ヒステリシス付き Genome で実 backtest を 1 回実施し、

    `status="evaluated"` かつ `oos_sharpe` が float 値（または None だが status は evaluated）に
    なることを検証する（detailed-design.md §3.2 ケース 14）。
    """
    from src.alpha_factory.primitives import RegistryEvaluator, ensure_registered
    from src.dsl.serialize import genome_to_dict

    ensure_registered()
    evaluator = RegistryEvaluator(pair="EUR_JPY")
    genome = _make_minimal_intraday_genome()
    bars = _make_real_bars(n_days=2, step_minutes=60)
    candidate = sieve_mod.CandidateRow(
        individual_name=genome.name,
        lane_id="tier1_EUR_JPY",
        instrument="EUR_JPY",
        generation=0,
        genome_json=json.dumps(genome_to_dict(genome), sort_keys=True),
        stage_c_sharpe=1.0,
        stage_c_total_pnl=50000.0,
        stage_c_trade_count=60,
    )
    bt_cfg = _dummy_backtest_config()
    cfg = sieve_mod.SieveConfig()

    result = sieve_mod._evaluate_one(
        candidate=candidate,
        bars=bars,
        meta=_dummy_meta(),
        backtest_config=bt_cfg,
        primitive_evaluator=evaluator,
        sieve_config=cfg,
    )
    # 成功パス: status="evaluated" かつ exception なし
    assert result.status == "evaluated"
    # backtest が走って trade_count / total_pnl / max_drawdown_pct が確定値で入る
    assert isinstance(result.oos_total_pnl, float)
    assert isinstance(result.oos_trade_count, int)
    assert isinstance(result.oos_max_drawdown_pct, float)
    # oos_sharpe は trade が無いと None になりうる（compute_metrics の仕様）
    assert result.oos_sharpe is None or isinstance(result.oos_sharpe, float)
    # DSR は Phase 2 では恒常 None
    assert result.oos_dsr is None
    # passed の bool 妥当性: reasons と整合
    assert result.passed == (len(result.reason_codes) == 0)


def test_evaluate_one_returns_no_data_for_empty_bars() -> None:
    """空 bars 入力時の早期 return パス。"""
    candidate = sieve_mod.CandidateRow(
        individual_name="g0_i0",
        lane_id="tier1_EUR_JPY",
        instrument="EUR_JPY",
        generation=0,
        genome_json='{"name":"g0_i0"}',
        stage_c_sharpe=1.0,
        stage_c_total_pnl=50000.0,
        stage_c_trade_count=60,
    )
    cfg = sieve_mod.SieveConfig()
    result = sieve_mod._evaluate_one(
        candidate=candidate,
        bars=[],  # empty
        meta=_dummy_meta(),
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=_NullEvaluator(),
        sieve_config=cfg,
    )
    assert result.status == "no_data"
    assert result.reason_codes == ("no_data",)
    assert result.passed is False


# ---------------------------------------------------------------------------
# 16: DSR fail-soft (Phase 2 = always None)
# ---------------------------------------------------------------------------


def test_compute_dsr_safe_returns_none_in_phase2() -> None:
    assert sieve_mod._compute_dsr_safe(sharpe=0.6) is None
    assert sieve_mod._compute_dsr_safe(sharpe=None) is None
    assert sieve_mod._compute_dsr_safe(sharpe=10.0) is None


# ---------------------------------------------------------------------------
# 17-18: _build_oos_backtest_config (YAML SSOT + mismatch warning)
# ---------------------------------------------------------------------------


def test_build_oos_backtest_config_uses_yaml_ssot(tmp_path: Path) -> None:
    """YAML 設定の値が BacktestConfig に反映される (SSOT)。"""
    yaml_path = tmp_path / "min_config.yaml"
    yaml_path.write_text(
        _make_min_yaml(initial_cash="1000000", leverage=25, units=10000),
        encoding="utf-8",
    )
    summary = _make_summary(
        initial_cash="1000000", leverage=25, units=10000
    )
    sieve_start = datetime(2026, 6, 5, tzinfo=UTC)
    sieve_end = datetime(2026, 9, 3, tzinfo=UTC)
    bt_cfg = sieve_mod._build_oos_backtest_config(
        instrument="EUR_JPY",
        summary=summary,
        sieve_start=sieve_start,
        sieve_end=sieve_end,
        config_path=yaml_path,
    )
    assert bt_cfg.instrument == "EUR_JPY"
    assert bt_cfg.start == sieve_start
    assert bt_cfg.end == sieve_end
    assert bt_cfg.initial_cash == Decimal("1000000")
    assert bt_cfg.leverage == 25


def test_build_oos_backtest_config_warns_on_mismatch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    yaml_path = tmp_path / "min_config.yaml"
    yaml_path.write_text(
        _make_min_yaml(initial_cash="1000000", leverage=25, units=10000),
        encoding="utf-8",
    )
    # summary は YAML と異なる initial_cash を持つ
    summary = _make_summary(initial_cash="500000")
    bt_cfg = sieve_mod._build_oos_backtest_config(
        instrument="EUR_JPY",
        summary=summary,
        sieve_start=datetime(2026, 6, 5, tzinfo=UTC),
        sieve_end=datetime(2026, 9, 3, tzinfo=UTC),
        config_path=yaml_path,
    )
    # structlog はデフォルトで stdout に出力。
    # mismatch event 名 + summary/config 値が含まれることを検証。
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "alpha_sieve.backtest_config_mismatch" in out
    assert "initial_cash" in out
    assert "500000" in out
    # YAML 値が反映されていること（summary の 500000 ではなく YAML の 1000000）
    assert bt_cfg.initial_cash == Decimal("1000000")


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_min_yaml(
    *,
    initial_cash: str = "1000000",
    leverage: int = 25,
    units: int = 10000,
) -> str:
    """テスト用 minimal YAML config。"""
    return f"""
dataset:
  instrument: EUR_JPY
  start: "2025-10-01T00:00:00Z"
  end: "2026-04-01T00:00:00Z"
backtest:
  initial_cash: "{initial_cash}"
  leverage: {leverage}
  units: {units}
ga:
  population_size: 4
  generations: 2
  crossover_rate: 0.7
  mutation_rate: 0.3
  tournament_size: 3
  elite_count: 2
  max_depth: 4
  fitness_metric: sharpe
  seed: 42
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
    wf_train_days: 120
    wf_test_days: 20
    wf_step_days: 20
    wf_embargo_days: 1
    median_oos_sharpe_min: 0.20
    positive_fold_min: 0.60
    dsr_min: 0.0
  stage_c:
    holdout_days: 60
    spread_stress_multiplier: 1.5
    spread_stress_min_total_pnl: 0.0
    spread_stress_min_sharpe: 0.0
cross_pair:
  mode: shadow
  aggregator_lambda: 0.5
  pass_criteria:
    sharpe_target_cross_ratio_min: 0.8
    mean_sharpe_cross_min: 0.15
    min_sharpe_cross_min: -0.20
  anchors:
    EUR_JPY: [EUR_USD, USD_JPY]
    USD_JPY: [USD_CAD, EUR_JPY]
    EUR_USD: [EUR_JPY, USD_CAD]
    AUD_JPY: [USD_JPY, EUR_USD]
    USD_CAD: [USD_JPY, EUR_USD]
    USD_ZAR: [USD_CAD, USD_JPY]
swim_lane:
  tier1:
    population_size: 30
    generations: 15
    crossover_rate: 0.7
    mutation_rate: 0.3
    elite_count: 2
  graduation:
    population_size: 40
    seed_strategy: "union_of_tier1_graduates"
  graduation_criteria:
    require_stage_c_pass: true
    require_cross_pair_pass: true
improve_cycle:
  max_cycle_seconds: 3600
  plateau_cycles: 3
  plateau_mutation_bump: 0.05
  mutation_rate_max: 0.6
"""


def _dummy_bar() -> Any:
    """単一 bar の sentinel (non-empty 検査用、実 backtest は通らない想定)."""
    from src.domain.price import Ohlc, PriceBar

    return PriceBar(
        pair_name="EUR_JPY",
        bar_time=datetime(2026, 6, 5, 0, 0, tzinfo=UTC),
        bid=Ohlc(
            open=Decimal("154.000"),
            high=Decimal("154.000"),
            low=Decimal("154.000"),
            close=Decimal("154.000"),
        ),
        ask=Ohlc(
            open=Decimal("154.005"),
            high=Decimal("154.005"),
            low=Decimal("154.005"),
            close=Decimal("154.005"),
        ),
        volume=10,
        complete=True,
    )


def _dummy_meta() -> Any:
    from src.broker.mock import InstrumentMeta

    return InstrumentMeta(
        oanda_name="EUR_JPY",
        base_currency="EUR",
        quote_currency="JPY",
        margin_rate=Decimal("0.04"),
        pip_size=InstrumentMeta.default_pip_size_for_quote("JPY"),
        display_precision=InstrumentMeta.default_display_precision_for_quote("JPY"),
    )


def _dummy_backtest_config() -> BacktestConfig:
    return BacktestConfig(
        instrument="EUR_JPY",
        start=datetime(2026, 6, 5, tzinfo=UTC),
        end=datetime(2026, 9, 3, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=25,
        max_spread_bps=None,
        holding_cost_per_day_bps=Decimal("0"),
        session_close_utc_hours=frozenset({23}),
        bar_minutes=1,
    )


class _NullEvaluator:
    """Primitive 名問わず常に 0.0 を返す dummy evaluator。"""

    def evaluate(self, bars: Any, idx: Any, signal: Any) -> float:
        return 0.0


def _make_minimal_intraday_genome() -> Any:
    """テスト用 minimal Genome (random_genome の seeded 版)。

    real backtest を 1 度回すためのゲノム。primitives registry が
    `ensure_registered()` で投入されている前提。
    """
    import random

    from src.alpha_factory._registry_bridge import build_random_gen_registry
    from src.alpha_factory.primitives import ensure_registered
    from src.ga.random_gen import random_genome

    ensure_registered()
    registry = build_random_gen_registry()
    rng = random.Random(42)
    return random_genome(
        rng=rng,
        name="g0_test",
        units=10000,
        max_clause=1,
        max_depth=2,
        registry=registry,
    )


def _make_real_bars(*, n_days: int = 2, step_minutes: int = 60) -> list[Any]:
    """連続する複数日 UTC bars (intraday 制約クリアのため複数 UTC date 跨ぎ)。

    1 hour 刻みで `n_days` 日分。BacktestConfig.session_close_utc_hours={23} と
    複数日跨ぎの両方で intraday 制約を担保する。
    """
    from src.domain.price import Ohlc, PriceBar

    bars: list[Any] = []
    base_time = datetime(2026, 6, 5, 0, 0, tzinfo=UTC)
    base_mid = Decimal("154.000")
    n_bars = n_days * (24 * 60 // step_minutes)
    for i in range(n_bars):
        # 微小変動: 0.001 刻みで sin-like パターン
        tick = Decimal(str((i % 10) * 0.001))
        mid = base_mid + tick
        spread = Decimal("0.005")
        bars.append(
            PriceBar(
                pair_name="EUR_JPY",
                bar_time=base_time + (i * timedelta_safe(step_minutes)),
                bid=Ohlc(open=mid, high=mid, low=mid, close=mid),
                ask=Ohlc(
                    open=mid + spread,
                    high=mid + spread,
                    low=mid + spread,
                    close=mid + spread,
                ),
                volume=10,
                complete=True,
            )
        )
    return bars


def timedelta_safe(minutes: int):
    from datetime import timedelta

    return timedelta(minutes=minutes)
