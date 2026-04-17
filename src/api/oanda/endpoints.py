from __future__ import annotations


def account_summary(account_id: str) -> str:
    return f"/v3/accounts/{account_id}/summary"


def account_instruments(account_id: str) -> str:
    return f"/v3/accounts/{account_id}/instruments"


def instrument_candles(instrument: str) -> str:
    return f"/v3/instruments/{instrument}/candles"


def account_pricing(account_id: str) -> str:
    return f"/v3/accounts/{account_id}/pricing"
