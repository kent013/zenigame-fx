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
        quote_currency="JPY",  # 既存テストは JPY 固定で monkeypatch ロジック検証のみ
        margin_rate=Decimal("0.04"),
        pip_size=Decimal("0.01"),
        display_precision=3,
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
    """``_run_pair_sharpe`` を固定 Sharpe で置換する.

    B step 1.8 で戻り値が 3-tuple ``(sharpe, failure_reason, sidecar_inputs)`` に
    拡張された (= dual-path 経路用 sidecar 追加)。 本 helper では sidecar は
    None を返す (= 既存 test は dual-path 経路を直接検証しないため、
    cross_pair.py 内 aggregation 経路の振る舞いのみ確認する pattern)。
    sidecar 関連の振る舞いを検証する test は別途 _PairSidecarInputs を
    構築する fake を使う。
    """

    def fake_run(
        *,
        genome: Genome,
        pair: str,
        bars: list[PriceBar],
        meta: InstrumentMeta,
        backtest_config: BacktestConfig,
        primitive_evaluator: Any,
    ) -> tuple[float, str | None, Any]:
        v = sharpes[pair]
        if isinstance(v, tuple):
            sharpe, fail = v
            return sharpe, fail, None
        return float(v), None, None

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
        pip_size=Decimal("0.01"),
        display_precision=3,
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


# ---------------------------------------------------------------------------
# B step 1.8: cross_pair dual-path sidecar / dataclass / pickle (8)
# ---------------------------------------------------------------------------


def test_cross_pair_result_dataclass_compare_excludes_shadow_sidecar() -> None:
    """`_shadow_sidecar_inputs` が dataclass equality から除外される
    (= acceptance E5、 `field(compare=False)` の振る舞い)."""
    from src.alpha_factory.stage_gate import CrossPairResult, _PairSidecarInputs
    from src.backtest.metrics import BacktestMetrics

    bt_a = BacktestMetrics(
        trade_count=5, win_count=3, loss_count=2,
        win_rate=Decimal("0.6"), total_pnl=Decimal("100"),
        avg_win=Decimal("50"), avg_loss=Decimal("-25"),
        profit_factor=Decimal("3"),
        max_drawdown=Decimal("0"), max_drawdown_pct=Decimal("0"),
        final_equity=Decimal("1000100"),
        sharpe=None, sortino=None, calmar=None,
        avg_trade_duration=None, max_trade_duration=None,
    )
    side_a = _PairSidecarInputs(bars=[], trades=[], equity_curve=[], bt=bt_a)
    base_args: dict[str, Any] = {
        "target_pair": "EUR_JPY",
        "anchor_pairs": ("EUR_USD", "USD_JPY"),
        "aggregator_name": "mean_minus_0.5_std",
        "window": (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC)),
        "passed": True,
        "metrics": {"sharpe_per_pair": {"EUR_JPY": 1.0}},
        "reason_codes": (),
    }
    r_empty = CrossPairResult(**base_args)
    r_with_sidecar = CrossPairResult(**base_args, _shadow_sidecar_inputs={"EUR_JPY": side_a})
    # equality は sidecar を除外して比較される (= field(compare=False))
    assert r_empty == r_with_sidecar


def test_cross_pair_result_dataclass_repr_excludes_shadow_sidecar() -> None:
    """`_shadow_sidecar_inputs` が repr から除外される (= acceptance E5、
    `field(repr=False)` の振る舞い、 snapshot 比較ノイズ排除)."""
    from src.alpha_factory.stage_gate import CrossPairResult, _PairSidecarInputs
    from src.backtest.metrics import BacktestMetrics

    bt_a = BacktestMetrics(
        trade_count=5, win_count=3, loss_count=2,
        win_rate=Decimal("0.6"), total_pnl=Decimal("100"),
        avg_win=Decimal("50"), avg_loss=Decimal("-25"),
        profit_factor=Decimal("3"),
        max_drawdown=Decimal("0"), max_drawdown_pct=Decimal("0"),
        final_equity=Decimal("1000100"),
        sharpe=None, sortino=None, calmar=None,
        avg_trade_duration=None, max_trade_duration=None,
    )
    side_a = _PairSidecarInputs(bars=[], trades=[], equity_curve=[], bt=bt_a)
    r = CrossPairResult(
        target_pair="EUR_JPY",
        anchor_pairs=("EUR_USD", "USD_JPY"),
        aggregator_name="mean_minus_0.5_std",
        window=(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC)),
        passed=True,
        metrics={},
        reason_codes=(),
        _shadow_sidecar_inputs={"EUR_JPY": side_a},
    )
    rendered = repr(r)
    assert "_shadow_sidecar_inputs" not in rendered
    assert "_PairSidecarInputs" not in rendered


def test_cross_pair_result_pickle_compatible_with_empty_and_nonempty_sidecar() -> None:
    """`pickle.dumps` が空 sidecar / non-空 sidecar 両方で TypeError を出さず成功
    (= acceptance E4、 multiprocessing pickle 互換、 `default_factory=dict` が key)."""
    import pickle

    from src.alpha_factory.stage_gate import CrossPairResult, _PairSidecarInputs
    from src.backtest.metrics import BacktestMetrics

    bt_a = BacktestMetrics(
        trade_count=5, win_count=3, loss_count=2,
        win_rate=Decimal("0.6"), total_pnl=Decimal("100"),
        avg_win=Decimal("50"), avg_loss=Decimal("-25"),
        profit_factor=Decimal("3"),
        max_drawdown=Decimal("0"), max_drawdown_pct=Decimal("0"),
        final_equity=Decimal("1000100"),
        sharpe=None, sortino=None, calmar=None,
        avg_trade_duration=None, max_trade_duration=None,
    )
    side_a = _PairSidecarInputs(bars=[], trades=[], equity_curve=[], bt=bt_a)
    base_args: dict[str, Any] = {
        "target_pair": "EUR_JPY",
        "anchor_pairs": ("EUR_USD", "USD_JPY"),
        "aggregator_name": "mean_minus_0.5_std",
        "window": (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC)),
        "passed": True,
        "metrics": {},
        "reason_codes": (),
    }
    r_empty = CrossPairResult(**base_args)
    r_full = CrossPairResult(**base_args, _shadow_sidecar_inputs={"EUR_JPY": side_a})
    # 両方とも pickle 成功
    blob_empty = pickle.dumps(r_empty)
    blob_full = pickle.dumps(r_full)
    restored_empty = pickle.loads(blob_empty)
    restored_full = pickle.loads(blob_full)
    assert restored_empty._shadow_sidecar_inputs == {}
    assert "EUR_JPY" in restored_full._shadow_sidecar_inputs


def test_evaluate_cross_pair_returns_sidecar_inputs_per_pair_for_all_successful_pairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`evaluate_cross_pair` が成功 pair 全件について _shadow_sidecar_inputs に
    sidecar を集約する (= acceptance A2 cross_pair sidecar 集約、
    詳細設計 § 7.4)."""
    from src.alpha_factory.cross_pair import _PairSidecarInputs as _SidecarRef

    # 自前 fake で sidecar を返す (= 既存 _patch_run_pair_sharpe は sidecar None)
    def fake_run(
        *,
        genome: Genome,
        pair: str,
        bars: list[PriceBar],
        meta: InstrumentMeta,
        backtest_config: BacktestConfig,
        primitive_evaluator: Any,
    ) -> tuple[float, str | None, _SidecarRef | None]:
        from src.backtest.metrics import BacktestMetrics
        bt = BacktestMetrics(
            trade_count=5, win_count=3, loss_count=2,
            win_rate=Decimal("0.6"), total_pnl=Decimal("100"),
            avg_win=Decimal("50"), avg_loss=Decimal("-25"),
            profit_factor=Decimal("3"),
            max_drawdown=Decimal("0"), max_drawdown_pct=Decimal("0"),
            final_equity=Decimal("1000100"),
            sharpe=None, sortino=None, calmar=None,
            avg_trade_duration=None, max_trade_duration=None,
            trade_sharpe_raw=Decimal("1.0"),
        )
        sidecar = _SidecarRef(bars=bars, trades=[], equity_curve=[], bt=bt)
        return 1.0, None, sidecar

    monkeypatch.setattr(
        "src.alpha_factory.cross_pair._run_pair_sharpe", fake_run
    )

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
    assert set(result._shadow_sidecar_inputs.keys()) == {
        "EUR_JPY", "EUR_USD", "USD_JPY"
    }


def test_evaluate_cross_pair_existing_metrics_keys_unchanged_full_deep_equality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`evaluate_cross_pair` の `metrics` dict 既存全 key (= sharpe_per_pair /
    aggregate_fitness 等) が sidecar 配線追加で変化しない
    (= acceptance A2、 詳細設計 Round 2 [Suggestion 施策 4] 反映で deep equality 強化)."""
    sharpes = {"EUR_JPY": 1.0, "EUR_USD": 1.2, "USD_JPY": 0.8}
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
    metrics = result.metrics
    # 既存 public keys 全件存在 (= 元の API)
    expected_keys = {
        "sharpe_per_pair", "mean_sharpe", "std_sharpe", "min_sharpe",
        "aggregate_fitness", "aggregator_lambda",
        "sharpe_target_single", "sharpe_target_cross", "sharpe_target_cross_ratio",
        "liquidity_weighted_mean", "pass_criteria",
        "skipped", "skip_reason", "mode",
    }
    assert set(metrics.keys()) == expected_keys
    # sidecar 起源 key が metrics に絶対漏れないこと (= acceptance E1/E2)
    assert "canonical_per_pair" not in metrics
    assert "legacy_per_pair" not in metrics
    assert "_shadow_sidecar_inputs" not in metrics


# ---------------------------------------------------------------------------
# B step 1.8: helper 単体識別子契約 + 既存 caller 互換 (8)
# ---------------------------------------------------------------------------


def _build_dummy_legacy_metrics() -> Any:
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


def test_log_canonical_dual_path_rejects_pair_label_none_for_c_cross_pair() -> None:
    """`stage_label="C_cross_pair"` で `pair_label=None` は ValueError
    (= acceptance D5、 識別子契約 fail-fast)."""
    from src.alpha_factory.stage_gate import _log_canonical_dual_path
    with pytest.raises(ValueError, match="C_cross_pair"):
        _log_canonical_dual_path(
            stage_label="C_cross_pair",
            genome_name="g",
            legacy=_build_dummy_legacy_metrics(),
            canonical=None,
            pair_label=None,
        )


def test_log_canonical_dual_path_rejects_empty_pair_label_for_c_cross_pair() -> None:
    """`pair_label=""` / `"  "` は ValueError (= 識別子契約 fail-fast)."""
    from src.alpha_factory.stage_gate import _log_canonical_dual_path
    for bad in ("", "  ", "\t\n"):
        with pytest.raises(ValueError, match="C_cross_pair"):
            _log_canonical_dual_path(
                stage_label="C_cross_pair",
                genome_name="g",
                legacy=_build_dummy_legacy_metrics(),
                canonical=None,
                pair_label=bad,
            )


def test_log_canonical_dual_path_rejects_pair_label_with_leading_or_trailing_whitespace() -> None:
    """`pair_label=' EUR_USD '` 等 前後空白付きは ValueError
    (= acceptance D5、 Codex detailed-review Round 2 [Warning 施策 2] 反映)."""
    from src.alpha_factory.stage_gate import _log_canonical_dual_path
    for bad in (" EUR_USD", "EUR_USD ", " EUR_USD ", "\tEUR_USD"):
        with pytest.raises(ValueError, match="whitespace"):
            _log_canonical_dual_path(
                stage_label="C_cross_pair",
                genome_name="g",
                legacy=_build_dummy_legacy_metrics(),
                canonical=None,
                pair_label=bad,
            )


def test_log_canonical_dual_path_rejects_pair_label_for_non_cross_pair_stages() -> None:
    """`stage_label != "C_cross_pair"` で `pair_label is not None` は ValueError
    (= acceptance D5、 Codex detailed-review Round 2 [Suggestion 施策 2] 反映、
    ログ名前空間汚染防止)."""
    from src.alpha_factory.stage_gate import _log_canonical_dual_path
    for stage in ("A", "B_IS", "B_fold", "C_base", "C_stress"):
        with pytest.raises(ValueError, match="does not accept"):
            _log_canonical_dual_path(
                stage_label=stage,
                genome_name="g",
                legacy=_build_dummy_legacy_metrics(),
                canonical=None,
                fold_index=0 if stage == "B_fold" else None,
                pair_label="EUR_USD",
            )


def test_log_canonical_dual_path_existing_caller_compat_stage_a(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`stage_label="A"` で `pair_label` 不指定 (default None) で動作不変
    (= acceptance A5、 既存 51 caller 後方互換、 Round 1 [Warning 施策 2] 反映)."""
    from src.alpha_factory.stage_gate import _log_canonical_dual_path
    _log_canonical_dual_path(
        stage_label="A",
        genome_name="g",
        legacy=_build_dummy_legacy_metrics(),
        canonical=None,
    )
    _captured = capsys.readouterr()
    combined = _captured.out + _captured.err
    assert "stage='A'" in combined or "stage=A" in combined or "stage_gate.canonical_five.dual_path" in combined
    assert "pair=" not in combined


def test_log_canonical_dual_path_existing_caller_compat_stage_b_fold(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`stage_label="B_fold"` で `pair_label` 不指定 + `fold_index=0` で動作不変."""
    from src.alpha_factory.stage_gate import _log_canonical_dual_path
    _log_canonical_dual_path(
        stage_label="B_fold",
        genome_name="g",
        legacy=_build_dummy_legacy_metrics(),
        canonical=None,
        fold_index=2,
    )
    _captured = capsys.readouterr()
    combined = _captured.out + _captured.err
    assert "fold=2" in combined
    assert "pair=" not in combined


def test_log_canonical_dual_path_existing_caller_compat_stage_c_base(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`stage_label="C_base"` で `pair_label` 不指定で動作不変."""
    from src.alpha_factory.stage_gate import _log_canonical_dual_path
    _log_canonical_dual_path(
        stage_label="C_base",
        genome_name="g",
        legacy=_build_dummy_legacy_metrics(),
        canonical=None,
    )
    _captured = capsys.readouterr()
    combined = _captured.out + _captured.err
    assert "pair=" not in combined


def test_log_canonical_dual_path_existing_caller_compat_stage_c_stress(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`stage_label="C_stress"` で `pair_label` 不指定で動作不変."""
    from src.alpha_factory.stage_gate import _log_canonical_dual_path
    _log_canonical_dual_path(
        stage_label="C_stress",
        genome_name="g",
        legacy=_build_dummy_legacy_metrics(),
        canonical=None,
    )
    _captured = capsys.readouterr()
    combined = _captured.out + _captured.err
    assert "pair=" not in combined


def test_log_canonical_dual_path_emits_pair_kwarg_for_c_cross_pair(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`stage_label="C_cross_pair"` + `pair_label="EUR_USD"` で log_kwargs に
    `pair=EUR_USD` が emit される (= acceptance C4、 識別子契約)."""
    from src.alpha_factory.stage_gate import _log_canonical_dual_path
    _log_canonical_dual_path(
        stage_label="C_cross_pair",
        genome_name="g",
        legacy=_build_dummy_legacy_metrics(),
        canonical=None,
        pair_label="EUR_USD",
    )
    _captured = capsys.readouterr()
    combined = _captured.out + _captured.err
    assert "pair=" in combined
    # canonical_skipped event なら canonical=None で `canonical_skipped=True` が emit
    assert "canonical_skipped" in combined


# ---------------------------------------------------------------------------
# B step 1.8: evaluate_stage_c cross_pair dual-path E2E (8)
# ---------------------------------------------------------------------------


class _StubCrossPairEvaluatorWithSidecar:
    """test 用 stub: 任意の sidecar を保持して CrossPairResult を返す.

    real な per-pair backtest を走らせず、 dual-path 経路 (= stage_gate.py 側
    canonical 計算 + log emit + sanitize) を直接駆動するための fake。
    """

    def __init__(
        self,
        anchor_pairs: tuple[str, str] = ("EUR_USD", "USD_JPY"),
        sidecar_pairs: tuple[str, ...] = ("EUR_JPY", "EUR_USD", "USD_JPY"),
        *,
        skipped: bool = False,
    ) -> None:
        self._anchor_pairs = anchor_pairs
        self._sidecar_pairs = sidecar_pairs
        self._skipped = skipped

    def evaluate(
        self,
        genome: Genome,
        target_pair: str,
        pair_bars_map: Mapping[str, list[PriceBar]],
        meta_map: Mapping[str, InstrumentMeta],
        backtest_config: BacktestConfig,
    ) -> CrossPairResult:
        from src.alpha_factory.stage_gate import _PairSidecarInputs
        dummy_dt = datetime(2026, 1, 1, tzinfo=UTC)
        bt = _build_dummy_legacy_metrics()
        bars = list(pair_bars_map.get(target_pair, []))
        sidecars: dict[str, _PairSidecarInputs] = {}
        if not self._skipped:
            for pair in self._sidecar_pairs:
                sidecars[pair] = _PairSidecarInputs(
                    bars=bars, trades=[], equity_curve=[], bt=bt,
                )
        return CrossPairResult(
            target_pair=target_pair,
            anchor_pairs=self._anchor_pairs,
            aggregator_name="stub",
            window=(dummy_dt, dummy_dt),
            passed=not self._skipped,
            metrics={
                "skipped": self._skipped,
                "skip_reason": "stub_skip" if self._skipped else "",
                "pass_criteria": {
                    "sharpe_ratio": None, "mean": True, "min": True,
                    "all": not self._skipped,
                },
            },
            reason_codes=("skipped",) if self._skipped else (),
            _shadow_sidecar_inputs=sidecars,
        )


def test_evaluate_stage_c_cross_pair_dual_path_emits_per_pair_logs_in_log_only_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """log_only mode で C_cross_pair dual-path log が per-pair × N 件 emit される
    (= acceptance B1 / C1-C4)."""
    bars, meta, bt_config, pair_bars_map, meta_map = _make_stage_c_inputs()
    stub = _StubCrossPairEvaluatorWithSidecar(
        sidecar_pairs=("USD_JPY", "EUR_USD", "EUR_JPY"),
    )
    pair_bars_map_full = {
        "USD_JPY": pair_bars_map["USD_JPY"],
        "EUR_USD": pair_bars_map["USD_JPY"],
        "EUR_JPY": pair_bars_map["USD_JPY"],
    }
    meta_map_full = {p: meta_map["USD_JPY"] for p in pair_bars_map_full}
    result = evaluate_stage_c(
        genome=_dummy_genome(),
        bars_holdout=bars,
        meta=meta,
        backtest_config=bt_config,
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        stage_config=StageGateConfig(phase2_canonical_metrics_mode="log_only"),
        cross_pair_evaluator=stub,
        cross_pair_inputs={
            "target_pair": "USD_JPY",
            "pair_bars_map": pair_bars_map_full,
            "meta_map": meta_map_full,
        },
    )
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # C_cross_pair dual_path event が 3 件 (= per pair) emit
    cp_lines = [
        ln for ln in combined.splitlines()
        if "stage_gate.canonical_five.dual_path" in ln and "C_cross_pair" in ln
    ]
    assert len(cp_lines) == 3, f"expected 3, got {len(cp_lines)}: {cp_lines}"
    # 全 pair が log entry に含まれる
    for pair in ("USD_JPY", "EUR_USD", "EUR_JPY"):
        assert any(pair in ln for ln in cp_lines), f"missing pair {pair}"
    # dual-path 自体は cross_pair gate の passed に影響しない
    assert isinstance(result.metrics["payload"], Mapping)


def test_evaluate_stage_c_cross_pair_dual_path_skips_when_skipped(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """cp_result が skipped のとき C_cross_pair dual-path event は 0 件
    (= acceptance C5)."""
    bars, meta, bt_config, pair_bars_map, meta_map = _make_stage_c_inputs()
    stub = _StubCrossPairEvaluatorWithSidecar(skipped=True)
    evaluate_stage_c(
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
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    cp_lines = [
        ln for ln in combined.splitlines()
        if "stage_gate.canonical_five" in ln and "C_cross_pair" in ln
    ]
    assert len(cp_lines) == 0


def test_evaluate_stage_c_cross_pair_dual_path_skips_when_evaluator_none(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """cross_pair_evaluator=None なら C_cross_pair dual-path event は 0 件
    (= acceptance C5)."""
    bars, meta, bt_config, _, _ = _make_stage_c_inputs()
    evaluate_stage_c(
        genome=_dummy_genome(),
        bars_holdout=bars,
        meta=meta,
        backtest_config=bt_config,
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        stage_config=StageGateConfig(),
        cross_pair_evaluator=None,
    )
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    cp_lines = [
        ln for ln in combined.splitlines()
        if "stage_gate.canonical_five" in ln and "C_cross_pair" in ln
    ]
    assert len(cp_lines) == 0


def test_evaluate_stage_c_cross_pair_payload_sidecar_is_sanitized_after_dual_path() -> None:
    """dual-path 経路成功後、 cross_pair_payload['result']._shadow_sidecar_inputs が
    空 dict に sanitize される (= acceptance E2 / E6)."""
    bars, meta, bt_config, pair_bars_map, meta_map = _make_stage_c_inputs()
    stub = _StubCrossPairEvaluatorWithSidecar(sidecar_pairs=("USD_JPY",))
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
    assert isinstance(cp["result"], CrossPairResult)
    assert cp["result"]._shadow_sidecar_inputs == {}


def test_evaluate_stage_c_cross_pair_payload_sidecar_is_sanitized_when_canonical_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dual-path で canonical helper が raise しても sanitize は finally で常時実行
    される (= acceptance E2 / D1 / D3、 try-finally 保証)."""
    from src.alpha_factory import stage_gate as sg

    original_helper = sg._try_evaluate_canonical_five_safe

    def conditional_raise(**kwargs: Any) -> Any:
        if kwargs.get("stage_label") == "C_cross_pair":
            raise RuntimeError("simulated C_cross_pair canonical failure")
        return original_helper(**kwargs)

    monkeypatch.setattr(sg, "_try_evaluate_canonical_five_safe", conditional_raise)
    bars, meta, bt_config, pair_bars_map, meta_map = _make_stage_c_inputs()
    stub = _StubCrossPairEvaluatorWithSidecar(sidecar_pairs=("USD_JPY", "EUR_USD"))
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
    assert isinstance(cp["result"], CrossPairResult)
    # 例外発生でも sanitize は finally で常時実行
    assert cp["result"]._shadow_sidecar_inputs == {}


def test_evaluate_stage_c_cross_pair_payload_sidecar_is_sanitized_in_disabled_mode() -> None:
    """disabled mode でも sanitize は finally で常時実行される
    (= acceptance E2、 disabled mode 軽量分岐)."""
    bars, meta, bt_config, pair_bars_map, meta_map = _make_stage_c_inputs()
    stub = _StubCrossPairEvaluatorWithSidecar(sidecar_pairs=("USD_JPY",))
    result = evaluate_stage_c(
        genome=_dummy_genome(),
        bars_holdout=bars,
        meta=meta,
        backtest_config=bt_config,
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        stage_config=StageGateConfig(phase2_canonical_metrics_mode="disabled"),
        cross_pair_evaluator=stub,
        cross_pair_inputs={
            "target_pair": "USD_JPY",
            "pair_bars_map": pair_bars_map,
            "meta_map": meta_map,
        },
    )
    payload = cast(Mapping[str, Any], result.metrics["payload"])
    cp = cast(Mapping[str, Any], payload["cross_pair"])
    assert isinstance(cp["result"], CrossPairResult)
    assert cp["result"]._shadow_sidecar_inputs == {}


def test_evaluate_stage_c_cross_pair_disabled_mode_emits_canonical_skipped_event(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """disabled mode で per-pair lightweight log (= canonical_skipped event) が
    emit される (= acceptance C5、 step 1.6 disabled mode と整合)."""
    bars, meta, bt_config, pair_bars_map, meta_map = _make_stage_c_inputs()
    stub = _StubCrossPairEvaluatorWithSidecar(sidecar_pairs=("USD_JPY", "EUR_USD"))
    evaluate_stage_c(
        genome=_dummy_genome(),
        bars_holdout=bars,
        meta=meta,
        backtest_config=bt_config,
        primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
        stage_config=StageGateConfig(phase2_canonical_metrics_mode="disabled"),
        cross_pair_evaluator=stub,
        cross_pair_inputs={
            "target_pair": "USD_JPY",
            "pair_bars_map": pair_bars_map,
            "meta_map": meta_map,
        },
    )
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    cp_lines = [
        ln for ln in combined.splitlines()
        if "stage_gate.canonical_five.dual_path" in ln and "C_cross_pair" in ln
    ]
    # disabled mode でも per-pair × 2 件 emit (= canonical_skipped=True)
    assert len(cp_lines) == 2
    for ln in cp_lines:
        assert "canonical_skipped" in ln


def test_evaluate_stage_c_cross_pair_skips_invalid_pair_key(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """sidecar dict に invalid pair key (= 空文字 / 空白) が混入しても
    `_log_canonical_dual_path` は呼ばれず WARN log + skip
    (= acceptance D5、 内部不整合の早期検出、
    Codex detailed-review Round 2 [Suggestion 施策 5] 反映)."""
    from src.alpha_factory import stage_gate as sg
    from src.alpha_factory.stage_gate import _PairSidecarInputs
    dummy_dt = datetime(2026, 1, 1, tzinfo=UTC)
    bt = _build_dummy_legacy_metrics()

    class _StubWithBadKey:
        def evaluate(
            self,
            genome: Genome,
            target_pair: str,
            pair_bars_map: Mapping[str, list[PriceBar]],
            meta_map: Mapping[str, InstrumentMeta],
            backtest_config: BacktestConfig,
        ) -> CrossPairResult:
            return CrossPairResult(
                target_pair=target_pair,
                anchor_pairs=("EUR_USD", "EUR_JPY"),
                aggregator_name="stub",
                window=(dummy_dt, dummy_dt),
                passed=True,
                metrics={
                    "skipped": False,
                    "pass_criteria": {
                        "sharpe_ratio": None, "mean": True, "min": True,
                        "all": True,
                    },
                },
                reason_codes=(),
                _shadow_sidecar_inputs={
                    "USD_JPY": _PairSidecarInputs(bars=[], trades=[], equity_curve=[], bt=bt),
                    "  ": _PairSidecarInputs(bars=[], trades=[], equity_curve=[], bt=bt),
                    "": _PairSidecarInputs(bars=[], trades=[], equity_curve=[], bt=bt),
                },
            )

    bars, meta, bt_config, pair_bars_map, meta_map = _make_stage_c_inputs()
    log_calls: list[dict[str, Any]] = []
    original_log = sg._log_canonical_dual_path

    def spy_log(**kwargs: Any) -> None:
        log_calls.append(kwargs)
        original_log(**kwargs)

    import unittest.mock as _mock
    with _mock.patch.object(sg, "_log_canonical_dual_path", side_effect=spy_log):
        evaluate_stage_c(
            genome=_dummy_genome(),
            bars_holdout=bars,
            meta=meta,
            backtest_config=bt_config,
            primitive_evaluator=ConstantPrimitiveEvaluator(0.0),
            stage_config=StageGateConfig(),
            cross_pair_evaluator=_StubWithBadKey(),
            cross_pair_inputs={
                "target_pair": "USD_JPY",
                "pair_bars_map": pair_bars_map,
                "meta_map": meta_map,
            },
        )

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # invalid_pair_key WARN が emit
    assert "invalid_pair_key" in combined
    # _log_canonical_dual_path は USD_JPY (正当) に対してのみ呼ばれる
    cp_calls = [
        c for c in log_calls
        if c.get("stage_label") == "C_cross_pair"
    ]
    assert len(cp_calls) == 1
    assert cp_calls[0].get("pair_label") == "USD_JPY"


def test_evaluate_stage_c_cross_pair_dual_path_skips_exception_pair() -> None:
    """exception pair (= sidecar_inputs is None) では dual-path 経路に進まない
    (= acceptance C5 / C6、 dual-path skip SSOT)."""
    bars, meta, bt_config, pair_bars_map, meta_map = _make_stage_c_inputs()
    # sidecar_pairs は (target, anchor1) のみで anchor2 は不在 (= exception で sidecar None 想定)
    stub = _StubCrossPairEvaluatorWithSidecar(
        sidecar_pairs=("USD_JPY", "EUR_USD"),
    )
    # _shadow_sidecar_inputs に EUR_JPY は含まれない (= exception 模擬)
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
    # sanitize 後は空 dict
    assert cp["result"]._shadow_sidecar_inputs == {}


def test_log_canonical_dual_path_existing_caller_compat_stage_b_is(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`stage_label="B_IS"` で `pair_label` 不指定で動作不変
    (= acceptance A5、 既存 51 caller 後方互換、 Codex impl-review Round 1
    [Critical test_cross_pair.py] 反映で B_IS ケースを追加)."""
    from src.alpha_factory.stage_gate import _log_canonical_dual_path
    _log_canonical_dual_path(
        stage_label="B_IS",
        genome_name="g",
        legacy=_build_dummy_legacy_metrics(),
        canonical=None,
    )
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "stage_gate.canonical_five.dual_path" in combined
    assert "pair=" not in combined
    assert "fold=" not in combined


def test_try_evaluate_canonical_five_safe_returns_none_for_no_trade_input() -> None:
    """`_try_evaluate_canonical_five_safe` が trades=[] (= no-trade) 入力で
    None を返す (= Round 5 [Suggestion 施策 6] 反映で test #26a 分離、
    helper の None 返却 single-責務)."""
    from src.alpha_factory.stage_gate import _try_evaluate_canonical_five_safe
    bars = _make_continuous_bars(60, pair_name="USD_JPY")
    live_criteria: dict[str, float | int] = {
        "sharpe_min": 1.0,
        "total_pnl_min": 50000,
        "max_drawdown_max": 0.20,
        "trade_count_min": 50,
        "trade_count_max": 5000,
    }
    result = _try_evaluate_canonical_five_safe(
        trades=[],
        equity_curve=[],
        bars=bars,
        live_criteria=live_criteria,
        window_days=60,
        stage_label="C_cross_pair",
        genome_name="g_no_trade",
        enabled=True,
    )
    # no-trade / 不正 input → 内部 fallback で None
    assert result is None


def test_log_canonical_dual_path_emits_canonical_skipped_event_when_canonical_is_none(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`canonical=None` が helper に渡されたとき log entry が
    `canonical_skipped=True` を含む (= Round 5 [Suggestion 施策 6] 反映で
    test #26b 分離、 log emit single-責務)."""
    from src.alpha_factory.stage_gate import _log_canonical_dual_path
    _log_canonical_dual_path(
        stage_label="C_cross_pair",
        genome_name="g",
        legacy=_build_dummy_legacy_metrics(),
        canonical=None,
        pair_label="EUR_USD",
    )
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "stage_gate.canonical_five.dual_path" in combined
    assert "canonical_skipped" in combined
    assert "EUR_USD" in combined


def test_log_canonical_dual_path_rejects_fold_index_for_non_b_fold_stages() -> None:
    """`stage_label != "B_fold"` で `fold_index is not None` は ValueError
    (= acceptance D5、 Codex impl-review Round 1 [Warning stage_gate.py] 反映、
    識別子契約 SSOT を fold_index にも対称適用、 ログ名前空間汚染防止)."""
    from src.alpha_factory.stage_gate import _log_canonical_dual_path
    for stage in ("A", "B_IS", "C_base", "C_stress", "C_cross_pair"):
        with pytest.raises(ValueError, match="fold_index"):
            _log_canonical_dual_path(
                stage_label=stage,
                genome_name="g",
                legacy=_build_dummy_legacy_metrics(),
                canonical=None,
                fold_index=0,
                pair_label="EUR_USD" if stage == "C_cross_pair" else None,
            )
