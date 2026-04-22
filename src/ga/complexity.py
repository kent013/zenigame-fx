"""複雑度ペナルティ（T008）。

Luke & Panait 2006 の parsimony pressure（bloat control）に基づく size 罰則。
max_clause / max_depth hard cap（enforce + operator の前提条件）と併用し、
fitness スケールで構造的にシンプルな個体を優先する。

size_norm の定義:
    nodes      = sum(len(directional) + len(local_gate)) across clauses
    max_width  = max(len(directional) + len(local_gate)) across clauses
    n_clause   = len(clauses)
    gate_nodes = sum(len(local_gate)) across clauses

    size_norm = (nodes + 0.5 * max_width + 2 * (n_clause - 1) + 0.5 * gate_nodes) / size_ref

    fitness_pen = fitness_raw - alpha * size_norm

学術引用:
- Luke, S., & Panait, L. (2006). A Comparison of Bloat Control Methods for
  Genetic Programming. Evolutionary Computation, 14(3), 309-344.
- Poli, R., Langdon, W. B., & McPhee, N. F. (2008). A Field Guide to Genetic
  Programming. 4.3 Parsimony Pressure.
"""

from __future__ import annotations

from src.dsl.genome import Genome


def genome_size_norm(genome: Genome, *, size_ref: float = 10.0) -> float:
    """Clause 構造の複雑性指標を size_ref で正規化。

    size_ref は 10.0 を default（暫定値）とし、後続 TODO で SSOT 化する前提。

    Raises:
        ValueError: size_ref が 0 以下。
    """
    if size_ref <= 0.0:
        raise ValueError("size_ref must be > 0")
    n_clause = len(genome.clauses)
    if n_clause == 0:
        return 0.0
    nodes = sum(len(c.directional) + len(c.local_gate) for c in genome.clauses)
    max_width = max(
        len(c.directional) + len(c.local_gate) for c in genome.clauses
    )
    gate_nodes = sum(len(c.local_gate) for c in genome.clauses)
    return (
        nodes + 0.5 * max_width + 2.0 * (n_clause - 1) + 0.5 * gate_nodes
    ) / size_ref


def apply_penalty(
    fitness_raw: float,
    genome: Genome,
    *,
    alpha: float,
    size_ref: float = 10.0,
) -> float:
    """fitness_pen = fitness_raw - alpha * size_norm(genome)."""
    return fitness_raw - alpha * genome_size_norm(genome, size_ref=size_ref)
