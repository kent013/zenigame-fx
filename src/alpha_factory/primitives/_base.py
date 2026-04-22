"""primitives-registry の基本型定義（T010 骨格）。

PrimitiveSpec / ParamSpec / EvaluationContext と、GA slot と category の
対応関数 slot_from_category を提供する。

後続 primitive 実装 (F1-F14, M1-M6, P1-P12) はこのモジュールのみ import して
register する（_registry.py への循環 import を避けるため）。

学術引用:
- Montana, D. J. (1995). Strongly Typed Genetic Programming. Evolutionary
  Computation, 3(2), 199-230.（category による slot 制約の理論根拠）
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from src.domain.price import PriceBar

PrimitiveCategory = Literal[
    "TREND_FOLLOW", "MEAN_REVERT", "NEUTRAL", "MODULATOR"
]
PrimitiveDomain = Literal["generic", "pair_specific"]
GaSlot = Literal["directional", "local_gate"]

# required_data の canonical naming。cross_pair.<pair> は startswith + 非空で許容。
RequiredDataKey = Literal[
    "ohlc",
    "atr",
    "spread",
    "swap",
    "calendar.session",
    "calendar.economic_event",
    "macro.vix",
    "macro.dxy",
    "macro.dgs10",
    "macro.dgs2",
    "macro.t10yie",
    "macro.spx500",
]

_REQUIRED_DATA_LITERALS: frozenset[str] = frozenset(
    {
        "ohlc",
        "atr",
        "spread",
        "swap",
        "calendar.session",
        "calendar.economic_event",
        "macro.vix",
        "macro.dxy",
        "macro.dgs10",
        "macro.dgs2",
        "macro.t10yie",
        "macro.spx500",
    }
)

# Literal に含めない、ただし `<prefix><non-empty suffix>` 形式で許可されるプレフィックス
_REQUIRED_DATA_PREFIXES: tuple[str, ...] = ("cross_pair.",)


def is_valid_required_data(key: str) -> bool:
    """required_data の key が canonical vocabulary に従うかを判定。

    ルール:
        1. Literal 値 (_REQUIRED_DATA_LITERALS) に含まれる
        2. `cross_pair.<pair>` 形式で <pair> 部分が非空
    それ以外は False。

    後続 TODO の登録時 validation で使用予定。
    """
    if key in _REQUIRED_DATA_LITERALS:
        return True
    return any(
        key.startswith(pfx) and len(key) > len(pfx)
        for pfx in _REQUIRED_DATA_PREFIXES
    )


@dataclass(frozen=True)
class ParamSpec:
    """primitive parameter の範囲と型。

    Attributes:
        name: パラメータ名（例: "fast_n"）。
        low: 下限（包含）。
        high: 上限（包含）。
        is_int: True なら整数、False なら float。
        default: 省略時の既定値。None なら必須（呼び出し側で指定必須）。
    """

    name: str
    low: float
    high: float
    is_int: bool = False
    default: float | None = None


@dataclass(frozen=True)
class EvaluationContext:
    """primitive compute に渡される評価文脈（T010 骨格で導入）。

    Attributes:
        bars: OHLC 系列。bars[idx] が判定対象 bar。
        idx: 判定対象 bar のインデックス（0 <= idx < len(bars)）。
        pair: 通貨ペア名（例: "EUR_USD"）。pair_specific primitive が参照。
        params: SignalConfig.params をそのまま転写（primitive 固有）。
        aux_series: required_data の非 OHLC キーに対応する補助時系列。
                    本 TODO ではロード実装を持たないため空 Mapping 可。
                    長さは bars と同じか、primitive 側で吸収する契約。

    Note:
        pip_size / quote_currency などの pair metadata は将来拡張で追加する。
        frozen dataclass への field 追加（default 値付き）は後方互換のため許容。
    """

    bars: Sequence[PriceBar]
    idx: int
    pair: str
    params: Mapping[str, float | int]
    aux_series: Mapping[str, Sequence[float]] = field(default_factory=dict)


ComputeFn = Callable[[EvaluationContext], float]
ComputeAllBarsFn = Callable[[EvaluationContext], np.ndarray]


@dataclass(frozen=True)
class PrimitiveSpec:
    """primitive の正式仕様（T010 骨格）。

    本 TODO では registry は空。後続 primitive 実装 TODO で具体的に登録される。

    Attributes:
        id: 一意な primitive ID（例: "F1", "M1", "P5"）。SignalConfig.name と一致。
        name: primitive の表示名（例: "TrendEMA"）。
        category: PrimitiveCategory（TREND_FOLLOW / MEAN_REVERT / NEUTRAL / MODULATOR）。
        domain: PrimitiveDomain（generic / pair_specific）。
        param_schema: ParamSpec のタプル。param 値の範囲と型を宣言。
        required_data: 参照する系列の canonical key タプル。
                       is_valid_required_data で検証可能。
        compute: 1 点評価（EvaluationContext → float）。
        compute_all_bars: 一括評価（EvaluationContext → np.ndarray、
                           長さは len(ctx.bars)、warmup 内は np.nan で埋める規約）。
    """

    id: str
    name: str
    category: PrimitiveCategory
    domain: PrimitiveDomain
    param_schema: tuple[ParamSpec, ...]
    required_data: tuple[str, ...]
    compute: ComputeFn
    compute_all_bars: ComputeAllBarsFn


def validate_primitive_spec(spec: PrimitiveSpec) -> None:
    """PrimitiveSpec の不変条件を検証する（T010 骨格の register 時フック）。

    チェック項目:
        - id / name が非空
        - param_schema 内の name が重複しない
        - 各 ParamSpec の low <= high
        - default が指定されている場合、[low, high] 内
        - is_int=True の場合、low/high/default が整数値
        - required_data が全て is_valid_required_data を満たす

    Raises:
        ValueError: いずれかの不変条件違反。fail-fast で登録を拒否する。
    """
    if not spec.id:
        raise ValueError("PrimitiveSpec.id must be non-empty")
    if not spec.name:
        raise ValueError(
            f"PrimitiveSpec.name must be non-empty (id={spec.id!r})"
        )
    seen_names: set[str] = set()
    for p in spec.param_schema:
        if p.name in seen_names:
            raise ValueError(
                f"duplicate param name {p.name!r} in "
                f"PrimitiveSpec(id={spec.id!r})"
            )
        seen_names.add(p.name)
        if p.low > p.high:
            raise ValueError(
                f"ParamSpec {p.name!r}: low ({p.low}) > high ({p.high}) "
                f"in PrimitiveSpec(id={spec.id!r})"
            )
        if p.default is not None and not (p.low <= p.default <= p.high):
            raise ValueError(
                f"ParamSpec {p.name!r}: default ({p.default}) "
                f"out of [{p.low}, {p.high}] in "
                f"PrimitiveSpec(id={spec.id!r})"
            )
        if p.is_int:
            if p.low != int(p.low) or p.high != int(p.high):
                raise ValueError(
                    f"ParamSpec {p.name!r}: is_int but low/high "
                    f"({p.low}, {p.high}) are not integer values"
                )
            if p.default is not None and p.default != int(p.default):
                raise ValueError(
                    f"ParamSpec {p.name!r}: is_int but default "
                    f"({p.default}) is not an integer"
                )
    for key in spec.required_data:
        if not is_valid_required_data(key):
            raise ValueError(
                f"invalid required_data key {key!r} in "
                f"PrimitiveSpec(id={spec.id!r})"
            )


def slot_from_category(category: PrimitiveCategory) -> GaSlot:
    """PrimitiveCategory（4 値）を GA slot（2 値）に射影する。

    射影規則:
        MODULATOR → "local_gate"
        TREND_FOLLOW / MEAN_REVERT / NEUTRAL → "directional"

    GA random_gen は directional / local_gate の 2 slot を持つため、
    primitives-registry 側 4 値カテゴリをこの関数で橋渡しする。

    tests/ga/ の書換えは後続移行 TODO（T010-d）で本関数を経由して行う。

    Raises:
        ValueError: Literal 境界外の category（typo 等）を受け取った場合。
                    fail-fast で silent fallback を避ける。
    """
    if category == "MODULATOR":
        return "local_gate"
    if category in ("TREND_FOLLOW", "MEAN_REVERT", "NEUTRAL"):
        return "directional"
    raise ValueError(f"unknown PrimitiveCategory: {category!r}")
