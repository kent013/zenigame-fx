# Concept: primitives-pair-specific

## 目的

通貨ペア特化 primitive 12 個を実装。「設計の出発点は特定ペア」だが他ペアでも使用可能（opt-in）。

## 実装対象（2 個 × 6 ペア）

### EUR_USD 特化
- P1 LondonNYOverlapMomentum — ロンドン-NY オーバーラップ帯のモメンタム
- P2 IntradayRangeFade — 日内レンジ上下限で reversion

### USD_JPY 特化
- P3 TokyoOpenReversal — 東京オープン直後のギャップ反転
- P4 YenFixingBias — 仲値前後の実需フロー bias

### EUR_JPY 特化
- P5 CrossPairTriangulation — EUR_USD × USD_JPY の合成 implied と実 EUR_JPY の乖離
- P6 EuroHourVolRegime — 欧州時間ボラレジーム gate

### AUD_JPY 特化
- P7 RiskOnOffProxy — VIX + SPX からリスクオン/オフ bias
- P8 CommodityFlowBias — 銅 / 商品 index モメンタム

### USD_CAD 特化
- P9 OilPriceInverseFlow — WTI 原油逆相関
- P10 NADataSurpriseGate — 北米指標サプライズ window

### USD_ZAR 特化
- P11 EmergingMarketStressGate — VIX + DXY で EM ストレス判定
- P12 GoldCorrelationBias — 金価格順相関

## 前提

- P5: 複数ペアデータを参照（cross-pair データローダが必要）
- P7, P11: FRED VIX / DXY（`fred-ingest-implementation` 完了後）
- P8: OANDA XCU または FRED 商品 index
- P9: OANDA WTICO または FRED DCOILWTICO

## データアクセス戦略

- OANDA CFD が取れる場合: OANDA 経由
- 取れない場合: FRED 日足をルックアップ（日足なので前営業日 close を使用）

## テスト

- 各 primitive の単体テスト
- 他ペアに適用しても crash しない（符号・スケールは変わるが計算可能）

## 優先度・モード

- Priority: Medium
- Mode: incremental
- テーマ: primitives
