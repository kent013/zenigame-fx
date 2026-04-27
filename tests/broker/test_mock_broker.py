from __future__ import annotations

from decimal import Decimal

import pytest
from structlog.testing import capture_logs

from src.broker import InsufficientEquityError, MockBroker, OrderSignal
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


# -- T056: negative equity 多層防御 ---------------------------------------------


@pytest.fixture
def broke_broker() -> MockBroker:
    """equity が 0 / 負 / 非有限値になりうる broker を作成するヘルパ用 fixture。

    deposit せずに `_cash` を直接操作して非正値 equity を再現する（テスト専用パス）。
    """
    return MockBroker(instrument_meta=usd_jpy_meta(), maintenance_margin_level_pct=Decimal("100"))


def test_fill_pending_drops_open_signals_when_equity_is_zero(broke_broker: MockBroker) -> None:
    """T056 L1: equity = 0 で open 系 pending は drop される（counter +1）。"""
    # _cash を 0 に強制（deposit しない）
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    broke_broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)

    broke_broker.fill_pending(bar)

    assert len(broke_broker.open_positions) == 0
    assert broke_broker.pop_negative_equity_drop_count() == 1


def test_fill_pending_drops_open_signals_when_equity_is_negative(broke_broker: MockBroker) -> None:
    """T056 L1: equity < 0 で open_short pending は drop される。"""
    broke_broker._cash = Decimal("-100")
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    broke_broker.submit(OrderSignal(kind="open_short", units=5000), leverage=1)

    broke_broker.fill_pending(bar)

    assert len(broke_broker.open_positions) == 0
    assert broke_broker.pop_negative_equity_drop_count() == 1


def test_fill_pending_does_not_drop_when_equity_positive(broker: MockBroker) -> None:
    """T056: equity > 0 で通常 open、drop count = 0。"""
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)

    broker.fill_pending(bar)

    assert len(broker.open_positions) == 1
    assert broker.pop_negative_equity_drop_count() == 0


def test_fill_pending_drops_open_signals_when_equity_is_nan(broke_broker: MockBroker) -> None:
    """T056 L1: equity = NaN で fail-closed drop（InvalidOperation を起こさない）。"""
    broke_broker._cash = Decimal("NaN")
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    broke_broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)

    # 例外を起こさず drop されること
    broke_broker.fill_pending(bar)

    assert len(broke_broker.open_positions) == 0
    assert broke_broker.pop_negative_equity_drop_count() == 1


def test_fill_pending_drops_open_signals_when_equity_is_infinity(broke_broker: MockBroker) -> None:
    """T056 L1: equity = +Infinity / -Infinity の両方で drop される。

    +Infinity は `<= 0` を回避するが is_finite=False のため drop。
    -Infinity は `<= 0` で drop。両ケースとも fail-closed。

    各サブケースで別 bar を使い snapshot cache の混入を回避する。
    """
    bar1 = make_bar(0, bid_close="154.100", ask_close="154.110")

    # +Infinity ケース
    broke_broker._cash = Decimal("Infinity")
    broke_broker._invalidate_snapshot_cache()
    broke_broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broke_broker.fill_pending(bar1)
    assert len(broke_broker.open_positions) == 0

    # -Infinity ケース（別 bar、cache 無効化）
    bar2 = make_bar(1, bid_close="154.110", ask_close="154.120")
    broke_broker._cash = Decimal("-Infinity")
    broke_broker._invalidate_snapshot_cache()
    broke_broker.submit(OrderSignal(kind="open_short", units=5000), leverage=1)
    broke_broker.fill_pending(bar2)
    assert len(broke_broker.open_positions) == 0

    # 両方で counter が加算されている (合計 2)
    assert broke_broker.pop_negative_equity_drop_count() == 2


def test_fill_pending_close_signal_not_dropped_under_negative_equity(broker: MockBroker) -> None:
    """T056 L1: equity 負でも close_position は通常実行される。

    まず position を建てた後、_cash を強制的に大きく削って negative equity 状態を作り、
    close_position pending を発行 → 通常実行されることを確認。
    """
    bar_open = make_bar(0, bid_close="154.100", ask_close="154.110")
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar_open)
    pos_id = broker.open_positions[0].id
    assert broker.pop_negative_equity_drop_count() == 0

    # cash を負にして equity を負にする（mark-to-market 後の equity = cash + unrealized）
    broker._cash = Decimal("-10000000")

    bar_close = make_bar(1, bid_close="154.500", ask_close="154.510")
    broker.submit(OrderSignal(kind="close_position", position_id=pos_id), leverage=1)
    broker.fill_pending(bar_close)

    # close_position は drop されず実行される (trade が 1 件、open_positions が空)
    assert len(broker.open_positions) == 0
    assert len(broker.trades) == 1
    # close は drop counter に加算されない
    assert broker.pop_negative_equity_drop_count() == 0


def test_fill_pending_close_all_signal_not_dropped_under_negative_equity(broker: MockBroker) -> None:
    """T056 L1: equity 負でも close_all は通常実行される（drop counter 非加算）。"""
    bar_open = make_bar(0, bid_close="154.100", ask_close="154.110")
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar_open)

    # cash を負に
    broker._cash = Decimal("-10000000")

    bar_close = make_bar(1, bid_close="154.500", ask_close="154.510")
    broker.submit(OrderSignal(kind="close_all"), leverage=1)
    broker.fill_pending(bar_close)

    assert len(broker.open_positions) == 0
    assert len(broker.trades) == 1
    assert broker.pop_negative_equity_drop_count() == 0


def test_open_position_raises_insufficient_equity_error_for_zero_equity(broker: MockBroker) -> None:
    """T056 L2: _open_position 直接呼び出しで equity_at_entry=0 → InsufficientEquityError。"""
    with pytest.raises(InsufficientEquityError):
        broker._open_position(
            "long",
            10000,
            Decimal("154.110"),
            make_bar(0, bid_close="154.100", ask_close="154.110").bar_time,
            1,
            equity_at_entry=Decimal(0),
        )


def test_open_position_raises_insufficient_equity_error_for_nan_equity(broker: MockBroker) -> None:
    """T056 L2: equity_at_entry=NaN で InsufficientEquityError。"""
    with pytest.raises(InsufficientEquityError):
        broker._open_position(
            "short",
            5000,
            Decimal("154.100"),
            make_bar(0, bid_close="154.100", ask_close="154.110").bar_time,
            1,
            equity_at_entry=Decimal("NaN"),
        )


def test_pop_negative_equity_drop_count_zero_initially(broker: MockBroker) -> None:
    """T056: pop semantics - 初期値 0。"""
    assert broker.pop_negative_equity_drop_count() == 0


def test_pop_negative_equity_drop_count_resets_counter(broke_broker: MockBroker) -> None:
    """T056: pop semantics - 1 度 pop すると次回は 0、累積カウントは pop 間のみ。"""
    bar = make_bar(0, bid_close="154.100", ask_close="154.110")
    broke_broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broke_broker.submit(OrderSignal(kind="open_short", units=5000), leverage=1)
    broke_broker.fill_pending(bar)

    # 1 回目 pop で 2 件
    assert broke_broker.pop_negative_equity_drop_count() == 2
    # 2 回目は reset されて 0
    assert broke_broker.pop_negative_equity_drop_count() == 0


def test_fill_pending_l2_exception_continues_loop() -> None:
    """T056 V7: L1 を bypass しても L2 で `_open_position` が
    `InsufficientEquityError` を raise した場合、bar 処理は中断せず後続 signal が
    実行されることを確認する。

    L1 (`pre_fill_equity > 0`) を通過させた上で、`_open_position` を override して
    open_long submit 時のみ強制的に L2 例外を発生させ、後続の close_position が
    通常実行されることを assert する。
    """

    class _L2InjectingBroker(MockBroker):
        """`_open_position` を hook して open_long のみ L2 例外を発生させる broker。"""

        def _open_position(self, side, units, entry_price, entry_time, leverage, *, equity_at_entry):  # type: ignore[no-untyped-def]
            if side == "long":
                # L1 を通過しても L2 が発火する経路を simulate
                raise InsufficientEquityError(
                    "injected L2 failure for V7 verification"
                )
            return super()._open_position(
                side, units, entry_price, entry_time, leverage,
                equity_at_entry=equity_at_entry,
            )

    broker = _L2InjectingBroker(instrument_meta=usd_jpy_meta(), maintenance_margin_level_pct=Decimal("100"))
    broker.deposit(Decimal("1000000"))

    # まず short を 1 つ建てておく（後で close_position の対象にする）
    bar_open = make_bar(0, bid_close="154.100", ask_close="154.110")
    broker.submit(OrderSignal(kind="open_short", units=5000), leverage=1)
    broker.fill_pending(bar_open)
    pos_id = broker.open_positions[0].id
    assert broker.pop_negative_equity_drop_count() == 0

    # 次 bar: equity > 0（L1 通過）で open_long + close_position を発注
    # open_long は L2 で injected 例外 → drop counter +1
    # close_position はループ継続して通常実行
    bar_next = make_bar(1, bid_close="154.050", ask_close="154.060")
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.submit(OrderSignal(kind="close_position", position_id=pos_id), leverage=1)
    broker.fill_pending(bar_next)

    # L2 例外で 1 件 drop、close_position は実行されて trade 1 件
    assert broker.pop_negative_equity_drop_count() == 1
    assert len(broker.trades) == 1
    assert broker.trades[0].position_id == pos_id
    assert len(broker.open_positions) == 0


def test_fill_pending_drop_count_independent_from_spread_reject(broker: MockBroker) -> None:
    """T056: spread filter による reject と negative equity drop は独立した counter で集計される。

    spread filter で reject された signal は `_negative_equity_drop_count` に加算されない。
    """
    # spread filter を有効化
    broker.set_spread_filter(Decimal("1"))  # 非常に狭い 1 bps 上限
    # 前バー close_spread を大きく（fill_pending で reject 発火させる）
    bar_with_wide_spread = make_bar(0, bid_close="154.000", ask_close="155.000")
    broker.mark_to_market(bar_with_wide_spread)

    # 次 bar の fill_pending で前バー spread が rejected_by_spread を発火
    bar_next = make_bar(1, bid_close="154.000", ask_close="154.010")
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=1)
    broker.fill_pending(bar_next)

    # spread reject 経路では negative equity counter は 0 のまま
    assert broker.pop_negative_equity_drop_count() == 0
    assert len(broker.open_positions) == 0  # spread で reject されているはず
