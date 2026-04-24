"""MockBroker snapshot の immutability invariance テスト。

T028 施策 0 で Position を @dataclass(frozen=True) 化したことを受け、以下を検証:
  - Position field 書き換えが FrozenInstanceError を投げる
  - snapshot.positions の値が broker._positions.values() と等価 (==)
  - Position を mutate しようとすると即座に例外で失敗する
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.broker.mock import InstrumentMeta, MockBroker
from src.broker.orders import OrderSignal, Position
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


def _bar() -> PriceBar:
    bt = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
    b = Decimal("154.00")
    a = b + Decimal("0.01")
    return PriceBar(
        pair_name="USD_JPY", bar_time=bt,
        bid=Ohlc(b, b, b, b), ask=Ohlc(a, a, a, a),
        volume=1, complete=True,
    )


def test_position_is_frozen() -> None:
    """Position が @dataclass(frozen=True) で field 書き換えが禁止されていること。"""
    pos = Position(
        id=1, instrument="USD_JPY", side="long", units=10000,
        entry_price=Decimal("154.00"),
        entry_time=datetime(2026, 4, 1, tzinfo=UTC),
        entry_margin=Decimal("5000"), leverage=10,
    )
    with pytest.raises(FrozenInstanceError):
        pos.entry_price = Decimal("155.00")  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        pos.units = 20000  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        pos.entry_margin = Decimal("1000")  # type: ignore[misc]


def test_position_value_equality() -> None:
    """frozen dataclass としての value equality が機能すること。"""
    pos_a = Position(
        id=1, instrument="USD_JPY", side="long", units=10000,
        entry_price=Decimal("154.00"),
        entry_time=datetime(2026, 4, 1, tzinfo=UTC),
        entry_margin=Decimal("5000"), leverage=10,
    )
    pos_b = Position(
        id=1, instrument="USD_JPY", side="long", units=10000,
        entry_price=Decimal("154.00"),
        entry_time=datetime(2026, 4, 1, tzinfo=UTC),
        entry_margin=Decimal("5000"), leverage=10,
    )
    # 別 object だが値が同一 → equality True
    assert pos_a is not pos_b
    assert pos_a == pos_b


def test_snapshot_positions_equal_broker_positions() -> None:
    """snapshot.positions の内容が broker._positions.values() と == で等価。

    identity ではなく equality で比較（将来の防御コピー化にも耐える）。
    """
    broker = MockBroker(instrument_meta=_meta())
    broker.deposit(Decimal("1000000"))
    bar = _bar()
    broker.submit(OrderSignal(kind="open_long", units=10000), leverage=10)
    broker.fill_pending(bar)
    broker.mark_to_market(bar)
    snap = broker.snapshot()
    broker_positions = list(broker._positions.values())
    assert list(snap.positions) == broker_positions, (
        "snapshot.positions value must equal broker._positions.values()"
    )
