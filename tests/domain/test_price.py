from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from src.domain.price import Ohlc, PriceBar


def test_spread_close_computed_from_bid_ask() -> None:
    bar = PriceBar(
        pair_name="USD_JPY",
        bar_time=datetime(2026, 4, 17, tzinfo=UTC),
        bid=Ohlc(Decimal("154.120"), Decimal("154.135"), Decimal("154.110"), Decimal("154.125")),
        ask=Ohlc(Decimal("154.130"), Decimal("154.145"), Decimal("154.120"), Decimal("154.135")),
        volume=42,
        complete=True,
    )
    assert bar.spread_close == Decimal("0.010")
