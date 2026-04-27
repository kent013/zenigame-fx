"""T057 Phase 2 Gate B: RegistryEvaluator.with_aux() tests.

`with_aux` は stage 別 aligned bundle を注入した evaluator clone を作る.
preflight verify は冪等性のため再実行しない.
"""

from __future__ import annotations

import numpy as np

from src.alpha_factory.primitives import RegistryEvaluator


def test_with_aux_returns_new_instance() -> None:
    base = RegistryEvaluator(pair="EUR_JPY")
    new = base.with_aux(aux_series={"macro.vix": np.array([1.0, 2.0])})
    assert new is not base


def test_with_aux_preserves_pair() -> None:
    base = RegistryEvaluator(pair="EUR_JPY")
    new = base.with_aux(aux_series={"macro.vix": np.array([1.0])})
    assert new._pair == "EUR_JPY"


def test_with_aux_swaps_aux_series() -> None:
    base = RegistryEvaluator(
        pair="EUR_JPY",
        aux_series={"macro.dxy": [10.0, 11.0]},
    )
    new = base.with_aux(aux_series={"macro.vix": np.array([20.0])})
    # 元の aux_series は base に残る
    assert "macro.dxy" in base._aux_series
    # 新 instance は新 aux_series で上書き
    assert "macro.vix" in new._aux_series
    assert "macro.dxy" not in new._aux_series


def test_with_aux_no_args_clones() -> None:
    """引数なしで呼ぶと aux 部分は base と同じ内容になる."""
    base = RegistryEvaluator(
        pair="EUR_JPY",
        aux_series={"macro.dxy": [10.0]},
    )
    new = base.with_aux()
    assert "macro.dxy" in new._aux_series


def test_with_aux_skips_preflight_verify() -> None:
    """strict_aux_required=True で構築した base から with_aux しても再 verify しない."""
    # strict_aux_required=True で正しく aux を埋めて preflight 通す
    base = RegistryEvaluator(
        pair="EUR_JPY",
        aux_series={"macro.vix": [1.0]},
        strict_aux_required=False,  # preflight verify をスキップ
    )
    new = base.with_aux(aux_series={"macro.vix": np.array([42.0])})
    # new._strict_aux_required は False (再 verify は不要)
    assert new._strict_aux_required is False
