from __future__ import annotations

from src.broker.orders import OrderSignal, PortfolioSnapshot
from src.domain.price import PriceBar
from src.events.calendar import EconomicCalendar
from src.strategy.base import Strategy


class EventAwareStrategy:
    """指定した経済イベントのブラックアウト期間中は新規エントリーをブロックする Strategy ラッパー。

    既存ポジションの決済（close_position / close_all）はブラックアウト中でも通す。
    """

    def __init__(
        self,
        inner: Strategy,
        calendar: EconomicCalendar,
        instrument: str,
        minutes_before: int = 15,
        minutes_after: int = 30,
        min_impact: int = 3,
    ) -> None:
        self._inner = inner
        self._calendar = calendar
        self._instrument = instrument
        self._before = minutes_before
        self._after = minutes_after
        self._min_impact = min_impact

    def warmup_bars(self) -> int:
        return self._inner.warmup_bars()

    def on_bar(self, bar: PriceBar, snapshot: PortfolioSnapshot) -> list[OrderSignal]:
        signals = self._inner.on_bar(bar, snapshot)
        if not signals:
            return signals
        if self._calendar.is_blackout(
            bar.bar_time,
            self._instrument,
            minutes_before=self._before,
            minutes_after=self._after,
            min_impact=self._min_impact,
        ):
            return [s for s in signals if s.kind not in ("open_long", "open_short")]
        return signals
