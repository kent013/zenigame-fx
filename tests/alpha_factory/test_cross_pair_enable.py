"""T114: cross-pair enable (multi-pair shadow 有効化) の config/CLI plumbing tests。

run_ga の cp_inputs 配線・_load_holdout_only の DB 依存統合は R87 (multi-pair run) で
検証。本テストは config default 不変 + yaml/CLI plumbing + ANCHOR_PAIRS 契約を固める。
"""

from __future__ import annotations

import argparse

from src.alpha_factory.cross_pair import ANCHOR_PAIRS, CrossPairConfig


def test_cross_pair_config_enable_default_false() -> None:
    """T114: enable は default False (= cross-pair skip、現状挙動不変)。"""
    assert CrossPairConfig().enable is False


def test_cross_pair_config_enable_settable() -> None:
    assert CrossPairConfig(enable=True).enable is True


def test_build_cross_pair_reads_enable() -> None:
    from src.alpha_factory.config import _build_cross_pair

    assert _build_cross_pair({}).enable is False
    assert _build_cross_pair({"enable": True}).enable is True
    assert _build_cross_pair({"enable": False}).enable is False


def test_anchor_pairs_covers_all_targets() -> None:
    """T114: ANCHOR_PAIRS が主要 target を 2 anchor で定義 (cross-pair 必須契約)。"""
    assert ANCHOR_PAIRS["EUR_JPY"] == ("EUR_USD", "USD_JPY")
    for target, anchors in ANCHOR_PAIRS.items():
        assert len(anchors) == 2, (target, anchors)
        assert target not in anchors, (target, anchors)  # target は anchor に含めない


def test_args_to_overrides_includes_cross_pair_enable() -> None:
    """T114: --cross-pair-enable が overrides.cross_pair.enable に伝搬。

    未指定 (None) は _deep_merge で skip され yaml default(False) 尊重。
    """
    from scripts.alpha_factory.run_ga import _args_to_overrides

    def _ns(cross_pair_enable):
        return argparse.Namespace(
            instrument=None, start=None, end=None,
            population_size=None, generations=None, mutation_rate=None,
            crossover_rate=None, tournament_size=None, elite_count=None,
            max_depth=None, fitness_metric=None, seed=None, max_workers=None,
            max_tasks_per_child=None, warmstart_ratio=None,
            warmstart_motif_archive=None, cross_pair_enable=cross_pair_enable,
            cross_pair_selection_pressure=None,
            fitness_mode=None, nsga2_selection=None,
        )

    ov_none = _args_to_overrides(_ns(None))
    assert ov_none["cross_pair"]["enable"] is None  # _deep_merge で skip される
    ov_true = _args_to_overrides(_ns(True))
    assert ov_true["cross_pair"]["enable"] is True
