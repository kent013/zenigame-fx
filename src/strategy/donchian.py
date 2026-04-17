from __future__ import annotations

from collections import deque
from decimal import Decimal

from src.broker.orders import OrderSignal, PortfolioSnapshot
from src.domain.price import PriceBar
from src.strategy.registry import register


@register("donchian")
class DonchianBreakoutStrategy:
    """N 期間の最高値 / 最安値を超えた方向に順張りでエントリーする。

    ロング中に最安値割れで反転ショート、ショート中に最高値抜けで反転ロング。
    """

    def __init__(self, window: int = 20, units: int = 10000) -> None:
        if window < 2:
            raise ValueError("window must be >= 2")
        self._window = window
        self._units = units
        # ブレイク判定は前 N 期間の値を使う。現バーは判定後に buffer に追加する
        self._highs: deque[Decimal] = deque(maxlen=window)
        self._lows: deque[Decimal] = deque(maxlen=window)

    def warmup_bars(self) -> int:
        return self._window + 1

    def on_bar(self, bar: PriceBar, snapshot: PortfolioSnapshot) -> list[OrderSignal]:
        highest = max(self._highs) if len(self._highs) == self._window else None
        lowest = min(self._lows) if len(self._lows) == self._window else None

        orders: list[OrderSignal] = []
        mid_close = (bar.bid.close + bar.ask.close) / Decimal(2)

        if highest is not None and lowest is not None:
            break_up = mid_close > highest
            break_down = mid_close < lowest

            if snapshot.positions:
                pos = snapshot.positions[0]
                if pos.side == "long" and break_down:
                    orders.append(OrderSignal(kind="close_all"))
                    orders.append(OrderSignal(kind="open_short", units=self._units))
                elif pos.side == "short" and break_up:
                    orders.append(OrderSignal(kind="close_all"))
                    orders.append(OrderSignal(kind="open_long", units=self._units))
            else:
                if break_up:
                    orders.append(OrderSignal(kind="open_long", units=self._units))
                elif break_down:
                    orders.append(OrderSignal(kind="open_short", units=self._units))

        # 判定後にバッファ更新
        self._highs.append((bar.bid.high + bar.ask.high) / Decimal(2))
        self._lows.append((bar.bid.low + bar.ask.low) / Decimal(2))
        return orders
