from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from src.backtest.engine import BacktestConfig
from src.ga.runner import GaConfig, run_ga
from tests._helpers import make_bar, usd_jpy_meta


def test_run_ga_returns_best_and_history_on_tiny_scale() -> None:
    bars = [
        make_bar(i, bid_close=str(Decimal("154.0") + Decimal(i) * Decimal("0.01")),
                 ask_close=str(Decimal("154.01") + Decimal(i) * Decimal("0.01")))
        for i in range(80)
    ]
    config = GaConfig(
        population_size=5,
        generations=2,
        crossover_rate=0.7,
        mutation_rate=0.5,
        tournament_size=2,
        elite_count=1,
        max_depth=2,
        units=1000,
        fitness_metric="total_pnl",
        seed=42,
    )
    bconfig = BacktestConfig(
        instrument="USD_JPY",
        start=bars[0].bar_time,
        end=datetime(2026, 4, 2, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
    )
    result = run_ga(bars, usd_jpy_meta(), bconfig, config)
    assert result.best.genome is not None
    # history には 初期 + 世代数 のエントリー
    assert len(result.history) == config.generations + 1
    assert len(result.final_population) == config.population_size
