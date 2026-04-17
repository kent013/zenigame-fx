from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Ohlc:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


@dataclass(frozen=True)
class PriceBar:
    pair_name: str
    bar_time: datetime
    bid: Ohlc
    ask: Ohlc
    volume: int
    complete: bool

    @property
    def spread_close(self) -> Decimal:
        return self.ask.close - self.bid.close
