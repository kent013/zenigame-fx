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


# ============================================================================
# B Phase 2 切替コミット step 1.5: Stage B IS monitor / Stage C base dual-path
# (= 詳細設計 § 7、 21 ケース追加。 設計参照:
#  devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-design.md)
# ============================================================================


def _stage_b_small_cfg(
    *, phase2_canonical_metrics_mode: str = "log_only",
) -> StageGateConfig:
    """Stage B test 用 小規模 WF cfg (= 複数 fold 生成可能、 step 1 fixture 流用)."""
    return StageGateConfig(
        wf_train_days=3,
        wf_test_days=2,
        wf_step_days=2,
        wf_embargo_days=0,
        phase2_canonical_metrics_mode=phase2_canonical_metrics_mode,  # type: ignore[arg-type]
    )


# --- Stage B IS dual-path (7 ケース) -----------------------------------------


def test_stage_b_is_canonical_dual_path_log_only_preserves_legacy_payload() -> None:
    """LOG_ONLY mode と disabled mode で Stage B の StageResult 全体が完全一致
    (= regression 0、 acceptance A1、 deep dict comparison)."""
    from src.alpha_factory.stage_gate import evaluate_stage_b
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    bars = _make_continuous_bars(20, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    cfg = _backtest_config()

    log_only_cfg = _stage_b_small_cfg(phase2_canonical_metrics_mode="log_only")
    disabled_cfg = _stage_b_small_cfg(phase2_canonical_metrics_mode="disabled")
    res_log = evaluate_stage_b(
        _one_clause_genome("g_b_legacy_unchanged"), bars, usd_jpy_meta(), cfg, ev,
        log_only_cfg,
    )
    res_dis = evaluate_stage_b(
        _one_clause_genome("g_b_legacy_unchanged"), bars, usd_jpy_meta(), cfg, ev,
        disabled_cfg,
    )

    # 判定 / reason_codes / stage 完全一致
    assert res_log.passed == res_dis.passed
    assert res_log.reason_codes == res_dis.reason_codes
    assert res_log.stage == res_dis.stage

    # payload 全体一致 (wall_time_seconds は除外)
    payload_log = dict(res_log.metrics["payload"])  # type: ignore[arg-type]
    payload_dis = dict(res_dis.metrics["payload"])  # type: ignore[arg-type]
    assert set(payload_log.keys()) == set(payload_dis.keys())
    for key in payload_log:
        assert payload_log[key] == payload_dis[key], (
            f"Stage B payload[{key}] differs"
        )


def test_stage_b_is_canonical_log_isolation_when_canonical_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_try_evaluate_canonical_five_safe が raise した場合、 Stage B IS monitor の
    outer try except で巻き取られる (= IS monitor 値は default で base 値ベース)。
    Codex impl-review Round 1 [Warning] 反映: 「raise しても evaluate_stage_b が
    完走し、 per-fold OOS 経路と StageResult 構造が legacy 経路相当」を確認。

    注: 「baseline 完全一致」 (= 厳密 deep equality) は IS monitor outer try で
    巻き取られた場合に is_full_* が default になる場合があり厳密 deep equality は
    崩れる。 step 1.5 では「raise しないこと + StageResult 構造が evaluate_stage_b
    の本来仕様で出力される」 までを acceptance とする (= 詳細設計 § 8 acceptance B1)."""
    from src.alpha_factory import stage_gate as sg
    from src.alpha_factory.stage_gate import evaluate_stage_b
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    def _raising(**kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated canonical failure")

    monkeypatch.setattr(sg, "_try_evaluate_canonical_five_safe", _raising)

    bars = _make_continuous_bars(20, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)

    res = evaluate_stage_b(
        _one_clause_genome("g_b_canonical_fail"), bars, usd_jpy_meta(),
        _backtest_config(), ev, _stage_b_small_cfg(),
    )
    # 1. legacy 経路で stage B 評価が完成 (= raise しない)
    assert res.stage == "B"
    # 2. per-fold OOS 経路は IS monitor の outer try と独立、 reason_codes / passed
    #    は per-fold 結果に依存する (= canonical raise の影響を受けない)
    payload = dict(res.metrics["payload"])  # type: ignore[arg-type]
    # legacy field が必ず出る (= per-fold ベースの集約)
    assert "n_fold" in payload
    assert "n_fold_unavailable" in payload
    assert "median_oos_sharpe" in payload
    assert "positive_fold_ratio" in payload
    # 3. is_full_* (= IS monitor 由来) は outer try で巻き取られる場合 default 値
    #    (= IS monitor 失敗時の design)。 type は維持
    assert "is_full_total_pnl" in payload
    assert "is_full_trade_count" in payload


def test_stage_b_is_canonical_log_helper_isolation_when_log_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_log_canonical_dual_path が raise しても Stage B IS legacy 経路不変."""
    from src.alpha_factory import stage_gate as sg
    from src.alpha_factory.stage_gate import evaluate_stage_b
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    def _failing_log(**kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated logger processor failure (Stage B IS)")

    monkeypatch.setattr(sg, "_log_canonical_dual_path", _failing_log)

    bars = _make_continuous_bars(20, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res = evaluate_stage_b(
        _one_clause_genome("g_b_log_fail"), bars, usd_jpy_meta(),
        _backtest_config(), ev, _stage_b_small_cfg(),
    )
    # log helper raise しても legacy 経路完成
    assert res.stage == "B"
    payload = dict(res.metrics["payload"])  # type: ignore[arg-type]
    assert "n_fold" in payload
    assert "is_full_total_pnl" in payload  # IS monitor 値も出る


def test_stage_b_is_canonical_disabled_mode_skips_calculation() -> None:
    """phase2_canonical_metrics_mode='disabled' で canonical 計算 skip (= None 返り)."""
    trades: list[BrokerTrade] = []
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]
    result = _try_evaluate_canonical_five_safe(
        trades=trades, equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=540,  # Stage B IS 想定
        stage_label="B_IS", genome_name="g_b_disabled",
        enabled=False,
    )
    assert result is None


def test_stage_b_is_canonical_succeeds_for_18m_window(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Stage B IS dual-path log entry が stage='B_IS' で出力されることを確認
    + 必須キー (stage / genome / interpretation_note / canonical_*) 含有
    (= acceptance B1 / B5 / C1-C3、 Codex impl-review Round 1 [Warning] 反映で
    event-key 検証に強化)."""
    from src.alpha_factory.stage_gate import evaluate_stage_b
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    bars = _make_continuous_bars(20, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res = evaluate_stage_b(
        _one_clause_genome("g_b_log_check"), bars, usd_jpy_meta(),
        _backtest_config(), ev, _stage_b_small_cfg(),
    )
    assert res.stage == "B"
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # B_IS stage label の dual-path log entry が出ている
    assert "stage=B_IS" in combined
    # canonical_five.dual_path event が出る (= step 1 と同型 log helper、 acceptance C1)
    assert "stage_gate.canonical_five.dual_path" in combined
    # genome 必須キー (= B5、 helper 引数 genome_name → logger kwargs key genome)
    assert "genome=g_b_log_check" in combined
    # interpretation_note (= C3、 step 1 規約継承)
    assert "interpretation_note=direction_monitoring_only" in combined
    # canonical_* と legacy_* が共存 (= C2)
    assert "canonical_trade_count=" in combined
    assert "legacy_trade_count=" in combined


def test_stage_b_is_canonical_handles_empty_trades_gracefully() -> None:
    """trades=[] でも _try_evaluate_canonical_five_safe が non-raise で動作."""
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]
    result = _try_evaluate_canonical_five_safe(
        trades=[], equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=540, stage_label="B_IS", genome_name="g_b_empty",
        enabled=True,
    )
    # canonical evaluate は no-raise で reason 含む結果を返す
    assert result is not None
    assert not result.invariants.is_feasible


def test_stage_b_is_canonical_handles_single_trade() -> None:
    """trades=[1 trade] (= 境界条件) でも crash なく動作."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    trades = [
        _bt(pid=0, entry_time=base + timedelta(hours=11),
            exit_time=base + timedelta(hours=12)),
    ]
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]
    result = _try_evaluate_canonical_five_safe(
        trades=trades, equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=540, stage_label="B_IS", genome_name="g_b_single",
        enabled=True,
    )
    assert result is not None
    assert result.trade_count == 1


# --- Stage C base dual-path (7 ケース) ---------------------------------------


def test_stage_c_base_canonical_dual_path_log_only_preserves_legacy_payload() -> None:
    """LOG_ONLY mode と disabled mode で Stage C の StageResult 全体が完全一致
    (= regression 0、 acceptance A1)."""
    from src.alpha_factory.stage_gate import evaluate_stage_c
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

    log_only_cfg = StageGateConfig(phase2_canonical_metrics_mode="log_only")
    disabled_cfg = StageGateConfig(phase2_canonical_metrics_mode="disabled")
    res_log = evaluate_stage_c(
        _one_clause_genome("g_c_legacy_unchanged"), bars, usd_jpy_meta(), cfg, ev,
        log_only_cfg,
    )
    res_dis = evaluate_stage_c(
        _one_clause_genome("g_c_legacy_unchanged"), bars, usd_jpy_meta(), cfg, ev,
        disabled_cfg,
    )
    assert res_log.passed == res_dis.passed
    assert res_log.reason_codes == res_dis.reason_codes
    assert res_log.stage == res_dis.stage
    payload_log = dict(res_log.metrics["payload"])  # type: ignore[arg-type]
    payload_dis = dict(res_dis.metrics["payload"])  # type: ignore[arg-type]
    assert set(payload_log.keys()) == set(payload_dis.keys())
    for key in payload_log:
        assert payload_log[key] == payload_dis[key], (
            f"Stage C payload[{key}] differs"
        )


def test_stage_c_base_canonical_log_isolation_when_canonical_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_try_evaluate_canonical_five_safe が raise した場合、 Stage C base evaluation の
    outer try except で巻き取られ、 base_failed=True で system_failure reason 化する。
    Codex impl-review Round 1 [Warning] 反映: 「raise しても evaluate_stage_c が
    完走し、 stress / cross_pair 経路は影響なし」を確認。

    注: canonical raise が outer try で巻き取られると base evaluation 自体が
    failure になるため、 「legacy 完全不変」 ではなく 「raise しないこと + stress /
    cross_pair 経路が独立に動作する」 までを acceptance とする (= 詳細設計 § 8
    acceptance B1、 Round 1 [Warning] 反映で文言を緩和)."""
    from src.alpha_factory import stage_gate as sg
    from src.alpha_factory.stage_gate import evaluate_stage_c
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    def _raising(**kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated canonical failure")

    monkeypatch.setattr(sg, "_try_evaluate_canonical_five_safe", _raising)

    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res = evaluate_stage_c(
        _one_clause_genome("g_c_canonical_fail"), bars, usd_jpy_meta(),
        _backtest_config(), ev, StageGateConfig(),
    )
    # 1. legacy 経路で stage C 評価が完成 (= raise しない)
    assert res.stage == "C"
    # 2. canonical raise → outer try で巻き取られ system_failure reason 化
    assert "system_failure" in res.reason_codes
    # 3. stress / cross_pair payload は独立経路で出る
    payload = dict(res.metrics["payload"])  # type: ignore[arg-type]
    assert "stress" in payload
    assert "cross_pair" in payload


def test_stage_c_base_canonical_log_helper_isolation_when_log_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_log_canonical_dual_path が raise しても Stage C legacy 経路不変."""
    from src.alpha_factory import stage_gate as sg
    from src.alpha_factory.stage_gate import evaluate_stage_c
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    def _failing_log(**kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated logger processor failure (Stage C base)")

    monkeypatch.setattr(sg, "_log_canonical_dual_path", _failing_log)

    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res = evaluate_stage_c(
        _one_clause_genome("g_c_log_fail"), bars, usd_jpy_meta(),
        _backtest_config(), ev, StageGateConfig(),
    )
    # log helper raise しても legacy 経路完成
    assert res.stage == "C"
    payload = dict(res.metrics["payload"])  # type: ignore[arg-type]
    assert "trade_sharpe_raw" in payload
    assert "live_criteria_pass" in payload  # legacy 評価値が出る


def test_stage_c_base_canonical_disabled_mode_skips_calculation() -> None:
    """phase2_canonical_metrics_mode='disabled' (= Stage C window_days=60) で skip."""
    trades: list[BrokerTrade] = []
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]
    result = _try_evaluate_canonical_five_safe(
        trades=trades, equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=60, stage_label="C_base", genome_name="g_c_disabled",
        enabled=False,
    )
    assert result is None


def test_stage_c_base_canonical_succeeds_for_60d_holdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Stage C base dual-path log entry が stage='C_base' で出力されることを確認
    + 必須キー含有 (= acceptance B1 / B5 / C1-C3、 event-key 検証強化)."""
    from src.alpha_factory.stage_gate import evaluate_stage_c
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res = evaluate_stage_c(
        _one_clause_genome("g_c_log_check"), bars, usd_jpy_meta(),
        _backtest_config(), ev, StageGateConfig(),
    )
    assert res.stage == "C"
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # C_base stage label の dual-path log entry が出ている
    assert "stage=C_base" in combined
    assert "stage_gate.canonical_five.dual_path" in combined
    # genome 必須キー (= B5、 logger kwargs key genome)
    assert "genome=g_c_log_check" in combined
    # interpretation_note 継承 (= C3)
    assert "interpretation_note=direction_monitoring_only" in combined
    # canonical_* / legacy_* 共存 (= C2)
    assert "canonical_trade_count=" in combined
    assert "legacy_trade_count=" in combined


def test_stage_c_base_canonical_handles_empty_trades_gracefully() -> None:
    """Stage C base: trades=[] (= holdout で 0 trade) でも non-raise."""
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]
    result = _try_evaluate_canonical_five_safe(
        trades=[], equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=60, stage_label="C_base", genome_name="g_c_empty",
        enabled=True,
    )
    assert result is not None
    assert not result.invariants.is_feasible


def test_stage_c_base_canonical_handles_single_trade() -> None:
    """Stage C base: 単一 trade 境界条件で crash なし."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    trades = [
        _bt(pid=0, entry_time=base + timedelta(hours=11),
            exit_time=base + timedelta(hours=12)),
    ]
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]
    result = _try_evaluate_canonical_five_safe(
        trades=trades, equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=60, stage_label="C_base", genome_name="g_c_single",
        enabled=True,
    )
    assert result is not None
    assert result.trade_count == 1


# --- ゴールデン回帰 (= 各 stage 成功 / 失敗 / 境界 3 群 = 6 ケース) ---


def _golden_50_trades_fixture() -> tuple[list[BrokerTrade], list[PriceBar], list[tuple[datetime, Decimal]]]:
    """成功群: 50 trades + bars_60d + flat equity_curve."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    trades = []
    for i in range(50):
        entry = base + timedelta(days=i // 10, hours=11, minutes=30)
        exit = base + timedelta(days=i // 10, hours=12, minutes=i % 10)
        trades.append(_bt(pid=i, entry_time=entry, exit_time=exit))
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]
    return trades, bars, equity_curve


def _golden_single_trade_fixture() -> tuple[list[BrokerTrade], list[PriceBar], list[tuple[datetime, Decimal]]]:
    """境界群: 1 trade + bars_60d + flat equity_curve."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    trades = [
        _bt(pid=0, entry_time=base + timedelta(hours=11),
            exit_time=base + timedelta(hours=12)),
    ]
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]
    return trades, bars, equity_curve


def _assert_canonical_golden(
    result, *, trade_count: int, net_pnl: float, is_feasible: bool,
) -> None:
    """Codex impl-review Round 1 [Critical] 反映: canonical sidecar 主要 field を
    fixture-locked 期待値で比較 (= 退行検知強度の確保、 acceptance A5)。

    現 fixture (= bars_60d 5d × 3 bucket = 15 bars、 flat equity = 1M JPY、
    pnl=100/trade で固定) では session-block 集約結果は以下に決定:
    - net_pnl_after_cost = trade_count × 100 (= pnl 線形和)
    - max_dd = 0.0 (= flat equity)
    - sr_session_worst_block_scale = 0.0 (= flat equity)
    - sr_session_worst_annual_estimate = 0.0
    - session_block_win_rate_worst = 0.5 (= synthesis § 6.4 neutral)
    - gate_pass = False (= sharpe_min=1.0 を満たさない)
    - gate_worst_gap = 1.0 (= sharpe_min - 0 = 1.0)
    """
    assert result is not None
    assert result.trade_count == trade_count
    assert result.net_pnl_after_cost == pytest.approx(net_pnl, abs=1e-9)
    assert result.max_dd == pytest.approx(0.0, abs=1e-9)
    assert result.sr_session_worst_block_scale == pytest.approx(0.0, abs=1e-9)
    assert result.sr_session_worst_annual_estimate == pytest.approx(0.0, abs=1e-9)
    assert result.session_block_win_rate_worst == pytest.approx(0.5, abs=1e-9)
    assert result.gate_pass is False
    assert result.gate_worst_gap == pytest.approx(1.0, abs=1e-9)
    assert result.invariants.is_feasible is is_feasible


def test_stage_b_is_canonical_golden_success_genome() -> None:
    """Stage B IS: 成功群 (= 50 trades) で canonical sidecar が fixture-locked
    期待値と一致 (= acceptance A5、 Codex impl-review Round 1 [Critical] 反映)."""
    trades, bars, equity_curve = _golden_50_trades_fixture()
    result = _try_evaluate_canonical_five_safe(
        trades=trades, equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=540, stage_label="B_IS", genome_name="g_b_golden_success",
        enabled=True,
    )
    _assert_canonical_golden(
        result, trade_count=50, net_pnl=5000.0, is_feasible=True,
    )


def test_stage_b_is_canonical_golden_failure_genome() -> None:
    """Stage B IS: 失敗群 (= 0 trade) で feasibility=False + golden 値一致."""
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]
    result = _try_evaluate_canonical_five_safe(
        trades=[], equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=540, stage_label="B_IS", genome_name="g_b_golden_failure",
        enabled=True,
    )
    _assert_canonical_golden(
        result, trade_count=0, net_pnl=0.0, is_feasible=False,
    )


def test_stage_b_is_canonical_golden_boundary_genome() -> None:
    """Stage B IS: 境界群 (= 1 trade) で fixture-locked 値一致 (= gate_pass=False 固定)."""
    trades, bars, equity_curve = _golden_single_trade_fixture()
    result = _try_evaluate_canonical_five_safe(
        trades=trades, equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=540, stage_label="B_IS", genome_name="g_b_golden_boundary",
        enabled=True,
    )
    _assert_canonical_golden(
        result, trade_count=1, net_pnl=100.0, is_feasible=True,
    )


def test_stage_c_base_canonical_golden_success_genome() -> None:
    """Stage C base: 成功群 (= 50 trades) で fixture-locked 値一致."""
    trades, bars, equity_curve = _golden_50_trades_fixture()
    result = _try_evaluate_canonical_five_safe(
        trades=trades, equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=60, stage_label="C_base", genome_name="g_c_golden_success",
        enabled=True,
    )
    _assert_canonical_golden(
        result, trade_count=50, net_pnl=5000.0, is_feasible=True,
    )


def test_stage_c_base_canonical_golden_failure_genome() -> None:
    """Stage C base: 失敗群 (= 0 trade) で fixture-locked 値一致."""
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]
    result = _try_evaluate_canonical_five_safe(
        trades=[], equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=60, stage_label="C_base", genome_name="g_c_golden_failure",
        enabled=True,
    )
    _assert_canonical_golden(
        result, trade_count=0, net_pnl=0.0, is_feasible=False,
    )


def test_stage_c_base_canonical_golden_boundary_genome() -> None:
    """Stage C base: 境界群 (= 1 trade) で fixture-locked 値一致."""
    trades, bars, equity_curve = _golden_single_trade_fixture()
    result = _try_evaluate_canonical_five_safe(
        trades=trades, equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=60, stage_label="C_base", genome_name="g_c_golden_boundary",
        enabled=True,
    )
    _assert_canonical_golden(
        result, trade_count=1, net_pnl=100.0, is_feasible=True,
    )


# --- 並列 log key 一意性 (= 1 ケース) ---


def test_stage_b_is_and_c_base_log_keys_are_distinguishable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Stage B IS と Stage C base の dual-path log が同 worker / 同 genome で
    連続実行された場合、 stage='B_IS' と stage='C_base' が独立 entry として
    記録され、 logger kwargs key (`genome` + `stage`) で一意特定可能であることを確認
    (= § 4.6 ログ命名規約 SSOT 準拠。 注: helper 引数名は genome_name だが
    logger kwargs key は genome で統一)."""
    from src.alpha_factory.stage_gate import evaluate_stage_b, evaluate_stage_c
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    bars = _make_continuous_bars(20, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    cfg = _backtest_config()
    genome_name = "g_log_keys_test"
    # Stage B IS
    res_b = evaluate_stage_b(
        _one_clause_genome(genome_name), bars, usd_jpy_meta(), cfg, ev,
        _stage_b_small_cfg(),
    )
    # Stage C base
    res_c = evaluate_stage_c(
        _one_clause_genome(genome_name), _make_continuous_bars(2, bars_per_day=4),
        usd_jpy_meta(), cfg, ev, StageGateConfig(),
    )
    assert res_b.stage == "B"
    assert res_c.stage == "C"
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # 両方の stage label が独立 entry として記録される
    assert "B_IS" in combined
    assert "C_base" in combined
    # genome 値も記録 (= logger kwargs key `genome` は legacy / dual-path 共通)
    assert genome_name in combined


# ============================================================================
# B Phase 2 切替コミット step 1.6: Stage B per-fold dual-path
# (= 詳細設計 § 7、 10 ケース追加 (= Codex impl-review Round 1 [Suggestion]
# 反映で +1 ケース B_IS/C_base no-fold-kwarg 追加)。 設計参照:
#  devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/detailed-design.md)
# ============================================================================


def _stage_b_multi_fold_cfg(
    *, phase2_canonical_metrics_mode: str = "log_only",
) -> StageGateConfig:
    """Stage B test 用 多 fold 生成可能な cfg (= n_fold ≥ 5、 step 1.5 fixture 流用)。

    n_fold は make_wf_folds(_make_continuous_bars(20), wf_train=3, wf_test=2,
    wf_step=2, wf_embargo=0) で動的決定 (= ~8 fold 想定だが test では値に依存しない、
    Codex Round 1 [Critical] 反映で動的化)。
    """
    return StageGateConfig(
        wf_train_days=3,
        wf_test_days=2,
        wf_step_days=2,
        wf_embargo_days=0,
        phase2_canonical_metrics_mode=phase2_canonical_metrics_mode,  # type: ignore[arg-type]
    )


def _dummy_legacy_metrics():  # type: ignore[no-untyped-def]
    """test 用 dummy BacktestMetrics."""
    from src.backtest.metrics import BacktestMetrics
    return BacktestMetrics(
        trade_count=10, win_count=5, loss_count=5,
        win_rate=Decimal("0.5"), total_pnl=Decimal("100"),
        avg_win=Decimal("10"), avg_loss=Decimal("-10"),
        profit_factor=Decimal("1.0"),
        max_drawdown=Decimal("10"), max_drawdown_pct=Decimal("0.01"),
        final_equity=Decimal("1000100"),
        sharpe=Decimal("0.1"), sortino=Decimal("0.1"), calmar=Decimal("0.1"),
        avg_trade_duration=None, max_trade_duration=None,
    )


# --- 10 ケース (= Round 1 [Suggestion] +1 反映) ---


def test_stage_b_per_fold_canonical_dual_path_log_only_preserves_legacy_payload() -> None:
    """LOG_ONLY mode と disabled mode で Stage B の StageResult 全体が完全一致
    (= regression 0、 acceptance A1。 per-fold dual-path 配線追加で oos_sharpes /
    median_oos_sharpe / positive_fold_ratio / unavailable_reason_counts /
    他全 payload 完全不変)。
    """
    from src.alpha_factory.stage_gate import evaluate_stage_b
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    bars = _make_continuous_bars(20, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    cfg = _backtest_config()
    log_only_cfg = _stage_b_multi_fold_cfg(phase2_canonical_metrics_mode="log_only")
    disabled_cfg = _stage_b_multi_fold_cfg(phase2_canonical_metrics_mode="disabled")
    res_log = evaluate_stage_b(
        _one_clause_genome("g_b_per_fold_legacy_unchanged"), bars, usd_jpy_meta(),
        cfg, ev, log_only_cfg,
    )
    res_dis = evaluate_stage_b(
        _one_clause_genome("g_b_per_fold_legacy_unchanged"), bars, usd_jpy_meta(),
        cfg, ev, disabled_cfg,
    )
    # 判定 / reason_codes / stage 完全一致
    assert res_log.passed == res_dis.passed
    assert res_log.reason_codes == res_dis.reason_codes
    assert res_log.stage == res_dis.stage
    # payload 全体一致 (wall_time_seconds は除外)
    payload_log = dict(res_log.metrics["payload"])  # type: ignore[arg-type]
    payload_dis = dict(res_dis.metrics["payload"])  # type: ignore[arg-type]
    assert set(payload_log.keys()) == set(payload_dis.keys())
    for key in payload_log:
        assert payload_log[key] == payload_dis[key], (
            f"Stage B per-fold payload[{key}] differs"
        )


def test_stage_b_per_fold_canonical_log_isolation_when_canonical_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_try_evaluate_canonical_five_safe` が **stage_label='B_fold' のときだけ**
    raise する wrapper で置換し、 per-fold legacy 判定が完全不変であることを確認。

    Codex Round 1 [Critical] 反映: helper を無条件 raise させると同 helper が
    B_IS でも呼ばれ、 is_full_* が変わって disabled 比較が崩れる。 monkeypatch を
    stage_label 限定 raise の wrapper に変更 (= B_IS 呼出は元 helper に透過)。
    """
    from src.alpha_factory import stage_gate as sg
    from src.alpha_factory.stage_gate import evaluate_stage_b
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    original_helper = sg._try_evaluate_canonical_five_safe

    def _conditional_raise(**kwargs):  # type: ignore[no-untyped-def]
        if kwargs.get("stage_label") == "B_fold":
            raise RuntimeError("simulated B_fold canonical failure")
        return original_helper(**kwargs)

    monkeypatch.setattr(sg, "_try_evaluate_canonical_five_safe", _conditional_raise)

    bars = _make_continuous_bars(20, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)

    # B_fold 限定 raise 版 vs disabled mode で StageResult deep equality (D3)
    res_with_raise = evaluate_stage_b(
        _one_clause_genome("g_b_per_fold_canonical_fail"), bars, usd_jpy_meta(),
        _backtest_config(), ev, _stage_b_multi_fold_cfg(),
    )
    monkeypatch.setattr(sg, "_try_evaluate_canonical_five_safe", original_helper)
    res_disabled = evaluate_stage_b(
        _one_clause_genome("g_b_per_fold_canonical_fail"), bars, usd_jpy_meta(),
        _backtest_config(), ev,
        _stage_b_multi_fold_cfg(phase2_canonical_metrics_mode="disabled"),
    )
    # passed / reason_codes / payload / n_bars 完全一致 (= wall_time_seconds 除外、
    # acceptance D3、 Codex Round 2 [Warning] 反映)
    assert res_with_raise.passed == res_disabled.passed
    assert res_with_raise.reason_codes == res_disabled.reason_codes
    assert res_with_raise.metrics["n_bars"] == res_disabled.metrics["n_bars"]
    payload_raise = dict(res_with_raise.metrics["payload"])  # type: ignore[arg-type]
    payload_dis = dict(res_disabled.metrics["payload"])  # type: ignore[arg-type]
    assert set(payload_raise.keys()) == set(payload_dis.keys())
    for key in payload_raise:
        assert payload_raise[key] == payload_dis[key], (
            f"per-fold canonical raise: payload[{key}] differs"
        )


def test_stage_b_per_fold_canonical_log_helper_isolation_when_log_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_log_canonical_dual_path` が `stage_label='B_fold'` のときだけ raise しても
    per-fold legacy 判定は完全不変 (= acceptance D1, D2、 disabled baseline と
    deep equality、 Codex impl-review Round 1 [Warning] 反映で強化)。
    """
    from src.alpha_factory import stage_gate as sg
    from src.alpha_factory.stage_gate import evaluate_stage_b
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    original_log = sg._log_canonical_dual_path

    def _conditional_log_raise(**kwargs):  # type: ignore[no-untyped-def]
        if kwargs.get("stage_label") == "B_fold":
            raise RuntimeError("simulated B_fold logger processor failure")
        return original_log(**kwargs)

    monkeypatch.setattr(sg, "_log_canonical_dual_path", _conditional_log_raise)
    bars = _make_continuous_bars(20, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res_with_log_raise = evaluate_stage_b(
        _one_clause_genome("g_b_per_fold_log_fail"), bars, usd_jpy_meta(),
        _backtest_config(), ev, _stage_b_multi_fold_cfg(),
    )
    # disabled baseline と deep equality 比較 (= D1 厳密性、 fold_sharpe /
    # fold_reason / reason_counts 全件不変を payload 全 key で確認)
    monkeypatch.setattr(sg, "_log_canonical_dual_path", original_log)
    res_disabled = evaluate_stage_b(
        _one_clause_genome("g_b_per_fold_log_fail"), bars, usd_jpy_meta(),
        _backtest_config(), ev,
        _stage_b_multi_fold_cfg(phase2_canonical_metrics_mode="disabled"),
    )
    assert res_with_log_raise.passed == res_disabled.passed
    assert res_with_log_raise.reason_codes == res_disabled.reason_codes
    assert res_with_log_raise.metrics["n_bars"] == res_disabled.metrics["n_bars"]
    payload_log_raise = dict(res_with_log_raise.metrics["payload"])  # type: ignore[arg-type]
    payload_dis = dict(res_disabled.metrics["payload"])  # type: ignore[arg-type]
    assert set(payload_log_raise.keys()) == set(payload_dis.keys())
    for key in payload_log_raise:
        assert payload_log_raise[key] == payload_dis[key], (
            f"per-fold log helper raise: payload[{key}] differs"
        )


def test_stage_b_per_fold_canonical_disabled_mode_skips_calculation() -> None:
    """phase2_canonical_metrics_mode='disabled' で per-fold canonical 計算 skip。

    helper の enabled=False で adapter / thresholds / evaluate_canonical_five が
    呼ばれないことを確認 (= Codex Round 2 [Warning] 反映で「skip」定義明確化)。
    """
    trades: list[BrokerTrade] = []
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]
    result = _try_evaluate_canonical_five_safe(
        trades=trades, equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=20, stage_label="B_fold", genome_name="g_b_per_fold_disabled",
        enabled=False,  # disabled
    )
    assert result is None  # threshold / adapter / canonical 計算は呼ばれない


def test_stage_b_per_fold_dual_path_emits_one_entry_per_fold(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """各 fold で dual-path log entry が `stage='B_fold'` + `fold=<0..n_fold-1>` で出力。
    (stage, genome, fold) で一意特定可能 (= 識別子契約 SSOT、 acceptance C1, C4)。

    Codex Round 1 [Critical] 反映: n_fold は make_wf_folds で動的取得、
    5 fold hard-code しない。
    """
    from src.alpha_factory.stage_gate import evaluate_stage_b
    from src.alpha_factory.walk_forward import make_wf_folds
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    bars = _make_continuous_bars(20, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    cfg = _stage_b_multi_fold_cfg()
    n_fold_expected = len(make_wf_folds(
        bars,
        train_days=cfg.wf_train_days,
        test_days=cfg.wf_test_days,
        step_days=cfg.wf_step_days,
        embargo_days=cfg.wf_embargo_days,
    ))
    assert n_fold_expected >= 2, "fixture must produce at least 2 folds"
    genome_name = "g_b_per_fold_log_check"
    res = evaluate_stage_b(
        _one_clause_genome(genome_name), bars, usd_jpy_meta(),
        _backtest_config(), ev, cfg,
    )
    assert res.stage == "B"
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # stage='B_fold' を含む dual-path 行を全件抽出
    b_fold_lines = [
        line for line in combined.splitlines()
        if "stage_gate.canonical_five.dual_path" in line and "stage=B_fold" in line
    ]
    assert len(b_fold_lines) == n_fold_expected, (
        f"expected {n_fold_expected} B_fold log entries, got {len(b_fold_lines)}"
    )
    # 各行に fold=0..n_fold-1 が含まれる (set 比較)
    import re
    fold_values: set[int] = set()
    for line in b_fold_lines:
        m = re.search(r"fold=(\d+)", line)
        assert m is not None, f"B_fold line missing fold=: {line}"
        fold_values.add(int(m.group(1)))
    assert fold_values == set(range(n_fold_expected))


def test_log_canonical_dual_path_rejects_b_fold_without_fold_index() -> None:
    """`_log_canonical_dual_path(stage_label='B_fold', fold_index=None)` は
    ValueError raise (= 識別子契約 fail-fast、 acceptance D5)。
    """
    from src.alpha_factory.stage_gate import _log_canonical_dual_path

    with pytest.raises(ValueError, match="fold_index"):
        _log_canonical_dual_path(
            stage_label="B_fold",
            genome_name="g_test",
            legacy=_dummy_legacy_metrics(),
            canonical=None,
            fold_index=None,
        )


def test_stage_b_per_fold_canonical_golden_first_fold_succeeds() -> None:
    """Stage B per-fold: 50 trades fixture で 1 fold 代表の canonical が
    fixture-locked 期待値 (= 50 trades, net_pnl=5000, 他 step 1.5 と同じ deterministic
    出力) と一致 (= acceptance A5)。

    複数 fold での golden は overengineering (= 概念設計 scope)、
    1 fold 代表で deterministic 性確認に十分。
    """
    base = datetime(2026, 1, 1, tzinfo=UTC)
    trades = []
    for i in range(50):
        entry = base + timedelta(days=i // 10, hours=11, minutes=30)
        exit = base + timedelta(days=i // 10, hours=12, minutes=i % 10)
        trades.append(_bt(pid=i, entry_time=entry, exit_time=exit))
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]
    result = _try_evaluate_canonical_five_safe(
        trades=trades, equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=20,  # wf_test_days
        stage_label="B_fold", genome_name="g_b_per_fold_golden",
        enabled=True,
    )
    # step 1.5 と同じ deterministic 出力を期待
    assert result is not None
    assert result.trade_count == 50
    assert result.net_pnl_after_cost == pytest.approx(5000.0, abs=1e-9)
    assert result.max_dd == pytest.approx(0.0, abs=1e-9)
    assert result.session_block_win_rate_worst == pytest.approx(0.5, abs=1e-9)
    assert result.gate_pass is False  # sharpe_min=1.0 を満たさない
    assert result.invariants.is_feasible is True


def test_existing_callers_log_does_not_include_fold_kwarg(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """既存 _log_canonical_dual_path caller (= Stage A / B_IS / C_base) の出力に
    `fold=` kwargs key が含まれないことを確認 (= optional kwarg 追加の後方互換、
    acceptance A4、 Codex Round 2 [Suggestion] 反映)。
    """
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
    res = evaluate_stage_a(
        _one_clause_genome("g_a_no_fold_kwarg"), bars, usd_jpy_meta(),
        _backtest_config(), ev, StageGateConfig(),
    )
    assert res.stage == "A"
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # Stage A の dual-path log 行を取得
    a_lines = [
        line for line in combined.splitlines()
        if "stage_gate.canonical_five.dual_path" in line and "stage=A " in line
    ]
    # fold kwargs key は含まれない (= None default で出力されない)
    for line in a_lines:
        assert "fold=" not in line, (
            f"Stage A dual-path log should not include fold kwarg: {line}"
        )


def test_stage_b_is_and_c_base_log_does_not_include_fold_kwarg(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Stage B IS / Stage C base の dual-path log にも `fold=` kwargs key が
    含まれないことを確認 (= optional kwarg 後方互換補強、 Codex impl-review
    Round 1 [Suggestion] 反映で A4 強化)。
    """
    from src.alpha_factory.stage_gate import evaluate_stage_b, evaluate_stage_c
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    bars = _make_continuous_bars(20, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    cfg = _backtest_config()
    # Stage B IS (= 既存 _stage_b_small_cfg fixture 流用)
    res_b = evaluate_stage_b(
        _one_clause_genome("g_b_is_no_fold_kwarg"), bars, usd_jpy_meta(),
        cfg, ev, _stage_b_small_cfg(),
    )
    # Stage C base
    res_c = evaluate_stage_c(
        _one_clause_genome("g_c_base_no_fold_kwarg"),
        _make_continuous_bars(2, bars_per_day=4),
        usd_jpy_meta(), cfg, ev, StageGateConfig(),
    )
    assert res_b.stage == "B"
    assert res_c.stage == "C"
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # B_IS / C_base log 行に fold kwarg が含まれない
    for stage_marker in ("stage=B_IS", "stage=C_base"):
        lines = [
            line for line in combined.splitlines()
            if "stage_gate.canonical_five.dual_path" in line and stage_marker in line
        ]
        assert len(lines) >= 1, f"expected at least 1 line for {stage_marker}"
        for line in lines:
            assert "fold=" not in line, (
                f"{stage_marker} dual-path log should not include fold kwarg: {line}"
            )


def test_stage_b_per_fold_canonical_skipped_path_includes_fold_kwarg(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """phase2_canonical_metrics_mode='disabled' で `stage='B_fold'` log entry が
    出る場合、 すべての行に `fold=` kwargs key が含まれる (= acceptance C5)。

    Codex Round 1 [Warning] 反映: canonical_skipped=True path でも
    fold kwarg は識別子契約 SSOT で必須。
    """
    from src.alpha_factory.stage_gate import evaluate_stage_b
    from src.alpha_factory.walk_forward import make_wf_folds
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    bars = _make_continuous_bars(20, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    cfg = _stage_b_multi_fold_cfg(phase2_canonical_metrics_mode="disabled")
    n_fold_expected = len(make_wf_folds(
        bars,
        train_days=cfg.wf_train_days,
        test_days=cfg.wf_test_days,
        step_days=cfg.wf_step_days,
        embargo_days=cfg.wf_embargo_days,
    ))
    res = evaluate_stage_b(
        _one_clause_genome("g_b_per_fold_skipped_fold_key"), bars, usd_jpy_meta(),
        _backtest_config(), ev, cfg,
    )
    assert res.stage == "B"
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # disabled mode でも B_fold 行は出る (canonical_skipped=True path)
    b_fold_lines = [
        line for line in combined.splitlines()
        if "stage_gate.canonical_five.dual_path" in line and "stage=B_fold" in line
    ]
    assert len(b_fold_lines) == n_fold_expected
    # 全行に fold kwarg が含まれる
    import re
    for line in b_fold_lines:
        assert re.search(r"fold=\d+", line) is not None, (
            f"B_fold canonical_skipped line must include fold=: {line}"
        )


# ============================================================================
# B Phase 2 切替コミット step 1.7: Stage C stress dual-path
# (= 詳細設計 § 6、 8 ケース追加。 設計参照:
#  devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/detailed-design.md)
# ============================================================================


# --- 8 ケース ---


def test_stage_c_stress_canonical_dual_path_log_only_preserves_legacy_payload() -> None:
    """LOG_ONLY mode と disabled mode で Stage C の StageResult 全体が完全一致
    (= regression 0、 acceptance A1。 stress dual-path 配線追加で
    stress_payload / reasons / cross_pair / live_criteria_pass 全件不変)."""
    from src.alpha_factory.stage_gate import evaluate_stage_c
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
    log_only_cfg = StageGateConfig(phase2_canonical_metrics_mode="log_only")
    disabled_cfg = StageGateConfig(phase2_canonical_metrics_mode="disabled")
    res_log = evaluate_stage_c(
        _one_clause_genome("g_c_stress_legacy_unchanged"), bars, usd_jpy_meta(),
        cfg, ev, log_only_cfg,
    )
    res_dis = evaluate_stage_c(
        _one_clause_genome("g_c_stress_legacy_unchanged"), bars, usd_jpy_meta(),
        cfg, ev, disabled_cfg,
    )
    assert res_log.passed == res_dis.passed
    assert res_log.reason_codes == res_dis.reason_codes
    assert res_log.stage == res_dis.stage
    payload_log = dict(res_log.metrics["payload"])  # type: ignore[arg-type]
    payload_dis = dict(res_dis.metrics["payload"])  # type: ignore[arg-type]
    assert set(payload_log.keys()) == set(payload_dis.keys())
    for key in payload_log:
        assert payload_log[key] == payload_dis[key], (
            f"Stage C stress payload[{key}] differs"
        )


def test_stage_c_stress_canonical_log_isolation_when_canonical_raises(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`_try_evaluate_canonical_five_safe` が `stage_label='C_stress'` のときだけ
    raise しても stress_payload / reasons は完全不変、 かつ `stage_c.stress_failure`
    が **非出力** (= D2 反証、 Codex impl-review Round 1 [Critical] 反映)。
    """
    from src.alpha_factory import stage_gate as sg
    from src.alpha_factory.stage_gate import evaluate_stage_c
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    original_helper = sg._try_evaluate_canonical_five_safe

    def _conditional_raise(**kwargs):  # type: ignore[no-untyped-def]
        if kwargs.get("stage_label") == "C_stress":
            raise RuntimeError("simulated C_stress canonical failure")
        return original_helper(**kwargs)

    monkeypatch.setattr(sg, "_try_evaluate_canonical_five_safe", _conditional_raise)
    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res_with_raise = evaluate_stage_c(
        _one_clause_genome("g_c_stress_canonical_fail"), bars, usd_jpy_meta(),
        _backtest_config(), ev, StageGateConfig(),
    )
    captured_with_raise = capsys.readouterr()
    monkeypatch.setattr(sg, "_try_evaluate_canonical_five_safe", original_helper)
    res_disabled = evaluate_stage_c(
        _one_clause_genome("g_c_stress_canonical_fail"), bars, usd_jpy_meta(),
        _backtest_config(), ev,
        StageGateConfig(phase2_canonical_metrics_mode="disabled"),
    )
    # passed / reason_codes / payload / n_bars 完全一致 (= wall_time_seconds 除外、 D1/D3)
    assert res_with_raise.passed == res_disabled.passed
    assert res_with_raise.reason_codes == res_disabled.reason_codes
    assert res_with_raise.metrics["n_bars"] == res_disabled.metrics["n_bars"]
    payload_raise = dict(res_with_raise.metrics["payload"])  # type: ignore[arg-type]
    payload_dis = dict(res_disabled.metrics["payload"])  # type: ignore[arg-type]
    assert set(payload_raise.keys()) == set(payload_dis.keys())
    for key in payload_raise:
        assert payload_raise[key] == payload_dis[key], (
            f"C_stress canonical raise: payload[{key}] differs"
        )
    # D2 反証: dual-path 例外で stage_c.stress_failure が誤って emit されないこと
    combined = captured_with_raise.out + captured_with_raise.err
    assert "stage_c.stress_failure" not in combined, (
        "D2 violation: dual-path canonical raise must not trigger stage_c.stress_failure"
    )
    # canonical 経路は unexpected_failure or log_failed の WARN のみ
    assert (
        "stage_gate.canonical_five.unexpected_failure" in combined
        or "stage_gate.canonical_five.log_failed" in combined
    )


def test_stage_c_stress_canonical_log_helper_isolation_when_log_raises(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`_log_canonical_dual_path` が `stage_label='C_stress'` のときだけ raise しても
    stress_payload / reasons は完全不変、 かつ `stage_c.stress_failure` が
    **非出力** (= D2 反証、 Codex impl-review Round 1 [Critical] 反映)。
    """
    from src.alpha_factory import stage_gate as sg
    from src.alpha_factory.stage_gate import evaluate_stage_c
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    original_log = sg._log_canonical_dual_path

    def _conditional_log_raise(**kwargs):  # type: ignore[no-untyped-def]
        if kwargs.get("stage_label") == "C_stress":
            raise RuntimeError("simulated C_stress logger failure")
        return original_log(**kwargs)

    monkeypatch.setattr(sg, "_log_canonical_dual_path", _conditional_log_raise)
    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res_with_raise = evaluate_stage_c(
        _one_clause_genome("g_c_stress_log_fail"), bars, usd_jpy_meta(),
        _backtest_config(), ev, StageGateConfig(),
    )
    captured_with_raise = capsys.readouterr()
    monkeypatch.setattr(sg, "_log_canonical_dual_path", original_log)
    res_disabled = evaluate_stage_c(
        _one_clause_genome("g_c_stress_log_fail"), bars, usd_jpy_meta(),
        _backtest_config(), ev,
        StageGateConfig(phase2_canonical_metrics_mode="disabled"),
    )
    # legacy 不変 (= D1)
    assert res_with_raise.passed == res_disabled.passed
    assert res_with_raise.reason_codes == res_disabled.reason_codes
    assert res_with_raise.metrics["n_bars"] == res_disabled.metrics["n_bars"]
    payload_raise = dict(res_with_raise.metrics["payload"])  # type: ignore[arg-type]
    payload_dis = dict(res_disabled.metrics["payload"])  # type: ignore[arg-type]
    assert set(payload_raise.keys()) == set(payload_dis.keys())
    for key in payload_raise:
        assert payload_raise[key] == payload_dis[key], (
            f"C_stress log helper raise: payload[{key}] differs"
        )
    # D2 反証
    combined = captured_with_raise.out + captured_with_raise.err
    assert "stage_c.stress_failure" not in combined, (
        "D2 violation: log helper raise must not trigger stage_c.stress_failure"
    )
    assert "stage_gate.canonical_five.log_failed" in combined


def test_stage_c_stress_canonical_disabled_mode_emits_skipped_log(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """phase2_canonical_metrics_mode='disabled' で stress 成功時に
    `stage='C_stress'` + `canonical_skipped=True` の dual_path log entry が
    1 entry / genome emit され、 `fold=` kwarg は含まれない
    (= C5 disabled path、 step 1.6 B_fold と同型)."""
    from src.alpha_factory.stage_gate import evaluate_stage_c
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res = evaluate_stage_c(
        _one_clause_genome("g_c_stress_disabled"), bars, usd_jpy_meta(),
        _backtest_config(), ev,
        StageGateConfig(phase2_canonical_metrics_mode="disabled"),
    )
    assert res.stage == "C"
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    c_stress_lines = [
        line for line in combined.splitlines()
        if "stage_gate.canonical_five.dual_path" in line and "stage=C_stress" in line
    ]
    # disabled mode でも stress 成功なら 1 entry / genome
    assert len(c_stress_lines) == 1
    # canonical_skipped=True を含む
    assert "canonical_skipped=True" in c_stress_lines[0]
    # fold= kwarg は含まれない (= 識別子契約 C4)
    assert "fold=" not in c_stress_lines[0]


def test_stage_c_stress_canonical_succeeds_for_60d_holdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Stage C stress dual-path log entry が `stage='C_stress'` で 1 entry / genome 出力、
    必須 kwargs (= genome / interpretation_note / canonical_* / legacy_*、 fold 不在)
    含有 (= acceptance B1, C1-C4)."""
    from src.alpha_factory.stage_gate import evaluate_stage_c
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res = evaluate_stage_c(
        _one_clause_genome("g_c_stress_log_check"), bars, usd_jpy_meta(),
        _backtest_config(), ev, StageGateConfig(),
    )
    assert res.stage == "C"
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    c_stress_lines = [
        line for line in combined.splitlines()
        if "stage_gate.canonical_five.dual_path" in line and "stage=C_stress" in line
    ]
    assert len(c_stress_lines) == 1
    line = c_stress_lines[0]
    assert "genome=g_c_stress_log_check" in line
    assert "interpretation_note=direction_monitoring_only" in line
    assert "canonical_trade_count=" in line
    assert "legacy_trade_count=" in line
    # C4: C_stress 識別子契約 (= fold key 不在)
    assert "fold=" not in line


def test_stage_c_stress_canonical_skipped_when_max_spread_bps_is_none(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """backtest_config.max_spread_bps is None のとき、
    `stage='C_stress'` の dual_path event と canonical_five.skipped event が
    両者 0 件 (= acceptance C5)."""
    from dataclasses import replace as dc_replace

    from src.alpha_factory.stage_gate import evaluate_stage_c
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    cfg = dc_replace(_backtest_config(), max_spread_bps=None)
    res = evaluate_stage_c(
        _one_clause_genome("g_c_stress_no_spread"), bars, usd_jpy_meta(),
        cfg, ev, StageGateConfig(),
    )
    assert res.stage == "C"
    # spread_stress_skipped reason は legacy 経路で出る
    assert "spread_stress_skipped" in res.reason_codes
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    c_stress_lines = [
        line for line in combined.splitlines()
        if "stage=C_stress" in line
    ]
    # dual_path / canonical_five.skipped event 両者 0 件
    assert len(c_stress_lines) == 0


def test_stage_c_stress_canonical_skipped_when_stress_backtest_raises(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """stress backtest が例外発生 → `stage_c.stress_failure` WARN 後、
    `stage='C_stress'` の event は 0 件 (= acceptance C5)。

    Codex Round 1 [Warning] 反映: call count 依存を廃止し、
    `max_spread_bps` 値で stress 経路を同定 (= 将来の呼出追加に対する堅牢性)。"""
    from decimal import Decimal as _Decimal

    from src.alpha_factory import stage_gate as sg
    from src.alpha_factory.stage_gate import evaluate_stage_c
    from tests._helpers import usd_jpy_meta
    from tests.alpha_factory.test_stage_gate import (
        _backtest_config,
        _make_continuous_bars,
        _one_clause_genome,
    )
    from tests.dsl.conftest import ConstantPrimitiveEvaluator

    original_run = sg.run_backtest
    base_max_spread = _backtest_config().max_spread_bps
    assert base_max_spread is not None, "fixture must have max_spread_bps set"
    base_max_dec = _Decimal(str(base_max_spread))
    multiplier = _Decimal(str(StageGateConfig().spread_stress_multiplier))
    stress_max_dec = base_max_dec * multiplier  # stress 経路のみ一致する値

    def _conditional_run(bars_in, strategy, broker, config):  # type: ignore[no-untyped-def]
        # max_spread_bps が stress 値と一致するときだけ raise (= stress 経路同定)
        if config.max_spread_bps is not None:
            cur_dec = _Decimal(str(config.max_spread_bps))
            if cur_dec == stress_max_dec:
                raise RuntimeError("simulated stress backtest failure")
        return original_run(bars_in, strategy, broker, config)

    monkeypatch.setattr(sg, "run_backtest", _conditional_run)
    bars = _make_continuous_bars(2, bars_per_day=4)
    ev = ConstantPrimitiveEvaluator(value=0.0)
    res = evaluate_stage_c(
        _one_clause_genome("g_c_stress_raise"), bars, usd_jpy_meta(),
        _backtest_config(), ev, StageGateConfig(),
    )
    assert res.stage == "C"
    assert "spread_stress_skipped" in res.reason_codes
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # stage_c.stress_failure WARN は出る (legacy)
    assert "stage_c.stress_failure" in combined
    # ただし C_stress dual-path event は 0 件
    c_stress_lines = [
        line for line in combined.splitlines()
        if "stage=C_stress" in line and "stage_gate.canonical_five" in line
    ]
    assert len(c_stress_lines) == 0


def test_stage_c_stress_canonical_golden_first_evaluation_succeeds() -> None:
    """fixed seed × fixed fixture で C_stress canonical sidecar の主要 field が
    deterministic な期待値と一致 (= acceptance A5、 Codex Round 1 [Suggestion] 反映)。

    現 fixture (= 50 trades + bars_60d + flat equity = 1M JPY) で C_stress label
    で base 同等 fixture を渡して deterministic 性のみ確認。
    """
    base = datetime(2026, 1, 1, tzinfo=UTC)
    trades = []
    for i in range(50):
        entry = base + timedelta(days=i // 10, hours=11, minutes=30)
        exit = base + timedelta(days=i // 10, hours=12, minutes=i % 10)
        trades.append(_bt(pid=i, entry_time=entry, exit_time=exit))
    bars = _make_bars_60d()
    equity_curve = [(b.bar_time, Decimal("1000000")) for b in bars]
    result = _try_evaluate_canonical_five_safe(
        trades=trades, equity_curve=equity_curve, bars=bars,
        live_criteria=_make_default_live_criteria(),
        window_days=60,  # stage_c_holdout_days
        stage_label="C_stress", genome_name="g_c_stress_golden",
        enabled=True,
    )
    assert result is not None
    assert result.trade_count == 50
    assert result.net_pnl_after_cost == pytest.approx(5000.0, abs=1e-9)
    assert result.max_dd == pytest.approx(0.0, abs=1e-9)
    assert result.session_block_win_rate_worst == pytest.approx(0.5, abs=1e-9)
    assert result.gate_pass is False  # sharpe_min=1.0 を満たさない
    assert result.invariants.is_feasible is True
