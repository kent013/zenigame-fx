from __future__ import annotations

from decimal import Decimal


def notional_home_currency(units: int, price_quote_per_base: Decimal, quote_is_home: bool) -> Decimal:
    """home currency 建ての想定元本を返す。

    MVP は home=JPY で quote=JPY（USD_JPY 等）のケースのみ対応。quote != home の場合は Phase 4 で換算レートを導入予定。
    """
    if not quote_is_home:
        raise NotImplementedError("quote != home currency (e.g. EUR_USD in JPY account) is Phase 4")
    return Decimal(abs(units)) * price_quote_per_base


def required_margin(notional_home: Decimal, leverage: int) -> Decimal:
    if leverage <= 0:
        raise ValueError("leverage must be >= 1")
    return notional_home / Decimal(leverage)


def validate_leverage(user_leverage: int, instrument_margin_rate: Decimal, max_project_leverage: int = 25) -> None:
    """プロジェクト仕様の上限 (25x) と業者上限 (1 / margin_rate) の両方をチェック。"""
    if user_leverage < 1:
        raise ValueError("user_leverage must be >= 1")
    if user_leverage > max_project_leverage:
        raise ValueError(f"user_leverage {user_leverage} exceeds project max {max_project_leverage}")
    broker_max = int(Decimal(1) / instrument_margin_rate)
    if user_leverage > broker_max:
        raise ValueError(
            f"user_leverage {user_leverage} exceeds broker max {broker_max} (margin_rate={instrument_margin_rate})"
        )
