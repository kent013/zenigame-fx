# Detailed Design: primitives-registry（T010 骨格）

本詳細設計は `conceptual-design.md`（APPROVED）を実装レベルまで落とし込んだもの。

## 1. ファイル構成

```
src/alpha_factory/primitives/
├── __init__.py           # 公開 API の re-export
├── _base.py              # dataclass 定義 (PrimitiveSpec / ParamSpec / EvaluationContext) + slot_from_category + RequiredDataKey
├── _registry.py          # module-level dict + register/get/list/clear + ensure_registered
└── evaluator.py          # RegistryEvaluator (PrimitiveEvaluator Protocol 実装)

tests/alpha_factory/
└── test_primitives_registry.py   # 契約テスト一式
```

既存ファイル（差分ゼロ）:
- `src/ga/_dummy_registry.py`
- `src/ga/random_gen.py`
- `src/dsl/strategy.py`
- `tests/ga/**`

## 2. `src/alpha_factory/primitives/_base.py`

```python
"""primitives-registry の基本型定義（T010 骨格）。

PrimitiveSpec / ParamSpec / EvaluationContext と、GA slot と category の
対応関数 slot_from_category を提供する。

後続 primitive 実装 (F1-F14, M1-M6, P1-P12) はこのモジュールのみ import して
register する（_registry.py への循環 import を避けるため）。

学術引用:
- Montana, D. J. (1995). Strongly Typed Genetic Programming. Evolutionary
  Computation, 3(2), 199-230.
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

# required_data の canonical naming。cross_pair.<pair> は startswith で追加許容。
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

# Literal に含めない、ただし許可されるプレフィックス
_REQUIRED_DATA_PREFIXES: tuple[str, ...] = ("cross_pair.",)


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
    for pfx in _REQUIRED_DATA_PREFIXES:
        if key.startswith(pfx) and len(key) > len(pfx):
            return True
    return False


@dataclass(frozen=True)
class ParamSpec:
    """primitive parameter の範囲と型。

    Attributes:
        name: パラメータ名（例: "fast_n"）。
        low: 下限（包含）。
        high: 上限（包含）。
        is_int: True なら整数、False なら float。
        default: 省略時の既定値。None なら必須。
    """

    name: str
    low: float
    high: float
    is_int: bool = False
    default: float | None = None


@dataclass(frozen=True)
class EvaluationContext:
    """primitive compute に渡される評価文脈。

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
        dataclass への field 追加（default 値付き）は後方互換のため許容される。
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
    """primitive の正式仕様。

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
                           長さは len(ctx.bars)、warmup 内は np.nan）。
    """

    id: str
    name: str
    category: PrimitiveCategory
    domain: PrimitiveDomain
    param_schema: tuple[ParamSpec, ...]
    required_data: tuple[str, ...]
    compute: ComputeFn
    compute_all_bars: ComputeAllBarsFn


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
```

### 型 alias について

- `ComputeFn` / `ComputeAllBarsFn` を public alias として公開（後続 primitive 実装で import）。
- `_REQUIRED_DATA_PREFIXES` は module private（`_` prefix）。

### slot_from_category の戻り値確認

`src/ga/random_gen.py:86` の Literal が `Literal["directional", "local_gate"]`、
`tests/ga/test_random_gen.py` でも同じ値を期待。一致確認済（Round 2 NOTE 対応）。

## 3. `src/alpha_factory/primitives/_registry.py`

```python
"""primitives-registry の登録・取得 API（T010 骨格）。

registry は module-level dict。本 TODO では空のまま。
後続 primitive 実装 TODO で register されて埋まる。

Bootstrap 方針:
    production path (GA entry) から ensure_registered() を明示的に呼ぶ。
    副作用 import 単独には依存しない（登録漏れ検出のため）。
"""

from __future__ import annotations

from src.alpha_factory.primitives._base import (
    PrimitiveCategory,
    PrimitiveDomain,
    PrimitiveSpec,
)

_PRIMITIVES: dict[str, PrimitiveSpec] = {}


def register(spec: PrimitiveSpec) -> None:
    """PrimitiveSpec を registry に登録する。

    Raises:
        ValueError: 同じ id が既に登録されている場合。silent override は許さない。
    """
    if spec.id in _PRIMITIVES:
        raise ValueError(f"primitive {spec.id!r} already registered")
    _PRIMITIVES[spec.id] = spec


def get_primitive(primitive_id: str) -> PrimitiveSpec:
    """id で PrimitiveSpec を取得する。

    Raises:
        KeyError: id が未登録の場合。
    """
    if primitive_id not in _PRIMITIVES:
        raise KeyError(f"primitive {primitive_id!r} not in registry")
    return _PRIMITIVES[primitive_id]


def list_all() -> tuple[PrimitiveSpec, ...]:
    """全 PrimitiveSpec を登録順（dict 挿入順）で返す。"""
    return tuple(_PRIMITIVES.values())


def list_by_category(
    category: PrimitiveCategory,
) -> tuple[PrimitiveSpec, ...]:
    """指定 category の PrimitiveSpec を登録順で返す。"""
    return tuple(
        spec for spec in _PRIMITIVES.values() if spec.category == category
    )


def list_by_domain(
    domain: PrimitiveDomain,
) -> tuple[PrimitiveSpec, ...]:
    """指定 domain の PrimitiveSpec を登録順で返す。"""
    return tuple(
        spec for spec in _PRIMITIVES.values() if spec.domain == domain
    )


def clear() -> None:
    """registry を空にする（テスト用）。

    本番 path では呼ばない。tests 内の fixture などで isolation のために使う。
    """
    _PRIMITIVES.clear()


def ensure_registered() -> None:
    """primitive モジュールの明示的 bootstrap 関数（本 TODO では no-op）。

    後続 TODO で primitive 実装モジュールを import してここから register を
    発火させる。冪等（複数回呼んでも 2 回目以降は既登録で no-op、ただし
    重複 register を避けるため各 primitive 側が id 済みチェックを行う）。

    production path (GA entry) から明示的に 1 回呼ぶ規約。
    """
    # 骨格では未登録。primitive 実装 TODO で埋まる。
    return None
```

## 4. `src/alpha_factory/primitives/evaluator.py`

```python
"""RegistryEvaluator: PrimitiveEvaluator Protocol の registry ベース実装（T010 骨格）。

signal.name → registry lookup → EvaluationContext 構築 → spec.compute(ctx) の
薄い adapter。状態（キャッシュ等）は保持しない。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from src.alpha_factory.primitives._base import EvaluationContext
from src.alpha_factory.primitives._registry import get_primitive
from src.domain.price import PriceBar
from src.dsl.genome import SignalConfig


class RegistryEvaluator:
    """PrimitiveEvaluator Protocol (src/dsl/strategy.py) の実装。

    registry に登録された PrimitiveSpec を lookup し、EvaluationContext を
    構築して compute を呼ぶ。

    Attributes:
        pair: 評価対象の通貨ペア名（pair_specific primitive が参照）。
        aux_series: 補助時系列 Mapping（本 TODO では呼び出し側が直接用意）。
    """

    def __init__(
        self,
        *,
        pair: str,
        aux_series: Mapping[str, Sequence[float]] | None = None,
    ) -> None:
        self._pair = pair
        # None → 空 dict（mutable 回避のため毎回新規作成）
        self._aux_series: Mapping[str, Sequence[float]] = (
            dict(aux_series) if aux_series is not None else {}
        )

    def evaluate(
        self, bars: list[PriceBar], idx: int, signal: SignalConfig
    ) -> float:
        """PrimitiveEvaluator Protocol の実装。

        Raises:
            KeyError: signal.name が registry に無い場合（get_primitive が raise）。
        """
        spec = get_primitive(signal.name)
        ctx = EvaluationContext(
            bars=bars,
            idx=idx,
            pair=self._pair,
            params=signal.params,
            aux_series=self._aux_series,
        )
        return spec.compute(ctx)
```

## 5. `src/alpha_factory/primitives/__init__.py`

```python
"""primitives-registry 公開 API。

後続 primitive 実装 TODO は `_base` のみ import して register する規約。
外部 consumer（GA / DslStrategy）は本 __init__ の re-export を使う。
"""

from src.alpha_factory.primitives._base import (
    ComputeAllBarsFn,
    ComputeFn,
    EvaluationContext,
    GaSlot,
    ParamSpec,
    PrimitiveCategory,
    PrimitiveDomain,
    PrimitiveSpec,
    RequiredDataKey,
    is_valid_required_data,
    slot_from_category,
)
from src.alpha_factory.primitives._registry import (
    clear,
    ensure_registered,
    get_primitive,
    list_all,
    list_by_category,
    list_by_domain,
    register,
)
from src.alpha_factory.primitives.evaluator import RegistryEvaluator

__all__ = [
    "ComputeAllBarsFn",
    "ComputeFn",
    "EvaluationContext",
    "GaSlot",
    "ParamSpec",
    "PrimitiveCategory",
    "PrimitiveDomain",
    "PrimitiveSpec",
    "RegistryEvaluator",
    "RequiredDataKey",
    "clear",
    "ensure_registered",
    "get_primitive",
    "is_valid_required_data",
    "list_all",
    "list_by_category",
    "list_by_domain",
    "register",
    "slot_from_category",
]
```

## 6. 契約テスト `tests/alpha_factory/test_primitives_registry.py`

テスト観点の網羅:

1. `register → get` で同一 spec を取得できる。
2. 同じ id を再 register すると `ValueError`。
3. `list_all()` が登録順で返す。
4. `list_by_category()` / `list_by_domain()` が正しいサブセットを返す。
5. `clear()` で空になる。
6. 未登録 id で `get_primitive` が `KeyError`。
7. `RegistryEvaluator` が `evaluate(bars, idx, signal)` 経由で spec.compute を呼ぶ。
8. 未登録 signal を evaluate すると `KeyError`（get_primitive 経由）。
9. `slot_from_category` が全 4 値に対して正しい slot を返す。
10. `is_valid_required_data` が Literal 値 / `cross_pair.EUR_USD` で True、無関係 key で False。
11. `ensure_registered()` が副作用なく呼べる（骨格では no-op）。
12. `aux_series=None` で RegistryEvaluator を作れる（空 dict にフォールバック）。

```python
"""primitives-registry 契約テスト（T010 骨格）。"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import numpy as np
import pytest

from src.alpha_factory.primitives import (
    EvaluationContext,
    ParamSpec,
    PrimitiveSpec,
    RegistryEvaluator,
    clear,
    ensure_registered,
    get_primitive,
    is_valid_required_data,
    list_all,
    list_by_category,
    list_by_domain,
    register,
    slot_from_category,
)
from src.domain.price import Ohlc, PriceBar
from src.dsl.genome import (
    ClauseConfig,
    Genome,
    PositionConfig,
    RiskConfig,
    SignalConfig,
)
from src.dsl.strategy import DslStrategy


@pytest.fixture(autouse=True)
def _isolate_registry():
    clear()
    yield
    clear()


def _dummy_bar(ts: datetime) -> PriceBar:
    o = Ohlc(
        open=Decimal("1.0"),
        high=Decimal("1.0"),
        low=Decimal("1.0"),
        close=Decimal("1.0"),
    )
    return PriceBar(
        pair_name="EUR_USD",
        bar_time=ts,
        bid=o,
        ask=o,
        volume=0,
        complete=True,
    )


def _dummy_compute(ctx: EvaluationContext) -> float:
    return float(ctx.params.get("value", 0.0))


def _dummy_compute_all_bars(ctx: EvaluationContext) -> np.ndarray:
    return np.full(len(ctx.bars), float(ctx.params.get("value", 0.0)))


def _make_spec(
    *,
    id: str = "X1",
    name: str = "DummyPrimitive",
    category: str = "TREND_FOLLOW",
    domain: str = "generic",
) -> PrimitiveSpec:
    return PrimitiveSpec(
        id=id,
        name=name,
        category=category,  # type: ignore[arg-type]
        domain=domain,  # type: ignore[arg-type]
        param_schema=(ParamSpec(name="value", low=0.0, high=1.0),),
        required_data=("ohlc",),
        compute=_dummy_compute,
        compute_all_bars=_dummy_compute_all_bars,
    )


class TestRegistryBasics:
    def test_register_then_get(self):
        spec = _make_spec()
        register(spec)
        assert get_primitive("X1") is spec

    def test_duplicate_register_raises(self):
        register(_make_spec())
        with pytest.raises(ValueError, match="already registered"):
            register(_make_spec())

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError, match="not in registry"):
            get_primitive("UNKNOWN")

    def test_list_all_returns_registration_order(self):
        s1 = _make_spec(id="A1")
        s2 = _make_spec(id="A2")
        register(s1)
        register(s2)
        assert list_all() == (s1, s2)

    def test_list_by_category(self):
        s_trend = _make_spec(id="T1", category="TREND_FOLLOW")
        s_mod = _make_spec(id="M1", category="MODULATOR")
        register(s_trend)
        register(s_mod)
        assert list_by_category("TREND_FOLLOW") == (s_trend,)
        assert list_by_category("MODULATOR") == (s_mod,)
        assert list_by_category("MEAN_REVERT") == ()

    def test_list_by_domain(self):
        s_g = _make_spec(id="G1", domain="generic")
        s_p = _make_spec(id="P1", domain="pair_specific")
        register(s_g)
        register(s_p)
        assert list_by_domain("generic") == (s_g,)
        assert list_by_domain("pair_specific") == (s_p,)

    def test_clear_empties_registry(self):
        register(_make_spec())
        clear()
        assert list_all() == ()


class TestSlotFromCategory:
    @pytest.mark.parametrize(
        "category,expected",
        [
            ("TREND_FOLLOW", "directional"),
            ("MEAN_REVERT", "directional"),
            ("NEUTRAL", "directional"),
            ("MODULATOR", "local_gate"),
        ],
    )
    def test_slot_from_category(self, category, expected):
        assert slot_from_category(category) == expected

    def test_slot_from_category_rejects_unknown(self):
        with pytest.raises(ValueError, match="unknown PrimitiveCategory"):
            slot_from_category("BOGUS")  # type: ignore[arg-type]


class TestRequiredDataNaming:
    @pytest.mark.parametrize(
        "key,ok",
        [
            ("ohlc", True),
            ("atr", True),
            ("spread", True),
            ("swap", True),
            ("calendar.session", True),
            ("calendar.economic_event", True),
            ("macro.vix", True),
            ("macro.dxy", True),
            ("macro.dgs10", True),
            ("macro.dgs2", True),
            ("macro.t10yie", True),
            ("macro.spx500", True),
            ("cross_pair.EUR_USD", True),
            ("cross_pair.", False),
            ("cross_pair", False),
            ("unknown", False),
            ("macro.unknown", False),
            ("", False),
        ],
    )
    def test_is_valid_required_data(self, key, ok):
        assert is_valid_required_data(key) is ok


class TestRegistryEvaluator:
    def test_evaluate_returns_compute_value(self):
        register(_make_spec(id="X1"))
        ev = RegistryEvaluator(pair="EUR_USD")
        bars = [_dummy_bar(datetime(2026, 1, 1, 9, tzinfo=timezone.utc))]
        sig = SignalConfig(name="X1", weight=1.0, params={"value": 0.42})
        assert ev.evaluate(bars, 0, sig) == pytest.approx(0.42)

    def test_evaluate_unknown_primitive_raises(self):
        ev = RegistryEvaluator(pair="EUR_USD")
        bars = [_dummy_bar(datetime(2026, 1, 1, 9, tzinfo=timezone.utc))]
        sig = SignalConfig(name="NOT_REGISTERED", weight=1.0)
        with pytest.raises(KeyError):
            ev.evaluate(bars, 0, sig)

    def test_aux_series_none_defaults_to_empty_mapping(self):
        register(_make_spec(id="X1"))
        ev = RegistryEvaluator(pair="EUR_USD", aux_series=None)
        bars = [_dummy_bar(datetime(2026, 1, 1, 9, tzinfo=timezone.utc))]
        sig = SignalConfig(name="X1", weight=1.0, params={"value": 1.5})
        # aux_series が空でも compute は呼べる
        assert ev.evaluate(bars, 0, sig) == pytest.approx(1.5)

    def test_context_receives_pair_and_params(self):
        captured: dict[str, object] = {}

        def _capture_compute(ctx: EvaluationContext) -> float:
            captured["pair"] = ctx.pair
            captured["params"] = dict(ctx.params)
            captured["idx"] = ctx.idx
            return 0.0

        spec = PrimitiveSpec(
            id="C1",
            name="Capture",
            category="NEUTRAL",
            domain="generic",
            param_schema=(),
            required_data=("ohlc",),
            compute=_capture_compute,
            compute_all_bars=_dummy_compute_all_bars,
        )
        register(spec)
        ev = RegistryEvaluator(pair="USD_JPY")
        bars = [
            _dummy_bar(datetime(2026, 1, 1, 9, tzinfo=timezone.utc)),
            _dummy_bar(datetime(2026, 1, 1, 10, tzinfo=timezone.utc)),
        ]
        sig = SignalConfig(name="C1", weight=1.0, params={"k": 7})
        ev.evaluate(bars, 1, sig)
        assert captured["pair"] == "USD_JPY"
        assert captured["params"] == {"k": 7}
        assert captured["idx"] == 1


class TestEnsureRegistered:
    def test_ensure_registered_is_noop_skeleton(self):
        # 骨格では登録対象が無いので no-op
        ensure_registered()
        assert list_all() == ()

    def test_ensure_registered_is_idempotent(self):
        ensure_registered()
        ensure_registered()
        # エラー無しで 2 回呼べる
        assert list_all() == ()


class TestDslStrategyIntegration:
    """RegistryEvaluator が DslStrategy.PrimitiveEvaluator Protocol を
    structural に満たし、DslStrategy に直接注入可能であることを検証する。
    互換性回帰（Protocol シグネチャ変更や import 破壊）の早期検知用。"""

    def test_registry_evaluator_fits_protocol(self):
        # directional 1 個の最小 Genome を組み、DslStrategy から evaluator を
        # 呼ばせて signature / import が生きていることを確認
        register(_make_spec(id="DIR1", category="TREND_FOLLOW"))
        genome = Genome(
            name="test",
            units=1000,
            clauses=(
                ClauseConfig(
                    directional=(
                        SignalConfig(
                            name="DIR1", weight=1.0, params={"value": 0.5}
                        ),
                    ),
                    local_gate=(),
                    weight=1.0,
                ),
            ),
            position=PositionConfig(
                entry_threshold=0.3,
                exit_threshold=0.1,
                max_pos=1,
                time_stop_min=0,
            ),
            risk=RiskConfig(stop_atr=2.0, take_atr=2.0),
        )
        evaluator = RegistryEvaluator(pair="EUR_USD")
        strategy = DslStrategy(genome=genome, evaluator=evaluator)
        # warmup_bars / genome property が生きていることを確認
        assert strategy.genome is genome
        assert strategy.warmup_bars() == 0
```

### PrimitiveEvaluator Protocol 互換性の確認

`src/dsl/strategy.py:PrimitiveEvaluator.evaluate(bars, idx, signal) -> float` に対し、
`RegistryEvaluator.evaluate` は同一シグネチャ。Protocol は structural なので
明示 subclass 宣言なしで duck-typing 互換。DslStrategy(evaluator=RegistryEvaluator(...)) で使える。

## 7. mypy / ruff 考慮

- `PrimitiveCategory` / `PrimitiveDomain` は `Literal` なので `type: ignore[arg-type]` が
  テストヘルパで必要（ヘルパ関数の引数を str で受けて Literal に渡すため）。
  これはテストコードのみで、production コードでは全て Literal 値直接利用。
- `aux_series: Mapping[str, Sequence[float]]` は共変でないが、`dict[str, Sequence[float]]` を
  frozen dataclass の default に使うので `field(default_factory=dict)` で空 dict を
  毎 instance 新規作成（mutable default 回避）。
- ruff: `N806` (variable names) の Literal 大文字許容。既存 `src/` で使用実績あり。

## 8. docs 更新

### `docs/alpha_factory/primitives.md`

「Registry の役割」セクションを以下に書き換え（骨格段階を明記、R2 対応）:

- T010 時点の状態: `src/alpha_factory/primitives/_registry.py` の module-level dict は **空**。契約（PrimitiveSpec / ParamSpec / EvaluationContext / RegistryEvaluator）のみ整備済。
- 後続 TODO（T010-a/b/c）で 32 プリミティブを段階的に登録する計画。登録は各 primitive モジュールが `register(PrimitiveSpec(...))` を呼ぶ。
- production path からは `ensure_registered()` を 1 回呼んでから `list_all()` / `get_primitive(id)` を使う規約（骨格では no-op）。
- GA random_gen は `slot_from_category()` 経由で 4 値 category → 2 値 slot へ射影。tests/ga/ の移行は T010-d。
- `required_data` は `RequiredDataKey` Literal（ohlc/atr/spread/swap/calendar.*/macro.*）+ `cross_pair.<pair>` プレフィックス規約。検証は `is_valid_required_data()`。

### `docs/alpha_factory/terminology.md`

4 語を追加（PrimitiveSpec / ParamSpec / RegistryEvaluator / PrimitiveDomain）。
さらに EvaluationContext / slot_from_category / RequiredDataKey も含める
（本設計で導入された contract 用語）。

## 9. 実装手順

worktree を切った後の順序:

1. `src/alpha_factory/primitives/__init__.py` を空で作成 → `_base.py` 作成 → `_registry.py` 作成 → `evaluator.py` 作成 → `__init__.py` を re-export に更新。
2. `tests/alpha_factory/test_primitives_registry.py` 作成。
3. `uv run pytest tests/alpha_factory/test_primitives_registry.py -q` → pass 確認。
4. `uv run pytest tests/ -q` → 全体 regression 確認。
5. `uv run mypy src/alpha_factory/primitives/` → clean。
6. `uv run ruff check src/alpha_factory/primitives/ tests/alpha_factory/` → clean。
7. docs 更新（primitives.md / terminology.md）。
8. Codex impl-review。
9. コミット。

## 10. 受入判定チェックリスト

- [ ] 4 ファイル `src/alpha_factory/primitives/{__init__, _base, _registry, evaluator}.py` が存在
- [ ] `tests/alpha_factory/test_primitives_registry.py` の全テストが pass（12 テスト + parametrize）
- [ ] 全体 regression pass（skip は既存 1 件のみ）
- [ ] `uv run mypy src/alpha_factory/primitives/` clean
- [ ] `uv run ruff check src/alpha_factory/primitives/ tests/alpha_factory/` clean
- [ ] `src/ga/_dummy_registry.py` 差分ゼロ（git diff で確認）
- [ ] docs/alpha_factory/primitives.md / terminology.md 更新済
