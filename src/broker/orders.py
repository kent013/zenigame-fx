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
