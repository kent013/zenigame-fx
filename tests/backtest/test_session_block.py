"""SessionBlock + spread stress unit tests (T070 cascade port v2 Phase 2 配線).

詳細設計 §5.1 / §7 の F1, F3, F5, F6, F7, F11, F12, F15, F18, F22 を 1:1 で
対応する unit test 群。 設計 SSOT との対応は各 test docstring に記述.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.backtest.session_block import (
    BLOCK_BUCKET_RANGES_UTC,
    SessionBlock,
    aggregate_session_blocks,
    apply_spread_stress,
    compute_bucket_for_bar,
    compute_bucket_for_trade,
)
from src.broker.orders import Trade
from src.domain.price import Ohlc, PriceBar

# -- helpers ------------------------------------------------------------


def _make_bar(bar_time: datetime, *, close: str = "1.1000") -> PriceBar:
    """Test 用 minimal PriceBar (USD-quote spread = 0.0001 程度)."""
    bid_close = Decimal(close)
    ask_close = bid_close + Decimal("0.0002")
    return PriceBar(
        pair_name="EUR_USD",
        bar_time=bar_time,
        bid=Ohlc(open=bid_close, high=bid_close, low=bid_close, close=bid_close),
        ask=Ohlc(open=ask_close, high=ask_close, low=ask_close, close=ask_close),
        volume=10,
        complete=True,
    )


def _make_bars_for_full_day(d: date) -> list[PriceBar]:
    """1 day × 1440 minutes = 1440 bars (M1) を全部生成."""
    base = datetime(d.year, d.month, d.day, 0, 0, tzinfo=UTC)
    return [_make_bar(base + timedelta(minutes=m)) for m in range(1440)]


def _make_trade(
    *,
    exit_time: datetime,
    pnl: Decimal,
    spread_cost: Decimal = Decimal(0),
    holding_cost: Decimal = Decimal(0),
) -> Trade:
    return Trade(
        position_id=1,
        instrument="EUR_USD",
        side="long",
        units=10000,
        entry_price=Decimal("1.1000"),
        entry_time=exit_time - timedelta(hours=1),
        exit_price=Decimal("1.1010"),
        exit_time=exit_time,
        pnl=pnl,
        exit_reason="signal",
        spread_cost=spread_cost,
        holding_cost=holding_cost,
    )


# -- F1 / F2 / F18: bucket 割当 + tz validation -----------------------------


class TestComputeBucketForBar:
    """F1 / F18: hour 範囲ごとの bucket 割当 + tz validation."""

    def test_F1_bucket_assignment_at_tokyo(self) -> None:
        # F1 / F3: hour 0-7 → tokyo
        for h in range(0, 8):
            t = datetime(2024, 1, 15, h, 0, tzinfo=UTC)
            assert compute_bucket_for_bar(t) == "tokyo"

    def test_F1_bucket_assignment_at_london(self) -> None:
        for h in range(8, 16):
            t = datetime(2024, 1, 15, h, 0, tzinfo=UTC)
            assert compute_bucket_for_bar(t) == "london"

    def test_F1_bucket_assignment_at_ny(self) -> None:
        for h in range(16, 24):
            t = datetime(2024, 1, 15, h, 0, tzinfo=UTC)
            assert compute_bucket_for_bar(t) == "ny"

    def test_F18_naive_datetime_raises(self) -> None:
        # F18: naive datetime は reject
        with pytest.raises(ValueError, match="timezone-aware"):
            compute_bucket_for_bar(datetime(2024, 1, 15, 12, 0))

    def test_F18_non_utc_offset_raises(self) -> None:
        # F18: JST (UTC+9) は reject
        jst = timezone(timedelta(hours=9))
        with pytest.raises(ValueError, match="UTC offset"):
            compute_bucket_for_bar(datetime(2024, 1, 15, 12, 0, tzinfo=jst))


class TestComputeBucketForTrade:
    """F4 / F16: trade.exit_time 基準で bucket 割当."""

    def test_exit_time_based_attribution(self) -> None:
        # entry_time が london、 exit_time が tokyo の trade は tokyo 帰属
        trade = _make_trade(
            exit_time=datetime(2024, 1, 15, 4, 0, tzinfo=UTC),
            pnl=Decimal(10),
        )
        assert compute_bucket_for_trade(trade) == "tokyo"


# -- F6 / F11: SessionBlock invariants -------------------------------------


class TestSessionBlockInvariants:
    """F6 / F11: SessionBlock の不変条件 (__post_init__ で raise)."""

    def test_F6_invariant_violation_raises(self) -> None:
        # F6: pnl_before_costs != pnl_net + spread + holding で raise
        with pytest.raises(ValueError, match="pnl_before_costs"):
            SessionBlock(
                business_date=date(2024, 1, 15),
                bucket="tokyo",
                bar_count=480,
                trade_count=0,
                pnl_net=Decimal(0),
                pnl_before_costs=Decimal(100),  # 不整合
                spread_cost_total=Decimal(0),
                holding_cost_total=Decimal(0),
            )

    def test_F11_negative_bar_count_raises(self) -> None:
        # F11: bar_count >= 0
        with pytest.raises(ValueError, match="bar_count"):
            SessionBlock(
                business_date=date(2024, 1, 15),
                bucket="tokyo",
                bar_count=-1,
                trade_count=0,
                pnl_net=Decimal(0),
                pnl_before_costs=Decimal(0),
                spread_cost_total=Decimal(0),
                holding_cost_total=Decimal(0),
            )

    def test_F11_negative_trade_count_raises(self) -> None:
        with pytest.raises(ValueError, match="trade_count"):
            SessionBlock(
                business_date=date(2024, 1, 15),
                bucket="tokyo",
                bar_count=0,
                trade_count=-1,
                pnl_net=Decimal(0),
                pnl_before_costs=Decimal(0),
                spread_cost_total=Decimal(0),
                holding_cost_total=Decimal(0),
            )

    def test_F11_negative_spread_cost_total_raises(self) -> None:
        with pytest.raises(ValueError, match="spread_cost_total"):
            SessionBlock(
                business_date=date(2024, 1, 15),
                bucket="tokyo",
                bar_count=0,
                trade_count=0,
                pnl_net=Decimal(0),
                pnl_before_costs=Decimal(-1),
                spread_cost_total=Decimal(-1),
                holding_cost_total=Decimal(0),
            )

    def test_F11_negative_holding_cost_total_raises(self) -> None:
        with pytest.raises(ValueError, match="holding_cost_total"):
            SessionBlock(
                business_date=date(2024, 1, 15),
                bucket="tokyo",
                bar_count=0,
                trade_count=0,
                pnl_net=Decimal(0),
                pnl_before_costs=Decimal(-1),
                spread_cost_total=Decimal(0),
                holding_cost_total=Decimal(-1),
            )

    def test_F11_property_is_empty_trade_block(self) -> None:
        block = SessionBlock(
            business_date=date(2024, 1, 15),
            bucket="tokyo",
            bar_count=480,
            trade_count=0,
            pnl_net=Decimal(0),
            pnl_before_costs=Decimal(0),
            spread_cost_total=Decimal(0),
            holding_cost_total=Decimal(0),
        )
        assert block.is_empty_trade_block is True
        assert block.is_partial_bar_block is False

    def test_F11_property_is_partial_bar_block(self) -> None:
        block = SessionBlock(
            business_date=date(2024, 1, 15),
            bucket="tokyo",
            bar_count=200,
            trade_count=0,
            pnl_net=Decimal(0),
            pnl_before_costs=Decimal(0),
            spread_cost_total=Decimal(0),
            holding_cost_total=Decimal(0),
        )
        assert block.is_partial_bar_block is True

    def test_F11_property_is_not_empty_when_trade_present(self) -> None:
        block = SessionBlock(
            business_date=date(2024, 1, 15),
            bucket="tokyo",
            bar_count=480,
            trade_count=1,
            pnl_net=Decimal(7),
            pnl_before_costs=Decimal(11),
            spread_cost_total=Decimal(3),
            holding_cost_total=Decimal(1),
        )
        assert block.is_empty_trade_block is False


# -- F3 / F7 / F12 / F22: aggregate_session_blocks --------------------------


class TestAggregateSessionBlocks:
    """F3 / F7 / F12 / F22: aggregate 結果の date universe / empty block / invariant."""

    def test_F7_empty_block_generated_when_no_trades(self) -> None:
        # F7: trade_count=0 でも block 生成 (synthesis § 6.3 0.5 neutral)
        bars = _make_bars_for_full_day(date(2024, 1, 15))
        blocks = aggregate_session_blocks(bars, trades=[], mode="test")
        assert len(blocks) == 3  # 1 day × 3 bucket
        assert all(b.is_empty_trade_block for b in blocks)
        # M1 full day: tokyo / london / ny = 480 bars each
        bar_counts = sorted(b.bar_count for b in blocks)
        assert bar_counts == [480, 480, 480]

    def test_F3_date_universe_from_bars(self) -> None:
        # F3: bars が触れた UTC date set × 3 bucket
        bars_d1 = _make_bars_for_full_day(date(2024, 1, 15))
        bars_d2 = _make_bars_for_full_day(date(2024, 1, 16))
        bars = bars_d1 + bars_d2
        blocks = aggregate_session_blocks(bars, trades=[], mode="test")
        assert len(blocks) == 6  # 2 dates × 3 bucket

    def test_F12_invariant_holds_for_aggregated(self) -> None:
        # F12: aggregate 結果も invariant 保持
        bars = _make_bars_for_full_day(date(2024, 1, 15))
        trades = [
            _make_trade(
                exit_time=datetime(2024, 1, 15, 4, 0, tzinfo=UTC),
                pnl=Decimal(10),
                spread_cost=Decimal(2),
                holding_cost=Decimal(1),
            )
        ]
        blocks = aggregate_session_blocks(bars, trades, mode="test")
        for b in blocks:
            assert b.pnl_before_costs == (
                b.pnl_net + b.spread_cost_total + b.holding_cost_total
            )

    def test_F22_pnl_net_uses_spread_subtraction(self) -> None:
        # F22: pnl_net = sum(t.pnl - t.spread_cost)、 §3.4.0 SSOT
        bars = _make_bars_for_full_day(date(2024, 1, 15))
        trade = _make_trade(
            exit_time=datetime(2024, 1, 15, 4, 0, tzinfo=UTC),
            pnl=Decimal(10),
            spread_cost=Decimal(3),
            holding_cost=Decimal(1),
        )
        blocks = aggregate_session_blocks(bars, [trade], mode="test")
        tokyo_block = next(
            b for b in blocks if b.bucket == "tokyo" and b.business_date == date(2024, 1, 15)
        )
        assert tokyo_block.pnl_net == Decimal(7)  # 10 - 3
        assert tokyo_block.pnl_before_costs == Decimal(11)  # 10 + 1
        assert tokyo_block.spread_cost_total == Decimal(3)
        assert tokyo_block.holding_cost_total == Decimal(1)
        assert tokyo_block.trade_count == 1

    def test_F16_exit_time_attribution_across_buckets(self) -> None:
        # F16: entry が london、 exit が tokyo の trade は tokyo に集計
        bars = _make_bars_for_full_day(date(2024, 1, 15))
        # entry_time = 10:00 (london), exit_time = 4:00 (= 翌日 4 時 を仮定すると
        # tokyo). ここでは date 同じだが exit_time の hour が tokyo 範囲にある trade.
        trade = Trade(
            position_id=1,
            instrument="EUR_USD",
            side="long",
            units=10000,
            entry_price=Decimal("1.1"),
            entry_time=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            exit_price=Decimal("1.11"),
            exit_time=datetime(2024, 1, 15, 4, 0, tzinfo=UTC),
            pnl=Decimal(5),
            exit_reason="signal",
            spread_cost=Decimal(1),
            holding_cost=Decimal(0),
        )
        blocks = aggregate_session_blocks(bars, [trade], mode="test")
        tokyo_block = next(
            b for b in blocks if b.bucket == "tokyo" and b.business_date == date(2024, 1, 15)
        )
        london_block = next(
            b for b in blocks if b.bucket == "london" and b.business_date == date(2024, 1, 15)
        )
        assert tokyo_block.trade_count == 1
        assert london_block.trade_count == 0

    def test_trade_outside_bars_date_still_contributes(self) -> None:
        # date universe は bars + trades の両方を union する SSOT.
        # bars が 2024-01-15 のみで trade.exit_time が 2024-01-16 → 16 日も出る
        bars = _make_bars_for_full_day(date(2024, 1, 15))
        trade = _make_trade(
            exit_time=datetime(2024, 1, 16, 4, 0, tzinfo=UTC),
            pnl=Decimal(2),
            spread_cost=Decimal(0),
            holding_cost=Decimal(0),
        )
        blocks = aggregate_session_blocks(bars, [trade], mode="test")
        # 2 dates × 3 buckets = 6 blocks
        assert len(blocks) == 6
        d16_tokyo = next(
            b for b in blocks
            if b.business_date == date(2024, 1, 16) and b.bucket == "tokyo"
        )
        assert d16_tokyo.trade_count == 1
        assert d16_tokyo.bar_count == 0  # bars は 2024-01-15 のみ

    def test_blocks_sorted_by_date_then_bucket_definition_order(self) -> None:
        bars = _make_bars_for_full_day(date(2024, 1, 16)) + _make_bars_for_full_day(
            date(2024, 1, 15)
        )
        blocks = aggregate_session_blocks(bars, trades=[], mode="test")
        # date 昇順 + bucket は dict insertion 順 (tokyo / london / ny)
        seq = [(b.business_date, b.bucket) for b in blocks]
        assert seq == [
            (date(2024, 1, 15), "tokyo"),
            (date(2024, 1, 15), "london"),
            (date(2024, 1, 15), "ny"),
            (date(2024, 1, 16), "tokyo"),
            (date(2024, 1, 16), "london"),
            (date(2024, 1, 16), "ny"),
        ]


# -- F5 / F22: apply_spread_stress -----------------------------------------


class TestApplySpreadStress:
    """F5 / F22: apply_spread_stress 代数的契約."""

    def test_F22_multiplier_1_is_noop(self) -> None:
        trade = _make_trade(
            exit_time=datetime(2024, 1, 15, 4, 0, tzinfo=UTC),
            pnl=Decimal(10),
            spread_cost=Decimal(2),
        )
        result = apply_spread_stress([trade], multiplier=Decimal(1))
        assert len(result) == 1
        assert result[0].pnl == Decimal(10)
        assert result[0].spread_cost == Decimal(2)
        assert result[0].holding_cost == trade.holding_cost

    def test_F22_multiplier_2_doubles_spread_cost(self) -> None:
        trade = _make_trade(
            exit_time=datetime(2024, 1, 15, 4, 0, tzinfo=UTC),
            pnl=Decimal(10),
            spread_cost=Decimal(2),
        )
        result = apply_spread_stress([trade], multiplier=Decimal(2))
        # delta_spread = 2 * (2-1) = 2
        # new_pnl = 10 - 2 = 8, new_spread_cost = 2 * 2 = 4
        assert result[0].pnl == Decimal(8)
        assert result[0].spread_cost == Decimal(4)

    def test_F22_multiplier_3_triples_spread(self) -> None:
        trade = _make_trade(
            exit_time=datetime(2024, 1, 15, 4, 0, tzinfo=UTC),
            pnl=Decimal(10),
            spread_cost=Decimal(2),
        )
        result = apply_spread_stress([trade], multiplier=Decimal(3))
        # delta_spread = 2 * (3-1) = 4, new_pnl = 10 - 4 = 6, new_spread = 2*3 = 6
        assert result[0].pnl == Decimal(6)
        assert result[0].spread_cost == Decimal(6)

    def test_F5_multiplier_below_one_raises(self) -> None:
        # F5
        trade = _make_trade(
            exit_time=datetime(2024, 1, 15, 4, 0, tzinfo=UTC),
            pnl=Decimal(10),
            spread_cost=Decimal(2),
        )
        with pytest.raises(ValueError, match=r"multiplier must be >= 1\.0"):
            apply_spread_stress([trade], multiplier=Decimal("0.5"))

    def test_F5_multiplier_nan_raises(self) -> None:
        trade = _make_trade(
            exit_time=datetime(2024, 1, 15, 4, 0, tzinfo=UTC),
            pnl=Decimal(10),
            spread_cost=Decimal(2),
        )
        with pytest.raises(ValueError, match="finite"):
            apply_spread_stress([trade], multiplier=Decimal("NaN"))

    def test_F5_multiplier_infinity_raises(self) -> None:
        trade = _make_trade(
            exit_time=datetime(2024, 1, 15, 4, 0, tzinfo=UTC),
            pnl=Decimal(10),
            spread_cost=Decimal(2),
        )
        with pytest.raises(ValueError, match="finite"):
            apply_spread_stress([trade], multiplier=Decimal("Infinity"))

    def test_empty_input_returns_empty_tuple(self) -> None:
        result = apply_spread_stress([], multiplier=Decimal(2))
        assert result == ()

    def test_zero_spread_cost_preserves_pnl(self) -> None:
        # spread_cost=0 trade は stress でも pnl 変化なし
        trade = _make_trade(
            exit_time=datetime(2024, 1, 15, 4, 0, tzinfo=UTC),
            pnl=Decimal(10),
            spread_cost=Decimal(0),
        )
        result = apply_spread_stress([trade], multiplier=Decimal(5))
        assert result[0].pnl == Decimal(10)
        assert result[0].spread_cost == Decimal(0)


# -- F15 / F18: partition invariants ---------------------------------------


class TestPartitionInvariant:
    """F15: BLOCK_BUCKET_RANGES_UTC が 24h covering / 重複なし を満たす."""

    def test_F15_block_bucket_ranges_cover_24h(self) -> None:
        # 8h × 3 = 24h covering、 重複なし
        ranges = sorted(BLOCK_BUCKET_RANGES_UTC.values())
        # 重複なし + 隣接 (連続)
        for i in range(len(ranges) - 1):
            assert ranges[i][1] == ranges[i + 1][0]
        # 24h カバー
        assert ranges[0][0] == 0
        assert ranges[-1][1] == 24

    def test_F15_no_overlap_between_buckets(self) -> None:
        # 全 hour 0-23 が exactly 1 bucket に属する
        coverage: set[int] = set()
        for _bucket, (start, end) in BLOCK_BUCKET_RANGES_UTC.items():
            for h in range(start, end):
                assert h not in coverage, f"hour {h} appears in multiple buckets"
                coverage.add(h)
        assert coverage == set(range(24))
