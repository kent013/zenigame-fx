from __future__ import annotations

from decimal import Decimal

from src.broker.orders import PortfolioSnapshot
from src.strategy.rsi import RsiMeanReversionStrategy
from tests._helpers import make_bar


def _empty_snap() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        cash=Decimal("1000000"), equity=Decimal("1000000"), margin_used=Decimal(0), margin_level_pct=None
    )


def test_rsi_warmup_yields_no_signals() -> None:
    strat = RsiMeanReversionStrategy(period=14)
    for i in range(10):
        bar = make_bar(i, bid_close="154.000", ask_close="154.010")
        assert strat.on_bar(bar, _empty_snap()) == []


def test_rsi_signals_long_after_sharp_decline() -> None:
    strat = RsiMeanReversionStrategy(period=5, oversold=30, overbought=70, units=10000)
    prices = ["155.000", "154.800", "154.600", "154.400", "154.200", "154.000", "153.800"]
    signals_seen: list = []
    for i, p in enumerate(prices):
        signals_seen.append(strat.on_bar(make_bar(i, bid_close=p, ask_close=p), _empty_snap()))
    # 連続下落で RSI が低下 → どこかで open_long が出るはず
    all_kinds = [s.kind for batch in signals_seen for s in batch]
    assert "open_long" in all_kinds
