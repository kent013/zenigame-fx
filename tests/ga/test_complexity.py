"""Complexity penalty のテスト（T008）."""

from __future__ import annotations

import pytest

from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.ga.complexity import apply_penalty, genome_size_norm


def _make_genome(clauses: list[ClauseConfig]) -> Genome:
    return Genome(
        name="test",
        units=10000,
        clauses=tuple(clauses),
        position=PositionConfig(0.3, 0.1, 1, 0),
        risk=RiskConfig(2.0, 3.0),
    )


def _sig(name: str) -> SignalConfig:
    return SignalConfig(name=name, weight=1.0)


class TestGenomeSizeNorm:
    def test_minimal(self) -> None:
        g = _make_genome(
            [ClauseConfig(directional=(_sig("a"),), local_gate=(), weight=1.0)]
        )
        # nodes=1, max_width=1, n_clause=1, gate_nodes=0
        # size_norm = (1 + 0.5*1 + 2*0 + 0.5*0) / 10 = 0.15
        assert abs(genome_size_norm(g) - 0.15) < 1e-9

    def test_with_gate(self) -> None:
        g = _make_genome(
            [
                ClauseConfig(
                    directional=(_sig("a"),),
                    local_gate=(_sig("b"),),
                    weight=1.0,
                )
            ]
        )
        # nodes=2, max_width=2, n_clause=1, gate_nodes=1
        # = (2 + 1.0 + 0 + 0.5) / 10 = 0.35
        assert abs(genome_size_norm(g) - 0.35) < 1e-9

    def test_multi_clause(self) -> None:
        g = _make_genome(
            [
                ClauseConfig(
                    directional=(_sig("a"),), local_gate=(), weight=1.0
                ),
                ClauseConfig(
                    directional=(_sig("b"),), local_gate=(), weight=1.0
                ),
            ]
        )
        # nodes=2, max_width=1, n_clause=2, gate_nodes=0
        # = (2 + 0.5 + 2.0 + 0) / 10 = 0.45
        assert abs(genome_size_norm(g) - 0.45) < 1e-9

    def test_invalid_size_ref(self) -> None:
        g = _make_genome(
            [ClauseConfig(directional=(_sig("a"),), local_gate=(), weight=1.0)]
        )
        with pytest.raises(ValueError):
            genome_size_norm(g, size_ref=0.0)

    def test_monotonic_with_signals(self) -> None:
        g1 = _make_genome(
            [ClauseConfig(directional=(_sig("a"),), local_gate=(), weight=1.0)]
        )
        g2 = _make_genome(
            [
                ClauseConfig(
                    directional=(_sig("a"), _sig("b")),
                    local_gate=(),
                    weight=1.0,
                )
            ]
        )
        assert genome_size_norm(g2) > genome_size_norm(g1)


class TestApplyPenalty:
    def test_alpha_zero(self) -> None:
        g = _make_genome(
            [ClauseConfig(directional=(_sig("a"),), local_gate=(), weight=1.0)]
        )
        assert apply_penalty(100.0, g, alpha=0.0) == 100.0

    def test_alpha_positive_reduces(self) -> None:
        g = _make_genome(
            [ClauseConfig(directional=(_sig("a"),), local_gate=(), weight=1.0)]
        )
        pen = apply_penalty(100.0, g, alpha=0.1)
        # penalty = 0.1 * 0.15 = 0.015
        assert abs(pen - (100.0 - 0.015)) < 1e-9

    def test_negative_raw_still_subtracts(self) -> None:
        g = _make_genome(
            [ClauseConfig(directional=(_sig("a"),), local_gate=(), weight=1.0)]
        )
        pen = apply_penalty(-5.0, g, alpha=1.0)
        # -5.0 - 1.0 * 0.15
        assert abs(pen - (-5.15)) < 1e-9
