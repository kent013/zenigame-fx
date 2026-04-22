"""GA runner — Clause-aware 対応（T008）。

Evaluator を外部注入することで fitness.py の復活を後続 TODO（T009
clause-backtest-integration）に委譲。本 TODO では dummy evaluator でテスト可能。

複雑度ペナルティ適用（runner 側で apply_penalty を呼ぶ）、elitism、
tournament 選択は従来通り。
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace

import structlog

from src.dsl.genome import Genome
from src.ga.complexity import apply_penalty
from src.ga.operators import crossover, mutate
from src.ga.random_gen import PrimitiveRegistry, random_genome

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class EvaluationResult:
    """evaluator から runner への返り値。

    Attributes:
        fitness_raw: 未ペナルティの生 fitness。NaN/inf は runner 側で -inf に落とす。
        meta: 任意の追加情報（trades_count, sharpe, reason, regime, warnings 等）。
              型は Mapping[str, object] で string/int/float/bool/list など混在可。
    """

    fitness_raw: float
    meta: Mapping[str, object] = field(default_factory=dict)


Evaluator = Callable[[Genome], EvaluationResult]


@dataclass(frozen=True)
class GaConfig:
    """GA 実行設定。"""

    population_size: int = 50
    generations: int = 20
    crossover_rate: float = 0.7
    mutation_rate: float = 0.3
    tournament_size: int = 3
    elite_count: int = 2
    max_clause: int = 1
    max_depth: int = 4
    units: int = 10000
    complexity_alpha: float = 0.03
    complexity_size_ref: float = 10.0
    n_edit_max: int = 3
    seed: int | None = None


@dataclass
class Individual:
    """1 個体 = Genome + fitness（生値 / ペナルティ適用後） + meta."""

    genome: Genome
    fitness_raw: float
    fitness_pen: float
    meta: Mapping[str, object] = field(default_factory=dict)


@dataclass
class GaResult:
    """GA 実行結果。"""

    config: GaConfig
    best: Individual
    history: list[tuple[int, float]] = field(default_factory=list)
    final_population: list[Individual] = field(default_factory=list)


def _safe_fitness(raw: float) -> float:
    """NaN / inf を -inf に落とす（比較で淘汰される安全策）。"""
    if not math.isfinite(raw):
        return -math.inf
    return raw


def _evaluate(
    genome: Genome,
    evaluator: Evaluator,
    alpha: float,
    size_ref: float,
) -> Individual:
    result = evaluator(genome)
    raw = _safe_fitness(result.fitness_raw)
    pen = apply_penalty(raw, genome, alpha=alpha, size_ref=size_ref)
    return Individual(
        genome=genome, fitness_raw=raw, fitness_pen=pen, meta=result.meta
    )


def _tournament(
    pop: list[Individual], rng: random.Random, k: int
) -> Individual:
    sample = rng.sample(pop, k=min(k, len(pop)))
    return max(sample, key=lambda ind: ind.fitness_pen)


def _rename(genome: Genome, name: str) -> Genome:
    return replace(genome, name=name)


def _validate_config(config: GaConfig) -> None:
    if config.population_size < 1:
        raise ValueError("population_size must be >= 1")
    if config.generations < 0:
        raise ValueError("generations must be >= 0")
    if not 0.0 <= config.crossover_rate <= 1.0:
        raise ValueError("crossover_rate must be in [0, 1]")
    if not 0.0 <= config.mutation_rate <= 1.0:
        raise ValueError("mutation_rate must be in [0, 1]")
    if config.tournament_size < 1:
        raise ValueError("tournament_size must be >= 1")
    if config.elite_count < 0:
        raise ValueError("elite_count must be >= 0")
    if config.elite_count > config.population_size:
        raise ValueError("elite_count must be <= population_size")
    if config.max_clause < 1:
        raise ValueError("max_clause must be >= 1")
    if config.max_depth < 1:
        raise ValueError("max_depth must be >= 1")
    if config.n_edit_max < 0:
        raise ValueError("n_edit_max must be >= 0")
    if config.complexity_size_ref <= 0.0:
        raise ValueError("complexity_size_ref must be > 0")


def run_ga(
    evaluator: Evaluator,
    config: GaConfig,
    *,
    registry: PrimitiveRegistry,
) -> GaResult:
    """GA を実行して GaResult を返す。

    Args:
        evaluator: Genome を受け取り EvaluationResult を返す関数。
                   bars / meta / backtest_config は closure に閉じ込める想定。
        config: GA 設定。
        registry: primitive registry（random / mutate で使用）。

    Raises:
        ValueError: GaConfig の値が許容範囲外の場合（population_size<1 等）。
    """
    _validate_config(config)
    rng = random.Random(config.seed)
    logger.info(
        "ga.start",
        pop=config.population_size,
        generations=config.generations,
        seed=config.seed,
    )

    population = [
        random_genome(
            rng,
            name=f"g0_i{i}",
            units=config.units,
            max_clause=config.max_clause,
            max_depth=config.max_depth,
            registry=registry,
        )
        for i in range(config.population_size)
    ]
    individuals = [
        _evaluate(
            g, evaluator, config.complexity_alpha, config.complexity_size_ref
        )
        for g in population
    ]
    individuals.sort(key=lambda ind: ind.fitness_pen, reverse=True)

    best_overall = individuals[0]
    history: list[tuple[int, float]] = [(0, best_overall.fitness_pen)]

    for gen in range(1, config.generations + 1):
        new_genomes: list[Genome] = [
            ind.genome for ind in individuals[: config.elite_count]
        ]
        while len(new_genomes) < config.population_size:
            p1 = _tournament(individuals, rng, config.tournament_size)
            p2 = _tournament(individuals, rng, config.tournament_size)
            if rng.random() < config.crossover_rate:
                c1, c2 = crossover(
                    p1.genome, p2.genome, rng, max_depth=config.max_depth
                )
            else:
                c1, c2 = p1.genome, p2.genome
            c1 = mutate(
                c1,
                rng,
                config.mutation_rate,
                max_clause=config.max_clause,
                max_depth=config.max_depth,
                registry=registry,
                n_edit_max=config.n_edit_max,
            )
            c2 = mutate(
                c2,
                rng,
                config.mutation_rate,
                max_clause=config.max_clause,
                max_depth=config.max_depth,
                registry=registry,
                n_edit_max=config.n_edit_max,
            )
            new_genomes.append(_rename(c1, f"g{gen}_i{len(new_genomes)}"))
            if len(new_genomes) < config.population_size:
                new_genomes.append(_rename(c2, f"g{gen}_i{len(new_genomes)}"))

        individuals = [
            _evaluate(
                g, evaluator, config.complexity_alpha, config.complexity_size_ref
            )
            for g in new_genomes
        ]
        individuals.sort(key=lambda ind: ind.fitness_pen, reverse=True)
        if individuals[0].fitness_pen > best_overall.fitness_pen:
            best_overall = individuals[0]
        history.append((gen, best_overall.fitness_pen))
        logger.info(
            "ga.generation",
            gen=gen,
            best_fitness=str(best_overall.fitness_pen),
        )

    return GaResult(
        config=config,
        best=best_overall,
        history=history,
        final_population=individuals,
    )
