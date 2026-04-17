# Phase 0 詳細設計 — 骨格構築

**作成**: 2026-04-17 18:30 JST
**更新**: 2026-04-17 JST（technical-design-review 反映: 依存関係整備・スキーマ補足・キャッシュ設計・config 設計追記）
**前提**: [../20260417-1700-initial-design/conceptual-design.md](../20260417-1700-initial-design/conceptual-design.md)（概念設計）
**状態**: REVIEWED

---

## 1. スコープ

Phase 0 は「FX 取引システムを実装するための土台整備」。コードは最小限、設定とスキーマ骨格が中心。

**含む**:
- Python/uv 環境、依存関係、lint/format 設定
- PostgreSQL + Alembic マイグレーション基盤
- ディレクトリ構造の確定
- OANDA v20 API クライアントの最小実装（疎通確認のみ）
- DB スキーマ骨格（`currency_pair`, `price_bar_m1`）
- コストモデル・マージンルールの OANDA 準拠設計方針（実装は Phase 2）

**含まない**:
- ヒストリカルデータ一括取得（Phase 1）
- バックテストエンジン実装（Phase 2）
- Paper Trading 実装（Phase 3）
- Dramatiq/RabbitMQ 導入（Phase 3 以降で必要になれば）

**完了判定**: §13 を参照。

---

## 2. 確定事項（概念設計から継承）

- **データソース**: OANDA v20 API、demo 口座（`api-fxpractice.oanda.com`）
- **初期通貨ペア**: USD/JPY（OANDA 表記: `USD_JPY`）
- **データ粒度**: 1 分足（`granularity=M1`）、bid/ask 両取得（`price=BA`）
- **レバレッジ**: 1〜25 倍の可変パラメータ。MockBroker で実マージンコールをモデル化
- **通貨ペア拡張**: Phase 4 以降

---

## 3. ディレクトリ構成

zenigame の構成を参考にしつつ、FX 特有の区分を導入する。

```
zenigame-fx/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── .env                    # ローカル（gitignore）
├── .python-version
├── alembic.ini
├── ruff.toml               # or pyproject.toml 内 [tool.ruff]
├── docker-compose.yml
├── docker/
│   └── postgres/
│       └── init.sql        # 拡張（uuid-ossp 等）初期化
├── src/
│   ├── __init__.py
│   ├── config.py           # 環境変数ローダー
│   ├── api/
│   │   ├── __init__.py
│   │   ├── cache/          # diskcache ラッパー
│   │   │   ├── __init__.py
│   │   │   └── http_cache.py
│   │   └── oanda/
│   │       ├── __init__.py
│   │       ├── client.py       # 認証・base URL 切替・リトライ
│   │       ├── endpoints.py    # candles / pricing / instruments / account
│   │       ├── models.py       # レスポンス dataclass（型付け）
│   │       └── rate_limit.py   # OANDA レート制限対応
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   ├── models.py           # SQLAlchemy モデル
│   │   └── migrations/         # Alembic versions
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── instrument.py       # CurrencyPair ドメインオブジェクト
│   │   └── price.py            # PriceBar
│   └── utils/                  # Phase 1 で追加（time.py: UTC⇔JST 変換等）
├── scripts/
│   ├── init.sh             # 初回セットアップ（uv sync → docker-compose up → alembic upgrade）
│   └── oanda_ping.py       # 疎通確認 + USD_JPY メタ表示 + currency_pair テーブルへの初回投入
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   │   └── oanda/          # OANDA レスポンス JSON サンプル
│   ├── api/
│   │   └── test_oanda_client.py
│   ├── db/
│   │   └── test_models.py
│   └── domain/             # ドメインオブジェクトのユニットテスト（Phase 0 は空可）
├── docs/
│   └── (空。Phase 1 以降に追加)
├── devnotes/
│   ├── 20260417-1700-initial-design/
│   └── 20260417-1830-phase0-detailed-design/
└── .gitignore
```

**設計判断**:
- `src/api/oanda/` を専用サブパッケージにする（zenigame では `src/api/jquants_client.py` 等フラット。今後 OANDA 以外のデータソース追加を見据えて最初から階層化）。
- `src/trading/` は **Phase 2 で追加**。Phase 0 では作らない。
- `src/queue/` は **Phase 3 以降で必要になった時に追加**。最初から作らない（YAGNI）。
- `src/domain/` を用意し、DB モデルと API クライアント両方から参照される「通貨ペア」「価格バー」等を一元化。zenigame は実運用中に後付けで分離した経緯があり、最初から分離する。

---

## 4. Python / uv 設定

- **Python**: 3.11（zenigame と揃える）。`.python-version` に記載。
- **パッケージマネージャ**: uv（`uv sync --dev`, `uv run`）。
- **仮想環境**: `.venv/`（uv デフォルト、gitignore）。

### pyproject.toml 依存関係（初期セット）

**本体**:
- `sqlalchemy >= 2.0`
- `alembic`
- `psycopg[binary] >= 3.1` — SQLAlchemy 2.x 推奨ドライバ
- `httpx` — OANDA HTTP クライアント（requests より async 対応、型付け良好）
- `tenacity` — httpx リトライ（exponential backoff）
- `diskcache` — HTTP レスポンスキャッシュ（zenigame と同じ戦略）
- `pydantic >= 2` — OANDA レスポンス dataclass 定義（Decimal 対応）
- `pydantic-settings` — `BaseSettings` による環境変数ローダー（pydantic v2 では別パッケージ）
- `structlog` — 構造化ログ（後段 Paper Trading の監査証跡で活用）

**開発**:
- `pytest`
- `pytest-asyncio` — httpx の async テスト
- `pytest-cov`
- `pytest-mock`
- `ruff` — lint + format（black 不使用）
- `mypy`（optional、型エラー警告のみ）
- `respx` — httpx モック（OANDA レスポンスのスタブに使用）

**意図的に除外**（Phase 3 以降で導入）:
- `dramatiq`, `pika` — タスクキュー
- `playwright` — FX ではほぼ不要
- `anthropic` 等 LLM SDK — Phase 4 以降
- `pandas` — 現段階では明確な必要性なし。DB 直 SQL と dataclass で十分。Phase 2 のバックテストで必要になったら追加

### ツール設定

**ruff**: `line-length = 120`, `select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]`、`target-version = "py311"`。  
**mypy**: `strict = false`（導入段階）、`python_version = "3.11"`、`plugins = ["pydantic.mypy"]`。  
**pytest**: `testpaths = ["tests"]`, `asyncio_mode = "auto"`。

### `src/config.py` 設計方針

pydantic v2 の `BaseSettings` を使用。`.env` からの読み込みと環境変数の型変換・バリデーションを一元化する。

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    oanda_env: str = "practice"
    oanda_account_id: str
    oanda_api_token: str
    oanda_base_url_practice: str = "https://api-fxpractice.oanda.com"
    oanda_base_url_live: str = "https://api-fxtrade.oanda.com"
    database_url: str
    diskcache_dir: str = ".cache/http"
    log_level: str = "INFO"
    log_format: str = "json"

    @property
    def oanda_base_url(self) -> str:
        return self.oanda_base_url_practice if self.oanda_env == "practice" else self.oanda_base_url_live

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
```

`pydantic-settings` を本体依存に追加する（pydantic v2 では別パッケージ）。`.env.example` と `Settings` フィールドが 1:1 対応するため、追加フィールドが必要になったら両方を同時に更新する。

---

## 5. 環境変数と `.env.example`

```dotenv
# OANDA
OANDA_ENV=practice                    # practice | live
OANDA_ACCOUNT_ID=
OANDA_API_TOKEN=                      # Bearer token
OANDA_BASE_URL_PRACTICE=https://api-fxpractice.oanda.com
OANDA_BASE_URL_LIVE=https://api-fxtrade.oanda.com

# Database
DATABASE_URL=postgresql+psycopg://zenigame_fx:zenigame_fx_dev@localhost:15433/zenigame_fx

# Cache
DISKCACHE_DIR=.cache/http

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json                       # json | console
```

**設計判断**:
- PostgreSQL ポートは **15433**（zenigame の 15432 と衝突回避。両プロジェクトを同時起動する可能性を想定）。
- DB 名・ユーザも `zenigame_fx` で分離。
- `OANDA_ENV` の切り替えで practice/live を選ぶ。Phase 0〜4 は practice 固定、Phase 5 移行時に live を導入。
- API トークンは `.env` のみ、コミット禁止。

---

## 6. PostgreSQL — docker-compose.yml

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: zenigame_fx
      POSTGRES_PASSWORD: zenigame_fx_dev
      POSTGRES_DB: zenigame_fx
    ports:
      - "15433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./docker/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U zenigame_fx"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  pgdata:
```

Phase 0 では **RabbitMQ は含めない**。Phase 3 以降で必要になった時点で追加。

---

## 7. Alembic 初期化

- `uv run alembic init src/db/migrations`
- `alembic.ini` の `script_location = src/db/migrations`
- `env.py` で `DATABASE_URL` を `src.config.settings.database_url` 経由で取得（`pydantic-settings` が `.env` の読み込みと環境変数フォールバックを統合して処理する）
- 初回 revision: `001_initial_schema.py`（§9 のスキーマを生成）

---

## 8. DB スキーマ骨格（OANDA 準拠）

### 8.1 `currency_pair`

OANDA の `GET /v3/accounts/{accountID}/instruments` レスポンスを保存する。

| カラム | 型 | 備考 |
|-------|----|------|
| `id` | SERIAL PK | |
| `oanda_name` | VARCHAR(20) UNIQUE NOT NULL | 例: `USD_JPY` |
| `display_name` | VARCHAR(20) NOT NULL | 例: `USD/JPY` |
| `base_currency` | CHAR(3) NOT NULL | `USD_JPY` なら `USD` |
| `quote_currency` | CHAR(3) NOT NULL | `USD_JPY` なら `JPY` |
| `pip_location` | SMALLINT NOT NULL | OANDA `pipLocation`（例: `USD_JPY` は -2、`EUR_USD` は -4） |
| `display_precision` | SMALLINT NOT NULL | 価格表示桁数 |
| `trade_units_precision` | SMALLINT NOT NULL | 発注単位精度 |
| `margin_rate` | NUMERIC(6,4) NOT NULL | OANDA の instrument メタ（例: 0.05 = 20倍相当）。実際の適用レバレッジは別途 `strategy` 側で指定 |
| `minimum_trade_size` | BIGINT NOT NULL | OANDA `minimumTradeSize`（通常 1） |
| `maximum_order_units` | BIGINT NOT NULL | |
| `instrument_type` | VARCHAR(20) NOT NULL | OANDA `type` (例: `CURRENCY`) |
| `is_active` | BOOLEAN NOT NULL DEFAULT true | |
| `fetched_at` | TIMESTAMPTZ NOT NULL | OANDA から取得した時刻（メタ情報の鮮度） |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

**設計判断**:
- `oanda_name` を一意キーに。アプリ内部も基本 `USD_JPY` 形式で統一（スラッシュ表記は表示時のみ）。
- `margin_rate` は OANDA の instrument 固有値（業者側が定める）。**取引側のレバレッジ指定とは別**であることを明示する（後者は `strategy_config` 等で個別管理）。
- zenigame の `Security` テーブルを参考にしたが、FX 固有のフィールド（pip_location 等）を一級市民に。

### 8.2 `price_bar_m1`

OANDA の candles エンドポイントで取得した 1分足を保存。

| カラム | 型 | 備考 |
|-------|----|------|
| `id` | BIGSERIAL PK | |
| `pair_id` | INTEGER FK → currency_pair | |
| `bar_time` | TIMESTAMPTZ NOT NULL | OANDA `time`（UTC、バー開始時刻） |
| `open_bid` | NUMERIC(12,6) NOT NULL | |
| `high_bid` | NUMERIC(12,6) NOT NULL | |
| `low_bid` | NUMERIC(12,6) NOT NULL | |
| `close_bid` | NUMERIC(12,6) NOT NULL | |
| `open_ask` | NUMERIC(12,6) NOT NULL | |
| `high_ask` | NUMERIC(12,6) NOT NULL | |
| `low_ask` | NUMERIC(12,6) NOT NULL | |
| `close_ask` | NUMERIC(12,6) NOT NULL | |
| `volume` | BIGINT NOT NULL | OANDA が返す疑似ボリューム（tick count ベース）。INTEGER でも実質溢れないが将来の粒度変更に備えて BIGINT |
| `complete` | BOOLEAN NOT NULL | OANDA `complete` をそのまま |
| `created_at` | TIMESTAMPTZ | |

**インデックス・制約**:
- `UNIQUE(pair_id, bar_time)` — 同じ時刻の重複投入を防ぐ
- `INDEX(pair_id, bar_time DESC)` — 直近バー検索用
- `pair_id` FK は `ON DELETE RESTRICT`（通貨ペアの誤削除によるデータ消失を防ぐ）

**設計判断**:
- **bid と ask を 4 本値ずつ保存**（mid は保存しない。スプレッド計算の精度を保つため常に bid/ask から導出）。OANDA も mid は別パラメータ `M` で返すが、情報量は bid/ask が上位集合。
- `NUMERIC(12,6)` は USD/JPY（5 桁小数まで、例: `154.123`）と EUR/USD（6 桁小数、例: `1.08765`）の両方をカバー。
- `bar_time` は **UTC で統一**（サマータイム対策、概念設計で合意済み）。
- `complete=false` のバー（形成中バー）もとりあえず保存許容。Phase 1 で要否を再評価。
- ボリューム (OANDA の volume) は tick count 相当。約定高ではないことをコメントで明記。

### 8.3 将来拡張テーブル（Phase 0 では作らない）

- `economic_event` — Phase 2 以降
- `strategy_config` — Phase 2（レバレッジ・ロット指定含む）
- `order` / `position` / `trade` / `account_snapshot` — Phase 3（Paper Trading）
- `pnl_daily` — Phase 3

---

## 9. OANDA v20 API クライアント設計

### 9.1 環境切替

- `OANDA_ENV=practice` → base URL は `api-fxpractice.oanda.com`
- `OANDA_ENV=live` → `api-fxtrade.oanda.com`
- `OANDA_API_TOKEN` は Bearer で全リクエストに付与
- Stream 用 URL（`stream-fxpractice.oanda.com`）は Phase 4 以降で必要になったら追加

### 9.2 使用エンドポイント（Phase 0 〜 1）

| エンドポイント | 用途 | Phase |
|--------------|------|-------|
| `GET /v3/accounts/{accountID}` | 疎通確認、残高取得 | 0 |
| `GET /v3/accounts/{accountID}/instruments` | 通貨ペアマスタ取得 | 0-1 |
| `GET /v3/instruments/{instrument}/candles` | ヒストリカル/最新 candles | 1 |
| `GET /v3/accounts/{accountID}/pricing` | リアルタイム bid/ask | 3 |

### 9.3 リクエスト設計

- **HTTP クライアント**: `httpx.Client`（同期）+ `httpx.AsyncClient`（Phase 3 で併用）。タイムアウト 10s、リトライは tenacity で exponential backoff（最大 3 回）
- **エラーマッピング**: 401 → 認証エラー例外、429 → レート制限例外、5xx → 一時障害例外。業務ロジック側が `except` しやすい階層化
- **リクエスト識別**: OANDA の `RequestID` レスポンスヘッダをログに記録
- **型付け**: pydantic BaseModel で candles/pricing/instruments レスポンスを定義。`Decimal` フィールドで価格を受ける（str → Decimal へ明示変換）

### 9.4 レート制限

OANDA の公式上限は「1 秒あたり 100 リクエスト」（接続単位、v20）。Phase 0 時点では単一接続での低頻度アクセスなので実質ヒットしない。`rate_limit.py` では token bucket 型の最小限実装（閾値は 50 req/sec に安全側設定）。

### 9.5 キャッシュ戦略

- **ヒストリカル candles**（過去の `complete=true` バー）: diskcache で**永続キャッシュ**。キー = `(instrument, granularity, from, to, price)` の tuple。zenigame の `src/api/cache/` パターンを踏襲。**キャッシュ対象は `to` が現在時刻より十分過去（例: 直近バー形成時刻より前）のリクエストに限定し、`complete=false` バーを含む可能性があるリクエスト結果はキャッシュしない**。具体的には Phase 1 実装時に「キャッシュ可否判定」ロジックを組み込む
- **リアルタイム pricing**: **キャッシュしない**（概念設計 §7 で合意）
- **instruments メタ**: 短期 TTL（6 時間）でキャッシュ。日次更新想定

### 9.6 疎通確認スクリプト

`scripts/oanda_ping.py`:
- `GET /v3/accounts/{accountID}` を叩いて残高・通貨・`marginRate` を表示
- `GET /v3/accounts/{accountID}/instruments` から `USD_JPY` のメタを抽出して表示
- 成功すれば Phase 0 完了判定の一項目を満たす
- **DB 書き込みも兼任**: 取得した `USD_JPY` メタを `currency_pair` テーブルへ UPSERT する（疎通確認と初期データ投入を 1 スクリプトにまとめることで、完了判定 #4/#5 を同時に検証できる）。「責務の混在」ではあるが Phase 0 の最小スクリプト原則を優先する。Phase 1 移行時に取得ロジックを `src/api/oanda/` 内に切り出す

---

## 10. コストモデル・マージンルール（OANDA 準拠、Phase 2 実装・ここでは方針のみ）

### 10.1 スプレッド（MVP 割り切り）

- OANDA の candles レスポンス `bid.c` / `ask.c` を「その時点のスプレッド」として採用
- バックテスト: バー close 時点の bid/ask 差をそのまま約定コストとみなす
- Paper Trading: `GET pricing` の最新 `bids[0].price` / `asks[0].price` を使用
- **スリッページはゼロ**として計算（概念設計で合意済み）

### 10.2 ファイナンシング（スワップ）

OANDA は「ポジション保有中の finance 計算を tick 単位で行う」特殊なモデル。詳細実装は Phase 2 で調整するが、MVP 方針として:

- 日次ロールオーバーではなく、**OANDA の financing を都度計算**する近似を採用（秒単位金利差）
- 公式 API `GET /v3/accounts/{accountID}/transactions` の `DAILY_FINANCING` を Paper Trading 時は参照可
- バックテスト: ポジション保有秒数 × `(base_financing_rate - quote_financing_rate) / seconds_per_year × position_notional` で近似。**金利データは OANDA の `GET /v3/instruments/{instrument}` メタから取得**（Phase 2 で確定）

### 10.3 マージン計算

OANDA のマージン計算式（公式）:

```
margin_required = |units| × price_in_home_currency × marginRate
```

- `marginRate` は instrument メタから取得（例: 主要通貨 0.02 = 50倍相当、JPY クロス 0.04 = 25倍相当等、業者・規制によって変動）
- **適用レバレッジの上限**は `1 / marginRate`。**本プロジェクトの「1〜25 倍」はこの上限内でさらに制限**する形を採る
- Paper Trading の MockBroker では、`margin_required` と残高の比から「証拠金維持率」を算出し、閾値割れで強制ロスカット

### 10.4 ロット単位（units）

OANDA は**株数に相当する「units」単位**で発注。`minimumTradeSize=1`、`maximumOrderUnits=100000000` が標準。「1 lot = 100000 units」のような抽象化レイヤは設けず、units 直接指定で設計する（国内業者に移行する際は業者側抽象化レイヤで吸収）。

### 10.5 手数料

OANDA は**手数料ゼロ**、コストはスプレッドとファイナンシングのみ。MVP では手数料フィールドは保持しつつ値は 0 固定。将来の業者差分を吸収する準備として。

---

## 11. キャッシュ設計

`src/api/cache/http_cache.py`:
- `diskcache.Cache(directory)` ラッパー
- キー生成: `hashlib.sha256(endpoint + json.dumps(params, sort_keys=True)).hexdigest()` でファイル名衝突回避。`sort_keys=True` により dict キー順序の揺れを排除
- TTL なし（ヒストリカルデータは永続）
- instruments メタ専用のショート TTL キャッシュを別インスタンスで用意

zenigame の構造を踏襲しつつ、namespace 構造は最初から FX 向けに整理:
```
.cache/http/oanda/candles/
.cache/http/oanda/instruments/
```

---

## 12. テスト戦略

- **ユニットテスト**: 各関数は mock で外部依存を遮断
- **OANDA クライアント**: `respx` で httpx 通信をスタブ化。`tests/fixtures/oanda/` に実レスポンス JSON を保存（初回は手動取得、以降は固定）
- **DB**: `tests/conftest.py` で pytest-postgresql あるいは Testcontainers を用意（後者を推奨、Docker さえあれば動く）。**テスト用 DB は本番と別**
- **型チェック**: `uv run mypy src/` を CI に入れる（warning のみ、fail させない）
- **lint**: `uv run ruff check src/ tests/` + `uv run ruff format --check`

**CI**: 初期は GitHub Actions の yaml だけ用意（実行は手元で十分。Phase 1 以降で PR ベース CI を本格化）。

---

## 13. 完了判定

Phase 0 完了 = 以下全てが成立する状態:

1. `bash scripts/init.sh` で 0 から環境構築できる（`uv sync`, `docker-compose up -d db`, `uv run alembic upgrade head`）
2. `uv run pytest` が green（実装済みテストのみ。空テスト可）
3. `uv run ruff check src/ tests/` が green
4. `uv run python scripts/oanda_ping.py` で OANDA demo 口座に接続成功し、`USD_JPY` の instrument メタ（`pipLocation`, `marginRate` 等）を表示できる
5. PostgreSQL に `currency_pair` / `price_bar_m1` テーブルが作成されており、`USD_JPY` が 1 行投入済み（`scripts/oanda_ping.py` の副作用として実行してもよい）
6. AGENTS.md / README.md / devnotes が最新状態でコミットされている

---

## 14. 次のアクション

1. 本設計のレビュー（`/technical-design-review` 推奨）
2. Phase 0 実装着手（レビュー反映後）
3. 完了後、Phase 1 詳細設計（ヒストリカルデータ取得）に進む

---

## 15. 既知のリスク・先送り事項

- **OANDA financing の正確な計算式**: 公式ドキュメントに完全な式が無く、transactions API のログから逆算する必要がある可能性。Phase 2 で深掘り
- **financing 近似式の `seconds_per_year` 定義**: 365×24×3600 = 31536000 か 365.25×24×3600 か、OANDA 定義に合わせるかは Phase 2 で確定する
- **home currency の扱い**: OANDA 口座は home currency（JPY/USD 等）を持ち、PnL はこの通貨に換算される。「JPY 建て口座で USD_JPY を取引」「USD 建て口座で USD_JPY を取引」で挙動が微妙に変わる。demo 口座作成時に **JPY 建て口座** を選び一貫させる方針
- **タイムゾーン処理**: OANDA は UTC。DB も UTC。表示時のみ JST 変換。この変換を一箇所に集約する `src/utils/time.py` を Phase 1 で追加
- **NUMERIC(12,6) の精度**: 現在の対象通貨ペア（USD/JPY、EUR/USD 等の主要ペア）では問題ない。将来的に JPY が基軸通貨になるペア（例: JPY/USD = 1/154 ≒ 0.00649...）を扱う場合は小数部 8 桁以上が必要になる可能性あり。Phase 4 の通貨ペア拡張時に再評価する
- **`complete=false` バーの UPSERT**: 同一 `(pair_id, bar_time)` で `complete=false` → `complete=true` に更新される際、UNIQUE 制約がある状態で INSERT すると競合する。Phase 1 で UPSERT（ON CONFLICT DO UPDATE）方針を明示する
- **WebSocket（streaming pricing）**: Phase 4 以降。Phase 3 までは polling 方式で許容
