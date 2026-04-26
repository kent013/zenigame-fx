"""``src/alpha_factory/stage_gate.py`` のテスト (T014).

設計根拠:
- devnotes/20260423-1540-stage-gate-implementation/detailed-design.md §5
- conceptual-design.md §5

テスト戦略:
- 実 backtest engine を使用（fake で run_backtest を mock しない）。
  Stage 関数は run_backtest の結果に依存するため、engine を含めて契約を担保。
- PrimitiveEvaluator は ``tests/dsl/conftest.py`` の Scripted/Constant 系を使用。
- bars は複数日跨ぎで生成（intraday absolute constraint を満たすため）。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, ClassVar, cast

import pytest

from src.alpha_factory.stage_gate import (
    TRADING_DAYS_PER_YEAR,
    CrossPairResult,
    StageGateConfig,
    StageResult,
    _annualize_trade_sharpe,
    _compute_mission_score,
    evaluate_stage_a,
    evaluate_stage_b,
    evaluate_stage_c,
)
from src.backtest.engine import BacktestConfig
from src.domain.price import Ohlc, PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.strategy import PrimitiveEvaluator
from tests._helpers import usd_jpy_meta
from tests.dsl.conftest import ConstantPrimitiveEvaluator

# ---------------------------------------------------------------------------
# 共通 fixture / helper
# ---------------------------------------------------------------------------


def _bar(
    *,
    day: int = 1,
    hour: int = 0,
    minute: int = 0,
    bid_close: str = "154.00",
    ask_close: str = "154.01",
    bid_open: str | None = None,
    ask_open: str | None = None,
    pair_name: str = "USD_JPY",
    base_year: int = 2026,
    base_month: int = 1,
) -> PriceBar:
    bt = datetime(base_year, base_month, day, hour, 0, 0, tzinfo=UTC) + timedelta(
        minutes=minute
    )
    bid_o = Decimal(bid_open or bid_close)
    ask_o = Decimal(ask_open or ask_close)
    bid_c = Decimal(bid_close)
    ask_c = Decimal(ask_close)
    return PriceBar(
        pair_name=pair_name,
        bar_time=bt,
        bid=Ohlc(bid_o, max(bid_o, bid_c), min(bid_o, bid_c), bid_c),
        ask=Ohlc(ask_o, max(ask_o, ask_c), min(ask_o, ask_c), ask_c),
        volume=10,
        complete=True,
    )


def _make_continuous_bars(
    n_days: int,
    bars_per_day: int = 4,
    *,
    base_year: int = 2026,
    base_month: int = 1,
    base_day: int = 1,
) -> list[PriceBar]:
    """連続 n_days 日 × bars_per_day bar の bars."""
    bars: list[PriceBar] = []
    base = datetime(base_year, base_month, base_day, 0, 0, 0, tzinfo=UTC)
    for d in range(n_days):
        for h in range(bars_per_day):
            t = base + timedelta(days=d, hours=h * (24 // max(bars_per_day, 1)))
            bid_o = Decimal("154.00")
            ask_o = Decimal("154.01")
            bars.append(
                PriceBar(
                    pair_name="USD_JPY",
                    bar_time=t,
                    bid=Ohlc(bid_o, bid_o, bid_o, bid_o),
                    ask=Ohlc(ask_o, ask_o, ask_o, ask_o),
                    volume=10,
                    complete=True,
                )
            )
    return bars


def _make_oscillating_bars(n_days: int, bars_per_day: int = 4) -> list[PriceBar]:
    """value が 1 bar ごとに up/down する bars（取引によって PnL が出やすい）."""
    bars: list[PriceBar] = []
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    n = 0
    for d in range(n_days):
        for h in range(bars_per_day):
            t = base + timedelta(days=d, hours=h * (24 // max(bars_per_day, 1)))
            # 上下する価格パターン
            offset = (n % 4) - 2  # -2, -1, 0, 1, -2, ...
            base_price = Decimal("154.00") + Decimal(offset) * Decimal("0.05")
            bid_close = base_price
            ask_close = base_price + Decimal("0.01")
            bars.append(
                PriceBar(
                    pair_name="USD_JPY",
                    bar_time=t,
                    bid=Ohlc(bid_close, bid_close, bid_close, bid_close),
                    ask=Ohlc(ask_close, ask_close, ask_close, ask_close),
                    volume=10,
                    complete=True,
                )
            )
            n += 1
    return bars


def _one_clause_genome(name: str = "g") -> Genome:
    return Genome(
        name=name,
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="D1", weight=1.0),),
                local_gate=(),
                weight=1.0,
            ),
        ),
        position=PositionConfig(
            entry_threshold=0.5, exit_threshold=0.2, max_pos=1, time_stop_min=0
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def _multi_clause_genome(name: str = "g_complex") -> Genome:
    """サイズが大きい Genome (size_norm が大きくなる)."""
    return Genome(
        name=name,
        units=10000,
        clauses=(
            ClauseConfig(
                directional=(
                    SignalConfig(name="D1", weight=1.0),
                    SignalConfig(name="D2", weight=0.8),
                    SignalConfig(name="D3", weight=0.5),
                ),
                local_gate=(
                    SignalConfig(name="G1", weight=1.0),
                    SignalConfig(name="G2", weight=0.5),
                ),
                weight=1.0,
            ),
            ClauseConfig(
                directional=(
                    SignalConfig(name="D4", weight=0.7),
                    SignalConfig(name="D5", weight=0.6),
                ),
                local_gate=(SignalConfig(name="G3", weight=0.8),),
                weight=0.5,
            ),
        ),
        position=PositionConfig(
            entry_threshold=0.5, exit_threshold=0.2, max_pos=1, time_stop_min=0
        ),
        risk=RiskConfig(stop_atr=2.0, take_atr=3.0),
    )


def _backtest_config(
    *,
    max_spread_bps: Decimal | None = Decimal("100"),
    session_close_utc_hours: frozenset[int] = frozenset({23}),
    holding_cost_per_day_bps: Decimal = Decimal("0"),
) -> BacktestConfig:
    return BacktestConfig(
        instrument="USD_JPY",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2027, 1, 1, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        max_spread_bps=max_spread_bps,
        holding_cost_per_day_bps=holding_cost_per_day_bps,
        session_close_utc_hours=session_close_utc_hours,
    )


def _payload(result: StageResult) -> dict[str, Any]:
    """metrics envelope から payload dict を `Any` で取り出す（mypy 用ヘルパ）."""
    env = cast(dict[str, Any], dict(result.metrics))
    return cast(dict[str, Any], env["payload"])


def _envelope(result: StageResult) -> dict[str, Any]:
    """metrics envelope を `Any` で取り出す（mypy 用ヘルパ）."""
    return cast(dict[str, Any], dict(result.metrics))


class _AlternatingEvaluator:
    """bar idx ごとに 1.0 / 0.0 を交互に返す evaluator (entry → exit パターン)."""

    def evaluate(
        self, bars: list[PriceBar], idx: int, signal: SignalConfig
    ) -> float:
        # 4 bar 周期: 1.0 (entry), 0.1 (hold), 0.0 (exit), 0.0 → 周期で再 entry
        cycle = idx % 4
        if cycle == 0:
            return 1.0
        if cycle == 1:
            return 0.1  # below exit threshold (0.2) なので exit
        return 0.0


class _RaisingEvaluator:
    """評価のたびに raise する evaluator (system_failure テスト用)."""

    def evaluate(
        self, bars: list[PriceBar], idx: int, signal: SignalConfig
    ) -> float:
        raise RuntimeError("forced failure for test")


# ===========================================================================
# StageGateConfig
# ===========================================================================


class TestStageGateConfig:
    def test_default_construction(self) -> None:
        cfg = StageGateConfig()
        assert cfg.stage_a_window_days == 60
        assert cfg.stage_a_alpha == 0.03
        assert cfg.wf_train_days == 120
        assert cfg.wf_test_days == 20
        assert cfg.wf_step_days == 20
        assert cfg.wf_embargo_days == 1
        assert cfg.spread_stress_multiplier == 1.5
        assert cfg.live_criteria["sharpe_min"] == 1.0
        assert cfg.live_criteria["trade_count_min"] == 50

    def test_alpha_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="stage_a_alpha"):
            StageGateConfig(stage_a_alpha=-0.1)
        with pytest.raises(ValueError, match="stage_a_alpha"):
            StageGateConfig(stage_a_alpha=1.5)

    def test_invalid_wf_train_days(self) -> None:
        with pytest.raises(ValueError, match="wf_train_days"):
            StageGateConfig(wf_train_days=0)

    def test_invalid_wf_embargo_days(self) -> None:
        with pytest.raises(ValueError, match="wf_embargo_days"):
            StageGateConfig(wf_embargo_days=-1)

    def test_invalid_spread_stress_multiplier(self) -> None:
        with pytest.raises(ValueError, match="spread_stress_multiplier"):
            StageGateConfig(spread_stress_multiplier=1.0)

    def test_live_criteria_missing_keys_raises(self) -> None:
        with pytest.raises(ValueError, match="live_criteria"):
            StageGateConfig(
                live_criteria={"sharpe_min": 1.0}  # 他の必須キーが欠ける
            )

    def test_live_criteria_is_frozen(self) -> None:
        """live_criteria は MappingProxyType で外部書き換え不能."""
        cfg = StageGateConfig()
        with pytest.raises(TypeError):
            cfg.live_criteria["sharpe_min"] = 999  # type: ignore[index]


# ===========================================================================
# StageResult
# ===========================================================================


class TestStageResult:
    def test_passed_no_reason(self) -> None:
        r = StageResult(stage="A", passed=True, metrics={"k": 1})
        assert r.passed
        assert r.reason_codes == ()
        assert r.reason_if_failed == ""

    def test_reason_if_failed_joins_with_semicolon(self) -> None:
        r = StageResult(
            stage="C",
            passed=False,
            metrics={},
            reason_codes=("a", "b", "c"),
        )
        assert r.reason_if_failed == "a;b;c"


# ===========================================================================
# Stage A — Fast Screen
# ===========================================================================


class TestStageA:
    def test_metrics_envelope_keys_present(self) -> None:
        bars = _make_continuous_bars(2, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        cfg = _backtest_config()
        res = evaluate_stage_a(
            _one_clause_genome("g_envelope"),
            bars,
            usd_jpy_meta(),
            cfg,
            ev,
            StageGateConfig(),
        )
        assert isinstance(res, StageResult)
        assert res.stage == "A"
        env = _envelope(res)
        assert env["stage"] == "A"
        assert env["genome_name"] == "g_envelope"
        assert env["n_bars"] == len(bars)
        assert isinstance(env["wall_time_seconds"], float)
        assert "payload" in env
        payload = cast(dict[str, Any], env["payload"])
        assert isinstance(payload, dict)
        for key in (
            "fitness_raw",
            "size_norm",
            "fitness_pen",
            "alpha_a",
            "threshold",
            "trade_count",
            # T-sharpe Phase 1A: payload key を sharpe_raw → trade_sharpe_raw に
            "trade_sharpe_raw",
            # T037: runtime fired clause 数 (active_clause)
            "active_clause",
        ):
            assert key in payload
        # T037: active_clause は int (>=0)
        ac = payload["active_clause"]
        assert isinstance(ac, int)
        assert ac >= 0

    def test_no_trades_reason(self) -> None:
        """Constant 0.0 では entry シグナルが発生しない → trade_count == 0."""
        bars = _make_continuous_bars(2, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        res = evaluate_stage_a(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            StageGateConfig(),
        )
        assert not res.passed
        assert res.reason_codes == ("no_trades",)

    def test_system_failure_reason(self) -> None:
        bars = _make_continuous_bars(2, bars_per_day=4)
        ev = _RaisingEvaluator()
        res = evaluate_stage_a(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            StageGateConfig(),
        )
        assert not res.passed
        assert "system_failure" in res.reason_codes

    def test_below_threshold_reason(self) -> None:
        """trade はあるが sharpe_raw が低く fitness_pen <= threshold."""
        # Alternating で trade を発生させるが、bars は flat → sharpe ~ 0 周辺
        bars = _make_continuous_bars(3, bars_per_day=4)
        ev = _AlternatingEvaluator()
        # threshold を高く設定して必ず below_threshold にする
        stage_cfg = StageGateConfig(stage_a_threshold=999.0)
        res = evaluate_stage_a(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        # trade があれば below_threshold、なければ no_trades のいずれか
        assert not res.passed
        assert res.reason_codes[0] in {"below_threshold", "no_trades", "metric_unavailable"}

    def test_fitness_pen_includes_complexity_penalty(self) -> None:
        """size_norm が大きい genome は fitness_pen が必ず低い (penalty 反映).

        `_AlternatingEvaluator` は signal.name に依存しない決定論的な値を返す。
        従って simple / complex Genome は同じ composite signal を出し、
        同じ bars で同じ trade を発生させ、結果として fitness_raw (sharpe) は
        一致する。size_norm のみ差があるため fitness_pen は必ず complex < simple。
        この前提を test 冒頭で hard assert し、条件分岐なしで大小比較する。
        """
        # 価格を変動させて sharpe を有限値にする
        bars = _make_oscillating_bars(5, bars_per_day=4)
        ev = _AlternatingEvaluator()
        cfg = _backtest_config()
        # T-sharpe Phase 1A: 短期 backtest で trade_sharpe_raw を有限値にするため
        # sample-size guard を緩める (production default=30)
        stage_cfg = StageGateConfig(stage_a_alpha=0.5, trade_count_min_for_sharpe=2)

        res_simple = evaluate_stage_a(
            _one_clause_genome("simple"),
            bars,
            usd_jpy_meta(),
            cfg,
            ev,
            stage_cfg,
        )
        res_complex = evaluate_stage_a(
            _multi_clause_genome("complex"),
            bars,
            usd_jpy_meta(),
            cfg,
            ev,
            stage_cfg,
        )

        ps = _payload(res_simple)
        pc = _payload(res_complex)

        # 前提: 両方とも fitness が計算できている (None でない)
        assert ps["fitness_raw"] is not None, (
            f"simple Genome の fitness_raw が None: payload={ps}"
        )
        assert pc["fitness_raw"] is not None, (
            f"complex Genome の fitness_raw が None: payload={pc}"
        )
        assert ps["size_norm"] is not None
        assert pc["size_norm"] is not None
        assert ps["fitness_pen"] is not None
        assert pc["fitness_pen"] is not None

        # 前提: size_norm は complex > simple
        assert pc["size_norm"] > ps["size_norm"]

        # 前提: 同 bars / 同 evaluator のため fitness_raw は一致 (sharpe 同値)
        assert ps["fitness_raw"] == pc["fitness_raw"], (
            "前提崩れ: fitness_raw が異なる "
            f"(simple={ps['fitness_raw']}, complex={pc['fitness_raw']})"
        )

        # CORE: fitness_pen は complex < simple (penalty 反映)
        assert pc["fitness_pen"] < ps["fitness_pen"]

        # 数値整合: fitness_pen = fitness_raw - alpha * size_norm
        alpha = stage_cfg.stage_a_alpha
        expected_s = ps["fitness_raw"] - alpha * ps["size_norm"]
        expected_c = pc["fitness_raw"] - alpha * pc["size_norm"]
        assert abs(ps["fitness_pen"] - expected_s) < 1e-9
        assert abs(pc["fitness_pen"] - expected_c) < 1e-9


# ===========================================================================
# Stage B — WF-OOS Gate
# ===========================================================================


class TestStageB:
    def test_no_folds_reason(self) -> None:
        """bars が WF fold_len 未満 → no_folds."""
        bars = _make_continuous_bars(5, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        # train=120 + embargo=1 + test=20 = 141 観測日必要、5 日では fold が出ない
        stage_cfg = StageGateConfig()
        res = evaluate_stage_b(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        assert not res.passed
        assert "no_folds" in res.reason_codes

    def test_insufficient_folds_reason(self) -> None:
        """fold が 1 だけ生成 → insufficient_folds."""
        # train=3, test=2, step=10, embargo=0 → fold_len=5、6日 bars で 1 fold
        bars = _make_continuous_bars(6, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        stage_cfg = StageGateConfig(
            wf_train_days=3,
            wf_test_days=2,
            wf_step_days=10,
            wf_embargo_days=0,
        )
        res = evaluate_stage_b(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        assert not res.passed
        assert "insufficient_folds" in res.reason_codes

    def test_metrics_envelope_keys_present(self) -> None:
        """共通 envelope と payload のキーが揃う."""
        bars = _make_continuous_bars(20, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        # 小さめ WF パラメータで複数 fold を作る
        stage_cfg = StageGateConfig(
            wf_train_days=3,
            wf_test_days=2,
            wf_step_days=2,
            wf_embargo_days=0,
        )
        res = evaluate_stage_b(
            _one_clause_genome("g_b_envelope"),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        env = _envelope(res)
        assert env["stage"] == "B"
        assert env["genome_name"] == "g_b_envelope"
        assert env["n_bars"] == len(bars)
        assert isinstance(env["wall_time_seconds"], float)
        payload = cast(dict[str, Any], env["payload"])
        assert isinstance(payload, dict)
        for key in (
            "n_fold",
            "n_fold_unavailable",
            "n_fold_effective",
            "oos_sharpes",
            "median_oos_sharpe",
            "positive_fold_ratio",
            "positive_fold_ratio_effective",
            "dsr",
            "is_full_sharpe",
            "is_full_total_pnl",
            "is_full_trade_count",
        ):
            assert key in payload

    def test_below_median_threshold(self) -> None:
        """全 fold が unavailable (no trade) → median=0.0 で min(0.20) 未満."""
        bars = _make_continuous_bars(20, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        stage_cfg = StageGateConfig(
            wf_train_days=3,
            wf_test_days=2,
            wf_step_days=2,
            wf_embargo_days=0,
            stage_b_median_oos_sharpe_min=0.20,
        )
        res = evaluate_stage_b(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        assert not res.passed
        # 全 fold で trade=0 → sharpe は None → 0 で imputed → median=0 < 0.20
        assert "median_oos_sharpe<min" in res.reason_codes
        # 全 fold metric_unavailable
        assert "all_folds_unavailable" in res.reason_codes
        env = _envelope(res)
        payload = cast(dict[str, Any], env["payload"])
        assert payload["n_fold"] >= 2
        assert payload["n_fold"] == payload["n_fold_unavailable"]

    def test_unavailable_fold_in_denominator(self) -> None:
        """unavailable fold (no-trade) が positive_ratio の分母に含まれる."""
        bars = _make_continuous_bars(20, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        stage_cfg = StageGateConfig(
            wf_train_days=3,
            wf_test_days=2,
            wf_step_days=2,
            wf_embargo_days=0,
            stage_b_positive_fold_min=0.60,
        )
        res = evaluate_stage_b(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        env = _envelope(res)
        payload = cast(dict[str, Any], env["payload"])
        # positive_fold_ratio = 0 / n_fold = 0
        assert payload["positive_fold_ratio"] == 0.0
        assert "positive_fold_ratio<min" in res.reason_codes


# ===========================================================================
# Stage C — Live Criteria + Stress
# ===========================================================================


class TestStageC:
    def test_metrics_envelope_keys_present(self) -> None:
        bars = _make_continuous_bars(2, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        res = evaluate_stage_c(
            _one_clause_genome("g_c_envelope"),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            StageGateConfig(),
        )
        env = _envelope(res)
        assert env["stage"] == "C"
        assert env["genome_name"] == "g_c_envelope"
        assert env["n_bars"] == len(bars)
        assert isinstance(env["wall_time_seconds"], float)
        payload = cast(dict[str, Any], env["payload"])
        for key in (
            # T-sharpe Phase 1A: Stage C payload key も "sharpe" → "trade_sharpe_raw"
            "trade_sharpe_raw",
            "total_pnl",
            "max_drawdown_frac",
            "trade_count",
            "live_criteria_pass",
            "intraday_compliant",
            "overnight_violations",
            "stress",
            "cross_pair",
        ):
            assert key in payload

    def test_no_trades_fails_live_criteria(self) -> None:
        """trade=0 では trade_count_min 違反 + sharpe 不足等で複数 reason."""
        bars = _make_continuous_bars(3, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        res = evaluate_stage_c(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            StageGateConfig(),
        )
        assert not res.passed
        # 少なくとも trade_count<min は出る
        assert "live_criteria.trade_count<min" in res.reason_codes
        # sharpe (None) も live_criteria.sharpe<min
        assert "live_criteria.sharpe<min" in res.reason_codes

    def test_max_spread_bps_none_fails_closed(self) -> None:
        """max_spread_bps=None → spread_stress_skipped で fail-closed."""
        bars = _make_continuous_bars(3, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        cfg = _backtest_config(max_spread_bps=None)
        res = evaluate_stage_c(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            cfg,
            ev,
            StageGateConfig(),
        )
        assert not res.passed
        assert "spread_stress_skipped" in res.reason_codes
        payload = _payload(res)
        assert payload["stress"]["skipped"] is True

    def test_max_spread_bps_set_does_not_skip_stress(self) -> None:
        """max_spread_bps を明示設定すると spread_stress_skipped は出ず stress を実評価する.

        T041: Stage C を spread_stress_skipped 常時 fail 状態から開放する規約の
        retest。base が trade を出さなくても stress の skip フラグは立たないこと
        を unit test で固定。
        """
        bars = _make_continuous_bars(3, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        cfg = _backtest_config(max_spread_bps=Decimal("10"))
        res = evaluate_stage_c(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            cfg,
            ev,
            StageGateConfig(),
        )
        assert "spread_stress_skipped" not in res.reason_codes
        payload = _payload(res)
        assert payload["stress"]["skipped"] is False

    def test_drawdown_unit_is_fraction(self) -> None:
        """payload.max_drawdown_frac は fraction (0-1) スケール."""
        bars = _make_continuous_bars(3, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        res = evaluate_stage_c(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            StageGateConfig(),
        )
        payload = _payload(res)
        dd = payload["max_drawdown_frac"]
        assert isinstance(dd, float)
        assert 0.0 <= dd <= 1.0

    def test_live_criteria_relaxed_can_pass(self) -> None:
        """live_criteria を緩めて oscillating 価格で trade を発生させ通過させる.

        sharpe_min は base_sharpe が None でないことを要求するため、価格を変動
        させる必要がある (flat bars だと returns 全部 0 → sharpe=None で必ず違反)。
        """
        bars = _make_oscillating_bars(5, bars_per_day=4)
        ev = _AlternatingEvaluator()
        relaxed_lc = {
            "sharpe_min": -1e9,
            "total_pnl_min": -1e9,
            "max_drawdown_max": 1.0,
            "trade_count_min": 0,
            "trade_count_max": 1_000_000,
        }
        stage_cfg = StageGateConfig(
            live_criteria=relaxed_lc,
            spread_stress_min_total_pnl=-1e9,
            spread_stress_min_sharpe=-1e9,
            # T-sharpe Phase 1A: 短期 backtest で trade_sharpe_raw を計算可能にする
            trade_count_min_for_sharpe=2,
        )
        res = evaluate_stage_c(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        # 通過条件が全部緩いので passed=True
        assert res.passed, f"expected pass, got reasons: {res.reason_codes}"
        payload = _payload(res)
        assert payload["intraday_compliant"] is True
        # trade が発生していることを念押し
        assert payload["trade_count"] > 0

    def test_max_drawdown_threshold_violation(self) -> None:
        """max_drawdown_max を厳しくして必ず違反させる."""
        bars = _make_continuous_bars(3, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        relaxed_but_dd = {
            "sharpe_min": -1e9,
            "total_pnl_min": -1e9,
            "max_drawdown_max": -0.1,  # 必ず違反 (dd >= 0)
            "trade_count_min": 0,
            "trade_count_max": 1_000_000,
        }
        stage_cfg = StageGateConfig(live_criteria=relaxed_but_dd)
        res = evaluate_stage_c(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        assert not res.passed
        assert "live_criteria.max_drawdown>max" in res.reason_codes

    def test_trade_count_max_violation(self) -> None:
        """trade_count_max を 0 にして必ず上限違反させる（trade=0 でも 0<=max なので
        AlternatingEvaluator + max=-1 を使う代替戦略）."""
        bars = _make_continuous_bars(3, bars_per_day=4)
        ev = _AlternatingEvaluator()
        # trade_count_max=-1 で必ず violation。trade_count_min も 0 で OK
        bad_lc = {
            "sharpe_min": -1e9,
            "total_pnl_min": -1e9,
            "max_drawdown_max": 1.0,
            "trade_count_min": 0,
            "trade_count_max": -1,
        }
        stage_cfg = StageGateConfig(live_criteria=bad_lc)
        res = evaluate_stage_c(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        assert not res.passed
        assert "live_criteria.trade_count>max" in res.reason_codes

    def test_system_failure_reason(self) -> None:
        bars = _make_continuous_bars(3, bars_per_day=4)
        ev = _RaisingEvaluator()
        res = evaluate_stage_c(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            StageGateConfig(),
        )
        assert not res.passed
        assert "system_failure" in res.reason_codes

    def test_intraday_constraint_violation_reason(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """日跨ぎ Trade を含む synthetic 結果で intraday_constraint_violation を検出.

        engine は normally EOD で強制クローズするため日跨ぎ Trade は発生しない。
        本テストでは run_backtest を monkeypatch し、entry_time.date() !=
        exit_time.date() の Trade を含む BacktestResult を返させる。
        """
        from src.broker.orders import Trade

        bars = _make_oscillating_bars(5, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)

        # 日跨ぎ Trade を 2 本含む synthetic result
        # T-sharpe Phase 1A: equity_at_entry を明示し、複数 trade で trade_sharpe_raw が
        # 計算されるようにする
        overnight_trade = Trade(
            position_id=1,
            instrument="USD_JPY",
            side="long",
            units=10000,
            entry_price=Decimal("154.00"),
            entry_time=datetime(2026, 1, 1, 22, 0, tzinfo=UTC),
            exit_price=Decimal("154.10"),
            exit_time=datetime(2026, 1, 2, 1, 0, tzinfo=UTC),  # 翌日
            pnl=Decimal("1000"),
            exit_reason="signal",
            equity_at_entry=Decimal("1000000"),
        )
        overnight_trade2 = Trade(
            position_id=2,
            instrument="USD_JPY",
            side="long",
            units=10000,
            entry_price=Decimal("154.10"),
            entry_time=datetime(2026, 1, 2, 22, 0, tzinfo=UTC),
            exit_price=Decimal("154.20"),
            exit_time=datetime(2026, 1, 3, 1, 0, tzinfo=UTC),  # 翌日
            pnl=Decimal("500"),
            exit_reason="signal",
            equity_at_entry=Decimal("1001000"),
        )

        from src.alpha_factory import stage_gate as sg_module
        from src.backtest.engine import BacktestResult

        # base evaluation 用 result（日跨ぎ trade を含む）
        # stress evaluation も同じ patch を共有するため、stress 側も同じ result を返す。
        # sharpe を None にしないため、equity curve は returns に variability を持たせる。
        equity = [
            (datetime(2026, 1, 1, 22, 0, tzinfo=UTC), Decimal("1000000")),
            (datetime(2026, 1, 1, 22, 30, tzinfo=UTC), Decimal("1000100")),
            (datetime(2026, 1, 1, 23, 0, tzinfo=UTC), Decimal("1000050")),
            (datetime(2026, 1, 1, 23, 30, tzinfo=UTC), Decimal("1000200")),
            (datetime(2026, 1, 2, 0, 30, tzinfo=UTC), Decimal("1000300")),
            (datetime(2026, 1, 2, 1, 0, tzinfo=UTC), Decimal("1001000")),
        ]
        result = BacktestResult(
            config=_backtest_config(),
            trades=[overnight_trade, overnight_trade2],
            equity_curve=equity,
        )

        def _fake_run_backtest(*args: Any, **kwargs: Any) -> BacktestResult:
            return result

        monkeypatch.setattr(sg_module, "run_backtest", _fake_run_backtest)

        # live_criteria を緩めて intraday violation のみを検出させる
        relaxed_lc = {
            "sharpe_min": -1e9,
            "total_pnl_min": -1e9,
            "max_drawdown_max": 1.0,
            "trade_count_min": 0,
            "trade_count_max": 1_000_000,
        }
        stage_cfg = StageGateConfig(
            live_criteria=relaxed_lc,
            spread_stress_min_total_pnl=-1e9,
            spread_stress_min_sharpe=-1e9,
            # T-sharpe Phase 1A: 2 trade のみで sharpe を計算できるようにする
            trade_count_min_for_sharpe=2,
        )
        res = evaluate_stage_c(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        assert not res.passed
        assert "intraday_constraint_violation" in res.reason_codes
        # 他の reason が混入していないこと（live_criteria を全て緩めているため
        # intraday_constraint_violation のみが原因であるはず）
        assert set(res.reason_codes) == {"intraday_constraint_violation"}
        payload = _payload(res)
        assert payload["intraday_compliant"] is False
        # T-sharpe Phase 1A: trade_sharpe_raw 計算のため 2 trade に増やしたので 2
        assert payload["overnight_violations"] == 2

    def test_cross_pair_none_skipped(self) -> None:
        """cross_pair_evaluator=None で cross_pair.skipped=True、passed には影響しない."""
        bars = _make_continuous_bars(3, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        relaxed_lc = {
            "sharpe_min": -1e9,
            "total_pnl_min": -1e9,
            "max_drawdown_max": 1.0,
            "trade_count_min": 0,
            "trade_count_max": 1_000_000,
        }
        stage_cfg = StageGateConfig(
            live_criteria=relaxed_lc,
            spread_stress_min_total_pnl=-1e9,
            spread_stress_min_sharpe=-1e9,
            # T-sharpe Phase 1A: 短期 backtest で trade_sharpe_raw を計算可能にする
            trade_count_min_for_sharpe=2,
        )
        res = evaluate_stage_c(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
            cross_pair_evaluator=None,
        )
        payload = _payload(res)
        assert payload["cross_pair"]["skipped"] is True
        assert payload["cross_pair"]["result"] is None

    def test_cross_pair_called_and_recorded_shadow_only(self) -> None:
        """fake CrossPairEvaluator を渡すと CrossPairResult が payload に格納される.

        Phase 2 では shadow only（passed には影響しない）。
        sharpe を成立させるため oscillating bars + AlternatingEvaluator を使う。
        """
        bars = _make_oscillating_bars(5, bars_per_day=4)
        ev = _AlternatingEvaluator()

        class _FakeCrossPair:
            def evaluate(
                self,
                genome: Genome,
                target_pair: str,
                pair_bars_map: Mapping[str, list[PriceBar]],
                meta_map: Mapping[str, object],
                backtest_config: BacktestConfig,
            ) -> CrossPairResult:
                return CrossPairResult(
                    target_pair=target_pair,
                    anchor_pairs=("EUR_USD",),
                    aggregator_name="mean",
                    window=(
                        datetime(2026, 1, 1, tzinfo=UTC),
                        datetime(2026, 1, 2, tzinfo=UTC),
                    ),
                    passed=False,  # shadow なので Stage C.passed には影響しない
                    metrics={"foo": 1},
                )

        relaxed_lc = {
            "sharpe_min": -1e9,
            "total_pnl_min": -1e9,
            "max_drawdown_max": 1.0,
            "trade_count_min": 0,
            "trade_count_max": 1_000_000,
        }
        stage_cfg = StageGateConfig(
            live_criteria=relaxed_lc,
            spread_stress_min_total_pnl=-1e9,
            spread_stress_min_sharpe=-1e9,
            # T-sharpe Phase 1A: 短期 backtest で trade_sharpe_raw を計算可能にする
            trade_count_min_for_sharpe=2,
        )
        res = evaluate_stage_c(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
            cross_pair_evaluator=_FakeCrossPair(),
            cross_pair_inputs={
                "target_pair": "USD_JPY",
                "pair_bars_map": {"USD_JPY": bars, "EUR_USD": bars},
                "meta_map": {"USD_JPY": usd_jpy_meta(), "EUR_USD": usd_jpy_meta()},
            },
        )
        # shadow なので CrossPairResult.passed=False でも Stage C は通過 (live_criteria が緩い)
        assert res.passed, f"shadow only のはず: reasons={res.reason_codes}"
        payload = _payload(res)
        assert payload["cross_pair"]["skipped"] is False
        cp_result = payload["cross_pair"]["result"]
        assert isinstance(cp_result, CrossPairResult)
        assert cp_result.target_pair == "USD_JPY"

    def test_cross_pair_inputs_required_when_evaluator_given(self) -> None:
        bars = _make_continuous_bars(3, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)

        class _FakeCrossPair:
            def evaluate(
                self,
                genome: Genome,
                target_pair: str,
                pair_bars_map: Mapping[str, list[PriceBar]],
                meta_map: Mapping[str, object],
                backtest_config: BacktestConfig,
            ) -> CrossPairResult:
                raise AssertionError("不要に呼ばれた")

        with pytest.raises(ValueError, match="cross_pair_inputs"):
            evaluate_stage_c(
                _one_clause_genome(),
                bars,
                usd_jpy_meta(),
                _backtest_config(),
                ev,
                StageGateConfig(),
                cross_pair_evaluator=_FakeCrossPair(),
                cross_pair_inputs=None,
            )

    def test_cross_pair_inputs_validation_missing_key(self) -> None:
        bars = _make_continuous_bars(3, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)

        class _FakeCrossPair:
            def evaluate(
                self,
                genome: Genome,
                target_pair: str,
                pair_bars_map: Mapping[str, list[PriceBar]],
                meta_map: Mapping[str, object],
                backtest_config: BacktestConfig,
            ) -> CrossPairResult:
                raise AssertionError("不要に呼ばれた")

        with pytest.raises(ValueError, match="cross_pair_inputs missing keys"):
            evaluate_stage_c(
                _one_clause_genome(),
                bars,
                usd_jpy_meta(),
                _backtest_config(),
                ev,
                StageGateConfig(),
                cross_pair_evaluator=_FakeCrossPair(),
                cross_pair_inputs={"target_pair": "USD_JPY"},
            )


# ===========================================================================
# Smoke: Stage A/B/C を共通の evaluator/bars で順に実行できる
# ===========================================================================


class TestStageGateSmoke:
    def test_stage_a_b_c_sequence_runs(self) -> None:
        """3 Stage を順に呼んで例外なく StageResult が返ることを確認."""
        bars = _make_continuous_bars(20, bars_per_day=4)
        ev: PrimitiveEvaluator = ConstantPrimitiveEvaluator(value=0.0)
        cfg = _backtest_config()
        # WF を小さくして fold が複数生成されるように
        stage_cfg = StageGateConfig(
            wf_train_days=3,
            wf_test_days=2,
            wf_step_days=2,
            wf_embargo_days=0,
        )
        ra = evaluate_stage_a(
            _one_clause_genome("g_smoke"), bars, usd_jpy_meta(), cfg, ev, stage_cfg
        )
        rb = evaluate_stage_b(
            _one_clause_genome("g_smoke"), bars, usd_jpy_meta(), cfg, ev, stage_cfg
        )
        rc = evaluate_stage_c(
            _one_clause_genome("g_smoke"), bars, usd_jpy_meta(), cfg, ev, stage_cfg
        )
        assert ra.stage == "A"
        assert rb.stage == "B"
        assert rc.stage == "C"


# T035: Stage B 観察可能性 ====================================================


class TestT035StageBObservability:
    """n_fold_effective / positive_fold_ratio_effective メトリクス追加."""

    def test_stage_b_metrics_payload_contains_n_fold_effective(self) -> None:
        bars = _make_continuous_bars(20, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        stage_cfg = StageGateConfig(
            wf_train_days=3,
            wf_test_days=2,
            wf_step_days=2,
            wf_embargo_days=0,
        )
        res = evaluate_stage_b(
            _one_clause_genome("g_t035"),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        env = _envelope(res)
        payload = cast(dict[str, Any], env["payload"])
        assert "n_fold_effective" in payload
        assert isinstance(payload["n_fold_effective"], int)

    def test_stage_b_n_fold_effective_equals_total_minus_unavailable(
        self,
    ) -> None:
        bars = _make_continuous_bars(20, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        stage_cfg = StageGateConfig(
            wf_train_days=3,
            wf_test_days=2,
            wf_step_days=2,
            wf_embargo_days=0,
        )
        res = evaluate_stage_b(
            _one_clause_genome("g_t035"),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        payload = cast(dict[str, Any], _envelope(res)["payload"])
        assert (
            payload["n_fold_effective"]
            == payload["n_fold"] - payload["n_fold_unavailable"]
        )

    def test_stage_b_positive_fold_ratio_effective_uses_only_available_folds(
        self,
    ) -> None:
        """全 fold unavailable のとき positive_fold_ratio_effective=None。

        ConstantPrimitiveEvaluator(0.0) は全 fold で no-trade → unavailable。
        effective サンプル 0 → positive_fold_ratio_effective が None になる。
        """
        bars = _make_continuous_bars(20, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        stage_cfg = StageGateConfig(
            wf_train_days=3,
            wf_test_days=2,
            wf_step_days=2,
            wf_embargo_days=0,
        )
        res = evaluate_stage_b(
            _one_clause_genome("g_t035"),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        payload = cast(dict[str, Any], _envelope(res)["payload"])
        # 全 fold unavailable → effective sample 0 → None
        if payload["n_fold_effective"] == 0:
            assert payload["positive_fold_ratio_effective"] is None
        else:
            assert isinstance(payload["positive_fold_ratio_effective"], float)


# T043: mission_score 4 軸 soft 合算 ===========================================


class TestT043MissionScore:
    """live_criteria 4 軸の soft 合算スコア (observation only)。"""

    LC_DEFAULT: ClassVar[dict[str, float]] = {
        "sharpe_min": 1.0,
        "total_pnl_min": 50000.0,
        "max_drawdown_max": 0.2,
        "trade_count_min": 50.0,
        "trade_count_max": 5000.0,
    }

    def test_returns_none_when_sharpe_is_none(self) -> None:
        """base 評価が trade を出せず Sharpe=None なら mission_score=None."""
        score = _compute_mission_score(
            sharpe=None,
            total_pnl=10000.0,
            max_drawdown_frac=0.05,
            trade_count=30,
            live_criteria=self.LC_DEFAULT,
        )
        assert score is None

    def test_all_axes_at_target_returns_one(self) -> None:
        """全軸 target 達成で mission_score = 1.0 (幾何平均上限)."""
        score = _compute_mission_score(
            sharpe=1.0,
            total_pnl=50000.0,
            max_drawdown_frac=0.0,
            trade_count=50,
            live_criteria=self.LC_DEFAULT,
        )
        assert score is not None
        assert score == pytest.approx(1.0, abs=1e-9)

    def test_all_axes_at_lower_returns_floor(self) -> None:
        """全軸 lower 以下で mission_score = floor (=0.1) ^ 1 = 0.1."""
        score = _compute_mission_score(
            sharpe=0.0,
            total_pnl=0.0,
            max_drawdown_frac=0.2,  # = max_drawdown_max (lower)
            trade_count=0,
            live_criteria=self.LC_DEFAULT,
        )
        assert score is not None
        assert score == pytest.approx(0.1, abs=1e-9)

    def test_score_above_target_clipped_to_one(self) -> None:
        """target 超過は 1.0 にクリップされ、scaled 0.1〜1.0 の幾何平均。"""
        score = _compute_mission_score(
            sharpe=2.0,  # > target=1.0
            total_pnl=100000.0,  # > target=50000
            max_drawdown_frac=0.0,
            trade_count=100,  # > target=50, < max=5000
            live_criteria=self.LC_DEFAULT,
        )
        assert score is not None
        assert score == pytest.approx(1.0, abs=1e-9)

    def test_trade_count_above_max_yields_zero_axis(self) -> None:
        """trade_count > max は 0 score → 幾何平均が大幅減 (1 軸 floor で全体下落)."""
        score = _compute_mission_score(
            sharpe=1.0,
            total_pnl=50000.0,
            max_drawdown_frac=0.0,
            trade_count=10000,  # > trade_count_max=5000
            live_criteria=self.LC_DEFAULT,
        )
        assert score is not None
        # 1 軸 0 (= scaled 0.1)、他 3 軸 1 (= scaled 1.0) → (0.1*1*1*1)^(1/4)
        expected = (0.1 * 1.0 * 1.0 * 1.0) ** (1.0 / 4.0)
        assert score == pytest.approx(expected, abs=1e-9)

    def test_partial_progress_returns_intermediate_value(self) -> None:
        """部分達成: sharpe=0.5 (半分), pnl=25000 (半分), dd=0.1 (半分), tc=25 (半分)
        → 各軸 score=0.5, scaled=0.55, geomean ≈ 0.55."""
        score = _compute_mission_score(
            sharpe=0.5,
            total_pnl=25000.0,
            max_drawdown_frac=0.1,
            trade_count=25,
            live_criteria=self.LC_DEFAULT,
        )
        assert score is not None
        assert score == pytest.approx(0.55, abs=1e-9)

    def test_drawdown_above_lower_yields_zero_axis(self) -> None:
        """max_drawdown_frac > max_drawdown_max は dd 軸 0 score (clip)."""
        score = _compute_mission_score(
            sharpe=1.0,
            total_pnl=50000.0,
            max_drawdown_frac=0.5,  # >> max=0.2
            trade_count=50,
            live_criteria=self.LC_DEFAULT,
        )
        assert score is not None
        # dd 軸 = 0 (scaled 0.1)、他 3 軸 = 1 (scaled 1.0)
        expected = (0.1 * 1.0 * 1.0 * 1.0) ** (1.0 / 4.0)
        assert score == pytest.approx(expected, abs=1e-9)

    def test_evaluate_stage_c_payload_includes_mission_score(self) -> None:
        """evaluate_stage_c の payload に mission_score キーが含まれること。"""
        bars = _make_continuous_bars(3, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        cfg = _backtest_config(max_spread_bps=Decimal("10"))
        res = evaluate_stage_c(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            cfg,
            ev,
            StageGateConfig(),
        )
        payload = cast(dict[str, Any], _envelope(res)["payload"])
        assert "mission_score" in payload
        # base が trade を出さない場合は None になる (defensive)
        ms = payload["mission_score"]
        assert ms is None or (isinstance(ms, float) and 0.1 <= ms <= 1.0)


# T042: trade-level → annualized Sharpe 換算 ===================================


class TestT042AnnualizeTradeSharpe:
    """live_criteria.sharpe_min (annualized) と GA fitness (trade-level) の
    スケール乖離を解消する換算ヘルパ。"""

    def test_basic_formula(self) -> None:
        """S_annual = S_trade × sqrt(λ_day × 252)、λ_day = trade_count / window."""
        s = _annualize_trade_sharpe(0.2, trade_count=60, window_days=60)
        assert s is not None
        assert s == pytest.approx(0.2 * (TRADING_DAYS_PER_YEAR ** 0.5), abs=1e-9)

    def test_returns_none_when_sharpe_is_none(self) -> None:
        assert _annualize_trade_sharpe(None, 60, 60) is None

    def test_returns_none_when_trade_count_zero(self) -> None:
        assert _annualize_trade_sharpe(0.5, 0, 60) is None

    def test_returns_none_when_window_zero(self) -> None:
        assert _annualize_trade_sharpe(0.5, 60, 0) is None

    def test_returns_none_when_sharpe_nan(self) -> None:
        assert _annualize_trade_sharpe(float("nan"), 60, 60) is None

    def test_returns_none_when_sharpe_inf(self) -> None:
        assert _annualize_trade_sharpe(float("inf"), 60, 60) is None


class TestT042StageGateConfigDefaults:
    """StageGateConfig() のデフォルト値が T042 後の trade-level スケールに揃っていること。

    Codex Round-1 [Critical] への対応: yaml ローダ非経由で StageGateConfig() を
    直接生成するパス (テスト・手動実行) でも新スケールが適用されるように、
    dataclass デフォルトと yaml の両方を 0.05 に揃える。
    """

    def test_default_stage_b_median_oos_sharpe_min_is_trade_level_005(self) -> None:
        cfg = StageGateConfig()
        assert cfg.stage_b_median_oos_sharpe_min == pytest.approx(0.05, abs=1e-9)


class TestT042StageCLiveCriteriaAnnualized:
    """Stage C の live_criteria.sharpe 判定が annualized で行われること。"""

    def test_payload_exposes_trade_sharpe_annualized(self) -> None:
        bars = _make_continuous_bars(3, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        cfg = _backtest_config(max_spread_bps=Decimal("10"))
        res = evaluate_stage_c(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            cfg,
            ev,
            StageGateConfig(),
        )
        payload = cast(dict[str, Any], _envelope(res)["payload"])
        # base が trade を出さない場合 None、出した場合 float
        assert "trade_sharpe_annualized" in payload
        a = payload["trade_sharpe_annualized"]
        assert a is None or isinstance(a, float)

    def test_lc_sharpe_passes_when_annualized_above_threshold(self) -> None:
        """trade-level Sharpe を annualized 換算した値で sharpe_min と比較する。

        相応に高い oscillating 価格 + alternating evaluator で trade を出させ、
        annualized Sharpe が sharpe_min を超える設定で lc_pass['sharpe']=True
        になることを確認する。

        live_criteria を緩めて sharpe_min=0.5 (annualized) にし、他軸も緩める。
        """
        bars = _make_oscillating_bars(5, bars_per_day=4)
        ev = _AlternatingEvaluator()
        relaxed_lc = {
            "sharpe_min": 0.5,  # annualized 0.5 (緩い)
            "total_pnl_min": -1e9,
            "max_drawdown_max": 1.0,
            "trade_count_min": 0,
            "trade_count_max": 1_000_000,
        }
        stage_cfg = StageGateConfig(
            live_criteria=relaxed_lc,
            spread_stress_min_total_pnl=-1e9,
            spread_stress_min_sharpe=-1e9,
            trade_count_min_for_sharpe=2,
        )
        res = evaluate_stage_c(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        payload = cast(dict[str, Any], _envelope(res)["payload"])
        # trade を出していれば annualized が計算され lc.sharpe_pass が True か False か明確
        if payload["trade_sharpe_annualized"] is not None:
            ann = float(payload["trade_sharpe_annualized"])
            expected = ann >= 0.5
            assert payload["live_criteria_pass"]["sharpe"] is expected
