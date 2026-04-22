"""Clause-aware GA operators: crossover / mutate（T008）。

設計原則:
- operator は構造不変条件を自ら守る（directional>=1、clauses>=1、weight finite、
  max_depth / max_clause hard cap）。
- enforce_consistency は最終正規化（clip / swap / dedupe）。
- crossover は実行可能 operator 集合から一様選択（STGP 系譜、Montana 1995）。
- mutate は attempted-edits 契約（rate=0 で 0 attempts、rate=1 で K attempts、
  effective-diffs は保証しない）。

学術引用:
- Koza, J. R. (1992). Genetic Programming. MIT Press.
- Holland, J. H. (1975). Adaptation in Natural and Artificial Systems.
- Montana, D. J. (1995). Strongly Typed Genetic Programming.
- Poli, R., Langdon, W. B., & McPhee, N. F. (2008). A Field Guide to GP.
- Luke, S., & Panait, L. (2006). A Comparison of Bloat Control Methods for GP.
"""

from __future__ import annotations

import math
import random
from dataclasses import replace
from typing import Literal

from src.dsl.enforce import enforce_consistency
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    SignalConfig,
)
from src.ga.random_gen import (
    PrimitiveRegistry,
    PrimitiveSpec,
    random_clause,
    random_params,
    random_signal_config,
)

# ============================================================
# Crossover
# ============================================================

CrossoverOp = Literal[
    "clause_point",
    "clause_swap",
    "directional_swap",
    "gate_swap",
    "position_swap",
    "risk_swap",
]


def _available_crossover_ops(a: Genome, b: Genome) -> list[CrossoverOp]:
    """両親に対して実行可能な crossover operator の集合を返す。

    `position_swap` / `risk_swap` / `clause_swap` は always で常に入るため、
    候補集合は空にならない。
    """
    ops: list[CrossoverOp] = ["position_swap", "risk_swap", "clause_swap"]
    if min(len(a.clauses), len(b.clauses)) >= 2:
        ops.append("clause_point")
    pair_len = min(len(a.clauses), len(b.clauses))
    # directional_swap: 対応 clause に len(directional) >= 2 が 1 組以上
    for i in range(pair_len):
        if (
            len(a.clauses[i].directional) >= 2
            and len(b.clauses[i].directional) >= 2
        ):
            ops.append("directional_swap")
            break
    # gate_swap: 対応 clause の local_gate が片方でも非空
    for i in range(pair_len):
        if len(a.clauses[i].local_gate) > 0 or len(b.clauses[i].local_gate) > 0:
            ops.append("gate_swap")
            break
    return ops


def _clause_point_crossover(
    a: Genome, b: Genome, rng: random.Random
) -> tuple[Genome, Genome]:
    k = rng.randint(1, min(len(a.clauses), len(b.clauses)) - 1)
    c1 = replace(a, clauses=a.clauses[:k] + b.clauses[k:])
    c2 = replace(b, clauses=b.clauses[:k] + a.clauses[k:])
    return c1, c2


def _clause_swap_crossover(
    a: Genome, b: Genome, rng: random.Random
) -> tuple[Genome, Genome]:
    i = rng.randrange(len(a.clauses))
    j = rng.randrange(len(b.clauses))
    new_a = list(a.clauses)
    new_b = list(b.clauses)
    new_a[i], new_b[j] = new_b[j], new_a[i]
    return replace(a, clauses=tuple(new_a)), replace(b, clauses=tuple(new_b))


def _directional_swap_crossover(
    a: Genome,
    b: Genome,
    rng: random.Random,
    max_depth: int,
) -> tuple[Genome, Genome]:
    """directional tuple 点交叉。max_depth を超えないよう切断点を共有する。"""
    pair_len = min(len(a.clauses), len(b.clauses))
    pairs = [
        i
        for i in range(pair_len)
        if len(a.clauses[i].directional) >= 2
        and len(b.clauses[i].directional) >= 2
    ]
    if not pairs:
        return a, b
    i = rng.choice(pairs)
    ca = a.clauses[i]
    cb = b.clauses[i]
    gate_a = len(ca.local_gate)
    gate_b = len(cb.local_gate)
    # 幅超過時は安全策: 丸ごと swap + 必要なら trim
    if (
        len(cb.directional) + gate_a > max_depth
        or len(ca.directional) + gate_b > max_depth
    ):
        new_a_clauses = list(a.clauses)
        new_b_clauses = list(b.clauses)
        new_a_clauses[i] = replace(ca, directional=cb.directional)
        new_b_clauses[i] = replace(cb, directional=ca.directional)
        if len(cb.directional) + gate_a > max_depth:
            trim = max(1, max_depth - gate_a)
            new_a_clauses[i] = replace(
                new_a_clauses[i], directional=cb.directional[:trim]
            )
        if len(ca.directional) + gate_b > max_depth:
            trim = max(1, max_depth - gate_b)
            new_b_clauses[i] = replace(
                new_b_clauses[i], directional=ca.directional[:trim]
            )
        return (
            replace(a, clauses=tuple(new_a_clauses)),
            replace(b, clauses=tuple(new_b_clauses)),
        )
    # 共有点交叉: k は 1..min-1
    k_max = min(len(ca.directional), len(cb.directional)) - 1
    k = rng.randint(1, k_max)
    new_ca_dir = ca.directional[:k] + cb.directional[k:]
    new_cb_dir = cb.directional[:k] + ca.directional[k:]
    if not new_ca_dir:
        new_ca_dir = ca.directional[:1]
    if not new_cb_dir:
        new_cb_dir = cb.directional[:1]
    new_a_clauses = list(a.clauses)
    new_b_clauses = list(b.clauses)
    new_a_clauses[i] = replace(ca, directional=new_ca_dir)
    new_b_clauses[i] = replace(cb, directional=new_cb_dir)
    return (
        replace(a, clauses=tuple(new_a_clauses)),
        replace(b, clauses=tuple(new_b_clauses)),
    )


def _gate_swap_crossover(
    a: Genome, b: Genome, rng: random.Random, max_depth: int
) -> tuple[Genome, Genome]:
    """clause の local_gate を丸ごと swap。幅超過時は gate を trim して hard cap を保つ。"""
    pair_len = min(len(a.clauses), len(b.clauses))
    pairs = [
        i
        for i in range(pair_len)
        if len(a.clauses[i].local_gate) > 0 or len(b.clauses[i].local_gate) > 0
    ]
    if not pairs:
        return a, b
    i = rng.choice(pairs)
    ca = a.clauses[i]
    cb = b.clauses[i]
    new_gate_for_a = cb.local_gate
    new_gate_for_b = ca.local_gate
    cap_a = max(0, max_depth - len(ca.directional))
    cap_b = max(0, max_depth - len(cb.directional))
    if len(new_gate_for_a) > cap_a:
        new_gate_for_a = new_gate_for_a[:cap_a]
    if len(new_gate_for_b) > cap_b:
        new_gate_for_b = new_gate_for_b[:cap_b]
    new_a_clauses = list(a.clauses)
    new_b_clauses = list(b.clauses)
    new_a_clauses[i] = replace(ca, local_gate=new_gate_for_a)
    new_b_clauses[i] = replace(cb, local_gate=new_gate_for_b)
    return (
        replace(a, clauses=tuple(new_a_clauses)),
        replace(b, clauses=tuple(new_b_clauses)),
    )


def _position_swap_crossover(
    a: Genome, b: Genome, rng: random.Random
) -> tuple[Genome, Genome]:
    return replace(a, position=b.position), replace(b, position=a.position)


def _risk_swap_crossover(
    a: Genome, b: Genome, rng: random.Random
) -> tuple[Genome, Genome]:
    return replace(a, risk=b.risk), replace(b, risk=a.risk)


def crossover(
    a: Genome,
    b: Genome,
    rng: random.Random,
    *,
    max_depth: int = 4,
) -> tuple[Genome, Genome]:
    """実行可能 operator 集合から一様選択、子 2 体を返す（名前は親継承）。

    各親の identity は不変（新 Genome を返す）。enforce_consistency を子に適用。

    Args:
        a: 親 Genome A。
        b: 親 Genome B。
        rng: 乱数源。
        max_depth: directional_swap / gate_swap の幅上限遵守に使用。
    """
    ops = _available_crossover_ops(a, b)
    assert ops, "crossover: available operator set must not be empty"
    op = rng.choice(ops)
    if op == "clause_point":
        c1, c2 = _clause_point_crossover(a, b, rng)
    elif op == "clause_swap":
        c1, c2 = _clause_swap_crossover(a, b, rng)
    elif op == "directional_swap":
        c1, c2 = _directional_swap_crossover(a, b, rng, max_depth)
    elif op == "gate_swap":
        c1, c2 = _gate_swap_crossover(a, b, rng, max_depth)
    elif op == "position_swap":
        c1, c2 = _position_swap_crossover(a, b, rng)
    elif op == "risk_swap":
        c1, c2 = _risk_swap_crossover(a, b, rng)
    else:
        raise AssertionError(f"unreachable operator: {op}")
    return enforce_consistency(c1), enforce_consistency(c2)


# ============================================================
# Mutate
# ============================================================

MutateKernel = Literal[
    "weight_perturb",
    "params_perturb",
    "signal_add",
    "signal_del",
    "clause_add",
    "clause_del",
    "position_perturb",
    "risk_perturb",
]

_SlotLiteral = Literal["directional", "local_gate"]


def _collect_signals(
    genome: Genome,
) -> list[tuple[int, _SlotLiteral, int]]:
    out: list[tuple[int, _SlotLiteral, int]] = []
    for ci, c in enumerate(genome.clauses):
        for si in range(len(c.directional)):
            out.append((ci, "directional", si))
        for si in range(len(c.local_gate)):
            out.append((ci, "local_gate", si))
    return out


def _signal_at(
    genome: Genome, ci: int, slot: _SlotLiteral, si: int
) -> SignalConfig:
    c = genome.clauses[ci]
    return c.directional[si] if slot == "directional" else c.local_gate[si]


def _signal_spec(
    genome: Genome,
    ci: int,
    slot: _SlotLiteral,
    si: int,
    registry: PrimitiveRegistry,
) -> PrimitiveSpec | None:
    sig = _signal_at(genome, ci, slot, si)
    return registry.get(sig.name)


def _available_mutate_kernels(
    genome: Genome,
    max_clause: int,
    max_depth: int,
    registry: PrimitiveRegistry,
) -> list[MutateKernel]:
    """ゲノムに適用可能な mutation kernel の集合を返す。

    `position_perturb` / `risk_perturb` は always なので候補集合は空にならない。
    """
    ks: list[MutateKernel] = ["position_perturb", "risk_perturb"]
    signals = _collect_signals(genome)
    if signals:
        ks.append("weight_perturb")
    has_params_target = False
    for ci, slot, si in signals:
        spec = _signal_spec(genome, ci, slot, si, registry)
        if spec is not None and spec.param_schema:
            has_params_target = True
            break
    if has_params_target:
        ks.append("params_perturb")
    if any(
        (len(c.directional) + len(c.local_gate)) < max_depth
        for c in genome.clauses
    ):
        ks.append("signal_add")
    if any(
        len(c.directional) >= 2 or len(c.local_gate) >= 1 for c in genome.clauses
    ):
        ks.append("signal_del")
    if len(genome.clauses) < max_clause:
        ks.append("clause_add")
    if len(genome.clauses) > 1:
        ks.append("clause_del")
    return ks


# --- kernel implementations ---


def _mut_weight_perturb(
    genome: Genome, rng: random.Random, registry: PrimitiveRegistry
) -> Genome:
    signals = _collect_signals(genome)
    if not signals:
        return genome
    ci, slot, si = rng.choice(signals)
    c = genome.clauses[ci]
    tup = c.directional if slot == "directional" else c.local_gate
    old = tup[si]
    sigma = 0.2
    new_weight = old.weight + rng.gauss(0.0, sigma)
    if not math.isfinite(new_weight):
        new_weight = old.weight
    new_sig = replace(old, weight=new_weight)
    new_tup = (*tup[:si], new_sig, *tup[si + 1 :])
    new_c = (
        replace(c, directional=new_tup)
        if slot == "directional"
        else replace(c, local_gate=new_tup)
    )
    new_clauses = list(genome.clauses)
    new_clauses[ci] = new_c
    return replace(genome, clauses=tuple(new_clauses))


def _mut_params_perturb(
    genome: Genome, rng: random.Random, registry: PrimitiveRegistry
) -> Genome:
    signals = _collect_signals(genome)
    cand: list[tuple[int, _SlotLiteral, int]] = []
    for ci, slot, si in signals:
        spec = _signal_spec(genome, ci, slot, si, registry)
        if spec is not None and spec.param_schema:
            cand.append((ci, slot, si))
    if not cand:
        return genome
    ci, slot, si = rng.choice(cand)
    c = genome.clauses[ci]
    tup = c.directional if slot == "directional" else c.local_gate
    old = tup[si]
    spec = registry[old.name]
    new_sig = replace(old, params=random_params(rng, spec))
    new_tup = (*tup[:si], new_sig, *tup[si + 1 :])
    new_c = (
        replace(c, directional=new_tup)
        if slot == "directional"
        else replace(c, local_gate=new_tup)
    )
    new_clauses = list(genome.clauses)
    new_clauses[ci] = new_c
    return replace(genome, clauses=tuple(new_clauses))


def _mut_signal_add(
    genome: Genome,
    rng: random.Random,
    registry: PrimitiveRegistry,
    max_depth: int,
) -> Genome:
    cands = [
        ci
        for ci, c in enumerate(genome.clauses)
        if (len(c.directional) + len(c.local_gate)) < max_depth
    ]
    if not cands:
        return genome
    ci = rng.choice(cands)
    c = genome.clauses[ci]
    slots: list[_SlotLiteral] = ["directional"]
    if len(c.local_gate) == 0:
        slots.append("local_gate")
    slot = rng.choice(slots)
    new_sig = random_signal_config(rng, slot, registry)
    if slot == "directional":
        new_c = replace(c, directional=(*c.directional, new_sig))
    else:
        new_c = replace(c, local_gate=(*c.local_gate, new_sig))
    new_clauses = list(genome.clauses)
    new_clauses[ci] = new_c
    return replace(genome, clauses=tuple(new_clauses))


def _mut_signal_del(
    genome: Genome, rng: random.Random, registry: PrimitiveRegistry
) -> Genome:
    cands: list[tuple[int, _SlotLiteral, int]] = []
    for ci, c in enumerate(genome.clauses):
        if len(c.directional) >= 2:
            for si in range(len(c.directional)):
                cands.append((ci, "directional", si))
        for si in range(len(c.local_gate)):
            cands.append((ci, "local_gate", si))
    if not cands:
        return genome
    ci, slot, si = rng.choice(cands)
    c = genome.clauses[ci]
    if slot == "directional":
        new_tup = c.directional[:si] + c.directional[si + 1 :]
        new_c = replace(c, directional=new_tup)
    else:
        new_tup_gate = c.local_gate[:si] + c.local_gate[si + 1 :]
        new_c = replace(c, local_gate=new_tup_gate)
    new_clauses = list(genome.clauses)
    new_clauses[ci] = new_c
    return replace(genome, clauses=tuple(new_clauses))


def _mut_clause_add(
    genome: Genome,
    rng: random.Random,
    registry: PrimitiveRegistry,
    max_clause: int,
    max_depth: int,
) -> Genome:
    if len(genome.clauses) >= max_clause:
        return genome
    n_gate = rng.randint(0, min(1, max_depth - 1))
    n_dir = rng.randint(1, max(1, max_depth - n_gate))
    new_c = random_clause(rng, n_dir, n_gate, registry)
    return replace(genome, clauses=(*genome.clauses, new_c))


def _mut_clause_del(
    genome: Genome, rng: random.Random, registry: PrimitiveRegistry
) -> Genome:
    if len(genome.clauses) <= 1:
        return genome
    i = rng.randrange(len(genome.clauses))
    new_clauses = genome.clauses[:i] + genome.clauses[i + 1 :]
    return replace(genome, clauses=new_clauses)


def _mut_position_perturb(
    genome: Genome, rng: random.Random, registry: PrimitiveRegistry
) -> Genome:
    p = genome.position
    sigma = 0.05
    entry = p.entry_threshold + rng.gauss(0.0, sigma)
    exit_ = p.exit_threshold + rng.gauss(0.0, sigma)
    if not math.isfinite(entry):
        entry = p.entry_threshold
    if not math.isfinite(exit_):
        exit_ = p.exit_threshold
    max_pos = max(1, p.max_pos + rng.choice((-1, 0, 1)))
    time_stop = max(0, p.time_stop_min + rng.choice((-30, 0, 30)))
    new_p = replace(
        p,
        entry_threshold=entry,
        exit_threshold=exit_,
        max_pos=max_pos,
        time_stop_min=time_stop,
    )
    return replace(genome, position=new_p)


def _mut_risk_perturb(
    genome: Genome, rng: random.Random, registry: PrimitiveRegistry
) -> Genome:
    r = genome.risk
    sigma = 0.3
    stop_atr = r.stop_atr + rng.gauss(0.0, sigma)
    take_atr = r.take_atr + rng.gauss(0.0, sigma)
    if not math.isfinite(stop_atr):
        stop_atr = r.stop_atr
    if not math.isfinite(take_atr):
        take_atr = r.take_atr
    new_r = replace(
        r, stop_atr=max(0.1, stop_atr), take_atr=max(0.1, take_atr)
    )
    return replace(genome, risk=new_r)


def mutate(
    genome: Genome,
    rng: random.Random,
    mutation_rate: float,
    *,
    max_clause: int,
    max_depth: int,
    registry: PrimitiveRegistry,
    n_edit_max: int = 3,
) -> Genome:
    """attempted-edits 契約: n_attempts ~ Binomial(n_edit_max, mutation_rate).

    rate=0 → 0 attempts（完全 no-op）、rate=1 → n_edit_max attempts 確定。
    effective-diffs 保証は提供しない（kernel が no-op になるケースあり）。
    各 attempt は実行可能 kernel から一様選択。enforce_consistency を最終適用。

    Raises:
        ValueError: mutation_rate が [0, 1] 範囲外。
    """
    if not 0.0 <= mutation_rate <= 1.0:
        raise ValueError("mutation_rate must be in [0, 1]")
    n_attempts = sum(1 for _ in range(n_edit_max) if rng.random() < mutation_rate)
    if n_attempts == 0:
        return genome
    current = genome
    for _ in range(n_attempts):
        kernels = _available_mutate_kernels(current, max_clause, max_depth, registry)
        if not kernels:
            break
        kernel = rng.choice(kernels)
        if kernel == "weight_perturb":
            current = _mut_weight_perturb(current, rng, registry)
        elif kernel == "params_perturb":
            current = _mut_params_perturb(current, rng, registry)
        elif kernel == "signal_add":
            current = _mut_signal_add(current, rng, registry, max_depth)
        elif kernel == "signal_del":
            current = _mut_signal_del(current, rng, registry)
        elif kernel == "clause_add":
            current = _mut_clause_add(
                current, rng, registry, max_clause, max_depth
            )
        elif kernel == "clause_del":
            current = _mut_clause_del(current, rng, registry)
        elif kernel == "position_perturb":
            current = _mut_position_perturb(current, rng, registry)
        elif kernel == "risk_perturb":
            current = _mut_risk_perturb(current, rng, registry)
        else:
            raise AssertionError(f"unreachable kernel: {kernel}")
    return enforce_consistency(current)


__all__ = [
    "ClauseConfig",  # re-export for type hints
    "CrossoverOp",
    "MutateKernel",
    "crossover",
    "mutate",
]
