from __future__ import annotations

from collections import deque
from decimal import Decimal

from src.broker.orders import OrderSignal, PortfolioSnapshot
from src.domain.price import PriceBar
from src.strategy.registry import register


@register("rsi")
class RsiMeanReversionStrategy:
    """Wilder 平滑化の RSI を使った逆張り戦略。

    RSI < oversold でロング、RSI > overbought でショート。RSI が中央値を越えたら決済。
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        exit_level: float = 50.0,
        units: int = 10000,
    ) -> None:
        if period < 2:
            raise ValueError("period must be >= 2")
        self._period = period
        self._oversold = Decimal(str(oversold))
        self._overbought = Decimal(str(overbought))
        self._exit_level = Decimal(str(exit_level))
        self._units = units
        self._last_close: Decimal | None = None
        self._avg_gain: Decimal | None = None
        self._avg_loss: Decimal | None = None
        self._init_buf: deque[tuple[Decimal, Decimal]] = deque(maxlen=period)

    def warmup_bars(self) -> int:
        return self._period + 1

    def _update_rsi(self, mid: Decimal) -> Decimal | None:
        if self._last_close is None:
            self._last_close = mid
            return None
        change = mid - self._last_close
        gain = change if change > 0 else Decimal(0)
        loss = -change if change < 0 else Decimal(0)
        self._last_close = mid

        if self._avg_gain is None:
            self._init_buf.append((gain, loss))
            if len(self._init_buf) < self._period:
                return None
            total_gain = sum((g for g, _ in self._init_buf), Decimal(0))
            total_loss = sum((l_ for _, l_ in self._init_buf), Decimal(0))
            self._avg_gain = total_gain / Decimal(self._period)
            self._avg_loss = total_loss / Decimal(self._period)
        else:
            p = Decimal(self._period)
            self._avg_gain = (self._avg_gain * (p - 1) + gain) / p
            self._avg_loss = (self._avg_loss * (p - 1) + loss) / p  # type: ignore[operator]

        if self._avg_loss == 0:
            return Decimal(100)
        rs = self._avg_gain / self._avg_loss
        return Decimal(100) - Decimal(100) / (Decimal(1) + rs)

    def on_bar(self, bar: PriceBar, snapshot: PortfolioSnapshot) -> list[OrderSignal]:
        mid = (bar.bid.close + bar.ask.close) / Decimal(2)
        rsi = self._update_rsi(mid)
        if rsi is None:
            return []

        if snapshot.positions:
            pos = snapshot.positions[0]
            if pos.side == "long" and rsi >= self._exit_level:
                return [OrderSignal(kind="close_position", position_id=pos.id)]
            if pos.side == "short" and rsi <= self._exit_level:
                return [OrderSignal(kind="close_position", position_id=pos.id)]
            return []

        if rsi < self._oversold:
            return [OrderSignal(kind="open_long", units=self._units)]
        if rsi > self._overbought:
            return [OrderSignal(kind="open_short", units=self._units)]
        return []
