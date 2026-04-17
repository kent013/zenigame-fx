from __future__ import annotations

from collections import deque
from decimal import Decimal
from statistics import mean

from src.broker.orders import OrderSignal, PortfolioSnapshot
from src.domain.price import PriceBar
from src.strategy.registry import register


@register("ma_crossover")
class MovingAverageCrossoverStrategy:
    """高速/低速 SMA クロスオーバー順張り戦略。

    fast > slow の状態になれば long、fast < slow になれば short。反対方向に転じたら既存ポジションを決済。
    保有ポジションは同時に 1 本のみ。
    """

    def __init__(self, fast_window: int = 5, slow_window: int = 20, units: int = 10000) -> None:
        if fast_window < 2 or slow_window < 2:
            raise ValueError("windows must be >= 2")
        if fast_window >= slow_window:
            raise ValueError("fast_window must be < slow_window")
        self._fast_window = fast_window
        self._slow_window = slow_window
        self._units = units
        self._slow_buf: deque[Decimal] = deque(maxlen=slow_window)
        self._prev_signal: int = 0  # +1=fast>slow, -1=fast<slow, 0=初期

    def warmup_bars(self) -> int:
        return self._slow_window

    def on_bar(self, bar: PriceBar, snapshot: PortfolioSnapshot) -> list[OrderSignal]:
        mid = (bar.bid.close + bar.ask.close) / Decimal(2)
        self._slow_buf.append(mid)
        if len(self._slow_buf) < self._slow_window:
            return []

        slow = Decimal(str(mean(float(v) for v in self._slow_buf)))
        fast = Decimal(str(mean(float(v) for v in list(self._slow_buf)[-self._fast_window :])))
        cur_signal = 1 if fast > slow else (-1 if fast < slow else 0)

        orders: list[OrderSignal] = []
        # クロスが確定したタイミングで既存ポジションを決済 → 反対方向へ新規
        if cur_signal != self._prev_signal and self._prev_signal != 0:
            if snapshot.positions:
                orders.append(OrderSignal(kind="close_all"))
            if cur_signal == 1:
                orders.append(OrderSignal(kind="open_long", units=self._units))
            elif cur_signal == -1:
                orders.append(OrderSignal(kind="open_short", units=self._units))
        elif self._prev_signal == 0 and not snapshot.positions:
            # 初回シグナル確定時もエントリー
            if cur_signal == 1:
                orders.append(OrderSignal(kind="open_long", units=self._units))
            elif cur_signal == -1:
                orders.append(OrderSignal(kind="open_short", units=self._units))

        self._prev_signal = cur_signal
        return orders
