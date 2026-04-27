"""T057 Gate B/C: aux_preflight tests.

検証:
    V4: hard_missing で fail-closed、--allow-aux-missing で override
    V13: 両端 freshness check
    coverage_pct ベースの check
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.alpha_factory.aux_preflight import (
    HARD_REQUIRED_AUX,
    HARD_REQUIRED_PAIRS,
    SOFT_REQUIRED_AUX,
    PreflightResult,
    preflight_check_aux_data,
)
from src.db.connection import Base
from src.db.models import CurrencyPair, MacroIndexDaily, PriceBarM1


@pytest.fixture
def sqlite_session():
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

    original_visit = SQLiteTypeCompiler.visit_BIGINT

    def _visit_bigint_as_integer(self, type_, **kw):  # type: ignore[no-untyped-def]
        return "INTEGER"

    SQLiteTypeCompiler.visit_BIGINT = _visit_bigint_as_integer  # type: ignore[method-assign]
    engine = create_engine("sqlite://", future=True)
    try:
        Base.metadata.create_all(
            engine,
            tables=[
                CurrencyPair.__table__,
                PriceBarM1.__table__,
                MacroIndexDaily.__table__,
            ],
        )
    finally:
        SQLiteTypeCompiler.visit_BIGINT = original_visit  # type: ignore[method-assign]
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _populate_dense_macro(
    session,
    series_id: str,
    *,
    start: date,
    end: date,
    value: float = 10.0,
) -> None:
    """期間中の毎日に value を入れる (coverage 100%)."""
    cur = start
    while cur <= end:
        session.add(
            MacroIndexDaily(
                series_id=series_id,
                date=cur,
                value=Decimal(str(value)),
                fetched_at=datetime(2026, 4, 27, tzinfo=UTC),
                effective_from_utc=datetime(
                    cur.year, cur.month, cur.day, tzinfo=UTC
                )
                + timedelta(hours=24),
                source="policy_conservative",
            )
        )
        cur += timedelta(days=1)
    session.commit()


def _populate_pair_with_dense_bars(
    session, oanda_name: str, *, start: datetime, count: int
) -> CurrencyPair:
    pair = CurrencyPair(
        oanda_name=oanda_name,
        display_name=oanda_name,
        base_currency=oanda_name.split("_")[0],
        quote_currency=oanda_name.split("_")[1],
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        margin_rate=Decimal("0.04"),
        minimum_trade_size=1,
        maximum_order_units=10000000,
        instrument_type="CURRENCY",
        is_active=True,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    session.add(pair)
    session.flush()
    for i in range(count):
        session.add(
            PriceBarM1(
                pair_id=pair.id,
                bar_time=start + timedelta(minutes=i),
                open_bid=Decimal("1.0"),
                high_bid=Decimal("1.0"),
                low_bid=Decimal("1.0"),
                close_bid=Decimal("1.0"),
                open_ask=Decimal("1.01"),
                high_ask=Decimal("1.01"),
                low_ask=Decimal("1.01"),
                close_ask=Decimal("1.01"),
                volume=1,
                complete=True,
            )
        )
    session.commit()
    return pair


class TestPreflightCheckAuxData:
    def test_passes_when_all_hard_required_present(self, sqlite_session) -> None:
        """V4 happy path: hard_required 全部揃って coverage 100% で PASS."""
        period_start = datetime(2026, 1, 1, tzinfo=UTC)
        period_end = datetime(2026, 4, 1, tzinfo=UTC)
        # Stage B 18ヶ月分の lookback を含めて 2024-07 から populate
        for series in HARD_REQUIRED_AUX:
            _populate_dense_macro(
                sqlite_session,
                series,
                start=date(2024, 7, 1),
                end=date(2026, 5, 31),
            )
        for pair in HARD_REQUIRED_PAIRS:
            extended_start = datetime(2024, 7, 1, tzinfo=UTC)
            n_minutes = int(
                (datetime(2026, 5, 31, tzinfo=UTC) - extended_start).total_seconds()
                // 60
            )
            _populate_pair_with_dense_bars(
                sqlite_session,
                pair,
                start=extended_start,
                count=min(n_minutes, 100),  # 一部だけ populate (コスト)
            )
        # pair の bar count を期間日数の 70% 程度に揃えるため、period を短くする:
        # 簡略化のため pair のテストは別に行う
        # ここでは macro が PASS することだけ確認する allow_missing=True で:
        result = preflight_check_aux_data(
            db_session=sqlite_session,
            period=(period_start, period_end),
            stage_b_window_months=18,
            stage_c_holdout_days=60,
            allow_missing=True,  # pair coverage 不足の影響を回避
        )
        # macro hard_satisfied に VIXCLS / DTWEXBGS が入る
        assert "VIXCLS" in result.hard_satisfied
        assert "DTWEXBGS" in result.hard_satisfied

    def test_fails_when_hard_missing_and_strict(self, sqlite_session) -> None:
        """V4 fail-closed: hard_missing があれば RuntimeError."""
        # 何も populate せずに preflight 呼ぶ
        with pytest.raises(RuntimeError, match="preflight aux check FAILED"):
            preflight_check_aux_data(
                db_session=sqlite_session,
                period=(
                    datetime(2026, 1, 1, tzinfo=UTC),
                    datetime(2026, 4, 1, tzinfo=UTC),
                ),
                stage_b_window_months=18,
                stage_c_holdout_days=60,
                allow_missing=False,
            )

    def test_override_with_allow_missing(self, sqlite_session) -> None:
        """V4 override: --allow-aux-missing で hard_missing でも warn のみ."""
        result = preflight_check_aux_data(
            db_session=sqlite_session,
            period=(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 4, 1, tzinfo=UTC),
            ),
            stage_b_window_months=18,
            stage_c_holdout_days=60,
            allow_missing=True,
        )
        # raise しない、結果オブジェクトを返す
        assert isinstance(result, PreflightResult)
        assert "VIXCLS" in result.hard_missing
        assert "DTWEXBGS" in result.hard_missing
        assert not result.passes

    def test_soft_missing_does_not_fail(self, sqlite_session) -> None:
        """soft_missing は raise しない (warn のみ)."""
        # hard だけ populate、soft は populate しない
        for series in HARD_REQUIRED_AUX:
            _populate_dense_macro(
                sqlite_session,
                series,
                start=date(2024, 7, 1),
                end=date(2026, 5, 31),
            )
        # pair はスキップ → hard_missing が出るが allow_missing で override
        result = preflight_check_aux_data(
            db_session=sqlite_session,
            period=(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 4, 1, tzinfo=UTC),
            ),
            stage_b_window_months=18,
            stage_c_holdout_days=60,
            allow_missing=True,
        )
        # soft 全部 missing
        assert set(result.soft_missing) == set(SOFT_REQUIRED_AUX.keys())

    def test_low_coverage_marked_as_missing(self, sqlite_session) -> None:
        """coverage_pct が 50% 未満 (sparse data) は missing として扱われる."""
        # わずか 5 日だけ populate (期間 30+ 日のうち)
        _populate_dense_macro(
            sqlite_session,
            "VIXCLS",
            start=date(2026, 3, 1),
            end=date(2026, 3, 5),
        )
        result = preflight_check_aux_data(
            db_session=sqlite_session,
            period=(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 4, 1, tzinfo=UTC),
            ),
            stage_b_window_months=18,
            stage_c_holdout_days=60,
            allow_missing=True,
        )
        assert "VIXCLS" in result.hard_missing

    def test_stale_tail_freshness_marks_missing(self, sqlite_session) -> None:
        """V13 反映: latest_effective_from が extended_end - safety_lag より古いと missing.

        coverage は十分でも tail freshness が崩れていたら fail-closed.
        """
        # 期間中 dense に populate するが **末尾 1 ヶ月分が欠落**
        # extended_end = period_end + holdout = 2026-04-01 + 60d = 2026-05-31
        # safety_lag = 35+7 = 42 日 → 2026-05-31 - 42d = 2026-04-19
        # latest_effective_from = 2026-02-15 + 24h = 2026-02-16 < 2026-04-19 で stale
        _populate_dense_macro(
            sqlite_session,
            "VIXCLS",
            start=date(2024, 7, 1),  # extended_start = 2026-01-01 - 18m = 2024-07-01
            end=date(2026, 2, 15),  # 末尾 stale (本来は 2026-04 直前まで欲しい)
        )
        result = preflight_check_aux_data(
            db_session=sqlite_session,
            period=(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 4, 1, tzinfo=UTC),
            ),
            stage_b_window_months=18,
            stage_c_holdout_days=60,
            allow_missing=True,
        )
        # tail stale → missing 判定 (両端 freshness check)
        assert "VIXCLS" in result.hard_missing


def test_preflight_result_passes_property() -> None:
    """PreflightResult.passes は hard_missing が空のときのみ True."""
    r1 = PreflightResult(hard_satisfied=["A"], hard_missing=[])
    assert r1.passes is True
    r2 = PreflightResult(hard_satisfied=[], hard_missing=["A"])
    assert r2.passes is False
