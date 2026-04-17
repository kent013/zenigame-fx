from __future__ import annotations

from src.dsl.samples import bollinger_genome, ma_crossover_genome
from src.dsl.serialize import expr_from_dict, expr_to_dict, genome_from_dict, genome_to_dict


def test_bollinger_genome_roundtrip_through_dict() -> None:
    original = bollinger_genome(window=20, k=2.0, units=5000)
    payload = genome_to_dict(original)
    restored = genome_from_dict(payload)
    assert original == restored
    assert genome_to_dict(restored) == payload


def test_ma_crossover_genome_roundtrip_through_dict() -> None:
    original = ma_crossover_genome(fast=5, slow=20, units=10000)
    payload = genome_to_dict(original)
    restored = genome_from_dict(payload)
    assert original == restored


def test_expr_roundtrip_preserves_structure() -> None:
    expr = bollinger_genome().entry_long
    assert expr_from_dict(expr_to_dict(expr)) == expr
