"""グリッドサーチ CLI。--param k=v1,v2,... を繰り返し指定してパラメータ空間を探索する。"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select

from src.backtest import GridSearchConfig, run_grid_search, write_comparison_report
from src.broker import InstrumentMeta
from src.db.connection import SessionLocal
from src.db.models import CurrencyPair, PriceBarM1
from src.domain.price import Ohlc, PriceBar
from src.strategy import list_strategies
from src.utils.time import to_utc


def _parse_dt(value: str) -> datetime:
    return to_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _coerce(token: str) -> Any:
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def _parse_param(value: str) -> tuple[str, list[Any]]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"--param expects name=v1,v2,... but got '{value}'")
    name, raw = value.split("=", 1)
    values = [_coerce(t.strip()) for t in raw.split(",") if t.strip()]
    if not values:
        raise argparse.ArgumentTypeError(f"--param {name}= has no values")
    return name, values


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run parameter grid search over a strategy")
    p.add_argument("--instrument", required=True)
    p.add_argument("--from", dest="from_", required=True)
    p.add_argument("--to", dest="to_", required=True)
    p.add_argument("--initial-cash", type=Decimal, default=Decimal("1000000"))
    p.add_argument("--leverage", type=int, default=1)
    p.add_argument("--strategy", required=True, help=f"one of {list_strategies()}")
    p.add_argument("--param", action="append", default=[], help="NAME=v1,v2,v3 (multiple times)")
    p.add_argument("--parallel", type=int, default=1)
    p.add_argument("--top-n", type=int, default=20)
    p.add_argument("--reports-dir", default="reports/grid-searches")
    args = p.parse_args(argv)

    parameter_grid = dict(_parse_param(v) for v in args.param)

    start = _parse_dt(args.from_)
    end = _parse_dt(args.to_)

    with SessionLocal() as session:
        pair = session.scalars(select(CurrencyPair).where(CurrencyPair.oanda_name == args.instrument)).one_or_none()
        if pair is None:
            print(f"[error] currency_pair for {args.instrument} not found", file=sys.stderr)
            return 1
        rows = session.scalars(
            select(PriceBarM1)
            .where(PriceBarM1.pair_id == pair.id)
            .where(PriceBarM1.bar_time >= start)
            .where(PriceBarM1.bar_time < end)
            .order_by(PriceBarM1.bar_time.asc())
        ).all()
        if not rows:
            print(f"[error] no bars in [{start}, {end}) for {args.instrument}", file=sys.stderr)
            return 1
        bars = [
            PriceBar(
                pair_name=args.instrument,
                bar_time=r.bar_time,
                bid=Ohlc(open=r.open_bid, high=r.high_bid, low=r.low_bid, close=r.close_bid),
                ask=Ohlc(open=r.open_ask, high=r.high_ask, low=r.low_ask, close=r.close_ask),
                volume=r.volume,
                complete=r.complete,
            )
            for r in rows
        ]
        meta = InstrumentMeta(
            oanda_name=pair.oanda_name,
            base_currency=pair.base_currency,
            quote_currency=pair.quote_currency,
            margin_rate=pair.margin_rate,
        )

    config = GridSearchConfig(
        instrument=args.instrument,
        start=start,
        end=end,
        initial_cash=args.initial_cash,
        leverage=args.leverage,
        strategy_name=args.strategy,
        parameter_grid=parameter_grid,
        parallel=args.parallel,
    )

    result = run_grid_search(bars, meta, config)
    out_dir = write_comparison_report(result, root=Path(args.reports_dir), top_n=args.top_n)
    print(f"[done] runs={len(result.runs)} report={out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
