from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import respx
from httpx import Response

from src.api.cache.http_cache import HttpCache
from src.api.oanda.client import OandaClient
from src.api.oanda.models import Candle, Ohlc
from src.ingest.candles import CandleFetcher, HistoricalRange, store_bars

BASE_URL = "https://api-fxpractice.oanda.com"
ACCOUNT_ID = "test-account"


def _ohlc(base: str) -> dict:
    return {"o": base, "h": base, "l": base, "c": base}


def _candle(time_iso: str, volume: int = 10, complete: bool = True) -> dict:
    return {
        "time": time_iso,
        "volume": volume,
        "complete": complete,
        "bid": _ohlc("154.100"),
        "ask": _ohlc("154.110"),
    }


@pytest.fixture
def client() -> OandaClient:
    return OandaClient(base_url=BASE_URL, token="dummy", account_id=ACCOUNT_ID)


@respx.mock
def test_iter_range_paginates_and_stops_at_end(client: OandaClient) -> None:
    first_page = {
        "instrument": "USD_JPY",
        "granularity": "M1",
        "candles": [_candle(f"2026-04-01T00:{m:02d}:00.000000000Z") for m in range(0, 3)],
    }
    # OANDA は includeFirst=false のとき from で指定したバーを除外するので、from=00:02 に対して 00:03 以降を返す
    second_page = {
        "instrument": "USD_JPY",
        "granularity": "M1",
        "candles": [_candle(f"2026-04-01T00:{m:02d}:00.000000000Z") for m in range(3, 5)],
    }
    route = respx.get(f"{BASE_URL}/v3/instruments/USD_JPY/candles").mock(
        side_effect=[Response(200, json=first_page), Response(200, json=second_page)]
    )

    plan = HistoricalRange(
        instrument="USD_JPY",
        start=datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC),
        end=datetime(2026, 4, 1, 0, 4, 0, tzinfo=UTC),
        chunk_count=3,
    )
    fetcher = CandleFetcher(client)
    candles = list(fetcher.iter_range(plan))

    # end は 00:04 exclusive、candle は 00:00〜00:03 の 4 本（重複除外後）
    assert [c.time.isoformat() for c in candles] == [
        "2026-04-01T00:00:00+00:00",
        "2026-04-01T00:01:00+00:00",
        "2026-04-01T00:02:00+00:00",
        "2026-04-01T00:03:00+00:00",
    ]
    assert route.call_count == 2
    second_call = route.calls[1].request
    assert "includeFirst=false" in str(second_call.url)


@respx.mock
def test_iter_range_continues_when_second_page_is_one_short(client: OandaClient) -> None:
    """OANDA は includeFirst=false の応答で最大 count-1 本しか返さない仕様のため、
    それを「終端」と誤判定して早期 return しない振る舞いを固定する。"""
    first_page = {
        "instrument": "USD_JPY",
        "granularity": "M1",
        "candles": [_candle(f"2026-04-01T00:{m:02d}:00.000000000Z") for m in range(0, 5)],
    }
    # includeFirst=false の 2 ページ目は意図的に count-1 (=4) 本
    second_page = {
        "instrument": "USD_JPY",
        "granularity": "M1",
        "candles": [_candle(f"2026-04-01T00:{m:02d}:00.000000000Z") for m in range(5, 9)],
    }
    # 3 ページ目は真の終端（count-1 未満 = 1 本のみ）
    third_page = {
        "instrument": "USD_JPY",
        "granularity": "M1",
        "candles": [_candle("2026-04-01T00:09:00.000000000Z")],
    }
    route = respx.get(f"{BASE_URL}/v3/instruments/USD_JPY/candles").mock(
        side_effect=[
            Response(200, json=first_page),
            Response(200, json=second_page),
            Response(200, json=third_page),
        ]
    )

    plan = HistoricalRange(
        instrument="USD_JPY",
        start=datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC),
        end=datetime(2026, 4, 1, 1, 0, 0, tzinfo=UTC),
        chunk_count=5,
    )
    candles = list(CandleFetcher(client).iter_range(plan))

    assert route.call_count == 3
    # 全ページの full set が返る（重複なし、欠落なし）
    assert [c.time.minute for c in candles] == list(range(0, 10))


@respx.mock
def test_iter_range_skips_incomplete_bars(client: OandaClient) -> None:
    page = {
        "instrument": "USD_JPY",
        "granularity": "M1",
        "candles": [
            _candle("2026-04-01T00:00:00.000000000Z", complete=True),
            _candle("2026-04-01T00:01:00.000000000Z", complete=False),
        ],
    }
    respx.get(f"{BASE_URL}/v3/instruments/USD_JPY/candles").mock(return_value=Response(200, json=page))

    plan = HistoricalRange(
        instrument="USD_JPY",
        start=datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC),
        end=datetime(2026, 4, 1, 0, 5, 0, tzinfo=UTC),
        chunk_count=5,
    )
    candles = list(CandleFetcher(client).iter_range(plan))
    assert len(candles) == 1
    assert candles[0].complete is True


@respx.mock
def test_iter_range_empty_response_returns_immediately(client: OandaClient) -> None:
    respx.get(f"{BASE_URL}/v3/instruments/USD_JPY/candles").mock(
        return_value=Response(200, json={"instrument": "USD_JPY", "granularity": "M1", "candles": []})
    )
    plan = HistoricalRange(
        instrument="USD_JPY",
        start=datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC),
        end=datetime(2026, 4, 1, 0, 5, 0, tzinfo=UTC),
    )
    assert list(CandleFetcher(client).iter_range(plan)) == []


@respx.mock
def test_iter_range_uses_cache_for_historical_chunks(client: OandaClient, tmp_path) -> None:
    old_start = (datetime.now(tz=UTC) - timedelta(days=10)).replace(microsecond=0)
    page = {
        "instrument": "USD_JPY",
        "granularity": "M1",
        "candles": [
            _candle((old_start + timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%S") + ".000000000Z") for m in range(3)
        ],
    }
    route = respx.get(f"{BASE_URL}/v3/instruments/USD_JPY/candles").mock(return_value=Response(200, json=page))

    cache = HttpCache(tmp_path)
    plan = HistoricalRange(
        instrument="USD_JPY",
        start=old_start,
        end=old_start + timedelta(minutes=3),
        chunk_count=10,  # response 3 本 < chunk_count で終端判定に入る
    )
    fetcher = CandleFetcher(client, cache=cache)
    list(fetcher.iter_range(plan))
    list(fetcher.iter_range(plan))

    assert route.call_count == 1  # 2 回目はキャッシュから返るので API 呼び出しは増えない
    cache.close()


@respx.mock
def test_fetch_latest_filters_incomplete(client: OandaClient) -> None:
    page = {
        "instrument": "USD_JPY",
        "granularity": "M1",
        "candles": [
            _candle("2026-04-01T00:00:00.000000000Z", complete=True),
            _candle("2026-04-01T00:01:00.000000000Z", complete=False),
        ],
    }
    respx.get(f"{BASE_URL}/v3/instruments/USD_JPY/candles").mock(return_value=Response(200, json=page))
    candles = CandleFetcher(client).fetch_latest("USD_JPY", count=2)
    assert len(candles) == 1


def _make_candle(minute: int, complete: bool = True) -> Candle:
    base = Decimal("154.100")
    ohlc = Ohlc(o=base, h=base, l=base, c=base)
    return Candle(
        time=datetime(2026, 4, 1, 0, minute, 0, tzinfo=UTC),
        volume=10,
        complete=complete,
        bid=ohlc,
        ask=Ohlc(
            o=base + Decimal("0.010"), h=base + Decimal("0.010"), l=base + Decimal("0.010"), c=base + Decimal("0.010")
        ),
    )


def test_store_bars_skips_incomplete_and_missing_sides() -> None:
    session = MagicMock()
    candles = [
        _make_candle(0, complete=True),
        _make_candle(1, complete=False),  # skipped (incomplete)
        _make_candle(2, complete=True),
    ]
    written = store_bars(session, pair_id=1, candles=candles)
    assert written == 2
    session.commit.assert_called_once()
    # バルク UPSERT なので session.execute は 1 回のみ
    assert session.execute.call_count == 1
