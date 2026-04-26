"""T031 RPC Phase 1: feasibility 制約の単体テスト.

scripts/alpha_factory/run_ga.py の以下を検証:
- IndividualCacheEntry.selection_score (6 要素) ordering
- _selection_key(entry, fallback_active) の v2 / legacy 切替
- _is_all_infeasible(...) の cache-global 判定
- _update_cache(..., feasibility_cfg) の trade_count → feasibility/violation 計算
"""

from __future__ import annotations

import math
import random
from typing import Any

from scripts.alpha_factory.run_ga import (
    IndividualCacheEntry,
    _is_all_infeasible,
    _selection_key,
    _tournament,
    _update_cache,
)
from src.alpha_factory.config import GAFeasibilityConfig


def _make_entry(
    *,
    fitness_pen: float = 0.0,
    a: bool = False,
    b: bool = False,
    c: bool = False,
    feasible: bool = True,
    violation: float = 0.0,
    generation: int = 0,
    stage_c_feasible: bool = True,  # T045
) -> IndividualCacheEntry:
    return IndividualCacheEntry(
        generation=generation,
        fitness_pen=fitness_pen,
        stage_a_pass=a,
        stage_b_pass=b,
        stage_c_pass=c,
        feasible=feasible,
        violation_magnitude=violation,
        stage_c_feasible=stage_c_feasible,
    )


def test_feasible_individual_wins_over_infeasible() -> None:
    """feasible=True / fitness_pen=-1 が feasible=False / fitness_pen=0 に勝つ."""
    feas = _make_entry(fitness_pen=-1.0, feasible=True, violation=0.0)
    infeas = _make_entry(fitness_pen=0.0, feasible=False, violation=5.0)
    assert feas.selection_score > infeas.selection_score


def test_violation_magnitude_orders_infeasible() -> None:
    """両方 infeasible で violation 小さい方が勝つ."""
    less = _make_entry(fitness_pen=0.0, feasible=False, violation=2.0)
    more = _make_entry(fitness_pen=0.0, feasible=False, violation=5.0)
    assert less.selection_score > more.selection_score


def test_legacy_selection_score_falls_back_to_4_tuple() -> None:
    """fallback_active=True の _selection_key は旧 4 要素を返す."""
    e = _make_entry(fitness_pen=1.5, a=True, feasible=False, violation=10.0)
    fb = _selection_key(e, fallback_active=True)
    assert fb == (0, 0, 1, 1.5)


def test_v3_selection_key_includes_stage_c_feasibility() -> None:
    """fallback_active=False の _selection_key は v3 7 要素を返す (T045)."""
    e = _make_entry(
        fitness_pen=1.5,
        a=True,
        feasible=True,
        violation=0.0,
        stage_c_feasible=True,
    )
    v3 = _selection_key(e, fallback_active=False)
    # (feasible, -violation, stage_c_feasible, C_pass, B_pass, A_pass, fitness_pen)
    assert v3 == (1, -0.0, 1, 0, 0, 1, 1.5)


def test_v3_stage_c_feasible_wins_over_infeasible_when_other_equal() -> None:
    """T045: stage_c_feasible=True が False に勝つ (他要素同条件)."""
    yes = _make_entry(
        fitness_pen=0.0, feasible=True, violation=0.0, stage_c_feasible=True
    )
    no = _make_entry(
        fitness_pen=10.0, feasible=True, violation=0.0, stage_c_feasible=False
    )
    # stage_c_feasible=True (yes) > False (no) なので fitness 高くても yes が勝つ
    assert yes.selection_score > no.selection_score


def test_is_all_infeasible_returns_true_when_no_feasible() -> None:
    cfg = GAFeasibilityConfig()
    cache = [
        _make_entry(feasible=False, violation=1.0),
        _make_entry(feasible=False, violation=2.0),
    ]
    assert _is_all_infeasible(cache, cfg) is True


def test_is_all_infeasible_returns_false_when_any_feasible() -> None:
    cfg = GAFeasibilityConfig()
    cache = [
        _make_entry(feasible=False, violation=1.0),
        _make_entry(feasible=True, violation=0.0),
    ]
    assert _is_all_infeasible(cache, cfg) is False


def test_is_all_infeasible_disabled_returns_false_even_if_all_infeasible() -> (
    None
):
    """enable_fallback_when_all_infeasible=False で fallback 自体が無効化."""
    cfg = GAFeasibilityConfig(enable_fallback_when_all_infeasible=False)
    cache = [_make_entry(feasible=False, violation=1.0)]
    assert _is_all_infeasible(cache, cfg) is False


def test_violation_nonfinite_normalized_to_inf() -> None:
    """violation が非有限 → -inf 化で確実に最下位."""
    finite = _make_entry(feasible=False, violation=1.0)
    nonfinite = _make_entry(feasible=False, violation=math.nan)
    # selection_score 2 要素目は -violation。nan は +inf 扱い → -inf
    assert finite.selection_score > nonfinite.selection_score


def test_fitness_pen_nonfinite_normalized_to_minus_inf() -> None:
    finite = _make_entry(fitness_pen=-100.0, feasible=True)
    nonfinite = _make_entry(fitness_pen=math.nan, feasible=True)
    assert finite.selection_score > nonfinite.selection_score


def test_apply_from_generation_disables_pre_threshold() -> None:
    """apply_from_generation=2, generation=1 で全 feasible=True."""
    cfg = GAFeasibilityConfig(apply_from_generation=2)

    class _DummyArchive:
        def get_row_snapshot(
            self, lane_id: str, generation: int, name: str
        ) -> dict[str, Any]:
            return {
                "fitness_pen": 0.5,
                "trade_count": 0,
                "stage_a_pass": False,
                "stage_b_pass": False,
                "stage_c_pass": False,
            }

    cache: dict[str, IndividualCacheEntry] = {}

    class _G:
        name = "g1_i0"

    _update_cache(cache, [_G()], _DummyArchive(), "lane", 1, cfg)
    # generation=1 < apply_from_generation=2 で feasibility 制約は disabled
    assert cache["g1_i0"].feasible is True
    assert cache["g1_i0"].violation_magnitude == 0.0


def test_update_cache_marks_no_trade_infeasible() -> None:
    """generation >= apply_from_generation で trade_count=0 が infeasible."""
    cfg = GAFeasibilityConfig(apply_from_generation=0, entry_count_min=1)

    class _A:
        def get_row_snapshot(
            self, lane_id: str, generation: int, name: str
        ) -> dict[str, Any]:
            return {
                "fitness_pen": 1.0,
                "trade_count": 0,
                "stage_a_pass": True,
                "stage_b_pass": False,
                "stage_c_pass": False,
            }

    cache: dict[str, IndividualCacheEntry] = {}

    class _G:
        name = "g0_i0"

    _update_cache(cache, [_G()], _A(), "lane", 0, cfg)
    assert cache["g0_i0"].feasible is False
    assert cache["g0_i0"].violation_magnitude == 1.0


def test_archive_missing_treated_as_infeasible_when_apply() -> None:
    """archive 不在 + apply=True で feasible=False, violation=entry_min."""
    cfg = GAFeasibilityConfig(apply_from_generation=0, entry_count_min=3)

    class _A:
        def get_row_snapshot(
            self, lane_id: str, generation: int, name: str
        ) -> None:
            return None

    cache: dict[str, IndividualCacheEntry] = {}

    class _G:
        name = "g0_i0"

    _update_cache(cache, [_G()], _A(), "lane", 0, cfg)
    assert cache["g0_i0"].feasible is False
    assert cache["g0_i0"].violation_magnitude == 3.0
    assert cache["g0_i0"].fitness_pen == -math.inf


def test_fallback_when_all_infeasible_uses_legacy_score() -> None:
    """全 infeasible で _select_best が legacy 4 要素で順序付ける."""
    from scripts.alpha_factory.run_ga import _select_best

    cfg = GAFeasibilityConfig()
    cache = {
        "lo": _make_entry(
            fitness_pen=-5.0, feasible=False, violation=10.0, a=True
        ),
        "hi": _make_entry(
            fitness_pen=2.0, feasible=False, violation=100.0, a=False
        ),
    }
    name, _ = _select_best(cache, cfg)
    # legacy fallback で (C,B,A,fp) lex 比較: lo は (0,0,1,-5), hi は (0,0,0,2)
    # → A_pass=True の lo が勝つ (3 番目要素 1 > 0)
    assert name == "lo"


def test_v2_score_picks_feasible_over_legacy_winner() -> None:
    """fallback 不発動時、feasible=True 個体が「legacy では負ける」状況でも勝つ."""
    from scripts.alpha_factory.run_ga import _select_best

    cfg = GAFeasibilityConfig()
    cache = {
        "feas_lo": _make_entry(
            fitness_pen=-1.0, feasible=True, violation=0.0
        ),
        "infeas_hi": _make_entry(
            fitness_pen=10.0, feasible=False, violation=1.0, a=True
        ),
    }
    # cache に feasible=True が 1 体いるので fallback 発動せず v2 で比較
    # → feasible=True > feasible=False → feas_lo が勝つ
    name, _ = _select_best(cache, cfg)
    assert name == "feas_lo"


def test_tournament_uses_global_fallback_not_local_sample() -> None:
    """tournament の sample (pop) が局所的に全 infeasible でも、cache 全体に
    feasible が存在すれば fallback 不発動 (v2 で比較される)."""
    cfg = GAFeasibilityConfig()
    rng = random.Random(0)

    class _G:
        def __init__(self, name: str) -> None:
            self.name = name

    # tournament 候補 pop は 'a','b' のみ (両方 infeasible)
    pop = [_G("a"), _G("b")]
    cache: dict[str, IndividualCacheEntry] = {
        "a": _make_entry(fitness_pen=10.0, feasible=False, violation=5.0),
        "b": _make_entry(fitness_pen=5.0, feasible=False, violation=2.0),
        # cache には feasible=True 個体 'c' が存在 (pop 外)
        "c": _make_entry(fitness_pen=-100.0, feasible=True, violation=0.0),
    }
    # cache 全体に feasible=c がいる → fallback 不発動 → v2 で比較
    # → 両者 feasible=False, violation 小さい b (-2) が大きい a (-5) に勝つ
    winner = _tournament(pop, cache, rng, 2, cfg)
    assert winner.name == "b"


def test_tournament_falls_back_when_cache_globally_infeasible() -> None:
    """cache 全体が infeasible で fallback 発動 → legacy 4要素で比較."""
    cfg = GAFeasibilityConfig()
    rng = random.Random(0)

    class _G:
        def __init__(self, name: str) -> None:
            self.name = name

    pop = [_G("a"), _G("b")]
    cache: dict[str, IndividualCacheEntry] = {
        # 両者 infeasible だが a は A_pass、b は fp 高
        "a": _make_entry(
            fitness_pen=-5.0, feasible=False, violation=10.0, a=True
        ),
        "b": _make_entry(
            fitness_pen=10.0, feasible=False, violation=2.0
        ),
    }
    # cache 全 infeasible → fallback 発動 → legacy (C,B,A,fp) で比較
    # a=(0,0,1,-5), b=(0,0,0,10) → A_pass の a が勝つ
    winner = _tournament(pop, cache, rng, 2, cfg)
    assert winner.name == "a"


def test_elite_selection_consistent_with_tournament_under_fallback() -> None:
    """全 infeasible で elite (sorted) と tournament が同じ規則 (legacy) で動く."""
    from scripts.alpha_factory.run_ga import _selection_key

    cfg = GAFeasibilityConfig()
    cache: dict[str, IndividualCacheEntry] = {
        "lo": _make_entry(
            fitness_pen=-5.0, feasible=False, violation=10.0, a=True
        ),
        "hi": _make_entry(
            fitness_pen=2.0, feasible=False, violation=100.0
        ),
    }
    fallback = _is_all_infeasible(cache.values(), cfg)
    assert fallback is True
    # elite は legacy (C,B,A,fp) で sort → A_pass の lo が先頭
    sorted_names = sorted(
        cache.keys(),
        key=lambda n: _selection_key(cache[n], fallback),
        reverse=True,
    )
    assert sorted_names[0] == "lo"


# T045 Stage C Feasibility =================================================


def test_update_cache_marks_negative_pnl_infeasible_for_c() -> None:
    """T045: total_pnl<=0 なら stage_c_feasible=False."""
    cfg = GAFeasibilityConfig(apply_from_generation=0, entry_count_min=1)

    class _A:
        def get_row_snapshot(
            self, lane_id: str, generation: int, name: str
        ) -> dict[str, Any]:
            return {
                "fitness_pen": 1.0,
                "trade_count": 100,
                "stage_a_pass": True,
                "stage_b_pass": False,
                "stage_c_pass": False,
                "total_pnl": -100.0,
                "trade_sharpe_raw": 0.5,
            }

    class _G:
        name = "g0_i0"

    cache: dict[str, IndividualCacheEntry] = {}
    _update_cache(
        cache, [_G()], _A(), "lane", 0, cfg, stage_c_feasibility_apply=True
    )
    assert cache["g0_i0"].stage_c_feasible is False


def test_update_cache_marks_negative_sharpe_infeasible_for_c() -> None:
    """T045: trade_sharpe_raw<=0 なら stage_c_feasible=False."""
    cfg = GAFeasibilityConfig(apply_from_generation=0, entry_count_min=1)

    class _A:
        def get_row_snapshot(
            self, lane_id: str, generation: int, name: str
        ) -> dict[str, Any]:
            return {
                "fitness_pen": 1.0,
                "trade_count": 100,
                "stage_a_pass": True,
                "stage_b_pass": False,
                "stage_c_pass": False,
                "total_pnl": 1000.0,
                "trade_sharpe_raw": -0.1,
            }

    class _G:
        name = "g0_i0"

    cache: dict[str, IndividualCacheEntry] = {}
    _update_cache(
        cache, [_G()], _A(), "lane", 0, cfg, stage_c_feasibility_apply=True
    )
    assert cache["g0_i0"].stage_c_feasible is False


def test_update_cache_marks_positive_both_feasible_for_c() -> None:
    """T045: PnL>0 ∧ Sharpe>0 で stage_c_feasible=True."""
    cfg = GAFeasibilityConfig(apply_from_generation=0, entry_count_min=1)

    class _A:
        def get_row_snapshot(
            self, lane_id: str, generation: int, name: str
        ) -> dict[str, Any]:
            return {
                "fitness_pen": 1.0,
                "trade_count": 100,
                "stage_a_pass": True,
                "stage_b_pass": True,
                "stage_c_pass": False,
                "total_pnl": 500.0,
                "trade_sharpe_raw": 0.3,
            }

    class _G:
        name = "g0_i0"

    cache: dict[str, IndividualCacheEntry] = {}
    _update_cache(
        cache, [_G()], _A(), "lane", 0, cfg, stage_c_feasibility_apply=True
    )
    assert cache["g0_i0"].stage_c_feasible is True


def test_update_cache_stage_c_feasibility_disabled_keeps_true() -> None:
    """T045: config で disabled なら stage_c_feasible は常に True."""
    cfg = GAFeasibilityConfig(apply_from_generation=0, entry_count_min=1)

    class _A:
        def get_row_snapshot(
            self, lane_id: str, generation: int, name: str
        ) -> dict[str, Any]:
            return {
                "fitness_pen": 1.0,
                "trade_count": 100,
                "stage_a_pass": True,
                "stage_b_pass": False,
                "stage_c_pass": False,
                "total_pnl": -1000.0,  # 負だが disabled なので True
                "trade_sharpe_raw": -0.5,
            }

    class _G:
        name = "g0_i0"

    cache: dict[str, IndividualCacheEntry] = {}
    _update_cache(
        cache, [_G()], _A(), "lane", 0, cfg, stage_c_feasibility_apply=False
    )
    assert cache["g0_i0"].stage_c_feasible is True
