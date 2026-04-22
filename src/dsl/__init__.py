"""DSL package — Clause ベース Genome 構造（T007）。"""

from src.dsl.composite import (
    compute_clause_score,
    compute_composite,
    compute_dir_score,
    compute_gate,
)
from src.dsl.enforce import enforce_consistency
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.serialize import genome_from_dict, genome_to_dict
from src.dsl.strategy import DslStrategy, PrimitiveEvaluator

__all__ = [
    "ClauseConfig",
    "DslStrategy",
    "Genome",
    "PositionConfig",
    "PrimitiveEvaluator",
    "RiskConfig",
    "SignalConfig",
    "compute_clause_score",
    "compute_composite",
    "compute_dir_score",
    "compute_gate",
    "enforce_consistency",
    "genome_from_dict",
    "genome_to_dict",
]
