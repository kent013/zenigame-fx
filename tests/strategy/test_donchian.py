from __future__ import annotations

from decimal import Decimal

from src.broker.orders import PortfolioSnapshot
from src.strategy.donchian import DonchianBreakoutStrategy
from tests._helpers import make_bar


def _empty_snap() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        cash=Decimal("1000000"), equity=Decimal("1000000"), margin_used=Decimal(0), margin_level_pct=None
    )


def test_donchian_warmup_returns_no_signals() -> None:
    strat = DonchianBreakoutStrategy(window=5, units=10000)
    for i in range(4):
        bar = make_bar(i, bid_close="154.000", ask_close="154.010")
        assert strat.on_bar(bar, _empty_snap()) == []


def test_open_long_on_upside_breakout() -> None:
    strat = DonchianBreakoutStrategy(window=3, units=10000)
    # 3 本のレンジ（154.00〜154.01）を作る
    for i in range(3):
        strat.on_bar(make_bar(i, bid_close="154.000", ask_close="154.010"), _empty_snap())
    # 4 本目で大きく上抜け
    signals = strat.on_bar(make_bar(3, bid_close="155.000", ask_close="155.010"), _empty_snap())
    assert len(signals) == 1
    assert signals[0].kind == "open_long"
