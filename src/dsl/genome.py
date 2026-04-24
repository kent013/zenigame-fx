"""Clause ベース Genome 構造（T007）。

旧フラット式（entry_long/entry_short/exit_long/exit_short の Expr ツリー 4 本）を
本 TODO で置き換える。Clause = directional × local_gate × weight を 1-3 個持ち、
composite score を介してヒステリシス判定で売買する。

仕様根拠:
- docs/alpha_factory/clause-architecture.md
- devnotes/20260421-1850-fx-skill-port/debate-synthesis.md
- devnotes/20260422-1423-clause-genome-structure/detailed-design.md

学術引用:
- Jacobs, R. A., Jordan, M. I., Nowlan, S. J., & Hinton, G. E. (1991).
  Adaptive mixtures of local experts. Neural Computation, 3(1), 79-87.
- Jordan, M. I., & Jacobs, R. A. (1994). Hierarchical mixtures of experts and
  the EM algorithm. Neural Computation, 6(2), 181-214.
- Koza, J. R. (1992). Genetic Programming. MIT Press.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True)
class SignalConfig:
    """単一 primitive の呼び出し定義。

    Attributes:
        name: primitive ID（例: "F1", "M1"）。後続 TODO で PrimitiveRegistry 登録値と一致必須。
        weight: directional の場合 [0.1, 2.0] の正、local_gate の場合 [-2.0, 2.0]。
        params: primitive 固有パラメータ（fast/slow 窓、閾値など）。
                生成時に defensive copy + MappingProxyType で immutable 化される
                (Cycle 2 / T029 で deep immutability 保証)。
    """

    name: str
    weight: float
    params: Mapping[str, float | int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Cycle 2 / T029: dict(self.params) で shared reference を遮断した上で
        # MappingProxyType で外部からの mutation を禁止 (deep immutability)。
        # DslStrategy の prepare-time identity check (`prepared.genome is
        # self._genome`) が安全に成立する前提を構成する。
        object.__setattr__(
            self, "params", MappingProxyType(dict(self.params))
        )


@dataclass(frozen=True)
class ClauseConfig:
    """1 clause = directional 群 × local_gate 群 × clause_weight."""

    directional: tuple[SignalConfig, ...]
    local_gate: tuple[SignalConfig, ...]
    weight: float


@dataclass(frozen=True)
class PositionConfig:
    """ポジション開閉パラメータ。

    entry_threshold > exit_threshold（ヒステリシス必須、enforce_consistency で保証）。
    time_stop_min == 0 で time_stop 無効。
    """

    entry_threshold: float
    exit_threshold: float
    max_pos: int
    time_stop_min: int


@dataclass(frozen=True)
class RiskConfig:
    """リスク管理パラメータ（ATR 係数）。"""

    stop_atr: float
    take_atr: float


@dataclass(frozen=True)
class Genome:
    """Clause ベース合成ゲノム。

    1 ゲノム = 1 通貨ペア用の signal generator。Clause を 1-3 個持ち、
    composite score 化してヒステリシス判定で発注する。
    """

    name: str
    units: int
    clauses: tuple[ClauseConfig, ...]
    position: PositionConfig
    risk: RiskConfig
