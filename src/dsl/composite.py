"""Composite score 計算（T007）。

Clause 合成式:
    dir_score = Σ(w_i × x_i) / Σ|w_i|  (directional の加重正規化和)
    gate      = Π gate_j                 (local_gate の積、[0, 1] pre-bounded 前提)
    clause_score = dir_score × gate
    composite = Σ(cw_k × clause_score_k) / Σ|cw_k|

pure function 群。Genome dataclass に依存するが primitive evaluator には依存しない。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from src.dsl.genome import ClauseConfig, SignalConfig


def compute_dir_score(
    signals: Sequence[SignalConfig], values: Mapping[str, float]
) -> float:
    """directional 加重和の正規化: Σ(w_i × x_i) / Σ|w_i|。

    Args:
        signals: directional signal 群（空は 0.0 を返す）。
        values: signal name → primitive 評価値（本 TODO では tanh 等 [-1, 1] 想定）。

    Returns:
        正規化された方向性スコア。signals 空または Σ|w_i| == 0 の場合は 0.0。
    """
    if not signals:
        return 0.0
    num = 0.0
    denom = 0.0
    for sig in signals:
        num += sig.weight * values[sig.name]
        denom += abs(sig.weight)
    if denom == 0.0:
        return 0.0
    return num / denom


def compute_gate(
    signals: Sequence[SignalConfig], values: Mapping[str, float]
) -> float:
    """local_gate の積: Π gate_j。

    本 TODO では primitive 側で sigmoid 済み [0, 1] 前提（pre-bounded）。
    signals が空の場合は 1.0 を返す（no-gate = pass-through）。

    Args:
        signals: local_gate signal 群。
        values: signal name → [0, 1] 範囲の gate 値。

    Returns:
        gate 積。signals 空で 1.0。
    """
    g = 1.0
    for sig in signals:
        g *= values[sig.name]
    return g


def compute_clause_score(
    clause: ClauseConfig, values: Mapping[str, float]
) -> float:
    """単一 clause の合成: dir_score × gate。"""
    dir_s = compute_dir_score(clause.directional, values)
    gate = compute_gate(clause.local_gate, values)
    return dir_s * gate


def compute_composite(
    clauses: Sequence[ClauseConfig],
    values_per_clause: Sequence[Mapping[str, float]],
) -> float:
    """複数 clause の加重合成: Σ(cw_k × cs_k) / Σ|cw_k|。

    Args:
        clauses: 1-3 個の clause。空は ValueError。
        values_per_clause: 各 clause の primitive 評価値辞書。len は clauses と一致必須。

    Returns:
        composite score。Σ|cw_k| == 0 の場合は 0.0。

    Raises:
        ValueError: clauses と values_per_clause の長さ不一致、または clauses が空。
    """
    if len(clauses) != len(values_per_clause):
        raise ValueError(
            f"clauses len={len(clauses)} != values_per_clause len={len(values_per_clause)}"
        )
    if not clauses:
        raise ValueError("clauses must not be empty")
    num = 0.0
    denom = 0.0
    for clause, values in zip(clauses, values_per_clause, strict=True):
        cs = compute_clause_score(clause, values)
        num += clause.weight * cs
        denom += abs(clause.weight)
    if denom == 0.0:
        return 0.0
    return num / denom


def is_close(a: float, b: float, *, abs_tol: float = 1e-9) -> bool:
    """テスト用 helper: math.isclose の tolerance wrapper."""
    return math.isclose(a, b, abs_tol=abs_tol)
