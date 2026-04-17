# Phase 1 詳細設計 — ヒストリカル & インクリメンタル取得

**作成**: 2026-04-17 22:00 JST
**前提**: [../20260417-1700-initial-design/conceptual-design.md](../20260417-1700-initial-design/conceptual-design.md), [../20260417-1830-phase0-detailed-design/detailed-design.md](../20260417-1830-phase0-detailed-design/detailed-design.md)
**状態**: DRAFT

---

## 1. スコープ

Phase 1 は「OANDA から USD/JPY の 1 分足を取得して DB に蓄積するパイプライン」。

**含む**:
- OANDA candles エンドポイントのページング対応
- ヒストリカル取得スクリプト（過去 N 日分、1 年デフォルト）
- インクリメンタル取得スクリプト（直近の完成バーを拾う）
- price_bar_m1 への UPSERT
- ヒストリカルの HTTP キャッシュ（complete=true バーのみ）
- UTC⇔JST 変換ユーティリティ（`src/utils/time.py`）

**含まない**:
- WebSocket streaming（Phase 4 以降）
- 複数通貨ペア並列取得（Phase 4 以降）
- マイクロ秒精度の tick 取得（Phase 2 以降、必要時）

---

## 2. OANDA API の挙動確認（公式ドキュメントから）

- endpoint: `GET /v3/instruments/{instrument}/candles`
- 1 リクエストあたり最大 **5000 candles**（`count` パラメータ、デフォルト 500）
- `count` と `from+to` 同時指定時は **`count` が無視され時間範囲と granularity が優先**される
- `from` のみ + `count` 指定時は `from` から count 件を返す
- `includeFirst` (default `true`) — `false` にすると `from` で指定したバーを除外。ページング時の重複排除に使う
- `price=BA` で bid/ask 両方取得
- 市場休止（土日など）は単に該当バーが返らない（欠番）
- `complete=false` は形成中の最新バー（まだクローズしていない）
- 時刻は **UTC、RFC3339 ナノ秒精度**（`2016-10-17T15:07:00.000000000Z`）

---

## 3. ページング方針

**採用方式**: `from` + `count=5000` + `includeFirst=false` ループ。

```
cursor = start_time
first_request = True
while True:
    candles = GET candles(from=cursor, count=5000, includeFirst=first_request)
    if not candles: break
    for c in candles:
        if c.time >= end_time: return
        yield c
    cursor = candles[-1].time          # 最後のバー時刻を次の from に
    first_request = False              # 2 回目以降は include_first=false で重複除外
```

**理由**:
- `from`+`to` で時間範囲指定する方式は count ≤ 5000 の保証が無く、「範囲が狭すぎてゼロ件」か「範囲が広すぎて切り捨て」のリスクがある
- `includeFirst=false` は公式が推奨するページング手法（仕様書の `includeFirst` 説明欄参照）
- 1 年分 M1 ≈ 週末除外で約 370,000 バー → 約 74 リクエスト。TokenBucket 50 req/s なら ~1.5 秒で完了

---

## 4. キャッシュ方針

**キャッシュ対象**:
- `to` 相当の境界（= `cursor + count × granularity_delta`）が**現在時刻より 1 時間以上過去**のリクエストのみ
- 理由: 直近バーは `complete=false` が混入する可能性があるため、永続キャッシュに残すと古い「形成中」データを引いてしまう

**キャッシュキー**: `(instrument, granularity, from, count, includeFirst, price)` を JSON 化して SHA256

**namespace**: `.cache/http/oanda/candles/`

**TTL**: 無し（永続）

---

## 5. DB UPSERT 方針

- テーブル: `price_bar_m1`
- 制約: `UNIQUE(pair_id, bar_time)`
- UPSERT: `ON CONFLICT (pair_id, bar_time) DO UPDATE` で全カラム更新
- **MVP では `complete=false` バーは保存しない**（スキップ）。Phase 3 の Paper Trading で必要になったら再検討
- バルクインサート: 5000 件単位で一括コミット（chunk 境界）

---

## 6. CLI 設計

### 6.1 `scripts/fetch_historical.py`

```
uv run python scripts/fetch_historical.py \
    --instrument USD_JPY \
    --days 365 \
    [--end 2026-04-17T00:00:00Z]
```

- デフォルト: 現在時刻の 1 時間前を end、そこから 365 日遡った時刻を start
- 進捗は 5000 件 chunk 単位で標準エラーに出力
- 成功時: 取得件数・スキップ件数・DB 書き込み件数を表示

### 6.2 `scripts/fetch_incremental.py`

```
uv run python scripts/fetch_incremental.py \
    --instrument USD_JPY \
    [--count 60]
```

- 最新 `count` 本（デフォルト 60 = 直近 1 時間分）を取得
- `complete=false` はスキップ
- UPSERT 件数を表示
- cron / systemd timer からの 1 分周期起動を想定

---

## 7. ディレクトリ構成の追加

```
src/
├── ingest/                    # ← 新規（データ取得層）
│   ├── __init__.py
│   └── candles.py             # CandleFetcher + store_bars
└── utils/                     # ← 新規
    ├── __init__.py
    └── time.py                # rfc3339_utc, now_utc, granularity_delta
scripts/
├── fetch_historical.py        # ← 新規
└── fetch_incremental.py       # ← 新規
tests/
├── ingest/
│   ├── __init__.py
│   └── test_candles.py        # ← 新規（respx モック + in-memory SQLite で UPSERT テスト）
└── utils/
    ├── __init__.py
    └── test_time.py
```

**設計判断**:
- `src/ingest/` は「OANDA → DB」の取り込みを担当。将来 Dukascopy 等の別ソースが増えたら `src/ingest/oanda/` と下層に移行
- `src/etl/`（zenigame の命名）を使わない理由: ETL は Transform が重い場合の命名。Phase 1 は単純な Extract+Load なので `ingest` にとどめる

---

## 8. エラーハンドリング

- `OandaAuthError` (401): 即時停止、原因は token 設定ミス。CLI は exit 2
- `OandaRateLimitError` (429): tenacity の retry で吸収（既存実装）
- `OandaServerError` (5xx): tenacity retry
- `httpx.TransportError`: tenacity retry
- バリデーションエラー（pydantic）: そのまま raise、CLI は exit 1
- DB エラー: そのまま raise、CLI は exit 1

---

## 9. テスト戦略

- `test_candles.py`:
  - respx で OANDA 複数ページ応答をスタブ
  - ページング境界（最終 chunk が 5000 未満、end 時刻を超えるバー）をカバー
  - `complete=false` バーがスキップされること
  - in-memory SQLite で UPSERT 再実行時に重複が発生しないこと（実 DB は CI で）
- `test_time.py`:
  - rfc3339_utc は常に末尾 `Z`、ミリ秒精度
  - granularity_delta は M1→60s, M5→300s, H1→3600s 等

---

## 10. 完了判定

1. `uv run python scripts/fetch_historical.py --instrument USD_JPY --days 1` で USD/JPY の直近 1 日分（約 1440 バー × 週末考慮で少なくとも 500 以上）が取得され DB に入る
2. `uv run python scripts/fetch_incremental.py --instrument USD_JPY --count 10` で最新 10 本前後が UPSERT される（2 回実行しても重複増えない）
3. ページングテスト・UPSERT テストが green
4. `uv run ruff check && uv run pytest` が green

---

## 11. 先送り事項

- `complete=false` バー保存戦略（Phase 3 で要検討: Paper Trading 用途）
- 取得失敗時の再実行（part を記録して途中から再開）— Phase 2 以降
- ギャップ検出（欠番バーの可視化）— Phase 2 以降
- 複数通貨ペア並列取得 — Phase 4
