"""DST/holiday boundary contract unit tests (T072 cascade port v2 Phase 2).

詳細設計 § 5 (test_id F1-F53) を 1:1 で対応する unit test 群。
"""

from __future__ import annotations

import random
import textwrap
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from src.backtest.calendar import (
    BROKER_SCHEDULE_VERSION,
    BUCKET_FULL_MINUTES,
    HOLIDAY_CALENDAR_VERSION,
    M1_PLUS_GRANULARITIES,
    RECORD_SCHEMA_VERSION,
    SESSION_BLOCK_DERIVED_FIELD_PATHS,
    SESSION_BLOCK_STORAGE_FIELDS,
    BrokerSchedulingProvenance,
    BrokerSeasonalCloseSpec,
    BrokerTradingSchedule,
    MarketHolidayCalendar,
    ObservabilityFlags,
    compute_bucket_open_minutes,
    compute_expected_bar_count,
    compute_observability_flags,
    is_dst_transition,
    is_market_holiday,
    load_broker_trading_schedule,
    load_market_holiday_calendar,
    validate_calendar_coverage,
)
from src.backtest.session_block import SessionBlock

# -- helpers ---------------------------------------------------------------


def _make_provenance() -> BrokerSchedulingProvenance:
    return BrokerSchedulingProvenance(
        source="test", verified_at=date(2024, 1, 1), confidence="high", notes="test"
    )


def _full_year_specs(year: int = 2024) -> tuple[BrokerSeasonalCloseSpec, ...]:
    """1 年を 1 region で cover する単純 spec (= test fixture)."""
    return (
        BrokerSeasonalCloseSpec(
            name=f"flat_{year}",
            region_start=date(year, 1, 1),
            region_end=date(year, 12, 31),
            close_hour_utc=22,
            reopen_hour_utc=22,
        ),
    )


def _make_simple_schedule(
    year: int = 2024,
    *,
    full_close: frozenset[date] = frozenset(),
    overrides: dict[date, tuple[int, int]] | None = None,
) -> BrokerTradingSchedule:
    return BrokerTradingSchedule(
        dst_aware_close_table=_full_year_specs(year),
        broker_full_close_holidays=full_close,
        date_overrides=overrides or {},
        period_start=date(year, 1, 1),
        period_end=date(year, 12, 31),
        provenance=_make_provenance(),
        version=BROKER_SCHEDULE_VERSION,
    )


def _make_calendar(
    market: str,
    holidays: frozenset[date] = frozenset(),
    *,
    period_start: date = date(2024, 1, 1),
    period_end: date = date(2024, 12, 31),
) -> MarketHolidayCalendar:
    return MarketHolidayCalendar(
        market=market,  # type: ignore[arg-type]
        period_start=period_start,
        period_end=period_end,
        holidays=holidays,
        schema_version=HOLIDAY_CALENDAR_VERSION,
    )


# -- F1-F5: pure function tests (is_dst_transition / is_market_holiday) ----


class TestIsDstTransition:
    """F1-F4: is_dst_transition pure function tests."""

    def test_is_dst_transition_tokyo_always_false(self) -> None:
        # F1: Tokyo は常に False
        for d in (date(2024, 3, 10), date(2024, 11, 3), date(2024, 6, 1)):
            assert is_dst_transition("tokyo", d) is False

    def test_is_dst_transition_london_critical_transitions(self) -> None:
        # F2: 重要 transition 6 件 + 反例
        # London: spring = last Sunday of March, fall = last Sunday of October
        london_transitions = (
            date(2024, 3, 31),
            date(2024, 10, 27),
            date(2025, 3, 30),
            date(2025, 10, 26),
            date(2026, 3, 29),
            date(2026, 10, 25),
        )
        for d in london_transitions:
            assert is_dst_transition("london", d) is True
        # 反例
        assert is_dst_transition("london", date(2024, 6, 1)) is False
        assert is_dst_transition("london", date(2024, 12, 25)) is False

    def test_is_dst_transition_ny_critical_transitions(self) -> None:
        # F3: NY 重要 transition 6 件 + 反例
        ny_transitions = (
            date(2024, 3, 10),
            date(2024, 11, 3),
            date(2025, 3, 9),
            date(2025, 11, 2),
            date(2026, 3, 8),
            date(2026, 11, 1),
        )
        for d in ny_transitions:
            assert is_dst_transition("ny", d) is True
        assert is_dst_transition("ny", date(2024, 6, 1)) is False
        assert is_dst_transition("ny", date(2024, 12, 25)) is False

    def test_is_dst_transition_unknown_market_raises(self) -> None:
        # F4
        with pytest.raises(ValueError, match="unknown market"):
            is_dst_transition("zurich", date(2024, 3, 31))  # type: ignore[arg-type]


class TestIsMarketHoliday:
    """F5: 旧 F5/F6/F7 統合."""

    def test_is_market_holiday_happy_and_mismatch(self) -> None:
        cal = _make_calendar(
            "tokyo",
            holidays=frozenset({date(2024, 1, 1), date(2024, 12, 31)}),
        )
        # happy: holiday に含まれる日
        assert is_market_holiday("tokyo", date(2024, 1, 1), cal) is True
        # 含まれない日
        assert is_market_holiday("tokyo", date(2024, 1, 2), cal) is False
        # market 不一致
        with pytest.raises(ValueError, match="!= requested market"):
            is_market_holiday("london", date(2024, 1, 1), cal)


# -- F8-F14: BrokerSeasonalCloseSpec / BrokerTradingSchedule tests --------


class TestBrokerSeasonalCloseSpec:
    def test_seasonal_close_spec_invalid_hour_raises(self) -> None:
        # F8
        with pytest.raises(ValueError, match="close_hour_utc"):
            BrokerSeasonalCloseSpec(
                name="bad",
                region_start=date(2024, 1, 1),
                region_end=date(2024, 12, 31),
                close_hour_utc=24,
                reopen_hour_utc=22,
            )
        with pytest.raises(ValueError, match="reopen_hour_utc"):
            BrokerSeasonalCloseSpec(
                name="bad",
                region_start=date(2024, 1, 1),
                region_end=date(2024, 12, 31),
                close_hour_utc=22,
                reopen_hour_utc=-1,
            )

    def test_seasonal_close_spec_invalid_region_order_raises(self) -> None:
        # F9
        with pytest.raises(ValueError, match=r"region_start.*region_end"):
            BrokerSeasonalCloseSpec(
                name="bad",
                region_start=date(2024, 12, 31),
                region_end=date(2024, 1, 1),
                close_hour_utc=22,
                reopen_hour_utc=22,
            )


class TestBrokerTradingSchedule:
    def test_broker_schedule_version_mismatch_raises(self) -> None:
        # F10
        with pytest.raises(ValueError, match="version"):
            BrokerTradingSchedule(
                dst_aware_close_table=_full_year_specs(2024),
                broker_full_close_holidays=frozenset(),
                date_overrides={},
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                provenance=_make_provenance(),
                version="0.0.1",
            )

    def test_broker_schedule_invalid_period_raises(self) -> None:
        # F11
        with pytest.raises(ValueError, match=r"period_start.*period_end"):
            BrokerTradingSchedule(
                dst_aware_close_table=_full_year_specs(2024),
                broker_full_close_holidays=frozenset(),
                date_overrides={},
                period_start=date(2024, 12, 31),
                period_end=date(2024, 1, 1),
                provenance=_make_provenance(),
                version=BROKER_SCHEDULE_VERSION,
            )

    def test_broker_schedule_dst_table_overlap_raises(self) -> None:
        # F12: 隣接 region 重複
        specs = (
            BrokerSeasonalCloseSpec(
                name="a",
                region_start=date(2024, 1, 1),
                region_end=date(2024, 6, 30),
                close_hour_utc=22,
                reopen_hour_utc=22,
            ),
            BrokerSeasonalCloseSpec(
                name="b",
                region_start=date(2024, 6, 30),  # overlap
                region_end=date(2024, 12, 31),
                close_hour_utc=21,
                reopen_hour_utc=21,
            ),
        )
        with pytest.raises(ValueError, match="region gap or overlap"):
            BrokerTradingSchedule(
                dst_aware_close_table=specs,
                broker_full_close_holidays=frozenset(),
                date_overrides={},
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                provenance=_make_provenance(),
                version=BROKER_SCHEDULE_VERSION,
            )

    def test_broker_schedule_dst_table_gap_raises(self) -> None:
        # F13: 隣接 region 間に隙間
        specs = (
            BrokerSeasonalCloseSpec(
                name="a",
                region_start=date(2024, 1, 1),
                region_end=date(2024, 6, 30),
                close_hour_utc=22,
                reopen_hour_utc=22,
            ),
            BrokerSeasonalCloseSpec(
                name="b",
                region_start=date(2024, 7, 2),  # gap
                region_end=date(2024, 12, 31),
                close_hour_utc=21,
                reopen_hour_utc=21,
            ),
        )
        with pytest.raises(ValueError, match="region gap or overlap"):
            BrokerTradingSchedule(
                dst_aware_close_table=specs,
                broker_full_close_holidays=frozenset(),
                date_overrides={},
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                provenance=_make_provenance(),
                version=BROKER_SCHEDULE_VERSION,
            )

    def test_broker_schedule_full_close_out_of_period_raises(self) -> None:
        # F14_full_close_out_of_period
        with pytest.raises(ValueError, match=r"broker_full_close_holiday.*out of period"):
            BrokerTradingSchedule(
                dst_aware_close_table=_full_year_specs(2024),
                broker_full_close_holidays=frozenset({date(2025, 1, 1)}),
                date_overrides={},
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                provenance=_make_provenance(),
                version=BROKER_SCHEDULE_VERSION,
            )

    def test_broker_schedule_overrides_out_of_period_raises(self) -> None:
        # F14_overrides_out_of_period
        with pytest.raises(ValueError, match=r"date_override key.*out of period"):
            BrokerTradingSchedule(
                dst_aware_close_table=_full_year_specs(2024),
                broker_full_close_holidays=frozenset(),
                date_overrides={date(2025, 1, 1): (0, 1080)},
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                provenance=_make_provenance(),
                version=BROKER_SCHEDULE_VERSION,
            )

    def test_broker_schedule_overrides_invalid_window_raises(self) -> None:
        # F14_overrides_invalid_window
        with pytest.raises(ValueError, match="window invalid"):
            BrokerTradingSchedule(
                dst_aware_close_table=_full_year_specs(2024),
                broker_full_close_holidays=frozenset(),
                date_overrides={date(2024, 7, 4): (1080, 1020)},  # start>end
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                provenance=_make_provenance(),
                version=BROKER_SCHEDULE_VERSION,
            )
        with pytest.raises(ValueError, match="window invalid"):
            BrokerTradingSchedule(
                dst_aware_close_table=_full_year_specs(2024),
                broker_full_close_holidays=frozenset(),
                date_overrides={date(2024, 7, 4): (0, 1500)},  # > 1440
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                provenance=_make_provenance(),
                version=BROKER_SCHEDULE_VERSION,
            )

    def test_broker_schedule_overrides_overlap_with_full_close_raises(self) -> None:
        # F14_overrides_overlap_full_close
        with pytest.raises(ValueError, match="must not overlap"):
            BrokerTradingSchedule(
                dst_aware_close_table=_full_year_specs(2024),
                broker_full_close_holidays=frozenset({date(2024, 12, 25)}),
                date_overrides={date(2024, 12, 25): (0, 1080)},
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                provenance=_make_provenance(),
                version=BROKER_SCHEDULE_VERSION,
            )


# -- F14_yaml_*: YAML loader duplicate / merge key reject ------------------


class TestYamlLoader:
    def test_broker_schedule_yaml_duplicate_key_rejected(
        self, tmp_path: Path
    ) -> None:
        # F14_yaml_duplicate_key_reject
        bad_yaml = textwrap.dedent("""\
            version: "1.0.0"
            period_start: "2024-01-01"
            period_end: "2024-12-31"
            provenance:
              source: "test"
              verified_at: "2024-01-01"
              confidence: "high"
              notes: "test"
            dst_aware_close_table:
              - name: "ny_2024"
                region_start: "2024-01-01"
                region_end: "2024-12-31"
                close_hour_utc: 22
                reopen_hour_utc: 22
            broker_full_close_holidays: []
            date_overrides:
              "2024-07-04": [0, 1020]
              "2024-07-04": [0, 1080]
            """)
        path = tmp_path / "bad.yaml"
        path.write_text(bad_yaml, encoding="utf-8")
        with pytest.raises(yaml.constructor.ConstructorError, match="duplicate key"):
            load_broker_trading_schedule(path)

    def test_broker_schedule_yaml_merge_key_rejected(self, tmp_path: Path) -> None:
        # F14_yaml_merge_key_reject
        bad_yaml = textwrap.dedent("""\
            version: "1.0.0"
            period_start: "2024-01-01"
            period_end: "2024-12-31"
            provenance: &prov
              source: "test"
              verified_at: "2024-01-01"
              confidence: "high"
              notes: "test"
            other:
              <<: *prov
              extra: "x"
            dst_aware_close_table:
              - name: "ny_2024"
                region_start: "2024-01-01"
                region_end: "2024-12-31"
                close_hour_utc: 22
                reopen_hour_utc: 22
            broker_full_close_holidays: []
            date_overrides: {}
            """)
        path = tmp_path / "merge.yaml"
        path.write_text(bad_yaml, encoding="utf-8")
        with pytest.raises(yaml.constructor.ConstructorError, match="merge key"):
            load_broker_trading_schedule(path)

    def test_broker_schedule_yaml_duplicate_after_merge_attempt_rejected(
        self, tmp_path: Path
    ) -> None:
        # F14_yaml_duplicate_after_flatten: merge key reject により duplicate 迂回不可を確認.
        bad_yaml = textwrap.dedent("""\
            version: "1.0.0"
            period_start: "2024-01-01"
            period_end: "2024-12-31"
            provenance: &prov
              source: "test"
              verified_at: "2024-01-01"
              confidence: "high"
              notes: "test"
            dst_aware_close_table:
              - name: "ny_2024"
                region_start: "2024-01-01"
                region_end: "2024-12-31"
                close_hour_utc: 22
                reopen_hour_utc: 22
            broker_full_close_holidays: []
            date_overrides:
              <<: {"2024-07-04": [0, 1020]}
              "2024-07-04": [0, 1080]
            """)
        path = tmp_path / "merge_dup.yaml"
        path.write_text(bad_yaml, encoding="utf-8")
        with pytest.raises(yaml.constructor.ConstructorError):
            load_broker_trading_schedule(path)


# -- F14 property-based ---------------------------------------------------


class TestBrokerSchedulePropertyBased:
    """F14_property_based_continuous_cover (Round D1 [S4]).

    hypothesis を導入していないため、 manual な randomized property-based test を実装.
    """

    def test_broker_schedule_property_continuous_cover(self) -> None:
        rng = random.Random(0xCAFE)
        # 50 random valid configurations -> all should construct
        for _ in range(50):
            year = rng.choice([2022, 2023, 2024, 2025])
            cuts = sorted(
                {rng.randint(40, 320) for _ in range(rng.randint(1, 5))}
            )
            specs: list[BrokerSeasonalCloseSpec] = []
            current = date(year, 1, 1)
            for offset_idx, day_off in enumerate(cuts):
                end = date(year, 1, 1) + timedelta(days=day_off)
                if end < current:
                    continue
                specs.append(
                    BrokerSeasonalCloseSpec(
                        name=f"r{offset_idx}",
                        region_start=current,
                        region_end=end,
                        close_hour_utc=22 if offset_idx % 2 == 0 else 21,
                        reopen_hour_utc=22 if offset_idx % 2 == 0 else 21,
                    )
                )
                current = end + timedelta(days=1)
            specs.append(
                BrokerSeasonalCloseSpec(
                    name="last",
                    region_start=current,
                    region_end=date(year, 12, 31),
                    close_hour_utc=22,
                    reopen_hour_utc=22,
                )
            )
            sched = BrokerTradingSchedule(
                dst_aware_close_table=tuple(specs),
                broker_full_close_holidays=frozenset(),
                date_overrides={},
                period_start=date(year, 1, 1),
                period_end=date(year, 12, 31),
                provenance=_make_provenance(),
                version=BROKER_SCHEDULE_VERSION,
            )
            # 全 date が 1 つの spec に対応する
            d = date(year, 1, 1)
            while d <= date(year, 12, 31):
                spec = sched._find_season(d)
                assert spec.region_start <= d <= spec.region_end
                d += timedelta(days=30)

        # 故意に gap を作って ValueError 確認
        with pytest.raises(ValueError, match="region gap or overlap"):
            BrokerTradingSchedule(
                dst_aware_close_table=(
                    BrokerSeasonalCloseSpec(
                        name="a",
                        region_start=date(2024, 1, 1),
                        region_end=date(2024, 6, 1),
                        close_hour_utc=22,
                        reopen_hour_utc=22,
                    ),
                    BrokerSeasonalCloseSpec(
                        name="b",
                        region_start=date(2024, 7, 1),  # gap
                        region_end=date(2024, 12, 31),
                        close_hour_utc=22,
                        reopen_hour_utc=22,
                    ),
                ),
                broker_full_close_holidays=frozenset(),
                date_overrides={},
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                provenance=_make_provenance(),
                version=BROKER_SCHEDULE_VERSION,
            )


# -- F15-F22: open_window_for_utc_date tests -------------------------------


class TestOpenWindowForUtcDate:
    """F15-F22: SSOT 優先順位 + season 別."""

    def _multi_season_schedule(self) -> BrokerTradingSchedule:
        # 2024-03-10 を境に standard → DST。 2024-11-03 を境に DST → standard.
        specs = (
            BrokerSeasonalCloseSpec(
                name="ny_std_pre",
                region_start=date(2024, 1, 1),
                region_end=date(2024, 3, 9),
                close_hour_utc=22,
                reopen_hour_utc=22,
            ),
            BrokerSeasonalCloseSpec(
                name="ny_dst",
                region_start=date(2024, 3, 10),
                region_end=date(2024, 11, 2),
                close_hour_utc=21,
                reopen_hour_utc=21,
            ),
            BrokerSeasonalCloseSpec(
                name="ny_std_post",
                region_start=date(2024, 11, 3),
                region_end=date(2024, 12, 31),
                close_hour_utc=22,
                reopen_hour_utc=22,
            ),
        )
        return BrokerTradingSchedule(
            dst_aware_close_table=specs,
            broker_full_close_holidays=frozenset({date(2024, 12, 25)}),
            date_overrides={date(2024, 12, 24): (0, 1080)},
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
            provenance=_make_provenance(),
            version=BROKER_SCHEDULE_VERSION,
        )

    def test_open_window_weekday_full_open(self) -> None:
        # F15: Mon-Thu
        sched = self._multi_season_schedule()
        for d in (
            date(2024, 1, 8),
            date(2024, 1, 9),
            date(2024, 1, 10),
            date(2024, 1, 11),
        ):
            assert sched.open_window_for_utc_date(d) == (0, 1440)

    def test_open_window_saturday_closed(self) -> None:
        # F16
        sched = self._multi_season_schedule()
        # 2024-01-06 = Sat
        assert sched.open_window_for_utc_date(date(2024, 1, 6)) == (0, 0)

    def test_open_window_sunday_standard_reopen(self) -> None:
        # F17: Sun standard (reopen=22) → (1320, 1440)
        sched = self._multi_season_schedule()
        # 2024-01-07 = Sun, in standard
        assert sched.open_window_for_utc_date(date(2024, 1, 7)) == (1320, 1440)

    def test_open_window_sunday_dst_reopen(self) -> None:
        # F18: Sun DST (reopen=21) → (1260, 1440)
        sched = self._multi_season_schedule()
        # 2024-06-02 = Sun, in DST
        assert sched.open_window_for_utc_date(date(2024, 6, 2)) == (1260, 1440)

    def test_open_window_friday_standard_close(self) -> None:
        # F19: Fri standard (close=22) → (0, 1320)
        sched = self._multi_season_schedule()
        # 2024-01-05 = Fri, in standard
        assert sched.open_window_for_utc_date(date(2024, 1, 5)) == (0, 1320)

    def test_open_window_friday_dst_close(self) -> None:
        # F20: Fri DST (close=21) → (0, 1260)
        sched = self._multi_season_schedule()
        # 2024-05-31 = Fri, in DST
        assert sched.open_window_for_utc_date(date(2024, 5, 31)) == (0, 1260)

    def test_open_window_full_close_holiday(self) -> None:
        # F21: 12/25 → (0, 0)
        sched = self._multi_season_schedule()
        assert sched.open_window_for_utc_date(date(2024, 12, 25)) == (0, 0)

    def test_open_window_date_override_priority(self) -> None:
        # F22: 12/24 = override (Tue), priority over default Mon-Thu (0, 1440)
        sched = self._multi_season_schedule()
        assert sched.open_window_for_utc_date(date(2024, 12, 24)) == (0, 1080)


# -- F23-F28: MarketHolidayCalendar tests ----------------------------------


class TestMarketHolidayCalendar:
    def test_market_holiday_calendar_load_and_contains(
        self, tmp_path: Path
    ) -> None:
        # F23
        yaml_text = textwrap.dedent("""\
            market: "tokyo"
            schema_version: "1.0.0"
            period_start: "2024-01-01"
            period_end: "2024-12-31"
            provenance:
              source: "test"
              verified_at: "2024-01-01"
              confidence: "high"
              notes: "test"
            holidays:
              - "2024-01-01"
              - "2024-12-31"
            """)
        path = tmp_path / "tokyo.yaml"
        path.write_text(yaml_text, encoding="utf-8")
        cal = load_market_holiday_calendar("tokyo", path)
        assert cal.contains(date(2024, 1, 1))
        assert cal.contains(date(2024, 12, 31))
        assert not cal.contains(date(2024, 6, 1))

    def test_market_holiday_calendar_version_mismatch_raises(self) -> None:
        # F24
        with pytest.raises(ValueError, match="schema_version"):
            MarketHolidayCalendar(
                market="tokyo",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                holidays=frozenset(),
                schema_version="0.0.1",
            )

    def test_market_holiday_calendar_market_mismatch_raises(
        self, tmp_path: Path
    ) -> None:
        # F25
        yaml_text = textwrap.dedent("""\
            market: "tokyo"
            schema_version: "1.0.0"
            period_start: "2024-01-01"
            period_end: "2024-12-31"
            provenance:
              source: "test"
              verified_at: "2024-01-01"
              confidence: "high"
              notes: "test"
            holidays: []
            """)
        path = tmp_path / "tokyo.yaml"
        path.write_text(yaml_text, encoding="utf-8")
        with pytest.raises(ValueError, match="!= requested market"):
            load_market_holiday_calendar("london", path)

    def test_market_holiday_calendar_out_of_period_raises(self) -> None:
        # F26
        with pytest.raises(ValueError, match=r"holiday.*out of period"):
            MarketHolidayCalendar(
                market="tokyo",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                holidays=frozenset({date(2025, 1, 1)}),
                schema_version=HOLIDAY_CALENDAR_VERSION,
            )

    def test_market_holiday_calendar_invalid_period_raises(self) -> None:
        # F27
        with pytest.raises(ValueError, match=r"period_start.*period_end"):
            MarketHolidayCalendar(
                market="tokyo",
                period_start=date(2024, 12, 31),
                period_end=date(2024, 1, 1),
                holidays=frozenset(),
                schema_version=HOLIDAY_CALENDAR_VERSION,
            )

    def test_market_holiday_calendar_unknown_market_raises(self) -> None:
        # F28
        with pytest.raises(ValueError, match="market must be"):
            MarketHolidayCalendar(
                market="zurich",  # type: ignore[arg-type]
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                holidays=frozenset(),
                schema_version=HOLIDAY_CALENDAR_VERSION,
            )


# -- F29-F33: ObservabilityFlags / compute_observability_flags ------------


class TestObservabilityFlags:
    def test_observability_flags_dst_subset_invariant(self) -> None:
        # F29
        with pytest.raises(ValueError, match="dst_transition_markets must be subset"):
            ObservabilityFlags(
                dst_transition_markets=frozenset({"tokyo"}),  # type: ignore[arg-type]
                holiday_markets=frozenset(),
            )

    def test_observability_flags_holiday_subset_invariant(self) -> None:
        # F30
        with pytest.raises(ValueError, match="holiday_markets must be subset"):
            ObservabilityFlags(
                dst_transition_markets=frozenset(),
                holiday_markets=frozenset({"zurich"}),  # type: ignore[arg-type]
            )

    def test_observability_flags_all_g3_property(self) -> None:
        # F31
        flags3 = ObservabilityFlags(
            dst_transition_markets=frozenset(),
            holiday_markets=frozenset({"tokyo", "london", "ny"}),
        )
        assert flags3.all_g3_market_holiday is True
        flags2 = ObservabilityFlags(
            dst_transition_markets=frozenset(),
            holiday_markets=frozenset({"tokyo", "london"}),
        )
        assert flags2.all_g3_market_holiday is False
        flags0 = ObservabilityFlags(
            dst_transition_markets=frozenset(),
            holiday_markets=frozenset(),
        )
        assert flags0.all_g3_market_holiday is False

    def test_compute_observability_flags_normal_day(self) -> None:
        # F32
        cals = {
            "tokyo": _make_calendar("tokyo"),
            "london": _make_calendar("london"),
            "ny": _make_calendar("ny"),
        }
        flags = compute_observability_flags(date(2024, 6, 5), cals)  # Wed normal
        assert flags.dst_transition_markets == frozenset()
        assert flags.holiday_markets == frozenset()

    def test_compute_observability_flags_compound_case(self) -> None:
        # F33: G3 holiday + London DST
        # 2024-03-31 (Sun) = London DST transition. Tokyo / NY も holiday に登録 (test fixture).
        cals = {
            "tokyo": _make_calendar(
                "tokyo", holidays=frozenset({date(2024, 3, 31)})
            ),
            "london": _make_calendar(
                "london", holidays=frozenset({date(2024, 3, 31)})
            ),
            "ny": _make_calendar("ny", holidays=frozenset({date(2024, 3, 31)})),
        }
        flags = compute_observability_flags(date(2024, 3, 31), cals)
        assert flags.holiday_markets == frozenset({"tokyo", "london", "ny"})
        assert flags.dst_transition_markets == frozenset({"london"})
        assert flags.all_g3_market_holiday is True


# -- F34-F37: compute_bucket_open_minutes / compute_expected_bar_count ---


class TestBucketOpenMinutes:
    def test_bucket_open_minutes_normal_weekday(self) -> None:
        # F34: Mon-Thu / 全 bucket / no override → 480
        sched = _make_simple_schedule()
        # 2024-01-08 = Mon
        for bucket in ("tokyo", "london", "ny"):
            assert (
                compute_bucket_open_minutes(date(2024, 1, 8), bucket, sched)  # type: ignore[arg-type]
                == 480
            )

    def test_bucket_open_minutes_saturday_closed(self) -> None:
        # F35
        sched = _make_simple_schedule()
        for bucket in ("tokyo", "london", "ny"):
            assert (
                compute_bucket_open_minutes(date(2024, 1, 6), bucket, sched)  # type: ignore[arg-type]
                == 0
            )

    def test_bucket_open_minutes_sunday_tokyo_closed(self) -> None:
        # F36: Sun standard / tokyo bucket → 0 (open=22:00 UTC = ny bucket)
        sched = _make_simple_schedule()
        # 2024-01-07 = Sun
        assert compute_bucket_open_minutes(date(2024, 1, 7), "tokyo", sched) == 0

    def test_bucket_open_minutes_sunday_ny_partial(self) -> None:
        # F37: Sun / ny / standard reopen 22 → 120 min
        sched = _make_simple_schedule()
        assert compute_bucket_open_minutes(date(2024, 1, 7), "ny", sched) == 120

    def test_bucket_open_minutes_sunday_ny_dst_partial_h4_floor(self) -> None:
        # F37_sunday_ny_dst: NY DST reopen 21 → 180 min, H4 floor → 0
        specs = (
            BrokerSeasonalCloseSpec(
                name="ny_dst",
                region_start=date(2024, 1, 1),
                region_end=date(2024, 12, 31),
                close_hour_utc=21,
                reopen_hour_utc=21,
            ),
        )
        sched = BrokerTradingSchedule(
            dst_aware_close_table=specs,
            broker_full_close_holidays=frozenset(),
            date_overrides={},
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
            provenance=_make_provenance(),
            version=BROKER_SCHEDULE_VERSION,
        )
        # 2024-01-07 = Sun
        assert compute_bucket_open_minutes(date(2024, 1, 7), "ny", sched) == 180
        # H4 floor
        assert compute_expected_bar_count(180, 14400) == 0

    def test_bucket_open_minutes_friday_ny_close_partial(self) -> None:
        # F37_friday_ny_standard: Fri / ny / standard close 22 → 360 min
        sched = _make_simple_schedule()
        # 2024-01-05 = Fri
        assert compute_bucket_open_minutes(date(2024, 1, 5), "ny", sched) == 360

    def test_bucket_open_minutes_friday_tokyo_normal(self) -> None:
        # F37_friday_tokyo_normal: Fri / tokyo / standard → 480
        sched = _make_simple_schedule()
        assert compute_bucket_open_minutes(date(2024, 1, 5), "tokyo", sched) == 480

    def test_bucket_open_minutes_holiday_no_impact(self) -> None:
        # F37_holiday_no_impact: Tokyo holiday は broker open に touch しない
        sched = _make_simple_schedule()
        # broker_full_close 不在の Tokyo holiday: broker open 480 のまま (collider bias 規範).
        assert compute_bucket_open_minutes(date(2024, 1, 8), "tokyo", sched) == 480

    def test_bucket_open_minutes_full_close_holiday(self) -> None:
        # F37_full_close: full_close holiday → 全 bucket 0
        sched = _make_simple_schedule(full_close=frozenset({date(2024, 12, 25)}))
        for bucket in ("tokyo", "london", "ny"):
            assert (
                compute_bucket_open_minutes(date(2024, 12, 25), bucket, sched)  # type: ignore[arg-type]
                == 0
            )

    def test_bucket_open_minutes_date_override(self) -> None:
        # F37_date_override: 12/24 = override [0, 1080] / ny bucket → 120 min
        sched = _make_simple_schedule(
            overrides={date(2024, 12, 24): (0, 1080)},
        )
        # 16:00-24:00 ∩ 0-18:00 = 16:00-18:00 = 120 min
        assert compute_bucket_open_minutes(date(2024, 12, 24), "ny", sched) == 120
        # tokyo full
        assert compute_bucket_open_minutes(date(2024, 12, 24), "tokyo", sched) == 480

    def test_compute_expected_bar_count_m5(self) -> None:
        # F37_m5_granularity: M5 (300 sec) で open_minutes=480 → 480*60/300 = 96
        assert compute_expected_bar_count(480, 300) == 96
        assert compute_expected_bar_count(120, 300) == 24

    def test_compute_expected_bar_count_h4_floor(self) -> None:
        # F37_h4_floor: H4 (14400 sec) で open=120 → floor 0
        assert compute_expected_bar_count(120, 14400) == 0
        assert compute_expected_bar_count(480, 14400) == 2

    def test_bucket_open_minutes_half_open_boundary(self) -> None:
        # F37_boundary_overlap: open_window が bucket の境界に一致するケース
        # Sun standard / tokyo bucket [0,8) は open_window [22:00, 24:00) と disjoint → 0
        sched = _make_simple_schedule()
        # tokyo bucket [0:00, 8:00) と open [22:00, 24:00) は完全 disjoint
        assert compute_bucket_open_minutes(date(2024, 1, 7), "tokyo", sched) == 0
        # london bucket [8:00, 16:00) も同 disjoint
        assert compute_bucket_open_minutes(date(2024, 1, 7), "london", sched) == 0

        # Fri standard close 22:00: ny bucket [16:00,24:00) ∩ [0,22:00) = [16:00,22:00) = 360
        assert compute_bucket_open_minutes(date(2024, 1, 5), "ny", sched) == 360
        # tokyo bucket [0,8:00) は完全包含 → 480
        assert compute_bucket_open_minutes(date(2024, 1, 5), "tokyo", sched) == 480


# -- F38-F44: SessionBlock backward-compat tests --------------------------


class TestSessionBlockBackwardCompat:
    """SessionBlock T072 改造 + T070 互換."""

    def _block(self, *, open_minutes: int = 480, granularity_seconds: int = 60) -> SessionBlock:
        from decimal import Decimal as _D

        return SessionBlock(
            business_date=date(2024, 1, 15),
            bucket="tokyo",
            bar_count=480,
            trade_count=0,
            pnl_net=_D(0),
            pnl_before_costs=_D(0),
            spread_cost_total=_D(0),
            holding_cost_total=_D(0),
            open_minutes=open_minutes,
            granularity_seconds=granularity_seconds,
        )

    def test_session_block_default_construction(self) -> None:
        # F38
        from decimal import Decimal as _D

        block = SessionBlock(
            business_date=date(2024, 1, 15),
            bucket="tokyo",
            bar_count=480,
            trade_count=0,
            pnl_net=_D(0),
            pnl_before_costs=_D(0),
            spread_cost_total=_D(0),
            holding_cost_total=_D(0),
        )
        assert block.open_minutes == 480
        assert block.granularity_seconds == 60
        assert block.observability_flags.dst_transition_markets == frozenset()
        assert block.observability_flags.holiday_markets == frozenset()

    def test_session_block_schedule_status_derived(self) -> None:
        # F39
        assert self._block(open_minutes=480).schedule_status == "regular"
        assert self._block(open_minutes=0).schedule_status == "closed_full"
        assert self._block(open_minutes=120).schedule_status == "closed_partial"

    def test_session_block_schedule_status_h4_partial_preserved(self) -> None:
        # F39_h4_partial_preserved
        block = self._block(open_minutes=120, granularity_seconds=14400)
        assert block.schedule_status == "closed_partial"
        assert block.expected_bar_count == 0  # H4 floor

    def test_session_block_t070_compat_eq_hash(self) -> None:
        # F40_eq_hash_compat
        from decimal import Decimal as _D

        b1 = SessionBlock(
            business_date=date(2024, 1, 15),
            bucket="tokyo",
            bar_count=480,
            trade_count=0,
            pnl_net=_D(0),
            pnl_before_costs=_D(0),
            spread_cost_total=_D(0),
            holding_cost_total=_D(0),
        )
        b2 = SessionBlock(
            business_date=date(2024, 1, 15),
            bucket="tokyo",
            bar_count=480,
            trade_count=0,
            pnl_net=_D(0),
            pnl_before_costs=_D(0),
            spread_cost_total=_D(0),
            holding_cost_total=_D(0),
            open_minutes=480,
            granularity_seconds=60,
            observability_flags=ObservabilityFlags(
                dst_transition_markets=frozenset(),
                holiday_markets=frozenset(),
            ),
        )
        assert b1 == b2
        assert hash(b1) == hash(b2)

    def test_session_block_to_record_storage_only(self) -> None:
        # F41_to_record_storage
        record = self._block().to_record(include_derived=False)
        for path in SESSION_BLOCK_STORAGE_FIELDS:
            head, _, tail = path.partition(".")
            if tail:
                assert head in record, f"missing top {head}"
                assert tail in record[head], f"missing nested {path}"
            else:
                assert path in record, f"missing top {path}"
        # derived は含まれない
        assert "schedule_status" not in record
        assert "expected_bar_count" not in record
        assert "is_partial_bar_block" not in record
        assert "all_g3_market_holiday" not in record["observability_flags"]

    def test_session_block_to_record_include_derived(self) -> None:
        # F41_to_record_derived
        record = self._block(open_minutes=120).to_record(include_derived=True)
        assert record["schedule_status"] == "closed_partial"
        assert record["expected_bar_count"] == 120  # M1
        assert "is_partial_bar_block" in record
        assert (
            record["observability_flags"]["all_g3_market_holiday"] is False
        )

    def test_session_block_to_record_schema_version(self) -> None:
        # F41_to_record_schema_version
        record = self._block().to_record()
        assert record["record_schema_version"] == RECORD_SCHEMA_VERSION

    def test_session_block_to_record_derived_field_paths_match_schema_constants(
        self,
    ) -> None:
        # F41_to_record_derived_field_paths_match
        record = self._block().to_record(include_derived=True)
        for path in SESSION_BLOCK_DERIVED_FIELD_PATHS:
            head, _, tail = path.partition(".")
            if tail:
                assert head in record
                assert tail in record[head], f"missing derived {path}"
            else:
                assert path in record, f"missing derived {path}"

    def test_session_block_invalid_granularity_raises(self) -> None:
        # F42_invalid_granularity
        with pytest.raises(ValueError, match="granularity_seconds"):
            self._block(granularity_seconds=45)

    def test_session_block_h3_granularity_rejected(self) -> None:
        # F42_h3_rejected
        with pytest.raises(ValueError, match="granularity_seconds"):
            self._block(granularity_seconds=10800)

    def test_session_block_invalid_open_minutes_raises(self) -> None:
        # F43_invalid_open_minutes
        with pytest.raises(ValueError, match="open_minutes"):
            self._block(open_minutes=500)
        with pytest.raises(ValueError, match="open_minutes"):
            self._block(open_minutes=-1)

    def test_session_block_tolerance_warning_open(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # F44_tolerance_warning_open: M1 で expected=120 / bar_count=126 → warning
        from decimal import Decimal as _D

        with caplog.at_level("WARNING", logger="src.backtest.session_block"):
            SessionBlock(
                business_date=date(2024, 1, 15),
                bucket="tokyo",
                bar_count=126,
                trade_count=0,
                pnl_net=_D(0),
                pnl_before_costs=_D(0),
                spread_cost_total=_D(0),
                holding_cost_total=_D(0),
                open_minutes=120,
                granularity_seconds=60,
            )
        assert any(
            "session_block_bar_count_exceeds_tolerance" in r.message
            for r in caplog.records
        )

    def test_session_block_closed_full_warning_separate_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # F44_closed_full_warning
        from decimal import Decimal as _D

        with caplog.at_level("WARNING", logger="src.backtest.session_block"):
            SessionBlock(
                business_date=date(2024, 1, 15),
                bucket="tokyo",
                bar_count=2,  # closed_full なのに bar が 2 個 (= 異常)
                trade_count=0,
                pnl_net=_D(0),
                pnl_before_costs=_D(0),
                spread_cost_total=_D(0),
                holding_cost_total=_D(0),
                open_minutes=0,
                granularity_seconds=60,
            )
        # 別系列ログ名
        assert any(
            "closed_full_unexpected_bars" in r.message for r in caplog.records
        )
        # session_block_bar_count_exceeds_tolerance は出ない
        assert not any(
            "session_block_bar_count_exceeds_tolerance" in r.message
            for r in caplog.records
        )


# -- F45-F49: aggregate_session_blocks 改造 ------------------------------


class TestAggregateSessionBlocks:
    """aggregate_session_blocks signature 拡張 + production wrapper."""

    def _make_one_bar_for_date(self, d: date):
        from datetime import UTC, datetime
        from decimal import Decimal as _D

        from src.domain.price import Ohlc, PriceBar

        bid = _D("1.1000")
        ask = _D("1.1002")
        return PriceBar(
            pair_name="EUR_USD",
            bar_time=datetime(d.year, d.month, d.day, 4, 0, tzinfo=UTC),  # tokyo
            bid=Ohlc(open=bid, high=bid, low=bid, close=bid),
            ask=Ohlc(open=ask, high=ask, low=ask, close=ask),
            volume=10,
            complete=True,
        )

    def test_aggregate_test_mode_all_none_defaults(self) -> None:
        # F45
        from src.backtest.session_block import aggregate_session_blocks

        bars = [self._make_one_bar_for_date(date(2024, 1, 8))]
        blocks = aggregate_session_blocks(bars, [], mode="test")
        assert len(blocks) == 3  # 3 buckets
        for b in blocks:
            assert b.open_minutes == 480
            assert b.observability_flags.dst_transition_markets == frozenset()
            assert b.observability_flags.holiday_markets == frozenset()

    def test_aggregate_test_mode_broker_only(self) -> None:
        # F46
        from src.backtest.session_block import aggregate_session_blocks

        sched = _make_simple_schedule()
        bars = [self._make_one_bar_for_date(date(2024, 1, 5))]  # Fri
        blocks = aggregate_session_blocks(bars, [], mode="test", broker_schedule=sched)
        # Fri close 22:00 → ny bucket = 360
        ny = next(b for b in blocks if b.bucket == "ny")
        assert ny.open_minutes == 360
        # flags は default
        assert ny.observability_flags.holiday_markets == frozenset()

    def test_aggregate_test_mode_calendars_only(self) -> None:
        # F47
        from src.backtest.session_block import aggregate_session_blocks

        cals = {
            "tokyo": _make_calendar(
                "tokyo", holidays=frozenset({date(2024, 1, 8)})
            ),
            "london": _make_calendar("london"),
            "ny": _make_calendar("ny"),
        }
        bars = [self._make_one_bar_for_date(date(2024, 1, 8))]  # Mon
        blocks = aggregate_session_blocks(bars, [], mode="test", calendars=cals)
        for b in blocks:
            assert b.open_minutes == 480
            assert b.observability_flags.holiday_markets == frozenset({"tokyo"})

    def test_aggregate_test_mode_both_provided(self) -> None:
        # F48
        from src.backtest.session_block import aggregate_session_blocks

        sched = _make_simple_schedule()
        cals = {
            "tokyo": _make_calendar("tokyo"),
            "london": _make_calendar("london"),
            "ny": _make_calendar("ny"),
        }
        bars = [self._make_one_bar_for_date(date(2024, 1, 8))]
        blocks = aggregate_session_blocks(
            bars, [], mode="test", broker_schedule=sched, calendars=cals
        )
        assert len(blocks) == 3
        for b in blocks:
            assert b.open_minutes == 480

    def test_aggregate_production_mode_both_provided(self) -> None:
        # F48_production_both
        from src.backtest.session_block import aggregate_session_blocks

        sched = _make_simple_schedule()
        cals = {
            "tokyo": _make_calendar("tokyo"),
            "london": _make_calendar("london"),
            "ny": _make_calendar("ny"),
        }
        bars = [self._make_one_bar_for_date(date(2024, 1, 8))]
        blocks = aggregate_session_blocks(
            bars, [], mode="production", broker_schedule=sched, calendars=cals
        )
        assert len(blocks) == 3

    def test_aggregate_production_mode_partial_raises(self) -> None:
        # F48_production_partial
        from src.backtest.session_block import aggregate_session_blocks

        sched = _make_simple_schedule()
        bars = [self._make_one_bar_for_date(date(2024, 1, 8))]
        with pytest.raises(ValueError, match="production mode"):
            aggregate_session_blocks(
                bars, [], mode="production", broker_schedule=sched, calendars=None
            )
        cals = {
            "tokyo": _make_calendar("tokyo"),
            "london": _make_calendar("london"),
            "ny": _make_calendar("ny"),
        }
        with pytest.raises(ValueError, match="production mode"):
            aggregate_session_blocks(
                bars, [], mode="production", broker_schedule=None, calendars=cals
            )

    def test_aggregate_production_mode_all_none_raises(self) -> None:
        # F48_production_all_none
        from src.backtest.session_block import aggregate_session_blocks

        bars = [self._make_one_bar_for_date(date(2024, 1, 8))]
        with pytest.raises(ValueError, match="production mode"):
            aggregate_session_blocks(bars, [], mode="production")

    def test_aggregate_mode_argument_required(self) -> None:
        # F48_mode_required: TypeError on missing mode
        from src.backtest.session_block import aggregate_session_blocks

        bars = [self._make_one_bar_for_date(date(2024, 1, 8))]
        with pytest.raises(TypeError, match="mode"):
            aggregate_session_blocks(bars, [])  # type: ignore[call-arg]

    def test_aggregate_session_blocks_production_wrapper(self) -> None:
        # F48_production_wrapper
        from src.backtest.session_block import aggregate_session_blocks_production

        sched = _make_simple_schedule()
        cals = {
            "tokyo": _make_calendar("tokyo"),
            "london": _make_calendar("london"),
            "ny": _make_calendar("ny"),
        }
        bars = [self._make_one_bar_for_date(date(2024, 1, 8))]
        blocks = aggregate_session_blocks_production(
            bars, [], broker_schedule=sched, calendars=cals
        )
        assert len(blocks) == 3

    def test_production_callers_use_wrapper_only(self) -> None:
        # F49_production_callers_no_test_mode (Round D2 [C3] [S3]):
        # src/ で `aggregate_session_blocks(..., mode="production", ...)` 直接呼出を禁止.
        # production 経路は必ず `aggregate_session_blocks_production` wrapper を使う.
        # `mode="test"` の直接呼出は test/debug / Phase 1 backward-compat (engine.py 等) で許容.
        repo_root = Path(__file__).resolve().parents[2]
        src_dir = repo_root / "src"
        offenders: list[str] = []
        for py_path in src_dir.rglob("*.py"):
            # session_block.py 自身 (= wrapper 内部) は除外
            if py_path.name == "session_block.py":
                continue
            text = py_path.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                # `mode="production"` の直接指定を検出
                if "aggregate_session_blocks(" in stripped and (
                    'mode="production"' in stripped
                    or "mode='production'" in stripped
                ):
                    offenders.append(f"{py_path}:{line_no}: {stripped}")
        assert not offenders, (
            "production code path で aggregate_session_blocks(..., mode='production') "
            "直接呼出禁止. aggregate_session_blocks_production wrapper を使うこと:\n"
            + "\n".join(offenders)
        )

    def test_aggregate_friday_ny_partial(self) -> None:
        # F49_friday_ny_partial: Fri / ny / standard → schedule_status="closed_partial" / open=360
        from src.backtest.session_block import aggregate_session_blocks

        sched = _make_simple_schedule()
        cals = {
            "tokyo": _make_calendar("tokyo"),
            "london": _make_calendar("london"),
            "ny": _make_calendar("ny"),
        }
        bars = [self._make_one_bar_for_date(date(2024, 1, 5))]  # Fri
        blocks = aggregate_session_blocks(
            bars, [], mode="production", broker_schedule=sched, calendars=cals
        )
        ny = next(b for b in blocks if b.bucket == "ny")
        assert ny.open_minutes == 360
        assert ny.schedule_status == "closed_partial"

    def test_aggregate_tokyo_holiday_observability_only(self) -> None:
        # F49_tokyo_holiday_obs: Mon / Tokyo holiday / tokyo bucket → status=regular, holiday_markets={tokyo}
        from src.backtest.session_block import aggregate_session_blocks

        sched = _make_simple_schedule()
        cals = {
            "tokyo": _make_calendar(
                "tokyo", holidays=frozenset({date(2024, 1, 8)})
            ),
            "london": _make_calendar("london"),
            "ny": _make_calendar("ny"),
        }
        bars = [self._make_one_bar_for_date(date(2024, 1, 8))]  # Mon
        blocks = aggregate_session_blocks(
            bars, [], mode="production", broker_schedule=sched, calendars=cals
        )
        tokyo = next(b for b in blocks if b.bucket == "tokyo")
        assert tokyo.schedule_status == "regular"
        assert tokyo.open_minutes == 480
        assert tokyo.observability_flags.holiday_markets == frozenset({"tokyo"})

    def test_aggregate_christmas_full_close_g3(self) -> None:
        # F49_christmas_full_close_g3: 12/25 / london bucket → closed_full, holiday_markets={tokyo,london,ny}
        from src.backtest.session_block import aggregate_session_blocks

        sched = _make_simple_schedule(full_close=frozenset({date(2024, 12, 25)}))
        cals = {
            "tokyo": _make_calendar(
                "tokyo", holidays=frozenset({date(2024, 12, 25)})
            ),
            "london": _make_calendar(
                "london", holidays=frozenset({date(2024, 12, 25)})
            ),
            "ny": _make_calendar(
                "ny", holidays=frozenset({date(2024, 12, 25)})
            ),
        }
        # 12/25 = Wed
        bars = [self._make_one_bar_for_date(date(2024, 12, 25))]
        blocks = aggregate_session_blocks(
            bars, [], mode="production", broker_schedule=sched, calendars=cals
        )
        london = next(b for b in blocks if b.bucket == "london")
        assert london.schedule_status == "closed_full"
        assert london.open_minutes == 0
        assert london.observability_flags.holiday_markets == frozenset(
            {"tokyo", "london", "ny"}
        )
        assert london.observability_flags.all_g3_market_holiday is True


# -- F50-F53: validate_calendar_coverage ----------------------------------


class TestValidateCalendarCoverage:
    def _make_cals(
        self, *, period_start: date = date(2024, 1, 1), period_end: date = date(2024, 12, 31)
    ) -> dict:
        return {
            "tokyo": _make_calendar(
                "tokyo", period_start=period_start, period_end=period_end
            ),
            "london": _make_calendar(
                "london", period_start=period_start, period_end=period_end
            ),
            "ny": _make_calendar(
                "ny", period_start=period_start, period_end=period_end
            ),
        }

    def test_validate_coverage_happy_path(self) -> None:
        # F50_happy
        cals = self._make_cals()
        sched = _make_simple_schedule()
        validate_calendar_coverage(cals, sched, (date(2024, 6, 1), date(2024, 6, 30)))

    def test_validate_coverage_calendars_out_of_period_raises(self) -> None:
        # F51_calendars_out: cals が dataset_span を覆わないが broker は覆う場合
        cals = self._make_cals(
            period_start=date(2024, 1, 1), period_end=date(2024, 6, 30)
        )
        sched = _make_simple_schedule()  # 2024-01-01 .. 2024-12-31
        with pytest.raises(ValueError, match=r"calendar.*period_end"):
            validate_calendar_coverage(
                cals, sched, (date(2024, 1, 1), date(2024, 12, 31))
            )

    def test_validate_coverage_broker_out_of_period_raises(self) -> None:
        # F52_broker_out
        cals = self._make_cals(
            period_start=date(2022, 1, 1), period_end=date(2027, 12, 31)
        )
        sched = _make_simple_schedule()  # period 2024
        with pytest.raises(ValueError, match="broker_schedule"):
            validate_calendar_coverage(
                cals, sched, (date(2025, 6, 1), date(2025, 6, 30))
            )

    def test_validate_coverage_missing_market_raises(self) -> None:
        # F53_missing_market
        cals = {
            "tokyo": _make_calendar("tokyo"),
            "london": _make_calendar("london"),
        }
        sched = _make_simple_schedule()
        with pytest.raises(KeyError):
            validate_calendar_coverage(
                cals,  # type: ignore[arg-type]
                sched,
                (date(2024, 1, 1), date(2024, 12, 31)),
            )

    def test_validate_coverage_inclusive_boundary(self) -> None:
        # F53_inclusive_boundary
        cals = self._make_cals()
        sched = _make_simple_schedule()
        # 両端 inclusive で pass
        validate_calendar_coverage(
            cals, sched, (date(2024, 1, 1), date(2024, 12, 31))
        )
        # start - 1 day → ValueError
        with pytest.raises(ValueError):
            validate_calendar_coverage(
                cals, sched, (date(2023, 12, 31), date(2024, 12, 31))
            )

    def test_validate_coverage_dataset_span_invalid(self) -> None:
        cals = self._make_cals()
        sched = _make_simple_schedule()
        with pytest.raises(ValueError, match="dataset_span"):
            validate_calendar_coverage(
                cals, sched, (date(2024, 12, 31), date(2024, 1, 1))
            )


# -- 5.2 YAML 検証 tests --------------------------------------------------


class TestRealYamlConfigs:
    """config/calendars/*.yaml の実 load 確認."""

    @property
    def _config_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "config" / "calendars"

    def test_load_real_yaml_market_holidays(self) -> None:
        for market, fname in (
            ("tokyo", "tokyo_market_holidays.yaml"),
            ("london", "london_market_holidays.yaml"),
            ("ny", "ny_market_holidays.yaml"),
        ):
            cal = load_market_holiday_calendar(market, self._config_dir / fname)  # type: ignore[arg-type]
            assert cal.market == market
            assert cal.period_start == date(2022, 1, 1)
            assert cal.period_end == date(2027, 12, 31)
            assert cal.schema_version == HOLIDAY_CALENDAR_VERSION
            assert len(cal.holidays) > 0

    def test_load_real_yaml_broker_schedule(self) -> None:
        sched = load_broker_trading_schedule(
            self._config_dir / "broker_trading_schedule.yaml"
        )
        assert sched.version == BROKER_SCHEDULE_VERSION
        assert sched.period_start == date(2022, 1, 1)
        assert sched.period_end == date(2027, 12, 31)
        # dst_aware_close_table cover check (= __post_init__ 検証済)
        assert len(sched.dst_aware_close_table) >= 1
        # validate_calendar_coverage と組み合わせ
        cals = {
            "tokyo": load_market_holiday_calendar(
                "tokyo", self._config_dir / "tokyo_market_holidays.yaml"
            ),
            "london": load_market_holiday_calendar(
                "london", self._config_dir / "london_market_holidays.yaml"
            ),
            "ny": load_market_holiday_calendar(
                "ny", self._config_dir / "ny_market_holidays.yaml"
            ),
        }
        validate_calendar_coverage(
            cals, sched, (date(2022, 1, 1), date(2027, 12, 31))
        )


# -- BUCKET_FULL_MINUTES sanity ------------------------------------------


def test_bucket_full_minutes_constant() -> None:
    assert BUCKET_FULL_MINUTES == 480
    assert frozenset(
        {60, 120, 240, 300, 600, 900, 1800, 3600, 7200, 14400}
    ) == M1_PLUS_GRANULARITIES
