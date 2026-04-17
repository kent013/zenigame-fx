from __future__ import annotations

from decimal import Decimal
from typing import Literal

import structlog

from src.backtest.engine import BacktestConfig, run_backtest
from src.backtest.metrics import compute_metrics
from src.broker.mock import InstrumentMeta, MockBroker
from src.domain.price import PriceBar
from src.dsl.genome import DslStrategy, Genome

logger = structlog.get_logger(__name__)

FitnessMetric = Literal["total_pnl", "sharpe", "calmar"]

_FAILURE_FITNESS = Decimal("-1000000000000")  # -1e12 相当


def evaluate_genome(
    genome: Genome,
    bars: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    metric: FitnessMetric = "total_pnl",
) -> Decimal:
    try:
        strategy = DslStrategy(genome)
        broker = MockBroker(instrument_meta=meta)
        result = run_backtest(bars, strategy, broker, backtest_config)
        metrics = compute_metrics(result.trades, result.equity_curve)
        if metric == "total_pnl":
            return metrics.total_pnl
        if metric == "sharpe":
            return metrics.sharpe if metrics.sharpe is not None else _FAILURE_FITNESS
        if metric == "calmar":
            return metrics.calmar if metrics.calmar is not None else _FAILURE_FITNESS
        raise ValueError(f"unknown metric: {metric}")
    except Exception as exc:
        logger.warning("ga.fitness.failure", genome=genome.name, error=str(exc))
        return _FAILURE_FITNESS
