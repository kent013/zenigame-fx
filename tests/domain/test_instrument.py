from __future__ import annotations

from decimal import Decimal

from src.domain.instrument import CurrencyPair


def test_from_oanda_name_splits_base_and_quote() -> None:
    pair = CurrencyPair.from_oanda_name(
        "USD_JPY",
        pip_location=-2,
        display_precision=3,
        trade_units_precision=0,
        margin_rate=Decimal("0.04"),
        minimum_trade_size=1,
        maximum_order_units=100_000_000,
    )
    assert pair.base_currency == "USD"
    assert pair.quote_currency == "JPY"
    assert pair.display_name == "USD/JPY"


def test_pip_size_uses_pip_location() -> None:
    pair = CurrencyPair.from_oanda_name(
        "EUR_USD",
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        margin_rate=Decimal("0.02"),
        minimum_trade_size=1,
        maximum_order_units=100_000_000,
    )
    assert pair.pip_size == Decimal("0.0001")
