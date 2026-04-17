from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.events.calendar import EconomicCalendar, EconomicEvent


def _ev(ccy: str, minute: int, impact: int = 3, name: str = "Test") -> EconomicEvent:
    return EconomicEvent(
        event_time=datetime(2026, 4, 1, 12, minute, 0, tzinfo=UTC),
        currency=ccy,
        name=name,
        impact=impact,
    )


def test_blackout_triggers_around_event_for_base_currency() -> None:
    cal = EconomicCalendar([_ev("USD", 30)])
    # 12:30 のイベント、15 分前〜30 分後
    assert cal.is_blackout(datetime(2026, 4, 1, 12, 15, 0, tzinfo=UTC), "USD_JPY", 15, 30, 3) is True
    assert cal.is_blackout(datetime(2026, 4, 1, 12, 45, 0, tzinfo=UTC), "USD_JPY", 15, 30, 3) is True
    # 13:01 は 30 分後の境界（13:00）を超えるので blackout 外
    assert cal.is_blackout(datetime(2026, 4, 1, 13, 1, 0, tzinfo=UTC), "USD_JPY", 15, 30, 3) is False
    # 12:14 は 15 分前の境界（12:15）を超えるので blackout 外
    assert cal.is_blackout(datetime(2026, 4, 1, 12, 14, 0, tzinfo=UTC), "USD_JPY", 15, 30, 3) is False


def test_blackout_ignores_unrelated_currency() -> None:
    cal = EconomicCalendar([_ev("CAD", 30)])
    assert cal.is_blackout(datetime(2026, 4, 1, 12, 30, 0, tzinfo=UTC), "USD_JPY", 15, 30, 3) is False


def test_blackout_respects_min_impact() -> None:
    cal = EconomicCalendar([_ev("USD", 30, impact=2)])
    assert cal.is_blackout(datetime(2026, 4, 1, 12, 30, 0, tzinfo=UTC), "USD_JPY", 15, 30, 3) is False
    assert cal.is_blackout(datetime(2026, 4, 1, 12, 30, 0, tzinfo=UTC), "USD_JPY", 15, 30, 2) is True


def test_events_for_instrument_includes_both_sides() -> None:
    cal = EconomicCalendar([_ev("USD", 0), _ev("JPY", 0), _ev("EUR", 0)])
    filtered = cal.events_for_instrument("USD_JPY")
    assert len(filtered) == 2
    currencies = {e.currency for e in filtered}
    assert currencies == {"USD", "JPY"}


def test_blackout_includes_exact_boundaries() -> None:
    cal = EconomicCalendar([_ev("JPY", 30)])
    center = datetime(2026, 4, 1, 12, 30, 0, tzinfo=UTC)
    assert cal.is_blackout(center - timedelta(minutes=15), "USD_JPY", 15, 30, 3) is True
    assert cal.is_blackout(center + timedelta(minutes=30), "USD_JPY", 15, 30, 3) is True
    assert cal.is_blackout(center + timedelta(minutes=31), "USD_JPY", 15, 30, 3) is False
