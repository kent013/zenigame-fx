"""Paper Trading ランナー。--mode replay（DB 再生）/ live（OANDA polling）に対応。"""

from __future__ import annotations

import argparse
import signal
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from src.api.oanda import OandaClient
from src.broker import InstrumentMeta, MockBroker
from src.db.connection import SessionLocal
from src.db.models import CurrencyPair, PriceBarM1
from src.domain.price import Ohlc, PriceBar
from src.paper_trading import EventLogger, LiveBarFeed, PaperTradingOrchestrator, ReplayBarFeed
from src.strategy import BollingerMeanReversionStrategy
from src.utils.time import to_utc


def _parse_dt(value: str) -> datetime:
    return to_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _build_strategy(name: str, args: argparse.Namespace):
    if name == "bollinger":
        return BollingerMeanReversionStrategy(window=args.window, k=args.k, units=args.units)
    raise ValueError(f"unknown strategy: {name}")


def _load_replay_bars(instrument: str, start: datetime, end: datetime) -> list[PriceBar]:
    with SessionLocal() as session:
        pair = session.scalars(select(CurrencyPair).where(CurrencyPair.oanda_name == instrument)).one_or_none()
        if pair is None:
            raise RuntimeError(f"currency_pair for {instrument} not found")
        rows = session.scalars(
            select(PriceBarM1)
            .where(PriceBarM1.pair_id == pair.id)
            .where(PriceBarM1.bar_time >= start)
            .where(PriceBarM1.bar_time < end)
            .order_by(PriceBarM1.bar_time.asc())
        ).all()
        return [
            PriceBar(
                pair_name=instrument,
                bar_time=r.bar_time,
                bid=Ohlc(open=r.open_bid, high=r.high_bid, low=r.low_bid, close=r.close_bid),
                ask=Ohlc(open=r.open_ask, high=r.high_ask, low=r.low_ask, close=r.close_ask),
                volume=r.volume,
                complete=r.complete,
            )
            for r in rows
        ]


def _load_instrument_meta(instrument: str) -> InstrumentMeta:
    with SessionLocal() as session:
        pair = session.scalars(select(CurrencyPair).where(CurrencyPair.oanda_name == instrument)).one_or_none()
        if pair is None:
            raise RuntimeError(f"currency_pair for {instrument} not found")
        return InstrumentMeta(
            oanda_name=pair.oanda_name,
            base_currency=pair.base_currency,
            quote_currency=pair.quote_currency,
            margin_rate=pair.margin_rate,
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run paper trading (replay or live)")
    p.add_argument("--mode", choices=["replay", "live"], required=True)
    p.add_argument("--instrument", required=True)
    p.add_argument("--from", dest="from_", default=None, help="replay 開始時刻 ISO8601")
    p.add_argument("--to", dest="to_", default=None, help="replay 終了時刻 ISO8601（exclusive）")
    p.add_argument("--speedup", type=float, default=0.0, help="replay speedup（0=as fast as possible）")
    p.add_argument("--poll-interval", type=float, default=10.0, help="live polling 間隔（秒）")
    p.add_argument("--initial-cash", type=Decimal, default=Decimal("1000000"))
    p.add_argument("--leverage", type=int, default=1)
    p.add_argument("--strategy", default="bollinger")
    p.add_argument("--window", type=int, default=20)
    p.add_argument("--k", type=float, default=2.0)
    p.add_argument("--units", type=int, default=10000)
    p.add_argument("--log-dir", default=None)
    args = p.parse_args(argv)

    session_id = f"paper-{datetime.now(tz=UTC).strftime('%Y%m%d-%H%M%S')}"
    log_dir = Path(args.log_dir) if args.log_dir else Path("paper-logs") / session_id
    event_logger = EventLogger(log_dir)

    meta = _load_instrument_meta(args.instrument)
    broker = MockBroker(instrument_meta=meta)
    strategy = _build_strategy(args.strategy, args)

    if args.mode == "replay":
        if args.from_ is None or args.to_ is None:
            print("[error] --from and --to are required in replay mode", file=sys.stderr)
            return 1
        bars = _load_replay_bars(args.instrument, _parse_dt(args.from_), _parse_dt(args.to_))
        if not bars:
            print("[error] no bars in the specified range", file=sys.stderr)
            return 1
        feed = ReplayBarFeed(bars, speedup=args.speedup)
    else:
        client = OandaClient()
        feed = LiveBarFeed(client, instrument=args.instrument, poll_interval_seconds=args.poll_interval)

    orchestrator = PaperTradingOrchestrator(
        feed=feed,
        strategy=strategy,
        broker=broker,
        logger_=event_logger,
        leverage=args.leverage,
        initial_cash=args.initial_cash,
    )

    def _handle_stop(signum, _frame):
        print(f"[signal] received {signum}, requesting graceful shutdown", file=sys.stderr)
        orchestrator.request_stop()

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    orchestrator.run()
    print(f"[done] log_dir={log_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
