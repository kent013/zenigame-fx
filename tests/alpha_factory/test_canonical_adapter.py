"""B Phase 2 切替コミット step 1: canonical_adapter unit test.

設計参照: devnotes/20260503-1024-B-phase2-step1-canonical-metrics/detailed-design.md § 4.4

8 ケース minimum (Codex Round 1 [Warning] 5 + Round 2 [Suggestion] 取込):
- test 1: trade_to_trade_record_basic (= session_bucket / business_day_index 正確)
- test 2: trade_to_trade_record_preserves_spread_cost (= T078 broker → float 1e-9 以内)
- test 3: trade_to_trade_record_business_day_index_monotone_within_period
- test 4: equity_curve_to_bar_equity_series_basic
- test 5: equity_curve_to_bar_equity_series_strict_monotone_violation_raises
- test 6: business_day_universe_from_bars_includes_all_buckets
- test 7: business_day_universe_includes_empty_blocks_when_no_trades (Codex [W5])
- test 8: default_false_flags_set_for_step_1 (Codex [W5])
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.alpha_factory.canonical_adapter import (
    BUSINESS_DAY_EPOCH,
    compute_business_day_universe_from_bars,
    equity_curve_to_bar_equity_series,
    trade_to_trade_record,
)
from src.alpha_factory.canonical_metrics import (
    BarEquityInvalidError,
    SessionBucket,
)
from src.broker.orders import Trade as BrokerTrade
from src.domain.price import Ohlc, PriceBar

# --- helpers ----------------------------------------------------------------


def _broker_trade(
    *,
    position_id: int = 1,
    side: str = "long",
    entry_time: datetime,
    exit_time: datetime,
    pnl: Decimal = Decimal("100"),
    spread_cost: Decimal = Decimal("0"),
    holding_cost: Decimal = Decimal("0"),
) -> BrokerTrade:
    return BrokerTrade(
        position_id=position_id,
        instrument="USD_JPY",
        side=side,  # type: ignore[arg-type]
        units=1000,
        entry_price=Decimal("150.00"),
        entry_time=entry_time,
        exit_price=Decimal("150.10"),
        exit_time=exit_time,
        pnl=pnl,
        exit_reason="signal",  # type: ignore[arg-type]
        equity_at_entry=Decimal("1000000"),
        spread_cost=spread_cost,
        holding_cost=holding_cost,
    )


def _price_bar(bar_time: datetime) -> PriceBar:
    bid = Decimal("150.00")
    ask = Decimal("150.01")
    return PriceBar(
        pair_name="USD_JPY",
        bar_time=bar_time,
        bid=Ohlc(bid, bid, bid, bid),
        ask=Ohlc(ask, ask, ask, ask),
        volume=10,
        complete=True,
    )


# --- test 1: trade_to_trade_record_basic ------------------------------------


def test_trade_to_trade_record_basic() -> None:
    """broker.Trade → TradeRecord 変換、 session_bucket / business_day_index が
    UTC date scheme で算出される (= Codex Round 2 [Suggestion] 2 取込で固定)."""
    # exit_time UTC 12:00 = LONDON bucket (= [8, 16) UTC hour 範囲)
    entry = datetime(2026, 1, 5, 11, 30, tzinfo=UTC)
    exit = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
    bt = _broker_trade(entry_time=entry, exit_time=exit)

    record = trade_to_trade_record(bt)

    assert record.session_bucket == SessionBucket.LONDON
    # business_day_index = (2026-01-05 - 1970-01-01).days = 20458
    assert record.business_day_index == (exit.date() - BUSINESS_DAY_EPOCH).days
    assert record.entry_time_utc == entry
    assert record.exit_time_utc == exit
    assert record.pnl_net == 100.0
    # step 1 では default False (= broker engine 経由伝搬は別 step)
    assert record.is_session_close_drop is False
    assert record.is_negative_equity_drop_open is False


# --- test 2: spread_cost / holding_cost preserve (T078) ----------------------


def test_trade_to_trade_record_preserves_spread_cost() -> None:
    """T078 broker.spread_cost / holding_cost が Decimal → float 変換で
    1e-9 以内の精度で伝搬される."""
    entry = datetime(2026, 1, 5, 11, 30, tzinfo=UTC)
    exit = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
    bt = _broker_trade(
        entry_time=entry,
        exit_time=exit,
        spread_cost=Decimal("2.5"),
        holding_cost=Decimal("1.25"),
    )

    record = trade_to_trade_record(bt)

    assert record.spread_cost == pytest.approx(2.5, abs=1e-9)
    assert record.holding_cost == pytest.approx(1.25, abs=1e-9)


# --- test 3: business_day_index monotone within period -----------------------


def test_trade_to_trade_record_business_day_index_monotone_within_period() -> None:
    """同一期間内で trade を時系列順に並べると business_day_index も monotone increasing
    (= UTC date encoding の妥当性、 Codex Round 2 [Suggestion] 2 取込)."""
    times = [
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        datetime(2026, 1, 2, 12, 0, tzinfo=UTC),
        datetime(2026, 1, 3, 12, 0, tzinfo=UTC),
        datetime(2026, 1, 5, 12, 0, tzinfo=UTC),  # 1 day skip OK
    ]
    indices = []
    for exit_t in times:
        entry_t = exit_t.replace(hour=11)
        bt = _broker_trade(entry_time=entry_t, exit_time=exit_t)
        record = trade_to_trade_record(bt)
        indices.append(record.business_day_index)
    # 全 monotone non-decreasing
    assert indices == sorted(indices)
    # 1-day diff は 1
    assert indices[1] - indices[0] == 1
    # 2-day skip (2026-01-03 → 2026-01-05) は 2
    assert indices[3] - indices[2] == 2


# --- test 4: equity_curve_to_bar_equity_series ------------------------------


def test_equity_curve_to_bar_equity_series_basic() -> None:
    """equity_curve (timestamp UTC, equity Decimal) → BarEquitySeries 変換."""
    equity_curve = [
        (datetime(2026, 1, 5, 12, 0, tzinfo=UTC), Decimal("1000000")),
        (datetime(2026, 1, 5, 12, 1, tzinfo=UTC), Decimal("1000100")),
        (datetime(2026, 1, 5, 12, 2, tzinfo=UTC), Decimal("999900")),
    ]
    series = equity_curve_to_bar_equity_series(equity_curve)
    assert len(series.points) == 3
    assert series.points[0].equity == 1000000.0
    assert series.points[1].equity == 1000100.0
    assert series.points[2].equity == 999900.0


# --- test 5: equity_curve_to_bar_equity_series strict_monotone violation ----


def test_equity_curve_to_bar_equity_series_strict_monotone_violation_raises() -> None:
    """equity_curve に重複 / 逆順 timestamp があると BarEquityInvalidError raise."""
    bad_curve = [
        (datetime(2026, 1, 5, 12, 0, tzinfo=UTC), Decimal("1000000")),
        (datetime(2026, 1, 5, 12, 0, tzinfo=UTC), Decimal("1000100")),  # 重複
    ]
    with pytest.raises(BarEquityInvalidError, match="strictly monotone"):
        equity_curve_to_bar_equity_series(bad_curve)


# --- test 6: business_day_universe_from_bars all buckets --------------------


def test_business_day_universe_from_bars_includes_all_buckets() -> None:
    """bars が触れた全 (bucket, day) を universe に含む、 必ず 3 bucket key 全件."""
    bars = [
        # TOKYO: hour 0-7
        _price_bar(datetime(2026, 1, 5, 3, 0, tzinfo=UTC)),
        # LONDON: hour 8-15
        _price_bar(datetime(2026, 1, 5, 12, 0, tzinfo=UTC)),
        # NY: hour 16-23
        _price_bar(datetime(2026, 1, 5, 20, 0, tzinfo=UTC)),
    ]
    universe = compute_business_day_universe_from_bars(bars)
    # 3 bucket key 全件
    assert set(universe.keys()) == {
        SessionBucket.TOKYO,
        SessionBucket.LONDON,
        SessionBucket.NY,
    }
    expected_day = (bars[0].bar_time.date() - BUSINESS_DAY_EPOCH).days
    assert expected_day in universe[SessionBucket.TOKYO]
    assert expected_day in universe[SessionBucket.LONDON]
    assert expected_day in universe[SessionBucket.NY]


# --- test 7: empty blocks included when no trades (Codex [W5]) --------------


def test_business_day_universe_includes_empty_blocks_when_no_trades() -> None:
    """trades が 1 bucket のみ集中していても、 bars が触れた他 bucket × day も
    universe に含まれる (= synthesis § 6.3 WR neutral 0.5 が発動可能、
    Codex Round 1 [Critical] 1 取込の検証)."""
    bars = [
        # 1 day 全 3 bucket (= 全 bucket × 全 day を universe にカバー)
        _price_bar(datetime(2026, 1, 5, 3, 0, tzinfo=UTC)),  # TOKYO
        _price_bar(datetime(2026, 1, 5, 12, 0, tzinfo=UTC)),  # LONDON
        _price_bar(datetime(2026, 1, 5, 20, 0, tzinfo=UTC)),  # NY
    ]
    # trades が空 (= 全 bucket × 全 day で trade_count_block=0)
    universe = compute_business_day_universe_from_bars(bars)
    expected_day = (bars[0].bar_time.date() - BUSINESS_DAY_EPOCH).days
    # universe 各 bucket に day が存在 (= WR 計算で trade_count_block=0 → neutral 0.5)
    assert expected_day in universe[SessionBucket.TOKYO]
    assert expected_day in universe[SessionBucket.LONDON]
    assert expected_day in universe[SessionBucket.NY]


# --- test 8: default_false flags step 1 範囲 (Codex [W5]) -------------------


def test_default_false_flags_set_for_step_1() -> None:
    """trade_to_trade_record で is_session_close_drop / is_negative_equity_drop_open
    が default False で設定される (= step 1 では broker engine 経由伝搬未実装、
    caller 側で flags_source="default_false" を log する責務)."""
    entry = datetime(2026, 1, 5, 11, 30, tzinfo=UTC)
    exit = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
    bt = _broker_trade(entry_time=entry, exit_time=exit)
    record = trade_to_trade_record(bt)
    # step 1 では常に False (= broker.Trade に対応 field なし)
    assert record.is_session_close_drop is False
    assert record.is_negative_equity_drop_open is False


# --- test 9 (boundary): business_day_index < 0 raises (Codex impl-review [W]) ---


def test_business_day_index_below_epoch_raises() -> None:
    """1970-01-01 以前のデータが流入すると ValueError raise (= canonical_metrics
    business_day_index >= 0 契約違反を caller 側で発見可能、 Codex impl-review
    Round 1 [Warning] 取込)."""
    pre_epoch_entry = datetime(1969, 12, 31, 11, 0, tzinfo=UTC)
    pre_epoch_exit = datetime(1969, 12, 31, 12, 0, tzinfo=UTC)
    bt = _broker_trade(entry_time=pre_epoch_entry, exit_time=pre_epoch_exit)
    with pytest.raises(ValueError, match="business_day_index must be >= 0"):
        trade_to_trade_record(bt)
