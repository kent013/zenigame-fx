from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.backtest.metrics import (
    SHARPE_CALC_VERSION_V2,
    compute_metrics,
)
from src.broker.orders import Trade


def _trade(
    pnl: Decimal,
    pid: int = 1,
    equity_at_entry: Decimal = Decimal("1000000"),
) -> Trade:
    entry = datetime(2026, 4, 1, tzinfo=UTC) + timedelta(minutes=pid)
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
        equity_at_entry=equity_at_entry,
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


# ---------------------------------------------------------------------------
# T-sharpe Phase 1A: trade-level Sharpe (`trade_sharpe_raw`) のテスト
# ---------------------------------------------------------------------------


def _make_trades(n: int, pnl_pattern: list[Decimal] | None = None) -> list[Trade]:
    """N 個の Trade を生成する。pnl_pattern を循環適用する。"""
    if pnl_pattern is None:
        pnl_pattern = [Decimal("100"), Decimal("-30")]
    return [
        _trade(pnl_pattern[i % len(pnl_pattern)], pid=i + 1)
        for i in range(n)
    ]


def test_trade_sharpe_raw_returns_none_when_trade_count_below_minimum() -> None:
    """trade_count < trade_count_min_for_sharpe → None (sample-size guard)."""
    trades = _make_trades(20)  # default 30 未満
    curve = [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    m = compute_metrics(trades, curve)
    assert m.trade_sharpe_raw is None


def test_trade_sharpe_raw_returns_value_with_sufficient_trades() -> None:
    """trade_count >= 30 + 分散有 → 有限値の trade_sharpe_raw."""
    trades = _make_trades(30)
    curve = [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    m = compute_metrics(trades, curve)
    assert m.trade_sharpe_raw is not None
    # win=15, loss=15, mean>0 だが std>0 なので有限
    val = float(m.trade_sharpe_raw)
    assert val == val  # not NaN


def test_trade_sharpe_raw_matches_manual_calculation() -> None:
    """式の厳密検証: 固定 returns 列で mean / std を手計算と照合する."""
    import math
    # 30 trade、equity_at_entry=1_000_000 一定で returns = pnl / 1_000_000
    pnls = [Decimal(str(p)) for p in [
        100.0, -50.0, 200.0, -30.0, 150.0,
        -80.0, 120.0, -40.0, 90.0, -20.0,
        110.0, -60.0, 180.0, -10.0, 70.0,
        -90.0, 140.0, -100.0, 130.0, -25.0,
        160.0, -55.0, 95.0, -35.0, 105.0,
        -45.0, 175.0, -65.0, 115.0, -75.0,
    ]]
    trades = [_trade(p, pid=i + 1) for i, p in enumerate(pnls)]
    curve = [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    m = compute_metrics(trades, curve)
    rets = [float(p) / 1_000_000 for p in pnls]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    std = math.sqrt(var)
    expected = mean / std
    assert m.trade_sharpe_raw is not None
    assert float(m.trade_sharpe_raw) == pytest.approx(expected, rel=1e-9)


def test_trade_sharpe_raw_returns_none_when_std_is_zero() -> None:
    """全 trade pnl が同じ → std=0 → None."""
    trades = [_trade(Decimal("100"), pid=i + 1) for i in range(35)]
    curve = [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    m = compute_metrics(trades, curve)
    assert m.trade_sharpe_raw is None


def test_trade_sharpe_raw_skips_trades_with_zero_equity_at_entry() -> None:
    """equity_at_entry=0 の trade はスキップされる (warning + 計算除外)."""
    trades = [
        _trade(Decimal("100"), pid=1, equity_at_entry=Decimal(0)),
        _trade(Decimal("-50"), pid=2, equity_at_entry=Decimal(0)),
    ]
    curve = [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    m = compute_metrics(trades, curve)
    # 全 trade スキップ → returns 空 → None
    assert m.trade_sharpe_raw is None


def test_trade_sharpe_raw_threshold_override() -> None:
    """trade_count_min_for_sharpe を低くすると 2 trade でも計算される."""
    trades = _make_trades(2)
    curve = [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    m = compute_metrics(trades, curve, trade_count_min_for_sharpe=2)
    assert m.trade_sharpe_raw is not None


def test_compute_metrics_sharpe_calc_version_is_v2() -> None:
    """sharpe_calc_version は常に v2_trade_level."""
    trades = _make_trades(35)
    curve = [(datetime(2026, 4, 1, tzinfo=UTC), Decimal("1000000"))]
    m = compute_metrics(trades, curve)
    assert m.sharpe_calc_version == SHARPE_CALC_VERSION_V2


def test_compute_metrics_legacy_sharpe_still_populated_for_backward_compat() -> None:
    """v1 bar-level sharpe は Phase 2 まで埋め続ける (非 AF consumer 後方互換)."""
    base = datetime(2026, 4, 1, tzinfo=UTC)
    curve = [
        (base + timedelta(minutes=i), Decimal(str(1_000_000 + i * 100)))
        for i in range(50)
    ]
    m = compute_metrics([], curve)
    assert m.sharpe is not None  # v1 bar-level Sharpe は equity_curve から計算される
