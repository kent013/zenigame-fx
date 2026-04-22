# Concept: oanda-cfd-ingest-pipeline

## 目的

T005 で全 7 instrument アクセス可能を確認した OANDA CFD（SPX500_USD, WTICO_USD, XAU_USD, XCU_USD, JP225_USD, USB10Y_USD, USB02Y_USD）を `price_bar_m1` テーブルに取り込むパイプラインを構築。

## 設計

### DB スキーマ

`currency_pair` テーブル名は misnomer（中身は generic instrument）。改名 or 維持判断:
- **Option A**: `currency_pair` を `instrument` に rename（migration で alias）+ `asset_class ENUM('fx','index','commodity','bond')` カラム追加
- **Option B**: `currency_pair` 名前維持、`asset_class` カラム追加

推奨: **Option A**（中長期で意味的一貫性）

### Ingest

- `scripts/fetch_incremental.py` を multi-instrument 対応化（既存は単一 instrument 想定？要確認）
- 各 CFD について OANDA candles 仕様（pip_location, market_hours 等）を `instrument_meta` に保持
- Bond CFD（USB10Y_USD, USB02Y_USD）は他より market_hours が短い → fetch スケジューラで配慮

### 検証

- 各 instrument について 1 ヶ月分 fetch → DB 投入 → row count 妥当性
- pytest: ingest フローのモックテスト

## 優先度・モード

- Priority: Medium
- Mode: standalone（DB schema 変更で広範囲影響）
- テーマ: data-ingest

## 関連

- 前提: T005 (oanda-cfd-probe) APPROVED
- 後続: primitives-pair-specific の P7-P12 が CFD データを参照する
