"""Phase 4c で追加した Sharpe / Sortino / Calmar / trade duration のテスト。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.backtest.metrics import compute_metrics
from src.broker.orders import Trade


def _trade(pnl: Decimal, pid: int = 1, duration_min: int = 10) -> Trade:
    entry = datetime(2026, 4, 1, tzinfo=UTC)
    return Trade(
        position_id=pid,
        instrument="USD_JPY",
        side="long",
        units=10000,
        entry_price=Decimal("154.000"),
        entry_time=entry,
        exit_price=Decimal("154.000") + pnl / Decimal(10000),
        exit_time=entry + timedelta(minutes=duration_min),
        pnl=pnl,
        exit_reason="signal",
    )


def test_sharpe_is_none_when_too_few_samples() -> None:
    curve = [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    m = compute_metrics([], curve)
    assert m.sharpe is None
    assert m.sortino is None


def test_sharpe_positive_on_steadily_rising_equity() -> None:
    base = datetime(2026, 4, 1, tzinfo=UTC)
    curve = [(base + timedelta(minutes=i), Decimal("1000000") + Decimal(i * 10)) for i in range(30)]
    m = compute_metrics([], curve)
    assert m.sharpe is not None
    assert m.sharpe > 0


def test_sortino_none_when_no_downside() -> None:
    base = datetime(2026, 4, 1, tzinfo=UTC)
    curve = [(base + timedelta(minutes=i), Decimal("1000000") + Decimal(i * 10)) for i in range(30)]
    m = compute_metrics([], curve)
    # 下落が無いので sortino は None（ダウンサイド分散が取れない）
    assert m.sortino is None


def test_calmar_computed_when_drawdown_positive() -> None:
    base = datetime(2026, 4, 1, tzinfo=UTC)
    # 30 分かけて 10% 上がる → 1 分下落で 5% のドローダウン → また回復
    values = [1000000] * 10 + [1100000] * 10 + [1045000] + [1100000] * 10
    curve = [(base + timedelta(minutes=i), Decimal(v)) for i, v in enumerate(values)]
    m = compute_metrics([], curve)
    assert m.calmar is not None


def test_trade_duration_statistics() -> None:
    trades = [_trade(Decimal("100"), pid=1, duration_min=5), _trade(Decimal("-50"), pid=2, duration_min=15)]
    curve = [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    m = compute_metrics(trades, curve)
    assert m.avg_trade_duration == timedelta(minutes=10)
    assert m.max_trade_duration == timedelta(minutes=15)
