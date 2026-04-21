"""OANDA 疎通確認 + 指定 instrument を currency_pair テーブルへ UPSERT。

デフォルトは USD_JPY。`--instruments EUR_JPY AUD_JPY ...` で複数指定可能。
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert

from src.api.oanda import OandaClient
from src.db.connection import SessionLocal
from src.db.models import CurrencyPair

DEFAULT_INSTRUMENTS = ["USD_JPY"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ping OANDA and upsert currency_pair rows")
    parser.add_argument(
        "--instruments",
        nargs="+",
        default=DEFAULT_INSTRUMENTS,
        help="OANDA instrument names (default: USD_JPY)",
    )
    args = parser.parse_args(argv)

    now = datetime.now(tz=UTC)
    with OandaClient() as client:
        summary = client.get_account_summary()
        print(f"[account] id={summary.id} currency={summary.currency} balance={summary.balance}")

        to_upsert: list[dict] = []
        for name in args.instruments:
            inst = client.get_instrument(name)
            if inst is None:
                print(f"[error] {name} not found in account instruments", file=sys.stderr)
                return 1
            print(
                f"[instrument] {inst.name} pipLocation={inst.pip_location} "
                f"marginRate={inst.margin_rate} displayPrecision={inst.display_precision}"
            )
            base, quote = inst.name.split("_", 1)
            to_upsert.append(
                {
                    "oanda_name": inst.name,
                    "display_name": inst.display_name,
                    "base_currency": base,
                    "quote_currency": quote,
                    "pip_location": inst.pip_location,
                    "display_precision": inst.display_precision,
                    "trade_units_precision": inst.trade_units_precision,
                    "margin_rate": inst.margin_rate,
                    "minimum_trade_size": inst.minimum_trade_size,
                    "maximum_order_units": inst.maximum_order_units,
                    "instrument_type": inst.type,
                    "is_active": True,
                    "fetched_at": now,
                }
            )

    with SessionLocal() as session:
        for values in to_upsert:
            stmt = insert(CurrencyPair).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=[CurrencyPair.oanda_name],
                set_={k: v for k, v in values.items() if k != "oanda_name"},
            )
            session.execute(stmt)
        session.commit()
    for values in to_upsert:
        print(f"[db] upserted currency_pair for {values['oanda_name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
