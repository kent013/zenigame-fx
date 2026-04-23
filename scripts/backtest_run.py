"""バックテスト実行 CLI。price_bar_m1 から期間を取り出し、戦略を走らせてレポートを生成する。"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from src.backtest import BacktestConfig, run_backtest, write_report
from src.broker import InstrumentMeta, MockBroker
from src.db.connection import SessionLocal
from src.db.models import CurrencyPair, PriceBarM1
from src.domain.price import Ohlc, PriceBar
from src.strategy import BollingerMeanReversionStrategy
from src.utils.time import to_utc


def _parse_dt(value: str) -> datetime:
    return to_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _build_strategy(name: str, args: argparse.Namespace):
    if name == "bollinger":
        return BollingerMeanReversionStrategy(window=args.window, k=args.k, units=args.units)
    raise ValueError(f"unknown strategy: {name}")


def _load_bars(session, pair_id: int, instrument: str, start: datetime, end: datetime) -> list[PriceBar]:
    rows = session.scalars(
        select(PriceBarM1)
        .where(PriceBarM1.pair_id == pair_id)
        .where(PriceBarM1.bar_time >= start)
        .where(PriceBarM1.bar_time < end)
        .order_by(PriceBarM1.bar_time.asc())
    ).all()
    bars: list[PriceBar] = []
    for r in rows:
        bars.append(
            PriceBar(
                pair_name=instrument,
                bar_time=r.bar_time,
                bid=Ohlc(open=r.open_bid, high=r.high_bid, low=r.low_bid, close=r.close_bid),
                ask=Ohlc(open=r.open_ask, high=r.high_ask, low=r.low_ask, close=r.close_ask),
                volume=r.volume,
                complete=r.complete,
            )
        )
    return bars


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run backtest for a single instrument / strategy")
    p.add_argument("--instrument", required=True)
    p.add_argument("--from", dest="from_", required=True, help="ISO8601 start")
    p.add_argument("--to", dest="to_", required=True, help="ISO8601 end (exclusive)")
    p.add_argument("--initial-cash", type=Decimal, default=Decimal("1000000"))
    p.add_argument("--leverage", type=int, default=1)
    p.add_argument("--strategy", default="bollinger")
    p.add_argument("--window", type=int, default=20)
    p.add_argument("--k", type=float, default=2.0)
    p.add_argument("--units", type=int, default=10000)
    p.add_argument("--reports-dir", default="reports/backtests")
    args = p.parse_args(argv)

    start = _parse_dt(args.from_)
    end = _parse_dt(args.to_)

    with SessionLocal() as session:
        pair = session.scalars(select(CurrencyPair).where(CurrencyPair.oanda_name == args.instrument)).one_or_none()
        if pair is None:
            print(
                f"[error] currency_pair for {args.instrument} not found. Run scripts/oanda_ping.py first.",
                file=sys.stderr,
            )
            return 1
        bars = _load_bars(session, pair.id, args.instrument, start, end)

    if not bars:
        print(f"[error] no bars in [{start}, {end}) for {args.instrument}", file=sys.stderr)
        return 1

    meta = InstrumentMeta(
        oanda_name=pair.oanda_name,
        base_currency=pair.base_currency,
        quote_currency=pair.quote_currency,
        margin_rate=pair.margin_rate,
        pip_size=InstrumentMeta.default_pip_size_for_quote(pair.quote_currency),
        display_precision=InstrumentMeta.default_display_precision_for_quote(pair.quote_currency),
    )
    broker = MockBroker(instrument_meta=meta)
    strategy = _build_strategy(args.strategy, args)
    config = BacktestConfig(
        instrument=args.instrument,
        start=start,
        end=end,
        initial_cash=args.initial_cash,
        leverage=args.leverage,
    )

    result = run_backtest(bars, strategy, broker, config)
    out_dir = write_report(result, root=Path(args.reports_dir))
    print(f"[done] bars={len(bars)} trades={len(result.trades)} report={out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
