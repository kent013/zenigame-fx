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

import bisect
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Literal

import numpy as np

from src.domain.price import PriceBar

if TYPE_CHECKING:
    from src.events.calendar import EconomicCalendar

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
class EconomicEventSnapshot:
    """as-of <= bar_time までに既知のイベントスケジュールのスナップショット (T012)。

    look-ahead bias 回避のため、primitive (M4) は本 snapshot を介して
    EconomicCalendar を参照する。`as_of` は「この時刻までに schedule が既知」と
    みなす上限であり、`event.event_time > as_of` のイベントは
    「bar_time 時点で未知」として primitive 側で除外される。

    MVP 仮定:
        - backtest 使用時は calendar 全量を `as_of=+∞ 近似` で渡す運用を許容
          （schedule の late amendment leakage は別 TODO で厳密化）
        - compute は `event.event_time` のみ参照、`event.actual` には触れない
          （FX live 時点で未公開のため）

    Attributes:
        calendar: EconomicCalendar インスタンス
        as_of: この時刻までに schedule が既知（future schedule の leakage を防ぐ cap）
    """

    calendar: EconomicCalendar
    as_of: datetime


@dataclass(frozen=True)
class VixSeriesSnapshot:
    """VIX close の publication timestamp 付き観測列 (T012)。

    Invariants (`__post_init__` で強制):
        - observations は publication_ts_utc 昇順にソート済
        - publication_ts_utc は tz-aware datetime（naive は ValueError）

    Lookup:
        `lookup(bar_time)` は publication_ts_utc < bar_time (strict) を満たす
        最新の vix_close を返す。該当なしなら None。

    Notes:
        Daily series x 数年程度 (~1000 obs) を想定。
        compute_all_bars 側で pubs 列を 1 度抽出して bisect する実装が推奨。
        本クラスの `lookup` は 1 点参照用 (毎回 O(N) で pubs 列を構築) のため、
        ループ内で繰り返し呼ばない。
    """

    # (publication_ts_utc, vix_close) 昇順
    observations: tuple[tuple[datetime, float], ...] = ()

    def __post_init__(self) -> None:
        """tz-aware datetime + 昇順を強制（fail-fast）。"""
        prev_ts: datetime | None = None
        for i, (ts, _val) in enumerate(self.observations):
            if ts.tzinfo is None:
                raise ValueError(
                    f"VixSeriesSnapshot.observations[{i}] is naive datetime; "
                    "publication_ts_utc must be tz-aware"
                )
            if prev_ts is not None and ts < prev_ts:
                raise ValueError(
                    f"VixSeriesSnapshot.observations must be ascending by "
                    f"publication_ts_utc; index {i}: {ts!r} < previous {prev_ts!r}"
                )
            prev_ts = ts

    def lookup(self, bar_time: datetime) -> float | None:
        """bar_time より前に publication された observation から最新 vix_close を返す。

        strict less than (`publication_ts_utc < bar_time`) で future leak を防ぐ。
        該当する観測がない場合は None。

        Notes:
            毎 call で pubs 列を構築するため O(N)。compute_all_bars でループする
            場合は呼び出し側で `[o[0] for o in observations]` を 1 度だけ
            キャッシュしてから bisect_left を使うこと（M5 実装参照）。
        """
        if not self.observations:
            return None
        pubs = [o[0] for o in self.observations]
        i = bisect.bisect_left(pubs, bar_time)
        if i == 0:
            return None
        return self.observations[i - 1][1]


@dataclass(frozen=True)
class EvaluationContext:
    """primitive compute に渡される評価文脈（T010 骨格で導入、T012 で拡張）。

    Attributes:
        bars: OHLC 系列。bars[idx] が判定対象 bar。
        idx: 判定対象 bar のインデックス（0 <= idx < len(bars)）。
        pair: 通貨ペア名（例: "EUR_USD"）。pair_specific primitive が参照。
        params: SignalConfig.params をそのまま転写（primitive 固有）。
        aux_series: required_data の非 OHLC キーに対応する補助時系列。
                    本 TODO ではロード実装を持たないため空 Mapping 可。
                    長さは bars と同じか、primitive 側で吸収する契約。
        event_snapshot: EconomicEventSnapshot（T012 追加, default=None）。
                        M4 EconomicEventGate が参照。
        vix_snapshot: VixSeriesSnapshot（T012 追加, default=None）。
                      M5 VIXRegimeGate が参照。
        strict_snapshot_required: True なら snapshot=None で primitive 呼び出し
                                  発生時に RuntimeError を raise（fail-fast）。
                                  production backtest runner はこの flag を True
                                  にして伝搬漏れを検知する規約。

    Note:
        pip_size / quote_currency などの pair metadata は将来拡張で追加する。
        frozen dataclass への field 追加（default 値付き）は後方互換のため許容
        （T011 既存テストは新フィールド未指定のまま動作する）。
    """

    bars: Sequence[PriceBar]
    idx: int
    pair: str
    params: Mapping[str, float | int]
    aux_series: Mapping[str, Sequence[float]] = field(default_factory=dict)
    # --- T012 追加（default=None で後方互換） ---
    event_snapshot: EconomicEventSnapshot | None = None
    vix_snapshot: VixSeriesSnapshot | None = None
    strict_snapshot_required: bool = False


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
