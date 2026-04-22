"""Clause-aware GA runner のテスト（T008）."""

from __future__ import annotations

import math

import pytest

from src.dsl.genome import Genome
from src.ga._dummy_registry import DUMMY_REGISTRY
from src.ga.complexity import genome_size_norm
from src.ga.runner import EvaluationResult, GaConfig, run_ga


def dummy_evaluator_neg_size(genome: Genome) -> EvaluationResult:
    return EvaluationResult(fitness_raw=-genome_size_norm(genome))


def dummy_evaluator_nan(genome: Genome) -> EvaluationResult:
    return EvaluationResult(fitness_raw=float("nan"))


class TestRunGa:
    def test_small_population_completes(self) -> None:
        cfg = GaConfig(
            population_size=5,
            generations=2,
            seed=0,
            crossover_rate=0.7,
            mutation_rate=0.3,
            max_clause=1,
            max_depth=4,
            complexity_alpha=0.03,
        )
        result = run_ga(
            dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY
        )
        assert result.best is not None
        assert len(result.final_population) == 5
        assert len(result.history) == cfg.generations + 1

    def test_best_in_final_population(self) -> None:
        cfg = GaConfig(
            population_size=5,
            generations=2,
            seed=1,
            max_clause=1,
            max_depth=4,
            elite_count=2,
        )
        result = run_ga(
            dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY
        )
        genomes = [ind.genome for ind in result.final_population]
        # elite_count>=1 で best は直近 final_population に残る
        assert result.best.genome in genomes

    def test_elitism_monotonic_best(self) -> None:
        cfg = GaConfig(
            population_size=10,
            generations=5,
            seed=2,
            elite_count=2,
            max_clause=1,
            max_depth=4,
        )
        result = run_ga(
            dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY
        )
        pen_history = [p for _, p in result.history]
        for i in range(1, len(pen_history)):
            assert pen_history[i] >= pen_history[i - 1] - 1e-9

    def test_evaluator_nan_replaced_with_neg_inf(self) -> None:
        cfg = GaConfig(
            population_size=5,
            generations=1,
            seed=3,
            max_clause=1,
            max_depth=4,
        )
        result = run_ga(dummy_evaluator_nan, cfg, registry=DUMMY_REGISTRY)
        for ind in result.final_population:
            assert ind.fitness_raw == -math.inf

    def test_seed_reproducibility(self) -> None:
        cfg = GaConfig(
            population_size=5,
            generations=2,
            seed=42,
            max_clause=1,
            max_depth=4,
        )
        r1 = run_ga(dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY)
        r2 = run_ga(dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY)
        assert [h[1] for h in r1.history] == [h[1] for h in r2.history]
        assert r1.best.fitness_pen == r2.best.fitness_pen
        # best Genome 自体も一致（fitness 値だけでなく構造的再現性）
        # Genome は frozen dataclass なので == は structural equality
        assert r1.best.genome == r2.best.genome

    def test_alpha_zero_pen_equals_raw(self) -> None:
        cfg = GaConfig(
            population_size=5,
            generations=1,
            seed=4,
            complexity_alpha=0.0,
            max_clause=1,
            max_depth=4,
        )
        result = run_ga(
            dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY
        )
        for ind in result.final_population:
            assert ind.fitness_pen == ind.fitness_raw

    def test_invalid_population_size_raises(self) -> None:
        cfg = GaConfig(population_size=0, generations=1, max_clause=1, max_depth=4)
        with pytest.raises(ValueError):
            run_ga(dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY)

    def test_invalid_elite_count_raises(self) -> None:
        cfg = GaConfig(
            population_size=5,
            generations=1,
            elite_count=10,
            max_clause=1,
            max_depth=4,
        )
        with pytest.raises(ValueError):
            run_ga(dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY)

    def test_alpha_positive_pen_less_than_raw(self) -> None:
        cfg = GaConfig(
            population_size=5,
            generations=1,
            seed=4,
            complexity_alpha=0.5,
            complexity_size_ref=10.0,
            max_clause=1,
            max_depth=4,
        )
        result = run_ga(
            dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY
        )
        # size_norm > 0 のため pen < raw
        for ind in result.final_population:
            assert ind.fitness_pen < ind.fitness_raw + 1e-12
