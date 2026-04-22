"""T007: enforce_consistency pure function の境界値テスト。"""

from __future__ import annotations

import math

import pytest

from src.dsl.enforce import enforce_consistency
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)


def _mk_genome(
    clauses: tuple[ClauseConfig, ...] | None = None,
    position: PositionConfig | None = None,
    risk: RiskConfig | None = None,
) -> Genome:
    if clauses is None:
        clauses = (
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=1.0),),
                local_gate=(),
                weight=1.0,
            ),
        )
    if position is None:
        position = PositionConfig(
            entry_threshold=0.3,
            exit_threshold=0.1,
            max_pos=1,
            time_stop_min=60,
        )
    if risk is None:
        risk = RiskConfig(stop_atr=2.0, take_atr=3.0)
    return Genome(
        name="g", units=1000, clauses=clauses, position=position, risk=risk
    )


# ---- directional weight ----


def test_directional_weight_clip_lower() -> None:
    g = _mk_genome(
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=0.05),),
                local_gate=(),
                weight=1.0,
            ),
        )
    )
    result = enforce_consistency(g)
    assert result.clauses[0].directional[0].weight == 0.1


def test_directional_weight_clip_upper() -> None:
    g = _mk_genome(
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=2.5),),
                local_gate=(),
                weight=1.0,
            ),
        )
    )
    result = enforce_consistency(g)
    assert result.clauses[0].directional[0].weight == 2.0


def test_directional_weight_abs() -> None:
    g = _mk_genome(
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=-0.5),),
                local_gate=(),
                weight=1.0,
            ),
        )
    )
    result = enforce_consistency(g)
    assert result.clauses[0].directional[0].weight == 0.5


def test_directional_dedupe_last_wins() -> None:
    g = _mk_genome(
        clauses=(
            ClauseConfig(
                directional=(
                    SignalConfig(name="F1", weight=0.5),
                    SignalConfig(name="F1", weight=1.5),
                ),
                local_gate=(),
                weight=1.0,
            ),
        )
    )
    result = enforce_consistency(g)
    assert len(result.clauses[0].directional) == 1
    assert result.clauses[0].directional[0].weight == 1.5


# ---- gate weight ----


def test_gate_weight_clip_upper() -> None:
    g = _mk_genome(
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=1.0),),
                local_gate=(SignalConfig(name="M1", weight=2.5),),
                weight=1.0,
            ),
        )
    )
    result = enforce_consistency(g)
    assert result.clauses[0].local_gate[0].weight == 2.0


def test_gate_weight_clip_lower() -> None:
    g = _mk_genome(
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=1.0),),
                local_gate=(SignalConfig(name="M1", weight=-2.5),),
                weight=1.0,
            ),
        )
    )
    result = enforce_consistency(g)
    assert result.clauses[0].local_gate[0].weight == -2.0


def test_gate_max_one_takes_largest_abs() -> None:
    g = _mk_genome(
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=1.0),),
                local_gate=(
                    SignalConfig(name="M1", weight=0.3),
                    SignalConfig(name="M2", weight=-1.5),
                    SignalConfig(name="M3", weight=0.8),
                ),
                weight=1.0,
            ),
        )
    )
    result = enforce_consistency(g)
    gates = result.clauses[0].local_gate
    assert len(gates) == 1
    assert gates[0].name == "M2"
    assert gates[0].weight == -1.5


def test_gate_dedupe_last_wins() -> None:
    g = _mk_genome(
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=1.0),),
                local_gate=(
                    SignalConfig(name="M1", weight=0.3),
                    SignalConfig(name="M1", weight=0.7),
                ),
                weight=1.0,
            ),
        )
    )
    result = enforce_consistency(g)
    gates = result.clauses[0].local_gate
    assert len(gates) == 1
    assert gates[0].weight == 0.7


# ---- position ----


def test_position_swap_when_entry_lte_exit() -> None:
    g = _mk_genome(
        position=PositionConfig(
            entry_threshold=0.1, exit_threshold=0.3, max_pos=1, time_stop_min=60
        )
    )
    result = enforce_consistency(g)
    assert result.position.entry_threshold == 0.3
    assert result.position.exit_threshold == 0.1


def test_position_swap_equal_thresholds_epsilon() -> None:
    g = _mk_genome(
        position=PositionConfig(
            entry_threshold=0.2, exit_threshold=0.2, max_pos=1, time_stop_min=60
        )
    )
    result = enforce_consistency(g)
    # entry > exit が厳密に成立
    assert result.position.entry_threshold > result.position.exit_threshold
    assert math.isclose(
        result.position.entry_threshold - result.position.exit_threshold,
        1e-6,
        abs_tol=1e-12,
    )


def test_position_max_pos_min_1() -> None:
    g = _mk_genome(
        position=PositionConfig(
            entry_threshold=0.3, exit_threshold=0.1, max_pos=0, time_stop_min=60
        )
    )
    result = enforce_consistency(g)
    assert result.position.max_pos == 1


def test_position_time_stop_non_negative() -> None:
    g = _mk_genome(
        position=PositionConfig(
            entry_threshold=0.3, exit_threshold=0.1, max_pos=1, time_stop_min=-5
        )
    )
    result = enforce_consistency(g)
    assert result.position.time_stop_min == 0


# ---- risk ----


def test_risk_positive_epsilon() -> None:
    g = _mk_genome(risk=RiskConfig(stop_atr=0.0, take_atr=-1.0))
    result = enforce_consistency(g)
    assert result.risk.stop_atr == 1e-6
    assert result.risk.take_atr == 1e-6


# ---- clause-level ----


def test_clause_all_directional_empty_raises() -> None:
    g = _mk_genome(
        clauses=(
            ClauseConfig(directional=(), local_gate=(), weight=1.0),
        )
    )
    with pytest.raises(ValueError, match="all clauses lost"):
        enforce_consistency(g)


def test_clause_directional_empty_removed_when_others_exist() -> None:
    g = _mk_genome(
        clauses=(
            ClauseConfig(directional=(), local_gate=(), weight=0.5),
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=1.0),),
                local_gate=(),
                weight=1.0,
            ),
        )
    )
    result = enforce_consistency(g)
    assert len(result.clauses) == 1
    assert result.clauses[0].directional[0].name == "F1"


def test_clauses_over_three_truncated_by_weight_abs() -> None:
    # 4 clause → 3 clause、|weight| 上位 3 が残る
    clauses = tuple(
        ClauseConfig(
            directional=(SignalConfig(name=f"F{i}", weight=1.0),),
            local_gate=(),
            weight=w,
        )
        for i, w in enumerate([0.1, 1.0, 0.5, -2.0])
    )
    g = _mk_genome(clauses=clauses)
    result = enforce_consistency(g)
    assert len(result.clauses) == 3
    abs_weights = sorted(abs(c.weight) for c in result.clauses)
    assert abs_weights == [0.5, 1.0, 2.0]


# ---- idempotency ----


def test_enforce_idempotent() -> None:
    # 有限実数入力で f(f(x)) == f(x)
    g = _mk_genome(
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=-3.0),),  # abs + clip
                local_gate=(SignalConfig(name="M1", weight=2.5),),  # clip
                weight=1.0,
            ),
        ),
        position=PositionConfig(
            entry_threshold=0.05, exit_threshold=0.3, max_pos=0, time_stop_min=-1
        ),
        risk=RiskConfig(stop_atr=0.0, take_atr=0.0),
    )
    once = enforce_consistency(g)
    twice = enforce_consistency(once)
    assert once == twice


def test_enforce_idempotent_multiclause_and_dedup() -> None:
    # 複数 clause + 同 name dedupe + truncate over 3 の複合ケースでも冪等
    g = _mk_genome(
        clauses=(
            ClauseConfig(
                directional=(
                    SignalConfig(name="F1", weight=0.05),  # clip low
                    SignalConfig(name="F1", weight=2.5),   # dedupe 後勝ち + clip high
                    SignalConfig(name="F2", weight=-1.5),  # abs
                ),
                local_gate=(
                    SignalConfig(name="M1", weight=0.4),
                    SignalConfig(name="M2", weight=-0.8),  # |weight| 最大なので残る
                ),
                weight=0.7,
            ),
            ClauseConfig(
                directional=(SignalConfig(name="F3", weight=1.0),),
                local_gate=(),
                weight=-1.2,
            ),
            ClauseConfig(
                directional=(SignalConfig(name="F4", weight=0.5),),
                local_gate=(),
                weight=0.1,  # 低い
            ),
            ClauseConfig(
                directional=(SignalConfig(name="F5", weight=0.5),),
                local_gate=(),
                weight=2.0,  # 高い
            ),
        ),
    )
    once = enforce_consistency(g)
    twice = enforce_consistency(once)
    thrice = enforce_consistency(twice)
    assert once == twice == thrice
    # 4 → 3 clause に truncate されている
    assert len(once.clauses) == 3
    # |weight| Top 3 = {2.0, 1.2, 0.7}
    abs_weights = sorted(abs(c.weight) for c in once.clauses)
    assert abs_weights == [0.7, 1.2, 2.0]


# ---- NaN / Inf rejection ----


def test_enforce_rejects_nan_directional_weight() -> None:
    g = _mk_genome(
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=math.nan),),
                local_gate=(),
                weight=1.0,
            ),
        )
    )
    with pytest.raises(ValueError, match="non-finite"):
        enforce_consistency(g)


def test_enforce_rejects_inf_directional_weight() -> None:
    g = _mk_genome(
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=math.inf),),
                local_gate=(),
                weight=1.0,
            ),
        )
    )
    with pytest.raises(ValueError, match="non-finite"):
        enforce_consistency(g)


def test_enforce_rejects_nan_gate_weight() -> None:
    g = _mk_genome(
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=1.0),),
                local_gate=(SignalConfig(name="M1", weight=math.nan),),
                weight=1.0,
            ),
        )
    )
    with pytest.raises(ValueError, match="non-finite"):
        enforce_consistency(g)


def test_enforce_rejects_nan_clause_weight() -> None:
    g = _mk_genome(
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=1.0),),
                local_gate=(),
                weight=math.nan,
            ),
        )
    )
    with pytest.raises(ValueError, match=r"ClauseConfig\.weight"):
        enforce_consistency(g)


def test_enforce_rejects_inf_clause_weight() -> None:
    g = _mk_genome(
        clauses=(
            ClauseConfig(
                directional=(SignalConfig(name="F1", weight=1.0),),
                local_gate=(),
                weight=math.inf,
            ),
        )
    )
    with pytest.raises(ValueError, match=r"ClauseConfig\.weight"):
        enforce_consistency(g)


def test_enforce_rejects_nan_entry_threshold() -> None:
    g = _mk_genome(
        position=PositionConfig(
            entry_threshold=math.nan,
            exit_threshold=0.1,
            max_pos=1,
            time_stop_min=60,
        )
    )
    with pytest.raises(ValueError, match="entry_threshold"):
        enforce_consistency(g)


def test_enforce_rejects_nan_stop_atr() -> None:
    g = _mk_genome(risk=RiskConfig(stop_atr=math.nan, take_atr=3.0))
    with pytest.raises(ValueError, match="stop_atr"):
        enforce_consistency(g)


# ---- no-op on already valid genome ----


def test_enforce_noop_on_valid_genome() -> None:
    g = _mk_genome()
    result = enforce_consistency(g)
    # 値は変わらないが、参照自体は新しい（replace で生成）
    assert result == g
