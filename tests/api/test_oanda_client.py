from __future__ import annotations

import pytest
import respx
from httpx import Response

from src.api.oanda.client import OandaAuthError, OandaClient

BASE_URL = "https://api-fxpractice.oanda.com"
ACCOUNT_ID = "001-009-12345-001"


@pytest.fixture
def client() -> OandaClient:
    return OandaClient(base_url=BASE_URL, token="dummy", account_id=ACCOUNT_ID)


@respx.mock
def test_get_account_summary_parses_response(client: OandaClient, oanda_fixture) -> None:
    respx.get(f"{BASE_URL}/v3/accounts/{ACCOUNT_ID}/summary").mock(
        return_value=Response(200, json=oanda_fixture("account_summary.json"))
    )
    summary = client.get_account_summary()
    assert summary.id == ACCOUNT_ID
    assert summary.currency == "JPY"
    assert str(summary.balance) == "1000000.00"


@respx.mock
def test_list_instruments_returns_usd_jpy(client: OandaClient, oanda_fixture) -> None:
    respx.get(f"{BASE_URL}/v3/accounts/{ACCOUNT_ID}/instruments").mock(
        return_value=Response(200, json=oanda_fixture("account_instruments.json"))
    )
    usd_jpy = client.get_instrument("USD_JPY")
    assert usd_jpy is not None
    assert usd_jpy.pip_location == -2
    assert usd_jpy.display_precision == 3


@respx.mock
def test_get_candles_parses_bid_ask(client: OandaClient, oanda_fixture) -> None:
    respx.get(f"{BASE_URL}/v3/instruments/USD_JPY/candles").mock(
        return_value=Response(200, json=oanda_fixture("candles_usdjpy_m1.json"))
    )
    resp = client.get_candles("USD_JPY", granularity="M1", price="BA", count=1)
    assert len(resp.candles) == 1
    bar = resp.candles[0]
    assert bar.complete is True
    assert bar.bid is not None and bar.ask is not None
    assert str(bar.bid.c) == "154.125"
    assert str(bar.ask.c) == "154.135"


@respx.mock
def test_auth_error_raises_oanda_auth_error(client: OandaClient) -> None:
    respx.get(f"{BASE_URL}/v3/accounts/{ACCOUNT_ID}/summary").mock(return_value=Response(401, text="nope"))
    with pytest.raises(OandaAuthError):
        client.get_account_summary()
