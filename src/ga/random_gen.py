"""Clause Genome の初期個体生成（T008）。

T007 で定義された Clause ベース Genome（SignalConfig × ClauseConfig ×
PositionConfig × RiskConfig）に対応した random 生成ルーチン群。

primitive_registry から ID / 範囲を引き、SignalConfig を組み立てる。
本 TODO では `_dummy_registry.DUMMY_REGISTRY` を tests から渡す前提で、
src/ga/random_gen.py 自体は registry I/F のみ公開。T010 primitives-registry
で正式な RegistryEvaluator が整備されたら DUMMY_REGISTRY を置換。

学術引用:
- Montana, D. J. (1995). Strongly Typed Genetic Programming. Evolutionary
  Computation, 3(2), 199-230.（category による slot 制約の理論根拠）
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
    """primitive の最小メタ情報。T010 で正式 Registry に置き換える前提の暫定型。"""

    id: str
    category: PrimitiveCategory
    domain: PrimitiveDomain
    param_schema: Mapping[str, ParamRange]


PrimitiveRegistry = Mapping[str, PrimitiveSpec]

# 生成レンジ（enforce_consistency で clip されるため、意図的にやや広めに取る）
_DIR_WEIGHT_RANGE = (0.5, 1.5)
_GATE_WEIGHT_RANGE = (-1.5, 1.5)
_CLAUSE_WEIGHT_RANGE = (0.5, 1.5)
_ENTRY_THRESHOLD_RANGE = (0.1, 0.5)
_EXIT_THRESHOLD_RANGE = (0.0, 0.3)
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
    """param_schema からパラメータ値をサンプリング。

    lo/hi の型で int / float を推論。返される dict は毎回新規作成されるので
    registry 側の schema と reference を共有しない。
    """
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

    Raises:
        ValueError: 対応 category の primitive が registry に存在しない場合。
    """
    category: PrimitiveCategory = (
        "directional" if slot == "directional" else "modulator"
    )
    pool = _filter_by_category(registry, category)
    if not pool:
        raise ValueError(
            f"random_signal_config: no primitives with category={category} in registry"
        )
    spec = rng.choice(pool)
    weight = (
        rng.uniform(*_DIR_WEIGHT_RANGE)
        if slot == "directional"
        else rng.uniform(*_GATE_WEIGHT_RANGE)
    )
    return SignalConfig(name=spec.id, weight=weight, params=random_params(rng, spec))


def random_clause(
    rng: random.Random,
    n_directional: int,
    n_gate: int,
    registry: PrimitiveRegistry,
) -> ClauseConfig:
    """1 Clause 分の directional + local_gate を生成。

    重複 name は enforce_consistency で dedupe されるが、本関数内では
    軽微な再抽選で緩和する（完全保証はしない、registry が小さい場合は重複許容）。

    Raises:
        ValueError: n_directional < 1 の場合。
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
    """PositionConfig をランダム生成。entry > exit は enforce が swap で保証。"""
    return PositionConfig(
        entry_threshold=rng.uniform(*_ENTRY_THRESHOLD_RANGE),
        exit_threshold=rng.uniform(*_EXIT_THRESHOLD_RANGE),
        max_pos=rng.randint(*_MAX_POS_RANGE),
        time_stop_min=rng.randint(*_TIME_STOP_RANGE),
    )


def random_risk_config(rng: random.Random) -> RiskConfig:
    """RiskConfig をランダム生成。"""
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
    """初期個体を生成し enforce_consistency で最終正規化して返す（bounded retry 3 回）。

    Args:
        rng: 乱数源。
        name: Genome 名。
        units: units（発注単位）。
        max_clause: clause 数上限（初期世代は 1 固定推奨、後続 TODO で段階解放）。
        max_depth: 1 clause 内の directional + local_gate の総数上限（幅）。
        registry: primitive registry。

    Raises:
        ValueError: max_clause / max_depth が 1 未満。
        RuntimeError: 3 回 retry してもゲノム生成に失敗した場合。
    """
    if max_clause < 1:
        raise ValueError("max_clause must be >= 1")
    if max_depth < 1:
        raise ValueError("max_depth must be >= 1")
    for _ in range(3):
        try:
            n_clause = rng.randint(1, max_clause)
            clauses: list[ClauseConfig] = []
            for _i in range(n_clause):
                # gate は enforce 制約と整合し最大 1 本に制限
                n_gate = rng.randint(0, min(1, max_depth - 1))
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
    raise RuntimeError(
        "random_genome: failed to generate a valid genome after 3 retries"
    )
