"""Clause-aware GA operators のテスト（T008）."""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

from src.dsl.enforce import enforce_consistency
from src.ga._dummy_registry import DUMMY_REGISTRY
from src.ga.operators import (
    _available_crossover_ops,
    crossover,
    mutate,
)
from src.ga.random_gen import random_genome, random_signal_config


@pytest.fixture
def single_clause_single_dir_parents() -> tuple:
    """両親を max_clause=1, directional=1 に正規化したペア。"""
    r1 = random.Random(1)
    r2 = random.Random(2)
    a = random_genome(
        r1, "a", 10000, max_clause=1, max_depth=2, registry=DUMMY_REGISTRY
    )
    b = random_genome(
        r2, "b", 10000, max_clause=1, max_depth=2, registry=DUMMY_REGISTRY
    )
    # テスト用に directional を 1 本に強制
    a_c = a.clauses[0]
    b_c = b.clauses[0]
    a = replace(a, clauses=(replace(a_c, directional=a_c.directional[:1]),))
    b = replace(b, clauses=(replace(b_c, directional=b_c.directional[:1]),))
    return a, b


class TestCrossoverCandidateSet:
    def test_single_clause_single_directional(
        self, single_clause_single_dir_parents: tuple
    ) -> None:
        a, b = single_clause_single_dir_parents
        ops = set(_available_crossover_ops(a, b))
        # always 3 つ
        assert {"position_swap", "risk_swap", "clause_swap"}.issubset(ops)
        # clause_point / directional_swap は入らない
        assert "clause_point" not in ops
        assert "directional_swap" not in ops
        # gate_swap は local_gate 有無に依存
        has_gate = (
            len(a.clauses[0].local_gate) > 0 or len(b.clauses[0].local_gate) > 0
        )
        assert ("gate_swap" in ops) == has_gate

    def test_multi_directional_enables_directional_swap(self) -> None:
        rng = random.Random(3)
        a = random_genome(
            rng, "a", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        b = random_genome(
            rng, "b", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        a_c = a.clauses[0]
        b_c = b.clauses[0]
        if len(a_c.directional) < 2:
            extra = random_signal_config(rng, "directional", DUMMY_REGISTRY)
            a = replace(
                a,
                clauses=(
                    replace(a_c, directional=(*a_c.directional, extra)),
                ),
            )
        if len(b_c.directional) < 2:
            extra = random_signal_config(rng, "directional", DUMMY_REGISTRY)
            b = replace(
                b,
                clauses=(
                    replace(b_c, directional=(*b_c.directional, extra)),
                ),
            )
        ops = set(_available_crossover_ops(a, b))
        assert "directional_swap" in ops

    def test_multi_clause_enables_clause_point(self) -> None:
        rng = random.Random(4)
        a = random_genome(
            rng, "a", 10000, max_clause=2, max_depth=4, registry=DUMMY_REGISTRY
        )
        # max_clause=2 は必ず 2 clause 生成するわけではないので、1 なら合成
        if len(a.clauses) < 2:
            b_seed = random_genome(
                rng,
                "x",
                10000,
                max_clause=1,
                max_depth=4,
                registry=DUMMY_REGISTRY,
            )
            a = replace(a, clauses=(*a.clauses, *b_seed.clauses))
        b = random_genome(
            rng, "b", 10000, max_clause=2, max_depth=4, registry=DUMMY_REGISTRY
        )
        if len(b.clauses) < 2:
            b_seed = random_genome(
                rng,
                "x",
                10000,
                max_clause=1,
                max_depth=4,
                registry=DUMMY_REGISTRY,
            )
            b = replace(b, clauses=(*b.clauses, *b_seed.clauses))
        ops = set(_available_crossover_ops(a, b))
        assert "clause_point" in ops


class TestCrossover:
    def test_returns_two_children(
        self, single_clause_single_dir_parents: tuple
    ) -> None:
        a, b = single_clause_single_dir_parents
        rng = random.Random(0)
        result = crossover(a, b, rng)
        assert isinstance(result, tuple) and len(result) == 2

    def test_children_pass_enforce(self) -> None:
        rng = random.Random(5)
        a = random_genome(
            rng, "a", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        b = random_genome(
            rng, "b", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        for _ in range(100):
            c1, c2 = crossover(a, b, rng, max_depth=4)
            # 冪等: 2 回 enforce しても結果同じ
            assert enforce_consistency(c1) == c1
            assert enforce_consistency(c2) == c2

    def test_parents_unchanged(self) -> None:
        rng = random.Random(6)
        a = random_genome(
            rng, "a", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        b = random_genome(
            rng, "b", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        a_copy = a
        b_copy = b
        crossover(a, b, rng)
        assert a == a_copy
        assert b == b_copy

    def test_params_dict_no_alias_to_children(self) -> None:
        """子の SignalConfig.params dict が親と reference を共有していないことを検証。

        SignalConfig.__post_init__ が defensive copy を取るため、子の params dict
        を mutate しても親側に影響しない。
        """
        rng = random.Random(20)
        a = random_genome(
            rng, "a", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        b = random_genome(
            rng, "b", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        # 親の directional signal の params を事前コピー
        a_sig = a.clauses[0].directional[0]
        a_params_before = dict(a_sig.params)
        c1, _ = crossover(a, b, rng, max_depth=4)
        # 子の params が親と is で共有されていないこと（dict identity 異なる）
        for c in c1.clauses:
            for sig in c.directional:
                if sig.name == a_sig.name:
                    assert sig.params is not a_sig.params
        # 親側が変化していないこと
        assert a.clauses[0].directional[0].params == a_params_before

    def test_max_depth_preserved(self) -> None:
        """gate_swap / directional_swap 後も max_depth を超えないこと。"""
        rng = random.Random(7)
        a = random_genome(
            rng, "a", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        b = random_genome(
            rng, "b", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        for _ in range(50):
            c1, c2 = crossover(a, b, rng, max_depth=4)
            for c in c1.clauses:
                assert len(c.directional) + len(c.local_gate) <= 4
            for c in c2.clauses:
                assert len(c.directional) + len(c.local_gate) <= 4


class TestMutateAttemptedEdits:
    def test_rate_zero_no_op(self) -> None:
        rng = random.Random(7)
        g = random_genome(
            rng, "g", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        for _ in range(50):
            out = mutate(
                g,
                rng,
                0.0,
                max_clause=1,
                max_depth=4,
                registry=DUMMY_REGISTRY,
                n_edit_max=3,
            )
            assert out == g

    def test_rate_one_attempts_k_times(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """rate=1, K=3 で kernel が 3 回呼ばれることを spy で検証。"""
        rng = random.Random(8)
        g = random_genome(
            rng, "g", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        counter = {"n": 0}
        kernel_names = {
            "weight_perturb",
            "params_perturb",
            "signal_add",
            "signal_del",
            "clause_add",
            "clause_del",
            "position_perturb",
            "risk_perturb",
        }
        orig_choice = random.Random.choice

        def spy_choice(self: random.Random, seq):
            result = orig_choice(self, seq)
            if isinstance(result, str) and result in kernel_names:
                counter["n"] += 1
            return result

        monkeypatch.setattr(random.Random, "choice", spy_choice)
        mutate(
            g,
            random.Random(100),
            1.0,
            max_clause=1,
            max_depth=4,
            registry=DUMMY_REGISTRY,
            n_edit_max=3,
        )
        assert counter["n"] == 3


class TestMutate:
    def test_passes_enforce(self) -> None:
        rng = random.Random(9)
        g = random_genome(
            rng, "g", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        for _ in range(100):
            out = mutate(
                g,
                rng,
                0.5,
                max_clause=1,
                max_depth=4,
                registry=DUMMY_REGISTRY,
                n_edit_max=3,
            )
            # 冪等性で検証
            assert enforce_consistency(out) == out

    def test_directional_at_least_one(self) -> None:
        rng = random.Random(10)
        g = random_genome(
            rng, "g", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        for _ in range(100):
            out = mutate(
                g,
                rng,
                1.0,
                max_clause=1,
                max_depth=4,
                registry=DUMMY_REGISTRY,
                n_edit_max=5,
            )
            for c in out.clauses:
                assert len(c.directional) >= 1

    def test_clauses_at_least_one(self) -> None:
        rng = random.Random(11)
        g = random_genome(
            rng, "g", 10000, max_clause=2, max_depth=4, registry=DUMMY_REGISTRY
        )
        for _ in range(100):
            out = mutate(
                g,
                rng,
                1.0,
                max_clause=2,
                max_depth=4,
                registry=DUMMY_REGISTRY,
                n_edit_max=5,
            )
            assert len(out.clauses) >= 1

    def test_seed_deterministic(self) -> None:
        g1 = random_genome(
            random.Random(12),
            "g",
            10000,
            max_clause=1,
            max_depth=4,
            registry=DUMMY_REGISTRY,
        )
        g2 = random_genome(
            random.Random(12),
            "g",
            10000,
            max_clause=1,
            max_depth=4,
            registry=DUMMY_REGISTRY,
        )
        assert g1 == g2
        out1 = mutate(
            g1,
            random.Random(99),
            0.5,
            max_clause=1,
            max_depth=4,
            registry=DUMMY_REGISTRY,
            n_edit_max=3,
        )
        out2 = mutate(
            g2,
            random.Random(99),
            0.5,
            max_clause=1,
            max_depth=4,
            registry=DUMMY_REGISTRY,
            n_edit_max=3,
        )
        assert out1 == out2

    def test_rate_invalid_raises(self) -> None:
        rng = random.Random(13)
        g = random_genome(
            rng, "g", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        with pytest.raises(ValueError):
            mutate(
                g,
                rng,
                -0.1,
                max_clause=1,
                max_depth=4,
                registry=DUMMY_REGISTRY,
                n_edit_max=3,
            )
        with pytest.raises(ValueError):
            mutate(
                g,
                rng,
                1.5,
                max_clause=1,
                max_depth=4,
                registry=DUMMY_REGISTRY,
                n_edit_max=3,
            )

    def test_max_depth_preserved(self) -> None:
        rng = random.Random(14)
        g = random_genome(
            rng, "g", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY
        )
        for _ in range(50):
            out = mutate(
                g,
                rng,
                1.0,
                max_clause=1,
                max_depth=4,
                registry=DUMMY_REGISTRY,
                n_edit_max=5,
            )
            for c in out.clauses:
                assert len(c.directional) + len(c.local_gate) <= 4
