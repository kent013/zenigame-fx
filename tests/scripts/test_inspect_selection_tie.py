"""T050: inspect_selection_tie unit tests."""

from __future__ import annotations

import pytest

from scripts.alpha_factory.inspect_selection_tie import (
    compute_hhi,
    fitness_pen_tie_ratio_per_generation,
    primitive_usage_per_generation,
)


class TestComputeHhi:
    def test_empty_returns_zero(self) -> None:
        assert compute_hhi([]) == 0.0

    def test_single_item_returns_one(self) -> None:
        assert compute_hhi([10]) == pytest.approx(1.0)

    def test_uniform_distribution(self) -> None:
        # 4 items × 25 each = HHI = 4 * 0.25^2 = 0.25
        assert compute_hhi([25, 25, 25, 25]) == pytest.approx(0.25)

    def test_concentrated_distribution(self) -> None:
        # 1 item dominant
        assert compute_hhi([90, 5, 5]) > 0.8

    def test_ignores_zero_counts(self) -> None:
        # zero counts are filtered (compute_hhi expects positive)
        assert compute_hhi([10, 0, 0]) == pytest.approx(1.0)


class TestPrimitiveUsagePerGeneration:
    def test_extracts_directional_and_local_gate(self) -> None:
        rows = [
            {
                "generation": 0,
                "genome_json": (
                    '{"clauses": [{"directional": [{"name": "F1"}, '
                    '{"name": "F2"}], "local_gate": [{"name": "M1"}]}]}'
                ),
            },
            {
                "generation": 0,
                "genome_json": (
                    '{"clauses": [{"directional": [{"name": "F1"}], '
                    '"local_gate": []}]}'
                ),
            },
            {
                "generation": 1,
                "genome_json": (
                    '{"clauses": [{"directional": [{"name": "F3"}]}]}'
                ),
            },
        ]
        out = primitive_usage_per_generation(rows)
        assert out[0]["F1"] == 2
        assert out[0]["F2"] == 1
        assert out[0]["M1"] == 1
        assert out[1]["F3"] == 1

    def test_skips_invalid_genome_json(self) -> None:
        rows = [
            {"generation": 0, "genome_json": "not-json"},
            {"generation": 0, "genome_json": None},
            {
                "generation": 0,
                "genome_json": '{"clauses": [{"directional": [{"name": "F1"}]}]}',
            },
        ]
        out = primitive_usage_per_generation(rows)
        assert out[0]["F1"] == 1


class TestFitnessPenTieRatio:
    def test_all_unique_returns_zero(self) -> None:
        rows = [
            {"generation": 0, "fitness_pen": 0.1},
            {"generation": 0, "fitness_pen": 0.2},
            {"generation": 0, "fitness_pen": 0.3},
        ]
        out = fitness_pen_tie_ratio_per_generation(rows)
        assert out[0] == pytest.approx(0.0)

    def test_all_same_returns_high_tie(self) -> None:
        rows = [
            {"generation": 0, "fitness_pen": 0.5} for _ in range(10)
        ]
        out = fitness_pen_tie_ratio_per_generation(rows)
        # 10 個全部同じ → unique=1, total=10, tie_ratio = 1 - 1/10 = 0.9
        assert out[0] == pytest.approx(0.9)

    def test_skips_none_fitness(self) -> None:
        rows = [
            {"generation": 0, "fitness_pen": None},
            {"generation": 0, "fitness_pen": 0.1},
        ]
        out = fitness_pen_tie_ratio_per_generation(rows)
        # n=1 → unique=1, tie_ratio=0
        assert out[0] == pytest.approx(0.0)
