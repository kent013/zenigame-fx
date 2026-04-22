"""T007: Clause ベース Genome dataclass 群の基本動作テスト。"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.serialize import genome_from_dict, genome_to_dict


def _mk_signal(name: str = "F1", weight: float = 1.0) -> SignalConfig:
    return SignalConfig(name=name, weight=weight, params={"w": 5})


def _mk_clause() -> ClauseConfig:
    return ClauseConfig(directional=(_mk_signal(),), local_gate=(), weight=1.0)


def _mk_position() -> PositionConfig:
    return PositionConfig(
        entry_threshold=0.3, exit_threshold=0.1, max_pos=1, time_stop_min=60
    )


def _mk_risk() -> RiskConfig:
    return RiskConfig(stop_atr=2.0, take_atr=3.0)


def test_signal_config_frozen() -> None:
    sig = _mk_signal()
    with pytest.raises(FrozenInstanceError):
        sig.name = "F2"  # type: ignore[misc]


def test_signal_config_default_params() -> None:
    sig = SignalConfig(name="F1", weight=1.0)
    assert sig.params == {}


def test_signal_config_defensive_copy() -> None:
    # __post_init__ で dict(...) コピーされるため外部変更が波及しないこと
    external = {"w": 5}
    sig = SignalConfig(name="F1", weight=1.0, params=external)
    external["w"] = 999
    assert sig.params == {"w": 5}


def test_clause_config_tuple_signals() -> None:
    c = _mk_clause()
    assert isinstance(c.directional, tuple)
    assert isinstance(c.local_gate, tuple)


def test_genome_minimal_construct() -> None:
    g = Genome(
        name="g0",
        units=10000,
        clauses=(_mk_clause(),),
        position=_mk_position(),
        risk=_mk_risk(),
    )
    assert g.name == "g0"
    assert len(g.clauses) == 1


def test_genome_three_clauses() -> None:
    g = Genome(
        name="g3",
        units=5000,
        clauses=tuple(_mk_clause() for _ in range(3)),
        position=_mk_position(),
        risk=_mk_risk(),
    )
    assert len(g.clauses) == 3


def test_genome_roundtrip_through_dict() -> None:
    g = Genome(
        name="gx",
        units=1000,
        clauses=(
            ClauseConfig(
                directional=(_mk_signal("F1", 1.2), _mk_signal("F2", 0.5)),
                local_gate=(_mk_signal("M1", 0.8),),
                weight=1.0,
            ),
            ClauseConfig(
                directional=(_mk_signal("F3", 0.9),),
                local_gate=(),
                weight=-0.7,
            ),
        ),
        position=_mk_position(),
        risk=_mk_risk(),
    )
    payload = genome_to_dict(g)
    restored = genome_from_dict(payload)
    assert restored == g
    assert genome_to_dict(restored) == payload
