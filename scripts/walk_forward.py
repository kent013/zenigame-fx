"""ウォークフォワード CLI。train でグリッドサーチして best params を test で評価する。"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select

from src.backtest import WalkForwardConfig, run_walk_forward, write_walk_forward_report
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
    p = argparse.ArgumentParser(description="Walk-forward validation")
    p.add_argument("--instrument", required=True)
    p.add_argument("--from", dest="from_", required=True)
    p.add_argument("--to", dest="to_", required=True)
    p.add_argument("--initial-cash", type=Decimal, default=Decimal("1000000"))
    p.add_argument("--leverage", type=int, default=1)
    p.add_argument("--strategy", required=True, help=f"one of {list_strategies()}")
    p.add_argument("--param", action="append", default=[])
    p.add_argument("--train-days", type=int, required=True)
    p.add_argument("--test-days", type=int, required=True)
    p.add_argument("--step-days", type=int, required=True)
    p.add_argument("--mode", choices=["rolling", "anchored"], default="rolling")
    p.add_argument("--parallel", type=int, default=1)
    p.add_argument("--reports-dir", default="reports/walk-forwards")
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
            pip_size=InstrumentMeta.default_pip_size_for_quote(pair.quote_currency),
            display_precision=InstrumentMeta.default_display_precision_for_quote(pair.quote_currency),
        )

    config = WalkForwardConfig(
        instrument=args.instrument,
        start=start,
        end=end,
        initial_cash=args.initial_cash,
        leverage=args.leverage,
        strategy_name=args.strategy,
        parameter_grid=parameter_grid,
        train_days=args.train_days,
        test_days=args.test_days,
        step_days=args.step_days,
        mode=args.mode,
        parallel=args.parallel,
    )
    result = run_walk_forward(bars, meta, config)
    out_dir = write_walk_forward_report(result, root=Path(args.reports_dir))
    print(f"[done] folds={len(result.folds)} report={out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
