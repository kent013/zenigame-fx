# OANDA CFD Instrument Probe Report (T005)

## 試験条件
- 試験日時 (UTC): 2026-04-22T03:47:29.076419+00:00
- base_url: https://api-fxtrade.oanda.com
- granularity: M1, price: BA, count: 10

## 結果サマリー

| Instrument | verdict | status | candle_count | first_candle_time | error |
|---|---|---|---|---|---|
| SPX500_USD | OK | 200 | 10 | 2026-04-22T03:38:00+00:00 |  |
| WTICO_USD | OK | 200 | 10 | 2026-04-22T03:38:00+00:00 |  |
| XAU_USD | OK | 200 | 10 | 2026-04-22T03:38:00+00:00 |  |
| XCU_USD | OK | 200 | 10 | 2026-04-22T03:38:00+00:00 |  |
| JP225_USD | OK | 200 | 10 | 2026-04-22T03:38:00+00:00 |  |
| USB10Y_USD | OK | 200 | 10 | 2026-04-22T02:53:00+00:00 |  |
| USB02Y_USD | OK | 200 | 10 | 2026-04-22T02:47:00+00:00 |  |

## 集計
- total: 7
- OK: 7
- FORBIDDEN: 0
- NOT_FOUND: 0
- OTHER: 0

## 判定
- 全 OK

## 次アクション提案

### 結論

**全 7 instrument が OANDA live 口座で M1 candles 取得可能**。仮説 H1（米国規制等で 403 が返る）は **REJECTED**、H2（全アクセス可能）が **CONFIRMED**。primitive P7-P12 用の外部データは OANDA 単一経路で取り込みできる見込み。

### 推奨される後続 TODO（別途起票）

1. **OANDA CFD ingest pipeline 拡張** (data-ingest, Medium-High)
   - `price_bar_m1` テーブルに `asset_class` カラムを追加（FX / CFD_INDEX / CFD_COMMODITY / CFD_BOND など）
   - 既存 `scripts/fetch_incremental.py` を multi-instrument 対応に拡張、もしくは CFD 用 ingest スクリプトを新設
   - `currency_pair` テーブルか別 `instrument_meta` テーブルで CFD instrument の pip_location, displayPrecision を保持
   - 注意: CFD は `quoteHomeConversionFactors` の概念や margin 計算が FX と異なるためカラム/モデル拡張が必要
2. **CFD primitive の P7-P12 実装** (primitives, Medium)
   - P7 RiskOnOffProxy (SPX500), P8 CommodityFlowBias (XCU), P9 OilPriceInverseFlow (WTICO), P12 GoldCorrelationBias (XAU) を実装
   - JP225/USB10Y/USB02Y も補助指標として primitive 化
3. **(オプション) FRED 補助維持** (data-ingest, Low)
   - 日足の VIX/DXY/Treasury は引き続き FRED 経由でも取得（macro_index_daily）。OANDA M1 と FRED 日足を相互補完して使う設計。

### 設計留意点（観測から導出）

- `first_candle_time` を見ると SPX500/WTI/XAU/XCU/JP225 は試験時刻 (03:47 UTC) 直前の M1 candles が取得できているが、USB10Y/USB02Y は約 1 時間前の candles が最新（流動性または market hours の差）。CFD ingest 設計時に **時間帯ごとの flow rate** を考慮する必要がある。
- M1 取得は FX と同じ機構で問題なさそうだが、CFD は **week-end gap** や market-hours が FX と異なるため backtest engine 側でも instrument-specific の market_hours 定義が必要。

## 観測 vs 解釈の分離（注記）
- verdict は観測事実のみを記録。FORBIDDEN / NOT_FOUND は **現 live/account/environment で当該 instrument の candles を取得できなかった** という事実に過ぎず、「永久に使えない」「OANDA に存在しない」と解釈してはならない。
- account 区分・契約状態・地域規制等によって挙動が変わる可能性がある。代替経路を検討する際の入力情報として扱うこと。
