from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

OrderKind = Literal["open_long", "open_short", "close_position", "close_all"]
PositionSide = Literal["long", "short"]
ExitReason = Literal["signal", "eod", "margin_call", "end_of_run"]


@dataclass(frozen=True)
class OrderSignal:
    kind: OrderKind
    units: int | None = None
    position_id: int | None = None


@dataclass(frozen=True)
class Position:
    id: int
    instrument: str
    side: PositionSide
    units: int
    entry_price: Decimal
    entry_time: datetime
    entry_margin: Decimal
    leverage: int
    equity_at_entry: Decimal = Decimal(0)  # T-sharpe: bar 開始時 pre-fill equity (SSOT)


@dataclass(frozen=True)
class Trade:
    position_id: int
    instrument: str
    side: PositionSide
    units: int
    entry_price: Decimal
    entry_time: datetime
    exit_price: Decimal
    exit_time: datetime
    pnl: Decimal
    exit_reason: ExitReason
    equity_at_entry: Decimal = Decimal(0)  # T-sharpe: Position から伝搬


@dataclass(frozen=True)
class PortfolioSnapshot:
    cash: Decimal
    equity: Decimal
    margin_used: Decimal
    margin_level_pct: Decimal | None  # 未保有時は None（無限大相当）
    positions: tuple[Position, ...] = field(default_factory=tuple)


class InsufficientEquityError(Exception):
    """`_open_position` で equity_at_entry が非有限値または非正値の場合に raise (T056)。

    `fill_pending` のループ内で個別捕捉し、当該 signal を drop 扱いとして
    counter に加算してループ継続する設計（fail-closed の「停止」ではなく「拒否」）。
    L1 (`fill_pending` 冒頭 gate) を通り抜けた異常経路の最終防御として機能する。

    `Exception` 直系で `ValueError` 派生にしない理由:
    既存コードに `except ValueError` を広域に書いた catcher があると、本例外が
    意図せず捕捉されて drop counter に加算されない silent な発生経路を生む。
    domain 限定の `InsufficientEquityError` として明示捕捉する。
    """
