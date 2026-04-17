from __future__ import annotations

from collections import deque
from decimal import Decimal
from statistics import mean, pstdev

from src.broker.orders import OrderSignal, PortfolioSnapshot
from src.domain.price import PriceBar
from src.strategy.registry import register


@register("bollinger")
class BollingerMeanReversionStrategy:
    """close が ±k*stddev のバンドを突き抜けたら逆張り、SMA タッチで決済。

    参考価格は mid close（bid.close と ask.close の平均）。1 ポジションのみ保有する。
    """

    def __init__(self, window: int = 20, k: float = 2.0, units: int = 10000, exit_on_sma_touch: bool = True) -> None:
        if window < 2:
            raise ValueError("window must be >= 2")
        self._window = window
        self._k = Decimal(str(k))
        self._units = units
        self._exit_on_sma_touch = exit_on_sma_touch
        self._mid_closes: deque[Decimal] = deque(maxlen=window)

    def warmup_bars(self) -> int:
        return self._window

    def on_bar(self, bar: PriceBar, snapshot: PortfolioSnapshot) -> list[OrderSignal]:
        mid_close = (bar.bid.close + bar.ask.close) / Decimal(2)
        self._mid_closes.append(mid_close)
        if len(self._mid_closes) < self._window:
            return []

        sma = Decimal(str(mean(float(v) for v in self._mid_closes)))
        sigma = Decimal(str(pstdev(float(v) for v in self._mid_closes)))
        upper = sma + self._k * sigma
        lower = sma - self._k * sigma

        # 既存ポジションがあれば決済判定を優先
        if snapshot.positions:
            pos = snapshot.positions[0]
            if self._exit_on_sma_touch:
                if pos.side == "long" and mid_close >= sma:
                    return [OrderSignal(kind="close_position", position_id=pos.id)]
                if pos.side == "short" and mid_close <= sma:
                    return [OrderSignal(kind="close_position", position_id=pos.id)]
            return []

        if mid_close < lower:
            return [OrderSignal(kind="open_long", units=self._units)]
        if mid_close > upper:
            return [OrderSignal(kind="open_short", units=self._units)]
        return []
