"""指定期間の M1 candles を OANDA から取得し price_bar_m1 に UPSERT する。

前提: `currency_pair` テーブルに対象 instrument が存在すること（無ければ `scripts/oanda_ping.py` を先に実行）。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta

from sqlalchemy import select

from src.api.cache.http_cache import HttpCache
from src.api.oanda import OandaClient
from src.api.oanda.client import OandaAuthError
from src.config import settings
from src.db.connection import SessionLocal
from src.db.models import CurrencyPair
from src.ingest import CandleFetcher, HistoricalRange, store_bars
from src.utils.time import now_utc, to_utc


def _parse_end(value: str | None) -> datetime:
    if value is None:
        return now_utc() - timedelta(hours=1)
    return to_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch historical M1 candles for an instrument")
    parser.add_argument("--instrument", required=True, help="OANDA instrument name (e.g. USD_JPY)")
    parser.add_argument("--days", type=int, default=365, help="days to backfill from --end")
    parser.add_argument("--end", default=None, help="end time in ISO8601 (UTC). default = now - 1h")
    parser.add_argument("--granularity", default="M1")
    parser.add_argument("--chunk-count", type=int, default=5000)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args(argv)

    end = _parse_end(args.end)
    start = end - timedelta(days=args.days)
    plan = HistoricalRange(
        instrument=args.instrument,
        start=start,
        end=end,
        granularity=args.granularity,
        chunk_count=args.chunk_count,
    )

    with SessionLocal() as session:
        pair = session.scalars(select(CurrencyPair).where(CurrencyPair.oanda_name == args.instrument)).one_or_none()
        if pair is None:
            print(
                f"[error] currency_pair for {args.instrument} not found. Run scripts/oanda_ping.py first.",
                file=sys.stderr,
            )
            return 1
        pair_id = pair.id

    cache: HttpCache | None = None
    if not args.no_cache:
        cache = HttpCache(f"{settings.diskcache_dir}/oanda/candles")

    try:
        with OandaClient() as client:
            fetcher = CandleFetcher(client, cache=cache)
            total_seen = 0
            total_written = 0
            chunk: list = []
            with SessionLocal() as session:
                for candle in fetcher.iter_range(plan):
                    total_seen += 1
                    chunk.append(candle)
                    if len(chunk) >= args.chunk_count:
                        total_written += store_bars(session, pair_id, chunk)
                        print(f"[progress] seen={total_seen} written={total_written}", file=sys.stderr)
                        chunk.clear()
                if chunk:
                    total_written += store_bars(session, pair_id, chunk)
    except OandaAuthError as e:
        print(f"[auth error] {e}", file=sys.stderr)
        return 2
    finally:
        if cache is not None:
            cache.close()

    print(f"[done] seen={total_seen} written={total_written} start={plan.start.isoformat()} end={plan.end.isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
