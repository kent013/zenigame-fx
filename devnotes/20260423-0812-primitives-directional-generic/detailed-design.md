# Detailed Design: primitives-directional-generic (T011)

本ドキュメントは `conceptual-design.md` の実装詳細版。各 primitive の `PrimitiveSpec` 定義・`compute` / `compute_all_bars` 擬似コード・`_indicators.py` ヘルパーのシグネチャを提示する。

## 共通ユーティリティ

### `_bars_to_close_arr(bars)` / `_bars_to_ohlc_arr(bars)`

```python
def _bars_to_mid_close(bars: Sequence[PriceBar]) -> np.ndarray:
    """bid/ask close の平均（mid close）を float64 ndarray で返す。"""
    return np.array(
        [(float(b.bid.close) + float(b.ask.close)) * 0.5 for b in bars],
        dtype=np.float64,
    )

def _bars_to_mid_ohlc(bars: Sequence[PriceBar]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """mid OHLC を返す（high/low は bid,ask の外接矩形）。"""
    n = len(bars)
    o = np.empty(n); h = np.empty(n); l = np.empty(n); c = np.empty(n)
    for i, b in enumerate(bars):
        bo, bh, bl, bc = float(b.bid.open), float(b.bid.high), float(b.bid.low), float(b.bid.close)
        ao, ah, al, ac = float(b.ask.open), float(b.ask.high), float(b.ask.low), float(b.ask.close)
        o[i] = (bo + ao) * 0.5
        h[i] = (bh + ah) * 0.5
        l[i] = (bl + al) * 0.5
        c[i] = (bc + ac) * 0.5
    return o, h, l, c
```

配置: `src/alpha_factory/primitives/directional_generic.py` 冒頭の module-private helper。

### `_EPS`

`_EPS = 1e-10`（全 tanh 内の 0 割り防止に加算）

### `_nan_to_zero(x)`

```python
def _nan_to_zero(x: float) -> float:
    return 0.0 if not np.isfinite(x) else float(x)
```

単点 compute で使用。compute_all_bars は NaN をそのまま array に返す（warmup 表現）。

## `_indicators.py`（numpy 実装）

全関数 pure numpy、float64、入力配列と同じ長さを返す。warmup 部は `np.nan`。

### シグネチャ一覧

```python
def ema(values: np.ndarray, n: int) -> np.ndarray: ...
def sma(values: np.ndarray, n: int) -> np.ndarray: ...
def rolling_sum(values: np.ndarray, n: int) -> np.ndarray: ...
def rolling_mean(values: np.ndarray, n: int) -> np.ndarray: ...
def rolling_std(values: np.ndarray, n: int, ddof: int = 0) -> np.ndarray: ...
def rolling_max(values: np.ndarray, n: int) -> np.ndarray: ...
def rolling_min(values: np.ndarray, n: int) -> np.ndarray: ...
def rolling_corr(x: np.ndarray, y: np.ndarray, n: int) -> np.ndarray: ...

def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray: ...
def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int) -> np.ndarray: ...

def rsi(values: np.ndarray, n: int) -> np.ndarray: ...
def bollinger(values: np.ndarray, n: int, k: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]: ...
def stochastic(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int, d_period: int = 3) -> tuple[np.ndarray, np.ndarray]: ...
def macd(values: np.ndarray, fast: int, slow: int, signal_n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]: ...
def donchian(high: np.ndarray, low: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]: ...
def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]: ...
# returns: (adx, plus_di, minus_di)

def realized_vol(log_returns: np.ndarray, n: int) -> np.ndarray: ...
def zscore(values: np.ndarray, n: int) -> np.ndarray: ...
def log_returns_from_close(close: np.ndarray) -> np.ndarray: ...
```

### アルゴリズム（主要関数のみ詳細化）

#### `ema(values, n)`
- `α = 2 / (n + 1)`
- seed: `ema[n-1] = mean(values[:n])`、`ema[i < n-1] = np.nan`
- recurrence: `ema[i] = α * values[i] + (1 - α) * ema[i-1]` for `i >= n`
- 実装: Python for-loop は避け、`np.empty` + 逐次代入 or `scipy.signal.lfilter`。依存削減のため numpy for-loop 単純実装で OK（len(bars) ~ 数万規模なので 十分高速）。
- **seed 選択の根拠**: pandas `ewm(span=n, adjust=False)` や多くの TA ライブラリ (TA-Lib) と揃える。`adjust=True` 系の重み付き平均は採用しない（backtest 再現性優先）。

#### `rolling_sum(values, n)`
- `cumsum = np.cumsum(values)`
- `result[i] = cumsum[i] - cumsum[i-n]` for `i >= n-1`
- `result[i] = cumsum[i]` for `i == n-1` (`cumsum[-1]` 相当回避で分岐)
- NaN 入力があると cumsum が伝播するため、呼び出し側で NaN を含まない前提（ or `np.where(np.isnan(values), 0, values)` 化してから）

実装:
```python
def rolling_sum(values: np.ndarray, n: int) -> np.ndarray:
    if n <= 0:
        raise ValueError("n must be >= 1")
    if len(values) < n:
        return np.full(len(values), np.nan)
    cs = np.cumsum(values)
    out = np.full(len(values), np.nan)
    out[n - 1] = cs[n - 1]
    out[n:] = cs[n:] - cs[:-n]
    return out
```

#### `rolling_max / rolling_min`
- monotonic deque（双方向キュー）。標準 `collections.deque` を用い O(N)。

#### `rolling_corr(x, y, n)`
```python
def rolling_corr(x, y, n):
    sx  = rolling_sum(x, n)
    sy  = rolling_sum(y, n)
    sxx = rolling_sum(x * x, n)
    syy = rolling_sum(y * y, n)
    sxy = rolling_sum(x * y, n)
    num = n * sxy - sx * sy
    denx = n * sxx - sx * sx
    deny = n * syy - sy * sy
    denom = np.sqrt(np.clip(denx, 0, None) * np.clip(deny, 0, None))
    with np.errstate(divide='ignore', invalid='ignore'):
        out = np.where(denom > 0, num / denom, np.nan)
    return out
```

#### `true_range / atr`
- `TR[0] = high[0] - low[0]`（prev_close が無いため一部書籍は NaN 扱いだが、本実装では幅として定義）
- `TR[i] = max(high[i] - low[i], |high[i] - close[i-1]|, |low[i] - close[i-1]|)` for i >= 1
- **ATR seed**: `atr[n-1] = mean(TR[0:n])`（TR[0] を含む SMA）、`atr[i] = (atr[i-1] * (n-1) + TR[i]) / n` for i >= n（Wilder smoothing、α=1/n）
- warmup: `atr[i < n-1] = np.nan`

#### `rsi(values, n)`
- `diff[i] = values[i] - values[i-1]` (i>=1)
- `up[i] = max(diff[i], 0)`, `down[i] = max(-diff[i], 0)`
- **Wilder seed**: `avg_up[n] = mean(up[1:n+1])`, `avg_down[n] = mean(down[1:n+1])`
- recurrence (i > n): `avg_up[i] = (avg_up[i-1]*(n-1) + up[i]) / n`（同 avg_down）
- `rs = avg_up / avg_down`, `rsi = 100 - 100/(1+rs)`
- avg_down == 0 の区間は `rsi = 100`（Wilder 定義）
- warmup: `rsi[i <= n-1] = np.nan`

#### `adx(high, low, close, n)`
- `+DM[i] = max(high[i] - high[i-1], 0) if (high[i]-high[i-1]) > (low[i-1]-low[i]) else 0`
- `-DM[i] = max(low[i-1] - low[i], 0) if (low[i-1]-low[i]) > (high[i]-high[i-1]) else 0`
- `TR[i]` 同上
- `+DI = 100 * Wilder_EMA(+DM) / Wilder_EMA(TR)`
- `-DI = 100 * Wilder_EMA(-DM) / Wilder_EMA(TR)`
- `DX = 100 * |+DI - -DI| / (+DI + -DI)`
- `ADX = Wilder_EMA(DX, n)`

返り値は `(adx, plus_di, minus_di)`。F4 で `sign(+DI - -DI)` も使うため DI も返す。

#### `stochastic(high, low, close, n)`
- `%K[i] = 100 * (close[i] - rolling_min(low, n)[i]) / (rolling_max(high, n)[i] - rolling_min(low, n)[i] + eps)`
- `%D = SMA(%K, d_period)`

#### `realized_vol(returns, n)`
- `sqrt(rolling_sum(r², n) / n)`（annualize せず raw。primitive 内で tanh スケール）

#### `zscore(values, n)`
- `(values - rolling_mean) / rolling_std`（rolling_std は ddof=0）

## 14 Primitive 詳細

各 primitive の `compute_all_bars` は以下のパターンに従う:

1. `close, high, low, open = _bars_to_mid_ohlc(bars)`
2. `_indicators` を呼んで必要な配列を算出
3. 式に従って element-wise で出力配列を作る（NaN propagation を `np.where(np.isfinite(...), ..., np.nan)` で制御）

`compute(ctx)` は `compute_all_bars(ctx)[ctx.idx]` を呼び、`_nan_to_zero` を通して `float` で返す。warmup 内で 0.0 を返す（primitive の意味的に neutral 値）。

### F1 TrendEMA

```python
F1_SPEC = PrimitiveSpec(
    id="F1",
    name="TrendEMA",
    category="TREND_FOLLOW",
    domain="generic",
    param_schema=(
        ParamSpec("fast_n", low=5, high=30, is_int=True, default=12),
        ParamSpec("slow_n", low=20, high=100, is_int=True, default=26),
        ParamSpec("atr_n", low=7, high=28, is_int=True, default=14),
    ),
    required_data=("ohlc",),
    compute=_compute_single(lambda ctx: _f1_compute_all(ctx)),
    compute_all_bars=_f1_compute_all,
)

def _f1_compute_all(ctx):
    _, h, l, c = _bars_to_mid_ohlc(ctx.bars)
    fast_n = int(ctx.params["fast_n"])
    slow_n = int(ctx.params["slow_n"])
    atr_n  = int(ctx.params["atr_n"])
    ef = ema(c, fast_n)
    es = ema(c, slow_n)
    a  = atr(h, l, c, atr_n)
    raw = (ef - es) / (a + _EPS)
    return np.tanh(raw)
```

warmup = `max(fast_n, slow_n, atr_n + 1)`

### F2 MACDSignal

```python
params:
  fast_n ∈ [6, 20] (int, default 12)
  slow_n ∈ [12, 40] (int, default 26)
  signal_n ∈ [5, 15] (int, default 9)
  scale_n ∈ [20, 100] (int, default 40)

def _f2_compute_all(ctx):
    _, _, _, c = _bars_to_mid_ohlc(ctx.bars)
    m, s, _ = macd(c, fast=fast_n, slow=slow_n, signal_n=signal_n)
    diff = m - s
    sigma = rolling_std(diff, scale_n, ddof=0)
    raw = diff / (sigma + _EPS)
    return np.tanh(raw)
```

正規化は「MACD histogram の rolling std」。ペア・時系列によるスケール差を吸収。

### F3 DonchianBreak

```python
params:
  n ∈ [10, 60] (int, default 20)
  k ∈ [0.5, 3.0] (float, default 1.5)
  atr_n ∈ [7, 28] (int, default 14)

def _f3_compute_all(ctx):
    _, h, l, c = _bars_to_mid_ohlc(ctx.bars)
    hi, lo, mid = donchian(h, l, n)
    a = atr(h, l, c, atr_n)
    raw = (c - mid) / (k * a + _EPS)
    return np.tanh(raw)
```

### F4 ADXTrend

```python
params:
  n ∈ [7, 28] (int, default 14)
  scale ∈ [5, 30] (float, default 15.0)

def _f4_compute_all(ctx):
    _, h, l, c = _bars_to_mid_ohlc(ctx.bars)
    adx_arr, plus_di, minus_di = adx(h, l, c, n)
    strength = np.tanh((adx_arr - 25.0) / scale)
    direction = np.sign(plus_di - minus_di)
    return strength * direction
```

**方向性**: +DI > -DI なら long (direction=+1)、逆なら -1。
**弱いときの挙動**: ADX < 25 で strength < 0 → direction を掛けると符号が反転する（弱い trend regime では誤ったシグナル）。これを避けるため **最終的には `strength = max(0, tanh((ADX - 25) / scale))` とし、弱い regime では 0 に倒す**。Round 1 Codex の Should-consider を取り込む。

修正版:
```python
def _f4_compute_all(ctx):
    _, h, l, c = _bars_to_mid_ohlc(ctx.bars)
    adx_arr, plus_di, minus_di = adx(h, l, c, n)
    strength = np.maximum(0.0, np.tanh((adx_arr - 25.0) / scale))
    direction = np.sign(plus_di - minus_di)  # -1, 0, +1
    return strength * direction
```

### F5 VolatilityBreak

```python
params:
  short_n ∈ [3, 20] (int, default 5)
  long_n ∈ [30, 120] (int, default 60)  # short_n < long_n を validate
  k ∈ [1, 10] (float, default 3.0)

def _f5_compute_all(ctx):
    _, h, l, c = _bars_to_mid_ohlc(ctx.bars)
    short_n = int(ctx.params["short_n"])
    long_n = int(ctx.params["long_n"])
    if short_n >= long_n:
        warnings.warn(f"F5: short_n ({short_n}) >= long_n ({long_n}); computing as-is",
                      RuntimeWarning, stacklevel=2)
    a_short = atr(h, l, c, short_n)
    a_long  = atr(h, l, c, long_n)
    ratio = a_short / (a_long + _EPS) - 1.0
    magnitude = np.maximum(0.0, np.tanh(k * ratio))  # 拡大のみ捕捉、収縮 (ratio<0) は 0
    ef = ema(c, short_n)
    es = ema(c, long_n)
    direction = np.sign(ef - es)
    return magnitude * direction
```

同様に「ボラ収縮（ratio<0）は 0」として、拡大 × 方向 のみ signal にする。

**注 (revision 2)**: `short_n < long_n` の関係は schema では表現できない。compute 内で swap せず、警告のみ出して式はそのまま通す（genotype→phenotype 多対一回避）。

### F6 SessionMomentum

```python
params:
  session ∈ {0, 1, 2} (int, default 0; 0=tokyo, 1=london, 2=ny)
  k ∈ [0.5, 3.0] (float, default 1.0)
  atr_n ∈ [7, 28] (int, default 14)

# Session (UTC) 静的境界:
_SESSION_RANGES_UTC = {
    0: (0, 9),   # Tokyo: 00:00-09:00 UTC
    1: (7, 16),  # London: 07:00-16:00 UTC
    2: (12, 21), # NY: 12:00-21:00 UTC
}

def _f6_compute_all(ctx):
    _, h, l, c = _bars_to_mid_ohlc(ctx.bars)
    session = int(ctx.params["session"])
    lo, hi = _SESSION_RANGES_UTC[session]
    a = atr(h, l, c, atr_n)
    n = len(ctx.bars)
    out = np.full(n, np.nan)
    session_open_close = np.nan
    prev_session_key: tuple[int, int] | None = None  # (session_day_utc, session_id)
    for i in range(n):
        b = ctx.bars[i]
        t_utc = b.bar_time.astimezone(timezone.utc)
        hour = t_utc.hour
        in_session = lo <= hour < hi
        # session_key を (UTC 日付 ordinal, session_id) で定義。
        # key が変わった最初の in_session bar が session 開始扱い。
        # これにより週末ギャップ・欠損バー越しでも開始を再検知できる。
        session_day = t_utc.toordinal() if in_session else None
        cur_key = (session_day, session) if session_day is not None else None
        if in_session and cur_key != prev_session_key:
            session_open_close = c[i]
            prev_session_key = cur_key
            out[i] = 0.0  # 開始 bar 自身は neutral
        elif in_session and np.isfinite(session_open_close) and np.isfinite(a[i]):
            raw = (c[i] - session_open_close) / (k * a[i] + _EPS)
            out[i] = np.tanh(raw)
        else:
            # session 外 → session_key リセット
            if not in_session:
                prev_session_key = None
            out[i] = 0.0
    return out
```

**Revision 2 (Codex design-review Must-fix 2 対応)**: 前 bar 非 session→当 bar session の隣接遷移のみで判定すると、週末ギャップや欠損バーで日を跨いだ場合に `session_open_close` が古い値のまま残る。`session_key = (UTC 日付 ordinal, session_id)` で判定し、key が変わった最初の in_session bar で必ず `session_open_close` を再設定する。

**lookahead 回避**: `session_open_close` は過去の開始 bar の `close`（確定値）のみ参照。当該 bar の `close` は `bar.complete=True` 前提で使用（DslStrategy 側で complete=False は除外する契約）。

### F7 RSIRevert

```python
params:
  n ∈ [7, 28] (int, default 14)
  scale ∈ [5, 30] (float, default 15.0)

def _f7_compute_all(ctx):
    _, _, _, c = _bars_to_mid_ohlc(ctx.bars)
    r = rsi(c, n)
    return np.tanh((50.0 - r) / scale)
```

RSI > 50（買われ過ぎ傾向）→ 出力 < 0（short bias）。逆で long bias。

### F8 BollingerRevert

```python
params:
  n ∈ [10, 60] (int, default 20)
  k ∈ [1.0, 3.0] (float, default 2.0)

def _f8_compute_all(ctx):
    _, _, _, c = _bars_to_mid_ohlc(ctx.bars)
    mid, std, _, _ = bollinger(c, n, k)
    raw = (mid - c) / (k * std + _EPS)
    return np.tanh(raw)
```

close が mid より上なら負（revert short）、下なら正（revert long）。

### F9 StochRevert

```python
params:
  n ∈ [7, 28] (int, default 14)
  scale ∈ [10, 40] (float, default 20.0)

def _f9_compute_all(ctx):
    _, h, l, c = _bars_to_mid_ohlc(ctx.bars)
    k, _ = stochastic(h, l, c, n)
    return np.tanh((50.0 - k) / scale)
```

### F10 ZScoreRevert

```python
params:
  n ∈ [10, 60] (int, default 20)

def _f10_compute_all(ctx):
    _, _, _, c = _bars_to_mid_ohlc(ctx.bars)
    z = zscore(c, n)
    return np.tanh(-z)
```

### F11 MeanReversionRange

```python
params:
  n ∈ [10, 60] (int, default 20)

def _f11_compute_all(ctx):
    _, h, l, c = _bars_to_mid_ohlc(ctx.bars)
    hi = rolling_max(h, n)
    lo = rolling_min(l, n)
    mid = (hi + lo) / 2.0
    width = (hi - lo) / 2.0 + _EPS
    raw = -(c - mid) / width
    return np.tanh(raw)  # raw が [-1, 1] 近くに収まるため tanh の鋭さは穏やか
```

### F12 RealizedVolZScore

```python
params:
  n ∈ [10, 60] (int, default 20)
  window ∈ [60, 500] (int, default 200)  # window > n を validate
  k_scale ∈ [1.5, 4.0] (float, default 2.5)

def _f12_compute_all(ctx):
    _, _, _, c = _bars_to_mid_ohlc(ctx.bars)
    r = log_returns_from_close(c)  # len == len(c), [0] = nan
    rv = realized_vol(r, n)
    z = zscore(rv, window)
    return np.tanh(z / k_scale)
```

**注**: `window > n` 関係を `_f12_compute_all` 内でガード。

### F13 ReturnAutocorrLag

```python
params:
  w ∈ [20, 200] (int, default 60)
  lag ∈ [1, 10] (int, default 1)

def _f13_compute_all(ctx):
    _, _, _, c = _bars_to_mid_ohlc(ctx.bars)
    r = log_returns_from_close(c)  # r[0] = nan
    # lag によるシフト: y[i] = r[i-lag]
    n = len(r)
    y = np.full(n, np.nan)
    y[lag:] = r[:-lag]
    # rolling_corr は NaN があると問題なので、先頭 (lag) + NaN 部を除く
    # x, y の NaN は出力側で自然に np.nan になるよう、rolling_corr は NaN-safe に
    # する代わり、最初の max(1, lag)+1 バーは NaN 返しで済ませる（標準的対応）。
    r_safe = np.where(np.isfinite(r), r, 0.0)
    y_safe = np.where(np.isfinite(y), y, 0.0)
    corr = rolling_corr(r_safe, y_safe, w)
    # NaN マスク: 最初の (1 + lag + w - 1) = lag + w バーは nan
    corr[: lag + w] = np.nan
    return corr  # rolling_corr は [-1, +1] が定義域、tanh 不要
```

### F14 TrendStrengthRatio

```python
params:
  fast_n ∈ [5, 30] (int, default 12)
  slow_n ∈ [20, 100] (int, default 26)
  rv_n ∈ [10, 60] (int, default 20)
  scale ∈ [0.5, 5.0] (float, default 1.0)
  k_scale ∈ [1.0, 5.0] (float, default 2.0)

def _f14_compute_all(ctx):
    _, _, _, c = _bars_to_mid_ohlc(ctx.bars)
    ef = ema(c, fast_n)
    es = ema(c, slow_n)
    r = log_returns_from_close(c)
    rv = realized_vol(r, rv_n)
    ratio = np.abs(ef - es) / (rv * scale * (c + _EPS) + _EPS)  # rv は対数収益率の std → 価格スケールに揃えるため close 倍。
    return np.tanh(ratio / k_scale)  # [0, +1]
```

**rv の単位**: `realized_vol` は log_return 単位（無次元）。`|EMA_diff|` は価格単位。両者を揃えるため `rv * c` で価格変動幅（絶対値）に戻し、さらに `scale` で調整する。

## PrimitiveSpec 統一定義パターン

重複を減らすため factory を用意:

```python
def _make_primitive_spec(
    *, id, name, category, param_schema, required_data, compute_all,
) -> PrimitiveSpec:
    def _single(ctx):
        arr = compute_all(ctx)
        idx = ctx.idx
        if idx < 0 or idx >= len(arr):
            return 0.0
        val = arr[idx]
        return 0.0 if not np.isfinite(val) else float(val)
    return PrimitiveSpec(
        id=id, name=name, category=category, domain="generic",
        param_schema=param_schema, required_data=required_data,
        compute=_single, compute_all_bars=compute_all,
    )
```

**性能上の注意**: `compute(ctx)` が `compute_all_bars` を毎回全系列再計算するのは O(N × N)。ただし DslStrategy は現状 `evaluate(bars, idx, signal)` を「バー毎の loop」で呼ぶため O(N²) になる。T009 の DslStrategy では primitive の per-bar 呼び出しを前提にしている:

```python
# src/dsl/strategy.py（T009）
# evaluator.evaluate(bars, idx, signal) が each bar ごとに呼ばれる
```

このパターンは GA の warmup_bars や evaluation 中 N^2 性能劣化を招くため、**将来の最適化 TODO**として cache 機構を提案（今回は scope 外）。T011 では契約に忠実に `compute` と `compute_all_bars` を両方提供し、単体テストは両方の一致を確認する。**本実装では `compute_all_bars` を public API として使う側（bulk 評価）と、`compute` を使う side（DslStrategy）の両経路をサポート**する。

### `compute_all_bars` を直接使える経路（性能最適化 hook）

DslStrategy 側で `evaluator.precompute(bars)` を呼ぶ方式が将来追加された場合に備え、`compute_all_bars` は pure function（state なし）で実装しておく。T011 では呼ばれない。

## ensure_registered（revision 2: 並行冪等性修正）

Codex design-review round 2 の Must-fix 1 対応: `try get_primitive / except KeyError: register` は非原子的で、並行時に `register` 側 `ValueError` が発生しうる。`_registry.py` に atomic な `register_if_absent(spec)` を追加する。

`src/alpha_factory/primitives/_registry.py` への追加（T010 骨格に対する追加変更）:
```python
def register_if_absent(spec: PrimitiveSpec) -> bool:
    """原子的に登録。既存なら False、新規登録なら True を返す。
    validate_primitive_spec は既存チェック前に呼ぶ（新規 spec の健全性は先に検証する）。
    """
    validate_primitive_spec(spec)
    with _LOCK:
        if spec.id in _PRIMITIVES:
            return False
        _PRIMITIVES[spec.id] = spec
        return True
```

`src/alpha_factory/primitives/__init__.py` に export を追加する。

directional_generic 側:
```python
_ALL_SPECS = (F1_SPEC, F2_SPEC, ..., F14_SPEC)

def ensure_registered() -> None:
    from src.alpha_factory.primitives._registry import register_if_absent
    for spec in _ALL_SPECS:
        register_if_absent(spec)
```

`src/alpha_factory/primitives/__init__.py` の `ensure_registered` を wrap して呼び出す。

## lookahead 検証

各 `compute_all_bars` を以下で verify:

1. numpy 実装内に `[::-1]`（reverse）が無い（reverse cumsum 禁止）。
2. rolling_* ヘルパーは `cumsum[i] - cumsum[i-n]` の形で i 未満のみ参照。
3. F6 SessionMomentum は `session_open_close` を過去 bar の close から更新、`ctx.bars[i+1:]` を一切参照しない。
4. ema の recurrence `ema[i] = α*x[i] + (1-α)*ema[i-1]` は過去のみ参照。
5. ATR / ADX の Wilder smoothing も recurrence で過去のみ。

テスト:
```python
def test_no_lookahead_property(spec):
    bars_n = 100
    bars = _build_random_bars(bars_n, seed=42)
    ctx = EvaluationContext(bars=bars, idx=bars_n - 1, pair="EUR_USD", params=_defaults(spec))
    result_full = spec.compute_all_bars(ctx)
    # bars[50:] を改変
    bars_mod = bars[:50] + _build_random_bars(50, seed=999)
    ctx_mod = EvaluationContext(bars=bars_mod, idx=bars_n - 1, pair="EUR_USD", params=_defaults(spec))
    result_mod = spec.compute_all_bars(ctx_mod)
    # 先頭 50 バーは不変
    np.testing.assert_allclose(result_full[:50], result_mod[:50], equal_nan=True)
```

## テスト計画詳細

### `tests/alpha_factory/primitives/test_indicators.py`
各ヘルパー 1-3 ケース:
- `test_ema_matches_recurrence`
- `test_rolling_sum_prefix_sum_equivalence`
- `test_rolling_std_variance_definition`
- `test_rolling_max_monotonic_deque`
- `test_rolling_corr_matches_numpy_corrcoef` — 既存ウィンドウを slice して `np.corrcoef` と比較
- `test_atr_wilder_smoothing`
- `test_rsi_extremes` — 全上昇で ~100、全下落で ~0
- `test_adx_on_constant_price_is_zero` — 価格変化なしで ADX = 0
- `test_stochastic_range_0_100`
- `test_bollinger_center_is_sma`
- `test_donchian_high_low_bracket`
- `test_realized_vol_sqrt_sum_sq`
- `test_zscore_mean_zero_std_one`

各テスト tolerance `1e-9`、入力は長さ 20-50 程度の既知シーケンス。

### `tests/alpha_factory/primitives/test_directional_generic.py`

1. `test_all_14_primitives_registered` — ensure_registered 後に 14 個すべて登録されていること、category 内訳 6/5/3。
2. 14 個 × `test_{id}_compute_matches_compute_all_bars` — N=50 bars、idx=40, 45, 49 で一致。
3. 14 個 × `test_{id}_bounded_within_unit_range` — 出力 `-1 <= x <= 1` (NaN 除く)。
4. 14 個 × `test_{id}_no_lookahead_property` — 上述のランダムバー改変テスト。
5. 14 個 × `test_{id}_known_input_expected_output` — 手計算 or 直接 numpy で期待値算出（小入力）。
6. F4/F5 の directional 妥当性:
   - 上昇トレンド + ADX 上昇 → F4 > 0
   - 下降トレンド + ADX 上昇 → F4 < 0
   - 横ばいかつ低 ADX → F4 ≈ 0
7. F6 Session boundary:
   - session 外 → 常に 0
   - session 開始 bar → 0
   - session 内 後続 bar → `tanh((close - open_close) / (k*ATR))` と一致
8. F13 rolling_corr が [-1, +1] で、全期間 i.i.d. シミュレーションで期待値 0 付近

## ParamSpec 制約まとめ

| ID | fast/short_n | slow/long_n | その他 |
|----|----------|---------|--------|
| F1 | [5, 30] | [20, 100] | atr_n [7, 28] |
| F2 | [6, 20] | [12, 40] | signal_n [5, 15], scale_n [20, 100] |
| F3 | - | - | n [10, 60], k [0.5, 3.0], atr_n [7, 28] |
| F4 | - | - | n [7, 28], scale [5, 30] |
| F5 | [3, 20] | [30, 120] | k [1, 10] |
| F6 | - | - | session {0,1,2}, k [0.5, 3.0], atr_n [7, 28] |
| F7 | - | - | n [7, 28], scale [5, 30] |
| F8 | - | - | n [10, 60], k [1.0, 3.0] |
| F9 | - | - | n [7, 28], scale [10, 40] |
| F10 | - | - | n [10, 60] |
| F11 | - | - | n [10, 60] |
| F12 | - | - | n [10, 60], window [60, 500], k_scale [1.5, 4.0] |
| F13 | - | - | w [20, 200], lag [1, 10] |
| F14 | [5, 30] | [20, 100] | rv_n [10, 60], scale [0.5, 5.0], k_scale [1.0, 5.0] |

**fast < slow の担保（revision 2: Codex design-review Must-fix 3 対応）**:

Round 2 Codex 指摘: compute 内で sort/swap すると genotype→phenotype 多対一化で GA 探索空間が歪む。

方針変更:
- **compute 内では swap しない**。`fast_n < slow_n` や `short_n < long_n` が破られた場合、compute_all_bars は ValueError を投げずに「そのまま計算」する。式が `EMA(fast) - EMA(slow)` → 実質 `EMA(slow_n) - EMA(fast_n)` の符号反転になる（GA が range 内で交差探索することを許容）。
- ただし `compute_all` 先頭で **warnings.warn** を 1 回出し、設計上の order 違反を観測可能にする（テスト fail を避けるため ValueError は避ける）。
- 将来 GA operator 側（T008 拡張）で「fast < slow 制約つき mutation」を入れる TODO を残す（本 T011 のスコープ外）。

同様に F12 の `window > n`:
- compute 内で `effective_window = max(window, n + 1)` を適用（完全な clamp ではなく、少なくとも rv の std が計算できる最低長を担保）。これは `zscore(rv, window)` の計算が window == n のとき rv の先頭 n - 1 個が NaN で実質標本数 1 になる退化を避ける。
- clamp 後の値は単に計算可能性を確保するだけで、GA の探索空間からは独立 sampling を維持。

実装方針:
- 設計ドキュメントで「input 制約の違反は compute_all の先頭で warnings.warn し、式はそのまま通す」と明記。
- テストで「fast > slow の極端入力が ValueError を起こさない」ことを確認。

## 実装の優先順位

1. `_indicators.py` (helper)
2. `directional_generic.py` の共通ユーティリティ + F1-F3（TREND 基本）
3. F4-F6（TREND 特殊系）
4. F7-F11（MEAN_REVERT）
5. F12-F14（NEUTRAL）
6. ensure_registered + `__init__.py` 更新
7. テスト

## 学術参照（実装根拠）

- Wilder (1978) — ATR / RSI / ADX の原典
- Lane (1984) Stochastic Oscillator — `%K = 100 * (C - min_low) / (max_high - min_low)`
- Bollinger (2001) — 2σ band デフォルト
- Appel (2005) — MACD
- Donchian (1960) — channel
- Cont (2001) *Empirical properties of asset returns* — rolling autocorr の stylized fact
- Andersen & Bollerslev (1997) — realized volatility
