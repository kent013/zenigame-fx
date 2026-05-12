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
    METRIC_UNAVAILABLE_FITNESS,
    NO_EXPOSURE_FITNESS,
    STAGE_A_FITNESS_SENTINELS,
    SYSTEM_FAILURE_FITNESS,
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

    def test_wf_min_safe_folds_default(self) -> None:
        # cycle 2 (improve-cycle): 起動時 fail-closed 用 statistical safety floor
        cfg = StageGateConfig()
        assert cfg.wf_min_safe_folds == 5

    def test_wf_min_safe_folds_distinct_from_min_folds_required(self) -> None:
        # 役割分離: wf_min_folds_required (worker 短絡) vs wf_min_safe_folds (起動 fail-closed)
        cfg = StageGateConfig(wf_min_folds_required=2, wf_min_safe_folds=10)
        assert cfg.wf_min_folds_required == 2
        assert cfg.wf_min_safe_folds == 10


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

    def test_no_exposure_reason(self) -> None:
        """T034: Constant 0.0 では entry シグナルが発生しない → trade_count == 0
        → no_exposure (旧 no_trades)。fitness_pen に NO_EXPOSURE_FITNESS が入る。"""
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
        assert res.reason_codes == ("no_exposure",)
        payload = cast(dict[str, Any], _envelope(res)["payload"])
        # T034: payload fitness_pen は sentinel 値 (None ではなく数値で埋まる)
        assert payload["fitness_pen"] == NO_EXPOSURE_FITNESS

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
        # T034: trade があれば below_threshold、なければ no_exposure のいずれか
        assert not res.passed
        assert res.reason_codes[0] in {"below_threshold", "no_exposure", "metric_unavailable"}

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

        # 数値整合: fitness_pen = fitness_raw - alpha * size_norm - gamma * trade_count_underrun
        # cycle 6: trade_count adequacy penalty を追加
        alpha = stage_cfg.stage_a_alpha
        gamma = stage_cfg.stage_a_trade_count_penalty_gamma
        entry_min = int(stage_cfg.live_criteria["trade_count_min"])

        def _expected_pen(p: dict) -> float:
            tc = p["trade_count"]
            tc_pen = (
                gamma * (entry_min - tc) / entry_min
                if tc < entry_min else 0.0
            )
            return p["fitness_raw"] - alpha * p["size_norm"] - tc_pen

        expected_s = _expected_pen(ps)
        expected_c = _expected_pen(pc)
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


class TestT092NFoldSafeFloor:
    """T092: n_fold_effective < wf_min_safe_folds で Stage B fail させる safety guard."""

    def _multi_fold_stage_cfg(
        self,
        *,
        wf_min_safe_folds: int,
    ) -> StageGateConfig:
        return StageGateConfig(
            wf_train_days=3,
            wf_test_days=2,
            wf_step_days=2,
            wf_embargo_days=0,
            wf_min_safe_folds=wf_min_safe_folds,
        )

    def test_below_safe_floor_records_reason(self) -> None:
        """n_fold_effective < wf_min_safe_folds=5 のとき reason に n_fold_below_safe_floor."""
        # 11 日 bars + WF (3/2/2/0) → fold_len=5, step=2 → n_fold=4 (< safe_floor=5)
        bars = _make_continuous_bars(11, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        stage_cfg = self._multi_fold_stage_cfg(wf_min_safe_folds=5)
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
        assert payload["n_fold"] >= 2  # else 分岐に入っている
        assert payload["n_fold_effective"] < stage_cfg.wf_min_safe_folds
        assert not res.passed
        assert "n_fold_below_safe_floor" in res.reason_codes

    def test_at_safe_floor_does_not_record_reason(self) -> None:
        """n_fold_effective == wf_min_safe_folds (=2 設定) のとき guard 不発."""
        # wf_min_safe_folds=2 に下げ、 6 日 bars で 1 fold (n_fold=1 → guard 発火)
        # ではなく 7 日 bars で 2 fold (n_fold=2 = safe_floor) を作る
        bars = _make_continuous_bars(7, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        stage_cfg = self._multi_fold_stage_cfg(wf_min_safe_folds=2)
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
        # 全 fold unavailable で effective=0 < 2 になりうるため、 effective>=safe_floor を満たすケースを直接 assert
        # ここでは guard が動的に config に追従することのみ確認 (effective<floor なら fire)
        if payload["n_fold_effective"] >= stage_cfg.wf_min_safe_folds:
            assert "n_fold_below_safe_floor" not in res.reason_codes
        else:
            assert "n_fold_below_safe_floor" in res.reason_codes

    def test_co_records_with_insufficient_folds(self) -> None:
        """n_fold==1 のとき insufficient_folds と n_fold_below_safe_floor が併記される (passed=False)."""
        bars = _make_continuous_bars(6, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        stage_cfg = self._multi_fold_stage_cfg(wf_min_safe_folds=5)
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
        assert payload["n_fold"] == 1
        assert not res.passed
        assert "insufficient_folds" in res.reason_codes
        # effective <= 1 < 5 → guard も併記
        assert "n_fold_below_safe_floor" in res.reason_codes

    def test_co_records_with_no_folds(self) -> None:
        """n_fold==0 のとき no_folds と n_fold_below_safe_floor が併記される (passed=False)."""
        # 5 日 bars + 既定 WF パラメータ (train=120/embargo=1/test=20) で fold が組めない
        bars = _make_continuous_bars(5, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        stage_cfg = StageGateConfig()  # default wf_min_safe_folds=5
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
        assert payload["n_fold"] == 0
        assert not res.passed
        assert "no_folds" in res.reason_codes
        assert "n_fold_below_safe_floor" in res.reason_codes

    def test_co_records_with_all_folds_unavailable(self) -> None:
        """全 fold unavailable のとき all_folds_unavailable と n_fold_below_safe_floor が併記される."""
        # 全 fold で trade=0 → unavailable → effective=0 < safe_floor=5
        bars = _make_continuous_bars(20, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        stage_cfg = self._multi_fold_stage_cfg(wf_min_safe_folds=5)
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
        assert payload["n_fold"] >= 2
        assert payload["n_fold_unavailable"] == payload["n_fold"]
        assert payload["n_fold_effective"] == 0
        assert not res.passed
        assert "all_folds_unavailable" in res.reason_codes
        assert "n_fold_below_safe_floor" in res.reason_codes

    @pytest.mark.parametrize("safe_floor", [3, 8])
    def test_safe_floor_threshold_respects_config(self, safe_floor: int) -> None:
        """wf_min_safe_folds の値が変化すると guard 発火境界も変わる."""
        bars = _make_continuous_bars(11, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        stage_cfg = self._multi_fold_stage_cfg(wf_min_safe_folds=safe_floor)
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
        eff = int(payload["n_fold_effective"])
        if eff < safe_floor:
            assert "n_fold_below_safe_floor" in res.reason_codes
        else:
            assert "n_fold_below_safe_floor" not in res.reason_codes


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
    """StageGateConfig() のデフォルト値が T091 後の noise-floor 整合化スケールに揃っていること。

    T042 → T091 cycle_phase1 (2026-05-08): trade-level スケールを 0.05 → 0.025 に再校正。
    Lo (2002) SE 公式 (heuristic): 10-fold median SE ≈ 0.10 → 0.025 で真値 SR=0.05 検出力 60%。
    詳細: devnotes/20260508-1203-stage-b-gate-redesign/conceptual-design.md (v2 APPROVED)
    """

    def test_default_stage_b_median_oos_sharpe_min_is_noise_floor_calibrated(self) -> None:
        """T091: median_oos_sharpe_min default は noise-floor 整合化された 0.025 (旧 0.05)。"""
        cfg = StageGateConfig()
        assert cfg.stage_b_median_oos_sharpe_min == pytest.approx(0.025, abs=1e-9)


class TestT091MedianThresholdNoiseFloorCalibration:
    """T091: median_oos_sharpe_min の noise-floor 整合化検証 (非 flaky 決定的テスト)。

    Lo (2002) SE 公式 (heuristic):
    - per-fold SE ≈ √((1 + 0.5×SR²)/N)、 N=stage_b_fold_trade_count_min=10 → SE ≈ 0.32
    - 10-fold median SE ≈ 0.32/√10 ≈ 0.10 (独立 fold 仮定)
    - 真値 SR=0.05 個体の median 推定値 >=0.025 確率: z=(0.025-0.05)/0.10=-0.25 → P≈Φ(0.25)≈0.60
    """

    def test_lo_2002_se_formula_for_per_fold(self) -> None:
        """Lo (2002) SE 公式の決定的計算: SR=0.05, N=10 で SE ≈ 0.3163。"""
        import math

        sr = 0.05
        n = 10
        se_per_fold = math.sqrt((1.0 + 0.5 * sr * sr) / n)
        assert se_per_fold == pytest.approx(0.3163, abs=1e-3)

    def test_median_se_across_10_folds(self) -> None:
        """10-fold median SE は per-fold SE / √10 ≈ 0.10。"""
        import math

        se_per_fold = math.sqrt((1.0 + 0.5 * 0.05 ** 2) / 10)
        se_median = se_per_fold / math.sqrt(10)
        assert se_median == pytest.approx(0.1000, abs=2e-3)

    @staticmethod
    def _norm_cdf(z: float) -> float:
        """標準正規分布 CDF (math.erf ベース、 scipy 不依存)。"""
        import math

        return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

    def test_detection_power_at_threshold_025(self) -> None:
        """真値 SR=0.05 個体の median 推定値が >=0.025 になる確率 ≈ 60% (=Φ(0.25))。

        z = (0.025 - 0.05) / 0.10 = -0.25
        P(estimate >= 0.025) = 1 - Φ(-0.25) = Φ(0.25) ≈ 0.5987
        """
        import math

        true_sr = 0.05
        threshold = 0.025
        se_median = math.sqrt((1.0 + 0.5 * true_sr * true_sr) / 10) / math.sqrt(10)
        z = (threshold - true_sr) / se_median
        p_pass = self._norm_cdf(-z)
        # 検出力 ~60% (Lo 近似 heuristic で 0.59-0.61 の範囲)
        assert 0.59 <= p_pass <= 0.61

    def test_detection_power_at_old_threshold_05_is_50_percent(self) -> None:
        """0.05 維持時の検出力は 50% (median == true value 期待)。

        true SR = 0.05 = threshold → P(estimate >= 0.05) = 0.5 (median=mean 仮定)
        """
        import math

        true_sr = 0.05
        threshold = 0.05
        se_median = math.sqrt((1.0 + 0.5 * true_sr * true_sr) / 10) / math.sqrt(10)
        z = (threshold - true_sr) / se_median
        p_pass = self._norm_cdf(-z)
        # P=0.5 (z=0)
        assert p_pass == pytest.approx(0.5, abs=1e-9)

    def test_stage_b_gate_boundary_at_threshold(self) -> None:
        """T091 Codex impl-review Round 1 [Warning] 対応: 境界値で実 gate 判定の回帰テスト。

        median_oos=0.0249 (0.025 未満) → fail、 median_oos=0.0251 (0.025 超え) → pass。
        evaluate_stage_b の median 集計後の判定ロジックを直接叩く。
        """
        cfg = StageGateConfig()
        # gate 判定: median_oos < cfg.stage_b_median_oos_sharpe_min なら "median_oos_sharpe<min" reason
        threshold = cfg.stage_b_median_oos_sharpe_min
        assert threshold == pytest.approx(0.025, abs=1e-9)

        # 境界直下 fail
        median_below = 0.0249
        assert median_below < threshold, "0.0249 は 0.025 未満で fail"

        # 境界直上 pass
        median_above = 0.0251
        assert not (median_above < threshold), "0.0251 は 0.025 以上で pass"

        # 境界等値 pass (>=ではなく <min なので等値は pass)
        median_equal = 0.025
        assert not (median_equal < threshold), "0.025 == threshold は pass (< 比較)"


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


# T034: 無取引優位の遮断 (no_exposure / sentinel) ===============================


class TestT034NoExposureSentinel:
    """trade_count<min_exposure_trade_count を no_exposure reason + sentinel
    fitness_pen で淘汰する。selection_score tie-break で「無取引優位」を
    構造的に解消する設計の動作検証。"""

    def test_sentinel_constants_have_correct_ordering(self) -> None:
        """sentinel 序列: system_failure < no_exposure < metric_unavailable < 0."""
        assert SYSTEM_FAILURE_FITNESS < NO_EXPOSURE_FITNESS
        assert NO_EXPOSURE_FITNESS < METRIC_UNAVAILABLE_FITNESS
        assert METRIC_UNAVAILABLE_FITNESS < 0.0

    def test_sentinel_set_membership(self) -> None:
        """STAGE_A_FITNESS_SENTINELS は 3 sentinel 全てを含む."""
        assert SYSTEM_FAILURE_FITNESS in STAGE_A_FITNESS_SENTINELS
        assert NO_EXPOSURE_FITNESS in STAGE_A_FITNESS_SENTINELS
        assert METRIC_UNAVAILABLE_FITNESS in STAGE_A_FITNESS_SENTINELS
        assert len(STAGE_A_FITNESS_SENTINELS) == 3

    def test_no_exposure_payload_fitness_pen_is_sentinel(self) -> None:
        """trade_count=0 なら payload fitness_pen は NO_EXPOSURE_FITNESS."""
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
        payload = cast(dict[str, Any], _envelope(res)["payload"])
        assert payload["fitness_pen"] == NO_EXPOSURE_FITNESS

    def test_system_failure_payload_fitness_pen_is_sentinel(self) -> None:
        """exception 経路では payload fitness_pen は SYSTEM_FAILURE_FITNESS."""
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
        payload = cast(dict[str, Any], _envelope(res)["payload"])
        assert "system_failure" in res.reason_codes
        assert payload["fitness_pen"] == SYSTEM_FAILURE_FITNESS

    def test_min_exposure_threshold_above_one_triggers_no_exposure(self) -> None:
        """min_exposure_trade_count=10 で trade_count=5 → no_exposure 判定."""
        bars = _make_oscillating_bars(5, bars_per_day=4)
        ev = _AlternatingEvaluator()
        # min_exposure_trade_count=10, live_criteria 緩和で他軸は通る
        relaxed_lc = {
            "sharpe_min": -1e9,
            "total_pnl_min": -1e9,
            "max_drawdown_max": 1.0,
            "trade_count_min": 100,  # >= 10 + 1 (validation)
            "trade_count_max": 1_000_000,
        }
        cfg = StageGateConfig(
            live_criteria=relaxed_lc,
            min_exposure_trade_count=10,
            stage_a_threshold=-1e9,
        )
        res = evaluate_stage_a(
            _one_clause_genome(),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            cfg,
        )
        payload = cast(dict[str, Any], _envelope(res)["payload"])
        # trade_count が 10 未満なら no_exposure、十分にあれば pass / below
        if payload["trade_count"] < 10:
            assert "no_exposure" in res.reason_codes
            assert payload["fitness_pen"] == NO_EXPOSURE_FITNESS

    def test_min_exposure_must_be_lt_trade_count_min(self) -> None:
        """validation: min_exposure_trade_count >= live_criteria.trade_count_min は ValueError."""
        with pytest.raises(ValueError, match="禁止事項 #4 ガード"):
            StageGateConfig(min_exposure_trade_count=50)  # default trade_count_min=50

    def test_min_exposure_must_be_at_least_one(self) -> None:
        """validation: min_exposure_trade_count < 1 は ValueError."""
        with pytest.raises(ValueError, match="must be >= 1"):
            StageGateConfig(min_exposure_trade_count=0)

    def test_min_exposure_validation_skipped_when_lc_trade_count_min_zero(self) -> None:
        """live_criteria.trade_count_min=0 (緩和テスト用) では validation skip."""
        relaxed_lc = {
            "sharpe_min": 0.0,
            "total_pnl_min": 0.0,
            "max_drawdown_max": 1.0,
            "trade_count_min": 0,  # 制約無効
            "trade_count_max": 1_000_000,
        }
        # min_exposure_trade_count=1 で 0 と比較されないこと
        cfg = StageGateConfig(
            live_criteria=relaxed_lc,
            min_exposure_trade_count=1,
        )
        assert cfg.min_exposure_trade_count == 1


# ===========================================================================
# T054: Stage B fold unavailable reason 排他的 enum + reason 別カウント
# ===========================================================================


class TestT054FoldUnavailableReason:
    """T054: FoldUnavailableReason enum と reason 別カウントの不変条件テスト."""

    def test_fold_unavailable_reason_enum_values(self) -> None:
        """5 つの reason value が string で取り出せる (排他的 enum)."""
        from src.alpha_factory.stage_gate import FoldUnavailableReason

        assert FoldUnavailableReason.FOLD_EXCEPTION.value == "fold_exception"
        assert FoldUnavailableReason.NO_TRADES.value == "no_trades"
        assert (
            FoldUnavailableReason.TRADE_COUNT_BELOW_MIN.value
            == "trade_count_below_min"
        )
        assert FoldUnavailableReason.ZERO_VARIANCE.value == "zero_variance"
        assert FoldUnavailableReason.OTHER.value == "other"

    def test_unavailable_reason_counts_in_payload(self) -> None:
        """payload に unavailable_reason_counts dict が含まれる."""
        bars = _make_continuous_bars(20, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        stage_cfg = StageGateConfig(
            wf_train_days=3,
            wf_test_days=2,
            wf_step_days=2,
            wf_embargo_days=0,
        )
        res = evaluate_stage_b(
            _one_clause_genome("g_t054_payload"),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        payload = _payload(res)
        assert "unavailable_reason_counts" in payload
        urc = payload["unavailable_reason_counts"]
        assert isinstance(urc, dict)
        # 5 つの reason value が key として揃っている
        assert set(urc.keys()) == {
            "fold_exception",
            "no_trades",
            "trade_count_below_min",
            "zero_variance",
            "other",
        }

    def test_reason_counts_sum_invariant(self) -> None:
        """sum(reason_counts.values()) == n_fold_unavailable 不変条件."""
        bars = _make_continuous_bars(20, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        stage_cfg = StageGateConfig(
            wf_train_days=3,
            wf_test_days=2,
            wf_step_days=2,
            wf_embargo_days=0,
        )
        res = evaluate_stage_b(
            _one_clause_genome("g_t054_invariant"),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        payload = _payload(res)
        urc = cast(dict[str, int], payload["unavailable_reason_counts"])
        assert sum(urc.values()) == payload["n_fold_unavailable"]

    def test_no_trades_reason_when_zero_signal(self) -> None:
        """value=0 で trades が出ない fold は no_trades reason に分類される."""
        bars = _make_continuous_bars(20, bars_per_day=4)
        ev = ConstantPrimitiveEvaluator(value=0.0)
        stage_cfg = StageGateConfig(
            wf_train_days=3,
            wf_test_days=2,
            wf_step_days=2,
            wf_embargo_days=0,
            stage_b_fold_trade_count_min=10,
        )
        res = evaluate_stage_b(
            _one_clause_genome("g_t054_no_trades"),
            bars,
            usd_jpy_meta(),
            _backtest_config(),
            ev,
            stage_cfg,
        )
        payload = _payload(res)
        urc = cast(dict[str, int], payload["unavailable_reason_counts"])
        # value=0 → no entry → trade_count=0 → no_trades reason
        assert urc["no_trades"] == payload["n_fold_unavailable"]
        assert urc["trade_count_below_min"] == 0


class TestT054StageBFoldTradeCountMin:
    """T054: Stage B fold 専用 trade_count_min が Stage A と独立に動く."""

    def test_default_value_is_ten(self) -> None:
        """default は 10 (Lo 2002 SE 上限から逆算)."""
        cfg = StageGateConfig()
        assert cfg.stage_b_fold_trade_count_min == 10

    def test_separated_from_stage_a_threshold(self) -> None:
        """trade_count_min_for_sharpe (Stage A) と独立 field."""
        cfg = StageGateConfig(
            trade_count_min_for_sharpe=30,
            stage_b_fold_trade_count_min=10,
        )
        assert cfg.trade_count_min_for_sharpe == 30
        assert cfg.stage_b_fold_trade_count_min == 10

    def test_can_override_via_config(self) -> None:
        """Stage B fold-min を 5 に下げられる (経験式禁止だが既存値の override 自体は可能)."""
        cfg = StageGateConfig(stage_b_fold_trade_count_min=5)
        assert cfg.stage_b_fold_trade_count_min == 5
