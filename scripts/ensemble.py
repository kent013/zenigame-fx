"""複数戦略のアンサンブル評価。--strategy LABEL:NAME:k1=v1,k2=v2 を複数指定する。"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select

from src.backtest import EnsembleConfig, EnsembleSpec, run_ensemble, write_ensemble_report
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


def _parse_spec(value: str) -> EnsembleSpec:
    # LABEL:NAME:k=v,k=v
    parts = value.split(":", 2)
    if len(parts) < 2:
        raise argparse.ArgumentTypeError(f"--strategy expects LABEL:NAME[:k=v,...] but got '{value}'")
    label, name = parts[0], parts[1]
    params: dict[str, Any] = {}
    if len(parts) == 3 and parts[2]:
        for kv in parts[2].split(","):
            if "=" not in kv:
                raise argparse.ArgumentTypeError(f"invalid param '{kv}' in '{value}'")
            k, v = kv.split("=", 1)
            params[k.strip()] = _coerce(v.strip())
    return EnsembleSpec(name=label, strategy=name, params=params)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run ensemble backtest across multiple strategies")
    p.add_argument("--instrument", required=True)
    p.add_argument("--from", dest="from_", required=True)
    p.add_argument("--to", dest="to_", required=True)
    p.add_argument("--initial-cash", type=Decimal, default=Decimal("1000000"))
    p.add_argument("--leverage", type=int, default=1)
    p.add_argument(
        "--strategy", action="append", required=True, help=f"LABEL:NAME:k=v,... (available: {list_strategies()})"
    )
    p.add_argument("--weights", default=None, help="comma-separated decimal weights, normalized")
    p.add_argument("--reports-dir", default="reports/ensembles")
    args = p.parse_args(argv)

    specs = [_parse_spec(v) for v in args.strategy]
    weights: list[Decimal] | None = None
    if args.weights:
        weights = [Decimal(t.strip()) for t in args.weights.split(",") if t.strip()]

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

    config = EnsembleConfig(
        instrument=args.instrument,
        start=start,
        end=end,
        initial_cash=args.initial_cash,
        leverage=args.leverage,
        specs=specs,
        weights=weights,
    )
    result = run_ensemble(bars, meta, config)
    out_dir = write_ensemble_report(result, root=Path(args.reports_dir))
    print(f"[done] strategies={len(result.per_strategy)} report={out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
