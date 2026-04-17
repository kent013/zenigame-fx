from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.backtest.metrics import compute_metrics
from src.broker.orders import Trade


def _trade(pnl: Decimal, pid: int = 1) -> Trade:
    entry = datetime(2026, 4, 1, tzinfo=UTC)
    return Trade(
        position_id=pid,
        instrument="USD_JPY",
        side="long",
        units=10000,
        entry_price=Decimal("154.000"),
        entry_time=entry,
        exit_price=Decimal("154.000") + pnl / Decimal(10000),
        exit_time=entry + timedelta(minutes=10),
        pnl=pnl,
        exit_reason="signal",
    )


def test_win_rate_and_profit_factor() -> None:
    trades = [_trade(Decimal("100"), 1), _trade(Decimal("-50"), 2), _trade(Decimal("200"), 3)]
    curve = [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    m = compute_metrics(trades, curve)
    assert m.trade_count == 3
    assert m.win_count == 2
    assert m.loss_count == 1
    assert m.win_rate == Decimal(2) / Decimal(3)
    assert m.total_pnl == Decimal("250")
    assert m.profit_factor == Decimal("300") / Decimal("50")


def test_profit_factor_is_none_when_no_losses() -> None:
    trades = [_trade(Decimal("100")), _trade(Decimal("50"))]
    curve = [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    m = compute_metrics(trades, curve)
    assert m.profit_factor is None


def test_max_drawdown_on_rising_then_falling_curve() -> None:
    base = datetime(2026, 4, 1, tzinfo=UTC)
    curve = [(base + timedelta(minutes=i), Decimal(v)) for i, v in enumerate([1000, 1200, 1500, 1100, 900, 950])]
    m = compute_metrics([], curve)
    # ピーク 1500 → トラフ 900 → DD 600、pct = 600/1500 * 100 = 40
    assert m.max_drawdown == Decimal("600")
    assert m.max_drawdown_pct == Decimal("600") / Decimal("1500") * Decimal("100")


def test_max_drawdown_zero_on_monotonic_rise() -> None:
    base = datetime(2026, 4, 1, tzinfo=UTC)
    curve = [(base + timedelta(minutes=i), Decimal(v)) for i, v in enumerate([1000, 1100, 1200])]
    m = compute_metrics([], curve)
    assert m.max_drawdown == Decimal(0)
