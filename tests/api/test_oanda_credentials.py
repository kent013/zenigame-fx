"""OANDA クライアント生成時の認証情報バリデーション（audit P1 follow-up）。"""

from __future__ import annotations

import pytest

from src.api.oanda.client import OandaClient

BASE_URL = "https://api-fxpractice.oanda.com"


def test_empty_api_token_raises() -> None:
    with pytest.raises(ValueError, match="api token"):
        OandaClient(base_url=BASE_URL, token="", account_id="001-009-12345-001")


def test_whitespace_only_api_token_raises() -> None:
    with pytest.raises(ValueError, match="api token"):
        OandaClient(base_url=BASE_URL, token="   ", account_id="001-009-12345-001")


def test_empty_account_id_raises() -> None:
    with pytest.raises(ValueError, match="account id"):
        OandaClient(base_url=BASE_URL, token="dummy", account_id="")


def test_valid_credentials_do_not_raise() -> None:
    # 疎通はしないので例外無く生成されるだけを確認
    client = OandaClient(base_url=BASE_URL, token="dummy-token", account_id="001-009-12345-001")
    client.close()
