from __future__ import annotations

from decimal import Decimal

from src.broker.orders import PortfolioSnapshot
from src.strategy.ma_crossover import MovingAverageCrossoverStrategy
from tests._helpers import make_bar


def _empty_snap() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        cash=Decimal("1000000"), equity=Decimal("1000000"), margin_used=Decimal(0), margin_level_pct=None
    )


def test_warmup_requires_slow_window_bars() -> None:
    strat = MovingAverageCrossoverStrategy(fast_window=2, slow_window=5, units=10000)
    for i in range(4):
        bar = make_bar(i, bid_close="154.000", ask_close="154.010")
        assert strat.on_bar(bar, _empty_snap()) == []


def test_open_long_when_fast_crosses_above_slow() -> None:
    strat = MovingAverageCrossoverStrategy(fast_window=2, slow_window=3, units=5000)
    # 3 本の下落（fast < slow）で初期 signal=-1 (short) を確定
    for i, price in enumerate(["155.000", "154.500", "154.000"]):
        strat.on_bar(make_bar(i, bid_close=price, ask_close=price), _empty_snap())
    # 4 本目の高値で fast > slow に転じる → close_all + open_long の組
    signals = strat.on_bar(make_bar(3, bid_close="156.000", ask_close="156.010"), _empty_snap())
    kinds = [s.kind for s in signals]
    assert "open_long" in kinds
