"""GA fitness 評価（T009 復活版）。

Clause Genome → DslStrategy → run_backtest → compute_metrics → fitness の経路で評価する。

例外（system_failure）と metric 不能（metric_unavailable）はログを分離してから
`_FAILURE_FITNESS` を返す。後続分析で原因特定できるようにするため。
"""

from __future__ import annotations

from datetime import time
from decimal import Decimal
from typing import Literal

import structlog

from src.backtest.engine import BacktestConfig, run_backtest
from src.backtest.metrics import DEFAULT_TRADE_COUNT_MIN_FOR_SHARPE, compute_metrics
from src.broker.mock import InstrumentMeta, MockBroker
from src.domain.price import PriceBar
from src.dsl.genome import Genome
from src.dsl.strategy import DslStrategy, PrimitiveEvaluator

logger = structlog.get_logger(__name__)

FitnessMetric = Literal["total_pnl", "sharpe", "calmar"]

_FAILURE_FITNESS = Decimal("-1000000000000")  # -1e12 相当


def evaluate_genome(
    genome: Genome,
    bars: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    primitive_evaluator: PrimitiveEvaluator,
    *,
    metric: FitnessMetric = "total_pnl",
    warmup_bars: int = 0,
    session_close_utc: time | None = None,
    trade_count_min_for_sharpe: int = DEFAULT_TRADE_COUNT_MIN_FOR_SHARPE,
) -> Decimal:
    """Clause Genome を評価して fitness を返す。

    例外時は warning ログ (system_failure)、metric 不能時は info ログ (metric_unavailable) で
    分離してから `_FAILURE_FITNESS` を返す（後続分析で原因特定可能）。

    Args:
        genome: Clause Genome。
        bars: 評価対象の価格 bar 列。
        meta: 銘柄メタ情報。
        backtest_config: backtest 設定。
        primitive_evaluator: primitive 評価関数。
        metric: 評価指標。
        warmup_bars: DslStrategy warmup 期間。
        session_close_utc: DslStrategy 内 fail-safe session close 時刻。
    """
    try:
        strategy = DslStrategy(
            genome,
            primitive_evaluator,
            warmup_bars=warmup_bars,
            session_close_utc=session_close_utc,
        )
        broker = MockBroker(instrument_meta=meta)
        result = run_backtest(bars, strategy, broker, backtest_config)
        metrics = compute_metrics(
            result.trades,
            result.equity_curve,
            trade_count_min_for_sharpe=trade_count_min_for_sharpe,
        )
    except Exception as exc:
        logger.warning(
            "ga.fitness.system_failure",
            genome=genome.name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return _FAILURE_FITNESS

    if metric == "total_pnl":
        return metrics.total_pnl
    if metric == "sharpe":
        # T-sharpe Phase 1A: trade_sharpe_raw (v2) を使用。bar-level sharpe (v1) は
        # 非 AF consumer 後方互換のために BacktestMetrics.sharpe で残存
        if metrics.trade_sharpe_raw is None:
            logger.info(
                "ga.fitness.metric_unavailable",
                genome=genome.name,
                metric=metric,
                reason="insufficient_trades_or_zero_std",
                sharpe_calc_version=metrics.sharpe_calc_version,
            )
            return _FAILURE_FITNESS
        return metrics.trade_sharpe_raw
    if metric == "calmar":
        if metrics.calmar is None:
            logger.info(
                "ga.fitness.metric_unavailable",
                genome=genome.name,
                metric=metric,
                reason="flat_equity_or_no_drawdown",
            )
            return _FAILURE_FITNESS
        return metrics.calmar
    raise ValueError(f"unknown metric: {metric}")
