"""通貨ペア特化 directional/MODULATOR primitive 12 個（T013, P1-P12）。

すべて domain="pair_specific"。設計起点ペアあるが他ペアでも crash しない。

EUR_USD 起点: P1 LondonNYOverlapMomentum / P2 IntradayRangeFade
USD_JPY 起点: P3 TokyoOpenReversal / P4 YenFixingBias
EUR_JPY 起点: P5 CrossPairTriangulation / P6 EuroHourVolRegime
AUD_JPY 起点: P7 RiskOnOffProxy / P8 CommodityFlowBias
USD_CAD 起点: P9 OilPriceInverseFlow / P10 NADataProximityGate
USD_ZAR 起点: P11 EmergingMarketStressGate / P12 GoldCorrelationBias

look-ahead bias 回避:
- 全 primitive は bar_time UTC 固定の時刻枠 + 過去 bar / 過去 publication のみ参照
- aux_pair_bars は bar_time strict 一致 (misalign は ValueError fail-fast)
- VIX は publication_ts < bar_time の bisect_left lookup (M5 と同方針)
- aux_series の stale は `_stale_mask` で前 finite 値からの距離が staleness_bars 超で NaN

snapshot/aux 欠損時:
- strict_snapshot_required=True → RuntimeError fail-fast
- それ以外 → RuntimeWarning + safe default (directional=0.0, MODULATOR は P10=1.0,
  P6/P11=0.5)

学術引用:
- Goyenko, R. & Marshall, B. R. (2024) "FX Liquidity at the Tokyo Fix" (要確認) —
  Tokyo 9:55 JST fixing flow に AR 効果が報告される
- Cenedese, G. et al. (2014) "Foreign Exchange Risk and the Cross-Section of Stock
  Returns" — risk-on/off プロキシとしての VIX/SPX
"""

from __future__ import annotations

import bisect
import warnings
from collections.abc import Callable, Mapping, Sequence
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
    atr,
    sigmoid,
    zscore,
)
from src.domain.price import PriceBar

# ---------------------------------------------------------------------------
# 共通ヘルパー（_bars_to_mid_ohlc は _bars_cache.py に統合済み: T030）
# ---------------------------------------------------------------------------


def _bars_to_mid_close(bars: Sequence[PriceBar]) -> np.ndarray:
    """mid close 配列のみが欲しいケース用 short-cut。"""
    n = len(bars)
    out = np.empty(n, dtype=np.float64)
    for i, b in enumerate(bars):
        out[i] = (float(b.bid.close) + float(b.ask.close)) * 0.5
    return out


def _bar_time_minutes_utc(b: PriceBar) -> float:
    """UTC 換算 hour*60 + minute + second/60 (分単位、float)。"""
    t = b.bar_time.astimezone(UTC)
    return t.hour * 60.0 + t.minute + t.second / 60.0


def _aligned_pair_close(
    target_bars: Sequence[PriceBar],
    aux_bars: Sequence[PriceBar | None],
) -> np.ndarray:
    """aux_bars[i] が None なら NaN、そうでなければ mid close を返す。

    bar_time strict 一致 / 長さ一致を assert（misalignment は ValueError fail-fast）。

    Args:
        target_bars: 比較先の bars（時刻軸の基準）
        aux_bars: aligned 別ペア bar 列（None 要素は stale 扱い → NaN）

    Returns:
        len(target_bars) の float64 配列。stale (None) は NaN。

    Raises:
        ValueError: 長さ不一致 / bar_time 不一致 (data integrity bug)
    """
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
    compute_all: _ComputeAllFn, *, neutral: float = 0.0
) -> Callable[[EvaluationContext], float]:
    """compute_all_bars から compute(single-point) を作る。

    warmup 内 (NaN) / range 外は neutral 値を返す。
    directional は 0.0、MODULATOR は P10=1.0 / P6/P11=0.5。
    """

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


def _check_aux_series_length(
    primitive_id: str,
    series_key: str,
    series: Sequence[float] | None,
    expected_len: int,
) -> None:
    """aux_series が provide されているなら長さ一致を strict assert。

    MISALIGNMENT 状態 (長さ不一致) は ValueError fail-fast。
    series が None の場合は何もしない (caller が MISSING_KEY 判定)。

    Codex impl-review 1-1 反映: aux_series 長さ不一致を MISSING_KEY ではなく
    MISALIGNMENT (ValueError) として正しく扱う。
    """
    if series is None:
        return
    if len(series) != expected_len:
        raise ValueError(
            f"{primitive_id}: aux_series[{series_key!r}] length "
            f"{len(series)} != bars length {expected_len} (MISALIGNMENT)"
        )


def _stale_mask(series: np.ndarray, staleness_bars: int) -> np.ndarray:
    """直前 finite 値からの距離が staleness_bars を超える index を True にする mask。

    series 自体の NaN は最初から stale 扱い（最後の finite から距離がリセットされる）。
    短い欠損 (<= staleness_bars) は finite forward-fill されている前提で許容（False）。
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
                mask[i] = False  # 短い欠損は許容
    return mask


# ---------------------------------------------------------------------------
# P1 LondonNYOverlapMomentum (TREND_FOLLOW, EUR_USD)
# ---------------------------------------------------------------------------


def _p1_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """ロンドン-NY オーバーラップ (13:00-17:00 UTC) 内 bar に対し過去 n バー return の
    符号付き正規化値を返す。範囲外は 0、warmup は NaN。
    """
    n = _get_int_param(ctx.params, "n")
    scale = _get_float_param(ctx.params, "scale")
    overlap_lo = 13 * 60.0
    overlap_hi = 17 * 60.0
    c = _bars_to_mid_close(ctx.bars)
    length = len(ctx.bars)
    out = np.zeros(length, dtype=np.float64)
    for i in range(length):
        m = _bar_time_minutes_utc(ctx.bars[i])
        if not (overlap_lo <= m < overlap_hi):
            out[i] = 0.0
            continue
        if i < n:
            out[i] = np.nan
            continue
        ret = (c[i] - c[i - n]) / (c[i - n] + _EPS)
        out[i] = float(np.tanh(ret / (scale + _EPS)))
    return out


P1_SPEC = PrimitiveSpec(
    id="P1",
    name="LondonNYOverlapMomentum",
    category="TREND_FOLLOW",
    domain="pair_specific",
    param_schema=(
        ParamSpec(name="n", low=2, high=24, is_int=True, default=6),
        ParamSpec(name="scale", low=0.0001, high=0.02, is_int=False, default=0.002),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_p1_compute_all),
    compute_all_bars=_p1_compute_all,
)


# ---------------------------------------------------------------------------
# P2 IntradayRangeFade (MEAN_REVERT, EUR_USD)
# ---------------------------------------------------------------------------


def _p2_compute_all(ctx: EvaluationContext) -> np.ndarray:
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
        if (
            not (ny_lo <= m < ny_hi)
            or not range_locked
            or not np.isfinite(a[i])
        ):
            out[i] = 0.0
            continue
        if cur_high <= cur_low:
            out[i] = 0.0
            continue
        atr_i = a[i] + _EPS
        if c[i] > cur_high:
            out[i] = -float(np.tanh((c[i] - cur_high) / atr_i))
        elif c[i] < cur_low:
            out[i] = float(np.tanh((cur_low - c[i]) / atr_i))
        else:
            out[i] = 0.0
    return out


P2_SPEC = PrimitiveSpec(
    id="P2",
    name="IntradayRangeFade",
    category="MEAN_REVERT",
    domain="pair_specific",
    param_schema=(
        ParamSpec(name="atr_n", low=7, high=28, is_int=True, default=14),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_p2_compute_all),
    compute_all_bars=_p2_compute_all,
)


# ---------------------------------------------------------------------------
# P3 TokyoOpenReversal (MEAN_REVERT, USD_JPY)
# ---------------------------------------------------------------------------


def _p3_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """東京オープン直後 (00:00-02:00 UTC) bar に対し過去 n バー return の符号反転を返す。
    範囲外は 0、warmup は NaN。
    """
    open_lo = 0 * 60.0
    open_hi = 2 * 60.0
    n = _get_int_param(ctx.params, "n")
    scale = _get_float_param(ctx.params, "scale")
    c = _bars_to_mid_close(ctx.bars)
    length = len(ctx.bars)
    out = np.zeros(length, dtype=np.float64)
    for i in range(length):
        m = _bar_time_minutes_utc(ctx.bars[i])
        if not (open_lo <= m < open_hi):
            out[i] = 0.0
            continue
        if i < n:
            out[i] = np.nan
            continue
        ret = (c[i] - c[i - n]) / (c[i - n] + _EPS)
        out[i] = -float(np.tanh(ret / (scale + _EPS)))
    return out


P3_SPEC = PrimitiveSpec(
    id="P3",
    name="TokyoOpenReversal",
    category="MEAN_REVERT",
    domain="pair_specific",
    param_schema=(
        ParamSpec(name="n", low=1, high=12, is_int=True, default=3),
        ParamSpec(name="scale", low=0.0001, high=0.02, is_int=False, default=0.002),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_p3_compute_all),
    compute_all_bars=_p3_compute_all,
)


# ---------------------------------------------------------------------------
# P4 YenFixingBias (TREND_FOLLOW, USD_JPY)
# ---------------------------------------------------------------------------


def _p4_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """仲値 (UTC 00:55) 前後 ±window_min 内で bias 符号付き signal を返す。
    仲値前 (delta < 0) → +1 寄り、仲値後 → -1 寄り。
    window 外は 0。bar_time のみ参照、deterministic。
    """
    fixing_min = 0 * 60.0 + 55.0
    window_min = _get_float_param(ctx.params, "window_min")
    scale_min = _get_float_param(ctx.params, "scale_min")
    n = len(ctx.bars)
    out = np.zeros(n, dtype=np.float64)
    for i in range(n):
        m = _bar_time_minutes_utc(ctx.bars[i])
        delta = m - fixing_min
        if abs(delta) > window_min:
            out[i] = 0.0
            continue
        sign = 1.0 if delta <= 0 else -1.0
        # |Δt| 小で magnitude 大 (1 寄り)、大で 0.5 寄り
        magnitude = 2.0 * float(sigmoid(-abs(delta) / (scale_min + _EPS)))
        out[i] = float(np.tanh(sign * magnitude))
    return out


P4_SPEC = PrimitiveSpec(
    id="P4",
    name="YenFixingBias",
    category="TREND_FOLLOW",
    domain="pair_specific",
    param_schema=(
        ParamSpec(name="window_min", low=5.0, high=120.0, is_int=False, default=30.0),
        ParamSpec(name="scale_min", low=1.0, high=30.0, is_int=False, default=10.0),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_p4_compute_all),
    compute_all_bars=_p4_compute_all,
)


# ---------------------------------------------------------------------------
# P5 CrossPairTriangulation (MEAN_REVERT, EUR_JPY)
# ---------------------------------------------------------------------------


def _p5_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """target = EUR_JPY、aux = EUR_USD * USD_JPY の合成 mid との残差を z-score 化し、
    符号反転で mean-revert signal (`-tanh(z / scale)`) を返す。

    aux_pair_bars["EUR_USD"] / aux_pair_bars["USD_JPY"] が両方そろっているとき動作。
    片方でも MISSING_KEY なら warning + safe default 0.0 全 bar 返却。
    misalign は ValueError fail-fast。
    """
    n = len(ctx.bars)
    eu = ctx.aux_pair_bars.get("EUR_USD")
    uj = ctx.aux_pair_bars.get("USD_JPY")
    if eu is None or uj is None:
        if ctx.strict_snapshot_required:
            raise RuntimeError(
                "P5: aux_pair_bars EUR_USD/USD_JPY missing but strict mode"
            )
        _warn_missing("P5", "aux_pair_bars EUR_USD/USD_JPY")
        return np.zeros(n, dtype=np.float64)
    eu_close = _aligned_pair_close(ctx.bars, eu)
    uj_close = _aligned_pair_close(ctx.bars, uj)
    target_close = _bars_to_mid_close(ctx.bars)
    synth = eu_close * uj_close
    residual = target_close - synth
    z_n = _get_int_param(ctx.params, "z_n")
    z = zscore(residual, z_n)
    scale = _get_float_param(ctx.params, "scale")
    out = -np.tanh(z / (scale + _EPS))
    out = np.where(np.isnan(z), np.nan, out)
    return out


P5_SPEC = PrimitiveSpec(
    id="P5",
    name="CrossPairTriangulation",
    category="MEAN_REVERT",
    domain="pair_specific",
    param_schema=(
        ParamSpec(name="z_n", low=20, high=200, is_int=True, default=60),
        ParamSpec(name="scale", low=0.5, high=5.0, is_int=False, default=2.0),
    ),
    required_data=("ohlc", "cross_pair.EUR_USD", "cross_pair.USD_JPY"),
    compute=_make_compute_single(_p5_compute_all),
    compute_all_bars=_p5_compute_all,
)


# ---------------------------------------------------------------------------
# P6 EuroHourVolRegime (MODULATOR, EUR_JPY)
# ---------------------------------------------------------------------------


def _p6_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """欧州時間 (07:00-15:00 UTC) かつ ATR_rel 高で 1 寄り gate。範囲外は 0。"""
    eu_lo, eu_hi = 7 * 60.0, 15 * 60.0
    n_atr = _get_int_param(ctx.params, "atr_n")
    threshold_rel = _get_float_param(ctx.params, "threshold_rel")
    scale_rel = _get_float_param(ctx.params, "scale_rel")
    _, h, low, c = _bars_to_mid_ohlc(ctx.bars)
    a = atr(h, low, c, n_atr)
    atr_rel = a / (c + _EPS)
    n = len(ctx.bars)
    out = np.zeros(n, dtype=np.float64)
    for i in range(n):
        m = _bar_time_minutes_utc(ctx.bars[i])
        if not (eu_lo <= m < eu_hi):
            out[i] = 0.0
            continue
        if not np.isfinite(atr_rel[i]):
            out[i] = np.nan
            continue
        out[i] = float(
            sigmoid((atr_rel[i] - threshold_rel) / (scale_rel + _EPS))
        )
    return out


P6_SPEC = PrimitiveSpec(
    id="P6",
    name="EuroHourVolRegime",
    category="MODULATOR",
    domain="pair_specific",
    param_schema=(
        ParamSpec(name="atr_n", low=7, high=28, is_int=True, default=14),
        ParamSpec(
            name="threshold_rel", low=0.0001, high=0.02,
            is_int=False, default=0.003,
        ),
        ParamSpec(
            name="scale_rel", low=0.00001, high=0.01,
            is_int=False, default=0.0015,
        ),
    ),
    required_data=("ohlc",),
    compute=_make_compute_single(_p6_compute_all, neutral=0.5),
    compute_all_bars=_p6_compute_all,
)


# ---------------------------------------------------------------------------
# P7 RiskOnOffProxy (TREND_FOLLOW, AUD_JPY)
# ---------------------------------------------------------------------------


def _p7_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """VIX 低 (リスクオン) かつ SPX 上昇モメンタム → +、その逆で -。

    依存:
      - vix_snapshot (publication-based, M5 と同方針)
      - aux_series["macro.spx500"] (bar-aligned)
    どちらか欠損 → warning + 0.0 全 bar。stale 判定で個別 bar NaN。
    """
    n = len(ctx.bars)
    vix_snap = ctx.vix_snapshot
    spx = ctx.aux_series.get("macro.spx500")
    # MISALIGNMENT: 長さ不一致は strict 関係なく ValueError
    _check_aux_series_length("P7", "macro.spx500", spx, n)
    has_vix = vix_snap is not None and vix_snap.observations
    has_spx = spx is not None
    if not has_vix or not has_spx:
        if ctx.strict_snapshot_required:
            raise RuntimeError(
                "P7: vix_snapshot or aux_series['macro.spx500'] missing but strict mode"
            )
        _warn_missing("P7", "vix_snapshot or macro.spx500")
        return np.zeros(n, dtype=np.float64)
    assert vix_snap is not None  # for mypy
    spx_arr = np.asarray(spx, dtype=np.float64)
    spx_n = _get_int_param(ctx.params, "spx_n")
    spx_mom = np.full(n, np.nan, dtype=np.float64)
    if n > spx_n:
        spx_mom[spx_n:] = (spx_arr[spx_n:] - spx_arr[:-spx_n]) / (
            np.abs(spx_arr[:-spx_n]) + _EPS
        )
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
        # vix_score: 低 VIX → > 0、高 VIX → < 0
        vix_score = float(
            sigmoid((vix_threshold - vix) / (vix_scale + _EPS))
        ) - 0.5
        spx_score = float(np.tanh(spx_mom[i] / 0.01))
        out[i] = float(np.tanh(vix_score * 2.0 + spx_score))
    return out


P7_SPEC = PrimitiveSpec(
    id="P7",
    name="RiskOnOffProxy",
    category="TREND_FOLLOW",
    domain="pair_specific",
    param_schema=(
        ParamSpec(name="spx_n", low=2, high=48, is_int=True, default=12),
        ParamSpec(
            name="vix_threshold", low=10.0, high=40.0,
            is_int=False, default=20.0,
        ),
        ParamSpec(name="vix_scale", low=1.0, high=15.0, is_int=False, default=5.0),
        ParamSpec(
            name="vix_staleness_days", low=1.0, high=30.0,
            is_int=False, default=7.0,
        ),
        ParamSpec(
            name="spx_staleness_bars", low=1, high=500,
            is_int=True, default=120,
        ),
    ),
    required_data=("ohlc", "macro.vix", "macro.spx500"),
    compute=_make_compute_single(_p7_compute_all),
    compute_all_bars=_p7_compute_all,
)


# ---------------------------------------------------------------------------
# P8 CommodityFlowBias (TREND_FOLLOW, AUD_JPY)
# ---------------------------------------------------------------------------


def _p8_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """銅 (1 次優先) または商品 index (fallback) momentum 上昇 → AUD-buy bias = +。
    両方欠損 → warning + 0.0 全 bar。
    """
    n = len(ctx.bars)
    copper = ctx.aux_series.get("macro.copper")
    commodity = ctx.aux_series.get("macro.commodity_index")
    # MISALIGNMENT 検査: 提供されているなら長さ一致を strict assert
    _check_aux_series_length("P8", "macro.copper", copper, n)
    _check_aux_series_length("P8", "macro.commodity_index", commodity, n)
    series: Sequence[float] | None = copper if copper is not None else commodity
    if series is None:
        if ctx.strict_snapshot_required:
            raise RuntimeError(
                "P8: macro.copper and macro.commodity_index both missing "
                "but strict mode"
            )
        _warn_missing("P8", "macro.copper or macro.commodity_index")
        return np.zeros(n, dtype=np.float64)
    arr = np.asarray(series, dtype=np.float64)
    mom_n = _get_int_param(ctx.params, "mom_n")
    staleness_bars = _get_int_param(ctx.params, "staleness_bars")
    stale = _stale_mask(arr, staleness_bars)
    mom = np.full(n, np.nan, dtype=np.float64)
    if n > mom_n:
        mom[mom_n:] = (arr[mom_n:] - arr[:-mom_n]) / (
            np.abs(arr[:-mom_n]) + _EPS
        )
    scale = _get_float_param(ctx.params, "scale")
    out = np.where(
        stale | ~np.isfinite(mom),
        np.nan,
        np.tanh(mom / (scale + _EPS)),
    )
    return out


P8_SPEC = PrimitiveSpec(
    id="P8",
    name="CommodityFlowBias",
    category="TREND_FOLLOW",
    domain="pair_specific",
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


# ---------------------------------------------------------------------------
# P9 OilPriceInverseFlow (TREND_FOLLOW, USD_CAD)
# ---------------------------------------------------------------------------


def _p9_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """WTI 上昇 momentum → CAD 上昇 → USD_CAD 下落 → -tanh(wti_mom)。
    依存: aux_series["macro.wti"]。
    """
    n = len(ctx.bars)
    series = ctx.aux_series.get("macro.wti")
    _check_aux_series_length("P9", "macro.wti", series, n)
    if series is None:
        if ctx.strict_snapshot_required:
            raise RuntimeError(
                "P9: aux_series['macro.wti'] missing but strict mode"
            )
        _warn_missing("P9", "macro.wti")
        return np.zeros(n, dtype=np.float64)
    arr = np.asarray(series, dtype=np.float64)
    mom_n = _get_int_param(ctx.params, "mom_n")
    staleness_bars = _get_int_param(ctx.params, "staleness_bars")
    stale = _stale_mask(arr, staleness_bars)
    mom = np.full(n, np.nan, dtype=np.float64)
    if n > mom_n:
        mom[mom_n:] = (arr[mom_n:] - arr[:-mom_n]) / (
            np.abs(arr[:-mom_n]) + _EPS
        )
    scale = _get_float_param(ctx.params, "scale")
    out = np.where(
        stale | ~np.isfinite(mom),
        np.nan,
        -np.tanh(mom / (scale + _EPS)),
    )
    return out


P9_SPEC = PrimitiveSpec(
    id="P9",
    name="OilPriceInverseFlow",
    category="TREND_FOLLOW",
    domain="pair_specific",
    param_schema=(
        ParamSpec(name="mom_n", low=2, high=48, is_int=True, default=12),
        ParamSpec(name="scale", low=0.001, high=0.1, is_int=False, default=0.02),
        ParamSpec(name="staleness_bars", low=1, high=500, is_int=True, default=120),
    ),
    required_data=("ohlc", "macro.wti"),
    compute=_make_compute_single(_p9_compute_all),
    compute_all_bars=_p9_compute_all,
)


# ---------------------------------------------------------------------------
# P10 NADataProximityGate (MODULATOR, USD_CAD)
# ---------------------------------------------------------------------------


def _p10_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """NA セッション (12:00-21:00 UTC) かつ USD/CAD イベント ±window 分以内で
    gate を抑制 (0 寄り)。NA セッション外は 1.0 (gate open) で M4 と切り分け。
    """
    n = len(ctx.bars)
    na_lo, na_hi = 12 * 60.0, 21 * 60.0
    if ctx.event_snapshot is None:
        if ctx.strict_snapshot_required:
            raise RuntimeError(
                "P10: event_snapshot missing but strict mode"
            )
        _warn_missing("P10", "event_snapshot")
        return np.ones(n, dtype=np.float64)
    snapshot = ctx.event_snapshot
    calendar = snapshot.calendar
    as_of_ts = snapshot.as_of.timestamp()
    min_impact = _get_int_param(ctx.params, "min_impact")
    window_min = _get_float_param(ctx.params, "window_min")
    scale_min = _get_float_param(ctx.params, "scale_min")
    relevant = [
        e
        for e in calendar.events
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
            out[i] = 1.0
            continue
        t = ctx.bars[i].bar_time.timestamp()
        diff_min = float(np.min(np.abs(event_times - t)) / 60.0)
        raw = (window_min - diff_min) / (scale_min + _EPS)
        out[i] = 1.0 - float(sigmoid(raw))
    return out


P10_SPEC = PrimitiveSpec(
    id="P10",
    name="NADataProximityGate",
    category="MODULATOR",
    domain="pair_specific",
    param_schema=(
        ParamSpec(
            name="window_min", low=5.0, high=120.0,
            is_int=False, default=30.0,
        ),
        ParamSpec(
            name="scale_min", low=1.0, high=30.0,
            is_int=False, default=5.0,
        ),
        ParamSpec(name="min_impact", low=1, high=3, is_int=True, default=3),
    ),
    required_data=("ohlc", "calendar.economic_event"),
    compute=_make_compute_single(_p10_compute_all, neutral=1.0),
    compute_all_bars=_p10_compute_all,
)


# ---------------------------------------------------------------------------
# P11 EmergingMarketStressGate (MODULATOR, USD_ZAR)
# ---------------------------------------------------------------------------


def _p11_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """高 VIX + DXY 上昇 → EM ストレス → gate 抑制 (0 寄り)。
    低 VIX + DXY 安定 → リスクオン → gate 開放 (1 寄り)。

    依存: vix_snapshot + aux_series["macro.dxy"]。
    """
    n = len(ctx.bars)
    vix_snap = ctx.vix_snapshot
    dxy = ctx.aux_series.get("macro.dxy")
    _check_aux_series_length("P11", "macro.dxy", dxy, n)
    has_vix = vix_snap is not None and vix_snap.observations
    has_dxy = dxy is not None
    if not has_vix or not has_dxy:
        if ctx.strict_snapshot_required:
            raise RuntimeError(
                "P11: vix_snapshot or macro.dxy missing but strict mode"
            )
        _warn_missing("P11", "vix_snapshot or macro.dxy")
        return np.full(n, 0.5, dtype=np.float64)
    assert vix_snap is not None
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
        # 高 VIX → vix_pressure ~ 1、低 VIX → ~ 0
        vix_pressure = float(sigmoid((vix - vix_threshold) / (vix_scale + _EPS)))
        # DXY mom > 0 → ~1
        dxy_pressure = float(sigmoid(dxy_mom[i] / 0.005))
        stress = (vix_pressure + dxy_pressure) * 0.5
        out[i] = 1.0 - stress
    return out


P11_SPEC = PrimitiveSpec(
    id="P11",
    name="EmergingMarketStressGate",
    category="MODULATOR",
    domain="pair_specific",
    param_schema=(
        ParamSpec(name="dxy_n", low=2, high=120, is_int=True, default=20),
        ParamSpec(
            name="vix_threshold", low=10.0, high=40.0,
            is_int=False, default=25.0,
        ),
        ParamSpec(
            name="vix_scale", low=1.0, high=15.0,
            is_int=False, default=5.0,
        ),
        ParamSpec(
            name="vix_staleness_days", low=1.0, high=30.0,
            is_int=False, default=7.0,
        ),
        ParamSpec(
            name="dxy_staleness_bars", low=1, high=500,
            is_int=True, default=240,
        ),
    ),
    required_data=("ohlc", "macro.vix", "macro.dxy"),
    compute=_make_compute_single(_p11_compute_all, neutral=0.5),
    compute_all_bars=_p11_compute_all,
)


# ---------------------------------------------------------------------------
# P12 GoldCorrelationBias (TREND_FOLLOW, USD_ZAR)
# ---------------------------------------------------------------------------


def _p12_compute_all(ctx: EvaluationContext) -> np.ndarray:
    """金 momentum 上昇 → ZAR 上昇 → USD_ZAR 下落 → -tanh(gold_mom)。
    依存: aux_series["macro.gold"]。
    """
    n = len(ctx.bars)
    series = ctx.aux_series.get("macro.gold")
    _check_aux_series_length("P12", "macro.gold", series, n)
    if series is None:
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
        mom[mom_n:] = (arr[mom_n:] - arr[:-mom_n]) / (
            np.abs(arr[:-mom_n]) + _EPS
        )
    scale = _get_float_param(ctx.params, "scale")
    out = np.where(
        stale | ~np.isfinite(mom),
        np.nan,
        -np.tanh(mom / (scale + _EPS)),
    )
    return out


P12_SPEC = PrimitiveSpec(
    id="P12",
    name="GoldCorrelationBias",
    category="TREND_FOLLOW",
    domain="pair_specific",
    param_schema=(
        ParamSpec(name="mom_n", low=2, high=48, is_int=True, default=12),
        ParamSpec(name="scale", low=0.001, high=0.1, is_int=False, default=0.02),
        ParamSpec(name="staleness_bars", low=1, high=500, is_int=True, default=120),
    ),
    required_data=("ohlc", "macro.gold"),
    compute=_make_compute_single(_p12_compute_all),
    compute_all_bars=_p12_compute_all,
)


# ---------------------------------------------------------------------------
# 登録
# ---------------------------------------------------------------------------


_ALL_SPECS: tuple[PrimitiveSpec, ...] = (
    P1_SPEC, P2_SPEC, P3_SPEC, P4_SPEC, P5_SPEC, P6_SPEC,
    P7_SPEC, P8_SPEC, P9_SPEC, P10_SPEC, P11_SPEC, P12_SPEC,
)


def ensure_registered() -> None:
    """12 pair-specific primitive を registry に登録する。冪等。

    `_registry.register_if_absent` を使い、lock 内で存在確認＋登録を atomic に行う
    （T011/T012 と同じ規約）。
    """
    from src.alpha_factory.primitives._registry import register_if_absent

    for spec in _ALL_SPECS:
        register_if_absent(spec)


def all_specs() -> tuple[PrimitiveSpec, ...]:
    """12 pair-specific PrimitiveSpec タプルを返す（テスト/インスペクション用）。"""
    return _ALL_SPECS


# ---------------------------------------------------------------------------
# Public re-export
# ---------------------------------------------------------------------------

PAIR_SPECIFIC_SPECS: tuple[PrimitiveSpec, ...] = _ALL_SPECS
