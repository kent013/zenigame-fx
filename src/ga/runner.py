from __future__ import annotations

import random
from dataclasses import dataclass, field
from decimal import Decimal

import structlog

from src.backtest.engine import BacktestConfig
from src.broker.mock import InstrumentMeta
from src.domain.price import PriceBar
from src.dsl.genome import Genome
from src.ga.fitness import FitnessMetric, evaluate_genome
from src.ga.operators import crossover, mutate
from src.ga.random_gen import random_genome

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class GaConfig:
    population_size: int = 50
    generations: int = 20
    crossover_rate: float = 0.7
    mutation_rate: float = 0.3
    tournament_size: int = 3
    elite_count: int = 2
    max_depth: int = 4
    units: int = 10000
    fitness_metric: FitnessMetric = "total_pnl"
    seed: int | None = None


@dataclass
class Individual:
    genome: Genome
    fitness: Decimal


@dataclass
class GaResult:
    config: GaConfig
    best: Individual
    history: list[tuple[int, Decimal]] = field(default_factory=list)
    final_population: list[Individual] = field(default_factory=list)


def _tournament(pop: list[Individual], rng: random.Random, k: int) -> Individual:
    sample = rng.sample(pop, k=min(k, len(pop)))
    return max(sample, key=lambda ind: ind.fitness)


def _evaluate_population(
    pop: list[Genome],
    bars: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    metric: FitnessMetric,
) -> list[Individual]:
    return [Individual(g, evaluate_genome(g, bars, meta, backtest_config, metric)) for g in pop]


def run_ga(
    bars: list[PriceBar],
    meta: InstrumentMeta,
    backtest_config: BacktestConfig,
    config: GaConfig,
) -> GaResult:
    rng = random.Random(config.seed)
    logger.info("ga.start", pop=config.population_size, generations=config.generations, seed=config.seed)

    population = [
        random_genome(rng, name=f"g0_i{i}", units=config.units, max_depth=config.max_depth)
        for i in range(config.population_size)
    ]
    individuals = _evaluate_population(population, bars, meta, backtest_config, config.fitness_metric)
    individuals.sort(key=lambda ind: ind.fitness, reverse=True)

    best_overall = individuals[0]
    history: list[tuple[int, Decimal]] = [(0, best_overall.fitness)]

    for gen in range(1, config.generations + 1):
        new_genomes: list[Genome] = [ind.genome for ind in individuals[: config.elite_count]]
        while len(new_genomes) < config.population_size:
            p1 = _tournament(individuals, rng, config.tournament_size)
            p2 = _tournament(individuals, rng, config.tournament_size)
            if rng.random() < config.crossover_rate:
                c1, c2 = crossover(p1.genome, p2.genome, rng)
            else:
                c1, c2 = p1.genome, p2.genome
            c1 = mutate(c1, rng, config.mutation_rate, config.max_depth)
            c2 = mutate(c2, rng, config.mutation_rate, config.max_depth)
            c1 = Genome(name=f"g{gen}_i{len(new_genomes)}", **_non_name_fields(c1))
            new_genomes.append(c1)
            if len(new_genomes) < config.population_size:
                c2 = Genome(name=f"g{gen}_i{len(new_genomes)}", **_non_name_fields(c2))
                new_genomes.append(c2)

        individuals = _evaluate_population(new_genomes, bars, meta, backtest_config, config.fitness_metric)
        individuals.sort(key=lambda ind: ind.fitness, reverse=True)
        if individuals[0].fitness > best_overall.fitness:
            best_overall = individuals[0]
        history.append((gen, best_overall.fitness))
        logger.info("ga.generation", gen=gen, best_fitness=str(best_overall.fitness))

    return GaResult(config=config, best=best_overall, history=history, final_population=individuals)


def _non_name_fields(genome: Genome) -> dict:
    return {
        "units": genome.units,
        "entry_long": genome.entry_long,
        "entry_short": genome.entry_short,
        "exit_long": genome.exit_long,
        "exit_short": genome.exit_short,
    }
