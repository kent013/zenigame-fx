from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog

from src.backtest.engine import BacktestConfig, run_backtest
from src.backtest.metrics import BacktestMetrics, compute_metrics
from src.broker.mock import InstrumentMeta, MockBroker
from src.broker.orders import Trade
from src.domain.price import PriceBar
from src.strategy import build as build_strategy

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class EnsembleSpec:
    name: str
    strategy: str
    params: dict[str, Any]


@dataclass(frozen=True)
class EnsembleConfig:
    instrument: str
    start: datetime
    end: datetime
    initial_cash: Decimal
    leverage: int
    specs: list[EnsembleSpec]
    weights: list[Decimal] | None = None  # None = 等配分


@dataclass
class StrategyRun:
    spec: EnsembleSpec
    capital_allocated: Decimal
    metrics: BacktestMetrics
    equity_curve: list[tuple[datetime, Decimal]]
    trades: list[Trade]


@dataclass
class EnsembleResult:
    config: EnsembleConfig
    per_strategy: list[StrategyRun] = field(default_factory=list)
    combined_equity: list[tuple[datetime, Decimal]] = field(default_factory=list)
    combined_metrics: BacktestMetrics | None = None
    correlation: dict[tuple[str, str], float | None] = field(default_factory=dict)


def _resolve_weights(specs: list[EnsembleSpec], weights: list[Decimal] | None) -> list[Decimal]:
    n = len(specs)
    if n == 0:
        raise ValueError("at least one strategy spec is required")
    if weights is None:
        return [Decimal(1) / Decimal(n)] * n
    if len(weights) != n:
        raise ValueError(f"weights length {len(weights)} != specs length {n}")
    total = sum(weights, Decimal(0))
    if total <= 0:
        raise ValueError("weights sum must be positive")
    return [w / total for w in weights]


def _pearson(a: list[float], b: list[float]) -> float | None:
    if len(a) != len(b) or len(a) < 2:
        return None
    n = len(a)
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    num = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((y - mean_b) ** 2 for y in b)
    denom_sq = var_a * var_b
    if denom_sq <= 0:
        return None
    return num / (denom_sq**0.5)


def _returns(equity: list[tuple[datetime, Decimal]]) -> list[float]:
    rets: list[float] = []
    prev: Decimal | None = None
    for _, eq in equity:
        if prev is not None and prev > 0:
            rets.append(float((eq - prev) / prev))
        prev = eq
    return rets


def run_ensemble(
    bars: list[PriceBar],
    meta: InstrumentMeta,
    config: EnsembleConfig,
) -> EnsembleResult:
    weights = _resolve_weights(config.specs, config.weights)
    logger.info("ensemble.start", strategies=len(config.specs), weights=[str(w) for w in weights])

    runs: list[StrategyRun] = []
    for spec, weight in zip(config.specs, weights, strict=True):
        alloc = config.initial_cash * weight
        strategy = build_strategy(spec.strategy, **spec.params)
        broker = MockBroker(instrument_meta=meta)
        bconfig = BacktestConfig(
            instrument=config.instrument,
            start=config.start,
            end=config.end,
            initial_cash=alloc,
            leverage=config.leverage,
            # T009: ensemble は同一 bars で複数 strategy を並走評価する想定。
            # session_close_utc_hours={23} でイントラデイ絶対制約を担保。
            session_close_utc_hours=frozenset({23}),
        )
        result = run_backtest(bars, strategy, broker, bconfig)
        metrics = compute_metrics(result.trades, result.equity_curve)
        runs.append(
            StrategyRun(
                spec=spec,
                capital_allocated=alloc,
                metrics=metrics,
                equity_curve=result.equity_curve,
                trades=list(result.trades),
            )
        )

    # 合成 equity: 同じタイムスタンプで合算（全 run は同じ bar 列から生成されるので timestamps 一致）
    combined_equity: list[tuple[datetime, Decimal]] = []
    if runs:
        length = min(len(r.equity_curve) for r in runs)
        for i in range(length):
            ts = runs[0].equity_curve[i][0]
            total = sum((r.equity_curve[i][1] for r in runs), Decimal(0))
            combined_equity.append((ts, total))

    combined_trades = [t for r in runs for t in r.trades]
    combined_trades.sort(key=lambda t: t.exit_time)
    combined_metrics = compute_metrics(combined_trades, combined_equity)

    # 相関行列
    per_returns = {r.spec.name: _returns(r.equity_curve) for r in runs}
    correlation: dict[tuple[str, str], float | None] = {}
    names = [r.spec.name for r in runs]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            correlation[(names[i], names[j])] = _pearson(per_returns[names[i]], per_returns[names[j]])

    return EnsembleResult(
        config=config,
        per_strategy=runs,
        combined_equity=combined_equity,
        combined_metrics=combined_metrics,
        correlation=correlation,
    )
