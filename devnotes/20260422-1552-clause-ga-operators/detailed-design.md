# Detailed Design: Clause-aware GA operators + complexity penalty (T008)

**作成日時**: 2026-04-22 16:40 (JST)
**概念設計**: `conceptual-design.md`（APPROVED_WITH_COMMENTS, Round 4）
**TODO ID**: T008

## 1. モジュール一覧

| Path | 新規/更新/削除 | 行数目安 |
|------|---------------|---------|
| `src/ga/random_gen.py` | **全面書き換え** | ~120 |
| `src/ga/_dummy_registry.py` | **新規** | ~30 |
| `src/ga/complexity.py` | **新規** | ~40 |
| `src/ga/operators.py` | **全面書き換え** | ~250 |
| `src/ga/runner.py` | **全面書き換え** | ~180 |
| `src/ga/fitness.py` | **変更なし**（NotImplementedError stub のまま） | |
| `src/ga/__init__.py` | 更新（export 刷新） | ~20 |
| `tests/ga/test_random_gen.py` | **全面書き直し** | ~150 |
| `tests/ga/test_operators.py` | **全面書き直し** | ~260 |
| `tests/ga/test_complexity.py` | **新規** | ~100 |
| `tests/ga/test_runner.py` | **全面書き直し** | ~180 |

## 2. `src/ga/random_gen.py` 詳細

```python
"""Clause Genome の初期個体生成（T008）。

primitive_registry から ID / 範囲を引き、SignalConfig を組み立てる。
本 TODO では `_dummy_registry.DUMMY_REGISTRY` を tests から渡す前提で、
src/ga/random_gen.py 自体は registry I/F のみ公開。
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from src.dsl.enforce import enforce_consistency
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)

PrimitiveCategory = Literal["directional", "modulator"]
PrimitiveDomain = Literal["generic", "pair_specific"]
ParamRange = tuple[float, float] | tuple[int, int]


@dataclass(frozen=True)
class PrimitiveSpec:
    id: str
    category: PrimitiveCategory
    domain: PrimitiveDomain
    param_schema: Mapping[str, ParamRange]


PrimitiveRegistry = Mapping[str, PrimitiveSpec]

# 生成レンジ
_DIR_WEIGHT_RANGE = (0.5, 1.5)   # enforce で [0.1, 2.0] に丸め
_GATE_WEIGHT_RANGE = (-1.5, 1.5)  # enforce で [-2.0, 2.0] に丸め
_CLAUSE_WEIGHT_RANGE = (0.5, 1.5)
_ENTRY_THRESHOLD_RANGE = (0.1, 0.5)
_EXIT_THRESHOLD_RANGE = (0.0, 0.3)  # enforce で swap
_MAX_POS_RANGE = (1, 3)
_TIME_STOP_RANGE = (0, 240)
_STOP_ATR_RANGE = (1.0, 3.0)
_TAKE_ATR_RANGE = (1.0, 4.0)


def _filter_by_category(
    registry: PrimitiveRegistry, category: PrimitiveCategory
) -> list[PrimitiveSpec]:
    return [p for p in registry.values() if p.category == category]


def random_params(
    rng: random.Random, spec: PrimitiveSpec
) -> dict[str, float | int]:
    """param_schema からパラメータ値をサンプリング。lo/hi の型で int / float を推論。"""
    out: dict[str, float | int] = {}
    for key, (lo, hi) in spec.param_schema.items():
        if isinstance(lo, int) and isinstance(hi, int):
            out[key] = rng.randint(lo, hi)
        else:
            out[key] = rng.uniform(float(lo), float(hi))
    return out


def random_signal_config(
    rng: random.Random,
    slot: Literal["directional", "local_gate"],
    registry: PrimitiveRegistry,
) -> SignalConfig:
    """slot に応じた category の primitive をランダム選択し SignalConfig を組み立てる。

    directional slot → category=directional のみ
    local_gate slot → category=modulator のみ
    """
    category: PrimitiveCategory = "directional" if slot == "directional" else "modulator"
    pool = _filter_by_category(registry, category)
    if not pool:
        raise ValueError(
            f"random_signal_config: no primitives with category={category} in registry"
        )
    spec = rng.choice(pool)
    if slot == "directional":
        weight = rng.uniform(*_DIR_WEIGHT_RANGE)
    else:
        weight = rng.uniform(*_GATE_WEIGHT_RANGE)
    return SignalConfig(name=spec.id, weight=weight, params=random_params(rng, spec))


def random_clause(
    rng: random.Random,
    n_directional: int,
    n_gate: int,
    registry: PrimitiveRegistry,
) -> ClauseConfig:
    """1 Clause 分の directional + local_gate を生成。

    重複 name は enforce_consistency で dedupe されるため、ここでは
    発生時に再抽選で軽減するが完全保証はしない。
    """
    if n_directional < 1:
        raise ValueError("random_clause: n_directional must be >= 1")
    dirs: list[SignalConfig] = []
    seen_dir: set[str] = set()
    attempts = 0
    while len(dirs) < n_directional and attempts < n_directional * 5:
        sig = random_signal_config(rng, "directional", registry)
        if sig.name not in seen_dir:
            dirs.append(sig)
            seen_dir.add(sig.name)
        attempts += 1
    # registry が小さすぎて埋まらない場合は重複許容（enforce が dedupe する）
    while len(dirs) < n_directional:
        dirs.append(random_signal_config(rng, "directional", registry))

    gates: list[SignalConfig] = []
    for _ in range(n_gate):
        gates.append(random_signal_config(rng, "local_gate", registry))

    return ClauseConfig(
        directional=tuple(dirs),
        local_gate=tuple(gates),
        weight=rng.uniform(*_CLAUSE_WEIGHT_RANGE),
    )


def random_position_config(rng: random.Random) -> PositionConfig:
    # entry > exit は enforce が swap で保証
    return PositionConfig(
        entry_threshold=rng.uniform(*_ENTRY_THRESHOLD_RANGE),
        exit_threshold=rng.uniform(*_EXIT_THRESHOLD_RANGE),
        max_pos=rng.randint(*_MAX_POS_RANGE),
        time_stop_min=rng.randint(*_TIME_STOP_RANGE),
    )


def random_risk_config(rng: random.Random) -> RiskConfig:
    return RiskConfig(
        stop_atr=rng.uniform(*_STOP_ATR_RANGE),
        take_atr=rng.uniform(*_TAKE_ATR_RANGE),
    )


def random_genome(
    rng: random.Random,
    name: str,
    units: int,
    *,
    max_clause: int,
    max_depth: int,
    registry: PrimitiveRegistry,
) -> Genome:
    """初期個体を生成。enforce_consistency を最後に通して返す（bounded retry 3 回）."""
    if max_clause < 1:
        raise ValueError("max_clause must be >= 1")
    if max_depth < 1:
        raise ValueError("max_depth must be >= 1")
    for _ in range(3):
        try:
            n_clause = rng.randint(1, max_clause)
            clauses: list[ClauseConfig] = []
            for _i in range(n_clause):
                # max_depth = directional + gate の合計上限
                n_gate = rng.randint(0, min(1, max_depth - 1))  # gate は最大 1（enforce 制約と整合）
                n_dir = rng.randint(1, max_depth - n_gate)
                clauses.append(random_clause(rng, n_dir, n_gate, registry))
            genome = Genome(
                name=name,
                units=units,
                clauses=tuple(clauses),
                position=random_position_config(rng),
                risk=random_risk_config(rng),
            )
            return enforce_consistency(genome)
        except ValueError:
            continue
    raise RuntimeError("random_genome: failed to generate a valid genome after 3 retries")
```

### 2.1 `max_depth` の意味

1 clause 内の `directional + local_gate` の signal 数上限（幅）。深さ概念ではない。
例: `max_depth=4` なら 1 clause は最大 4 signal。

### 2.2 `n_gate` を `min(1, max_depth - 1)` で制限する理由

enforce が local_gate を最大 1 本に圧縮するので、初期生成でも 0 or 1 に制限し、
enforce との整合性を取る（lossy repair の起動回数を減らす）。

## 3. `src/ga/_dummy_registry.py` 詳細

```python
"""T008 テスト / 暫定用の dummy primitive registry。

T010 primitives-registry で正式版 RegistryEvaluator が整備されたら置き換える。
本モジュールは private prefix (`_`) で公開 import を抑制。
"""

from __future__ import annotations

from typing import Final

from src.ga.random_gen import PrimitiveRegistry, PrimitiveSpec

DUMMY_REGISTRY: Final[PrimitiveRegistry] = {
    # directional
    "TrendEMA": PrimitiveSpec("TrendEMA", "directional", "generic", {"n": (5, 50)}),
    "RSIRevert": PrimitiveSpec(
        "RSIRevert", "directional", "generic", {"n": (5, 30), "level": (20.0, 80.0)}
    ),
    "DonchianBreak": PrimitiveSpec(
        "DonchianBreak", "directional", "generic", {"n": (10, 60)}
    ),
    "ZScoreRevert": PrimitiveSpec(
        "ZScoreRevert", "directional", "generic", {"n": (5, 40)}
    ),
    # modulator
    "SessionGate": PrimitiveSpec(
        "SessionGate", "modulator", "generic", {"start_h": (0, 23), "end_h": (0, 23)}
    ),
    "ATRRegimeGate": PrimitiveSpec(
        "ATRRegimeGate", "modulator", "generic", {"n": (10, 60), "k": (0.5, 2.0)}
    ),
    "TrendStrengthGate": PrimitiveSpec(
        "TrendStrengthGate", "modulator", "generic", {"n": (5, 30)}
    ),
}
```

## 4. `src/ga/complexity.py` 詳細

```python
"""複雑度ペナルティ（T008）。

Luke & Panait 2006 の parsimony pressure に基づく。
max_clause / max_depth hard cap と併用（二重化）。
"""

from __future__ import annotations

from src.dsl.genome import Genome


def genome_size_norm(genome: Genome, *, size_ref: float = 10.0) -> float:
    """Clause 構造の複雑性指標を size_ref で正規化。

    size_norm = (nodes + 0.5 * max_width + 2 * (n_clause - 1) + 0.5 * gate_nodes) / size_ref

    - nodes: 全 clause の signal 総数
    - max_width: 1 clause の最大 signal 数（深さではなく幅）
    - n_clause: clause 数
    - gate_nodes: 全 clause の local_gate signal 総数
    """
    if size_ref <= 0.0:
        raise ValueError("size_ref must be > 0")
    n_clause = len(genome.clauses)
    if n_clause == 0:
        return 0.0
    nodes = sum(len(c.directional) + len(c.local_gate) for c in genome.clauses)
    max_width = max(
        len(c.directional) + len(c.local_gate) for c in genome.clauses
    )
    gate_nodes = sum(len(c.local_gate) for c in genome.clauses)
    return (nodes + 0.5 * max_width + 2.0 * (n_clause - 1) + 0.5 * gate_nodes) / size_ref


def apply_penalty(
    fitness_raw: float,
    genome: Genome,
    *,
    alpha: float,
    size_ref: float = 10.0,
) -> float:
    """fitness_pen = fitness_raw - alpha * size_norm(genome)."""
    return fitness_raw - alpha * genome_size_norm(genome, size_ref=size_ref)
```

## 5. `src/ga/operators.py` 詳細

```python
"""Clause-aware GA operators: crossover / mutate（T008）。

設計原則:
- operator は構造不変条件を自ら守る（directional>=1、clauses>=1、weight finite）
- enforce_consistency は最終正規化（clip / swap / dedupe）
- crossover は実行可能 operator 集合から一様選択
- mutate は attempted-edits 契約（rate=0 で 0 attempts、rate=1 で K attempts）
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

CrossoverOp = Literal[
    "clause_point",
    "clause_swap",
    "directional_swap",
    "gate_swap",
    "position_swap",
    "risk_swap",
]


def _available_crossover_ops(a: Genome, b: Genome) -> list[CrossoverOp]:
    ops: list[CrossoverOp] = ["position_swap", "risk_swap", "clause_swap"]
    if min(len(a.clauses), len(b.clauses)) >= 2:
        ops.append("clause_point")
    # directional_swap: 対応 clause に len(directional) >= 2 が 1 組以上
    pair_len = min(len(a.clauses), len(b.clauses))
    for i in range(pair_len):
        if len(a.clauses[i].directional) >= 2 and len(b.clauses[i].directional) >= 2:
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
        return a, b  # 呼び出し側で前提を満たしている想定
    i = rng.choice(pairs)
    ca = a.clauses[i]
    cb = b.clauses[i]
    # gate を含んだ合計幅が max_depth を超えないよう k を共有
    gate_a = len(ca.local_gate)
    gate_b = len(cb.local_gate)
    # 子 ca' の directional 長 = k + (len(cb.directional) - k) = len(cb.directional)
    # 上限: gate_a + len(cb.directional) <= max_depth → len(cb.directional) <= max_depth - gate_a
    # 簡易化: 共有の点 k で両親の directional 長を入れ替えると子の長さは入れ替わる
    # → len(cb.directional) が max_depth - gate_a を超える場合は fallback
    if (
        len(cb.directional) + gate_a > max_depth
        or len(ca.directional) + gate_b > max_depth
    ):
        # 安全策: directional を丸ごと swap（構造保持のみ）
        new_a_clauses = list(a.clauses)
        new_b_clauses = list(b.clauses)
        new_a_clauses[i] = replace(ca, directional=cb.directional)
        new_b_clauses[i] = replace(cb, directional=ca.directional)
        # それでも超える場合は先頭から max_depth-gate で切る
        if len(cb.directional) + gate_a > max_depth:
            trim = max(1, max_depth - gate_a)
            new_a_clauses[i] = replace(new_a_clauses[i], directional=cb.directional[:trim])
        if len(ca.directional) + gate_b > max_depth:
            trim = max(1, max_depth - gate_b)
            new_b_clauses[i] = replace(new_b_clauses[i], directional=ca.directional[:trim])
        return (
            replace(a, clauses=tuple(new_a_clauses)),
            replace(b, clauses=tuple(new_b_clauses)),
        )
    # 共有点交叉: k は両親 directional 長の短い方の 1..min-1 範囲
    k_max = min(len(ca.directional), len(cb.directional)) - 1
    k = rng.randint(1, k_max)
    new_ca_dir = ca.directional[:k] + cb.directional[k:]
    new_cb_dir = cb.directional[:k] + ca.directional[k:]
    # 最低 1 本保証
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
    # 子 a は ca.directional + cb.local_gate、子 b は cb.directional + ca.local_gate
    # 幅超過時は gate を trim（directional を削ると構造不変条件違反につながるため gate 側で調整）
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


def _position_swap_crossover(a: Genome, b: Genome, rng: random.Random) -> tuple[Genome, Genome]:
    return replace(a, position=b.position), replace(b, position=a.position)


def _risk_swap_crossover(a: Genome, b: Genome, rng: random.Random) -> tuple[Genome, Genome]:
    return replace(a, risk=b.risk), replace(b, risk=a.risk)


def crossover(
    a: Genome,
    b: Genome,
    rng: random.Random,
    *,
    max_depth: int = 4,
) -> tuple[Genome, Genome]:
    """実行可能 operator 集合から一様選択、子 2 体を返す（名前は親継承）.

    各親の identity は不変（新 Genome を返す）。enforce_consistency を子に適用。
    max_depth: directional_swap の幅上限遵守に使用。
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


# ---------------- mutate ----------------

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


def _collect_signals(
    genome: Genome,
) -> list[tuple[int, Literal["directional", "local_gate"], int]]:
    out = []
    for ci, c in enumerate(genome.clauses):
        for si in range(len(c.directional)):
            out.append((ci, "directional", si))
        for si in range(len(c.local_gate)):
            out.append((ci, "local_gate", si))
    return out


def _signal_at(
    genome: Genome, ci: int, slot: Literal["directional", "local_gate"], si: int
) -> SignalConfig:
    c = genome.clauses[ci]
    return c.directional[si] if slot == "directional" else c.local_gate[si]


def _signal_spec(
    genome: Genome,
    ci: int,
    slot: Literal["directional", "local_gate"],
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
    ks: list[MutateKernel] = ["position_perturb", "risk_perturb"]
    signals = _collect_signals(genome)
    if signals:
        ks.append("weight_perturb")
    # params 非空な primitive の signal が存在するか
    has_params_target = False
    for ci, slot, si in signals:
        spec = _signal_spec(genome, ci, slot, si, registry)
        if spec is not None and spec.param_schema:
            has_params_target = True
            break
    if has_params_target:
        ks.append("params_perturb")
    # signal_add: 対象 clause に空きがある
    if any(
        (len(c.directional) + len(c.local_gate)) < max_depth for c in genome.clauses
    ):
        ks.append("signal_add")
    # signal_del: directional >= 2 or gate >= 1 の clause が存在
    if any(len(c.directional) >= 2 or len(c.local_gate) >= 1 for c in genome.clauses):
        ks.append("signal_del")
    # clause_add
    if len(genome.clauses) < max_clause:
        ks.append("clause_add")
    # clause_del
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
    new_tup = tup[:si] + (new_sig,) + tup[si + 1 :]
    if slot == "directional":
        new_c = replace(c, directional=new_tup)
    else:
        new_c = replace(c, local_gate=new_tup)
    new_clauses = list(genome.clauses)
    new_clauses[ci] = new_c
    return replace(genome, clauses=tuple(new_clauses))


def _mut_params_perturb(
    genome: Genome, rng: random.Random, registry: PrimitiveRegistry
) -> Genome:
    signals = _collect_signals(genome)
    cand: list[tuple[int, Literal["directional", "local_gate"], int]] = []
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
    new_tup = tup[:si] + (new_sig,) + tup[si + 1 :]
    new_c = (
        replace(c, directional=new_tup)
        if slot == "directional"
        else replace(c, local_gate=new_tup)
    )
    new_clauses = list(genome.clauses)
    new_clauses[ci] = new_c
    return replace(genome, clauses=tuple(new_clauses))


def _mut_signal_add(
    genome: Genome, rng: random.Random, registry: PrimitiveRegistry, max_depth: int
) -> Genome:
    # 空きのある clause から選ぶ
    cands = [
        ci
        for ci, c in enumerate(genome.clauses)
        if (len(c.directional) + len(c.local_gate)) < max_depth
    ]
    if not cands:
        return genome
    ci = rng.choice(cands)
    c = genome.clauses[ci]
    # directional / local_gate どちらに追加するか（gate は enforce が max 1 にするので上限チェック）
    slots: list[Literal["directional", "local_gate"]] = ["directional"]
    if len(c.local_gate) == 0:
        slots.append("local_gate")
    slot = rng.choice(slots)
    new_sig = random_signal_config(rng, slot, registry)
    if slot == "directional":
        new_c = replace(c, directional=c.directional + (new_sig,))
    else:
        new_c = replace(c, local_gate=c.local_gate + (new_sig,))
    new_clauses = list(genome.clauses)
    new_clauses[ci] = new_c
    return replace(genome, clauses=tuple(new_clauses))


def _mut_signal_del(
    genome: Genome, rng: random.Random, registry: PrimitiveRegistry
) -> Genome:
    # directional は最低 1 本残す
    cands: list[tuple[int, Literal["directional", "local_gate"], int]] = []
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
        new_tup = c.local_gate[:si] + c.local_gate[si + 1 :]
        new_c = replace(c, local_gate=new_tup)
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
    return replace(genome, clauses=genome.clauses + (new_c,))


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
    new_r = replace(r, stop_atr=max(0.1, stop_atr), take_atr=max(0.1, take_atr))
    return replace(genome, risk=new_r)


_MUTATE_DISPATCH = {
    "weight_perturb": _mut_weight_perturb,
    "params_perturb": _mut_params_perturb,
    "signal_del": _mut_signal_del,
    "position_perturb": _mut_position_perturb,
    "risk_perturb": _mut_risk_perturb,
}


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

    rate=0 → 0 attempts、rate=1 → n_edit_max attempts 確定。effective-diffs 保証なし。
    各 attempt は実行可能 kernel から一様選択。enforce_consistency を最終適用。
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
            break  # 理論上発生しないが保険
        kernel = rng.choice(kernels)
        if kernel == "signal_add":
            current = _mut_signal_add(current, rng, registry, max_depth)
        elif kernel == "clause_add":
            current = _mut_clause_add(current, rng, registry, max_clause, max_depth)
        elif kernel == "clause_del":
            current = _mut_clause_del(current, rng, registry)
        else:
            current = _MUTATE_DISPATCH[kernel](current, rng, registry)
    return enforce_consistency(current)
```

### 5.1 params alias 防止

`random_params` は新 dict を返すので SignalConfig 生成時点で独立。
SignalConfig `__post_init__` が `dict(params)` で defensive copy（T007 の仕様）。
crossover / mutate で `replace(sig, ...)` は新 SignalConfig を作るが、
元 SignalConfig の params dict を共有する。これは frozen dataclass で外部から書き換え不能
なので問題なし。念のためテストで alias チェック。

### 5.2 attempts 計数

`Binomial(K, p)` は `sum(1 for _ in range(K) if rng.random() < p)` で実現。
`p=0` で `random() < 0` は常に False → 0 attempts、`p=1` で `random() < 1` は常に True（[0, 1) 区間）
→ K attempts。

## 6. `src/ga/runner.py` 詳細

```python
"""GA runner — Clause-aware 対応（T008）。

evaluator を外部注入し、fitness.py の復活を T009 に委譲。
複雑度ペナルティ適用・elitism・tournament 選択は従来通り。
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace

import structlog

from src.dsl.genome import Genome
from src.ga.complexity import apply_penalty
from src.ga.operators import crossover, mutate
from src.ga.random_gen import PrimitiveRegistry, random_genome

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class EvaluationResult:
    fitness_raw: float
    meta: Mapping[str, object] = field(default_factory=dict)


Evaluator = Callable[[Genome], EvaluationResult]


@dataclass(frozen=True)
class GaConfig:
    population_size: int = 50
    generations: int = 20
    crossover_rate: float = 0.7
    mutation_rate: float = 0.3
    tournament_size: int = 3
    elite_count: int = 2
    max_clause: int = 1
    max_depth: int = 4
    units: int = 10000
    complexity_alpha: float = 0.03
    complexity_size_ref: float = 10.0
    n_edit_max: int = 3
    seed: int | None = None


@dataclass
class Individual:
    genome: Genome
    fitness_raw: float
    fitness_pen: float
    meta: Mapping[str, object] = field(default_factory=dict)


@dataclass
class GaResult:
    config: GaConfig
    best: Individual
    history: list[tuple[int, float]] = field(default_factory=list)
    final_population: list[Individual] = field(default_factory=list)


def _safe_fitness(raw: float) -> float:
    if not math.isfinite(raw):
        return -math.inf
    return raw


def _evaluate(
    genome: Genome,
    evaluator: Evaluator,
    alpha: float,
    size_ref: float,
) -> Individual:
    result = evaluator(genome)
    raw = _safe_fitness(result.fitness_raw)
    pen = apply_penalty(raw, genome, alpha=alpha, size_ref=size_ref)
    return Individual(
        genome=genome, fitness_raw=raw, fitness_pen=pen, meta=result.meta
    )


def _tournament(pop: list[Individual], rng: random.Random, k: int) -> Individual:
    sample = rng.sample(pop, k=min(k, len(pop)))
    return max(sample, key=lambda ind: ind.fitness_pen)


def _rename(genome: Genome, name: str) -> Genome:
    return replace(genome, name=name)


def run_ga(
    evaluator: Evaluator,
    config: GaConfig,
    *,
    registry: PrimitiveRegistry,
) -> GaResult:
    rng = random.Random(config.seed)
    logger.info(
        "ga.start",
        pop=config.population_size,
        generations=config.generations,
        seed=config.seed,
    )

    population = [
        random_genome(
            rng,
            name=f"g0_i{i}",
            units=config.units,
            max_clause=config.max_clause,
            max_depth=config.max_depth,
            registry=registry,
        )
        for i in range(config.population_size)
    ]
    individuals = [
        _evaluate(g, evaluator, config.complexity_alpha, config.complexity_size_ref)
        for g in population
    ]
    individuals.sort(key=lambda ind: ind.fitness_pen, reverse=True)

    best_overall = individuals[0]
    history: list[tuple[int, float]] = [(0, best_overall.fitness_pen)]

    for gen in range(1, config.generations + 1):
        new_genomes: list[Genome] = [ind.genome for ind in individuals[: config.elite_count]]
        while len(new_genomes) < config.population_size:
            p1 = _tournament(individuals, rng, config.tournament_size)
            p2 = _tournament(individuals, rng, config.tournament_size)
            if rng.random() < config.crossover_rate:
                c1, c2 = crossover(p1.genome, p2.genome, rng, max_depth=config.max_depth)
            else:
                c1, c2 = p1.genome, p2.genome
            c1 = mutate(
                c1,
                rng,
                config.mutation_rate,
                max_clause=config.max_clause,
                max_depth=config.max_depth,
                registry=registry,
                n_edit_max=config.n_edit_max,
            )
            c2 = mutate(
                c2,
                rng,
                config.mutation_rate,
                max_clause=config.max_clause,
                max_depth=config.max_depth,
                registry=registry,
                n_edit_max=config.n_edit_max,
            )
            new_genomes.append(_rename(c1, f"g{gen}_i{len(new_genomes)}"))
            if len(new_genomes) < config.population_size:
                new_genomes.append(_rename(c2, f"g{gen}_i{len(new_genomes)}"))

        individuals = [
            _evaluate(g, evaluator, config.complexity_alpha, config.complexity_size_ref)
            for g in new_genomes
        ]
        individuals.sort(key=lambda ind: ind.fitness_pen, reverse=True)
        if individuals[0].fitness_pen > best_overall.fitness_pen:
            best_overall = individuals[0]
        history.append((gen, best_overall.fitness_pen))
        logger.info(
            "ga.generation", gen=gen, best_fitness=str(best_overall.fitness_pen)
        )

    return GaResult(
        config=config,
        best=best_overall,
        history=history,
        final_population=individuals,
    )
```

## 7. `src/ga/__init__.py`

```python
"""GA package — Clause-aware operators + runner."""

from src.ga.complexity import apply_penalty, genome_size_norm
from src.ga.operators import crossover, mutate
from src.ga.random_gen import (
    PrimitiveCategory,
    PrimitiveDomain,
    PrimitiveRegistry,
    PrimitiveSpec,
    random_clause,
    random_genome,
    random_signal_config,
)
from src.ga.runner import (
    EvaluationResult,
    Evaluator,
    GaConfig,
    GaResult,
    Individual,
    run_ga,
)

__all__ = [
    "EvaluationResult",
    "Evaluator",
    "GaConfig",
    "GaResult",
    "Individual",
    "PrimitiveCategory",
    "PrimitiveDomain",
    "PrimitiveRegistry",
    "PrimitiveSpec",
    "apply_penalty",
    "crossover",
    "genome_size_norm",
    "mutate",
    "random_clause",
    "random_genome",
    "random_signal_config",
    "run_ga",
]
```

## 8. テスト詳細

### 8.1 `tests/ga/test_random_gen.py`

```python
import random

import pytest

from src.dsl.enforce import enforce_consistency
from src.ga._dummy_registry import DUMMY_REGISTRY
from src.ga.random_gen import (
    PrimitiveSpec,
    random_genome,
    random_params,
    random_signal_config,
)


class TestRandomSignalConfig:
    def test_directional_slot_uses_directional_category(self):
        rng = random.Random(0)
        sig = random_signal_config(rng, "directional", DUMMY_REGISTRY)
        assert DUMMY_REGISTRY[sig.name].category == "directional"

    def test_local_gate_slot_uses_modulator_category(self):
        rng = random.Random(0)
        sig = random_signal_config(rng, "local_gate", DUMMY_REGISTRY)
        assert DUMMY_REGISTRY[sig.name].category == "modulator"

    def test_empty_pool_raises(self):
        registry = {}
        rng = random.Random(0)
        with pytest.raises(ValueError):
            random_signal_config(rng, "directional", registry)


class TestRandomParams:
    def test_int_range_returns_int(self):
        spec = PrimitiveSpec("X", "directional", "generic", {"n": (5, 50)})
        rng = random.Random(0)
        p = random_params(rng, spec)
        assert isinstance(p["n"], int)
        assert 5 <= p["n"] <= 50

    def test_float_range_returns_float(self):
        spec = PrimitiveSpec("X", "directional", "generic", {"k": (0.5, 2.0)})
        rng = random.Random(0)
        p = random_params(rng, spec)
        assert isinstance(p["k"], float)
        assert 0.5 <= p["k"] <= 2.0


class TestRandomGenome:
    def test_passes_enforce_consistency(self):
        rng = random.Random(0)
        for i in range(20):
            g = random_genome(
                rng, f"g_{i}", 10000,
                max_clause=1, max_depth=4, registry=DUMMY_REGISTRY,
            )
            # enforce が例外出さずに恒等（または軽微 clip）
            assert enforce_consistency(g) is not None

    def test_max_clause_one(self):
        rng = random.Random(0)
        for _ in range(10):
            g = random_genome(
                rng, "g", 10000,
                max_clause=1, max_depth=4, registry=DUMMY_REGISTRY,
            )
            assert len(g.clauses) == 1

    def test_seed_deterministic(self):
        g1 = random_genome(
            random.Random(42), "g", 10000,
            max_clause=1, max_depth=4, registry=DUMMY_REGISTRY,
        )
        g2 = random_genome(
            random.Random(42), "g", 10000,
            max_clause=1, max_depth=4, registry=DUMMY_REGISTRY,
        )
        assert g1 == g2

    def test_params_no_alias(self):
        rng = random.Random(0)
        g = random_genome(
            rng, "g", 10000,
            max_clause=1, max_depth=4, registry=DUMMY_REGISTRY,
        )
        sig = g.clauses[0].directional[0]
        if sig.params:
            key = next(iter(sig.params))
            # registry の param_schema 側を mutate してもゲノムに波及しないことは
            # random_params が dict を新規作成することから自明。ここでは
            # SignalConfig.params が外部 dict reference を持たないことを確認。
            assert sig.params is not DUMMY_REGISTRY[sig.name].param_schema
```

### 8.2 `tests/ga/test_operators.py`

```python
import random

import pytest

from src.dsl.enforce import enforce_consistency
from src.ga._dummy_registry import DUMMY_REGISTRY
from src.ga.operators import (
    _available_crossover_ops,
    crossover,
    mutate,
)
from src.ga.random_gen import random_genome


@pytest.fixture
def rng():
    return random.Random(0)


@pytest.fixture
def single_clause_single_dir_parents():
    from dataclasses import replace
    r1 = random.Random(1)
    r2 = random.Random(2)
    a = random_genome(r1, "a", 10000, max_clause=1, max_depth=2, registry=DUMMY_REGISTRY)
    b = random_genome(r2, "b", 10000, max_clause=1, max_depth=2, registry=DUMMY_REGISTRY)
    # テスト用に directional を 1 本に強制
    a_c = a.clauses[0]
    b_c = b.clauses[0]
    a = replace(a, clauses=(replace(a_c, directional=a_c.directional[:1]),))
    b = replace(b, clauses=(replace(b_c, directional=b_c.directional[:1]),))
    return a, b


class TestCrossoverCandidateSet:
    def test_single_clause_single_directional(self, single_clause_single_dir_parents):
        a, b = single_clause_single_dir_parents
        ops = set(_available_crossover_ops(a, b))
        # always 3 つは必ず入る
        assert {"position_swap", "risk_swap", "clause_swap"}.issubset(ops)
        # clause_point / directional_swap は入らない
        assert "clause_point" not in ops
        assert "directional_swap" not in ops
        # gate_swap は local_gate の有無に依存
        has_gate = len(a.clauses[0].local_gate) > 0 or len(b.clauses[0].local_gate) > 0
        assert ("gate_swap" in ops) == has_gate

    def test_multi_directional_enables_directional_swap(self):
        rng = random.Random(3)
        a = random_genome(rng, "a", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY)
        b = random_genome(rng, "b", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY)
        # 少なくとも一方に directional 複数入るまで再試行
        from dataclasses import replace
        # directional 2 本を強制
        a_c = a.clauses[0]
        b_c = b.clauses[0]
        if len(a_c.directional) < 2:
            from src.ga.random_gen import random_signal_config
            extra = random_signal_config(rng, "directional", DUMMY_REGISTRY)
            a = replace(a, clauses=(replace(a_c, directional=a_c.directional + (extra,)),))
        if len(b_c.directional) < 2:
            from src.ga.random_gen import random_signal_config
            extra = random_signal_config(rng, "directional", DUMMY_REGISTRY)
            b = replace(b, clauses=(replace(b_c, directional=b_c.directional + (extra,)),))
        ops = set(_available_crossover_ops(a, b))
        assert "directional_swap" in ops

    def test_multi_clause_enables_clause_point(self):
        rng = random.Random(4)
        a = random_genome(rng, "a", 10000, max_clause=2, max_depth=4, registry=DUMMY_REGISTRY)
        # max_clause=2 なら 50% で n_clause=2
        while len(a.clauses) < 2:
            a = random_genome(rng, "a", 10000, max_clause=2, max_depth=4, registry=DUMMY_REGISTRY)
        b = random_genome(rng, "b", 10000, max_clause=2, max_depth=4, registry=DUMMY_REGISTRY)
        while len(b.clauses) < 2:
            b = random_genome(rng, "b", 10000, max_clause=2, max_depth=4, registry=DUMMY_REGISTRY)
        ops = set(_available_crossover_ops(a, b))
        assert "clause_point" in ops


class TestCrossover:
    def test_returns_two_children(self, single_clause_single_dir_parents, rng):
        a, b = single_clause_single_dir_parents
        result = crossover(a, b, rng)
        assert isinstance(result, tuple) and len(result) == 2

    def test_children_pass_enforce(self):
        rng = random.Random(5)
        a = random_genome(rng, "a", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY)
        b = random_genome(rng, "b", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY)
        for _ in range(100):
            c1, c2 = crossover(a, b, rng)
            assert enforce_consistency(c1) is not None
            assert enforce_consistency(c2) is not None

    def test_parents_unchanged(self):
        rng = random.Random(6)
        a = random_genome(rng, "a", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY)
        b = random_genome(rng, "b", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY)
        a_copy = a
        b_copy = b
        crossover(a, b, rng)
        assert a == a_copy
        assert b == b_copy


class TestMutateAttemptedEdits:
    def test_rate_zero_no_op(self):
        rng = random.Random(7)
        g = random_genome(rng, "g", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY)
        for _ in range(50):
            out = mutate(
                g, rng, 0.0,
                max_clause=1, max_depth=4, registry=DUMMY_REGISTRY, n_edit_max=3,
            )
            assert out == g

    def test_rate_one_attempts_k_times(self, monkeypatch):
        rng = random.Random(8)
        g = random_genome(rng, "g", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY)
        # 実装は Binomial = sum(rng.random() < rate) で、rate=1.0 なら [0,1) 常に < 1
        # したがって attempts = n_edit_max。kernel 呼び出し回数が K 回になることを間接検証。
        counter = {"n": 0}
        orig_choice = random.Random.choice

        def spy_choice(self, seq):
            # kernel 選択タイミングを捕捉（_available_mutate_kernels の結果が渡される時のみカウント）
            result = orig_choice(self, seq)
            if isinstance(result, str) and result in {
                "weight_perturb", "params_perturb", "signal_add", "signal_del",
                "clause_add", "clause_del", "position_perturb", "risk_perturb",
            }:
                counter["n"] += 1
            return result

        monkeypatch.setattr(random.Random, "choice", spy_choice)
        mutate(
            g, random.Random(100), 1.0,
            max_clause=1, max_depth=4, registry=DUMMY_REGISTRY, n_edit_max=3,
        )
        assert counter["n"] == 3


class TestMutate:
    def test_passes_enforce(self):
        rng = random.Random(9)
        g = random_genome(rng, "g", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY)
        for _ in range(100):
            out = mutate(
                g, rng, 0.5,
                max_clause=1, max_depth=4, registry=DUMMY_REGISTRY, n_edit_max=3,
            )
            assert enforce_consistency(out) is not None

    def test_directional_at_least_one(self):
        rng = random.Random(10)
        g = random_genome(rng, "g", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY)
        for _ in range(100):
            out = mutate(
                g, rng, 1.0,
                max_clause=1, max_depth=4, registry=DUMMY_REGISTRY, n_edit_max=5,
            )
            for c in out.clauses:
                assert len(c.directional) >= 1

    def test_clauses_at_least_one(self):
        rng = random.Random(11)
        g = random_genome(rng, "g", 10000, max_clause=2, max_depth=4, registry=DUMMY_REGISTRY)
        for _ in range(100):
            out = mutate(
                g, rng, 1.0,
                max_clause=2, max_depth=4, registry=DUMMY_REGISTRY, n_edit_max=5,
            )
            assert len(out.clauses) >= 1

    def test_seed_deterministic(self):
        g1 = random_genome(
            random.Random(12), "g", 10000,
            max_clause=1, max_depth=4, registry=DUMMY_REGISTRY,
        )
        g2 = random_genome(
            random.Random(12), "g", 10000,
            max_clause=1, max_depth=4, registry=DUMMY_REGISTRY,
        )
        assert g1 == g2
        out1 = mutate(
            g1, random.Random(99), 0.5,
            max_clause=1, max_depth=4, registry=DUMMY_REGISTRY, n_edit_max=3,
        )
        out2 = mutate(
            g2, random.Random(99), 0.5,
            max_clause=1, max_depth=4, registry=DUMMY_REGISTRY, n_edit_max=3,
        )
        assert out1 == out2

    def test_rate_invalid_raises(self):
        rng = random.Random(13)
        g = random_genome(rng, "g", 10000, max_clause=1, max_depth=4, registry=DUMMY_REGISTRY)
        with pytest.raises(ValueError):
            mutate(
                g, rng, -0.1,
                max_clause=1, max_depth=4, registry=DUMMY_REGISTRY, n_edit_max=3,
            )
        with pytest.raises(ValueError):
            mutate(
                g, rng, 1.5,
                max_clause=1, max_depth=4, registry=DUMMY_REGISTRY, n_edit_max=3,
            )
```

### 8.3 `tests/ga/test_complexity.py`

```python
import pytest

from src.dsl.genome import ClauseConfig, Genome, PositionConfig, RiskConfig, SignalConfig
from src.ga.complexity import apply_penalty, genome_size_norm


def make_genome(clauses: list[ClauseConfig]) -> Genome:
    return Genome(
        name="test",
        units=10000,
        clauses=tuple(clauses),
        position=PositionConfig(0.3, 0.1, 1, 0),
        risk=RiskConfig(2.0, 3.0),
    )


def sig(name: str) -> SignalConfig:
    return SignalConfig(name=name, weight=1.0)


class TestGenomeSizeNorm:
    def test_minimal(self):
        g = make_genome([ClauseConfig(directional=(sig("a"),), local_gate=(), weight=1.0)])
        # nodes=1, max_width=1, n_clause=1, gate_nodes=0
        # size_norm = (1 + 0.5*1 + 2*0 + 0.5*0) / 10 = 0.15
        assert abs(genome_size_norm(g) - 0.15) < 1e-9

    def test_with_gate(self):
        g = make_genome([
            ClauseConfig(directional=(sig("a"),), local_gate=(sig("b"),), weight=1.0)
        ])
        # nodes=2, max_width=2, n_clause=1, gate_nodes=1
        # = (2 + 1.0 + 0 + 0.5) / 10 = 0.35
        assert abs(genome_size_norm(g) - 0.35) < 1e-9

    def test_multi_clause(self):
        g = make_genome([
            ClauseConfig(directional=(sig("a"),), local_gate=(), weight=1.0),
            ClauseConfig(directional=(sig("b"),), local_gate=(), weight=1.0),
        ])
        # nodes=2, max_width=1, n_clause=2, gate_nodes=0
        # = (2 + 0.5 + 2.0 + 0) / 10 = 0.45
        assert abs(genome_size_norm(g) - 0.45) < 1e-9

    def test_invalid_size_ref(self):
        g = make_genome([ClauseConfig(directional=(sig("a"),), local_gate=(), weight=1.0)])
        with pytest.raises(ValueError):
            genome_size_norm(g, size_ref=0.0)


class TestApplyPenalty:
    def test_alpha_zero(self):
        g = make_genome([ClauseConfig(directional=(sig("a"),), local_gate=(), weight=1.0)])
        assert apply_penalty(100.0, g, alpha=0.0) == 100.0

    def test_alpha_positive_reduces(self):
        g = make_genome([ClauseConfig(directional=(sig("a"),), local_gate=(), weight=1.0)])
        pen = apply_penalty(100.0, g, alpha=0.1)
        # penalty = 0.1 * 0.15 = 0.015
        assert abs(pen - (100.0 - 0.015)) < 1e-9

    def test_negative_raw_still_subtracts(self):
        g = make_genome([ClauseConfig(directional=(sig("a"),), local_gate=(), weight=1.0)])
        pen = apply_penalty(-5.0, g, alpha=1.0)
        # -5.0 - 1.0 * 0.15
        assert abs(pen - (-5.15)) < 1e-9
```

### 8.4 `tests/ga/test_runner.py`

```python
import math

from src.ga._dummy_registry import DUMMY_REGISTRY
from src.ga.complexity import genome_size_norm
from src.ga.runner import EvaluationResult, GaConfig, run_ga


def dummy_evaluator_neg_size(genome) -> EvaluationResult:
    return EvaluationResult(fitness_raw=-genome_size_norm(genome))


def dummy_evaluator_nan(genome) -> EvaluationResult:
    return EvaluationResult(fitness_raw=float("nan"))


class TestRunGa:
    def test_small_population_completes(self):
        cfg = GaConfig(
            population_size=5, generations=2, seed=0,
            crossover_rate=0.7, mutation_rate=0.3,
            max_clause=1, max_depth=4, complexity_alpha=0.03,
        )
        result = run_ga(dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY)
        assert result.best is not None
        assert len(result.final_population) == 5
        assert len(result.history) == cfg.generations + 1

    def test_best_in_final_population(self):
        cfg = GaConfig(population_size=5, generations=2, seed=1, max_clause=1, max_depth=4)
        result = run_ga(dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY)
        genomes = [ind.genome for ind in result.final_population]
        # best は履歴の中でベストであり、現在の final_population に居るとは限らない
        # （elite_count=2 なので elite が入るはず）
        # 設計上 elite_count >= 1 で best は直近の final_population に入る
        assert result.best.genome in genomes

    def test_elitism_monotonic_best(self):
        cfg = GaConfig(
            population_size=10, generations=5, seed=2,
            elite_count=2, max_clause=1, max_depth=4,
        )
        result = run_ga(dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY)
        pen_history = [p for _, p in result.history]
        for i in range(1, len(pen_history)):
            assert pen_history[i] >= pen_history[i - 1] - 1e-9

    def test_evaluator_nan_replaced_with_neg_inf(self):
        cfg = GaConfig(population_size=5, generations=1, seed=3, max_clause=1, max_depth=4)
        result = run_ga(dummy_evaluator_nan, cfg, registry=DUMMY_REGISTRY)
        for ind in result.final_population:
            assert ind.fitness_raw == -math.inf

    def test_seed_reproducibility(self):
        cfg = GaConfig(population_size=5, generations=2, seed=42, max_clause=1, max_depth=4)
        r1 = run_ga(dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY)
        r2 = run_ga(dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY)
        assert [h[1] for h in r1.history] == [h[1] for h in r2.history]
        assert r1.best.fitness_pen == r2.best.fitness_pen

    def test_alpha_zero_pen_equals_raw(self):
        cfg = GaConfig(
            population_size=5, generations=1, seed=4,
            complexity_alpha=0.0, max_clause=1, max_depth=4,
        )
        result = run_ga(dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY)
        for ind in result.final_population:
            assert ind.fitness_pen == ind.fitness_raw

    def test_alpha_positive_pen_strictly_less_than_raw(self):
        cfg = GaConfig(
            population_size=5, generations=1, seed=4,
            complexity_alpha=0.5, complexity_size_ref=10.0,
            max_clause=1, max_depth=4,
        )
        result = run_ga(dummy_evaluator_neg_size, cfg, registry=DUMMY_REGISTRY)
        # alpha > 0 かつ size_norm > 0 なので pen < raw
        for ind in result.final_population:
            # dummy evaluator の raw は -size_norm、pen は raw - 0.5*size_norm
            assert ind.fitness_pen < ind.fitness_raw + 1e-12
```

## 9. 旧 `src/ga/` との互換性

- `GaConfig`: 旧 `fitness_metric: FitnessMetric = "total_pnl"` は削除（evaluator closure に
  閉じ込めるため不要）
- `Individual.fitness: Decimal` → `fitness_raw / fitness_pen: float` に変更
- `run_ga(bars, meta, backtest_config, config)` → `run_ga(evaluator, config, *, registry)` に変更
- `fitness.py::evaluate_genome` は T007 と同じく NotImplementedError のまま維持（T009 で復活）

## 10. 実装順序（最終）

1. `src/ga/random_gen.py` 書き換え
2. `src/ga/_dummy_registry.py` 新設
3. `src/ga/complexity.py` 新設
4. `src/ga/operators.py` 書き換え
5. `src/ga/runner.py` 書き換え
6. `src/ga/__init__.py` 更新
7. `tests/ga/test_random_gen.py` 書き直し
8. `tests/ga/test_complexity.py` 新規
9. `tests/ga/test_operators.py` 書き直し
10. `tests/ga/test_runner.py` 書き直し
11. `uv run pytest tests/ga/ tests/dsl/ -v`
12. `uv run mypy src/ga/`
13. `uv run ruff check src/ga/ tests/ga/`
