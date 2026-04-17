from __future__ import annotations

import random

from src.dsl.eval import EvalContext, evaluate
from src.ga.random_gen import random_condition, random_genome, random_numeric
from tests._helpers import make_bar


def _ctx() -> EvalContext:
    # 十分に indicators を埋められるだけのバー列を用意
    bars = [make_bar(i, bid_close=str(154.0 + i * 0.01), ask_close=str(154.01 + i * 0.01)) for i in range(60)]
    return EvalContext(bars=bars, i=len(bars) - 1)


def test_random_numeric_evaluates_without_error() -> None:
    rng = random.Random(42)
    for _ in range(20):
        expr = random_numeric(rng, max_depth=4)
        evaluate(expr, _ctx())


def test_random_condition_returns_bool_like() -> None:
    rng = random.Random(43)
    for _ in range(20):
        expr = random_condition(rng, max_depth=3)
        result = evaluate(expr, _ctx())
        assert result is True or result is False


def test_random_genome_has_four_distinct_slots() -> None:
    rng = random.Random(44)
    genome = random_genome(rng, name="test", units=1000, max_depth=3)
    # 4 式が生成されていることを確認
    assert genome.entry_long is not None
    assert genome.entry_short is not None
    assert genome.exit_long is not None
    assert genome.exit_short is not None
    assert genome.units == 1000


def test_seeded_random_genome_is_reproducible() -> None:
    a = random_genome(random.Random(1234), "a", 100, max_depth=3)
    b = random_genome(random.Random(1234), "b", 100, max_depth=3)
    # name は違うが構造は同一
    assert a.entry_long == b.entry_long
    assert a.entry_short == b.entry_short
