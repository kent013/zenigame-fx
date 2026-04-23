"""テスト用の軽量 PriceBar / InstrumentMeta ビルダー。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.broker import InstrumentMeta
from src.domain.price import Ohlc, PriceBar


def usd_jpy_meta(margin_rate: str = "0.04") -> InstrumentMeta:
    return InstrumentMeta(
        oanda_name="USD_JPY",
        base_currency="USD",
        quote_currency="JPY",
        margin_rate=Decimal(margin_rate),
        pip_size=Decimal("0.01"),
        display_precision=3,
    )


def eur_jpy_meta(margin_rate: str = "0.04") -> InstrumentMeta:
    return InstrumentMeta(
        oanda_name="EUR_JPY",
        base_currency="EUR",
        quote_currency="JPY",
        margin_rate=Decimal(margin_rate),
        pip_size=Decimal("0.01"),
        display_precision=3,
    )


def eur_usd_meta(margin_rate: str = "0.03") -> InstrumentMeta:
    return InstrumentMeta(
        oanda_name="EUR_USD",
        base_currency="EUR",
        quote_currency="USD",
        margin_rate=Decimal(margin_rate),
        pip_size=Decimal("0.0001"),
        display_precision=5,
    )


def usd_cad_meta(margin_rate: str = "0.04") -> InstrumentMeta:
    return InstrumentMeta(
        oanda_name="USD_CAD",
        base_currency="USD",
        quote_currency="CAD",
        margin_rate=Decimal(margin_rate),
        pip_size=Decimal("0.0001"),
        display_precision=5,
    )


def make_bar(
    minute: int,
    bid_close: str,
    ask_close: str,
    *,
    day: int = 1,
    pair_name: str = "USD_JPY",
    bid_open: str | None = None,
    ask_open: str | None = None,
) -> PriceBar:
    bid_open_d = Decimal(bid_open or bid_close)
    ask_open_d = Decimal(ask_open or ask_close)
    bid_close_d = Decimal(bid_close)
    ask_close_d = Decimal(ask_close)
    return PriceBar(
        pair_name=pair_name,
        bar_time=datetime(2026, 4, day, 0, 0, 0, tzinfo=UTC) + timedelta(minutes=minute),
        bid=Ohlc(
            open=bid_open_d, high=max(bid_open_d, bid_close_d), low=min(bid_open_d, bid_close_d), close=bid_close_d
        ),
        ask=Ohlc(
            open=ask_open_d, high=max(ask_open_d, ask_close_d), low=min(ask_open_d, ask_close_d), close=ask_close_d
        ),
        volume=10,
        complete=True,
    )
