"""LiveBarFeed の例外フィルタ・動的 count 計算の回帰テスト（audit P1/P2 follow-up）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import respx
from httpx import Response

from src.api.oanda.client import OandaAuthError, OandaClient
from src.paper_trading.feed import LiveBarFeed

BASE_URL = "https://api-fxpractice.oanda.com"
ACCOUNT_ID = "test"


def _make_client() -> OandaClient:
    return OandaClient(base_url=BASE_URL, token="dummy", account_id=ACCOUNT_ID)


def _ohlc(price: str) -> dict:
    return {"o": price, "h": price, "l": price, "c": price}


def _candle(time_iso: str, complete: bool = True) -> dict:
    return {
        "time": time_iso,
        "volume": 10,
        "complete": complete,
        "bid": _ohlc("154.100"),
        "ask": _ohlc("154.110"),
    }


@respx.mock
def test_live_feed_raises_on_auth_error_instead_of_looping() -> None:
    respx.get(f"{BASE_URL}/v3/instruments/USD_JPY/candles").mock(return_value=Response(401, text="unauth"))
    feed = LiveBarFeed(_make_client(), instrument="USD_JPY", poll_interval_seconds=0.01)
    with pytest.raises(OandaAuthError):
        next(iter(feed))


@respx.mock
def test_live_feed_requests_larger_count_after_long_gap() -> None:
    """前回 yield から長い時間経過している場合、count を増やしてバー欠落を最小化する。"""
    # 先に 1 本 yield させる
    first = {
        "instrument": "USD_JPY",
        "granularity": "M1",
        "candles": [_candle("2026-04-01T00:00:00.000000000Z", complete=True)],
    }
    route = respx.get(f"{BASE_URL}/v3/instruments/USD_JPY/candles").mock(return_value=Response(200, json=first))
    feed = LiveBarFeed(_make_client(), instrument="USD_JPY", poll_interval_seconds=0.01)
    feed._last_yielded = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC) - timedelta(minutes=30)  # 30 分遅延シミュレーション

    it = iter(feed)
    next(it)  # 1 回ポーリング

    # 最初のリクエストの count を検証
    first_request_url = str(route.calls[0].request.url)
    # 30 分遅延 → count は 30 + buffer 程度になるはず。2 より大きく、上限以内
    import re

    m = re.search(r"count=(\d+)", first_request_url)
    assert m is not None
    count = int(m.group(1))
    assert count > 2, f"expected dynamic count > 2 for a 30min gap, got count={count}"
    assert count <= 500, f"count should be capped for safety, got count={count}"


@respx.mock
def test_live_feed_first_poll_uses_small_count() -> None:
    first = {
        "instrument": "USD_JPY",
        "granularity": "M1",
        "candles": [_candle("2026-04-01T00:00:00.000000000Z", complete=True)],
    }
    route = respx.get(f"{BASE_URL}/v3/instruments/USD_JPY/candles").mock(return_value=Response(200, json=first))
    feed = LiveBarFeed(_make_client(), instrument="USD_JPY", poll_interval_seconds=0.01)

    it = iter(feed)
    next(it)
    import re

    m = re.search(r"count=(\d+)", str(route.calls[0].request.url))
    assert m is not None and int(m.group(1)) <= 5, "initial poll should use a small count"
