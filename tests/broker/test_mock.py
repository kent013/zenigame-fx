"""MockBroker._close_one の T070 拡張 unit tests.

詳細設計 §5.3 の F8 / F13 / F19 を 1:1 で対応:
    - F8: _close_one が spread_cost / holding_cost を Trade に転記
    - F13: invariant `Trade.pnl + Trade.holding_cost == raw_pnl` (price-diff pnl)
    - F19: 二重計上なし (= 既存 cash 動きが Trade.holding_cost 追加で変わらない)
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.broker import MockBroker, OrderSignal
from tests._helpers import make_bar, usd_jpy_meta


@pytest.fixture
def broker() -> MockBroker:
    b = MockBroker(instrument_meta=usd_jpy_meta())
    b.deposit(Decimal("1000000"))
    return b


def test_F8_close_one_records_spread_cost_on_trade(broker: MockBroker) -> None:
    """F8: _close_one が exit bar の spread × 2 を spread_cost に転記."""
    bar_open = make_bar(0, bid_close="154.100", ask_close="154.110")
    bar_next = make_bar(1, bid_close="154.500", ask_close="154.520")  # spread = 0.020

    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar_open)
    pos_id = broker.open_positions[0].id

    broker.submit(OrderSignal(kind="close_position", position_id=pos_id), leverage=1)
    broker.fill_pending(bar_next)

    trade = broker.trades[0]
    # spread_cost = abs(units) * (bar_next.spread_close * 2)
    expected = abs(Decimal(10000)) * bar_next.spread_close * Decimal(2)
    assert trade.spread_cost == expected


def test_F8_close_one_records_zero_holding_cost_when_no_holding_applied(
    broker: MockBroker,
) -> None:
    """F8: holding_cost を一度も apply していなければ Trade.holding_cost = 0."""
    bar_open = make_bar(0, bid_close="154.100", ask_close="154.110")
    bar_next = make_bar(1, bid_close="154.500", ask_close="154.510")

    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar_open)
    pos_id = broker.open_positions[0].id
    broker.submit(OrderSignal(kind="close_position", position_id=pos_id), leverage=1)
    broker.fill_pending(bar_next)

    trade = broker.trades[0]
    assert trade.holding_cost == Decimal(0)


def test_F8_close_one_transfers_accumulated_holding_cost(broker: MockBroker) -> None:
    """F8: apply_bar_holding_cost で累積した holding cost が Trade.holding_cost に転記."""
    bar_open = make_bar(0, bid_close="154.100", ask_close="154.110")
    bar_mid = make_bar(1, bid_close="154.150", ask_close="154.160")
    bar_close = make_bar(2, bid_close="154.500", ask_close="154.510")

    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar_open)
    pos_id = broker.open_positions[0].id
    broker.mark_to_market(bar_open)

    # bar_mid で holding cost を 1 bar 分発生させる
    cost_applied = broker.apply_bar_holding_cost(
        bar_mid, per_day_bps=Decimal("36"), bar_minutes=60
    )
    assert cost_applied > Decimal(0)

    broker.submit(OrderSignal(kind="close_position", position_id=pos_id), leverage=1)
    broker.fill_pending(bar_close)

    trade = broker.trades[0]
    # 転記の正本値
    assert trade.holding_cost == cost_applied


def test_F13_invariant_pnl_plus_holding_equals_raw_pnl(broker: MockBroker) -> None:
    """F13: invariant `Trade.pnl + Trade.holding_cost == raw_pnl` (= price-diff pnl)."""
    bar_open = make_bar(0, bid_close="154.100", ask_close="154.110")
    bar_mid = make_bar(1, bid_close="154.150", ask_close="154.160")
    bar_close = make_bar(2, bid_close="154.500", ask_close="154.510")

    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar_open)
    entry_price = broker.open_positions[0].entry_price
    pos_id = broker.open_positions[0].id
    broker.mark_to_market(bar_open)
    broker.apply_bar_holding_cost(bar_mid, per_day_bps=Decimal("36"), bar_minutes=60)
    broker.submit(OrderSignal(kind="close_position", position_id=pos_id), leverage=1)
    broker.fill_pending(bar_close)

    trade = broker.trades[0]
    # raw_pnl = units * (exit - entry) = 10000 * (154.500 - 154.110) = 3900
    # close_position の exit_kind="open" なので exit_price = bid.open = 154.500 (default)
    raw_pnl = Decimal(10000) * (trade.exit_price - entry_price)
    assert trade.pnl + trade.holding_cost == raw_pnl


def test_F19_no_double_counting_of_holding_cost(broker: MockBroker) -> None:
    """F19: 既存 cash 動きが Trade.holding_cost 追加で変わらない (二重計上防御).

    apply_bar_holding_cost で cash から控除済 → close 時に追加 cash 操作を行わず、
    Trade.holding_cost は記録のみ。 cash 最終値 = initial + raw_pnl - holding_cost.
    """
    initial_cash = broker.cash

    bar_open = make_bar(0, bid_close="154.100", ask_close="154.110")
    bar_mid = make_bar(1, bid_close="154.150", ask_close="154.160")
    bar_close = make_bar(2, bid_close="154.500", ask_close="154.510")

    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar_open)
    entry_price = broker.open_positions[0].entry_price
    pos_id = broker.open_positions[0].id
    broker.mark_to_market(bar_open)
    holding_applied = broker.apply_bar_holding_cost(
        bar_mid, per_day_bps=Decimal("36"), bar_minutes=60
    )
    broker.submit(OrderSignal(kind="close_position", position_id=pos_id), leverage=1)
    broker.fill_pending(bar_close)

    trade = broker.trades[0]
    raw_pnl = Decimal(10000) * (trade.exit_price - entry_price)
    expected_cash = initial_cash + raw_pnl - holding_applied
    assert broker.cash == expected_cash
    # Trade.holding_cost の追加は cash 操作を一切伴わない (= 記録のみ)
    assert trade.holding_cost == holding_applied


def test_F8_negative_spread_clamped_to_zero() -> None:
    """spread_close < 0 の異常 bar (bid > ask) でも spread_cost >= 0 invariant を維持."""
    from src.domain.price import Ohlc, PriceBar

    broker_local = MockBroker(instrument_meta=usd_jpy_meta())
    broker_local.deposit(Decimal("1000000"))
    bar_open = make_bar(0, bid_close="154.100", ask_close="154.110")
    # 異常: bid > ask な bar (spread_close = -0.005)
    bad_bar = PriceBar(
        pair_name="USD_JPY",
        bar_time=datetime(2026, 4, 1, 0, 1, tzinfo=UTC),
        bid=Ohlc(
            open=Decimal("154.500"),
            high=Decimal("154.510"),
            low=Decimal("154.500"),
            close=Decimal("154.510"),
        ),
        ask=Ohlc(
            open=Decimal("154.500"),
            high=Decimal("154.505"),
            low=Decimal("154.500"),
            close=Decimal("154.505"),
        ),
        volume=10,
        complete=True,
    )

    broker_local.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker_local.fill_pending(bar_open)
    pos_id = broker_local.open_positions[0].id
    broker_local.submit(
        OrderSignal(kind="close_position", position_id=pos_id), leverage=1
    )
    broker_local.fill_pending(bad_bar)

    trade = broker_local.trades[0]
    assert trade.spread_cost == Decimal(0)


def test_F8_close_all_records_spread_cost(broker: MockBroker) -> None:
    """close_all 経由 (= eod / margin_call) でも spread_cost が転記される."""
    bar_open = make_bar(0, bid_close="154.100", ask_close="154.110")
    bar_close = make_bar(1, bid_close="154.500", ask_close="154.520")

    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar_open)
    broker.mark_to_market(bar_open)
    trades = broker.close_all(bar_close, reason="eod")
    assert len(trades) == 1
    expected = abs(Decimal(10000)) * bar_close.spread_close * Decimal(2)
    assert trades[0].spread_cost == expected
    assert trades[0].holding_cost == Decimal(0)


def test_F8_short_side_spread_cost_uses_abs_units(broker: MockBroker) -> None:
    """short side でも spread_cost = abs(units) * spread * 2 で計算 (符号反転なし)."""
    bar_open = make_bar(0, bid_close="154.100", ask_close="154.110")
    bar_close = make_bar(1, bid_close="153.500", ask_close="153.520")  # spread 0.02

    broker.submit(OrderSignal(kind="open_short", units=10000), leverage=1)
    broker.fill_pending(bar_open)
    pos_id = broker.open_positions[0].id
    broker.submit(OrderSignal(kind="close_position", position_id=pos_id), leverage=1)
    broker.fill_pending(bar_close)

    trade = broker.trades[0]
    expected = abs(Decimal(10000)) * bar_close.spread_close * Decimal(2)
    assert trade.spread_cost == expected
