# Primitives

## 目的

プリミティブ 32 個カタログの索引。各プリミティブの実体（関数 signature・実装手順）は別 TODO で扱う。

## スコープ

- 32 プリミティブの分類（汎用 Directional 14 / 汎用 Modulator 6 / ペア特化 12）
- 各プリミティブが持つべき必須メタ情報
- registry の役割

実装本体・パラメータ範囲は別 TODO（`concepts/primitives-registry.md` 等）で扱う。

## 用語リンク

本ドキュメントで使用する用語: [Directional](terminology.md#directional), [Modulator](terminology.md#modulator), [Local Gate](terminology.md#local-gate), [IC](terminology.md#ic)

## 主要定義

### 必須メタ情報（registry 登録時）

各プリミティブは以下を必ず宣言する:

- `name` — 一意な識別子（PascalCase）
- `category` — `directional` / `modulator`
- `domain` — `generic` / `pair_specific`
- `required_data` — 必要な系列（`ohlcv`, `fred:VIXCLS`, `oanda:SPX500_USD` 等）

### 汎用 Directional (14)

| # | 名称 | カテゴリ |
|---|------|---------|
| 1 | TrendEMA | trend |
| 2 | MACDSignal | trend |
| 3 | DonchianBreak | breakout |
| 4 | ADXTrend | trend |
| 5 | VolatilityBreak | breakout |
| 6 | SessionMomentum | session |
| 7 | RSIRevert | mean-revert |
| 8 | BollingerRevert | mean-revert |
| 9 | StochRevert | mean-revert |
| 10 | ZScoreRevert | mean-revert |
| 11 | MeanReversionRange | mean-revert |
| 12 | RealizedVolZScore | volatility |
| 13 | ReturnAutocorrLag | autocorr |
| 14 | TrendStrengthRatio | trend |

### 汎用 Modulator (6)

| # | 名称 | 役割 |
|---|------|------|
| 15 | ATRRegimeGate | volatility regime |
| 16 | SessionGate | session window |
| 17 | SpreadConditionGate | cost gate |
| 18 | EconomicEventGate | event blackout |
| 19 | VIXRegimeGate | macro fear regime（FRED VIXCLS） |
| 20 | TrendStrengthGate | trend confidence |

### ペア特化 (12)

| # | 名称 | 対象ペア |
|---|------|---------|
| 21 | LondonNYOverlapMomentum | EUR_USD |
| 22 | IntradayRangeFade | EUR_USD |
| 23 | TokyoOpenReversal | USD_JPY |
| 24 | YenFixingBias | USD_JPY |
| 25 | CrossPairTriangulation | EUR_JPY |
| 26 | EuroHourVolRegime | EUR_JPY |
| 27 | RiskOnOffProxy | AUD_JPY |
| 28 | CommodityFlowBias | AUD_JPY |
| 29 | OilPriceInverseFlow | USD_CAD |
| 30 | NADataSurpriseGate | USD_CAD |
| 31 | EmergingMarketStressGate | USD_ZAR |
| 32 | GoldCorrelationBias | USD_ZAR |

### Registry の役割

- 全 32 プリミティブを `src/alpha_factory/primitives/_registry.py` で列挙
- GA の random / mutate operator は registry から候補を抽選
- 新規追加時は registry 登録 + テスト追加が必須

## SSOT 参照

プリミティブは config 駆動でなく registry 駆動のため、`default.yaml` への参照は無い。パラメータ範囲は各プリミティブ実装内で定義。

## 関連ドキュメント

- [clause-architecture.md](clause-architecture.md) — directional / local_gate での利用
- [concepts/primitives-registry.md](concepts/primitives-registry.md)
- [concepts/primitives-directional-generic.md](concepts/primitives-directional-generic.md)
- [concepts/primitives-modulator-generic.md](concepts/primitives-modulator-generic.md)
- [concepts/primitives-pair-specific.md](concepts/primitives-pair-specific.md)

## 関連 TODO

- 未着手（Phase 2D: 32 プリミティブ並列実装）
