# Concept: oanda-cfd-probe

## 目的

OANDA の現行 FX ライブ口座で CFD instrument（SPX500_USD, WTICO_USD, XAU_USD, XCU_USD, JP225_USD, USB10Y_USD, USB02Y_USD 等）にアクセス可能か試験する。アクセス不可の場合は FX データ完結方式（realized_vol, usd_strength_synthetic）を採用。

## 試験項目

1. `scripts/oanda_ping.py` 拡張で上記 instrument の `/v3/instruments/{X}/candles` エンドポイントを叩く
2. 200 応答 → OANDA で取り込み可能 → 後続 TODO で `price_bar_m1` テーブルに asset_class カラム追加し多様 instrument 対応
3. 403 等エラー応答 → 代替: FX データから `realized_vol(SPX500)` `usd_strength_synthetic` を計算する primitive を別 TODO で実装

## 方針

- 試験結果を devnotes に記録
- 結果に応じて次 TODO を生成（result 依存）

## 優先度・モード

- Priority: Medium
- Mode: incremental
- テーマ: data-ingest
