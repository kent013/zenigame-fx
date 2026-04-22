"""T007: composite score 計算 pure function の境界条件テスト。

手計算と math.isclose(abs_tol=1e-9) で一致を確認する。
"""

from __future__ import annotations

import math

import pytest

from src.dsl.composite import (
    compute_clause_score,
    compute_composite,
    compute_dir_score,
    compute_gate,
)
from src.dsl.genome import ClauseConfig, SignalConfig

_TOL = 1e-9


def _sig(name: str, weight: float) -> SignalConfig:
    return SignalConfig(name=name, weight=weight)


# ---- dir_score ----


def test_dir_score_single_signal() -> None:
    sig = _sig("F1", 1.0)
    assert math.isclose(compute_dir_score([sig], {"F1": 0.5}), 0.5, abs_tol=_TOL)


def test_dir_score_two_signals_normalized() -> None:
    # (2*0.5 + 1*(-1)) / (2 + 1) = 0 / 3 = 0
    sigs = [_sig("F1", 2.0), _sig("F2", 1.0)]
    v = {"F1": 0.5, "F2": -1.0}
    assert math.isclose(compute_dir_score(sigs, v), 0.0, abs_tol=_TOL)


def test_dir_score_two_signals_non_zero() -> None:
    # (1*0.8 + 1*0.4) / (1 + 1) = 0.6
    sigs = [_sig("F1", 1.0), _sig("F2", 1.0)]
    v = {"F1": 0.8, "F2": 0.4}
    assert math.isclose(compute_dir_score(sigs, v), 0.6, abs_tol=_TOL)


def test_dir_score_empty() -> None:
    assert compute_dir_score([], {}) == 0.0


def test_dir_score_zero_weights_sum() -> None:
    # 通常は enforce で |w| > 0 が保証されるが、safety として 0 返却を確認
    sigs = [_sig("F1", 0.0), _sig("F2", 0.0)]
    assert compute_dir_score(sigs, {"F1": 0.5, "F2": 0.5}) == 0.0


# ---- gate ----


def test_gate_empty() -> None:
    # 空積は 1.0（no-gate）
    assert compute_gate([], {}) == 1.0


def test_gate_product() -> None:
    sigs = [_sig("M1", 1.0), _sig("M2", 1.0)]
    assert math.isclose(
        compute_gate(sigs, {"M1": 0.8, "M2": 0.5}), 0.4, abs_tol=_TOL
    )


# ---- clause_score ----


def test_compute_clause_score() -> None:
    clause = ClauseConfig(
        directional=(_sig("F1", 1.0),),
        local_gate=(_sig("M1", 1.0),),
        weight=1.0,
    )
    # dir = 0.3, gate = 0.5, cs = 0.15
    values = {"F1": 0.3, "M1": 0.5}
    assert math.isclose(
        compute_clause_score(clause, values), 0.15, abs_tol=_TOL
    )


def test_compute_clause_score_no_gate_pass_through() -> None:
    clause = ClauseConfig(
        directional=(_sig("F1", 1.0),),
        local_gate=(),
        weight=1.0,
    )
    assert math.isclose(
        compute_clause_score(clause, {"F1": 0.75}), 0.75, abs_tol=_TOL
    )


# ---- composite ----


def test_composite_single_clause() -> None:
    clause = ClauseConfig(
        directional=(_sig("F1", 1.0),), local_gate=(), weight=1.0
    )
    # composite = (1 * 0.5) / 1 = 0.5
    result = compute_composite([clause], [{"F1": 0.5}])
    assert math.isclose(result, 0.5, abs_tol=_TOL)


def test_composite_multi_clause_normalized() -> None:
    # clause1: cw=1, cs=0.5  -> contrib = 0.5
    # clause2: cw=0.5, cs=0.2 -> contrib = 0.1
    # denom = |1| + |0.5| = 1.5
    # composite = (0.5 + 0.1) / 1.5 = 0.4
    c1 = ClauseConfig(directional=(_sig("F1", 1.0),), local_gate=(), weight=1.0)
    c2 = ClauseConfig(directional=(_sig("F2", 1.0),), local_gate=(), weight=0.5)
    result = compute_composite(
        [c1, c2], [{"F1": 0.5}, {"F2": 0.2}]
    )
    assert math.isclose(result, 0.4, abs_tol=_TOL)


def test_composite_negative_clause_weight() -> None:
    # 負の clause_weight は「反転信号」として機能可能
    c = ClauseConfig(directional=(_sig("F1", 1.0),), local_gate=(), weight=-1.0)
    result = compute_composite([c], [{"F1": 0.5}])
    assert math.isclose(result, -0.5, abs_tol=_TOL)  # (-1 * 0.5) / 1 = -0.5


def test_composite_len_mismatch_raises() -> None:
    c = ClauseConfig(directional=(_sig("F1", 1.0),), local_gate=(), weight=1.0)
    with pytest.raises(ValueError, match="len="):
        compute_composite([c], [])


def test_composite_empty_clauses_raises() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        compute_composite([], [])


def test_composite_denom_zero() -> None:
    c = ClauseConfig(directional=(_sig("F1", 1.0),), local_gate=(), weight=0.0)
    assert compute_composite([c], [{"F1": 0.5}]) == 0.0
