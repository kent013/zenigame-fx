from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
import respx
from httpx import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.connection import Base
from src.db.models import MacroIndexDaily
from src.ingest.fred import (
    MAX_ATTEMPTS,
    FredObservation,
    fetch_series,
    upsert_observations,
)

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


def _obs(date_str: str, value: str) -> dict:
    return {
        "realtime_start": "2026-04-22",
        "realtime_end": "2026-04-22",
        "date": date_str,
        "value": value,
    }


@pytest.fixture(autouse=True)
def _stub_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """テスト時間短縮のため backoff sleep を no-op に置き換える。"""
    monkeypatch.setattr("src.ingest.fred._sleep_backoff", lambda attempt: None)


@respx.mock
def test_fetch_series_normalizes_observations() -> None:
    route = respx.get(f"{BASE_URL}/series/observations").mock(
        return_value=Response(
            200,
            json=_fred_response([_obs("2026-04-14", "16.42"), _obs("2026-04-15", "17.01")]),
        )
    )

    obs = fetch_series(
        "VIXCLS",
        date(2026, 4, 14),
        date(2026, 4, 15),
        api_key="dummy",
        base_url=BASE_URL,
    )

    assert route.call_count == 1
    assert [(o.obs_date, o.value) for o in obs] == [
        (date(2026, 4, 14), Decimal("16.42")),
        (date(2026, 4, 15), Decimal("17.01")),
    ]
    assert all(o.series_id == "VIXCLS" for o in obs)
    assert all(isinstance(o.fetched_at, datetime) and o.fetched_at.tzinfo is UTC for o in obs)


@respx.mock
def test_fetch_series_handles_missing_value_dot() -> None:
    respx.get(f"{BASE_URL}/series/observations").mock(
        return_value=Response(
            200,
            json=_fred_response([_obs("2026-04-14", "16.42"), _obs("2026-04-15", ".")]),
        )
    )

    obs = fetch_series(
        "VIXCLS",
        date(2026, 4, 14),
        date(2026, 4, 15),
        api_key="dummy",
        base_url=BASE_URL,
    )

    assert obs[0].value == Decimal("16.42")
    assert obs[1].value is None


@respx.mock
def test_fetch_series_retries_on_429_then_succeeds() -> None:
    route = respx.get(f"{BASE_URL}/series/observations").mock(
        side_effect=[
            Response(429, json={"error": "rate limit"}),
            Response(200, json=_fred_response([_obs("2026-04-14", "16.42")])),
        ]
    )

    obs = fetch_series(
        "VIXCLS",
        date(2026, 4, 14),
        date(2026, 4, 14),
        api_key="dummy",
        base_url=BASE_URL,
    )

    assert route.call_count == 2  # 1 回リトライしてから成功
    assert len(obs) == 1


@respx.mock
def test_fetch_series_raises_on_401_without_retry() -> None:
    route = respx.get(f"{BASE_URL}/series/observations").mock(
        return_value=Response(401, json={"error_code": 401, "error_message": "Bad API key"})
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        fetch_series(
            "VIXCLS",
            date(2026, 4, 14),
            date(2026, 4, 14),
            api_key="bad",
            base_url=BASE_URL,
        )

    assert exc_info.value.response.status_code == 401
    assert route.call_count == 1  # リトライしない


@respx.mock
def test_fetch_series_raises_after_max_attempts() -> None:
    route = respx.get(f"{BASE_URL}/series/observations").mock(
        return_value=Response(503, json={"error": "service unavailable"})
    )

    with pytest.raises(httpx.HTTPStatusError):
        fetch_series(
            "VIXCLS",
            date(2026, 4, 14),
            date(2026, 4, 14),
            api_key="dummy",
            base_url=BASE_URL,
        )

    assert route.call_count == MAX_ATTEMPTS  # 全試行で raise


@respx.mock
def test_fetch_series_raises_http_status_when_last_attempt_is_status() -> None:
    """直前試行が TransportError でも、最終試行が retryable status なら
    `HTTPStatusError` を raise する（status 由来の失敗は status として表面化させる）。"""
    route = respx.get(f"{BASE_URL}/series/observations").mock(
        side_effect=[
            httpx.ConnectError("dns failure"),  # attempt 1
            httpx.ConnectError("dns failure"),  # attempt 2
            Response(503, json={"error": "service unavailable"}),  # attempt 3 (last)
        ]
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        fetch_series(
            "VIXCLS",
            date(2026, 4, 14),
            date(2026, 4, 14),
            api_key="dummy",
            base_url=BASE_URL,
        )

    assert exc_info.value.response.status_code == 503
    assert route.call_count == MAX_ATTEMPTS


@respx.mock
def test_fetch_series_returns_empty_list_when_no_observations() -> None:
    respx.get(f"{BASE_URL}/series/observations").mock(
        return_value=Response(200, json=_fred_response([]))
    )

    obs = fetch_series(
        "BOGUSID",
        date(2026, 4, 14),
        date(2026, 4, 14),
        api_key="dummy",
        base_url=BASE_URL,
    )

    assert obs == []


@respx.mock
def test_fetch_series_retries_on_transport_error_then_succeeds() -> None:
    route = respx.get(f"{BASE_URL}/series/observations").mock(
        side_effect=[
            httpx.ConnectError("dns failure"),
            Response(200, json=_fred_response([_obs("2026-04-14", "16.42")])),
        ]
    )

    obs = fetch_series(
        "VIXCLS",
        date(2026, 4, 14),
        date(2026, 4, 14),
        api_key="dummy",
        base_url=BASE_URL,
    )

    assert route.call_count == 2
    assert len(obs) == 1


def _make_obs(d: date, value: Any) -> FredObservation:
    return FredObservation(
        series_id="VIXCLS",
        obs_date=d,
        value=value,
        fetched_at=datetime(2026, 4, 22, 0, 0, 0, tzinfo=UTC),
    )


def test_upsert_observations_returns_zero_for_empty_input() -> None:
    session = MagicMock(spec=Session)
    written = upsert_observations(session, [])
    assert written == 0
    session.execute.assert_not_called()
    session.commit.assert_not_called()


def test_upsert_observations_emits_on_conflict_do_update() -> None:
    session = MagicMock(spec=Session)
    rows = [_make_obs(date(2026, 4, 14), Decimal("16.42")), _make_obs(date(2026, 4, 15), None)]

    written = upsert_observations(session, rows)

    assert written == 2
    assert session.execute.call_count == 1
    session.commit.assert_called_once()
    # SQL 文の文字列に ON CONFLICT が含まれることを確認（Postgres dialect）
    stmt = session.execute.call_args.args[0]
    compiled = str(stmt.compile(dialect=__import__("sqlalchemy.dialects.postgresql", fromlist=["dialect"]).dialect()))
    assert "ON CONFLICT" in compiled.upper()


# ----- DB 統合テスト（testcontainers Postgres） -----


@pytest.fixture(scope="module")
def pg_session():  # type: ignore[no-untyped-def]
    from sqlalchemy.engine.url import make_url
    from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

    with PostgresContainer("postgres:16") as pg:
        # SQLAlchemy 2 の psycopg (v3) ドライバを強制する。
        # testcontainers のバージョン差で `postgresql+psycopg2` / `postgresql` どちらの
        # drivername が返るか不定のため、parse して psycopg に正規化する。
        raw_url = pg.get_connection_url()
        url_obj = make_url(raw_url).set(drivername="postgresql+psycopg")
        engine = create_engine(url_obj, future=True)
        Base.metadata.create_all(engine, tables=[MacroIndexDaily.__table__])
        session_factory = sessionmaker(bind=engine, future=True)
        session = session_factory()
        try:
            yield session
        finally:
            session.close()
            engine.dispose()


@pytest.mark.integration
def test_upsert_observations_idempotent_on_repeat(pg_session: Session) -> None:
    rows_v1 = [
        FredObservation("VIXCLS", date(2026, 4, 14), Decimal("16.42"), datetime(2026, 4, 22, tzinfo=UTC)),
        FredObservation("VIXCLS", date(2026, 4, 15), None, datetime(2026, 4, 22, tzinfo=UTC)),
    ]
    rows_v2 = [
        FredObservation("VIXCLS", date(2026, 4, 14), Decimal("16.50"), datetime(2026, 4, 23, tzinfo=UTC)),
        FredObservation("VIXCLS", date(2026, 4, 15), None, datetime(2026, 4, 23, tzinfo=UTC)),
    ]

    assert upsert_observations(pg_session, rows_v1) == 2
    assert upsert_observations(pg_session, rows_v2) == 2

    rows = pg_session.query(MacroIndexDaily).order_by(MacroIndexDaily.date).all()
    assert len(rows) == 2  # row count 不変
    assert rows[0].value == Decimal("16.500000")  # value 上書き（NUMERIC(18,6) で正規化）
    assert rows[1].value is None  # NULL 保持
    # fetched_at が更新されている（v2 の値）
    assert rows[0].fetched_at.day == 23
    assert rows[1].fetched_at.day == 23
