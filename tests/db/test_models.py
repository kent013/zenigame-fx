from __future__ import annotations

from src.db.models import CurrencyPair, PriceBarM1


def test_currency_pair_tablename() -> None:
    assert CurrencyPair.__tablename__ == "currency_pair"


def test_price_bar_m1_has_bid_ask_ohlc_columns() -> None:
    columns = set(PriceBarM1.__table__.columns.keys())
    for name in ("open_bid", "high_bid", "low_bid", "close_bid", "open_ask", "high_ask", "low_ask", "close_ask"):
        assert name in columns


def test_price_bar_m1_unique_constraint() -> None:
    constraint_names = {c.name for c in PriceBarM1.__table__.constraints}
    assert "uq_price_bar_m1_pair_time" in constraint_names
