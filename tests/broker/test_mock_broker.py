from __future__ import annotations

from decimal import Decimal

import pytest
from structlog.testing import capture_logs

from src.broker import MockBroker, OrderSignal
from tests._helpers import make_bar, usd_jpy_meta


@pytest.fixture
def broker() -> MockBroker:
    b = MockBroker(instrument_meta=usd_jpy_meta(), maintenance_margin_level_pct=Decimal("100"))
    b.deposit(Decimal("1000000"))
    return b


def test_open_long_and_close_realizes_pnl_with_spread(broker: MockBroker) -> None:
    bar_open = make_bar(0, bid_close="154.100", ask_close="154.110")
    bar_next = make_bar(1, bid_close="154.500", ask_close="154.510")

    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar_open)  # long を ask.open=154.110 で約定
    broker.mark_to_market(bar_open)
    pos_id = broker.open_positions[0].id

    broker.submit(OrderSignal(kind="close_position", position_id=pos_id), leverage=1)
    broker.fill_pending(bar_next)  # long 決済は bid.open=154.500

    trade = broker.trades[0]
    assert trade.entry_price == Decimal("154.110")
    assert trade.exit_price == Decimal("154.500")
    assert trade.pnl == Decimal("10000") * (Decimal("154.500") - Decimal("154.110"))
    assert broker.cash == Decimal("1000000") + trade.pnl


def test_open_short_close_with_spread(broker: MockBroker) -> None:
    bar_open = make_bar(0, bid_close="154.100", ask_close="154.110")
    bar_next = make_bar(1, bid_close="153.500", ask_close="153.510")

    broker.submit(OrderSignal(kind="open_short", units=10000), leverage=1)
    broker.fill_pending(bar_open)  # short は bid.open=154.100
    pos_id = broker.open_positions[0].id

    broker.submit(OrderSignal(kind="close_position", position_id=pos_id), leverage=1)
    broker.fill_pending(bar_next)  # short 決済は ask.open=153.510

    trade = broker.trades[0]
    assert trade.entry_price == Decimal("154.100")
    assert trade.exit_price == Decimal("153.510")
    assert trade.pnl == Decimal("10000") * (Decimal("154.100") - Decimal("153.510"))


def test_leverage_above_broker_max_is_rejected(broker: MockBroker) -> None:
    # margin_rate=0.04 → max 25x
    with pytest.raises(ValueError):
        broker.submit(OrderSignal(kind="open_long", units=10000), leverage=50)


def test_project_leverage_cap_is_enforced(broker: MockBroker) -> None:
    with pytest.raises(ValueError):
        broker.submit(OrderSignal(kind="open_long", units=10000), leverage=26)


def test_margin_level_forces_close_when_below_threshold(broker: MockBroker) -> None:
    # 残高 100 万、20x で 5 万通貨 long → notional = 50000 * 154.110 ≈ 7,705,500、margin = 385,275
    bar_entry = make_bar(0, bid_close="154.100", ask_close="154.110")
    broker.submit(OrderSignal(kind="open_long", units=50000), leverage=20)
    broker.fill_pending(bar_entry)

    # 大きく逆行: 価格 140.000 付近（含み損 50000 * (154.110 - 140) = -705,500）
    # equity = cash(1,000,000) + unrealized(-705,500) ≈ 294,500
    # margin_level ≈ 294,500 / 385,275 * 100 ≈ 76.4% < 100%
    bar_crash = make_bar(1, bid_close="140.000", ask_close="140.010")
    broker.mark_to_market(bar_crash)
    trades = broker.force_close_if_margin_call(bar_crash)

    assert len(trades) == 1
    assert trades[0].exit_reason == "margin_call"
    assert len(broker.open_positions) == 0


def test_margin_level_no_close_when_healthy(broker: MockBroker) -> None:
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    # cash=1,000,000 + leverage=10 + units=10000 → margin=154,110、equity≈999,900 で 648% healthy
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=10)
    broker.fill_pending(bar)
    broker.mark_to_market(bar)

    trades = broker.force_close_if_margin_call(bar)
    assert trades == []
    assert len(broker.open_positions) == 1


def test_close_all_eod_uses_bar_close_prices(broker: MockBroker) -> None:
    bar = make_bar(0, bid_close="154.100", ask_close="154.110", bid_open="154.000", ask_open="154.010")
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar)  # ask.open=154.010
    trades = broker.close_all(bar, reason="eod")

    assert len(trades) == 1
    t = trades[0]
    assert t.exit_reason == "eod"
    assert t.entry_price == Decimal("154.010")
    # eod は bar.bid.close で決済
    assert t.exit_price == Decimal("154.100")
    assert t.pnl == Decimal("10000") * (Decimal("154.100") - Decimal("154.010"))


def test_snapshot_exposes_equity_and_margin(broker: MockBroker) -> None:
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=10)
    broker.fill_pending(bar)
    broker.mark_to_market(bar)

    snap = broker.snapshot()
    assert snap.cash == Decimal("1000000")
    # margin_used = 10000 * 154.110 / 10 = 154,110
    assert snap.margin_used == Decimal("10000") * Decimal("154.110") / Decimal(10)
    assert snap.margin_level_pct is not None


# ---------------------------------------------------------------------------
# T-sharpe Phase 1A: equity_at_entry 伝搬
# ---------------------------------------------------------------------------


def test_position_records_equity_at_entry(broker: MockBroker) -> None:
    """_open_position 経由で Position.equity_at_entry が pre-fill equity でセットされる."""
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar)
    pos = broker.open_positions[0]
    # bar 処理開始時点では cash=1000000, positions=空 なので equity=1000000
    assert pos.equity_at_entry == Decimal("1000000")


def test_trade_propagates_equity_at_entry_from_position(broker: MockBroker) -> None:
    """Position.equity_at_entry が Trade.equity_at_entry へ伝搬される."""
    bar_open = make_bar(0, bid_close="154.100", ask_close="154.110")
    bar_next = make_bar(1, bid_close="154.500", ask_close="154.510")
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar_open)
    pos_id = broker.open_positions[0].id
    broker.submit(OrderSignal(kind="close_position", position_id=pos_id), leverage=1)
    broker.fill_pending(bar_next)
    trade = broker.trades[0]
    assert trade.equity_at_entry == Decimal("1000000")


def test_same_bar_multiple_fills_share_pre_fill_equity(broker: MockBroker) -> None:
    """同一 bar 内の複数 open は同じ pre-fill equity を共有する (fill 順依存禁止)."""
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    # 同 bar に 2 つの open を投入
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.submit(OrderSignal(kind="open_short", units=5000), leverage=1)
    broker.fill_pending(bar)
    positions = broker.open_positions
    assert len(positions) == 2
    # 両方とも bar 開始時 equity (=1000000) が記録されている
    assert positions[0].equity_at_entry == Decimal("1000000")
    assert positions[1].equity_at_entry == Decimal("1000000")
    assert positions[0].equity_at_entry == positions[1].equity_at_entry


def test_drop_pending_open_returns_count_without_logging(broker: MockBroker) -> None:
    """T055: drop_pending_open は件数を返し、log を出さない (per-bar hot path コスト削減)."""
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.submit(OrderSignal(kind="open_short", units=5000), leverage=1)

    with capture_logs() as logs:
        dropped = broker.drop_pending_open()

    assert dropped == 2
    # broker.drop_pending_open イベントが発行されていないこと
    assert all(log.get("event") != "broker.drop_pending_open" for log in logs)


def test_drop_pending_open_returns_zero_when_no_pending_open(broker: MockBroker) -> None:
    """pending に open 系がない場合は 0 を返し log も出さない。"""
    with capture_logs() as logs:
        dropped = broker.drop_pending_open()
    assert dropped == 0
    assert all(log.get("event") != "broker.drop_pending_open" for log in logs)
