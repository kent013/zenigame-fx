from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.utils.time import granularity_delta, now_utc, rfc3339_utc, to_utc


def test_rfc3339_utc_formats_with_trailing_z() -> None:
    dt = datetime(2026, 4, 17, 12, 34, 56, tzinfo=UTC)
    assert rfc3339_utc(dt) == "2026-04-17T12:34:56Z"


def test_rfc3339_utc_converts_jst_to_utc() -> None:
    jst = timezone(timedelta(hours=9))
    dt = datetime(2026, 4, 17, 21, 34, 56, tzinfo=jst)
    assert rfc3339_utc(dt) == "2026-04-17T12:34:56Z"


def test_to_utc_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError):
        to_utc(datetime(2026, 4, 17, 0, 0, 0))


def test_granularity_delta_m1_is_60s() -> None:
    assert granularity_delta("M1") == timedelta(seconds=60)


def test_granularity_delta_h1_is_1h() -> None:
    assert granularity_delta("H1") == timedelta(hours=1)


def test_granularity_delta_unknown_raises() -> None:
    with pytest.raises(ValueError):
        granularity_delta("X99")


def test_now_utc_is_tz_aware() -> None:
    dt = now_utc()
    assert dt.tzinfo is not None
