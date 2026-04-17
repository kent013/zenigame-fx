from __future__ import annotations

from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.api.oanda import endpoints
from src.api.oanda.models import AccountSummary, CandlesResponse, Instrument
from src.api.oanda.rate_limit import TokenBucket
from src.config import settings

logger = structlog.get_logger(__name__)


class OandaError(Exception):
    pass


class OandaAuthError(OandaError):
    pass


class OandaRateLimitError(OandaError):
    pass


class OandaServerError(OandaError):
    pass


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 401:
        raise OandaAuthError(f"401 Unauthorized: {response.text}")
    if response.status_code == 429:
        raise OandaRateLimitError(f"429 Too Many Requests: {response.text}")
    if 500 <= response.status_code < 600:
        raise OandaServerError(f"{response.status_code}: {response.text}")
    response.raise_for_status()


class OandaClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        account_id: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._account_id = account_id or settings.oanda_account_id
        self._base_url = base_url or settings.oanda_base_url
        token = token or settings.oanda_api_token
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept-Datetime-Format": "RFC3339",
            },
            timeout=timeout,
        )
        self._limiter = TokenBucket()

    def __enter__(self) -> OandaClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    @retry(
        retry=retry_if_exception_type((OandaServerError, httpx.TransportError, OandaRateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        reraise=True,
    )
    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._limiter.acquire()
        response = self._client.get(path, params=params)
        request_id = response.headers.get("RequestID")
        logger.debug("oanda.request", path=path, params=params, status=response.status_code, request_id=request_id)
        _raise_for_status(response)
        return response.json()

    def get_account_summary(self) -> AccountSummary:
        payload = self._get(endpoints.account_summary(self._account_id))
        return AccountSummary.model_validate(payload["account"])

    def list_instruments(self) -> list[Instrument]:
        payload = self._get(endpoints.account_instruments(self._account_id))
        return [Instrument.model_validate(item) for item in payload["instruments"]]

    def get_instrument(self, name: str) -> Instrument | None:
        return next((inst for inst in self.list_instruments() if inst.name == name), None)

    def get_candles(
        self,
        instrument: str,
        granularity: str = "M1",
        price: str = "BA",
        count: int | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
    ) -> CandlesResponse:
        params: dict[str, Any] = {"granularity": granularity, "price": price}
        if count is not None:
            params["count"] = count
        if from_time is not None:
            params["from"] = from_time
        if to_time is not None:
            params["to"] = to_time
        payload = self._get(endpoints.instrument_candles(instrument), params=params)
        return CandlesResponse.model_validate(payload)
