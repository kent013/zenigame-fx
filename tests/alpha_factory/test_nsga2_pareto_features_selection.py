"""T112: select_from_pareto_features (NSGA-II lite 入口) のテスト。

ParetoFeaturesLite scalar から直接 non-dominated sort + crowding を行い、
offspring_count 件の parent_pairs を返す挙動を検証する。
"""

from __future__ import annotations

import random

from src.alpha_factory.nsga2_selection import select_from_pareto_features
from src.alpha_factory.pareto_features import ParetoFeaturesLite


def _usable(net: float, dd: float, gap: float) -> ParetoFeaturesLite:
    return ParetoFeaturesLite(
        net_pnl_after_cost=net,
        pooled_dd_per_fold_max=dd,
        mission_inf_gap=gap,
        is_feasible_invariant=True,
        pareto_axis_usable=True,
        source_stage="B",
    )


def _hashes(n: int) -> dict[int, str]:
    return {i: f"g_{i}" for i in range(n)}


def test_eligible_excludes_unusable() -> None:
    features = {
        0: _usable(100.0, 0.1, 0.0),
        1: ParetoFeaturesLite.unusable(),
        2: _usable(50.0, 0.2, 0.1),
    }
    res = select_from_pareto_features(
        features, offspring_count=4, rng=random.Random(0),
        genome_hash_by_idx=_hashes(3),
    )
    assert 1 in res.excluded_indices
    assert set(res.survivor_indices) == {0, 2}


def test_dominant_individual_ranks_first() -> None:
    # idx 0 が全軸で支配 (net 最大, dd/gap 最小) → front 1 先頭
    features = {
        0: _usable(100.0, 0.05, 0.0),
        1: _usable(40.0, 0.30, 0.5),
        2: _usable(30.0, 0.40, 0.8),
    }
    res = select_from_pareto_features(
        features, offspring_count=3, rng=random.Random(1),
        genome_hash_by_idx=_hashes(3),
    )
    assert res.survivor_indices[0] == 0
    assert res.front_assignments[0] == 1


def test_parent_pairs_length_equals_offspring_count() -> None:
    features = {i: _usable(100.0 - i, 0.1 + 0.01 * i, 0.0) for i in range(5)}
    for oc in (1, 3, 8):
        res = select_from_pareto_features(
            features, offspring_count=oc, rng=random.Random(2),
            genome_hash_by_idx=_hashes(5),
        )
        assert len(res.parent_pairs) == oc


def test_empty_eligible_returns_empty_with_warning() -> None:
    features = {0: ParetoFeaturesLite.unusable(), 1: ParetoFeaturesLite.unusable()}
    res = select_from_pareto_features(
        features, offspring_count=4, rng=random.Random(0),
        genome_hash_by_idx=_hashes(2),
    )
    assert res.survivor_indices == ()
    assert res.parent_pairs == ()
    assert "eligible_set_empty" in res.sample_size_warnings


def test_single_eligible_self_mating() -> None:
    features = {0: ParetoFeaturesLite.unusable(), 1: _usable(100.0, 0.1, 0.0)}
    res = select_from_pareto_features(
        features, offspring_count=3, rng=random.Random(0),
        genome_hash_by_idx=_hashes(2),
    )
    assert res.parent_pairs == ((1, 1), (1, 1), (1, 1))
    assert "nsga2_eligible_below_2" in res.sample_size_warnings


def test_deterministic_same_seed() -> None:
    features = {i: _usable(100.0 - i, 0.1 + 0.01 * i, 0.02 * i) for i in range(6)}
    kw = dict(offspring_count=6, genome_hash_by_idx=_hashes(6))
    r1 = select_from_pareto_features(features, rng=random.Random(42), **kw)
    r2 = select_from_pareto_features(features, rng=random.Random(42), **kw)
    assert r1.parent_pairs == r2.parent_pairs
    assert r1.survivor_indices == r2.survivor_indices


def test_unusable_when_scalar_nonfinite_excluded() -> None:
    # axis_usable=True だが scalar が None → eligible から除外 (defensive)
    bad = ParetoFeaturesLite(
        net_pnl_after_cost=None,
        pooled_dd_per_fold_max=0.1,
        mission_inf_gap=0.0,
        is_feasible_invariant=True,
        pareto_axis_usable=True,
        source_stage="B",
    )
    features = {0: bad, 1: _usable(100.0, 0.1, 0.0)}
    res = select_from_pareto_features(
        features, offspring_count=2, rng=random.Random(0),
        genome_hash_by_idx=_hashes(2),
    )
    assert set(res.survivor_indices) == {1}
    assert 0 in res.excluded_indices


def test_missing_genome_hash_raises() -> None:
    features = {0: _usable(100.0, 0.1, 0.0)}
    try:
        select_from_pareto_features(
            features, offspring_count=1, rng=random.Random(0),
            genome_hash_by_idx={},  # missing idx 0
        )
    except ValueError:
        return
    raise AssertionError("expected ValueError for missing genome_hash")
