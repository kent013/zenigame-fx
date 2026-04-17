from __future__ import annotations

from typing import Protocol

from src.broker.orders import OrderSignal, PortfolioSnapshot
from src.domain.price import PriceBar


class Strategy(Protocol):
    def warmup_bars(self) -> int: ...

    def on_bar(self, bar: PriceBar, snapshot: PortfolioSnapshot) -> list[OrderSignal]: ...
