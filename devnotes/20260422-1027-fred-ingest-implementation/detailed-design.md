# 詳細設計: FRED API ingest

- 作成日時: 2026-04-22 10:27 JST
- 関連: `conceptual-design.md`（同フォルダ）
- ステータス: Draft

---

## 0. 実装ファイルリスト

| ファイル | 種別 | 概要 |
|---------|------|------|
| `src/ingest/fred.py` | 新規 | `fetch_series` / `upsert_observations` |
| `scripts/fetch_fred.py` | 新規 | CLI エントリポイント |
| `src/db/models.py` | 修正 | `MacroIndexDaily` ORM 追加 |
| `src/db/migrations/versions/003_macro_index_daily.py` | 新規 | テーブル DDL |
| `tests/ingest/test_fred.py` | 新規 | unit + integration テスト |

設定変更なし（`src/config.py` / `.env.example` 既存のまま使用）。

---

## 1. データモデル

### 1.1 ORM (`src/db/models.py`)

`EconomicEventRow` の直後に追加:

```python
class MacroIndexDaily(Base):
    __tablename__ = "macro_index_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    series_id: Mapped[str] = mapped_column(String(20), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("series_id", "date", name="uq_macro_index_daily_series_date"),
        Index("ix_macro_index_daily_series_date", "series_id", "date"),
    )
```

import 追加: `from datetime import date`, `from sqlalchemy import Date`。

### 1.2 Alembic migration (`003_macro_index_daily.py`)

```python
"""macro_index_daily table

Revision ID: 003
Revises: 002
Create Date: 2026-04-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "macro_index_daily",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("series_id", sa.String(length=20), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(18, 6), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("series_id", "date", name="uq_macro_index_daily_series_date"),
    )
    op.create_index(
        "ix_macro_index_daily_series_date",
        "macro_index_daily",
        ["series_id", "date"],
    )


def downgrade() -> None:
    op.drop_index("ix_macro_index_daily_series_date", table_name="macro_index_daily")
    op.drop_table("macro_index_daily")
```

---

## 2. クライアント実装 `src/ingest/fred.py`

### 2.1 シグネチャと公開 API

```python
from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.config import settings
from src.db.models import MacroIndexDaily
from src.utils.time import now_utc

logger = structlog.get_logger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3  # 総試行回数（初回 + 2 リトライ）。"3 回までリトライ" の解釈ブレを避けるため Attempt ベースで命名
BACKOFF_BASE = 1.0  # 秒


@dataclass(frozen=True)
class FredObservation:
    series_id: str
    obs_date: date
    value: Decimal | None
    fetched_at: datetime


def fetch_series(
    series_id: str,
    start: date,
    end: date,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    client: httpx.Client | None = None,
) -> list[FredObservation]:
    """FRED の `/series/observations` から observation を取得して正規化する。

    - `value="."` は `None` として保持する
    - 429/5xx/Timeout/TransportError は exponential backoff で **総 MAX_ATTEMPTS 試行**
      （= 初回 1 回 + リトライ 最大 MAX_ATTEMPTS-1 回）までリトライ
    - 400/401/403 は即時 raise
    """


def upsert_observations(session: Session, rows: Iterable[FredObservation]) -> int:
    """`macro_index_daily` に ON CONFLICT (series_id, date) DO UPDATE で UPSERT する。

    戻り値は対象行数（insert + update を区別せず合算）。
    """
```

### 2.2 fetch_series 実装メモ

- `api_key` / `base_url` は引数省略時 `settings.fred_api_key` / `settings.fred_base_url` を使用
- `client` 省略時は内部で `httpx.Client(timeout=DEFAULT_TIMEOUT)` を `with` で管理
- エンドポイント: `f"{base_url}/series/observations"`
- params: `{"series_id": series_id, "observation_start": start.isoformat(), "observation_end": end.isoformat(), "file_type": "json", "api_key": api_key}`
- 値の正規化: `value_str = obs["value"]; value = None if value_str == "." else Decimal(value_str)`
- `obs_date = date.fromisoformat(obs["date"])`
- `fetched_at = now_utc()`（同一 fetch_series 呼び出し内では共通）
- ログ: `logger.info("ingest.fred.fetched", series_id=..., start=..., end=..., count=len(observations))`
- 0 件の場合は warning ログ（Series ID typo 検知用）

### 2.3 リトライロジック

```python
def _request_with_retry(
    client: httpx.Client, url: str, params: dict[str, Any]
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.get(url, params=params)
            if response.status_code in RETRYABLE_STATUS:
                logger.warning(
                    "ingest.fred.retry_status",
                    status_code=response.status_code,
                    attempt=attempt,
                    series_id=params.get("series_id"),
                )
                _sleep_backoff(attempt)
                continue
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            logger.warning(
                "ingest.fred.retry_exc",
                error=str(exc),
                attempt=attempt,
                series_id=params.get("series_id"),
            )
            _sleep_backoff(attempt)
    if last_exc is not None:
        raise last_exc
    response.raise_for_status()  # 最終 retry 後の retryable status を raise
    return response


def _sleep_backoff(attempt: int) -> None:
    time.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))
```

`raise_for_status()` は 400 / 401 / 403 を `httpx.HTTPStatusError` として即時 raise する（リトライ判定が優先されるのは RETRYABLE_STATUS のみ）。

### 2.4 upsert_observations

```python
def upsert_observations(session: Session, rows: Iterable[FredObservation]) -> int:
    payload = [
        {
            "series_id": r.series_id,
            "date": r.obs_date,
            "value": r.value,
            "fetched_at": r.fetched_at,
        }
        for r in rows
    ]
    if not payload:
        return 0
    stmt = insert(MacroIndexDaily).values(payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=["series_id", "date"],
        set_={"value": stmt.excluded.value, "fetched_at": stmt.excluded.fetched_at},
    )
    session.execute(stmt)
    session.commit()
    return len(payload)
```

---

## 3. CLI `scripts/fetch_fred.py`

```python
"""FRED API からマクロ指標日足を取得して macro_index_daily テーブルに UPSERT する。"""
from __future__ import annotations

import argparse
import sys
from datetime import date

import structlog

from src.config import settings
from src.db.connection import SessionLocal
from src.ingest.fred import fetch_series, upsert_observations

logger = structlog.get_logger(__name__)

DEFAULT_SERIES = ("VIXCLS", "DTWEXBGS", "DGS10", "DGS2", "T10YIE")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch FRED daily macro indicators")
    p.add_argument("--series", default=",".join(DEFAULT_SERIES), help="comma-separated series ids")
    p.add_argument("--from", dest="start", required=True, help="YYYY-MM-DD")
    p.add_argument("--to", dest="end", required=True, help="YYYY-MM-DD")
    args = p.parse_args(argv)

    if not settings.fred_api_key:
        print("[error] FRED_API_KEY is empty in settings/.env", file=sys.stderr)
        return 2

    series_list = [s.strip() for s in args.series.split(",") if s.strip()]
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start > end:
        print(f"[error] start ({start}) > end ({end})", file=sys.stderr)
        return 2

    total = 0
    empty_series: list[str] = []
    failed_series: list[tuple[str, str]] = []
    with SessionLocal() as session:
        for series_id in series_list:
            try:
                obs = fetch_series(series_id, start, end)
            except Exception as exc:  # noqa: BLE001 — CLI 境界で捕捉して継続
                failed_series.append((series_id, repr(exc)))
                print(f"[error] series={series_id} fetch_failed={exc!r}", file=sys.stderr)
                continue
            written = upsert_observations(session, obs)
            print(f"[done] series={series_id} fetched={len(obs)} upserted={written}")
            total += written
            if len(obs) == 0:
                empty_series.append(series_id)
    print(
        f"[summary] series={len(series_list)} total_upserted={total} "
        f"empty={empty_series} failed={[s for s, _ in failed_series]}"
    )
    # 部分失敗 (fetch error or 0 件) を見逃さない acceptance 要件のため非ゼロ終了
    if failed_series or empty_series:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`scripts/load_economic_events.py` と同パターン。`structlog` の loggin はライブラリ側の責務（CLI 自体は print も併用してオペレーション視認性を確保）。

---

## 4. テスト `tests/ingest/test_fred.py`

### 4.1 構成

ユニットテスト（mock 中心、デフォルト実行）:

| ケース | 確認内容 |
|--------|---------|
| `test_fetch_series_normalizes_observations` | 正常応答 → date / Decimal 変換 / fetched_at 付与 |
| `test_fetch_series_handles_missing_value_dot` | `value="."` が None 化される |
| `test_fetch_series_retries_on_429_then_succeeds` | 429 → 200 sequence で 1 回リトライしてから成功（attempt=2 で成功） |
| `test_fetch_series_raises_on_401` | 401 即時 raise（リトライしない） |
| `test_fetch_series_raises_after_max_attempts` | 5xx を MAX_ATTEMPTS 連続で返したら raise（試行回数を call_count で固定） |
| `test_fetch_series_returns_empty_list_when_no_observations` | 空配列応答時に `[]` を返す（warning ログは検証しない、ログは運用観点） |
| `test_upsert_observations_emits_on_conflict_do_update` | `MagicMock(Session)` で conflict 文が組まれることを確認 |
| `test_upsert_observations_returns_zero_for_empty_input` | 空入力で 0 を返す & session.execute 呼ばれない |

DB 統合テスト（testcontainers Postgres、`@pytest.mark.integration`）:

| ケース | 確認内容 |
|--------|---------|
| `test_upsert_observations_idempotent_on_repeat` | 同じ rows を 2 回 UPSERT → row count 不変、`fetched_at` のみ更新、`value` も最新で上書き、NULL も保持 |

実装方針:
- 既存 testcontainers 依存を活用し、`PostgresContainer("postgres:16")` で Postgres を一時起動
- `Base.metadata.create_all(engine)` で `macro_index_daily` を作成（migration を別経路で apply するより軽量）
- 1 ファイル内の session-scoped fixture で container を共有
- `pytest.ini_options` の `markers` に `integration` を登録（既存 `pyproject.toml` を確認し、未登録なら追加）

### 4.2 ログ検証方針

ログは運用視認性のためにあり、ユニットテストで構造を assert しない（`pytest-structlog` 導入は scope 外）。空配列応答 / リトライの「結果」は assertion で固定し、ログ出力は手動運用で確認する。

### 4.3 リトライテストの sleep スタブ

`monkeypatch.setattr("src.ingest.fred._sleep_backoff", lambda attempt: None)` でテスト時間を短縮する。

### 4.4 fixture / mock 例

```python
import pytest
import respx
from httpx import Response
from unittest.mock import MagicMock
from datetime import date
from decimal import Decimal

from src.ingest.fred import fetch_series, upsert_observations, FredObservation

BASE_URL = "https://api.stlouisfed.org/fred"


def _fred_response(observations: list[dict]) -> dict:
    return {
        "realtime_start": "2026-04-22",
        "realtime_end": "2026-04-22",
        "observation_start": "2026-04-14",
        "observation_end": "2026-04-21",
        "units": "lin",
        "output_type": 1,
        "file_type": "json",
        "order_by": "observation_date",
        "sort_order": "asc",
        "count": len(observations),
        "offset": 0,
        "limit": 100000,
        "observations": observations,
    }


@respx.mock
def test_fetch_series_normalizes_observations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.ingest.fred._sleep_backoff", lambda attempt: None)
    respx.get(f"{BASE_URL}/series/observations").mock(
        return_value=Response(
            200,
            json=_fred_response(
                [
                    {"realtime_start": "2026-04-22", "realtime_end": "2026-04-22", "date": "2026-04-14", "value": "16.42"},
                    {"realtime_start": "2026-04-22", "realtime_end": "2026-04-22", "date": "2026-04-15", "value": "."},
                ]
            ),
        )
    )
    obs = fetch_series("VIXCLS", date(2026, 4, 14), date(2026, 4, 15), api_key="dummy", base_url=BASE_URL)
    assert [(o.obs_date, o.value) for o in obs] == [
        (date(2026, 4, 14), Decimal("16.42")),
        (date(2026, 4, 15), None),
    ]
    assert all(o.series_id == "VIXCLS" for o in obs)
```

### 4.5 統合テスト雛形

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from src.db.connection import Base
from src.db.models import MacroIndexDaily
from src.ingest.fred import FredObservation, upsert_observations


@pytest.fixture(scope="module")
def pg_session():
    with PostgresContainer("postgres:16") as pg:
        engine = create_engine(pg.get_connection_url(), future=True)
        Base.metadata.create_all(engine, tables=[MacroIndexDaily.__table__])
        Session = sessionmaker(bind=engine, future=True)
        with Session() as s:
            yield s


@pytest.mark.integration
def test_upsert_observations_idempotent_on_repeat(pg_session) -> None:
    rows_v1 = [
        FredObservation("VIXCLS", date(2026, 4, 14), Decimal("16.42"), datetime(2026, 4, 22, tzinfo=UTC)),
        FredObservation("VIXCLS", date(2026, 4, 15), None, datetime(2026, 4, 22, tzinfo=UTC)),
    ]
    rows_v2 = [
        FredObservation("VIXCLS", date(2026, 4, 14), Decimal("16.50"), datetime(2026, 4, 23, tzinfo=UTC)),  # value 上書き
        FredObservation("VIXCLS", date(2026, 4, 15), None, datetime(2026, 4, 23, tzinfo=UTC)),              # NULL 保持
    ]
    upsert_observations(pg_session, rows_v1)
    upsert_observations(pg_session, rows_v2)

    # row count 不変
    rows = pg_session.query(MacroIndexDaily).order_by(MacroIndexDaily.date).all()
    assert len(rows) == 2
    assert rows[0].value == Decimal("16.50")  # 上書き
    assert rows[1].value is None              # NULL 保持
    # fetched_at が更新されている
    assert rows[0].fetched_at.day == 23
```

`pyproject.toml` の `[tool.pytest.ini_options]` に `markers = ["integration: requires running container"]` を確認・追加する。Default 実行は `pytest -m "not integration"` で除外（pyproject の現状を確認、未設定なら CI 戦略は別 TODO）。

---

## 5. 動作確認手順

D 章（Autopilot 指示書）に従う:

1. `cd worktrees/todo-T004 && uv sync`
2. `uv run alembic upgrade head` → `macro_index_daily` 作成確認
3. `uv run python scripts/fetch_fred.py --series VIXCLS --from 2026-04-14 --to 2026-04-21`
4. `docker exec zenigame-fx-db-1 psql -U zenigame_fx -d zenigame_fx -c "SELECT count(*) FROM macro_index_daily WHERE series_id='VIXCLS';"`
5. `uv run python scripts/fetch_fred.py --series VIXCLS,DTWEXBGS,DGS10,DGS2,T10YIE --from 2023-04-23 --to 2026-04-21`
6. `uv run pytest tests/ingest/test_fred.py -v`
7. `uv run mypy src/ingest/fred.py`
8. `uv run ruff check src/ingest/ tests/ingest/`

---

## 6. 既存資産との接続点まとめ

| 接続先 | 方法 |
|-------|------|
| `src/config.py` | `settings.fred_api_key` / `settings.fred_base_url` を読み取り |
| `src/db/connection.py` | `SessionLocal` を CLI で使用、`Base` を ORM 継承 |
| `src/db/models.py` | `MacroIndexDaily` を追加（既存 ORM パターンと統一） |
| `src/utils/time.py` | `now_utc()` を `fetched_at` に使用 |
| `src/ingest/candles.py` | `store_bars` の UPSERT パターンを参照（同じ `sqlalchemy.dialects.postgresql.insert`） |
| Alembic | `script.py.mako` テンプレートに従い `revision="003"`, `down_revision="002"` |

---

## 7. 開発タスクの順序

1. `src/db/models.py` に `MacroIndexDaily` を追加
2. Alembic migration 003 を作成 → `uv run alembic upgrade head` で確認
3. `src/ingest/fred.py` 実装
4. `tests/ingest/test_fred.py` 実装 → `uv run pytest tests/ingest/test_fred.py -v` 通過
5. `scripts/fetch_fred.py` 実装
6. 動作確認（短期間 → 全シリーズ）
7. mypy / ruff クリーン化
8. ドキュメント更新（runbook / terminology）
9. コミット / マージ

---

## 8. 既知の trade-off / 残課題

- **available_at 未保持**: T+1 利用原則を守る限り問題ないが、forward-fill 時に primitive 側で off-by-one を作りやすい。primitive 設計時に再検討
- **Series 別の rate limit 並列化なし**: 5 シリーズ程度なら逐次で 1 分以内に完了するため不要
- **Migration の autogenerate 未使用**: 既存 002 と同じ手書きパターン（autogenerate でも手書きでも DDL 結果は同じ）
- **`fetched_at` の意味**: 同一 fetch_series 呼び出し内では同一値。observation 単位の取得時刻ではなく fetch 単位の時刻
