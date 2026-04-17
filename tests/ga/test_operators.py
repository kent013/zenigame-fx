from __future__ import annotations

import random

from src.ga.operators import crossover, mutate
from src.ga.random_gen import random_genome


def test_crossover_exchanges_exactly_one_slot() -> None:
    rng = random.Random(1)
    a = random_genome(rng, "a", 100, max_depth=3)
    b = random_genome(rng, "b", 100, max_depth=3)
    c1, _c2 = crossover(a, b, random.Random(2))
    slots = ("entry_long", "entry_short", "exit_long", "exit_short")
    a_equal = sum(getattr(c1, s) == getattr(a, s) for s in slots)
    b_equal = sum(getattr(c1, s) == getattr(b, s) for s in slots)
    # c1 の 4 式のうち、3 つは a 由来、1 つは b 由来のはず（Genome が同じなら誤判定あり得るが確率的に OK）
    assert a_equal + b_equal == 4


def test_mutate_at_full_rate_changes_genome() -> None:
    rng = random.Random(3)
    g = random_genome(rng, "g", 100, max_depth=3)
    mutated = mutate(g, random.Random(4), mutation_rate=1.0, max_depth=3)
    assert mutated != g


def test_mutate_at_zero_rate_returns_same_genome() -> None:
    rng = random.Random(5)
    g = random_genome(rng, "g", 100, max_depth=3)
    same = mutate(g, random.Random(6), mutation_rate=0.0, max_depth=3)
    assert same is g
