from __future__ import annotations

from decimal import Decimal

from src.broker.orders import PortfolioSnapshot, Position
from src.strategy.bollinger import BollingerMeanReversionStrategy
from tests._helpers import make_bar


def _empty_snapshot() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        cash=Decimal("1000000"), equity=Decimal("1000000"), margin_used=Decimal(0), margin_level_pct=None
    )


def test_no_signal_during_warmup() -> None:
    strat = BollingerMeanReversionStrategy(window=5, k=2.0, units=10000)
    for i in range(4):
        bar = make_bar(i, bid_close="154.000", ask_close="154.010")
        assert strat.on_bar(bar, _empty_snapshot()) == []


def test_open_long_when_close_below_lower_band() -> None:
    strat = BollingerMeanReversionStrategy(window=5, k=1.0, units=10000)
    # 154.000 を 4 本、5 本目で大きく下落
    for i in range(4):
        strat.on_bar(make_bar(i, bid_close="154.000", ask_close="154.010"), _empty_snapshot())
    signals = strat.on_bar(make_bar(4, bid_close="153.500", ask_close="153.510"), _empty_snapshot())
    assert len(signals) == 1
    assert signals[0].kind == "open_long"
    assert signals[0].units == 10000


def test_open_short_when_close_above_upper_band() -> None:
    strat = BollingerMeanReversionStrategy(window=5, k=1.0, units=5000)
    for i in range(4):
        strat.on_bar(make_bar(i, bid_close="154.000", ask_close="154.010"), _empty_snapshot())
    signals = strat.on_bar(make_bar(4, bid_close="154.500", ask_close="154.510"), _empty_snapshot())
    assert len(signals) == 1
    assert signals[0].kind == "open_short"


def test_close_long_on_sma_touch() -> None:
    strat = BollingerMeanReversionStrategy(window=5, k=1.0, units=10000)
    for i in range(4):
        strat.on_bar(make_bar(i, bid_close="154.000", ask_close="154.010"), _empty_snapshot())
    # ポジションあり想定の snapshot
    pos = Position(
        id=1,
        instrument="USD_JPY",
        side="long",
        units=10000,
        entry_price=Decimal("153.510"),
        entry_time=make_bar(4, bid_close="0", ask_close="0").bar_time,
        entry_margin=Decimal("153510"),
        leverage=10,
    )
    snap = PortfolioSnapshot(
        cash=Decimal("1000000"),
        equity=Decimal("1000000"),
        margin_used=Decimal("153510"),
        margin_level_pct=Decimal("100"),
        positions=(pos,),
    )
    # SMA 付近へ価格復帰
    signals = strat.on_bar(make_bar(4, bid_close="154.000", ask_close="154.010"), snap)
    assert len(signals) == 1
    assert signals[0].kind == "close_position"
    assert signals[0].position_id == 1
