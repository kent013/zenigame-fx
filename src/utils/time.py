from __future__ import annotations

from datetime import UTC, datetime, timedelta

_GRANULARITY_SECONDS: dict[str, int] = {
    "S5": 5,
    "S10": 10,
    "S15": 15,
    "S30": 30,
    "M1": 60,
    "M2": 120,
    "M4": 240,
    "M5": 300,
    "M10": 600,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H2": 7200,
    "H3": 10800,
    "H4": 14400,
    "H6": 21600,
    "H8": 28800,
    "H12": 43200,
    "D": 86400,
    "W": 604800,
}


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime is not allowed; pass tz-aware datetime")
    return dt.astimezone(UTC)


def rfc3339_utc(dt: datetime) -> str:
    """OANDA 互換の RFC3339（UTC、秒精度）表現。末尾は必ず `Z`。"""
    dt_utc = to_utc(dt).replace(microsecond=0)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def granularity_delta(granularity: str) -> timedelta:
    try:
        return timedelta(seconds=_GRANULARITY_SECONDS[granularity])
    except KeyError as e:
        raise ValueError(f"unsupported granularity: {granularity}") from e
