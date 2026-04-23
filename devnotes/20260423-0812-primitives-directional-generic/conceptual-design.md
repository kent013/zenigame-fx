# Conceptual Design: primitives-directional-generic (T011)

## 目的

T010 で導入した primitives-registry に、全 FX ペアで共通利用可能な汎用 directional primitive 14 個（TREND_FOLLOW 6, MEAN_REVERT 5, NEUTRAL 3）を実装・登録する。Clause Architecture の GA（T007–T008）から生成された genome がこれらを `directional` slot から sampling し、DslStrategy（T009）が評価できる状態にする。

## 仮説と成功条件

- **仮説**: 14 primitive が「trend / reversion / volatility / autocorr」という統計的に独立した市場特性を表現するため、GA が clauses 内で組み合わせることで各 regime で有利なゲノムへ収束できる。
- **成功条件 (T011 スコープ内)**:
  1. registry.list_by_category が `TREND_FOLLOW=6 / MEAN_REVERT=5 / NEUTRAL=3` を返す
  2. 各 primitive の `compute(ctx)` と `compute_all_bars(ctx)[idx]` が (tolerance 1e-9 で) 一致
  3. look-ahead bias 6 チェックリスト全通過（後述）
  4. 既存 380 tests + 1 skip が壊れないこと
- **非スコープ**: 実際の fitness/Sharpe 改善は T012 以降の GA-run で計測。

## 配置方針

### モジュール分割

`src/alpha_factory/primitives/` 配下に以下を追加する:

- `_indicators.py` — numpy ベースの純粋な技術指標ヘルパー（EMA, RSI, ATR, BB, Stoch, MACD, Donchian, ADX, realized_vol, zscore）。registry には登録しない。
- `directional_generic.py` — 14 primitive の `PrimitiveSpec` を module-level 定義し、`ensure_registered()` 内で一括 register。

**14 個を 1 ファイルにまとめる理由**:
- どの primitive も `_indicators.py` のヘルパーを薄く wrap する構造（compute: 30–60 行、compute_all_bars: 20–40 行）であり、3 categoryにまたがる共通パターンを 1 ファイルで見通す方が保守しやすい。
- サブディレクトリに分割すると `ensure_registered` の集約が複数層になり、今後の primitive 追加（modulator-generic, pair-specific）との一貫性が崩れる。
- 1 ファイルにまとめても LoC は約 800–1000 で読める範囲。

`src/alpha_factory/primitives/__init__.py` の `ensure_registered` を以下に更新:

```python
def ensure_registered() -> None:
    from src.alpha_factory.primitives.directional_generic import (
        ensure_registered as _reg_directional_generic,
    )
    _reg_directional_generic()
```

冪等性は `register()` が `ValueError("already registered")` を投げるのを利用し、`ensure_registered` 側で「全 14 個が既登録なら即 return」する guard を入れる。

### ID と名前の対応

| ID | 名前 | Category |
|----|------|----------|
| F1 | TrendEMA | TREND_FOLLOW |
| F2 | MACDSignal | TREND_FOLLOW |
| F3 | DonchianBreak | TREND_FOLLOW |
| F4 | ADXTrend | TREND_FOLLOW |
| F5 | VolatilityBreak | TREND_FOLLOW |
| F6 | SessionMomentum | TREND_FOLLOW |
| F7 | RSIRevert | MEAN_REVERT |
| F8 | BollingerRevert | MEAN_REVERT |
| F9 | StochRevert | MEAN_REVERT |
| F10 | ZScoreRevert | MEAN_REVERT |
| F11 | MeanReversionRange | MEAN_REVERT |
| F12 | RealizedVolZScore | NEUTRAL |
| F13 | ReturnAutocorrLag | NEUTRAL |
| F14 | TrendStrengthRatio | NEUTRAL |

domain は全て `generic`。required_data は 14 primitive すべて `("ohlc",)`。F6 SessionMomentum は `bar.bar_time.hour`（UTC）のみで session 判定するため、aux_series `calendar.session` に依存しない（revision 1 で修正）。

## 共通契約

### 入出力

- 入力: `EvaluationContext(bars, idx, pair, params, aux_series)`
- 出力:
  - `compute(ctx) -> float` … 単一バー
  - `compute_all_bars(ctx) -> np.ndarray` … 長さ `len(ctx.bars)` の配列。warmup 不足 index は `np.nan`
- **全 14 primitive を `tanh(...)` で [-1, +1] に bounded**（2026-04-23 revision 1 で方針統一）。
  - 根拠: `slot_from_category` 上 `NEUTRAL` も `directional` slot に射影され、`dir_score = Σ(w_i × signal_i) / Σ|w_i|` で entry/exit 閾値に直接入る（clause-architecture.md:26, 39）。unbounded のままだと他 bounded signal を容易に圧倒し、実質的に hidden gate になる。
  - NEUTRAL 3 個（F12/F13/F14）は **tanh スケール定数 or 事前正規化** を組み込み、`[-1, +1]` に収める:
    - F12 RealizedVolZScore: zscore はすでに標準化済 → `tanh(z / k_scale)` で bound（`k_scale ∈ [1.5, 4.0]`）。
    - F13 ReturnAutocorrLag: rolling correlation は定義上 `[-1, +1]` なので `tanh` 不要（そのまま bounded）。
    - F14 TrendStrengthRatio: `|EMA_diff| / (rv + eps)` → `tanh(ratio / k_scale)` で bound。**注**: `|EMA_diff|` は常に非負 → 出力は `[0, 1]` に留まる。「NEUTRAL で sign を持たない absolute strength」という位置づけを保つ。
- 数値安定のため `np.nan` / `±inf` が混入する場合は有限値 or NaN にガード。

### source 値の取り方

`PriceBar.{bid,ask}.close` は `Decimal` 型。数値計算に `float` が必要なため、`_bar_to_close(bar)` / `_bars_to_close_arr(bars)` で `(bid.close + ask.close) / 2` を float 化する（mid 採用の根拠: 単一の directional 指標で bid/ask を分けない方針は T009 で確立）。

### warmup 規約

各 primitive の `warmup_bars()` 相当は **compute_all_bars の出力先頭 (warmup-1) 個を np.nan で埋める**ことで表現。`compute()` は `idx < warmup - 1` で np.nan を返す（float に変換した `np.nan` = `float('nan')`）。DslStrategy 側は warmup 内を skip するため問題ない（T009 実装を参照）。

## look-ahead bias チェックリスト（6 項目）

全 primitive で以下を compute と compute_all_bars の両方について verify する:

1. **未来バー参照なし** — `idx` より先の `bars[i] where i > idx` を一切参照しない。
2. **当日確定値の先取りなし** — `bars[idx].close` 等 "当該 bar の close" 使用は OK（bar が confirmed 前提）。ただし「当該 bar の外で発生するイベント」（例: session 境界の翌バー close など）を使わない。
3. **rolling window 方向** — `np.cumsum` / `pandas.rolling` 相当は `[i - n + 1, i]` の閉区間。将来方向 rolling（centered / future window）は禁止。
4. **正規化スケール** — z-score / bollinger の mean/std は**過去 window から算出**した rolling 値を使う。global mean/std は lookahead になるので禁止。
5. **バケット平均の因果性** — session 平均などグループ化集計は「過去 bar のみを含むグループ」から計算。F6 は「当日セッション開始 bar の close」のみ参照 → 過去方向。
6. **cumsum/accumulate の向き** — `np.cumsum(x)[i]` は `sum(x[:i+1])`（過去→現在）。`np.cumsum(x[::-1])[::-1]` のような逆向き cumsum は禁止。

各 primitive のテストで「**bars[idx+1:] を改変しても compute_all_bars(bars)[:idx+1] が不変**」という property test を実行する。

## 14 primitive の compute 式（要点のみ、詳細は detailed-design.md）

### TREND_FOLLOW (6)

- **F1 TrendEMA**: `tanh((EMA(close, fast) - EMA(close, slow)) / (ATR(bars, n) + eps))`  
  params: `fast_n ∈ [5, 30]`, `slow_n ∈ [20, 100]`, `atr_n ∈ [7, 28]`
- **F2 MACDSignal**: `MACD = EMA(c, fast) - EMA(c, slow); signal = EMA(MACD, signal_n); tanh((MACD - signal) / scale)`. scale は "MACD の rolling std * k" で正規化（固定 scale だとペア差が埋まらないため）。  
  params: `fast_n ∈ [6, 20]`, `slow_n ∈ [12, 40]`, `signal_n ∈ [5, 15]`, `scale_n ∈ [20, 100]`
- **F3 DonchianBreak**: `DC_mid = (max_high(n) + min_low(n)) / 2; tanh((close - DC_mid) / (k * ATR))`  
  params: `n ∈ [10, 60]`, `k ∈ [0.5, 3.0]`, `atr_n ∈ [7, 28]`
- **F4 ADXTrend**: `strength = (ADX(n) - 25) / scale; dir = sign(+DI(n) - -DI(n)); tanh(strength) * dir`  
  - directional の契約（long/short 方向 signal）を満たすため、`+DI - -DI` の符号で方向を与え、ADX の強度を tanh で [-1, 1] scale に正規化して掛ける。
  - 出力は「ADX が閾値 25 を超えるほど強い、+DI>-DI なら long、-DI>+DI なら short」を表す。
  - params: `n ∈ [7, 28]`, `scale ∈ [5, 30]`
- **F5 VolatilityBreak**: `magnitude = tanh(k * (ATR(short_n) / ATR(long_n) - 1)); dir = sign(EMA(close, short_n) - EMA(close, long_n)); magnitude * dir`  
  - compression / expansion の大小だけでは方向が出ないため、短期 EMA と長期 EMA の差の符号を掛けて「ボラ拡大 × 方向」を表す directional signal にする。
  - params: `short_n ∈ [3, 20]`, `long_n ∈ [30, 120]`, `k ∈ [1, 10]`（`long_n > short_n` は param validation で担保）
- **F6 SessionMomentum**: `ret = close - session_open_close; tanh(ret / (k * ATR))`  
  - session = `tokyo / london / ny` を UTC 時刻で静的マッピング。**実計算も `bar_time.hour`（UTC）だけで判定し外部系列に依存しないため、required_data は `("ohlc",)` のみ**（revision 1: 当初 `calendar.session` を宣言していたが、registry の required_data の契約「実際に消費する aux_series」と乖離するため削除）。  
  - `session_open_close` は「当該 bar が属するセッション開始 bar の `close`」。**lookahead 回避**: 開始 bar の確定 close を使うため、開始 bar 自体では 0 扱い（セッション開始直後は neutral）。  
  - params: `session ∈ {tokyo=0, london=1, ny=2}`（is_int）, `k ∈ [0.5, 3.0]`, `atr_n ∈ [7, 28]`

### MEAN_REVERT (5)

- **F7 RSIRevert**: `tanh((50 - RSI(n)) / scale)`  
  params: `n ∈ [7, 28]`, `scale ∈ [5, 30]`
- **F8 BollingerRevert**: `mid, std = bollinger(close, n, k); tanh((mid - close) / (k * std + eps))`  
  params: `n ∈ [10, 60]`, `k ∈ [1.0, 3.0]`
- **F9 StochRevert**: `%K = stochastic(bars, n).k; tanh((50 - %K) / scale)`  
  params: `n ∈ [7, 28]`, `scale ∈ [10, 40]`
- **F10 ZScoreRevert**: `z = zscore(close, n); tanh(-z)`  
  params: `n ∈ [10, 60]`
- **F11 MeanReversionRange**: `mid = (max_high(n) + min_low(n)) / 2; width = (max_high(n) - min_low(n)) / 2 + eps; tanh(-(close - mid) / width)`  
  params: `n ∈ [10, 60]`

### NEUTRAL (3)

NEUTRAL は「方向を主張しないが directional slot から sampling される」位置づけ。[-1, +1] に bounded し、値の大小で regime 情報を、符号で（該当する場合の）方向を表す。

- **F12 RealizedVolZScore**: `rv = realized_vol(log_returns, n); z = zscore(rv, window); tanh(z / k_scale)`  
  - 出力は「rv が過去分布より高い/低い」regime indicator。vol breakout の方向 bias は持たないが、z スコアの符号をそのまま通す（高 vol → 正、低 vol → 負）。directional slot 内で `weight` の符号で買い/売り bias を GA が学習する前提。
  - params: `n ∈ [10, 60]`, `window ∈ [60, 500]`, `k_scale ∈ [1.5, 4.0]`
- **F13 ReturnAutocorrLag**: `rolling_corr(returns[i-w+1..i], returns[i-w+1-lag..i-lag], w)`  
  - 定義上 `[-1, +1]` なので追加 tanh 不要。正=持続型、負=mean-revert 型 regime を示す。
  - params: `w ∈ [20, 200]`, `lag ∈ [1, 10]`
  - **O(N) 実装要件**: `rolling_corr` は prefix-sum で `sum(x)`, `sum(y)`, `sum(xy)`, `sum(x²)`, `sum(y²)` を O(1) 差分更新 → 各 i で相関計算 O(1) → 全体 O(N)。`_indicators.py` に `rolling_corr(x, y, w)` ヘルパーを追加する。warmup は `lag + w` バー。
- **F14 TrendStrengthRatio**: `ratio = |EMA(close, fast_n) - EMA(close, slow_n)| / (realized_vol(log_returns, rv_n) * scale + eps); tanh(ratio / k_scale)`  
  - `|EMA_diff|` が非負なので出力は `[0, +1]`。絶対的 trend 強度を neutral に返す。
  - params: `fast_n ∈ [5, 30]`, `slow_n ∈ [20, 100]`, `rv_n ∈ [10, 60]`, `scale ∈ [0.5, 5.0]`, `k_scale ∈ [1.0, 5.0]`

## 技術指標ヘルパー（`_indicators.py`）

全て numpy float64 で実装。戻り値は `len(input)` と同じ長さ、warmup 部は `np.nan`。

- `ema(values: np.ndarray, n: int) -> np.ndarray` — 再帰 `EMA[t] = α*x[t] + (1-α)*EMA[t-1]`, `α = 2/(n+1)`, seed は先頭 n 個の SMA。
- `true_range(bars) -> np.ndarray` — `max(high - low, |high - prev_close|, |low - prev_close|)`
- `atr(bars, n) -> np.ndarray` — TR の Wilder EMA（α = 1/n）。
- `rsi(values, n) -> np.ndarray` — Wilder RSI。
- `bollinger(values, n, k) -> (mid, std, upper, lower)` — rolling SMA と std。
- `stochastic(bars, n) -> (k, d)` — `%K = (close - min_low(n)) / (max_high(n) - min_low(n)) * 100`, `%D = SMA(%K, 3)`
- `macd(values, fast, slow, signal_n) -> (macd, signal, hist)` — EMA 差。
- `donchian(bars, n) -> (high, low, mid)`
- `adx(bars, n) -> np.ndarray` — +DI / -DI の Wilder EMA から DX → ADX。
- `realized_vol(returns, n) -> np.ndarray` — `sqrt(rolling_sum(r², n) / n)`
- `zscore(values, n) -> np.ndarray` — `(x - SMA(x, n)) / std(x, n)`
- `rolling_sum / rolling_mean / rolling_std / rolling_max / rolling_min` — O(N) prefix sum / monotonic deque 実装。
- `rolling_corr(x, y, n) -> np.ndarray` — `sum(x), sum(y), sum(xy), sum(x²), sum(y²)` の 5 本の prefix sum を各 O(1) 差分で更新し、`r = (n*Σxy - Σx*Σy) / sqrt((n*Σx² - (Σx)²)(n*Σy² - (Σy)²))` を各 i で算出。標準偏差が 0 になる区間は `np.nan` を返す。全体 O(N)。F13 で使用。

**O(N) 性能要件**:
- EMA は recurrence で O(N)。
- rolling_sum / mean / std は prefix-sum 差分で O(N)。
- rolling_max / min は **monotonic deque** で O(N)。np.maximum.accumulate は NG（window 外が落ちない）。
- cumsum 系の全ての operation は過去方向のみ使用。

## テスト方針

### `tests/alpha_factory/primitives/test_indicators.py`
- 各ヘルパーを「手計算で算出できる小入力（n=10 程度）」と比較。tolerance `1e-9`。
- warmup（最初の n 個 or 2n-1 個）が NaN であることを確認。
- 単調性や対称性のチェック（例: stochastic は [0, 100] 範囲）。

### `tests/alpha_factory/primitives/test_directional_generic.py`
- 各 primitive について:
  - `ensure_registered()` 後に `get_primitive(id)` で取得できる。
  - 既知入力で expected value を直接計算したものと一致。
  - `compute(ctx) == compute_all_bars(ctx)[idx]`（`idx = len(bars)-1` など複数 idx で）。
  - warmup 不足で `np.isnan` が返る。
  - **look-ahead property test**: `bars[idx+1:]` の `close` をランダム改変 → `compute_all_bars(bars_modified)[:idx+1]` が元の結果と完全一致。
- registry 集計:
  - `list_by_category("TREND_FOLLOW")` が 6 件
  - `list_by_category("MEAN_REVERT")` が 5 件
  - `list_by_category("NEUTRAL")` が 3 件
  - `list_by_domain("generic")` が 14 件

## 学術引用

- Wilder, J. W. (1978). *New Concepts in Technical Trading Systems*. — RSI / ADX / ATR の定義根拠。
- Donchian, R. (1960). *Donchian Channels*. — breakout indicator。
- Bollinger, J. (2001). *Bollinger on Bollinger Bands*. — BB の std 倍率 k。
- Appel, G. (2005). *Technical Analysis: Power Tools for Active Investors*. — MACD の fast=12/slow=26/signal=9 デフォルト。
- Lo, A. W. (2004). *The Adaptive Markets Hypothesis*. — trend/revert の時変性、primitive 並列配備の根拠。

## 既知のリスク／考慮事項

- **ATR のゼロ割り**: 新興市場・低流動性区間で ATR が極小になり得る。`eps = 1e-10` を全ての tanh 内除算で加算（値が歪まない range）。
- **float 変換損**: `Decimal → float` で精度落ちあるが、directional signal は [-1, 1] の粗さのため影響 negligible。Close 抽出を `_bars_to_close_arr` に集約し、同じ変換を全 primitive で使う。
- **F6 SessionMomentum の境界**: DST / 祝日で session 時刻がずれるが、UTC 静的境界で近似（具体的範囲は detailed-design で明記）。session mismatch bar は 0 (neutral) を返す。
- **NEUTRAL の bounded 化（revision 1 で変更）**: 当初 unbounded 案だったが、`NEUTRAL` も `directional` slot に射影されて `dir_score` に直接入るため他 bounded signal を圧倒してしまう。revision 1 で 3 個とも [-1, +1] bounded に変更（F12/F14 は tanh、F13 は rolling_corr が元から [-1, +1]）。

## 次ステップ

1. 本設計を `scripts/codex` (gpt-5.4 medium, conceptual-review) に投げて APPROVED 取得。
2. `detailed-design.md` で 14 primitive 各々の関数シグネチャ / compute_all_bars 擬似コード / param validation を詳細化。
3. `scripts/codex` (gpt-5.3-codex high, design-review) に投げて APPROVED 取得。
4. TODO 登録 → worktree 実装 → テスト → impl-review → commit/merge。
