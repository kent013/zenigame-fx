"""Trade dataclass field 拡張 unit tests (T070 cascade port v2 Phase 2 配線).

詳細設計 §5.2 の F23 を 1:1 で対応:
    - spread_cost / holding_cost default=Decimal(0)
    - 既存 caller (positional / keyword) への破壊変更なし
    - 明示指定時の値保持 + frozen 性
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from src.broker.orders import Trade


def _trade_kwargs() -> dict[str, object]:
    return dict(
        position_id=1,
        instrument="EUR_USD",
        side="long",
        units=10000,
        entry_price=Decimal("1.1"),
        entry_time=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        exit_price=Decimal("1.11"),
        exit_time=datetime(2024, 1, 15, 14, 0, tzinfo=UTC),
        pnl=Decimal(100),
        exit_reason="signal",
    )


def test_F23_trade_default_costs_are_zero() -> None:
    """F23: spread_cost / holding_cost default=Decimal(0)."""
    trade = Trade(**_trade_kwargs())  # type: ignore[arg-type]
    assert trade.spread_cost == Decimal(0)
    assert trade.holding_cost == Decimal(0)


def test_F23_trade_with_costs_assigned_explicitly() -> None:
    """F23: spread_cost / holding_cost を明示指定すると保持される."""
    kwargs = _trade_kwargs()
    kwargs["spread_cost"] = Decimal(3)
    kwargs["holding_cost"] = Decimal(2)
    trade = Trade(**kwargs)  # type: ignore[arg-type]
    assert trade.spread_cost == Decimal(3)
    assert trade.holding_cost == Decimal(2)


def test_F23_existing_keyword_construction_remains_compatible() -> None:
    """既存 caller (12 field を keyword で構築) が破壊されない (Phase1-PR-CHECK-F9)."""
    trade = Trade(
        position_id=1,
        instrument="EUR_USD",
        side="long",
        units=10000,
        entry_price=Decimal("1.1"),
        entry_time=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        exit_price=Decimal("1.11"),
        exit_time=datetime(2024, 1, 15, 14, 0, tzinfo=UTC),
        pnl=Decimal(100),
        exit_reason="signal",
        equity_at_entry=Decimal("100000"),
    )
    # 既存 11 field 構築 (T-sharpe equity_at_entry を含む) が引き続き valid
    assert trade.equity_at_entry == Decimal("100000")
    # 新 field は default 適用
    assert trade.spread_cost == Decimal(0)
    assert trade.holding_cost == Decimal(0)


def test_F23_trade_is_frozen() -> None:
    """frozen dataclass の不変性が新 field でも保持される."""
    import dataclasses

    trade = Trade(**_trade_kwargs())  # type: ignore[arg-type]
    # 新 field も frozen
    try:
        trade.spread_cost = Decimal(5)  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError("Trade.spread_cost should be frozen")
