from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from src.broker.orders import OrderSignal, PortfolioSnapshot, Position
from src.domain.price import PriceBar
from src.events.calendar import EconomicCalendar, EconomicEvent
from src.strategy.event_aware import EventAwareStrategy
from tests._helpers import make_bar


def _empty_snap() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        cash=Decimal("1000000"), equity=Decimal("1000000"), margin_used=Decimal(0), margin_level_pct=None
    )


def _snap_with_long() -> PortfolioSnapshot:
    pos = Position(
        id=1,
        instrument="USD_JPY",
        side="long",
        units=10000,
        entry_price=Decimal("154.000"),
        entry_time=datetime(2026, 4, 1, tzinfo=UTC),
        entry_margin=Decimal("15400"),
        leverage=10,
    )
    return PortfolioSnapshot(
        cash=Decimal("1000000"),
        equity=Decimal("1000000"),
        margin_used=Decimal("15400"),
        margin_level_pct=Decimal("100"),
        positions=(pos,),
    )


class _AlwaysOpenLong:
    def warmup_bars(self) -> int:
        return 0

    def on_bar(self, bar: PriceBar, snapshot: PortfolioSnapshot) -> list[OrderSignal]:
        return [OrderSignal(kind="open_long", units=10000)]


class _AlwaysClose:
    def warmup_bars(self) -> int:
        return 0

    def on_bar(self, bar: PriceBar, snapshot: PortfolioSnapshot) -> list[OrderSignal]:
        return [OrderSignal(kind="close_all")]


def test_blocks_open_signals_during_blackout() -> None:
    event = EconomicEvent(
        event_time=datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC), currency="USD", name="FOMC", impact=3
    )
    wrapped = EventAwareStrategy(_AlwaysOpenLong(), EconomicCalendar([event]), instrument="USD_JPY")
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    assert wrapped.on_bar(bar, _empty_snap()) == []


def test_allows_close_signals_during_blackout() -> None:
    event = EconomicEvent(
        event_time=datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC), currency="JPY", name="BoJ", impact=3
    )
    wrapped = EventAwareStrategy(_AlwaysClose(), EconomicCalendar([event]), instrument="USD_JPY")
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    signals = wrapped.on_bar(bar, _snap_with_long())
    assert len(signals) == 1
    assert signals[0].kind == "close_all"


def test_passes_through_outside_blackout() -> None:
    event = EconomicEvent(
        event_time=datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC), currency="USD", name="FOMC", impact=3
    )
    wrapped = EventAwareStrategy(_AlwaysOpenLong(), EconomicCalendar([event]), instrument="USD_JPY")
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    signals = wrapped.on_bar(bar, _empty_snap())
    assert len(signals) == 1
    assert signals[0].kind == "open_long"
