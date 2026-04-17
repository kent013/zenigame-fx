from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from src.backtest.grid_search import GridSearchConfig, _expand_grid, run_grid_search
from tests._helpers import make_bar, usd_jpy_meta


def test_expand_grid_produces_cartesian_product() -> None:
    grid = {"a": [1, 2], "b": ["x", "y"]}
    combos = _expand_grid(grid)
    assert len(combos) == 4
    assert {"a": 1, "b": "x"} in combos
    assert {"a": 2, "b": "y"} in combos


def test_expand_grid_empty_returns_single_empty_dict() -> None:
    assert _expand_grid({}) == [{}]


def test_run_grid_search_sorts_runs_by_total_pnl_desc() -> None:
    bars = [
        make_bar(0, bid_close="154.100", ask_close="154.110"),
        make_bar(1, bid_close="154.200", ask_close="154.210", bid_open="154.150", ask_open="154.160"),
        make_bar(2, bid_close="154.300", ask_close="154.310"),
    ]
    config = GridSearchConfig(
        instrument="USD_JPY",
        start=bars[0].bar_time,
        end=datetime(2026, 4, 2, tzinfo=UTC),
        initial_cash=Decimal("1000000"),
        leverage=10,
        strategy_name="bollinger",
        parameter_grid={"window": [2, 3], "k": [1.0, 2.0], "units": [5000]},
        parallel=1,
    )
    result = run_grid_search(bars, usd_jpy_meta(), config)

    assert len(result.runs) == 4  # 2 × 2 × 1
    pnls = [r.metrics.total_pnl for r in result.runs]
    assert pnls == sorted(pnls, reverse=True)
