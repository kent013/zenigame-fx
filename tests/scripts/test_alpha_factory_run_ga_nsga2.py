"""T112: run_ga の NSGA-II selection 配線 (_breed_nsga2 / cache mapping / bit-exact OFF)。"""

from __future__ import annotations

import random

from scripts.alpha_factory.run_ga import (
    IndividualCacheEntry,
    _breed_next_gen,
    _cache_entry_to_pareto_lite,
)
from src.alpha_factory.config import GAConfig
from src.dsl import genome_to_dict
from src.ga._dummy_registry import DUMMY_REGISTRY
from src.ga.random_gen import random_genome


def _entry(
    *,
    usable: bool,
    net: float = 100.0,
    dd: float = 0.1,
    gap: float = 0.0,
) -> IndividualCacheEntry:
    return IndividualCacheEntry(
        generation=0,
        fitness_pen=0.0,
        stage_a_pass=True,
        stage_b_pass=True,
        stage_c_pass=False,
        pareto_net_pnl=net if usable else None,
        pareto_pooled_dd=dd if usable else None,
        pareto_mission_inf_gap=gap if usable else None,
        pareto_axis_usable=usable,
    )


def _ga_cfg(*, nsga2: bool, pop: int = 6) -> GAConfig:
    return GAConfig(
        population_size=pop,
        generations=2,
        crossover_rate=0.7,
        mutation_rate=0.5,
        tournament_size=3,
        elite_count=2,
        max_depth=4,
        max_clause=1,
        nsga2_selection_enabled=nsga2,
    )


def _pop(n: int) -> list:
    rng = random.Random(0)
    return [
        random_genome(
            rng, f"g0_i{i}", 10000, max_clause=1, max_depth=4,
            registry=DUMMY_REGISTRY,
        )
        for i in range(n)
    ]


class TestCacheEntryToParetoLite:
    def test_usable_entry_maps_axes(self) -> None:
        lite = _cache_entry_to_pareto_lite(
            _entry(usable=True, net=61000.0, dd=0.07, gap=0.0)
        )
        assert lite.pareto_axis_usable is True
        assert lite.source_stage == "B"
        assert lite.net_pnl_after_cost == 61000.0
        assert lite.pooled_dd_per_fold_max == 0.07

    def test_unusable_entry_maps_to_unusable(self) -> None:
        lite = _cache_entry_to_pareto_lite(_entry(usable=False))
        assert lite.pareto_axis_usable is False
        assert lite.source_stage is None

    def test_none_entry_maps_to_unusable(self) -> None:
        lite = _cache_entry_to_pareto_lite(None)
        assert lite.pareto_axis_usable is False


class TestBreedNsga2:
    def test_nsga2_produces_population_size_genomes(self) -> None:
        pop = _pop(6)
        # 全個体 usable、 net を変えて front 差をつける
        cache = {
            g.name: _entry(usable=True, net=100.0 - i, dd=0.1 + 0.01 * i)
            for i, g in enumerate(pop)
        }
        cfg = _ga_cfg(nsga2=True, pop=6)
        next_gen, prov = _breed_next_gen(
            pop, cache, cfg, DUMMY_REGISTRY, random.Random(1), gen=1,
            run_id="run_test",
        )
        assert len(next_gen) == 6
        assert all(g.name.startswith("g1_i") for g in next_gen)
        assert len(prov) == 6

    def test_nsga2_all_unusable_falls_back_to_tournament(self) -> None:
        pop = _pop(6)
        # 全個体 unusable → eligible 0 → tournament fallback でも pop_size 体
        cache = {g.name: _entry(usable=False) for g in pop}
        cfg = _ga_cfg(nsga2=True, pop=6)
        next_gen, _prov = _breed_next_gen(
            pop, cache, cfg, DUMMY_REGISTRY, random.Random(1), gen=1,
            run_id="run_test",
        )
        assert len(next_gen) == 6

    def test_off_path_is_deterministic_and_unaffected_by_pareto(self) -> None:
        """nsga2_selection_enabled=False では Pareto 軸の有無で結果が変わらない
        (= bit-exact、 legacy tournament 経路)。"""
        pop = _pop(6)
        cache_with = {
            g.name: _entry(usable=True, net=100.0 - i)
            for i, g in enumerate(pop)
        }
        cache_without = {g.name: _entry(usable=False) for g in pop}
        cfg = _ga_cfg(nsga2=False, pop=6)
        g_with, prov_with = _breed_next_gen(
            pop, cache_with, cfg, DUMMY_REGISTRY, random.Random(7), gen=1,
            run_id="run_test",
        )
        g_without, prov_without = _breed_next_gen(
            pop, cache_without, cfg, DUMMY_REGISTRY, random.Random(7), gen=1,
            run_id="run_test",
        )
        # OFF 経路は Pareto 軸を参照しない → 名前だけでなく genome 内容・provenance
        # まで完全一致 (= bit-exact、 name は再採番で一致しうるため内容で検証)。
        assert [genome_to_dict(g) for g in g_with] == [
            genome_to_dict(g) for g in g_without
        ]
        assert prov_with == prov_without

    def test_off_path_matches_legacy_breed_when_pareto_present(self) -> None:
        """nsga2 OFF + Pareto 軸ありの結果が、 Pareto 軸を一切持たない cache の
        legacy breed と完全一致する (= Pareto 列追加が OFF 挙動に無影響、 bit-exact)。"""
        pop = _pop(6)
        # 同一の selection 関連フィールド、 pareto 軸の有無のみ差
        cache_pareto = {
            g.name: _entry(usable=True, net=100.0 - i)
            for i, g in enumerate(pop)
        }
        cache_nopareto = {
            g.name: IndividualCacheEntry(
                generation=0, fitness_pen=0.0,
                stage_a_pass=True, stage_b_pass=True, stage_c_pass=False,
            )
            for g in pop
        }
        cfg = _ga_cfg(nsga2=False, pop=6)
        a, _ = _breed_next_gen(
            pop, cache_pareto, cfg, DUMMY_REGISTRY, random.Random(3), gen=1,
            run_id="r",
        )
        b, _ = _breed_next_gen(
            pop, cache_nopareto, cfg, DUMMY_REGISTRY, random.Random(3), gen=1,
            run_id="r",
        )
        assert [genome_to_dict(g) for g in a] == [genome_to_dict(g) for g in b]
