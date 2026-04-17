from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

import structlog

from src.backtest.engine import BacktestConfig, run_backtest
from src.backtest.grid_search import GridSearchConfig, run_grid_search
from src.backtest.metrics import BacktestMetrics, compute_metrics
from src.broker.mock import InstrumentMeta, MockBroker
from src.domain.price import PriceBar
from src.strategy import build as build_strategy

logger = structlog.get_logger(__name__)

FoldMode = Literal["rolling", "anchored"]


@dataclass(frozen=True)
class WalkForwardConfig:
    instrument: str
    start: datetime
    end: datetime
    initial_cash: Decimal
    leverage: int
    strategy_name: str
    parameter_grid: dict[str, Sequence[Any]]
    train_days: int
    test_days: int
    step_days: int
    mode: FoldMode = "rolling"
    parallel: int = 1
    top_k: int = 1


@dataclass(frozen=True)
class FoldSlice:
    index: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime


@dataclass
class FoldOutcome:
    slice: FoldSlice
    best_params: dict[str, Any]
    train_metrics: BacktestMetrics
    test_metrics: BacktestMetrics


@dataclass
class WalkForwardResult:
    config: WalkForwardConfig
    folds: list[FoldOutcome] = field(default_factory=list)


def slice_folds(
    start: datetime,
    end: datetime,
    train_days: int,
    test_days: int,
    step_days: int,
    mode: FoldMode,
) -> list[FoldSlice]:
    if train_days <= 0 or test_days <= 0 or step_days <= 0:
        raise ValueError("train/test/step days must be positive")
    if step_days > test_days:
        logger.warning("walk_forward.gap_between_folds", step_days=step_days, test_days=test_days)
    if step_days < test_days:
        logger.warning("walk_forward.overlapping_test_windows", step_days=step_days, test_days=test_days)

    folds: list[FoldSlice] = []
    idx = 0
    first_test_start = start + timedelta(days=train_days)
    test_start = first_test_start
    while test_start + timedelta(days=test_days) <= end:
        train_end = test_start
        train_start = start if mode == "anchored" else test_start - timedelta(days=train_days)
        test_end = test_start + timedelta(days=test_days)
        folds.append(
            FoldSlice(
                index=idx,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
        )
        idx += 1
        test_start = test_start + timedelta(days=step_days)
    return folds


def _slice_bars(bars: list[PriceBar], start: datetime, end: datetime) -> list[PriceBar]:
    return [b for b in bars if start <= b.bar_time < end]


def _run_test(
    bars: list[PriceBar],
    meta: InstrumentMeta,
    config: WalkForwardConfig,
    slice_: FoldSlice,
    best_params: dict[str, Any],
) -> BacktestMetrics:
    strategy = build_strategy(config.strategy_name, **best_params)
    broker = MockBroker(instrument_meta=meta)
    test_bars = _slice_bars(bars, slice_.test_start, slice_.test_end)
    if not test_bars:
        logger.warning("walk_forward.test_empty", fold=slice_.index)
        return compute_metrics([], [])
    bconfig = BacktestConfig(
        instrument=config.instrument,
        start=slice_.test_start,
        end=slice_.test_end,
        initial_cash=config.initial_cash,
        leverage=config.leverage,
    )
    result = run_backtest(test_bars, strategy, broker, bconfig)
    return compute_metrics(result.trades, result.equity_curve)


def run_walk_forward(
    bars: list[PriceBar],
    meta: InstrumentMeta,
    config: WalkForwardConfig,
) -> WalkForwardResult:
    folds = slice_folds(config.start, config.end, config.train_days, config.test_days, config.step_days, config.mode)
    logger.info("walk_forward.start", folds=len(folds), strategy=config.strategy_name)

    outcomes: list[FoldOutcome] = []
    for slice_ in folds:
        train_bars = _slice_bars(bars, slice_.train_start, slice_.train_end)
        if not train_bars:
            logger.warning("walk_forward.train_empty", fold=slice_.index)
            continue

        gs_config = GridSearchConfig(
            instrument=config.instrument,
            start=slice_.train_start,
            end=slice_.train_end,
            initial_cash=config.initial_cash,
            leverage=config.leverage,
            strategy_name=config.strategy_name,
            parameter_grid=config.parameter_grid,
            parallel=config.parallel,
        )
        gs_result = run_grid_search(train_bars, meta, gs_config)
        if not gs_result.runs:
            logger.warning("walk_forward.no_runs", fold=slice_.index)
            continue

        best = gs_result.runs[0]
        test_metrics = _run_test(bars, meta, config, slice_, best.params)
        outcomes.append(
            FoldOutcome(
                slice=slice_,
                best_params=best.params,
                train_metrics=best.metrics,
                test_metrics=test_metrics,
            )
        )

    return WalkForwardResult(config=config, folds=outcomes)


def aggregate(result: WalkForwardResult) -> dict[str, Decimal | None]:
    if not result.folds:
        return {
            "train_total_pnl": Decimal(0),
            "test_total_pnl": Decimal(0),
            "train_win_rate_avg": Decimal(0),
            "test_win_rate_avg": Decimal(0),
            "train_max_dd_pct_max": Decimal(0),
            "test_max_dd_pct_max": Decimal(0),
            "overfit_score": None,
        }
    train_total = sum((f.train_metrics.total_pnl for f in result.folds), Decimal(0))
    test_total = sum((f.test_metrics.total_pnl for f in result.folds), Decimal(0))
    train_wr = sum((f.train_metrics.win_rate for f in result.folds), Decimal(0)) / Decimal(len(result.folds))
    test_wr = sum((f.test_metrics.win_rate for f in result.folds), Decimal(0)) / Decimal(len(result.folds))
    train_dd_max = max((f.train_metrics.max_drawdown_pct for f in result.folds), default=Decimal(0))
    test_dd_max = max((f.test_metrics.max_drawdown_pct for f in result.folds), default=Decimal(0))
    overfit: Decimal | None = (train_total - test_total) / train_total if train_total > 0 else None
    return {
        "train_total_pnl": train_total,
        "test_total_pnl": test_total,
        "train_win_rate_avg": train_wr,
        "test_win_rate_avg": test_wr,
        "train_max_dd_pct_max": train_dd_max,
        "test_max_dd_pct_max": test_dd_max,
        "overfit_score": overfit,
    }
