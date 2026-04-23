# T013 Pair-specific primitives (P1-P12) — Detailed Design

参照: [conceptual-design.md](./conceptual-design.md)、Codex round 1/2 review。

## 0. 全体構成

新規ファイル:
- `src/alpha_factory/primitives/pair_specific.py` — 12 primitive 実装 + ensure_registered
- `tests/alpha_factory/primitives/test_pair_specific.py` — テスト

修正ファイル:
- `src/alpha_factory/primitives/_base.py` — EvaluationContext に `aux_pair_bars` field
  追加、`RequiredDataKey` Literal 拡張、`_REQUIRED_DATA_LITERALS` 同期更新
- `src/alpha_factory/primitives/_registry.py::ensure_registered()` — pair_specific
  bootstrap 追加
- `src/alpha_factory/primitives/evaluator.py` — `RegistryEvaluator` に
  `aux_pair_bars` / `strict_aux_required` / `selected_primitive_ids` kwarg + preflight
  verify 実装
- `src/alpha_factory/primitives/__init__.py` — 必要に応じ re-export 追加（既存
  公開 API は維持）
- `docs/alpha_factory/primitives.md` — P1-P12 詳細テーブル追記

**既存テストの更新が必要 (Codex design-review 1-2 反映)**:
- `tests/alpha_factory/primitives/test_directional_generic.py:159-160`:
  - `list_by_domain("generic") == 20` を `>= 20` に緩める (or 既存の generic 数が固定 20 の
    ことを意図するなら正確数を維持)
  - `list_by_domain("pair_specific") == 0` を `>= 0` に緩める or `== 12` に更新
  - **方針**: 「F1-F14 が generic として登録されている」を直接検証するよう変更
    (`generic` 集合に F1-F14 全 ID 含まれることを確認、count 直接比較は避ける)
- `tests/alpha_factory/primitives/test_modulator_generic.py:200, 224-225`:
  - `len(specs) == 20` → `len(specs) >= 20` (or `== 32` 完全数で更新)
  - `list_by_domain("generic") == 20` → 直接 ID 集合を確認に変更
  - `list_by_domain("pair_specific") == 0` → 削除 or `>= 0` に変更
  - **方針**: 「F1-F14 + M1-M6 全 20 個が generic として存在」を ID 集合で直接 verify
- `tests/alpha_factory/test_primitives_registry.py:241, 251`:
  - `len(specs) == 20` → 同様に更新
  - **方針**: count 直接比較を避け、必要 ID 集合 (`{f"F{i}" for i in 1..14} | {f"M{i}" for i in 1..6}`)
    が含まれていること、本 TODO の追加 ID 集合も含まれていることを ID 集合で verify

**修正パターン**: count を hard-code するのではなく、ID 集合の `is_subset` または
完全一致で検証する。これにより本 TODO 後も将来追加で破綻しない。本 TODO では:
- `test_directional_generic.py`: F1-F14 のみ verify、generic 全数比較を ID 集合に変更
- `test_modulator_generic.py`: F1-F14 + M1-M6 を verify、`pair_specific == 0` を削除
- `test_primitives_registry.py`: 同様に集合ベースに変更

## 1. _base.py 改修

### 1.1 RequiredDataKey 拡張

```python
RequiredDataKey = Literal[
    # ...既存項目...
    "macro.copper",
    "macro.commodity_index",
    "macro.wti",
    "macro.gold",
]

_REQUIRED_DATA_LITERALS: frozenset[str] = frozenset({
    # ...既存項目...
    "macro.copper",
    "macro.commodity_index",
    "macro.wti",
    "macro.gold",
})
```

`is_valid_required_data` のロジックは不変（`_REQUIRED_DATA_LITERALS` を内部で使うため
集合更新だけで動作）。

### 1.2 EvaluationContext に aux_pair_bars 追加

```python
@dataclass(frozen=True)
class EvaluationContext:
    bars: Sequence[PriceBar]
    idx: int
    pair: str
    params: Mapping[str, float | int]
    aux_series: Mapping[str, Sequence[float]] = field(default_factory=dict)
    event_snapshot: EconomicEventSnapshot | None = None
    vix_snapshot: VixSeriesSnapshot | None = None
    strict_snapshot_required: bool = False
    # T013 追加 (default 空 dict で後方互換)
    aux_pair_bars: Mapping[str, Sequence[PriceBar | None]] = field(default_factory=dict)
```

frozen dataclass への field 追加 (default 値付き) は既存呼び出し側のコードが破壊
されない。

### 1.3 PrimitiveSpec に optional_data_groups 追加 (Codex design-review 1-3 反映)

P8 のように「macro.copper OR macro.commodity_index」の or-semantics 依存を表現する
ため、`optional_data_groups: tuple[tuple[str, ...], ...] = ()` を field に追加。

```python
@dataclass(frozen=True)
class PrimitiveSpec:
    id: str
    name: str
    category: PrimitiveCategory
    domain: PrimitiveDomain
    param_schema: tuple[ParamSpec, ...]
    required_data: tuple[str, ...]
    compute: ComputeFn
    compute_all_bars: ComputeAllBarsFn
    # T013 追加 (default 空 tuple で後方互換)
    optional_data_groups: tuple[tuple[str, ...], ...] = ()
```

`validate_primitive_spec` に追加 check:
- `optional_data_groups` 内の各 tuple が非空
- 各 key が `is_valid_required_data` を満たす
- key が `required_data` と重複しないこと (混乱回避)

## 2. evaluator.py 改修

```python
from collections.abc import Iterable, Mapping, Sequence
from src.alpha_factory.primitives._base import (
    EconomicEventSnapshot, EvaluationContext, VixSeriesSnapshot,
)
from src.alpha_factory.primitives._registry import get_primitive
from src.domain.price import PriceBar
from src.dsl.genome import SignalConfig


class RegistryEvaluator:
    def __init__(
        self,
        *,
        pair: str,
        aux_series: Mapping[str, Sequence[float]] | None = None,
        aux_pair_bars: Mapping[str, Sequence[PriceBar | None]] | None = None,
        event_snapshot: EconomicEventSnapshot | None = None,
        vix_snapshot: VixSeriesSnapshot | None = None,
        strict_snapshot_required: bool = False,
        strict_aux_required: bool = False,
        selected_primitive_ids: Iterable[str] | None = None,
    ) -> None:
        self._pair = pair
        self._aux_series: Mapping[str, Sequence[float]] = (
            dict(aux_series) if aux_series is not None else {}
        )
        self._aux_pair_bars: Mapping[str, Sequence[PriceBar | None]] = (
            dict(aux_pair_bars) if aux_pair_bars is not None else {}
        )
        self._event_snapshot = event_snapshot
        self._vix_snapshot = vix_snapshot
        self._strict_snapshot_required = strict_snapshot_required
        self._strict_aux_required = strict_aux_required
        if strict_aux_required:
            if selected_primitive_ids is None:
                raise ValueError(
                    "strict_aux_required=True requires selected_primitive_ids "
                    "to be provided (preflight verify input)"
                )
            self._preflight_verify(tuple(selected_primitive_ids))

    # bars が直接 provide する key 集合 (preflight でスキップ)
    _BARS_PROVIDED_KEYS: frozenset[str] = frozenset({
        "ohlc", "atr", "spread", "swap", "calendar.session",
    })

    def _preflight_verify(self, ids: tuple[str, ...]) -> None:
        """selected primitive 群の required_data が現 evaluator で provide されるか
        起動時に verify。不足があれば RuntimeError fail-fast。

        Codex design-review 1-1 反映: `_BARS_PROVIDED_KEYS` で `RequiredDataKey` の
        bar 由来の key (atr 含む) を網羅。
        Codex design-review 1-3 反映: spec.optional_data_groups の or-semantics
        (group 内 1 つ以上 provide) を check。
        """
        # union of required keys (必須)
        required: set[str] = set()
        # list of optional groups (各 tuple は OR で 1 つ以上必要)
        optional_groups: list[tuple[str, ...]] = []
        for pid in ids:
            spec = get_primitive(pid)
            required.update(spec.required_data)
            optional_groups.extend(spec.optional_data_groups)

        # required: 全 key が provide されている必要
        for key in required:
            if key in self._BARS_PROVIDED_KEYS:
                continue  # bars 自体で provide (atr は indicators で計算可能)
            if key == "calendar.economic_event":
                if self._event_snapshot is None:
                    raise RuntimeError(
                        f"required aux missing for selected primitives: "
                        f"{key} (event_snapshot is None)"
                    )
                continue
            if key == "macro.vix":
                if (
                    self._vix_snapshot is None
                    or not self._vix_snapshot.observations
                ):
                    raise RuntimeError(
                        f"required aux missing: {key} (vix_snapshot empty)"
                    )
                continue
            if key.startswith("cross_pair."):
                pair_name = key[len("cross_pair."):]
                if pair_name not in self._aux_pair_bars:
                    raise RuntimeError(
                        f"required aux missing: {key} "
                        f"(aux_pair_bars[{pair_name!r}] not provided)"
                    )
                continue
            if key.startswith("macro."):
                if key not in self._aux_series:
                    raise RuntimeError(
                        f"required aux missing: {key} "
                        f"(aux_series[{key!r}] not provided)"
                    )
                continue
            # 未知の key はそもそも validate_primitive_spec で reject 済の想定
            raise RuntimeError(
                f"unknown required_data key {key!r} in preflight verify "
                f"(should have been caught at registration)"
            )

        # optional_data_groups: 各 group につき 1 つ以上 provide されていれば OK
        for group in optional_groups:
            if not any(self._is_aux_provided(k) for k in group):
                raise RuntimeError(
                    f"required aux missing for selected primitives: "
                    f"none of {group} is provided "
                    f"(at least one required by optional_data_groups)"
                )

    def _is_aux_provided(self, key: str) -> bool:
        """単一 key が現 evaluator で provide されるか判定 (optional group 用)。"""
        if key in self._BARS_PROVIDED_KEYS:
            return True
        if key == "calendar.economic_event":
            return self._event_snapshot is not None
        if key == "macro.vix":
            return (
                self._vix_snapshot is not None
                and bool(self._vix_snapshot.observations)
            )
        if key.startswith("cross_pair."):
            return key[len("cross_pair."):] in self._aux_pair_bars
        if key.startswith("macro."):
            return key in self._aux_series
        return False

    def evaluate(
        self, bars: list[PriceBar], idx: int, signal: SignalConfig
    ) -> float:
        spec = get_primitive(signal.name)
        ctx = EvaluationContext(
            bars=bars,
            idx=idx,
            pair=self._pair,
            params=signal.params,
            aux_series=self._aux_series,
            event_snapshot=self._event_snapshot,
            vix_snapshot=self._vix_snapshot,
            strict_snapshot_required=self._strict_snapshot_required,
            aux_pair_bars=self._aux_pair_bars,
        )
        return spec.compute(ctx)
```

注: 既存 evaluator は event_snapshot / vix_snapshot を kwarg で持たない。
T013 で追加するが既存テスト (T012) は変更不要 (default None)。

## 2.5 strict_* flag の責務境界 (Codex design-review 1-4 反映)

T012 で導入された `strict_snapshot_required` と本 TODO 追加の `strict_aux_required` の
責務を以下に明確化:

| flag | 責務範囲 | 検証タイミング | 触発する例外 |
|------|----------|----------------|--------------|
| `strict_snapshot_required` | M4/M5/P5/P7/P10/P11 など、**compute 内で snapshot/aux 欠損時に safe default で走る挙動**を許さない | compute 実行時 (per-call) | `RuntimeError("...missing but strict mode")` |
| `strict_aux_required` | **RegistryEvaluator 起動時に preflight verify** で selected primitive の required_data が provide されているかチェック | `RegistryEvaluator.__init__` | `RuntimeError("required aux missing for selected primitives: ...")` |

**両 flag の関係**:
- `strict_aux_required=True` は preflight で MISSING_KEY を起動時に弾く → compute 中に
  MISSING_KEY が発生しないため、`strict_snapshot_required` の compute 中チェックも
  実質的に発火しない
- `strict_snapshot_required=True` は単独でも有効 (preflight をスキップして compute 中に
  fail-fast)
- production runner では **両方 True** が推奨 (preflight + compute 両層で fail-fast)
- 開発/テストでは両方 False が default、特定 case のみ True を testing fixture で
  切替

**既存 EvaluationContext の `strict_snapshot_required` field の意味更新**:
- T012 では「snapshot (event/vix) 欠損時の compute 内挙動」を制御していた
- T013 では aux_series / aux_pair_bars 欠損時の compute 内挙動も含めて「**aux 全般の
  per-call strict**」という意味に拡張する
- field 名は変更しない (後方互換、既存テスト T012 の意図と整合)
- docstring を更新して新しい意味を明記

## 3. pair_specific.py 共通ヘルパー

```python
"""通貨ペア特化 directional/MODULATOR primitive 12 個 (T013, P1-P12)。

すべて domain="pair_specific"。設計起点ペアあるが他ペアでも crash しない。

look-ahead bias 回避は conceptual-design.md L1-L10 を参照。
"""

from __future__ import annotations

import bisect
import warnings
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC

import numpy as np

from src.alpha_factory.primitives._base import (
    EvaluationContext,
    ParamSpec,
    PrimitiveSpec,
)
from src.alpha_factory.primitives._indicators import (
    _EPS,
    atr,
    sigmoid,
    zscore,
)
from src.domain.price import PriceBar

# Codex design-review 1-5 反映: P1-P12 で実際に使う `_EPS`, `atr`, `sigmoid`,
# `zscore` のみ import。`log_returns_from_close`, `rolling_max`, `rolling_min` は
# 本 TODO 範囲では使用しないため import しない (lint clean)。実装中に必要が出たら
# 追加 import する規約。


def _bars_to_mid_ohlc(bars):
    """mid OHLC を float64 配列で。directional_generic / modulator_generic と同等。"""
    length = len(bars)
    o = np.empty(length, dtype=np.float64)
    h = np.empty(length, dtype=np.float64)
    low = np.empty(length, dtype=np.float64)
    c = np.empty(length, dtype=np.float64)
    for i, b in enumerate(bars):
        o[i] = (float(b.bid.open) + float(b.ask.open)) * 0.5
        h[i] = (float(b.bid.high) + float(b.ask.high)) * 0.5
        low[i] = (float(b.bid.low) + float(b.ask.low)) * 0.5
        c[i] = (float(b.bid.close) + float(b.ask.close)) * 0.5
    return o, h, low, c


def _bars_to_mid_close(bars) -> np.ndarray:
    """mid close 配列のみが欲しいケース用 short-cut。"""
    n = len(bars)
    out = np.empty(n, dtype=np.float64)
    for i, b in enumerate(bars):
        out[i] = (float(b.bid.close) + float(b.ask.close)) * 0.5
    return out


def _bar_time_minutes_utc(b: PriceBar) -> float:
    t = b.bar_time.astimezone(UTC)
    return t.hour * 60.0 + t.minute + t.second / 60.0


def _aligned_pair_close(
    target_bars: Sequence[PriceBar],
    aux_bars: Sequence[PriceBar | None] | None,
) -> np.ndarray:
    """aux_bars[i] が None なら NaN、そうでなければ mid close。
    bar_time 一致を strict assert（misalignment は ValueError）。
    aux_bars が None または長さ不一致は ValueError。
    """
    if aux_bars is None:
        # MISSING_KEY 経路 (caller が判断する)
        return np.full(len(target_bars), np.nan, dtype=np.float64)
    if len(aux_bars) != len(target_bars):
        raise ValueError(
            f"aux_pair_bars length mismatch: aux={len(aux_bars)} != "
            f"bars={len(target_bars)}"
        )
    out = np.empty(len(target_bars), dtype=np.float64)
    for i, (tb, ab) in enumerate(zip(target_bars, aux_bars, strict=True)):
        if ab is None:
            out[i] = np.nan
            continue
        if ab.bar_time != tb.bar_time:
            raise ValueError(
                f"aux_pair_bars bar_time mismatch at i={i}: "
                f"aux={ab.bar_time!r} != target={tb.bar_time!r}"
            )
        out[i] = (float(ab.bid.close) + float(ab.ask.close)) * 0.5
    return out


_ComputeAllFn = Callable[[EvaluationContext], np.ndarray]


def _make_compute_single(
    compute_all: _ComputeAllFn, *, neutral: float = 0.0,
) -> Callable[[EvaluationContext], float]:
    def _compute(ctx: EvaluationContext) -> float:
        arr = compute_all(ctx)
        idx = ctx.idx
        if idx < 0 or idx >= len(arr):
            return neutral
        v = arr[idx]
        return neutral if not np.isfinite(v) else float(v)
    return _compute


def _get_int_param(params: Mapping[str, float | int], key: str) -> int:
    return int(params[key])


def _get_float_param(params: Mapping[str, float | int], key: str) -> float:
    return float(params[key])


def _warn_missing(primitive_id: str, what: str) -> None:
    warnings.warn(
        f"{primitive_id}: {what} missing; returning safe default. "
        "Production must enable strict_aux_required for fail-fast.",
        RuntimeWarning,
        stacklevel=3,
    )


def _stale_mask(
    series: np.ndarray, staleness_bars: int,
) -> np.ndarray:
    """直前 finite 値からの距離が staleness_bars を超える index を True にする mask。

    series 自体の NaN は最初から True (stale 同等)。
    """
    n = len(series)
    mask = np.ones(n, dtype=bool)  # default stale
    last_finite = -1
    for i in range(n):
        if np.isfinite(series[i]):
            last_finite = i
            mask[i] = False
        else:
            if last_finite < 0 or (i - last_finite) > staleness_bars:
                mask[i] = True
            else:
                mask[i] = False  # 短い欠損は許容 (forward-fill 想定)
    return mask
```

## 4. P1-P12 仕様

各 primitive のテンプレートは下記。

### P1 LondonNYOverlapMomentum (TREND_FOLLOW, EUR_USD)

```python
def _p1_compute_all(ctx):
    """ロンドン-NY オーバーラップ (13:00-17:00 UTC) 内の bar に対し、
    過去 n バー return の符号付き正規化値を返す。範囲外は 0。
    """
    n = _get_int_param(ctx.params, "n")
    overlap_lo = 13 * 60.0
    overlap_hi = 17 * 60.0
    c = _bars_to_mid_close(ctx.bars)
    out = np.zeros(len(ctx.bars), dtype=np.float64)
    for i in range(len(ctx.bars)):
        m = _bar_time_minutes_utc(ctx.bars[i])
        if not (overlap_lo <= m < overlap_hi):
            out[i] = 0.0
            continue
        if i < n:
            out[i] = np.nan
            continue
        ret = (c[i] - c[i - n]) / (c[i - n] + _EPS)
        # tanh 正規化、scale param で sensitivity 調整
        scale = _get_float_param(ctx.params, "scale")
        out[i] = float(np.tanh(ret / (scale + _EPS)))
    return out

P1_SPEC = PrimitiveSpec(
    id="P1", name="LondonNYOverlapMomentum",
    category="TREND_FOLLOW", domain="pair_specific",
    param_schema=(
        ParamSpec(name="n", low=2, high=24, is_int=True, default=6),
        ParamSpec(name="scale", low=0.0001, high=0.02,
                  is_int=False, default=0.002),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_p1_compute_all),
    compute_all_bars=_p1_compute_all,
)
```

### P2 IntradayRangeFade (MEAN_REVERT, EUR_USD)

```python
def _p2_compute_all(ctx):
    """アジア時間 (00:00-07:00 UTC) bar の rolling max/min を当日 range とし、
    NY 時間 (12:00-21:00 UTC) bar で close が range 外なら reversion (符号反転)。
    """
    asia_lo, asia_hi = 0 * 60.0, 7 * 60.0
    ny_lo, ny_hi = 12 * 60.0, 21 * 60.0
    n_atr = _get_int_param(ctx.params, "atr_n")
    _, h, low, c = _bars_to_mid_ohlc(ctx.bars)
    a = atr(h, low, c, n_atr)
    n = len(ctx.bars)
    out = np.zeros(n, dtype=np.float64)
    # 当日 range を保持: bar_time の date が変わったらリセット
    cur_date = None
    cur_high = -np.inf
    cur_low = np.inf
    range_locked = False  # アジア終了後 True
    for i in range(n):
        bt_utc = ctx.bars[i].bar_time.astimezone(UTC)
        d = bt_utc.date()
        m = _bar_time_minutes_utc(ctx.bars[i])
        if d != cur_date:
            cur_date = d
            cur_high = -np.inf
            cur_low = np.inf
            range_locked = False
        if asia_lo <= m < asia_hi:
            cur_high = max(cur_high, h[i])
            cur_low = min(cur_low, low[i])
            out[i] = 0.0
            continue
        if m >= asia_hi:
            range_locked = True
        if not (ny_lo <= m < ny_hi) or not range_locked or not np.isfinite(a[i]):
            out[i] = 0.0
            continue
        if cur_high <= cur_low:  # range 形成不能
            out[i] = 0.0
            continue
        # close が range 上限 (cur_high) 超え → 売り (-)、下限 (cur_low) 未満 → 買い (+)
        atr_i = a[i] + _EPS
        if c[i] > cur_high:
            out[i] = -float(np.tanh((c[i] - cur_high) / atr_i))
        elif c[i] < cur_low:
            out[i] = +float(np.tanh((cur_low - c[i]) / atr_i))
        else:
            out[i] = 0.0
    return out

P2_SPEC = PrimitiveSpec(
    id="P2", name="IntradayRangeFade",
    category="MEAN_REVERT", domain="pair_specific",
    param_schema=(
        ParamSpec(name="atr_n", low=7, high=28, is_int=True, default=14),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_p2_compute_all),
    compute_all_bars=_p2_compute_all,
)
```

### P3 TokyoOpenReversal (MEAN_REVERT, USD_JPY)

```python
def _p3_compute_all(ctx):
    """東京オープン直後 (00:00-02:00 UTC) bar に対し、過去 n バー return の符号反転を返す。
    範囲外は 0。
    """
    open_lo = 0 * 60.0
    open_hi = 2 * 60.0
    n = _get_int_param(ctx.params, "n")
    c = _bars_to_mid_close(ctx.bars)
    out = np.zeros(len(ctx.bars), dtype=np.float64)
    for i in range(len(ctx.bars)):
        m = _bar_time_minutes_utc(ctx.bars[i])
        if not (open_lo <= m < open_hi):
            out[i] = 0.0
            continue
        if i < n:
            out[i] = np.nan
            continue
        ret = (c[i] - c[i - n]) / (c[i - n] + _EPS)
        scale = _get_float_param(ctx.params, "scale")
        # mean revert: 反転符号
        out[i] = -float(np.tanh(ret / (scale + _EPS)))
    return out

P3_SPEC = PrimitiveSpec(
    id="P3", name="TokyoOpenReversal",
    category="MEAN_REVERT", domain="pair_specific",
    param_schema=(
        ParamSpec(name="n", low=1, high=12, is_int=True, default=3),
        ParamSpec(name="scale", low=0.0001, high=0.02,
                  is_int=False, default=0.002),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_p3_compute_all),
    compute_all_bars=_p3_compute_all,
)
```

### P4 YenFixingBias (TREND_FOLLOW, USD_JPY)

```python
def _p4_compute_all(ctx):
    """仲値 (UTC 00:55) 前後 ±window_min 内で bias を返す。仲値以前 = +1 寄り、以後 = -1 寄り。
    """
    fixing_min = 0 * 60.0 + 55.0  # 00:55 UTC
    window_min = _get_float_param(ctx.params, "window_min")
    scale_min = _get_float_param(ctx.params, "scale_min")
    n = len(ctx.bars)
    out = np.zeros(n, dtype=np.float64)
    for i in range(n):
        m = _bar_time_minutes_utc(ctx.bars[i])
        # 当日内の仲値時刻との分差 (24h 周回は無視)
        delta = m - fixing_min
        if abs(delta) > window_min:
            out[i] = 0.0
            continue
        # 仲値前 (delta < 0) → +1 寄り、後 (delta > 0) → -1 寄り
        # 強度 = sigmoid(-|delta| / scale_min) → 0 寄りと 1 寄り、bias_sign で符号
        sign = 1.0 if delta <= 0 else -1.0
        magnitude = 2.0 * float(sigmoid(-abs(delta) / (scale_min + _EPS))) - 0.0
        # 0..1 → 0..2 から sign で符号付与、tanh 正規化
        out[i] = float(np.tanh(sign * magnitude))
    return out

P4_SPEC = PrimitiveSpec(
    id="P4", name="YenFixingBias",
    category="TREND_FOLLOW", domain="pair_specific",
    param_schema=(
        ParamSpec(name="window_min", low=5.0, high=120.0,
                  is_int=False, default=30.0),
        ParamSpec(name="scale_min", low=1.0, high=30.0,
                  is_int=False, default=10.0),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_p4_compute_all),
    compute_all_bars=_p4_compute_all,
)
```

### P5 CrossPairTriangulation (MEAN_REVERT, EUR_JPY)

```python
def _p5_compute_all(ctx):
    """target = EUR_JPY、aux = EUR_USD * USD_JPY の合成 mid との残差を z-score 化し、
    符号反転で mean-revert signal を返す。

    aux_pair_bars["EUR_USD"] / aux_pair_bars["USD_JPY"] が両方そろっているとき動作。
    片方でも MISSING_KEY なら warning + safe default 0.0 全 bar 返却。
    """
    n = len(ctx.bars)
    eu = ctx.aux_pair_bars.get("EUR_USD")
    uj = ctx.aux_pair_bars.get("USD_JPY")
    if eu is None or uj is None:
        if ctx.strict_snapshot_required:
            raise RuntimeError(
                "P5: aux_pair_bars EUR_USD / USD_JPY missing but strict mode"
            )
        _warn_missing("P5", "aux_pair_bars EUR_USD/USD_JPY")
        return np.zeros(n, dtype=np.float64)
    eu_close = _aligned_pair_close(ctx.bars, eu)  # NaN if stale
    uj_close = _aligned_pair_close(ctx.bars, uj)
    target_close = _bars_to_mid_close(ctx.bars)
    synth = eu_close * uj_close
    residual = target_close - synth
    z_n = _get_int_param(ctx.params, "z_n")
    z = zscore(residual, z_n)
    # mean-revert: -tanh(z / scale)
    scale = _get_float_param(ctx.params, "scale")
    out = -np.tanh(z / (scale + _EPS))
    # NaN 伝播 (stale or warmup)
    out = np.where(np.isnan(z), np.nan, out)
    return out

P5_SPEC = PrimitiveSpec(
    id="P5", name="CrossPairTriangulation",
    category="MEAN_REVERT", domain="pair_specific",
    param_schema=(
        ParamSpec(name="z_n", low=20, high=200, is_int=True, default=60),
        ParamSpec(name="scale", low=0.5, high=5.0,
                  is_int=False, default=2.0),
    ),
    required_data=("ohlc", "cross_pair.EUR_USD", "cross_pair.USD_JPY"),
    compute=_make_compute_single(_p5_compute_all),
    compute_all_bars=_p5_compute_all,
)
```

### P6 EuroHourVolRegime (MODULATOR, EUR_JPY)

```python
def _p6_compute_all(ctx):
    """欧州時間 (07:00-15:00 UTC) かつ ATR_rel が threshold 超のとき 1 寄り。
    範囲外 / 低 vol は 0。
    """
    eu_lo, eu_hi = 7 * 60.0, 15 * 60.0
    n_atr = _get_int_param(ctx.params, "atr_n")
    threshold_rel = _get_float_param(ctx.params, "threshold_rel")
    scale_rel = _get_float_param(ctx.params, "scale_rel")
    _, h, low, c = _bars_to_mid_ohlc(ctx.bars)
    a = atr(h, low, c, n_atr)
    atr_rel = a / (c + _EPS)
    out = np.zeros(len(ctx.bars), dtype=np.float64)
    for i in range(len(ctx.bars)):
        m = _bar_time_minutes_utc(ctx.bars[i])
        if not (eu_lo <= m < eu_hi):
            out[i] = 0.0
            continue
        if not np.isfinite(atr_rel[i]):
            out[i] = np.nan
            continue
        out[i] = float(sigmoid((atr_rel[i] - threshold_rel) / (scale_rel + _EPS)))
    return out

P6_SPEC = PrimitiveSpec(
    id="P6", name="EuroHourVolRegime",
    category="MODULATOR", domain="pair_specific",
    param_schema=(
        ParamSpec(name="atr_n", low=7, high=28, is_int=True, default=14),
        ParamSpec(name="threshold_rel", low=0.0001, high=0.02,
                  is_int=False, default=0.003),
        ParamSpec(name="scale_rel", low=0.00001, high=0.01,
                  is_int=False, default=0.0015),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_p6_compute_all, neutral=0.5),
    compute_all_bars=_p6_compute_all,
)
```

### P7 RiskOnOffProxy (TREND_FOLLOW, AUD_JPY)

```python
def _p7_compute_all(ctx):
    """VIX 低 (リスクオン) かつ SPX 上昇モメンタム → AUD-buy / JPY-sell bias = +
    VIX 高 or SPX 下落 → 反対方向。

    依存:
      - vix_snapshot (publication-based, M5 と同方針)
      - aux_series["macro.spx500"] (bar-aligned)
    """
    n = len(ctx.bars)
    vix_snap = ctx.vix_snapshot
    spx = ctx.aux_series.get("macro.spx500")
    has_vix = (
        vix_snap is not None and vix_snap.observations
    )
    has_spx = spx is not None and len(spx) == n
    if not has_vix or not has_spx:
        if ctx.strict_snapshot_required:
            raise RuntimeError(
                "P7: vix_snapshot or aux_series['macro.spx500'] missing but strict mode"
            )
        _warn_missing("P7", "vix_snapshot or macro.spx500")
        return np.zeros(n, dtype=np.float64)
    spx_arr = np.asarray(spx, dtype=np.float64)
    # SPX momentum (n bar)
    spx_n = _get_int_param(ctx.params, "spx_n")
    spx_mom = np.full(n, np.nan, dtype=np.float64)
    if n > spx_n:
        spx_mom[spx_n:] = (spx_arr[spx_n:] - spx_arr[:-spx_n]) / (
            np.abs(spx_arr[:-spx_n]) + _EPS
        )
    # VIX lookup per bar (bisect_left)
    pubs = [o[0] for o in vix_snap.observations]
    vals = [o[1] for o in vix_snap.observations]
    vix_threshold = _get_float_param(ctx.params, "vix_threshold")
    vix_scale = _get_float_param(ctx.params, "vix_scale")
    vix_staleness_days = _get_float_param(ctx.params, "vix_staleness_days")
    spx_staleness_bars = _get_int_param(ctx.params, "spx_staleness_bars")
    spx_stale = _stale_mask(spx_arr, spx_staleness_bars)
    out = np.zeros(n, dtype=np.float64)
    for i in range(n):
        bt = ctx.bars[i].bar_time
        k = bisect.bisect_left(pubs, bt)
        if k == 0:
            out[i] = np.nan
            continue
        vix = vals[k - 1]
        vix_age_days = (bt - pubs[k - 1]).total_seconds() / 86400.0
        if vix_age_days > vix_staleness_days:
            out[i] = np.nan
            continue
        if spx_stale[i] or not np.isfinite(spx_mom[i]):
            out[i] = np.nan
            continue
        # risk_on score: low VIX + SPX up → +1
        vix_score = float(sigmoid((vix_threshold - vix) / (vix_scale + _EPS))) - 0.5
        # vix_score > 0 (低 VIX), < 0 (高 VIX)
        spx_score = float(np.tanh(spx_mom[i] / 0.01))  # scale 0.01 ~= 1% momentum ≈ 1
        # combined: 平均 (-1 .. +1)
        out[i] = float(np.tanh(vix_score * 2.0 + spx_score))
    return out

P7_SPEC = PrimitiveSpec(
    id="P7", name="RiskOnOffProxy",
    category="TREND_FOLLOW", domain="pair_specific",
    param_schema=(
        ParamSpec(name="spx_n", low=2, high=48, is_int=True, default=12),
        ParamSpec(name="vix_threshold", low=10.0, high=40.0,
                  is_int=False, default=20.0),
        ParamSpec(name="vix_scale", low=1.0, high=15.0,
                  is_int=False, default=5.0),
        ParamSpec(name="vix_staleness_days", low=1.0, high=30.0,
                  is_int=False, default=7.0),
        ParamSpec(name="spx_staleness_bars", low=1, high=500,
                  is_int=True, default=120),
    ),
    required_data=("ohlc", "macro.vix", "macro.spx500"),
    compute=_make_compute_single(_p7_compute_all),
    compute_all_bars=_p7_compute_all,
)
```

### P8 CommodityFlowBias (TREND_FOLLOW, AUD_JPY)

**Codex design-review 1-3 反映**: `use_copper` param を撤廃し、aux_series 提供者の
存在で自動切替する設計に統一。`required_data` は両方記載し preflight でいずれか
1 つは必ず提供される必要がある (両方 OK でも片方 OK)。

実装: `aux_series["macro.copper"]` を 1 次優先、無ければ `aux_series["macro.commodity_index"]`
fallback。両方無いとき MISSING_KEY (warning + safe default)。

```python
def _p8_compute_all(ctx):
    """銅 (1 次) / 商品 index (fallback) momentum 上昇 → AUD-buy bias = +。
    依存: aux_series["macro.copper"] OR aux_series["macro.commodity_index"]。
    """
    n = len(ctx.bars)
    series = ctx.aux_series.get("macro.copper")
    selected_key = "macro.copper"
    if series is None or len(series) != n:
        series = ctx.aux_series.get("macro.commodity_index")
        selected_key = "macro.commodity_index"
    if series is None or len(series) != n:
        if ctx.strict_snapshot_required:
            raise RuntimeError(
                "P8: macro.copper and macro.commodity_index both missing but strict mode"
            )
        _warn_missing("P8", "macro.copper or macro.commodity_index")
        return np.zeros(n, dtype=np.float64)
    arr = np.asarray(series, dtype=np.float64)
    mom_n = _get_int_param(ctx.params, "mom_n")
    staleness_bars = _get_int_param(ctx.params, "staleness_bars")
    stale = _stale_mask(arr, staleness_bars)
    mom = np.full(n, np.nan, dtype=np.float64)
    if n > mom_n:
        mom[mom_n:] = (arr[mom_n:] - arr[:-mom_n]) / (np.abs(arr[:-mom_n]) + _EPS)
    scale = _get_float_param(ctx.params, "scale")
    out = np.where(stale | ~np.isfinite(mom), np.nan, np.tanh(mom / (scale + _EPS)))
    return out

P8_SPEC = PrimitiveSpec(
    id="P8", name="CommodityFlowBias",
    category="TREND_FOLLOW", domain="pair_specific",
    param_schema=(
        ParamSpec(name="mom_n", low=2, high=48, is_int=True, default=12),
        ParamSpec(name="scale", low=0.001, high=0.1, is_int=False, default=0.01),
        ParamSpec(name="staleness_bars", low=1, high=500, is_int=True, default=120),
    ),
    required_data=("ohlc",),
    optional_data_groups=(("macro.copper", "macro.commodity_index"),),
    compute=_make_compute_single(_p8_compute_all),
    compute_all_bars=_p8_compute_all,
)
```

**preflight verify の OR semantics 拡張**:

P8 の `required_data` は両方記載されるが、`(macro.copper OR macro.commodity_index)` の
いずれかが provide されれば OK にしたい。本 TODO では preflight verify を以下のように
拡張する:

`PrimitiveSpec` に **optional な `optional_data_groups: tuple[tuple[str, ...], ...] = ()`**
を追加し、各 group 内 1 つ以上が provide されれば OK と扱う。
P8: `optional_data_groups=(("macro.copper", "macro.commodity_index"),)`、
`required_data=("ohlc",)` のみ強制。

```python
@dataclass(frozen=True)
class PrimitiveSpec:
    id: str
    name: str
    category: PrimitiveCategory
    domain: PrimitiveDomain
    param_schema: tuple[ParamSpec, ...]
    required_data: tuple[str, ...]
    compute: ComputeFn
    compute_all_bars: ComputeAllBarsFn
    # T013 追加 (default 空 tuple で後方互換)
    optional_data_groups: tuple[tuple[str, ...], ...] = ()
```

`validate_primitive_spec` で `optional_data_groups` 内の全 key が
`is_valid_required_data` を満たすことを check。

`RegistryEvaluator._preflight_verify` で:
1. spec.required_data の全 key が provide されていることを必須 check
2. spec.optional_data_groups の各 group につき、少なくとも 1 つが provide されていることを check

これで P8 は `required_data=("ohlc",)` + `optional_data_groups=(("macro.copper",
"macro.commodity_index"),)` で「ohlc 必須、commodity 系列はどちらか 1 つ必須」を表現できる。

### P9 OilPriceInverseFlow (TREND_FOLLOW, USD_CAD)

```python
def _p9_compute_all(ctx):
    """WTI 上昇 → CAD 上昇 → USD_CAD 下落、therefore -tanh(wti_momentum)。
    依存: aux_series["macro.wti"]。
    """
    n = len(ctx.bars)
    series = ctx.aux_series.get("macro.wti")
    if series is None or len(series) != n:
        if ctx.strict_snapshot_required:
            raise RuntimeError("P9: aux_series['macro.wti'] missing but strict mode")
        _warn_missing("P9", "macro.wti")
        return np.zeros(n, dtype=np.float64)
    arr = np.asarray(series, dtype=np.float64)
    mom_n = _get_int_param(ctx.params, "mom_n")
    staleness_bars = _get_int_param(ctx.params, "staleness_bars")
    stale = _stale_mask(arr, staleness_bars)
    mom = np.full(n, np.nan, dtype=np.float64)
    if n > mom_n:
        mom[mom_n:] = (arr[mom_n:] - arr[:-mom_n]) / (np.abs(arr[:-mom_n]) + _EPS)
    scale = _get_float_param(ctx.params, "scale")
    out = np.where(stale | ~np.isfinite(mom), np.nan, -np.tanh(mom / (scale + _EPS)))
    return out

P9_SPEC = PrimitiveSpec(
    id="P9", name="OilPriceInverseFlow",
    category="TREND_FOLLOW", domain="pair_specific",
    param_schema=(
        ParamSpec(name="mom_n", low=2, high=48, is_int=True, default=12),
        ParamSpec(name="scale", low=0.001, high=0.1, is_int=False, default=0.02),
        ParamSpec(name="staleness_bars", low=1, high=500, is_int=True, default=120),
    ),
    required_data=("ohlc", "macro.wti"),
    compute=_make_compute_single(_p9_compute_all),
    compute_all_bars=_p9_compute_all,
)
```

### P10 NADataProximityGate (MODULATOR, USD_CAD)

```python
def _p10_compute_all(ctx):
    """北米セッション (12:00-21:00 UTC) かつ USD/CAD イベント ±window 分以内で gate を
    抑制する。範囲外は 1.0 (無効化、M4 と切り分け)。
    """
    n = len(ctx.bars)
    na_lo, na_hi = 12 * 60.0, 21 * 60.0
    if ctx.event_snapshot is None:
        if ctx.strict_snapshot_required:
            raise RuntimeError("P10: event_snapshot missing but strict mode")
        _warn_missing("P10", "event_snapshot")
        return np.ones(n, dtype=np.float64)
    snapshot = ctx.event_snapshot
    calendar = snapshot.calendar
    as_of_ts = snapshot.as_of.timestamp()
    min_impact = _get_int_param(ctx.params, "min_impact")
    window_min = _get_float_param(ctx.params, "window_min")
    scale_min = _get_float_param(ctx.params, "scale_min")
    relevant = [
        e for e in calendar.events
        if e.impact >= min_impact
        and e.currency in ("USD", "CAD")
        and e.event_time.timestamp() <= as_of_ts
    ]
    out = np.ones(n, dtype=np.float64)
    if not relevant:
        return out
    event_times = np.array(
        [e.event_time.timestamp() for e in relevant], dtype=np.float64
    )
    for i in range(n):
        m = _bar_time_minutes_utc(ctx.bars[i])
        if not (na_lo <= m < na_hi):
            out[i] = 1.0  # NA セッション外は gate 開放
            continue
        t = ctx.bars[i].bar_time.timestamp()
        diff_min = float(np.min(np.abs(event_times - t)) / 60.0)
        raw = (window_min - diff_min) / (scale_min + _EPS)
        out[i] = 1.0 - float(sigmoid(raw))
    return out

P10_SPEC = PrimitiveSpec(
    id="P10", name="NADataProximityGate",
    category="MODULATOR", domain="pair_specific",
    param_schema=(
        ParamSpec(name="window_min", low=5.0, high=120.0,
                  is_int=False, default=30.0),
        ParamSpec(name="scale_min", low=1.0, high=30.0,
                  is_int=False, default=5.0),
        ParamSpec(name="min_impact", low=1, high=3, is_int=True, default=3),
    ),
    required_data=("ohlc", "calendar.economic_event"),
    compute=_make_compute_single(_p10_compute_all, neutral=1.0),
    compute_all_bars=_p10_compute_all,
)
```

### P11 EmergingMarketStressGate (MODULATOR, USD_ZAR)

```python
def _p11_compute_all(ctx):
    """高 VIX + DXY 高 → EM ストレス → gate 抑制 (0 寄り)。
    低 VIX + DXY 低 → リスクオン → gate 開放 (1 寄り)。

    依存: vix_snapshot + aux_series["macro.dxy"]。
    """
    n = len(ctx.bars)
    vix_snap = ctx.vix_snapshot
    dxy = ctx.aux_series.get("macro.dxy")
    has_vix = vix_snap is not None and vix_snap.observations
    has_dxy = dxy is not None and len(dxy) == n
    if not has_vix or not has_dxy:
        if ctx.strict_snapshot_required:
            raise RuntimeError("P11: vix_snapshot or macro.dxy missing but strict mode")
        _warn_missing("P11", "vix_snapshot or macro.dxy")
        return np.full(n, 0.5, dtype=np.float64)
    dxy_arr = np.asarray(dxy, dtype=np.float64)
    dxy_n = _get_int_param(ctx.params, "dxy_n")
    dxy_staleness_bars = _get_int_param(ctx.params, "dxy_staleness_bars")
    vix_staleness_days = _get_float_param(ctx.params, "vix_staleness_days")
    vix_threshold = _get_float_param(ctx.params, "vix_threshold")
    vix_scale = _get_float_param(ctx.params, "vix_scale")
    dxy_stale = _stale_mask(dxy_arr, dxy_staleness_bars)
    dxy_mom = np.full(n, np.nan, dtype=np.float64)
    if n > dxy_n:
        dxy_mom[dxy_n:] = (dxy_arr[dxy_n:] - dxy_arr[:-dxy_n]) / (
            np.abs(dxy_arr[:-dxy_n]) + _EPS
        )
    pubs = [o[0] for o in vix_snap.observations]
    vals = [o[1] for o in vix_snap.observations]
    out = np.full(n, 0.5, dtype=np.float64)
    for i in range(n):
        if dxy_stale[i] or not np.isfinite(dxy_mom[i]):
            out[i] = np.nan
            continue
        bt = ctx.bars[i].bar_time
        k = bisect.bisect_left(pubs, bt)
        if k == 0:
            out[i] = np.nan
            continue
        vix = vals[k - 1]
        if (bt - pubs[k - 1]).total_seconds() / 86400.0 > vix_staleness_days:
            out[i] = np.nan
            continue
        # stress score: 高 VIX + DXY 上昇 → stress 大、gate 閉じる (0 寄り)
        vix_pressure = float(sigmoid((vix - vix_threshold) / (vix_scale + _EPS)))  # high vix → 1
        dxy_pressure = float(sigmoid(dxy_mom[i] / 0.005))  # dxy mom > 0 → ~1
        stress = (vix_pressure + dxy_pressure) * 0.5
        out[i] = 1.0 - stress  # high stress → low gate value
    return out

P11_SPEC = PrimitiveSpec(
    id="P11", name="EmergingMarketStressGate",
    category="MODULATOR", domain="pair_specific",
    param_schema=(
        ParamSpec(name="dxy_n", low=2, high=120, is_int=True, default=20),
        ParamSpec(name="vix_threshold", low=10.0, high=40.0,
                  is_int=False, default=25.0),
        ParamSpec(name="vix_scale", low=1.0, high=15.0,
                  is_int=False, default=5.0),
        ParamSpec(name="vix_staleness_days", low=1.0, high=30.0,
                  is_int=False, default=7.0),
        ParamSpec(name="dxy_staleness_bars", low=1, high=500,
                  is_int=True, default=240),
    ),
    required_data=("ohlc", "macro.vix", "macro.dxy"),
    compute=_make_compute_single(_p11_compute_all, neutral=0.5),
    compute_all_bars=_p11_compute_all,
)
```

### P12 GoldCorrelationBias (TREND_FOLLOW, USD_ZAR)

```python
def _p12_compute_all(ctx):
    """金価格 momentum 上昇 → ZAR 上昇 → USD_ZAR 下落、therefore -tanh(gold_mom)。
    依存: aux_series["macro.gold"]。
    """
    n = len(ctx.bars)
    series = ctx.aux_series.get("macro.gold")
    if series is None or len(series) != n:
        if ctx.strict_snapshot_required:
            raise RuntimeError("P12: macro.gold missing but strict mode")
        _warn_missing("P12", "macro.gold")
        return np.zeros(n, dtype=np.float64)
    arr = np.asarray(series, dtype=np.float64)
    mom_n = _get_int_param(ctx.params, "mom_n")
    staleness_bars = _get_int_param(ctx.params, "staleness_bars")
    stale = _stale_mask(arr, staleness_bars)
    mom = np.full(n, np.nan, dtype=np.float64)
    if n > mom_n:
        mom[mom_n:] = (arr[mom_n:] - arr[:-mom_n]) / (np.abs(arr[:-mom_n]) + _EPS)
    scale = _get_float_param(ctx.params, "scale")
    out = np.where(stale | ~np.isfinite(mom), np.nan, -np.tanh(mom / (scale + _EPS)))
    return out

P12_SPEC = PrimitiveSpec(
    id="P12", name="GoldCorrelationBias",
    category="TREND_FOLLOW", domain="pair_specific",
    param_schema=(
        ParamSpec(name="mom_n", low=2, high=48, is_int=True, default=12),
        ParamSpec(name="scale", low=0.001, high=0.1, is_int=False, default=0.02),
        ParamSpec(name="staleness_bars", low=1, high=500, is_int=True, default=120),
    ),
    required_data=("ohlc", "macro.gold"),
    compute=_make_compute_single(_p12_compute_all),
    compute_all_bars=_p12_compute_all,
)
```

## 5. ensure_registered

```python
_ALL_SPECS: tuple[PrimitiveSpec, ...] = (
    P1_SPEC, P2_SPEC, P3_SPEC, P4_SPEC, P5_SPEC, P6_SPEC,
    P7_SPEC, P8_SPEC, P9_SPEC, P10_SPEC, P11_SPEC, P12_SPEC,
)


def ensure_registered() -> None:
    """12 pair-specific primitive を registry に登録する。冪等。"""
    from src.alpha_factory.primitives._registry import register_if_absent
    for spec in _ALL_SPECS:
        register_if_absent(spec)


def all_specs() -> tuple[PrimitiveSpec, ...]:
    return _ALL_SPECS


PAIR_SPECIFIC_SPECS: tuple[PrimitiveSpec, ...] = _ALL_SPECS
```

## 6. _registry.py::ensure_registered() への追加

```python
def ensure_registered() -> None:
    from src.alpha_factory.primitives.directional_generic import (
        ensure_registered as _reg_directional_generic,
    )
    from src.alpha_factory.primitives.modulator_generic import (
        ensure_registered as _reg_modulator_generic,
    )
    from src.alpha_factory.primitives.pair_specific import (
        ensure_registered as _reg_pair_specific,
    )

    _reg_directional_generic()
    _reg_modulator_generic()
    _reg_pair_specific()
```

## 7. テスト設計 (test_pair_specific.py)

`test_modulator_generic.py` のパターンを踏襲。

### 7.1 Fixtures
- `_build_bars(...)` を流用 (既存と同じ helper)、必要に応じ pair_specific 用 base_time を
  渡す
- `_mock_aux_series(name, value, length)` ヘルパー (定数 series 生成)
- `_mock_aux_pair_bars(target_bars, pair_name, ratio)` ヘルパー
  (target と同じ bar_time, mid 値を ratio 倍した synthetic bar 列)

### 7.2 TestRegistryIntegration
- `test_all_32_registered`: list_all() == 32, P1-P12 含む
- `test_pair_specific_count_is_12`: list_by_domain("pair_specific") == 12
- `test_each_pair_specific_retrievable`: P1-P12 が get_primitive で取れる
- `test_module_level_spec_tuple_consistent`: PAIR_SPECIFIC_SPECS == _ALL_SPECS
- `test_total_generic_unchanged`: list_by_domain("generic") == 20

### 7.3 TestEachPrimitiveCommon (parametrize)
全 12 primitive に対し:
- `test_compute_matches_compute_all_bars`: compute(idx) == compute_all_bars[idx]
  (NaN は neutral 値に吸収)
- `test_output_in_expected_range`: directional は [-1, +1]、MODULATOR は [0, 1]
- `test_no_lookahead_property`: bars[k+1:] 改変で過去 index 不変

各 primitive の必要 aux はモック注入する (snapshot + aux_series + aux_pair_bars)。

### 7.4 個別テスト
- P1: London-NY 帯 (UTC 13-17) 内で正の momentum bar → 正値、外で 0
- P2: アジア range 上限超え → 負値、内側 → 0
- P3: 東京 open 直後で過去 return が正 → 反転で負値
- P4: 仲値 ±30 分以前で +、以後で -
- P5: aux_pair_bars 揃い、residual > 0 (target が合成より高い) → 負値 (mean-revert 売り)
- P6: 欧州時間内 (UTC 7-15) かつ高 ATR → > 0.5
- P7: vix=10, spx_mom>0 → +、vix=35, spx_mom<0 → -
- P8: copper 上昇 momentum → +
- P9: wti 上昇 momentum → -
- P10: NA セッション内 + event ±window 内 → 0 寄り、外 → 1.0
- P11: 高 VIX + DXY 上昇 → < 0.5
- P12: gold 上昇 momentum → -

### 7.5 3 状態テスト (TestAuxStateBehavior)
- MISSING_KEY:
  - P5/P7/P8/P9/P10/P11/P12 で aux 未指定 → RuntimeWarning + safe default 全 bar
- STALE_VALUE:
  - aux_series に NaN 列 / aux_pair_bars に None 列 → 該当 bar 出力 NaN
- MISALIGNMENT:
  - aux_pair_bars[k] の長さ違い → ValueError
  - aux_pair_bars[k][i].bar_time != bars[i].bar_time → ValueError

### 7.6 strict_aux_required preflight verify
- `RegistryEvaluator(strict_aux_required=True, selected_primitive_ids=("P5",))`:
  aux_pair_bars 未指定 → RuntimeError
- 必要 aux が揃っているとき → 正常初期化
- `strict_aux_required=True, selected_primitive_ids=None` → ValueError

### 7.7 strict_snapshot_required (compute 中)
- P5 strict=True で aux_pair_bars 未指定 → RuntimeError
- P7 strict=True で vix_snapshot 未指定 → RuntimeError
- P10 strict=True で event_snapshot 未指定 → RuntimeError

### 7.8 後方互換
- F1-F14 / M1-M6 が aux_pair_bars 未指定でも動く (既存テスト全件 pass)
- EvaluationContext を新フィールド未指定で構築可能

### 7.9 RegistryEvaluator 経由
- 全 12 primitive を SignalConfig で evaluate して [-1, +1] / [0, 1] に収まる

## 8. ドキュメント更新

`docs/alpha_factory/primitives.md` に Pair-specific セクションを追加し、12 primitive の
ID, name, category, domain, param schema, required_data を明記。

## 9. 実装順序

1. `_base.py` の Literal / `_REQUIRED_DATA_LITERALS` / `EvaluationContext` 拡張
2. `pair_specific.py` の helper + P1-P4, P6 (価格内部 5 個) 実装
3. P5 + aux_pair_bars 関連
4. P7-P12 (aux_series 系)
5. `_registry.ensure_registered` 統合
6. `evaluator.py` の preflight verify
7. テスト追加 / 既存テスト破壊なし確認
8. mypy / ruff
9. ドキュメント追記

## 10. risk / mitigation

- **risk**: aux_series の bar-aligned 契約が loader 別 TODO に依存 → MVP では mock のみ
  - mitigation: preflight verify と strict_aux_required を本 TODO で実装済 →
    本物データ注入時に fail-fast 機能
- **risk**: 12 primitive のロジックが過剰でレビュー時間圧迫
  - mitigation: 共通ヘルパー (`_aligned_pair_close`, `_stale_mask`, `_warn_missing`) で
    冗長 code を削減、impl-review にも対応マトリクスで提示
- **risk**: P5/P7/P11 の複合ロジック誤算で fitness を歪める
  - mitigation: strict 3 状態テスト + look-ahead property テストで bias 0 を担保

## 11. Definition of Done (再掲)

`conceptual-design.md` の DoD と一致。
