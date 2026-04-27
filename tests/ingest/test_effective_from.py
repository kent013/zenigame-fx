"""T057 Gate A: effective_from_utc policy unit tests."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from src.ingest.effective_from import (
    SERIES_POLICY_CONSERVATIVE,
    EffectiveFromSource,
    compute_effective_from_utc,
    max_policy_lag_days,
)


class TestComputeEffectiveFromUtc:
    def test_daily_series_24h_lag(self) -> None:
        eff = compute_effective_from_utc("VIXCLS", date(2026, 1, 1))
        assert eff == datetime(2026, 1, 2, 0, 0, tzinfo=UTC)

    def test_dxy_24h_lag(self) -> None:
        eff = compute_effective_from_utc("DTWEXBGS", date(2026, 4, 15))
        assert eff == datetime(2026, 4, 16, 0, 0, tzinfo=UTC)

    def test_monthly_series_35d_lag(self) -> None:
        eff = compute_effective_from_utc("PCOPPUSDM", date(2026, 1, 1))
        assert eff == datetime(2026, 2, 5, 0, 0, tzinfo=UTC)

    def test_unknown_series_default_24h_lag(self) -> None:
        eff = compute_effective_from_utc("UNKNOWN_SERIES", date(2026, 1, 1))
        assert eff == datetime(2026, 1, 2, 0, 0, tzinfo=UTC)

    def test_returns_tz_aware_utc(self) -> None:
        eff = compute_effective_from_utc("VIXCLS", date(2026, 1, 1))
        assert eff.tzinfo is not None
        assert eff.tzinfo == UTC


class TestMaxPolicyLagDays:
    def test_returns_max_among_series(self) -> None:
        # 月次系列が 35 日なので最大は 35
        assert max_policy_lag_days() == 35

    def test_consistent_with_policy_table(self) -> None:
        expected = max(p["lag_hours"] // 24 for p in SERIES_POLICY_CONSERVATIVE.values())
        assert max_policy_lag_days() == expected


class TestEffectiveFromSource:
    def test_enum_values_are_strings(self) -> None:
        assert EffectiveFromSource.POLICY_CONSERVATIVE.value == "policy_conservative"
        assert EffectiveFromSource.FRED_REALTIME_START.value == "fred_realtime_start"

    def test_enum_can_be_compared_to_string(self) -> None:
        # Enum は str 継承 (str, Enum) なので value 比較が可能
        assert EffectiveFromSource.POLICY_CONSERVATIVE == "policy_conservative"


@pytest.mark.parametrize(
    "series_id,obs_date,expected_hours",
    [
        ("VIXCLS", date(2026, 1, 1), 24),
        ("DTWEXBGS", date(2026, 1, 1), 24),
        ("PCOPPUSDM", date(2026, 1, 1), 24 * 35),
        ("PALLFNFINDEXM", date(2026, 1, 1), 24 * 35),
        ("GOLDPMGBD228NLBM", date(2026, 1, 1), 24),
        ("DCOILWTICO", date(2026, 1, 1), 24),
        ("SP500", date(2026, 1, 1), 24),
    ],
)
def test_compute_effective_from_utc_table(
    series_id: str, obs_date: date, expected_hours: int
) -> None:
    eff = compute_effective_from_utc(series_id, obs_date)
    expected = datetime.combine(
        obs_date, datetime.min.time(), tzinfo=UTC
    )
    delta = eff - expected
    assert int(delta.total_seconds() // 3600) == expected_hours
