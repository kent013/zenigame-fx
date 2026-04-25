# 概念設計: primitives-directional-generic (T011)

## 背景

T010 で `src/alpha_factory/primitives/` に registry 骨格（PrimitiveSpec / ParamSpec / PrimitiveCategory / EvaluationContext / register / get_primitive / ensure_registered）が整備済だが、登録された primitive はゼロ。本 TODO では、全 FX ペアで共通使用可能な directional primitive 14 個（TREND_FOLLOW 6 + MEAN_REVERT 5 + NEUTRAL 3）を実装し registry に登録する。

## 目的

- Clause ベース Genome の directional スロットに入れる合計 14 個の汎用 primitive を用意する。
- 全て `EvaluationContext` (bars, idx, pair, params, aux_series) を受け、`float` または `np.ndarray` を返す。
- GA random_gen / mutator / crossover が registry 経由で参照できる状態にする。

## 非目的（本 TODO の scope 外）

- MODULATOR 系 primitive (M1-M6)
- pair_specific primitive (P1-P12)
- GA 側の random_gen の registry 切替（`src/ga/_dummy_registry.py` は触らない — 後続 TODO）
- Local gate・stage gate 機構

## 対象 14 primitive

| ID | 名前 | Category | 数式概要 |
|----|------|----------|----------|
| F1 | TrendEMA | TREND_FOLLOW | tanh((EMA_fast - EMA_slow) / ATR) |
| F2 | MACDSignal | TREND_FOLLOW | tanh((MACD - signal) / scale) |
| F3 | DonchianBreak | TREND_FOLLOW | tanh((close - DC_mid) / (k * ATR)) |
| F4 | ADXTrend | TREND_FOLLOW | tanh((ADX - 25) / scale) |
| F5 | VolatilityBreak | TREND_FOLLOW | tanh(k * (ATR_short/ATR_long - 1)) |
| F6 | SessionMomentum | TREND_FOLLOW | tanh(scale * session_return) |
| F7 | RSIRevert | MEAN_REVERT | tanh((50 - RSI) / scale) |
| F8 | BollingerRevert | MEAN_REVERT | tanh((BB_mid - close) / (k * BB_std)) |
| F9 | StochRevert | MEAN_REVERT | tanh((50 - %K) / scale) |
| F10 | ZScoreRevert | MEAN_REVERT | tanh(-zscore(close, n)) |
| F11 | MeanReversionRange | MEAN_REVERT | tanh(-(close - range_mid) / range_width) |
| F12 | RealizedVolZScore | NEUTRAL | zscore(realized_vol, n)（非 bounded） |
| F13 | ReturnAutocorrLag | NEUTRAL | Corr(returns, returns_lag_k) |
| F14 | TrendStrengthRatio | NEUTRAL | \|EMA_fast - EMA_slow\| / realized_vol |

## 設計方針

### 1. データ抽出

- `EvaluationContext.bars: Sequence[PriceBar]` から最初に `close = (bid.close + ask.close) / 2` の mid 系列を `np.ndarray[np.float64]` として抽出する。high / low も同様に mid ベース。
- Decimal → float 変換は一括（`compute_all_bars` では 1 回のみ）。`compute` 単一バー呼び出しでも内部的には同じ変換を経由（`compute_all_bars` を呼んで idx 要素を取るのが最もシンプル）。
- `atr` は OHLC の True Range を使う。`required_data=("ohlc",)` のみで自己完結可能なので本 TODO では `atr` key は使わず OHLC から算出する（ATR key は将来の aux_series ロード用に予約）。

### 2. モジュール構成

1 ファイル案（`directional_generic.py`）と分割案（`directional/{trend_follow,mean_revert,neutral}.py`）があるが、14 primitive は関連性が強く、共通 helper（mid 抽出）を共有するため **1 ファイル案** を採用する。判断理由:

- 全て「bars + params → ndarray」パターンで構造が同じ
- テストも 1 ファイルでまとめた方が重複を減らせる
- import/registry bootstrap が単純（1 import で 14 登録）

`_indicators.py` (technical indicator helpers) は別ファイルに分離する。

### 3. 技術指標ヘルパー (`_indicators.py`)

全て numpy ベースで因果的（最新バーまでの情報のみ使用）。

- `ema(values: np.ndarray, n: int) -> np.ndarray` — 指数移動平均（再帰式 `ema_t = alpha*x_t + (1-alpha)*ema_{t-1}`、alpha=2/(n+1)、初期値は先頭 n 本の SMA）
- `sma(values, n)` — 単純移動平均（numpy convolve または cumsum 差分）
- `rsi(values, n) -> np.ndarray` — Wilder RSI（gain/loss の SMMA）
- `atr_from_ohlc(high, low, close, n)` — True Range の Wilder SMMA
- `bollinger(values, n, k) -> (mid, std, upper, lower)` — rolling SMA と rolling std
- `stochastic(high, low, close, n) -> (k_pct, d_pct)` — %K = 100*(close - min_low) / (max_high - min_low), %D は %K の 3-SMA
- `macd(values, fast, slow, signal_n) -> (macd_line, signal_line, histogram)`
- `donchian(high, low, n) -> (dc_high, dc_low, dc_mid)` — rolling max/min
- `adx(high, low, close, n) -> np.ndarray` — Wilder の DI+/DI-/DX/ADX
- `realized_vol(returns, n) -> np.ndarray` — rolling std of log returns（または simple returns）
- `zscore(values, n) -> np.ndarray` — (x - rolling_mean) / rolling_std
- `rolling_corr(x, y, n) -> np.ndarray` — rolling Pearson correlation

全ての rolling 系は「index i の出力に i 以前の値のみ使用」という因果契約を明記（docstring）。warmup 不足期間は `np.nan`。

### 4. compute / compute_all_bars の関係

- **compute_all_bars が primary**: 内部で mid / high / low 抽出 → indicator 計算 → tanh 適用を O(N) で完結。
- `compute(ctx)` は `compute_all_bars(ctx)[ctx.idx]` を返す薄いラッパー（ただし返値が float であることを保証）。
- `compute_all_bars` の返値長は `len(ctx.bars)`、warmup 不足区間は `np.nan`。`compute` で NaN の場合はそのまま `float('nan')` を返す（上位の RegistryEvaluator / DslStrategy は既に nan 対応済と仮定、本 TODO では nan のまま）。

### 5. パラメータ範囲

各 primitive の ParamSpec は zenigame 参考に以下の範囲:

- 短期 EMA/SMA 窓: `fast_n [5, 30]` (int, default 12)
- 長期 EMA/SMA 窓: `slow_n [20, 100]` (int, default 26)
- ATR 窓: `atr_n [7, 30]` (int, default 14)
- RSI 窓: `n [5, 30]` (int, default 14)
- Bollinger 窓・k: `n [10, 60]` (default 20), `k [1.0, 3.0]` (default 2.0)
- Stochastic 窓: `n [5, 30]` (default 14)
- Donchian 窓: `n [10, 100]` (default 20), `k_atr [0.5, 3.0]` (default 1.0)
- MACD: `fast [5, 20]` (default 12), `slow [20, 50]` (default 26), `signal_n [5, 20]` (default 9)
- ADX 窓: `n [7, 30]` (default 14), `scale [5, 30]` (default 15)
- Volatility break: `short_n [3, 10]` (default 5), `long_n [14, 50]` (default 20), `k [1, 10]` (default 3)
- Session momentum: `session_hours [1, 8]` (default 4), `scale [0.001, 0.01]` (default 0.003)
- ZScore: `n [10, 100]` (default 30)
- MeanReversionRange: `n [10, 100]` (default 30)
- RealizedVolZScore: `vol_n [10, 100]` (default 20), `z_n [30, 200]` (default 60)
- ReturnAutocorrLag: `lag_k [1, 10]` (default 1), `n [20, 200]` (default 60)
- TrendStrengthRatio: `fast_n [5, 30]` (default 12), `slow_n [20, 100]` (default 26), `vol_n [10, 60]` (default 20)

細部は detailed-design で固定。

### 6. Session（F6 SessionMomentum）

`calendar.session` は本 TODO では aux_series にロードしない方針を維持しつつも、F6 は「session 開始からの累積リターン」を計算する必要がある。方針:

- `bar_time.hour` (UTC) からセッションを判定（Tokyo 0-8, London 7-15, NewYork 12-20、重複は後で扱う）。
- セッション境界で cumulative return をリセット。
- aux_series を使わない（ohlc だけで完結）。

詳細は detailed-design。

### 7. ルックアヘッドバイアス防止 (最重要)

- rolling 関数（mean / std / min / max）は `numpy.lib.stride_tricks.sliding_window_view` を使うか、cumsum 差分で index i に対して `values[i-n+1:i+1]` を使う方式（closed right）。
- EMA 再帰は `ema[i] = alpha*x[i] + (1-alpha)*ema[i-1]` — 因果的。
- rolling corr / z-score も同様に `[i-n+1, i]` window。
- F13（lag_k autocorrelation）は `returns[i-k]` と `returns[i]` の rolling corr。
- Session reset も「そのバーの時刻まで」で判定。
- テスト: 全 primitive に対し「idx 番目の値が bars[idx+1:] を改変しても不変」テストを実装。

### 8. 性能

`compute_all_bars` は O(N) 一括計算を必須とする。`compute(ctx)` を N 回呼ぶフォールバックは禁止（T010 PrimitiveSpec の docstring に明記あり）。内部 helper は numpy vectorized / sliding_window_view / cumsum 差分で実現。

### 9. 正規化契約

- TREND_FOLLOW / MEAN_REVERT: 出力は `[-1, +1]` に tanh 正規化。方向の符号は「+ = long シグナル、- = short シグナル」。
- NEUTRAL: tanh なし（F12 zscore, F13 corr [-1,1], F14 ratio [0,∞)）。clause 側 modulator / gate で変換する前提。F13 は [-1, 1] に自然に収まる。F14 は NaN/inf を安全に処理（vol=0 なら 0 を返す等）。

### 10. 数値安全性

- ATR = 0 や BB_std = 0 の場合: 分母 0 回避のため、`max(atr, epsilon)` で clip（epsilon = 1e-10）。
- Warmup 不足区間: 全 primitive で `np.nan` を返す。
- F12 realized_vol の zscore: 内部の std が 0 なら 0 を返す。

## テスト戦略

1. **既知入力での数値一致**: 手計算または reference 実装（pandas の rolling / talib 互換計算）との差分 < 1e-9。
2. **compute / compute_all_bars 一致**: `compute(ctx)` が `compute_all_bars(ctx)[idx]` と一致（nan 同士は nan 同士で一致判定）。
3. **ルックアヘッドバイアス**: `bars[:idx+1]` だけで構築した sub-context の結果と、完全 bars の結果の idx 番目が一致。
4. **境界**: warmup 不足で NaN 返却、0 分母で NaN / 0 返却、単一 bar 入力でも crash しない。
5. **registry 登録**: `import src.alpha_factory.primitives.directional_generic` で 14 個 registry 登録、カテゴリ別件数一致。
6. **_indicators.py 単体テスト**: 各 helper 関数に対して既知入力テスト。

## 制約

- Codex 呼び出しは `scripts/codex` 経由、API rate limit 配慮で round 数最低限。
- `src/ga/_dummy_registry.py` は触らない。
- mypy / ruff クリーン必須。
- 既存 380 tests passing / 1 skip を回帰させない。

## オープン質問（detailed-design で確定）

1. F6 SessionMomentum のセッション境界の具体的定義（UTC 時刻 / 重複セッション扱い）
2. F11 MeanReversionRange の range_mid / range_width の定義（`(HH+LL)/2`, `HH-LL`）
3. F13 ReturnAutocorrLag の zero-variance case の扱い
4. F14 TrendStrengthRatio の vol 分母 0 時の出力（0 か NaN か）
5. EMA 初期値の扱い（先頭 n 本の SMA を warmup として nan、それ以降で計算）

## 学術引用

- Wilder, J. W. (1978). *New Concepts in Technical Trading Systems*. Trend Research. — RSI / ATR / ADX
- Bollinger, J. (2002). *Bollinger on Bollinger Bands*. McGraw-Hill. — BB
- Appel, G. (2005). *Technical Analysis: Power Tools for Active Investors*. FT Press. — MACD
- Donchian, R. (1960). "Trend-Following Methods in Commodity Price Analysis". — Donchian Channel
- Lane, G. (1984). "Lane's Stochastics". — Stochastic
- López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. — look-ahead bias discipline
