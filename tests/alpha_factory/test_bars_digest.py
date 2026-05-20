"""Tests for ``src/alpha_factory/bars_digest.py`` (T106)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from src.alpha_factory.bars_digest import bars_digest
from src.domain.price import Ohlc, PriceBar


def _bar(
    *,
    pair_name: str = "EUR_JPY",
    bar_time: datetime | None = None,
    bid: str = "154.000",
    ask: str = "154.005",
    volume: int = 10,
    complete: bool = True,
) -> PriceBar:
    bt = bar_time or datetime(2026, 1, 1, tzinfo=UTC)
    return PriceBar(
        pair_name=pair_name,
        bar_time=bt,
        bid=Ohlc(
            open=Decimal(bid),
            high=Decimal(bid),
            low=Decimal(bid),
            close=Decimal(bid),
        ),
        ask=Ohlc(
            open=Decimal(ask),
            high=Decimal(ask),
            low=Decimal(ask),
            close=Decimal(ask),
        ),
        volume=volume,
        complete=complete,
    )


def test_bars_digest_identical_inputs_match() -> None:
    bars_a = [_bar(), _bar(bar_time=datetime(2026, 1, 1, 0, 1, tzinfo=UTC))]
    bars_b = [_bar(), _bar(bar_time=datetime(2026, 1, 1, 0, 1, tzinfo=UTC))]
    assert bars_digest(bars_a) == bars_digest(bars_b)


def test_bars_digest_order_sensitive() -> None:
    b0 = _bar(bar_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC))
    b1 = _bar(bar_time=datetime(2026, 1, 1, 0, 1, tzinfo=UTC))
    assert bars_digest([b0, b1]) != bars_digest([b1, b0])


def test_bars_digest_decimal_preserves_precision() -> None:
    """trailing zero 差 (1.234560 vs 1.23456) を検出できる."""
    a = _bar(bid="1.234560")
    b = _bar(bid="1.23456")
    assert bars_digest([a]) != bars_digest([b])


def test_bars_digest_complete_field_distinguishes() -> None:
    a = _bar(complete=True)
    b = _bar(complete=False)
    assert bars_digest([a]) != bars_digest([b])


def test_bars_digest_pair_name_distinguishes() -> None:
    a = _bar(pair_name="EUR_JPY")
    b = _bar(pair_name="USD_JPY")
    assert bars_digest([a]) != bars_digest([b])


def test_bars_digest_naive_datetime_treated_as_utc() -> None:
    naive = _bar(bar_time=datetime(2026, 1, 1, 0, 0))  # tz-naive
    aware = _bar(bar_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC))
    assert bars_digest([naive]) == bars_digest([aware])


def test_bars_digest_empty_is_stable() -> None:
    assert bars_digest([]) == bars_digest([])
