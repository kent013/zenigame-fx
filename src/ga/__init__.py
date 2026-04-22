"""GA package — Clause-aware operators + runner（T008）."""

from src.ga.complexity import apply_penalty, genome_size_norm
from src.ga.operators import crossover, mutate
from src.ga.random_gen import (
    PrimitiveCategory,
    PrimitiveDomain,
    PrimitiveRegistry,
    PrimitiveSpec,
    random_clause,
    random_genome,
    random_signal_config,
)
from src.ga.runner import (
    EvaluationResult,
    Evaluator,
    GaConfig,
    GaResult,
    Individual,
    run_ga,
)

__all__ = [
    "EvaluationResult",
    "Evaluator",
    "GaConfig",
    "GaResult",
    "Individual",
    "PrimitiveCategory",
    "PrimitiveDomain",
    "PrimitiveRegistry",
    "PrimitiveSpec",
    "apply_penalty",
    "crossover",
    "genome_size_norm",
    "mutate",
    "random_clause",
    "random_genome",
    "random_signal_config",
    "run_ga",
]
