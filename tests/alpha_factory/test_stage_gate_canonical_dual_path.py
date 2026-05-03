"""B Phase 2 切替コミット step 1: stage_gate.py dual-path canonical 5 metrics test.

設計参照: devnotes/20260503-1024-B-phase2-step1-canonical-metrics/detailed-design.md § 4.4

8 ケース minimum:
- test 9: dual_path_log_only_legacy_unchanged (= regression 0)
- test 10: dual_path_canonical_sidecar_logged
- test 11: dual_path_canonical_skipped_on_naive_datetime (= 例外 fallback)
- test 12: dual_path_disabled_mode_skips_canonical
- test 13: dual_path_empty_trades_returns_canonical_with_reason_codes
- test 14: dual_path_interpretation_note_included_in_log (= 方向性監視規約)
- test 15: phase2_config_rejects_fail_closed (Codex [W4])
- test 16: dual_path_does_not_modify_payload_or_archive_schema (Codex [W5])
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.alpha_factory.config import Phase2Config
from src.alpha_factory.stage_gate import (
    StageGateConfig,
    _try_evaluate_canonical_five_safe,
)
from src.broker.orders import Trade as BrokerTrade
from src.domain.price import Ohlc, PriceBar


def _bt(
    *,
    pid: int = 1,
    side: str = "long",
    entry_time: datetime,
    exit_time: datetime,
    pnl: Decimal = Decimal("100"),
) -> BrokerTrade:
    return BrokerTrade(
        position_id=pid,
        instrument="USD_JPY",
        side=side,  # type: ignore[arg-type]
        units=1000,
        entry_price=Decimal("150.00"),
        entry_time=entry_time,
        exit_price=Decimal("150.10"),
        exit_time=exit_time,
        pnl=pnl,
        exit_reason="signal",  # type: ignore[arg-type]
        equity_at_entry=Decimal("1000000"),
    )


def _bar(bar_time: datetime) -> PriceBar:
    bid = Decimal("150.00")
    ask = Decimal("150.01")
    return PriceBar(
        pair_name="USD_JPY",
        bar_time=bar_time,
        bid=Ohlc(bid, bid, bid, bid),
        ask=Ohlc(ask, ask, ask, ask),
        volume=10,
        complete=True,
    )


def _make_default_live_criteria() -> dict[str, float | int]:
    return {
        "sharpe_min": 1.0,
        "total_pnl_min": 50000,
        "max_drawdown_max": 0.20,
        "trade_count_min": 50,
        "trade_count_max": 5000,
    }


def _make_bars_60d() -> list[PriceBar]:
    """60-day bars covering all 3 buckets (= business_day_universe 全 bucket)."""
    bars = []
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for d in range(5):  # 5 day
        for hour in (3, 12, 20):  # TOKYO / LONDON / NY 各 1 bar
            bars.append(_bar(base + timedelta(days=d, hours=hour)))
    return bars


def _make_trades_50() -> list[BrokerTrade]:
    trades = []
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(50):
        entry = base + timedelta(days=i // 10, hours=11, minutes=30)
        exit = base + timedelta(days=i // 10, hours=12, minutes=i % 10)
        trades.append(_bt(pid=i, entry_time=entry, exit_time=exit))
    return trades


# --- test 11: skip on naive datetime ----------------------------------------


def test_dual_path_canonical_skipped_on_naive_datetime(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """broker Trade.exit_time が naive datetime → adapter で ValueError raise →
    helper が catch して None 返り、 既存判定経路は不変. structlog log で
    canonical_five.skipped event が出る."""
    naive_entry = datetime(2026, 1, 5, 11, 30)  # naive (no tzinfo)
    naive_exit = datetime(2026, 1, 5, 12, 0)
    trades = [_bt(entry_time=naive_entry, exit_time=naive_exit)]
    bars = _make_bars_60d()
    equity_curve = [
        (datetime(2026, 1, 1, tzinfo=UTC), Decimal("1000000")),
        (datetime(2026, 1, 2, tzinfo=UTC), Decimal("1000100")),
    ]

    result = _try_evaluate_canonical_five_safe(
        trades=trades,
        equity_curve=equity_curve,
        bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=60,
        stage_label="A",
        genome_name="g_test",
        enabled=True,
    )

    assert result is None  # 例外 fallback で None
    # structlog 経由 log を stdout/stderr で確認
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "canonical_five.skipped" in combined or "skipped" in combined.lower()


# --- test 12: disabled mode skips canonical ---------------------------------


def test_dual_path_disabled_mode_skips_canonical() -> None:
    """phase2_canonical_metrics_mode=disabled で canonical 計算 skip (None 返り)."""
    trades = _make_trades_50()
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]

    result = _try_evaluate_canonical_five_safe(
        trades=trades,
        equity_curve=equity_curve,
        bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=60,
        stage_label="A",
        genome_name="g_test",
        enabled=False,  # disabled
    )

    assert result is None


# --- test 13: empty trades returns canonical with reason codes --------------


def test_dual_path_empty_trades_returns_canonical_with_reason_codes() -> None:
    """trades 空でも evaluate_canonical_five が no-raise で reason 含む結果を返す."""
    trades: list[BrokerTrade] = []
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]

    result = _try_evaluate_canonical_five_safe(
        trades=trades,
        equity_curve=equity_curve,
        bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=60,
        stage_label="A",
        genome_name="g_test",
        enabled=True,
    )

    # canonical evaluate は no-raise で reason 含む結果を返す
    assert result is not None
    # INPUT_EMPTY_TRADE_LIST が reason に入る (= synthesis § 6.6 / canonical_metrics
    # の no-raise 契約)
    assert not result.invariants.is_feasible
    assert any(
        "empty_trade" in str(rc).lower()
        for rc in result.invariants.infeasible_reason_codes
    )


# --- test 15: Phase2Config rejects fail_closed (Codex [W4]) ------------------


def test_phase2_config_rejects_fail_closed() -> None:
    """Phase2Config(canonical_metrics_mode="fail_closed") は ValueError raise
    (= step 1 で fail_closed 不許容契約、 Codex Round 1 [Warning] 4 取込)."""
    with pytest.raises(ValueError, match="fail_closed は step 1 範囲外"):
        Phase2Config(canonical_metrics_mode="fail_closed")  # type: ignore[arg-type]


def test_phase2_config_accepts_log_only_and_disabled() -> None:
    """Phase2Config は log_only / disabled の 2 値のみ許容."""
    Phase2Config(canonical_metrics_mode="log_only")
    Phase2Config(canonical_metrics_mode="disabled")
    # default は log_only
    assert Phase2Config().canonical_metrics_mode == "log_only"


# --- test 16: payload / archive schema unchanged (Codex [W5]) ---------------


def test_dual_path_does_not_modify_payload_or_archive_schema() -> None:
    """canonical_sidecar が StageResult.metrics["payload"] にも archive Parquet にも
    添付されないことを **実コード出力で検証** (= regression 0、 Codex impl-review
    Round 1 [Critical] 取込で実 evaluate_stage_a 呼出に置換)."""
    from src.alpha_factory.stage_gate import evaluate_stage_a
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    cfg = _backtest_config()

    # LOG_ONLY mode (= default)
    log_only_cfg = StageGateConfig(phase2_canonical_metrics_mode="log_only")
    res_log_only = evaluate_stage_a(
        _one_clause_genome("g_log_only"), bars, usd_jpy_meta(), cfg, ev, log_only_cfg,
    )
    payload_log_only = dict(res_log_only.metrics["payload"])  # type: ignore[arg-type]

    # disabled mode
    disabled_cfg = StageGateConfig(phase2_canonical_metrics_mode="disabled")
    res_disabled = evaluate_stage_a(
        _one_clause_genome("g_disabled"), bars, usd_jpy_meta(), cfg, ev, disabled_cfg,
    )
    payload_disabled = dict(res_disabled.metrics["payload"])  # type: ignore[arg-type]

    # 両 mode で payload keys 完全一致 (= canonical_sidecar 非添付、 schema 不変)
    assert set(payload_log_only.keys()) == set(payload_disabled.keys())

    # canonical 系 key が一切含まれない
    payload_keys = set(payload_log_only.keys())
    forbidden_substrings = ("canonical", "sidecar", "gate_pass", "gate_worst_gap")
    for key in payload_keys:
        for forbidden in forbidden_substrings:
            assert forbidden not in key.lower(), (
                f"payload key {key!r} contains forbidden substring {forbidden!r} "
                f"(= step 1 canonical_sidecar 非添付契約違反)"
            )


# --- test 14: interpretation note included (= 直接 helper 経路、 log 内容を assert) ---


def test_log_canonical_dual_path_includes_interpretation_note(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """_log_canonical_dual_path が interpretation_note="direction_monitoring_only"
    と flags_source="default_false" を log に含める (Codex Round 1 [Warning] 2 / 3 取込)."""
    from src.alpha_factory.stage_gate import _log_canonical_dual_path

    trades = _make_trades_50()
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]

    canonical = _try_evaluate_canonical_five_safe(
        trades=trades,
        equity_curve=equity_curve,
        bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=60,
        stage_label="A",
        genome_name="g_test",
        enabled=True,
    )
    assert canonical is not None  # smoke 計算が動くこと

    # legacy BacktestMetrics は trivial dummy で OK (= log 形式 test のため)
    from src.backtest.metrics import BacktestMetrics
    legacy = BacktestMetrics(
        trade_count=50, win_count=25, loss_count=25,
        win_rate=Decimal("0.5"), total_pnl=Decimal("1000"),
        avg_win=Decimal("10"), avg_loss=Decimal("-10"),
        profit_factor=Decimal("1.0"),
        max_drawdown=Decimal("100"), max_drawdown_pct=Decimal("0.1"),
        final_equity=Decimal("1001000"),
        sharpe=Decimal("0.5"), sortino=Decimal("0.6"), calmar=Decimal("0.7"),
        avg_trade_duration=None, max_trade_duration=None,
    )

    _log_canonical_dual_path(
        stage_label="A",
        genome_name="g_test",
        legacy=legacy,
        canonical=canonical,
    )

    # structlog 経由 log を stdout/stderr で確認 (Codex Round 1 [W2] / [W3] 取込)
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "direction_monitoring_only" in combined
    assert "default_false" in combined
    assert "fail_fast_flags_comparable" in combined


# --- test 9 / 10: regression check と sidecar log (= 既存 evaluate_stage_a 統合) ---


def test_dual_path_log_only_legacy_unchanged() -> None:
    """LOG_ONLY mode (= default) と disabled mode で StageResult が完全一致
    (= regression 0、 Codex impl-review Round 1 [Critical] 取込で
    実 evaluate_stage_a 呼出に置換、 C9 falsification-first 達成)."""
    from src.alpha_factory.stage_gate import evaluate_stage_a
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    cfg = _backtest_config()

    # LOG_ONLY mode
    log_only_cfg = StageGateConfig(phase2_canonical_metrics_mode="log_only")
    res_log_only = evaluate_stage_a(
        _one_clause_genome("g_legacy_unchanged"), bars, usd_jpy_meta(), cfg, ev,
        log_only_cfg,
    )

    # disabled mode (= canonical 計算 skip、 legacy 経路のみ)
    disabled_cfg = StageGateConfig(phase2_canonical_metrics_mode="disabled")
    res_disabled = evaluate_stage_a(
        _one_clause_genome("g_legacy_unchanged"), bars, usd_jpy_meta(), cfg, ev,
        disabled_cfg,
    )

    # 判定結果 / passed / reason_codes 完全一致 (= regression 0)
    assert res_log_only.passed == res_disabled.passed
    assert res_log_only.reason_codes == res_disabled.reason_codes
    assert res_log_only.stage == res_disabled.stage

    # Codex impl-review Round 2 [Warning] 取込: payload **全体** の値一致を比較
    # (= 主要 field だけでは regression 0 の反証テストとして弱い、 C9 強化)。
    # wall_time_seconds は計算量差で diff するため除外。
    payload_log = dict(res_log_only.metrics["payload"])  # type: ignore[arg-type]
    payload_dis = dict(res_disabled.metrics["payload"])  # type: ignore[arg-type]
    # key 集合完全一致
    assert set(payload_log.keys()) == set(payload_dis.keys()), (
        f"payload key set differs: log_only={set(payload_log.keys())} "
        f"disabled={set(payload_dis.keys())}"
    )
    # 全 key の値一致
    for key in payload_log:
        assert payload_log[key] == payload_dis[key], (
            f"payload[{key}] differs: log_only={payload_log[key]!r} "
            f"disabled={payload_dis[key]!r}"
        )
    # n_bars は metrics envelope レベル
    assert res_log_only.metrics["n_bars"] == res_disabled.metrics["n_bars"]


def test_stage_gate_config_default_phase2_log_only() -> None:
    """StageGateConfig() default で phase2_canonical_metrics_mode='log_only'."""
    cfg = StageGateConfig()
    assert cfg.phase2_canonical_metrics_mode == "log_only"


def test_stage_gate_config_phase2_disabled() -> None:
    """StageGateConfig で phase2_canonical_metrics_mode='disabled' を設定可能."""
    cfg = StageGateConfig(phase2_canonical_metrics_mode="disabled")
    assert cfg.phase2_canonical_metrics_mode == "disabled"


def test_phase2_disabled_mode_propagates_to_stage_gate_config(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Codex impl-review Round 1 [Critical] 取込:
    yaml の phase2.canonical_metrics_mode が StageGateConfig.phase2_canonical_metrics_mode
    に正しく値伝搬される (= 禁止事項 8 値伝搬漏れ防止) ことを test で固定."""
    from pathlib import Path

    from src.alpha_factory.config import load_config

    yaml_path = tmp_path / "test_config.yaml"
    yaml_path.write_text(
        """
dataset:
  instrument: USD_JPY
  start: '2026-01-01T00:00:00Z'
  end: '2026-01-02T00:00:00Z'
backtest:
  initial_cash: 1000000
  leverage: 10
  session_close_utc_hours: [23]
ga:
  generations: 1
  population_size: 4
  elite_count: 1
  feasibility:
    soft_fitness_minus_inf_to_zero: false
live_criteria:
  sharpe_min: 1.0
  total_pnl_min: 50000
  max_drawdown_max: 0.20
  trade_count_min: 50
  trade_count_max: 5000
stage_gate:
  stage_a_threshold: 0.0
phase2:
  canonical_metrics_mode: disabled
""",
        encoding="utf-8",
    )
    cfg = load_config(Path(yaml_path))
    # phase2 自身が disabled
    assert cfg.phase2.canonical_metrics_mode == "disabled"
    # StageGateConfig にも値伝搬済 (= dataclasses.replace 経路)
    assert cfg.stage_gate.phase2_canonical_metrics_mode == "disabled"


def test_log_canonical_dual_path_exception_does_not_break_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex impl-review Round 2 [Warning] 取込: _log_canonical_dual_path が raise
    しても evaluate_stage_a は完成 (= legacy 経路完全隔離、 C9 falsification-first 強化)."""
    from src.alpha_factory import stage_gate as sg
    from src.alpha_factory.stage_gate import evaluate_stage_a
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    def _failing_log(**kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated logger processor failure")

    monkeypatch.setattr(sg, "_log_canonical_dual_path", _failing_log)

    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    cfg = _backtest_config()
    log_only_cfg = StageGateConfig(phase2_canonical_metrics_mode="log_only")

    # log helper が raise しても evaluate_stage_a は legacy 経路で完了
    res = evaluate_stage_a(
        _one_clause_genome("g_log_failure"), bars, usd_jpy_meta(), cfg, ev, log_only_cfg,
    )
    # 既存 logic で stage A 評価が完了 (= passed / reason_codes が普通に設定される)
    assert res.stage == "A"
    payload = dict(res.metrics["payload"])  # type: ignore[arg-type]
    # 既存 payload の主要 field が出る (= legacy 経路は touch されていない)
    assert "fitness_pen" in payload
    assert "trade_count" in payload
