"""Composite score 計算（T007）。

Clause 合成式:
    dir_score = Σ(w_i × x_i) / Σ|w_i|  (directional の加重正規化和)
    gate      = Π gate_j                 (local_gate の積、[0, 1] pre-bounded 前提)
    clause_score = dir_score × gate
    composite = Σ(cw_k × clause_score_k) / Σ|cw_k|

pure function 群。Genome dataclass に依存するが primitive evaluator には依存しない。

T053 (devnotes/20260427-1723-composite-numba-jit) で Numba njit fused kernel
`compute_composite_at_bar_jit` を追加。prepared path の per-bar 計算を kernel
に集約し、dict 構築 / hashing / 二重 compute_clause_score 呼び出しを排除する。
既存純 Python 関数 (compute_dir_score / compute_gate / compute_clause_score /
compute_composite) は **削除しない** (unprepared path / リファレンス用)。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numba
import numpy as np

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


# ---------------------------------------------------------------------------
# T053: Numba njit fused kernel
# ---------------------------------------------------------------------------
#
# 純 Python 実装 (compute_composite + compute_clause_score) と同じ演算順序で
# composite と per-clause score を 1 関数内で同時計算する fused kernel。
#
# 数値契約:
#   - aggregate (composite 戻り値) は純 Python と np.allclose(atol=1e-6, rtol=0)
#   - per-clause score (out_clause_scores) は exact `!= 0.0` parity (T037)
#   - fastmath=False で IEEE 754 演算順序を厳守 (再結合最適化禁止)
#
# 例外契約:
#   - kernel は per-bar に呼ばれるため n_clauses == 0 を **検証しない**
#     (既存 compute_composite() は ValueError を raise する)。
#     呼び出し側 (prepare()) で len(clauses) == 0 を事前検証する契約。
#
# math.isfinite semantics:
#   - NaN, +inf, -inf を 0.0 に置換 (純 Python 実装の `if not math.isfinite(v)`
#     と同等)。Numba njit 内では `not (v == v) or v == np.inf or v == -np.inf`
#     で同等判定を構造的に再現。


@numba.njit(cache=True, fastmath=False)
def compute_composite_at_bar_jit(
    idx: int,
    clause_weights: np.ndarray,
    dir_weights_flat: np.ndarray,
    dir_offsets: np.ndarray,
    dir_signal_idx: np.ndarray,
    gate_offsets: np.ndarray,
    gate_signal_idx: np.ndarray,
    unique_signal_matrix: np.ndarray,
    out_clause_scores: np.ndarray,
) -> float:
    """Numba njit 版 composite 計算 (per-bar fused kernel)。

    Args:
        idx: 対象 bar index。`0 <= idx < n_bars` 外なら全 signal 値を 0.0 として扱う
            (純 Python prepared path の `arr[idx] if 0 <= idx < len(arr) else 0.0`
            と同 semantics)。
        clause_weights: float64[n_clauses] - 各 clause の weight。
        dir_weights_flat: float64[total_dir] - directional weight を occurrence 順に連結。
        dir_offsets: int64[n_clauses+1] - clause 境界 (CSR 形式)。
        dir_signal_idx: int64[total_dir] - 各 directional occurrence の
            unique_signal_matrix 行 index。
        gate_offsets: int64[n_clauses+1] - clause 境界 (CSR 形式)。
        gate_signal_idx: int64[total_gate] - gate occurrence の行 index。
            **gate 側は weight を持たない** (既存 compute_gate 仕様維持: 値の積のみ)。
        unique_signal_matrix: float64[n_unique_signals, n_bars] - unique
            (name, params) ごとに 1 行の precomputed signal value。
        out_clause_scores: float64[n_clauses] - **毎 bar に全 clause 分上書き**
            される preallocated buffer。途中スキップ禁止。
            T037 active_clause 判定は呼び出し側で exact `!= 0.0` で行う。

    Returns:
        composite score (float)。Σ|cw| == 0 で 0.0、n_clauses == 0 でも 0.0
        を返すが本番では prepare() で事前に ValueError を raise する契約。
    """
    n_clauses = clause_weights.shape[0]
    n_bars = unique_signal_matrix.shape[1]

    # 純 Python prepared path と同 semantics:
    #   v = arr[idx] if 0 <= idx < len(arr) else 0.0
    bars_in_range = (idx >= 0) and (idx < n_bars)

    composite_num = 0.0
    composite_denom = 0.0

    for ci in range(n_clauses):
        # 1) dir_score = Σ(w × x) / Σ|w|
        d_start = dir_offsets[ci]
        d_end = dir_offsets[ci + 1]
        dir_num = 0.0
        dir_denom = 0.0
        for k in range(d_start, d_end):
            w = dir_weights_flat[k]
            if bars_in_range:
                v = unique_signal_matrix[dir_signal_idx[k], idx]
                # math.isfinite と同等: NaN, +inf, -inf を 0.0 に
                # NOTE: `v != v` は IEEE754 NaN 判定 (NaN は自身と != True)。
                #       Numba njit 内で math.isfinite を使わないのは、
                #       純 Python 実装と構造的に同 semantics を担保するため。
                if v != v or v == np.inf or v == -np.inf:
                    v = 0.0
            else:
                v = 0.0
            dir_num += w * v
            dir_denom += abs(w)
        # Σ|w| == 0 ガード (純 Python compute_dir_score と同等)。
        # ternary ではなく if/else にしているのは、Numba kernel での
        # divide-by-zero 回避を構造的に明示するため。
        if dir_denom == 0.0:  # noqa: SIM108
            dir_score = 0.0
        else:
            dir_score = dir_num / dir_denom

        # 2) gate = Π gate_j (weight 不使用 = 既存 compute_gate 仕様)
        g_start = gate_offsets[ci]
        g_end = gate_offsets[ci + 1]
        gate = 1.0
        for k in range(g_start, g_end):
            if bars_in_range:
                v = unique_signal_matrix[gate_signal_idx[k], idx]
                # NOTE: `v != v` で NaN 判定 (上記 dir loop と同等理由)。
                if v != v or v == np.inf or v == -np.inf:
                    v = 0.0
            else:
                v = 0.0
            gate *= v

        # 3) clause_score = dir_score × gate を毎 bar 全 clause 上書き
        cs = dir_score * gate
        out_clause_scores[ci] = cs

        # 4) composite = Σ(cw × cs) / Σ|cw|
        cw = clause_weights[ci]
        composite_num += cw * cs
        composite_denom += abs(cw)

    if composite_denom == 0.0:
        return 0.0
    return composite_num / composite_denom
