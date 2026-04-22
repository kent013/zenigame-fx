"""enforce_consistency: Clause Genome の整合性ルールを pure function で適用する（T007）。

後続 TODO `clause-ga-operators` で random_gen / crossover / mutate 各 operator の直後に
本関数を呼ぶ運用を想定。異常入力（非有限値）は clip ではなく ValueError で raise する
（下流の composite 計算への NaN 伝搬を構造的に遮断）。
"""

from __future__ import annotations

import math
from dataclasses import replace

from src.dsl.genome import ClauseConfig, Genome, PositionConfig, SignalConfig

_DIR_WEIGHT_MIN = 0.1
_DIR_WEIGHT_MAX = 2.0
_GATE_WEIGHT_MIN = -2.0
_GATE_WEIGHT_MAX = 2.0
_MAX_CLAUSES = 3


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _check_finite(value: float, field_name: str) -> float:
    """NaN / inf を検出して ValueError。clip 前に呼ぶ。"""
    if not math.isfinite(value):
        raise ValueError(
            f"enforce_consistency: non-finite value in {field_name}: {value!r}"
        )
    return value


def _enforce_directional(
    signals: tuple[SignalConfig, ...],
) -> tuple[SignalConfig, ...]:
    """directional: abs + clip [0.1, 2.0]、同一 name は後勝ちで dedupe。非有限値は raise."""
    seen: dict[str, SignalConfig] = {}
    for sig in signals:
        _check_finite(sig.weight, f"SignalConfig({sig.name}).weight")
        w = _clip(abs(sig.weight), _DIR_WEIGHT_MIN, _DIR_WEIGHT_MAX)
        seen[sig.name] = replace(sig, weight=w)
    return tuple(seen.values())


def _enforce_gate(signals: tuple[SignalConfig, ...]) -> tuple[SignalConfig, ...]:
    """local_gate: clip [-2.0, 2.0]、同一 name 後勝ち dedupe、最大 1 本（|weight| 最大）。非有限値は raise."""
    seen: dict[str, SignalConfig] = {}
    for sig in signals:
        _check_finite(sig.weight, f"SignalConfig({sig.name}).weight")
        w = _clip(sig.weight, _GATE_WEIGHT_MIN, _GATE_WEIGHT_MAX)
        seen[sig.name] = replace(sig, weight=w)
    if len(seen) <= 1:
        return tuple(seen.values())
    # 最大 |weight| 1 本のみ残す
    best = max(seen.values(), key=lambda s: abs(s.weight))
    return (best,)


def _enforce_clause(clause: ClauseConfig) -> ClauseConfig | None:
    """directional が空になった場合は None を返し、呼び出し側で除去する。非有限値は raise."""
    _check_finite(clause.weight, "ClauseConfig.weight")
    dirs = _enforce_directional(clause.directional)
    if not dirs:
        return None
    gates = _enforce_gate(clause.local_gate)
    return ClauseConfig(directional=dirs, local_gate=gates, weight=clause.weight)


def _enforce_position(pos: PositionConfig) -> PositionConfig:
    _check_finite(pos.entry_threshold, "PositionConfig.entry_threshold")
    _check_finite(pos.exit_threshold, "PositionConfig.exit_threshold")
    entry = pos.entry_threshold
    exit_ = pos.exit_threshold
    if entry <= exit_:
        # swap（entry の方が大きいのが正しい状態）
        entry, exit_ = exit_, entry
        if entry == exit_:
            # 厳密に > にするため epsilon 分離
            exit_ = entry - 1e-6
    return replace(
        pos,
        entry_threshold=entry,
        exit_threshold=exit_,
        max_pos=max(1, pos.max_pos),
        time_stop_min=max(0, pos.time_stop_min),
    )


def enforce_consistency(genome: Genome) -> Genome:
    """Genome 全体に整合性ルールを適用する pure function。

    冪等性: f(f(x)) == f(x)（有限実数入力前提）。

    Raises:
        ValueError: 全 Clause が directional 空、clauses が空、または任意の weight/threshold/ATR
                    に非有限値（NaN / inf）が含まれる場合。
    """
    new_clauses: list[ClauseConfig] = []
    for c in genome.clauses:
        fixed = _enforce_clause(c)
        if fixed is not None:
            new_clauses.append(fixed)
    if not new_clauses:
        raise ValueError(
            "enforce_consistency: all clauses lost their directional signals"
        )
    # clause 数上限
    if len(new_clauses) > _MAX_CLAUSES:
        new_clauses.sort(key=lambda c: abs(c.weight), reverse=True)
        new_clauses = new_clauses[:_MAX_CLAUSES]
    new_position = _enforce_position(genome.position)
    _check_finite(genome.risk.stop_atr, "RiskConfig.stop_atr")
    _check_finite(genome.risk.take_atr, "RiskConfig.take_atr")
    new_risk = replace(
        genome.risk,
        stop_atr=max(1e-6, genome.risk.stop_atr),
        take_atr=max(1e-6, genome.risk.take_atr),
    )
    return replace(
        genome,
        clauses=tuple(new_clauses),
        position=new_position,
        risk=new_risk,
    )
