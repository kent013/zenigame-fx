from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class EconomicEvent:
    event_time: datetime
    currency: str
    name: str
    impact: int  # 1=Low, 2=Medium, 3=High
    forecast: Decimal | None = None
    actual: Decimal | None = None


class EconomicCalendar:
    """手元にあるイベント一覧を保持し、指定時刻 / 通貨に対するブラックアウト判定を提供する。"""

    def __init__(self, events: list[EconomicEvent]) -> None:
        self._events = sorted(events, key=lambda e: e.event_time)

    @property
    def events(self) -> list[EconomicEvent]:
        return list(self._events)

    @staticmethod
    def instrument_currencies(instrument: str) -> tuple[str, str]:
        base, quote = instrument.split("_", 1)
        return base, quote

    def is_blackout(
        self,
        ts: datetime,
        instrument: str,
        minutes_before: int = 15,
        minutes_after: int = 30,
        min_impact: int = 3,
    ) -> bool:
        base, quote = self.instrument_currencies(instrument)
        before = timedelta(minutes=minutes_before)
        after = timedelta(minutes=minutes_after)
        for event in self._events:
            if event.impact < min_impact:
                continue
            if event.currency not in (base, quote):
                continue
            if event.event_time - before <= ts <= event.event_time + after:
                return True
        return False

    def events_for_instrument(self, instrument: str, min_impact: int = 1) -> list[EconomicEvent]:
        base, quote = self.instrument_currencies(instrument)
        return [e for e in self._events if e.currency in (base, quote) and e.impact >= min_impact]
