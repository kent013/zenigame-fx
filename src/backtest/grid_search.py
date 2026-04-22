from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog

from src.backtest.engine import BacktestConfig, run_backtest
from src.backtest.metrics import BacktestMetrics, compute_metrics
from src.broker.mock import InstrumentMeta, MockBroker
from src.domain.price import PriceBar
from src.strategy import build as build_strategy

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class GridSearchConfig:
    instrument: str
    start: datetime
    end: datetime
    initial_cash: Decimal
    leverage: int
    strategy_name: str
    parameter_grid: dict[str, Sequence[Any]]
    parallel: int = 1


@dataclass
class RunOutcome:
    params: dict[str, Any]
    metrics: BacktestMetrics


@dataclass
class GridSearchResult:
    config: GridSearchConfig
    runs: list[RunOutcome] = field(default_factory=list)


def _expand_grid(grid: dict[str, Sequence[Any]]) -> list[dict[str, Any]]:
    if not grid:
        return [{}]
    keys = list(grid.keys())
    values = [grid[k] for k in keys]
    return [dict(zip(keys, combo, strict=True)) for combo in itertools.product(*values)]


def _execute_single(args: tuple[list[PriceBar], InstrumentMeta, GridSearchConfig, dict[str, Any]]) -> RunOutcome:
    bars, meta, gsconfig, params = args
    strategy = build_strategy(gsconfig.strategy_name, **params)
    broker = MockBroker(instrument_meta=meta)
    bconfig = BacktestConfig(
        instrument=gsconfig.instrument,
        start=gsconfig.start,
        end=gsconfig.end,
        initial_cash=gsconfig.initial_cash,
        leverage=gsconfig.leverage,
        # T009: grid_search は短期 bars を扱う想定のため、イントラデイ絶対制約を
        # session_close_utc_hours={23} で担保（既存挙動の維持）。
        session_close_utc_hours=frozenset({23}),
    )
    result = run_backtest(bars, strategy, broker, bconfig)
    metrics = compute_metrics(result.trades, result.equity_curve)
    return RunOutcome(params=params, metrics=metrics)


def run_grid_search(
    bars: list[PriceBar],
    meta: InstrumentMeta,
    config: GridSearchConfig,
    *,
    executor: Callable[..., Any] | None = None,
) -> GridSearchResult:
    combos = _expand_grid(config.parameter_grid)
    logger.info("grid_search.start", strategy=config.strategy_name, runs=len(combos), parallel=config.parallel)

    payloads = [(bars, meta, config, combo) for combo in combos]
    outcomes: list[RunOutcome]

    if config.parallel <= 1:
        outcomes = [_execute_single(p) for p in payloads]
    else:
        with ProcessPoolExecutor(max_workers=config.parallel) as pool:
            outcomes = list(pool.map(_execute_single, payloads))

    # total_pnl 降順ソート
    outcomes.sort(key=lambda o: o.metrics.total_pnl, reverse=True)
    return GridSearchResult(config=config, runs=outcomes)
