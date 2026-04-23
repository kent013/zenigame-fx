"""``src/alpha_factory/cross_pair.py`` のテスト (T016).

設計根拠:
- devnotes/20260423-1957-cross-pair-evaluation-shadow/conceptual-design.md
- devnotes/20260423-1957-cross-pair-evaluation-shadow/detailed-design.md §4

テスト戦略:
- ``evaluate_cross_pair`` の集約・判定ロジックは pure な数値計算なので、
  ``_run_pair_sharpe`` を monkeypatch して固定 Sharpe を返す pattern を基本にする。
- 実 backtest 経由の E2E sanity test は 1 ケースのみ (JPY-quote 3 pairs)。
- Stage C 統合 test は ``StageCRunCrossPairEvaluator`` を adapter に注入し、
  ``evaluate_stage_c`` 経由で payload 形状と例外隔離を検証する。
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import pytest

from src.alpha_factory.cross_pair import (
    ANCHOR_PAIRS,
    CrossPairConfig,
    StageCRunCrossPairEvaluator,
    evaluate_cross_pair,
)
from src.alpha_factory.stage_gate import (
    CrossPairResult,
    StageGateConfig,
    evaluate_stage_c,
)
from src.backtest.engine import BacktestConfig
from src.broker.mock import InstrumentMeta
from src.domain.price import Ohlc, PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from tests.dsl.conftest import ConstantPrimitiveEvaluator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dummy_genome(name: str = "g_test") -> Genome:
    sig = SignalConfig(name="ConstSignal", weight=1.0, params={})
    clause = ClauseConfig(directional=(sig,), local_gate=(), weight=1.0)
    pos = PositionConfig(
        entry_threshold=0.5,
        exit_threshold=0.1,
        max_pos=1,
        time_stop_min=0,
    )
    risk = RiskConfig(stop_atr=2.0, take_atr=2.0)
    return Genome(
        name=name,
        units=10000,
        clauses=(clause,),
        position=pos,
        risk=risk,
    )


def _dummy_meta(pair: str) -> InstrumentMeta:
    base = pair.split("_")[0]
    return InstrumentMeta(
        oanda_name=pair,
        base_currency=base,
        quote_currency="JPY",  # MockBroker 制約のため統一
        margin_rate=Decimal("0.04"),
    )


def _dummy_bar(pair: str, *, day: int = 1, minute: int = 0) -> PriceBar:
    bid = Decimal("154.00")
    ask = Decimal("154.01")
    bt = datetime(2026, 1, day, 0, 0, 0, tzinfo=UTC) + timedelta(minutes=minute)
    return PriceBar(
        pair_name=pair,
        bar_time=bt,
        bid=Ohlc(bid, bid, bid, bid),
        ask=Ohlc(ask, ask, ask, ask),
        volume=10,
        complete=True,
    )


def _dummy_backtest_config(instrument: str = "EUR_JPY") -> BacktestConfig:
    return BacktestConfig(
        instrument=instrument,
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 5, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=25,
        session_close_utc_hours=frozenset({23}),
        bar_minutes=1,
    )


def _build_pair_inputs(pairs: list[str]) -> tuple[
    dict[str, list[PriceBar]], dict[str, InstrumentMeta]
]:
    bars = {p: [_dummy_bar(p, minute=i) for i in range(3)] for p in pairs}
    metas = {p: _dummy_meta(p) for p in pairs}
    return bars, metas


def _patch_run_pair_sharpe(
    monkeypatch: pytest.MonkeyPatch,
    sharpes: dict[str, float] | dict[str, tuple[float, str | None]],
) -> None:
    """``_run_pair_sharpe`` を固定 Sharpe で置換する."""

    def fake_run(
        *,
        genome: Genome,
        pair: str,
        bars: list[PriceBar],
        meta: InstrumentMeta,
        backtest_config: BacktestConfig,
        primitive_evaluator: Any,
    ) -> tuple[float, str | None]:
        v = sharpes[pair]
        if isinstance(v, tuple):
            return v
        return float(v), None

    monkeypatch.setattr(
        "src.alpha_factory.cross_pair._run_pair_sharpe",
        fake_run,
    )


# ---------------------------------------------------------------------------
# anchor & config 整合性 (7)
# ---------------------------------------------------------------------------


def test_anchor_pairs_has_six_targets() -> None:
    expected = {
        "EUR_JPY", "USD_JPY", "EUR_USD", "AUD_JPY", "USD_CAD", "USD_ZAR",
    }
    assert set(ANCHOR_PAIRS.keys()) == expected


def test_anchor_pairs_each_has_two() -> None:
    for target, anchors in ANCHOR_PAIRS.items():
        assert len(anchors) == 2, f"{target} should have exactly 2 anchors"
        assert isinstance(anchors, tuple)


def test_anchor_pairs_no_self_reference() -> None:
    for target, anchors in ANCHOR_PAIRS.items():
        assert target not in anchors, f"{target} should not be in its own anchors"


def test_cross_pair_config_default_values() -> None:
    c = CrossPairConfig()
    assert c.sharpe_target_cross_ratio_min == 0.8
    assert c.mean_sharpe_cross_min == 0.15
    assert c.min_sharpe_cross_min == -0.20
    assert c.aggregator_lambda == 0.5
    assert c.mode == "shadow"


def test_cross_pair_config_invalid_lambda_raises() -> None:
    with pytest.raises(ValueError, match="aggregator_lambda"):
        CrossPairConfig(aggregator_lambda=-0.1)


def test_cross_pair_config_invalid_ratio_raises() -> None:
    with pytest.raises(ValueError, match="sharpe_target_cross_ratio_min"):
        CrossPairConfig(sharpe_target_cross_ratio_min=1.5)
    with pytest.raises(ValueError, match="sharpe_target_cross_ratio_min"):
        CrossPairConfig(sharpe_target_cross_ratio_min=-0.1)


def test_cross_pair_config_invalid_mode_raises() -> None:
    with pytest.raises(ValueError, match="mode"):
        CrossPairConfig(mode=cast(Any, "monitor"))


# ---------------------------------------------------------------------------
# 集約計算 (2)
# ---------------------------------------------------------------------------


def test_aggregate_fitness_correct(monkeypatch: pytest.MonkeyPatch) -> None:
    """mean=0.6, pstdev=0.16329932..., F = 0.6 - 0.5*pstdev = 0.518..."""
    sharpes = {"EUR_JPY": 0.8, "EUR_USD": 0.6, "USD_JPY": 0.4}
    _patch_run_pair_sharpe(monkeypatch, sharpes)
    pair_bars, pair_meta = _build_pair_inputs(list(sharpes))
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    assert math.isclose(
        cast(float, result.metrics["mean_sharpe"]), 0.6, abs_tol=1e-9
    )
    assert math.isclose(
        cast(float, result.metrics["std_sharpe"]),
        0.16329931618554522,
        abs_tol=1e-6,
    )
    assert math.isclose(
        cast(float, result.metrics["aggregate_fitness"]),
        0.6 - 0.5 * 0.16329931618554522,
        abs_tol=1e-6,
    )
    assert math.isclose(
        cast(float, result.metrics["min_sharpe"]), 0.4, abs_tol=1e-9
    )


def test_pstdev_used_not_stdev(monkeypatch: pytest.MonkeyPatch) -> None:
    """ddof=0 (pstdev) 使用確認: [1, 2, 3] → pstdev = 0.8164..., stdev = 1.0"""
    sharpes = {"EUR_JPY": 1.0, "EUR_USD": 2.0, "USD_JPY": 3.0}
    _patch_run_pair_sharpe(monkeypatch, sharpes)
    pair_bars, pair_meta = _build_pair_inputs(list(sharpes))
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    # pstdev([1,2,3]) = sqrt(2/3) = 0.8164965...
    # stdev([1,2,3]) = 1.0 (NOT this)
    assert math.isclose(
        cast(float, result.metrics["std_sharpe"]),
        math.sqrt(2.0 / 3.0),
        abs_tol=1e-6,
    )


# ---------------------------------------------------------------------------
# 通過基準境界 (3)
# ---------------------------------------------------------------------------


def test_pass_criteria_mean_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """mean = 0.15 ちょうどで pass (>= 比較)."""
    # mean = 0.15 にするため (0.15, 0.15, 0.15)
    sharpes = {"EUR_JPY": 0.15, "EUR_USD": 0.15, "USD_JPY": 0.15}
    _patch_run_pair_sharpe(monkeypatch, sharpes)
    pair_bars, pair_meta = _build_pair_inputs(list(sharpes))
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    pc = cast(Mapping[str, Any], result.metrics["pass_criteria"])
    assert pc["mean"] is True
    assert pc["min"] is True

    # boundary - epsilon → fail
    sharpes2 = {p: 0.1499 for p in sharpes}
    _patch_run_pair_sharpe(monkeypatch, sharpes2)
    result2 = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    pc2 = cast(Mapping[str, Any], result2.metrics["pass_criteria"])
    assert pc2["mean"] is False


def test_pass_criteria_min_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """min = -0.20 ちょうどで pass、< -0.20 で fail."""
    sharpes = {"EUR_JPY": 0.5, "EUR_USD": 0.5, "USD_JPY": -0.20}
    _patch_run_pair_sharpe(monkeypatch, sharpes)
    pair_bars, pair_meta = _build_pair_inputs(list(sharpes))
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    pc = cast(Mapping[str, Any], result.metrics["pass_criteria"])
    assert pc["min"] is True

    sharpes2 = {"EUR_JPY": 0.5, "EUR_USD": 0.5, "USD_JPY": -0.21}
    _patch_run_pair_sharpe(monkeypatch, sharpes2)
    result2 = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    pc2 = cast(Mapping[str, Any], result2.metrics["pass_criteria"])
    assert pc2["min"] is False


def test_pass_criteria_ratio_boundary_with_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """target_cross/target_single = 0.8 ちょうどで pass、< 0.8 で fail."""
    # target_cross = 0.8 になるように設定、single = 1.0
    sharpes = {"EUR_JPY": 0.8, "EUR_USD": 0.5, "USD_JPY": 0.5}
    _patch_run_pair_sharpe(monkeypatch, sharpes)
    pair_bars, pair_meta = _build_pair_inputs(list(sharpes))
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
        sharpe_target_single=1.0,
    )
    pc = cast(Mapping[str, Any], result.metrics["pass_criteria"])
    assert pc["sharpe_ratio"] is True

    # below boundary
    result2 = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
        sharpe_target_single=1.01,  # ratio = 0.8/1.01 = 0.792 < 0.8
    )
    pc2 = cast(Mapping[str, Any], result2.metrics["pass_criteria"])
    assert pc2["sharpe_ratio"] is False


# ---------------------------------------------------------------------------
# pass_criteria.all (3)
# ---------------------------------------------------------------------------


def test_pass_criteria_all_two_conditions_phase2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 2 (provider 未注入): mean+min の 2 条件 AND."""
    sharpes = {"EUR_JPY": 0.5, "EUR_USD": 0.4, "USD_JPY": 0.3}
    _patch_run_pair_sharpe(monkeypatch, sharpes)
    pair_bars, pair_meta = _build_pair_inputs(list(sharpes))
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
        # sharpe_target_single is default None
    )
    pc = cast(Mapping[str, Any], result.metrics["pass_criteria"])
    assert pc["sharpe_ratio"] is None
    assert pc["mean"] is True
    assert pc["min"] is True
    assert pc["all"] is True
    assert result.passed is True


def test_pass_criteria_all_three_conditions_with_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """provider 注入 + valid: 3 条件 AND."""
    sharpes = {"EUR_JPY": 0.9, "EUR_USD": 0.5, "USD_JPY": 0.3}
    _patch_run_pair_sharpe(monkeypatch, sharpes)
    pair_bars, pair_meta = _build_pair_inputs(list(sharpes))
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
        sharpe_target_single=1.0,
    )
    pc = cast(Mapping[str, Any], result.metrics["pass_criteria"])
    assert pc["sharpe_ratio"] is True
    assert pc["mean"] is True
    assert pc["min"] is True
    assert pc["all"] is True


def test_pass_criteria_all_one_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """1 条件 fail で all=False."""
    # mean = 0.10 < 0.15 なので fail
    sharpes = {"EUR_JPY": 0.20, "EUR_USD": 0.05, "USD_JPY": 0.05}
    _patch_run_pair_sharpe(monkeypatch, sharpes)
    pair_bars, pair_meta = _build_pair_inputs(list(sharpes))
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    pc = cast(Mapping[str, Any], result.metrics["pass_criteria"])
    assert pc["mean"] is False
    assert pc["all"] is False
    assert result.passed is False


# ---------------------------------------------------------------------------
# ratio skip pattern (3)
# ---------------------------------------------------------------------------


def test_sharpe_target_single_none_means_ratio_skip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sharpes = {"EUR_JPY": 0.5, "EUR_USD": 0.5, "USD_JPY": 0.5}
    _patch_run_pair_sharpe(monkeypatch, sharpes)
    pair_bars, pair_meta = _build_pair_inputs(list(sharpes))
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
        sharpe_target_single=None,
    )
    pc = cast(Mapping[str, Any], result.metrics["pass_criteria"])
    assert pc["sharpe_ratio"] is None
    assert result.metrics["sharpe_target_cross_ratio"] is None


def test_sharpe_target_single_zero_means_ratio_skip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sharpes = {"EUR_JPY": 0.5, "EUR_USD": 0.5, "USD_JPY": 0.5}
    _patch_run_pair_sharpe(monkeypatch, sharpes)
    pair_bars, pair_meta = _build_pair_inputs(list(sharpes))
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
        sharpe_target_single=0.0,
    )
    pc = cast(Mapping[str, Any], result.metrics["pass_criteria"])
    assert pc["sharpe_ratio"] is None
    assert result.metrics["sharpe_target_cross_ratio"] is None


def test_sharpe_target_single_negative_means_ratio_skip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sharpes = {"EUR_JPY": 0.5, "EUR_USD": 0.5, "USD_JPY": 0.5}
    _patch_run_pair_sharpe(monkeypatch, sharpes)
    pair_bars, pair_meta = _build_pair_inputs(list(sharpes))
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
        sharpe_target_single=-0.5,
    )
    pc = cast(Mapping[str, Any], result.metrics["pass_criteria"])
    assert pc["sharpe_ratio"] is None
    assert result.metrics["sharpe_target_cross_ratio"] is None


# ---------------------------------------------------------------------------
# skipped (4)
# ---------------------------------------------------------------------------


def test_skipped_target_not_in_anchors() -> None:
    pair_bars, pair_meta = _build_pair_inputs(["XXX_YYY", "AAA_BBB", "CCC_DDD"])
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="XXX_YYY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    assert result.passed is False
    assert result.reason_codes == ("skipped",)
    assert result.metrics["skipped"] is True
    assert "target_not_in_anchors" in cast(
        str, result.metrics["skip_reason"]
    )


def test_skipped_anchor_bars_missing() -> None:
    # EUR_JPY target、anchor の EUR_USD bars 欠落
    pair_bars: dict[str, list[PriceBar]] = {
        "EUR_JPY": [_dummy_bar("EUR_JPY")],
        "USD_JPY": [_dummy_bar("USD_JPY")],
    }
    pair_meta = {p: _dummy_meta(p) for p in ["EUR_JPY", "EUR_USD", "USD_JPY"]}
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    assert result.passed is False
    assert result.reason_codes == ("skipped",)
    assert result.metrics["skipped"] is True
    assert "EUR_USD" in cast(str, result.metrics["skip_reason"])


def test_skipped_anchor_meta_missing() -> None:
    pair_bars = {p: [_dummy_bar(p)] for p in ["EUR_JPY", "EUR_USD", "USD_JPY"]}
    pair_meta = {p: _dummy_meta(p) for p in ["EUR_JPY", "USD_JPY"]}  # EUR_USD 欠落
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    assert result.passed is False
    assert result.reason_codes == ("skipped",)
    assert result.metrics["skipped"] is True


def test_skipped_metrics_shape() -> None:
    """skipped 時の metrics canonical key 集合確認."""
    pair_bars, pair_meta = _build_pair_inputs(["EUR_JPY", "USD_JPY"])
    # EUR_USD 欠落 → skipped
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    expected_keys = {
        "sharpe_per_pair", "mean_sharpe", "std_sharpe", "min_sharpe",
        "aggregate_fitness", "aggregator_lambda",
        "sharpe_target_single", "sharpe_target_cross",
        "sharpe_target_cross_ratio", "liquidity_weighted_mean",
        "pass_criteria", "skipped", "skip_reason", "mode",
    }
    assert set(result.metrics.keys()) == expected_keys
    assert result.metrics["sharpe_per_pair"] == {}
    assert result.metrics["mean_sharpe"] is None
    assert result.metrics["aggregate_fitness"] is None
    pc = cast(Mapping[str, Any], result.metrics["pass_criteria"])
    assert pc["sharpe_ratio"] is None
    assert pc["mean"] is None
    assert pc["min"] is None
    assert pc["all"] is False


# ---------------------------------------------------------------------------
# pair_failure (3)
# ---------------------------------------------------------------------------


def test_pair_backtest_failure_imputed_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """1 pair で例外発生 → 0.0 imputation."""
    sharpes: dict[str, float | tuple[float, str | None]] = {
        "EUR_JPY": 0.5,
        "EUR_USD": (0.0, "exception:RuntimeError"),
        "USD_JPY": 0.5,
    }
    _patch_run_pair_sharpe(monkeypatch, cast(dict[str, float], sharpes))
    pair_bars, pair_meta = _build_pair_inputs(["EUR_JPY", "EUR_USD", "USD_JPY"])
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    sharpe_per_pair = cast(
        Mapping[str, float], result.metrics["sharpe_per_pair"]
    )
    assert sharpe_per_pair["EUR_USD"] == 0.0


def test_pair_backtest_failure_in_reason_codes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sharpes: dict[str, float | tuple[float, str | None]] = {
        "EUR_JPY": 0.5,
        "EUR_USD": (0.0, "exception:RuntimeError"),
        "USD_JPY": 0.5,
    }
    _patch_run_pair_sharpe(monkeypatch, cast(dict[str, float], sharpes))
    pair_bars, pair_meta = _build_pair_inputs(["EUR_JPY", "EUR_USD", "USD_JPY"])
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    assert any("pair_failure:EUR_USD" in r for r in result.reason_codes)


def test_pair_failure_forces_passed_false_even_if_thresholds_met(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pair_failure があれば mean/min が閾値を満たしても passed=False (fail-fast)."""
    # mean > 0.15、min > -0.20 だが EUR_USD で例外 → passed=False
    sharpes: dict[str, float | tuple[float, str | None]] = {
        "EUR_JPY": 0.8,
        "EUR_USD": (0.0, "exception:RuntimeError"),  # 失敗
        "USD_JPY": 0.5,
    }
    # mean = (0.8 + 0.0 + 0.5)/3 = 0.433 (> 0.15)
    # min = 0.0 (> -0.20)
    _patch_run_pair_sharpe(monkeypatch, cast(dict[str, float], sharpes))
    pair_bars, pair_meta = _build_pair_inputs(["EUR_JPY", "EUR_USD", "USD_JPY"])
    result = evaluate_cross_pair(
        genome=_dummy_genome(),
        target="EUR_JPY",
        pair_bars=pair_bars,
        pair_meta=pair_meta,
        backtest_config=_dummy_backtest_config(),
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    pc = cast(Mapping[str, Any], result.metrics["pass_criteria"])
    assert pc["mean"] is True
    assert pc["min"] is True
    assert pc["all"] is False  # ★ fail-fast on pair_failure
    assert result.passed is False


# ---------------------------------------------------------------------------
# Stage C 統合 (5)
# ---------------------------------------------------------------------------


def test_stage_c_run_evaluator_protocol_duck_typing() -> None:
    """StageCRunCrossPairEvaluator が evaluate(...) を持つ."""
    adapter = StageCRunCrossPairEvaluator(
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    assert hasattr(adapter, "evaluate")
    assert callable(adapter.evaluate)


def _make_continuous_bars(
    n_days: int, *, pair_name: str = "USD_JPY"
) -> list[PriceBar]:
    """test_stage_gate.py 流の連続日 bars 生成."""
    bars: list[PriceBar] = []
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    for d in range(n_days):
        for h in range(4):
            t = base + timedelta(days=d, hours=h * 6)
            bid = Decimal("154.00")
            ask = Decimal("154.01")
            bars.append(
                PriceBar(
                    pair_name=pair_name,
                    bar_time=t,
                    bid=Ohlc(bid, bid, bid, bid),
                    ask=Ohlc(ask, ask, ask, ask),
                    volume=10,
                    complete=True,
                )
            )
    return bars


class _StubCrossPairEvaluator:
    """test 用 stub. behavior: 'skipped' / 'exception' / 'normal'."""

    def __init__(self, behavior: str) -> None:
        self._behavior = behavior

    def evaluate(
        self,
        genome: Genome,
        target_pair: str,
        pair_bars_map: Mapping[str, list[PriceBar]],
        meta_map: Mapping[str, InstrumentMeta],
        backtest_config: BacktestConfig,
    ) -> CrossPairResult:
        if self._behavior == "exception":
            raise RuntimeError("stub failure")
        dummy_dt = datetime(2026, 1, 1, tzinfo=UTC)
        if self._behavior == "skipped":
            return CrossPairResult(
                target_pair=target_pair,
                anchor_pairs=("X", "Y"),
                aggregator_name="stub",
                window=(dummy_dt, dummy_dt),
                passed=False,
                metrics={
                    "skipped": True,
                    "skip_reason": "stub_skip",
                    "pass_criteria": {
                        "sharpe_ratio": None, "mean": None, "min": None,
                        "all": False,
                    },
                },
                reason_codes=("skipped",),
            )
        # normal
        return CrossPairResult(
            target_pair=target_pair,
            anchor_pairs=("X", "Y"),
            aggregator_name="stub",
            window=(dummy_dt, dummy_dt),
            passed=True,
            metrics={
                "skipped": False,
                "pass_criteria": {
                    "sharpe_ratio": True, "mean": True, "min": True,
                    "all": True,
                },
            },
            reason_codes=(),
        )


def _make_stage_c_inputs() -> tuple[
    list[PriceBar], InstrumentMeta, BacktestConfig, dict[str, list[PriceBar]],
    dict[str, InstrumentMeta],
]:
    bars = _make_continuous_bars(60, pair_name="USD_JPY")
    meta = InstrumentMeta(
        oanda_name="USD_JPY",
        base_currency="USD",
        quote_currency="JPY",
        margin_rate=Decimal("0.04"),
    )
    bt_config = BacktestConfig(
        instrument="USD_JPY",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 3, 1, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=25,
        max_spread_bps=Decimal("100"),
        session_close_utc_hours=frozenset({23}),
        bar_minutes=1,
    )
    pair_bars_map = {"USD_JPY": bars[:5]}
    meta_map = {"USD_JPY": meta}
    return bars, meta, bt_config, pair_bars_map, meta_map


def test_stage_c_skipped_propagates_to_payload() -> None:
    bars, meta, bt_config, pair_bars_map, meta_map = _make_stage_c_inputs()
    stub = _StubCrossPairEvaluator("skipped")
    result = evaluate_stage_c(
        genome=_dummy_genome(),
        bars_holdout=bars,
        meta=meta,
        backtest_config=bt_config,
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        stage_config=StageGateConfig(),
        cross_pair_evaluator=stub,
        cross_pair_inputs={
            "target_pair": "USD_JPY",
            "pair_bars_map": pair_bars_map,
            "meta_map": meta_map,
        },
    )
    payload = cast(Mapping[str, Any], result.metrics["payload"])
    cp = cast(Mapping[str, Any], payload["cross_pair"])
    assert cp["skipped"] is True
    # result は保持される (metrics 詳細用)
    assert isinstance(cp["result"], CrossPairResult)


def test_stage_c_exception_isolated_records_error_type() -> None:
    bars, meta, bt_config, pair_bars_map, meta_map = _make_stage_c_inputs()
    stub = _StubCrossPairEvaluator("exception")
    result = evaluate_stage_c(
        genome=_dummy_genome(),
        bars_holdout=bars,
        meta=meta,
        backtest_config=bt_config,
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        stage_config=StageGateConfig(),
        cross_pair_evaluator=stub,
        cross_pair_inputs={
            "target_pair": "USD_JPY",
            "pair_bars_map": pair_bars_map,
            "meta_map": meta_map,
        },
    )
    payload = cast(Mapping[str, Any], result.metrics["payload"])
    cp = cast(Mapping[str, Any], payload["cross_pair"])
    assert cp["skipped"] is True
    assert cp["result"] is None
    assert cp["error_type"] == "RuntimeError"
    # cross-pair 例外で stage_c.passed が False にならない (= base 判定のみ)
    # (既存 stage_c の passed は live_criteria 等で決まる)
    # cross-pair が原因で reason_codes に追加されないことを確認
    assert not any("cross_pair" in r for r in result.reason_codes)


def test_stage_c_normal_completion_payload_shape() -> None:
    bars, meta, bt_config, pair_bars_map, meta_map = _make_stage_c_inputs()
    stub = _StubCrossPairEvaluator("normal")
    result = evaluate_stage_c(
        genome=_dummy_genome(),
        bars_holdout=bars,
        meta=meta,
        backtest_config=bt_config,
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        stage_config=StageGateConfig(),
        cross_pair_evaluator=stub,
        cross_pair_inputs={
            "target_pair": "USD_JPY",
            "pair_bars_map": pair_bars_map,
            "meta_map": meta_map,
        },
    )
    payload = cast(Mapping[str, Any], result.metrics["payload"])
    cp = cast(Mapping[str, Any], payload["cross_pair"])
    assert cp["skipped"] is False
    assert isinstance(cp["result"], CrossPairResult)
    assert cp["error_type"] is None


def test_stage_c_passed_unaffected_by_cross_pair() -> None:
    """cross-pair の通過/失敗は stage_c.passed に影響しない (Phase 2 shadow)."""
    bars, meta, bt_config, pair_bars_map, meta_map = _make_stage_c_inputs()

    # without cross-pair
    result_a = evaluate_stage_c(
        genome=_dummy_genome(),
        bars_holdout=bars,
        meta=meta,
        backtest_config=bt_config,
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        stage_config=StageGateConfig(),
    )
    # with cross-pair (passed=True stub)
    result_b = evaluate_stage_c(
        genome=_dummy_genome(),
        bars_holdout=bars,
        meta=meta,
        backtest_config=bt_config,
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        stage_config=StageGateConfig(),
        cross_pair_evaluator=_StubCrossPairEvaluator("normal"),
        cross_pair_inputs={
            "target_pair": "USD_JPY",
            "pair_bars_map": pair_bars_map,
            "meta_map": meta_map,
        },
    )
    # with cross-pair (passed=False stub via skipped)
    result_c = evaluate_stage_c(
        genome=_dummy_genome(),
        bars_holdout=bars,
        meta=meta,
        backtest_config=bt_config,
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        stage_config=StageGateConfig(),
        cross_pair_evaluator=_StubCrossPairEvaluator("skipped"),
        cross_pair_inputs={
            "target_pair": "USD_JPY",
            "pair_bars_map": pair_bars_map,
            "meta_map": meta_map,
        },
    )
    # 3 つとも passed が一致 (cross-pair は無影響)
    assert result_a.passed == result_b.passed == result_c.passed


# ---------------------------------------------------------------------------
# archive 連動 (2)
# ---------------------------------------------------------------------------


def test_archive_ii_lite_pass_skipped_yields_none() -> None:
    """skipped CrossPairResult → archive ii_lite_pass=None."""
    from src.alpha_factory.archive import GenomeArchive

    bars, meta, bt_config, pair_bars_map, meta_map = _make_stage_c_inputs()
    stub = _StubCrossPairEvaluator("skipped")
    stage_c_result = evaluate_stage_c(
        genome=_dummy_genome(),
        bars_holdout=bars,
        meta=meta,
        backtest_config=bt_config,
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        stage_config=StageGateConfig(),
        cross_pair_evaluator=stub,
        cross_pair_inputs={
            "target_pair": "USD_JPY",
            "pair_bars_map": pair_bars_map,
            "meta_map": meta_map,
        },
    )
    archive = GenomeArchive(run_id="run_test", run_number=1)
    archive.collect_stage_c(
        genome=_dummy_genome(),
        lane_id="lane1",
        generation=0,
        stage_result=stage_c_result,
        instrument="USD_JPY",
    )
    row = archive._rows[("lane1", 0, "g_test")]
    assert row["ii_lite_pass"] is None


def test_archive_ii_lite_pass_normal_completion_yields_bool() -> None:
    """non-skipped CrossPairResult → archive ii_lite_pass = bool(result.passed)."""
    from src.alpha_factory.archive import GenomeArchive

    bars, meta, bt_config, pair_bars_map, meta_map = _make_stage_c_inputs()
    stub = _StubCrossPairEvaluator("normal")
    stage_c_result = evaluate_stage_c(
        genome=_dummy_genome(),
        bars_holdout=bars,
        meta=meta,
        backtest_config=bt_config,
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        stage_config=StageGateConfig(),
        cross_pair_evaluator=stub,
        cross_pair_inputs={
            "target_pair": "USD_JPY",
            "pair_bars_map": pair_bars_map,
            "meta_map": meta_map,
        },
    )
    archive = GenomeArchive(run_id="run_test", run_number=1)
    archive.collect_stage_c(
        genome=_dummy_genome(),
        lane_id="lane1",
        generation=0,
        stage_result=stage_c_result,
        instrument="USD_JPY",
    )
    row = archive._rows[("lane1", 0, "g_test")]
    # stub の normal は passed=True を返す
    assert row["ii_lite_pass"] is True


# ---------------------------------------------------------------------------
# E2E sanity (1) — 実 backtest with monkeypatched _run_pair_sharpe is enough
# 真の E2E (実 backtest 3 回) は MockBroker 制約のため省略
# ---------------------------------------------------------------------------


def test_e2e_evaluator_returns_cross_pair_result_via_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """StageCRunCrossPairEvaluator.evaluate が CrossPairResult を返す."""
    sharpes = {"EUR_JPY": 0.5, "EUR_USD": 0.4, "USD_JPY": 0.3}
    _patch_run_pair_sharpe(monkeypatch, sharpes)
    pair_bars, pair_meta = _build_pair_inputs(list(sharpes))
    adapter = StageCRunCrossPairEvaluator(
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
    )
    result = adapter.evaluate(
        genome=_dummy_genome(),
        target_pair="EUR_JPY",
        pair_bars_map=pair_bars,
        meta_map=pair_meta,
        backtest_config=_dummy_backtest_config(),
    )
    assert isinstance(result, CrossPairResult)
    assert result.target_pair == "EUR_JPY"
    assert result.anchor_pairs == ("EUR_USD", "USD_JPY")


def test_adapter_with_provider_invokes_ratio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """provider 注入で ratio 評価が opt-in される."""
    sharpes = {"EUR_JPY": 0.8, "EUR_USD": 0.5, "USD_JPY": 0.5}
    _patch_run_pair_sharpe(monkeypatch, sharpes)
    pair_bars, pair_meta = _build_pair_inputs(list(sharpes))
    adapter = StageCRunCrossPairEvaluator(
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
        sharpe_target_single_provider=lambda: 1.0,
    )
    result = adapter.evaluate(
        genome=_dummy_genome(),
        target_pair="EUR_JPY",
        pair_bars_map=pair_bars,
        meta_map=pair_meta,
        backtest_config=_dummy_backtest_config(),
    )
    pc = cast(Mapping[str, Any], result.metrics["pass_criteria"])
    assert pc["sharpe_ratio"] is not None  # 評価された
    assert result.metrics["sharpe_target_single"] == 1.0


def test_adapter_provider_failure_falls_back_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """provider が例外を投げると ratio が None になる (fallback)."""
    sharpes = {"EUR_JPY": 0.5, "EUR_USD": 0.5, "USD_JPY": 0.5}
    _patch_run_pair_sharpe(monkeypatch, sharpes)
    pair_bars, pair_meta = _build_pair_inputs(list(sharpes))

    def failing_provider() -> float | None:
        raise RuntimeError("provider broken")

    adapter = StageCRunCrossPairEvaluator(
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        cross_pair_config=CrossPairConfig(),
        sharpe_target_single_provider=failing_provider,
    )
    result = adapter.evaluate(
        genome=_dummy_genome(),
        target_pair="EUR_JPY",
        pair_bars_map=pair_bars,
        meta_map=pair_meta,
        backtest_config=_dummy_backtest_config(),
    )
    pc = cast(Mapping[str, Any], result.metrics["pass_criteria"])
    assert pc["sharpe_ratio"] is None
