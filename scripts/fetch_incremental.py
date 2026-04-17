"""直近の完成済み M1 candles を OANDA から取得し price_bar_m1 に UPSERT する。"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from src.api.oanda import OandaClient
from src.api.oanda.client import OandaAuthError
from src.db.connection import SessionLocal
from src.db.models import CurrencyPair
from src.ingest import CandleFetcher, store_bars


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch latest M1 candles for an instrument")
    parser.add_argument("--instrument", required=True)
    parser.add_argument("--count", type=int, default=60, help="number of most recent candles to pull")
    parser.add_argument("--granularity", default="M1")
    args = parser.parse_args(argv)

    with SessionLocal() as session:
        pair = session.scalars(select(CurrencyPair).where(CurrencyPair.oanda_name == args.instrument)).one_or_none()
        if pair is None:
            print(
                f"[error] currency_pair for {args.instrument} not found. Run scripts/oanda_ping.py first.",
                file=sys.stderr,
            )
            return 1
        pair_id = pair.id

    try:
        with OandaClient() as client:
            fetcher = CandleFetcher(client)
            candles = fetcher.fetch_latest(args.instrument, count=args.count, granularity=args.granularity)
    except OandaAuthError as e:
        print(f"[auth error] {e}", file=sys.stderr)
        return 2

    with SessionLocal() as session:
        written = store_bars(session, pair_id, candles)
    print(f"[done] fetched={len(candles)} written={written}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
