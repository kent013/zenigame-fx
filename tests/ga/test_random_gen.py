"""Clause-aware random_gen のテスト（T008）."""

from __future__ import annotations

import random

import pytest

from src.dsl.enforce import enforce_consistency
from src.ga._dummy_registry import DUMMY_REGISTRY
from src.ga.random_gen import (
    PrimitiveSpec,
    random_genome,
    random_params,
    random_signal_config,
)


class TestRandomSignalConfig:
    def test_directional_slot_uses_directional_category(self) -> None:
        rng = random.Random(0)
        sig = random_signal_config(rng, "directional", DUMMY_REGISTRY)
        assert DUMMY_REGISTRY[sig.name].category == "directional"

    def test_local_gate_slot_uses_modulator_category(self) -> None:
        rng = random.Random(0)
        sig = random_signal_config(rng, "local_gate", DUMMY_REGISTRY)
        assert DUMMY_REGISTRY[sig.name].category == "modulator"

    def test_empty_pool_raises(self) -> None:
        registry: dict[str, PrimitiveSpec] = {}
        rng = random.Random(0)
        with pytest.raises(ValueError):
            random_signal_config(rng, "directional", registry)


class TestRandomParams:
    def test_int_range_returns_int(self) -> None:
        spec = PrimitiveSpec("X", "directional", "generic", {"n": (5, 50)})
        rng = random.Random(0)
        p = random_params(rng, spec)
        assert isinstance(p["n"], int)
        assert 5 <= p["n"] <= 50

    def test_float_range_returns_float(self) -> None:
        spec = PrimitiveSpec("X", "directional", "generic", {"k": (0.5, 2.0)})
        rng = random.Random(0)
        p = random_params(rng, spec)
        assert isinstance(p["k"], float)
        assert 0.5 <= p["k"] <= 2.0


class TestRandomGenome:
    def test_passes_enforce_consistency(self) -> None:
        rng = random.Random(0)
        for i in range(20):
            g = random_genome(
                rng,
                f"g_{i}",
                10000,
                max_clause=1,
                max_depth=4,
                registry=DUMMY_REGISTRY,
            )
            # enforce 適用後の結果を再度 enforce しても同じ（冪等）
            assert enforce_consistency(g) == g

    def test_max_clause_one(self) -> None:
        rng = random.Random(0)
        for _ in range(10):
            g = random_genome(
                rng,
                "g",
                10000,
                max_clause=1,
                max_depth=4,
                registry=DUMMY_REGISTRY,
            )
            assert len(g.clauses) == 1

    def test_seed_deterministic(self) -> None:
        g1 = random_genome(
            random.Random(42),
            "g",
            10000,
            max_clause=1,
            max_depth=4,
            registry=DUMMY_REGISTRY,
        )
        g2 = random_genome(
            random.Random(42),
            "g",
            10000,
            max_clause=1,
            max_depth=4,
            registry=DUMMY_REGISTRY,
        )
        assert g1 == g2

    def test_params_no_alias_to_registry(self) -> None:
        """生成された SignalConfig.params が registry の param_schema と
        reference 共有しないことを確認。
        """
        rng = random.Random(0)
        g = random_genome(
            rng,
            "g",
            10000,
            max_clause=1,
            max_depth=4,
            registry=DUMMY_REGISTRY,
        )
        sig = g.clauses[0].directional[0]
        if sig.params:
            assert sig.params is not DUMMY_REGISTRY[sig.name].param_schema

    def test_invalid_max_clause_raises(self) -> None:
        rng = random.Random(0)
        with pytest.raises(ValueError):
            random_genome(
                rng,
                "g",
                10000,
                max_clause=0,
                max_depth=4,
                registry=DUMMY_REGISTRY,
            )

    def test_invalid_max_depth_raises(self) -> None:
        rng = random.Random(0)
        with pytest.raises(ValueError):
            random_genome(
                rng,
                "g",
                10000,
                max_clause=1,
                max_depth=0,
                registry=DUMMY_REGISTRY,
            )

    def test_width_within_max_depth(self) -> None:
        rng = random.Random(0)
        for _ in range(30):
            g = random_genome(
                rng,
                "g",
                10000,
                max_clause=1,
                max_depth=4,
                registry=DUMMY_REGISTRY,
            )
            for c in g.clauses:
                assert len(c.directional) + len(c.local_gate) <= 4
