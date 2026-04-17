"""OANDA 疎通確認 + USD_JPY を currency_pair テーブルへ UPSERT。

完了判定 #4 / #5 を同時に満たす最小スクリプト。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from src.api.oanda import OandaClient
from src.db.connection import SessionLocal
from src.db.models import CurrencyPair

TARGET_INSTRUMENT = "USD_JPY"


def main() -> None:
    with OandaClient() as client:
        summary = client.get_account_summary()
        print(f"[account] id={summary.id} currency={summary.currency} balance={summary.balance}")

        usd_jpy = client.get_instrument(TARGET_INSTRUMENT)
        if usd_jpy is None:
            raise RuntimeError(f"{TARGET_INSTRUMENT} not found in account instruments")

        print(
            f"[instrument] {usd_jpy.name} pipLocation={usd_jpy.pip_location} "
            f"marginRate={usd_jpy.margin_rate} displayPrecision={usd_jpy.display_precision}"
        )

    base, quote = usd_jpy.name.split("_", 1)
    now = datetime.now(tz=timezone.utc)
    values = {
        "oanda_name": usd_jpy.name,
        "display_name": usd_jpy.display_name,
        "base_currency": base,
        "quote_currency": quote,
        "pip_location": usd_jpy.pip_location,
        "display_precision": usd_jpy.display_precision,
        "trade_units_precision": usd_jpy.trade_units_precision,
        "margin_rate": usd_jpy.margin_rate,
        "minimum_trade_size": usd_jpy.minimum_trade_size,
        "maximum_order_units": usd_jpy.maximum_order_units,
        "instrument_type": usd_jpy.type,
        "is_active": True,
        "fetched_at": now,
    }
    stmt = insert(CurrencyPair).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[CurrencyPair.oanda_name],
        set_={k: v for k, v in values.items() if k != "oanda_name"},
    )
    with SessionLocal() as session:
        session.execute(stmt)
        session.commit()
    print(f"[db] upserted currency_pair for {usd_jpy.name}")


if __name__ == "__main__":
    main()
