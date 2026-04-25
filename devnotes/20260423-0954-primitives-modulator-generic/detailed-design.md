# T012 Modulator generic primitives (M1-M6) — Detailed Design

## 参照

- 概念設計: [`conceptual-design.md`](./conceptual-design.md)
- 既存 T011 実装: `src/alpha_factory/primitives/directional_generic.py`
- 既存 T010 base: `src/alpha_factory/primitives/_base.py`
- events: `src/events/calendar.py`, `src/events/repository.py`
- FRED ingest: `src/ingest/fred.py`, `src/db/models.py::MacroIndexDaily`

## 1. EvaluationContext 拡張と snapshot dataclass

### 1.1 新規 dataclass（`src/alpha_factory/primitives/_base.py` に追加）

```python
from __future__ import annotations
import bisect
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.events.calendar import EconomicCalendar


@dataclass(frozen=True)
class EconomicEventSnapshot:
    """as-of <= bar_time までに既知のイベントスケジュールのスナップショット。

    MVP 仮定:
        - backtest 使用時は calendar 全量を as_of=+∞ で渡す近似を許容
          （schedule の late amendment leakage は別 TODO で厳密化）
        - compute は event.event_time のみ参照、event.actual は触れない（FX live で未公開）

    Attributes:
        calendar: EconomicCalendar インスタンス
        as_of: この時刻までに予定が既知（future の schedule addition を防ぐ目安、MVP では使用は任意）
    """

    calendar: "EconomicCalendar"
    as_of: datetime


@dataclass(frozen=True)
class VixSeriesSnapshot:
    """VIX close の publication timestamp 付き観測列。

    Invariants:
        observations は publication_ts_utc 昇順にソート済み
        publication_ts_utc は obs_date の 21:15 UTC（保守固定、DST 考慮は別 TODO）

    Lookup:
        `lookup(bar_time)` は publication_ts_utc < bar_time (strict) を満たす最新 vix_close を返す。
        該当なしなら None。
    """

    # (publication_ts_utc, vix_close) 昇順
    observations: tuple[tuple[datetime, float], ...] = ()

    def __post_init__(self) -> None:
        """tz-aware datetime + 昇順を強制（Should-consider 対応）。"""
        prev_ts: datetime | None = None
        for i, (ts, _val) in enumerate(self.observations):
            if ts.tzinfo is None:
                raise ValueError(
                    f"VixSeriesSnapshot.observations[{i}] is naive datetime; "
                    "publication_ts_utc must be tz-aware"
                )
            if prev_ts is not None and ts < prev_ts:
                raise ValueError(
                    f"VixSeriesSnapshot.observations must be ascending by publication_ts_utc; "
                    f"index {i}: {ts!r} < previous {prev_ts!r}"
                )
            prev_ts = ts

    def lookup(self, bar_time: datetime) -> float | None:
        """bar_time より前に publication された observation から最新 vix_close を返す。

        O(log N) bisect_left。strict less than で future leak を防ぐ。
        """
        # observations[i][0] は datetime。bisect_left では key 関数を使う。
        # sequence が空なら None
        if not self.observations:
            return None
        # observations を publication_ts で二分探索
        # bisect が tuple 比較をしないよう、timestamp 列を作るのは O(N)。
        # MVP では observations サイズが daily * 数年 = ~1000 なので
        # 毎 bar で O(log N) + O(N) の timestamp 抽出を避けるため
        # 事前に publication_ts 列をキャッシュしたい。frozen dataclass なので
        # __post_init__ で object.__setattr__ を使うか、module-level helper で
        # lookup する。ここでは simple に lineal list comprehension で実装。
        pubs = [o[0] for o in self.observations]
        # bisect_left で ts 以上の最初の index を探す → 1 つ前が strict less than の最新
        i = bisect.bisect_left(pubs, bar_time)
        if i == 0:
            return None
        return self.observations[i - 1][1]
```

**性能注意**: 上記 `lookup` は毎 call で pubs 再構築し O(N)。MVP では problematic ではないが、
compute_all_bars で 20000 bar × daily 1000 observations だと 2e7 operations → 数秒で問題なし。
必要なら `__post_init__` で `object.__setattr__(self, "_pubs", tuple(...))` で cache する。

**採用**: simple 実装 + `compute_all_bars` 内で pubs を 1 度だけ構築して bar ループで bisect を
直接呼ぶ。個別 primitive 側で最適化。

### 1.2 EvaluationContext 変更（後方互換）

```python
@dataclass(frozen=True)
class EvaluationContext:
    bars: Sequence[PriceBar]
    idx: int
    pair: str
    params: Mapping[str, float | int]
    aux_series: Mapping[str, Sequence[float]] = field(default_factory=dict)
    # --- T012 追加（default=None で後方互換） ---
    event_snapshot: EconomicEventSnapshot | None = None
    vix_snapshot: VixSeriesSnapshot | None = None
    # --- Codex Must-fix 4 対応: strict mode ---
    strict_snapshot_required: bool = False
```

- T011 の既存テストは `event_snapshot / vix_snapshot / strict_snapshot_required` を指定せず構築するので壊れない（frozen dataclass への default 値付きフィールド追加は backward-compatible）。
- `_base.py` の既存 import（`EconomicCalendar`）は循環 import 回避のため TYPE_CHECKING ガード。
- `strict_snapshot_required=True` のとき、snapshot=None で primitive 呼び出しが発生したら `RuntimeError` を raise（safe default 経路を通らない）。production backtest runner はこの flag を True で渡すことで伝搬漏れを fail-fast で検知。

## 2. 共通 helper

### 2.1 `_modulator_indicators.py` は作らない（既存 `_indicators.py` に追加）

- `sigmoid(x) -> np.ndarray`: `1 / (1 + exp(-x))`（overflow 対策で `np.clip(x, -500, 500)`）
- セッション範囲の canonical 定義: `_SESSION_RANGES_UTC` を `_indicators.py` に移動（F6 からは re-export）

### 2.2 新規 helper（`_indicators.py` に追加）

```python
def sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    """数値安定な logistic sigmoid."""
    x_clipped = np.clip(x, -500.0, 500.0)
    return 1.0 / (1.0 + np.exp(-x_clipped))


# _indicators.py に移動（F6 と共通化）
_SESSION_RANGES_UTC: dict[int, tuple[int, int]] = {
    0: (0, 9),    # Tokyo
    1: (7, 16),   # London
    2: (12, 21),  # NY
}
```

`directional_generic.py` 側は `_SESSION_RANGES_UTC` の import 元を `_indicators.py` に差し替える。
**変更は minimal（import 行のみ）で、F6 compute のロジックは一切変わらない**。

## 3. 各 primitive の詳細設計

共通: `category="MODULATOR"`, `domain="generic"`, 出力 `[0, 1]`.

### 3.1 M1 ATRRegimeGate

**役割**: ATR が閾値を超えたら「高ボラ regime」、下回ったら「低ボラ regime」。
方向 param `prefer_high` (int, 0/1) で preferred regime を切替。

```python
def _m1_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, h, low, c = _bars_to_mid_ohlc(ctx.bars)
    n = _get_int_param(ctx.params, "n")
    threshold_rel = _get_float_param(ctx.params, "threshold_rel")
    scale_rel = _get_float_param(ctx.params, "scale_rel")
    prefer_high = _get_int_param(ctx.params, "prefer_high")  # 0 or 1
    a = atr(h, low, c, n)
    atr_rel = a / (c + _EPS)  # close 相対 (pair 非依存)
    direction = 1.0 if prefer_high == 1 else -1.0
    raw = direction * (atr_rel - threshold_rel) / (scale_rel + _EPS)
    out = sigmoid(raw)
    out = np.where(np.isnan(a), np.nan, out)
    return out

M1_SPEC = PrimitiveSpec(
    id="M1",
    name="ATRRegimeGate",
    category="MODULATOR",
    domain="generic",
    param_schema=(
        ParamSpec(name="n", low=7, high=28, is_int=True, default=14),
        # ATR を close 相対比率に正規化 (atr / close) して pair 非依存化
        ParamSpec(name="threshold_rel", low=0.0001, high=0.02, is_int=False, default=0.003),
        ParamSpec(name="scale_rel", low=0.00001, high=0.01, is_int=False, default=0.0015),
        ParamSpec(name="prefer_high", low=0, high=1, is_int=True, default=1),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_m1_compute_all),
    compute_all_bars=_m1_compute_all,
)
```

**設計変更（Codex review Must-fix 1 対応）**: 当初 `threshold` を raw price 単位にしていたが、
EURUSD（ATR 0.0005 - 0.005）と USDJPY（ATR 0.05 - 0.5）でスケールが 100 倍違い generic として
機能しない。**ATR を close 相対比率に正規化** (`atr / close`) して pair 非依存化する。

```python
# 修正後の _m1_compute_all（core のみ）
a = atr(h, low, c, n)
atr_rel = a / (c + _EPS)  # 相対比率 [-] 単位
direction = 1.0 if prefer_high == 1 else -1.0
raw = direction * (atr_rel - threshold_rel) / (scale_rel + _EPS)
out = sigmoid(raw)
out = np.where(np.isnan(a), np.nan, out)
```

- `threshold_rel = 0.003` は「close の 0.3% 相当の ATR」（時間足 ATR の典型値）。
- EURUSD close 1.10 で atr_rel=0.003 → ATR=0.0033、USDJPY close 150 で atr_rel=0.003 → ATR=0.45。両者整合。
- range [0.0001, 0.02] は「close の 0.01% ～ 2%」相当で pair に関係なく有効。

### 3.2 M2 SessionGate

**役割**: tokyo / london / ny のいずれかのセッション内で 1、外で 0（step）。`soft_edge_min>0`
のとき境界 ±soft_edge_min 分を sigmoid blend。

```python
def _m2_compute_all(ctx: EvaluationContext) -> np.ndarray:
    length = len(ctx.bars)
    session = _get_int_param(ctx.params, "session")
    soft_edge_min = _get_float_param(ctx.params, "soft_edge_min")
    if session not in _SESSION_RANGES_UTC:
        session = max(0, min(2, session))
    lo_h, hi_h = _SESSION_RANGES_UTC[session]
    out = np.zeros(length, dtype=np.float64)
    for i in range(length):
        b = ctx.bars[i]
        t_utc = b.bar_time.astimezone(UTC)
        # bar_time を「当日 00:00 UTC から何分」に変換
        minutes = t_utc.hour * 60.0 + t_utc.minute + t_utc.second / 60.0
        lo_min = lo_h * 60.0
        hi_min = hi_h * 60.0
        if soft_edge_min <= 0:
            out[i] = 1.0 if lo_min <= minutes < hi_min else 0.0
        else:
            # 境界 ±soft_edge_min 分で sigmoid blend
            # open edge: sigmoid((minutes - lo_min) / soft_edge_min) → session 開始後 1 に寄る
            # close edge: sigmoid((hi_min - minutes) / soft_edge_min) → session 終了前 1 に寄る
            # session 内で両方 ~1 / 境界で急減少させるため積 (AND-like) を使う
            open_gate = sigmoid((minutes - lo_min) / soft_edge_min)
            close_gate = sigmoid((hi_min - minutes) / soft_edge_min)
            out[i] = float(open_gate * close_gate)  # 積で AND blend
    return out

M2_SPEC = PrimitiveSpec(
    id="M2", name="SessionGate", category="MODULATOR", domain="generic",
    param_schema=(
        ParamSpec(name="session", low=0, high=2, is_int=True, default=0),
        ParamSpec(name="soft_edge_min", low=0.0, high=60.0, is_int=False, default=0.0),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_m2_compute_all),
    compute_all_bars=_m2_compute_all,
)
```

warmup なし（完全 deterministic）。F6 同様 UTC 日境界またぎ対策は不要（`minutes` は 0-1440 の
範囲、lo_min < hi_min は `_SESSION_RANGES_UTC` で保証）。

### 3.3 M3 SpreadConditionGate

**役割**: `spread_bps = (ask.close - bid.close) / mid * 10_000`。
`threshold_bps` 以下なら 1 に近づく。

```python
def _m3_compute_all(ctx: EvaluationContext) -> np.ndarray:
    length = len(ctx.bars)
    threshold_bps = _get_float_param(ctx.params, "threshold_bps")
    k = _get_float_param(ctx.params, "k")
    bid_c = np.array([float(b.bid.close) for b in ctx.bars], dtype=np.float64)
    ask_c = np.array([float(b.ask.close) for b in ctx.bars], dtype=np.float64)
    mid = (bid_c + ask_c) * 0.5
    # spread_bps: mid > 0 前提（_bars_to_mid_ohlc 同規約）
    with np.errstate(divide="ignore", invalid="ignore"):
        spread_bps = np.where(mid > 0, (ask_c - bid_c) / mid * 10000.0, np.nan)
    # sigmoid(-k * (spread - threshold)): spread 小で 1 に近く、大で 0
    out = sigmoid(-k * (spread_bps - threshold_bps))
    out = np.where(np.isnan(spread_bps), np.nan, out)
    return out

M3_SPEC = PrimitiveSpec(
    id="M3", name="SpreadConditionGate", category="MODULATOR", domain="generic",
    param_schema=(
        ParamSpec(name="threshold_bps", low=0.1, high=20.0, is_int=False, default=2.0),
        ParamSpec(name="k", low=0.1, high=5.0, is_int=False, default=1.0),
    ),
    required_data=("ohlc", "spread"),
    compute=_make_compute_single(_m3_compute_all),
    compute_all_bars=_m3_compute_all,
)
```

warmup なし。

**実行タイミング仕様（Should-consider 1）**: M3 は bar close 時点の spread を参照。
zenigame-fx の backtest 規約「signal at close → execute next bar open」と整合。実行される bar は
signal 生成後の **次バー**で、その時点のスプレッドとは異なる可能性があるが、MVP では close spread を
proxy として扱う。厳密な next-bar spread 参照への拡張は後続 TODO で検討。

### 3.4 M4 EconomicEventGate

**役割**: high-impact event の ±window 分を抑制。

```python
# module-level warn flag は廃止（Codex review Must-fix 3 対応）。
# warnings.warn(..., category=RuntimeWarning) を毎回呼び、pytest filter "once"
# に任せる。テストでは warnings.simplefilter("always") で強制捕捉できる。

def _m4_compute_all(ctx: EvaluationContext) -> np.ndarray:
    length = len(ctx.bars)
    window_min = _get_float_param(ctx.params, "window_min")
    scale_min = _get_float_param(ctx.params, "scale_min")
    min_impact = _get_int_param(ctx.params, "min_impact")
    if ctx.event_snapshot is None:
        if ctx.strict_snapshot_required:
            raise RuntimeError(
                "M4 EconomicEventGate: event_snapshot is None but strict_snapshot_required=True. "
                "Provide EconomicEventSnapshot or disable strict mode."
            )
        warnings.warn(
            "M4 EconomicEventGate: event_snapshot is None; returning 1.0 safe default. "
            "Production path must provide EconomicEventSnapshot (or use strict mode).",
            RuntimeWarning,
            stacklevel=2,
        )
        return np.ones(length, dtype=np.float64)

    snapshot = ctx.event_snapshot
    calendar = snapshot.calendar
    as_of = snapshot.as_of  # 実使用（Must-fix 2 対応）

    pair = ctx.pair
    try:
        base, quote = calendar.instrument_currencies(pair)
    except Exception:
        base, quote = ("", "")
    # as-of 制約: as_of 以降に登録されたイベントは本来 "bar_time 時点で未知" なので
    # 設計としては relevant_events を as_of でフィルタしたいが、calendar には
    # `known_at` column が無いため完全な enforcement は不可能（別 TODO）。
    # MVP では as_of 自体を利用して「event_time > as_of の future-published イベントは
    # calendar に含まれていない前提」と assume し、compute 内で as_of を docstring と
    # metric に露出させる（e.g., logger debug once）。
    # ただし、各 bar_time の最大参照時刻 = as_of であることを明示的に cap：
    #   relevant events は event_time ≤ as_of までに限定する。
    # これは "backtest の calendar snapshot が as_of までの既知 event だけを含む"
    # 前提を primitive 側で enforcement する 1 次防衛線。
    as_of_ts = as_of.timestamp()
    relevant_events = [
        e for e in calendar.events
        if e.impact >= min_impact
        and e.currency in (base, quote)
        and e.event_time.timestamp() <= as_of_ts
    ]
    event_times = np.array(
        [e.event_time.timestamp() for e in relevant_events], dtype=np.float64
    )
    out = np.ones(length, dtype=np.float64)
    if event_times.size == 0:
        return out
    for i in range(length):
        t = ctx.bars[i].bar_time.timestamp()
        diff_min = np.min(np.abs(event_times - t)) / 60.0
        raw = (window_min - diff_min) / (scale_min + _EPS)
        out[i] = 1.0 - float(sigmoid(raw))
    return out

M4_SPEC = PrimitiveSpec(
    id="M4", name="EconomicEventGate", category="MODULATOR", domain="generic",
    param_schema=(
        ParamSpec(name="window_min", low=5.0, high=120.0, is_int=False, default=30.0),
        ParamSpec(name="scale_min", low=1.0, high=30.0, is_int=False, default=5.0),
        ParamSpec(name="min_impact", low=1, high=3, is_int=True, default=3),
    ),
    required_data=("ohlc", "calendar.economic_event"),
    compute=_make_compute_single(_m4_compute_all),
    compute_all_bars=_m4_compute_all,
)
```

**Must-fix 2 対応 (as_of 実使用)**: `snapshot.as_of` を実際に event filter に使う。`event.event_time > as_of` のイベントは「bar_time 時点で未知」として除外する。
  - MVP 仮定: backtest では `as_of = datetime.max` 近似 (全イベント参照可能) で渡される運用を許容するが、primitive は as_of を cap として使う。
  - Live / walk-forward では walk-forward window の右端 bar_time を as_of として指定することで schedule leakage を防ぐ。

look-ahead: `EconomicEvent.actual` を参照しない。`event.event_time` のみ使う。`event_time > as_of` は cap で除外。

### 3.5 M5 VIXRegimeGate

```python
# module-level flag 廃止（Codex review Must-fix 3 対応）。

def _m5_compute_all(ctx: EvaluationContext) -> np.ndarray:
    length = len(ctx.bars)
    threshold = _get_float_param(ctx.params, "threshold")
    scale = _get_float_param(ctx.params, "scale")
    if ctx.vix_snapshot is None or not ctx.vix_snapshot.observations:
        if ctx.strict_snapshot_required:
            raise RuntimeError(
                "M5 VIXRegimeGate: vix_snapshot missing but strict_snapshot_required=True. "
                "Provide VixSeriesSnapshot or disable strict mode."
            )
        warnings.warn(
            "M5 VIXRegimeGate: vix_snapshot missing; returning 0.5 safe default. "
            "Production path must provide VixSeriesSnapshot (or use strict mode).",
            RuntimeWarning,
            stacklevel=2,
        )
        return np.full(length, 0.5, dtype=np.float64)

    # pubs 列を 1 度だけ抽出
    obs = ctx.vix_snapshot.observations
    pubs = [o[0] for o in obs]
    vals = [o[1] for o in obs]
    out = np.empty(length, dtype=np.float64)
    for i in range(length):
        bar_time = ctx.bars[i].bar_time
        # strict less than: bisect_left → index 0 なら NaN 相当（該当なし）
        k = bisect.bisect_left(pubs, bar_time)
        if k == 0:
            out[i] = 0.5  # 前に publication なし → neutral default
            continue
        vix = vals[k - 1]
        # sigmoid((threshold - vix) / scale): 低 VIX で 1、高 VIX で 0
        out[i] = float(sigmoid((threshold - vix) / (scale + _EPS)))
    return out

M5_SPEC = PrimitiveSpec(
    id="M5", name="VIXRegimeGate", category="MODULATOR", domain="generic",
    param_schema=(
        ParamSpec(name="threshold", low=10.0, high=40.0, is_int=False, default=20.0),
        ParamSpec(name="scale", low=1.0, high=15.0, is_int=False, default=5.0),
    ),
    required_data=("ohlc", "macro.vix"),
    compute=_make_compute_single(_m5_compute_all),
    compute_all_bars=_m5_compute_all,
)
```

### 3.6 M6 TrendStrengthGate

```python
def _m6_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, h, low, c = _bars_to_mid_ohlc(ctx.bars)
    n = _get_int_param(ctx.params, "n")
    theta = _get_float_param(ctx.params, "theta")
    scale = _get_float_param(ctx.params, "scale")
    adx_arr, _plus, _minus = adx(h, low, c, n)
    raw = (adx_arr - theta) / (scale + _EPS)
    out = sigmoid(raw)
    out = np.where(np.isnan(adx_arr), np.nan, out)
    return out

M6_SPEC = PrimitiveSpec(
    id="M6", name="TrendStrengthGate", category="MODULATOR", domain="generic",
    param_schema=(
        ParamSpec(name="n", low=7, high=28, is_int=True, default=14),
        ParamSpec(name="theta", low=10.0, high=40.0, is_int=False, default=25.0),
        ParamSpec(name="scale", low=2.0, high=15.0, is_int=False, default=5.0),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_m6_compute_all),
    compute_all_bars=_m6_compute_all,
)
```

## 4. ensure_registered と category_counts 更新

### 4.1 `modulator_generic.py::ensure_registered`

```python
_ALL_SPECS: tuple[PrimitiveSpec, ...] = (
    M1_SPEC, M2_SPEC, M3_SPEC, M4_SPEC, M5_SPEC, M6_SPEC,
)

def ensure_registered() -> None:
    from src.alpha_factory.primitives._registry import register_if_absent
    for spec in _ALL_SPECS:
        register_if_absent(spec)

def all_specs() -> tuple[PrimitiveSpec, ...]:
    return _ALL_SPECS
```

### 4.2 `_registry.py::ensure_registered` の更新

`directional_generic.ensure_registered()` の後に `modulator_generic.ensure_registered()` を呼ぶ:

```python
def ensure_registered() -> None:
    from src.alpha_factory.primitives.directional_generic import (
        ensure_registered as _reg_directional_generic,
    )
    from src.alpha_factory.primitives.modulator_generic import (
        ensure_registered as _reg_modulator_generic,
    )
    _reg_directional_generic()
    _reg_modulator_generic()
```

### 4.3 `directional_generic.category_counts()` の整合

`category_counts()` は directional_generic.py にあるが、これは F1-F14 だけを集計する関数で、
Registry 全体の集計ではない。整合性のため:

- `directional_generic.category_counts()` の `"MODULATOR": 0` を残す（directional 側の内訳のみ示す）
- registry 全体の count を取りたいなら `list_by_category("MODULATOR")` を使う
- 既存 F1-F14 テスト (`test_category_counts`) は `list_by_category` 経由で count しているので影響なし

**誤用防止（Should-consider 4）**: `directional_generic.category_counts()` は **モジュール固有の
内訳カウント**（F1-F14 のみ）を返し、registry 全体ではないことを docstring と `docs/alpha_factory/primitives.md` に明記。
registry 全体 count は必ず `list_by_category(category)` / `list_all()` を使うこと。

## 5. `__init__.py` の re-export

`src/alpha_factory/primitives/__init__.py` に snapshot dataclass を export:

```python
from src.alpha_factory.primitives._base import (
    ...,
    EconomicEventSnapshot,
    VixSeriesSnapshot,
)

__all__ = [
    ...,
    "EconomicEventSnapshot",
    "VixSeriesSnapshot",
]
```

## 6. テスト設計（`tests/alpha_factory/primitives/test_modulator_generic.py`）

### 6.1 Fixture

```python
@pytest.fixture(autouse=True)
def _registry_isolation():
    clear()
    ensure_registered()  # F1-F14 + M1-M6 すべて登録
    yield
    clear()

def _build_bars(...):  # test_directional_generic と同じパターン
    ...

ALL_MODULATOR_SPECS = (M1_SPEC, M2_SPEC, M3_SPEC, M4_SPEC, M5_SPEC, M6_SPEC)
```

### 6.2 Registry 集計

```python
class TestRegistryIntegration:
    def test_all_20_registered(self):
        assert len(list_all()) == 20

    def test_modulator_count_is_6(self):
        mods = list_by_category("MODULATOR")
        assert len(mods) == 6
        assert {s.id for s in mods} == {f"M{i}" for i in range(1, 7)}

    def test_each_modulator_retrievable(self):
        for i in range(1, 7):
            spec = get_primitive(f"M{i}")
            assert spec.category == "MODULATOR"
            assert spec.domain == "generic"

    def test_module_level_spec_tuple_consistent(self):
        assert all_specs() == ALL_MODULATOR_SPECS
```

### 6.3 Parametrize 共通

```python
@pytest.mark.parametrize("spec", ALL_MODULATOR_SPECS, ids=[s.id for s in ALL_MODULATOR_SPECS])
class TestModulatorCommon:
    def test_output_bounded_0_to_1(self, spec):
        bars = _build_bars(150, seed=2)
        ctx = _ctx(bars, 149, spec, event_snapshot=_mock_event_snapshot(), vix_snapshot=_mock_vix_snapshot(bars))
        arr = spec.compute_all_bars(ctx)
        valid = arr[~np.isnan(arr)]
        assert np.all(valid >= -1e-9)
        assert np.all(valid <= 1.0 + 1e-9)

    def test_compute_matches_all_bars(self, spec):
        ...

    def test_no_lookahead_property(self, spec):
        """後続 bar を改変しても先頭 k+1 の値は不変"""
        ...
```

### 6.4 個別

- `TestM1`: prefer_high=1 で ATR 大→1, 小→0 に近づく
- `TestM2`:
  - tokyo 外の UTC 10:00 以降 bar → 0
  - tokyo 内 UTC 03:00 bar → 1 (soft_edge_min=0)
  - soft_edge_min=30 で境界近辺で 0<val<1
- `TestM3`: spread_bps=1.0 (< threshold=2.0) で close to 1, spread_bps=10 で close to 0
- `TestM4`:
  - event_snapshot=None → `pytest.warns(RuntimeWarning)` + 全 1.0
  - event 付近（Δt=0）→ 0 に近づく、event 外（Δt >> window）→ 1 に近づく
  - `min_impact=3` で Medium (impact=2) event は無視
- `TestM5`:
  - vix_snapshot=None → `pytest.warns` + 全 0.5
  - low VIX (10) → close to 1, high VIX (35) → close to 0
  - **no-lookahead**: `publication_ts_utc == bar_time` の observation は strict less than で除外されることを verify
- `TestM6`: ADX 15 (< theta=25) → close to 0, ADX 35 → close to 1

### 6.5 後方互換

```python
class TestBackwardCompatibility:
    def test_existing_f_primitives_work_without_snapshots(self):
        """F1-F14 は event_snapshot/vix_snapshot なしで動くこと"""
        bars = _build_bars(100, seed=7)
        for fid in [f"F{i}" for i in range(1, 15)]:
            spec = get_primitive(fid)
            ctx = EvaluationContext(bars=bars, idx=99, pair="EUR_USD", params=_default_params(spec))
            val = spec.compute(ctx)
            assert isinstance(val, float)

    def test_f6_session_output_unchanged_after_indicator_move(self):
        """F6 の _SESSION_RANGES_UTC を _indicators.py に移動しても出力が変わらない回帰テスト。"""
        from src.alpha_factory.primitives.directional_generic import F6_SPEC
        base = datetime(2026, 1, 1, 0, tzinfo=UTC)
        bars = _build_bars(48, seed=31, base_time=base)
        ctx = _ctx(bars, 47, F6_SPEC)
        arr = F6_SPEC.compute_all_bars(ctx)
        # 計算の一貫性のみ verify（値自体の snapshot は T011 test がカバー）
        assert arr.shape == (48,)
```

### 6.6 strict mode

```python
class TestStrictMode:
    def test_m4_raises_when_strict_and_no_snapshot(self):
        bars = _build_bars(30, seed=40)
        ctx = EvaluationContext(
            bars=bars, idx=29, pair="EUR_USD",
            params=_default_params(M4_SPEC),
            strict_snapshot_required=True,
        )
        with pytest.raises(RuntimeError, match="event_snapshot is None"):
            M4_SPEC.compute_all_bars(ctx)

    def test_m5_raises_when_strict_and_no_snapshot(self):
        bars = _build_bars(30, seed=41)
        ctx = EvaluationContext(
            bars=bars, idx=29, pair="EUR_USD",
            params=_default_params(M5_SPEC),
            strict_snapshot_required=True,
        )
        with pytest.raises(RuntimeError, match="vix_snapshot missing"):
            M5_SPEC.compute_all_bars(ctx)
```

### 6.7 tz-aware 検証（Should-consider 2）

```python
class TestVixSnapshotTimezone:
    def test_lookup_raises_with_naive_datetime(self):
        """naive datetime 混入時の bisect 比較例外を fail-fast で検知。"""
        # 構築側で tz-aware を強制する（VixSeriesSnapshot.__post_init__ で検証）
        with pytest.raises(ValueError, match="tz-aware"):
            VixSeriesSnapshot(observations=(
                (datetime(2026, 1, 1, 21, 15), 20.0),  # naive
            ))
```

この検証のため `VixSeriesSnapshot.__post_init__` で observations の datetime が tz-aware か
validate する（`if obs_ts.tzinfo is None: raise ValueError(...)`）。

### 6.6 Mock factory

```python
def _mock_event_snapshot(
    events: list[EconomicEvent] | None = None,
    as_of: datetime | None = None,
) -> EconomicEventSnapshot:
    if events is None:
        events = [
            EconomicEvent(
                event_time=datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
                currency="USD", name="NFP", impact=3,
            ),
        ]
    return EconomicEventSnapshot(
        calendar=EconomicCalendar(events),
        as_of=as_of or datetime(2099, 1, 1, tzinfo=UTC),
    )

def _mock_vix_snapshot(bars: list[PriceBar], level: float = 20.0) -> VixSeriesSnapshot:
    """bars 区間をカバーする daily VIX publication を生成"""
    from datetime import timedelta
    start = bars[0].bar_time.date()
    end = bars[-1].bar_time.date()
    obs: list[tuple[datetime, float]] = []
    cur = start - timedelta(days=5)  # 前日カバー
    while cur <= end:
        pub_ts = datetime.combine(cur, datetime.min.time()).replace(
            hour=21, minute=15, tzinfo=UTC
        )
        obs.append((pub_ts, level))
        cur += timedelta(days=1)
    return VixSeriesSnapshot(observations=tuple(obs))
```

## 7. mypy / ruff 対応

- `bisect` は stdlib、型 hint `list[datetime]` OK
- `datetime` tz-aware を frozen dataclass 内で使うため、`__post_init__` での `object.__setattr__` は使わない（MVP は simple impl）
- `EconomicCalendar` の forward ref は `TYPE_CHECKING` ガードで回避
- `Mapping[str, Sequence[float]]` 既存契約は維持

## 8. docs 更新

`docs/alpha_factory/primitives.md` の **汎用 Modulator (6)** 節を T011 directional テーブルと
同じ形式で詳細化:

```markdown
### 汎用 Modulator (6)

T012 で `src/alpha_factory/primitives/modulator_generic.py` に実装・登録済。
出力は全て `[0, 1]` bounded。`category="MODULATOR"`, `domain="generic"`。

| ID | 名称 | Category | 数式 | 主要パラメータ | 外部データ |
|----|------|----------|------|----------------|-----------|
| M1 | ATRRegimeGate | MODULATOR | `sigmoid(direction * (atr_rel - threshold_rel) / scale_rel)`（`atr_rel = ATR/close` で pair 非依存） | n[7,28], threshold_rel[0.0001,0.02], scale_rel[1e-5,0.01], prefer_high∈{0,1} | なし |
| M2 | SessionGate | MODULATOR | `in_session ? 1 : 0`（`soft_edge_min>0` で境界 sigmoid blend） | session{0=tokyo,1=london,2=ny}, soft_edge_min[0,60] | なし |
| M3 | SpreadConditionGate | MODULATOR | `sigmoid(-k*(spread_bps - threshold_bps))` | threshold_bps[0.1,20], k[0.1,5] | `spread` |
| M4 | EconomicEventGate | MODULATOR | `1 - sigmoid((window_min - |Δt_min|)/scale_min)`（high-impact 絞り込み） | window_min[5,120], scale_min[1,30], min_impact{1,2,3} | `event_snapshot` |
| M5 | VIXRegimeGate | MODULATOR | `sigmoid((threshold - vix)/scale)`（publication_ts < bar_time の最新 close） | threshold[10,40], scale[1,15] | `vix_snapshot` |
| M6 | TrendStrengthGate | MODULATOR | `sigmoid((ADX(n) - theta)/scale)` | n[7,28], theta[10,40], scale[2,15] | なし |

**look-ahead 回避**: M4/M5 は snapshot 型で "as-of" 制約を表現。M5 は `publication_ts_utc < bar_time`（strict）で bisect_left lookup。M4 は `event.actual` に触れず `event_time` のみ参照。

**欠損時挙動**: M4 snapshot=None → 1.0 + `RuntimeWarning`（1 回のみ）、M5 snapshot=None → 0.5 + 同様。実装は `src/alpha_factory/primitives/modulator_generic.py`。
```

## 9. 伝搬漏れ 4 段チェック

| Stage | T012 での対応 |
|-------|--------------|
| config / loader | `src/alpha_factory/snapshots.py` helper は本 TODO では作らず、RegistryEvaluator で直接 snapshot を受け取る設計。loader 実装は `dummy registry 廃止` TODO で完結 |
| GaConfig 読み込み | 該当なし（GA param 変更なし） |
| genome.meta 注入 | 該当なし（本 TODO は primitive 追加のみ） |
| consumer 参照 | `EvaluationContext` 後方互換 default=None、primitive 側が warning + safe default |

→ 本 TODO 単独では snapshot を実 load しないが、型定義・compute path・warning 発出までは揃える。
実データ接続は後続 TODO で実装されるので、そこで 4 段が完成する。

## 10. 実装順序（Phase 1 → Phase 2）

1. `_base.py`: `EconomicEventSnapshot`, `VixSeriesSnapshot`, `EvaluationContext` 拡張
2. `_indicators.py`: `sigmoid` 追加、`_SESSION_RANGES_UTC` の再定義（既存 F6 import 差替え）
3. `directional_generic.py`: F6 の `_SESSION_RANGES_UTC` import を `_indicators.py` から差替え
4. `modulator_generic.py`: M1 / M2 / M3 / M6（外部 snapshot 不要）→ テスト → M4 / M5 → テスト
5. `_registry.py::ensure_registered`: modulator_generic を追加
6. `__init__.py`: snapshot dataclass re-export
7. `primitives.md` 更新
8. `tests/alpha_factory/primitives/test_modulator_generic.py` 全体

## 11. 想定リスクと緩和

| リスク | 緩和策 |
|-------|-------|
| M4 の O(N_bars × N_events) が大規模 bar で遅い | MVP では許容。primitive compute は GA 世代ごと反復呼ばれるのでキャッシュ検討（後続） |
| M5 lookup の O(N) pubs 抽出が遅い | compute_all_bars で 1 度抽出すれば N bars × O(log N_obs) で問題なし |
| `EconomicCalendar.instrument_currencies` で `pair` が `_` 区切りでないと失敗 | try/except で catch してイベントなし扱い |
| T011 F6 の `_SESSION_RANGES_UTC` を `_indicators.py` に移動する際の import ループ | `_indicators.py` は `_base.py` に依存しない（numpy のみ） → 循環なし |
| frozen dataclass への field 追加で既存 positional 呼出しが壊れる | EvaluationContext の既存呼出しは kwargs ベース（`EvaluationContext(bars=..., idx=..., pair=..., params=...)`）。aux_series 追加時も default だったので後方互換 OK |
