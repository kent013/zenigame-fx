from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from src.backtest.ensemble import EnsembleConfig, EnsembleSpec, _pearson, _resolve_weights, run_ensemble
from tests._helpers import make_bar, usd_jpy_meta


def test_resolve_weights_equal_when_none() -> None:
    specs = [EnsembleSpec(name=f"s{i}", strategy="bollinger", params={}) for i in range(4)]
    weights = _resolve_weights(specs, None)
    assert len(weights) == 4
    assert sum(weights) == Decimal(1)


def test_resolve_weights_normalizes_custom() -> None:
    specs = [EnsembleSpec(name=f"s{i}", strategy="bollinger", params={}) for i in range(3)]
    weights = _resolve_weights(specs, [Decimal(1), Decimal(2), Decimal(1)])
    assert weights == [Decimal(1) / Decimal(4), Decimal(2) / Decimal(4), Decimal(1) / Decimal(4)]


def test_pearson_identity_returns_one() -> None:
    a = [0.1, 0.2, -0.1, 0.05, -0.05]
    corr = _pearson(a, a)
    assert corr is not None
    assert abs(corr - 1.0) < 1e-9


def test_pearson_returns_none_on_constant_series() -> None:
    a = [0.0, 0.0, 0.0, 0.0]
    b = [0.1, 0.2, 0.1, 0.2]
    assert _pearson(a, b) is None


def test_run_ensemble_produces_per_strategy_and_combined() -> None:
    bars = [
        make_bar(0, bid_close="154.100", ask_close="154.110"),
        make_bar(1, bid_close="154.200", ask_close="154.210", bid_open="154.150", ask_open="154.160"),
        make_bar(2, bid_close="154.300", ask_close="154.310"),
    ]
    specs = [
        EnsembleSpec(name="boll_narrow", strategy="bollinger", params={"window": 2, "k": 0.5, "units": 1000}),
        EnsembleSpec(name="boll_wide", strategy="bollinger", params={"window": 2, "k": 3.0, "units": 1000}),
    ]
    config = EnsembleConfig(
        instrument="USD_JPY",
        start=bars[0].bar_time,
        end=datetime(2026, 4, 2, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        specs=specs,
    )
    result = run_ensemble(bars, usd_jpy_meta(), config)

    assert len(result.per_strategy) == 2
    assert result.per_strategy[0].capital_allocated == Decimal("500000")
    assert len(result.combined_equity) == len(bars)
    assert result.combined_metrics is not None
    # 2 戦略の equity 合算が総資金 + 合算 PnL に一致
    per_equity_sum = sum(r.equity_curve[-1][1] for r in result.per_strategy)
    assert result.combined_equity[-1][1] == per_equity_sum
    # 相関行列は 1 ペアのみ
    assert len(result.correlation) == 1
