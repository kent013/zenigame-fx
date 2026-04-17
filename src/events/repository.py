from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.db.models import EconomicEventRow
from src.events.calendar import EconomicEvent


def upsert_events(session: Session, events: list[EconomicEvent], source: str = "manual_csv") -> int:
    """(event_time, currency, name) で UPSERT。戻り値は対象件数。"""
    count = 0
    for event in events:
        values = {
            "event_time": event.event_time,
            "currency": event.currency,
            "name": event.name,
            "impact": event.impact,
            "forecast": event.forecast,
            "actual": event.actual,
            "source": source,
        }
        stmt = insert(EconomicEventRow).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["event_time", "currency", "name"],
            set_={k: v for k, v in values.items() if k not in ("event_time", "currency", "name")},
        )
        session.execute(stmt)
        count += 1
    session.commit()
    return count


def list_events_in_range(
    session: Session, start: datetime, end: datetime, currencies: list[str] | None = None, min_impact: int = 1
) -> list[EconomicEvent]:
    stmt = (
        select(EconomicEventRow)
        .where(EconomicEventRow.event_time >= start)
        .where(EconomicEventRow.event_time < end)
        .where(EconomicEventRow.impact >= min_impact)
    )
    if currencies:
        stmt = stmt.where(EconomicEventRow.currency.in_(currencies))
    rows = session.scalars(stmt.order_by(EconomicEventRow.event_time.asc())).all()
    return [
        EconomicEvent(
            event_time=r.event_time,
            currency=r.currency,
            name=r.name,
            impact=r.impact,
            forecast=r.forecast if r.forecast is None else Decimal(r.forecast),
            actual=r.actual if r.actual is None else Decimal(r.actual),
        )
        for r in rows
    ]
