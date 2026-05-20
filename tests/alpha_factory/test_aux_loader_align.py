"""T057 Gate A: AuxBundle.align_to / AuxAlignmentCache / DB readers tests.

検証項目:
    V2: look-ahead bias なし (4 ケース)
    V3: misalign vs 欠番分離 (aux_pair_bars)
    V5: stage 別 alignment (bars_60d / bars_stage_b / bars_holdout)
    V7: numpy ndarray 互換 (dtype=float64)
    V14: AuxAlignmentCache key + invalidation
    V15: _normalize_bar_time 丸め衝突 fail-fast
"""

from __future__ import annotations

import pickle
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.alpha_factory.aux_loader import (
    AlignedAuxBundle,
    AuxAlignmentCache,
    AuxBundle,
    AuxPairMidSeries,
    DailyObservation,
    _to_epoch_ns,
    build_aux_bundle_from_db,
    load_aux_pair_mid_index,
    load_daily_series_from_db,
    series_id_to_aux_key,
)
from src.db.connection import Base
from src.db.models import CurrencyPair, MacroIndexDaily, PriceBarM1
from src.domain.price import Ohlc, PriceBar


def _mid_series(*ts_mid: tuple[datetime, float]) -> AuxPairMidSeries:
    """(datetime, mid) ペアから AuxPairMidSeries を構築するテスト helper."""
    ts = np.asarray([_to_epoch_ns(t) for t, _ in ts_mid], dtype=np.int64)
    mid = np.asarray([m for _, m in ts_mid], dtype=np.float64)
    return AuxPairMidSeries(ts_epoch_ns=ts, mid_close=mid)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_bar(ts: datetime, *, pair: str = "EUR_JPY") -> PriceBar:
    return PriceBar(
        pair_name=pair,
        bar_time=ts,
        bid=Ohlc(
            open=Decimal("100.0"),
            high=Decimal("100.0"),
            low=Decimal("100.0"),
            close=Decimal("100.0"),
        ),
        ask=Ohlc(
            open=Decimal("100.01"),
            high=Decimal("100.01"),
            low=Decimal("100.01"),
            close=Decimal("100.01"),
        ),
        volume=10,
        complete=True,
    )


def _make_bars(start: datetime, count: int, *, step_minutes: int = 60) -> list[PriceBar]:
    return [
        _make_bar(start + timedelta(minutes=i * step_minutes))
        for i in range(count)
    ]


@pytest.fixture
def sqlite_session():
    # SQLite では BigInteger PK + AUTOINCREMENT が直接効かないため
    # compile レイヤで BIGINT → INTEGER に変換する。
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


# ---------------------------------------------------------------------------
# V2 / V5: align_to look-ahead bias and stage-specific alignment
# ---------------------------------------------------------------------------


class TestAlignToLookAhead:
    def test_uses_only_past_obs(self) -> None:
        """V2-1: bar_time 直前の obs しか使わない (look-ahead bias なし)."""
        # obs[0] effective_from 2026-01-02T00:00 UTC, obs[1] 2026-01-03T00:00 UTC
        observations = [
            DailyObservation(
                observation_date=date(2026, 1, 1),
                value=10.0,
                effective_from_utc=datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
            ),
            DailyObservation(
                observation_date=date(2026, 1, 2),
                value=20.0,
                effective_from_utc=datetime(2026, 1, 3, 0, 0, tzinfo=UTC),
            ),
        ]
        raw = AuxBundle(daily_series={"VIXCLS": observations})

        # bars: 2026-01-01T12:00 (warmup) / 2026-01-02T12:00 (obs[0]) / 2026-01-03T12:00 (obs[1])
        bars = [
            _make_bar(datetime(2026, 1, 1, 12, 0, tzinfo=UTC)),
            _make_bar(datetime(2026, 1, 2, 12, 0, tzinfo=UTC)),
            _make_bar(datetime(2026, 1, 3, 12, 0, tzinfo=UTC)),
        ]
        aligned = raw.align_to(bars)
        arr = aligned.aux_series["macro.vix"]
        assert arr[0] == 0.0  # warmup
        assert arr[1] == 10.0  # obs[0] effective
        assert arr[2] == 20.0  # obs[1] effective

    def test_warmup_zero_when_no_past_obs(self) -> None:
        """V2-2: dataset 開始時点で obs が無い場合 0.0 (warmup default)."""
        observations = [
            DailyObservation(
                observation_date=date(2026, 1, 5),
                value=99.0,
                effective_from_utc=datetime(2026, 1, 6, 0, 0, tzinfo=UTC),
            ),
        ]
        raw = AuxBundle(daily_series={"VIXCLS": observations})
        bars = [
            _make_bar(datetime(2026, 1, 1, 12, 0, tzinfo=UTC)),
            _make_bar(datetime(2026, 1, 2, 12, 0, tzinfo=UTC)),
        ]
        aligned = raw.align_to(bars)
        arr = aligned.aux_series["macro.vix"]
        assert all(v == 0.0 for v in arr)

    def test_weekend_holiday_forward_fill(self) -> None:
        """V2-3: 週末跨ぎの obs が forward-fill される."""
        # 金曜の obs が effective_from 土曜 → 月曜の bar まで使われる
        observations = [
            DailyObservation(
                observation_date=date(2026, 1, 2),  # 金曜
                value=15.0,
                effective_from_utc=datetime(2026, 1, 3, 0, 0, tzinfo=UTC),  # 土曜
            ),
        ]
        raw = AuxBundle(daily_series={"VIXCLS": observations})
        bars = [
            _make_bar(datetime(2026, 1, 5, 12, 0, tzinfo=UTC)),  # 月曜
            _make_bar(datetime(2026, 1, 6, 12, 0, tzinfo=UTC)),  # 火曜
        ]
        aligned = raw.align_to(bars)
        arr = aligned.aux_series["macro.vix"]
        assert arr[0] == 15.0
        assert arr[1] == 15.0

    def test_strict_inequality_at_effective_from(self) -> None:
        """V2-4: bar_time == effective_from_utc は採用 (>=).

        保守的に「effective_from 時点で利用可能」とする。
        """
        observations = [
            DailyObservation(
                observation_date=date(2026, 1, 1),
                value=42.0,
                effective_from_utc=datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
            ),
        ]
        raw = AuxBundle(daily_series={"VIXCLS": observations})
        bars = [
            _make_bar(datetime(2026, 1, 1, 23, 59, tzinfo=UTC)),  # before
            _make_bar(datetime(2026, 1, 2, 0, 0, tzinfo=UTC)),  # exactly at effective
        ]
        aligned = raw.align_to(bars)
        arr = aligned.aux_series["macro.vix"]
        assert arr[0] == 0.0
        assert arr[1] == 42.0


class TestAlignToStageAlignment:
    def test_different_bars_yield_different_lengths(self) -> None:
        """V5: stage 別 bars で正しい長さの aux_series を返す."""
        observations = [
            DailyObservation(
                observation_date=date(2026, 1, 1),
                value=11.0,
                effective_from_utc=datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
            ),
        ]
        raw = AuxBundle(daily_series={"VIXCLS": observations})
        bars_a = _make_bars(datetime(2026, 1, 5, tzinfo=UTC), count=10)
        bars_b = _make_bars(datetime(2026, 1, 5, tzinfo=UTC), count=100)
        bars_holdout = _make_bars(datetime(2026, 1, 5, tzinfo=UTC), count=50)

        aligned_a = raw.align_to(bars_a)
        aligned_b = raw.align_to(bars_b)
        aligned_h = raw.align_to(bars_holdout)

        assert aligned_a.aux_series["macro.vix"].shape[0] == 10
        assert aligned_b.aux_series["macro.vix"].shape[0] == 100
        assert aligned_h.aux_series["macro.vix"].shape[0] == 50

    def test_empty_bars_returns_empty_bundle(self) -> None:
        """空 bars 契約: warmup-only シナリオ用."""
        raw = AuxBundle()
        aligned = raw.align_to([])
        assert aligned.aux_series == {}
        assert aligned.event_snapshot is None
        assert aligned.aux_pair_mid_close == {}


class TestAlignToReturnsNdarray:
    def test_aux_series_is_ndarray_float64(self) -> None:
        """V7: aux_series が np.ndarray、dtype=float64."""
        observations = [
            DailyObservation(
                observation_date=date(2026, 1, 1),
                value=11.0,
                effective_from_utc=datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
            ),
        ]
        raw = AuxBundle(daily_series={"VIXCLS": observations})
        bars = _make_bars(datetime(2026, 1, 5, tzinfo=UTC), count=5)
        aligned = raw.align_to(bars)
        arr = aligned.aux_series["macro.vix"]
        assert isinstance(arr, np.ndarray)
        assert arr.dtype == np.float64


class TestAlignToAuxPairMidClose:
    def test_exact_match_and_miss_is_nan(self) -> None:
        """T107: exact-match は mid 値、 欠番は NaN."""
        ts1 = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
        ts2 = datetime(2026, 1, 5, 13, 0, tzinfo=UTC)
        ts_missing = datetime(2026, 1, 5, 14, 0, tzinfo=UTC)
        raw = AuxBundle(
            aux_pair_mid_index={"EUR_USD": _mid_series((ts1, 1.1), (ts2, 1.2))}
        )
        target_bars = [_make_bar(ts1), _make_bar(ts2), _make_bar(ts_missing)]
        aligned = raw.align_to(target_bars)
        eu = aligned.aux_pair_mid_close["EUR_USD"]
        assert eu[0] == 1.1
        assert eu[1] == 1.2
        assert np.isnan(eu[2])

    def test_target_before_first_is_nan(self) -> None:
        """T107: target_ns < raw 先頭 → NaN (pos=0 だが不一致)."""
        ts_raw = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
        ts_before = datetime(2026, 1, 5, 11, 0, tzinfo=UTC)
        raw = AuxBundle(aux_pair_mid_index={"EUR_USD": _mid_series((ts_raw, 1.1))})
        aligned = raw.align_to([_make_bar(ts_before)])
        assert np.isnan(aligned.aux_pair_mid_close["EUR_USD"][0])

    def test_target_after_last_is_nan(self) -> None:
        """T107: target_ns > raw 末尾 → NaN (pos==size, in_range で防御)."""
        ts_raw = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
        ts_after = datetime(2026, 1, 5, 13, 0, tzinfo=UTC)
        raw = AuxBundle(aux_pair_mid_index={"EUR_USD": _mid_series((ts_raw, 1.1))})
        aligned = raw.align_to([_make_bar(ts_after)])
        assert np.isnan(aligned.aux_pair_mid_close["EUR_USD"][0])

    def test_equal_last_is_matched(self) -> None:
        """T107: target_ns == raw 末尾 → mid 値 (境界一致)."""
        ts1 = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
        ts2 = datetime(2026, 1, 5, 13, 0, tzinfo=UTC)
        raw = AuxBundle(
            aux_pair_mid_index={"EUR_USD": _mid_series((ts1, 1.1), (ts2, 1.2))}
        )
        aligned = raw.align_to([_make_bar(ts2)])
        assert aligned.aux_pair_mid_close["EUR_USD"][0] == 1.2

    def test_misalign_is_nan_not_forward_fill(self) -> None:
        """T107: bar_time が完全一致しない → NaN (forward-fill 禁止)."""
        ts1 = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
        ts1_off = datetime(2026, 1, 5, 12, 5, tzinfo=UTC)  # 5min ずれ
        raw = AuxBundle(aux_pair_mid_index={"EUR_USD": _mid_series((ts1, 1.1))})
        aligned = raw.align_to([_make_bar(ts1_off)])
        assert np.isnan(aligned.aux_pair_mid_close["EUR_USD"][0])

    def test_empty_raw_all_nan(self) -> None:
        """T107: raw 空 (pair_not_found) → 全 NaN."""
        from src.alpha_factory.aux_loader import _empty_aux_pair_mid_series

        raw = AuxBundle(aux_pair_mid_index={"EUR_USD": _empty_aux_pair_mid_series()})
        ts1 = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
        aligned = raw.align_to([_make_bar(ts1)])
        assert np.isnan(aligned.aux_pair_mid_close["EUR_USD"][0])

    def test_aligned_mid_is_read_only(self) -> None:
        """T107: 整列後 mid 配列は read-only."""
        ts1 = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
        raw = AuxBundle(aux_pair_mid_index={"EUR_USD": _mid_series((ts1, 1.1))})
        aligned = raw.align_to([_make_bar(ts1)])
        assert aligned.aux_pair_mid_close["EUR_USD"].flags.writeable is False

    def test_empty_bars_returns_empty(self) -> None:
        """T107: 空 bars → 空 aux_pair_mid_close."""
        ts1 = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
        raw = AuxBundle(aux_pair_mid_index={"EUR_USD": _mid_series((ts1, 1.1))})
        aligned = raw.align_to([])
        assert aligned.aux_pair_mid_close == {}

    def test_pickle_roundtrip_refreezes(self) -> None:
        """T107: pickle 復元後も read-only が維持される (__setstate__ re-freeze)."""
        ts1 = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
        series = _mid_series((ts1, 1.1), (datetime(2026, 1, 5, 13, 0, tzinfo=UTC), 1.2))
        restored = pickle.loads(pickle.dumps(series))
        assert np.array_equal(restored.ts_epoch_ns, series.ts_epoch_ns)
        assert np.array_equal(restored.mid_close, series.mid_close)
        assert restored.ts_epoch_ns.flags.writeable is False
        assert restored.mid_close.flags.writeable is False


# ---------------------------------------------------------------------------
# V14: AuxAlignmentCache
# ---------------------------------------------------------------------------


class TestAuxAlignmentCache:
    def test_returns_same_instance_for_same_bars(self) -> None:
        """V14 key: 同 bars / 同 as_of_strict → 同 instance."""
        observations = [
            DailyObservation(
                observation_date=date(2026, 1, 1),
                value=11.0,
                effective_from_utc=datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
            ),
        ]
        raw = AuxBundle(daily_series={"VIXCLS": observations})
        cache = AuxAlignmentCache(raw)
        bars = _make_bars(datetime(2026, 1, 5, tzinfo=UTC), count=5)
        a1 = cache.get(bars)
        a2 = cache.get(bars)
        assert a1 is a2

    def test_different_bars_yield_different_entries(self) -> None:
        """V14 key: bars が違うと別 cache entry."""
        raw = AuxBundle()
        cache = AuxAlignmentCache(raw)
        bars1 = _make_bars(datetime(2026, 1, 5, tzinfo=UTC), count=5)
        bars2 = _make_bars(datetime(2026, 1, 5, tzinfo=UTC), count=10)
        a1 = cache.get(bars1)
        a2 = cache.get(bars2)
        assert a1 is not a2

    def test_reset_invalidates_cache(self) -> None:
        """V14 invalidation: reset() で cache クリア."""
        raw = AuxBundle()
        cache = AuxAlignmentCache(raw)
        bars = _make_bars(datetime(2026, 1, 5, tzinfo=UTC), count=5)
        a1 = cache.get(bars)
        cache.reset()
        a2 = cache.get(bars)
        assert a1 is not a2  # 再構築


# ---------------------------------------------------------------------------
# pickle (Gate C 先取り; AlignedAuxBundle が multiprocessing で破壊されないこと)
# ---------------------------------------------------------------------------


def test_aligned_aux_bundle_picklable_for_multiprocessing() -> None:
    """worker 並列で broadcast されるため pickle round-trip が可能であること."""
    observations = [
        DailyObservation(
            observation_date=date(2026, 1, 1),
            value=11.0,
            effective_from_utc=datetime(2026, 1, 2, 0, 0, tzinfo=UTC),
        ),
    ]
    raw = AuxBundle(daily_series={"VIXCLS": observations})
    bars = _make_bars(datetime(2026, 1, 5, tzinfo=UTC), count=5)
    aligned = raw.align_to(bars)
    blob = pickle.dumps(aligned)
    restored = pickle.loads(blob)
    assert isinstance(restored, AlignedAuxBundle)
    assert np.array_equal(
        restored.aux_series["macro.vix"], aligned.aux_series["macro.vix"]
    )


# ---------------------------------------------------------------------------
# DB readers (Gate B)
# ---------------------------------------------------------------------------


class TestLoadDailySeriesFromDb:
    def test_filters_by_period(self, sqlite_session) -> None:
        rows = [
            MacroIndexDaily(
                series_id="VIXCLS",
                date=date(2026, 1, 1),
                value=Decimal("10.0"),
                fetched_at=datetime(2026, 1, 2, tzinfo=UTC),
            ),
            MacroIndexDaily(
                series_id="VIXCLS",
                date=date(2026, 2, 15),
                value=Decimal("12.0"),
                fetched_at=datetime(2026, 2, 16, tzinfo=UTC),
            ),
            MacroIndexDaily(
                series_id="VIXCLS",
                date=date(2026, 3, 1),
                value=Decimal("14.0"),
                fetched_at=datetime(2026, 3, 2, tzinfo=UTC),
            ),
        ]
        sqlite_session.add_all(rows)
        sqlite_session.commit()
        out = load_daily_series_from_db(
            db_session=sqlite_session,
            series_id="VIXCLS",
            period=(
                datetime(2026, 2, 1, tzinfo=UTC),
                datetime(2026, 2, 28, tzinfo=UTC),
            ),
        )
        # period[0] 側に max_policy_lag_days+7=42 日 buffer があるので、
        # 2026-02-01 - 42 days = 2025-12-21 以降の rows がすべて入る
        # → 3 行全部入るが、period[1]=2026-02-28 で end filter かかるので 2 行
        assert len(out) == 2
        assert out[0].value == 10.0
        assert out[1].value == 12.0

    def test_orders_by_date_ascending(self, sqlite_session) -> None:
        rows = [
            MacroIndexDaily(
                series_id="VIXCLS",
                date=date(2026, 1, 3),
                value=Decimal("3.0"),
                fetched_at=datetime(2026, 1, 4, tzinfo=UTC),
            ),
            MacroIndexDaily(
                series_id="VIXCLS",
                date=date(2026, 1, 1),
                value=Decimal("1.0"),
                fetched_at=datetime(2026, 1, 2, tzinfo=UTC),
            ),
            MacroIndexDaily(
                series_id="VIXCLS",
                date=date(2026, 1, 2),
                value=Decimal("2.0"),
                fetched_at=datetime(2026, 1, 3, tzinfo=UTC),
            ),
        ]
        sqlite_session.add_all(rows)
        sqlite_session.commit()
        out = load_daily_series_from_db(
            db_session=sqlite_session,
            series_id="VIXCLS",
            period=(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 31, tzinfo=UTC),
            ),
        )
        assert [o.value for o in out] == [1.0, 2.0, 3.0]

    def test_skips_null_values(self, sqlite_session) -> None:
        rows = [
            MacroIndexDaily(
                series_id="VIXCLS",
                date=date(2026, 1, 1),
                value=Decimal("1.0"),
                fetched_at=datetime(2026, 1, 2, tzinfo=UTC),
            ),
            MacroIndexDaily(
                series_id="VIXCLS",
                date=date(2026, 1, 2),
                value=None,  # NULL は skip
                fetched_at=datetime(2026, 1, 3, tzinfo=UTC),
            ),
            MacroIndexDaily(
                series_id="VIXCLS",
                date=date(2026, 1, 3),
                value=Decimal("3.0"),
                fetched_at=datetime(2026, 1, 4, tzinfo=UTC),
            ),
        ]
        sqlite_session.add_all(rows)
        sqlite_session.commit()
        out = load_daily_series_from_db(
            db_session=sqlite_session,
            series_id="VIXCLS",
            period=(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 31, tzinfo=UTC),
            ),
        )
        assert [o.value for o in out] == [1.0, 3.0]


# ---------------------------------------------------------------------------
# V15: aux_pair_bars duplicate normalize fail-fast
# ---------------------------------------------------------------------------


class TestAuxPairBarsLoader:
    def _add_pair(self, session, oanda_name: str) -> CurrencyPair:
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
        session.commit()
        return pair

    def _add_bar(
        self, session, pair_id: int, bar_time: datetime
    ) -> PriceBarM1:
        row = PriceBarM1(
            pair_id=pair_id,
            bar_time=bar_time,
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
        session.add(row)
        session.commit()
        return row

    def test_returns_columnar_mid_series(self, sqlite_session) -> None:
        pair = self._add_pair(sqlite_session, "EUR_USD")
        ts = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
        self._add_bar(sqlite_session, pair.id, ts)
        index = load_aux_pair_mid_index(
            db_session=sqlite_session,
            pairs=["EUR_USD"],
            period=(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 31, tzinfo=UTC),
            ),
        )
        assert "EUR_USD" in index
        series = index["EUR_USD"]
        assert series.ts_epoch_ns.tolist() == [_to_epoch_ns(ts)]
        # mid = (1.0 + 1.01)/2
        assert series.mid_close.tolist() == [1.005]
        # read-only 契約
        assert series.ts_epoch_ns.flags.writeable is False
        assert series.mid_close.flags.writeable is False

    def test_missing_pair_returns_empty_series(self, sqlite_session) -> None:
        index = load_aux_pair_mid_index(
            db_session=sqlite_session,
            pairs=["NOPE_NOPE"],
            period=(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 31, tzinfo=UTC),
            ),
        )
        assert index["NOPE_NOPE"].ts_epoch_ns.size == 0
        assert index["NOPE_NOPE"].mid_close.size == 0

    def test_duplicate_minute_raises(self, sqlite_session) -> None:
        """V15 + monotonic/unique: 同 minute に複数 row があれば fail-fast."""
        pair = self._add_pair(sqlite_session, "EUR_USD")
        ts1 = datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC)
        ts2 = datetime(2026, 1, 5, 12, 0, 30, tzinfo=UTC)  # 同 minute (秒違い)
        self._add_bar(sqlite_session, pair.id, ts1)
        self._add_bar(sqlite_session, pair.id, ts2)
        with pytest.raises(ValueError, match="non-monotonic/duplicate"):
            load_aux_pair_mid_index(
                db_session=sqlite_session,
                pairs=["EUR_USD"],
                period=(
                    datetime(2026, 1, 1, tzinfo=UTC),
                    datetime(2026, 1, 31, tzinfo=UTC),
                ),
            )

    def test_no_identity_map_pollution(self, sqlite_session) -> None:
        """T106/T107: column-tuple streaming は caller session の identity map に
        PriceBarM1 entity を積まない (ORM entity 経路廃止の契約)."""
        pair = self._add_pair(sqlite_session, "EUR_USD")
        for minute in range(5):
            self._add_bar(
                sqlite_session,
                pair.id,
                datetime(2026, 1, 5, 12, minute, tzinfo=UTC),
            )
        # add/commit 後の identity map を expire してクリーンにする
        sqlite_session.expunge_all()
        load_aux_pair_mid_index(
            db_session=sqlite_session,
            pairs=["EUR_USD"],
            period=(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 31, tzinfo=UTC),
            ),
        )
        loaded_bar_rows = [
            obj
            for obj in sqlite_session.identity_map.values()
            if isinstance(obj, PriceBarM1)
        ]
        assert loaded_bar_rows == []

    def test_stream_aux_pair_mid_closes_result_on_v15_raise(self) -> None:
        """T106/T107: V15 早期 ValueError でも result.close()."""

        class _SpyResult:
            def __init__(self, rows: list[object]) -> None:
                self._rows = rows
                self.closed = False

            def __iter__(self):
                return iter(self._rows)

            def close(self) -> None:
                self.closed = True

        class _SpySession:
            def __init__(self, result: object) -> None:
                self.result = result

            def execute(self, stmt: object) -> object:
                return self.result

        # 同 minute (秒違い) の 2 row → normalize 後重複 → V15 raise
        from types import SimpleNamespace

        def _row(sec: int):
            return SimpleNamespace(
                bar_time=datetime(2026, 1, 5, 12, 0, sec, tzinfo=UTC),
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

        result = _SpyResult([_row(0), _row(30)])
        session = _SpySession(result)
        from src.alpha_factory.aux_loader import _stream_aux_pair_mid

        with pytest.raises(ValueError, match="non-monotonic/duplicate"):
            _stream_aux_pair_mid(
                session,  # type: ignore[arg-type]
                pair_db_id=1,
                pair_name="EUR_USD",
                start=datetime(2026, 1, 1, tzinfo=UTC),
                end=datetime(2026, 1, 31, tzinfo=UTC),
            )
        assert result.closed is True


# ---------------------------------------------------------------------------
# Build aux bundle from db (smoke)
# ---------------------------------------------------------------------------


class TestBuildAuxBundleFromDb:
    def test_returns_aux_bundle_with_daily_series(self, sqlite_session) -> None:
        sqlite_session.add(
            MacroIndexDaily(
                series_id="VIXCLS",
                date=date(2026, 1, 1),
                value=Decimal("15.0"),
                fetched_at=datetime(2026, 1, 2, tzinfo=UTC),
            )
        )
        sqlite_session.commit()
        bundle = build_aux_bundle_from_db(
            db_session=sqlite_session,
            period=(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 31, tzinfo=UTC),
            ),
            series_ids=["VIXCLS"],
        )
        assert "VIXCLS" in bundle.daily_series
        assert len(bundle.daily_series["VIXCLS"]) == 1
        # vix_snapshot は VIXCLS から自動生成される
        assert bundle.vix_snapshot is not None

    def test_db_build_to_align_to_p5_integration(self, sqlite_session) -> None:
        """T107 (Critical 1): DB build → align_to → P5 の end-to-end 統合。

        aux pair (EUR_USD/USD_JPY) を DB に入れ、 build_aux_bundle_from_db で
        columnar 構築 → align_to で EUR_JPY target bars に整列 → P5 が動くこと。
        契約移行で経路が壊れていないことを保証する。
        """
        from src.alpha_factory.primitives._base import EvaluationContext
        from src.alpha_factory.primitives.pair_specific import P5_SPEC

        # aux pair を 2 本 (EUR_USD/USD_JPY) DB 登録
        loader = TestAuxPairBarsLoader()
        eu_pair = loader._add_pair(sqlite_session, "EUR_USD")
        uj_pair = loader._add_pair(sqlite_session, "USD_JPY")
        target_bars = _make_bars(
            datetime(2026, 1, 5, 12, 0, tzinfo=UTC), count=80, step_minutes=60
        )
        for tb in target_bars:
            loader._add_bar(sqlite_session, eu_pair.id, tb.bar_time)
            loader._add_bar(sqlite_session, uj_pair.id, tb.bar_time)
        bundle = build_aux_bundle_from_db(
            db_session=sqlite_session,
            period=(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 2, 1, tzinfo=UTC),
            ),
            series_ids=[],
            aux_pairs=["EUR_USD", "USD_JPY"],
        )
        assert "EUR_USD" in bundle.aux_pair_mid_index
        aligned = bundle.align_to(target_bars)
        eu = aligned.aux_pair_mid_close["EUR_USD"]
        uj = aligned.aux_pair_mid_close["USD_JPY"]
        assert len(eu) == len(target_bars)
        # 全 bar exact-match (DB と target が同 bar_time) → NaN なし
        assert not np.isnan(eu).any()
        assert not np.isnan(uj).any()
        # P5 が動く (mid = (1.0+1.01)/2 = 1.005 一定)
        ctx = EvaluationContext(
            bars=target_bars,
            idx=79,
            pair="EUR_JPY",
            params={"z_n": 60, "scale": 2.0},
            aux_pair_mid_close={"EUR_USD": eu, "USD_JPY": uj},
        )
        out = P5_SPEC.compute_all_bars(ctx)
        assert out.shape == (len(target_bars),)


# ---------------------------------------------------------------------------
# series_id_to_aux_key
# ---------------------------------------------------------------------------


def test_series_id_to_aux_key_known() -> None:
    assert series_id_to_aux_key("VIXCLS") == "macro.vix"
    assert series_id_to_aux_key("DTWEXBGS") == "macro.dxy"
    assert series_id_to_aux_key("PCOPPUSDM") == "macro.copper"
    assert series_id_to_aux_key("PALLFNFINDEXM") == "macro.commodity_index"
    assert series_id_to_aux_key("SP500") == "macro.spx500"


def test_series_id_to_aux_key_unknown_falls_back() -> None:
    assert series_id_to_aux_key("UNKNOWN") == "macro.unknown"
