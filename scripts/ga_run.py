"""GA による DSL ゲノム探索 CLI。結果は reports/ga-runs/ 以下。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from src.backtest.engine import BacktestConfig
from src.broker import InstrumentMeta
from src.db.connection import SessionLocal
from src.db.models import CurrencyPair, PriceBarM1
from src.domain.price import Ohlc, PriceBar
from src.dsl import genome_to_dict
from src.ga import GaConfig, run_ga
from src.utils.time import to_utc


def _parse_dt(value: str) -> datetime:
    return to_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Evolve DSL genomes with simple GA")
    p.add_argument("--instrument", required=True)
    p.add_argument("--from", dest="from_", required=True)
    p.add_argument("--to", dest="to_", required=True)
    p.add_argument("--initial-cash", type=Decimal, default=Decimal("1000000"))
    p.add_argument("--leverage", type=int, default=1)
    p.add_argument("--population", type=int, default=30)
    p.add_argument("--generations", type=int, default=10)
    p.add_argument("--crossover-rate", type=float, default=0.7)
    p.add_argument("--mutation-rate", type=float, default=0.3)
    p.add_argument("--tournament-size", type=int, default=3)
    p.add_argument("--elite-count", type=int, default=2)
    p.add_argument("--max-depth", type=int, default=4)
    p.add_argument("--units", type=int, default=10000)
    p.add_argument("--fitness-metric", choices=["total_pnl", "sharpe", "calmar"], default="total_pnl")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--reports-dir", default="reports/ga-runs")
    args = p.parse_args(argv)

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

    bconfig = BacktestConfig(
        instrument=args.instrument,
        start=start,
        end=end,
        initial_cash=args.initial_cash,
        leverage=args.leverage,
    )
    config = GaConfig(
        population_size=args.population,
        generations=args.generations,
        crossover_rate=args.crossover_rate,
        mutation_rate=args.mutation_rate,
        tournament_size=args.tournament_size,
        elite_count=args.elite_count,
        max_depth=args.max_depth,
        units=args.units,
        fitness_metric=args.fitness_metric,
        seed=args.seed,
    )
    result = run_ga(bars, meta, bconfig, config)

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.reports_dir) / f"ga-{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = [
        f"# GA Run — {args.instrument}",
        "",
        f"**Generated**: {datetime.now(tz=UTC).isoformat()}",
        "",
        "## Config",
        "",
        f"- population: {config.population_size}",
        f"- generations: {config.generations}",
        f"- fitness: {config.fitness_metric}",
        f"- seed: {config.seed}",
        "",
        "## Best",
        "",
        f"- name: `{result.best.genome.name}`",
        f"- fitness: {result.best.fitness}",
        "",
        "## History (gen, best_fitness)",
        "",
    ]
    summary.extend(f"- gen {gen}: {fit}" for gen, fit in result.history)
    (out_dir / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    best_payload = {
        "name": result.best.genome.name,
        "fitness": str(result.best.fitness),
        "genome": genome_to_dict(result.best.genome),
    }
    (out_dir / "best_genome.json").write_text(json.dumps(best_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[done] best_fitness={result.best.fitness} report={out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
