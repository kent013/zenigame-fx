from __future__ import annotations

import pytest

from src.strategy import build, list_strategies


def test_registry_lists_all_built_in_strategies() -> None:
    names = list_strategies()
    assert "bollinger" in names
    assert "ma_crossover" in names
    assert "rsi" in names
    assert "donchian" in names


def test_build_bollinger_returns_strategy_instance() -> None:
    strat = build("bollinger", window=10, k=1.5, units=5000)
    assert strat.warmup_bars() == 10


def test_build_unknown_strategy_raises() -> None:
    with pytest.raises(ValueError):
        build("not_a_real_strategy")
