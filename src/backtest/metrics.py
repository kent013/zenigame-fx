from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

import structlog

from src.broker.orders import Trade

logger = structlog.get_logger(__name__)

# 1分足を前提とした年間バー数（24h * 60min * 365日 * FX 営業率 5/7）
BARS_PER_YEAR_M1 = int(24 * 60 * 365 * 5 / 7)

# T-sharpe Phase 1A: trade-level Sharpe メタ
SHARPE_CALC_VERSION_V1 = "v1_bar_annualized"
SHARPE_CALC_VERSION_V2 = "v2_trade_level"
DEFAULT_TRADE_COUNT_MIN_FOR_SHARPE = 30  # config 経由で上書き可能


@dataclass(frozen=True)
class BacktestMetrics:
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: Decimal  # 0..1
    total_pnl: Decimal
    avg_win: Decimal
    avg_loss: Decimal  # 負値（損失）
    profit_factor: Decimal | None
    max_drawdown: Decimal
    max_drawdown_pct: Decimal
    final_equity: Decimal
    sharpe: Decimal | None  # v1 bar-level annualized。非 AF consumer 後方互換のため Phase 2 まで維持
    sortino: Decimal | None  # 年率 Sortino。損失分散ゼロ時 None
    calmar: Decimal | None  # annual_return / max_drawdown_pct。未計算時 None
    avg_trade_duration: timedelta | None
    max_trade_duration: timedelta | None
    # T-sharpe Phase 1A: trade-level Sharpe (AF consumer の正規指標)
    trade_sharpe_raw: Decimal | None = None  # v2 trade-level raw Sharpe (annualize なし)
    sharpe_calc_version: str = SHARPE_CALC_VERSION_V2


def _bar_returns(equity_curve: list[tuple[datetime, Decimal]]) -> list[float]:
    rets: list[float] = []
    prev: Decimal | None = None
    for _, eq in equity_curve:
        if prev is not None and prev > 0:
            rets.append(float((eq - prev) / prev))
        prev = eq
    return rets


def _sharpe(returns: list[float], periods_per_year: int = BARS_PER_YEAR_M1) -> float | None:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(var)
    if std == 0:
        return None
    return (mean / std) * math.sqrt(periods_per_year)


def _trade_returns(trades: list[Trade]) -> list[float]:
    """各クローズドトレードの return = net_pnl / equity_at_entry。

    equity_at_entry が 0 以下の trade は「未設定（バグ）」として警告ログを出してスキップ。
    invalid_count は本関数内でログ集計し caller には返さない。
    """
    rets: list[float] = []
    invalid_count = 0
    for t in trades:
        if t.equity_at_entry <= 0:
            invalid_count += 1
            logger.warning(
                "trade_return.invalid_equity_at_entry",
                trade_position_id=t.position_id,
                equity_at_entry=str(t.equity_at_entry),
            )
            continue
        rets.append(float(t.pnl / t.equity_at_entry))
    if invalid_count > 0:
        logger.warning(
            "trade_return.invalid_equity_at_entry_total",
            invalid_count=invalid_count,
            total_trades=len(trades),
        )
    return rets


def _trade_sharpe_raw(
    returns: list[float],
    trade_count_min: int = DEFAULT_TRADE_COUNT_MIN_FOR_SHARPE,
) -> float | None:
    """trade-level raw Sharpe (annualize なし)。

    - len(returns) < max(2, trade_count_min) → None
    - std <= 1e-15 → None
    - 非有限 (NaN/Inf) → None
    """
    if len(returns) < max(2, trade_count_min):  # ゼロ除算防止 (len-1>=1)
        return None
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(var)
    if std <= 1e-15:
        return None
    result = mean / std
    if not math.isfinite(result):
        return None
    return result


def _sortino(returns: list[float], periods_per_year: int = BARS_PER_YEAR_M1) -> float | None:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    downside = [r for r in returns if r < 0]
    if len(downside) < 2:
        return None
    dvar = sum(r**2 for r in downside) / len(downside)
    dstd = math.sqrt(dvar)
    if dstd == 0:
        return None
    return (mean / dstd) * math.sqrt(periods_per_year)


def _calmar(equity_curve: list[tuple[datetime, Decimal]], max_dd_pct: Decimal) -> Decimal | None:
    if len(equity_curve) < 2 or max_dd_pct == 0:
        return None
    start_time, start_equity = equity_curve[0]
    end_time, end_equity = equity_curve[-1]
    if start_equity <= 0:
        return None
    period_days = (end_time - start_time).total_seconds() / 86400
    if period_days <= 0:
        return None
    total_return_pct = (end_equity - start_equity) / start_equity * Decimal(100)
    # 年率化
    annual_return_pct = total_return_pct * Decimal(365) / Decimal(str(period_days))
    return annual_return_pct / max_dd_pct


def compute_metrics(
    trades: list[Trade],
    equity_curve: list[tuple[datetime, Decimal]],
    *,
    trade_count_min_for_sharpe: int = DEFAULT_TRADE_COUNT_MIN_FOR_SHARPE,
) -> BacktestMetrics:
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
    profit_factor: Decimal | None = None if total_loss_abs == 0 else total_win / total_loss_abs

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

    rets = _bar_returns(equity_curve)
    sharpe_f = _sharpe(rets)
    sortino_f = _sortino(rets)
    sharpe = Decimal(str(sharpe_f)) if sharpe_f is not None else None
    sortino = Decimal(str(sortino_f)) if sortino_f is not None else None
    calmar = _calmar(equity_curve, max_drawdown_pct)

    # T-sharpe Phase 1A: trade-level raw Sharpe
    trade_rets = _trade_returns(trades)
    trade_sharpe_f = _trade_sharpe_raw(
        trade_rets, trade_count_min=trade_count_min_for_sharpe
    )
    trade_sharpe_raw = (
        Decimal(str(trade_sharpe_f)) if trade_sharpe_f is not None else None
    )

    # トレード保有時間
    durations = [t.exit_time - t.entry_time for t in trades]
    avg_duration = sum(durations, timedelta(0)) / len(durations) if durations else None
    max_duration = max(durations) if durations else None

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
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        avg_trade_duration=avg_duration,
        max_trade_duration=max_duration,
        trade_sharpe_raw=trade_sharpe_raw,
        sharpe_calc_version=SHARPE_CALC_VERSION_V2,
    )
