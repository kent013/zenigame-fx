"""全 FX ペア共通の MODULATOR primitive 6 個（T012）。

MODULATOR (6): M1 ATRRegimeGate, M2 SessionGate, M3 SpreadConditionGate,
               M4 EconomicEventGate, M5 VIXRegimeGate, M6 TrendStrengthGate

すべて:
- domain = "generic"
- category = "MODULATOR"
- 出力は [0, 1] bounded（warmup は np.nan）
- compute と compute_all_bars の両 API を提供
- GA slot は "local_gate"（slot_from_category("MODULATOR") = "local_gate"）

ensure_registered() を production path から 1 回呼ぶことで 6 個を registry に
登録する（T011 directional_generic と同じ規約）。

look-ahead bias 回避:
- M1 ATR / M6 ADX は Wilder smoothing で過去のみ参照
- M2 SessionGate は bar_time の hour/minute だけで決まり deterministic
- M3 SpreadConditionGate は close 時点の bid/ask スプレッドを参照
  （signal at close → execute next bar open 規約と整合、MVP では proxy）
- M4 EconomicEventGate は `event.event_time` のみ参照、`event.actual` は触れない
  さらに `event_time > as_of` のイベントは「bar_time 時点で未知」として除外
- M5 VIXRegimeGate は `publication_ts_utc < bar_time` (strict less than) で
  bisect_left lookup（同時刻 publication は除外）
- snapshot=None 時は `RuntimeWarning` + safe default、
  `strict_snapshot_required=True` 時は `RuntimeError` で fail-fast

学術引用: _indicators.py 冒頭を参照。
"""

from __future__ import annotations

import bisect
import warnings
from collections.abc import Callable
from datetime import UTC

import numpy as np

from src.alpha_factory.primitives._bars_cache import (
    bars_to_mid_ohlc as _bars_to_mid_ohlc,
)
from src.alpha_factory.primitives._base import (
    EvaluationContext,
    ParamSpec,
    PrimitiveSpec,
)
from src.alpha_factory.primitives._indicators import (
    _EPS,
    _SESSION_RANGES_UTC,
    adx,
    atr,
    sigmoid,
)

# ---------------------------------------------------------------------------
# 共通 helper（_bars_cache.py に統合済み: T030）
# ---------------------------------------------------------------------------


def _nan_to_neutral(x: float, neutral: float) -> float:
    """NaN / inf を neutral 値に吸収（compute single-point 用）。"""
    return neutral if not np.isfinite(x) else float(x)


_ComputeAllFn = Callable[[EvaluationContext], np.ndarray]


def _make_compute_single(
    compute_all: _ComputeAllFn, *, neutral: float = 0.5
) -> Callable[[EvaluationContext], float]:
    """compute_all_bars から compute(single-point) を作る。

    warmup 内 (NaN) / range 外 は MODULATOR の neutral 値 (default 0.5) を返す。
    directional_generic では neutral=0.0 だが、MODULATOR の出力域 [0,1] では
    0.5 が中立 gate (pass-through に近い扱い)。
    """

    def _compute(ctx: EvaluationContext) -> float:
        arr = compute_all(ctx)
        idx = ctx.idx
        if idx < 0 or idx >= len(arr):
            return neutral
        val = arr[idx]
        return _nan_to_neutral(float(val), neutral)

    return _compute


def _get_int_param(params, key: str) -> int:
    return int(params[key])


def _get_float_param(params, key: str) -> float:
    return float(params[key])


# ---------------------------------------------------------------------------
# M1 ATRRegimeGate (MODULATOR)
# ---------------------------------------------------------------------------


def _m1_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """ATR を close 相対比率 (atr/close) に正規化し sigmoid gate。

    pair 非依存（EURUSD: atr~0.003, USDJPY: atr~0.45 を比率 0.003 で揃える）。
    `prefer_high=1` のとき高 ATR で 1 / 低 ATR で 0、`prefer_high=0` のとき逆。
    """
    _, h, low, c = _bars_to_mid_ohlc(ctx.bars)
    n = _get_int_param(ctx.params, "n")
    threshold_rel = _get_float_param(ctx.params, "threshold_rel")
    scale_rel = _get_float_param(ctx.params, "scale_rel")
    prefer_high = _get_int_param(ctx.params, "prefer_high")  # 0 or 1
    a = atr(h, low, c, n)
    atr_rel = a / (c + _EPS)
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
        # ATR を close 相対比率 (atr / close) に正規化して pair 非依存化
        ParamSpec(
            name="threshold_rel", low=0.0001, high=0.02,
            is_int=False, default=0.003,
        ),
        ParamSpec(
            name="scale_rel", low=0.00001, high=0.01,
            is_int=False, default=0.0015,
        ),
        ParamSpec(
            name="prefer_high", low=0, high=1, is_int=True, default=1,
        ),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_m1_compute_all),
    compute_all_bars=_m1_compute_all,
)


# ---------------------------------------------------------------------------
# M2 SessionGate (MODULATOR)
# ---------------------------------------------------------------------------


def _m2_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """指定 session (tokyo/london/ny) 内で 1、外で 0 (step)。

    `soft_edge_min > 0` のとき境界 ±soft_edge_min 分を sigmoid blend
    （open/close 両 gate の積で AND-like blend）。
    warmup なし (deterministic)。
    """
    length = len(ctx.bars)
    session = _get_int_param(ctx.params, "session")
    soft_edge_min = _get_float_param(ctx.params, "soft_edge_min")
    if session not in _SESSION_RANGES_UTC:
        # defensive: clamp to nearest defined session
        session = max(0, min(2, session))
    lo_h, hi_h = _SESSION_RANGES_UTC[session]
    lo_min = lo_h * 60.0
    hi_min = hi_h * 60.0
    out = np.zeros(length, dtype=np.float64)
    for i in range(length):
        b = ctx.bars[i]
        t_utc = b.bar_time.astimezone(UTC)
        minutes = t_utc.hour * 60.0 + t_utc.minute + t_utc.second / 60.0
        if soft_edge_min <= 0:
            out[i] = 1.0 if lo_min <= minutes < hi_min else 0.0
        else:
            # 境界 ±soft_edge_min 分を sigmoid blend
            #   open_gate = sigmoid((minutes - lo_min) / soft_edge_min)
            #   close_gate = sigmoid((hi_min - minutes) / soft_edge_min)
            # 両 gate の積で AND-like blend (session 内で ~1、境界で急減少)
            open_gate = sigmoid((minutes - lo_min) / soft_edge_min)
            close_gate = sigmoid((hi_min - minutes) / soft_edge_min)
            out[i] = float(open_gate * close_gate)
    return out


M2_SPEC = PrimitiveSpec(
    id="M2",
    name="SessionGate",
    category="MODULATOR",
    domain="generic",
    param_schema=(
        # 0=Tokyo / 1=London / 2=NY
        ParamSpec(name="session", low=0, high=2, is_int=True, default=0),
        ParamSpec(
            name="soft_edge_min", low=0.0, high=60.0,
            is_int=False, default=0.0,
        ),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_m2_compute_all),
    compute_all_bars=_m2_compute_all,
)


# ---------------------------------------------------------------------------
# M3 SpreadConditionGate (MODULATOR)
# ---------------------------------------------------------------------------


def _m3_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """bar close 時点の bid/ask スプレッド (bps) が threshold 以下で 1 に近づく。

    spread_bps = (ask.close - bid.close) / mid * 10000
    out = sigmoid(-k * (spread_bps - threshold_bps))

    実行タイミング規約: zenigame-fx の backtest は signal at close →
    execute next bar open のため、本 primitive は bar close 時点のスプレッドを
    proxy として参照する（次バー約定時のスプレッドとは異なる可能性あり）。
    厳密な next-bar spread 参照は後続 TODO で検討。
    """
    length = len(ctx.bars)
    threshold_bps = _get_float_param(ctx.params, "threshold_bps")
    k = _get_float_param(ctx.params, "k")
    bid_c = np.array([float(b.bid.close) for b in ctx.bars], dtype=np.float64)
    ask_c = np.array([float(b.ask.close) for b in ctx.bars], dtype=np.float64)
    mid = (bid_c + ask_c) * 0.5
    with np.errstate(divide="ignore", invalid="ignore"):
        spread_bps = np.where(
            mid > 0, (ask_c - bid_c) / mid * 10000.0, np.nan
        )
    out = sigmoid(-k * (spread_bps - threshold_bps))
    out = np.where(np.isnan(spread_bps), np.nan, out)
    # length 0 防御（length=0 のとき sigmoid 結果も length 0 だが型を維持）
    if length == 0:
        return np.zeros(0, dtype=np.float64)
    return out


M3_SPEC = PrimitiveSpec(
    id="M3",
    name="SpreadConditionGate",
    category="MODULATOR",
    domain="generic",
    param_schema=(
        ParamSpec(
            name="threshold_bps", low=0.1, high=20.0,
            is_int=False, default=2.0,
        ),
        ParamSpec(name="k", low=0.1, high=5.0, is_int=False, default=1.0),
    ),
    required_data=("ohlc", "spread"),
    compute=_make_compute_single(_m3_compute_all),
    compute_all_bars=_m3_compute_all,
)


# ---------------------------------------------------------------------------
# M4 EconomicEventGate (MODULATOR)
# ---------------------------------------------------------------------------


def _m4_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """high-impact event の ±window 分を抑制 gate。

    formula: out = 1 - sigmoid((window_min - |Δt_min|) / scale_min)
    Δt_min = (bar_time - event_time) を分単位で取った絶対値。
    `min_impact` 以上のイベントだけ対象。

    look-ahead 回避:
        - `event.event_time > snapshot.as_of` のイベントは未知として除外
        - `event.actual` は参照しない（schedule のみ使用）

    snapshot=None:
        - `strict_snapshot_required=True` → RuntimeError
        - それ以外 → RuntimeWarning + 全 1.0 (gate 開放 = 影響なし)
    """
    length = len(ctx.bars)
    window_min = _get_float_param(ctx.params, "window_min")
    scale_min = _get_float_param(ctx.params, "scale_min")
    min_impact = _get_int_param(ctx.params, "min_impact")
    if ctx.event_snapshot is None:
        if ctx.strict_snapshot_required:
            raise RuntimeError(
                "M4 EconomicEventGate: event_snapshot is None but "
                "strict_snapshot_required=True. "
                "Provide EconomicEventSnapshot or disable strict mode."
            )
        warnings.warn(
            "M4 EconomicEventGate: event_snapshot is None; returning 1.0 "
            "safe default (gate open). Production path must provide "
            "EconomicEventSnapshot (or use strict mode).",
            RuntimeWarning,
            stacklevel=2,
        )
        return np.ones(length, dtype=np.float64)

    snapshot = ctx.event_snapshot
    calendar = snapshot.calendar
    as_of = snapshot.as_of

    pair = ctx.pair
    try:
        base, quote = calendar.instrument_currencies(pair)
    except Exception:
        base, quote = ("", "")
    as_of_ts = as_of.timestamp()
    relevant_events = [
        e for e in calendar.events
        if e.impact >= min_impact
        and e.currency in (base, quote)
        and e.event_time.timestamp() <= as_of_ts
    ]
    out = np.ones(length, dtype=np.float64)
    if not relevant_events:
        return out
    event_times = np.array(
        [e.event_time.timestamp() for e in relevant_events], dtype=np.float64
    )
    for i in range(length):
        t = ctx.bars[i].bar_time.timestamp()
        diff_min = float(np.min(np.abs(event_times - t)) / 60.0)
        raw = (window_min - diff_min) / (scale_min + _EPS)
        out[i] = 1.0 - float(sigmoid(raw))
    return out


M4_SPEC = PrimitiveSpec(
    id="M4",
    name="EconomicEventGate",
    category="MODULATOR",
    domain="generic",
    param_schema=(
        ParamSpec(
            name="window_min", low=5.0, high=120.0,
            is_int=False, default=30.0,
        ),
        ParamSpec(
            name="scale_min", low=1.0, high=30.0,
            is_int=False, default=5.0,
        ),
        ParamSpec(
            name="min_impact", low=1, high=3, is_int=True, default=3,
        ),
    ),
    required_data=("ohlc", "calendar.economic_event"),
    compute=_make_compute_single(_m4_compute_all, neutral=1.0),
    compute_all_bars=_m4_compute_all,
)


# ---------------------------------------------------------------------------
# M5 VIXRegimeGate (MODULATOR)
# ---------------------------------------------------------------------------


def _m5_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """直近の VIX 終値 (publication_ts < bar_time) を sigmoid gate に通す。

    out = sigmoid((threshold - vix) / scale)
    低 VIX (リスクオン) で 1 に近く、高 VIX (恐怖) で 0 に近づく。

    look-ahead 回避:
        - `bisect_left(pubs, bar_time)` の strict less than で同時刻 publication は除外

    snapshot None or 空:
        - `strict_snapshot_required=True` → RuntimeError
        - それ以外 → RuntimeWarning + 全 0.5 (neutral)
    """
    length = len(ctx.bars)
    threshold = _get_float_param(ctx.params, "threshold")
    scale = _get_float_param(ctx.params, "scale")
    if ctx.vix_snapshot is None or not ctx.vix_snapshot.observations:
        if ctx.strict_snapshot_required:
            raise RuntimeError(
                "M5 VIXRegimeGate: vix_snapshot missing but "
                "strict_snapshot_required=True. "
                "Provide VixSeriesSnapshot or disable strict mode."
            )
        warnings.warn(
            "M5 VIXRegimeGate: vix_snapshot missing; returning 0.5 safe "
            "default (neutral). Production path must provide "
            "VixSeriesSnapshot (or use strict mode).",
            RuntimeWarning,
            stacklevel=2,
        )
        return np.full(length, 0.5, dtype=np.float64)

    obs = ctx.vix_snapshot.observations
    pubs = [o[0] for o in obs]
    vals = [o[1] for o in obs]
    out = np.empty(length, dtype=np.float64)
    for i in range(length):
        bar_time = ctx.bars[i].bar_time
        # strict less than: bisect_left → index 0 なら該当なし
        k = bisect.bisect_left(pubs, bar_time)
        if k == 0:
            out[i] = 0.5  # 前に publication なし → neutral
            continue
        vix = vals[k - 1]
        out[i] = float(sigmoid((threshold - vix) / (scale + _EPS)))
    return out


M5_SPEC = PrimitiveSpec(
    id="M5",
    name="VIXRegimeGate",
    category="MODULATOR",
    domain="generic",
    param_schema=(
        ParamSpec(
            name="threshold", low=10.0, high=40.0,
            is_int=False, default=20.0,
        ),
        ParamSpec(name="scale", low=1.0, high=15.0, is_int=False, default=5.0),
    ),
    required_data=("ohlc", "macro.vix"),
    compute=_make_compute_single(_m5_compute_all, neutral=0.5),
    compute_all_bars=_m5_compute_all,
)


# ---------------------------------------------------------------------------
# M6 TrendStrengthGate (MODULATOR)
# ---------------------------------------------------------------------------


def _m6_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """ADX(n) を sigmoid gate に通す: 強トレンド (ADX 高) で 1、横ばいで 0。"""
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
    id="M6",
    name="TrendStrengthGate",
    category="MODULATOR",
    domain="generic",
    param_schema=(
        ParamSpec(name="n", low=7, high=28, is_int=True, default=14),
        ParamSpec(
            name="theta", low=10.0, high=40.0, is_int=False, default=25.0,
        ),
        ParamSpec(name="scale", low=2.0, high=15.0, is_int=False, default=5.0),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_m6_compute_all),
    compute_all_bars=_m6_compute_all,
)


# ---------------------------------------------------------------------------
# 登録
# ---------------------------------------------------------------------------


_ALL_SPECS: tuple[PrimitiveSpec, ...] = (
    M1_SPEC,
    M2_SPEC,
    M3_SPEC,
    M4_SPEC,
    M5_SPEC,
    M6_SPEC,
)


def ensure_registered() -> None:
    """6 modulator primitive を registry に登録する。冪等。

    並行安全性: `_registry.register_if_absent` を使い、lock 内で存在確認＋
    登録を atomic に行う（T011 directional_generic と同じ規約）。
    """
    from src.alpha_factory.primitives._registry import register_if_absent

    for spec in _ALL_SPECS:
        register_if_absent(spec)


def all_specs() -> tuple[PrimitiveSpec, ...]:
    """6 modulator PrimitiveSpec タプルを返す（テスト/インスペクション用）。"""
    return _ALL_SPECS


# ---------------------------------------------------------------------------
# Public re-export
# ---------------------------------------------------------------------------

MODULATOR_SPECS: tuple[PrimitiveSpec, ...] = _ALL_SPECS
