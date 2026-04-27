"""T053: composite per-bar Numba JIT kernel の単体テスト。

devnotes/20260427-1723-composite-numba-jit/detailed-design.md 施策 2 / 5。

検証要件:
  - V2: aggregate np.allclose(atol=1e-6, rtol=0) で純 Python と一致
  - V3: T037 active_clause exact `!= 0.0` parity
  - V13: ゼロ近傍ケース (+0.0 / -0.0 / 1e-320 / cancellation) で T037 完全一致
  - kernel が NaN / +inf / -inf を 0.0 に置換する semantics (math.isfinite 同等)
  - idx out-of-range で全 signal 値が 0 として扱われる
  - clause_score_buffer が毎 bar 全 clause を上書き (途中スキップなし)
"""

from __future__ import annotations

import numpy as np
import pytest

from src.dsl.composite import (
    compute_clause_score,
    compute_composite,
    compute_composite_at_bar_jit,
)
from src.dsl.genome import ClauseConfig, SignalConfig


def _build_flat_inputs_from_clauses(
    clauses: tuple[ClauseConfig, ...],
    signal_values: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """clauses + signal_name -> values array から kernel 入力 dict を構築する.

    純 Python 実装と kernel を同じ入力で比較するための helper。
    name の出現順を deterministic にするため、登場順に行を割り振る。
    """
    n_clauses = len(clauses)
    if n_clauses == 0:
        raise ValueError("clauses must not be empty for kernel input")
    n_bars = next(iter(signal_values.values())).shape[0]

    # name -> row idx (登場順)
    name_to_row: dict[str, int] = {}
    for clause in clauses:
        for sig in (*clause.directional, *clause.local_gate):
            if sig.name not in name_to_row:
                name_to_row[sig.name] = len(name_to_row)

    n_unique = len(name_to_row)
    unique_signal_matrix = np.empty((n_unique, n_bars), dtype=np.float64)
    for name, row in name_to_row.items():
        unique_signal_matrix[row, :] = np.asarray(
            signal_values[name], dtype=np.float64
        )

    clause_weights = np.array([c.weight for c in clauses], dtype=np.float64)

    dir_offsets = [0]
    dir_weights: list[float] = []
    dir_signal_idx: list[int] = []
    gate_offsets = [0]
    gate_signal_idx: list[int] = []
    for clause in clauses:
        for sig in clause.directional:
            dir_weights.append(sig.weight)
            dir_signal_idx.append(name_to_row[sig.name])
        dir_offsets.append(len(dir_weights))
        for sig in clause.local_gate:
            gate_signal_idx.append(name_to_row[sig.name])
        gate_offsets.append(len(gate_signal_idx))

    return {
        "clause_weights": clause_weights,
        "dir_weights_flat": np.array(dir_weights, dtype=np.float64),
        "dir_offsets": np.array(dir_offsets, dtype=np.int64),
        "dir_signal_idx": np.array(dir_signal_idx, dtype=np.int64),
        "gate_offsets": np.array(gate_offsets, dtype=np.int64),
        "gate_signal_idx": np.array(gate_signal_idx, dtype=np.int64),
        "unique_signal_matrix": unique_signal_matrix,
        "clause_score_buffer": np.empty(n_clauses, dtype=np.float64),
    }


def _python_composite_at_bar(
    clauses: tuple[ClauseConfig, ...],
    signal_values: dict[str, np.ndarray],
    idx: int,
) -> tuple[float, list[float]]:
    """純 Python 実装で composite + per-clause score を計算する (oracle)."""
    n_bars = next(iter(signal_values.values())).shape[0]
    values_per_clause: list[dict[str, float]] = []
    for clause in clauses:
        vals: dict[str, float] = {}
        for sig in clause.directional:
            v = (
                float(signal_values[sig.name][idx])
                if 0 <= idx < n_bars
                else 0.0
            )
            if not np.isfinite(v):
                v = 0.0
            vals[sig.name] = v
        for sig in clause.local_gate:
            v = (
                float(signal_values[sig.name][idx])
                if 0 <= idx < n_bars
                else 0.0
            )
            if not np.isfinite(v):
                v = 0.0
            vals[sig.name] = v
        values_per_clause.append(vals)
    composite = compute_composite(clauses, values_per_clause)
    clause_scores = [
        compute_clause_score(c, vals)
        for c, vals in zip(clauses, values_per_clause, strict=True)
    ]
    return composite, clause_scores


# ---------------------------------------------------------------------------
# property-based: random genome × random bars
# ---------------------------------------------------------------------------


def _random_clause(
    rng: np.random.Generator,
    name_prefix: str,
    n_dir: int,
    n_gate: int,
) -> ClauseConfig:
    return ClauseConfig(
        directional=tuple(
            SignalConfig(
                name=f"{name_prefix}_d{i}",
                weight=float(rng.uniform(-2.0, 2.0)),
            )
            for i in range(n_dir)
        ),
        local_gate=tuple(
            SignalConfig(
                name=f"{name_prefix}_g{i}",
                weight=1.0,  # gate weight は kernel では使われない
            )
            for i in range(n_gate)
        ),
        weight=float(rng.uniform(-2.0, 2.0)),
    )


def test_jit_kernel_matches_python_impl_on_random_genomes() -> None:
    rng = np.random.default_rng(20260427)
    n_bars = 50

    for trial in range(30):
        n_clauses = int(rng.integers(1, 4))
        clauses = tuple(
            _random_clause(
                rng,
                f"c{ci}",
                n_dir=int(rng.integers(1, 4)),
                n_gate=int(rng.integers(0, 3)),
            )
            for ci in range(n_clauses)
        )
        signal_values: dict[str, np.ndarray] = {}
        for clause in clauses:
            for sig in (*clause.directional, *clause.local_gate):
                if sig.name not in signal_values:
                    signal_values[sig.name] = rng.uniform(-1.0, 1.0, size=n_bars)

        kw = _build_flat_inputs_from_clauses(clauses, signal_values)

        for idx in range(n_bars):
            py_composite, py_clause_scores = _python_composite_at_bar(
                clauses, signal_values, idx
            )
            jit_composite = compute_composite_at_bar_jit(
                idx,
                kw["clause_weights"],
                kw["dir_weights_flat"],
                kw["dir_offsets"],
                kw["dir_signal_idx"],
                kw["gate_offsets"],
                kw["gate_signal_idx"],
                kw["unique_signal_matrix"],
                kw["clause_score_buffer"],
            )
            assert np.allclose(jit_composite, py_composite, atol=1e-6, rtol=0), (
                f"trial={trial} idx={idx}: jit={jit_composite} vs py={py_composite}"
            )
            jit_clause_scores = list(kw["clause_score_buffer"])
            assert np.allclose(
                jit_clause_scores, py_clause_scores, atol=1e-6, rtol=0
            )


def test_jit_kernel_handles_nan_and_inf_inputs() -> None:
    """NaN, +inf, -inf を 0.0 に置換する (math.isfinite 同等 semantics)."""
    clauses = (
        ClauseConfig(
            directional=(
                SignalConfig(name="d1", weight=1.0),
                SignalConfig(name="d2", weight=1.0),
            ),
            local_gate=(SignalConfig(name="g1", weight=1.0),),
            weight=1.0,
        ),
    )
    signal_values = {
        "d1": np.array([np.nan, np.inf, -np.inf, 0.5], dtype=np.float64),
        "d2": np.array([np.nan, 0.0, 1.0, 0.5], dtype=np.float64),
        "g1": np.array([np.nan, 1.0, 1.0, 1.0], dtype=np.float64),
    }
    kw = _build_flat_inputs_from_clauses(clauses, signal_values)

    # idx=0: 全 signal が NaN → dir_score 0, gate 0 → composite 0
    composite_at_0 = compute_composite_at_bar_jit(
        0,
        kw["clause_weights"],
        kw["dir_weights_flat"],
        kw["dir_offsets"],
        kw["dir_signal_idx"],
        kw["gate_offsets"],
        kw["gate_signal_idx"],
        kw["unique_signal_matrix"],
        kw["clause_score_buffer"],
    )
    assert composite_at_0 == 0.0
    assert kw["clause_score_buffer"][0] == 0.0

    # idx=1: d1=+inf→0, d2=0, g1=1 → dir_score=0, gate=1, clause_score=0
    composite_at_1 = compute_composite_at_bar_jit(
        1,
        kw["clause_weights"],
        kw["dir_weights_flat"],
        kw["dir_offsets"],
        kw["dir_signal_idx"],
        kw["gate_offsets"],
        kw["gate_signal_idx"],
        kw["unique_signal_matrix"],
        kw["clause_score_buffer"],
    )
    assert composite_at_1 == 0.0

    # 純 Python と完全一致するか確認 (idx=2: d1=-inf→0, d2=1, g1=1)
    py_c, py_cs = _python_composite_at_bar(clauses, signal_values, 2)
    composite_at_2 = compute_composite_at_bar_jit(
        2,
        kw["clause_weights"],
        kw["dir_weights_flat"],
        kw["dir_offsets"],
        kw["dir_signal_idx"],
        kw["gate_offsets"],
        kw["gate_signal_idx"],
        kw["unique_signal_matrix"],
        kw["clause_score_buffer"],
    )
    assert np.allclose(composite_at_2, py_c, atol=1e-6, rtol=0)
    assert np.allclose(
        list(kw["clause_score_buffer"]), py_cs, atol=1e-6, rtol=0
    )


def test_jit_kernel_zero_clause_weight_returns_zero() -> None:
    """全 clause weight = 0 で composite が 0.0 (Σ|cw| == 0 ガード)."""
    clauses = (
        ClauseConfig(
            directional=(SignalConfig(name="d1", weight=1.0),),
            local_gate=(),
            weight=0.0,
        ),
        ClauseConfig(
            directional=(SignalConfig(name="d2", weight=1.0),),
            local_gate=(),
            weight=0.0,
        ),
    )
    signal_values = {
        "d1": np.array([0.5, 0.5], dtype=np.float64),
        "d2": np.array([0.5, 0.5], dtype=np.float64),
    }
    kw = _build_flat_inputs_from_clauses(clauses, signal_values)
    composite = compute_composite_at_bar_jit(
        0,
        kw["clause_weights"],
        kw["dir_weights_flat"],
        kw["dir_offsets"],
        kw["dir_signal_idx"],
        kw["gate_offsets"],
        kw["gate_signal_idx"],
        kw["unique_signal_matrix"],
        kw["clause_score_buffer"],
    )
    assert composite == 0.0


def test_jit_kernel_zero_dir_weight_clause_zero() -> None:
    """clause 内 dir_weight 全 0 で当該 clause score 0.0 (Σ|w| == 0 ガード)."""
    clauses = (
        ClauseConfig(
            directional=(
                SignalConfig(name="d1", weight=0.0),
                SignalConfig(name="d2", weight=0.0),
            ),
            local_gate=(),
            weight=1.0,
        ),
    )
    signal_values = {
        "d1": np.array([0.5], dtype=np.float64),
        "d2": np.array([0.7], dtype=np.float64),
    }
    kw = _build_flat_inputs_from_clauses(clauses, signal_values)
    composite = compute_composite_at_bar_jit(
        0,
        kw["clause_weights"],
        kw["dir_weights_flat"],
        kw["dir_offsets"],
        kw["dir_signal_idx"],
        kw["gate_offsets"],
        kw["gate_signal_idx"],
        kw["unique_signal_matrix"],
        kw["clause_score_buffer"],
    )
    assert composite == 0.0
    assert kw["clause_score_buffer"][0] == 0.0


def test_jit_kernel_empty_gate_acts_as_passthrough() -> None:
    """gate signal 0 個の clause で gate=1.0 (積の単位元)."""
    clauses = (
        ClauseConfig(
            directional=(SignalConfig(name="d1", weight=1.0),),
            local_gate=(),
            weight=1.0,
        ),
    )
    signal_values = {"d1": np.array([0.7], dtype=np.float64)}
    kw = _build_flat_inputs_from_clauses(clauses, signal_values)
    composite = compute_composite_at_bar_jit(
        0,
        kw["clause_weights"],
        kw["dir_weights_flat"],
        kw["dir_offsets"],
        kw["dir_signal_idx"],
        kw["gate_offsets"],
        kw["gate_signal_idx"],
        kw["unique_signal_matrix"],
        kw["clause_score_buffer"],
    )
    # dir_score = 1*0.7 / 1 = 0.7, gate = 1.0, clause_score = 0.7,
    # composite = 1*0.7 / 1 = 0.7
    assert np.allclose(composite, 0.7, atol=1e-12, rtol=0)
    assert kw["clause_score_buffer"][0] == 0.7


@pytest.mark.parametrize("idx", [-1, -10, 5, 100])
def test_jit_kernel_idx_out_of_range_returns_zero(idx: int) -> None:
    """idx < 0 / idx >= n_bars で全 signal 値が 0 として扱われる."""
    clauses = (
        ClauseConfig(
            directional=(SignalConfig(name="d1", weight=1.0),),
            local_gate=(SignalConfig(name="g1", weight=1.0),),
            weight=1.0,
        ),
    )
    signal_values = {
        "d1": np.array([0.5, 0.5, 0.5, 0.5, 0.5], dtype=np.float64),
        "g1": np.array([1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64),
    }
    kw = _build_flat_inputs_from_clauses(clauses, signal_values)
    composite = compute_composite_at_bar_jit(
        idx,
        kw["clause_weights"],
        kw["dir_weights_flat"],
        kw["dir_offsets"],
        kw["dir_signal_idx"],
        kw["gate_offsets"],
        kw["gate_signal_idx"],
        kw["unique_signal_matrix"],
        kw["clause_score_buffer"],
    )
    # out-of-range: dir_score = 0, gate = 0 (空でない gate)、clause_score = 0
    assert composite == 0.0
    assert kw["clause_score_buffer"][0] == 0.0


def test_jit_kernel_clause_score_buffer_overwritten_every_bar() -> None:
    """同じ buffer を 2 bar 連続で再利用して 2 bar 目の値が正しく上書き."""
    clauses = (
        ClauseConfig(
            directional=(SignalConfig(name="d1", weight=1.0),),
            local_gate=(),
            weight=1.0,
        ),
        ClauseConfig(
            directional=(SignalConfig(name="d2", weight=1.0),),
            local_gate=(),
            weight=1.0,
        ),
    )
    signal_values = {
        "d1": np.array([0.7, 0.0], dtype=np.float64),
        "d2": np.array([0.0, 0.4], dtype=np.float64),
    }
    kw = _build_flat_inputs_from_clauses(clauses, signal_values)
    # bar 0: clause 0 = 0.7, clause 1 = 0.0
    compute_composite_at_bar_jit(
        0,
        kw["clause_weights"],
        kw["dir_weights_flat"],
        kw["dir_offsets"],
        kw["dir_signal_idx"],
        kw["gate_offsets"],
        kw["gate_signal_idx"],
        kw["unique_signal_matrix"],
        kw["clause_score_buffer"],
    )
    assert kw["clause_score_buffer"][0] == 0.7
    assert kw["clause_score_buffer"][1] == 0.0
    # bar 1: clause 0 = 0.0 (上書き), clause 1 = 0.4 (上書き)
    compute_composite_at_bar_jit(
        1,
        kw["clause_weights"],
        kw["dir_weights_flat"],
        kw["dir_offsets"],
        kw["dir_signal_idx"],
        kw["gate_offsets"],
        kw["gate_signal_idx"],
        kw["unique_signal_matrix"],
        kw["clause_score_buffer"],
    )
    assert kw["clause_score_buffer"][0] == 0.0
    assert kw["clause_score_buffer"][1] == 0.4


def test_jit_kernel_active_clause_parity_zero_threshold() -> None:
    """exact `!= 0.0` で純 Python compute_clause_score と判定一致 (T037)."""
    clauses = (
        ClauseConfig(
            directional=(SignalConfig(name="d1", weight=1.0),),
            local_gate=(),
            weight=1.0,
        ),
        ClauseConfig(
            directional=(SignalConfig(name="d2", weight=1.0),),
            local_gate=(),
            weight=1.0,
        ),
    )
    signal_values = {
        "d1": np.array([0.7, 0.0, 1e-300], dtype=np.float64),
        "d2": np.array([0.0, 0.5, 0.0], dtype=np.float64),
    }
    kw = _build_flat_inputs_from_clauses(clauses, signal_values)

    for idx in range(3):
        compute_composite_at_bar_jit(
            idx,
            kw["clause_weights"],
            kw["dir_weights_flat"],
            kw["dir_offsets"],
            kw["dir_signal_idx"],
            kw["gate_offsets"],
            kw["gate_signal_idx"],
            kw["unique_signal_matrix"],
            kw["clause_score_buffer"],
        )
        _, py_clause_scores = _python_composite_at_bar(
            clauses, signal_values, idx
        )
        # exact != 0.0 parity (T037 semantics)
        for ci in range(2):
            jit_active = kw["clause_score_buffer"][ci] != 0.0
            py_active = py_clause_scores[ci] != 0.0
            assert jit_active == py_active, (
                f"idx={idx} ci={ci}: jit_score={kw['clause_score_buffer'][ci]} "
                f"vs py_score={py_clause_scores[ci]}"
            )


def test_jit_kernel_zero_neighborhood_signed_zero_parity() -> None:
    """V13 (Round 1 Warning 2): ゼロ近傍ケースの T037 exact parity.

    決定的ケースで純 Python と kernel の `clause_score != 0.0` 判定が一致:
      - case A: +0.0 と -0.0 が混在する weights × values
      - case B: 極小値 1e-320 (subnormal) 入力で aggregate allclose かつ T037 判定一致
      - case C: 0.0 - 0.0 で対消失する weights × values (cancellation 狙い)
    """
    # ----- case A: +0.0 / -0.0 混在 -----
    clauses_a = (
        ClauseConfig(
            directional=(
                SignalConfig(name="dp", weight=1.0),
                SignalConfig(name="dn", weight=-1.0),
            ),
            local_gate=(),
            weight=1.0,
        ),
    )
    signal_values_a = {
        "dp": np.array([0.0], dtype=np.float64),  # +0.0
        "dn": np.array([-0.0], dtype=np.float64),  # -0.0
    }
    kw_a = _build_flat_inputs_from_clauses(clauses_a, signal_values_a)
    compute_composite_at_bar_jit(
        0,
        kw_a["clause_weights"],
        kw_a["dir_weights_flat"],
        kw_a["dir_offsets"],
        kw_a["dir_signal_idx"],
        kw_a["gate_offsets"],
        kw_a["gate_signal_idx"],
        kw_a["unique_signal_matrix"],
        kw_a["clause_score_buffer"],
    )
    _, py_cs_a = _python_composite_at_bar(clauses_a, signal_values_a, 0)
    # T037 exact parity: != 0.0 判定が一致
    assert (kw_a["clause_score_buffer"][0] != 0.0) == (py_cs_a[0] != 0.0)

    # ----- case B: subnormal 1e-320 -----
    clauses_b = (
        ClauseConfig(
            directional=(SignalConfig(name="d1", weight=1.0),),
            local_gate=(),
            weight=1.0,
        ),
    )
    signal_values_b = {
        "d1": np.array([1e-320], dtype=np.float64),  # subnormal
    }
    kw_b = _build_flat_inputs_from_clauses(clauses_b, signal_values_b)
    composite_b = compute_composite_at_bar_jit(
        0,
        kw_b["clause_weights"],
        kw_b["dir_weights_flat"],
        kw_b["dir_offsets"],
        kw_b["dir_signal_idx"],
        kw_b["gate_offsets"],
        kw_b["gate_signal_idx"],
        kw_b["unique_signal_matrix"],
        kw_b["clause_score_buffer"],
    )
    py_c_b, py_cs_b = _python_composite_at_bar(clauses_b, signal_values_b, 0)
    assert np.allclose(composite_b, py_c_b, atol=1e-6, rtol=0)
    # T037 exact parity
    assert (kw_b["clause_score_buffer"][0] != 0.0) == (py_cs_b[0] != 0.0)

    # ----- case C: 対消失 (cancellation) -----
    # 1*0.5 + (-1)*0.5 = 0.0 を狙う
    clauses_c = (
        ClauseConfig(
            directional=(
                SignalConfig(name="dp", weight=1.0),
                SignalConfig(name="dn", weight=-1.0),
            ),
            local_gate=(),
            weight=1.0,
        ),
    )
    signal_values_c = {
        "dp": np.array([0.5], dtype=np.float64),
        "dn": np.array([0.5], dtype=np.float64),
    }
    kw_c = _build_flat_inputs_from_clauses(clauses_c, signal_values_c)
    composite_c = compute_composite_at_bar_jit(
        0,
        kw_c["clause_weights"],
        kw_c["dir_weights_flat"],
        kw_c["dir_offsets"],
        kw_c["dir_signal_idx"],
        kw_c["gate_offsets"],
        kw_c["gate_signal_idx"],
        kw_c["unique_signal_matrix"],
        kw_c["clause_score_buffer"],
    )
    py_c_c, py_cs_c = _python_composite_at_bar(clauses_c, signal_values_c, 0)
    assert np.allclose(composite_c, py_c_c, atol=1e-6, rtol=0)
    assert (kw_c["clause_score_buffer"][0] != 0.0) == (py_cs_c[0] != 0.0)
