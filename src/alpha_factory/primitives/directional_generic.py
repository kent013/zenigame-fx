"""全 FX ペア共通の directional primitive 14 個（T011）。

TREND_FOLLOW (6): F1 TrendEMA, F2 MACDSignal, F3 DonchianBreak, F4 ADXTrend,
                  F5 VolatilityBreak, F6 SessionMomentum
MEAN_REVERT (5):  F7 RSIRevert, F8 BollingerRevert, F9 StochRevert,
                  F10 ZScoreRevert, F11 MeanReversionRange
NEUTRAL (3):      F12 RealizedVolZScore, F13 ReturnAutocorrLag, F14 TrendStrengthRatio

すべて:
- domain = "generic"
- required_data = ("ohlc",)
- 出力は [-1, +1] bounded（F14 は [0, +1]）
- compute と compute_all_bars の両 API を提供

ensure_registered() を production path から 1 回呼ぶことで 14 個を registry に登録する。

look-ahead bias:
- rolling_* は過去方向 prefix-sum/deque
- ema/atr/adx/rsi は recurrence で過去のみ参照
- F6 は session_key (UTC 日付, session_id) の変化で開始検知（週末ギャップ耐性）
- 後続バー改変で過去 index が不変であることを property test で検証

学術引用: _indicators.py 冒頭を参照。
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from datetime import UTC

import numpy as np

from src.alpha_factory.primitives._base import (
    EvaluationContext,
    ParamSpec,
    PrimitiveCategory,
    PrimitiveSpec,
)
from src.alpha_factory.primitives._indicators import (
    _EPS,
    adx,
    atr,
    bollinger,
    donchian,
    ema,
    log_returns_from_close,
    macd,
    realized_vol,
    rolling_corr,
    rolling_max,
    rolling_min,
    rolling_std,
    rsi,
    stochastic,
    zscore,
)
from src.domain.price import PriceBar

# ---------------------------------------------------------------------------
# 共通 helper
# ---------------------------------------------------------------------------


def _bars_to_mid_ohlc(
    bars,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """mid OHLC (bid/ask 平均) を float64 配列で返す。"""
    length = len(bars)
    o = np.empty(length, dtype=np.float64)
    h = np.empty(length, dtype=np.float64)
    low = np.empty(length, dtype=np.float64)
    c = np.empty(length, dtype=np.float64)
    for i, b in enumerate(bars):
        bo = float(b.bid.open)
        bh = float(b.bid.high)
        bl = float(b.bid.low)
        bc = float(b.bid.close)
        ao = float(b.ask.open)
        ah = float(b.ask.high)
        al = float(b.ask.low)
        ac = float(b.ask.close)
        o[i] = (bo + ao) * 0.5
        h[i] = (bh + ah) * 0.5
        low[i] = (bl + al) * 0.5
        c[i] = (bc + ac) * 0.5
    return o, h, low, c


def _nan_to_zero(x: float) -> float:
    return 0.0 if not np.isfinite(x) else float(x)


# compute_all_bars 関数の型（EvaluationContext → ndarray）
_ComputeAllFn = Callable[[EvaluationContext], np.ndarray]


def _make_compute_single(compute_all: _ComputeAllFn) -> Callable[[EvaluationContext], float]:
    """compute_all_bars から compute(single-point) を作る。

    warmup 内 (NaN) / range 外 は 0.0 を返す（primitive の neutral 値）。
    """

    def _compute(ctx: EvaluationContext) -> float:
        arr = compute_all(ctx)
        idx = ctx.idx
        if idx < 0 or idx >= len(arr):
            return 0.0
        val = arr[idx]
        return _nan_to_zero(float(val))

    return _compute


def _get_int_param(params, key: str) -> int:
    return int(params[key])


def _get_float_param(params, key: str) -> float:
    return float(params[key])


# ---------------------------------------------------------------------------
# F1 TrendEMA (TREND_FOLLOW)
# ---------------------------------------------------------------------------


def _f1_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, h, low, c = _bars_to_mid_ohlc(ctx.bars)
    fast_n = _get_int_param(ctx.params, "fast_n")
    slow_n = _get_int_param(ctx.params, "slow_n")
    atr_n = _get_int_param(ctx.params, "atr_n")
    ef = ema(c, fast_n)
    es = ema(c, slow_n)
    a = atr(h, low, c, atr_n)
    raw = (ef - es) / (a + _EPS)
    out = np.tanh(raw)
    # warmup を明示的に NaN にする: ef/es/a のいずれかが NaN の index
    mask = np.isnan(ef) | np.isnan(es) | np.isnan(a)
    out = np.where(mask, np.nan, out)
    return out


F1_SPEC = PrimitiveSpec(
    id="F1",
    name="TrendEMA",
    category="TREND_FOLLOW",
    domain="generic",
    param_schema=(
        ParamSpec(name="fast_n", low=5, high=30, is_int=True, default=12),
        ParamSpec(name="slow_n", low=20, high=100, is_int=True, default=26),
        ParamSpec(name="atr_n", low=7, high=28, is_int=True, default=14),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_f1_compute_all),
    compute_all_bars=_f1_compute_all,
)


# ---------------------------------------------------------------------------
# F2 MACDSignal (TREND_FOLLOW)
# ---------------------------------------------------------------------------


def _f2_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, _, _, c = _bars_to_mid_ohlc(ctx.bars)
    fast_n = _get_int_param(ctx.params, "fast_n")
    slow_n = _get_int_param(ctx.params, "slow_n")
    signal_n = _get_int_param(ctx.params, "signal_n")
    scale_n = _get_int_param(ctx.params, "scale_n")
    m, s, _ = macd(c, fast=fast_n, slow=slow_n, signal_n=signal_n)
    diff = m - s
    # rolling_std は NaN 入力で NaN を返す。diff の NaN を 0 で埋めた上で計算するのは
    # bias 要因になるため、NaN mask で保護し、warmup は NaN を返す。
    safe_diff = np.where(np.isnan(diff), 0.0, diff)
    sigma = rolling_std(safe_diff, scale_n, ddof=0)
    raw = diff / (sigma + _EPS)
    out = np.tanh(raw)
    mask = np.isnan(diff) | np.isnan(sigma)
    out = np.where(mask, np.nan, out)
    return out


F2_SPEC = PrimitiveSpec(
    id="F2",
    name="MACDSignal",
    category="TREND_FOLLOW",
    domain="generic",
    param_schema=(
        ParamSpec(name="fast_n", low=6, high=20, is_int=True, default=12),
        ParamSpec(name="slow_n", low=12, high=40, is_int=True, default=26),
        ParamSpec(name="signal_n", low=5, high=15, is_int=True, default=9),
        ParamSpec(name="scale_n", low=20, high=100, is_int=True, default=40),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_f2_compute_all),
    compute_all_bars=_f2_compute_all,
)


# ---------------------------------------------------------------------------
# F3 DonchianBreak (TREND_FOLLOW)
# ---------------------------------------------------------------------------


def _f3_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, h, low, c = _bars_to_mid_ohlc(ctx.bars)
    n = _get_int_param(ctx.params, "n")
    k = _get_float_param(ctx.params, "k")
    atr_n = _get_int_param(ctx.params, "atr_n")
    _hi, _lo, mid = donchian(h, low, n)
    a = atr(h, low, c, atr_n)
    raw = (c - mid) / (k * a + _EPS)
    out = np.tanh(raw)
    mask = np.isnan(mid) | np.isnan(a)
    out = np.where(mask, np.nan, out)
    return out


F3_SPEC = PrimitiveSpec(
    id="F3",
    name="DonchianBreak",
    category="TREND_FOLLOW",
    domain="generic",
    param_schema=(
        ParamSpec(name="n", low=10, high=60, is_int=True, default=20),
        ParamSpec(name="k", low=0.5, high=3.0, is_int=False, default=1.5),
        ParamSpec(name="atr_n", low=7, high=28, is_int=True, default=14),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_f3_compute_all),
    compute_all_bars=_f3_compute_all,
)


# ---------------------------------------------------------------------------
# F4 ADXTrend (TREND_FOLLOW)
# ---------------------------------------------------------------------------


def _f4_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, h, low, c = _bars_to_mid_ohlc(ctx.bars)
    n = _get_int_param(ctx.params, "n")
    scale = _get_float_param(ctx.params, "scale")
    adx_arr, plus_di, minus_di = adx(h, low, c, n)
    strength = np.maximum(0.0, np.tanh((adx_arr - 25.0) / (scale + _EPS)))
    direction = np.sign(plus_di - minus_di)
    out = strength * direction
    mask = np.isnan(adx_arr) | np.isnan(plus_di) | np.isnan(minus_di)
    out = np.where(mask, np.nan, out)
    return out


F4_SPEC = PrimitiveSpec(
    id="F4",
    name="ADXTrend",
    category="TREND_FOLLOW",
    domain="generic",
    param_schema=(
        ParamSpec(name="n", low=7, high=28, is_int=True, default=14),
        ParamSpec(name="scale", low=5.0, high=30.0, is_int=False, default=15.0),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_f4_compute_all),
    compute_all_bars=_f4_compute_all,
)


# ---------------------------------------------------------------------------
# F5 VolatilityBreak (TREND_FOLLOW)
# ---------------------------------------------------------------------------


def _f5_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, h, low, c = _bars_to_mid_ohlc(ctx.bars)
    short_n = _get_int_param(ctx.params, "short_n")
    long_n = _get_int_param(ctx.params, "long_n")
    k = _get_float_param(ctx.params, "k")
    if short_n >= long_n:
        warnings.warn(
            f"F5 VolatilityBreak: short_n ({short_n}) >= long_n ({long_n});"
            " computing as-is (genotype-phenotype mapping preserved).",
            RuntimeWarning,
            stacklevel=2,
        )
    a_short = atr(h, low, c, short_n)
    a_long = atr(h, low, c, long_n)
    ratio = a_short / (a_long + _EPS) - 1.0
    magnitude = np.maximum(0.0, np.tanh(k * ratio))
    ef = ema(c, short_n)
    es = ema(c, long_n)
    direction = np.sign(ef - es)
    out = magnitude * direction
    mask = (
        np.isnan(a_short) | np.isnan(a_long) | np.isnan(ef) | np.isnan(es)
    )
    out = np.where(mask, np.nan, out)
    return out


F5_SPEC = PrimitiveSpec(
    id="F5",
    name="VolatilityBreak",
    category="TREND_FOLLOW",
    domain="generic",
    param_schema=(
        ParamSpec(name="short_n", low=3, high=20, is_int=True, default=5),
        ParamSpec(name="long_n", low=30, high=120, is_int=True, default=60),
        ParamSpec(name="k", low=1.0, high=10.0, is_int=False, default=3.0),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_f5_compute_all),
    compute_all_bars=_f5_compute_all,
)


# ---------------------------------------------------------------------------
# F6 SessionMomentum (TREND_FOLLOW)
# ---------------------------------------------------------------------------


# UTC 静的境界 (DST 無視)
_SESSION_RANGES_UTC: dict[int, tuple[int, int]] = {
    0: (0, 9),   # Tokyo
    1: (7, 16),  # London
    2: (12, 21), # NY
}


def _f6_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, h, low, c = _bars_to_mid_ohlc(ctx.bars)
    session = _get_int_param(ctx.params, "session")
    if session not in _SESSION_RANGES_UTC:
        # defensive: clamp to nearest defined session
        session = max(0, min(2, session))
    lo_h, hi_h = _SESSION_RANGES_UTC[session]
    k = _get_float_param(ctx.params, "k")
    atr_n = _get_int_param(ctx.params, "atr_n")
    a = atr(h, low, c, atr_n)

    length = len(ctx.bars)
    out = np.zeros(length, dtype=np.float64)  # session 外は 0 を default
    session_open_close = np.nan
    prev_session_key: tuple[int, int] | None = None
    for i in range(length):
        b: PriceBar = ctx.bars[i]
        t_utc = b.bar_time.astimezone(UTC)
        hour = t_utc.hour
        in_session = lo_h <= hour < hi_h
        if in_session:
            cur_key = (t_utc.toordinal(), session)
            if cur_key != prev_session_key:
                # セッション境界: 開始 bar
                session_open_close = c[i]
                prev_session_key = cur_key
                out[i] = 0.0
            else:
                if np.isfinite(session_open_close) and np.isfinite(a[i]):
                    raw = (c[i] - session_open_close) / (k * a[i] + _EPS)
                    out[i] = np.tanh(raw)
                else:
                    # ATR warmup 不足 → NaN (session 内だが計算不能)
                    out[i] = np.nan
        else:
            # session 外: key リセットして 0
            prev_session_key = None
            out[i] = 0.0
    return out


F6_SPEC = PrimitiveSpec(
    id="F6",
    name="SessionMomentum",
    category="TREND_FOLLOW",
    domain="generic",
    param_schema=(
        ParamSpec(name="session", low=0, high=2, is_int=True, default=0),
        ParamSpec(name="k", low=0.5, high=3.0, is_int=False, default=1.0),
        ParamSpec(name="atr_n", low=7, high=28, is_int=True, default=14),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_f6_compute_all),
    compute_all_bars=_f6_compute_all,
)


# ---------------------------------------------------------------------------
# F7 RSIRevert (MEAN_REVERT)
# ---------------------------------------------------------------------------


def _f7_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, _, _, c = _bars_to_mid_ohlc(ctx.bars)
    n = _get_int_param(ctx.params, "n")
    scale = _get_float_param(ctx.params, "scale")
    r = rsi(c, n)
    raw = (50.0 - r) / (scale + _EPS)
    out = np.tanh(raw)
    out = np.where(np.isnan(r), np.nan, out)
    return out


F7_SPEC = PrimitiveSpec(
    id="F7",
    name="RSIRevert",
    category="MEAN_REVERT",
    domain="generic",
    param_schema=(
        ParamSpec(name="n", low=7, high=28, is_int=True, default=14),
        ParamSpec(name="scale", low=5.0, high=30.0, is_int=False, default=15.0),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_f7_compute_all),
    compute_all_bars=_f7_compute_all,
)


# ---------------------------------------------------------------------------
# F8 BollingerRevert (MEAN_REVERT)
# ---------------------------------------------------------------------------


def _f8_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, _, _, c = _bars_to_mid_ohlc(ctx.bars)
    n = _get_int_param(ctx.params, "n")
    k = _get_float_param(ctx.params, "k")
    mid, std, _, _ = bollinger(c, n, k)
    raw = (mid - c) / (k * std + _EPS)
    out = np.tanh(raw)
    mask = np.isnan(mid) | np.isnan(std)
    out = np.where(mask, np.nan, out)
    return out


F8_SPEC = PrimitiveSpec(
    id="F8",
    name="BollingerRevert",
    category="MEAN_REVERT",
    domain="generic",
    param_schema=(
        ParamSpec(name="n", low=10, high=60, is_int=True, default=20),
        ParamSpec(name="k", low=1.0, high=3.0, is_int=False, default=2.0),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_f8_compute_all),
    compute_all_bars=_f8_compute_all,
)


# ---------------------------------------------------------------------------
# F9 StochRevert (MEAN_REVERT)
# ---------------------------------------------------------------------------


def _f9_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, h, low, c = _bars_to_mid_ohlc(ctx.bars)
    n = _get_int_param(ctx.params, "n")
    scale = _get_float_param(ctx.params, "scale")
    k_arr, _ = stochastic(h, low, c, n)
    raw = (50.0 - k_arr) / (scale + _EPS)
    out = np.tanh(raw)
    out = np.where(np.isnan(k_arr), np.nan, out)
    return out


F9_SPEC = PrimitiveSpec(
    id="F9",
    name="StochRevert",
    category="MEAN_REVERT",
    domain="generic",
    param_schema=(
        ParamSpec(name="n", low=7, high=28, is_int=True, default=14),
        ParamSpec(name="scale", low=10.0, high=40.0, is_int=False, default=20.0),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_f9_compute_all),
    compute_all_bars=_f9_compute_all,
)


# ---------------------------------------------------------------------------
# F10 ZScoreRevert (MEAN_REVERT)
# ---------------------------------------------------------------------------


def _f10_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, _, _, c = _bars_to_mid_ohlc(ctx.bars)
    n = _get_int_param(ctx.params, "n")
    z = zscore(c, n)
    out = np.tanh(-z)
    out = np.where(np.isnan(z), np.nan, out)
    return out


F10_SPEC = PrimitiveSpec(
    id="F10",
    name="ZScoreRevert",
    category="MEAN_REVERT",
    domain="generic",
    param_schema=(
        ParamSpec(name="n", low=10, high=60, is_int=True, default=20),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_f10_compute_all),
    compute_all_bars=_f10_compute_all,
)


# ---------------------------------------------------------------------------
# F11 MeanReversionRange (MEAN_REVERT)
# ---------------------------------------------------------------------------


def _f11_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, h, low, c = _bars_to_mid_ohlc(ctx.bars)
    n = _get_int_param(ctx.params, "n")
    hi = rolling_max(h, n)
    lo = rolling_min(low, n)
    mid = (hi + lo) / 2.0
    width = (hi - lo) / 2.0 + _EPS
    raw = -(c - mid) / width
    out = np.tanh(raw)
    mask = np.isnan(hi) | np.isnan(lo)
    out = np.where(mask, np.nan, out)
    return out


F11_SPEC = PrimitiveSpec(
    id="F11",
    name="MeanReversionRange",
    category="MEAN_REVERT",
    domain="generic",
    param_schema=(
        ParamSpec(name="n", low=10, high=60, is_int=True, default=20),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_f11_compute_all),
    compute_all_bars=_f11_compute_all,
)


# ---------------------------------------------------------------------------
# F12 RealizedVolZScore (NEUTRAL)
# ---------------------------------------------------------------------------


def _f12_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, _, _, c = _bars_to_mid_ohlc(ctx.bars)
    n = _get_int_param(ctx.params, "n")
    window = _get_int_param(ctx.params, "window")
    k_scale = _get_float_param(ctx.params, "k_scale")
    # defensive: ensure window > n+1 で zscore が計算可能
    effective_window = max(window, n + 1)
    r = log_returns_from_close(c)
    rv = realized_vol(r, n)
    z = zscore(rv, effective_window)
    out = np.tanh(z / (k_scale + _EPS))
    out = np.where(np.isnan(z), np.nan, out)
    return out


F12_SPEC = PrimitiveSpec(
    id="F12",
    name="RealizedVolZScore",
    category="NEUTRAL",
    domain="generic",
    param_schema=(
        ParamSpec(name="n", low=10, high=60, is_int=True, default=20),
        ParamSpec(name="window", low=60, high=500, is_int=True, default=200),
        ParamSpec(name="k_scale", low=1.5, high=4.0, is_int=False, default=2.5),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_f12_compute_all),
    compute_all_bars=_f12_compute_all,
)


# ---------------------------------------------------------------------------
# F13 ReturnAutocorrLag (NEUTRAL)
# ---------------------------------------------------------------------------


def _f13_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, _, _, c = _bars_to_mid_ohlc(ctx.bars)
    w = _get_int_param(ctx.params, "w")
    lag = _get_int_param(ctx.params, "lag")
    r = log_returns_from_close(c)  # r[0] = NaN
    length = len(r)
    y = np.full(length, np.nan, dtype=np.float64)
    if lag < length:
        y[lag:] = r[:-lag] if lag > 0 else r
    # lag=0 は定数 1 (自分自身) → degenerate。param_schema で lag >= 1 を担保。
    r_safe = np.where(np.isfinite(r), r, 0.0)
    y_safe = np.where(np.isfinite(y), y, 0.0)
    corr = rolling_corr(r_safe, y_safe, w)
    # warmup: 最初の lag+w index は相関の有効範囲ではない
    # rolling_corr は [w-1..] で有効、ただし y は [lag..] で初めて値が入る
    # → 有効開始 index = max(w-1, lag+w-1) = lag+w-1
    invalid_upper = min(length, lag + w - 1)
    corr[:invalid_upper] = np.nan
    # rolling_corr は [-1, +1] が定義域。tanh 不要。
    return corr


F13_SPEC = PrimitiveSpec(
    id="F13",
    name="ReturnAutocorrLag",
    category="NEUTRAL",
    domain="generic",
    param_schema=(
        ParamSpec(name="w", low=20, high=200, is_int=True, default=60),
        ParamSpec(name="lag", low=1, high=10, is_int=True, default=1),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_f13_compute_all),
    compute_all_bars=_f13_compute_all,
)


# ---------------------------------------------------------------------------
# F14 TrendStrengthRatio (NEUTRAL)
# ---------------------------------------------------------------------------


def _f14_compute_all(ctx: EvaluationContext) -> np.ndarray:
    _, _, _, c = _bars_to_mid_ohlc(ctx.bars)
    fast_n = _get_int_param(ctx.params, "fast_n")
    slow_n = _get_int_param(ctx.params, "slow_n")
    rv_n = _get_int_param(ctx.params, "rv_n")
    scale = _get_float_param(ctx.params, "scale")
    k_scale = _get_float_param(ctx.params, "k_scale")
    ef = ema(c, fast_n)
    es = ema(c, slow_n)
    r = log_returns_from_close(c)
    rv = realized_vol(r, rv_n)
    # rv (無次元, log 単位) × c で価格スケールに整合させる
    denom = rv * scale * (c + _EPS) + _EPS
    ratio = np.abs(ef - es) / denom
    out = np.tanh(ratio / (k_scale + _EPS))
    mask = np.isnan(ef) | np.isnan(es) | np.isnan(rv)
    out = np.where(mask, np.nan, out)
    return out


F14_SPEC = PrimitiveSpec(
    id="F14",
    name="TrendStrengthRatio",
    category="NEUTRAL",
    domain="generic",
    param_schema=(
        ParamSpec(name="fast_n", low=5, high=30, is_int=True, default=12),
        ParamSpec(name="slow_n", low=20, high=100, is_int=True, default=26),
        ParamSpec(name="rv_n", low=10, high=60, is_int=True, default=20),
        ParamSpec(name="scale", low=0.5, high=5.0, is_int=False, default=1.0),
        ParamSpec(name="k_scale", low=1.0, high=5.0, is_int=False, default=2.0),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_f14_compute_all),
    compute_all_bars=_f14_compute_all,
)


# ---------------------------------------------------------------------------
# 登録
# ---------------------------------------------------------------------------


_ALL_SPECS: tuple[PrimitiveSpec, ...] = (
    F1_SPEC,
    F2_SPEC,
    F3_SPEC,
    F4_SPEC,
    F5_SPEC,
    F6_SPEC,
    F7_SPEC,
    F8_SPEC,
    F9_SPEC,
    F10_SPEC,
    F11_SPEC,
    F12_SPEC,
    F13_SPEC,
    F14_SPEC,
)


def ensure_registered() -> None:
    """14 primitive を registry に登録する。冪等（既登録はスキップ）。

    並行安全性: `_registry.register_if_absent` を使い、lock 内で存在確認＋登録を
    atomic に行う。
    """
    from src.alpha_factory.primitives._registry import register_if_absent

    for spec in _ALL_SPECS:
        register_if_absent(spec)


def all_specs() -> tuple[PrimitiveSpec, ...]:
    """14 primitive の PrimitiveSpec タプルを返す（テスト/インスペクション用）。"""
    return _ALL_SPECS


# ---------------------------------------------------------------------------
# Public re-export（category 別）
# ---------------------------------------------------------------------------

TREND_FOLLOW_SPECS: tuple[PrimitiveSpec, ...] = (
    F1_SPEC,
    F2_SPEC,
    F3_SPEC,
    F4_SPEC,
    F5_SPEC,
    F6_SPEC,
)
MEAN_REVERT_SPECS: tuple[PrimitiveSpec, ...] = (
    F7_SPEC,
    F8_SPEC,
    F9_SPEC,
    F10_SPEC,
    F11_SPEC,
)
NEUTRAL_SPECS: tuple[PrimitiveSpec, ...] = (F12_SPEC, F13_SPEC, F14_SPEC)


def category_counts() -> dict[PrimitiveCategory, int]:
    return {
        "TREND_FOLLOW": len(TREND_FOLLOW_SPECS),
        "MEAN_REVERT": len(MEAN_REVERT_SPECS),
        "NEUTRAL": len(NEUTRAL_SPECS),
        "MODULATOR": 0,
    }
