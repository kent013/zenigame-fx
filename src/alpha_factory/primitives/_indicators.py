"""技術指標ヘルパー（T011）。

全関数 pure numpy、float64、入力と同じ長さの配列を返す（warmup 部は np.nan）。
primitive 実装から利用され、registry には登録しない。

look-ahead bias 回避:
- rolling_* は prefix-sum/monotonic-deque で過去方向のみ参照
- Wilder smoothing (EMA/ATR/RSI/ADX) は recurrence で過去のみ
- reverse / future-shift は使用しない

学術参照:
- Wilder, J. W. (1978). New Concepts in Technical Trading Systems. — RSI/ADX/ATR 原典
- Donchian, R. (1960). Donchian Channels.
- Bollinger, J. (2001). Bollinger on Bollinger Bands.
- Appel, G. (2005). Technical Analysis: Power Tools for Active Investors. — MACD
- Lane, G. (1984). Stochastic Oscillator.
- Andersen, T. G., & Bollerslev, T. (1997). — realized volatility
"""

from __future__ import annotations

from collections import deque

import numpy as np

_EPS = 1e-10


# ---------------------------------------------------------------------------
# rolling 系 O(N) ヘルパー
# ---------------------------------------------------------------------------


def rolling_sum(values: np.ndarray, n: int) -> np.ndarray:
    """長さ n の過去方向 rolling sum を返す。warmup 部 (i < n-1) は NaN。

    O(N) 実装: `cumsum[i] - cumsum[i-n]`。
    入力に NaN を含まない前提（呼び出し側で事前処理）。
    """
    if n <= 0:
        raise ValueError(f"n must be >= 1, got {n}")
    values = np.asarray(values, dtype=np.float64)
    length = len(values)
    out = np.full(length, np.nan, dtype=np.float64)
    if length < n:
        return out
    cs = np.cumsum(values)
    out[n - 1] = cs[n - 1]
    if length > n:
        out[n:] = cs[n:] - cs[:-n]
    return out


def rolling_mean(values: np.ndarray, n: int) -> np.ndarray:
    s = rolling_sum(values, n)
    return s / float(n)


def sma(values: np.ndarray, n: int) -> np.ndarray:
    """Simple Moving Average (= rolling_mean) のエイリアス。"""
    return rolling_mean(values, n)


def rolling_std(values: np.ndarray, n: int, ddof: int = 0) -> np.ndarray:
    """長さ n の過去方向 rolling 標準偏差 (population; ddof=0 default)。

    O(N) 実装: `var = E[X²] - (E[X])²` を prefix-sum 2 本で算出。
    numerical round-off で var が負になりうるため max(var, 0) でクランプ。
    """
    if n <= 1 and ddof >= n:
        raise ValueError(f"n ({n}) must exceed ddof ({ddof})")
    values = np.asarray(values, dtype=np.float64)
    s = rolling_sum(values, n)
    s2 = rolling_sum(values * values, n)
    # var = E[X²] - (E[X])² (ddof=0) or (Σx² - (Σx)²/n) / (n - ddof) (ddof>0)
    var = (
        s2 / n - (s / n) ** 2
        if ddof == 0
        else (s2 - (s * s) / n) / (n - ddof)
    )
    var = np.maximum(var, 0.0)
    out = np.sqrt(var)
    # warmup NaN は s 経由で既に NaN
    return out


def rolling_max(values: np.ndarray, n: int) -> np.ndarray:
    """Monotonic deque による O(N) rolling max。warmup (i<n-1) は NaN。"""
    if n <= 0:
        raise ValueError(f"n must be >= 1, got {n}")
    values = np.asarray(values, dtype=np.float64)
    length = len(values)
    out = np.full(length, np.nan, dtype=np.float64)
    dq: deque[int] = deque()
    for i in range(length):
        # ウィンドウ外になった index を左から drop
        while dq and dq[0] <= i - n:
            dq.popleft()
        # 小さい値を右から drop (strict: >= なら drop; 等値は残しておく)
        while dq and values[dq[-1]] <= values[i]:
            dq.pop()
        dq.append(i)
        if i >= n - 1:
            out[i] = values[dq[0]]
    return out


def rolling_min(values: np.ndarray, n: int) -> np.ndarray:
    """Monotonic deque による O(N) rolling min。warmup (i<n-1) は NaN。"""
    if n <= 0:
        raise ValueError(f"n must be >= 1, got {n}")
    values = np.asarray(values, dtype=np.float64)
    length = len(values)
    out = np.full(length, np.nan, dtype=np.float64)
    dq: deque[int] = deque()
    for i in range(length):
        while dq and dq[0] <= i - n:
            dq.popleft()
        while dq and values[dq[-1]] >= values[i]:
            dq.pop()
        dq.append(i)
        if i >= n - 1:
            out[i] = values[dq[0]]
    return out


def rolling_corr(x: np.ndarray, y: np.ndarray, n: int) -> np.ndarray:
    """長さ n の過去方向 rolling Pearson 相関。warmup (i<n-1) は NaN。

    O(N) 実装: Σx, Σy, Σxy, Σx², Σy² の 5 本 prefix-sum を差分更新し、
    各 i で r = (n*Σxy - Σx*Σy) / sqrt((n*Σx² - (Σx)²)(n*Σy² - (Σy)²))。
    denom == 0 は NaN。
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if len(x) != len(y):
        raise ValueError("x and y must have the same length")
    sx = rolling_sum(x, n)
    sy = rolling_sum(y, n)
    sxx = rolling_sum(x * x, n)
    syy = rolling_sum(y * y, n)
    sxy = rolling_sum(x * y, n)
    num = n * sxy - sx * sy
    denx = np.maximum(n * sxx - sx * sx, 0.0)
    deny = np.maximum(n * syy - sy * sy, 0.0)
    denom = np.sqrt(denx * deny)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(denom > 0, num / denom, np.nan)
    # np.where は broadcasting 済み ndarray を返すため、入力が float の場合も ndarray
    # 出力を clip して numerical noise で [-1, +1] を僅かに超えるケースを抑える
    out = np.clip(out, -1.0, 1.0)
    # NaN は clip で保持されない場合があるため mask 戻し
    out = np.where(np.isnan(denom), np.nan, out)
    return out


# ---------------------------------------------------------------------------
# EMA 系
# ---------------------------------------------------------------------------


def ema(values: np.ndarray, n: int) -> np.ndarray:
    """指数移動平均。seed は最初の n 個の SMA、α = 2/(n+1)。

    warmup: out[i<n-1] = NaN。
    """
    if n <= 0:
        raise ValueError(f"n must be >= 1, got {n}")
    values = np.asarray(values, dtype=np.float64)
    length = len(values)
    out = np.full(length, np.nan, dtype=np.float64)
    if length < n:
        return out
    alpha = 2.0 / (n + 1.0)
    seed = float(values[:n].mean())
    out[n - 1] = seed
    prev = seed
    for i in range(n, length):
        cur = alpha * values[i] + (1.0 - alpha) * prev
        out[i] = cur
        prev = cur
    return out


def _wilder_smooth(values: np.ndarray, n: int) -> np.ndarray:
    """Wilder smoothing: seed = mean(values[:n]), α = 1/n.

    values の先頭 n 個の平均を seed とし、以降 recurrence。
    入力 NaN は 0 扱いしない（呼び出し側で除外する契約）。
    warmup: out[i<n-1] = NaN。
    """
    if n <= 0:
        raise ValueError(f"n must be >= 1, got {n}")
    values = np.asarray(values, dtype=np.float64)
    length = len(values)
    out = np.full(length, np.nan, dtype=np.float64)
    if length < n:
        return out
    # NaN を含む場合、先頭 n に NaN が混じっていたら seed が NaN に伝播する
    seed = float(np.nanmean(values[:n])) if np.any(np.isnan(values[:n])) else float(values[:n].mean())
    out[n - 1] = seed
    prev = seed
    for i in range(n, length):
        v = values[i]
        if np.isnan(v):
            # NaN 入力は前値を維持（Wilder は自己回帰）
            out[i] = prev
            continue
        cur = (prev * (n - 1) + v) / n
        out[i] = cur
        prev = cur
    return out


# ---------------------------------------------------------------------------
# TR / ATR
# ---------------------------------------------------------------------------


def true_range(
    high: np.ndarray, low: np.ndarray, close: np.ndarray
) -> np.ndarray:
    """True Range。

    TR[0] = high[0] - low[0]
    TR[i] = max(high[i] - low[i], |high[i] - close[i-1]|, |low[i] - close[i-1]|) for i >= 1
    """
    high = np.asarray(high, dtype=np.float64)
    low = np.asarray(low, dtype=np.float64)
    close = np.asarray(close, dtype=np.float64)
    length = len(high)
    tr = np.empty(length, dtype=np.float64)
    if length == 0:
        return tr
    tr[0] = high[0] - low[0]
    if length > 1:
        prev_close = close[:-1]
        h = high[1:]
        lo = low[1:]
        tr[1:] = np.maximum.reduce(
            [h - lo, np.abs(h - prev_close), np.abs(lo - prev_close)]
        )
    return tr


def atr(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int
) -> np.ndarray:
    """ATR (Wilder smoothing, α = 1/n)。warmup (i<n-1) は NaN。"""
    tr = true_range(high, low, close)
    return _wilder_smooth(tr, n)


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------


def rsi(values: np.ndarray, n: int) -> np.ndarray:
    """Wilder RSI。

    diff[i] = v[i] - v[i-1] (i>=1)
    up = max(diff, 0), down = max(-diff, 0)
    avg_up/avg_down = Wilder_EMA(..., n), seed = mean(up[1:n+1]) 等
    rs = avg_up / avg_down; rsi = 100 - 100/(1+rs)
    avg_down == 0 の区間は rsi = 100。
    warmup: rsi[i<=n] = NaN（seed が i=n 時点）。
    """
    if n <= 0:
        raise ValueError(f"n must be >= 1, got {n}")
    values = np.asarray(values, dtype=np.float64)
    length = len(values)
    out = np.full(length, np.nan, dtype=np.float64)
    if length < n + 1:
        return out
    diff = np.diff(values, prepend=values[0])  # diff[0] = 0
    up = np.where(diff > 0, diff, 0.0)
    down = np.where(diff < 0, -diff, 0.0)
    # seed: mean over i in [1, n] (inclusive) == indices 1..n
    avg_up = np.full(length, np.nan, dtype=np.float64)
    avg_down = np.full(length, np.nan, dtype=np.float64)
    # index n has seed
    seed_up = float(up[1 : n + 1].mean())
    seed_down = float(down[1 : n + 1].mean())
    avg_up[n] = seed_up
    avg_down[n] = seed_down
    prev_up = seed_up
    prev_down = seed_down
    for i in range(n + 1, length):
        prev_up = (prev_up * (n - 1) + up[i]) / n
        prev_down = (prev_down * (n - 1) + down[i]) / n
        avg_up[i] = prev_up
        avg_down[i] = prev_down
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = np.where(avg_down > 0, avg_up / avg_down, np.inf)
        out = 100.0 - 100.0 / (1.0 + rs)
    out = np.where(np.isnan(avg_up), np.nan, out)
    return out


# ---------------------------------------------------------------------------
# Bollinger
# ---------------------------------------------------------------------------


def bollinger(
    values: np.ndarray, n: int, k: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Bollinger Bands (mid=SMA, std=population std, upper/lower = mid ± k*std)。"""
    mid = sma(values, n)
    std = rolling_std(values, n, ddof=0)
    upper = mid + k * std
    lower = mid - k * std
    return mid, std, upper, lower


# ---------------------------------------------------------------------------
# Stochastic
# ---------------------------------------------------------------------------


def stochastic(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    n: int,
    d_period: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    """Stochastic Oscillator (%K, %D)。

    %K = 100 * (C - min_low(n)) / (max_high(n) - min_low(n) + eps)
    %D = SMA(%K, d_period)
    warmup %K: i < n-1 → NaN。
    """
    hi = rolling_max(high, n)
    lo = rolling_min(low, n)
    denom = hi - lo
    with np.errstate(divide="ignore", invalid="ignore"):
        k = np.where(denom > 0, 100.0 * (close - lo) / denom, 0.0)
    # warmup は hi/lo が NaN → k に伝播させる
    k = np.where(np.isnan(hi) | np.isnan(lo), np.nan, k)
    k = np.clip(k, 0.0, 100.0)
    k = np.where(np.isnan(hi) | np.isnan(lo), np.nan, k)  # clip で nan 消えたら戻す
    d = sma(k, d_period)
    return k, d


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------


def macd(
    values: np.ndarray, fast: int, slow: int, signal_n: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MACD = EMA(fast) - EMA(slow); Signal = EMA(MACD, signal_n); Hist = MACD - Signal."""
    ef = ema(values, fast)
    es = ema(values, slow)
    m = ef - es
    # signal 用に ema を計算するが、m に NaN があるので NaN を含んだ入力になる
    # ema は NaN 伝播で warmup を拡張する: seed 計算で np.nan 入ると失敗
    # ここでは slow 以降の値が有効なので、slow 分ずらして EMA を計算する実装
    length = len(values)
    s = np.full(length, np.nan, dtype=np.float64)
    start = max(fast, slow) - 1  # m が有効になる先頭 index
    if length - start >= signal_n:
        # 有効範囲だけで EMA を計算し元の index に戻す
        sub = m[start:]
        sub_ema = ema(sub, signal_n)
        s[start:] = sub_ema
    hist = m - s
    return m, s, hist


# ---------------------------------------------------------------------------
# Donchian
# ---------------------------------------------------------------------------


def donchian(
    high: np.ndarray, low: np.ndarray, n: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Donchian channel (upper=rolling_max(high,n), lower=rolling_min(low,n), mid)."""
    hi = rolling_max(high, n)
    lo = rolling_min(low, n)
    mid = (hi + lo) / 2.0
    return hi, lo, mid


# ---------------------------------------------------------------------------
# ADX
# ---------------------------------------------------------------------------


def adx(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ADX / +DI / -DI (Wilder smoothing)。

    返り値: (adx, plus_di, minus_di)
    warmup: i < 2n-1 程度で NaN。
    """
    high = np.asarray(high, dtype=np.float64)
    low = np.asarray(low, dtype=np.float64)
    close = np.asarray(close, dtype=np.float64)
    length = len(high)
    plus_di = np.full(length, np.nan, dtype=np.float64)
    minus_di = np.full(length, np.nan, dtype=np.float64)
    adx_out = np.full(length, np.nan, dtype=np.float64)
    if length < 2:
        return adx_out, plus_di, minus_di

    up_move = high[1:] - high[:-1]
    down_move = low[:-1] - low[1:]
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    # index 0 は未定義
    plus_dm_full = np.concatenate([[0.0], plus_dm])
    minus_dm_full = np.concatenate([[0.0], minus_dm])

    tr = true_range(high, low, close)

    # Wilder smoothing on tr, plus_dm, minus_dm starting at index n.
    # seed は mean (Wilder 原典は sum then smooth だが、mean seed で
    # _wilder_smooth と一貫性を保つ)。

    sm_tr = _wilder_smooth(tr, n)
    sm_plus = _wilder_smooth(plus_dm_full, n)
    sm_minus = _wilder_smooth(minus_dm_full, n)

    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = np.where(sm_tr > 0, 100.0 * sm_plus / sm_tr, 0.0)
        minus_di = np.where(sm_tr > 0, 100.0 * sm_minus / sm_tr, 0.0)
    plus_di = np.where(np.isnan(sm_tr), np.nan, plus_di)
    minus_di = np.where(np.isnan(sm_tr), np.nan, minus_di)

    di_sum = plus_di + minus_di
    with np.errstate(divide="ignore", invalid="ignore"):
        dx = np.where(di_sum > 0, 100.0 * np.abs(plus_di - minus_di) / di_sum, 0.0)
    dx = np.where(np.isnan(plus_di) | np.isnan(minus_di), np.nan, dx)

    adx_out = _wilder_smooth(dx, n)
    return adx_out, plus_di, minus_di


# ---------------------------------------------------------------------------
# Realized vol / z-score
# ---------------------------------------------------------------------------


def log_returns_from_close(close: np.ndarray) -> np.ndarray:
    """対数収益率 log(c[i]/c[i-1])。先頭 [0] = NaN。"""
    close = np.asarray(close, dtype=np.float64)
    length = len(close)
    out = np.full(length, np.nan, dtype=np.float64)
    if length < 2:
        return out
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = close[1:] / close[:-1]
        out[1:] = np.where(
            (close[:-1] > 0) & (ratio > 0), np.log(ratio), np.nan
        )
    return out


def realized_vol(log_ret: np.ndarray, n: int) -> np.ndarray:
    """sqrt(rolling_sum(r², n) / n)。log_ret の NaN は 0 扱いせずに伝播。"""
    log_ret = np.asarray(log_ret, dtype=np.float64)
    # NaN を含む場合、rolling_sum が NaN になる → realized_vol も NaN。
    # 先頭 [0] の NaN を避けるため NaN を 0 に置換してから rolling_sum。
    # 先頭 [0:1] の 0 を使うと bias するため、先頭マスクを別途掛ける。
    safe = np.where(np.isnan(log_ret), 0.0, log_ret)
    s = rolling_sum(safe * safe, n)
    out = np.sqrt(np.maximum(s / n, 0.0))
    # 最初の n 個は rolling_sum で NaN、さらに log_ret[0] が NaN である以上 i>=n で有効
    return out


def zscore(values: np.ndarray, n: int) -> np.ndarray:
    """(x - rolling_mean) / rolling_std (ddof=0)。std==0 は NaN。"""
    m = rolling_mean(values, n)
    s = rolling_std(values, n, ddof=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(s > 0, (values - m) / s, np.nan)
    # m が NaN の warmup 区間は out も NaN にする
    out = np.where(np.isnan(m), np.nan, out)
    return out
