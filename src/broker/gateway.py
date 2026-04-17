from __future__ import annotations

from typing import Protocol

from src.broker.orders import OrderSignal, PortfolioSnapshot, Trade
from src.domain.price import PriceBar


class BrokerError(Exception):
    pass


class LeverageExceededError(BrokerError):
    pass


class InsufficientMarginError(BrokerError):
    pass


class BrokerGateway(Protocol):
    """MockBroker と将来の OandaBroker / TachibanaBroker が共通に実装する抽象。"""

    def submit(self, signal: OrderSignal, leverage: int) -> None: ...

    def fill_pending(self, bar: PriceBar) -> list[Trade]:
        """`bar.open` で保留中の注文を約定させる。決済注文が含まれる場合は Trade を返す。"""
        ...

    def mark_to_market(self, bar: PriceBar) -> None:
        """最新バーの close で equity を更新。"""
        ...

    def force_close_if_margin_call(self, bar: PriceBar) -> list[Trade]: ...

    def close_all(self, bar: PriceBar, reason: str) -> list[Trade]: ...

    def snapshot(self) -> PortfolioSnapshot: ...
