# Concept: fred-ingest-implementation

## 目的

FRED API（Federal Reserve Economic Data）から VIX / DXY / 金利等の日足マクロ指標を取り込む。

## 対象シリーズ（初期）

- VIXCLS — CBOE VIX Daily Close
- DTWEXBGS — Dollar Index (Broad)
- DGS10 — 米 10 年債利回り
- DGS2 — 米 2 年債利回り
- T10YIE — 10 年ブレークイーブンインフレ率

## 方針

1. `src/ingest/fred.py` 新設（httpx ベース、`fetch_series(series_id, start, end)` 関数）
2. `scripts/fetch_fred.py` CLI（`--series ... --from ... --to ...`）
3. DB schema: `macro_index_daily` テーブル alembic migration（id, series_id, date, value, fetched_at）
4. 3 年分一括取得で初期化
5. テスト: httpx モックで 1 シリーズ取得 → DB upsert まで

## 前提

- `src/config.py` に `fred_api_key`, `fred_base_url` 既存
- `.env` に `FRED_API_KEY` 設定済み
- レート制限: 120 req/min（十分余裕）

## 優先度・モード

- Priority: High
- Mode: incremental
- テーマ: data-ingest
