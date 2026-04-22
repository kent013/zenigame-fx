"""Clause Genome の JSON serialize / deserialize（T007）。

旧 Expr ツリー serialize (expr_to_dict/expr_from_dict) は本 TODO で削除。
ast.py / eval.py は後続 primitive 実装で再利用するため残す。
"""

from __future__ import annotations

from typing import Any

from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)


def signal_to_dict(sig: SignalConfig) -> dict[str, Any]:
    return {"name": sig.name, "weight": sig.weight, "params": dict(sig.params)}


def signal_from_dict(d: dict[str, Any]) -> SignalConfig:
    return SignalConfig(
        name=str(d["name"]),
        weight=float(d["weight"]),
        params=dict(d.get("params", {})),
    )


def clause_to_dict(c: ClauseConfig) -> dict[str, Any]:
    return {
        "directional": [signal_to_dict(s) for s in c.directional],
        "local_gate": [signal_to_dict(s) for s in c.local_gate],
        "weight": c.weight,
    }


def clause_from_dict(d: dict[str, Any]) -> ClauseConfig:
    return ClauseConfig(
        directional=tuple(signal_from_dict(s) for s in d["directional"]),
        local_gate=tuple(signal_from_dict(s) for s in d["local_gate"]),
        weight=float(d["weight"]),
    )


def position_to_dict(p: PositionConfig) -> dict[str, Any]:
    return {
        "entry_threshold": p.entry_threshold,
        "exit_threshold": p.exit_threshold,
        "max_pos": p.max_pos,
        "time_stop_min": p.time_stop_min,
    }


def position_from_dict(d: dict[str, Any]) -> PositionConfig:
    return PositionConfig(
        entry_threshold=float(d["entry_threshold"]),
        exit_threshold=float(d["exit_threshold"]),
        max_pos=int(d["max_pos"]),
        time_stop_min=int(d["time_stop_min"]),
    )


def risk_to_dict(r: RiskConfig) -> dict[str, Any]:
    return {"stop_atr": r.stop_atr, "take_atr": r.take_atr}


def risk_from_dict(d: dict[str, Any]) -> RiskConfig:
    return RiskConfig(
        stop_atr=float(d["stop_atr"]),
        take_atr=float(d["take_atr"]),
    )


def genome_to_dict(g: Genome) -> dict[str, Any]:
    return {
        "name": g.name,
        "units": g.units,
        "clauses": [clause_to_dict(c) for c in g.clauses],
        "position": position_to_dict(g.position),
        "risk": risk_to_dict(g.risk),
    }


def genome_from_dict(d: dict[str, Any]) -> Genome:
    return Genome(
        name=str(d["name"]),
        units=int(d["units"]),
        clauses=tuple(clause_from_dict(c) for c in d["clauses"]),
        position=position_from_dict(d["position"]),
        risk=risk_from_dict(d["risk"]),
    )
