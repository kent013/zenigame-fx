"""FRED API ingest — daily macro indicator (VIX / DXY / Treasury yields / breakeven 等)。

詳細設計: devnotes/20260422-1027-fred-ingest-implementation/
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
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
# 総試行回数（初回 1 + 最大 MAX_ATTEMPTS-1 リトライ）。"3 回までリトライ" の解釈ブレを避けるため Attempt ベース命名。
MAX_ATTEMPTS = 3
BACKOFF_BASE_SEC = 1.0


@dataclass(frozen=True)
class FredObservation:
    """FRED の単一 observation を正規化したもの。"""

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

    - `value="."` は `None` として保持する（FRED の欠損表現）
    - 429 / 5xx / `httpx.TimeoutException` / `httpx.TransportError` は exponential backoff で
      総 `MAX_ATTEMPTS` 試行（= 初回 1 回 + リトライ最大 `MAX_ATTEMPTS-1` 回）までリトライ
    - 400 / 401 / 403 等の 4xx は `httpx.HTTPStatusError` で即時 raise（リトライしない）

    `api_key` / `base_url` を省略した場合は `settings.fred_api_key` / `settings.fred_base_url`
    を使用する。
    """

    effective_api_key = api_key if api_key is not None else settings.fred_api_key
    effective_base_url = (base_url if base_url is not None else settings.fred_base_url).rstrip("/")
    url = f"{effective_base_url}/series/observations"
    params: dict[str, Any] = {
        "series_id": series_id,
        "observation_start": start.isoformat(),
        "observation_end": end.isoformat(),
        "file_type": "json",
        "api_key": effective_api_key,
    }

    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=DEFAULT_TIMEOUT)
    try:
        assert client is not None  # for mypy
        response = _request_with_retry(client, url, params)
    finally:
        if owns_client and client is not None:
            client.close()

    payload = response.json()
    raw_obs = payload.get("observations", [])
    fetched_at = now_utc()
    observations: list[FredObservation] = []
    for raw in raw_obs:
        value_str = raw.get("value", ".")
        value: Decimal | None = None if value_str == "." else Decimal(value_str)
        obs_date = date.fromisoformat(raw["date"])
        observations.append(
            FredObservation(
                series_id=series_id,
                obs_date=obs_date,
                value=value,
                fetched_at=fetched_at,
            )
        )

    if not observations:
        logger.warning(
            "ingest.fred.zero_observations",
            series_id=series_id,
            start=start.isoformat(),
            end=end.isoformat(),
        )
    else:
        logger.info(
            "ingest.fred.fetched",
            series_id=series_id,
            start=start.isoformat(),
            end=end.isoformat(),
            count=len(observations),
        )
    return observations


def upsert_observations(session: Session, rows: Iterable[FredObservation]) -> int:
    """`macro_index_daily` に ON CONFLICT (series_id, date) DO UPDATE で UPSERT する。

    `value` は NULL も含めて最新値で上書き、`fetched_at` も最新値に更新される。
    戻り値は対象行数（insert + update を区別せず合算）。空入力は 0 を返す。
    """
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


def _request_with_retry(client: httpx.Client, url: str, params: dict[str, Any]) -> httpx.Response:
    last_exc: Exception | None = None
    last_response: httpx.Response | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        is_last_attempt = attempt == MAX_ATTEMPTS
        try:
            response = client.get(url, params=params)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            last_response = None  # 最新試行は例外なので status を保留しない
            logger.warning(
                "ingest.fred.retry_exc",
                error=str(exc),
                attempt=attempt,
                series_id=params.get("series_id"),
            )
            if not is_last_attempt:
                _sleep_backoff(attempt)
            continue
        if response.status_code in RETRYABLE_STATUS:
            last_response = response
            last_exc = None  # 最新試行は status 失敗なので、status 由来の例外を優先
            logger.warning(
                "ingest.fred.retry_status",
                status_code=response.status_code,
                attempt=attempt,
                series_id=params.get("series_id"),
            )
            if is_last_attempt:
                # 最終試行が retryable status の場合、HTTPStatusError を raise する
                response.raise_for_status()
            else:
                _sleep_backoff(attempt)
            continue
        # retryable でない status はここで raise_for_status (4xx は即時 raise、2xx は通過)
        response.raise_for_status()
        return response

    # 全試行失敗時: 最終試行が例外だった場合のみここに到達する
    # （最終試行が retryable status だった場合は上の raise_for_status() で抜けるため）
    if last_exc is not None:
        raise last_exc
    # 防御的: 最終試行が status だった場合も念のため raise（通常は到達しない）
    assert last_response is not None
    last_response.raise_for_status()
    return last_response


def _sleep_backoff(attempt: int) -> None:
    """`attempt` (1-indexed) に対し exponential backoff で sleep する。テストで monkeypatch 可能。"""
    time.sleep(BACKOFF_BASE_SEC * (2 ** (attempt - 1)))
