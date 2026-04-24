"""MockBroker snapshot cache の invariance / invalidation テスト。

T028 (devnotes/20260425-0158-broker-snapshot-caching) で導入した per-bar
snapshot cache が以下を満たすことを検証する:
  - 同一 bar で複数回呼ぶと cache hit（同一オブジェクトを返す）
  - 新しい bar / position 変化 / cash 変化で cache miss（再計算される）
  - duplicate timestamp + 別 object でも cache miss（object identity 判定）
  - cache 有無で PortfolioSnapshot の数値が bit-identical
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.broker.mock import InstrumentMeta, MockBroker
from src.broker.orders import OrderKind, OrderSignal
from src.domain.price import Ohlc, PriceBar


def _meta() -> InstrumentMeta:
    return InstrumentMeta(
        oanda_name="USD_JPY",
        base_currency="USD",
        quote_currency="JPY",
        margin_rate=Decimal("0.04"),
        pip_size=Decimal("0.01"),
        display_precision=3,
    )


def _bar(hour: int = 0, minute: int = 0, bid_close: str = "154.00") -> PriceBar:
    bt = datetime(2026, 4, 1, hour, minute, 0, tzinfo=UTC)
    b = Decimal(bid_close)
    a = b + Decimal("0.01")
    return PriceBar(
        pair_name="USD_JPY",
        bar_time=bt,
        bid=Ohlc(b, b, b, b),
        ask=Ohlc(a, a, a, a),
        volume=1,
        complete=True,
    )


def _broker_with_position(side: OrderKind = "open_long") -> tuple[MockBroker, PriceBar]:
    broker = MockBroker(instrument_meta=_meta())
    broker.deposit(Decimal("1000000"))
    bar = _bar()
    broker.submit(OrderSignal(kind=side, units=10000), leverage=10)
    broker.fill_pending(bar)
    broker.mark_to_market(bar)
    return broker, bar


# long/short 両方向で cache invariance を検証
@pytest.mark.parametrize("side", ["open_long", "open_short"])
def test_snapshot_cache_hit_returns_identical_object(side: OrderKind) -> None:
    broker, bar = _broker_with_position(side=side)
    s1 = broker._snapshot_at(bar)
    s2 = broker._snapshot_at(bar)
    assert s1 is s2, "same bar should return cached object (is comparison)"


@pytest.mark.parametrize("side", ["open_long", "open_short"])
def test_snapshot_cache_values_symmetric_for_long_short(side: OrderKind) -> None:
    """long/short 両方向で cache hit / miss の値一貫性を確認。"""
    broker, bar = _broker_with_position(side=side)
    s1 = broker._snapshot_at(bar)
    broker._invalidate_snapshot_cache()
    s2 = broker._snapshot_at(bar)
    assert s1.cash == s2.cash
    assert s1.equity == s2.equity
    assert s1.margin_used == s2.margin_used
    assert s1.margin_level_pct == s2.margin_level_pct


def test_snapshot_cache_miss_on_new_bar() -> None:
    broker, bar = _broker_with_position()
    s1 = broker._snapshot_at(bar)
    next_bar = _bar(minute=1, bid_close="154.05")
    broker.mark_to_market(next_bar)
    s2 = broker._snapshot_at(next_bar)
    assert s1 is not s2


def test_snapshot_invalidates_on_position_open() -> None:
    broker = MockBroker(instrument_meta=_meta())
    broker.deposit(Decimal("1000000"))
    bar = _bar()
    broker.mark_to_market(bar)
    s_before = broker._snapshot_at(bar)
    # position を open
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=10)
    broker.fill_pending(bar)
    s_after = broker._snapshot_at(bar)
    assert s_before is not s_after
    assert s_before.margin_used == Decimal(0)
    assert s_after.margin_used > Decimal(0)


def test_snapshot_invalidates_on_position_close() -> None:
    broker, bar = _broker_with_position()
    s_before = broker._snapshot_at(bar)
    # close all positions
    broker.close_all(bar, reason="signal")
    s_after = broker._snapshot_at(bar)
    assert s_before is not s_after
    assert s_after.margin_used == Decimal(0)


def test_snapshot_invalidates_on_holding_cost() -> None:
    broker, bar = _broker_with_position()
    s_before = broker._snapshot_at(bar)
    cost = broker.apply_bar_holding_cost(
        bar, per_day_bps=Decimal("10"), bar_minutes=1,
    )
    assert cost > 0
    s_after = broker._snapshot_at(bar)
    assert s_before is not s_after
    assert s_after.cash < s_before.cash


def test_snapshot_invalidates_on_deposit() -> None:
    broker = MockBroker(instrument_meta=_meta())
    broker.deposit(Decimal("1000000"))
    bar = _bar()
    broker.mark_to_market(bar)
    s_before = broker._snapshot_at(bar)
    broker.deposit(Decimal("500000"))
    s_after = broker._snapshot_at(bar)
    assert s_before is not s_after
    assert s_after.cash == s_before.cash + Decimal("500000")


def test_snapshot_invalidates_on_chained_close() -> None:
    """T028 Round 1 Critical 対応: force_close_if_margin_call などで
    _close_all_internal → _close_one × N を実行した直後の snapshot が、
    毎回再計算された結果と一致すること。
    """
    broker = MockBroker(instrument_meta=_meta())
    broker.deposit(Decimal("1000000"))
    bar = _bar()
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=10)
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=10)
    broker.fill_pending(bar)
    broker.mark_to_market(bar)
    s_before = broker._snapshot_at(bar)
    assert s_before.margin_used > Decimal(0)
    # chain close: 全 position を同 bar で close
    broker.close_all(bar, reason="eod")
    s_after = broker._snapshot_at(bar)
    assert s_before is not s_after
    assert s_after.margin_used == Decimal(0)
    assert len(s_after.positions) == 0


def test_snapshot_duplicate_timestamp_different_prices() -> None:
    """T028 Round 2 Critical 対応: 同一 bar_time を持つ異なる PriceBar オブジェクトを
    連続で渡した際に cache miss が発生して異なる snapshot を返すこと。
    bar_time のみで判定していると stale snapshot を返してしまう反証ケース。
    """
    broker, bar_a = _broker_with_position()
    # 同じ bar_time だが別 object (bid_close が異なる)
    bar_b = _bar(bid_close="154.50")
    assert bar_a.bar_time == bar_b.bar_time
    assert bar_a is not bar_b
    s_a = broker._snapshot_at(bar_a)
    s_b = broker._snapshot_at(bar_b)
    assert s_a is not s_b, "different bar objects should always miss cache"
    # 価格が違うので unrealized PnL も変わる → equity が異なる
    assert s_a.equity != s_b.equity


def test_snapshot_object_reference_identity() -> None:
    """T028 Round 3 Critical 対応: object reference cache が id 再利用問題を
    回避することを模擬検証する。同一 bar_time + 同一内容だが別 object の
    PriceBar で cache miss を確認。
    """
    broker, bar_a = _broker_with_position()
    # 内容完全同一だが別 object
    bar_clone = PriceBar(
        pair_name=bar_a.pair_name,
        bar_time=bar_a.bar_time,
        bid=bar_a.bid,
        ask=bar_a.ask,
        volume=bar_a.volume,
        complete=bar_a.complete,
    )
    assert bar_a is not bar_clone
    assert bar_a == bar_clone  # frozen dataclass equality
    s_a = broker._snapshot_at(bar_a)
    s_clone = broker._snapshot_at(bar_clone)
    assert s_a is not s_clone  # reference 判定なので miss
    # ただし内容は同一なので値は一致
    assert s_a.cash == s_clone.cash
    assert s_a.equity == s_clone.equity
    assert s_a.margin_used == s_clone.margin_used


def test_snapshot_values_bit_identical_cache_vs_no_cache() -> None:
    """cache 有効 / 無効で equity / margin_used / margin_level_pct / positions
    が完全一致することを 100 bar 分 record して確認。selection invariance の
    原子的保証。
    """
    broker = MockBroker(instrument_meta=_meta())
    broker.deposit(Decimal("1000000"))
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=10)

    bars = [
        _bar(hour=h, minute=m, bid_close=f"{154 + (h * 60 + m) * 0.001:.3f}")
        for h in range(5) for m in range(20)
    ]

    values_with_cache: list[tuple[Decimal, Decimal, Decimal, Decimal | None]] = []
    for bar in bars:
        broker.fill_pending(bar)
        broker.mark_to_market(bar)
        s = broker.snapshot()
        values_with_cache.append(
            (s.cash, s.equity, s.margin_used, s.margin_level_pct)
        )

    # もう一度 broker を作り直して cache 無効化 (手動で invalidate を連打して
    # 常に miss を強制) で同じ bars を流す
    broker2 = MockBroker(instrument_meta=_meta())
    broker2.deposit(Decimal("1000000"))
    broker2.submit(OrderSignal(kind="open_long", units=10000), leverage=10)
    values_without_cache: list[tuple[Decimal, Decimal, Decimal, Decimal | None]] = []
    for bar in bars:
        broker2.fill_pending(bar)
        broker2.mark_to_market(bar)
        broker2._invalidate_snapshot_cache()  # 毎回強制 miss
        s = broker2.snapshot()
        values_without_cache.append(
            (s.cash, s.equity, s.margin_used, s.margin_level_pct)
        )

    assert values_with_cache == values_without_cache, \
        "snapshot values must be bit-identical with/without cache"
