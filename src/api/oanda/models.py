from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class AccountSummary(BaseModel):
    id: str
    currency: str
    balance: Decimal
    margin_rate: Decimal = Field(alias="marginRate")
    open_trade_count: int = Field(alias="openTradeCount", default=0)
    open_position_count: int = Field(alias="openPositionCount", default=0)

    model_config = {"populate_by_name": True}


class Instrument(BaseModel):
    name: str
    display_name: str = Field(alias="displayName")
    type: str
    pip_location: int = Field(alias="pipLocation")
    display_precision: int = Field(alias="displayPrecision")
    trade_units_precision: int = Field(alias="tradeUnitsPrecision")
    margin_rate: Decimal = Field(alias="marginRate")
    minimum_trade_size: int = Field(alias="minimumTradeSize", default=1)
    maximum_order_units: int = Field(alias="maximumOrderUnits", default=0)

    model_config = {"populate_by_name": True}


class Ohlc(BaseModel):
    """OANDA のローソク足フィールドに合わせて o/h/l/c を保持する。"""

    o: Decimal
    h: Decimal
    l: Decimal  # noqa: E741  OANDA API の low キーに対応
    c: Decimal


class Candle(BaseModel):
    time: datetime
    volume: int
    complete: bool
    bid: Ohlc | None = None
    ask: Ohlc | None = None
    mid: Ohlc | None = None


class CandlesResponse(BaseModel):
    instrument: str
    granularity: str
    candles: list[Candle]
