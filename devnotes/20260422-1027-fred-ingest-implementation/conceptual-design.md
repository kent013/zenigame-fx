# 概念設計: FRED API ingest（マクロ指標日足取り込み）

- 作成日時: 2026-04-22 10:27 JST
- ステータス: Draft
- トピック: fred-ingest-implementation
- 関連 concept: `docs/alpha_factory/concepts/fred-ingest-implementation.md`

---

## 1. 目的

FRED API（St. Louis Fed の Federal Reserve Economic Data）から、Alpha Factory primitive 群が必要とするマクロ指標日足を取り込み、PostgreSQL（`zenigame_fx_db_1`）の `macro_index_daily` テーブルへ蓄積する。

**スコープ限定**: 初期対象は **FRED 上の daily market-derived proxy（VIX / DXY / Treasury yields / breakeven）** に限定する。Monthly / Quarterly や CPI 等の revision-sensitive な macro 指標は本設計の対象外（revision 履歴を保持しないため）。

これは後続の以下 primitive 実装の前提となる:

- **M5 VIXRegimeGate** — VIX 水準で trade allow/deny
- **P7 RiskOnOffProxy** — VIX / DXY / 金利スプレッドから risk-on / risk-off proxy
- 将来の rate-spread / breakeven 系 primitive

## 2. 対象シリーズ（初期）

| series_id | 内容 | 想定用途 |
|-----------|------|---------|
| `VIXCLS` | CBOE VIX 終値 | リスク回避指標、VIXRegimeGate |
| `DTWEXBGS` | Dollar Index (Broad) | USD 強弱、EUR/USD・GBP/USD 等の方向感 |
| `DGS10` | 米 10 年債利回り | 金利水準、金利感応度の高いペア |
| `DGS2` | 米 2 年債利回り | 短期金利、利回り曲線 |
| `T10YIE` | 10 年ブレークイーブンインフレ率 | 期待インフレ |

5 シリーズ × 3 年 = 5 リクエスト初期、追加は日次差分のみ。

## 3. 入出力

### Input

- `series_id`: FRED シリーズ識別子（例: `VIXCLS`）
- `start`: 取得開始日（inclusive、`date` 型）
- `end`: 取得終了日（inclusive、`date` 型）
- 環境変数 `FRED_API_KEY`（既存 `src/config.py` の `settings.fred_api_key`）

### Output

- DB テーブル `macro_index_daily`
  - `id BIGSERIAL PRIMARY KEY`
  - `series_id VARCHAR(20) NOT NULL`
  - `date DATE NOT NULL` — observation date（FRED 上の `observations[].date` 値）
  - `value NUMERIC(18, 6) NULL` — FRED は欠損値を `.` で返すため NULL 許容
  - `fetched_at TIMESTAMPTZ NOT NULL`
  - `created_at TIMESTAMPTZ DEFAULT now() NOT NULL`
  - UNIQUE(`series_id`, `date`)

### Look-ahead 契約（重要）

`date=D` の観測値は、現実には FRED 配信タイムラグ（数時間〜翌営業日）で利用可能になるが、本テーブルでは `available_at` を持たない。**Primitive 側は必ず `date=D` の値を `D+1` 以降の判断に利用する（T+1 利用原則）**。当日 intraday の使用は look-ahead bias を生むため禁止。`available_at` 列は本設計のスコープ外（必要になれば別 TODO で追加）。

## 4. 方針

### A. クライアント

- **httpx** ベース（既存 `src/api/oanda/client.py` と同方針）
- `fetch_series(series_id: str, start: date, end: date) -> list[dict]`
  - FRED のエンドポイント: `GET {fred_base_url}/series/observations`
  - パラメータ: `series_id`, `observation_start=YYYY-MM-DD`, `observation_end=YYYY-MM-DD`, `file_type=json`, `api_key=...`
  - 応答 `observations` 配列を `[{"date": date, "value": Decimal | None}]` に正規化
  - 値が `"."` のものは `None` として保持（欠損）

### B. タイムアウト・リトライ・エラー処理

- FRED 公開上限: 120 req/min（実用上 5 シリーズ × 数回程度なら全く問題ない）
- `httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)` を明示的に指定
- リトライ対象:
  - HTTP 429（rate limit） / 5xx → exponential backoff 最大 3 回
  - `httpx.TimeoutException`, `httpx.TransportError`（DNS / connection error 含む）→ 同上
- 即時 raise:
  - HTTP 400（bad request: シリーズ ID 不正 等）
  - HTTP 401 / 403（認証エラー: API key 不正）
- structlog で `series_id`, `attempt`, `status_code`, `elapsed` を出力
- グローバル token-bucket は不要と判断（必要になったら別 TODO で追加）

### C. CLI

`scripts/fetch_fred.py`
- `--series VIXCLS,DTWEXBGS,DGS10,DGS2,T10YIE`（カンマ区切り）
- `--from 2023-04-23 --to 2026-04-21`（YYYY-MM-DD）
- 各シリーズを順次 `fetch_series` → `upsert_observations` する
- 進捗・件数を stdout / structlog で出力
- 既存 `scripts/fetch_historical.py` / `scripts/load_economic_events.py` 等と同じく初手から `scripts/` 配下に置く（既存 ingest CLI が同パターンで安定稼働しているため、devnotes 経由を省略）

### D. DB upsert

- `upsert_observations(session, rows: list[dict]) -> int`
- `INSERT ... ON CONFLICT (series_id, date) DO UPDATE SET value=EXCLUDED.value, fetched_at=EXCLUDED.fetched_at`
- 既存実装 `src/ingest/candles.py:store_bars` と同パターン（`sqlalchemy.dialects.postgresql.insert`）

### E. テスト

- `tests/ingest/test_fred.py`
  - `respx` で httpx mock → `fetch_series` の正規化確認
  - 欠損値（`"."`）の None 化を確認
  - `upsert_observations` は `MagicMock(Session)` での conflict 動作確認（既存 `test_candles.py` と同方針）
  - レート制限テストはスコープ外（実用ではほぼ発生しないため）

## 5. 既存資産との接続

- `src/db/connection.py` の `Base` / `SessionLocal` をそのまま使用
- Migration は `src/db/migrations/versions/003_macro_index_daily.py` として追加（`002_economic_event.py` が現行 head）
- Settings は既存 `settings.fred_api_key` / `settings.fred_base_url` を利用（追加なし）
- **前提条件確認済み**: `src/config.py` に `fred_api_key=""`, `fred_base_url="https://api.stlouisfed.org/fred"` 既存。`.env.example` にも `FRED_API_KEY` キー定義あり。settings の追加変更は不要

## 6. 非ゴール

- 月次・週次・四半期データ（FRED の他頻度シリーズ）は対象外
- リアルタイムストリーミング（FRED 自体が日次更新なので不要）
- マクロ指標から派生する primitive（M5/P7）の実装はこの TODO のスコープ外（別 TODO）
- **Revision 履歴の保持**（`realtime_start` / `realtime_end`）— 初期 5 シリーズは market-derived で revision されないため不要
- **Forward-fill / stale 制御 / as-of join** — 取り込みは生データのみ。「最新営業日値の引き継ぎ」「週末跨ぎの値伝播」「ペアデータとの as-of join」は全て primitive 側の責務
- **available_at 列の追加** — T+1 利用原則でカバーするため、初期スコープ外

## 7. 成功基準（acceptance）

機能要件:
1. **全シリーズ取得成功**: 指定 5 series（VIXCLS / DTWEXBGS / DGS10 / DGS2 / T10YIE）全てで `series_id` ごとに 1 行以上の row が DB に挿入される（部分失敗を見逃さない）
2. **欠損 NULL 保存**: FRED 応答中の `value="."` の observation が DB 上で `value IS NULL` で保存される
3. **Idempotency**: 同一期間で再実行した際、(a) row count が変わらない、(b) `value` が API 最新値で上書きされる、(c) `fetched_at` のみ更新される
4. **Retry 動作**: 429 / 5xx / TimeoutException で 3 回までリトライしてから raise（テストで mock した sequence で確認）
5. **Series 別 row count 健全性**: 3 年取得後、各 series が「0 件ではない」かつ「極端に少なくない」（target: 期間営業日数 ~750 のオーダーで、初回ベースラインを記録し以降の差分監視に使う）。固定閾値での合否判定はしない（FRED の各シリーズは営業日ベースで欠損 `.` を含むため、暦日近くまで埋まる前提は brittle）

品質ゲート:
6. `tests/ingest/test_fred.py` が pytest で全通過
7. `uv run mypy src/ingest/fred.py` がクリーン
8. `uv run ruff check src/ingest/ tests/ingest/` がクリーン

## 8. リスク・既知の制約

- **欠損値**: FRED の `value` は文字列で `"."` を含むため、Decimal 変換時に None ハンドル必須
- **頻度の混在**: 営業日のみ値があるシリーズ（VIXCLS, DTWEXBGS, T10YIE）vs 暦日近くまで値があるシリーズ（DGS10, DGS2）が混在 — テーブル uniqueness では問題ないが、downstream join では「forward-fill 可否 / 最大 stale 日数 / 週末跨ぎ」を primitive 側が定義する責務（ingest スコープ外）
- **Look-ahead bias**: `date=D` の値を `D` 当日の intraday 判断に使うと bias。本設計では T+1 利用原則で対処（§3 Look-ahead 契約参照）
- **Revision risk**: 初期 5 シリーズは market-derived のため revision されないが、将来 CPI 等を追加する際には別設計（`realtime_start`/`realtime_end`）が必要
- **Series ID の typo**: FRED は不正 series_id でも 200 を返し空配列にする場合がある。row count 0 のシリーズを警告ログに出す
- **API key 未設定**: `FRED_API_KEY` 空のままだと 400 が返る。CLI 起動時に early-fail で警告出力
