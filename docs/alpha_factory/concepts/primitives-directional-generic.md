# Concept: primitives-directional-generic

## 目的

全 FX ペアで共通使用可能な directional primitive 14 個を `src/alpha_factory/primitives/` に実装。

## 実装対象

### TREND_FOLLOW (6)

| ID | 名前 | 数式 |
|----|------|------|
| F1 | TrendEMA | tanh((EMA_fast - EMA_slow) / ATR) |
| F2 | MACDSignal | tanh((MACD - signal) / scale) |
| F3 | DonchianBreak | tanh((close - DC_mid) / (k × ATR)) |
| F4 | ADXTrend | tanh((ADX - 25) / scale) |
| F5 | VolatilityBreak | tanh(k × (short_ATR/long_ATR - 1)) |
| F6 | SessionMomentum | tokyo / london / ny セッション内モメンタム |

### MEAN_REVERT (5)

| ID | 名前 | 数式 |
|----|------|------|
| F7 | RSIRevert | tanh((50 - RSI) / scale) |
| F8 | BollingerRevert | tanh((BB_mid - close) / (k × BB_std)) |
| F9 | StochRevert | tanh((50 - %K) / scale) |
| F10 | ZScoreRevert | tanh(-zscore(close, window)) |
| F11 | MeanReversionRange | tanh(-(close - range_mid) / range_width) |

### NEUTRAL (3)

| ID | 名前 | 数式 |
|----|------|------|
| F12 | RealizedVolZScore | zscore(realized_vol, window) |
| F13 | ReturnAutocorrLag | Corr(returns, returns_lag_k) |
| F14 | TrendStrengthRatio | |EMA_diff| / realized_vol |

## 共通仕様

- すべて `[-1, +1]` に tanh 正規化
- `compute(bars, idx, params) -> float` 単一バー用
- `compute_all_bars(bars, params) -> np.ndarray` O(N) 一括計算必須（compute の N 回フォールバック禁止）
- ルックアヘッドバイアスチェック 6 項目全通過

## テスト

- 各 primitive の単体テスト: 既知入力で期待値一致
- `compute` と `compute_all_bars` の結果一致
- ルックアヘッドバイアステスト: 後続バーを変えても過去の値が変わらない

## 優先度・モード

- Priority: High
- Mode: incremental（primitive 単位で分割可）
- テーマ: primitives
