from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.broker.orders import Trade


@dataclass(frozen=True)
class BacktestMetrics:
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: Decimal  # 0..1
    total_pnl: Decimal
    avg_win: Decimal
    avg_loss: Decimal  # 負値（損失）
    profit_factor: Decimal | None  # 損失ゼロなら None（無限大相当）
    max_drawdown: Decimal
    max_drawdown_pct: Decimal  # 0..100
    final_equity: Decimal


def compute_metrics(trades: list[Trade], equity_curve: list[tuple[datetime, Decimal]]) -> BacktestMetrics:
    trade_count = len(trades)
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl < 0]
    total_pnl = sum((t.pnl for t in trades), Decimal(0))

    win_count = len(wins)
    loss_count = len(losses)
    win_rate = Decimal(win_count) / Decimal(trade_count) if trade_count else Decimal(0)
    avg_win = sum(wins, Decimal(0)) / Decimal(win_count) if win_count else Decimal(0)
    avg_loss = sum(losses, Decimal(0)) / Decimal(loss_count) if loss_count else Decimal(0)
    total_loss_abs = -sum(losses, Decimal(0))
    total_win = sum(wins, Decimal(0))
    profit_factor: Decimal | None
    profit_factor = None if total_loss_abs == 0 else total_win / total_loss_abs

    max_drawdown = Decimal(0)
    max_drawdown_pct = Decimal(0)
    peak = Decimal(0)
    for _, equity in equity_curve:
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = peak - equity
            if dd > max_drawdown:
                max_drawdown = dd
                max_drawdown_pct = dd / peak * Decimal(100)

    final_equity = equity_curve[-1][1] if equity_curve else Decimal(0)

    return BacktestMetrics(
        trade_count=trade_count,
        win_count=win_count,
        loss_count=loss_count,
        win_rate=win_rate,
        total_pnl=total_pnl,
        avg_win=avg_win,
        avg_loss=avg_loss,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
        max_drawdown_pct=max_drawdown_pct,
        final_equity=final_equity,
    )
