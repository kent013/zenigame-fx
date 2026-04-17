from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CurrencyPair:
    oanda_name: str
    display_name: str
    base_currency: str
    quote_currency: str
    pip_location: int
    display_precision: int
    trade_units_precision: int
    margin_rate: Decimal
    minimum_trade_size: int
    maximum_order_units: int

    @classmethod
    def from_oanda_name(cls, oanda_name: str, **fields: object) -> CurrencyPair:
        base, quote = oanda_name.split("_", 1)
        return cls(
            oanda_name=oanda_name,
            display_name=f"{base}/{quote}",
            base_currency=base,
            quote_currency=quote,
            **fields,  # type: ignore[arg-type]
        )

    @property
    def pip_size(self) -> Decimal:
        return Decimal(10) ** self.pip_location
