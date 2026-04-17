from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from src.events.calendar import EconomicEvent
from src.utils.time import to_utc


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    token = value.strip()
    if not token:
        return None
    return Decimal(token)


def load_events_from_csv(path: Path) -> list[EconomicEvent]:
    events: list[EconomicEvent] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"event_time", "currency", "name", "impact"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing columns: {sorted(missing)}")
        for row in reader:
            from datetime import datetime

            ts = to_utc(datetime.fromisoformat(row["event_time"].replace("Z", "+00:00")))
            events.append(
                EconomicEvent(
                    event_time=ts,
                    currency=row["currency"].strip().upper(),
                    name=row["name"].strip(),
                    impact=int(row["impact"]),
                    forecast=_parse_decimal(row.get("forecast")),
                    actual=_parse_decimal(row.get("actual")),
                )
            )
    return events
