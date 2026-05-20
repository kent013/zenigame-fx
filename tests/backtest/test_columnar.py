from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from src.backtest.columnar import (
    CASH_SCALE,
    PRICE_SCALE,
    SCALE_RATIO,
    ColumnarScaleError,
    bars_to_columnar,
    price_to_scaled,
    scaled_to_price,
)
from src.domain.price import Ohlc, PriceBar


def _bar(t: datetime, bid_c: str, ask_c: str) -> PriceBar:
    bid = Decimal(bid_c)
    ask = Decimal(ask_c)
    return PriceBar(
        pair_name="EUR_JPY",
        bar_time=t,
        bid=Ohlc(open=bid, high=bid, low=bid, close=bid),
        ask=Ohlc(open=ask, high=ask, low=ask, close=ask),
        volume=1,
        complete=True,
    )


def test_scale_ratio_is_cash_over_price() -> None:
    assert SCALE_RATIO == CASH_SCALE // PRICE_SCALE
    assert SCALE_RATIO == 1000


def test_price_scaled_roundtrip_is_lossless() -> None:
    for s in ("162.345", "162.34500", "0.00001", "300.99999"):
        d = Decimal(s)
        assert scaled_to_price(price_to_scaled(d)) == d


def test_price_scaled_fail_closed_on_excess_precision() -> None:
    # 6 桁小数は PRICE_SCALE=1e5 で lossless 化できない。
    with pytest.raises(ColumnarScaleError):
        price_to_scaled(Decimal("1.000001"))


def test_bars_to_columnar_roundtrip_matches_source() -> None:
    base = datetime(2025, 1, 6, 0, 0, tzinfo=UTC)
    bars = [
        _bar(base + timedelta(minutes=i), f"162.{300 + i:03d}", f"162.{305 + i:03d}")
        for i in range(5)
    ]
    col = bars_to_columnar(bars)
    assert len(col) == 5
    for i, bar in enumerate(bars):
        assert scaled_to_price(int(col.bid_c[i])) == bar.bid.close
        assert scaled_to_price(int(col.ask_c[i])) == bar.ask.close
        assert scaled_to_price(int(col.bid_o[i])) == bar.bid.open
        assert scaled_to_price(int(col.ask_o[i])) == bar.ask.open
        assert int(col.hour[i]) == bar.bar_time.hour


def test_bars_to_columnar_is_eod_on_date_change_and_last() -> None:
    d1 = datetime(2025, 1, 6, 23, 58, tzinfo=UTC)
    bars = [
        _bar(d1, "162.300", "162.305"),
        _bar(d1 + timedelta(minutes=1), "162.301", "162.306"),  # 23:59 同日
        _bar(d1 + timedelta(minutes=2), "162.302", "162.307"),  # 翌日 00:00 -> 前 bar が EOD
        _bar(d1 + timedelta(minutes=3), "162.303", "162.308"),  # 翌日 00:01 (末尾)
    ]
    col = bars_to_columnar(bars)
    # bar1 (23:59) は次が翌日 -> is_eod True、bar0 は同日 -> False、末尾は常に True
    assert list(col.is_eod) == [False, True, False, True]


def test_bars_to_columnar_arrays_are_read_only() -> None:
    base = datetime(2025, 1, 6, 0, 0, tzinfo=UTC)
    bars = [_bar(base + timedelta(minutes=i), "162.300", "162.305") for i in range(3)]
    col = bars_to_columnar(bars)
    with pytest.raises(ValueError):
        col.bid_c[0] = 0
    assert col.epoch_ns.dtype == np.int64
